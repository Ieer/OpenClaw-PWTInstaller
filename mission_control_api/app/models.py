from __future__ import annotations

import sqlalchemy as sa


metadata = sa.MetaData()


tasks = sa.Table(
    "tasks",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("status", sa.Text, nullable=False, server_default="INBOX"),
    sa.Column("assignee", sa.Text, nullable=True),
    sa.Column("tags", sa.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
)


comments = sa.Table(
    "comments",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("task_id", sa.Uuid, nullable=False, index=True),
    sa.Column("author", sa.Text, nullable=False),
    sa.Column("body", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
)


events = sa.Table(
    "events",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("type", sa.Text, nullable=False),
    sa.Column("agent", sa.Text, nullable=True),
    sa.Column("task_id", sa.Uuid, nullable=True),
    sa.Column("payload", sa.JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
)


agent_skill_mappings = sa.Table(
    "agent_skill_mappings",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("agent_slug", sa.Text, nullable=False, index=True),
    sa.Column("skill_slug", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.UniqueConstraint("agent_slug", "skill_slug", name="uq_agent_skill_mappings_agent_skill"),
)
