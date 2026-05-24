from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from mission_control_api.app.config import Settings
from mission_control_api.app.main import create_app
from mission_control_api.app.models import events


class _Row:
    def __init__(self, **values) -> None:
        self.__dict__.update(values)

    def _asdict(self) -> dict:
        return dict(self.__dict__)


class _FakeResult:
    def __init__(self, *, first=None, rows=None) -> None:
        self._first = first
        self._rows = list(rows or [])

    def first(self):
        return self._first

    def all(self) -> list:
        return list(self._rows)


class _FakeSession:
    def __init__(self, results: list[_FakeResult] | None = None) -> None:
        self.results = list(results or [])
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        if not self.results:
            raise AssertionError(f"unexpected statement: {statement}")
        return self.results.pop(0)


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> _FakeSession:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeSessionFactory:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    def __call__(self) -> _FakeSessionContext:
        return _FakeSessionContext(self.session)


class _FakeRedis:
    async def aclose(self) -> None:
        return None


class _FakeEngine:
    async def dispose(self) -> None:
        return None


class TaskDetailEndpointTests(unittest.TestCase):
    def _build_client(self, session: _FakeSession, settings: Settings | None = None) -> TestClient:
        fake_settings = settings or Settings(
            auth_token=None,
            agent_homes_dir="/missing-agent-homes",
            agent_manifest_path="/missing-agent-manifest.yaml",
        )
        patches = [
            patch("mission_control_api.app.main.load_settings", return_value=fake_settings),
            patch("mission_control_api.app.main.create_engine", return_value=_FakeEngine()),
            patch("mission_control_api.app.main.create_session_factory", return_value=_FakeSessionFactory(session)),
            patch.object(
                __import__("mission_control_api.app.main", fromlist=["Redis"]).Redis,
                "from_url",
                return_value=_FakeRedis(),
            ),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        return TestClient(create_app())

    def _task_row(self, task_id: UUID | None = None, *, status: str = "INBOX") -> _Row:
        now = datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc)
        return _Row(
            id=task_id or uuid4(),
            title="Detail API task",
            status=status,
            assignee="writing",
            tags=["detail", "api"],
            created_at=now,
            updated_at=now + timedelta(minutes=5),
        )

    def _comment_row(self, task_id: UUID, *, minutes: int, body: str) -> _Row:
        return _Row(
            id=uuid4(),
            task_id=task_id,
            author="nox",
            body=body,
            created_at=datetime(2026, 5, 24, 10, minutes, tzinfo=timezone.utc),
        )

    def _event_row(self, task_id: UUID, *, minutes: int, event_type: str, payload: dict) -> _Row:
        return _Row(
            id=uuid4(),
            type=event_type,
            agent="writing",
            task_id=task_id,
            payload=payload,
            created_at=datetime(2026, 5, 24, 10, minutes, tzinfo=timezone.utc),
        )

    def test_get_task_returns_task_out(self) -> None:
        task_id = uuid4()
        session = _FakeSession([_FakeResult(first=self._task_row(task_id, status="ASSIGNED"))])

        with self._build_client(session) as client:
            response = client.get(f"/v1/tasks/{task_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], str(task_id))
        self.assertEqual(payload["status"], "ASSIGNED")
        self.assertEqual(payload["assignee"], "writing")
        self.assertEqual(payload["tags"], ["detail", "api"])
        self.assertEqual(len(session.statements), 1)

    def test_get_task_missing_and_invalid_uuid_are_rejected(self) -> None:
        missing_id = uuid4()
        session = _FakeSession([_FakeResult(first=None)])

        with self._build_client(session) as client:
            missing = client.get(f"/v1/tasks/{missing_id}")
            invalid = client.get("/v1/tasks/not-a-uuid")

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["detail"], f"task not found: {missing_id}")
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(len(session.statements), 1)

    def test_get_task_requires_bearer_token_when_auth_enabled(self) -> None:
        task_id = uuid4()
        session = _FakeSession([_FakeResult(first=self._task_row(task_id))])
        settings = Settings(
            auth_token="secret",
            agent_homes_dir="/missing-agent-homes",
            agent_manifest_path="/missing-agent-manifest.yaml",
        )

        with self._build_client(session, settings=settings) as client:
            missing = client.get(f"/v1/tasks/{task_id}")
            invalid = client.get(f"/v1/tasks/{task_id}", headers={"authorization": "Bearer wrong"})
            ok = client.get(f"/v1/tasks/{task_id}", headers={"authorization": "Bearer secret"})

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(invalid.status_code, 403)
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(len(session.statements), 1)

    def test_get_task_comments_returns_recent_comments_in_ascending_display_order(self) -> None:
        task_id = uuid4()
        older = self._comment_row(task_id, minutes=1, body="older")
        newer = self._comment_row(task_id, minutes=3, body="newer")
        session = _FakeSession([
            _FakeResult(first=self._task_row(task_id)),
            _FakeResult(rows=[newer, older]),
        ])

        with self._build_client(session) as client:
            response = client.get(f"/v1/tasks/{task_id}/comments?limit=2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["body"] for item in response.json()], ["older", "newer"])
        self.assertEqual(len(session.statements), 2)

    def test_get_task_comments_limit_is_validated(self) -> None:
        task_id = uuid4()
        session = _FakeSession([])

        with self._build_client(session) as client:
            response = client.get(f"/v1/tasks/{task_id}/comments?limit=0")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(len(session.statements), 0)

    def test_get_task_events_returns_recent_events_descending_with_payload(self) -> None:
        task_id = uuid4()
        newest = self._event_row(task_id, minutes=5, event_type="task.done", payload={"artifact_refs": ["artifact://done"]})
        older = self._event_row(task_id, minutes=2, event_type="task.created", payload={"title": "Detail API task"})
        session = _FakeSession([
            _FakeResult(first=self._task_row(task_id)),
            _FakeResult(rows=[newest, older]),
        ])

        with self._build_client(session) as client:
            response = client.get(f"/v1/tasks/{task_id}/events?limit=2")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([item["type"] for item in payload], ["task.done", "task.created"])
        self.assertEqual(payload[0]["payload"], {"artifact_refs": ["artifact://done"]})
        self.assertEqual(len(session.statements), 2)

    def test_get_task_events_missing_task_returns_404(self) -> None:
        task_id = uuid4()
        session = _FakeSession([_FakeResult(first=None)])

        with self._build_client(session) as client:
            response = client.get(f"/v1/tasks/{task_id}/events")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], f"task not found: {task_id}")
        self.assertEqual(len(session.statements), 1)

    def test_events_metadata_includes_task_detail_index(self) -> None:
        indexes = {index.name: index for index in events.indexes}
        self.assertIn("idx_events_task_id_created_at_desc", indexes)
        index = indexes["idx_events_task_id_created_at_desc"]
        self.assertEqual([expr.name for expr in index.expressions if hasattr(expr, "name")], ["task_id"])

    def test_migration_contains_task_detail_index(self) -> None:
        migration = Path("mission_control_api/alembic/versions/20260524_0013_task_detail_events_index.py")
        text = migration.read_text(encoding="utf-8")
        self.assertIn("idx_events_task_id_created_at_desc", text)
        self.assertIn("ON events(task_id, created_at DESC)", text)
        self.assertIn("DROP INDEX IF EXISTS idx_events_task_id_created_at_desc", text)


if __name__ == "__main__":
    unittest.main()
