"""DATA-12 pytest: patch_version 변경을 mock으로 주입해 배치 트리거 호출 여부를
확인한다(op.gg는 실 호출 안 함 — mock 오브젝트로 대체, policies.md 10.2/11).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db_session import models
from patch_detection import (
    PatchDetectionError,
    get_current_patch_version,
    get_latest_patch_version,
    run_patch_detection,
)


class _FakeOpggClient:
    def __init__(self, version: str | None) -> None:
        self._version = version

    def list_item_combinations(self) -> dict:
        if self._version is None:
            return {"set": 17, "data": []}  # version 필드 자체가 없는 케이스
        return {"set": 17, "version": self._version, "data": []}


def test_get_latest_patch_version_returns_version_field() -> None:
    assert get_latest_patch_version(_FakeOpggClient("17.9")) == "17.9"


def test_get_latest_patch_version_raises_when_field_missing() -> None:
    with pytest.raises(PatchDetectionError):
        get_latest_patch_version(_FakeOpggClient(None))


@pytest.fixture
def db_session(migrated_engine: Engine) -> Session:
    with Session(migrated_engine) as session:
        yield session


def test_get_current_patch_version_returns_none_when_no_patch(
    db_session: Session,
) -> None:
    assert get_current_patch_version(db_session) is None


def test_get_current_patch_version_returns_is_current_version(
    db_session: Session,
) -> None:
    db_session.add(
        models.Patch(
            version="17.7",
            set_number=17,
            released_at=datetime(2026, 1, 1, tzinfo=UTC),
            is_current=False,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    db_session.add(
        models.Patch(
            version="17.8",
            set_number=17,
            released_at=datetime(2026, 1, 15, tzinfo=UTC),
            is_current=True,
            detected_at=datetime(2026, 1, 15, tzinfo=UTC),
        )
    )
    db_session.commit()

    assert get_current_patch_version(db_session) == "17.8"


def test_run_patch_detection_triggers_when_no_current_patch(
    db_session: Session,
) -> None:
    calls = []
    result = run_patch_detection(
        db_session,
        _FakeOpggClient("17.8"),
        lambda before, after: calls.append((before, after)),
    )

    assert result.triggered is True
    assert result.patch_version_before is None
    assert result.patch_version_after == "17.8"
    assert calls == [(None, "17.8")]


def test_run_patch_detection_skips_when_version_unchanged(db_session: Session) -> None:
    db_session.add(
        models.Patch(
            version="17.8",
            set_number=17,
            released_at=datetime(2026, 1, 1, tzinfo=UTC),
            is_current=True,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    db_session.commit()

    calls = []
    result = run_patch_detection(
        db_session,
        _FakeOpggClient("17.8"),
        lambda before, after: calls.append((before, after)),
    )

    assert result.triggered is False
    assert calls == []


def test_run_patch_detection_triggers_when_version_changed(db_session: Session) -> None:
    db_session.add(
        models.Patch(
            version="17.8",
            set_number=17,
            released_at=datetime(2026, 1, 1, tzinfo=UTC),
            is_current=True,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    db_session.commit()

    calls = []
    result = run_patch_detection(
        db_session,
        _FakeOpggClient("17.9"),
        lambda before, after: calls.append((before, after)),
    )

    assert result.triggered is True
    assert calls == [("17.8", "17.9")]


def test_run_patch_detection_records_run_log(db_session: Session) -> None:
    run_patch_detection(db_session, _FakeOpggClient("17.8"), lambda before, after: None)
    db_session.commit()

    runs = db_session.scalars(select(models.PatchDetectionRun)).all()
    assert len(runs) == 1
    assert runs[0].status == "triggered"
    assert runs[0].patch_version_before == "(none)"
    assert runs[0].patch_version_after == "17.8"
    assert runs[0].duration_ms >= 0


def test_run_patch_detection_does_not_call_trigger_on_no_op(
    db_session: Session,
) -> None:
    db_session.add(
        models.Patch(
            version="17.8",
            set_number=17,
            released_at=datetime(2026, 1, 1, tzinfo=UTC),
            is_current=True,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    db_session.commit()

    def _fail_if_called(before: str | None, after: str) -> None:
        raise AssertionError("변경이 없는데 트리거가 호출됨")

    run_patch_detection(db_session, _FakeOpggClient("17.8"), _fail_if_called)
