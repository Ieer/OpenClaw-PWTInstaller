"""add dynamic policy lifecycle and rollout tables

Revision ID: 20260404_0010
Revises: 20260404_0009
Create Date: 2026-04-04
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260404_0010"
down_revision: str | None = "20260404_0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_units",
        sa.Column("lifecycle_stage", sa.Text(), server_default="active", nullable=False),
    )
    op.add_column(
        "knowledge_units",
        sa.Column("superseded_by_unit_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "knowledge_units",
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_knowledge_units_superseded_by_unit_id",
        "knowledge_units",
        "knowledge_units",
        ["superseded_by_unit_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_units_lifecycle_stage_updated_at_desc ON knowledge_units(lifecycle_stage, updated_at DESC)"
    )

    op.create_table(
        "knowledge_validation_policy_bundles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bundle_key", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bundle_key", name="uq_knowledge_validation_policy_bundles_bundle_key"),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_validation_policy_bundles_default_enabled ON knowledge_validation_policy_bundles(is_default, enabled)"
    )

    op.create_table(
        "knowledge_validation_policy_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bundle_id", sa.Uuid(), nullable=False),
        sa.Column("rule_key", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.Text(), nullable=False),
        sa.Column("task_pattern", sa.Text(), nullable=True),
        sa.Column("agent_slug", sa.Text(), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("strict_mode", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("require_validation", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("require_approved", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("require_not_expired", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("min_confidence", sa.Float(), nullable=True),
        sa.Column("max_validation_age_days", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bundle_id"], ["knowledge_validation_policy_bundles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bundle_id", "rule_key", name="uq_knowledge_validation_policy_rules_bundle_rule_key"),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_validation_policy_rules_match ON knowledge_validation_policy_rules(bundle_id, risk_level, enabled, priority DESC)"
    )

    op.create_table(
        "knowledge_validation_policy_rollouts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bundle_id", sa.Uuid(), nullable=False),
        sa.Column("rollout_key", sa.Text(), nullable=False),
        sa.Column("target_agent_slug", sa.Text(), nullable=True),
        sa.Column("target_source_type", sa.Text(), nullable=True),
        sa.Column("task_pattern", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("rollout_mode", sa.Text(), server_default="full", nullable=False),
        sa.Column("rollout_percentage", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bundle_id"], ["knowledge_validation_policy_bundles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bundle_id", "rollout_key", name="uq_knowledge_validation_policy_rollouts_bundle_rollout_key"),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_validation_policy_rollouts_enabled_priority ON knowledge_validation_policy_rollouts(enabled, priority DESC)"
    )

    op.create_table(
        "knowledge_unit_lifecycle_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["unit_id"], ["knowledge_units.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_unit_lifecycle_events_unit_created_at_desc ON knowledge_unit_lifecycle_events(unit_id, created_at DESC)"
    )

    op.execute(
        """
        INSERT INTO knowledge_validation_policy_bundles (id, bundle_key, description, is_default, enabled)
        SELECT gen_random_uuid(), 'default-v1', 'default fallback validation policy bundle', true, true
        WHERE NOT EXISTS (
          SELECT 1 FROM knowledge_validation_policy_bundles WHERE bundle_key = 'default-v1'
        )
        """
    )


def downgrade() -> None:
    op.drop_index("idx_knowledge_unit_lifecycle_events_unit_created_at_desc", table_name="knowledge_unit_lifecycle_events")
    op.drop_table("knowledge_unit_lifecycle_events")

    op.drop_index("idx_knowledge_validation_policy_rollouts_enabled_priority", table_name="knowledge_validation_policy_rollouts")
    op.drop_table("knowledge_validation_policy_rollouts")

    op.drop_index("idx_knowledge_validation_policy_rules_match", table_name="knowledge_validation_policy_rules")
    op.drop_table("knowledge_validation_policy_rules")

    op.drop_index("idx_knowledge_validation_policy_bundles_default_enabled", table_name="knowledge_validation_policy_bundles")
    op.drop_table("knowledge_validation_policy_bundles")

    op.drop_index("idx_knowledge_units_lifecycle_stage_updated_at_desc", table_name="knowledge_units")
    op.drop_constraint("fk_knowledge_units_superseded_by_unit_id", "knowledge_units", type_="foreignkey")
    op.drop_column("knowledge_units", "retired_at")
    op.drop_column("knowledge_units", "superseded_by_unit_id")
    op.drop_column("knowledge_units", "lifecycle_stage")