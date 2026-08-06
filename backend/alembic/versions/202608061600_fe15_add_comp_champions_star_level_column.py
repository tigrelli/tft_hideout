"""fe15_add_comp_champions_star_level_column

Revision ID: d4f0e13a125e
Revises: bd31bb11470f
Create Date: 2026-08-06 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f0e13a125e"
down_revision: str | Sequence[str] | None = "bd31bb11470f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 조합 상세 헥스 배치도의 챔피언 성급(op.gg tft_list_meta_decks 응답
    # units[].tier, 정수 2 또는 3). NULL이면 프론트가 별 표시를 생략한다(FE-15).
    op.add_column(
        "comp_champions", sa.Column("star_level", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("comp_champions", "star_level")
