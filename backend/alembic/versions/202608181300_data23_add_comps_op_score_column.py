"""data23_add_comps_op_score_column

Revision ID: 52c529032f95
Revises: fb2416485070
Create Date: 2026-08-18 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "52c529032f95"
down_revision: str | Sequence[str] | None = "fb2416485070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # DATA-23: op.gg stat.opScore 원값. assign_self_tiers()가 이 값을
    # 0~100 정규화한 뒤 상대임계값 간격 클러스터링으로 tier_rank를
    # 계산하는 데 쓴다(docs/spike/comp-tier-scoring.md). 이 컬럼 추가
    # 전 배치가 채운 기존 행은 NULL(다음 배치 실행 시 채워짐, NULL인
    # 동안은 assign_self_tiers()가 해당 행을 "C"로 고정 처리한다).
    op.add_column("comps", sa.Column("op_score", sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("comps", "op_score")
