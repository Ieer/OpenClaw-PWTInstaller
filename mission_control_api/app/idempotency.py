from __future__ import annotations

import hashlib
import json

import sqlalchemy as sa
from fastapi import HTTPException

from .models import task_action_requests


def request_hash(body) -> str:
    return hashlib.sha256(json.dumps(body.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


async def replay_action(session, *, scope: str, key: str | None, body) -> dict | None:
    if key is None:
        return None
    if not key.strip():
        raise HTTPException(status_code=422, detail="Idempotency-Key must not be blank")
    lock_key = int.from_bytes(hashlib.sha256(f"action:{scope}:{key}".encode()).digest()[:8], "big", signed=True)
    await session.execute(sa.select(sa.func.pg_advisory_xact_lock(lock_key)))
    row = (await session.execute(sa.select(task_action_requests).where(
        task_action_requests.c.scope == scope, task_action_requests.c.key == key
    ))).first()
    if row:
        if row.request_hash != request_hash(body):
            raise HTTPException(status_code=409, detail="Idempotency-Key reused with different content")
        return row.response
    return None


async def save_action(session, *, scope: str, key: str | None, body, response) -> None:
    if key is not None:
        await session.execute(task_action_requests.insert().values(
            scope=scope, key=key, request_hash=request_hash(body),
            response=response.model_dump(mode="json") if hasattr(response, "model_dump") else response,
        ))