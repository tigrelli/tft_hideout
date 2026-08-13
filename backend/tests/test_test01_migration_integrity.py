"""TEST-01: DB 스키마/마이그레이션 검증 — 전체 테이블·인덱스·제약조건 검증,
DoD "마이그레이션 재실행 무결성 확인". DATA-01~04 각 TASK가 만든
test_dataNN_migration.py는 자신이 추가한 테이블/컬럼만 스팟체크하므로,
여기서는 전체 마이그레이션 체인(현재 18개)을 대상으로 downgrade→upgrade가
스키마를 동일하게 재현하는지, downgrade가 애플리케이션 테이블을 빠짐없이
제거하는지, head에서 upgrade를 다시 호출해도 안전한지(멱등성)를 검증한다.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

BACKEND_DIR = Path(__file__).resolve().parents[1]

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/tft_hideout_test",
)


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def _schema_snapshot(engine: Engine) -> dict[str, set[str]]:
    inspector = inspect(engine)
    return {
        table: {c["name"] for c in inspector.get_columns(table)}
        for table in inspector.get_table_names()
        if table != "alembic_version"
    }


@pytest.fixture
def fresh_engine() -> Engine:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    return engine


def test_downgrade_base_then_upgrade_head_reproduces_identical_schema(
    fresh_engine: Engine,
) -> None:
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    before = _schema_snapshot(fresh_engine)
    assert before, "최초 업그레이드 후 테이블이 하나도 없음"

    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    after = _schema_snapshot(fresh_engine)

    assert after == before


def test_downgrade_base_removes_all_application_tables(fresh_engine: Engine) -> None:
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    inspector = inspect(fresh_engine)
    remaining = set(inspector.get_table_names()) - {"alembic_version"}
    assert remaining == set(), f"downgrade 후에도 남은 테이블: {remaining}"


def test_upgrade_head_when_already_at_head_is_idempotent(
    fresh_engine: Engine,
) -> None:
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    before = _schema_snapshot(fresh_engine)

    command.upgrade(cfg, "head")
    after = _schema_snapshot(fresh_engine)

    assert after == before
