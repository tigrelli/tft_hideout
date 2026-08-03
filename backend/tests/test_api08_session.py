import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.models import ChatLog, Patch
from services.chat_session import get_session_history, validate_session_id

SESSION_A = str(uuid.uuid4())
SESSION_B = str(uuid.uuid4())


@pytest.fixture
def seeded_chat_logs(migrated_engine: Engine) -> Engine:
    with Session(migrated_engine) as session:
        session.execute(
            insert(Patch).values(
                version="14.5",
                set_number=14,
                released_at=datetime(2026, 1, 1, tzinfo=UTC),
                is_current=True,
                detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.execute(
            insert(ChatLog).values(
                session_id=SESSION_A,
                patch_version="14.5",
                user_query="첫 질문",
                intent="comp_recommendation",
                retrieved_doc_ids=[1],
                answer="답변1",
                latency_ms=500,
                cold_start=False,
                created_at=datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
            )
        )
        session.execute(
            insert(ChatLog).values(
                session_id=SESSION_A,
                patch_version="14.5",
                user_query="후속 질문",
                intent="comp_recommendation",
                retrieved_doc_ids=[2],
                answer="답변2",
                latency_ms=400,
                cold_start=False,
                created_at=datetime(2026, 1, 2, 0, 1, tzinfo=UTC),
            )
        )
        session.execute(
            insert(ChatLog).values(
                session_id=SESSION_B,
                patch_version="14.5",
                user_query="다른 세션 질문",
                intent="item_recommendation",
                retrieved_doc_ids=[3],
                answer="답변3",
                latency_ms=300,
                cold_start=True,
                created_at=datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
            )
        )
        session.commit()
    return migrated_engine


def test_same_session_id_groups_same_conversation(seeded_chat_logs: Engine) -> None:
    with Session(seeded_chat_logs) as db:
        history = get_session_history(db, SESSION_A)

    assert [log.user_query for log in history] == ["첫 질문", "후속 질문"]


def test_new_uuid_is_isolated_from_other_sessions(seeded_chat_logs: Engine) -> None:
    other_session = str(uuid.uuid4())
    with Session(seeded_chat_logs) as db:
        history_b = get_session_history(db, SESSION_B)
        history_new = get_session_history(db, other_session)

    assert [log.user_query for log in history_b] == ["다른 세션 질문"]
    assert history_new == []


def test_validate_session_id_rejects_non_uuid() -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_session_id("not-a-uuid")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"]["code"] == "invalid_session_id"


def test_validate_session_id_accepts_uuid() -> None:
    valid = str(uuid.uuid4())
    assert validate_session_id(valid) == valid
