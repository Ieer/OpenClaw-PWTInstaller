from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Health(BaseModel):
    ok: bool


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
