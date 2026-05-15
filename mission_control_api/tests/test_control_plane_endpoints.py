from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from mission_control_api.app.config import Settings
from mission_control_api.app.main import create_app
from mission_control_api.app.schemas import AgentControlActionOut


class _FakeResult:
    def scalar_one(self) -> int:
        return 1


class _FakeSession:
    async def execute(self, _statement):
        return _FakeResult()


class _FakeSessionContext:
    async def __aenter__(self) -> _FakeSession:
        return _FakeSession()

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeSessionFactory:
    def __call__(self) -> _FakeSessionContext:
        return _FakeSessionContext()


class _FakeRedis:
    def __init__(self, *, latest_id: str | None = None) -> None:
        self.latest_id = latest_id
        self.xread_calls: list[dict] = []
        self._event_sent = False

    async def ping(self) -> bool:
        return True

    async def xrevrange(self, _stream_key: str, *, count: int = 1):
        if not self.latest_id:
            return []
        return [(self.latest_id, {"event": json.dumps({"type": "older.event"})})]

    async def xread(self, streams: dict, *, block: int, count: int):
        self.xread_calls.append(dict(streams))
        if self._event_sent:
            raise WebSocketDisconnect(code=1000)
        self._event_sent = True
        return [
            (
                "mc:events",
                [("43-0", {"event": json.dumps({"type": "new.event"})})],
            )
        ]

    async def xadd(self, _stream_key: str, _fields: dict, **_kwargs):
        return "1-0"

    async def aclose(self) -> None:
        return None


class _FakeEngine:
    async def dispose(self) -> None:
        return None


class ControlPlaneEndpointTests(unittest.TestCase):
    def _build_client(self, settings: Settings, redis: _FakeRedis | None = None) -> TestClient:
        fake_redis = redis or _FakeRedis()
        patches = [
            patch("mission_control_api.app.main.load_settings", return_value=settings),
            patch("mission_control_api.app.main.create_engine", return_value=_FakeEngine()),
            patch("mission_control_api.app.main.create_session_factory", return_value=_FakeSessionFactory()),
            patch.object(
                __import__("mission_control_api.app.main", fromlist=["Redis"]).Redis,
                "from_url",
                return_value=fake_redis,
            ),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        return TestClient(create_app())

    def test_ws_events_requires_bearer_token_when_auth_is_enabled(self) -> None:
        settings = Settings(auth_token="secret", agent_homes_dir="/missing-agent-homes", agent_manifest_path="/missing")
        with self._build_client(settings) as client:
            with self.assertRaises(WebSocketDisconnect) as missing:
                with client.websocket_connect("/ws/events") as websocket:
                    websocket.receive_text()
            self.assertEqual(missing.exception.code, 4401)

            with self.assertRaises(WebSocketDisconnect) as invalid:
                with client.websocket_connect("/ws/events", headers={"authorization": "Bearer wrong"}) as websocket:
                    websocket.receive_text()
            self.assertEqual(invalid.exception.code, 4403)

    def test_ws_events_starts_from_latest_stream_id_after_auth(self) -> None:
        redis = _FakeRedis(latest_id="42-0")
        settings = Settings(auth_token="secret", redis_stream_key="mc:events", agent_homes_dir="/missing", agent_manifest_path="/missing")
        with self._build_client(settings, redis=redis) as client:
            with client.websocket_connect("/ws/events", headers={"authorization": "Bearer secret"}) as websocket:
                payload = json.loads(websocket.receive_text())

        self.assertEqual(payload, {"type": "new.event"})
        self.assertEqual(redis.xread_calls[0], {"mc:events": "42-0"})

    def test_agent_control_endpoint_rejects_unknown_agent_and_invalid_action_before_forwarding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "nox").mkdir()
            settings = Settings(
                auth_token=None,
                agent_homes_dir=tmp,
                agent_manifest_path="/missing",
                agent_controller_auth_token="controller-token",
            )
            forward = AsyncMock(
                return_value=AgentControlActionOut(
                    ok=True,
                    agent="nox",
                    action="restart",
                    container="openclaw-nox",
                    status="running",
                    detail="restarted",
                )
            )
            with patch("mission_control_api.app.main._forward_agent_control", new=forward):
                with self._build_client(settings) as client:
                    unknown = client.post("/v1/agents/metrics/control", json={"action": "restart"})
                    invalid = client.post("/v1/agents/nox/control", json={"action": "destroy"})
                    ok = client.post("/v1/agents/nox/control", json={"action": "restart"})

        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["status"], "running")
        forward.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()