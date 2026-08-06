"""fe_add_items_square_icon_url_column

Revision ID: c8949e1b0636
Revises: 9a3c7e5b1d24
Create Date: 2026-08-06 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8949e1b0636"
down_revision: str | Sequence[str] | None = "9a3c7e5b1d24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 조합 상세(챔피언 구성)의 추천 아이템을 이미지로 표시하기 위한 아이콘 URL
    # (champions.square_icon_url과 동일 규칙: Community Dragon cdragon/tft
    # 응답의 items[].icon .tex 경로를 raw.communitydragon.org PNG URL로 변환).
    op.add_column("items", sa.Column("square_icon_url", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("items", "square_icon_url")
