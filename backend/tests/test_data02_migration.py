import pytest
from sqlalchemy import insert, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from db.models import CompAugment, CompChampion

EXPECTED_TABLES: dict[str, set[str]] = {
    "comps": {
        "id",
        "patch_version",
        "riot_comp_id",
        "name",
        "tier_rank",
        "avg_place",
        "play_rate",
        "win_rate",
        "playstyle_text",
        "updated_at",
        "is_active",
    },
    "comp_champions": {
        "comp_id",
        "champion_id",
        "is_carry",
        "recommended_items",
        "cell_x",
        "cell_y",
        "star_level",
    },
    "comp_augments": {"comp_id", "augment_id", "priority"},
    "champion_item_builds": {
        "id",
        "champion_id",
        "patch_version",
        "item_combination",
        "play_rate",
        "avg_place",
        "win_rate",
    },
}


def test_all_meta_comp_tables_created(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    table_names = set(inspector.get_table_names())
    for table in EXPECTED_TABLES:
        assert table in table_names, f"{table} 테이블이 생성되지 않음"


def test_meta_comp_table_columns_match_schema(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    for table, expected_columns in EXPECTED_TABLES.items():
        actual_columns = {c["name"] for c in inspector.get_columns(table)}
        assert actual_columns == expected_columns, (
            f"{table} 컬럼 불일치: {actual_columns}"
        )


def test_comp_champions_fk_violation_raises_integrity_error(
    migrated_engine: Engine,
) -> None:
    with pytest.raises(IntegrityError), migrated_engine.begin() as conn:
        conn.execute(
            insert(CompChampion).values(
                comp_id=9999,
                champion_id=9999,
                is_carry=True,
                recommended_items=[],
            )
        )


def test_comp_augments_fk_violation_raises_integrity_error(
    migrated_engine: Engine,
) -> None:
    with pytest.raises(IntegrityError), migrated_engine.begin() as conn:
        conn.execute(
            insert(CompAugment).values(comp_id=9999, augment_id=9999, priority=1)
        )
