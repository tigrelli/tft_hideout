"""fe13_add_champions_square_icon_url_column

Revision ID: 9a3c7e5b1d24
Revises: 2fdcd6f417ba
Create Date: 2026-08-05 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a3c7e5b1d24"
down_revision: str | Sequence[str] | None = "2fdcd6f417ba"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # FE-13: 티어리스트 카드 캐리 챔피언 표시용 아이콘 이미지 URL(Community Dragon
    # squareIcon .tex 경로를 raw.communitydragon.org PNG URL로 변환한 값).
    op.add_column("champions", sa.Column("square_icon_url", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("champions", "square_icon_url")
