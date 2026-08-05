from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Comp, Patch
from db.session import get_db
from main import app


@pytest.fixture
def seeded_engine(migrated_engine: Engine) -> Engine:
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
            insert(Patch).values(
                version="14.4",
                set_number=14,
                released_at=datetime(2025, 12, 1, tzinfo=UTC),
                is_current=False,
                detected_at=datetime(2025, 12, 1, tzinfo=UTC),
            )
        )
        session.execute(
            insert(Comp).values(
                patch_version="14.5",
                riot_comp_id="fake-comp-reroll-yone",
                name="Reroll Yone",
                tier_rank="S",
                avg_place=4.2,
                play_rate=0.05,
                win_rate=0.12,
                playstyle_text="8레벨 리롤",
                updated_at=datetime(2026, 1, 2, tzinfo=UTC),
            )
        )
        session.execute(
            insert(Comp).values(
                patch_version="14.4",
                riot_comp_id="fake-comp-old-patch",
                name="Old Patch Comp",
                tier_rank="A",
                avg_place=4.5,
                play_rate=0.03,
                win_rate=0.10,
                playstyle_text="구버전 조합",
                updated_at=datetime(2025, 12, 2, tzinfo=UTC),
            )
        )
        session.commit()
    return migrated_engine


@pytest.fixture
def client(seeded_engine: Engine) -> TestClient:
    test_session_local = sessionmaker(bind=seeded_engine)

    def override_get_db():
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_tierlist_filters_by_patch(client: TestClient) -> None:
    response = client.get("/api/v1/catalog/tierlist?patch=14.5")
    assert response.status_code == 200
    body = response.json()
    assert body["patch_version"] == "14.5"
    assert [c["name"] for c in body["comps"]] == ["Reroll Yone"]


def test_tierlist_defaults_to_current_patch_when_omitted(client: TestClient) -> None:
    response = client.get("/api/v1/catalog/tierlist")
    assert response.status_code == 200
    body = response.json()
    assert body["patch_version"] == "14.5"
    assert [c["name"] for c in body["comps"]] == ["Reroll Yone"]


def test_tierlist_invalid_patch_format_returns_400(client: TestClient) -> None:
    response = client.get("/api/v1/catalog/tierlist?patch=not-a-patch")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_patch"
