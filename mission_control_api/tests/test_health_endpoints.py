from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from mission_control_api.app.config import Settings
from mission_control_api.app.main import create_app


class _FakeResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class _FakeSession:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def execute(self, _statement):
        if self._fail:
            raise RuntimeError("db unavailable")
        return _FakeResult(1)


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeSessionFactory:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def __call__(self) -> _FakeSessionContext:
        return _FakeSessionContext(self._session)


class _FakeRedis:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def ping(self) -> bool:
        if self._fail:
            raise RuntimeError("redis unavailable")
        return True

    async def aclose(self) -> None:
        return None


class _FakeEngine:
    async def dispose(self) -> None:
        return None


class HealthEndpointTests(unittest.TestCase):
    def _build_client(self, *, redis_fail: bool = False, db_fail: bool = False) -> TestClient:
        fake_session_factory = _FakeSessionFactory(_FakeSession(fail=db_fail))
        fake_settings = Settings(auth_token=None)
        fake_engine = _FakeEngine()

        patches = [
            patch("mission_control_api.app.main.load_settings", return_value=fake_settings),
            patch("mission_control_api.app.main.create_engine", return_value=fake_engine),
            patch("mission_control_api.app.main.create_session_factory", return_value=fake_session_factory),
            patch.object(
                __import__("mission_control_api.app.main", fromlist=["Redis"]).Redis,
                "from_url",
                return_value=_FakeRedis(fail=redis_fail),
            ),
        ]

        for item in patches:
            item.start()
            self.addCleanup(item.stop)

        return TestClient(create_app())

    def test_health_stays_lightweight(self) -> None:
        with self._build_client() as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_ready_returns_200_when_dependencies_are_ready(self) -> None:
        with self._build_client() as client:
            response = client.get("/ready")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["dependency_ok"], 2)
        self.assertEqual(payload["dependency_total"], 2)
        self.assertEqual([item["name"] for item in payload["signals"]], ["redis.ping", "postgres.select_1"])

    def test_ready_returns_503_when_dependencies_fail(self) -> None:
        with self._build_client(redis_fail=True) as client:
            response = client.get("/ready")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertFalse(payload["ready"])
        self.assertEqual(payload["dependency_ok"], 1)
        self.assertEqual(payload["dependency_total"], 2)
        self.assertIn("redis unavailable", payload["signals"][0]["detail"])


if __name__ == "__main__":
    unittest.main()