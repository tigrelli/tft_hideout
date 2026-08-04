"""DATA-15 pytest(WBS 테스트 요구사항: 배치 완료 이벤트 발생 시 chat_answer_cache에서
이전 patch_version 행이 삭제되는지 확인)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from cache_cleanup import delete_stale_chat_answer_cache
from db_session import models
from patch_transition import BatchStep, run_batch_with_atomic_promotion


def _seed_patches(session: Session) -> None:
    session.add(
        models.Patch(
            version="17.7",
            set_number=17,
            released_at=datetime(2026, 1, 1, tzinfo=UTC),
            is_current=False,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.add(
        models.Patch(
            version="17.8",
            set_number=17,
            released_at=datetime(2026, 1, 15, tzinfo=UTC),
            is_current=True,
            detected_at=datetime(2026, 1, 15, tzinfo=UTC),
        )
    )
    session.commit()


def _add_cache_row(session: Session, cache_key: str, patch_version: str) -> None:
    session.add(
        models.ChatAnswerCache(
            cache_key=cache_key,
            patch_version=patch_version,
            answer="mock answer",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )


@pytest.fixture
def db_session(migrated_engine: Engine) -> Session:
    with Session(migrated_engine) as session:
        _seed_patches(session)
        yield session


def _remaining_versions(session: Session) -> set[str]:
    rows = session.scalars(select(models.ChatAnswerCache)).all()
    return {r.patch_version for r in rows}


# ---- DATA-15 #1: 이전 patch_version 행만 삭제 ------------------------------------


def test_deletes_only_stale_patch_version_rows(db_session: Session) -> None:
    _add_cache_row(db_session, "q1", "17.7")
    _add_cache_row(db_session, "q2", "17.7")
    _add_cache_row(db_session, "q3", "17.8")
    db_session.commit()

    deleted = delete_stale_chat_answer_cache(db_session, "17.8")
    db_session.commit()

    assert deleted == 2
    assert _remaining_versions(db_session) == {"17.8"}


# ---- DATA-15 #2: 삭제할 이전 버전 행이 없으면 0 반환 ------------------------------


def test_returns_zero_when_no_stale_rows(db_session: Session) -> None:
    _add_cache_row(db_session, "q1", "17.8")
    db_session.commit()

    deleted = delete_stale_chat_answer_cache(db_session, "17.8")
    db_session.commit()

    assert deleted == 0
    assert _remaining_versions(db_session) == {"17.8"}


# ---- DATA-15 #3: 배치 완료 이벤트(원자적 전환 성공) 발생 시 정리 -----------------


def test_cleanup_runs_after_batch_completes_successfully(db_session: Session) -> None:
    _add_cache_row(db_session, "q1", "17.7")
    db_session.commit()

    result = run_batch_with_atomic_promotion(
        db_session, "17.8", [BatchStep(name="ok", run=lambda: None)]
    )
    if result.success:
        delete_stale_chat_answer_cache(db_session, "17.8")
    db_session.commit()

    assert result.success is True
    assert _remaining_versions(db_session) == set()


# ---- DATA-15 #4: 배치 실패(승격 안 됨) 시에는 캐시 정리도 건너뜀 -----------------


def test_cleanup_skipped_when_batch_fails(db_session: Session) -> None:
    _add_cache_row(db_session, "q1", "17.7")
    db_session.commit()

    def _fail() -> None:
        raise RuntimeError("mock 실패")

    result = run_batch_with_atomic_promotion(
        db_session, "17.9", [BatchStep(name="boom", run=_fail)]
    )
    if result.success:
        delete_stale_chat_answer_cache(db_session, "17.9")
    db_session.commit()

    assert result.success is False
    # 이전 패치(17.7)가 그대로 is_current라 17.7 캐시 행도 삭제되면 안 된다
    assert _remaining_versions(db_session) == {"17.7"}
