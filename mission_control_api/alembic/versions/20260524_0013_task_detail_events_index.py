"""add task detail events index

Revision ID: 20260524_0013
Revises: 20260511_0012
Create Date: 2026-05-24
"""

from typing import Sequence

from alembic import op


revision: str = "20260524_0013"
down_revision: str | None = "20260511_0012"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_task_id_created_at_desc "
        "ON events(task_id, created_at DESC) WHERE task_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_events_task_id_created_at_desc")
