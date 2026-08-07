"""chat08_add_cache_intent_and_doc_ids

Revision ID: 0e7e474c8b49
Revises: 28d3c2f2aa27
Create Date: 2026-08-07 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0e7e474c8b49"
down_revision: str | Sequence[str] | None = "28d3c2f2aa27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 캐시 hit 시 chat_logs 적재를 위해 캐시 저장 시점의 intent·근거문서id를
    # 함께 보관한다(2026-08-07 발견: 캐시 hit 턴이 chat_logs에 전혀 기록되지
    # 않아 후속 턴의 대화이력이 비어버리는 버그 수정). intent 재계산을 위해
    # classify_fn(Groq 2차 분류 포함)을 다시 호출하면 캐싱의 존재 이유(무료
    # 티어 호출 절감)가 무의미해지므로, 저장 시점 값을 그대로 재사용한다.
    # 배포 시점에 이미 존재하는 캐시 행은 이 값이 비어(NULL) 있으므로
    # nullable로 두고, 그런 행은 캐시 hit이어도 로깅을 건너뛴다(자연 무효화로
    # 곧 새 값으로 덮어써짐).
    op.add_column("chat_answer_cache", sa.Column("intent", sa.String(), nullable=True))
    op.add_column(
        "chat_answer_cache",
        sa.Column(
            "retrieved_doc_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("chat_answer_cache", "retrieved_doc_ids")
    op.drop_column("chat_answer_cache", "intent")
