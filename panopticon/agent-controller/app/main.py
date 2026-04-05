from __future__ import annotations

import os
import re
import shlex
import subprocess
from dataclasses import dataclass

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel


class ControlActionIn(BaseModel):
    action: str


class ControlActionOut(BaseModel):
    ok: bool
    agent: str
    action: str
    container: str
    status: str
    detail: str = ""


@dataclass(frozen=True)
class ControllerSettings:
    docker_bin: str
    allowed_agents: set[str]
    auth_token: str


def _load_allowed_agents() -> set[str]:
    raw = (os.getenv("MC_AGENT_CONTROLLER_ALLOWED_AGENTS") or "").strip()
    if not raw:
        return set()
    out: set[str] = set()
    for item in re.split(r"[;,\n]", raw):
        slug = item.strip()
        if slug:
            out.add(slug)
    return out


def _settings() -> ControllerSettings:
    return ControllerSettings(
        docker_bin=(os.getenv("MC_AGENT_CONTROLLER_DOCKER_BIN") or "docker").strip() or "docker",
        allowed_agents=_load_allowed_agents(),
        auth_token=(os.getenv("MC_AGENT_CONTROLLER_AUTH_TOKEN") or "").strip(),
    )


def _require_auth(settings: ControllerSettings, authorization: str | None) -> None:
    expected = settings.auth_token
    if not expected:
        raise HTTPException(status_code=503, detail="agent controller auth token is not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(status_code=403, detail="invalid token")


def _validate_slug(slug: str) -> str:
    value = str(slug or "").strip().lower()
    if not value:
        raise HTTPException(status_code=400, detail="agent is required")
    if not re.fullmatch(r"[a-z0-9_-]+", value):
        raise HTTPException(status_code=400, detail="invalid agent slug")
    return value


def _normalize_action(action: str) -> str:
    value = str(action or "").strip().lower()
    if value not in {"start", "stop", "restart"}:
        raise HTTPException(status_code=400, detail=f"invalid action: {value}")
    return value


def _run_command(settings: ControllerSettings, args: list[str]) -> tuple[int, str]:
    cmd = [settings.docker_bin, *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail=f"docker binary not found: {settings.docker_bin}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="docker command timeout")

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    detail = stdout or stderr
    if len(detail) > 400:
        detail = detail[:397] + "..."
    return proc.returncode, detail


def _container_status(settings: ControllerSettings, container: str) -> str:
    code, out = _run_command(
        settings,
        ["inspect", "-f", "{{.State.Status}}", container],
    )
    if code != 0:
        return "unknown"
    status = out.splitlines()[0].strip().lower() if out else "unknown"
    if status in {"running", "exited", "created", "restarting", "paused", "dead"}:
        return status
    return "unknown"


app = FastAPI(title="mission-control-agent-controller", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/v1/containers/{agent}/control", response_model=ControlActionOut)
def control_agent(
    agent: str,
    body: ControlActionIn,
    authorization: str | None = Header(default=None),
) -> ControlActionOut:
    settings = _settings()
    _require_auth(settings, authorization)

    slug = _validate_slug(agent)
    if settings.allowed_agents and slug not in settings.allowed_agents:
        raise HTTPException(status_code=403, detail=f"agent not allowed: {slug}")

    action = _normalize_action(body.action)
    container = f"openclaw-{slug}"

    code, detail = _run_command(settings, [action, container])
    if code != 0:
        raise HTTPException(
            status_code=502,
            detail=f"docker {shlex.quote(action)} {shlex.quote(container)} failed: {detail or 'unknown error'}",
        )

    status = _container_status(settings, container)
    return ControlActionOut(
        ok=True,
        agent=slug,
        action=action,
        container=container,
        status=status,
        detail=detail,
    )
