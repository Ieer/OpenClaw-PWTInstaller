"""add observability performance indexes

Revision ID: 20260511_0012
Revises: 20260404_0011
Create Date: 2026-05-11
"""

from typing import Sequence

from alembic import op


revision: str = "20260511_0012"
down_revision: str | None = "20260404_0011"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_updated_at_desc ON tasks(status, updated_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tasks_updated_at_desc ON tasks(updated_at DESC)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_heartbeat_agent_created_at_desc "
        "ON events(agent, created_at DESC) WHERE type = 'agent.heartbeat'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_events_heartbeat_agent_created_at_desc")
    op.execute("DROP INDEX IF EXISTS idx_tasks_updated_at_desc")
    op.execute("DROP INDEX IF EXISTS idx_tasks_status_updated_at_desc")