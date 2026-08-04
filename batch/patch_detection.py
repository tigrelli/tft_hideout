"""DATA-12: GitHub Actions 크론(매시간)에서 호출할 자동 패치 감지 트리거.

DATA-05 결정: op.gg 5개 도구 중 `tft_list_item_combinations().version`에만
패치 버전 신호가 있어 이를 1차 신호로 쓴다(PRD 9-1이 대비책으로 제시한 Riot
리더보드 샘플링은 불필요). 실제 "전체 배치 재수집"(정규화·임베딩·원자적 전환)
오케스트레이션은 DATA-13 이후 하나로 묶일 예정이라, 이 모듈은 감지 결과에 따라
주입받은 콜백(`on_trigger`)을 호출하는 것까지만 담당한다(동시 실행 방지는
DATA-14의 GitHub Actions concurrency 설정 몫, 여기서 다루지 않음).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

import db_session as batch_db
from opgg_client import OpggMcpClient

models = batch_db.models

OnTrigger = Callable[[str | None, str], None]


class PatchDetectionError(Exception):
    """op.gg 응답에 patch_version 상당 필드가 없는 등 감지 자체가 실패한 경우."""


@dataclass
class PatchDetectionResult:
    triggered: bool
    patch_version_before: str | None
    patch_version_after: str
    duration_ms: int


def get_current_patch_version(session: Session) -> str | None:
    """patches.is_current=true인 버전을 반환. 아직 없으면(최초 실행) None."""
    return session.scalar(select(models.Patch.version).where(models.Patch.is_current))


def get_latest_patch_version(opgg_client: OpggMcpClient) -> str:
    """op.gg tft_list_item_combinations().version을 최신 패치 신호로 사용한다."""
    data = opgg_client.list_item_combinations()
    version = data.get("version")
    if not version:
        raise PatchDetectionError(
            "op.gg tft_list_item_combinations 응답에 version 필드가 없습니다"
        )
    return str(version)


def run_patch_detection(
    session: Session,
    opgg_client: OpggMcpClient,
    on_trigger: OnTrigger,
    *,
    now: datetime | None = None,
) -> PatchDetectionResult:
    """현재 DB의 is_current 패치와 op.gg 최신 버전을 비교해 다르면 on_trigger를
    호출하고, 결과를 patch_detection_runs에 기록한다(session.commit은 호출부 몫)."""
    start = time.monotonic()
    triggered_at = now or datetime.now(UTC)

    before = get_current_patch_version(session)
    after = get_latest_patch_version(opgg_client)
    triggered = before != after

    if triggered:
        on_trigger(before, after)

    duration_ms = int((time.monotonic() - start) * 1000)
    session.add(
        models.PatchDetectionRun(
            triggered_at=triggered_at,
            patch_version_before=before or "(none)",
            patch_version_after=after,
            duration_ms=duration_ms,
            status="triggered" if triggered else "skipped",
        )
    )

    return PatchDetectionResult(
        triggered=triggered,
        patch_version_before=before,
        patch_version_after=after,
        duration_ms=duration_ms,
    )
