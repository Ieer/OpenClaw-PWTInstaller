"""add knowledge chunk policy and resolve audit tables

Revision ID: 20260331_0004
Revises: 20260331_0003
Create Date: 2026-03-31
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260331_0004"
down_revision: str | None = "20260331_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_validation_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("risk_level", sa.Text(), nullable=False),
        sa.Column("require_validation", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("require_approved", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("require_not_expired", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("min_confidence", sa.Float(), nullable=True),
        sa.Column("max_validation_age_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("risk_level", name="uq_knowledge_validation_policies_risk_level"),
    )

    op.create_table(
        "knowledge_resolve_audits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("agent_slug", sa.Text(), nullable=True),
        sa.Column("requested_risk_level", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("selected_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rejected_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("payload", sa.JSON(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_resolve_audits_created_at_desc ON knowledge_resolve_audits(created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_resolve_audits_risk_created_at_desc ON knowledge_resolve_audits(requested_risk_level, created_at DESC)")


def downgrade() -> None:
    op.drop_index("idx_knowledge_resolve_audits_risk_created_at_desc", table_name="knowledge_resolve_audits")
    op.drop_index("idx_knowledge_resolve_audits_created_at_desc", table_name="knowledge_resolve_audits")
    op.drop_table("knowledge_resolve_audits")

    op.drop_table("knowledge_validation_policies")
