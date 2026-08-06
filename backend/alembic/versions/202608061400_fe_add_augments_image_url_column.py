"""fe_add_augments_image_url_column

Revision ID: a5d18d09d18a
Revises: c8949e1b0636
Create Date: 2026-08-06 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5d18d09d18a"
down_revision: str | Sequence[str] | None = "c8949e1b0636"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 증강체 카드에 대표 이미지를 보여주기 위한 아이콘 URL. 챔피언/아이템과 달리
    # op.gg tft_list_augments 응답이 자체 imageUrl 필드를 이미 제공한다
    # (c-tft-api.op.gg CDN, DATA-05 스파이크로 확인 — Community Dragon 변환 불필요).
    op.add_column("augments", sa.Column("image_url", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("augments", "image_url")
