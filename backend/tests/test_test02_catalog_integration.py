"""TEST-02: catalog API 단위/통합 테스트 — API-02~06 각 TASK가 이미 자기
엔드포인트별 단위 테스트를 갖고 있어(test_api0{2,3,4,5,6}_*.py), 여기서는
그 파일들이 다루지 않는 두 가지 교차 엔드포인트 관점만 다룬다.

1. `routers/catalog.py`의 `_resolve_patch()`는 tierlist(API-02)·
   item_builds(API-04)·augments(API-05) 3개 엔드포인트가 공유하는데,
   "patches 테이블이 완전히 비어 있을 때"(no_current_patch) 분기는
   API-06 자신의 엔드포인트(GET /patches/current, 별도 inline 체크)
   테스트에서만 검증돼 있었다 — 정작 이 공유 헬퍼를 쓰는 3개 엔드포인트
   자신은 이 분기가 한 번도 실행된 적이 없었다.
2. invalid_patch(400) 에러 응답 포맷이 3개 엔드포인트에서 동일한지.
3. 5개 엔드포인트를 하나의 공유 시드 데이터로 순서대로 호출해 실제
   서비스 흐름(티어리스트 → 조합 상세 → 아이템 빌드 → 증강체 → 현재 패치)이
   함께 잘 맞물리는지 스모크로 확인한다.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import (
    Augment,
    Champion,
    ChampionItemBuild,
    Comp,
    CompAugment,
    CompChampion,
    Item,
    Patch,
)
from db.session import get_db
from main import app

RESOLVE_PATCH_ENDPOINTS = [
    "/api/v1/catalog/tierlist",
    "/api/v1/catalog/items/builds",
    "/api/v1/catalog/augments",
]


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


# ---- 1. 공유 _resolve_patch() — 패치가 하나도 없을 때 404 -----------------------


@pytest.mark.parametrize("path", RESOLVE_PATCH_ENDPOINTS)
def test_no_current_patch_returns_404_across_resolve_patch_endpoints(
    client: TestClient, path: str
) -> None:
    response = client.get(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_current_patch"


# ---- 2. invalid_patch(400) 에러 포맷 일관성 ------------------------------------


@pytest.mark.parametrize("path", RESOLVE_PATCH_ENDPOINTS)
def test_invalid_patch_format_error_shape_consistent_across_endpoints(
    client: TestClient, path: str
) -> None:
    response = client.get(path, params={"patch": "not-a-patch"})
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "invalid_patch"
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]


# ---- 3. 5개 엔드포인트 통합 스모크 ----------------------------------------------


@pytest.fixture
def shared_seed(migrated_engine: Engine) -> Engine:
    with Session(migrated_engine) as session:
        session.execute(
            insert(Patch).values(
                version="17.8",
                set_number=17,
                released_at=datetime(2026, 1, 1, tzinfo=UTC),
                is_current=True,
                detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.execute(
            insert(Champion).values(
                patch_version="17.8",
                riot_champion_id="TFT17_Yone",
                name_kr="요네",
                name_en="Yone",
                cost=4,
                square_icon_url=None,
            )
        )
        session.execute(
            insert(Item).values(
                patch_version="17.8",
                riot_item_id="bt",
                name_kr="피바라기",
                name_en="Bloodthirster",
                item_type="combined",
                components=[],
                stats={},
                square_icon_url=None,
            )
        )
        session.execute(
            insert(Augment).values(
                patch_version="17.8",
                riot_augment_id="TFT17_Augment_Mock",
                name_kr="모의 증강체",
                name_en="Mock Augment",
                tier="gold",
                description="테스트용 설명",
                is_legend_related=False,
                win_rate=0.53,
                image_url=None,
            )
        )
        session.execute(
            insert(Comp).values(
                patch_version="17.8",
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

        champion_id = session.execute(select(Champion.id)).scalar_one()
        comp_id = session.execute(select(Comp.id)).scalar_one()
        augment_id = session.execute(select(Augment.id)).scalar_one()

        session.execute(
            insert(CompChampion).values(
                comp_id=comp_id,
                champion_id=champion_id,
                is_carry=True,
                recommended_items=["bt"],
            )
        )
        session.execute(
            insert(CompAugment).values(
                comp_id=comp_id, augment_id=augment_id, priority=1
            )
        )
        session.execute(
            insert(ChampionItemBuild).values(
                champion_id=champion_id,
                patch_version="17.8",
                item_combination=["bt"],
                play_rate=0.10,
                avg_place=4.0,
                win_rate=0.15,
            )
        )
        session.commit()
        return {"comp_id": comp_id}  # type: ignore[return-value]


def test_all_catalog_endpoints_work_together_against_shared_seed(
    client: TestClient, shared_seed: dict[str, int]
) -> None:
    tierlist = client.get("/api/v1/catalog/tierlist")
    assert tierlist.status_code == 200
    tierlist_body = tierlist.json()
    assert tierlist_body["patch_version"] == "17.8"
    assert [c["name"] for c in tierlist_body["comps"]] == ["Reroll Yone"]

    comp_detail = client.get(f"/api/v1/catalog/comps/{shared_seed['comp_id']}")
    assert comp_detail.status_code == 200
    comp_body = comp_detail.json()
    assert comp_body["patch_version"] == "17.8"
    assert [c["name_kr"] for c in comp_body["champions"]] == ["요네"]
    assert [a["name_kr"] for a in comp_body["augments"]] == ["모의 증강체"]

    item_builds = client.get("/api/v1/catalog/items/builds")
    assert item_builds.status_code == 200
    assert item_builds.json()["patch_version"] == "17.8"
    assert len(item_builds.json()["builds"]) == 1

    augments = client.get("/api/v1/catalog/augments")
    assert augments.status_code == 200
    augments_body = augments.json()
    assert augments_body["patch_version"] == "17.8"
    assert augments_body["augments"][0]["win_rate"] == 0.53
    assert augments_body["augments"][0]["related_comp_ids"] == [shared_seed["comp_id"]]

    current_patch = client.get("/api/v1/catalog/patches/current")
    assert current_patch.status_code == 200
    assert current_patch.json()["version"] == "17.8"
