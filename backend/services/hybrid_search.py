"""CHAT-02: SQL 필터(현재 패치 + 의도별 doc_type) + 관련도 top-k 검색.

의도별 검색 대상은 glossary.md "챗봇 의도 분류(4종, 고정)"을 그대로 따른다.

CHAT-36(2026-10-18): Hugging Face가 2026-10-07부로 무료 계정 추론 크레딧을
폐지해 BGE-M3 질의 임베딩을 더 이상 만들 수 없게 되면서(진행현황.md 2026-10-18
이력), pgvector 코사인 거리 대신 Postgres `pg_trgm` 텍스트 유사도로 관련도를
계산한다. 외부 API 호출 없이 DB 안에서 끝난다. 관련도 신호는 두 가지다.

1. 이름 점수(주 신호): 문서의 이름 키(metadata의 name/champion, 그리고
   champions/items 목록)가 질의 문자열 안에 얼마나 들어있는지 —
   `word_similarity(이름, 질의)`. 챗봇 질문 대부분은 고유명사(챔피언·아이템·
   증강·조합 이름)를 포함하고, 줄임말은 CHAT-31 사전이 이미 정식 명칭으로
   치환한 뒤 여기로 오므로 이 신호가 가장 정확하다(2026-10-18 실측: 정답 1.00,
   무관한 문서 0~0.4).
2. 본문 점수(보조 신호): 질의가 content_text에 얼마나 들어있는지 —
   `word_similarity(질의, 본문)`. "효과는", "추천" 같은 흔한 단어 때문에
   노이즈가 커서(실측: 존재하지 않는 "광폭검 효과는?"도 0.50) 가중치를 낮춰
   보조로만 쓴다. "3코스트 챔피언은?"처럼 이름 없이 속성을 묻는 질의에 쓰인다.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, cast, func, literal, or_, select
from sqlalchemy.dialects.postgresql import JSONB
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
    # item: CHAT-14 — "보석 건틀릿 아이템 효과 알려줘"처럼 특정 아이템의 효과
    # 자체를 묻는 질문에도 답할 수 있도록 item_build(빌드 조합)뿐 아니라
    # item(DATA-19 description 기반 효과 설명) 문서도 함께 검색한다. 실제 배분은
    # doc_types 튜플이 아니라 _balanced_item_build_search()가 담당한다(아래 참고).
    INTENT_ITEM_RECOMMENDATION: ("item_build", "item"),
    INTENT_AUGMENT_RECOMMENDATION: ("augment",),
    # champion: 2026-08-07 PM 피드백 — "3코스트 챔피언은?"처럼 코스트/특성 등
    # 챔피언 자체를 묻는 질문이 검색 문서가 아예 없어 항상 "정보 없음"으로만
    # 답하던 문제. "챔피언"을 키워드 목록에 추가하는 방안은 "이 챔피언 빌드
    # 추천"(item_recommendation) 같은 기존 케이스와 충돌해 보류하고(intent_
    # classification.py 참고), 대신 애매한 질문은 그대로 2차 LLM 분류에 맡긴다
    # — general_strategy로 오기만 하면 아래에서 champion 문서를 검색한다.
    # item: CHAT-14 — "보석 건틀릿 효과가 뭐야?"처럼 "아이템" 키워드 없이
    # 묻는 질문은 item_recommendation이 아니라 여기로 분류되므로 동일하게 추가.
    INTENT_GENERAL_STRATEGY: (
        "comp",
        "playstyle",
        "augment",
        "item_build",
        "champion",
        "item",
    ),
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

# CHAT-14: item_recommendation 질의에 "아이템 효과"를 묻는 부분이 섞여 있을
# 수 있어(예: "보석 건틀릿 아이템 효과 알려주고 쓰는 챔피언도 알려줘") item
# doc_type에서도 소수만 함께 가져온다. item_build 슬롯(ITEM_RECOMMENDATION_TOP_K)
# 을 줄이지 않고 별도로 추가한다 — 아이템 설명 문서는 챔피언별 빌드보다 훨씬
# 적어(패치당 최대 수백 개) 비용 부담이 적다.
ITEM_DESCRIPTION_TOP_K = 3

# comp 청크는 embeddings.py collect_chunks()가 doc_metadata에 "tier_rank"를
# 심어둔다(comp_rows()가 만드는 값 그대로: OP·S·A·B·C, 없으면 "unknown").
# 순수 코사인 거리만으로 정렬하면 "메타" 같은 추상 질의에서 A티어가 OP/S보다
# 먼저 뽑히는 문제가 실제로 확인돼(2026-08-07 PM 피드백 — "현재 메타는?"과
# "메타"에 서로 다른 A티어 조합만 나오고 OP/S티어인 N.O.V.A. 아칼리는 아예
# 안 뽑힘), 티어를 1차 정렬 기준으로 두고 코사인 거리(CHAT-36 이후 텍스트
# 관련도)는 동티어 내 2차 기준으로만 쓴다(단 CHAT-36부터 질의가 이름으로
# 지목한 문서는 티어보다 앞선다 — _order_by() 참고). tier_rank가 없는
# 문서(playstyle 등)는 unknown과 동일하게
# 가장 낮은 우선순위로 취급된다.
_TIER_RANK_PRIORITY = case(
    (MetaDocumentEmbedding.doc_metadata["tier_rank"].astext == "OP", 0),
    (MetaDocumentEmbedding.doc_metadata["tier_rank"].astext == "S", 1),
    (MetaDocumentEmbedding.doc_metadata["tier_rank"].astext == "A", 2),
    (MetaDocumentEmbedding.doc_metadata["tier_rank"].astext == "B", 3),
    (MetaDocumentEmbedding.doc_metadata["tier_rank"].astext == "C", 4),
    else_=5,
)

# CHAT-18(PM 제보 2026-08-12): DATA-17 소프트 삭제(is_active=false)로 op.gg
# 상위 10위 밖으로 밀려난 조합은 그 시점 이후 tier_rank가 갱신되지 않고
# 얼어붙는다 — 위 _TIER_RANK_PRIORITY만으로 정렬하면 오래된 "S"가 실제로는
# 지금 활성인 "A"보다 먼저 뽑히는 랭킹 왜곡이 생긴다. is_active를 tier_rank보다
# 앞선 1차 정렬 기준으로 둬 비활성 조합은 항상 활성 조합보다 뒤로 밀리게 한다.
# doc_metadata에 "is_active" 키가 없는 doc_type(augment/item_build/champion/item)은
# JSONB ->>가 NULL을 반환해 "false"와 같지 않으므로 else_(0, 정상 취급)로 빠진다
# — comp/playstyle에만 실질적으로 영향을 준다.
_ACTIVE_PRIORITY = case(
    (MetaDocumentEmbedding.doc_metadata["is_active"].astext == "false", 1),
    else_=0,
)

# CHAT-36: 관련도 계산 가중치. 목록 키(조합 구성 챔피언, 빌드 아이템)는 문서
# 자체의 이름보다 한 단계 약한 근거라(예: "아지르 조합" 질의에서 조합명에
# 아지르가 들어간 조합이 구성원으로만 아지르를 가진 조합보다 앞서야 함) 약간
# 낮춘다. 본문 점수는 위 모듈 docstring의 이유로 절반만 반영한다.
_LIST_KEY_WEIGHT = 0.9
_CONTENT_WEIGHT = 0.5

# CHAT-36: 이 값 이상이면 "질의가 이 문서를 이름으로 지목했다"고 본다. 조사가
# 붙은 이름("아리를")도 0.67 정도로 통과하고, 일부 글자만 겹치는 다른 이름
# ("공허 건틀릿" vs "보석 건틀릿 효과는?" 0.57)은 걸러진다(2026-10-18 실측).
# 정렬에서 활성 여부 다음, 티어보다 앞선 기준으로 쓴다 — 이름을 지목하지 않은
# 일반 질의("요즘 메타 조합?")는 모든 문서가 미달이라 기존과 동일하게 티어 순.
NAME_HIT_MIN_SCORE = 0.6

# CHAT-15(임계값 도입) → CHAT-36(텍스트 유사도로 재정의): top-k 안에만 들면
# 아무리 관련이 없어도 근거 문서로 채택돼, 사전(SLANG_DICTIONARY)에 없는
# 줄임말·오타 질의("죽무 효과는?")가 전혀 다른 아이템을 확신에 찬 문장으로
# 답하는 사고가 실제로 있었다(CHAT-14 PM 제보, 2026-08-09). item·augment는
# 효과 자체를 묻는 질의라 이름 지목이 정상이므로 최소 관련도를 요구한다
# (본문 점수만으로는 "광폭검 효과는?"이 0.50×가중치로 통과하지 못하도록
# NAME_HIT_MIN_SCORE와 같은 값). champion·comp 등 목록형·일반 추천 질의가
# 정상인 doc_type은 기존과 동일하게 임계값 없음.
_DOC_TYPE_MIN_RELEVANCE: dict[str, float] = {
    "item": NAME_HIT_MIN_SCORE,
    "augment": NAME_HIT_MIN_SCORE,
}


def _list_key_score(key: str, query_text: str) -> Any:
    """doc_metadata[key]가 문자열 배열(comp/playstyle의 champions, item_build의
    items)일 때, 원소 중 질의에 가장 잘 들어맞는 이름의 점수. 키가 없거나
    배열이 아니면 0."""
    values = MetaDocumentEmbedding.doc_metadata[key]
    array_or_empty = case(
        (func.jsonb_typeof(values) == "array", values),
        else_=cast(literal("[]"), JSONB),
    )
    elements = func.jsonb_array_elements_text(array_or_empty).table_valued("value")
    return func.coalesce(
        select(func.max(func.word_similarity(elements.c.value, query_text)))
        .correlate(MetaDocumentEmbedding)
        .scalar_subquery(),
        0.0,
    )


def _name_score(query_text: str) -> Any:
    """문서 이름 키가 질의 안에 얼마나 들어있는지(0~1, 모듈 docstring 1번)."""
    metadata = MetaDocumentEmbedding.doc_metadata
    return func.greatest(
        func.coalesce(func.word_similarity(metadata["name"].astext, query_text), 0.0),
        func.coalesce(
            func.word_similarity(metadata["champion"].astext, query_text), 0.0
        ),
        _list_key_score("champions", query_text) * _LIST_KEY_WEIGHT,
        _list_key_score("items", query_text) * _LIST_KEY_WEIGHT,
    )


def _relevance(query_text: str) -> Any:
    """정렬·임계값에 쓰는 관련도(0~1, 클수록 관련). 이름 점수와 가중 본문
    점수 중 큰 값."""
    content_score = func.word_similarity(query_text, MetaDocumentEmbedding.content_text)
    return func.greatest(_name_score(query_text), content_score * _CONTENT_WEIGHT)


def _name_hit_priority(relevance: Any) -> Any:
    return case((relevance >= NAME_HIT_MIN_SCORE, 0), else_=1)


def _order_by(relevance: Any) -> tuple[Any, ...]:
    """CHAT-18 활성 우선 → CHAT-36 이름 지목 우선 → 티어 → 관련도 → id(동점 시
    결과를 결정적으로 만들기 위함)."""
    return (
        _ACTIVE_PRIORITY,
        _name_hit_priority(relevance),
        _TIER_RANK_PRIORITY,
        relevance.desc(),
        MetaDocumentEmbedding.id,
    )


def hybrid_search(
    session: Session,
    intent: str,
    patch_version: str,
    query_text: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[MetaDocumentEmbedding]:
    """의도에 대응하는 doc_type + 현재 patch_version으로 먼저 SQL 필터링한 뒤,
    그 안에서 관련도(pg_trgm, 모듈 docstring 참고) 순 top-k를 반환한다.

    general_strategy는 doc_type 4종을 통합해 순수 유사도로만 top-k를
    뽑았는데, 실제로 "현재 메타는?" 같은 추상적 질의에서 특정 타입(관측:
    augment)이 결과를 통째로 차지해 comp가 전혀 검색되지 않는 문제가 확인됐다
    (2026-08-07 PM 피드백). doc_type별로 균등 배분해 검색하면 특정 타입이
    결과를 독식하지 못한다 — general_strategy에서만 이 방식을 쓰고, 나머지
    의도는 doc_type이 애초에 좁아 기존 방식을 그대로 둔다."""
    doc_types = INTENT_DOC_TYPES[intent]
    if intent == INTENT_GENERAL_STRATEGY:
        return _balanced_search_by_doc_type(
            session, doc_types, patch_version, query_text, top_k
        )
    if intent == INTENT_ITEM_RECOMMENDATION:
        return _balanced_item_build_search(session, patch_version, query_text)
    relevance = _relevance(query_text)
    stmt = (
        select(MetaDocumentEmbedding)
        .where(
            MetaDocumentEmbedding.patch_version == patch_version,
            MetaDocumentEmbedding.doc_type.in_(doc_types),
            _relevance_within_threshold(doc_types, relevance),
        )
        .order_by(*_order_by(relevance))
        .limit(top_k)
    )
    return list(session.scalars(stmt).all())


def _relevance_within_threshold(
    doc_types: tuple[str, ...] | list[str], relevance: Any
) -> Any:
    """doc_types 중 _DOC_TYPE_MIN_RELEVANCE에 임계값이 정의된 타입은 그 관련도
    이상만, 정의되지 않은 타입은 무제한으로 통과시키는 OR 조건을 만든다(여러
    doc_type을 한 SQL 쿼리로 함께 조회하는 지점 — comp_recommendation의
    ("comp","playstyle"), augment_recommendation의 ("augment",) — 에서
    doc_type마다 다른 임계값 정책을 적용하기 위함)."""
    conditions = []
    for doc_type in doc_types:
        min_relevance = _DOC_TYPE_MIN_RELEVANCE.get(doc_type)
        if min_relevance is None:
            conditions.append(MetaDocumentEmbedding.doc_type == doc_type)
        else:
            conditions.append(
                (MetaDocumentEmbedding.doc_type == doc_type)
                & (relevance >= min_relevance)
            )
    return or_(*conditions)


def _search_single_doc_type(
    session: Session,
    doc_type: str,
    patch_version: str,
    query_text: str,
    count: int,
) -> list[MetaDocumentEmbedding]:
    """doc_type이 _DOC_TYPE_MIN_RELEVANCE에 있으면 그 관련도에 못 미치는 결과는
    애초에 제외한다(호출부 변경 없이 이 함수 안에서 자동 적용 — champion처럼
    정의 안 된 doc_type은 임계값 없음)."""
    if count <= 0:
        return []
    relevance = _relevance(query_text)
    min_relevance = _DOC_TYPE_MIN_RELEVANCE.get(doc_type)
    conditions = [
        MetaDocumentEmbedding.patch_version == patch_version,
        MetaDocumentEmbedding.doc_type == doc_type,
    ]
    if min_relevance is not None:
        conditions.append(relevance >= min_relevance)
    stmt = (
        select(MetaDocumentEmbedding)
        .where(*conditions)
        .order_by(*_order_by(relevance))
        .limit(count)
    )
    return list(session.scalars(stmt).all())


def _balanced_search_by_doc_type(
    session: Session,
    doc_types: tuple[str, ...],
    patch_version: str,
    query_text: str,
    top_k: int,
) -> list[MetaDocumentEmbedding]:
    """champion은 GENERAL_STRATEGY_CHAMPION_TOP_K로 고정 배정하고(코스트
    목록형 질문 대응), 나머지 doc_type끼리 top_k를 균등 배분한다(나머지는
    앞쪽 타입부터 1개씩 더 배정 — doc_types 순서상 comp가 먼저라 "메타"
    질의에 가장 중요한 타입이 우선권을 가짐). 타입별로 각각 top-N 검색을
    수행해 합친다."""
    results: list[MetaDocumentEmbedding] = []
    if "champion" in doc_types:
        results.extend(
            _search_single_doc_type(
                session,
                "champion",
                patch_version,
                query_text,
                GENERAL_STRATEGY_CHAMPION_TOP_K,
            )
        )

    remaining_types = [dt for dt in doc_types if dt != "champion"]
    base, remainder = divmod(top_k, len(remaining_types))
    for index, doc_type in enumerate(remaining_types):
        count = base + (1 if index < remainder else 0)
        results.extend(
            _search_single_doc_type(session, doc_type, patch_version, query_text, count)
        )
    return results


def _balanced_item_build_search(
    session: Session,
    patch_version: str,
    query_text: str,
) -> list[MetaDocumentEmbedding]:
    """doc_metadata->>'champion'으로 파티션해 챔피언별 관련도 순위를 매기고,
    챔피언당 ITEM_BUILD_PER_CHAMPION_LIMIT개까지만 남긴 뒤 전체를 관련도순으로
    다시 정렬해 ITEM_RECOMMENDATION_TOP_K개로 자른다 — 특정 챔피언 1~2명의
    빌드가 슬롯을 독식해 다른 챔피언은 아예 안 뽑히는 문제를 막는다
    (2026-08-07 PM 피드백)."""
    relevance = _relevance(query_text).label("relevance")
    champion_rank = func.row_number().over(
        partition_by=MetaDocumentEmbedding.doc_metadata["champion"].astext,
        order_by=(relevance.element.desc(), MetaDocumentEmbedding.id),
    )
    ranked = (
        select(MetaDocumentEmbedding, relevance, champion_rank.label("champion_rank"))
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
        .order_by(ranked.c.relevance.desc(), ranked_doc.id)
        .limit(ITEM_RECOMMENDATION_TOP_K)
    )
    item_build_results = list(session.scalars(stmt).all())
    item_description_results = _search_single_doc_type(
        session, "item", patch_version, query_text, ITEM_DESCRIPTION_TOP_K
    )
    return item_description_results + item_build_results


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


# CHAT-15 2차 보정(2026-08-09 PM 검증 중 발견): 거리 임계값(_DOC_TYPE_MAX_DISTANCE)
# 만으로는 "그럴듯하게 지어낸 이름"이 우연히 진짜 아이템과 의미상 가까워서
# 회색지대(관측: 0.45~0.55)에 들어오는 걸 못 걸러낸다 — 실측: "광폭검 효과는?"
# (존재하지 않는 아이템)이 '포악한 절단검'과 거리 0.49로 임계값(0.5)을 통과해
# 확신에 찬 오답이 재현됨. 문자 단위 이름 겹침 비율이라는 별도 신호를 추가로
# 결합한다 — 벡터 유사도(의미)와 달리 표기 자체가 얼마나 겹치는지 보는
# 결정론적 보강 신호로, 정상 케이스(줄임말이 SLANG_DICTIONARY로 이미 정식
# 명칭으로 치환된 뒤 검색되므로 질의 문자열에 정답 이름이 그대로 들어있음)는
# 거의 항상 통과하고, 지어낸 이름은 실제 아이템명과 글자가 거의 안 겹쳐 걸러진다.
NAME_OVERLAP_DOC_TYPES = frozenset({"item", "augment"})
MIN_NAME_OVERLAP_RATIO = 0.5


def _name_overlap_ratio(name: str, query_text: str) -> float:
    """name의 공백 제외 고유 글자 중 query_text에도 등장하는 비율(0~1). name이
    비어있으면(문서 메타데이터 결손) 안전하게 0.0 — 판단 불가는 통과가 아니라
    탈락으로 처리한다."""
    name_chars = set(name) - {" "}
    if not name_chars:
        return 0.0
    query_chars = set(query_text)
    return len(name_chars & query_chars) / len(name_chars)


def filter_by_name_overlap(
    docs: list[MetaDocumentEmbedding], query_text: str
) -> list[MetaDocumentEmbedding]:
    """NAME_OVERLAP_DOC_TYPES(item/augment)에 속한 문서만 doc_metadata["name"]과
    query_text의 글자 겹침 비율이 MIN_NAME_OVERLAP_RATIO 이상일 때 남긴다.
    그 외 doc_type(comp/playstyle/champion/item_build)은 그대로 통과 — 거리
    임계값을 의도적으로 안 건 doc_type과 동일한 이유(위 hybrid_search 모듈
    주석 참고, 목록형·일반 추천 질의는 이름이 질의에 안 나오는 게 정상)."""
    kept = []
    for doc in docs:
        if doc.doc_type not in NAME_OVERLAP_DOC_TYPES:
            kept.append(doc)
            continue
        name = doc.doc_metadata.get("name", "")
        if _name_overlap_ratio(name, query_text) >= MIN_NAME_OVERLAP_RATIO:
            kept.append(doc)
    return kept
