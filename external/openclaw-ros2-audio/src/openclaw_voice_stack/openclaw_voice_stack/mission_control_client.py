from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class MissionControlClientError(RuntimeError):
    """Raised when Mission Control cannot be reached or returns invalid data."""


@dataclass(slots=True)
class MissionControlClient:
    api_url: str = "http://127.0.0.1:18910"
    auth_token: str = ""
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        self.api_url = (self.api_url or "http://127.0.0.1:18910").rstrip("/")
        self.auth_token = self.auth_token.strip()

    @classmethod
    def from_env(cls, *, api_url: str = "", token_env: str = "MC_AUTH_TOKEN") -> "MissionControlClient":
        return cls(
            api_url=(api_url or os.getenv("MC_API_URL") or "http://127.0.0.1:18910"),
            auth_token=(os.getenv(token_env) or ""),
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def get_json(self, path: str) -> Any:
        url = f"{self.api_url}{path if path.startswith('/') else '/' + path}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            raise MissionControlClientError(f"Mission Control HTTP {exc.code}: {url}") from exc
        except urllib.error.URLError as exc:
            raise MissionControlClientError(f"Mission Control unreachable: {exc}") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MissionControlClientError("Mission Control returned non-JSON response") from exc

    def health(self) -> dict[str, Any]:
        payload = self.get_json("/health")
        return payload if isinstance(payload, dict) else {}

    def feed_lite(self, *, limit: int = 80) -> list[dict[str, Any]]:
        payload = self.get_json(f"/v1/feed-lite?limit={int(limit)}")
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    def feed(self, *, limit: int = 80) -> list[dict[str, Any]]:
        payload = self.get_json(f"/v1/feed?limit={int(limit)}")
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]


@dataclass(slots=True)
class FeedCursor:
    device_id: str = ""
    state_path: Path | None = None
    seen_keys: set[str] = field(default_factory=set)
    seen_order: deque[str] = field(default_factory=deque)
    pending_keys: set[str] = field(default_factory=set)
    max_seen: int = 1000
    max_pending: int = 128

    def __post_init__(self) -> None:
        self.device_id = (self.device_id or os.getenv("MC_VOICE_DEVICE_ID") or "").strip()
        if self.state_path is None:
            configured_path = (os.getenv("MC_VOICE_CURSOR_DB") or "").strip()
            self.state_path = (Path(configured_path).expanduser() if configured_path
                               else Path.home() / ".openclaw" / "voice" / "tts-cursor.sqlite3")
        self.state_path = Path(self.state_path).expanduser()
        existed = self.state_path.parent.exists()
        self.state_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not existed:
            self.state_path.parent.chmod(0o700)
        with sqlite3.connect(self.state_path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS consumed_tts_events ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL, "
                "event_key TEXT NOT NULL, consumed_at REAL NOT NULL, UNIQUE(device_id, event_key))"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS tts_cursor_state (device_id TEXT PRIMARY KEY, initialized_at REAL NOT NULL)"
            )
            rows = connection.execute(
                "SELECT event_key FROM consumed_tts_events WHERE device_id=? ORDER BY id DESC LIMIT ?",
                (self.device_id, self.max_seen),
            ).fetchall()
        self.seen_order.extend(row[0] for row in reversed(rows))
        self.seen_keys.update(self.seen_order)
        self.state_path.chmod(0o600)

    @staticmethod
    def event_key(item: dict[str, Any]) -> str:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        return str(
            item.get("id")
            or payload.get("event_key")
            or f"{item.get('type')}|{item.get('created_at')}|{payload.get('text')}"
        )

    def filter_new_tts_requests(self, feed_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.device_id:
            return []
        selected: list[dict[str, Any]] = []
        matched_items = []
        for item in reversed(feed_items):
            if str(item.get("type") or "") != "voice.tts.requested":
                continue
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            if not self.device_id or str(payload.get("device_id") or "").strip() != self.device_id:
                continue
            key = self.event_key(item)
            matched_items.append((key, item))
            if key in self.seen_keys or key in self.pending_keys:
                continue
            if len(self.pending_keys) >= self.max_pending:
                continue
            self.pending_keys.add(key)
            selected.append(item)
        if self.state_path is not None:
            with sqlite3.connect(self.state_path) as connection:
                initialized = connection.execute(
                    "SELECT 1 FROM tts_cursor_state WHERE device_id=?", (self.device_id,)
                ).fetchone()
                if initialized is None:
                    keys = [key for key, _item in matched_items]
                    connection.executemany(
                        "INSERT OR IGNORE INTO consumed_tts_events(device_id, event_key, consumed_at) VALUES (?, ?, ?)",
                        [(self.device_id, key, time.time()) for key in keys],
                    )
                    connection.execute(
                        "INSERT INTO tts_cursor_state(device_id, initialized_at) VALUES (?, ?)",
                        (self.device_id, time.time()),
                    )
                    self.seen_keys.update(keys)
                    return []
        return selected

    def acknowledge(self, item: dict[str, Any]) -> None:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        if not self.device_id or str(payload.get("device_id") or "").strip() != self.device_id:
            return
        key = self.event_key(item)
        self.pending_keys.discard(key)
        if key not in self.seen_keys:
            self.seen_keys.add(key)
            self.seen_order.append(key)
        while len(self.seen_order) > self.max_seen:
            self.seen_keys.discard(self.seen_order.popleft())
        if self.state_path is not None:
            with sqlite3.connect(self.state_path) as connection:
                connection.execute(
                    "INSERT OR IGNORE INTO consumed_tts_events(device_id, event_key, consumed_at) VALUES (?, ?, ?)",
                    (self.device_id, key, time.time()),
                )
                connection.execute(
                    "DELETE FROM consumed_tts_events WHERE device_id=? AND id NOT IN ("
                    "SELECT id FROM consumed_tts_events WHERE device_id=? ORDER BY id DESC LIMIT ?)",
                    (self.device_id, self.device_id, self.max_seen),
                )

    def release(self, item: dict[str, Any]) -> None:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        if self.device_id and str(payload.get("device_id") or "").strip() == self.device_id:
            self.pending_keys.discard(self.event_key(item))
