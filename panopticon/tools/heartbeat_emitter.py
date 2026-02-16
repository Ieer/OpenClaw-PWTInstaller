from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _agent_slugs() -> list[str]:
    raw = _env("MC_HEARTBEAT_AGENTS")
    slugs: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        slug = part.strip()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        slugs.append(slug)
    return slugs


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = _env("MC_AUTH_TOKEN") or _env("MISSION_CONTROL_AUTH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _post_event(base_url: str, headers: dict[str, str], slug: str) -> None:
    payload = {
        "type": "agent.heartbeat",
        "agent": slug,
        "payload": {
            "ok": True,
            "source": "mc-heartbeat",
            "ts": datetime.now(timezone.utc).isoformat(),
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=f"{base_url.rstrip('/')}/v1/events",
        data=body,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5):
        pass


def main() -> None:
    base_url = _env("MC_API_URL", "http://mission-control-api:9090")
    interval = int(_env("MC_HEARTBEAT_INTERVAL_SECONDS", "60") or "60")
    interval = max(10, interval)
    headers = _headers()

    while True:
        slugs = _agent_slugs()
        if not slugs:
            print("[mc-heartbeat] no agents configured in MC_HEARTBEAT_AGENTS")
        for slug in slugs:
            try:
                _post_event(base_url, headers, slug)
                print(f"[mc-heartbeat] sent heartbeat: {slug}")
            except urllib.error.HTTPError as e:
                print(f"[mc-heartbeat] http error for {slug}: {e.code}")
            except Exception as e:  # noqa: BLE001
                print(f"[mc-heartbeat] failed for {slug}: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
