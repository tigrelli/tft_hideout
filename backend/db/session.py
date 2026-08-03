import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL 환경변수가 설정되어 있지 않습니다")
    return url


engine = create_engine(get_database_url())
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
