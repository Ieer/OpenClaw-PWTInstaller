from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from fastapi import HTTPException


RISK_RANK = {"low": 0, "normal": 1, "high": 2, "critical": 3}


def load_access_profiles(path: str | None) -> dict[str, dict[str, str]]:
    if not path:
        return {}
    profiles = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(profiles, dict):
        raise ValueError("knowledge access profiles must be an object")
    for digest, profile in profiles.items():
        if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("invalid knowledge credential digest")
        if not isinstance(profile, dict) or not profile.get("agent_slug") or profile.get("risk_floor") not in RISK_RANK:
            raise ValueError("invalid knowledge principal profile")
    return profiles


def bind_knowledge_request(body, *, authorization: str | None, admin_token: str | None,
                           profiles: dict[str, dict[str, str]]):
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if admin_token and token and hmac.compare_digest(token, admin_token):
        return body, "admin"
    if not admin_token and not profiles:
        return body, "legacy-unconfigured"
    if not token:
        raise HTTPException(status_code=401, detail="missing knowledge bearer token")
    profile = profiles.get(hashlib.sha256(token.encode("utf-8")).hexdigest())
    if profile is None:
        raise HTTPException(status_code=403, detail="invalid knowledge credential")
    agent = profile["agent_slug"]
    if body.agent_slug is not None and body.agent_slug != agent:
        raise HTTPException(status_code=403, detail="knowledge role does not match credential")
    risk = str(body.risk_level).strip().lower()
    if risk not in RISK_RANK:
        raise HTTPException(status_code=422, detail="invalid knowledge risk level")
    floor = profile["risk_floor"]
    if RISK_RANK[risk] < RISK_RANK[floor]:
        risk = floor
    if not body.task.strip() or len(body.task) > 4096 or len(body.semantic_query or "") > 4096:
        raise HTTPException(status_code=422, detail="knowledge query exceeds the principal budget")
    return body.model_copy(update={
        "agent_slug": agent, "risk_level": risk, "require_approved_validation": True,
        "include_rejected": False, "limit": min(max(body.limit, 1), 5),
        "semantic_limit": min(max(body.semantic_limit, 1), 20),
    }), "role"