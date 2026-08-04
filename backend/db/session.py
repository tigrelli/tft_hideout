import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL 환경변수가 설정되어 있지 않습니다")
    # Supabase 등에서 그대로 복사한 연결 문자열은 드라이버 지정이 없는
    # "postgresql://"/"postgres://" 형태인 경우가 많다. 이 프로젝트는
    # psycopg2가 아니라 psycopg(v3)만 설치하므로(requirements.txt), SQLAlchemy가
    # 기본값인 psycopg2로 해석하지 않도록 명시적으로 +psycopg를 붙여준다
    # (이미 드라이버가 지정돼 있으면 그대로 둠) — 2026-08-04 GitHub Actions
    # 배치에서 ModuleNotFoundError: psycopg2로 실제로 겪은 문제.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


engine = create_engine(get_database_url())
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
