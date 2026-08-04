"""op.gg MCP(https://mcp-api.op.gg/mcp) TFT 도구 5종 호출 클라이언트.

DATA-05 스파이크(docs/spike/opgg-schema.md) 결과를 근거로 구현. tft_get_play_style은
PUUID가 필요한 개인화 도구라 이 모듈에서 제외하고 PGA-07에서 별도로 호출한다.
"""

from __future__ import annotations

import json
import time
from types import TracebackType
from typing import Any, Self

import httpx

DEFAULT_BASE_URL = "https://mcp-api.op.gg/mcp"
MCP_PROTOCOL_VERSION = "2024-11-05"
CLIENT_INFO = {"name": "tft-hideout-batch", "version": "0.1"}


class OpggMcpError(Exception):
    """op.gg MCP 호출 실패(HTTP 오류, JSON-RPC 오류, 세션 미초기화 등)."""


class OpggMcpClient:
    """세션 하나로 여러 도구를 순차 호출하기 위한 컨텍스트 매니저.

    사용 예:
        with OpggMcpClient() as client:
            decks = client.list_meta_decks()
            items = client.list_item_combinations()
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 15.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 1.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url, timeout=timeout, transport=transport
        )
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._session_id: str | None = None
        self._next_request_id = 1

    def __enter__(self) -> Self:
        self._initialize()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._http.close()

    def _initialize(self) -> None:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._allocate_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": CLIENT_INFO,
                },
            },
            include_session=False,
        )
        session_id = response.headers.get("Mcp-Session-Id")
        if not session_id:
            raise OpggMcpError("initialize 응답에 Mcp-Session-Id 헤더가 없습니다")
        self._session_id = session_id
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _allocate_id(self) -> int:
        request_id = self._next_request_id
        self._next_request_id += 1
        return request_id

    def _post(
        self, payload: dict[str, Any], include_session: bool = True
    ) -> httpx.Response:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if include_session:
            if not self._session_id:
                raise OpggMcpError(
                    "세션이 초기화되지 않았습니다(with 블록 밖에서 호출됨)"
                )
            headers["Mcp-Session-Id"] = self._session_id

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._http.post("", json=payload, headers=headers)
                response.raise_for_status()
                return response
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(self._retry_backoff_seconds)
        raise OpggMcpError(f"op.gg MCP 요청 실패: {last_error}") from last_error

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._allocate_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        body = response.json()
        if "error" in body:
            raise OpggMcpError(f"{name} 호출 오류: {body['error']}")
        try:
            text = body["result"]["content"][0]["text"]
            return json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise OpggMcpError(f"{name} 응답 파싱 실패: {exc}") from exc

    def list_meta_decks(self) -> dict[str, Any]:
        """현재 메타 조합 목록. 응답: {data: [...], metadata: {...}} (patch_version 필드 없음)."""
        return self._call_tool("tft_list_meta_decks", {})

    def list_item_combinations(self, lang: str = "ko_KR") -> dict[str, Any]:
        """아이템 조합 레시피. 응답: {set, version, type, lang, data: [...]}.

        DATA-05 결론: 5개 도구 중 유일하게 `version` 필드(예: "17.8")가 있어
        DATA-12 패치 감지 신호로 사용한다.
        """
        return self._call_tool("tft_list_item_combinations", {"lang": lang})

    def list_augments(self, lang: str = "ko_KR") -> dict[str, Any]:
        """증강체 목록. 응답: {headers, rows, header_description} 테이블 포맷."""
        return self._call_tool("tft_list_augments", {"lang": lang})

    def get_champion_item_build(self, champion_id: str) -> dict[str, Any]:
        """챔피언별 아이템 빌드. 응답: {data: [...]}. champion_id 예: "TFT17_Akali"."""
        return self._call_tool(
            "tft_get_champion_item_build", {"champion_id": champion_id}
        )

    def list_champions_for_item(self, item_id: str) -> list[dict[str, Any]]:
        """아이템별 추천 챔피언. 응답이 바로 배열. item_id 예: "TFT_Item_Deathblade"."""
        return self._call_tool("tft_list_champions_for_item", {"item_id": item_id})
