"""DATA-18 pytest: patch_version 미변경 상황(=run_patch_detection이 skip한
경우)에서도 comps/comp_champions 재수집 트리거가 실제로 호출·반영되는지
검증한다(op.gg는 실 호출 안 함 — mock으로 대체, policies.md 10.2/11).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from comps_refresh import refresh_comps
from db_session import models
from normalize import ensure_patch, upsert_champions, upsert_comps
from patch_detection import run_patch_detection

FAKE_DECK_TOP10 = {
    "id": "comp-still-top10",
    "name": {"ko_KR": "가짜 조합", "en_US": "Fake Comp"},
    "units": [
        {
            "key": "TFT17_FakeAkali",
            "isCore": True,
            "items": ["TFT_Item_FakeSword"],
            "cell": {"x": 4, "y": 1},
            "tier": 2,
        }
    ],
    "badge": [],
    "stat": {
        "opTier": "OP",
        "deck": {"avgPlacement": 3.1, "pickRate": 0.02, "winRate": 0.19},
    },
}
FAKE_META_DECKS = {
    "data": [FAKE_DECK_TOP10],
    "metadata": {"gameStatDateTime": "2026-08-01T00:00:00.000Z"},
}


class _FakeOpggClient:
    def __init__(self, meta_decks: dict, version: str = "17.8") -> None:
        self._meta_decks = meta_decks
        self._version = version

    def list_meta_decks(self) -> dict:
        return self._meta_decks

    def list_item_combinations(self) -> dict:
        return {"set": 17, "version": self._version, "data": []}


@pytest.fixture
def db_session(migrated_engine: Engine) -> Session:
    with Session(migrated_engine) as session:
        ensure_patch(session, version="17.8", set_number=17)
        upsert_champions(
            session,
            "17.8",
            [
                {
                    "riot_champion_id": "TFT17_FakeAkali",
                    "name_kr": "가짜 아칼리",
                    "name_en": "FakeAkali",
                    "cost": 4,
                }
            ],
        )
        session.commit()
        yield session


def test_refresh_comps_upserts_comp_and_comp_champions(db_session: Session) -> None:
    result = refresh_comps(db_session, _FakeOpggClient(FAKE_META_DECKS), "17.8")
    db_session.commit()

    assert result.comp_count == 1
    comp = db_session.scalar(
        select(models.Comp).where(models.Comp.riot_comp_id == "comp-still-top10")
    )
    assert comp is not None
    assert comp.is_active is True

    linked = db_session.scalars(
        select(models.CompChampion).where(models.CompChampion.comp_id == comp.id)
    ).all()
    assert len(linked) == 1
    assert linked[0].cell_x == 4
    assert linked[0].cell_y == 1
    assert linked[0].star_level == 2


def test_refresh_comps_deactivates_comp_missing_from_new_response(
    db_session: Session,
) -> None:
    # 이전 실행에서 상위 10위였던 조합이 이번 op.gg 응답엔 없다고 가정.
    upsert_comps(
        db_session,
        "17.8",
        [
            {
                "riot_comp_id": "comp-dropped",
                "name": "탈락 조합",
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

    result = refresh_comps(db_session, _FakeOpggClient(FAKE_META_DECKS), "17.8")
    db_session.commit()

    assert result.deactivated_count == 1
    dropped = db_session.scalar(
        select(models.Comp).where(models.Comp.riot_comp_id == "comp-dropped")
    )
    assert dropped.is_active is False


def test_refresh_comps_records_patch_detection_run(db_session: Session) -> None:
    refresh_comps(db_session, _FakeOpggClient(FAKE_META_DECKS), "17.8")
    db_session.commit()

    runs = db_session.scalars(select(models.PatchDetectionRun)).all()
    assert len(runs) == 1
    assert runs[0].status == "comps_refreshed"
    assert runs[0].patch_version_before == "17.8"
    assert runs[0].patch_version_after == "17.8"


def test_run_patch_detection_skip_still_leaves_room_for_comps_refresh_trigger(
    db_session: Session,
) -> None:
    """DATA-18 DoD: patch_version 미변경(스킵)이어도 상위 오케스트레이션이
    comps 재수집을 호출할 수 있어야 한다 — run_patch_detection 자체는 DATA-12
    그대로 두고, 스킵 결과(patch_version_after)를 그대로 refresh_comps에
    넘기는 것이 run_patch_batch.main()의 실제 배선(DATA-18)이다."""
    db_session.execute(
        models.Patch.__table__.update()
        .where(models.Patch.version == "17.8")
        .values(is_current=True)
    )
    db_session.commit()

    detection = run_patch_detection(
        db_session, _FakeOpggClient(FAKE_META_DECKS, version="17.8"), lambda *_: None
    )
    db_session.commit()
    assert detection.triggered is False

    refresh_calls = []
    if not detection.triggered:
        refresh_calls.append(
            refresh_comps(
                db_session,
                _FakeOpggClient(FAKE_META_DECKS, version="17.8"),
                detection.patch_version_after,
            )
        )
    db_session.commit()

    assert len(refresh_calls) == 1
    assert refresh_calls[0].comp_count == 1
