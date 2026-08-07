"""DATA-18: patch_version이 바뀌지 않아도 comps/comp_champions만 주기적으로
재수집한다.

op.gg tft_list_meta_decks는 patch_version과 무관하게 상시 메타 조합이
회전하는데(DATA-17, docs/spike/opgg-schema.md 8번 — 페이지네이션 없이 항상
상위 10개만 반환), DATA-12 `patch_detection.run_patch_detection()`은
patch_version이 바뀌었을 때만 전체 배치(정규화)를 실행해 이 회전을 놓친다
(FE-05·DATA-17에서 두 차례 재현, `docs/verification/DATA-17-작업결과.md`
"구조적 공백" 참고). 패치 감지·원자적 전환(DATA-13) 로직은 그대로 두고,
`run_patch_batch.main()`이 같은 크론(1일 1회) 안에서 patch_version이 안 바뀐
경우에만 이 모듈을 호출해 comps/comp_champions만 별도로 갱신한다.

챔피언 이름·ID 매핑은 이미 적재된 champions 테이블을 재사용한다(Community
Dragon을 다시 호출하지 않아 전체 배치보다 op.gg 호출 1회로 훨씬 가볍다)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

import db_session as batch_db
from normalize import (
    comp_champion_rows,
    comp_rows,
    mark_stale_comps_inactive,
    upsert_comp_champions,
    upsert_comps,
)
from opgg_client import OpggMcpClient

models = batch_db.models


@dataclass
class CompsRefreshResult:
    comp_count: int
    deactivated_count: int
    duration_ms: int


def refresh_comps(
    session: Session,
    opgg_client: OpggMcpClient,
    patch_version: str,
    *,
    now: datetime | None = None,
) -> CompsRefreshResult:
    """op.gg 최신 메타 조합으로 comps/comp_champions를 갱신하고
    `patch_detection_runs`에 결과를 기록한다(session.commit은 호출부 몫)."""
    start = time.monotonic()
    triggered_at = now or datetime.now(UTC)

    champions = session.execute(
        select(
            models.Champion.riot_champion_id,
            models.Champion.id,
            models.Champion.name_kr,
        ).where(models.Champion.patch_version == patch_version)
    ).all()
    champion_ids = {riot_id: db_id for riot_id, db_id, _ in champions}
    champion_names = {riot_id: name_kr for riot_id, _, name_kr in champions}

    meta_decks = opgg_client.list_meta_decks()
    comp_ids = upsert_comps(
        session, patch_version, comp_rows(meta_decks, champion_names)
    )
    deactivated = mark_stale_comps_inactive(
        session, patch_version, set(comp_ids.keys())
    )
    session.flush()
    for deck in meta_decks.get("data", []):
        comp_id = comp_ids.get(deck["id"])
        if comp_id is not None:
            upsert_comp_champions(
                session, comp_id, comp_champion_rows(deck), champion_ids
            )

    duration_ms = int((time.monotonic() - start) * 1000)
    session.add(
        models.PatchDetectionRun(
            triggered_at=triggered_at,
            patch_version_before=patch_version,
            patch_version_after=patch_version,
            duration_ms=duration_ms,
            status="comps_refreshed",
        )
    )

    return CompsRefreshResult(
        comp_count=len(comp_ids),
        deactivated_count=deactivated,
        duration_ms=duration_ms,
    )
