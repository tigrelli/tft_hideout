"""DATA-13: 배치(수집→정규화→임베딩) 전체가 성공했을 때만 patches.is_current를
원자적으로 전환한다. 중간 실패 시 이전 패치를 그대로 유지한다.

설계 근거(개발설계서 4.3 para 49, schema.md 정합성 규칙): 각 단계(op.gg 수집,
DATA-10 정규화, DATA-11 임베딩)는 실행 도중 이미 DB에 커밋될 수 있다(새
patch_version으로 태깅된 채) — 이건 정상이다. 이 모듈이 보장하는 건 오직
"모든 단계가 성공해야만 `patches.is_current`가 새 버전을 가리킨다"는 것 하나뿐이고,
그 전환 자체는 이 모듈의 `promote_patch_to_current()` 한 트랜잭션(커밋 전까지는
이전 버전이 계속 is_current)으로 이뤄진다.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

import db_session as batch_db

models = batch_db.models


@dataclass
class BatchStep:
    name: str
    run: Callable[[], Any]


@dataclass
class BatchRunResult:
    success: bool
    failed_step: str | None
    patch_version_before: str | None
    patch_version_after: str
    duration_ms: int


def promote_patch_to_current(session: Session, new_version: str) -> None:
    """단일 트랜잭션: 기존 is_current 행을 False로, new_version 행을 True로.
    이 함수를 호출하고 session.commit()하기 전까지는 이전 버전이 계속
    is_current=true로 남는다(동시 조회 시 반쯤 갱신된 상태가 노출되지 않음)."""
    session.execute(
        update(models.Patch)
        .where(models.Patch.is_current.is_(True))
        .values(is_current=False)
    )
    result = session.execute(
        update(models.Patch)
        .where(models.Patch.version == new_version)
        .values(is_current=True)
    )
    if result.rowcount == 0:
        raise ValueError(
            f"patches에 version={new_version!r} 행이 없습니다(먼저 ensure_patch 필요)"
        )


def run_batch_with_atomic_promotion(
    session: Session,
    new_version: str,
    steps: list[BatchStep],
    *,
    now: datetime | None = None,
) -> BatchRunResult:
    """steps를 순서대로 실행한다. 하나라도 예외가 나면 그 즉시 중단하고 이후 단계는
    실행하지 않는다 — `promote_patch_to_current`가 호출되지 않으므로 is_current는
    이전 값 그대로 유지된다. 예외는 삼키고(배치 크론이 죽지 않도록) 결과 객체와
    `patch_detection_runs` 로그로 성공/실패를 알린다(TEST-00 DATA-13 #5)."""
    start = time.monotonic()
    triggered_at = now or datetime.now(UTC)
    before = session.scalar(
        select(models.Patch.version).where(models.Patch.is_current.is_(True))
    )

    failed_step: str | None = None
    for step in steps:
        try:
            step.run()
        except Exception:  # noqa: BLE001 - 배치 크론을 죽이지 않고 결과로 알림
            failed_step = step.name
            break

    success = failed_step is None
    if success:
        promote_patch_to_current(session, new_version)

    duration_ms = int((time.monotonic() - start) * 1000)
    session.add(
        models.PatchDetectionRun(
            triggered_at=triggered_at,
            patch_version_before=before or "(none)",
            patch_version_after=new_version,
            duration_ms=duration_ms,
            status="success" if success else "failed",
        )
    )

    return BatchRunResult(
        success=success,
        failed_step=failed_step,
        patch_version_before=before,
        patch_version_after=new_version,
        duration_ms=duration_ms,
    )
