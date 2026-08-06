from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Augment, Champion, Comp, CompAugment, CompChampion, Item, Patch
from db.session import get_db
from main import app


@pytest.fixture
def seeded_comp_id(migrated_engine: Engine) -> int:
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
            insert(Augment).values(
                patch_version="14.5",
                name_kr="완전무장",
                name_en="Full Armory",
                tier="A",
                description="아이템 완전 무장",
                is_legend_related=False,
                riot_augment_id="TFT_Augment_FullArmory",
            )
        )
        session.execute(
            insert(Item).values(
                patch_version="14.5",
                name_kr="무한의 대검",
                name_en="Infinity Edge",
                item_type="completed",
                riot_item_id="TFT_Item_InfinityEdge",
                square_icon_url="https://raw.communitydragon.org/fake-item.png",
                components={},
                stats={},
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
        session.commit()

        comp_id = session.execute(select(Comp.id)).scalar_one()
        yone_id, ahri_id = session.execute(select(Champion.id)).scalars().all()
        augment_id = session.execute(select(Augment.id)).scalar_one()

        session.execute(
            insert(CompChampion).values(
                comp_id=comp_id,
                champion_id=yone_id,
                is_carry=True,
                recommended_items=["TFT_Item_InfinityEdge"],
                cell_x=4,
                cell_y=1,
            )
        )
        session.execute(
            insert(CompChampion).values(
                comp_id=comp_id,
                champion_id=ahri_id,
                is_carry=False,
                recommended_items=[],
            )
        )
        session.execute(
            insert(CompAugment).values(
                comp_id=comp_id, augment_id=augment_id, priority=2
            )
        )
        session.commit()
        return comp_id


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


def test_comp_detail_returns_champions_and_augments(
    client: TestClient, seeded_comp_id: int
) -> None:
    response = client.get(f"/api/v1/catalog/comps/{seeded_comp_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Reroll Yone"
    assert len(body["champions"]) == 2
    assert len(body["augments"]) == 1
    assert body["augments"][0]["priority"] == 2
    assert isinstance(body["augments"][0]["augment_id"], int)
    assert body["augments"][0]["name_kr"] == "완전무장"
    assert body["augments"][0]["name_en"] == "Full Armory"


def test_comp_detail_distinguishes_carry_from_sub_champion(
    client: TestClient, seeded_comp_id: int
) -> None:
    response = client.get(f"/api/v1/catalog/comps/{seeded_comp_id}")
    champions = response.json()["champions"]

    carry = next(c for c in champions if c["is_carry"])
    sub = next(c for c in champions if not c["is_carry"])

    assert carry["name_kr"] == "요네"
    assert carry["name_en"] == "Yone"
    assert carry["square_icon_url"] == "https://raw.communitydragon.org/fake-yone.png"
    assert carry["recommended_items"] == ["TFT_Item_InfinityEdge"]
    assert carry["recommended_item_names"] == ["무한의 대검"]
    assert carry["recommended_item_icons"] == [
        "https://raw.communitydragon.org/fake-item.png"
    ]
    assert carry["cell_x"] == 4
    assert carry["cell_y"] == 1
    assert sub["name_kr"] == "아리"
    assert sub["square_icon_url"] is None
    assert sub["recommended_items"] == []
    assert sub["recommended_item_names"] == []
    assert sub["recommended_item_icons"] == []
    # cell_x/cell_y를 지정하지 않은 챔피언(구 데이터 시뮬레이션)은 None —
    # 프론트가 이 값을 보고 실좌표/휴리스틱 배치를 분기한다(FE-14).
    assert sub["cell_x"] is None
    assert sub["cell_y"] is None


def test_comp_detail_not_found_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/catalog/comps/999999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "comp_not_found"


def test_comp_detail_item_name_falls_back_to_raw_id_when_unresolvable(
    migrated_engine: Engine, client: TestClient
) -> None:
    """items 테이블에 없는 아이템 ID(예: 매핑 누락)는 원본 ID 문자열을 그대로
    이름 자리에 반환한다(예외를 던지지 않고 방어적으로 처리)."""
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
            insert(Comp).values(
                patch_version="14.5",
                riot_comp_id="fake-comp-unresolved-item",
                name="Unresolved Item Comp",
                tier_rank="B",
                avg_place=4.5,
                play_rate=0.02,
                win_rate=0.10,
                playstyle_text="테스트",
                updated_at=datetime(2026, 1, 2, tzinfo=UTC),
            )
        )
        session.commit()
        comp_id = session.execute(
            select(Comp.id).where(Comp.riot_comp_id == "fake-comp-unresolved-item")
        ).scalar_one()
        yone_id = session.execute(select(Champion.id)).scalar_one()
        session.execute(
            insert(CompChampion).values(
                comp_id=comp_id,
                champion_id=yone_id,
                is_carry=True,
                recommended_items=["TFT_Item_DoesNotExist"],
            )
        )
        session.commit()

    response = client.get(f"/api/v1/catalog/comps/{comp_id}")
    assert response.status_code == 200
    champion = response.json()["champions"][0]
    assert champion["recommended_items"] == ["TFT_Item_DoesNotExist"]
    assert champion["recommended_item_names"] == ["TFT_Item_DoesNotExist"]
    assert champion["recommended_item_icons"] == [None]
