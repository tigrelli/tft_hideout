"""chat36_nullable_embedding_add_pg_trgm

Revision ID: 3c6d2e9a1f47
Revises: 52c529032f95
Create Date: 2026-10-18 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c6d2e9a1f47"
down_revision: str | Sequence[str] | None = "52c529032f95"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # CHAT-36: Hugging Face가 2026-10-07부로 무료 계정 추론 크레딧을 폐지해
    # BGE-M3 임베딩을 더 이상 만들 수 없다(진행현황.md 2026-10-18 이력). 배치는
    # 청크 텍스트만 적재하고(embedding NULL), 챗봇은 pg_trgm 텍스트 유사도로
    # 검색한다. 기존 패치의 벡터 값은 이력 보존용으로 그대로 둔다(검색에는
    # 더 이상 쓰이지 않음).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.alter_column("meta_document_embeddings", "embedding", nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # NOT NULL 복원 전에 벡터 없이 적재된 행(CHAT-36 이후 배치분)을 지운다 —
    # 다운그레이드된 코드(벡터 검색)는 이 행들을 어차피 쓸 수 없다.
    op.execute("DELETE FROM meta_document_embeddings WHERE embedding IS NULL")
    op.alter_column("meta_document_embeddings", "embedding", nullable=False)
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
