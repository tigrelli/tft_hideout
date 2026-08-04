"""DATA-09: Community Dragon 기반 챔피언/특성 ID→이름 매핑.

DATA-06 스파이크(docs/spike/tft-ddragon.md) 결론에 따라 공식 "TFT DDragon" 분리
엔드포인트가 아직 없어 Community Dragon(raw.communitydragon.org)을 소스로 쓴다.
op.gg MCP 응답(DATA-08)은 챔피언(characterId/key)과 특성(traits[].key)에 표시
이름을 포함하지 않으므로(아이템·증강체는 op.gg 응답 자체에 이름이 있어 대상 아님)
이 매핑으로 보충한다(개발설계서 4.3 "이름 매핑에만 보조로 사용").
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Self

import httpx

DEFAULT_BASE_URL = "https://raw.communitydragon.org"
_SET_PREFIX_PATTERN = re.compile(r"^tft\d*_", re.IGNORECASE)


class CommunityDragonError(Exception):
    """Community Dragon 조회 실패."""


class CommunityDragonClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url, timeout=timeout, transport=transport
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._http.close()

    def fetch_tft_data(
        self, lang: str = "ko_kr", version: str = "latest"
    ) -> dict[str, Any]:
        """TFT 전체 데이터(items/setData/sets)를 조회한다. lang 예: "ko_kr", "en_us"."""
        try:
            response = self._http.get(f"/{version}/cdragon/tft/{lang}.json")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise CommunityDragonError(f"Community Dragon 조회 실패: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise CommunityDragonError(
                f"Community Dragon 응답 파싱 실패: {exc}"
            ) from exc


@dataclass
class NameMaps:
    """특정 세트 하나에 대한 apiName → 표시 이름 매핑."""

    champions: dict[str, str] = field(default_factory=dict)
    traits: dict[str, str] = field(default_factory=dict)

    def champion_name(self, champion_id: str) -> str:
        return self.champions.get(champion_id, _fallback_name(champion_id))

    def trait_name(self, trait_id: str) -> str:
        return self.traits.get(trait_id, _fallback_name(trait_id))


def build_name_maps(tft_data: dict[str, Any], set_number: int) -> NameMaps:
    """tft_data(fetch_tft_data 결과)에서 set_number에 해당하는 setData 항목을 찾아
    챔피언/특성 이름 매핑을 만든다. 해당 세트가 아직 없으면(예: Set 18 런칭 전)
    빈 매핑을 반환한다 — 예외를 던지지 않고 champion_name/trait_name의 폴백에 맡긴다.
    """
    for entry in tft_data.get("setData", []):
        if entry.get("number") != set_number:
            continue
        champions = {c["apiName"]: c["name"] for c in entry.get("champions", [])}
        traits = {t["apiName"]: t["name"] for t in entry.get("traits", [])}
        return NameMaps(champions=champions, traits=traits)
    return NameMaps()


def _fallback_name(raw_id: str) -> str:
    """매핑 누락 시 폴백: "TFT17_BlueGolem" -> "BlueGolem"처럼 세트 접두어만 제거해
    최소한 읽을 수 있는 이름을 돌려준다. 배치를 예외로 중단시키지 않는 것이 목적."""
    return _SET_PREFIX_PATTERN.sub("", raw_id)
