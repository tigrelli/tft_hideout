"""배치가 쓰는 DB 세션. 테이블 정의(Alembic 마이그레이션·ORM 모델)는 backend/에만
두고(단일 소스), batch는 backend/db/models.py를 그대로 재사용해 두 곳에 스키마가
따로 관리되며 어긋나는 걸 방지한다(둘 다 같은 저장소·같은 DB를 공유하므로).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from db import models  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL 환경변수가 설정되어 있지 않습니다")
    return url


def create_session(database_url: str | None = None) -> Session:
    engine = create_engine(database_url or get_database_url())
    return sessionmaker(bind=engine)()


__all__ = ["create_session", "get_database_url", "models"]
