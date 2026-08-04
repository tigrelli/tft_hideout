"""DATA-08 pytest: op.gg 응답을 DATA-05 스파이크 결과 기반 합성 fixture로 고정해
5개 도구 호출·파싱을 검증한다(실 API 미호출, policies.md 10.2/11 mock 정책).
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from opgg_client import OpggMcpClient, OpggMcpError

SESSION_ID = "test-session-id-0000"


def _mcp_result(request_id: int, payload: dict | list) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {"content": [{"type": "text", "text": json.dumps(payload)}]},
    }


# DATA-05 스파이크(docs/spike/opgg-schema.md)에서 확인한 응답 구조를 그대로 따르되
# 값은 전부 합성 데이터로 치환(CLAUDE.md 10.2 fixture 정책).
FAKE_META_DECKS = {
    "data": [
        {
            "id": "fake-deck-id-1",
            "name": {"ko_KR": "가짜 조합 A"},
            "teamCode": "0000000000000000TFTSet17",
            "units": [
                {"key": "TFT17_FakeCarry", "items": [], "tier": 3, "isCore": True}
            ],
            "stat": {
                "opTier": "OP",
                "deck": {
                    "totalCount": 1000,
                    "winRate": 0.21,
                    "top4Rate": 0.55,
                    "pickRate": 0.01,
                },
            },
        }
    ],
    "metadata": {
        "gameStatCounts": 100000,
        "gameStatDateTime": "2026-08-01T00:00:00.000Z",
    },
}

FAKE_ITEM_COMBINATIONS = {
    "set": 17,
    "version": "17.8",
    "type": "cdragon-item",
    "lang": "ko_KR",
    "data": [
        {
            "apiName": "TFT_Item_FakeSword",
            "name": "가짜 검",
            "composition": ["TFT_Item_FakeComponentA", "TFT_Item_FakeComponentB"],
        }
    ],
}

FAKE_AUGMENTS = {
    "headers": ["apiName", "desc", "name", "tier", "imageUrl"],
    "rows": [
        [
            "TFT17_Augment_FakeOne",
            "가짜 증강체 설명",
            "가짜 증강체",
            "gold",
            "https://example.invalid/fake-augment.png",
        ]
    ],
    "header_description": {"apiName": "Augment API name (identifier)"},
}

FAKE_CHAMPION_ITEM_BUILD = {
    "data": [
        {
            "characterId": "TFT17_FakeChampion",
            "itemNames": ["TFT_Item_FakeSword"],
            "winRate": 0.18,
            "avgPlacement": 3.9,
        }
    ]
}

FAKE_CHAMPIONS_FOR_ITEM = [
    {"characterId": "TFT17_FakeChampion", "winRate": 0.19, "avgPlacement": 3.8},
]


def _make_transport(
    tool_responses: dict[str, dict | list],
    on_tool_call: Callable[[str], None] | None = None,
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method = body.get("method")

        if method == "initialize":
            return httpx.Response(
                200,
                headers={"Mcp-Session-Id": SESSION_ID},
                json={
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {"protocolVersion": "2025-06-18", "serverInfo": {}},
                },
            )
        if method == "notifications/initialized":
            return httpx.Response(200, json={})
        if method == "tools/call":
            assert request.headers.get("Mcp-Session-Id") == SESSION_ID
            tool_name = body["params"]["name"]
            if on_tool_call:
                on_tool_call(tool_name)
            if tool_name not in tool_responses:
                raise AssertionError(f"예상치 못한 도구 호출: {tool_name}")
            return httpx.Response(
                200, json=_mcp_result(body["id"], tool_responses[tool_name])
            )
        raise AssertionError(f"예상치 못한 method: {method}")

    return httpx.MockTransport(handler)


ALL_TOOL_RESPONSES = {
    "tft_list_meta_decks": FAKE_META_DECKS,
    "tft_list_item_combinations": FAKE_ITEM_COMBINATIONS,
    "tft_list_augments": FAKE_AUGMENTS,
    "tft_get_champion_item_build": FAKE_CHAMPION_ITEM_BUILD,
    "tft_list_champions_for_item": FAKE_CHAMPIONS_FOR_ITEM,
}


def test_list_meta_decks_parses_data_and_metadata() -> None:
    transport = _make_transport(ALL_TOOL_RESPONSES)
    with OpggMcpClient(transport=transport) as client:
        result = client.list_meta_decks()

    assert result == FAKE_META_DECKS
    assert result["data"][0]["stat"]["deck"]["winRate"] == 0.21


def test_list_item_combinations_includes_version_field() -> None:
    transport = _make_transport(ALL_TOOL_RESPONSES)
    with OpggMcpClient(transport=transport) as client:
        result = client.list_item_combinations()

    # DATA-05 핵심 발견: 5개 도구 중 이 도구에만 version 필드가 있다(DATA-12 패치 감지 신호).
    assert result["set"] == 17
    assert result["version"] == "17.8"


def test_list_augments_returns_table_format() -> None:
    transport = _make_transport(ALL_TOOL_RESPONSES)
    with OpggMcpClient(transport=transport) as client:
        result = client.list_augments()

    assert result["headers"] == ["apiName", "desc", "name", "tier", "imageUrl"]
    assert result["rows"][0][0] == "TFT17_Augment_FakeOne"


def test_get_champion_item_build_sends_champion_id_argument() -> None:
    seen_args: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("method") == "initialize":
            return httpx.Response(
                200,
                headers={"Mcp-Session-Id": SESSION_ID},
                json={"jsonrpc": "2.0", "id": body["id"], "result": {}},
            )
        if body.get("method") == "notifications/initialized":
            return httpx.Response(200, json={})
        seen_args.update(body["params"]["arguments"])
        return httpx.Response(
            200, json=_mcp_result(body["id"], FAKE_CHAMPION_ITEM_BUILD)
        )

    transport = httpx.MockTransport(handler)
    with OpggMcpClient(transport=transport) as client:
        result = client.get_champion_item_build("TFT17_FakeChampion")

    assert seen_args == {"champion_id": "TFT17_FakeChampion"}
    assert result["data"][0]["characterId"] == "TFT17_FakeChampion"


def test_list_champions_for_item_returns_bare_list() -> None:
    transport = _make_transport(ALL_TOOL_RESPONSES)
    with OpggMcpClient(transport=transport) as client:
        result = client.list_champions_for_item("TFT_Item_FakeSword")

    assert isinstance(result, list)
    assert result[0]["characterId"] == "TFT17_FakeChampion"


def test_all_five_tools_callable_in_one_session() -> None:
    called: list[str] = []
    transport = _make_transport(ALL_TOOL_RESPONSES, on_tool_call=called.append)

    with OpggMcpClient(transport=transport) as client:
        client.list_meta_decks()
        client.list_item_combinations()
        client.list_augments()
        client.get_champion_item_build("TFT17_FakeChampion")
        client.list_champions_for_item("TFT_Item_FakeSword")

    assert called == [
        "tft_list_meta_decks",
        "tft_list_item_combinations",
        "tft_list_augments",
        "tft_get_champion_item_build",
        "tft_list_champions_for_item",
    ]


def test_jsonrpc_error_response_raises_opgg_mcp_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("method") == "initialize":
            return httpx.Response(
                200,
                headers={"Mcp-Session-Id": SESSION_ID},
                json={"jsonrpc": "2.0", "id": body["id"], "result": {}},
            )
        if body.get("method") == "notifications/initialized":
            return httpx.Response(200, json={})
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "error": {"code": -32602, "message": "Invalid params"},
            },
        )

    transport = httpx.MockTransport(handler)
    with (
        OpggMcpClient(transport=transport) as client,
        pytest.raises(OpggMcpError, match="Invalid params"),
    ):
        client.list_meta_decks()


def test_transient_http_error_is_retried_then_succeeds() -> None:
    attempts: dict[str, int] = {"tools/call": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method = body.get("method")
        if method == "initialize":
            return httpx.Response(
                200,
                headers={"Mcp-Session-Id": SESSION_ID},
                json={"jsonrpc": "2.0", "id": body["id"], "result": {}},
            )
        if method == "notifications/initialized":
            return httpx.Response(200, json={})
        attempts["tools/call"] += 1
        if attempts["tools/call"] == 1:
            return httpx.Response(503, text="temporarily unavailable")
        return httpx.Response(200, json=_mcp_result(body["id"], FAKE_META_DECKS))

    transport = httpx.MockTransport(handler)
    with OpggMcpClient(transport=transport, retry_backoff_seconds=0) as client:
        result = client.list_meta_decks()

    assert attempts["tools/call"] == 2
    assert result == FAKE_META_DECKS


def test_retries_exhausted_raises_opgg_mcp_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("method") == "initialize":
            return httpx.Response(
                200,
                headers={"Mcp-Session-Id": SESSION_ID},
                json={"jsonrpc": "2.0", "id": body["id"], "result": {}},
            )
        if body.get("method") == "notifications/initialized":
            return httpx.Response(200, json={})
        return httpx.Response(500, text="server error")

    transport = httpx.MockTransport(handler)
    with (
        OpggMcpClient(
            transport=transport, max_retries=1, retry_backoff_seconds=0
        ) as client,
        pytest.raises(OpggMcpError),
    ):
        client.list_meta_decks()


def test_initialize_missing_session_header_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(
            200, json={"jsonrpc": "2.0", "id": body["id"], "result": {}}
        )

    transport = httpx.MockTransport(handler)
    with (
        pytest.raises(OpggMcpError, match="Mcp-Session-Id"),
        OpggMcpClient(transport=transport),
    ):
        pass
