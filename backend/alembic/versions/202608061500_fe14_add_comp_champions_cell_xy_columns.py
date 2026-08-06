"""fe14_add_comp_champions_cell_xy_columns

Revision ID: bd31bb11470f
Revises: a5d18d09d18a
Create Date: 2026-08-06 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bd31bb11470f"
down_revision: str | Sequence[str] | None = "a5d18d09d18a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 조합 상세 헥스 배치도의 실제 좌표(op.gg tft_list_meta_decks 응답
    # units[].cell.{x,y}, x:1~7 y:1~4). NULL이면 프론트가 기존 is_carry
    # 휴리스틱 배치로 폴백한다(FE-14).
    op.add_column("comp_champions", sa.Column("cell_x", sa.Integer(), nullable=True))
    op.add_column("comp_champions", sa.Column("cell_y", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("comp_champions", "cell_y")
    op.drop_column("comp_champions", "cell_x")
