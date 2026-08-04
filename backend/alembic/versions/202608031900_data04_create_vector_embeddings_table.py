"""data04_create_vector_embeddings_table

Revision ID: bb7e9fa7208f
Revises: 7fcfedaf81ac
Create Date: 2026-08-03 16:31:56.675461

"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bb7e9fa7208f"
down_revision: str | Sequence[str] | None = "7fcfedaf81ac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "meta_document_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patch_version", sa.String(), nullable=False),
        sa.Column("doc_type", sa.String(), nullable=False),
        sa.Column("source_table", sa.String(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column(
            "embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=False
        ),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["patch_version"],
            ["patches.version"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # HNSW 인덱스(vector_cosine_ops, m=16/ef_construction=64) — ivfflat은 정책상 사용 금지(schema.md)
    op.execute(
        "CREATE INDEX ix_meta_document_embeddings_embedding_hnsw "
        "ON meta_document_embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.create_index(
        "ix_meta_document_embeddings_patch_doctype",
        "meta_document_embeddings",
        ["patch_version", "doc_type"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_meta_document_embeddings_patch_doctype",
        table_name="meta_document_embeddings",
    )
    op.execute("DROP INDEX IF EXISTS ix_meta_document_embeddings_embedding_hnsw")
    op.drop_table("meta_document_embeddings")
