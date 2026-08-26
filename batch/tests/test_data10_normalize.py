"""DATA-10 pytest: 동일 엔티티 재수집 시 upsert(덮어쓰기 아님) + 신규 행
patch_version 태깅을 검증한다. 순수 변환 함수는 합성 fixture로, upsert 동작은
실제 마이그레이션이 적용된 테스트 DB(docker-compose.test.yml)로 검증한다
(policies.md 12번 — 이 테스트는 DB가 필요해 실 API 호출 정책과는 무관).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db_session import models
from normalize import (
    assign_self_tiers,
    augment_rows,
    build_playstyle_text,
    cdragon_asset_url,
    champion_item_build_rows,
    champion_rows,
    clean_augment_description,
    clean_item_description,
    comp_champion_rows,
    comp_rows,
    comp_trait_rows,
    ensure_patch,
    format_item_stats,
    item_rows,
    mark_stale_comps_inactive,
    replace_champion_item_builds,
    trait_rows,
    upsert_augments,
    upsert_champions,
    upsert_comp_champions,
    upsert_comp_traits,
    upsert_comps,
    upsert_items,
    upsert_traits,
    validate_champion_collection,
)

# ---- 합성 fixture(DATA-05/06 스파이크 구조 기반, 값은 전부 가짜) ----------------

CDRAGON_KO = {
    "items": [
        {
            "apiName": "TFT_Item_FakeSword",
            "icon": "ASSETS/Maps/TFT/Icons/Items/Hexcore/TFT_Item_FakeSword.tex",
        },
        {"apiName": "TFT_Item_FakeNoIcon"},
    ],
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
                    "traits": ["가짜 특성"],
                },
                {
                    "apiName": "TFT17_FakeOnlyKo",
                    "name": "한국어만",
                    "cost": 1,
                    "traits": ["가짜 특성"],
                },
                {
                    "apiName": "TFT17_FakeNoIcon",
                    "name": "아이콘 없음",
                    "cost": 2,
                    "traits": ["가짜 특성"],
                },
                {
                    "apiName": "TFT_FakeKrug",
                    "name": "가짜 돌거북",
                    "cost": 0,
                    "traits": [],
                },
            ],
            "traits": [
                {
                    "apiName": "TFT17_FakeTrait",
                    "name": "가짜 특성",
                    "effects": [{"minUnits": 1, "maxUnits": 3, "style": 1}],
                }
            ],
        }
    ],
}
CDRAGON_EN = {
    "setData": [
        {
            "number": 17,
            "mutator": "TFTSet17",
            "champions": [
                {"apiName": "TFT17_FakeAkali", "name": "FakeAkali", "cost": 4},
                {"apiName": "TFT17_FakeNoIcon", "name": "FakeNoIcon", "cost": 2},
                {"apiName": "TFT_FakeKrug", "name": "FakeKrug", "cost": 0},
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
            "desc": "공격력이 증가합니다.<br><br>@TFTUnitProperty.item:X@",
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
        {
            "key": "TFT17_FakeAkali",
            "isCore": True,
            "items": ["TFT_Item_FakeSword"],
            "cell": {"x": 4, "y": 1},
            "tier": 3,
        },
        {"key": "TFT17_FakeUnknown", "isCore": False, "items": []},
    ],
    "traits": [
        {"key": "TFT17_FakeTrait", "style": 3, "numUnits": 4},
        {"key": "TFT17_UnknownTrait", "style": 1, "numUnits": 2},
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
        "opScore": 1.5,
        "deck": {
            "avgPlacement": 3.1,
            "pickRate": 0.02,
            "winRate": 0.19,
            "top4Rate": 0.81,
            "compsCount": 1234,
        },
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


def test_champion_rows_skips_entities_with_no_traits() -> None:
    # 2026-08-26 사고 회귀 테스트: 정글 몬스터·모루 같은 비챔피언 엔티티
    # (traits: [])는 apiName이 있어도 챔피언 목록에서 제외돼야 한다.
    rows = champion_rows(CDRAGON_KO, CDRAGON_EN, set_number=17)

    assert not any(r["riot_champion_id"] == "TFT_FakeKrug" for r in rows)


def test_validate_champion_collection_passes_with_enough_champions() -> None:
    champions = [{"riot_champion_id": f"TFT17_Fake{i}"} for i in range(40)]
    validate_champion_collection(champions, set_number=17)  # 예외 없어야 함


def test_validate_champion_collection_raises_when_too_few() -> None:
    # 2026-08-26 패치 18.1 사고 재현: Community Dragon 세트 데이터가 프리뷰
    # 상태(챔피언 2명)일 때 그대로 승격되지 않고 예외로 배치가 중단돼야 한다.
    champions = [
        {"riot_champion_id": "DA_18_Alune"},
        {"riot_champion_id": "DA_18_Kobuko"},
    ]

    with pytest.raises(ValueError, match="비정상적으로 적습니다"):
        validate_champion_collection(champions, set_number=18)


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
    rows = item_rows(ITEMS_KO, ITEMS_EN, CDRAGON_KO)

    assert rows == [
        {
            "riot_item_id": "TFT_Item_FakeSword",
            "name_kr": "가짜 검",
            "name_en": "Fake Sword",
            "item_type": "core",
            "components": ["TFT_Item_FakeA", "TFT_Item_FakeB"],
            "stats": {"AP": 10},
            "square_icon_url": (
                "https://raw.communitydragon.org/latest/game/"
                "assets/maps/tft/icons/items/hexcore/tft_item_fakesword.png"
            ),
            "description": "공격력이 증가합니다.\n\n(수치 정보 없음)",
        }
    ]


def test_item_rows_square_icon_url_none_when_missing() -> None:
    items_ko = {"data": [{"apiName": "TFT_Item_FakeNoIcon", "name": "아이콘 없음"}]}
    items_en = {"data": [{"apiName": "TFT_Item_FakeNoIcon", "name": "NoIcon"}]}

    rows = item_rows(items_ko, items_en, CDRAGON_KO)

    assert rows[0]["square_icon_url"] is None


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
            "image_url": "https://x.invalid",
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


# ---- DATA-19: clean_item_description() ---------------------------------------
# 실제 op.gg tft_list_item_combinations 응답에서 발견된 패턴을 그대로 재현한
# 합성 fixture(2026-08-08 실호출로 형태 확인, docs/spike/opgg-schema.md 9번).


def test_clean_item_description_resolves_known_keyword_reference() -> None:
    raw = "정밀을 얻습니다.<br><br>{{TFT_Keyword_Precision}}"
    assert clean_item_description(raw) == (
        "정밀을 얻습니다.\n\n스킬 공격도 치명타로 적중할 수 있게 되고, "
        "치명타 확률과 치명타 피해량이 증가합니다."
    )


def test_clean_item_description_removes_unknown_keyword_reference() -> None:
    raw = "알 수 없는 효과입니다.<br><br>{{TFT_Keyword_NotInGlossary}}"
    assert clean_item_description(raw) == "알 수 없는 효과입니다."


def test_clean_item_description_still_handles_numeric_template_and_tags() -> None:
    raw = "<tftitemrules>전투 시작: 마나 @TFTUnitProperty.item:X@ 획득</tftitemrules>"
    assert clean_item_description(raw) == "전투 시작: 마나 (수치 정보 없음) 획득"


def test_clean_item_description_no_op_for_plain_text() -> None:
    assert clean_item_description("매초 잃은 체력의 2%만큼 체력 회복") == (
        "매초 잃은 체력의 2%만큼 체력 회복"
    )


# ---- DATA-20: format_item_stats() ---------------------------------------------
# '보석 건틀릿' 실측 stats(2026-08-09, CHAT-14 PM 검증 중 발견)를 기반으로 한
# 합성 fixture.


def test_format_item_stats_formats_whitelisted_keys_only() -> None:
    stats = {"AP": 35, "CritChance": 35, "CritDamageToGive": None}
    assert format_item_stats(stats) == "주문력 +35, 치명타 확률 +35%"


def test_format_item_stats_converts_percent_fraction_and_absorbs_float_precision_error() -> (
    None
):
    """'무한의 대검' 실측: AD가 0~1 소수(부동소수점 오차 포함, float32 -> float64
    변환 시 흔히 생기는 0.3499999940395355 형태)로 저장돼 있어 그대로 노출하면
    "+0.3499999940395355%"처럼 깨진 문자열이 나온다(2026-08-09 백필 중 발견 —
    같은 문제가 AttackSpeed에서도 재현돼 그 키는 화이트리스트에서 아예 제외)."""
    stats = {"AD": 0.3499999940395355}
    assert format_item_stats(stats) == "공격력 +35%"


def test_format_item_stats_skips_none_and_unknown_keys() -> None:
    stats = {
        "Health": 300,
        "HexRadius": 4,
        "{cd951938}": 0.1,
        "PercentHealthStore": 0.025,
    }
    assert format_item_stats(stats) == "체력 +300"


def test_format_item_stats_returns_empty_string_when_no_whitelisted_stats() -> None:
    assert format_item_stats({"HexRadius": 4, "Duration": 8}) == ""


def test_format_item_stats_handles_missing_stats() -> None:
    assert format_item_stats(None) == ""
    assert format_item_stats({}) == ""


def test_item_rows_includes_cleaned_description() -> None:
    items_ko = {
        "data": [
            {
                "apiName": "TFT_Item_FakeGauntlet",
                "name": "가짜 건틀릿",
                "category": "core",
                "composition": [],
                "effects": {"CritChance": 35},
                "desc": "<TFTKeyword>정밀</TFTKeyword>을 얻습니다.<br><br>{{TFT_Keyword_Precision}}",
            }
        ]
    }
    items_en = {"data": [{"apiName": "TFT_Item_FakeGauntlet", "name": "Fake Gauntlet"}]}

    rows = item_rows(items_ko, items_en, CDRAGON_KO)

    assert rows[0]["description"] == (
        "정밀을 얻습니다.\n\n스킬 공격도 치명타로 적중할 수 있게 되고, "
        "치명타 확률과 치명타 피해량이 증가합니다."
    )


def test_build_playstyle_text_includes_carry_and_nonfalsy_badges() -> None:
    text = build_playstyle_text(FAKE_DECK, {"TFT17_FakeAkali": "가짜 아칼리"})

    assert "가짜 아칼리 캐리" in text
    assert "난이도 2" in text
    assert "리롤 성향 7" in text
    assert "이코노미(하이퍼롤)" in text  # value=True -> 라벨만
    assert "템포" not in text  # value=None -> 제외
    # 2026-08-18: ppm은 검증 안 된 추측 라벨("파워스파이크 속도")이었고 실측
    # 결과 opScore 상위권 표시 플래그로 추정돼(정확한 의미 불명) PM 결정으로
    # 화면 표시에서 제외 — value가 있어도("high") 절대 노출되면 안 된다.
    assert "ppm" not in text
    assert "파워스파이크" not in text
    assert "high" not in text


def test_build_playstyle_text_falls_back_to_unknown_champion_id() -> None:
    text = build_playstyle_text(FAKE_DECK, {})

    assert "TFT17_FakeAkali 캐리" in text


def test_comp_rows_maps_fields_from_deck() -> None:
    rows = comp_rows(FAKE_META_DECKS, {"TFT17_FakeAkali": "가짜 아칼리"})

    assert len(rows) == 1
    row = rows[0]
    assert row["riot_comp_id"] == "fake-origin-hash-1"
    assert row["name"] == "가짜 조합"
    # DATA-23: tier_rank는 op.gg opTier("OP")가 아니라 assign_self_tiers()의
    # 자체 계산 값(op_score 기반). 배치에 op_score 있는 조합이 1개뿐이면
    # 비교 대상이 없어 "A"(중립) 고정.
    assert row["tier_rank"] == "A"
    assert row["avg_place"] == 3.1
    assert row["play_rate"] == 0.02
    assert row["win_rate"] == 0.19
    # DATA-22: top4Rate/compsCount 매핑(compsCount가 조합별 실제 표본
    # 게임수 — totalCount는 집계구간 전체 공통분모라 여기서 쓰지 않음).
    assert row["top4_rate"] == 0.81
    assert row["game_count"] == 1234
    # DATA-23: op_score 원값 매핑.
    assert row["op_score"] == 1.5
    assert row["updated_at"] == datetime(2026, 8, 1, tzinfo=UTC)


# ---- DATA-23: assign_self_tiers 단위 테스트(op_score 기반 간격 클러스터링) ---


def _comp(op_score: float | None) -> dict[str, Any]:
    return {"op_score": op_score}


def test_assign_self_tiers_empty_list_is_no_op() -> None:
    rows: list[dict[str, Any]] = []
    assign_self_tiers(rows)
    assert rows == []


def test_assign_self_tiers_single_scored_comp_lands_in_neutral_tier() -> None:
    """op_score가 있는 조합이 배치에 1개뿐이면 비교 대상이 없어 "A"(중립) 고정."""
    rows = [_comp(op_score=1.5)]
    assign_self_tiers(rows)
    assert rows[0]["tier_rank"] == "A"


def test_assign_self_tiers_missing_op_score_gets_lowest_tier() -> None:
    """op_score가 None(op.gg 응답 결측)인 행은 다른 조합의 점수 분포와
    무관하게 항상 "C"로 고정된다."""
    rows = [_comp(op_score=None), _comp(op_score=2.0), _comp(op_score=0.2)]
    assign_self_tiers(rows)
    assert rows[0]["tier_rank"] == "C"
    assert rows[1]["tier_rank"] != "C"


def test_assign_self_tiers_all_tied_scores_land_in_single_top_tier() -> None:
    """op_score가 전부 동점이면 격차가 0이라 경계가 하나도 안 생겨 전부
    최상위 티어("OP")로 묶인다 — 비교 우위를 가릴 근거가 없다는 뜻."""
    rows = [_comp(op_score=1.0) for _ in range(5)]
    assign_self_tiers(rows)
    assert all(row["tier_rank"] == "OP" for row in rows)


def test_assign_self_tiers_reproduces_real_snapshot_clusters() -> None:
    """2026-08-18 실측 스냅샷(docs/spike/comp-tier-scoring.md)의 opScore
    10개를 그대로 넣으면, 두드러진 격차를 경계로 {상위 2개}=OP,
    {다음 2개}=S, {나머지 6개}=A로 나뉜다(고정 5단계가 아니라 실제
    점수 분포에 따라 3단계만 나온 사례) — op.gg 원본 라벨(OP,OP,S,S,
    A,A,A,A,A,A)과 완전히 일치했던 조합이다."""
    scores = [2.221, 2.000, 0.953, 0.893, 0.442, 0.432, 0.402, 0.252, 0.234, 0.209]
    rows = [_comp(op_score=s) for s in scores]
    assign_self_tiers(rows)
    tiers = [row["tier_rank"] for row in rows]
    assert tiers[0:2] == ["OP", "OP"]
    assert tiers[2:4] == ["S", "S"]
    assert tiers[4:10] == ["A"] * 6


def test_assign_self_tiers_never_exceeds_five_labels() -> None:
    """유의미한 격차(gap=1, 임계값 0.867 초과)가 연속 6번 나와 경계 후보가
    6개 생겨도, 라벨은 5단계(OP~C)를 넘어서지 않고 6번째부터는 "C"에
    누적된다."""
    scores = [
        60.003,
        59.003,
        58.003,
        57.003,
        56.003,
        55.003,
        54.003,
        54.002,
        54.001,
        54.000,
    ]
    rows = [_comp(op_score=s) for s in scores]
    assign_self_tiers(rows)
    tiers = [row["tier_rank"] for row in rows]
    assert tiers == ["OP", "S", "A", "B", "C", "C", "C", "C", "C", "C"]


def test_comp_champion_rows_extracts_units() -> None:
    rows = comp_champion_rows(FAKE_DECK)

    assert rows == [
        {
            "riot_champion_id": "TFT17_FakeAkali",
            "is_carry": True,
            "recommended_items": ["TFT_Item_FakeSword"],
            "cell_x": 4,
            "cell_y": 1,
            "star_level": 3,
        },
        {
            "riot_champion_id": "TFT17_FakeUnknown",
            "is_carry": False,
            "recommended_items": [],
            "cell_x": None,
            "cell_y": None,
            "star_level": None,
        },
    ]


def test_comp_trait_rows_extracts_traits() -> None:
    rows = comp_trait_rows(FAKE_DECK)

    assert rows == [
        {"riot_trait_id": "TFT17_FakeTrait", "style": 3, "num_units": 4},
        {"riot_trait_id": "TFT17_UnknownTrait", "style": 1, "num_units": 2},
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


# DATA-19: upsert_items()가 description을 저장하고, 재수집(같은 patch_version)
# 시 갱신도 되는지 확인(다른 컬럼들과 동일한 upsert 패턴).
def test_upsert_items_persists_and_updates_description(db_session: Session) -> None:
    item_ids = upsert_items(
        db_session,
        "17.8",
        [
            {
                "riot_item_id": "TFT_Item_Y",
                "name_kr": "아이템와이",
                "name_en": "ItemY",
                "item_type": "core",
                "components": [],
                "stats": {},
                "description": "첫 번째 설명",
            }
        ],
    )
    db_session.commit()
    item = db_session.get(models.Item, item_ids["TFT_Item_Y"])
    assert item.description == "첫 번째 설명"

    upsert_items(
        db_session,
        "17.8",
        [
            {
                "riot_item_id": "TFT_Item_Y",
                "name_kr": "아이템와이",
                "name_en": "ItemY",
                "item_type": "core",
                "components": [],
                "stats": {},
                "description": "갱신된 설명",
            }
        ],
    )
    db_session.commit()
    db_session.refresh(item)
    assert item.description == "갱신된 설명"


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


def test_upsert_comp_traits_skips_unmapped_trait(db_session: Session) -> None:
    trait_ids = upsert_traits(
        db_session,
        "17.8",
        [
            {
                "riot_trait_id": "TFT17_Known",
                "name_kr": "K",
                "name_en": "K",
                "tier_thresholds": {},
            }
        ],
    )
    comp_ids = upsert_comps(
        db_session,
        "17.8",
        [
            {
                "riot_comp_id": "comp-z",
                "name": "조합제트",
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
    comp_id = comp_ids["comp-z"]

    rows = [
        {"riot_trait_id": "TFT17_Known", "style": 2, "num_units": 3},
        {"riot_trait_id": "TFT17_NotInTraitsTable", "style": 1, "num_units": 2},
    ]
    upsert_comp_traits(db_session, comp_id, rows, trait_ids)
    db_session.commit()

    linked = db_session.scalars(
        select(models.CompTrait).where(models.CompTrait.comp_id == comp_id)
    ).all()
    assert len(linked) == 1
    assert linked[0].trait_id == trait_ids["TFT17_Known"]
    assert linked[0].style == 2
    assert linked[0].num_units == 3


def test_upsert_comp_traits_updates_style_and_num_units_on_conflict(
    db_session: Session,
) -> None:
    trait_ids = upsert_traits(
        db_session,
        "17.8",
        [
            {
                "riot_trait_id": "TFT17_Known",
                "name_kr": "K",
                "name_en": "K",
                "tier_thresholds": {},
            }
        ],
    )
    comp_ids = upsert_comps(
        db_session,
        "17.8",
        [
            {
                "riot_comp_id": "comp-z2",
                "name": "조합제트투",
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
    comp_id = comp_ids["comp-z2"]

    upsert_comp_traits(
        db_session,
        comp_id,
        [{"riot_trait_id": "TFT17_Known", "style": 1, "num_units": 2}],
        trait_ids,
    )
    db_session.commit()
    upsert_comp_traits(
        db_session,
        comp_id,
        [{"riot_trait_id": "TFT17_Known", "style": 4, "num_units": 6}],
        trait_ids,
    )
    db_session.commit()

    linked = db_session.scalars(
        select(models.CompTrait).where(models.CompTrait.comp_id == comp_id)
    ).all()
    assert len(linked) == 1
    assert linked[0].style == 4
    assert linked[0].num_units == 6


def _comp_row(riot_comp_id: str) -> dict:
    return {
        "riot_comp_id": riot_comp_id,
        "name": riot_comp_id,
        "tier_rank": "S",
        "avg_place": 3.0,
        "play_rate": 0.1,
        "win_rate": 0.2,
        "playstyle_text": "설명",
        "updated_at": datetime.now(UTC),
    }


def test_upsert_comps_defaults_new_rows_to_active(db_session: Session) -> None:
    comp_ids = upsert_comps(db_session, "17.8", [_comp_row("comp-active")])
    db_session.commit()

    comp = db_session.get(models.Comp, comp_ids["comp-active"])
    assert comp.is_active is True


def test_mark_stale_comps_inactive_deactivates_comps_missing_from_batch(
    db_session: Session,
) -> None:
    comp_ids = upsert_comps(
        db_session, "17.8", [_comp_row("comp-still-top10"), _comp_row("comp-dropped")]
    )
    db_session.commit()

    # 이번 배치 op.gg 응답엔 comp-still-top10만 있고 comp-dropped는 메타
    # 회전으로 빠졌다고 가정.
    updated = mark_stale_comps_inactive(db_session, "17.8", {"comp-still-top10"})
    db_session.commit()

    assert updated == 1
    still_top10 = db_session.get(models.Comp, comp_ids["comp-still-top10"])
    dropped = db_session.get(models.Comp, comp_ids["comp-dropped"])
    assert still_top10.is_active is True
    assert dropped.is_active is False


def test_mark_stale_comps_inactive_ignores_other_patch_versions(
    db_session: Session,
) -> None:
    comp_ids_17_8 = upsert_comps(db_session, "17.8", [_comp_row("comp-shared-id")])
    comp_ids_17_9 = upsert_comps(db_session, "17.9", [_comp_row("comp-shared-id")])
    db_session.commit()

    # 17.9 배치를 도는 중이고, 이번 op.gg 응답엔 이 리스트가 없다고 가정해도
    # 17.8 행은 건드리면 안 된다(정합성 원칙: 다른 패치 행은 절대 덮어쓰지 않음).
    mark_stale_comps_inactive(db_session, "17.9", set())
    db_session.commit()

    comp_17_8 = db_session.get(models.Comp, comp_ids_17_8["comp-shared-id"])
    comp_17_9 = db_session.get(models.Comp, comp_ids_17_9["comp-shared-id"])
    assert comp_17_8.is_active is True
    assert comp_17_9.is_active is False


def test_upsert_comps_reactivates_previously_inactive_comp(
    db_session: Session,
) -> None:
    comp_ids = upsert_comps(db_session, "17.8", [_comp_row("comp-returns")])
    db_session.commit()
    mark_stale_comps_inactive(db_session, "17.8", set())
    db_session.commit()
    assert db_session.get(models.Comp, comp_ids["comp-returns"]).is_active is False

    # 다음 배치에서 메타가 다시 상위 10위 안으로 돌아왔다고 가정.
    upsert_comps(db_session, "17.8", [_comp_row("comp-returns")])
    db_session.commit()

    assert db_session.get(models.Comp, comp_ids["comp-returns"]).is_active is True


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
