"""DATA-10 pytest: 동일 엔티티 재수집 시 upsert(덮어쓰기 아님) + 신규 행
patch_version 태깅을 검증한다. 순수 변환 함수는 합성 fixture로, upsert 동작은
실제 마이그레이션이 적용된 테스트 DB(docker-compose.test.yml)로 검증한다
(policies.md 12번 — 이 테스트는 DB가 필요해 실 API 호출 정책과는 무관).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db_session import models
from normalize import (
    augment_rows,
    build_playstyle_text,
    cdragon_asset_url,
    champion_item_build_rows,
    champion_rows,
    clean_augment_description,
    comp_champion_rows,
    comp_rows,
    ensure_patch,
    item_rows,
    replace_champion_item_builds,
    trait_rows,
    upsert_augments,
    upsert_champions,
    upsert_comp_champions,
    upsert_comps,
    upsert_items,
    upsert_traits,
)

# ---- 합성 fixture(DATA-05/06 스파이크 구조 기반, 값은 전부 가짜) ----------------

CDRAGON_KO = {
    "setData": [
        {
            "number": 17,
            "mutator": "TFTSet17",
            "champions": [
                {
                    "apiName": "TFT17_FakeAkali",
                    "name": "가짜 아칼리",
                    "cost": 4,
                    "squareIcon": "ASSETS/Characters/TFT17_FakeAkali/Icon.tex",
                },
                {"apiName": "TFT17_FakeOnlyKo", "name": "한국어만", "cost": 1},
                {"apiName": "TFT17_FakeNoIcon", "name": "아이콘 없음", "cost": 2},
            ],
            "traits": [
                {
                    "apiName": "TFT17_FakeTrait",
                    "name": "가짜 특성",
                    "effects": [{"minUnits": 1, "maxUnits": 3, "style": 1}],
                }
            ],
        }
    ]
}
CDRAGON_EN = {
    "setData": [
        {
            "number": 17,
            "mutator": "TFTSet17",
            "champions": [
                {"apiName": "TFT17_FakeAkali", "name": "FakeAkali", "cost": 4},
                {"apiName": "TFT17_FakeNoIcon", "name": "FakeNoIcon", "cost": 2},
            ],
            "traits": [
                {"apiName": "TFT17_FakeTrait", "name": "FakeTrait", "effects": []}
            ],
        }
    ]
}

ITEMS_KO = {
    "data": [
        {
            "apiName": "TFT_Item_FakeSword",
            "name": "가짜 검",
            "category": "core",
            "composition": ["TFT_Item_FakeA", "TFT_Item_FakeB"],
            "effects": {"AP": 10},
        }
    ]
}
ITEMS_EN = {
    "data": [{"apiName": "TFT_Item_FakeSword", "name": "Fake Sword"}],
}

AUGMENTS_KO = {
    "headers": ["apiName", "desc", "name", "tier", "imageUrl"],
    "rows": [
        ["TFT17_Augment_Fake", "가짜 설명", "가짜 증강체", "gold", "https://x.invalid"]
    ],
}
AUGMENTS_EN = {
    "headers": ["apiName", "desc", "name", "tier", "imageUrl"],
    "rows": [
        ["TFT17_Augment_Fake", "fake desc", "Fake Augment", "gold", "https://x.invalid"]
    ],
}

FAKE_DECK = {
    "id": "fake-origin-hash-1",
    "name": {"ko_KR": "가짜 조합", "en_US": "Fake Comp"},
    "units": [
        {"key": "TFT17_FakeAkali", "isCore": True, "items": ["TFT_Item_FakeSword"]},
        {"key": "TFT17_FakeUnknown", "isCore": False, "items": []},
    ],
    "badge": [
        {"key": "difficulty", "value": 2},
        {"key": "tempo", "value": None},
        {"key": "reroll", "value": 7},
        {"key": "honey", "value": True},
        {"key": "ppm", "value": "high"},
    ],
    "stat": {
        "opTier": "OP",
        "deck": {"avgPlacement": 3.1, "pickRate": 0.02, "winRate": 0.19},
    },
}
FAKE_META_DECKS = {
    "data": [FAKE_DECK],
    "metadata": {"gameStatDateTime": "2026-08-01T00:00:00.000Z"},
}


# ---- 순수 변환 함수 -------------------------------------------------------------


def test_champion_rows_matches_ko_and_en_by_api_name() -> None:
    rows = champion_rows(CDRAGON_KO, CDRAGON_EN, set_number=17)
    akali = next(r for r in rows if r["riot_champion_id"] == "TFT17_FakeAkali")

    assert akali == {
        "riot_champion_id": "TFT17_FakeAkali",
        "name_kr": "가짜 아칼리",
        "name_en": "FakeAkali",
        "cost": 4,
        "square_icon_url": "https://raw.communitydragon.org/latest/game/assets/characters/tft17_fakeakali/icon.png",
    }


def test_champion_rows_skips_entries_missing_in_other_language() -> None:
    rows = champion_rows(CDRAGON_KO, CDRAGON_EN, set_number=17)

    assert not any(r["riot_champion_id"] == "TFT17_FakeOnlyKo" for r in rows)


def test_champion_rows_square_icon_url_none_when_missing() -> None:
    rows = champion_rows(CDRAGON_KO, CDRAGON_EN, set_number=17)
    no_icon = next(r for r in rows if r["riot_champion_id"] == "TFT17_FakeNoIcon")

    assert no_icon["square_icon_url"] is None


# ---- FE-13: cdragon_asset_url() ----------------------------------------------


def test_cdragon_asset_url_lowercases_path_and_converts_extension() -> None:
    assert cdragon_asset_url(
        "ASSETS/Characters/TFT17_Akali/Skins/Base/Images/TFT17_Akali_splash_tile_68.tex"
    ) == (
        "https://raw.communitydragon.org/latest/game/"
        "assets/characters/tft17_akali/skins/base/images/tft17_akali_splash_tile_68.png"
    )


def test_champion_rows_unknown_set_returns_empty() -> None:
    assert champion_rows(CDRAGON_KO, CDRAGON_EN, set_number=18) == []


def test_trait_rows_builds_tier_thresholds_from_effects() -> None:
    rows = trait_rows(CDRAGON_KO, CDRAGON_EN, set_number=17)

    assert rows == [
        {
            "riot_trait_id": "TFT17_FakeTrait",
            "name_kr": "가짜 특성",
            "name_en": "FakeTrait",
            "tier_thresholds": [{"minUnits": 1, "maxUnits": 3, "style": 1}],
        }
    ]


def test_item_rows_maps_category_and_composition() -> None:
    rows = item_rows(ITEMS_KO, ITEMS_EN)

    assert rows == [
        {
            "riot_item_id": "TFT_Item_FakeSword",
            "name_kr": "가짜 검",
            "name_en": "Fake Sword",
            "item_type": "core",
            "components": ["TFT_Item_FakeA", "TFT_Item_FakeB"],
            "stats": {"AP": 10},
        }
    ]


def test_augment_rows_always_sets_is_legend_related_false() -> None:
    rows = augment_rows(AUGMENTS_KO, AUGMENTS_EN)

    assert rows == [
        {
            "riot_augment_id": "TFT17_Augment_Fake",
            "name_kr": "가짜 증강체",
            "name_en": "Fake Augment",
            "tier": "gold",
            "description": "가짜 설명",
            "is_legend_related": False,
        }
    ]


# ---- DATA-16: clean_augment_description() -----------------------------------
# 실제 op.gg 응답에서 발견된 패턴을 그대로 재현한 합성 fixture(2026-08-05
# 실호출로 형태 확인, docs/verification/FE-06-작업결과.md).


def test_clean_augment_description_converts_br_to_newline() -> None:
    raw = "효과 설명입니다.<br><br>추가 설명입니다."
    assert clean_augment_description(raw) == "효과 설명입니다.\n\n추가 설명입니다."


def test_clean_augment_description_replaces_unresolved_template_placeholder() -> None:
    raw = "선택한 퀘스트: @TFTUnitProperty.item:TFT17_Augment_AurelionSolGodAugment@"
    assert clean_augment_description(raw) == "선택한 퀘스트: (수치 정보 없음)"


def test_clean_augment_description_handles_multiple_placeholders_independently() -> (
    None
):
    raw = (
        "(체력: @TFTUnitProperty.:TFT17_Augment_Timebreaker_Timestream_HP@, "
        "공격 속도: @TFTUnitProperty.:TFT17_Augment_Timebreaker_Timestream_AS*100@%)"
    )
    assert (
        clean_augment_description(raw)
        == "(체력: (수치 정보 없음), 공격 속도: (수치 정보 없음)%)"
    )


def test_clean_augment_description_strips_rules_tags_and_collapses_blank_lines() -> (
    None
):
    raw = (
        "효과 설명입니다.<br><br><rules><br>"
        "체력: @TFTUnitProperty.item:TFT17_ThreshGodAugment_Health@<br>"
        "공격 속도: @TFTUnitProperty.item:TFT17_ThreshGodAugment_AttackSpeed@%<br>"
        "</rules>"
    )
    cleaned = clean_augment_description(raw)

    assert "<rules>" not in cleaned
    assert "</rules>" not in cleaned
    assert "<br>" not in cleaned
    assert "@" not in cleaned
    assert "\n\n\n" not in cleaned
    assert cleaned == (
        "효과 설명입니다.\n\n체력: (수치 정보 없음)\n공격 속도: (수치 정보 없음)%"
    )


def test_clean_augment_description_no_op_for_plain_text() -> None:
    assert clean_augment_description("평범한 설명입니다.") == "평범한 설명입니다."


def test_augment_rows_cleans_description_template_artifacts() -> None:
    augments_ko = {
        "headers": ["apiName", "desc", "name", "tier", "imageUrl"],
        "rows": [
            [
                "TFT17_Augment_Fake",
                "효과 설명입니다.<br>선택: @TFTUnitProperty.item:X@",
                "가짜 증강체",
                "gold",
                "https://x.invalid",
            ]
        ],
    }
    rows = augment_rows(augments_ko, AUGMENTS_EN)

    assert rows[0]["description"] == "효과 설명입니다.\n선택: (수치 정보 없음)"


def test_build_playstyle_text_includes_carry_and_nonfalsy_badges() -> None:
    text = build_playstyle_text(FAKE_DECK, {"TFT17_FakeAkali": "가짜 아칼리"})

    assert "가짜 아칼리 캐리" in text
    assert "난이도 2" in text
    assert "리롤 성향 7" in text
    assert "이코노미(하이퍼롤)" in text  # value=True -> 라벨만
    assert "파워스파이크 속도 high" in text
    assert "템포" not in text  # value=None -> 제외


def test_build_playstyle_text_falls_back_to_unknown_champion_id() -> None:
    text = build_playstyle_text(FAKE_DECK, {})

    assert "TFT17_FakeAkali 캐리" in text


def test_comp_rows_maps_fields_from_deck() -> None:
    rows = comp_rows(FAKE_META_DECKS, {"TFT17_FakeAkali": "가짜 아칼리"})

    assert len(rows) == 1
    row = rows[0]
    assert row["riot_comp_id"] == "fake-origin-hash-1"
    assert row["name"] == "가짜 조합"
    assert row["tier_rank"] == "OP"
    assert row["avg_place"] == 3.1
    assert row["play_rate"] == 0.02
    assert row["win_rate"] == 0.19
    assert row["updated_at"] == datetime(2026, 8, 1, tzinfo=UTC)


def test_comp_champion_rows_extracts_units() -> None:
    rows = comp_champion_rows(FAKE_DECK)

    assert rows == [
        {
            "riot_champion_id": "TFT17_FakeAkali",
            "is_carry": True,
            "recommended_items": ["TFT_Item_FakeSword"],
        },
        {
            "riot_champion_id": "TFT17_FakeUnknown",
            "is_carry": False,
            "recommended_items": [],
        },
    ]


def test_champion_item_build_rows_computes_play_rate() -> None:
    rows = champion_item_build_rows(
        {
            "data": [
                {
                    "itemNames": ["TFT_Item_FakeSword"],
                    "totalChampionCount": 200,
                    "itemCount": 50,
                    "avgPlacement": 3.5,
                    "winRate": 0.2,
                }
            ]
        }
    )

    assert rows == [
        {
            "item_combination": ["TFT_Item_FakeSword"],
            "play_rate": 0.25,
            "avg_place": 3.5,
            "win_rate": 0.2,
        }
    ]


def test_champion_item_build_rows_handles_zero_total_without_division_error() -> None:
    rows = champion_item_build_rows(
        {"data": [{"itemNames": [], "totalChampionCount": 0, "itemCount": 0}]}
    )

    assert rows[0]["play_rate"] == 0.0


# ---- DB upsert(실제 마이그레이션 적용된 테스트 DB 사용) -------------------------


@pytest.fixture
def db_session(migrated_engine: Engine) -> Session:
    with Session(migrated_engine) as session:
        ensure_patch(session, version="17.8", set_number=17)
        ensure_patch(session, version="17.9", set_number=17)
        session.commit()
        yield session


def test_ensure_patch_does_not_overwrite_existing_is_current(
    db_session: Session,
) -> None:
    # DATA-13이 is_current를 True로 전환했다고 가정 후 재실행해도 유지돼야 한다.
    db_session.execute(
        models.Patch.__table__.update()
        .where(models.Patch.version == "17.8")
        .values(is_current=True)
    )
    db_session.commit()

    ensure_patch(db_session, version="17.8", set_number=17)
    db_session.commit()

    patch = db_session.scalar(
        select(models.Patch).where(models.Patch.version == "17.8")
    )
    assert patch.is_current is True


def test_upsert_champions_same_patch_updates_in_place_not_duplicate(
    db_session: Session,
) -> None:
    rows = [
        {"riot_champion_id": "TFT17_X", "name_kr": "엑스", "name_en": "X", "cost": 1}
    ]

    ids_first = upsert_champions(db_session, "17.8", rows)
    db_session.commit()

    rows[0] = {**rows[0], "name_kr": "엑스(수정)"}
    ids_second = upsert_champions(db_session, "17.8", rows)
    db_session.commit()

    assert ids_first == ids_second  # 같은 DB id -> 새 행이 아니라 갱신됨

    all_rows = db_session.scalars(
        select(models.Champion).where(models.Champion.riot_champion_id == "TFT17_X")
    ).all()
    assert len(all_rows) == 1
    assert all_rows[0].name_kr == "엑스(수정)"


def test_upsert_champions_different_patch_creates_new_row_not_overwrite(
    db_session: Session,
) -> None:
    rows = [
        {"riot_champion_id": "TFT17_Y", "name_kr": "와이", "name_en": "Y", "cost": 2}
    ]

    upsert_champions(db_session, "17.8", rows)
    db_session.commit()
    upsert_champions(db_session, "17.9", rows)
    db_session.commit()

    all_rows = db_session.scalars(
        select(models.Champion).where(models.Champion.riot_champion_id == "TFT17_Y")
    ).all()
    assert len(all_rows) == 2
    assert {r.patch_version for r in all_rows} == {"17.8", "17.9"}


def test_upsert_traits_items_augments_comps_tag_patch_version(
    db_session: Session,
) -> None:
    trait_ids = upsert_traits(
        db_session,
        "17.8",
        [
            {
                "riot_trait_id": "TFT17_TraitX",
                "name_kr": "특성엑스",
                "name_en": "TraitX",
                "tier_thresholds": [],
            }
        ],
    )
    item_ids = upsert_items(
        db_session,
        "17.8",
        [
            {
                "riot_item_id": "TFT_Item_X",
                "name_kr": "아이템엑스",
                "name_en": "ItemX",
                "item_type": "core",
                "components": [],
                "stats": {},
            }
        ],
    )
    augment_ids = upsert_augments(
        db_session,
        "17.8",
        [
            {
                "riot_augment_id": "TFT17_AugX",
                "name_kr": "증강엑스",
                "name_en": "AugX",
                "tier": "gold",
                "description": "d",
                "is_legend_related": False,
            }
        ],
    )
    comp_ids = upsert_comps(
        db_session,
        "17.8",
        [
            {
                "riot_comp_id": "comp-x",
                "name": "조합엑스",
                "tier_rank": "S",
                "avg_place": 3.0,
                "play_rate": 0.1,
                "win_rate": 0.2,
                "playstyle_text": "설명",
                "updated_at": datetime.now(UTC),
            }
        ],
    )
    db_session.commit()

    assert set(trait_ids) == {"TFT17_TraitX"}
    assert set(item_ids) == {"TFT_Item_X"}
    assert set(augment_ids) == {"TFT17_AugX"}
    assert set(comp_ids) == {"comp-x"}

    trait = db_session.get(models.Trait, trait_ids["TFT17_TraitX"])
    assert trait.patch_version == "17.8"


def test_upsert_comp_champions_skips_unmapped_champion(db_session: Session) -> None:
    champion_ids = upsert_champions(
        db_session,
        "17.8",
        [
            {
                "riot_champion_id": "TFT17_Known",
                "name_kr": "K",
                "name_en": "K",
                "cost": 1,
            }
        ],
    )
    comp_ids = upsert_comps(
        db_session,
        "17.8",
        [
            {
                "riot_comp_id": "comp-y",
                "name": "조합와이",
                "tier_rank": "A",
                "avg_place": 4.0,
                "play_rate": 0.05,
                "win_rate": None,
                "playstyle_text": "설명",
                "updated_at": datetime.now(UTC),
            }
        ],
    )
    db_session.commit()
    comp_id = comp_ids["comp-y"]

    rows = [
        {"riot_champion_id": "TFT17_Known", "is_carry": True, "recommended_items": []},
        {
            "riot_champion_id": "TFT17_NotInChampionsTable",
            "is_carry": False,
            "recommended_items": [],
        },
    ]
    upsert_comp_champions(db_session, comp_id, rows, champion_ids)
    db_session.commit()

    linked = db_session.scalars(
        select(models.CompChampion).where(models.CompChampion.comp_id == comp_id)
    ).all()
    assert len(linked) == 1
    assert linked[0].champion_id == champion_ids["TFT17_Known"]


def test_replace_champion_item_builds_swaps_full_set(db_session: Session) -> None:
    champion_ids = upsert_champions(
        db_session,
        "17.8",
        [{"riot_champion_id": "TFT17_Z", "name_kr": "제트", "name_en": "Z", "cost": 3}],
    )
    db_session.commit()
    champion_id = champion_ids["TFT17_Z"]

    replace_champion_item_builds(
        db_session,
        champion_id,
        "17.8",
        [
            {
                "item_combination": ["A"],
                "play_rate": 0.1,
                "avg_place": 4.0,
                "win_rate": 0.2,
            }
        ],
    )
    db_session.commit()

    replace_champion_item_builds(
        db_session,
        champion_id,
        "17.8",
        [
            {
                "item_combination": ["B"],
                "play_rate": 0.3,
                "avg_place": 3.5,
                "win_rate": 0.25,
            }
        ],
    )
    db_session.commit()

    builds = db_session.scalars(
        select(models.ChampionItemBuild).where(
            models.ChampionItemBuild.champion_id == champion_id
        )
    ).all()
    assert len(builds) == 1
    assert builds[0].item_combination == ["B"]
