import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import AccountLinkEvent, LinkClickEvent
from db.session import get_db
from main import app
from services.kpi_events import record_account_link_event, record_link_click


def test_record_link_click_creates_row_with_correct_fields(
    migrated_engine: Engine,
) -> None:
    session_id = str(uuid.uuid4())
    with Session(migrated_engine) as db:
        record_link_click(
            db, session_id=session_id, chat_log_id=None, target_page="/comps/1"
        )

        row = db.execute(
            select(LinkClickEvent).where(LinkClickEvent.session_id == session_id)
        ).scalar_one()
        assert row.chat_log_id is None
        assert row.target_page == "/comps/1"
        assert row.clicked_at is not None


def test_record_account_link_event_creates_row_with_correct_fields(
    migrated_engine: Engine,
) -> None:
    with Session(migrated_engine) as db:
        record_account_link_event(
            db,
            riot_id_hash="hash-abc123",
            region="kr",
            event_type="link",
            match_id=None,
            latency_ms=250,
        )

        row = db.execute(
            select(AccountLinkEvent).where(
                AccountLinkEvent.riot_id_hash == "hash-abc123"
            )
        ).scalar_one()
        assert row.region == "kr"
        assert row.event_type == "link"
        assert row.match_id is None
        assert row.latency_ms == 250


@pytest.fixture
def client(migrated_engine: Engine) -> TestClient:
    test_session_local = sessionmaker(bind=migrated_engine)

    def override_get_db():
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_link_click_endpoint_persists_event(client: TestClient) -> None:
    session_id = str(uuid.uuid4())
    response = client.post(
        "/api/v1/chat/events/link-click",
        json={
            "session_id": session_id,
            "chat_log_id": None,
            "target_page": "/augments",
        },
    )
    assert response.status_code == 201
    assert isinstance(response.json()["id"], int)


def test_link_click_endpoint_invalid_session_id_returns_400(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/chat/events/link-click",
        json={
            "session_id": "not-a-uuid",
            "chat_log_id": None,
            "target_page": "/augments",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_session_id"
