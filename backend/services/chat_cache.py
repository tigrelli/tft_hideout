"""CHAT-08: 첫 턴 질문 캐시(Postgres `chat_answer_cache`, v1.7 — 이전 Redis 대체).
cache_key = hash(정규화 질문 + patch_version). 후속 턴(세션에 대화 이력이 있음)은
캐시 대상에서 제외한다 — 같은 문장이라도 직전 맥락(drill-down)에 따라 정답이
달라지므로, 캐싱은 대화 이력이 없는 첫 턴 질문에만 적용한다(설계서 4.4.1/4.6,
PRD 9-6). 패치가 바뀌면 cache_key 자체가 달라져 자연스럽게 무효화되고(DATA-15가
이전 patch_version 행을 별도로 정리)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from db.models import ChatAnswerCache


@dataclass(frozen=True)
class CachedAnswer:
    """캐시 hit 시 필요한 전부(2026-08-07): answer뿐 아니라 저장 시점의
    intent·근거문서id도 함께 돌려줘 chat_logs 적재(CHAT-09)에 classify_fn
    재호출 없이 그대로 쓸 수 있게 한다. intent/retrieved_doc_ids가 None이면
    이 컬럼이 없던 시절 저장된 레거시 캐시 행이라는 뜻이며, 이 경우 호출측은
    로깅을 건너뛴다(패치 갱신 시 자연 무효화되므로 곧 해소됨)."""

    answer: str
    intent: str | None
    retrieved_doc_ids: list[int] | None


def compute_cache_key(normalized_query: str, patch_version: str) -> str:
    raw = f"{normalized_query}|{patch_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached_answer(
    db: Session, normalized_query: str, patch_version: str
) -> CachedAnswer | None:
    cache_key = compute_cache_key(normalized_query, patch_version)
    row = db.execute(
        select(ChatAnswerCache).where(ChatAnswerCache.cache_key == cache_key)
    ).scalar_one_or_none()
    if row is None:
        return None
    return CachedAnswer(
        answer=row.answer,
        intent=row.intent,
        retrieved_doc_ids=row.retrieved_doc_ids,
    )


def store_answer_in_cache(
    db: Session,
    normalized_query: str,
    patch_version: str,
    answer: str,
    *,
    intent: str | None = None,
    retrieved_doc_ids: list[int] | None = None,
) -> None:
    cache_key = compute_cache_key(normalized_query, patch_version)
    stmt = pg_insert(ChatAnswerCache).values(
        cache_key=cache_key,
        patch_version=patch_version,
        answer=answer,
        intent=intent,
        retrieved_doc_ids=retrieved_doc_ids,
        created_at=datetime.now(UTC),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[ChatAnswerCache.cache_key],
        set_={
            "answer": stmt.excluded.answer,
            "intent": stmt.excluded.intent,
            "retrieved_doc_ids": stmt.excluded.retrieved_doc_ids,
            "created_at": stmt.excluded.created_at,
        },
    )
    db.execute(stmt)
    db.commit()
