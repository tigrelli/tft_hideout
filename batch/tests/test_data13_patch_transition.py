"""DATA-13 pytest(TEST-00 시나리오 그대로 옮김, docs/test-scenarios.md DATA-13):
배치 중간 강제 실패 주입 시 is_current가 이전 값을 유지하는지, 전체 성공 시에만
전환되는지 검증한다.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db_session import models
from patch_transition import (
    BatchStep,
    promote_patch_to_current,
    run_batch_with_atomic_promotion,
)


def _seed_patches(session: Session) -> None:
    session.add(
        models.Patch(
            version="17.7",
            set_number=17,
            released_at=datetime(2026, 1, 1, tzinfo=UTC),
            is_current=True,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.add(
        models.Patch(
            version="17.8",
            set_number=17,
            released_at=datetime(2026, 1, 15, tzinfo=UTC),
            is_current=False,
            detected_at=datetime(2026, 1, 15, tzinfo=UTC),
        )
    )
    session.commit()


@pytest.fixture
def db_session(migrated_engine: Engine) -> Session:
    with Session(migrated_engine) as session:
        _seed_patches(session)
        yield session


def _current_version(session: Session) -> str | None:
    return session.scalar(
        select(models.Patch.version).where(models.Patch.is_current.is_(True))
    )


# ---- TEST-00 DATA-13 #1: 전체 성공 시 전환 --------------------------------------


def test_all_steps_succeed_promotes_new_patch(db_session: Session) -> None:
    ran = []
    steps = [BatchStep(name=n, run=lambda n=n: ran.append(n)) for n in ["a", "b", "c"]]

    result = run_batch_with_atomic_promotion(db_session, "17.8", steps)
    db_session.commit()

    assert result.success is True
    assert result.failed_step is None
    assert ran == ["a", "b", "c"]
    assert _current_version(db_session) == "17.8"

    old = db_session.scalar(select(models.Patch).where(models.Patch.version == "17.7"))
    assert old.is_current is False


# ---- TEST-00 DATA-13 #2: 중간(4번째/6개 중) 실패 시 롤백 -------------------------


def test_failure_on_fourth_of_six_steps_keeps_previous_patch(
    db_session: Session,
) -> None:
    ran = []

    def _fail():
        raise RuntimeError("op.gg 4번째 도구 호출 실패(mock)")

    steps = [
        BatchStep(name=n, run=lambda n=n: ran.append(n))
        for n in ["meta_decks", "item_combinations", "augments"]
    ] + [
        BatchStep(name="champion_builds", run=_fail),
        BatchStep(name="normalize", run=lambda: ran.append("normalize")),
        BatchStep(name="embed", run=lambda: ran.append("embed")),
    ]

    result = run_batch_with_atomic_promotion(db_session, "17.8", steps)
    db_session.commit()

    assert result.success is False
    assert result.failed_step == "champion_builds"
    assert ran == ["meta_decks", "item_combinations", "augments"]  # 4번째 이후는 미실행
    assert _current_version(db_session) == "17.7"  # 이전 패치 그대로


# ---- TEST-00 DATA-13 #3: 마지막(임베딩) 단계 실패해도 전환 안 됨 -----------------


def test_failure_on_last_step_still_keeps_previous_patch(db_session: Session) -> None:
    # 앞 단계(정규화 흉내)가 실제로 DB에 커밋 가능한 행을 만들어도(부분 적재)
    # is_current는 전환되지 않아야 한다.
    def _partial_normalize():
        db_session.add(
            models.Champion(
                patch_version="17.8",
                riot_champion_id="TFT17_Partial",
                name_kr="부분적재",
                name_en="Partial",
                cost=1,
            )
        )
        db_session.flush()

    def _fail_embedding():
        raise RuntimeError("임베딩 생성 실패(mock)")

    steps = [
        BatchStep(name="collect", run=lambda: None),
        BatchStep(name="normalize", run=_partial_normalize),
        BatchStep(name="embed", run=_fail_embedding),
    ]

    result = run_batch_with_atomic_promotion(db_session, "17.8", steps)
    db_session.commit()

    assert result.success is False
    assert result.failed_step == "embed"
    assert _current_version(db_session) == "17.7"

    # 부분 적재된 정규화 행은 그대로 남아있다(is_current만 안 바뀜)
    partial = db_session.scalar(
        select(models.Champion).where(
            models.Champion.riot_champion_id == "TFT17_Partial"
        )
    )
    assert partial is not None
    assert partial.patch_version == "17.8"


# ---- TEST-00 DATA-13 #4: 전환 도중 동시 조회 -------------------------------------


def test_concurrent_read_sees_old_patch_until_commit(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as setup:
        _seed_patches(setup)

    session_a = Session(migrated_engine)
    session_b = Session(migrated_engine)
    try:
        promote_patch_to_current(session_a, "17.8")  # 아직 커밋 안 함

        assert _current_version(session_b) == "17.7"  # 커밋 전: 다른 커넥션엔 이전 값

        session_a.commit()

        assert _current_version(session_b) == "17.8"  # 커밋 후: 새 값 보임
    finally:
        session_a.close()
        session_b.close()


# ---- TEST-00 DATA-13 #5: 배치 실행 로그 ------------------------------------------


def test_success_and_failure_both_recorded_in_patch_detection_runs(
    db_session: Session,
) -> None:
    run_batch_with_atomic_promotion(
        db_session, "17.8", [BatchStep(name="ok", run=lambda: None)]
    )
    db_session.commit()

    def _fail():
        raise RuntimeError("mock 실패")

    run_batch_with_atomic_promotion(
        db_session, "17.9", [BatchStep(name="boom", run=_fail)]
    )
    db_session.commit()

    runs = db_session.scalars(
        select(models.PatchDetectionRun).order_by(models.PatchDetectionRun.id)
    ).all()
    assert len(runs) == 2
    assert runs[0].status == "success"
    assert runs[0].patch_version_after == "17.8"
    assert runs[0].duration_ms >= 0
    assert runs[1].status == "failed"
    assert runs[1].patch_version_after == "17.9"
    assert runs[1].duration_ms >= 0


def test_promote_raises_if_target_version_row_missing(db_session: Session) -> None:
    with pytest.raises(ValueError, match="patches에"):
        promote_patch_to_current(db_session, "존재하지-않는-버전")
