"""mission control baseline schema

Revision ID: 20260318_0001
Revises:
Create Date: 2026-03-18
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260318_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="INBOX", nullable=False),
        sa.Column("assignee", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_comments_task_id", "comments", ["task_id"], unique=False)

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("agent", sa.Text(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("payload", sa.JSON(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_created_at_desc ON events(created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_type_created_at_desc ON events(type, created_at DESC)")

    op.create_table(
        "agent_skill_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_slug", sa.Text(), nullable=False),
        sa.Column("skill_slug", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_slug", "skill_slug", name="uq_agent_skill_mappings_agent_skill"),
    )
    op.create_index("idx_agent_skill_mappings_agent_slug", "agent_skill_mappings", ["agent_slug"], unique=False)

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_chunks (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          source text NOT NULL,
          content text NOT NULL,
          embedding vector(1536),
          metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS memory_chunks")

    op.drop_index("idx_agent_skill_mappings_agent_slug", table_name="agent_skill_mappings")
    op.drop_table("agent_skill_mappings")

    op.drop_index("idx_events_type_created_at_desc", table_name="events")
    op.drop_index("idx_events_created_at_desc", table_name="events")
    op.drop_table("events")

    op.drop_index("idx_comments_task_id", table_name="comments")
    op.drop_table("comments")

    op.drop_table("tasks")
