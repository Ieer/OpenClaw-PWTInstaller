from __future__ import annotations

import sqlalchemy as sa


metadata = sa.MetaData()


class VectorType(sa.types.UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int | None = None):
        self.dimensions = int(dimensions) if dimensions is not None else None

    def get_col_spec(self, **kw) -> str:
        if self.dimensions is None:
            return "vector"
        return f"vector({self.dimensions})"


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


knowledge_sources = sa.Table(
    "knowledge_sources",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("source_type", sa.Text, nullable=False),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("external_uri", sa.Text, nullable=True),
    sa.Column("storage_path", sa.Text, nullable=False),
    sa.Column("checksum_sha256", sa.Text, nullable=True),
    sa.Column("mime_type", sa.Text, nullable=True),
    sa.Column("owner", sa.Text, nullable=True),
    sa.Column("version_label", sa.Text, nullable=True),
    sa.Column("status", sa.Text, nullable=False, server_default="active"),
    sa.Column("meta", sa.JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.UniqueConstraint("storage_path", name="uq_knowledge_sources_storage_path"),
)


knowledge_units = sa.Table(
    "knowledge_units",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("source_id", sa.Uuid, sa.ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True, index=True),
    sa.Column("unit_key", sa.Text, nullable=False),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("content", sa.Text, nullable=False),
    sa.Column("content_sha256", sa.Text, nullable=True),
    sa.Column("tags", sa.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("agent_scope", sa.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("risk_level", sa.Text, nullable=False, server_default="normal"),
    sa.Column("status", sa.Text, nullable=False, server_default="active"),
    sa.Column("lifecycle_stage", sa.Text, nullable=False, server_default="active"),
    sa.Column("superseded_by_unit_id", sa.Uuid, sa.ForeignKey("knowledge_units.id", ondelete="SET NULL"), nullable=True),
    sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("meta", sa.JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.UniqueConstraint("unit_key", name="uq_knowledge_units_unit_key"),
)


knowledge_validations = sa.Table(
    "knowledge_validations",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("unit_id", sa.Uuid, sa.ForeignKey("knowledge_units.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("validator", sa.Text, nullable=False),
    sa.Column("validation_status", sa.Text, nullable=False, server_default="approved"),
    sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("confidence", sa.Float, nullable=True),
    sa.Column("notes", sa.Text, nullable=True),
    sa.Column("meta", sa.JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
)


knowledge_feedback_events = sa.Table(
    "knowledge_feedback_events",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("unit_id", sa.Uuid, sa.ForeignKey("knowledge_units.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("agent", sa.Text, nullable=True, index=True),
    sa.Column("feedback_type", sa.Text, nullable=False),
    sa.Column("severity", sa.Text, nullable=False, server_default="info"),
    sa.Column("payload", sa.JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
)


knowledge_validation_policies = sa.Table(
    "knowledge_validation_policies",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("risk_level", sa.Text, nullable=False),
    sa.Column("strict_mode", sa.Boolean, nullable=False, server_default=sa.text("false")),
    sa.Column("require_validation", sa.Boolean, nullable=False, server_default=sa.text("true")),
    sa.Column("require_approved", sa.Boolean, nullable=False, server_default=sa.text("true")),
    sa.Column("require_not_expired", sa.Boolean, nullable=False, server_default=sa.text("false")),
    sa.Column("min_confidence", sa.Float, nullable=True),
    sa.Column("max_validation_age_days", sa.Integer, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.UniqueConstraint("risk_level", name="uq_knowledge_validation_policies_risk_level"),
)


knowledge_validation_policy_bundles = sa.Table(
    "knowledge_validation_policy_bundles",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("bundle_key", sa.Text, nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
    sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.UniqueConstraint("bundle_key", name="uq_knowledge_validation_policy_bundles_bundle_key"),
)


knowledge_validation_policy_rules = sa.Table(
    "knowledge_validation_policy_rules",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("bundle_id", sa.Uuid, sa.ForeignKey("knowledge_validation_policy_bundles.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("rule_key", sa.Text, nullable=False),
    sa.Column("risk_level", sa.Text, nullable=False),
    sa.Column("task_pattern", sa.Text, nullable=True),
    sa.Column("agent_slug", sa.Text, nullable=True),
    sa.Column("source_type", sa.Text, nullable=True),
    sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
    sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
    sa.Column("strict_mode", sa.Boolean, nullable=False, server_default=sa.text("false")),
    sa.Column("require_validation", sa.Boolean, nullable=False, server_default=sa.text("true")),
    sa.Column("require_approved", sa.Boolean, nullable=False, server_default=sa.text("true")),
    sa.Column("require_not_expired", sa.Boolean, nullable=False, server_default=sa.text("false")),
    sa.Column("min_confidence", sa.Float, nullable=True),
    sa.Column("max_validation_age_days", sa.Integer, nullable=True),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.UniqueConstraint("bundle_id", "rule_key", name="uq_knowledge_validation_policy_rules_bundle_rule_key"),
)


knowledge_validation_policy_rollouts = sa.Table(
    "knowledge_validation_policy_rollouts",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("bundle_id", sa.Uuid, sa.ForeignKey("knowledge_validation_policy_bundles.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("rollout_key", sa.Text, nullable=False),
    sa.Column("target_agent_slug", sa.Text, nullable=True),
    sa.Column("target_source_type", sa.Text, nullable=True),
    sa.Column("task_pattern", sa.Text, nullable=True),
    sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
    sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
    sa.Column("rollout_mode", sa.Text, nullable=False, server_default="full"),
    sa.Column("rollout_percentage", sa.Integer, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.UniqueConstraint("bundle_id", "rollout_key", name="uq_knowledge_validation_policy_rollouts_bundle_rollout_key"),
)


knowledge_validation_policy_change_events = sa.Table(
    "knowledge_validation_policy_change_events",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("entity_type", sa.Text, nullable=False),
    sa.Column("entity_id", sa.Uuid, nullable=True),
    sa.Column("entity_key", sa.Text, nullable=False),
    sa.Column("action", sa.Text, nullable=False),
    sa.Column("actor", sa.Text, nullable=True),
    sa.Column("before_state", sa.JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("after_state", sa.JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
)


knowledge_resolve_ranking_profiles = sa.Table(
    "knowledge_resolve_ranking_profiles",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("profile_key", sa.Text, nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
    sa.Column("base_score", sa.Float, nullable=False, server_default="1.0"),
    sa.Column("lexical_weight", sa.Float, nullable=False, server_default="0.8"),
    sa.Column("semantic_weight", sa.Float, nullable=False, server_default="1.0"),
    sa.Column("tag_weight", sa.Float, nullable=False, server_default="0.3"),
    sa.Column("validation_confidence_weight", sa.Float, nullable=False, server_default="0.5"),
    sa.Column("approved_bonus", sa.Float, nullable=False, server_default="0.5"),
    sa.Column("preferred_bonus", sa.Float, nullable=False, server_default="0.35"),
    sa.Column("deprecated_penalty", sa.Float, nullable=False, server_default="0.25"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.UniqueConstraint("profile_key", name="uq_knowledge_resolve_ranking_profiles_profile_key"),
)


knowledge_unit_lifecycle_events = sa.Table(
    "knowledge_unit_lifecycle_events",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("unit_id", sa.Uuid, sa.ForeignKey("knowledge_units.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("action", sa.Text, nullable=False),
    sa.Column("actor", sa.Text, nullable=True),
    sa.Column("payload", sa.JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
)


knowledge_resolve_audits = sa.Table(
    "knowledge_resolve_audits",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("task", sa.Text, nullable=False),
    sa.Column("agent_slug", sa.Text, nullable=True),
    sa.Column("requested_risk_level", sa.Text, nullable=False),
    sa.Column("tags", sa.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("selected_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("rejected_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("payload", sa.JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
)


knowledge_unit_embeddings = sa.Table(
    "knowledge_unit_embeddings",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("unit_id", sa.Uuid, sa.ForeignKey("knowledge_units.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("embedding_model", sa.Text, nullable=False),
    sa.Column("embedding_dimensions", sa.Integer, nullable=False),
    sa.Column("content_sha256", sa.Text, nullable=False),
    sa.Column("embedding", VectorType(), nullable=False),
    sa.Column("meta", sa.JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.UniqueConstraint("unit_id", "embedding_model", name="uq_knowledge_unit_embeddings_unit_model"),
)
