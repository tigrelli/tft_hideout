from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Patch
from db.session import get_db
from main import app


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


def _seed_patches(engine: Engine) -> None:
    with Session(engine) as session:
        session.execute(
            insert(Patch).values(
                version="14.4",
                set_number=14,
                released_at=datetime(2025, 12, 1, tzinfo=UTC),
                is_current=False,
                detected_at=datetime(2025, 12, 1, tzinfo=UTC),
            )
        )
        session.execute(
            insert(Patch).values(
                version="14.5",
                set_number=14,
                released_at=datetime(2026, 1, 1, tzinfo=UTC),
                is_current=True,
                detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.commit()


def test_current_patch_returns_only_the_is_current_one(
    client: TestClient, migrated_engine: Engine
) -> None:
    _seed_patches(migrated_engine)

    response = client.get("/api/v1/catalog/patches/current")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "14.5"
    assert body["set_number"] == 14


def test_current_patch_returns_404_when_none_set(
    client: TestClient, migrated_engine: Engine
) -> None:
    response = client.get("/api/v1/catalog/patches/current")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_current_patch"
