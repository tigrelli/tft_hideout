"""data19 add items description column

Revision ID: c18bded125c4
Revises: 0e7e474c8b49
Create Date: 2026-08-08 08:08:05.541588

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c18bded125c4"
down_revision: Union[str, Sequence[str], None] = "0e7e474c8b49"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # DATA-19: items.description 컬럼만 추가한다. autogenerate가 함께 잡아낸
    # meta_document_embeddings의 HNSW/patch_doctype 인덱스 drop은 이 로컬 테스트
    # DB의 인덱스 메타데이터 추적 차이로 생긴 오탐(spurious diff)이라 제외했다 —
    # 두 인덱스 모두 하이브리드 검색(CHAT-02) 성능에 필수라 실수로라도 지우면
    # 안 된다.
    op.add_column("items", sa.Column("description", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("items", "description")
