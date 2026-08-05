"""API-05 pytest(TEST-00 시나리오 그대로 옮김, docs/test-scenarios.md API-05):
is_legend_related=true 증강체는 응답에서 win_rate가 항상 null이어야 한다
(policies.md 1번, Legend 계열 증강체 승률 비노출)."""

import re
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from db.models import Augment, Comp, CompAugment, Patch
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


def _seed_patch(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(Patch).values(
                version="17.8",
                set_number=17,
                released_at=datetime(2026, 1, 1, tzinfo=UTC),
                is_current=True,
                detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )


def _seed_augment(engine: Engine, **overrides) -> None:
    values = {
        "patch_version": "17.8",
        "riot_augment_id": "TFT17_Augment_Mock",
        "name_kr": "모의 증강체",
        "name_en": "Mock Augment",
        "tier": "gold",
        "description": "테스트용 설명",
        "is_legend_related": False,
        "win_rate": None,
    }
    values.update(overrides)
    with engine.begin() as conn:
        conn.execute(insert(Augment).values(**values))


# ---- TEST-00 API-05 #1: 일반 증강체는 win_rate 그대로 노출 -----------------------


def test_normal_augment_exposes_win_rate(
    client: TestClient, migrated_engine: Engine
) -> None:
    _seed_patch(migrated_engine)
    _seed_augment(
        migrated_engine,
        riot_augment_id="TFT17_Augment_Normal",
        is_legend_related=False,
        win_rate=0.42,
    )

    response = client.get("/api/v1/catalog/augments?patch=17.8")

    assert response.status_code == 200
    augments = response.json()["augments"]
    assert len(augments) == 1
    assert augments[0]["win_rate"] == 0.42


# ---- TEST-00 API-05 #2: Legend 계열 증강체는 win_rate가 null ---------------------


def test_legend_related_augment_masks_win_rate_to_null(
    client: TestClient, migrated_engine: Engine
) -> None:
    _seed_patch(migrated_engine)
    _seed_augment(
        migrated_engine,
        riot_augment_id="TFT17_Augment_Legend",
        is_legend_related=True,
        win_rate=0.55,
    )

    response = client.get("/api/v1/catalog/augments?patch=17.8")

    assert response.status_code == 200
    augments = response.json()["augments"]
    assert len(augments) == 1
    assert "win_rate" in augments[0]  # 키 자체는 생략되지 않고 명시적으로 존재
    assert augments[0]["win_rate"] is None


# ---- TEST-00 API-05 #3: 목록에 혼재해도 legend 항목만 마스킹 ---------------------


def test_mixed_list_masks_only_legend_related_entries(
    client: TestClient, migrated_engine: Engine
) -> None:
    _seed_patch(migrated_engine)
    _seed_augment(
        migrated_engine,
        riot_augment_id="TFT17_Augment_Legend",
        is_legend_related=True,
        win_rate=0.55,
    )
    _seed_augment(
        migrated_engine,
        riot_augment_id="TFT17_Augment_Normal",
        is_legend_related=False,
        win_rate=0.42,
    )

    response = client.get("/api/v1/catalog/augments?patch=17.8")

    assert response.status_code == 200
    win_rate_by_legend_flag = {
        a["is_legend_related"]: a["win_rate"] for a in response.json()["augments"]
    }
    assert win_rate_by_legend_flag[True] is None
    assert win_rate_by_legend_flag[False] == 0.42


# ---- TEST-00 API-05 #4: 직렬화된 JSON에도 승률 숫자 패턴이 남지 않아야 함 --------


def test_legend_related_entry_json_has_no_numeric_leak(
    client: TestClient, migrated_engine: Engine
) -> None:
    _seed_patch(migrated_engine)
    _seed_augment(
        migrated_engine,
        riot_augment_id="TFT17_Augment_Legend",
        is_legend_related=True,
        win_rate=0.55,
    )

    response = client.get("/api/v1/catalog/augments?patch=17.8")
    raw = response.text

    # win_rate 키의 원문 값(다음 콤마/중괄호 전까지)을 그대로 추출 — id 등 다른
    # 필드의 숫자와 섞이지 않도록 win_rate 필드 자체의 직렬화 값만 검사한다.
    match = re.search(r'"win_rate"\s*:\s*([^,}]+)', raw)
    assert match is not None
    win_rate_raw_value = match.group(1).strip()

    assert win_rate_raw_value == "null"
    assert re.search(r"\d+(\.\d+)?%?", win_rate_raw_value) is None


# ---- 기본 동작: patch/tier 필터, 패치 미지정 시 현재 패치 ------------------------


def test_augments_filtered_by_tier(client: TestClient, migrated_engine: Engine) -> None:
    _seed_patch(migrated_engine)
    _seed_augment(migrated_engine, riot_augment_id="TFT17_Augment_Gold", tier="gold")
    _seed_augment(migrated_engine, riot_augment_id="TFT17_Augment_Prism", tier="prism")

    response = client.get("/api/v1/catalog/augments?patch=17.8&tier=prism")

    assert response.status_code == 200
    augments = response.json()["augments"]
    assert len(augments) == 1
    assert augments[0]["tier"] == "prism"


def test_augments_invalid_tier_returns_400(
    client: TestClient, migrated_engine: Engine
) -> None:
    _seed_patch(migrated_engine)

    response = client.get("/api/v1/catalog/augments?patch=17.8&tier=platinum")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_tier"


def test_augments_without_patch_uses_current_patch(
    client: TestClient, migrated_engine: Engine
) -> None:
    _seed_patch(migrated_engine)
    _seed_augment(migrated_engine)

    response = client.get("/api/v1/catalog/augments")

    assert response.status_code == 200
    body = response.json()
    assert body["patch_version"] == "17.8"
    assert len(body["augments"]) == 1


# ---- 화면설계서 2.4 related-comps-link: comp_augments 조인 -----------------------


def test_augment_without_comp_augments_has_empty_related_comp_ids(
    client: TestClient, migrated_engine: Engine
) -> None:
    _seed_patch(migrated_engine)
    _seed_augment(migrated_engine)

    response = client.get("/api/v1/catalog/augments?patch=17.8")

    assert response.status_code == 200
    assert response.json()["augments"][0]["related_comp_ids"] == []


def test_augment_related_comp_ids_from_comp_augments(
    client: TestClient, migrated_engine: Engine
) -> None:
    _seed_patch(migrated_engine)
    _seed_augment(migrated_engine, riot_augment_id="TFT17_Augment_A")
    _seed_augment(migrated_engine, riot_augment_id="TFT17_Augment_B")

    with migrated_engine.begin() as conn:
        augment_ids = [
            row[0]
            for row in conn.execute(
                Augment.__table__.select().order_by(Augment.id)
            ).fetchall()
        ]
        conn.execute(
            insert(Comp).values(
                patch_version="17.8",
                riot_comp_id="TFT17_Comp_Mock",
                name="모의 조합",
                tier_rank="S",
                avg_place=4.0,
                play_rate=0.1,
                win_rate=0.2,
                playstyle_text="테스트",
                updated_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        comp_id = conn.execute(Comp.__table__.select()).fetchone()[0]
        conn.execute(
            insert(CompAugment).values(
                comp_id=comp_id, augment_id=augment_ids[0], priority=1
            )
        )

    response = client.get("/api/v1/catalog/augments?patch=17.8")

    augments_by_id = {a["id"]: a for a in response.json()["augments"]}
    assert augments_by_id[augment_ids[0]]["related_comp_ids"] == [comp_id]
    assert augments_by_id[augment_ids[1]]["related_comp_ids"] == []
