"""data22_add_comps_top4_rate_game_count_and_comp_traits

Revision ID: fb2416485070
Revises: c18bded125c4
Create Date: 2026-08-18 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fb2416485070"
down_revision: str | Sequence[str] | None = "c18bded125c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # DATA-22: op.gg stat.deck.top4Rate/compsCount(조합별 실제 표본 게임수 —
    # totalCount는 집계구간 전체 공통분모일 뿐 조합별 표본이 아님,
    # docs/spike/opgg-schema.md 10번 항목). 이 컬럼 추가 전 배치가 채운
    # 기존 행은 NULL, 다음 배치 실행 시 채워짐.
    op.add_column("comps", sa.Column("top4_rate", sa.Float(), nullable=True))
    op.add_column("comps", sa.Column("game_count", sa.Integer(), nullable=True))

    op.create_table(
        "comp_traits",
        sa.Column("comp_id", sa.Integer(), nullable=False),
        sa.Column("trait_id", sa.Integer(), nullable=False),
        sa.Column("style", sa.Integer(), nullable=False),
        sa.Column("num_units", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["comp_id"], ["comps.id"]),
        sa.ForeignKeyConstraint(["trait_id"], ["traits.id"]),
        sa.PrimaryKeyConstraint("comp_id", "trait_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("comp_traits")
    op.drop_column("comps", "game_count")
    op.drop_column("comps", "top4_rate")
