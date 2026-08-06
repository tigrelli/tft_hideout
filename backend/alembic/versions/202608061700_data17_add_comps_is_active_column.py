"""data17_add_comps_is_active_column

Revision ID: 28d3c2f2aa27
Revises: d4f0e13a125e
Create Date: 2026-08-06 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "28d3c2f2aa27"
down_revision: str | Sequence[str] | None = "d4f0e13a125e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # op.gg tft_list_meta_decks는 페이지네이션 없이 항상 현재 상위 10개 조합만
    # 반환해, 같은 patch_version 내에서도 메타 회전으로 이전에 상위 10위였던
    # 조합이 응답에서 사라질 수 있다(DATA-17). comp_champions/comp_augments·
    # match_analyses.matched_comp_id FK가 있어 하드 삭제 대신 이 플래그로
    # 소프트 삭제한다 — false면 티어리스트에서 제외되지만 조합 상세·PGA
    # 매칭·챗봇 인용은 계속 조회 가능하다.
    op.add_column(
        "comps",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("comps", "is_active")
