from __future__ import annotations

import json
import re
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, Response
import httpx
import asyncio
from redis.asyncio import Redis

from .config import Settings, load_settings
from .db import create_engine, create_session_factory
from .models import agent_skill_mappings, comments, events, tasks
from .schemas import (
    AgentControlActionIn,
    AgentControlActionOut,
    AgentSkillMappingOut,
    AgentUsageSnapshotOut,
    BoardColumn,
    BoardOut,
    CommentCreate,
    CommentOut,
    EventIn,
    EventLiteOut,
    EventOut,
    ContainerHealthSummaryOut,
    Health,
    HealthSignalOut,
    ObservabilitySummaryOut,
    SkillItem,
    SkillsMappingFailureItem,
    SkillsMappingPatchIn,
    SkillsMappingPatchOut,
    TaskCreate,
    TaskOut,
    WorkspaceSkillGroup,
)


ALLOWED_TASK_STATUSES = {"INBOX", "ASSIGNED", "IN PROGRESS", "REVIEW", "DONE"}
TASK_STATUS_TRANSITIONS = {
    "INBOX": {"ASSIGNED"},
    "ASSIGNED": {"IN PROGRESS", "REVIEW"},
    "IN PROGRESS": {"REVIEW", "DONE"},
    "REVIEW": {"IN PROGRESS", "DONE"},
    "DONE": set(),
}

USAGE_CACHE_TTL_SECONDS = 15.0
_AGENT_USAGE_CACHE: dict[str, object] = {
    "days": None,
    "generated_at": 0.0,
    "data": [],
}

ALLOWED_AGENT_CONTROL_ACTIONS = {"start", "stop", "restart"}


def _rewrite_avatar_paths(obj, agent: str):
    if isinstance(obj, str):
        if obj.startswith("/avatar/"):
            return f"/chat/{agent}{obj}"
        return obj
    if isinstance(obj, list):
        return [_rewrite_avatar_paths(item, agent) for item in obj]
    if isinstance(obj, dict):
        return {k: _rewrite_avatar_paths(v, agent) for k, v in obj.items()}
    return obj


def _build_chat_inject_script(
    agent: str,
    token: str | None,
    *,
    clear_device_auth_storage: bool = True,
    inject_gateway_settings: bool = True,
    dom_avatar_rewrite: bool = True,
) -> str:
    base_path = f"/chat/{agent}"
    token_json = json.dumps(token or "", ensure_ascii=False)
    parts = [f'window.__OPENCLAW_CONTROL_UI_BASE_PATH__="{base_path}";', "(function(){"]
    if clear_device_auth_storage or inject_gateway_settings:
        parts.append("try{")
        if clear_device_auth_storage:
            parts.append('localStorage.removeItem("openclaw.device.auth.v1");')
            parts.append('sessionStorage.removeItem("openclaw.device.auth.v1");')
        if inject_gateway_settings:
            parts.extend(
                [
                    'const k="openclaw.control.settings.v1";',
                    'const raw=localStorage.getItem(k);',
                    'let v={};',
                    'try{v=raw?JSON.parse(raw):{};}catch{}',
                    f'v.gatewayUrl=(location.protocol==="https:"?"wss":"ws")+"://"+location.host+"{base_path}/";',
                    f'v.token={token_json};',
                    'localStorage.setItem(k,JSON.stringify(v));',
                ]
            )
        parts.append("}catch(e){}")
    if dom_avatar_rewrite:
        parts.extend(
            [
                "try{",
                f'const p="{base_path}";',
                "const scan=()=>{",
                "document.querySelectorAll('img.chat-avatar.assistant[src^=\"/avatar/\"]').forEach((img)=>{",
                'const s=img.getAttribute("src")||"";',
                'if(s.startsWith("/avatar/"))img.setAttribute("src",p+s);',
                "});",
                "};",
                "scan();",
                "const mo=new MutationObserver(()=>scan());",
                'mo.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:["src"]});',
                'window.addEventListener("beforeunload",()=>mo.disconnect(),{once:true});',
                "}catch(e){}",
            ]
        )
    parts.append("})();")
    return "".join(parts)


def _normalize_control_ui_origin(origin: str | None) -> str | None:
    if not origin:
        return None
    if origin.startswith("http://127.0.0.1:"):
        return origin.replace("http://127.0.0.1", "http://localhost", 1)
    if origin.startswith("https://127.0.0.1:"):
        return origin.replace("https://127.0.0.1", "https://localhost", 1)
    return origin


def _sanitize_connect_auth(
    message: str,
    token: str | None,
    *,
    strip_stale_device_fields: bool = True,
    force_token_in_connect: bool = True,
) -> str:
    try:
        req = json.loads(message)
    except Exception:
        return message

    if not isinstance(req, dict):
        return message
    if req.get("type") != "req" or req.get("method") != "connect":
        return message
    if not isinstance(req.get("params"), dict):
        return message

    params = req["params"]

    stale_device_keys = {
        "device",
        "deviceId",
        "deviceID",
        "device_id",
        "deviceKey",
        "device_key",
        "deviceSecret",
        "device_secret",
        "deviceToken",
        "device_token",
        "clientId",
        "client_id",
    }

    auth = params.get("auth")
    if not isinstance(auth, dict):
        auth = {}

    if strip_stale_device_fields:
        for key in stale_device_keys:
            auth.pop(key, None)
            params.pop(key, None)

    if token and force_token_in_connect:
        params["auth"] = {"token": token}
    elif token and not auth.get("token"):
        auth["token"] = token
        params["auth"] = auth
    elif auth:
        params["auth"] = auth
    else:
        params.pop("auth", None)

    req["params"] = params
    return json.dumps(req, ensure_ascii=False)


def _rewrite_avatar_meta(content: bytes, agent: str, query: str) -> bytes:
    try:
        payload = json.loads(content.decode("utf-8", errors="replace"))
    except Exception:
        return content

    avatar_url = payload.get("avatarUrl") if isinstance(payload, dict) else None
    if isinstance(avatar_url, str) and avatar_url.startswith("/avatar/"):
        rewritten = f"/chat/{agent}{avatar_url}"
        if query:
            rewritten = f"{rewritten}?{query}"
        payload["avatarUrl"] = rewritten
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return content


def _rewrite_control_ui_config(content: bytes, agent: str, *, rewrite_avatar: bool = True) -> bytes:
    try:
        payload = json.loads(content.decode("utf-8", errors="replace"))
    except Exception:
        return content

    if not isinstance(payload, dict):
        return content

    base_path = f"/chat/{agent}"
    payload["basePath"] = base_path

    if rewrite_avatar:
        avatar = payload.get("assistantAvatar")
        if isinstance(avatar, str) and avatar.startswith("/avatar/"):
            payload["assistantAvatar"] = f"{base_path}{avatar}"

    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _avatar_fallback_svg(agent: str) -> bytes:
    label = (agent[:1] or "A").upper()
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'>"
        "<rect width='96' height='96' rx='48' fill='#2f3747'/>"
        "<text x='50%' y='54%' dominant-baseline='middle' text-anchor='middle' "
        "font-family='system-ui, -apple-system, Segoe UI, Roboto, sans-serif' "
        "font-size='42' fill='#ffffff'>"
        f"{label}</text></svg>"
    ).encode("utf-8")


def require_auth(settings: Settings, authorization: str | None = Header(default=None)) -> None:
    if not settings.auth_token:
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != settings.auth_token:
        raise HTTPException(status_code=403, detail="invalid token")


def _parse_skill_frontmatter(skill_file: Path, fallback_slug: str) -> tuple[str, str | None]:
    name = fallback_slug
    description: str | None = None

    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError:
        return name, description

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return name, description

    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("name:"):
            parsed = line.split(":", 1)[1].strip().strip('"').strip("'")
            if parsed:
                name = parsed
        elif line.startswith("description:"):
            parsed = line.split(":", 1)[1].strip().strip('"').strip("'")
            if parsed:
                description = parsed
    return name, description


def _scan_global_skills(settings: Settings) -> list[SkillItem]:
    root = Path(settings.global_skills_dir)
    if not root.exists() or not root.is_dir():
        return []

    out: list[SkillItem] = []
    for skill_file in sorted(root.glob("*/SKILL.md")):
        slug = skill_file.parent.name
        name, description = _parse_skill_frontmatter(skill_file, slug)
        out.append(
            SkillItem(
                slug=slug,
                name=name,
                description=description,
                path=str(skill_file),
                scope="global",
            )
        )
    return out


def _scan_workspace_skills(settings: Settings, agent_slug: str | None = None) -> list[WorkspaceSkillGroup]:
    root = Path(settings.agent_homes_dir)
    if not root.exists() or not root.is_dir():
        return []

    groups: list[WorkspaceSkillGroup] = []
    agent_dirs = sorted(path for path in root.iterdir() if path.is_dir())

    for agent_dir in agent_dirs:
        slug = agent_dir.name
        if agent_slug and slug != agent_slug:
            continue

        skills_dir = agent_dir / "skills"
        skill_items: list[SkillItem] = []
        if skills_dir.exists() and skills_dir.is_dir():
            for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
                s_slug = skill_file.parent.name
                s_name, s_desc = _parse_skill_frontmatter(skill_file, s_slug)
                skill_items.append(
                    SkillItem(
                        slug=s_slug,
                        name=s_name,
                        description=s_desc,
                        path=str(skill_file),
                        scope="workspace",
                    )
                )

        groups.append(WorkspaceSkillGroup(agent_slug=slug, skills=skill_items))
    return groups


def _scan_agent_slugs(settings: Settings) -> list[str]:
    root = Path(settings.agent_homes_dir)
    if not root.exists() or not root.is_dir():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def _known_agent_slugs(settings: Settings) -> set[str]:
    root = Path(settings.agent_homes_dir)
    if not root.exists() or not root.is_dir():
        return set()
    return {path.name for path in root.iterdir() if path.is_dir()}


async def _forward_agent_control(
    settings: Settings,
    *,
    agent: str,
    action: str,
) -> AgentControlActionOut:
    base_url = (settings.agent_controller_url or "").strip().rstrip("/")
    if not base_url:
        raise HTTPException(status_code=503, detail="agent controller is not configured")

    target_url = f"{base_url}/v1/containers/{urllib.parse.quote(agent, safe='')}/control"
    timeout = max(1.0, float(settings.agent_controller_timeout_seconds or 5.0))

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(target_url, json={"action": action})
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"agent controller unavailable: {exc.__class__.__name__}")

    try:
        payload = resp.json()
    except Exception:
        payload = {}

    if resp.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else "controller returned error"
        raise HTTPException(status_code=resp.status_code, detail=str(detail or "controller returned error"))

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="invalid controller response")

    return AgentControlActionOut(
        ok=bool(payload.get("ok", False)),
        agent=str(payload.get("agent") or agent),
        action=str(payload.get("action") or action),
        container=str(payload.get("container") or f"openclaw-{agent}"),
        status=str(payload.get("status") or "unknown"),
        detail=str(payload.get("detail") or ""),
    )


def _validate_handoff_payload(payload: dict, known_agents: set[str]) -> list[str]:
    errors: list[str] = []

    target_agent = str(payload.get("to") or "").strip()
    if not target_agent:
        errors.append("payload.to is required")
    elif known_agents and target_agent not in known_agents:
        errors.append(f"payload.to agent not found: {target_agent}")

    for field in ("problem", "context", "expected_output"):
        value = str(payload.get(field) or "").strip()
        if not value:
            errors.append(f"payload.{field} is required")

    artifact_refs = payload.get("artifact_refs")
    if not isinstance(artifact_refs, list) or not artifact_refs:
        errors.append("payload.artifact_refs must be a non-empty list")
    elif not all(isinstance(item, str) and item.strip() for item in artifact_refs):
        errors.append("payload.artifact_refs must contain non-empty strings")

    if not isinstance(payload.get("review_gate"), bool):
        errors.append("payload.review_gate must be boolean")

    return errors


def _parse_iso_datetime(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _host_port_from_url(raw_url: str, default_port: int) -> tuple[str | None, int]:
    parsed = urlparse(raw_url)
    host = parsed.hostname
    port = parsed.port or default_port
    return host, int(port)


async def _probe_tcp(host: str, port: int, *, timeout_seconds: float = 1.2) -> tuple[bool, int | None, str]:
    started = time.perf_counter()
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, int(port)), timeout=timeout_seconds)
        writer.close()
        await writer.wait_closed()
        latency_ms = int((time.perf_counter() - started) * 1000)
        return True, latency_ms, "connected"
    except Exception as exc:
        return False, None, f"{exc.__class__.__name__}: {exc}"


async def _probe_http(url: str, *, timeout_seconds: float = 1.5) -> tuple[bool, int | None, str]:
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            response = await client.get(url)
        latency_ms = int((time.perf_counter() - started) * 1000)
        ok = int(response.status_code) < 500
        return ok, latency_ms, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, None, f"{exc.__class__.__name__}: {exc}"


def _line_usage_from_session_event(line_obj: dict) -> tuple[datetime | None, dict | None]:
    message = line_obj.get("message") if isinstance(line_obj.get("message"), dict) else {}
    payload = line_obj.get("payload") if isinstance(line_obj.get("payload"), dict) else {}

    usage = None
    for candidate in (message.get("usage"), line_obj.get("usage"), payload.get("usage")):
        if isinstance(candidate, dict):
            usage = candidate
            break

    if not isinstance(usage, dict):
        return None, None

    mapped_usage = {
        "input": _safe_int(usage.get("input") or usage.get("input_tokens")),
        "output": _safe_int(usage.get("output") or usage.get("output_tokens")),
        "cacheRead": _safe_int(usage.get("cacheRead") or usage.get("cache_read_tokens")),
        "cacheWrite": _safe_int(usage.get("cacheWrite") or usage.get("cache_write_tokens")),
        "totalTokens": _safe_int(usage.get("totalTokens") or usage.get("total_tokens")),
        "cost": {
            "total": _safe_float(
                (usage.get("cost") or {}).get("total") if isinstance(usage.get("cost"), dict) else usage.get("total_cost")
            ),
        },
    }

    if mapped_usage["totalTokens"] <= 0:
        mapped_usage["totalTokens"] = (
            mapped_usage["input"]
            + mapped_usage["output"]
            + mapped_usage["cacheRead"]
            + mapped_usage["cacheWrite"]
        )

    event_ts = _parse_iso_datetime(
        line_obj.get("timestamp")
        or line_obj.get("created_at")
        or line_obj.get("createdAt")
        or line_obj.get("updated_at")
        or line_obj.get("updatedAt")
    )
    if event_ts is None:
        ts_value = line_obj.get("ts")
        if isinstance(ts_value, (int, float)):
            try:
                epoch = float(ts_value)
                if epoch > 10_000_000_000:
                    epoch = epoch / 1000.0
                event_ts = datetime.fromtimestamp(epoch)
            except (ValueError, OSError):
                event_ts = None

    return event_ts, mapped_usage


def _line_usage_from_cron_event(line_obj: dict) -> tuple[datetime | None, dict | None]:
    usage = line_obj.get("usage")
    if not isinstance(usage, dict):
        payload = line_obj.get("payload") if isinstance(line_obj.get("payload"), dict) else {}
        usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None, None

    ts_ms_raw = line_obj.get("ts")
    event_ts = None
    if isinstance(ts_ms_raw, (int, float)):
        try:
            event_ts = datetime.fromtimestamp(float(ts_ms_raw) / 1000.0)
        except (ValueError, OSError):
            event_ts = None

    mapped_usage = {
        "input": int(usage.get("input_tokens") or 0),
        "output": int(usage.get("output_tokens") or 0),
        "cacheRead": int(usage.get("cache_read_tokens") or 0),
        "cacheWrite": int(usage.get("cache_write_tokens") or 0),
        "totalTokens": int(usage.get("total_tokens") or 0),
        "cost": {
            "total": float(usage.get("total_cost") or 0.0),
        },
    }
    return event_ts, mapped_usage


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _accumulate_usage(aggregate: dict, usage: dict, *, window_key: str) -> None:
    aggregate[f"input_tokens_{window_key}"] += _safe_int(usage.get("input"))
    aggregate[f"output_tokens_{window_key}"] += _safe_int(usage.get("output"))
    aggregate[f"cache_read_tokens_{window_key}"] += _safe_int(usage.get("cacheRead"))
    aggregate[f"cache_write_tokens_{window_key}"] += _safe_int(usage.get("cacheWrite"))

    total_tokens = _safe_int(usage.get("totalTokens"))
    if total_tokens <= 0:
        total_tokens = (
            _safe_int(usage.get("input"))
            + _safe_int(usage.get("output"))
            + _safe_int(usage.get("cacheRead"))
            + _safe_int(usage.get("cacheWrite"))
        )
    aggregate[f"total_tokens_{window_key}"] += total_tokens

    usage_cost = usage.get("cost") if isinstance(usage.get("cost"), dict) else {}
    if isinstance(usage_cost, dict):
        total_cost = _safe_float(usage_cost.get("total"))
        aggregate[f"total_cost_{window_key}"] += total_cost
        if total_cost <= 0 and total_tokens > 0:
            aggregate["missing_cost_entries_window"] += 1


def _iter_agent_usage_lines(agent_dir: Path):
    yielded: set[str] = set()

    session_patterns = [
        "agents/*/sessions/**/*.jsonl",
        "agents/*/sessions/**/*.jsonl.reset.*",
        "agents/*/sessions/**/*.jsonl.deleted.*",
        "sessions/**/*.jsonl",
        "sessions/**/*.jsonl.reset.*",
        "sessions/**/*.jsonl.deleted.*",
    ]
    cron_patterns = [
        "cron/runs/*.jsonl",
        "cron/runs/**/*.jsonl",
    ]

    for pattern in session_patterns:
        for file_path in agent_dir.glob(pattern):
            if file_path.is_file():
                key = str(file_path)
                if key not in yielded:
                    yielded.add(key)
                    yield file_path, "session"

    for pattern in cron_patterns:
        for file_path in agent_dir.glob(pattern):
            if file_path.is_file():
                key = str(file_path)
                if key not in yielded:
                    yielded.add(key)
                    yield file_path, "cron"


def _collect_agent_usage_snapshot(settings: Settings, days: int) -> list[AgentUsageSnapshotOut]:
    root = Path(settings.agent_homes_dir)
    if not root.exists() or not root.is_dir():
        return []

    window_seconds = max(1, min(days, 90)) * 24 * 60 * 60
    window_start_epoch = time.time() - window_seconds
    day_24h_epoch = time.time() - 24 * 60 * 60

    out: list[AgentUsageSnapshotOut] = []

    for agent_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        aggregate = {
            "agent": agent_dir.name,
            "input_tokens_24h": 0,
            "output_tokens_24h": 0,
            "cache_read_tokens_24h": 0,
            "cache_write_tokens_24h": 0,
            "total_tokens_24h": 0,
            "total_cost_24h": 0.0,
            "input_tokens_window": 0,
            "output_tokens_window": 0,
            "cache_read_tokens_window": 0,
            "cache_write_tokens_window": 0,
            "total_tokens_window": 0,
            "total_cost_window": 0.0,
            "missing_cost_entries_window": 0,
            "days": max(1, min(days, 90)),
        }

        for file_path, source_type in _iter_agent_usage_lines(agent_dir):
            try:
                with file_path.open("r", encoding="utf-8") as handle:
                    for raw_line in handle:
                        line = raw_line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        if source_type == "session":
                            event_dt, usage = _line_usage_from_session_event(obj)
                        else:
                            event_dt, usage = _line_usage_from_cron_event(obj)

                        if usage is None:
                            continue

                        include_24h = False
                        include_window = True
                        if event_dt is not None:
                            event_epoch = event_dt.timestamp()
                            include_window = event_epoch >= window_start_epoch
                            include_24h = event_epoch >= day_24h_epoch

                        if include_window:
                            _accumulate_usage(aggregate, usage, window_key="window")
                        if include_24h:
                            _accumulate_usage(aggregate, usage, window_key="24h")
            except OSError:
                continue

        out.append(AgentUsageSnapshotOut(**aggregate))

    return out


def _get_agent_usage_snapshot(settings: Settings, days: int) -> list[AgentUsageSnapshotOut]:
    clamped_days = max(1, min(int(days), 90))
    now_ts = time.time()

    cached_days = _AGENT_USAGE_CACHE.get("days")
    cached_at = _safe_float(_AGENT_USAGE_CACHE.get("generated_at"))
    cached_data = _AGENT_USAGE_CACHE.get("data")

    if (
        cached_days == clamped_days
        and isinstance(cached_data, list)
        and now_ts - cached_at <= USAGE_CACHE_TTL_SECONDS
    ):
        return cached_data  # type: ignore[return-value]

    fresh = _collect_agent_usage_snapshot(settings, clamped_days)
    _AGENT_USAGE_CACHE["days"] = clamped_days
    _AGENT_USAGE_CACHE["generated_at"] = now_ts
    _AGENT_USAGE_CACHE["data"] = fresh
    return fresh


def create_app() -> FastAPI:
    settings = load_settings()

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    app = FastAPI(title="Mission Control API", version="0.1.0")

    async def get_session():
        async with session_factory() as session:
            yield session

    async def publish_validation_result(
        *,
        accepted: bool,
        body: EventIn,
        errors: list[str],
        details: dict | None = None,
    ) -> None:
        await publish_event(
            redis,
            stream_key=settings.redis_stream_key,
            event={
                "id": str(uuid4()),
                "type": "event.validation",
                "agent": body.agent,
                "task_id": str(body.task_id) if body.task_id else None,
                "payload": {
                    "event_type": body.type,
                    "accepted": accepted,
                    "errors": errors,
                    "details": details or {},
                },
                "created_at": datetime.utcnow().isoformat() + "Z",
            },
        )

    @app.get("/health", response_model=Health)
    async def healthcheck() -> Health:
        return Health(ok=True)

    @app.get("/v1/observability/summary", response_model=ObservabilitySummaryOut)
    async def get_observability_summary(
        window_minutes: int = 5,
        heartbeat_stale_seconds: int = 180,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> ObservabilitySummaryOut:
        now = datetime.utcnow()
        window = max(1, min(int(window_minutes or 5), 60))
        stale = max(30, min(int(heartbeat_stale_seconds or 180), 3600))
        since = now - timedelta(minutes=window)

        status_code_expr = sa.cast(
            sa.func.nullif(sa.func.jsonb_extract_path_text(events.c.payload, "status_code"), ""),
            sa.Integer,
        )
        error_type_expr = sa.func.jsonb_extract_path_text(events.c.payload, "error_type")
        accepted_expr = sa.func.jsonb_extract_path_text(events.c.payload, "accepted")

        request_total_stmt = sa.select(sa.func.count()).where(
            events.c.created_at >= since,
            events.c.type == "chat.gateway.access",
        )
        request_total = int((await session.execute(request_total_stmt)).scalar_one() or 0)

        error_total_stmt = sa.select(sa.func.count()).where(
            events.c.created_at >= since,
            sa.or_(
                sa.and_(events.c.type == "event.validation", accepted_expr == "false"),
                events.c.type.like("%.error"),
                status_code_expr >= 400,
                sa.and_(error_type_expr.is_not(None), error_type_expr != ""),
            ),
        )
        error_total = int((await session.execute(error_total_stmt)).scalar_one() or 0)

        events_total_stmt = sa.select(sa.func.count()).where(events.c.created_at >= since)
        events_total = int((await session.execute(events_total_stmt)).scalar_one() or 0)

        tasks_done_stmt = sa.select(sa.func.count()).where(
            tasks.c.updated_at >= since,
            tasks.c.status == "DONE",
        )
        tasks_done_total = int((await session.execute(tasks_done_stmt)).scalar_one() or 0)

        task_backlog_stmt = sa.select(sa.func.count()).where(tasks.c.status != "DONE")
        task_backlog_total = int((await session.execute(task_backlog_stmt)).scalar_one() or 0)

        try:
            event_backlog_total = int(await redis.xlen(settings.redis_stream_key))
        except Exception:
            event_backlog_total = 0

        known_agents = sorted(_known_agent_slugs(settings))
        total_agents = len(known_agents)
        healthy_agents = 0

        if known_agents:
            heartbeats_stmt = (
                sa.select(events.c.agent, sa.func.max(events.c.created_at).label("last_seen"))
                .where(
                    events.c.type == "agent.heartbeat",
                    events.c.agent.is_not(None),
                    events.c.agent.in_(known_agents),
                )
                .group_by(events.c.agent)
            )
            rows = (await session.execute(heartbeats_stmt)).all()
            cutoff = now - timedelta(seconds=stale)
            for row in rows:
                last_seen = row.last_seen
                if isinstance(last_seen, datetime) and last_seen >= cutoff:
                    healthy_agents += 1

        denominator = request_total if request_total > 0 else max(events_total, 1)
        error_rate = float(error_total) / float(denominator)

        return ObservabilitySummaryOut(
            generated_at=now,
            window_minutes=window,
            request_total=request_total,
            error_total=error_total,
            error_rate=error_rate,
            event_throughput_per_min=float(events_total) / float(window),
            task_throughput_per_min=float(tasks_done_total) / float(window),
            event_backlog_total=event_backlog_total,
            task_backlog_total=task_backlog_total,
            healthy_agents=healthy_agents,
            total_agents=total_agents,
            agent_health_ratio=(float(healthy_agents) / float(total_agents)) if total_agents > 0 else 0.0,
            heartbeat_stale_seconds=stale,
        )

    @app.get("/v1/observability/container-health", response_model=ContainerHealthSummaryOut)
    async def get_container_health_summary(
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> ContainerHealthSummaryOut:
        now = datetime.utcnow()
        signals: list[HealthSignalOut] = []

        redis_host, redis_port = _host_port_from_url(settings.redis_url, 6379)
        db_host, db_port = _host_port_from_url(settings.database_url, 5432)

        compose_ok = 0
        compose_total = 0

        compose_total += 1
        redis_started = time.perf_counter()
        try:
            redis_ok = bool(await redis.ping())
            redis_latency = int((time.perf_counter() - redis_started) * 1000)
            if redis_ok:
                compose_ok += 1
            signals.append(
                HealthSignalOut(
                    name="redis.ping",
                    source="compose",
                    target=f"{redis_host or 'redis'}:{redis_port}",
                    ok=redis_ok,
                    latency_ms=redis_latency,
                    detail="PONG" if redis_ok else "No PONG",
                )
            )
        except Exception as exc:
            signals.append(
                HealthSignalOut(
                    name="redis.ping",
                    source="compose",
                    target=f"{redis_host or 'redis'}:{redis_port}",
                    ok=False,
                    detail=f"{exc.__class__.__name__}: {exc}",
                )
            )

        compose_total += 1
        db_started = time.perf_counter()
        try:
            db_ok = bool((await session.execute(sa.select(sa.literal(1)))).scalar_one() == 1)
            db_latency = int((time.perf_counter() - db_started) * 1000)
            if db_ok:
                compose_ok += 1
            signals.append(
                HealthSignalOut(
                    name="postgres.select_1",
                    source="compose",
                    target=f"{db_host or 'postgres'}:{db_port}",
                    ok=db_ok,
                    latency_ms=db_latency,
                    detail="SELECT 1",
                )
            )
        except Exception as exc:
            signals.append(
                HealthSignalOut(
                    name="postgres.select_1",
                    source="compose",
                    target=f"{db_host or 'postgres'}:{db_port}",
                    ok=False,
                    detail=f"{exc.__class__.__name__}: {exc}",
                )
            )

        port_targets: list[tuple[str, str, int]] = [
            ("mission-control-api", "mission-control-api", 9090),
            ("mission-control-ui", "mission-control-ui", 9090),
            ("mission-control-gateway", "mission-control-gateway", 80),
        ]
        for slug in sorted(_known_agent_slugs(settings)):
            port_targets.append((f"openclaw-{slug}", f"openclaw-{slug}", settings.chat_upstream_port))

        port_ok = 0
        port_total = len(port_targets)
        for name, host, port in port_targets:
            ok, latency_ms, detail = await _probe_tcp(host, port)
            if ok:
                port_ok += 1
            signals.append(
                HealthSignalOut(
                    name=name,
                    source="port",
                    target=f"{host}:{port}",
                    ok=ok,
                    latency_ms=latency_ms,
                    detail=detail,
                )
            )

        http_targets: list[tuple[str, str]] = [
            ("mission-control-api.health", "http://mission-control-api:9090/health"),
            ("mission-control-gateway.root", "http://mission-control-gateway/"),
            ("mission-control-ui.root", "http://mission-control-ui:9090/"),
        ]

        http_ok = 0
        http_total = len(http_targets)
        for name, url in http_targets:
            ok, latency_ms, detail = await _probe_http(url)
            if ok:
                http_ok += 1
            signals.append(
                HealthSignalOut(
                    name=name,
                    source="http",
                    target=url,
                    ok=ok,
                    latency_ms=latency_ms,
                    detail=detail,
                )
            )

        overall_ok = compose_ok + port_ok + http_ok
        overall_total = compose_total + port_total + http_total

        return ContainerHealthSummaryOut(
            generated_at=now,
            compose_ok=compose_ok,
            compose_total=compose_total,
            port_ok=port_ok,
            port_total=port_total,
            http_ok=http_ok,
            http_total=http_total,
            overall_ok=overall_ok,
            overall_total=overall_total,
            overall_ratio=(float(overall_ok) / float(overall_total)) if overall_total > 0 else 0.0,
            signals=signals,
        )

    @app.get("/v1/skills/global", response_model=list[SkillItem])
    async def get_global_skills(
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
    ) -> list[SkillItem]:
        return _scan_global_skills(settings)

    @app.get("/v1/skills/workspace", response_model=list[WorkspaceSkillGroup])
    async def get_workspace_skills(
        agent_slug: str | None = None,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
    ) -> list[WorkspaceSkillGroup]:
        return _scan_workspace_skills(settings, agent_slug=agent_slug)

    @app.get("/v1/usage/agents", response_model=list[AgentUsageSnapshotOut])
    async def get_agent_usage_snapshot(
        days: int = 7,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
    ) -> list[AgentUsageSnapshotOut]:
        return _get_agent_usage_snapshot(settings, days)

    @app.post("/v1/agents/{agent}/control", response_model=AgentControlActionOut)
    async def control_agent_container(
        agent: str,
        body: AgentControlActionIn,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
    ) -> AgentControlActionOut:
        slug = str(agent or "").strip()
        if not slug:
            raise HTTPException(status_code=400, detail="agent is required")

        known_agents = _known_agent_slugs(settings)
        if known_agents and slug not in known_agents:
            raise HTTPException(status_code=404, detail=f"unknown agent: {slug}")

        action = str(body.action or "").strip().lower()
        if action not in ALLOWED_AGENT_CONTROL_ACTIONS:
            raise HTTPException(status_code=400, detail=f"invalid action: {action}")

        return await _forward_agent_control(settings, agent=slug, action=action)

    @app.get("/v1/skills/mappings", response_model=list[AgentSkillMappingOut])
    async def get_skill_mappings(
        agent_slug: str | None = None,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> list[AgentSkillMappingOut]:
        stmt = sa.select(
            agent_skill_mappings.c.id,
            agent_skill_mappings.c.agent_slug,
            agent_skill_mappings.c.skill_slug,
            agent_skill_mappings.c.created_at,
        ).order_by(agent_skill_mappings.c.agent_slug.asc(), agent_skill_mappings.c.skill_slug.asc())
        if agent_slug:
            stmt = stmt.where(agent_skill_mappings.c.agent_slug == agent_slug)
        rows = (await session.execute(stmt)).all()
        return [AgentSkillMappingOut(**row._asdict()) for row in rows]

    @app.patch("/v1/skills/mappings", response_model=SkillsMappingPatchOut)
    async def patch_skill_mappings(
        body: SkillsMappingPatchIn,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> SkillsMappingPatchOut:
        agent_slugs = sorted({slug.strip() for slug in body.agent_slugs if slug and slug.strip()})
        add_skill_slugs = sorted({slug.strip() for slug in body.add_skill_slugs if slug and slug.strip()})
        remove_skill_slugs = sorted({slug.strip() for slug in body.remove_skill_slugs if slug and slug.strip()})

        if not agent_slugs:
            raise HTTPException(status_code=400, detail="agent_slugs is required")
        if not add_skill_slugs and not remove_skill_slugs:
            raise HTTPException(status_code=400, detail="nothing to update")

        failed: list[SkillsMappingFailureItem] = []
        known_agents = set(_scan_agent_slugs(settings))
        valid_agents = agent_slugs
        if known_agents:
            unknown_agents = [slug for slug in agent_slugs if slug not in known_agents]
            valid_agents = [slug for slug in agent_slugs if slug in known_agents]
            for agent in unknown_agents:
                for skill in add_skill_slugs:
                    failed.append(
                        SkillsMappingFailureItem(
                            action="add",
                            agent_slug=agent,
                            skill_slug=skill,
                            reason="unknown_agent",
                        )
                    )
                for skill in remove_skill_slugs:
                    failed.append(
                        SkillsMappingFailureItem(
                            action="remove",
                            agent_slug=agent,
                            skill_slug=skill,
                            reason="unknown_agent",
                        )
                    )

        known_global = {item.slug for item in _scan_global_skills(settings)}
        unknown_add = [slug for slug in add_skill_slugs if slug not in known_global]
        unknown_remove = [slug for slug in remove_skill_slugs if slug not in known_global]
        valid_add_skill_slugs = [slug for slug in add_skill_slugs if slug in known_global]
        valid_remove_skill_slugs = [slug for slug in remove_skill_slugs if slug in known_global]

        for skill in unknown_add:
            for agent in valid_agents:
                failed.append(
                    SkillsMappingFailureItem(
                        action="add",
                        agent_slug=agent,
                        skill_slug=skill,
                        reason="unknown_global_skill",
                    )
                )
        for skill in unknown_remove:
            for agent in valid_agents:
                failed.append(
                    SkillsMappingFailureItem(
                        action="remove",
                        agent_slug=agent,
                        skill_slug=skill,
                        reason="unknown_global_skill",
                    )
                )

        if not valid_agents:
            return SkillsMappingPatchOut(
                updated=0,
                affected_agents=[],
                restart_hint="No valid mappings were updated.",
                failed=failed,
            )

        updated = 0
        if valid_add_skill_slugs:
            target_pairs = {(agent, skill) for agent in valid_agents for skill in valid_add_skill_slugs}
            existing_stmt = sa.select(
                agent_skill_mappings.c.agent_slug,
                agent_skill_mappings.c.skill_slug,
            ).where(
                agent_skill_mappings.c.agent_slug.in_(valid_agents),
                agent_skill_mappings.c.skill_slug.in_(valid_add_skill_slugs),
            )
            existing_rows = (await session.execute(existing_stmt)).all()
            existing_pairs = {(str(row.agent_slug), str(row.skill_slug)) for row in existing_rows}

            for agent, skill in sorted(existing_pairs):
                failed.append(
                    SkillsMappingFailureItem(
                        action="add",
                        agent_slug=agent,
                        skill_slug=skill,
                        reason="already_mapped",
                    )
                )

            rows = [
                {"id": uuid4(), "agent_slug": agent, "skill_slug": skill}
                for (agent, skill) in sorted(target_pairs - existing_pairs)
            ]
            if rows:
                insert_stmt = pg_insert(agent_skill_mappings).values(rows)
                insert_stmt = insert_stmt.on_conflict_do_nothing(
                    constraint="uq_agent_skill_mappings_agent_skill"
                )
                insert_stmt = insert_stmt.returning(agent_skill_mappings.c.id)
                result = await session.execute(insert_stmt)
                updated += len(result.scalars().all())

        if valid_remove_skill_slugs:
            target_pairs = {(agent, skill) for agent in valid_agents for skill in valid_remove_skill_slugs}
            existing_stmt = sa.select(
                agent_skill_mappings.c.id,
                agent_skill_mappings.c.agent_slug,
                agent_skill_mappings.c.skill_slug,
            ).where(
                agent_skill_mappings.c.agent_slug.in_(valid_agents),
                agent_skill_mappings.c.skill_slug.in_(valid_remove_skill_slugs),
            )
            existing_rows = (await session.execute(existing_stmt)).all()
            existing_pairs = {(str(row.agent_slug), str(row.skill_slug)) for row in existing_rows}

            missing_pairs = sorted(target_pairs - existing_pairs)
            for agent, skill in missing_pairs:
                failed.append(
                    SkillsMappingFailureItem(
                        action="remove",
                        agent_slug=agent,
                        skill_slug=skill,
                        reason="not_mapped",
                    )
                )

            if existing_rows:
                existing_ids = [row.id for row in existing_rows]
                delete_stmt = agent_skill_mappings.delete().where(agent_skill_mappings.c.id.in_(existing_ids))
                result = await session.execute(delete_stmt)
                updated += int(result.rowcount or 0)

        await session.commit()

        return SkillsMappingPatchOut(
            updated=updated,
            affected_agents=valid_agents,
            restart_hint=(
                "Configuration saved. Restart affected agent containers to apply changes."
                if updated > 0
                else "No mapping changes were applied."
            ),
            failed=failed,
        )

    @app.post("/v1/tasks", response_model=TaskOut)
    async def create_task(
        body: TaskCreate,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> TaskOut:
        if body.status not in ALLOWED_TASK_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"invalid task status: {body.status}; allowed={sorted(ALLOWED_TASK_STATUSES)}",
            )

        task_id = uuid4()
        now = datetime.utcnow()
        stmt = (
            tasks.insert()
            .values(
                id=task_id,
                title=body.title,
                status=body.status,
                assignee=body.assignee,
                tags=body.tags,
                created_at=now,
                updated_at=now,
            )
            .returning(
                tasks.c.id,
                tasks.c.title,
                tasks.c.status,
                tasks.c.assignee,
                tasks.c.tags,
                tasks.c.created_at,
                tasks.c.updated_at,
            )
        )
        row = (await session.execute(stmt)).one()
        await session.commit()
        return TaskOut(**row._asdict())

    @app.get("/v1/boards/default", response_model=BoardOut)
    async def get_board(
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> BoardOut:
        statuses = ["INBOX", "ASSIGNED", "IN PROGRESS", "REVIEW", "DONE"]
        columns: list[BoardColumn] = []
        for status in statuses:
            stmt = (
                sa.select(
                    tasks.c.id,
                    tasks.c.title,
                    tasks.c.status,
                    tasks.c.assignee,
                    tasks.c.tags,
                    tasks.c.created_at,
                    tasks.c.updated_at,
                )
                .where(tasks.c.status == status)
                .order_by(tasks.c.updated_at.desc())
                .limit(100)
            )
            rows = (await session.execute(stmt)).all()
            cards = [TaskOut(**r._asdict()) for r in rows]
            columns.append(BoardColumn(title=status, count=len(cards), cards=cards))
        return BoardOut(columns=columns)

    @app.post("/v1/tasks/{task_id}/comments", response_model=CommentOut)
    async def add_comment(
        task_id: UUID,
        body: CommentCreate,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> CommentOut:
        comment_id = uuid4()
        stmt = (
            comments.insert()
            .values(id=comment_id, task_id=task_id, author=body.author, body=body.body)
            .returning(
                comments.c.id,
                comments.c.task_id,
                comments.c.author,
                comments.c.body,
                comments.c.created_at,
            )
        )
        row = (await session.execute(stmt)).one()
        await session.commit()

        await publish_event(
            redis,
            stream_key=settings.redis_stream_key,
            event={
                "id": str(uuid4()),
                "type": "comment.created",
                "agent": body.author,
                "task_id": str(task_id),
                "payload": {"comment_id": str(row.id)},
                "created_at": datetime.utcnow().isoformat() + "Z",
            },
        )

        return CommentOut(**row._asdict())

    @app.post("/v1/events", response_model=EventOut)
    async def ingest_event(
        body: EventIn,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> EventOut:
        validation_errors: list[str] = []
        validation_details: dict = {}

        if body.type == "task.handoff":
            if not body.task_id:
                validation_errors.append("task.handoff requires task_id")
            known_agents = _known_agent_slugs(settings)
            validation_errors.extend(_validate_handoff_payload(body.payload, known_agents))
            validation_details["known_agents_count"] = len(known_agents)

        event_payload = dict(body.payload)
        if body.type == "task.status":
            if not body.task_id:
                validation_errors.append("task.status requires task_id")
            next_status = str(body.payload.get("new_status") or "").strip().upper()
            if not next_status:
                validation_errors.append("payload.new_status is required")
            elif next_status not in ALLOWED_TASK_STATUSES:
                validation_errors.append(
                    f"payload.new_status invalid: {next_status}; allowed={sorted(ALLOWED_TASK_STATUSES)}"
                )

            current_status = None
            if body.task_id:
                current_row = (
                    await session.execute(
                        sa.select(tasks.c.id, tasks.c.status).where(tasks.c.id == body.task_id)
                    )
                ).first()
                if not current_row:
                    validation_errors.append(f"task not found: {body.task_id}")
                else:
                    current_status = str(current_row.status)

            if not validation_errors and current_status is not None:
                allowed = TASK_STATUS_TRANSITIONS.get(current_status, set())
                if next_status != current_status and next_status not in allowed:
                    validation_errors.append(
                        f"invalid status transition: {current_status} -> {next_status}; allowed={sorted(allowed)}"
                    )

            if not validation_errors and current_status is not None:
                now = datetime.utcnow()
                await session.execute(
                    tasks.update()
                    .where(tasks.c.id == body.task_id)
                    .values(status=next_status, updated_at=now)
                )
                event_payload["previous_status"] = current_status
                event_payload["new_status"] = next_status
                event_payload["transition_applied"] = True
                validation_details["transition"] = {
                    "from": current_status,
                    "to": next_status,
                }

        if validation_errors:
            await publish_validation_result(
                accepted=False,
                body=body,
                errors=validation_errors,
                details=validation_details,
            )
            raise HTTPException(status_code=422, detail={"errors": validation_errors})

        event_id = uuid4()
        stmt = (
            events.insert()
            .values(id=event_id, type=body.type, agent=body.agent, task_id=body.task_id, payload=event_payload)
            .returning(
                events.c.id,
                events.c.type,
                events.c.agent,
                events.c.task_id,
                events.c.payload,
                events.c.created_at,
            )
        )
        row = (await session.execute(stmt)).one()
        await session.commit()

        await publish_event(
            redis,
            stream_key=settings.redis_stream_key,
            event={
                "id": str(row.id),
                "type": row.type,
                "agent": row.agent,
                "task_id": str(row.task_id) if row.task_id else None,
                "payload": row.payload,
                "created_at": row.created_at.isoformat(),
            },
        )

        await publish_validation_result(
            accepted=True,
            body=body,
            errors=[],
            details=validation_details,
        )

        return EventOut(**row._asdict())

    @app.get("/v1/feed", response_model=list[EventOut])
    async def get_feed(
        limit: int = 50,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> list[EventOut]:
        stmt = (
            sa.select(
                events.c.id,
                events.c.type,
                events.c.agent,
                events.c.task_id,
                events.c.payload,
                events.c.created_at,
            )
            .order_by(events.c.created_at.desc())
            .limit(min(limit, 200))
        )
        rows = (await session.execute(stmt)).all()
        return [EventOut(**r._asdict()) for r in rows]

    @app.get("/v1/feed-lite", response_model=list[EventLiteOut])
    async def get_feed_lite(
        limit: int = 50,
        _auth: None = Depends(lambda authorization=Header(default=None): require_auth(settings, authorization)),
        session=Depends(get_session),
    ) -> list[EventLiteOut]:
        stmt = (
            sa.select(
                events.c.id,
                events.c.type,
                events.c.agent,
                events.c.task_id,
                events.c.created_at,
                sa.func.jsonb_extract_path_text(events.c.payload, "method").label("method"),
                sa.func.jsonb_extract_path_text(events.c.payload, "path").label("path"),
                sa.cast(sa.func.nullif(sa.func.jsonb_extract_path_text(events.c.payload, "status_code"), ""), sa.Integer).label("status_code"),
                sa.func.jsonb_extract_path_text(events.c.payload, "error_type").label("error_type"),
                sa.func.jsonb_extract_path_text(events.c.payload, "test_id").label("test_id"),
                sa.cast(sa.func.nullif(sa.func.jsonb_extract_path_text(events.c.payload, "round"), ""), sa.Integer).label("round"),
            )
            .order_by(events.c.created_at.desc())
            .limit(min(limit, 500))
        )
        rows = (await session.execute(stmt)).all()
        return [EventLiteOut(**r._asdict()) for r in rows]

    @app.websocket("/ws/events")
    async def ws_events(websocket: WebSocket):
        await websocket.accept()

        # 可選 Bearer token（如果設定了 MC_AUTH_TOKEN）
        if settings.auth_token:
            auth = websocket.headers.get("authorization")
            if not auth or not auth.lower().startswith("bearer "):
                await websocket.close(code=4401)
                return
            token = auth.split(" ", 1)[1].strip()
            if token != settings.auth_token:
                await websocket.close(code=4403)
                return

        # Start from the latest stream ID to avoid replaying long history on each
        # new websocket connection, which can significantly increase perceived
        # real-time latency on the dashboard.
        last_id = "$"
        try:
            latest = await redis.xrevrange(settings.redis_stream_key, count=1)
            if latest:
                last_id = str(latest[0][0])
        except Exception:
            # Fall back to '$' (new entries only).
            last_id = "$"
        try:
            while True:
                result = await redis.xread({settings.redis_stream_key: last_id}, block=25_000, count=50)
                if not result:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                    continue

                _, entries = result[0]
                for entry_id, fields in entries:
                    last_id = entry_id
                    # fields["event"] 會是一個 JSON 字串
                    event_json = fields.get("event")
                    if event_json:
                        await websocket.send_text(event_json)
        except WebSocketDisconnect:
            return

    
    @app.api_route("/chat/{agent}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
    async def chat_proxy(agent: str, path: str, request: Request):
        started = time.perf_counter()
        upgrade = request.headers.get("upgrade", "").lower() == "websocket"
            
        target_url = f"http://openclaw-{agent}:{settings.chat_upstream_port}/{path}"
        query = request.url.query
        if query:
            target_url += f"?{query}"
            
        async with httpx.AsyncClient(timeout=3600.0) as client:
            headers = dict(request.headers.items())
            headers.pop("host", None)
            if settings.chat_force_loopback_headers:
                headers["x-real-ip"] = "127.0.0.1"
                headers["x-forwarded-for"] = "127.0.0.1"
            
            token = settings.agent_token_map.get(agent)
            if token:
                headers["authorization"] = f"Bearer {token}"
                
            req = client.build_request(
                request.method,
                target_url,
                headers=headers,
                content=request.stream(),
            )
            
            try:
                resp = await client.send(req, stream=True)
            except Exception as e:
                if not upgrade:
                    elapsed = max(0.0, time.perf_counter() - started)
                    await publish_event(
                        redis,
                        stream_key=settings.redis_stream_key,
                        event={
                            "type": "chat.gateway.access",
                            "agent": agent,
                            "payload": {
                                "path": f"/{path}",
                                "query": str(request.url.query)[:256],
                                "method": request.method,
                                "status_code": 502,
                                "request_time": f"{elapsed:.4f}",
                                "upstream_status": "error",
                                "error_type": e.__class__.__name__,
                                "is_ws_upgrade": False,
                                "source": "api_gateway_proxy",
                                "ts": datetime.utcnow().isoformat() + "Z",
                            },
                        },
                    )
                raise HTTPException(status_code=502, detail=f"Proxy error: {e}")
            
            is_html = "text/html" in resp.headers.get("content-type", "")
            if is_html:
                content = await resp.aread()
                text = content.decode("utf-8", errors="replace")
                
                if settings.chat_inject_script_enabled:
                    inject_script = _build_chat_inject_script(
                        agent,
                        token,
                        clear_device_auth_storage=settings.chat_clear_device_auth_storage,
                        inject_gateway_settings=settings.chat_inject_gateway_settings,
                        dom_avatar_rewrite=settings.chat_dom_avatar_rewrite,
                    )

                    if 'window.__OPENCLAW_CONTROL_UI_BASE_PATH__="";' in text:
                        text = text.replace('window.__OPENCLAW_CONTROL_UI_BASE_PATH__="";', inject_script)
                    else:
                        injected = f"<script>{inject_script}</script>"
                        if '<script type="module"' in text:
                            text = text.replace('<script type="module"', f"{injected}<script type=\"module\"", 1)
                        elif "</head>" in text:
                            text = text.replace("</head>", f"{injected}</head>", 1)
                        elif "<body>" in text:
                            text = text.replace("<body>", f"<body>{injected}", 1)
                        else:
                            text = f"{injected}{text}"
                    if settings.chat_dom_avatar_rewrite:
                        text = re.sub(
                            r'window\.__OPENCLAW_ASSISTANT_AVATAR__=("|\')/avatar/[^"\']*("|\')',
                            'window.__OPENCLAW_ASSISTANT_AVATAR__=""',
                            text,
                        )
                await resp.aclose()
                
                return HTMLResponse(content=text, status_code=resp.status_code)

            content = await resp.aread()
            await resp.aclose()

            if (
                settings.chat_rewrite_control_ui_config
                and request.method.upper() == "GET"
                and path.endswith("control-ui-config.json")
                and resp.status_code == 200
            ):
                content = _rewrite_control_ui_config(content, agent, rewrite_avatar=settings.chat_rewrite_avatar_payloads)

            if request.method.upper() == "GET" and path.startswith("avatar/"):
                is_meta = request.query_params.get("meta") == "1"

                if is_meta and resp.status_code == 200 and "application/json" in resp.headers.get("content-type", ""):
                    if settings.chat_rewrite_avatar_payloads:
                        content = _rewrite_avatar_meta(content, agent, query)

                if not is_meta and resp.status_code == 404:
                    svg = _avatar_fallback_svg(agent)
                    return Response(content=svg, status_code=200, media_type="image/svg+xml")

            r = Response(content=content, status_code=resp.status_code)
            for k, v in resp.headers.items():
                if k.lower() not in ("content-length", "transfer-encoding", "connection"):
                    r.headers[k] = v

            if not upgrade:
                elapsed = max(0.0, time.perf_counter() - started)
                error_type = None
                if resp.status_code >= 400:
                    error_type = f"http_{resp.status_code}"
                await publish_event(
                    redis,
                    stream_key=settings.redis_stream_key,
                    event={
                        "type": "chat.gateway.access",
                        "agent": agent,
                        "payload": {
                            "path": f"/{path}",
                            "query": str(request.url.query)[:256],
                            "method": request.method,
                            "status_code": int(resp.status_code),
                            "request_time": f"{elapsed:.4f}",
                            "upstream_status": "ok" if resp.status_code < 500 else "error",
                            "error_type": error_type,
                            "is_ws_upgrade": False,
                            "source": "api_gateway_proxy",
                            "ts": datetime.utcnow().isoformat() + "Z",
                        },
                    },
                )
            return r

    async def _chat_ws_proxy_impl(agent: str, path: str, websocket: WebSocket):
        await websocket.accept()
        
        payload = {
            "path": f"/{path}",
            "query": "",
            "method": "GET",
            "status_code": 101,
            "request_time": "0.0",
            "upstream_status": "proxy",
            "is_ws_upgrade": True,
            "source": "api_gateway_proxy",
            "ts": datetime.utcnow().isoformat() + "Z",
        }
        await publish_event(
            redis,
            stream_key=settings.redis_stream_key,
            event={
                "type": "chat.gateway.access",
                "agent": agent,
                "payload": payload,
            },
        )
            
        target_ws_url = f"ws://openclaw-{agent}:{settings.chat_upstream_port}/{path}"
        ws_query = websocket.scope.get("query_string", b"")
        if isinstance(ws_query, (bytes, bytearray)) and ws_query:
            target_ws_url = f"{target_ws_url}?{ws_query.decode('utf-8', errors='ignore')}"
        import websockets
        from websockets.exceptions import ConnectionClosed
        
        token = settings.agent_token_map.get(agent)
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if settings.chat_force_loopback_headers:
            headers["X-Real-IP"] = "127.0.0.1"
            headers["X-Forwarded-For"] = "127.0.0.1"
        upstream_origin = _normalize_control_ui_origin(websocket.headers.get("origin"))
            
        try:
            async with websockets.connect(
                target_ws_url,
                extra_headers=headers or None,
                origin=upstream_origin or None,
            ) as upstream_ws:
                async def forward_to_upstream():
                    try:
                        while True:
                            msg = await websocket.receive_text()
                            if settings.chat_sanitize_connect_auth:
                                msg = _sanitize_connect_auth(
                                    msg,
                                    token,
                                    strip_stale_device_fields=settings.chat_strip_stale_device_fields,
                                    force_token_in_connect=settings.chat_force_token_in_connect,
                                )
                            await upstream_ws.send(msg)
                    except WebSocketDisconnect:
                        pass
                    except Exception:
                        pass
                        
                async def forward_to_client():
                    try:
                        while True:
                            msg = await upstream_ws.recv()
                            if settings.chat_rewrite_avatar_payloads and isinstance(msg, str) and "/avatar/" in msg:
                                try:
                                    payload = json.loads(msg)
                                    rewritten = _rewrite_avatar_paths(payload, agent)
                                    msg = json.dumps(rewritten, ensure_ascii=False)
                                except Exception:
                                    pass
                            await websocket.send_text(msg)
                    except ConnectionClosed:
                        pass
                    except Exception:
                        pass
                        
                await asyncio.gather(
                    forward_to_upstream(),
                    forward_to_client()
                )
        except Exception as e:
            await websocket.close(code=1011, reason=str(e))

    @app.websocket("/chat/{agent}")
    async def chat_ws_proxy_root(agent: str, websocket: WebSocket):
        await _chat_ws_proxy_impl(agent, "", websocket)

    @app.websocket("/chat/{agent}/{path:path}")
    async def chat_ws_proxy(agent: str, path: str, websocket: WebSocket):
        await _chat_ws_proxy_impl(agent, path, websocket)

    @app.on_event("shutdown")
    async def _shutdown():
        await redis.aclose()
        await engine.dispose()

    return app


async def publish_event(redis: Redis, stream_key: str, event: dict) -> None:
    await redis.xadd(stream_key, {"event": json.dumps(event, ensure_ascii=False)})


app = create_app()
