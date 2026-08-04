"""DATABASE_URL이 드라이버 미지정 형태로 와도 psycopg(v3)를 쓰도록 정규화하는지
검증한다(backend/db/session.py와 동일 처리, 2026-08-04 실제로 겪은 문제).
"""

import pytest

from db_session import get_database_url


def test_bare_postgresql_scheme_gets_psycopg_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host:5432/db")
    assert get_database_url() == "postgresql+psycopg://user:pw@host:5432/db"


def test_bare_postgres_scheme_gets_psycopg_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pw@host:5432/db")
    assert get_database_url() == "postgresql+psycopg://user:pw@host:5432/db"


def test_already_specified_driver_is_left_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@host:5432/db")
    assert get_database_url() == "postgresql+psycopg://user:pw@host:5432/db"


def test_missing_database_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_database_url()
