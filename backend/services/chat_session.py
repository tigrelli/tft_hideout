import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import ChatLog


def validate_session_id(raw: str) -> str:
    """session_id는 로그인과 무관한 UUID 대화 묶음 키다 (policies.md 4번).
    형식이 올바르지 않으면 400을 던진다."""
    try:
        return str(uuid.UUID(raw))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_session_id",
                    "message": "session_id는 UUID 형식이어야 합니다",
                }
            },
        ) from exc


def get_session_history(db: Session, session_id: str) -> list[ChatLog]:
    """동일 session_id로 기록된 chat_logs를 시간순으로 조회한다.
    존재하지 않는(아직 대화가 없는) session_id는 빈 리스트를 반환한다."""
    validated = validate_session_id(session_id)
    return list(
        db.execute(
            select(ChatLog)
            .where(ChatLog.session_id == validated)
            .order_by(ChatLog.created_at)
        ).scalars()
    )
