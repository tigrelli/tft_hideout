"""data25_add_champion_item_builds_patch_champion_index

Revision ID: 8e1b4c7d2a90
Revises: 3c6d2e9a1f47
Create Date: 2026-10-26 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8e1b4c7d2a90"
down_revision: str | Sequence[str] | None = "3c6d2e9a1f47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # DATA-25(2026-10-26 Supabase Disk IO 경고): champion_item_builds엔 PK 외
    # 인덱스가 없어, 배치의 빌드 교체 DELETE와 카탈로그 GET /items/builds가
    # patch_version/champion_id 조건으로 매번 테이블 전체(운영 40만 행·80MB)를
    # 순차 스캔했다(누적 seq_tup_read 약 5.4억).
    op.create_index(
        "ix_champion_item_builds_patch_champion",
        "champion_item_builds",
        ["patch_version", "champion_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_champion_item_builds_patch_champion",
        table_name="champion_item_builds",
    )
