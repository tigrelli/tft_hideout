"""CHAT-02: SQL 필터(현재 패치 + 의도별 doc_type) + pgvector top-k 코사인 검색.

의도별 검색 대상은 glossary.md "챗봇 의도 분류(4종, 고정)"을 그대로 따른다.
"""

from __future__ import annotations

from sqlalchemy import select
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


def hybrid_search(
    session: Session,
    intent: str,
    patch_version: str,
    query_embedding: list[float],
    top_k: int = DEFAULT_TOP_K,
) -> list[MetaDocumentEmbedding]:
    """의도에 대응하는 doc_type + 현재 patch_version으로 먼저 SQL 필터링한 뒤,
    그 안에서 pgvector 코사인 거리 오름차순(가까운 순) top-k를 반환한다."""
    doc_types = INTENT_DOC_TYPES[intent]
    stmt = (
        select(MetaDocumentEmbedding)
        .where(
            MetaDocumentEmbedding.patch_version == patch_version,
            MetaDocumentEmbedding.doc_type.in_(doc_types),
        )
        .order_by(MetaDocumentEmbedding.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    return list(session.scalars(stmt).all())
