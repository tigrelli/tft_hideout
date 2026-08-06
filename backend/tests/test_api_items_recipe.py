from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Item, Patch
from db.session import get_db
from main import app


@pytest.fixture
def seeded_items(migrated_engine: Engine) -> None:
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
            insert(Item).values(
                [
                    {
                        "patch_version": "14.5",
                        "riot_item_id": "TFT_Item_BFSword",
                        "name_kr": "장검",
                        "name_en": "B.F. Sword",
                        "item_type": "component",
                        "components": [],
                        "stats": {},
                        "square_icon_url": "https://x.invalid/bf.png",
                    },
                    {
                        "patch_version": "14.5",
                        "riot_item_id": "TFT_Item_SparringGloves",
                        "name_kr": "장갑",
                        "name_en": "Sparring Gloves",
                        "item_type": "component",
                        "components": [],
                        "stats": {},
                        "square_icon_url": None,
                    },
                    {
                        "patch_version": "14.5",
                        "riot_item_id": "TFT_Item_InfinityEdge",
                        "name_kr": "무한의 대검",
                        "name_en": "Infinity Edge",
                        "item_type": "core",
                        "components": ["TFT_Item_BFSword", "TFT_Item_SparringGloves"],
                        "stats": {},
                        "square_icon_url": "https://x.invalid/ie.png",
                    },
                ]
            )
        )
        session.commit()


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


def test_items_resolves_component_names_and_icons(
    client: TestClient, seeded_items: None
) -> None:
    response = client.get("/api/v1/catalog/items?patch=14.5")
    assert response.status_code == 200
    body = response.json()

    ie = next(i for i in body["items"] if i["riot_item_id"] == "TFT_Item_InfinityEdge")
    assert ie["name_kr"] == "무한의 대검"
    assert ie["components"] == [
        {
            "riot_item_id": "TFT_Item_BFSword",
            "name_kr": "장검",
            "square_icon_url": "https://x.invalid/bf.png",
        },
        {
            "riot_item_id": "TFT_Item_SparringGloves",
            "name_kr": "장갑",
            "square_icon_url": None,
        },
    ]


def test_items_base_component_has_empty_components(
    client: TestClient, seeded_items: None
) -> None:
    response = client.get("/api/v1/catalog/items?patch=14.5")
    body = response.json()

    bf = next(i for i in body["items"] if i["riot_item_id"] == "TFT_Item_BFSword")
    assert bf["components"] == []
