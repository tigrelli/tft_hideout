"""CHAT-02: SQL 필터(현재 패치 + 의도별 doc_type) + pgvector top-k 코사인 검색.

의도별 검색 대상은 glossary.md "챗봇 의도 분류(4종, 고정)"을 그대로 따른다.
"""

from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, aliased

from db.models import Champion, MetaDocumentEmbedding
from services.intent_classification import (
    INTENT_AUGMENT_RECOMMENDATION,
    INTENT_COMP_RECOMMENDATION,
    INTENT_GENERAL_STRATEGY,
    INTENT_ITEM_RECOMMENDATION,
)

DEFAULT_TOP_K = 5

INTENT_DOC_TYPES: dict[str, tuple[str, ...]] = {
    INTENT_COMP_RECOMMENDATION: ("comp", "playstyle"),
    INTENT_ITEM_RECOMMENDATION: ("item_build",),
    INTENT_AUGMENT_RECOMMENDATION: ("augment",),
    # champion: 2026-08-07 PM 피드백 — "3코스트 챔피언은?"처럼 코스트/특성 등
    # 챔피언 자체를 묻는 질문이 검색 문서가 아예 없어 항상 "정보 없음"으로만
    # 답하던 문제. "챔피언"을 키워드 목록에 추가하는 방안은 "이 챔피언 빌드
    # 추천"(item_recommendation) 같은 기존 케이스와 충돌해 보류하고(intent_
    # classification.py 참고), 대신 애매한 질문은 그대로 2차 LLM 분류에 맡긴다
    # — general_strategy로 오기만 하면 아래에서 champion 문서를 검색한다.
    INTENT_GENERAL_STRATEGY: ("comp", "playstyle", "augment", "item_build", "champion"),
}

# 챔피언 코스트 목록형 질문("3코스트 챔피언은?")은 벡터 유사도 상위 몇 개로는
# 부족하다 — 코스트 하나에 최대 18명(1코스트, 2026-08-07 실측)까지 있어,
# 다른 doc_type과 top_k를 n분의 1로 나누면 1명만 뽑혀 "정보 없음"과 별
# 차이 없는 부분 답변만 나온다(2026-08-07 PM 피드백). champion 청크는
# 문장이 짧아 넉넉하게 가져와도 비용 부담이 적으므로, champion만 별도의
# 고정 top_k를 쓰고 나머지 doc_type끼리 기존 top_k를 n분의 1로 나눈다.
GENERAL_STRATEGY_CHAMPION_TOP_K = 20

# item_recommendation 후속질문("이 챔피언들을 조합에 넣을 때 주로 사용하는
# 아이템은?")이 여러 챔피언을 한꺼번에 물어볼 수 있는데, 순수 코사인 거리
# top-k만 쓰면 가장 가까운 챔피언 1~2명의 빌드만 여러 개 뽑히고 나머지
# 챔피언은 아예 안 뽑히는 문제가 확인됐다(2026-08-07 PM 피드백 — 5코스트
# 챔피언 9명을 물었는데 1명 빌드만 답변에 나옴). 챔피언별 최대
# ITEM_BUILD_PER_CHAMPION_LIMIT개까지만 허용해 여러 챔피언에 걸쳐 고르게
# 뽑히게 하고, 전체는 ITEM_RECOMMENDATION_TOP_K까지 가져온다.
ITEM_RECOMMENDATION_TOP_K = 15
ITEM_BUILD_PER_CHAMPION_LIMIT = 2

# comp 청크는 embeddings.py collect_chunks()가 doc_metadata에 "tier_rank"를
# 심어둔다(comp_rows()가 만드는 값 그대로: OP·S·A·B·C, 없으면 "unknown").
# 순수 코사인 거리만으로 정렬하면 "메타" 같은 추상 질의에서 A티어가 OP/S보다
# 먼저 뽑히는 문제가 실제로 확인돼(2026-08-07 PM 피드백 — "현재 메타는?"과
# "메타"에 서로 다른 A티어 조합만 나오고 OP/S티어인 N.O.V.A. 아칼리는 아예
# 안 뽑힘), 티어를 1차 정렬 기준으로 두고 코사인 거리는 동티어 내 2차
# 기준으로만 쓴다. tier_rank가 없는 문서(playstyle 등)는 unknown과 동일하게
# 가장 낮은 우선순위로 취급된다.
_TIER_RANK_PRIORITY = case(
    (MetaDocumentEmbedding.doc_metadata["tier_rank"].astext == "OP", 0),
    (MetaDocumentEmbedding.doc_metadata["tier_rank"].astext == "S", 1),
    (MetaDocumentEmbedding.doc_metadata["tier_rank"].astext == "A", 2),
    (MetaDocumentEmbedding.doc_metadata["tier_rank"].astext == "B", 3),
    (MetaDocumentEmbedding.doc_metadata["tier_rank"].astext == "C", 4),
    else_=5,
)


def hybrid_search(
    session: Session,
    intent: str,
    patch_version: str,
    query_embedding: list[float],
    top_k: int = DEFAULT_TOP_K,
) -> list[MetaDocumentEmbedding]:
    """의도에 대응하는 doc_type + 현재 patch_version으로 먼저 SQL 필터링한 뒤,
    그 안에서 pgvector 코사인 거리 오름차순(가까운 순) top-k를 반환한다.

    general_strategy는 doc_type 4종을 통합해 순수 벡터 유사도로만 top-k를
    뽑았는데, 실제로 "현재 메타는?" 같은 추상적 질의에서 특정 타입(관측:
    augment)이 결과를 통째로 차지해 comp가 전혀 검색되지 않는 문제가 확인됐다
    (2026-08-07 PM 피드백 — 실측: 상위 8개 전부 augment, 최상위 comp는 전체
    377개 청크 중 112위. comp_chunk_text가 숫자 위주라 짧고 추상적인 질의와
    임베딩 거리가 먼 것으로 추정). doc_type별로 균등 배분해 검색하면 특정
    타입이 결과를 독식하지 못한다 — general_strategy에서만 이 방식을 쓰고,
    나머지 의도는 doc_type이 애초에 좁아 기존 방식을 그대로 둔다."""
    doc_types = INTENT_DOC_TYPES[intent]
    if intent == INTENT_GENERAL_STRATEGY:
        return _balanced_search_by_doc_type(
            session, doc_types, patch_version, query_embedding, top_k
        )
    if intent == INTENT_ITEM_RECOMMENDATION:
        return _balanced_item_build_search(session, patch_version, query_embedding)
    stmt = (
        select(MetaDocumentEmbedding)
        .where(
            MetaDocumentEmbedding.patch_version == patch_version,
            MetaDocumentEmbedding.doc_type.in_(doc_types),
        )
        .order_by(
            _TIER_RANK_PRIORITY,
            MetaDocumentEmbedding.embedding.cosine_distance(query_embedding),
        )
        .limit(top_k)
    )
    return list(session.scalars(stmt).all())


def _search_single_doc_type(
    session: Session,
    doc_type: str,
    patch_version: str,
    query_embedding: list[float],
    count: int,
) -> list[MetaDocumentEmbedding]:
    if count <= 0:
        return []
    stmt = (
        select(MetaDocumentEmbedding)
        .where(
            MetaDocumentEmbedding.patch_version == patch_version,
            MetaDocumentEmbedding.doc_type == doc_type,
        )
        .order_by(
            _TIER_RANK_PRIORITY,
            MetaDocumentEmbedding.embedding.cosine_distance(query_embedding),
        )
        .limit(count)
    )
    return list(session.scalars(stmt).all())


def _balanced_search_by_doc_type(
    session: Session,
    doc_types: tuple[str, ...],
    patch_version: str,
    query_embedding: list[float],
    top_k: int,
) -> list[MetaDocumentEmbedding]:
    """champion은 GENERAL_STRATEGY_CHAMPION_TOP_K로 고정 배정하고(코스트
    목록형 질문 대응), 나머지 doc_type끼리 top_k를 균등 배분한다(나머지는
    앞쪽 타입부터 1개씩 더 배정 — doc_types 순서상 comp가 먼저라 "메타"
    질의에 가장 중요한 타입이 우선권을 가짐). 타입별로 각각 top-N 벡터
    검색을 수행해 합친다."""
    results: list[MetaDocumentEmbedding] = []
    if "champion" in doc_types:
        results.extend(
            _search_single_doc_type(
                session,
                "champion",
                patch_version,
                query_embedding,
                GENERAL_STRATEGY_CHAMPION_TOP_K,
            )
        )

    remaining_types = [dt for dt in doc_types if dt != "champion"]
    base, remainder = divmod(top_k, len(remaining_types))
    for index, doc_type in enumerate(remaining_types):
        count = base + (1 if index < remainder else 0)
        results.extend(
            _search_single_doc_type(
                session, doc_type, patch_version, query_embedding, count
            )
        )
    return results


def _balanced_item_build_search(
    session: Session,
    patch_version: str,
    query_embedding: list[float],
) -> list[MetaDocumentEmbedding]:
    """doc_metadata->>'champion'으로 파티션해 챔피언별 코사인 거리 순위를
    매기고, 챔피언당 ITEM_BUILD_PER_CHAMPION_LIMIT개까지만 남긴 뒤 전체를
    거리순으로 다시 정렬해 ITEM_RECOMMENDATION_TOP_K개로 자른다 — 특정
    챔피언 1~2명의 빌드가 슬롯을 독식해 다른 챔피언은 아예 안 뽑히는 문제를
    막는다(2026-08-07 PM 피드백)."""
    distance = MetaDocumentEmbedding.embedding.cosine_distance(query_embedding)
    champion_rank = func.row_number().over(
        partition_by=MetaDocumentEmbedding.doc_metadata["champion"].astext,
        order_by=distance,
    )
    ranked = (
        select(MetaDocumentEmbedding, champion_rank.label("champion_rank"))
        .where(
            MetaDocumentEmbedding.patch_version == patch_version,
            MetaDocumentEmbedding.doc_type == "item_build",
        )
        .subquery()
    )
    ranked_doc = aliased(MetaDocumentEmbedding, ranked)
    stmt = (
        select(ranked_doc)
        .where(ranked.c.champion_rank <= ITEM_BUILD_PER_CHAMPION_LIMIT)
        .order_by(ranked_doc.embedding.cosine_distance(query_embedding))
        .limit(ITEM_RECOMMENDATION_TOP_K)
    )
    return list(session.scalars(stmt).all())


def lookup_item_builds_by_champion_ids(
    session: Session,
    patch_version: str,
    champion_ids: list[int],
) -> list[MetaDocumentEmbedding]:
    """의미 검색(임베딩 유사도) 대신, 직전 답변에 이미 있는 정확한
    champion_id로 그 챔피언들의 아이템 빌드만 구조화 조회한다(2026-08-07
    PM 요청). chat_links.extract_champion_ids_from_answer가 직전 봇 답변의
    `/items/builds?champion_id={id}` 링크에서 뽑아준 id를 그대로 받는다 —
    의미 검색은 "이 챔피언들"을 근사할 뿐이라 무관한 챔피언이 섞이거나
    언급된 챔피언이 빠지는 문제가 실제로 확인됐는데(예: 5코스트 9명 질문
    후속에 다른 코스트 챔피언들이 섞여 나옴), 링크에 이미 있는 id를
    재사용하면 100% 정확하다. 정렬 기준이 없어(구조화 조회라 "가까운 순"
    개념 자체가 없음) id 오름차순(=적재 시 play_rate 내림차순 순서와
    대략 일치)으로 챔피언당 ITEM_BUILD_PER_CHAMPION_LIMIT개까지만 남긴다."""
    if not champion_ids:
        return []
    champion_names = [
        name
        for (name,) in session.execute(
            select(Champion.name_kr).where(
                Champion.patch_version == patch_version,
                Champion.id.in_(champion_ids),
            )
        )
    ]
    if not champion_names:
        return []
    champion_rank = func.row_number().over(
        partition_by=MetaDocumentEmbedding.doc_metadata["champion"].astext,
        order_by=MetaDocumentEmbedding.id,
    )
    ranked = (
        select(MetaDocumentEmbedding, champion_rank.label("champion_rank"))
        .where(
            MetaDocumentEmbedding.patch_version == patch_version,
            MetaDocumentEmbedding.doc_type == "item_build",
            MetaDocumentEmbedding.doc_metadata["champion"].astext.in_(champion_names),
        )
        .subquery()
    )
    ranked_doc = aliased(MetaDocumentEmbedding, ranked)
    stmt = select(ranked_doc).where(
        ranked.c.champion_rank <= ITEM_BUILD_PER_CHAMPION_LIMIT
    )
    return list(session.scalars(stmt).all())
