from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Champion, ChampionItemBuild, Patch
from db.session import get_db
from main import app


@pytest.fixture
def seeded_champion_ids(migrated_engine: Engine) -> tuple[int, int]:
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
            insert(Champion).values(
                patch_version="14.5",
                riot_champion_id="TFT14_Yone",
                name_kr="요네",
                name_en="Yone",
                cost=4,
            )
        )
        session.execute(
            insert(Champion).values(
                patch_version="14.5",
                riot_champion_id="TFT14_Ahri",
                name_kr="아리",
                name_en="Ahri",
                cost=1,
            )
        )
        session.commit()
        yone_id, ahri_id = session.execute(select(Champion.id)).scalars().all()

        # Yone: play_rate 낮음/높음 2개 빌드, Ahri: 1개 빌드
        session.execute(
            insert(ChampionItemBuild).values(
                champion_id=yone_id,
                patch_version="14.5",
                item_combination={"items": ["bt", "gs", "ie"]},
                play_rate=0.10,
                avg_place=4.0,
                win_rate=0.15,
            )
        )
        session.execute(
            insert(ChampionItemBuild).values(
                champion_id=yone_id,
                patch_version="14.5",
                item_combination={"items": ["ie", "gs", "lw"]},
                play_rate=0.30,
                avg_place=3.8,
                win_rate=0.18,
            )
        )
        session.execute(
            insert(ChampionItemBuild).values(
                champion_id=ahri_id,
                patch_version="14.5",
                item_combination={"items": ["ludens"]},
                play_rate=0.20,
                avg_place=4.2,
                win_rate=0.11,
            )
        )
        session.commit()
        return yone_id, ahri_id


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


def test_item_builds_without_champion_filter_returns_all(
    client: TestClient, seeded_champion_ids: tuple[int, int]
) -> None:
    response = client.get("/api/v1/catalog/items/builds?patch=14.5")
    assert response.status_code == 200
    body = response.json()
    assert body["champion_id"] is None
    assert len(body["builds"]) == 3


def test_item_builds_with_champion_filter_returns_only_that_champion(
    client: TestClient, seeded_champion_ids: tuple[int, int]
) -> None:
    yone_id, _ahri_id = seeded_champion_ids
    response = client.get(
        f"/api/v1/catalog/items/builds?patch=14.5&champion_id={yone_id}"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["champion_id"] == yone_id
    assert len(body["builds"]) == 2
    assert all(b["champion_id"] == yone_id for b in body["builds"])


def test_item_builds_sorted_by_play_rate_descending(
    client: TestClient, seeded_champion_ids: tuple[int, int]
) -> None:
    yone_id, _ahri_id = seeded_champion_ids
    response = client.get(
        f"/api/v1/catalog/items/builds?patch=14.5&champion_id={yone_id}"
    )
    play_rates = [b["play_rate"] for b in response.json()["builds"]]
    assert play_rates == sorted(play_rates, reverse=True)
