"""data11_add_embeddings_unique_constraint

Revision ID: c5d8f1a3e6b9
Revises: a1c4e9f2b7d3
Create Date: 2026-08-04 11:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5d8f1a3e6b9"
down_revision: str | Sequence[str] | None = "a1c4e9f2b7d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # DATA-10과 동일 이유: 같은 소스 레코드를 재수집(같은 패치 내 재실행)해도
    # 중복 임베딩 행이 쌓이지 않고 upsert(갱신)되도록. 같은 source_id가
    # doc_type이 다르면(comp/playstyle 등) 별개 문서이므로 doc_type도 키에 포함.
    op.create_unique_constraint(
        "uq_meta_document_embeddings_patch_doctype_source",
        "meta_document_embeddings",
        ["patch_version", "doc_type", "source_table", "source_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_meta_document_embeddings_patch_doctype_source",
        "meta_document_embeddings",
        type_="unique",
    )
