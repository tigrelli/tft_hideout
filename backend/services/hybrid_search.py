"""CHAT-02: SQL 필터(현재 패치 + 의도별 doc_type) + pgvector top-k 코사인 검색.

의도별 검색 대상은 glossary.md "챗봇 의도 분류(4종, 고정)"을 그대로 따른다.
"""

from __future__ import annotations

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from db.models import MetaDocumentEmbedding
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
    INTENT_GENERAL_STRATEGY: ("comp", "playstyle", "augment", "item_build"),
}

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


def _balanced_search_by_doc_type(
    session: Session,
    doc_types: tuple[str, ...],
    patch_version: str,
    query_embedding: list[float],
    top_k: int,
) -> list[MetaDocumentEmbedding]:
    """top_k를 doc_types 개수로 균등 배분하고(나머지는 앞쪽 타입부터 1개씩
    더 배정 — doc_types 순서상 comp가 먼저라 "메타" 질의에 가장 중요한
    타입이 우선권을 가짐), 타입별로 각각 top-N 벡터 검색을 수행해 합친다."""
    base, remainder = divmod(top_k, len(doc_types))
    results: list[MetaDocumentEmbedding] = []
    for index, doc_type in enumerate(doc_types):
        count = base + (1 if index < remainder else 0)
        if count <= 0:
            continue
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
        results.extend(session.scalars(stmt).all())
    return results
