from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid4

import sqlalchemy as sa
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .models import execution_jobs, execution_provider_charges


class JobCreate(BaseModel):
    agent_slug: str
    idempotency_key: str = Field(min_length=1, max_length=128)
    kind: Literal["main", "subtask", "maintenance"] = "main"
    priority: int = Field(default=100, ge=0, le=1000)
    provider: str | None = Field(default=None, max_length=128)
    estimated_tokens: int = Field(default=0, ge=0, le=1000000)
    max_attempts: int = Field(default=3, ge=1, le=5)
    timeout_seconds: int = Field(default=900, ge=10, le=86400)
    payload: dict = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def validate_payload_size(cls, value: dict) -> dict:
        if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > 32768:
            raise ValueError("payload must not exceed 32 KiB; use artifact references")
        return value

    @field_validator("idempotency_key", "provider")
    @classmethod
    def validate_nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("value must not be blank")
        return value.strip() if value else value


class JobClaim(BaseModel):
    agent_slug: str
    worker_id: str = Field(min_length=1, max_length=128)
    kind: Literal["main", "subtask", "maintenance"] = "main"
    workflows: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("workflows")
    @classmethod
    def validate_workflows(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 64 for value in values):
            raise ValueError("invalid workflow capability")
        return list(dict.fromkeys(value.strip() for value in values))


class JobLease(BaseModel):
    lease_token: UUID


class JobFinish(JobLease):
    success: bool = True
    result: dict = Field(default_factory=dict)
    retry: bool = False
    error: str | None = Field(default=None, max_length=1000)

    @field_validator("result")
    @classmethod
    def validate_result_size(cls, value: dict) -> dict:
        return JobCreate.validate_payload_size(value)


def job_fingerprint(body: JobCreate) -> str:
    values = body.model_dump(mode="json", exclude={"idempotency_key"})
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def job_public(row, *, include_lease: bool = False) -> dict:
    values = dict(row._mapping)
    if not include_lease:
        values.pop("lease_token", None)
    values.pop("payload_hash", None)
    return values


def lease_is_valid(row, lease_token: UUID, now: datetime) -> bool:
    return row.status == "RUNNING" and row.lease_token == lease_token and row.lease_expires_at > now


async def recover_expired_jobs(session, now: datetime) -> int:
    result = await session.execute(execution_jobs.update().where(
        execution_jobs.c.status == "RUNNING",
        sa.or_(execution_jobs.c.lease_expires_at <= now, execution_jobs.c.deadline_at <= now)
    ).values(
        status=sa.case((execution_jobs.c.attempts < execution_jobs.c.max_attempts, "QUEUED"), else_="FAILED"),
        lease_token=None, worker_id=None, lease_expires_at=None,
        available_at=now + timedelta(seconds=30), updated_at=now,
        last_error="lease expired; side effects must be reconciled before retry",
    ))
    return int(result.rowcount or 0)


async def claim_job(session, settings, body: JobClaim):
    await session.execute(sa.select(sa.func.pg_advisory_xact_lock(18910001)))
    now = datetime.now(timezone.utc)
    await recover_expired_jobs(session, now)
    active = (await session.execute(sa.select(
        execution_jobs.c.agent_slug, execution_jobs.c.kind
    ).where(execution_jobs.c.status == "RUNNING"))).all()
    kind_limits = {"main": settings.execution_main_limit, "subtask": settings.execution_subtask_limit,
                   "maintenance": settings.execution_maintenance_limit}
    if len(active) >= settings.execution_global_limit:
        return None
    if sum(row.agent_slug == body.agent_slug for row in active) >= settings.execution_agent_limit:
        return None
    if sum(row.kind == body.kind for row in active) >= kind_limits[body.kind]:
        return None
    candidate_query = sa.select(execution_jobs).where(
        execution_jobs.c.status == "QUEUED", execution_jobs.c.agent_slug == body.agent_slug,
        execution_jobs.c.kind == body.kind, execution_jobs.c.available_at <= now,
    )
    if body.workflows:
        candidate_query = candidate_query.where(execution_jobs.c.payload["workflow"].as_string().in_(body.workflows))
    candidates = (await session.execute(candidate_query.order_by(
        execution_jobs.c.priority, execution_jobs.c.created_at, execution_jobs.c.id
    ).limit(50).with_for_update(skip_locked=True))).all()
    for row in candidates:
        if row.provider:
            charges = (await session.execute(sa.select(
                sa.func.count(), sa.func.coalesce(sa.func.sum(execution_provider_charges.c.tokens), 0)
            ).where(execution_provider_charges.c.provider == row.provider,
                    execution_provider_charges.c.created_at > now - timedelta(seconds=60)))).one()
            if charges[0] >= settings.execution_provider_rpm or charges[1] + row.estimated_tokens > settings.execution_provider_tpm:
                continue
            await session.execute(execution_provider_charges.insert().values(
                id=uuid4(), provider=row.provider, tokens=row.estimated_tokens, created_at=now
            ))
        await session.execute(execution_provider_charges.delete().where(
            execution_provider_charges.c.created_at < now - timedelta(minutes=5)
        ))
        return (await session.execute(execution_jobs.update().where(execution_jobs.c.id == row.id).values(
            status="RUNNING", worker_id=body.worker_id, lease_token=uuid4(),
            lease_expires_at=now + timedelta(seconds=min(settings.execution_lease_seconds, row.timeout_seconds)),
            deadline_at=now + timedelta(seconds=row.timeout_seconds),
            attempts=row.attempts + 1, updated_at=now,
        ).returning(execution_jobs))).one()
    return None


def register_execution_routes(app, *, settings, get_session, auth_dependency, normalize_agent) -> None:
    def ensure_enabled() -> None:
        if not settings.execution_enabled:
            raise HTTPException(status_code=503, detail="managed execution queue is disabled")

    @app.post("/v1/execution/jobs")
    async def submit_job(body: JobCreate, _auth=Depends(auth_dependency), session=Depends(get_session)):
        ensure_enabled()
        body.agent_slug = normalize_agent(body.agent_slug)
        if body.provider and not 0 < body.estimated_tokens <= settings.execution_provider_tpm:
            raise HTTPException(status_code=422, detail="provider jobs require a positive token estimate within the per-minute budget")
        fingerprint = job_fingerprint(body)
        lock_key = int.from_bytes(hashlib.sha256(f"{body.agent_slug}:{body.idempotency_key}".encode()).digest()[:8], "big", signed=True)
        await session.execute(sa.select(sa.func.pg_advisory_xact_lock(lock_key)))
        existing = (await session.execute(sa.select(execution_jobs).where(
            execution_jobs.c.agent_slug == body.agent_slug, execution_jobs.c.idempotency_key == body.idempotency_key
        ))).first()
        if existing:
            if existing.payload_hash != fingerprint:
                raise HTTPException(status_code=409, detail="idempotency key reused with different content")
            return job_public(existing)
        values = body.model_dump(exclude={"agent_slug"})
        row = (await session.execute(execution_jobs.insert().values(
            id=uuid4(), agent_slug=body.agent_slug, payload_hash=fingerprint, **values
        ).returning(execution_jobs))).one()
        await session.commit()
        return job_public(row)

    @app.post("/v1/execution/claim")
    async def claim(body: JobClaim, _auth=Depends(auth_dependency), session=Depends(get_session)):
        ensure_enabled()
        body.agent_slug = normalize_agent(body.agent_slug)
        row = await claim_job(session, settings, body)
        await session.commit()
        return {"job": job_public(row, include_lease=True) if row else None}

    async def locked_lease(session, job_id: UUID, lease_token: UUID):
        row = (await session.execute(sa.select(execution_jobs).where(execution_jobs.c.id == job_id).with_for_update())).first()
        if not row:
            raise HTTPException(status_code=404, detail="job not found")
        now = datetime.now(timezone.utc)
        if not lease_is_valid(row, lease_token, now) or row.deadline_at <= now:
            raise HTTPException(status_code=409, detail="lease expired or superseded")
        return row, now

    @app.post("/v1/execution/jobs/{job_id}/heartbeat")
    async def heartbeat(job_id: UUID, body: JobLease, _auth=Depends(auth_dependency), session=Depends(get_session)):
        ensure_enabled()
        row, now = await locked_lease(session, job_id, body.lease_token)
        expires = min(row.deadline_at, now + timedelta(seconds=settings.execution_lease_seconds))
        await session.execute(execution_jobs.update().where(execution_jobs.c.id == job_id).values(lease_expires_at=expires, updated_at=now))
        await session.commit()
        return {"lease_expires_at": expires}

    @app.post("/v1/execution/jobs/{job_id}/finish")
    async def finish(job_id: UUID, body: JobFinish, _auth=Depends(auth_dependency), session=Depends(get_session)):
        ensure_enabled()
        row, now = await locked_lease(session, job_id, body.lease_token)
        status = "SUCCEEDED" if body.success else "QUEUED" if body.retry and row.attempts < row.max_attempts else "FAILED"
        row = (await session.execute(execution_jobs.update().where(execution_jobs.c.id == job_id).values(
            status=status, result=body.result, last_error=body.error,
            lease_token=None, worker_id=None, lease_expires_at=None, updated_at=now,
            available_at=now + timedelta(seconds=min(300, 2 ** row.attempts)),
        ).returning(execution_jobs))).one()
        await session.commit()
        return job_public(row)

    @app.get("/v1/execution/jobs/{job_id}")
    async def get_job(job_id: UUID, _auth=Depends(auth_dependency), session=Depends(get_session)):
        ensure_enabled()
        row = (await session.execute(sa.select(execution_jobs).where(execution_jobs.c.id == job_id))).first()
        if not row:
            raise HTTPException(status_code=404, detail="job not found")
        return job_public(row)

    @app.post("/v1/execution/jobs/{job_id}/cancel")
    async def cancel_job(job_id: UUID, _auth=Depends(auth_dependency), session=Depends(get_session)):
        ensure_enabled()
        row = (await session.execute(sa.select(execution_jobs).where(
            execution_jobs.c.id == job_id).with_for_update())).first()
        if not row:
            raise HTTPException(status_code=404, detail="job not found")
        if row.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return job_public(row)
        row = (await session.execute(execution_jobs.update().where(execution_jobs.c.id == job_id).values(
            status="CANCELLED", lease_token=None, worker_id=None, lease_expires_at=None,
            updated_at=datetime.now(timezone.utc), last_error="cancelled by trusted operator",
        ).returning(execution_jobs))).one()
        await session.commit()
        return job_public(row)

    @app.get("/v1/execution/summary")
    async def summary(_auth=Depends(auth_dependency), session=Depends(get_session)):
        ensure_enabled()
        now = datetime.now(timezone.utc)
        rows = (await session.execute(sa.select(execution_jobs.c.status, sa.func.count()).group_by(execution_jobs.c.status))).all()
        expired = (await session.execute(sa.select(sa.func.count()).select_from(execution_jobs).where(
            execution_jobs.c.status == "RUNNING", execution_jobs.c.lease_expires_at <= now
        ))).scalar_one()
        return {"counts": {row[0]: row[1] for row in rows}, "expired_leases": expired,
                "limits": {"global": settings.execution_global_limit, "main": settings.execution_main_limit,
                           "subtask": settings.execution_subtask_limit, "maintenance": settings.execution_maintenance_limit,
                           "per_agent": settings.execution_agent_limit},
                "scope": "managed jobs only; native chats and cron are not intercepted"}