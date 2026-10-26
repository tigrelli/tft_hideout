"""DATA-25 마이그레이션 pytest: champion_item_builds (patch_version, champion_id)
인덱스 생성·제거, 그리고 패치 조건 DELETE가 실제로 이 인덱스를 쓰는지 확인."""

from __future__ import annotations

from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from alembic import command
from tests.conftest import BACKEND_DIR

DATA25_REVISION = "8e1b4c7d2a90"
PREVIOUS_REVISION = "3c6d2e9a1f47"
INDEX_NAME = "ix_champion_item_builds_patch_champion"


def _alembic_cfg() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def _index_columns(engine: Engine) -> dict[str, list[str]]:
    return {
        ix["name"]: ix["column_names"]
        for ix in inspect(engine).get_indexes("champion_item_builds")
    }


def test_upgrade_creates_patch_champion_index(migrated_engine: Engine) -> None:
    assert _index_columns(migrated_engine)[INDEX_NAME] == [
        "patch_version",
        "champion_id",
    ]


def test_patch_scoped_delete_uses_index_instead_of_seq_scan(
    migrated_engine: Engine,
) -> None:
    """배치의 패치 단위 DELETE(normalize.replace_patch_item_builds)가 전체 순차
    스캔 대신 이 인덱스를 쓰는지 실행 계획으로 확인한다(테스트 DB는 행이 적어
    플래너가 seq scan을 고를 수 있어 enable_seqscan을 꺼서 사용 가능 여부만 본다)."""
    with migrated_engine.begin() as conn:
        conn.execute(text("SET LOCAL enable_seqscan = off"))
        plan = "\n".join(
            row[0]
            for row in conn.execute(
                text(
                    "EXPLAIN DELETE FROM champion_item_builds "
                    "WHERE patch_version = '18.5'"
                )
            )
        )
    assert INDEX_NAME in plan


def test_downgrade_drops_index(migrated_engine: Engine) -> None:
    cfg = _alembic_cfg()
    command.downgrade(cfg, PREVIOUS_REVISION)
    assert INDEX_NAME not in _index_columns(migrated_engine)

    command.upgrade(cfg, DATA25_REVISION)
    assert INDEX_NAME in _index_columns(migrated_engine)
