"""CHAT-36 마이그레이션 pytest: meta_document_embeddings.embedding nullable 전환 +
pg_trgm 확장 설치, downgrade 시 벡터 없는 행 정리 후 NOT NULL 복원."""

from __future__ import annotations

from datetime import UTC, datetime

from alembic.config import Config
from sqlalchemy import inspect, insert, text
from sqlalchemy.engine import Engine

from alembic import command
from db.models import MetaDocumentEmbedding, Patch
from tests.conftest import BACKEND_DIR

CHAT36_REVISION = "3c6d2e9a1f47"
PREVIOUS_REVISION = "52c529032f95"


def _alembic_cfg() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def _embedding_nullable(engine: Engine) -> bool:
    columns = inspect(engine).get_columns("meta_document_embeddings")
    return next(c for c in columns if c["name"] == "embedding")["nullable"]


def _has_pg_trgm(engine: Engine) -> bool:
    with engine.connect() as conn:
        return (
            conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
            ).first()
            is not None
        )


def test_upgrade_makes_embedding_nullable_and_installs_pg_trgm(
    migrated_engine: Engine,
) -> None:
    assert _embedding_nullable(migrated_engine) is True
    assert _has_pg_trgm(migrated_engine) is True


def test_downgrade_drops_vectorless_rows_and_restores_not_null(
    migrated_engine: Engine,
) -> None:
    with migrated_engine.begin() as conn:
        conn.execute(
            insert(Patch).values(
                version="17.8",
                set_number=17,
                released_at=datetime(2026, 1, 1, tzinfo=UTC),
                is_current=True,
                detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        # CHAT-36 이후 배치가 넣는 벡터 없는 행과, 그 이전 배치가 남긴 벡터 행
        conn.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="augment",
                source_table="augments",
                source_id=1,
                content_text="벡터 없음",
                doc_metadata={},
            )
        )
        conn.execute(
            insert(MetaDocumentEmbedding).values(
                patch_version="17.8",
                doc_type="augment",
                source_table="augments",
                source_id=2,
                content_text="벡터 있음",
                embedding=[0.1] * 1024,
                doc_metadata={},
            )
        )

    cfg = _alembic_cfg()
    command.downgrade(cfg, PREVIOUS_REVISION)

    assert _embedding_nullable(migrated_engine) is False
    assert _has_pg_trgm(migrated_engine) is False
    with migrated_engine.connect() as conn:
        remaining = conn.execute(
            text("SELECT content_text FROM meta_document_embeddings")
        ).scalars()
        assert list(remaining) == ["벡터 있음"]

    command.upgrade(cfg, CHAT36_REVISION)
    assert _embedding_nullable(migrated_engine) is True
    assert _has_pg_trgm(migrated_engine) is True
