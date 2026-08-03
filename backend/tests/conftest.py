import os
import sys
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/tft_hideout_test",
)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """RateLimitMiddleware(API-07)의 전역 버킷을 매 테스트마다 초기화해
    테스트 간 요청 수 누적으로 인한 스퓨리어스 429를 방지한다."""
    from middleware.rate_limit import reset_buckets

    reset_buckets()
    yield
    reset_buckets()


@pytest.fixture
def migrated_engine() -> Engine:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))

    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    command.upgrade(alembic_cfg, "head")
    return engine
