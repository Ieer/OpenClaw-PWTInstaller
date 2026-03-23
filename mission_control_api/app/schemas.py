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
