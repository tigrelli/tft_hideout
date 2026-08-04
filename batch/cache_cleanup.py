"""DATA-15: 배치(패치 승격)가 완료된 뒤 chat_answer_cache에서 이전
patch_version 행을 삭제한다(Postgres DELETE, v1.7 — 이전 Redis 키 만료 대체).

puuid_cache는 expires_at 기반 자체 TTL이라 이 배치의 범위가 아니다(schema.md,
db/models.py PuuidCache 참고 — WBS DATA-15 TASK 설명·완료기준 모두
chat_answer_cache만 명시).
"""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

import db_session as batch_db

models = batch_db.models


def delete_stale_chat_answer_cache(session: Session, current_patch_version: str) -> int:
    """patch_version이 현재 패치와 다른 chat_answer_cache 행을 전부 삭제하고
    삭제된 행 수를 반환한다."""
    result = session.execute(
        delete(models.ChatAnswerCache).where(
            models.ChatAnswerCache.patch_version != current_patch_version
        )
    )
    return result.rowcount
