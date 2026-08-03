"""api02_add_comps_rank_tier_column

Revision ID: 8320a6545d5d
Revises: bb7e9fa7208f
Create Date: 2026-08-03 16:44:50.142867

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8320a6545d5d"
down_revision: str | Sequence[str] | None = "bb7e9fa7208f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # rank 필터(API-02)를 위해 comps에 rank_tier 컬럼 추가. 실제 op.gg 랭크 구간 값은
    # DATA-05 스파이크 완료 후 재검토 — 지금은 기본값 "all"만 사용
    op.add_column(
        "comps",
        sa.Column("rank_tier", sa.String(), server_default="all", nullable=False),
    )
    # 주의: meta_document_embeddings의 HNSW/btree 인덱스는 raw SQL(op.execute)로 생성되어
    # SQLAlchemy 메타데이터에 잡히지 않음 — autogenerate가 이를 "삭제 대상"으로 잘못 감지해
    # 생성한 op.drop_index 2건은 의도적으로 제거함(DATA-04 인덱스 유지)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("comps", "rank_tier")
