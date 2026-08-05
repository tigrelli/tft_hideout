"""api02_drop_comps_rank_tier_column

Revision ID: 2fdcd6f417ba
Revises: f1b3c9d4e8a2
Create Date: 2026-08-05 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2fdcd6f417ba"
down_revision: str | Sequence[str] | None = "f1b3c9d4e8a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 랭크 필터(API-02, 챌린저/그랜드마스터/마스터) 제거(2026-08-05 PM 결정) —
    # op.gg MCP tft_list_meta_decks의 입력 스키마가 파라미터를 아예 받지 않아
    # (실호출로 확인, docs/spike/opgg-schema.md) 랭크 구간별 데이터를 얻을 방법이
    # 없음이 확정됨. rank_tier는 항상 server_default "all"만 채워지던 사실상
    # 죽은 컬럼이었다.
    op.drop_column("comps", "rank_tier")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "comps",
        sa.Column("rank_tier", sa.String(), server_default="all", nullable=False),
    )
