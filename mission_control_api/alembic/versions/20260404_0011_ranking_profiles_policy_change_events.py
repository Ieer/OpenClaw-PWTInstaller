"""add ranking profiles and policy change events

Revision ID: 20260404_0011
Revises: 20260404_0010
Create Date: 2026-04-04
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260404_0011"
down_revision: str | None = "20260404_0010"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_validation_policy_change_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("entity_key", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=True),
        sa.Column("before_state", sa.JSON(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("after_state", sa.JSON(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_validation_policy_change_events_entity_created_at_desc ON knowledge_validation_policy_change_events(entity_type, entity_key, created_at DESC)"
    )

    op.create_table(
        "knowledge_resolve_ranking_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_key", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("base_score", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("lexical_weight", sa.Float(), server_default="0.8", nullable=False),
        sa.Column("semantic_weight", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("tag_weight", sa.Float(), server_default="0.3", nullable=False),
        sa.Column("validation_confidence_weight", sa.Float(), server_default="0.5", nullable=False),
        sa.Column("approved_bonus", sa.Float(), server_default="0.5", nullable=False),
        sa.Column("preferred_bonus", sa.Float(), server_default="0.35", nullable=False),
        sa.Column("deprecated_penalty", sa.Float(), server_default="0.25", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_key", name="uq_knowledge_resolve_ranking_profiles_profile_key"),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_resolve_ranking_profiles_enabled_profile_key ON knowledge_resolve_ranking_profiles(enabled, profile_key)"
    )

    op.execute(
        """
        INSERT INTO knowledge_resolve_ranking_profiles (
          id, profile_key, description, enabled, base_score, lexical_weight, semantic_weight,
          tag_weight, validation_confidence_weight, approved_bonus, preferred_bonus, deprecated_penalty
        )
        VALUES
          (gen_random_uuid(), 'balanced', 'Balanced default profile for mixed lexical and semantic ranking.', true, 1.0, 0.8, 1.0, 0.3, 0.5, 0.5, 0.35, 0.25),
          (gen_random_uuid(), 'precision', 'Precision-focused profile for high-risk retrieval.', true, 1.0, 0.8, 1.25, 0.2, 0.65, 0.5, 0.35, 0.25),
          (gen_random_uuid(), 'recall', 'Recall-focused profile with stronger lexical and tag emphasis.', true, 1.0, 1.0, 0.9, 0.4, 0.4, 0.4, 0.25, 0.15)
        ON CONFLICT (profile_key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("idx_knowledge_resolve_ranking_profiles_enabled_profile_key", table_name="knowledge_resolve_ranking_profiles")
    op.drop_table("knowledge_resolve_ranking_profiles")

    op.drop_index("idx_knowledge_validation_policy_change_events_entity_created_at_desc", table_name="knowledge_validation_policy_change_events")
    op.drop_table("knowledge_validation_policy_change_events")