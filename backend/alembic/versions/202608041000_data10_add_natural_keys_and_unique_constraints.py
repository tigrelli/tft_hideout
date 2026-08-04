"""data10_add_natural_keys_and_unique_constraints

Revision ID: a1c4e9f2b7d3
Revises: 8320a6545d5d
Create Date: 2026-08-04 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c4e9f2b7d3"
down_revision: str | Sequence[str] | None = "8320a6545d5d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # DATA-10: 배치 재수집 시 "동일 엔티티 upsert(덮어쓰기 아님)"를 DB 레벨에서
    # 보장하려면 (patch_version, 원본 ID) 조합에 UNIQUE 제약이 있어야 한다.
    # champions/items/augments는 riot_*_id 컬럼이 이미 있어 제약만 추가.
    # traits/comps는 원본 ID를 저장하는 컬럼 자체가 없어 새로 추가한다.
    op.add_column("traits", sa.Column("riot_trait_id", sa.String(), nullable=True))
    op.add_column("comps", sa.Column("riot_comp_id", sa.String(), nullable=True))

    # 기존 행이 없는 그린필드 스키마라 NOT NULL로 바로 전환 가능(DATA-08/09/10 이전엔
    # 배치가 한 번도 실행되지 않아 champions/items/augments/traits/comps 전부 비어 있음).
    op.alter_column("traits", "riot_trait_id", nullable=False)
    op.alter_column("comps", "riot_comp_id", nullable=False)

    op.create_unique_constraint(
        "uq_champions_patch_riot_id", "champions", ["patch_version", "riot_champion_id"]
    )
    op.create_unique_constraint(
        "uq_items_patch_riot_id", "items", ["patch_version", "riot_item_id"]
    )
    op.create_unique_constraint(
        "uq_augments_patch_riot_id", "augments", ["patch_version", "riot_augment_id"]
    )
    op.create_unique_constraint(
        "uq_traits_patch_riot_id", "traits", ["patch_version", "riot_trait_id"]
    )
    op.create_unique_constraint(
        "uq_comps_patch_riot_id", "comps", ["patch_version", "riot_comp_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_comps_patch_riot_id", "comps", type_="unique")
    op.drop_constraint("uq_traits_patch_riot_id", "traits", type_="unique")
    op.drop_constraint("uq_augments_patch_riot_id", "augments", type_="unique")
    op.drop_constraint("uq_items_patch_riot_id", "items", type_="unique")
    op.drop_constraint("uq_champions_patch_riot_id", "champions", type_="unique")
    op.drop_column("comps", "riot_comp_id")
    op.drop_column("traits", "riot_trait_id")
