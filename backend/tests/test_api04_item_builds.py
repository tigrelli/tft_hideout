from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Champion, ChampionItemBuild, Item, Patch
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
                square_icon_url="https://raw.communitydragon.org/fake-yone.png",
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
        session.execute(
            insert(Item).values(
                [
                    {
                        "patch_version": "14.5",
                        "riot_item_id": "bt",
                        "name_kr": "피바라기",
                        "name_en": "Bloodthirster",
                        "item_type": "combined",
                        "components": [],
                        "stats": {},
                        "square_icon_url": "https://raw.communitydragon.org/fake-bt.png",
                    },
                    {
                        "patch_version": "14.5",
                        "riot_item_id": "gs",
                        "name_kr": "거인의 결의",
                        "name_en": "Giant Slayer",
                        "item_type": "combined",
                        "components": [],
                        "stats": {},
                        "square_icon_url": None,
                    },
                    {
                        "patch_version": "14.5",
                        "riot_item_id": "ie",
                        "name_kr": "무한의 대검",
                        "name_en": "Infinity Edge",
                        "item_type": "combined",
                        "components": [],
                        "stats": {},
                        "square_icon_url": None,
                    },
                ]
            )
        )
        session.commit()
        yone_id, ahri_id = session.execute(select(Champion.id)).scalars().all()

        # Yone: play_rate 낮음/높음 2개 빌드, Ahri: 1개 빌드
        session.execute(
            insert(ChampionItemBuild).values(
                champion_id=yone_id,
                patch_version="14.5",
                item_combination=["bt", "gs", "ie"],
                play_rate=0.10,
                avg_place=4.0,
                win_rate=0.15,
            )
        )
        session.execute(
            insert(ChampionItemBuild).values(
                champion_id=yone_id,
                patch_version="14.5",
                item_combination=["ie", "gs", "lw"],
                play_rate=0.30,
                avg_place=3.8,
                win_rate=0.18,
            )
        )
        session.execute(
            insert(ChampionItemBuild).values(
                champion_id=ahri_id,
                patch_version="14.5",
                item_combination=["bt"],
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


def test_item_builds_include_champion_and_item_display_names(
    client: TestClient, seeded_champion_ids: tuple[int, int]
) -> None:
    yone_id, _ahri_id = seeded_champion_ids
    response = client.get(
        f"/api/v1/catalog/items/builds?patch=14.5&champion_id={yone_id}"
    )
    body = response.json()
    build = next(
        b for b in body["builds"] if b["item_combination"] == ["bt", "gs", "ie"]
    )
    assert build["champion_name_kr"] == "요네"
    assert build["champion_name_en"] == "Yone"
    assert (
        build["champion_square_icon_url"]
        == "https://raw.communitydragon.org/fake-yone.png"
    )
    assert build["item_combination_names"] == ["피바라기", "거인의 결의", "무한의 대검"]
    assert build["item_combination_icons"] == [
        "https://raw.communitydragon.org/fake-bt.png",
        None,
        None,
    ]


def test_item_builds_unknown_item_id_falls_back_to_raw_id(
    client: TestClient, seeded_champion_ids: tuple[int, int]
) -> None:
    yone_id, _ahri_id = seeded_champion_ids
    response = client.get(
        f"/api/v1/catalog/items/builds?patch=14.5&champion_id={yone_id}"
    )
    body = response.json()
    build = next(b for b in body["builds"] if "lw" in b["item_combination"])
    # "lw"는 fixture에 등록하지 않아 items 테이블에 없음 -> 원본 id로 폴백
    assert build["item_combination_names"] == ["무한의 대검", "거인의 결의", "lw"]
    assert build["item_combination_icons"] == [None, None, None]


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


def test_item_builds_capped_at_top_n_per_champion(
    client: TestClient,
    seeded_champion_ids: tuple[int, int],
    migrated_engine: Engine,
) -> None:
    # 실제 op.gg 데이터는 챔피언 1명당 수백~1700개 조합까지 나옴(2026-08-05 로컬
    # 실배치 검증) — play_rate 상위 TOP_BUILDS_PER_CHAMPION(10)개만 반환돼야 한다.
    yone_id, _ahri_id = seeded_champion_ids
    with Session(migrated_engine) as session:
        session.execute(
            insert(ChampionItemBuild),
            [
                {
                    "champion_id": yone_id,
                    "patch_version": "14.5",
                    "item_combination": [f"extra{i}"],
                    "play_rate": 0.5 + i * 0.001,
                    "avg_place": 4.0,
                    "win_rate": 0.1,
                }
                for i in range(15)
            ],
        )
        session.commit()

    response = client.get(
        f"/api/v1/catalog/items/builds?patch=14.5&champion_id={yone_id}"
    )
    builds = response.json()["builds"]
    assert len(builds) == 10
    play_rates = [b["play_rate"] for b in builds]
    assert play_rates == sorted(play_rates, reverse=True)
    assert play_rates[0] == pytest.approx(0.5 + 14 * 0.001)


def test_item_builds_caps_per_champion_when_no_champion_filter(
    client: TestClient,
    seeded_champion_ids: tuple[int, int],
    migrated_engine: Engine,
) -> None:
    yone_id, ahri_id = seeded_champion_ids
    with Session(migrated_engine) as session:
        session.execute(
            insert(ChampionItemBuild),
            [
                {
                    "champion_id": yone_id,
                    "patch_version": "14.5",
                    "item_combination": [f"extra{i}"],
                    "play_rate": 0.5 + i * 0.001,
                    "avg_place": 4.0,
                    "win_rate": 0.1,
                }
                for i in range(15)
            ],
        )
        session.commit()

    response = client.get("/api/v1/catalog/items/builds?patch=14.5")
    builds = response.json()["builds"]
    from collections import Counter

    per_champion = Counter(b["champion_id"] for b in builds)
    assert per_champion[yone_id] == 10
    assert per_champion[ahri_id] == 1
