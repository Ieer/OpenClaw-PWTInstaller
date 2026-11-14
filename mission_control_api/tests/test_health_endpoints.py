from __future__ import annotations

import asyncio
import json
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from mission_control_api.app.config import Settings
from mission_control_api.app import main as api
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
    def test_usage_cache_avoids_scans_until_configured_ttl(self) -> None:
        settings = Settings(agent_usage_cache_ttl_seconds=120.0)
        snapshot = []
        with patch.dict(api._AGENT_USAGE_CACHE, {
            "days": 7, "generated_at": 1000.0, "data": snapshot,
        }, clear=True), patch.object(api.time, "time", return_value=1061.0), patch.object(
            api, "_collect_agent_usage_snapshot", return_value=[]
        ) as collect:
            self.assertIs(api._get_agent_usage_snapshot(settings, 7), snapshot)
            self.assertIs(asyncio.run(api._get_agent_usage_snapshot_nonblocking(settings, 7)), snapshot)
            collect.assert_not_called()
            with patch.object(api.time, "time", return_value=1121.0):
                api._get_agent_usage_snapshot(settings, 7)
            collect.assert_called_once_with(settings, 7)

    def test_chat_proxy_retries_interrupted_asset_body(self) -> None:
        class InterruptedBody(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b"partial"
                raise httpx.ReadError("upstream disconnected")

        async def verify() -> None:
            calls = []

            async def empty_body():
                yield b""

            async def handle(request):
                self.assertNotIn("transfer-encoding", request.headers)
                calls.append(request.method)
                if len(calls) == 1:
                    return httpx.Response(200, stream=InterruptedBody())
                return httpx.Response(200, content=b"complete asset")

            async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                request = client.build_request("GET", "http://gateway/assets/app.js", content=empty_body())
                response = await api._send_chat_proxy_request(client, request)
                self.assertEqual(response.content, b"complete asset")
                self.assertEqual(calls, ["GET", "GET"])

        asyncio.run(verify())

    def test_chat_proxy_does_not_retry_writes_or_repeated_failure(self) -> None:
        async def verify() -> None:
            for method, expected in (("POST", 1), ("GET", 2)):
                calls = []

                async def handle(request):
                    calls.append(request.method)
                    raise httpx.ReadError("upstream disconnected")

                async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                    request = client.build_request(method, "http://gateway/resource")
                    with self.assertRaises(httpx.ReadError):
                        await api._send_chat_proxy_request(client, request)
                self.assertEqual(len(calls), expected)

        asyncio.run(verify())

    def test_control_ui_html_rewrites_only_local_tag_paths(self) -> None:
        original = '<link href="/assets/style.css">\n<script src="/assets/main.js"></script><link href="//cdn.example/style.css"><script>const text=\'<link href="/keep">\';</script>'
        rewritten = api._rewrite_control_ui_html_paths(original, "personal")
        self.assertIn('href="/chat/personal/assets/style.css"', rewritten)
        self.assertIn('src="/chat/personal/assets/main.js"', rewritten)
        self.assertIn('href="//cdn.example/style.css"', rewritten)
        self.assertIn('const text=\'<link href="/keep">\';', rewritten)

    def test_chat_client_headers_trust_only_explicit_proxy(self) -> None:
        trusted = ("172.21.0.3",)
        self.assertEqual(api._chat_client_headers("172.21.0.3", "192.168.8.130", trusted), {
            "X-Real-IP": "192.168.8.130", "X-Forwarded-For": "192.168.8.130",
        })
        self.assertEqual(api._chat_client_headers("192.168.8.20", "127.0.0.1", trusted), {
            "X-Real-IP": "192.168.8.20", "X-Forwarded-For": "192.168.8.20",
        })
        for invalid in ("spoofed", "127.0.0.1, 192.168.8.130", "192.168.8.130\r\nX-Test: forged"):
            self.assertEqual(api._chat_client_headers("172.21.0.3", invalid, trusted)["X-Forwarded-For"], "172.21.0.3")
        self.assertEqual(api._chat_client_headers(None, "127.0.0.1", trusted), {})

    def test_usage_file_cache_tracks_changes_and_sliding_windows(self) -> None:
        epoch = 1_700_000_000
        event = json.dumps({"ts": epoch * 1000, "usage": {"input": 10, "totalTokens": 10}}) + "\n"
        changed = json.dumps({"ts": epoch * 1000, "usage": {"input": 30, "totalTokens": 30}}) + "\n"
        with TemporaryDirectory() as directory, patch.dict(api._AGENT_USAGE_FILE_CACHE, {}, clear=True):
            sessions = Path(directory) / "nox" / "sessions"
            sessions.mkdir(parents=True)
            path = sessions / "test.jsonl"
            path.write_text(event, encoding="utf-8")
            settings = Settings(agent_homes_dir=directory)
            with patch.object(api.time, "time", return_value=epoch), patch.object(
                api.json, "loads", wraps=json.loads
            ) as parse:
                self.assertEqual(api._collect_agent_usage_snapshot(settings, 7)[0].total_tokens_24h, 10)
                self.assertEqual(api._collect_agent_usage_snapshot(settings, 7)[0].total_tokens_window, 10)
                self.assertEqual(parse.call_count, 1)
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(event)
                self.assertEqual(api._collect_agent_usage_snapshot(settings, 7)[0].total_tokens_window, 20)
                path.write_text(changed, encoding="utf-8")
                self.assertEqual(api._collect_agent_usage_snapshot(settings, 7)[0].total_tokens_window, 30)
            with patch.object(api.time, "time", return_value=epoch + 2 * 86400):
                rows = api._collect_agent_usage_snapshot(settings, 7)
                self.assertEqual(rows[0].total_tokens_24h, 0)
                self.assertEqual(rows[0].total_tokens_window, 30)
            with patch.object(api.time, "time", return_value=epoch + 8 * 86400):
                self.assertEqual(api._collect_agent_usage_snapshot(settings, 7)[0].total_tokens_window, 0)
            path.rename(sessions / "test.jsonl.reset.1")
            with patch.object(api.time, "time", return_value=epoch):
                self.assertEqual(api._collect_agent_usage_snapshot(settings, 7)[0].total_tokens_window, 30)
                (sessions / "test.jsonl.reset.1").unlink()
                self.assertEqual(api._collect_agent_usage_snapshot(settings, 7)[0].total_tokens_window, 0)
            self.assertFalse(api._AGENT_USAGE_FILE_CACHE)

    def _build_client(
        self,
        *,
        redis_fail: bool = False,
        db_fail: bool = False,
        settings: Settings | None = None,
    ) -> TestClient:
        fake_session_factory = _FakeSessionFactory(_FakeSession(fail=db_fail))
        fake_settings = settings or Settings(
            auth_token=None,
            agent_homes_dir="/missing-agent-homes",
            agent_manifest_path="/missing-agent-manifest.yaml",
        )
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

    def test_container_health_probes_port_and_http_targets_concurrently(self) -> None:
        fake_settings = Settings(
            auth_token=None,
            agent_homes_dir="/missing-agent-homes",
            agent_manifest_path="/missing-agent-manifest.yaml",
            agent_slugs="nox,metrics,email,growth",
            container_health_probe_concurrency=2,
        )
        active = {"port": 0, "http": 0}
        max_active = {"port": 0, "http": 0}

        async def fake_probe_tcp(host: str, port: int, *, timeout_seconds: float = 1.2):
            active["port"] += 1
            max_active["port"] = max(max_active["port"], active["port"])
            try:
                await asyncio.sleep(0.01)
                return True, 7, f"tcp-ok {host}:{port}"
            finally:
                active["port"] -= 1

        async def fake_probe_http(url: str, *, timeout_seconds: float = 1.5):
            active["http"] += 1
            max_active["http"] = max(max_active["http"], active["http"])
            try:
                await asyncio.sleep(0.01)
                return True, 11, f"HTTP 204 {url}"
            finally:
                active["http"] -= 1

        with patch("mission_control_api.app.main._probe_tcp", new=fake_probe_tcp), patch(
            "mission_control_api.app.main._probe_http",
            new=fake_probe_http,
        ):
            with self._build_client(settings=fake_settings) as client:
                response = client.get("/v1/observability/container-health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["compose_total"], 2)
        self.assertEqual(payload["port_total"], 7)
        self.assertEqual(payload["http_total"], 3)
        self.assertEqual(payload["port_ok"], 7)
        self.assertEqual(payload["http_ok"], 3)
        self.assertEqual(payload["overall_ok"], 12)
        self.assertEqual(payload["overall_total"], 12)
        self.assertEqual(max_active["port"], 2)
        self.assertEqual(max_active["http"], 2)

        port_signals = [item for item in payload["signals"] if item["source"] == "port"]
        http_signals = [item for item in payload["signals"] if item["source"] == "http"]
        self.assertEqual([item["name"] for item in port_signals[:3]], [
            "mission-control-api",
            "mission-control-ui",
            "mission-control-gateway",
        ])
        self.assertTrue(all(item["latency_ms"] == 7 for item in port_signals))
        self.assertTrue(all(item["detail"].startswith("tcp-ok") for item in port_signals))
        self.assertTrue(all(item["latency_ms"] == 11 for item in http_signals))
        self.assertTrue(all(item["detail"].startswith("HTTP 204") for item in http_signals))

    def test_usage_snapshot_timeout_returns_cached_fallback(self) -> None:
        fake_settings = Settings(
            auth_token=None,
            agent_homes_dir="/missing-agent-homes",
            agent_manifest_path="/missing-agent-manifest.yaml",
            agent_usage_snapshot_timeout_seconds=0.01,
        )

        def slow_usage_snapshot(_settings: Settings, _days: int):
            time.sleep(0.1)
            return []

        with patch.dict(api._AGENT_USAGE_CACHE, {"days": None, "generated_at": 0.0, "data": []}), patch(
            "mission_control_api.app.main._collect_agent_usage_snapshot", new=slow_usage_snapshot
        ):
            with self._build_client(settings=fake_settings) as client:
                response = client.get("/v1/usage/agents?days=7")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_stale_usage_returns_immediately_and_refreshes_once(self) -> None:
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()
        stale = [object()]
        fresh = [object()]

        def collect(_settings: Settings, _days: int):
            started.set()
            release.wait(2)
            return fresh

        async def check():
            first = await asyncio.wait_for(api._get_agent_usage_snapshot_nonblocking(Settings(), 7), 0.2)
            self.assertIs(first, stale)
            self.assertTrue(started.wait(0.2))
            second = await api._get_agent_usage_snapshot_nonblocking(Settings(), 7)
            self.assertIs(second, stale)

        with patch.dict(api._AGENT_USAGE_CACHE, {"days": 7, "generated_at": 1.0, "data": stale}), patch.object(
            api, "_AGENT_USAGE_REFRESH_LOCK", threading.Lock()
        ), patch.object(api, "_collect_agent_usage_snapshot", side_effect=collect) as scan:
            original_get = api._get_agent_usage_snapshot

            def get_and_signal(settings, days):
                try:
                    return original_get(settings, days)
                finally:
                    finished.set()

            with patch.object(api, "_get_agent_usage_snapshot", side_effect=get_and_signal):
                try:
                    asyncio.run(check())
                finally:
                    release.set()
                    self.assertTrue(finished.wait(2))
                    self.assertTrue(api._AGENT_USAGE_REFRESH_LOCK.acquire(timeout=2))
                    api._AGENT_USAGE_REFRESH_LOCK.release()
                self.assertEqual(scan.call_count, 1)
                self.assertIs(api._AGENT_USAGE_CACHE["data"], fresh)
                self.assertGreater(api._AGENT_USAGE_CACHE["generated_at"], 1.0)

    def test_cold_usage_timeout_does_not_duplicate_inflight_scan(self) -> None:
        release = threading.Event()
        settings = Settings(agent_usage_snapshot_timeout_seconds=0.1)

        def collect(_settings: Settings, _days: int):
            release.wait(2)
            return []

        async def check():
            self.assertEqual(await api._get_agent_usage_snapshot_nonblocking(settings, 7), [])
            with patch.object(api.time, "time", return_value=api.time.time() + 100):
                self.assertEqual(await api._get_agent_usage_snapshot_nonblocking(settings, 7), [])

        with patch.dict(api._AGENT_USAGE_CACHE, {"days": None, "generated_at": 0.0, "data": []}), patch.object(
            api, "_AGENT_USAGE_REFRESH_LOCK", threading.Lock()
        ), patch.object(api, "_collect_agent_usage_snapshot", side_effect=collect) as scan:
            try:
                asyncio.run(check())
                self.assertEqual(scan.call_count, 1)
            finally:
                release.set()
                self.assertTrue(api._AGENT_USAGE_REFRESH_LOCK.acquire(timeout=2))
                api._AGENT_USAGE_REFRESH_LOCK.release()
            self.assertEqual(api._AGENT_USAGE_CACHE["refresh_started_at"], 0.0)


if __name__ == "__main__":
    unittest.main()