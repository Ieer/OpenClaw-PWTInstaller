"""add knowledge units validations and feedback tables

Revision ID: 20260331_0003
Revises: 20260330_0002
Create Date: 2026-03-31
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260331_0003"
down_revision: str | None = "20260330_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_units",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("unit_key", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("agent_scope", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("risk_level", sa.Text(), server_default="normal", nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("meta", sa.JSON(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unit_key", name="uq_knowledge_units_unit_key"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_units_source_id ON knowledge_units(source_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_units_status_updated_at_desc ON knowledge_units(status, updated_at DESC)")

    op.create_table(
        "knowledge_validations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("validator", sa.Text(), nullable=False),
        sa.Column("validation_status", sa.Text(), server_default="approved", nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("meta", sa.JSON(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["unit_id"], ["knowledge_units.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_validations_unit_id ON knowledge_validations(unit_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_validations_unit_validated_at_desc ON knowledge_validations(unit_id, validated_at DESC)")

    op.create_table(
        "knowledge_feedback_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("agent", sa.Text(), nullable=True),
        sa.Column("feedback_type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), server_default="info", nullable=False),
        sa.Column("payload", sa.JSON(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["unit_id"], ["knowledge_units.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_feedback_events_unit_id ON knowledge_feedback_events(unit_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_feedback_events_type_created_at_desc ON knowledge_feedback_events(feedback_type, created_at DESC)")


def downgrade() -> None:
    op.drop_index("idx_knowledge_feedback_events_type_created_at_desc", table_name="knowledge_feedback_events")
    op.drop_index("idx_knowledge_feedback_events_unit_id", table_name="knowledge_feedback_events")
    op.drop_table("knowledge_feedback_events")

    op.drop_index("idx_knowledge_validations_unit_validated_at_desc", table_name="knowledge_validations")
    op.drop_index("idx_knowledge_validations_unit_id", table_name="knowledge_validations")
    op.drop_table("knowledge_validations")

    op.drop_index("idx_knowledge_units_status_updated_at_desc", table_name="knowledge_units")
    op.drop_index("idx_knowledge_units_source_id", table_name="knowledge_units")
    op.drop_table("knowledge_units")
