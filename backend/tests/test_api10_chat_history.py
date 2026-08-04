import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import ChatLog, Patch
from db.session import get_db
from main import app
from services.chat_session import RECENT_TURNS_LIMIT, get_session_history

SESSION_ID = str(uuid.uuid4())


def _insert_turn(session: Session, *, query: str, answer: str, minute: int) -> None:
    session.execute(
        insert(ChatLog).values(
            session_id=SESSION_ID,
            patch_version="14.5",
            user_query=query,
            intent="comp_recommendation",
            retrieved_doc_ids=[1],
            answer=answer,
            latency_ms=300,
            cold_start=False,
            created_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minute),
        )
    )


@pytest.fixture
def four_turn_session(migrated_engine: Engine) -> Engine:
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
        for i, (q, a) in enumerate(
            [
                ("1턴 질문", "1턴 답변"),
                ("2턴 질문", "2턴 답변"),
                ("3턴 질문", "3턴 답변"),
                ("4턴 질문", "4턴 답변"),
            ]
        ):
            _insert_turn(session, query=q, answer=a, minute=i)
        session.commit()
    return migrated_engine


def test_get_session_history_with_limit_returns_only_recent_turns_in_order(
    four_turn_session: Engine,
) -> None:
    with Session(four_turn_session) as db:
        history = get_session_history(db, SESSION_ID, limit=RECENT_TURNS_LIMIT)

    assert [log.user_query for log in history] == ["2턴 질문", "3턴 질문", "4턴 질문"]


def test_get_session_history_without_limit_returns_all_turns(
    four_turn_session: Engine,
) -> None:
    with Session(four_turn_session) as db:
        history = get_session_history(db, SESSION_ID)

    assert len(history) == 4


@pytest.fixture
def client(four_turn_session: Engine) -> TestClient:
    test_session_local = sessionmaker(bind=four_turn_session)

    def override_get_db():
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_history_endpoint_returns_only_recent_3_turns(client: TestClient) -> None:
    response = client.get(f"/api/v1/chat/session/{SESSION_ID}/history")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == SESSION_ID
    assert [turn["user_query"] for turn in body["turns"]] == [
        "2턴 질문",
        "3턴 질문",
        "4턴 질문",
    ]


def test_history_endpoint_unknown_session_returns_empty_turns(
    client: TestClient,
) -> None:
    response = client.get(f"/api/v1/chat/session/{uuid.uuid4()}/history")

    assert response.status_code == 200
    assert response.json()["turns"] == []


def test_history_endpoint_invalid_session_id_returns_400(client: TestClient) -> None:
    response = client.get("/api/v1/chat/session/not-a-uuid/history")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_session_id"
