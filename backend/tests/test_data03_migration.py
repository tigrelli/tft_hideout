from sqlalchemy import inspect
from sqlalchemy.engine import Engine

EXPECTED_TABLES: dict[str, set[str]] = {
    "match_analyses": {
        "id",
        "match_id",
        "puuid",
        "patch_version",
        "comp_deviation",
        "item_concentration",
        "augment_synergy",
        "matched_comp_id",
        "coaching_text",
        "created_at",
    },
    "chat_logs": {
        "id",
        "session_id",
        "patch_version",
        "user_query",
        "intent",
        "retrieved_doc_ids",
        "answer",
        "latency_ms",
        "cold_start",
        "created_at",
    },
    "link_click_events": {
        "id",
        "session_id",
        "chat_log_id",
        "target_page",
        "clicked_at",
    },
    "account_link_events": {
        "id",
        "riot_id_hash",
        "region",
        "event_type",
        "match_id",
        "latency_ms",
        "created_at",
    },
    "patch_detection_runs": {
        "id",
        "triggered_at",
        "patch_version_before",
        "patch_version_after",
        "duration_ms",
        "status",
    },
    "ragas_eval_results": {
        "id",
        "eval_date",
        "sample_query",
        "faithfulness_score",
        "answer_relevancy_score",
        "patch_version",
    },
    "chat_answer_cache": {"id", "cache_key", "patch_version", "answer", "created_at"},
    "puuid_cache": {"id", "cache_key", "puuid", "expires_at", "created_at"},
}

# schema.md/개발설계서 5.1·5.3에 "(nullable)"로 명시된 컬럼만 nullable=True여야 한다.
NULLABLE_COLUMNS: dict[str, set[str]] = {
    "match_analyses": {"matched_comp_id"},
    "link_click_events": {"chat_log_id"},
    "account_link_events": {"match_id"},
}


def test_all_analysis_log_cache_tables_created(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    table_names = set(inspector.get_table_names())
    for table in EXPECTED_TABLES:
        assert table in table_names, f"{table} 테이블이 생성되지 않음"


def test_analysis_log_cache_table_columns_match_schema(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    for table, expected_columns in EXPECTED_TABLES.items():
        actual_columns = {c["name"] for c in inspector.get_columns(table)}
        assert actual_columns == expected_columns, (
            f"{table} 컬럼 불일치: {actual_columns}"
        )


def test_nullable_policy_matches_schema(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    for table, expected_columns in EXPECTED_TABLES.items():
        nullable_expected = NULLABLE_COLUMNS.get(table, set())
        columns = {c["name"]: c["nullable"] for c in inspector.get_columns(table)}
        for column_name in expected_columns:
            if column_name == "id":
                continue
            expected_nullable = column_name in nullable_expected
            assert columns[column_name] == expected_nullable, (
                f"{table}.{column_name} nullable 정책 불일치 "
                f"(기대: {expected_nullable}, 실제: {columns[column_name]})"
            )


def test_cache_tables_have_unique_cache_key(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    for table in ("chat_answer_cache", "puuid_cache"):
        unique_constraints = inspector.get_unique_constraints(table)
        unique_columns = {
            col for uc in unique_constraints for col in uc["column_names"]
        }
        assert "cache_key" in unique_columns, f"{table}.cache_key는 UNIQUE여야 함"
