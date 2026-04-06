from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Health(BaseModel):
    ok: bool


class ObservabilitySummaryOut(BaseModel):
    generated_at: datetime
    window_minutes: int
    request_total: int
    error_total: int
    error_rate: float
    event_throughput_per_min: float
    task_throughput_per_min: float
    event_backlog_total: int
    task_backlog_total: int
    healthy_agents: int
    total_agents: int
    agent_health_ratio: float
    heartbeat_stale_seconds: int


class HealthSignalOut(BaseModel):
    name: str
    source: str
    target: str
    ok: bool
    latency_ms: int | None = None
    detail: str | None = None


class ContainerHealthSummaryOut(BaseModel):
    generated_at: datetime
    compose_ok: int
    compose_total: int
    port_ok: int
    port_total: int
    http_ok: int
    http_total: int
    overall_ok: int
    overall_total: int
    overall_ratio: float
    signals: list[HealthSignalOut]


class TaskCreate(BaseModel):
    title: str
    status: str = "INBOX"
    assignee: str | None = None
    tags: list[str] = Field(default_factory=list)


class TaskOut(BaseModel):
    id: UUID
    title: str
    status: str
    assignee: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class CommentCreate(BaseModel):
    author: str
    body: str


class CommentOut(BaseModel):
    id: UUID
    task_id: UUID
    author: str
    body: str
    created_at: datetime


class EventIn(BaseModel):
    type: str
    agent: str | None = None
    task_id: UUID | None = None
    payload: dict = Field(default_factory=dict)


class EventOut(BaseModel):
    id: UUID
    type: str
    agent: str | None
    task_id: UUID | None
    payload: dict
    created_at: datetime


class EventLiteOut(BaseModel):
    id: UUID
    type: str
    agent: str | None
    task_id: UUID | None
    created_at: datetime
    method: str | None = None
    path: str | None = None
    status_code: int | None = None
    error_type: str | None = None
    test_id: str | None = None
    round: int | None = None


class AgentUsageSnapshotOut(BaseModel):
    agent: str
    input_tokens_24h: int = 0
    output_tokens_24h: int = 0
    cache_read_tokens_24h: int = 0
    cache_write_tokens_24h: int = 0
    total_tokens_24h: int = 0
    total_cost_24h: float = 0.0
    input_tokens_window: int = 0
    output_tokens_window: int = 0
    cache_read_tokens_window: int = 0
    cache_write_tokens_window: int = 0
    total_tokens_window: int = 0
    total_cost_window: float = 0.0
    missing_cost_entries_window: int = 0
    days: int = 7


class AgentControlActionIn(BaseModel):
    action: str


class AgentControlActionOut(BaseModel):
    ok: bool
    agent: str
    action: str
    container: str
    status: str
    detail: str = ""


class AgentCatalogItemOut(BaseModel):
    slug: str
    label: str
    enabled: bool = True
    gateway_host_port: int | None = None
    bridge_host_port: int | None = None
    direct_url: str = ""
    embed_path: str = ""
    gateway_token: str = ""
    open_mode: str = "iframe"
    order: int = 0


class BoardColumn(BaseModel):
    title: str
    count: int
    cards: list[TaskOut]


class BoardOut(BaseModel):
    columns: list[BoardColumn]


class SkillItem(BaseModel):
    slug: str
    name: str
    description: str | None = None
    path: str
    scope: str


class WorkspaceSkillGroup(BaseModel):
    agent_slug: str
    skills: list[SkillItem]


class AgentSkillMappingOut(BaseModel):
    id: UUID
    agent_slug: str
    skill_slug: str
    created_at: datetime


class SkillsMappingPatchIn(BaseModel):
    agent_slugs: list[str] = Field(default_factory=list)
    add_skill_slugs: list[str] = Field(default_factory=list)
    remove_skill_slugs: list[str] = Field(default_factory=list)


class SkillsMappingFailureItem(BaseModel):
    action: str
    agent_slug: str
    skill_slug: str
    reason: str


class SkillsMappingPatchOut(BaseModel):
    updated: int
    affected_agents: list[str]
    restart_hint: str
    failed: list[SkillsMappingFailureItem] = Field(default_factory=list)


class SkillsDriftItem(BaseModel):
    severity: str
    category: str
    agent_slug: str | None = None
    skill_slug: str | None = None
    path: str | None = None
    message: str


class SkillsMetricOut(BaseModel):
    key: str
    label: str
    value: str
    tone: str = "neutral"
    detail: str | None = None


class SkillInventoryItem(BaseModel):
    slug: str
    name: str
    description: str | None = None
    path: str
    scope: str
    agent_slug: str | None = None
    mapped_agents: list[str] = Field(default_factory=list)
    runtime_agents: list[str] = Field(default_factory=list)


class AgentSkillRuntimeConfigOut(BaseModel):
    agent_slug: str
    config_path: str
    config_exists: bool
    native_skills_mode: str | None = None
    allow_bundled: list[str] = Field(default_factory=list)
    extra_dirs: list[str] = Field(default_factory=list)


class AgentSkillRuntimeConfigPatchIn(BaseModel):
    agent_slug: str
    native_skills_mode: str | None = None
    allow_bundled: list[str] | None = None
    extra_dirs: list[str] | None = None


class AgentSkillRuntimeConfigPatchOut(BaseModel):
    updated: bool
    agent_slug: str
    runtime_config: AgentSkillRuntimeConfigOut
    drift: list[SkillsDriftItem] = Field(default_factory=list)
    restart_hint: str


class AgentSkillsDetailOut(BaseModel):
    agent_slug: str
    label: str
    enabled: bool = True
    mapped_global_skills: list[SkillItem] = Field(default_factory=list)
    workspace_skills: list[SkillItem] = Field(default_factory=list)
    runtime_skills: list[SkillItem] = Field(default_factory=list)
    runtime_config: AgentSkillRuntimeConfigOut
    drift: list[SkillsDriftItem] = Field(default_factory=list)
    restart_required: bool = False
    restart_hint: str = ""


class SkillsReportOut(BaseModel):
    generated_at: datetime
    total_agents: int
    total_global_skills: int
    total_workspace_skills: int
    total_runtime_skills: int
    total_mappings: int
    mapped_agents: int
    workspace_agents: int
    runtime_override_agents: int
    coverage_ratio: float
    drift_total: int
    pending_restart_agents: list[str] = Field(default_factory=list)
    metrics: list[SkillsMetricOut] = Field(default_factory=list)
    drift: list[SkillsDriftItem] = Field(default_factory=list)


class KnowledgeSourceImportIn(BaseModel):
    source_type: str = "file"
    title: str
    relative_path: str
    external_uri: str | None = None
    owner: str | None = None
    version_label: str | None = None
    meta: dict = Field(default_factory=dict)


class KnowledgeSourceOut(BaseModel):
    id: UUID
    source_type: str
    title: str
    external_uri: str | None = None
    storage_path: str
    checksum_sha256: str | None = None
    mime_type: str | None = None
    owner: str | None = None
    version_label: str | None = None
    status: str
    meta: dict = Field(default_factory=dict)
    collected_at: datetime
    updated_at: datetime


class KnowledgeSourceScanIn(BaseModel):
    subdir: str = ""
    source_type: str = "file"
    owner: str | None = None
    version_label: str | None = None
    max_files: int = 200
    include_extensions: list[str] = Field(default_factory=list)
    dry_run: bool = False


class KnowledgeSourceScanOut(BaseModel):
    scanned: int
    imported: int
    skipped_existing: int
    skipped_invalid: int
    dry_run: bool
    items: list[KnowledgeSourceOut] = Field(default_factory=list)


class KnowledgeSourceChunkIn(BaseModel):
    chunk_chars: int = 1200
    chunk_overlap: int = 120
    max_chunks: int = 200
    risk_level: str = "normal"
    tags: list[str] = Field(default_factory=list)
    agent_scope: list[str] = Field(default_factory=list)
    owner: str | None = None
    ocr_enabled: bool = True
    ocr_languages: str | None = None
    max_pdf_pages: int | None = None
    dry_run: bool = False


class KnowledgeSourceChunkOut(BaseModel):
    source_id: UUID
    scanned_chars: int
    chunks_total: int
    created: int
    skipped_existing: int
    dry_run: bool
    items: list[KnowledgeUnitOut] = Field(default_factory=list)


class KnowledgeUnitCreateIn(BaseModel):
    source_id: UUID | None = None
    unit_key: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    agent_scope: list[str] = Field(default_factory=list)
    risk_level: str = "normal"
    status: str = "active"
    meta: dict = Field(default_factory=dict)


class KnowledgeUnitOut(BaseModel):
    id: UUID
    source_id: UUID | None = None
    unit_key: str
    title: str
    content: str
    content_sha256: str | None = None
    tags: list[str] = Field(default_factory=list)
    agent_scope: list[str] = Field(default_factory=list)
    risk_level: str
    status: str
    lifecycle_stage: str = "active"
    superseded_by_unit_id: UUID | None = None
    retired_at: datetime | None = None
    meta: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class KnowledgeValidationCreateIn(BaseModel):
    unit_id: UUID
    validator: str
    validation_status: str = "approved"
    expires_at: datetime | None = None
    confidence: float | None = None
    notes: str | None = None
    meta: dict = Field(default_factory=dict)


class KnowledgeValidationOut(BaseModel):
    id: UUID
    unit_id: UUID
    validator: str
    validation_status: str
    validated_at: datetime
    expires_at: datetime | None = None
    confidence: float | None = None
    notes: str | None = None
    meta: dict = Field(default_factory=dict)
    created_at: datetime


class KnowledgeValidationPolicyUpsertIn(BaseModel):
    strict_mode: bool = False
    require_validation: bool = True
    require_approved: bool = True
    require_not_expired: bool = False
    min_confidence: float | None = None
    max_validation_age_days: int | None = None


class KnowledgeValidationPolicyBundleUpsertIn(BaseModel):
    bundle_key: str
    description: str | None = None
    is_default: bool = False
    enabled: bool = True


class KnowledgeValidationPolicyBundleOut(BaseModel):
    id: UUID
    bundle_key: str
    description: str | None = None
    is_default: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime


class KnowledgeValidationPolicyRuleUpsertIn(BaseModel):
    bundle_id: UUID
    rule_key: str
    risk_level: str
    task_pattern: str | None = None
    agent_slug: str | None = None
    source_type: str | None = None
    priority: int = 100
    enabled: bool = True
    strict_mode: bool = False
    require_validation: bool = True
    require_approved: bool = True
    require_not_expired: bool = False
    min_confidence: float | None = None
    max_validation_age_days: int | None = None
    description: str | None = None


class KnowledgeValidationPolicyRuleOut(BaseModel):
    id: UUID
    bundle_id: UUID
    rule_key: str
    risk_level: str
    task_pattern: str | None = None
    agent_slug: str | None = None
    source_type: str | None = None
    priority: int
    enabled: bool
    strict_mode: bool
    require_validation: bool
    require_approved: bool
    require_not_expired: bool
    min_confidence: float | None = None
    max_validation_age_days: int | None = None
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeValidationPolicyRolloutUpsertIn(BaseModel):
    bundle_id: UUID
    rollout_key: str
    target_agent_slug: str | None = None
    target_source_type: str | None = None
    task_pattern: str | None = None
    priority: int = 100
    enabled: bool = True
    rollout_mode: str = "full"
    rollout_percentage: int | None = None


class KnowledgeValidationPolicyRolloutOut(BaseModel):
    id: UUID
    bundle_id: UUID
    rollout_key: str
    target_agent_slug: str | None = None
    target_source_type: str | None = None
    task_pattern: str | None = None
    priority: int
    enabled: bool
    rollout_mode: str
    rollout_percentage: int | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeValidationPolicyChangeEventOut(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID | None = None
    entity_key: str
    action: str
    actor: str | None = None
    before_state: dict = Field(default_factory=dict)
    after_state: dict = Field(default_factory=dict)
    created_at: datetime


class KnowledgeValidationPolicyRollbackIn(BaseModel):
    actor: str | None = None


class KnowledgeValidationPolicyRollbackOut(BaseModel):
    entity_type: str
    entity_id: UUID
    entity_key: str
    rollback_action: str
    restored_from_event_id: UUID | None = None
    current_state: dict = Field(default_factory=dict)


class KnowledgeValidationPolicyObservabilityItemOut(BaseModel):
    key: str
    total_resolve_requests: int
    requests_with_hits: int
    requests_with_rejections: int
    total_selected_units: int
    total_rejected_units: int
    resolve_hit_rate: float
    resolve_rejection_rate: float


class KnowledgeValidationPolicyObservabilityOut(BaseModel):
    window_days: int
    total_resolve_requests: int
    bundles: list[KnowledgeValidationPolicyObservabilityItemOut] = Field(default_factory=list)
    rollouts: list[KnowledgeValidationPolicyObservabilityItemOut] = Field(default_factory=list)
    ranking_profiles: list[KnowledgeValidationPolicyObservabilityItemOut] = Field(default_factory=list)


class KnowledgeResolveRankingProfileUpsertIn(BaseModel):
    profile_key: str
    description: str | None = None
    enabled: bool = True
    base_score: float = 1.0
    lexical_weight: float = 0.8
    semantic_weight: float = 1.0
    tag_weight: float = 0.3
    validation_confidence_weight: float = 0.5
    approved_bonus: float = 0.5
    preferred_bonus: float = 0.35
    deprecated_penalty: float = 0.25


class KnowledgeResolveRankingProfileOut(BaseModel):
    id: UUID
    profile_key: str
    description: str | None = None
    enabled: bool
    base_score: float
    lexical_weight: float
    semantic_weight: float
    tag_weight: float
    validation_confidence_weight: float
    approved_bonus: float
    preferred_bonus: float
    deprecated_penalty: float
    created_at: datetime
    updated_at: datetime


class KnowledgeValidationPolicyOut(BaseModel):
    risk_level: str
    strict_mode: bool
    require_validation: bool
    require_approved: bool
    require_not_expired: bool
    min_confidence: float | None = None
    max_validation_age_days: int | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeResolveIn(BaseModel):
    task: str
    agent_slug: str | None = None
    risk_level: str = "normal"
    tags: list[str] = Field(default_factory=list)
    limit: int = 10
    retrieval_mode: str = "lexical"
    ranking_profile: str = "balanced"
    semantic_query: str | None = None
    semantic_limit: int = 20
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    min_semantic_similarity: float | None = None
    min_score: float | None = None
    source_type: str | None = None
    require_approved_validation: bool | None = None
    include_rejected: bool = False


class KnowledgeResolveItemOut(BaseModel):
    unit: KnowledgeUnitOut
    validation_status: str | None = None
    validation_expires_at: datetime | None = None
    score: float = 0.0
    semantic_similarity: float | None = None
    retrieval_channels: list[str] = Field(default_factory=list)
    score_breakdown: dict = Field(default_factory=dict)


class KnowledgeResolveRejectedOut(BaseModel):
    unit_id: str
    unit_key: str
    source_id: str | None = None
    reason: str


class KnowledgeResolveOut(BaseModel):
    task: str
    agent_slug: str | None = None
    risk_level: str
    total: int
    rejected_count: int = 0
    items: list[KnowledgeResolveItemOut] = Field(default_factory=list)
    rejected: list[KnowledgeResolveRejectedOut] = Field(default_factory=list)


class KnowledgeSearchIn(BaseModel):
    query: str
    limit: int = 10
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    source_id: UUID | None = None
    source_type: str | None = None
    agent_slug: str | None = None
    risk_level: str = "normal"
    require_approved_validation: bool = False
    tags: list[str] = Field(default_factory=list)


class KnowledgeSearchItemOut(BaseModel):
    unit: KnowledgeUnitOut
    embedding_model: str
    embedding_dimensions: int
    source_type: str | None = None
    distance: float
    similarity: float


class KnowledgeSearchOut(BaseModel):
    query: str
    total: int
    embedding_model: str
    embedding_dimensions: int
    items: list[KnowledgeSearchItemOut] = Field(default_factory=list)


class KnowledgeFeedbackIn(BaseModel):
    unit_id: UUID
    feedback_type: str
    agent: str | None = None
    severity: str = "info"
    payload: dict = Field(default_factory=dict)


class KnowledgeFeedbackOut(BaseModel):
    id: UUID
    unit_id: UUID
    feedback_type: str
    agent: str | None = None
    severity: str
    payload: dict = Field(default_factory=dict)
    created_at: datetime


class KnowledgeFeedbackSummaryOut(BaseModel):
    feedback_type: str
    count: int


class KnowledgeResolveAuditOut(BaseModel):
    id: UUID
    task: str
    agent_slug: str | None = None
    requested_risk_level: str
    tags: list[str] = Field(default_factory=list)
    selected_count: int
    rejected_count: int
    payload: dict = Field(default_factory=dict)
    created_at: datetime


class KnowledgeLifecycleActionIn(BaseModel):
    action: str
    actor: str | None = None
    superseded_by_unit_id: UUID | None = None
    payload: dict = Field(default_factory=dict)


class KnowledgeLifecycleEventOut(BaseModel):
    id: UUID
    unit_id: UUID
    action: str
    actor: str | None = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime


class KnowledgeResolveRejectSummaryOut(BaseModel):
    reason: str
    count: int
    rate: float = 0.0


class KnowledgeResolveRiskMetricsOut(BaseModel):
    risk_level: str
    total_resolve_requests: int
    requests_with_hits: int
    requests_with_rejections: int
    total_selected_units: int
    total_rejected_units: int
    resolve_hit_rate: float
    resolve_rejection_rate: float


class KnowledgeResolveMetricsOut(BaseModel):
    window_days: int
    total_resolve_requests: int
    requests_with_hits: int
    requests_with_rejections: int
    requests_without_hits: int = 0
    requests_without_rejections: int = 0
    total_selected_units: int
    total_rejected_units: int
    resolve_hit_rate: float
    resolve_error_rate: float
    resolve_rejection_rate: float = 0.0
    unit_selection_rate: float = 0.0
    expired_rejection_count: int
    expired_rejection_rate: float = 0.0
    total_parsed_sources: int = 0
    ocr_fallback_count: int = 0
    ocr_failure_count: int = 0
    ocr_failure_rate: float = 0.0
    ocr_page_truncation_count: int = 0
    top_reject_reasons: list[KnowledgeResolveRejectSummaryOut] = Field(default_factory=list)
    risk_breakdown: list[KnowledgeResolveRiskMetricsOut] = Field(default_factory=list)
