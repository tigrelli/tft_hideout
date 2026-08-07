from sqlalchemy import inspect
from sqlalchemy.engine import Engine

EXPECTED_TABLES: dict[str, set[str]] = {
    "patches": {
        "id",
        "version",
        "set_number",
        "released_at",
        "is_current",
        "detected_at",
    },
    "champions": {
        "id",
        "patch_version",
        "riot_champion_id",
        "name_kr",
        "name_en",
        "cost",
        "square_icon_url",
    },
    "traits": {
        "id",
        "patch_version",
        "riot_trait_id",
        "name_kr",
        "name_en",
        "tier_thresholds",
    },
    "champion_traits": {"champion_id", "trait_id"},
    "items": {
        "id",
        "patch_version",
        "name_kr",
        "name_en",
        "item_type",
        "riot_item_id",
        "components",
        "stats",
        "square_icon_url",
        "description",
    },
    "augments": {
        "id",
        "patch_version",
        "name_kr",
        "name_en",
        "tier",
        "description",
        "is_legend_related",
        "riot_augment_id",
        "win_rate",
        "image_url",
    },
}

JSONB_COLUMNS: dict[str, set[str]] = {
    "traits": {"tier_thresholds"},
    "items": {"components", "stats"},
}


def test_all_static_tables_created(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    table_names = set(inspector.get_table_names())
    for table in EXPECTED_TABLES:
        assert table in table_names, f"{table} 테이블이 생성되지 않음"


def test_static_table_columns_match_schema(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    for table, expected_columns in EXPECTED_TABLES.items():
        actual_columns = {c["name"] for c in inspector.get_columns(table)}
        assert actual_columns == expected_columns, (
            f"{table} 컬럼 불일치: {actual_columns}"
        )


def test_jsonb_columns_use_jsonb_type(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    for table, jsonb_cols in JSONB_COLUMNS.items():
        columns = {c["name"]: str(c["type"]) for c in inspector.get_columns(table)}
        for col in jsonb_cols:
            assert columns[col] == "JSONB", f"{table}.{col}는 JSONB 타입이어야 함"


def test_champion_traits_is_junction_table(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    pk = inspector.get_pk_constraint("champion_traits")
    assert set(pk["constrained_columns"]) == {"champion_id", "trait_id"}

    fks = inspector.get_foreign_keys("champion_traits")
    referred_tables = {fk["referred_table"] for fk in fks}
    assert referred_tables == {"champions", "traits"}


def test_patches_version_is_unique(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    unique_constraints = inspector.get_unique_constraints("patches")
    unique_columns = {col for uc in unique_constraints for col in uc["column_names"]}
    assert "version" in unique_columns
