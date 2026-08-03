from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.models import EMBEDDING_DIM, MetaDocumentEmbedding, Patch


def _one_hot(dim: int, index: int, value: float = 1.0) -> list[float]:
    vec = [0.0] * dim
    vec[index] = value
    return vec


def _seed_patch_and_docs(engine: Engine) -> None:
    with Session(engine) as session:
        session.execute(
            insert(Patch).values(
                version="14.5",
                set_number=14,
                released_at=datetime(2026, 1, 1, tzinfo=UTC),
                is_current=True,
                detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )

        # query embedding will be e0 (1.0 at index 0). Distances (ascending expected):
        # doc_identical (e0) < doc_partial (e0+e1 혼합) < doc_orthogonal (e1) < doc_opposite (-e0)
        docs = [
            ("doc_identical", _one_hot(EMBEDDING_DIM, 0, 1.0)),
            (
                "doc_partial",
                [0.7 if i in (0, 1) else 0.0 for i in range(EMBEDDING_DIM)],
            ),
            ("doc_orthogonal", _one_hot(EMBEDDING_DIM, 1, 1.0)),
            ("doc_opposite", _one_hot(EMBEDDING_DIM, 0, -1.0)),
        ]
        for name, vector in docs:
            session.execute(
                insert(MetaDocumentEmbedding).values(
                    patch_version="14.5",
                    doc_type="comp",
                    source_table="comps",
                    source_id=1,
                    content_text=name,
                    embedding=vector,
                    doc_metadata={"name": name},
                )
            )
        session.commit()


@pytest.fixture(scope="module")
def seeded_docs(migrated_engine: Engine) -> Engine:
    _seed_patch_and_docs(migrated_engine)
    return migrated_engine


def test_meta_document_embeddings_table_created(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    assert "meta_document_embeddings" in inspector.get_table_names()

    expected_columns = {
        "id",
        "patch_version",
        "doc_type",
        "source_table",
        "source_id",
        "content_text",
        "embedding",
        "metadata",
    }
    actual_columns = {
        c["name"] for c in inspector.get_columns("meta_document_embeddings")
    }
    assert actual_columns == expected_columns


def test_hnsw_and_btree_indexes_exist(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    indexes = {ix["name"] for ix in inspector.get_indexes("meta_document_embeddings")}
    assert "ix_meta_document_embeddings_embedding_hnsw" in indexes
    assert "ix_meta_document_embeddings_patch_doctype" in indexes

    composite_index = next(
        ix
        for ix in inspector.get_indexes("meta_document_embeddings")
        if ix["name"] == "ix_meta_document_embeddings_patch_doctype"
    )
    assert composite_index["column_names"] == ["patch_version", "doc_type"]


def test_cosine_search_returns_expected_order(seeded_docs: Engine) -> None:
    query_vector = _one_hot(EMBEDDING_DIM, 0, 1.0)
    with Session(seeded_docs) as session:
        stmt = (
            select(MetaDocumentEmbedding.content_text)
            .order_by(MetaDocumentEmbedding.embedding.cosine_distance(query_vector))
            .limit(4)
        )
        result = [row[0] for row in session.execute(stmt)]

    assert result == ["doc_identical", "doc_partial", "doc_orthogonal", "doc_opposite"]


def test_explain_uses_hnsw_index(seeded_docs: Engine) -> None:
    query_vector = _one_hot(EMBEDDING_DIM, 0, 1.0)
    vector_literal = "[" + ",".join(str(v) for v in query_vector) + "]"

    with seeded_docs.connect() as conn, conn.begin():
        conn.execute(text("SET LOCAL enable_seqscan = off"))
        plan_rows = conn.execute(
            text(
                "EXPLAIN SELECT content_text FROM meta_document_embeddings "
                f"ORDER BY embedding <=> '{vector_literal}' LIMIT 4"
            )
        ).fetchall()

    plan_text = "\n".join(row[0] for row in plan_rows)
    assert "ix_meta_document_embeddings_embedding_hnsw" in plan_text
