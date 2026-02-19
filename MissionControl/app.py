import os
import re
import threading
import time
from urllib.parse import parse_qs, urlencode
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
import websocket
from dash import Dash, Input, Output, State, ctx, dcc, html, no_update
from flask import Response, request

APP_TITLE = "Mission Control"

MISSION_CONTROL_API_URL = os.getenv("MISSION_CONTROL_API_URL") or "http://localhost:18910"
MISSION_CONTROL_AGENT_MANIFEST_PATH = os.getenv("MISSION_CONTROL_AGENT_MANIFEST_PATH") or "/app/panopticon_agents.manifest.yaml"
MISSION_CONTROL_AGENT_SLUGS = os.getenv("MISSION_CONTROL_AGENT_SLUGS") or ""
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
MISSION_CONTROL_CHAT_CONTAINER_GATEWAY_PORT = int((os.getenv("MISSION_CONTROL_CHAT_CONTAINER_GATEWAY_PORT") or "26216").strip())
MISSION_CONTROL_CHAT_AUTH_SCHEME = (os.getenv("MISSION_CONTROL_CHAT_AUTH_SCHEME") or "Bearer").strip() or "Bearer"
MISSION_CONTROL_CHAT_AGENT_TOKEN_MAP = (os.getenv("MISSION_CONTROL_CHAT_AGENT_TOKEN_MAP") or "").strip()


def _load_static_agent_names() -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    env_names = [part.strip() for part in MISSION_CONTROL_AGENT_SLUGS.split(",") if part.strip()]
    for name in env_names:
        if name not in seen:
            seen.add(name)
            names.append(name)

    manifest_path = MISSION_CONTROL_AGENT_MANIFEST_PATH.strip()
    if not manifest_path:
        return names

    if not os.path.exists(manifest_path):
        return names

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                match = re.match(r"^\s*-\s*slug\s*:\s*([A-Za-z0-9_-]+)\s*$", line)
                if not match:
                    continue
                slug = match.group(1).strip()
                if slug and slug not in seen:
                    seen.add(slug)
                    names.append(slug)
    except OSError:
        return names

    return names


STATIC_AGENT_NAMES = _load_static_agent_names()


def _slug_label(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title() or slug


def _is_placeholder_token(token: str | None) -> bool:
    raw = str(token or "").strip()
    if not raw:
        return True
    upper = raw.upper()
    return upper.startswith("CHANGE_ME") or upper in {"TODO", "REPLACE_ME", "YOUR_TOKEN"}


def _parse_agent_token_overrides(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    text = (raw or "").strip()
    if not text:
        return out
    for chunk in re.split(r"[;,\n]", text):
        item = chunk.strip()
        if not item:
            continue
        if "=" in item:
            slug, token = item.split("=", 1)
        elif ":" in item:
            slug, token = item.split(":", 1)
        else:
            continue
        slug_key = slug.strip()
        token_val = token.strip()
        if not slug_key or _is_placeholder_token(token_val):
            continue
        out[slug_key] = token_val
    return out


CHAT_AGENT_TOKEN_OVERRIDES = _parse_agent_token_overrides(MISSION_CONTROL_CHAT_AGENT_TOKEN_MAP)


def _load_chat_agent_configs() -> list[dict]:
    configs: list[dict] = []
    seen: set[str] = set()

    manifest_path = MISSION_CONTROL_AGENT_MANIFEST_PATH.strip()
    if manifest_path and os.path.exists(manifest_path):
        current: dict | None = None
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    slug_match = re.match(r"^-\s*slug\s*:\s*([A-Za-z0-9_-]+)$", line)
                    if slug_match:
                        if current and current.get("slug"):
                            configs.append(current)
                        current = {
                            "slug": slug_match.group(1).strip(),
                            "enabled": True,
                            "gateway_host_port": None,
                            "bridge_host_port": None,
                            "gateway_token": "",
                        }
                        continue
                    if current is None:
                        continue
                    enabled_match = re.match(r"^enabled\s*:\s*(true|false)$", line, flags=re.IGNORECASE)
                    if enabled_match:
                        current["enabled"] = enabled_match.group(1).lower() == "true"
                        continue
                    gateway_match = re.match(r"^gateway_host_port\s*:\s*([0-9]+)$", line)
                    if gateway_match:
                        current["gateway_host_port"] = int(gateway_match.group(1))
                        continue
                    bridge_match = re.match(r"^bridge_host_port\s*:\s*([0-9]+)$", line)
                    if bridge_match:
                        current["bridge_host_port"] = int(bridge_match.group(1))
                        continue
                    token_match = re.match(r"^gateway_token\s*:\s*(.+)$", line)
                    if token_match:
                        token_text = token_match.group(1).strip().strip('"').strip("'")
                        current["gateway_token"] = token_text
            if current and current.get("slug"):
                configs.append(current)
        except OSError:
            configs = []

    out: list[dict] = []
    inside_docker = os.path.exists("/.dockerenv")
    for idx, item in enumerate(configs):
        slug = str(item.get("slug") or "").strip()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        gateway_port = item.get("gateway_host_port")
        bridge_port = item.get("bridge_host_port")
        token_candidate = CHAT_AGENT_TOKEN_OVERRIDES.get(slug) or str(item.get("gateway_token") or "").strip()
        gateway_token = "" if _is_placeholder_token(token_candidate) else token_candidate
        if gateway_port is None:
            gateway_port = 18801 + idx * 10
        out.append(
            {
                "slug": slug,
                "label": _slug_label(slug),
                "enabled": bool(item.get("enabled", True)),
                "chat_url": f"http://{MISSION_CONTROL_CHAT_HOST}:{int(gateway_port)}",
                "proxy_target_url": (
                    f"http://openclaw-{slug}:{MISSION_CONTROL_CHAT_CONTAINER_GATEWAY_PORT}"
                    if inside_docker
                    else f"http://{MISSION_CONTROL_CHAT_HOST}:{int(gateway_port)}"
                ),
                "bridge_url": f"tcp://{MISSION_CONTROL_CHAT_HOST}:{int(bridge_port)}" if bridge_port else "",
                "health_url": f"http://{MISSION_CONTROL_CHAT_HOST}:{int(gateway_port)}",
                "gateway_token": gateway_token,
                "open_mode": "iframe",
                "order": idx,
            }
        )

    if out:
        return [item for item in out if item.get("enabled", True)]

    fallback = []
    for idx, slug in enumerate(STATIC_AGENT_NAMES):
        gateway_port = 18801 + idx * 10
        bridge_port = gateway_port + 1
        token_candidate = CHAT_AGENT_TOKEN_OVERRIDES.get(slug) or ""
        gateway_token = "" if _is_placeholder_token(token_candidate) else token_candidate
        fallback.append(
            {
                "slug": slug,
                "label": _slug_label(slug),
                "enabled": True,
                "chat_url": f"http://{MISSION_CONTROL_CHAT_HOST}:{gateway_port}",
                "proxy_target_url": (
                    f"http://openclaw-{slug}:{MISSION_CONTROL_CHAT_CONTAINER_GATEWAY_PORT}"
                    if inside_docker
                    else f"http://{MISSION_CONTROL_CHAT_HOST}:{gateway_port}"
                ),
                "bridge_url": f"tcp://{MISSION_CONTROL_CHAT_HOST}:{bridge_port}",
                "health_url": f"http://{MISSION_CONTROL_CHAT_HOST}:{gateway_port}",
                "gateway_token": gateway_token,
                "open_mode": "iframe",
                "order": idx,
            }
        )
    return fallback


CHAT_AGENT_CONFIGS = _load_chat_agent_configs()
CHAT_AGENT_URL_MAP = {item["slug"]: item["chat_url"] for item in CHAT_AGENT_CONFIGS if item.get("slug")}
CHAT_AGENT_PROXY_TARGET_URL_MAP = {
    item["slug"]: item.get("proxy_target_url") or item["chat_url"]
    for item in CHAT_AGENT_CONFIGS
    if item.get("slug")
}
CHAT_AGENT_TOKEN_MAP = {
    item["slug"]: str(item.get("gateway_token") or "").strip()
    for item in CHAT_AGENT_CONFIGS
    if item.get("slug") and str(item.get("gateway_token") or "").strip()
}
CHAT_AGENT_EMBED_URL_MAP = {item["slug"]: f"/chat/{item['slug']}/" for item in CHAT_AGENT_CONFIGS if item.get("slug")}


WS_LOCK = threading.Lock()
WS_STATE = {
    "connected": False,
    "revision": 0,
    "last_error": "",
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
        }


def _ws_headers() -> list[str]:
    if not MISSION_CONTROL_AUTH_TOKEN:
        return []
    return [f"Authorization: Bearer {MISSION_CONTROL_AUTH_TOKEN}"]


def _ws_subscriber_loop():
    ws_url = _build_ws_url()
    headers = _ws_headers()

    while True:
        try:
            ws_app = websocket.WebSocketApp(
                ws_url,
                header=headers,
                on_open=lambda _ws: _update_ws_state(connected=True, last_error=""),
                on_message=lambda _ws, _msg: _bump_ws_revision(),
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


def _build_agents(board: dict, feed: list[dict]) -> list[dict]:
    names: set[str] = set(STATIC_AGENT_NAMES)
    last_seen: dict[str, datetime] = {}

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
        agents.append(
            {
                "name": name,
                "role": role,
                "badge": "AGENT",
                "status": status,
                "tag": "AGENT",
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
            payload = {}

        category = "system"
        if evt_type.startswith("task."):
            category = "tasks"
        elif evt_type.startswith("comment."):
            category = "comments"

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
    allowed = {"all", "tasks", "comments", "system"}
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


def _rewrite_location_for_proxy(location_value: str, agent_slug: str, upstream_base: str) -> str:
    if not location_value:
        return location_value
    base = upstream_base.rstrip("/")
    prefix = f"/chat/{agent_slug}"
    if location_value.startswith(base):
        tail = location_value[len(base):]
        if not tail.startswith("/"):
            tail = "/" + tail
        return f"{prefix}{tail}"
    if location_value.startswith("/"):
        return f"{prefix}{location_value}"
    return location_value


@app.server.route("/chat/<agent_slug>/", defaults={"proxy_path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
@app.server.route("/chat/<agent_slug>/<path:proxy_path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
def chat_reverse_proxy(agent_slug: str, proxy_path: str):
    upstream_base = CHAT_AGENT_PROXY_TARGET_URL_MAP.get(agent_slug)
    if not upstream_base:
        return Response("Unknown agent", status=404)

    upstream = upstream_base.rstrip("/") + "/"
    if proxy_path:
        upstream += proxy_path.lstrip("/")

    query_string = request.query_string.decode("utf-8", errors="ignore")
    if query_string:
        upstream = f"{upstream}?{query_string}"

    skip_headers = {"host", "content-length", "connection"}
    forward_headers = {}
    for key, value in request.headers.items():
        if key.lower() in skip_headers:
            continue
        forward_headers[key] = value

    token = CHAT_AGENT_TOKEN_MAP.get(agent_slug, "").strip()
    if token:
        auth_value = token if token.lower().startswith("bearer ") else f"{MISSION_CONTROL_CHAT_AUTH_SCHEME} {token}"
        forward_headers["Authorization"] = auth_value

    body = request.get_data() if request.method in {"POST", "PUT", "PATCH", "DELETE"} else None

    try:
        upstream_resp = requests.request(
            method=request.method,
            url=upstream,
            headers=forward_headers,
            data=body,
            cookies=request.cookies,
            allow_redirects=False,
            timeout=20,
        )
    except Exception as e:
        return Response(f"Upstream unavailable: {e}", status=502)

    excluded_resp_headers = {
        "content-length",
        "transfer-encoding",
        "content-encoding",
        "connection",
        "x-frame-options",
        "content-security-policy",
    }

    resp = Response(upstream_resp.content, status=upstream_resp.status_code)
    for key, value in upstream_resp.headers.items():
        lk = key.lower()
        if lk in excluded_resp_headers:
            continue
        if lk == "location":
            value = _rewrite_location_for_proxy(value, agent_slug, upstream_base)
        resp.headers[key] = value

    return resp

app.layout = html.Div(
    className="page",
    children=[
        dcc.Location(id="url", refresh=False),
        dcc.Interval(id="refresh", interval=5_000, n_intervals=0),
        dcc.Interval(id="ws-tick", interval=1_000, n_intervals=0),
        dcc.Interval(id="clock-tick", interval=1_000, n_intervals=0),
        dcc.Store(
            id="ui-state",
            data={
                "board_filter": "all",
                "feed_filter": "all",
            },
        ),
        dcc.Store(
            id="ws-meta",
            data={
                "revision": 0,
            },
        ),
        dcc.Store(
            id="skills-ui",
            data={
                "open": False,
                "revision": 0,
                "message": "",
                "message_tone": "neutral",
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
        html.Div(
            className="topbar",
            children=[
                html.Div(
                    className="brand",
                    children=[
                        html.Span("Mission Control", className="brand-title"),
                        html.Span("SiteGPT", className="brand-chip"),
                    ],
                ),
                html.Div(
                    className="stats",
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
                        html.Div("-", id="api-status", className="status-pill status-unknown"),
                        html.Div("--:--:--", id="clock", className="clock"),
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
                        html.Div(
                            className="skills-grid",
                            children=[
                                html.Div(
                                    className="skills-col",
                                    children=[
                                        html.Div("Global Skills", className="skills-col-title"),
                                        dcc.Checklist(id="skills-global-checklist", options=[], value=[]),
                                    ],
                                ),
                                html.Div(
                                    className="skills-col",
                                    children=[
                                        html.Div("Agents (multi-select)", className="skills-col-title"),
                                        dcc.Checklist(id="skills-agent-checklist", options=[], value=[]),
                                        html.Div(
                                            className="skills-actions",
                                            children=[
                                                html.Button("Add Skills", id="skills-add", className="ghost-button"),
                                                html.Button("Remove Skills", id="skills-remove", className="ghost-button"),
                                            ],
                                        ),
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
                                        html.Div("Assigned Global Skills", className="skills-col-title"),
                                        html.Div(id="skills-mapping-view", className="skills-scroll"),
                                    ],
                                ),
                                html.Div(
                                    className="skills-list-block",
                                    children=[
                                        html.Div("Workspace Skills (agent-homes/<agent>/skills)", className="skills-col-title"),
                                        html.Div(id="skills-workspace-view", className="skills-scroll"),
                                    ],
                                ),
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
                                            "For security, Mission Control does not inject gateway tokens. Login/pair in the target chat page if prompted.",
                                            className="chat-hint",
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="chat-main",
                                    children=[
                                        html.Iframe(id="chat-iframe", src="about:blank", className="chat-iframe"),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ],
)


@app.callback(Output("clock", "children"), Input("clock-tick", "n_intervals"))
def update_clock(_):
    return datetime.now().strftime("%H:%M:%S")


@app.callback(
    Output("ui-state", "data"),
    Input("url", "search"),
    Input("board-filter-all", "n_clicks"),
    Input("board-filter-tasks", "n_clicks"),
    Input("feed-filter-all", "n_clicks"),
    Input("feed-filter-tasks", "n_clicks"),
    Input("feed-filter-comments", "n_clicks"),
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
    Output("ws-meta", "data"),
    Input("ws-tick", "n_intervals"),
    State("ws-meta", "data"),
)
def poll_ws_meta(_, current):
    current = current or {"revision": 0}
    ws_state = _get_ws_state()
    revision = int(ws_state.get("revision") or 0)
    if int(current.get("revision") or 0) == revision:
        return no_update
    return {"revision": revision}


@app.callback(
    Output("skills-ui", "data", allow_duplicate=True),
    Input("open-skills", "n_clicks"),
    Input("close-skills", "n_clicks"),
    State("skills-ui", "data"),
    prevent_initial_call=True,
)
def toggle_skills_modal(_, __, data):
    data = data or {"open": False, "revision": 0, "message": "", "message_tone": "neutral"}
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

    available_slugs = [str(item.get("slug")) for item in CHAT_AGENT_CONFIGS if item.get("slug")]
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
    data = data or {"open": False, "revision": 0, "message": "", "message_tone": "neutral"}
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
        data["message"] = f"Saved. {updated} mapping change(s) applied. Restart affected agents to take effect."
        data["message_tone"] = "ok"
        data["revision"] = int(data.get("revision") or 0) + 1
    except Exception as e:
        data["message"] = f"Update failed: {e}"
        data["message_tone"] = "error"
    return data


@app.callback(
    Output("skills-modal", "className"),
    Output("skills-global-checklist", "options"),
    Output("skills-global-checklist", "value"),
    Output("skills-agent-checklist", "options"),
    Output("skills-agent-checklist", "value"),
    Output("skills-mapping-view", "children"),
    Output("skills-workspace-view", "children"),
    Output("skills-notice", "children"),
    Output("skills-notice", "className"),
    Input("refresh", "n_intervals"),
    Input("skills-ui", "data"),
    State("skills-global-checklist", "value"),
    State("skills-agent-checklist", "value"),
    prevent_initial_call=False,
)
def render_skills_modal(_, skills_ui, selected_skill_slugs, selected_agent_slugs):
    skills_ui = skills_ui or {}
    is_open = bool(skills_ui.get("open"))

    if not is_open:
        return (
            "skills-modal",
            [],
            [],
            [],
            [],
            html.Div("Open Skills to load mappings.", className="column-empty"),
            html.Div("Open Skills to load workspace skills.", className="column-empty"),
            "",
            "skills-notice",
        )

    try:
        global_skills = api_get_json("/v1/skills/global")
        workspace_groups = api_get_json("/v1/skills/workspace")
        mappings = api_get_json("/v1/skills/mappings")
    except Exception as e:
        msg = f"Unable to load skills data: {e}"
        return (
            "skills-modal open",
            [],
            [],
            [],
            [],
            html.Div(msg, className="column-empty"),
            html.Div(msg, className="column-empty"),
            msg,
            "skills-notice error",
        )

    global_options = [
        {
            "label": f"{item.get('slug', '-')}: {item.get('description') or item.get('name') or ''}".strip(),
            "value": item.get("slug"),
        }
        for item in global_skills
        if item.get("slug")
    ]
    global_values_allowed = {opt["value"] for opt in global_options}
    selected_skill_slugs = [s for s in (selected_skill_slugs or []) if s in global_values_allowed]

    agent_pool = sorted({str(m.get("agent_slug")) for m in mappings if m.get("agent_slug")})
    if not agent_pool:
        agent_pool = sorted({str(g.get("agent_slug")) for g in workspace_groups if g.get("agent_slug")})
    if not agent_pool:
        agent_pool = list(STATIC_AGENT_NAMES)

    agent_options = [{"label": a, "value": a} for a in agent_pool]
    selected_agent_slugs = [a for a in (selected_agent_slugs or []) if a in set(agent_pool)]

    mapping_by_agent: dict[str, list[str]] = {}
    for row in mappings:
        agent = str(row.get("agent_slug") or "")
        skill = str(row.get("skill_slug") or "")
        if not agent or not skill:
            continue
        mapping_by_agent.setdefault(agent, []).append(skill)
    for agent in mapping_by_agent:
        mapping_by_agent[agent] = sorted(set(mapping_by_agent[agent]))

    focused_agents = selected_agent_slugs or sorted(mapping_by_agent.keys())[:8]
    if focused_agents:
        mapping_children = []
        for agent in focused_agents:
            skills = mapping_by_agent.get(agent) or []
            mapping_children.append(
                html.Div(
                    className="skills-item",
                    children=[
                        html.Div(agent, className="skills-item-title"),
                        html.Div(
                            [html.Span(s, className="tag") for s in skills] if skills else "No mapped global skills",
                            className="skills-item-body",
                        ),
                    ],
                )
            )
    else:
        mapping_children = [html.Div("No agents selected.", className="column-empty")]

    workspace_children = []
    for group in workspace_groups:
        agent = group.get("agent_slug")
        skills = group.get("skills") or []
        skill_slugs = [str(s.get("slug")) for s in skills if s.get("slug")]
        workspace_children.append(
            html.Div(
                className="skills-item",
                children=[
                    html.Div(str(agent), className="skills-item-title"),
                    html.Div(
                        [html.Span(s, className="tag") for s in skill_slugs] if skill_slugs else "No workspace skills",
                        className="skills-item-body",
                    ),
                ],
            )
        )
    if not workspace_children:
        workspace_children = [html.Div("No workspace agents discovered.", className="column-empty")]

    message = str(skills_ui.get("message") or "")
    tone = str(skills_ui.get("message_tone") or "neutral")
    notice_class = "skills-notice"
    if tone in {"ok", "warn", "error"}:
        notice_class = f"skills-notice {tone}"

    return (
        "skills-modal open",
        global_options,
        selected_skill_slugs,
        agent_options,
        selected_agent_slugs,
        mapping_children,
        workspace_children,
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

    options = [
        {
            "label": f"{item.get('label') or item.get('slug')} ({item.get('slug')})",
            "value": item.get("slug"),
        }
        for item in CHAT_AGENT_CONFIGS
        if item.get("enabled", True) and item.get("slug")
    ]
    values = [str(opt.get("value")) for opt in options if opt.get("value")]

    selected = str(chat_ui.get("selected_agent") or chat_ui.get("last_agent") or "").strip()
    if selected not in values:
        selected = values[0] if values else ""

    embed_url = CHAT_AGENT_EMBED_URL_MAP.get(selected, "")
    # Prefer the same-origin proxy path for external open as well.
    # Direct 188xx gateway URLs do not inject token into localStorage and will prompt for manual token paste.
    external_url = embed_url or (CHAT_AGENT_URL_MAP.get(selected, "") or "#")
    probe_url = CHAT_AGENT_PROXY_TARGET_URL_MAP.get(selected, "")
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
        try:
            resp = requests.get(probe_url or external_url, timeout=2.0)
            if 200 <= resp.status_code < 400:
                notice = "Embedded chat via same-origin proxy is enabled. If target flow blocks in-frame, click Open External."
                notice_class = "chat-notice ok"
            else:
                notice = f"Agent endpoint reachable with HTTP {resp.status_code}. If embed fails, use Open External."
                notice_class = "chat-notice warn"
        except Exception:
            notice = "Agent endpoint appears offline from Mission Control. Check container status or use Open External."
            notice_class = "chat-notice error"

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
        _chip_class(feed_filter, "system"),
    )


@app.callback(
    Output("agents", "children"),
    Output("board", "children"),
    Output("feed", "children"),
    Output("stat-agents", "children"),
    Output("stat-tasks", "children"),
    Output("agents-count", "children"),
    Output("api-status", "children"),
    Output("api-status", "className"),
    Input("refresh", "n_intervals"),
    Input("ws-meta", "data"),
    Input("ui-state", "data"),
    prevent_initial_call=False,
)
def refresh_data(n_intervals, ws_meta, state):
    _ = n_intervals
    _ = ws_meta
    state = state or {}
    board_filter = (state.get("board_filter") or "all").lower()
    feed_filter = (state.get("feed_filter") or "all").lower()

    try:
        board_json = api_get_json("/v1/boards/default")
        feed_json = api_get_json("/v1/feed?limit=50")

        columns = _convert_board(board_json)
        feed = _convert_feed(feed_json)
        agents = _build_agents(board_json, feed_json)

        visible_columns = _filter_board(columns, board_filter)
        visible_feed = _filter_feed(feed, feed_filter)

        tasks_total = sum(int(c.get("count") or 0) for c in columns)
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
