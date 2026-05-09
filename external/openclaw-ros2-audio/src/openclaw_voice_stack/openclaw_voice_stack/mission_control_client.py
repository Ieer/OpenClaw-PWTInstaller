from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
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
    seen_keys: set[str] = field(default_factory=set)
    max_seen: int = 1000

    @staticmethod
    def event_key(item: dict[str, Any]) -> str:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        return str(
            item.get("id")
            or payload.get("event_key")
            or f"{item.get('type')}|{item.get('created_at')}|{payload.get('text')}"
        )

    def filter_new_tts_requests(self, feed_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        for item in reversed(feed_items):
            if str(item.get("type") or "") != "voice.tts.requested":
                continue
            key = self.event_key(item)
            if key in self.seen_keys:
                continue
            self.seen_keys.add(key)
            selected.append(item)
        if len(self.seen_keys) > self.max_seen:
            self.seen_keys = set(list(self.seen_keys)[-self.max_seen :])
        return selected
