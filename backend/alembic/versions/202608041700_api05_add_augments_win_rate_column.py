"""api05_add_augments_win_rate_column

Revision ID: f1b3c9d4e8a2
Revises: c5d8f1a3e6b9
Create Date: 2026-08-04 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1b3c9d4e8a2"
down_revision: str | Sequence[str] | None = "c5d8f1a3e6b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # API-05 승률 마스킹(is_legend_related) 정책 대상 컬럼. op.gg/Riot 어느 쪽도
    # 증강체 단위 승률 데이터를 제공하지 않아(DATA-05 스파이크) 배치는 이 컬럼을
    # 채우지 않고 항상 NULL로 둔다 — 마스킹 로직만 미리 구현해두고, 나중에 데이터
    # 소스가 생기면 그때 값을 채운다(PM 승인 2026-08-04, DATA-07과 동일한 패턴).
    op.add_column("augments", sa.Column("win_rate", sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("augments", "win_rate")
