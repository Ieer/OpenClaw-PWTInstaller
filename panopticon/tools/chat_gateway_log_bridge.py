#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any

LOG_FILE = Path(os.getenv("MC_CHAT_GATEWAY_LOG_FILE") or "/var/log/nginx/chat_access.log")
API_BASE = (os.getenv("MC_API_URL") or "http://mission-control-api:9090").rstrip("/")
AUTH_TOKEN = (os.getenv("MC_AUTH_TOKEN") or "").strip()
POLL_SECONDS = float(os.getenv("MC_CHAT_BRIDGE_POLL_SECONDS") or "0.5")
START_MODE = (os.getenv("MC_CHAT_BRIDGE_START_MODE") or "tail").strip().lower()
MAX_RECENT_KEYS = int(os.getenv("MC_CHAT_BRIDGE_MAX_RECENT_KEYS") or "2000")

CHAT_URI_RE = re.compile(r"^/chat/(?P<agent>[a-zA-Z0-9_-]+)/?(?P<rest>.*)$")


def _post_event(event: dict[str, Any]) -> tuple[bool, str]:
    payload = json.dumps(event, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"

    req = urllib.request.Request(
        url=f"{API_BASE}/v1/events",
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            return 200 <= int(resp.status) < 300, f"status={resp.status}"
    except urllib.error.HTTPError as exc:
        return False, f"http={exc.code}"
    except Exception as exc:
        return False, f"error={exc.__class__.__name__}"


def _extract_event(log_obj: dict[str, Any]) -> dict[str, Any] | None:
    uri = str(log_obj.get("uri") or "")
    match = CHAT_URI_RE.match(uri)
    if not match:
        return None

    agent = match.group("agent")
    rest = match.group("rest") or ""
    status = int(log_obj.get("status") or 0)
    method = str(log_obj.get("method") or "GET")
    request_time = str(log_obj.get("request_time") or "")
    upstream_status = str(log_obj.get("upstream_status") or "")
    upgrade = str(log_obj.get("upgrade") or "").lower() == "websocket"
    query = str(log_obj.get("query") or "")

    path = "/" + rest.lstrip("/") if rest else "/"

    payload = {
        "path": path,
        "query": query[:256],
        "method": method,
        "status_code": status,
        "request_time": request_time,
        "upstream_status": upstream_status,
        "is_ws_upgrade": upgrade,
        "source": "gateway_log_bridge",
        "ts": str(log_obj.get("time_iso") or datetime.now(timezone.utc).isoformat()),
    }

    return {
        "type": "chat.gateway.access",
        "agent": agent,
        "payload": payload,
    }


def _line_key(text: str) -> str:
    return sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def tail_log_file() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_FILE.exists():
        LOG_FILE.touch()

    recent_keys: deque[str] = deque(maxlen=MAX_RECENT_KEYS)
    recent_set: set[str] = set()

    with LOG_FILE.open("r", encoding="utf-8", errors="replace") as f:
        if START_MODE == "tail":
            f.seek(0, 2)

        while True:
            line = f.readline()
            if not line:
                time.sleep(POLL_SECONDS)
                continue

            line = line.strip()
            if not line:
                continue

            key = _line_key(line)
            if key in recent_set:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            event = _extract_event(obj)
            if not event:
                continue

            ok, msg = _post_event(event)
            if ok:
                recent_keys.append(key)
                recent_set.add(key)
                while len(recent_set) > MAX_RECENT_KEYS and recent_keys:
                    old = recent_keys.popleft()
                    if old in recent_set:
                        recent_set.remove(old)
            else:
                print(f"[chat-bridge] failed to post event: {msg}")


if __name__ == "__main__":
    print(f"[chat-bridge] starting, log={LOG_FILE}, api={API_BASE}")
    tail_log_file()
