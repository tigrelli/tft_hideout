"""DATA-09 pytest: Community Dragon(TFT DDragon 대체) mock 기준 ID→이름 매핑
정확도 + 매핑 누락 시 폴백 동작을 검증한다(실 API 미호출).
"""

from __future__ import annotations

import httpx
import pytest

from id_name_mapping import (
    CommunityDragonClient,
    CommunityDragonError,
    build_name_maps,
)

# DATA-06 스파이크(docs/spike/tft-ddragon.md)에서 확인한 Community Dragon 응답 구조를
# 그대로 따르되 값은 합성 데이터로 치환(CLAUDE.md 10.2 fixture 정책).
FAKE_TFT_DATA = {
    "items": [],
    "setData": [
        {
            "number": 16,
            "mutator": "TFTSet16",
            "champions": [{"apiName": "TFT16_OldChamp", "name": "옛날 챔피언"}],
            "traits": [{"apiName": "TFT16_OldTrait", "name": "옛날 특성"}],
        },
        {
            "number": 17,
            "mutator": "TFTSet17",
            "champions": [
                {"apiName": "TFT17_FakeAkali", "name": "가짜 아칼리"},
                {"apiName": "TFT17_FakeJinx", "name": "가짜 징크스"},
                {"apiName": "TFT_FakeGolem", "name": "가짜 골렘"},
            ],
            "traits": [
                {"apiName": "TFT17_FakeTraitDoomer", "name": "가짜 파멸자"},
            ],
        },
        {
            "number": 17,
            "mutator": "TFTSet17_PVEMODE",
            "champions": [{"apiName": "TFT17_PveOnlyChamp", "name": "PVE 전용"}],
            "traits": [],
        },
    ],
    "sets": {"16": {}, "17": {}},
}


def test_build_name_maps_returns_champion_and_trait_names_for_set() -> None:
    maps = build_name_maps(FAKE_TFT_DATA, set_number=17)

    assert maps.champion_name("TFT17_FakeAkali") == "가짜 아칼리"
    assert maps.champion_name("TFT17_FakeJinx") == "가짜 징크스"
    assert maps.trait_name("TFT17_FakeTraitDoomer") == "가짜 파멸자"


def test_build_name_maps_picks_first_matching_setdata_entry() -> None:
    # setData에 number=17 항목이 2개(TFTSet17, TFTSet17_PVEMODE) 있을 때
    # 첫 번째(정상 모드)를 사용한다 — PVE 전용 챔피언은 포함되지 않아야 함.
    maps = build_name_maps(FAKE_TFT_DATA, set_number=17)

    assert "TFT17_PveOnlyChamp" not in maps.champions


def test_build_name_maps_does_not_mix_up_different_sets() -> None:
    # 정확도 케이스: set 16 데이터가 set 17 조회 결과에 섞여 들어가지 않는다.
    maps17 = build_name_maps(FAKE_TFT_DATA, set_number=17)
    assert "TFT16_OldChamp" not in maps17.champions

    maps16 = build_name_maps(FAKE_TFT_DATA, set_number=16)
    assert maps16.champion_name("TFT16_OldChamp") == "옛날 챔피언"


def test_build_name_maps_unknown_set_returns_empty_maps() -> None:
    # DATA-06 시나리오: Set 18이 아직 Community Dragon에 없는 경우.
    maps = build_name_maps(FAKE_TFT_DATA, set_number=18)

    assert maps.champions == {}
    assert maps.traits == {}


def test_champion_name_falls_back_to_stripped_id_when_missing() -> None:
    maps = build_name_maps(FAKE_TFT_DATA, set_number=17)

    assert maps.champion_name("TFT17_UnknownChampion") == "UnknownChampion"


def test_trait_name_falls_back_when_missing() -> None:
    maps = build_name_maps(FAKE_TFT_DATA, set_number=17)

    assert maps.trait_name("TFT17_UnknownTrait") == "UnknownTrait"


def test_champion_name_fallback_handles_lowercase_and_no_digit_prefix() -> None:
    maps = build_name_maps(FAKE_TFT_DATA, set_number=17)

    # op.gg 챔피언 ID enum엔 "tft17_bardfollower"처럼 소문자 접두어도 있고
    # "TFT_FakeGolem"처럼 세트 번호 없는 접두어도 있다(DATA-09 조사 시 확인).
    assert maps.champion_name("tft17_unknownlowercase") == "unknownlowercase"
    assert maps.champion_name("TFT_UnknownNoDigits") == "UnknownNoDigits"


def test_fetch_tft_data_requests_expected_path() -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        return httpx.Response(200, json=FAKE_TFT_DATA)

    transport = httpx.MockTransport(handler)
    with CommunityDragonClient(transport=transport) as client:
        result = client.fetch_tft_data(lang="ko_kr")

    assert seen_paths == ["/latest/cdragon/tft/ko_kr.json"]
    assert result == FAKE_TFT_DATA


def test_fetch_tft_data_raises_community_dragon_error_on_http_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    transport = httpx.MockTransport(handler)
    with (
        CommunityDragonClient(transport=transport) as client,
        pytest.raises(CommunityDragonError),
    ):
        client.fetch_tft_data()


def test_fetch_tft_data_raises_community_dragon_error_on_invalid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    transport = httpx.MockTransport(handler)
    with (
        CommunityDragonClient(transport=transport) as client,
        pytest.raises(CommunityDragonError),
    ):
        client.fetch_tft_data()
