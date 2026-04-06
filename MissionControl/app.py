import os
import re
import threading
import time
from urllib.parse import parse_qs, urlencode
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
import websocket
from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update
from flask import Response

APP_TITLE = "Mission Control"

MISSION_CONTROL_API_URL = os.getenv("MISSION_CONTROL_API_URL") or "http://localhost:18910"
MISSION_CONTROL_DOCS_URL = os.getenv("MISSION_CONTROL_DOCS_URL") or (
    "https://github.com/Ieer/OpenClaw-PWTInstaller/blob/main/panopticon/README.md"
)
MISSION_CONTROL_AUTH_TOKEN = (
    os.getenv("MISSION_CONTROL_AUTH_TOKEN")
    or os.getenv("MC_AUTH_TOKEN")
    or os.getenv("MISSION_CONTROL_TOKEN")
    or ""
).strip()
MISSION_CONTROL_CHAT_HOST = (os.getenv("MISSION_CONTROL_CHAT_HOST") or "127.0.0.1").strip() or "127.0.0.1"
MISSION_CONTROL_ENABLE_LEGACY_CHAT_PROXY = (
    (os.getenv("MISSION_CONTROL_ENABLE_LEGACY_CHAT_PROXY") or "0").strip().lower() in {"1", "true", "yes", "on"}
)
MISSION_CONTROL_CHAT_EVENT_BRIDGE_ENABLED = (
    (os.getenv("MISSION_CONTROL_CHAT_EVENT_BRIDGE_ENABLED") or "1").strip().lower() in {"1", "true", "yes", "on"}
)
MISSION_CONTROL_VOICE_OVERLAY_ENABLED = (
    (os.getenv("MISSION_CONTROL_VOICE_OVERLAY_ENABLED") or "1").strip().lower() in {"1", "true", "yes", "on"}
)

try:
    MISSION_CONTROL_WS_TICK_MS = max(80, int((os.getenv("MISSION_CONTROL_WS_TICK_MS") or "150").strip()))
except ValueError:
    MISSION_CONTROL_WS_TICK_MS = 150


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except ValueError:
        return float(default)


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except ValueError:
        return int(default)


OBS_ERROR_RATE_WARN_PCT = _env_float("MISSION_CONTROL_OBS_ERROR_RATE_WARN_PCT", 2.0)
OBS_ERROR_RATE_CRIT_PCT = _env_float("MISSION_CONTROL_OBS_ERROR_RATE_CRIT_PCT", 5.0)
OBS_EVENT_BACKLOG_WARN = _env_int("MISSION_CONTROL_OBS_EVENT_BACKLOG_WARN", 200)
OBS_EVENT_BACKLOG_CRIT = _env_int("MISSION_CONTROL_OBS_EVENT_BACKLOG_CRIT", 1000)
OBS_TASK_THROUGHPUT_WARN_PER_MIN = _env_float("MISSION_CONTROL_OBS_TASK_THROUGHPUT_WARN_PER_MIN", 0.5)
OBS_TASK_THROUGHPUT_CRIT_PER_MIN = _env_float("MISSION_CONTROL_OBS_TASK_THROUGHPUT_CRIT_PER_MIN", 0.1)
OBS_HEALTH_RATIO_WARN = _env_float("MISSION_CONTROL_OBS_HEALTH_RATIO_WARN", 0.8)
OBS_HEALTH_RATIO_CRIT = _env_float("MISSION_CONTROL_OBS_HEALTH_RATIO_CRIT", 0.6)


def _normalize_text(text: str | None) -> str:
    return str(text or "").strip().lower()


def _format_mapping_failure_summary(failed: list[dict], *, limit: int = 8) -> str:
    if not failed:
        return ""

    reason_map = {
        "unknown_agent": "unknown agent",
        "unknown_global_skill": "unknown global skill",
        "already_mapped": "already mapped",
        "not_mapped": "not mapped",
    }

    lines: list[str] = []
    for item in failed[:limit]:
        action = str(item.get("action") or "update")
        agent = str(item.get("agent_slug") or "-")
        skill = str(item.get("skill_slug") or "-")
        reason = reason_map.get(str(item.get("reason") or ""), str(item.get("reason") or "unknown error"))
        lines.append(f"{action} {agent}/{skill} ({reason})")

    hidden = len(failed) - len(lines)
    suffix = f"; +{hidden} more" if hidden > 0 else ""
    return "Failed items: " + "; ".join(lines) + suffix


def _parse_text_list(value: str | None) -> list[str]:
    raw = str(value or "").strip()

    parts = re.split(r"[\n,]", raw)
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        item = str(part or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _scope_badge_tone(scope: str) -> str:
    normalized = _normalize_text(scope)
    if normalized == "global":
        return "scope-global"
    if normalized == "workspace":
        return "scope-workspace"
    if normalized == "runtime":
        return "scope-runtime"
    return "scope-neutral"


def _render_metric_cards(metrics: list[dict]):
    if not metrics:
        return [html.Div("No skills metrics available.", className="column-empty")]

    cards = []
    for item in metrics:
        tone = _normalize_text(item.get("tone")) or "neutral"
        cards.append(
            html.Div(
                className=f"skills-metric-card tone-{tone}",
                children=[
                    html.Div(str(item.get("label") or "Metric"), className="skills-metric-label"),
                    html.Div(str(item.get("value") or "-"), className="skills-metric-value"),
                    html.Div(str(item.get("detail") or ""), className="skills-metric-detail"),
                ],
            )
        )
    return cards


def _render_inventory_children(items: list[dict], *, limit: int = 24):
    if not items:
        return [html.Div("No inventory items discovered.", className="column-empty")]

    scope_order = {"global": 0, "workspace": 1, "runtime": 2}
    ordered = sorted(
        items,
        key=lambda item: (
            scope_order.get(_normalize_text(item.get("scope")), 99),
            str(item.get("agent_slug") or ""),
            str(item.get("slug") or ""),
        ),
    )

    children = []
    for item in ordered[:limit]:
        mapped_agents = item.get("mapped_agents") or []
        runtime_agents = item.get("runtime_agents") or []
        badges = [
            html.Span(str(item.get("scope") or "unknown").title(), className=f"skills-scope-badge {_scope_badge_tone(str(item.get('scope') or ''))}")
        ]
        if item.get("agent_slug"):
            badges.append(html.Span(str(item.get("agent_slug")), className="skills-meta-chip"))
        if mapped_agents:
            badges.append(html.Span(f"Mapped {len(mapped_agents)}", className="skills-meta-chip"))
        if runtime_agents:
            badges.append(html.Span(f"Runtime {len(runtime_agents)}", className="skills-meta-chip"))

        meta_lines = []
        if item.get("description"):
            meta_lines.append(html.Div(str(item.get("description")), className="skills-item-copy"))
        meta_lines.append(html.Div(str(item.get("path") or ""), className="skills-item-path"))

        children.append(
            html.Div(
                className="skills-item",
                children=[
                    html.Div(
                        className="skills-item-head",
                        children=[
                            html.Div(str(item.get("slug") or "-"), className="skills-item-title"),
                            html.Div(badges, className="skills-item-badges"),
                        ],
                    ),
                    html.Div(meta_lines, className="skills-item-body skills-item-body-stack"),
                ],
            )
        )

    hidden = len(ordered) - len(children)
    if hidden > 0:
        children.append(html.Div(f"Showing first {len(children)} items; {hidden} more hidden.", className="skills-hint"))
    return children


def _render_drift_children(items: list[dict], *, empty_text: str):
    if not items:
        return [html.Div(empty_text, className="column-empty")]

    children = []
    for item in items:
        severity = _normalize_text(item.get("severity")) or "neutral"
        meta_bits = [str(item.get("category") or "issue")]
        if item.get("skill_slug"):
            meta_bits.append(str(item.get("skill_slug")))
        if item.get("path"):
            meta_bits.append(str(item.get("path")))
        children.append(
            html.Div(
                className=f"skills-drift-item severity-{severity}",
                children=[
                    html.Div(str(item.get("message") or "Issue detected."), className="skills-drift-message"),
                    html.Div(" · ".join(meta_bits), className="skills-drift-meta"),
                ],
            )
        )
    return children


def _render_skill_group(items: list[dict], *, empty_text: str):
    if not items:
        return html.Div(empty_text, className="column-empty")

    return html.Div(
        [html.Span(str(item.get("slug") or "-"), className="tag") for item in items],
        className="skills-item-body",
    )


def _slug_label(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title() or slug


def _is_placeholder_token(token: str | None) -> bool:
    raw = str(token or "").strip()
    if not raw:
        return True
    upper = raw.upper()
    return upper.startswith("CHANGE_ME") or upper in {"TODO", "REPLACE_ME", "YOUR_TOKEN"}


WS_LOCK = threading.Lock()
WS_STATE = {
    "connected": False,
    "revision": 0,
    "last_error": "",
    "last_event_type": "",
    "last_event_agent": "",
    "last_event_id": "",
    "last_event_created_at": "",
    "last_event_payload": {},
}
WS_THREAD_STARTED = False


def _build_ws_url() -> str:
    parsed = urlparse(MISSION_CONTROL_API_URL)
    if parsed.scheme in {"http", "https"}:
        ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    else:
        ws_scheme = "ws"

    netloc = parsed.netloc or parsed.path
    return f"{ws_scheme}://{netloc.rstrip('/')}/ws/events"


def _update_ws_state(**kwargs):
    with WS_LOCK:
        WS_STATE.update(kwargs)


def _bump_ws_revision():
    with WS_LOCK:
        WS_STATE["revision"] = int(WS_STATE.get("revision") or 0) + 1


def _get_ws_state() -> dict:
    with WS_LOCK:
        return {
            "connected": bool(WS_STATE.get("connected")),
            "revision": int(WS_STATE.get("revision") or 0),
            "last_error": str(WS_STATE.get("last_error") or ""),
            "last_event_type": str(WS_STATE.get("last_event_type") or ""),
            "last_event_agent": str(WS_STATE.get("last_event_agent") or ""),
            "last_event_id": str(WS_STATE.get("last_event_id") or ""),
            "last_event_created_at": str(WS_STATE.get("last_event_created_at") or ""),
            "last_event_payload": WS_STATE.get("last_event_payload") if isinstance(WS_STATE.get("last_event_payload"), dict) else {},
        }


def _ws_headers() -> list[str]:
    if not MISSION_CONTROL_AUTH_TOKEN:
        return []
    return [f"Authorization: Bearer {MISSION_CONTROL_AUTH_TOKEN}"]


def _on_ws_message(raw_msg: str) -> None:
    event_type = ""
    event_agent = ""
    event_id = ""
    event_created_at = ""
    event_payload: dict = {}

    try:
        import json

        parsed = json.loads(raw_msg)
        if isinstance(parsed, dict):
            event_type = str(parsed.get("type") or "")
            event_agent = str(parsed.get("agent") or "")
            event_id = str(parsed.get("id") or "")
            event_created_at = str(parsed.get("created_at") or "")
            payload = parsed.get("payload")
            if isinstance(payload, dict):
                event_payload = payload
    except Exception:
        pass

    _update_ws_state(
        last_event_type=event_type,
        last_event_agent=event_agent,
        last_event_id=event_id,
        last_event_created_at=event_created_at,
        last_event_payload=event_payload,
    )
    _bump_ws_revision()


def _ws_subscriber_loop():
    ws_url = _build_ws_url()
    headers = _ws_headers()

    while True:
        try:
            ws_app = websocket.WebSocketApp(
                ws_url,
                header=headers,
                on_open=lambda _ws: _update_ws_state(connected=True, last_error=""),
                on_message=lambda _ws, _msg: _on_ws_message(_msg),
                on_error=lambda _ws, err: _update_ws_state(connected=False, last_error=str(err)),
                on_close=lambda _ws, _code, _msg: _update_ws_state(connected=False),
            )
            ws_app.run_forever(ping_interval=20, ping_timeout=10)
        except Exception as e:
            _update_ws_state(connected=False, last_error=str(e))
        time.sleep(2)


def _ensure_ws_thread_started() -> None:
    global WS_THREAD_STARTED
    if WS_THREAD_STARTED:
        return

    with WS_LOCK:
        if WS_THREAD_STARTED:
            return
        thread = threading.Thread(target=_ws_subscriber_loop, name="mc-ws-subscriber", daemon=True)
        thread.start()
        WS_THREAD_STARTED = True


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        ts = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _human_age(dt: datetime | None) -> str:
    if not dt:
        return ""
    now = datetime.now(timezone.utc)
    seconds = int((now - dt).total_seconds())
    if seconds < 30:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hr ago"
    days = hours // 24
    return f"{days} day ago" if days == 1 else f"{days} days ago"


def _state_label_for_overlay(state: str) -> str:
    mapping = {
        "listening": "Listening",
        "thinking": "Thinking",
        "speaking": "Speaking",
        "error": "Attention",
        "idle": "Ready",
    }
    return mapping.get((state or "idle").lower(), "Ready")


def _overlay_duration_seconds(state: str) -> float:
    key = (state or "idle").lower()
    if key == "listening":
        return 2.0
    if key == "thinking":
        return 3.0
    if key == "speaking":
        return 4.0
    if key == "error":
        return 5.0
    return 2.0


def _voice_overlay_default() -> dict:
    now = time.time()
    return {
        "enabled": bool(MISSION_CONTROL_VOICE_OVERLAY_ENABLED),
        "visible": False,
        "state": "idle",
        "title": "",
        "subtitle": "",
        "agent": "",
        "last_event_id": "",
        "last_event_type": "",
        "updated_at_epoch": now,
        "expires_at_epoch": now,
        "cooldown_until_epoch": 0.0,
        "manual_dismiss_until_epoch": 0.0,
    }


def _voice_state_from_event(event_type: str, payload: dict | None) -> str | None:
    event_type = str(event_type or "").strip().lower()
    payload = payload if isinstance(payload, dict) else {}

    if event_type == "chat.proxy.error" or event_type == "voice.error":
        return "error"
    if event_type == "chat.message.received" or event_type == "voice.tts.start":
        return "speaking"
    if event_type == "chat.message.sent" or event_type == "voice.asr.final":
        return "thinking"
    if event_type == "voice.state":
        state = str(payload.get("state") or "").strip().lower()
        if state in {"listening", "thinking", "speaking", "error", "idle"}:
            return state
    if event_type == "voice.llm.first_token":
        return "speaking"
    return None


def _api_headers() -> dict[str, str]:
    if not MISSION_CONTROL_AUTH_TOKEN:
        return {}
    return {"Authorization": f"Bearer {MISSION_CONTROL_AUTH_TOKEN}"}


def _format_api_status(is_online: bool, last_success: str = "", error: Exception | None = None) -> str:
    base = MISSION_CONTROL_API_URL
    ws_info = _get_ws_state()
    ws_suffix = " | ws:live" if ws_info.get("connected") else " | ws:fallback"
    if is_online:
        tail = f" · updated {last_success}" if last_success else ""
        return f"Online · {base}{tail}{ws_suffix}"
    if not error:
        return f"Offline · {base}{ws_suffix} · retry in 5s"
    detail = f"{error.__class__.__name__}: {error}".strip()
    if len(detail) > 80:
        detail = detail[:77] + "..."
    return f"Offline · {base}{ws_suffix} · {detail} · retry in 5s"


def api_get_json(path: str, *, timeout: float = 3.0):
    url = MISSION_CONTROL_API_URL.rstrip("/") + path
    resp = requests.get(url, headers=_api_headers(), timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def api_patch_json(path: str, body: dict, *, timeout: float = 5.0):
    url = MISSION_CONTROL_API_URL.rstrip("/") + path
    resp = requests.patch(url, headers=_api_headers(), json=body, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def api_post_json(path: str, body: dict, *, timeout: float = 3.0):
    url = MISSION_CONTROL_API_URL.rstrip("/") + path
    resp = requests.post(url, headers=_api_headers(), json=body, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


_AGENT_CATALOG_CACHE = {
    "generated_at": 0.0,
    "data": [],
}


def _normalize_agent_catalog_items(raw_items) -> list[dict]:
    if not isinstance(raw_items, list):
        return []

    out: list[dict] = []
    seen: set[str] = set()
    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue

        slug = str(item.get("slug") or "").strip()
        if not slug or slug in seen:
            continue
        seen.add(slug)

        gateway_token = str(item.get("gateway_token") or "").strip()
        out.append(
            {
                "slug": slug,
                "label": str(item.get("label") or _slug_label(slug)).strip() or _slug_label(slug),
                "enabled": bool(item.get("enabled", True)),
                "gateway_host_port": item.get("gateway_host_port"),
                "bridge_host_port": item.get("bridge_host_port"),
                "direct_url": str(item.get("direct_url") or "").strip(),
                "embed_path": str(item.get("embed_path") or f"/chat/{slug}/").strip() or f"/chat/{slug}/",
                "gateway_token": "" if _is_placeholder_token(gateway_token) else gateway_token,
                "open_mode": str(item.get("open_mode") or "iframe").strip() or "iframe",
                "order": int(item.get("order") if item.get("order") is not None else idx),
            }
        )
    return out


def _get_agent_catalog(*, force_refresh: bool = False, timeout: float = 2.0) -> list[dict]:
    cached = _AGENT_CATALOG_CACHE.get("data")
    if isinstance(cached, list) and cached:
        stale_cache = cached
    else:
        stale_cache = []

    now = time.time()
    if not force_refresh and now - float(_AGENT_CATALOG_CACHE.get("generated_at") or 0.0) <= 4.0:
        if isinstance(cached, list) and cached:
            return cached

    catalog: list[dict] = []
    try:
        catalog = _normalize_agent_catalog_items(api_get_json("/v1/agents/catalog", timeout=timeout))
    except Exception:
        catalog = stale_cache

    _AGENT_CATALOG_CACHE["generated_at"] = now
    _AGENT_CATALOG_CACHE["data"] = catalog
    return catalog


def emit_chat_event(agent_slug: str, event_type: str, payload: dict):
    if not MISSION_CONTROL_CHAT_EVENT_BRIDGE_ENABLED:
        return
    try:
        api_post_json(
            "/v1/events",
            {
                "type": event_type,
                "agent": agent_slug,
                "payload": payload,
            },
            timeout=1.5,
        )
    except Exception:
        return


def api_patch_json(path: str, body: dict, *, timeout: float = 5.0):
    url = MISSION_CONTROL_API_URL.rstrip("/") + path
    resp = requests.patch(url, headers=_api_headers(), json=body, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _tone_for_status(status: str) -> str:
    mapping = {
        "INBOX": "amber",
        "ASSIGNED": "stone",
        "IN PROGRESS": "teal",
        "REVIEW": "olive",
        "DONE": "ink",
    }
    return mapping.get(status.upper(), "stone")


def _format_token_compact(value: int) -> str:
    number = int(value or 0)
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if number >= 1_000:
        return f"{number / 1_000:.1f}k"
    return str(number)


def _default_settings_ui() -> dict:
    return {
        "open": False,
        "warn_24h": 120_000,
        "warn_7d": 700_000,
        "close_24h": 240_000,
        "close_7d": 1_500_000,
        "message": "",
        "message_tone": "neutral",
    }


def _threshold_int(value, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(fallback)
    return max(1, parsed)


def _safe_agent_slug(value: str | None) -> str:
    slug = str(value or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_-]+", slug):
        return ""
    return slug


def _stat_class_high_bad(value: float, warn: float, critical: float) -> str:
    if value >= critical:
        return "stat stat-critical"
    if value >= warn:
        return "stat stat-warn"
    return "stat stat-ok"


def _stat_class_low_bad(value: float, warn: float, critical: float) -> str:
    if value <= critical:
        return "stat stat-critical"
    if value <= warn:
        return "stat stat-warn"
    return "stat stat-ok"


def _settings_risk_level(tokens_24h: int, tokens_7d: int, cfg: dict) -> tuple[str, str, str]:
    warn_24h = int(cfg.get("warn_24h") or 120_000)
    warn_7d = int(cfg.get("warn_7d") or 700_000)
    close_24h = int(cfg.get("close_24h") or 240_000)
    close_7d = int(cfg.get("close_7d") or 1_500_000)

    if tokens_24h >= close_24h or tokens_7d >= close_7d:
        return "建议关闭", "settings-risk-close", "超过关闭阈值，建议暂停该 agent 并人工复核。"
    if tokens_24h >= warn_24h or tokens_7d >= warn_7d:
        return "Token预警", "settings-risk-warn", "接近上限，建议降频或收缩上下文。"
    return "正常", "settings-risk-ok", "运行正常。"


def _settings_summary_hint(total_tokens_7d: int, total_cost_7d: float, missing_cost_entries: int) -> str:
    if total_tokens_7d <= 0:
        return "No recent usage data available yet."
    if total_cost_7d <= 0 and total_tokens_7d > 0:
        return "Cost data may be incomplete because model pricing is not configured."
    if missing_cost_entries > 0:
        return f"Cost data may be incomplete because {missing_cost_entries} usage entries are missing pricing."
    return "Cost data is available for the current 7d assessment window."


def _build_agents(
    board: dict,
    feed: list[dict],
    usage_by_agent: dict[str, dict] | None = None,
    agent_catalog: list[dict] | None = None,
) -> list[dict]:
    catalog = agent_catalog if isinstance(agent_catalog, list) else _get_agent_catalog()
    names: set[str] = {str(item.get("slug")) for item in catalog if item.get("slug") and item.get("enabled", True)}
    last_seen: dict[str, datetime] = {}
    usage_by_agent = usage_by_agent or {}

    for col in board.get("columns", []) or []:
        for card in col.get("cards", []) or []:
            assignee = card.get("assignee")
            if assignee:
                names.add(str(assignee))
                dt = _parse_iso(card.get("updated_at")) or _parse_iso(card.get("created_at"))
                if dt:
                    current = last_seen.get(str(assignee))
                    if not current or dt > current:
                        last_seen[str(assignee)] = dt

    for evt in feed:
        agent = evt.get("agent")
        if agent:
            agent_name = str(agent)
            names.add(agent_name)
            dt = _parse_iso(evt.get("created_at"))
            if dt:
                current = last_seen.get(agent_name)
                if not current or dt > current:
                    last_seen[agent_name] = dt

    now = datetime.now(timezone.utc)

    agents = []
    for name in sorted(names):
        recent_time = last_seen.get(name)
        status = "IDLE"
        if recent_time and (now - recent_time).total_seconds() <= 30 * 60:
            status = "RECENT"
        role = "Seen in board/feed" if recent_time else "Manifest agent"

        usage = usage_by_agent.get(name) or usage_by_agent.get(str(name).lower()) or {}
        tokens_24h = int(usage.get("total_tokens_24h") or 0)
        tokens_7d = int(usage.get("total_tokens_window") or 0)
        cost_7d = float(usage.get("total_cost_window") or 0.0)
        days_window = int(usage.get("days") or 7)
        usage_text = (
            f"Usage 24h { _format_token_compact(tokens_24h) } · {days_window}d { _format_token_compact(tokens_7d) } · Cost ${cost_7d:.4f}"
        )

        agents.append(
            {
                "name": name,
                "role": role,
                "badge": "AGENT",
                "status": status,
                "tag": "AGENT",
                "usage_text": usage_text,
            }
        )
    return agents


def _convert_board(board: dict) -> list[dict]:
    columns = []
    for col in board.get("columns", []) or []:
        status = str(col.get("title") or "").strip() or "INBOX"
        cards = []
        for t in col.get("cards", []) or []:
            updated = _parse_iso(t.get("updated_at")) or _parse_iso(t.get("created_at"))
            cards.append(
                {
                    "title": t.get("title") or "(untitled)",
                    "tags": t.get("tags") or [],
                    "assignee": t.get("assignee") or "-",
                    "age": _human_age(updated),
                    "tone": _tone_for_status(status),
                }
            )
        columns.append({"title": status, "count": int(col.get("count") or len(cards)), "cards": cards})
    return columns


def _convert_feed(feed: list[dict]) -> list[dict]:
    out = []
    for evt in feed or []:
        created = _parse_iso(evt.get("created_at"))
        evt_type = evt.get("type") or "event"
        agent = evt.get("agent") or "-"
        task_id = str(evt.get("task_id") or "")
        short_task = task_id[:8] if task_id else ""
        payload = evt.get("payload")
        if not isinstance(payload, dict):
            payload = {
                "method": evt.get("method"),
                "path": evt.get("path"),
                "status_code": evt.get("status_code"),
                "error_type": evt.get("error_type"),
            }

        category = "system"
        if evt_type.startswith("task."):
            category = "tasks"
        elif evt_type.startswith("comment."):
            category = "comments"
        elif evt_type.startswith("chat."):
            category = "chat"

        if evt_type == "comment.created":
            action = f"commented on task {short_task}" if short_task else "commented"
        elif evt_type == "task.created":
            title = str(payload.get("title") or "").strip()
            action = f"created task: {title}" if title else "created a task"
        elif evt_type == "task.updated":
            action = f"updated task {short_task}" if short_task else "updated a task"
        elif evt_type == "agent.heartbeat":
            status = "ok" if payload.get("ok") is True else "signal"
            action = f"heartbeat ({status})"
        elif evt_type == "chat.message.sent":
            method = str(payload.get("method") or "-")
            path = str(payload.get("path") or "")
            action = f"chat sent {method} {path}".strip()
        elif evt_type == "chat.message.received":
            status_code = payload.get("status_code")
            action = f"chat received (HTTP {status_code})" if status_code is not None else "chat received"
        elif evt_type == "chat.proxy.error":
            error_type = str(payload.get("error_type") or "proxy_error")
            action = f"chat proxy error: {error_type}"
        else:
            action = f"event: {evt_type}"

        out.append(
            {
                "agent": agent,
                "action": action,
                "age": _human_age(created),
                "category": category,
            }
        )
    return out


def _filter_board(columns: list[dict], selected: str) -> list[dict]:
    key = (selected or "all").lower()
    if key in {"all", "tasks"}:
        return columns
    return columns


def _filter_feed(feed_items: list[dict], selected: str) -> list[dict]:
    key = (selected or "all").lower()
    if key == "all":
        return feed_items
    return [item for item in feed_items if item.get("category") == key]


def _chip_class(selected: str, value: str) -> str:
    if (selected or "all").lower() == value:
        return "filter-chip active"
    return "filter-chip"


def _sanitize_board_filter(value: str | None) -> str:
    allowed = {"all", "tasks"}
    key = (value or "all").lower().strip()
    return key if key in allowed else "all"


def _sanitize_feed_filter(value: str | None) -> str:
    legacy_map = {"decisions": "system"}
    key = (value or "all").lower().strip()
    key = legacy_map.get(key, key)
    allowed = {"all", "tasks", "comments", "chat", "system"}
    return key if key in allowed else "all"


def _parse_filters_from_search(search: str | None) -> tuple[str, str]:
    if not search:
        return "all", "all"
    text = search[1:] if search.startswith("?") else search
    params = parse_qs(text)
    board_filter = _sanitize_board_filter((params.get("board") or ["all"])[0])
    feed_filter = _sanitize_feed_filter((params.get("feed") or ["all"])[0])
    return board_filter, feed_filter


def _build_search(board_filter: str, feed_filter: str) -> str:
    board = _sanitize_board_filter(board_filter)
    feed = _sanitize_feed_filter(feed_filter)
    if board == "all" and feed == "all":
        return ""
    query = urlencode({"board": board, "feed": feed})
    return f"?{query}"


def agent_card(agent):
    status = str(agent.get("status") or "IDLE").lower()
    return html.Div(
        className="agent-card",
        children=[
            html.Div(className="agent-avatar", children=agent["name"][0]),
            html.Div(
                className="agent-meta",
                children=[
                    html.Div(
                        className="agent-header",
                        children=[
                            html.Span(agent["name"], className="agent-name"),
                            html.Span(agent["badge"], className="agent-badge"),
                        ],
                    ),
                    html.Div(agent["role"], className="agent-role"),
                    html.Div(agent.get("usage_text") or "Usage 24h 0 · 7d 0 · Cost $0.0000", className="agent-usage"),
                ],
            ),
            html.Div(
                className=f"agent-status status-{status}",
                children=[
                    html.Span(className="status-dot"),
                    html.Span(agent["status"], className="status-text"),
                ],
            ),
        ],
    )


def task_card(card):
    tone_class = f"card tone-{card['tone']}"
    return html.Div(
        className=tone_class,
        children=[
            html.Div(card["title"], className="card-title"),
            html.Div(
                className="card-meta",
                children=[
                    html.Div(
                        className="card-tags",
                        children=[html.Span(tag, className="tag") for tag in card["tags"]],
                    ),
                    html.Div(
                        className="card-footer",
                        children=[
                            html.Span(card["assignee"], className="card-assignee"),
                            html.Span(card["age"], className="card-age"),
                        ],
                    ),
                ],
            ),
        ],
    )


def column(column_data):
    return html.Div(
        className="board-column",
        children=[
            html.Div(
                className="column-header",
                children=[
                    html.Span(column_data["title"], className="column-title"),
                    html.Span(str(column_data["count"]), className="column-count"),
                ],
            ),
            html.Div(
                className="column-cards",
                children=[task_card(card) for card in column_data["cards"]]
                or [html.Div("No cards", className="column-empty")],
            ),
        ],
    )


def feed_item(item):
    return html.Div(
        className="feed-item",
        children=[
            html.Div(item["agent"], className="feed-agent"),
            html.Div(item["action"], className="feed-action"),
            html.Div(item["age"], className="feed-age"),
        ],
    )


app = Dash(__name__)
app.title = APP_TITLE

app.clientside_callback(
    """
    function(voiceUi, current) {
        const state = voiceUi || {};
        const prev = current || {
            samples: [],
            last_event_id: "",
            last_visible_latency_ms: 0,
            p50_ms: 0,
            p95_ms: 0,
            samples_count: 0
        };

        if (!state.enabled || !state.visible) {
            return prev;
        }

        const eventId = String(state.last_event_id || "");
        if (!eventId || eventId === String(prev.last_event_id || "")) {
            return prev;
        }

        const sentMs = Number(state.trigger_client_sent_ms || 0);
        if (!Number.isFinite(sentMs) || sentMs <= 0) {
            return {
                ...prev,
                last_event_id: eventId
            };
        }

        const nowMs = Date.now();
        const latency = Math.max(0, nowMs - sentMs);

        const samples = (Array.isArray(prev.samples) ? prev.samples.slice(-199) : []);
        samples.push(latency);
        const sorted = samples.slice().sort((a, b) => a - b);

        const pick = function(arr, p) {
            if (!arr.length) return 0;
            const idx = Math.max(0, Math.min(arr.length - 1, Math.floor((arr.length - 1) * p)));
            return Number(arr[idx] || 0);
        };

        return {
            samples: samples,
            last_event_id: eventId,
            last_visible_latency_ms: Number(latency.toFixed(1)),
            p50_ms: Number(pick(sorted, 0.50).toFixed(1)),
            p95_ms: Number(pick(sorted, 0.95).toFixed(1)),
            samples_count: samples.length
        };
    }
    """,
    Output("voice-metrics", "data"),
    Input("voice-ui", "data"),
    State("voice-metrics", "data"),
)


@app.server.route("/chat/<agent_slug>/", defaults={"proxy_path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
@app.server.route("/chat/<agent_slug>/<path:proxy_path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
def chat_reverse_proxy(agent_slug: str, proxy_path: str):
    if not MISSION_CONTROL_ENABLE_LEGACY_CHAT_PROXY:
        return Response(
            "Legacy Mission Control chat proxy is disabled. Use /chat via mission-control-gateway.",
            status=410,
        )

    return Response(
        "Legacy Mission Control chat proxy is deprecated. Use /chat via mission-control-gateway.",
        status=410,
    )
    return resp

app.layout = html.Div(
    className="page",
    children=[
        dcc.Location(id="url", refresh=False),
        dcc.Interval(id="refresh", interval=5_000, n_intervals=0),
        dcc.Interval(id="ws-tick", interval=MISSION_CONTROL_WS_TICK_MS, n_intervals=0),
        dcc.Interval(id="clock-tick", interval=1_000, n_intervals=0),
        dcc.Store(
            id="ui-state",
            data={
                "board_filter": "all",
                "feed_filter": "all",
            },
        ),
        dcc.Store(
            id="skills-ui",
            data={
                "open": False,
                "revision": 0,
                "message": "",
                "message_tone": "neutral",
                "detail_agent": "",
            },
        ),
        dcc.Store(
            id="chat-ui",
            data={
                "open": False,
                "selected_agent": "",
                "last_agent": "",
                "window_mode": "floating",
                "panel_mode": "split",
                "iframe_status": "idle",
                "error_message": "",
            },
        ),
        dcc.Store(id="settings-ui", data=_default_settings_ui()),
        dcc.Store(id="voice-ui", data=_voice_overlay_default()),
        dcc.Store(
            id="voice-metrics",
            data={
                "samples": [],
                "last_event_id": "",
                "last_visible_latency_ms": 0,
                "p50_ms": 0,
                "p95_ms": 0,
                "samples_count": 0,
            },
        ),
        html.Div(
            className="topbar",
            children=[
                html.Div(
                    className="topbar-row",
                    children=[
                        html.Div(
                            className="topbar-left",
                            children=[
                                html.Div(
                                    className="brand",
                                    children=[
                                        html.Span("Mission Control", className="brand-title"),
                                        html.Span("SiteGPT", className="brand-chip"),
                                    ],
                                ),
                                html.Div(
                                    className="stats stats-primary",
                                    children=[
                                        html.Div(
                                            className="stat",
                                            children=[
                                                html.Span("-", id="stat-agents", className="stat-value"),
                                                html.Span("Agents Active", className="stat-label"),
                                            ],
                                        ),
                                        html.Div(
                                            className="stat",
                                            children=[
                                                html.Span("-", id="stat-tasks", className="stat-value"),
                                                html.Span("Tasks in Queue", className="stat-label"),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(
                            className="topbar-actions",
                            children=[
                                html.A(
                                    "Docs",
                                    href=MISSION_CONTROL_DOCS_URL,
                                    target="_blank",
                                    rel="noreferrer",
                                    className="ghost-button docs-link",
                                ),
                                html.Button("Chat", id="open-chat", className="ghost-button"),
                                html.Button("Skills", id="open-skills", className="ghost-button"),
                                html.Button("Clear Filters", id="clear-filters", className="ghost-button"),
                                html.Div("Overlay n/a", id="voice-latency-pill", className="status-pill status-unknown"),
                                html.Div("-", id="api-status", className="status-pill status-unknown"),
                                html.Button("Settings", id="open-settings", className="ghost-button"),
                            ],
                        ),
                    ],
                ),
                html.Div(
                    className="stats stats-observability",
                    children=[
                        html.Div(
                            id="stat-card-error-rate",
                            className="stat stat-observability-card",
                            children=[
                                html.Span("Error", className="stat-label"),
                                html.Span("-", id="stat-error-rate", className="stat-value"),
                            ],
                        ),
                        html.Div(
                            id="stat-card-event-backlog",
                            className="stat stat-observability-card",
                            children=[
                                html.Span("Backlog", className="stat-label"),
                                html.Span("-", id="stat-event-backlog", className="stat-value"),
                            ],
                        ),
                        html.Div(
                            id="stat-card-task-throughput",
                            className="stat stat-observability-card",
                            children=[
                                html.Span("Throughput", className="stat-label"),
                                html.Span("-", id="stat-task-throughput", className="stat-value"),
                            ],
                        ),
                        html.Div(
                            id="stat-card-health-ratio",
                            className="stat stat-observability-card",
                            children=[
                                html.Span("Health", className="stat-label"),
                                html.Span("-", id="stat-health-ratio", className="stat-value"),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        html.Div(
            className="main",
            children=[
                html.Div(
                    className="panel left",
                    children=[
                        html.Div(
                            className="panel-title",
                            children=[
                                html.Span("Agents"),
                                html.Span("-", id="agents-count", className="panel-count"),
                            ],
                        ),
                        html.Div(id="agents", className="agent-list"),
                    ],
                ),
                html.Div(
                    className="panel center",
                    children=[
                        html.Div(
                            className="panel-title",
                            children=[
                                html.Span("Mission Queue"),
                                html.Div(
                                    className="panel-filters",
                                    children=[
                                        html.Button("All", id="board-filter-all", className="filter-chip active"),
                                        html.Button("Tasks", id="board-filter-tasks", className="filter-chip"),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(id="board", className="board"),
                    ],
                ),
                html.Div(
                    className="panel right",
                    children=[
                        html.Div(
                            className="panel-title",
                            children=[
                                html.Span("Live Feed"),
                                html.Div(
                                    className="panel-filters",
                                    children=[
                                        html.Button("All", id="feed-filter-all", className="filter-chip active"),
                                        html.Button("Tasks", id="feed-filter-tasks", className="filter-chip"),
                                        html.Button("Comments", id="feed-filter-comments", className="filter-chip"),
                                        html.Button("Chat", id="feed-filter-chat", className="filter-chip"),
                                        html.Button("System", id="feed-filter-system", className="filter-chip"),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(id="feed", className="feed"),
                    ],
                ),
            ],
        ),
        html.Div(
            id="settings-modal",
            className="settings-modal",
            children=[
                html.Div(
                    className="settings-modal-card",
                    children=[
                        html.Div(
                            className="settings-modal-header",
                            children=[
                                html.Div(
                                    children=[
                                        html.Div("Configuration Center", className="settings-title"),
                                        html.Div(
                                            "Monitor per-agent usage, token thresholds, and close recommendations.",
                                            className="settings-subtitle",
                                        ),
                                    ]
                                ),
                                html.Button("Close", id="close-settings", className="ghost-button"),
                            ],
                        ),
                        html.Div(id="settings-notice", className="settings-notice"),
                        html.Div(
                            id="settings-overview",
                            className="settings-overview",
                        ),
                        html.Div(
                            className="settings-thresholds",
                            children=[
                                html.Div("Token Threshold Policy", className="settings-col-title"),
                                html.Div(
                                    className="settings-threshold-grid",
                                    children=[
                                        html.Div(
                                            className="settings-field",
                                            children=[
                                                html.Div("Warn 24h tokens", className="settings-label"),
                                                dcc.Input(
                                                    id="settings-threshold-24h-warn",
                                                    type="number",
                                                    min=1,
                                                    step=1000,
                                                    value=120000,
                                                    className="settings-input",
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            className="settings-field",
                                            children=[
                                                html.Div("Warn 7d tokens", className="settings-label"),
                                                dcc.Input(
                                                    id="settings-threshold-7d-warn",
                                                    type="number",
                                                    min=1,
                                                    step=1000,
                                                    value=700000,
                                                    className="settings-input",
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            className="settings-field",
                                            children=[
                                                html.Div("Close Suggest 24h", className="settings-label"),
                                                dcc.Input(
                                                    id="settings-threshold-24h-close",
                                                    type="number",
                                                    min=1,
                                                    step=1000,
                                                    value=240000,
                                                    className="settings-input",
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            className="settings-field",
                                            children=[
                                                html.Div("Close Suggest 7d", className="settings-label"),
                                                dcc.Input(
                                                    id="settings-threshold-7d-close",
                                                    type="number",
                                                    min=1,
                                                    step=1000,
                                                    value=1500000,
                                                    className="settings-input",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="settings-actions",
                                    children=[
                                        html.Button("Apply Thresholds", id="apply-settings-thresholds", className="ghost-button"),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(
                            className="settings-assessment",
                            children=[
                                html.Div("Agent Usage Assessment", className="settings-col-title"),
                                html.Div(id="settings-assessment-list", className="settings-scroll"),
                            ],
                        ),
                    ],
                )
            ],
        ),
        html.Div(
            id="skills-modal",
            className="skills-modal",
            children=[
                html.Div(
                    className="skills-modal-card",
                    children=[
                        html.Div(
                            className="skills-modal-header",
                            children=[
                                html.Div(
                                    children=[
                                        html.Div("Skills Management", className="skills-title"),
                                        html.Div(
                                            "View global/workspace skills and batch-assign global skills to agents.",
                                            className="skills-subtitle",
                                        ),
                                    ]
                                ),
                                html.Button("Close", id="close-skills", className="ghost-button"),
                            ],
                        ),
                        html.Div(
                            id="skills-notice",
                            className="skills-notice",
                        ),
                        html.Div(id="skills-overview", className="skills-overview"),
                        html.Div(
                            className="skills-grid",
                            children=[
                                html.Div(
                                    className="skills-col",
                                    children=[
                                        html.Div("Global Skills", className="skills-col-title"),
                                        html.Div(
                                            className="skills-toolbar",
                                            children=[
                                                dcc.Input(
                                                    id="skills-global-search",
                                                    type="text",
                                                    placeholder="Search global skills",
                                                    className="skills-search-input",
                                                ),
                                                html.Button("Select All", id="skills-global-select-all", className="ghost-button"),
                                                html.Button("Clear", id="skills-global-clear", className="ghost-button"),
                                            ],
                                        ),
                                        dcc.Checklist(
                                            id="skills-global-checklist",
                                            options=[],
                                            value=[],
                                            className="skills-checklist skills-global-checklist",
                                            inputClassName="skills-checklist-input",
                                            labelClassName="skills-checklist-label skills-global-checklist-label",
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="skills-col",
                                    children=[
                                        html.Div("Agents (multi-select)", className="skills-col-title"),
                                        html.Div(
                                            className="skills-toolbar",
                                            children=[
                                                dcc.Input(
                                                    id="skills-agent-search",
                                                    type="text",
                                                    placeholder="Search agents",
                                                    className="skills-search-input",
                                                ),
                                                html.Button("Select All", id="skills-agent-select-all", className="ghost-button"),
                                                html.Button("Clear", id="skills-agent-clear", className="ghost-button"),
                                            ],
                                        ),
                                        dcc.Checklist(id="skills-agent-checklist", options=[], value=[]),
                                        html.Div("Inspect Agent", className="skills-field-label"),
                                        dcc.Dropdown(
                                            id="skills-detail-agent",
                                            options=[],
                                            value=None,
                                            clearable=False,
                                            className="skills-detail-select",
                                        ),
                                        html.Div(
                                            className="skills-actions",
                                            children=[
                                                html.Button("Add Skills", id="skills-add", className="ghost-button"),
                                                html.Button("Remove Skills", id="skills-remove", className="ghost-button"),
                                            ],
                                        ),
                                        html.Div(id="skills-selection-summary", className="skills-selection-summary"),
                                        html.Div(
                                            "Changes are saved immediately. Restart affected agent containers to apply.",
                                            className="skills-hint",
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(
                            className="skills-lists",
                            children=[
                                html.Div(
                                    className="skills-list-block",
                                    children=[
                                        html.Div("Inventory", className="skills-col-title"),
                                        html.Div(id="skills-inventory-view", className="skills-scroll skills-scroll-tall"),
                                    ],
                                ),
                                html.Div(
                                    className="skills-list-block skills-detail-block",
                                    children=[
                                        html.Div("Agent Detail", className="skills-col-title"),
                                        html.Div(id="skills-agent-detail-view", className="skills-detail-view"),
                                        html.Div(
                                            className="skills-runtime-editor",
                                            children=[
                                                html.Div("Runtime Config", className="skills-col-title"),
                                                html.Div(
                                                    className="skills-runtime-grid",
                                                    children=[
                                                        html.Div(
                                                            className="skills-runtime-field",
                                                            children=[
                                                                html.Div("nativeSkills mode", className="skills-field-label"),
                                                                dcc.Input(
                                                                    id="skills-runtime-native-mode",
                                                                    type="text",
                                                                    placeholder="auto",
                                                                    className="skills-search-input",
                                                                ),
                                                            ],
                                                        ),
                                                        html.Div(
                                                            className="skills-runtime-field",
                                                            children=[
                                                                html.Div("allowBundled", className="skills-field-label"),
                                                                dcc.Textarea(
                                                                    id="skills-runtime-allow-bundled",
                                                                    placeholder="One per line or comma-separated",
                                                                    className="skills-textarea",
                                                                ),
                                                            ],
                                                        ),
                                                        html.Div(
                                                            className="skills-runtime-field skills-runtime-field-wide",
                                                            children=[
                                                                html.Div("extraDirs", className="skills-field-label"),
                                                                dcc.Textarea(
                                                                    id="skills-runtime-extra-dirs",
                                                                    placeholder="One per line or comma-separated",
                                                                    className="skills-textarea",
                                                                ),
                                                            ],
                                                        ),
                                                    ],
                                                ),
                                                html.Div(
                                                    className="skills-actions",
                                                    children=[
                                                        html.Button("Save Runtime Config", id="skills-runtime-save", className="ghost-button"),
                                                    ],
                                                ),
                                                html.Div(
                                                    "Only skill-related runtime fields are edited here. Restart the agent container after changes.",
                                                    className="skills-hint",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(
                            className="skills-list-block skills-report-block",
                            children=[
                                html.Div("Report Issues", className="skills-col-title"),
                                html.Div(id="skills-report-view", className="skills-scroll"),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        html.Div(
            id="chat-modal",
            className="chat-modal",
            children=[
                html.Div(
                    id="chat-modal-card",
                    className="chat-modal-card",
                    children=[
                        html.Div(
                            className="chat-modal-header",
                            children=[
                                html.Div(
                                    children=[
                                        html.Div("Agent Chat", className="chat-title"),
                                        html.Div(
                                            "Switch agents in one window. If embedded chat is blocked, use Open External.",
                                            className="chat-subtitle",
                                        ),
                                    ]
                                ),
                                html.Div(
                                    className="chat-header-actions",
                                    children=[
                                        html.Button("Maximize", id="toggle-chat-max", className="ghost-button"),
                                        html.Button("Chat Only", id="toggle-chat-panel", className="ghost-button"),
                                        html.Button("Close", id="close-chat", className="ghost-button"),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(id="chat-notice", className="chat-notice"),
                        html.Div(
                            id="chat-modal-body",
                            className="chat-modal-body",
                            children=[
                                html.Div(
                                    className="chat-sidebar",
                                    children=[
                                        html.Div("Agent", className="chat-col-title"),
                                        dcc.Dropdown(
                                            id="chat-agent-select",
                                            options=[],
                                            value=None,
                                            clearable=False,
                                            placeholder="Select an agent",
                                        ),
                                        html.A(
                                            "Open External",
                                            id="chat-open-external",
                                            href="#",
                                            target="_blank",
                                            rel="noreferrer",
                                            className="ghost-button docs-link chat-external-link",
                                        ),
                                        html.Div(
                                            "Mission Control now routes chat via the unified gateway. If a browser policy blocks iframe rendering, use Open External.",
                                            className="chat-hint",
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="chat-main",
                                    children=[
                                        html.Iframe(
                                            id="chat-iframe",
                                            src="about:blank",
                                            className="chat-iframe",
                                            allow="camera; microphone; display-capture; autoplay; clipboard-read; clipboard-write; fullscreen"
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        html.Div(
            id="voice-overlay",
            className="voice-overlay",
            children=[
                html.Div(
                    id="voice-overlay-card",
                    className="voice-overlay-card state-idle",
                    children=[
                        html.Div(className="voice-overlay-pulse", children=[html.Span(className="status-dot")]),
                        html.Div(
                            className="voice-overlay-content",
                            children=[
                                html.Div("Ready", id="voice-overlay-title", className="voice-overlay-title"),
                                html.Div("Awaiting wakeup event", id="voice-overlay-subtitle", className="voice-overlay-subtitle"),
                            ],
                        ),
                        html.Div(
                            className="voice-overlay-actions",
                            children=[
                                html.Button("Open", id="voice-overlay-open-chat", className="ghost-button"),
                                html.Button("Close", id="voice-overlay-close", className="ghost-button"),
                            ],
                        ),
                    ],
                )
            ],
        ),
    ],
)


@app.callback(
    Output("ui-state", "data"),
    Input("url", "search"),
    Input("board-filter-all", "n_clicks"),
    Input("board-filter-tasks", "n_clicks"),
    Input("feed-filter-all", "n_clicks"),
    Input("feed-filter-tasks", "n_clicks"),
    Input("feed-filter-comments", "n_clicks"),
    Input("feed-filter-chat", "n_clicks"),
    Input("feed-filter-system", "n_clicks"),
    Input("clear-filters", "n_clicks"),
    State("ui-state", "data"),
    prevent_initial_call=False,
)
def update_ui_state(*args):
    state = args[-1] or {}
    trigger = ctx.triggered_id

    board_filter = (state.get("board_filter") or "all").lower()
    feed_filter = (state.get("feed_filter") or "all").lower()

    board_map = {
        "board-filter-all": "all",
        "board-filter-tasks": "tasks",
    }
    feed_map = {
        "feed-filter-all": "all",
        "feed-filter-tasks": "tasks",
        "feed-filter-comments": "comments",
        "feed-filter-chat": "chat",
        "feed-filter-system": "system",
    }

    if trigger == "url" or trigger is None:
        url_search = args[0]
        board_filter, feed_filter = _parse_filters_from_search(url_search)
        return {
            "board_filter": board_filter,
            "feed_filter": feed_filter,
        }

    if trigger == "clear-filters":
        return {
            "board_filter": "all",
            "feed_filter": "all",
        }

    if trigger in board_map:
        board_filter = board_map[trigger]
    if trigger in feed_map:
        feed_filter = feed_map[trigger]

    return {
        "board_filter": board_filter,
        "feed_filter": feed_filter,
    }


@app.callback(
    Output("url", "search"),
    Input("ui-state", "data"),
    State("url", "search"),
)
def sync_url_with_filters(state, current_search):
    state = state or {}
    board_filter = _sanitize_board_filter(state.get("board_filter"))
    feed_filter = _sanitize_feed_filter(state.get("feed_filter"))
    expected = _build_search(board_filter, feed_filter)
    if (current_search or "") == expected:
        return no_update
    return expected


@app.callback(
    Output("voice-ui", "data"),
    Input("ws-tick", "n_intervals"),
    State("voice-ui", "data"),
    prevent_initial_call=False,
)
def update_voice_overlay_from_event(_, voice_ui):
    state = _voice_overlay_default()
    if isinstance(voice_ui, dict):
        state.update(voice_ui)

    if not state.get("enabled"):
        if state != (voice_ui or {}):
            return state
        return no_update

    ws_state = _get_ws_state()
    event_type = str(ws_state.get("last_event_type") or "")
    event_id = str(ws_state.get("last_event_id") or "")
    event_agent = str(ws_state.get("last_event_agent") or "")
    payload = ws_state.get("last_event_payload") if isinstance(ws_state.get("last_event_payload"), dict) else {}

    if not event_type:
        return no_update
    if event_id and event_id == str(state.get("last_event_id") or ""):
        return no_update

    next_voice_state = _voice_state_from_event(event_type, payload)
    if not next_voice_state:
        if event_id:
            state["last_event_id"] = event_id
            state["last_event_type"] = event_type
            return state
        return no_update

    now = time.time()
    if now < float(state.get("manual_dismiss_until_epoch") or 0.0) and next_voice_state != "error":
        state["last_event_id"] = event_id
        state["last_event_type"] = event_type
        return state

    current_state = str(state.get("state") or "idle")
    same_state = current_state == next_voice_state and str(state.get("agent") or "") == event_agent
    if same_state and now < float(state.get("cooldown_until_epoch") or 0.0):
        state["last_event_id"] = event_id
        state["last_event_type"] = event_type
        return state

    subtitle = ""
    if next_voice_state == "listening":
        subtitle = "Wake word captured"
    elif next_voice_state == "thinking":
        subtitle = "Understanding request"
    elif next_voice_state == "speaking":
        subtitle = "Delivering response"
    elif next_voice_state == "error":
        subtitle = "Please check service health"

    if event_agent:
        subtitle = f"{event_agent}: {subtitle}" if subtitle else event_agent

    state["visible"] = True
    state["state"] = next_voice_state
    state["title"] = _state_label_for_overlay(next_voice_state)
    state["subtitle"] = subtitle
    state["agent"] = event_agent
    state["last_event_id"] = event_id
    state["last_event_type"] = event_type
    trigger_sent_ms = payload.get("client_sent_ms")
    try:
        state["trigger_client_sent_ms"] = float(trigger_sent_ms) if trigger_sent_ms is not None else 0.0
    except (TypeError, ValueError):
        state["trigger_client_sent_ms"] = 0.0
    state["updated_at_epoch"] = now
    state["expires_at_epoch"] = now + _overlay_duration_seconds(next_voice_state)
    state["cooldown_until_epoch"] = now + (0.8 if next_voice_state != "error" else 0.0)
    return state


@app.callback(
    Output("voice-ui", "data", allow_duplicate=True),
    Input("clock-tick", "n_intervals"),
    State("voice-ui", "data"),
    prevent_initial_call=True,
)
def auto_fade_voice_overlay(_, voice_ui):
    state = _voice_overlay_default()
    if isinstance(voice_ui, dict):
        state.update(voice_ui)

    if not state.get("enabled"):
        return state
    if not state.get("visible"):
        return no_update

    now = time.time()
    if now < float(state.get("expires_at_epoch") or 0.0):
        return no_update

    state["visible"] = False
    state["state"] = "idle"
    state["title"] = ""
    state["subtitle"] = ""
    state["updated_at_epoch"] = now
    return state


@app.callback(
    Output("voice-ui", "data", allow_duplicate=True),
    Input("voice-overlay-close", "n_clicks"),
    State("voice-ui", "data"),
    prevent_initial_call=True,
)
def close_voice_overlay(_, voice_ui):
    state = _voice_overlay_default()
    if isinstance(voice_ui, dict):
        state.update(voice_ui)

    now = time.time()
    state["visible"] = False
    state["state"] = "idle"
    state["title"] = ""
    state["subtitle"] = ""
    state["manual_dismiss_until_epoch"] = now + 2.0
    state["updated_at_epoch"] = now
    return state


@app.callback(
    Output("chat-ui", "data", allow_duplicate=True),
    Input("voice-overlay-open-chat", "n_clicks"),
    State("chat-ui", "data"),
    State("voice-ui", "data"),
    prevent_initial_call=True,
)
def open_chat_from_voice_overlay(_, chat_ui, voice_ui):
    data = chat_ui or {
        "open": False,
        "selected_agent": "",
        "last_agent": "",
        "window_mode": "floating",
        "panel_mode": "split",
        "iframe_status": "idle",
        "error_message": "",
    }
    voice_state = voice_ui if isinstance(voice_ui, dict) else {}

    agent_catalog = _get_agent_catalog()
    available_slugs = [str(item.get("slug")) for item in agent_catalog if item.get("slug") and item.get("enabled", True)]
    preferred_agent = str(voice_state.get("agent") or "").strip()
    if preferred_agent not in available_slugs:
        preferred_agent = data.get("selected_agent") or data.get("last_agent") or (available_slugs[0] if available_slugs else "")

    data["open"] = True
    data["selected_agent"] = str(preferred_agent or "")
    data["last_agent"] = str(preferred_agent or "")
    data["iframe_status"] = "loading"
    data["error_message"] = ""
    return data


@app.callback(
    Output("voice-overlay", "className"),
    Output("voice-overlay-card", "className"),
    Output("voice-overlay-title", "children"),
    Output("voice-overlay-subtitle", "children"),
    Input("voice-ui", "data"),
    prevent_initial_call=False,
)
def render_voice_overlay(voice_ui):
    state = _voice_overlay_default()
    if isinstance(voice_ui, dict):
        state.update(voice_ui)

    if not state.get("enabled"):
        return "voice-overlay disabled", "voice-overlay-card state-idle", "", ""

    visible = bool(state.get("visible"))
    voice_state = str(state.get("state") or "idle").lower()
    title = str(state.get("title") or _state_label_for_overlay(voice_state))
    subtitle = str(state.get("subtitle") or "")

    overlay_class = "voice-overlay open" if visible else "voice-overlay"
    card_class = f"voice-overlay-card state-{voice_state}"
    return overlay_class, card_class, title, subtitle


@app.callback(
    Output("voice-latency-pill", "children"),
    Output("voice-latency-pill", "className"),
    Input("voice-metrics", "data"),
    prevent_initial_call=False,
)
def render_voice_latency_pill(metrics):
    data = metrics if isinstance(metrics, dict) else {}
    count = int(data.get("samples_count") or 0)
    if count <= 0:
        return "Overlay n/a", "status-pill status-unknown"

    p50 = float(data.get("p50_ms") or 0.0)
    p95 = float(data.get("p95_ms") or 0.0)
    text = f"Overlay p50 {p50:.0f}ms · p95 {p95:.0f}ms"

    if p95 <= 800:
        tone = "status-online"
    elif p95 <= 1500:
        tone = "status-unknown"
    else:
        tone = "status-offline"
    return text, f"status-pill {tone}"


@app.callback(
    Output("settings-ui", "data", allow_duplicate=True),
    Input("open-settings", "n_clicks"),
    Input("close-settings", "n_clicks"),
    Input("apply-settings-thresholds", "n_clicks"),
    Input({"type": "settings-agent-action", "agent": ALL, "action": ALL}, "n_clicks"),
    State("settings-ui", "data"),
    State("settings-threshold-24h-warn", "value"),
    State("settings-threshold-7d-warn", "value"),
    State("settings-threshold-24h-close", "value"),
    State("settings-threshold-7d-close", "value"),
    prevent_initial_call=True,
)
def update_settings_ui(
    _,
    __,
    ___,
    ____,
    data,
    warn_24h,
    warn_7d,
    close_24h,
    close_7d,
):
    state = _default_settings_ui()
    if isinstance(data, dict):
        state.update(data)

    trigger = ctx.triggered_id
    if trigger == "open-settings":
        state["open"] = True
        state["message"] = ""
        state["message_tone"] = "neutral"
        return state

    if trigger == "close-settings":
        state["open"] = False
        return state

    if trigger == "apply-settings-thresholds":
        state["warn_24h"] = _threshold_int(warn_24h, int(state.get("warn_24h") or 120_000))
        state["warn_7d"] = _threshold_int(warn_7d, int(state.get("warn_7d") or 700_000))
        state["close_24h"] = _threshold_int(close_24h, int(state.get("close_24h") or 240_000))
        state["close_7d"] = _threshold_int(close_7d, int(state.get("close_7d") or 1_500_000))

        if state["close_24h"] < state["warn_24h"] or state["close_7d"] < state["warn_7d"]:
            state["message"] = "Close阈值应不低于Warn阈值，系统已保留输入但请复核。"
            state["message_tone"] = "warn"
        else:
            state["message"] = "Token阈值已更新。"
            state["message_tone"] = "ok"
        return state

    if isinstance(trigger, dict) and trigger.get("type") == "settings-agent-action":
        slug = _safe_agent_slug(trigger.get("agent"))
        action = str(trigger.get("action") or "").strip().lower()
        if not slug or action not in {"start", "stop", "restart"}:
            state["message"] = "Agent control failed: invalid action target."
            state["message_tone"] = "error"
            return state

        try:
            resp = api_post_json(f"/v1/agents/{slug}/control", {"action": action}, timeout=6.0)
            if isinstance(resp, dict) and bool(resp.get("ok", False)):
                status = str(resp.get("status") or "unknown")
                state["message"] = f"{slug}: {action} completed (status: {status})."
                state["message_tone"] = "ok"
            else:
                state["message"] = f"{slug}: {action} finished with unknown response."
                state["message_tone"] = "warn"
        except Exception as e:
            state["message"] = f"{slug}: {action} failed: {e}"
            state["message_tone"] = "error"
        return state

    return state


@app.callback(
    Output("settings-modal", "className"),
    Output("settings-threshold-24h-warn", "value"),
    Output("settings-threshold-7d-warn", "value"),
    Output("settings-threshold-24h-close", "value"),
    Output("settings-threshold-7d-close", "value"),
    Output("settings-overview", "children"),
    Output("settings-assessment-list", "children"),
    Output("settings-notice", "children"),
    Output("settings-notice", "className"),
    Input("refresh", "n_intervals"),
    Input("settings-ui", "data"),
    prevent_initial_call=False,
)
def render_settings_modal(_, settings_ui):
    state = _default_settings_ui()
    if isinstance(settings_ui, dict):
        state.update(settings_ui)

    is_open = bool(state.get("open"))

    warn_24h = _threshold_int(state.get("warn_24h"), 120_000)
    warn_7d = _threshold_int(state.get("warn_7d"), 700_000)
    close_24h = _threshold_int(state.get("close_24h"), 240_000)
    close_7d = _threshold_int(state.get("close_7d"), 1_500_000)

    overview = html.Div(
        className="settings-overview-grid",
        children=[
            html.Div("主要功能：按 agent 查看 usage、token 预警阈值评估、关闭建议。", className="settings-overview-item"),
            html.Div("评估窗口：24h + 7d，来源于 /v1/usage/agents 聚合数据。", className="settings-overview-item"),
            html.Div("关闭建议：仅建议，不会自动停用 agent。", className="settings-overview-item"),
            html.Div("24h: 0 tokens · 7d: 0 tokens · 7d cost: $0.0000", className="settings-summary-line"),
            html.Div("No recent usage data available yet.", className="settings-summary-hint"),
        ],
    )

    if not is_open:
        return (
            "settings-modal",
            warn_24h,
            warn_7d,
            close_24h,
            close_7d,
            overview,
            [html.Div("Open 配置 to load assessment.", className="column-empty")],
            "",
            "settings-notice",
        )

    try:
        usage_rows = api_get_json("/v1/usage/agents?days=7", timeout=2.5)
    except Exception as e:
        msg = f"Unable to load usage assessment: {e}"
        return (
            "settings-modal open",
            warn_24h,
            warn_7d,
            close_24h,
            close_7d,
            overview,
            [html.Div(msg, className="column-empty")],
            msg,
            "settings-notice error",
        )

    rows = usage_rows if isinstance(usage_rows, list) else []
    rows_sorted = sorted(
        [row for row in rows if isinstance(row, dict)],
        key=lambda item: int(item.get("total_tokens_24h") or 0),
        reverse=True,
    )

    total_tokens_24h = sum(int(item.get("total_tokens_24h") or 0) for item in rows_sorted)
    total_tokens_7d = sum(int(item.get("total_tokens_window") or 0) for item in rows_sorted)
    total_cost_7d = sum(float(item.get("total_cost_window") or 0.0) for item in rows_sorted)
    missing_cost_entries = sum(int(item.get("missing_cost_entries_window") or 0) for item in rows_sorted)

    overview = html.Div(
        className="settings-overview-grid",
        children=[
            html.Div("主要功能：按 agent 查看 usage、token 预警阈值评估、关闭建议。", className="settings-overview-item"),
            html.Div("评估窗口：24h + 7d，来源于 /v1/usage/agents 聚合数据。", className="settings-overview-item"),
            html.Div("关闭建议：仅建议，不会自动停用 agent。", className="settings-overview-item"),
            html.Div(
                f"24h: {_format_token_compact(total_tokens_24h)} tokens · 7d: {_format_token_compact(total_tokens_7d)} tokens · 7d cost: ${total_cost_7d:.4f}",
                className="settings-summary-line",
            ),
            html.Div(
                _settings_summary_hint(total_tokens_7d, total_cost_7d, missing_cost_entries),
                className="settings-summary-hint",
            ),
        ],
    )

    by_slug = {str(item.get("slug")): item for item in _get_agent_catalog() if item.get("slug")}

    items = []
    for row in rows_sorted:
        slug = str(row.get("agent") or "-")
        tokens_24h = int(row.get("total_tokens_24h") or 0)
        tokens_7d = int(row.get("total_tokens_window") or 0)
        cost_7d = float(row.get("total_cost_window") or 0.0)
        missing_cost = int(row.get("missing_cost_entries_window") or 0)

        risk_text, risk_class, recommendation = _settings_risk_level(tokens_24h, tokens_7d, {
            "warn_24h": warn_24h,
            "warn_7d": warn_7d,
            "close_24h": close_24h,
            "close_7d": close_7d,
        })

        agent_info = by_slug.get(slug) or {}
        enabled_text = "enabled" if bool(agent_info.get("enabled", True)) else "disabled"

        cost_hint = ""
        if cost_7d <= 0 and (tokens_24h > 0 or tokens_7d > 0):
            cost_hint = " (cost likely not configured)"
        elif missing_cost > 0:
            cost_hint = f" (missing cost entries: {missing_cost})"

        items.append(
            html.Div(
                className="settings-item",
                children=[
                    html.Div(
                        className="settings-item-header",
                        children=[
                            html.Span(slug, className="settings-item-title"),
                            html.Span(enabled_text, className="settings-item-meta"),
                            html.Span(risk_text, className=f"settings-risk {risk_class}"),
                        ],
                    ),
                    html.Div(
                        f"24h: {_format_token_compact(tokens_24h)} tokens · 7d: {_format_token_compact(tokens_7d)} tokens · 7d cost: ${cost_7d:.4f}{cost_hint}",
                        className="settings-item-body",
                    ),
                    html.Div(f"关闭建议：{recommendation}", className="settings-item-hint"),
                    html.Div(
                        className="settings-item-actions",
                        children=[
                            html.Button(
                                "Start",
                                id={"type": "settings-agent-action", "agent": slug, "action": "start"},
                                className="ghost-button settings-action-btn",
                            ),
                            html.Button(
                                "Stop",
                                id={"type": "settings-agent-action", "agent": slug, "action": "stop"},
                                className="ghost-button settings-action-btn",
                            ),
                            html.Button(
                                "Restart",
                                id={"type": "settings-agent-action", "agent": slug, "action": "restart"},
                                className="ghost-button settings-action-btn",
                            ),
                        ],
                    ),
                ],
            )
        )

    if not items:
        items = [html.Div("No usage data found for agents.", className="column-empty")]

    message = str(state.get("message") or "")
    tone = str(state.get("message_tone") or "neutral")
    notice_class = "settings-notice"
    if tone in {"ok", "warn", "error"}:
        notice_class = f"settings-notice {tone}"

    return (
        "settings-modal open",
        warn_24h,
        warn_7d,
        close_24h,
        close_7d,
        overview,
        items,
        message,
        notice_class,
    )


@app.callback(
    Output("skills-ui", "data", allow_duplicate=True),
    Input("open-skills", "n_clicks"),
    Input("close-skills", "n_clicks"),
    State("skills-ui", "data"),
    prevent_initial_call=True,
)
def toggle_skills_modal(_, __, data):
    data = data or {"open": False, "revision": 0, "message": "", "message_tone": "neutral", "detail_agent": ""}
    trigger = ctx.triggered_id
    if trigger == "open-skills":
        data["open"] = True
        data["message"] = ""
        data["message_tone"] = "neutral"
        data["revision"] = int(data.get("revision") or 0) + 1
    elif trigger == "close-skills":
        data["open"] = False
    return data


@app.callback(
    Output("chat-ui", "data", allow_duplicate=True),
    Input("open-chat", "n_clicks"),
    Input("close-chat", "n_clicks"),
    Input("toggle-chat-max", "n_clicks"),
    Input("toggle-chat-panel", "n_clicks"),
    Input("chat-agent-select", "value"),
    State("chat-ui", "data"),
    prevent_initial_call=True,
)
def update_chat_ui(_, __, ___, ____, selected_agent, data):
    data = data or {
        "open": False,
        "selected_agent": "",
        "last_agent": "",
        "window_mode": "floating",
        "panel_mode": "split",
        "iframe_status": "idle",
        "error_message": "",
    }
    trigger = ctx.triggered_id

    agent_catalog = _get_agent_catalog()
    available_slugs = [str(item.get("slug")) for item in agent_catalog if item.get("slug") and item.get("enabled", True)]
    default_slug = data.get("last_agent") or (available_slugs[0] if available_slugs else "")

    if trigger == "open-chat":
        data["open"] = True
        data["selected_agent"] = str(data.get("selected_agent") or default_slug)
        data["last_agent"] = str(data.get("selected_agent") or default_slug)
        data["error_message"] = ""
        data["iframe_status"] = "loading"
        return data
    if trigger == "close-chat":
        data["open"] = False
        return data
    if trigger == "toggle-chat-max":
        current_mode = str(data.get("window_mode") or "floating")
        data["window_mode"] = "maximized" if current_mode != "maximized" else "floating"
        return data
    if trigger == "toggle-chat-panel":
        current_panel = str(data.get("panel_mode") or "split")
        data["panel_mode"] = "chat_only" if current_panel != "chat_only" else "split"
        return data
    if trigger == "chat-agent-select":
        chosen = str(selected_agent or "").strip()
        if chosen and chosen in available_slugs:
            data["selected_agent"] = chosen
            data["last_agent"] = chosen
            data["iframe_status"] = "loading"
            data["error_message"] = ""
        return data

    return data


@app.callback(
    Output("skills-ui", "data", allow_duplicate=True),
    Input("skills-add", "n_clicks"),
    Input("skills-remove", "n_clicks"),
    State("skills-global-checklist", "value"),
    State("skills-agent-checklist", "value"),
    State("skills-ui", "data"),
    prevent_initial_call=True,
)
def patch_skill_mappings(add_clicks, remove_clicks, skill_slugs, agent_slugs, data):
    _ = add_clicks
    _ = remove_clicks
    data = data or {"open": False, "revision": 0, "message": "", "message_tone": "neutral", "detail_agent": ""}
    trigger = ctx.triggered_id

    selected_skills = [s for s in (skill_slugs or []) if s]
    selected_agents = [a for a in (agent_slugs or []) if a]

    if not selected_skills or not selected_agents:
        data["message"] = "Select at least one global skill and one agent first."
        data["message_tone"] = "warn"
        return data

    body = {
        "agent_slugs": selected_agents,
        "add_skill_slugs": selected_skills if trigger == "skills-add" else [],
        "remove_skill_slugs": selected_skills if trigger == "skills-remove" else [],
    }

    try:
        resp = api_patch_json("/v1/skills/mappings", body)
        updated = int(resp.get("updated") or 0)
        failed = resp.get("failed") or []
        action = "added" if trigger == "skills-add" else "removed"
        base_message = (
            f"Saved. {updated} mapping change(s) applied ({action} {len(selected_skills)} skill(s) across "
            f"{len(selected_agents)} agent(s)). Restart affected agents to take effect."
        )
        failure_summary = _format_mapping_failure_summary(failed)
        data["message"] = f"{base_message} {failure_summary}".strip()
        data["message_tone"] = "ok"
        if failed and updated == 0:
            data["message_tone"] = "warn"
        if selected_agents:
            data["detail_agent"] = str(selected_agents[0])
        data["revision"] = int(data.get("revision") or 0) + 1
    except Exception as e:
        data["message"] = f"Update failed: {e}"
        data["message_tone"] = "error"
    return data


@app.callback(
    Output("skills-ui", "data", allow_duplicate=True),
    Input("skills-runtime-save", "n_clicks"),
    State("skills-detail-agent", "value"),
    State("skills-runtime-native-mode", "value"),
    State("skills-runtime-allow-bundled", "value"),
    State("skills-runtime-extra-dirs", "value"),
    State("skills-ui", "data"),
    prevent_initial_call=True,
)
def save_skill_runtime_config(_, detail_agent, native_mode, allow_bundled, extra_dirs, data):
    data = data or {"open": False, "revision": 0, "message": "", "message_tone": "neutral", "detail_agent": ""}
    agent_slug = str(detail_agent or "").strip()
    if not agent_slug:
        data["message"] = "Choose an agent before saving runtime config."
        data["message_tone"] = "warn"
        return data

    body = {
        "agent_slug": agent_slug,
        "native_skills_mode": str(native_mode or "").strip(),
        "allow_bundled": _parse_text_list(allow_bundled),
        "extra_dirs": _parse_text_list(extra_dirs),
    }

    try:
        resp = api_patch_json("/v1/skills/runtime-config", body, timeout=6.0)
        updated = bool(resp.get("updated"))
        restart_hint = str(resp.get("restart_hint") or "")
        drift = resp.get("drift") or []
        data["detail_agent"] = agent_slug
        data["message"] = (
            f"{agent_slug}: runtime config saved. {restart_hint}" if updated else f"{agent_slug}: {restart_hint}"
        )
        data["message_tone"] = "ok" if updated else "warn"
        if drift and not updated:
            data["message_tone"] = "warn"
        data["revision"] = int(data.get("revision") or 0) + 1
    except Exception as e:
        data["message"] = f"Runtime config update failed: {e}"
        data["message_tone"] = "error"

    return data


@app.callback(
    Output("skills-global-checklist", "value", allow_duplicate=True),
    Input("skills-global-select-all", "n_clicks"),
    Input("skills-global-clear", "n_clicks"),
    State("skills-global-checklist", "options"),
    State("skills-global-checklist", "value"),
    prevent_initial_call=True,
)
def bulk_select_global_skills(_, __, options, current):
    trigger = ctx.triggered_id
    if trigger == "skills-global-clear":
        return []
    if trigger == "skills-global-select-all":
        return [str(opt.get("value")) for opt in (options or []) if opt.get("value")]
    return current or []


@app.callback(
    Output("skills-agent-checklist", "value", allow_duplicate=True),
    Input("skills-agent-select-all", "n_clicks"),
    Input("skills-agent-clear", "n_clicks"),
    State("skills-agent-checklist", "options"),
    State("skills-agent-checklist", "value"),
    prevent_initial_call=True,
)
def bulk_select_agents(_, __, options, current):
    trigger = ctx.triggered_id
    if trigger == "skills-agent-clear":
        return []
    if trigger == "skills-agent-select-all":
        return [str(opt.get("value")) for opt in (options or []) if opt.get("value")]
    return current or []


@app.callback(
    Output("skills-detail-agent", "value"),
    Input("skills-detail-agent", "options"),
    Input("skills-ui", "data"),
    State("skills-detail-agent", "value"),
    State("skills-agent-checklist", "value"),
    prevent_initial_call=False,
)
def sync_skills_detail_agent(options, skills_ui, current_value, selected_agent_slugs):
    valid_values = [str(opt.get("value")) for opt in (options or []) if opt.get("value")]
    if not valid_values:
        return None

    current = str(current_value or "").strip()
    preferred = str((skills_ui or {}).get("detail_agent") or "").strip()
    selected_agents = [str(item) for item in (selected_agent_slugs or []) if item]

    if preferred and preferred in valid_values:
        return preferred
    if selected_agents:
        for agent_slug in selected_agents:
            if agent_slug in valid_values:
                return agent_slug
    if current in valid_values:
        return current
    return valid_values[0]


@app.callback(
    Output("skills-modal", "className"),
    Output("skills-global-checklist", "options"),
    Output("skills-global-checklist", "value"),
    Output("skills-agent-checklist", "options"),
    Output("skills-agent-checklist", "value"),
    Output("skills-detail-agent", "options"),
    Output("skills-overview", "children"),
    Output("skills-inventory-view", "children"),
    Output("skills-agent-detail-view", "children"),
    Output("skills-runtime-native-mode", "value"),
    Output("skills-runtime-allow-bundled", "value"),
    Output("skills-runtime-extra-dirs", "value"),
    Output("skills-report-view", "children"),
    Output("skills-selection-summary", "children"),
    Output("skills-notice", "children"),
    Output("skills-notice", "className"),
    Input("skills-ui", "data"),
    Input("skills-global-search", "value"),
    Input("skills-agent-search", "value"),
    Input("skills-detail-agent", "value"),
    State("skills-global-checklist", "value"),
    State("skills-agent-checklist", "value"),
    prevent_initial_call=False,
)
def render_skills_modal(skills_ui, global_search, agent_search, selected_detail_agent, selected_skill_slugs, selected_agent_slugs):
    skills_ui = skills_ui or {}
    is_open = bool(skills_ui.get("open"))

    if not is_open:
        return (
            "skills-modal",
            [],
            [],
            [],
            [],
            [],
            [html.Div("Open Skills to load overview.", className="column-empty")],
            [html.Div("Open Skills to load inventory.", className="column-empty")],
            [html.Div("Choose an agent to inspect skills and runtime config.", className="column-empty")],
            "",
            "",
            "",
            [html.Div("Open Skills to load report issues.", className="column-empty")],
            "Select one or more global skills and agents to prepare a batch change.",
            "",
            "skills-notice",
        )

    try:
        global_skills = api_get_json("/v1/skills/global")
        agent_details = api_get_json("/v1/skills/agents")
        inventory = api_get_json("/v1/skills/inventory")
        report = api_get_json("/v1/skills/report")
    except Exception as e:
        msg = f"Unable to load skills data: {e}"
        return (
            "skills-modal open",
            [],
            [],
            [],
            [],
            [],
            [html.Div(msg, className="column-empty")],
            [html.Div(msg, className="column-empty")],
            [html.Div(msg, className="column-empty")],
            "",
            "",
            "",
            [html.Div(msg, className="column-empty")],
            "",
            msg,
            "skills-notice error",
        )

    all_global_options = [
        {
            "label": f"{item.get('slug', '-')}: {item.get('description') or item.get('name') or ''}".strip(),
            "value": item.get("slug"),
        }
        for item in global_skills
        if item.get("slug")
    ]
    global_values_allowed = {opt["value"] for opt in all_global_options}
    selected_skill_slugs = [s for s in (selected_skill_slugs or []) if s in global_values_allowed]

    global_query = _normalize_text(global_search)
    global_options = [
        opt
        for opt in all_global_options
        if not global_query
        or global_query in _normalize_text(opt.get("label"))
        or global_query in _normalize_text(opt.get("value"))
    ]

    details = [item for item in (agent_details or []) if isinstance(item, dict)]
    detail_by_agent = {str(item.get("agent_slug")): item for item in details if item.get("agent_slug")}

    agent_pool = sorted(detail_by_agent.keys())
    if not agent_pool:
        agent_pool = [str(item.get("slug")) for item in _get_agent_catalog() if item.get("slug")]

    all_agent_options = [{"label": a, "value": a} for a in agent_pool]
    selected_agent_slugs = [a for a in (selected_agent_slugs or []) if a in set(agent_pool)]

    agent_query = _normalize_text(agent_search)
    agent_options = [
        opt
        for opt in all_agent_options
        if not agent_query
        or agent_query in _normalize_text(opt.get("label"))
        or agent_query in _normalize_text(opt.get("value"))
    ]

    detail_options = [
        {
            "label": str(detail.get("label") or detail.get("agent_slug") or "-"),
            "value": str(detail.get("agent_slug") or ""),
        }
        for detail in details
        if detail.get("agent_slug")
    ]

    chosen_detail_agent = str(selected_detail_agent or "").strip()
    if not chosen_detail_agent:
        chosen_detail_agent = str(skills_ui.get("detail_agent") or "").strip()
    if not chosen_detail_agent and selected_agent_slugs:
        chosen_detail_agent = str(selected_agent_slugs[0])
    valid_detail_values = {str(opt.get("value")) for opt in detail_options if opt.get("value")}
    if chosen_detail_agent not in valid_detail_values and detail_options:
        chosen_detail_agent = str(detail_options[0].get("value") or "")

    selected_detail = detail_by_agent.get(chosen_detail_agent) or {}
    runtime_config = selected_detail.get("runtime_config") or {}
    mapped_global_skills = selected_detail.get("mapped_global_skills") or []
    workspace_skills = selected_detail.get("workspace_skills") or []
    runtime_skills = selected_detail.get("runtime_skills") or []
    detail_drift = selected_detail.get("drift") or []

    overview_children = _render_metric_cards(report.get("metrics") or []) if isinstance(report, dict) else [html.Div("No report data available.", className="column-empty")]
    inventory_children = _render_inventory_children([item for item in (inventory or []) if isinstance(item, dict)])

    detail_children = []
    if selected_detail:
        detail_children = [
            html.Div(
                className="skills-item skills-item-emphasis",
                children=[
                    html.Div(
                        className="skills-item-head",
                        children=[
                            html.Div(str(selected_detail.get("label") or chosen_detail_agent or "-"), className="skills-item-title"),
                            html.Div(
                                [
                                    html.Span(str(chosen_detail_agent or "-"), className="skills-meta-chip"),
                                    html.Span(
                                        f"Drift {len(detail_drift)}",
                                        className=f"skills-meta-chip {_scope_badge_tone('runtime') if detail_drift else 'scope-neutral'}",
                                    ),
                                ],
                                className="skills-item-badges",
                            ),
                        ],
                    ),
                    html.Div(str(selected_detail.get("restart_hint") or ""), className="skills-item-copy"),
                    html.Div(str(runtime_config.get("config_path") or ""), className="skills-item-path"),
                ],
            ),
            html.Div(
                className="skills-detail-grid",
                children=[
                    html.Div(
                        className="skills-detail-section",
                        children=[
                            html.Div("Mapped Global Skills", className="skills-subsection-title"),
                            _render_skill_group(mapped_global_skills, empty_text="No mapped global skills."),
                        ],
                    ),
                    html.Div(
                        className="skills-detail-section",
                        children=[
                            html.Div("Workspace Skills", className="skills-subsection-title"),
                            _render_skill_group(workspace_skills, empty_text="No workspace skills."),
                        ],
                    ),
                    html.Div(
                        className="skills-detail-section",
                        children=[
                            html.Div("Runtime Skills", className="skills-subsection-title"),
                            _render_skill_group(runtime_skills, empty_text="No runtime skills discovered from extraDirs."),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="skills-detail-section",
                children=[
                    html.Div("Drift", className="skills-subsection-title"),
                    html.Div(_render_drift_children(detail_drift, empty_text="No drift detected for this agent."), className="skills-drift-list"),
                ],
            ),
        ]
    else:
        detail_children = [html.Div("Choose an agent to inspect skills and runtime config.", className="column-empty")]

    report_children = _render_drift_children(
        [item for item in (report.get("drift") or []) if isinstance(item, dict)] if isinstance(report, dict) else [],
        empty_text="No cross-agent drift issues detected.",
    )

    native_mode_value = str(runtime_config.get("native_skills_mode") or "")
    allow_bundled_value = "\n".join(str(item) for item in (runtime_config.get("allow_bundled") or []))
    extra_dirs_value = "\n".join(str(item) for item in (runtime_config.get("extra_dirs") or []))

    message = str(skills_ui.get("message") or "")
    tone = str(skills_ui.get("message_tone") or "neutral")
    notice_class = "skills-notice"
    if tone in {"ok", "warn", "error"}:
        notice_class = f"skills-notice {tone}"

    visible_global_count = len(global_options)
    total_global_count = len(all_global_options)
    visible_agent_count = len(agent_options)
    total_agent_count = len(all_agent_options)
    drift_total = int(report.get("drift_total") or 0) if isinstance(report, dict) else 0
    selection_summary = (
        f"Ready to apply: {len(selected_skill_slugs)} skill(s) × {len(selected_agent_slugs)} agent(s). "
        f"Visible now: {visible_global_count}/{total_global_count} global skills, "
        f"{visible_agent_count}/{total_agent_count} agents. Inspecting: {chosen_detail_agent or '-'} · Drift: {drift_total}."
    )

    return (
        "skills-modal open",
        global_options,
        selected_skill_slugs,
        agent_options,
        selected_agent_slugs,
        detail_options,
        overview_children,
        inventory_children,
        detail_children,
        native_mode_value,
        allow_bundled_value,
        extra_dirs_value,
        report_children,
        selection_summary,
        message,
        notice_class,
    )


@app.callback(
    Output("chat-modal", "className"),
    Output("chat-modal-card", "className"),
    Output("chat-modal-body", "className"),
    Output("chat-agent-select", "options"),
    Output("chat-agent-select", "value"),
    Output("chat-iframe", "src"),
    Output("chat-open-external", "href"),
    Output("chat-notice", "children"),
    Output("chat-notice", "className"),
    Output("toggle-chat-max", "children"),
    Output("toggle-chat-panel", "children"),
    Input("refresh", "n_intervals"),
    Input("chat-ui", "data"),
    prevent_initial_call=False,
)
def render_chat_modal(_, chat_ui):
    chat_ui = chat_ui or {}
    is_open = bool(chat_ui.get("open"))
    window_mode = str(chat_ui.get("window_mode") or "floating")
    panel_mode = str(chat_ui.get("panel_mode") or "split")

    agent_catalog = _get_agent_catalog()
    options = [
        {
            "label": f"{item.get('label') or item.get('slug')} ({item.get('slug')})",
            "value": item.get("slug"),
        }
        for item in agent_catalog
        if item.get("enabled", True) and item.get("slug")
    ]
    values = [str(opt.get("value")) for opt in options if opt.get("value")]

    selected = str(chat_ui.get("selected_agent") or chat_ui.get("last_agent") or "").strip()
    if selected not in values:
        selected = values[0] if values else ""

    by_slug = {str(item.get("slug")): item for item in agent_catalog if item.get("slug")}
    selected_config = by_slug.get(selected) or {}
    embed_url = str(selected_config.get("embed_path") or "")
    # Prefer the same-origin proxy path for external open as well.
    # Direct 188xx gateway URLs do not inject token into localStorage and will prompt for manual token paste.
    external_url = embed_url or (str(selected_config.get("direct_url") or "") or "#")
    iframe_src = embed_url or "about:blank"

    notice = ""
    notice_class = "chat-notice"
    if not options:
        notice = "No enabled agents discovered in manifest."
        notice_class = "chat-notice error"
    elif not external_url or external_url == "#":
        notice = "Selected agent has no chat URL mapping."
        notice_class = "chat-notice warn"
    else:
        notice = "Embedded chat is enabled. If your browser blocks in-frame rendering, click Open External."
        notice_class = "chat-notice ok"

    modal_class = "chat-modal open" if is_open else "chat-modal"
    card_classes = ["chat-modal-card"]
    body_classes = ["chat-modal-body"]
    if window_mode == "maximized":
        card_classes.append("maximized")
    if panel_mode == "chat_only":
        body_classes.append("chat-only")

    max_label = "Exit Max" if window_mode == "maximized" else "Maximize"
    panel_label = "Split View" if panel_mode == "chat_only" else "Chat Only"

    if not is_open:
        return (
            "chat-modal",
            "chat-modal-card",
            "chat-modal-body",
            options,
            selected or None,
            "about:blank",
            external_url,
            "",
            "chat-notice",
            max_label,
            panel_label,
        )

    return (
        modal_class,
        " ".join(card_classes),
        " ".join(body_classes),
        options,
        selected or None,
        iframe_src,
        external_url,
        notice,
        notice_class,
        max_label,
        panel_label,
    )


@app.callback(
    Output("board-filter-all", "className"),
    Output("board-filter-tasks", "className"),
    Output("feed-filter-all", "className"),
    Output("feed-filter-tasks", "className"),
    Output("feed-filter-comments", "className"),
    Output("feed-filter-chat", "className"),
    Output("feed-filter-system", "className"),
    Input("ui-state", "data"),
)
def sync_filter_chip_classes(state):
    state = state or {}
    board_filter = (state.get("board_filter") or "all").lower()
    feed_filter = (state.get("feed_filter") or "all").lower()
    return (
        _chip_class(board_filter, "all"),
        _chip_class(board_filter, "tasks"),
        _chip_class(feed_filter, "all"),
        _chip_class(feed_filter, "tasks"),
        _chip_class(feed_filter, "comments"),
        _chip_class(feed_filter, "chat"),
        _chip_class(feed_filter, "system"),
    )


@app.callback(
    Output("agents", "children"),
    Output("board", "children"),
    Output("feed", "children"),
    Output("stat-agents", "children"),
    Output("stat-tasks", "children"),
    Output("stat-error-rate", "children"),
    Output("stat-event-backlog", "children"),
    Output("stat-task-throughput", "children"),
    Output("stat-health-ratio", "children"),
    Output("stat-card-error-rate", "className"),
    Output("stat-card-event-backlog", "className"),
    Output("stat-card-task-throughput", "className"),
    Output("stat-card-health-ratio", "className"),
    Output("agents-count", "children"),
    Output("api-status", "children"),
    Output("api-status", "className"),
    Input("refresh", "n_intervals"),
    Input("ui-state", "data"),
    prevent_initial_call=False,
)
def refresh_data(n_intervals, state):
    _ = n_intervals
    state = state or {}
    board_filter = (state.get("board_filter") or "all").lower()
    feed_filter = (state.get("feed_filter") or "all").lower()

    try:
        board_json = api_get_json("/v1/boards/default")
        feed_json = api_get_json("/v1/feed-lite?limit=80")
        agent_catalog = _get_agent_catalog(force_refresh=True)
        usage_by_agent = {}
        try:
            usage_rows = api_get_json("/v1/usage/agents?days=7", timeout=2.0)
            if isinstance(usage_rows, list):
                for row in usage_rows:
                    if isinstance(row, dict):
                        slug = str(row.get("agent") or "").strip()
                        if slug:
                            usage_by_agent[slug] = row
        except Exception:
            usage_by_agent = {}

        columns = _convert_board(board_json)
        feed = _convert_feed(feed_json)
        agents = _build_agents(board_json, feed_json, usage_by_agent, agent_catalog)

        visible_columns = _filter_board(columns, board_filter)
        visible_feed = _filter_feed(feed, feed_filter)

        tasks_total = sum(int(c.get("count") or 0) for c in columns)
        error_rate_text = "-"
        event_backlog_text = "-"
        task_throughput_text = "-"
        health_ratio_text = "-"
        error_rate_class = "stat stat-observability-card"
        event_backlog_class = "stat stat-observability-card"
        task_throughput_class = "stat stat-observability-card"
        health_ratio_class = "stat stat-observability-card"

        try:
            obs = api_get_json("/v1/observability/summary?window_minutes=5", timeout=2.0)
            if isinstance(obs, dict):
                error_rate = float(obs.get("error_rate") or 0.0) * 100.0
                event_backlog = int(obs.get("event_backlog_total") or 0)
                task_tp = float(obs.get("task_throughput_per_min") or 0.0)
                healthy = int(obs.get("healthy_agents") or 0)
                total = int(obs.get("total_agents") or 0)
                health_ratio = float(obs.get("agent_health_ratio") or 0.0) * 100.0

                error_rate_text = f"{error_rate:.1f}%"
                event_backlog_text = str(event_backlog)
                task_throughput_text = f"{task_tp:.1f}/m"
                health_ratio_text = f"{healthy}/{total} · {health_ratio:.0f}%" if total > 0 else "0/0 · 0%"

                error_rate_class = _stat_class_high_bad(
                    error_rate,
                    OBS_ERROR_RATE_WARN_PCT,
                    OBS_ERROR_RATE_CRIT_PCT,
                ) + " stat-observability-card"
                event_backlog_class = _stat_class_high_bad(
                    float(event_backlog),
                    float(OBS_EVENT_BACKLOG_WARN),
                    float(OBS_EVENT_BACKLOG_CRIT),
                ) + " stat-observability-card"
                task_throughput_class = _stat_class_low_bad(
                    task_tp,
                    OBS_TASK_THROUGHPUT_WARN_PER_MIN,
                    OBS_TASK_THROUGHPUT_CRIT_PER_MIN,
                ) + " stat-observability-card"
                health_ratio_class = _stat_class_low_bad(
                    float(obs.get("agent_health_ratio") or 0.0),
                    OBS_HEALTH_RATIO_WARN,
                    OBS_HEALTH_RATIO_CRIT,
                ) + " stat-observability-card"
        except Exception:
            pass

        try:
            health_summary = api_get_json("/v1/observability/container-health", timeout=2.0)
            if isinstance(health_summary, dict):
                overall_ok = int(health_summary.get("overall_ok") or 0)
                overall_total = int(health_summary.get("overall_total") or 0)
                overall_ratio = float(health_summary.get("overall_ratio") or 0.0)
                if overall_total > 0:
                    health_ratio_text = f"{overall_ok}/{overall_total} · {overall_ratio * 100.0:.0f}%"
                    health_ratio_class = _stat_class_low_bad(
                        overall_ratio,
                        OBS_HEALTH_RATIO_WARN,
                        OBS_HEALTH_RATIO_CRIT,
                    ) + " stat-observability-card"
        except Exception:
            pass

        now_text = datetime.now().strftime("%H:%M:%S")

        agents_children = [agent_card(a) for a in agents] or [
            html.Div("No agents", className="column-empty")
        ]
        board_children = [column(c) for c in visible_columns] or [
            html.Div("No columns", className="column-empty")
        ]
        feed_children = [feed_item(i) for i in visible_feed] or [
            html.Div("No feed", className="column-empty")
        ]

        return (
            agents_children,
            board_children,
            feed_children,
            str(len(agents)),
            str(tasks_total),
            error_rate_text,
            event_backlog_text,
            task_throughput_text,
            health_ratio_text,
            error_rate_class,
            event_backlog_class,
            task_throughput_class,
            health_ratio_class,
            str(len(agents)),
            _format_api_status(True, now_text),
            "status-pill status-online",
        )
    except Exception as e:
        return (
            [html.Div("API unavailable", className="column-empty")],
            [html.Div("API unavailable", className="column-empty")],
            [html.Div("API unavailable", className="column-empty")],
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "stat",
            "stat",
            "stat",
            "stat",
            "-",
            _format_api_status(False, "", e),
            "status-pill status-offline",
        )

_ensure_ws_thread_started()


if __name__ == "__main__":
    debug = (os.getenv("DASH_DEBUG") or "").strip().lower() in {"1", "true", "yes"}
    port_raw = (os.getenv("PORT") or os.getenv("DASH_PORT") or "9090").strip()
    try:
        port = int(port_raw)
    except ValueError:
        port = 9090
    app.run(host="0.0.0.0", port=port, debug=debug)
