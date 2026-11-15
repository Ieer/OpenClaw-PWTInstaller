from __future__ import annotations

import asyncio
import hashlib
import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mission_control_api.app.config import Settings
from mission_control_api.app.execution import JobCreate, job_fingerprint, lease_is_valid
from mission_control_api.app.knowledge_access import bind_knowledge_request
from mission_control_api.app.schemas import KnowledgeResolveIn
from mission_control_api.app.embedding_cache import EmbeddingCache, embedding_cache_key
from mission_control_api.app.main import _voice_source_refs, create_app
from mission_control_api.app.models import metadata, tasks, events, event_outbox, execution_jobs, execution_provider_charges, task_action_requests, knowledge_units, knowledge_validations, knowledge_resolve_audits
from mission_control_api.app.outbox import EventOutbox, stage_event


class ExecutionUnitTests(unittest.TestCase):
    def test_voice_source_identity_preserves_device_and_stable_event_key(self):
        refs = _voice_source_refs({"id": "source-1", "agent": "nox", "payload": {
            "turn_id": "turn-1", "event_key": "event-1", "device_id": "desk"}})
        self.assertEqual(refs, {"source_voice_event_id": "source-1", "source_voice_agent": "nox",
                                "voice_turn_id": "turn-1", "voice_event_key": "event-1", "device_id": "desk"})

    def test_knowledge_principal_binds_scope_risk_and_approved_only(self):
        profiles = {hashlib.sha256(b"role-token").hexdigest(): {"agent_slug": "health", "risk_floor": "high"}}
        body = KnowledgeResolveIn(task="evaluate supplied evidence", risk_level="low", limit=100,
                                  require_approved_validation=False, include_rejected=True)
        bound, kind = bind_knowledge_request(body, authorization="Bearer role-token", admin_token="admin", profiles=profiles)
        self.assertEqual((bound.agent_slug, bound.risk_level, kind), ("health", "high", "role"))
        self.assertTrue(bound.require_approved_validation)
        self.assertFalse(bound.include_rejected)
        self.assertEqual(bound.limit, 5)

    def test_knowledge_principal_cannot_change_role(self):
        profiles = {hashlib.sha256(b"role-token").hexdigest(): {"agent_slug": "metrics", "risk_floor": "normal"}}
        for body, token in ((KnowledgeResolveIn(task="test", agent_slug="health"), "role-token"),
                            (KnowledgeResolveIn(task="test"), "wrong-token")):
            with self.assertRaises(Exception) as caught:
                bind_knowledge_request(body, authorization=f"Bearer {token}", admin_token="admin", profiles=profiles)
            self.assertEqual(caught.exception.status_code, 403)

    def test_knowledge_admin_retains_explicit_management_scope(self):
        body = KnowledgeResolveIn(task="admin review", agent_slug=None, limit=20)
        bound, kind = bind_knowledge_request(body, authorization="Bearer admin", admin_token="admin", profiles={})
        self.assertIs(bound, body)
        self.assertEqual(kind, "admin")

    def test_fingerprint_is_stable_and_covers_execution_contract(self) -> None:
        body = JobCreate(agent_slug="nox", idempotency_key="one", payload={"a": 1, "b": 2})
        other = JobCreate(agent_slug="nox", idempotency_key="two", payload={"b": 2, "a": 1})
        self.assertEqual(job_fingerprint(body), job_fingerprint(other))
        self.assertNotEqual(job_fingerprint(body), job_fingerprint(body.model_copy(update={"kind": "maintenance"})))

    def test_payload_and_blank_keys_are_rejected(self) -> None:
        for values in ({"idempotency_key": " "}, {"payload": {"text": "x" * 32769}}, {"kind": "unknown"}):
            with self.assertRaises(ValueError):
                JobCreate(**{"agent_slug": "nox", "idempotency_key": "one", **values})

    def test_lease_rejects_old_worker_and_expiry(self) -> None:
        now = datetime.now(timezone.utc)
        token = uuid4()
        row = SimpleNamespace(status="RUNNING", lease_token=token, lease_expires_at=now + timedelta(seconds=1))
        self.assertTrue(lease_is_valid(row, token, now))
        self.assertFalse(lease_is_valid(row, uuid4(), now))
        self.assertFalse(lease_is_valid(row, token, now + timedelta(seconds=1)))


class EmbeddingCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_singleflight_and_copy_isolation(self) -> None:
        cache = EmbeddingCache()
        factory = AsyncMock(return_value=([[1.0, 2.0]], "test", 2))
        results = await asyncio.gather(*[cache.get("key", factory) for _ in range(8)])
        factory.assert_awaited_once()
        results[0][0][0][0] = 99
        self.assertEqual((await cache.get("key", factory))[0][0][0], 1)

    async def test_expiry_budget_and_failure_retry(self) -> None:
        now = [0.0]
        cache = EmbeddingCache(ttl_seconds=10, max_entries=2, clock=lambda: now[0])
        factory = AsyncMock(return_value=[1])
        await cache.get("one", factory)
        await cache.get("two", factory)
        await cache.get("three", factory)
        self.assertEqual(len(cache.entries), 2)
        now[0] = 10
        await cache.get("three", factory)
        self.assertEqual(factory.await_count, 4)
        failing = AsyncMock(side_effect=ValueError("test"))
        with self.assertRaises(ValueError):
            await cache.get("failure", failing)
        self.assertNotIn("failure", cache.entries)
        await cache.get("failure", factory)

    async def test_role_risk_model_credential_and_revision_change_key(self) -> None:
        values = {"query": "question", "agent_slug": "nox", "risk_level": "normal", "config": {"model": "one", "api_key": "test"}, "revision": "1"}
        key = embedding_cache_key(**values)
        for change in ({"agent_slug": "health"}, {"risk_level": "high"}, {"config": {"model": "two"}}, {"config": {"model": "one", "api_key": "different"}}, {"revision": "2"}):
            self.assertNotEqual(key, embedding_cache_key(**{**values, **change}))
        self.assertNotIn("question", key)
        self.assertNotIn("test", key)

    async def test_cancelled_waiter_does_not_cancel_other_waiters(self) -> None:
        cache = EmbeddingCache()
        started = asyncio.Event()
        release = asyncio.Event()
        async def factory():
            started.set()
            await release.wait()
            return [1]
        first = asyncio.create_task(cache.get("one", factory))
        await started.wait()
        second = asyncio.create_task(cache.get("one", factory))
        first.cancel()
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await first
        self.assertEqual(await second, [1])
        await cache.close()


@unittest.skipUnless(os.getenv("MC_TEST_DATABASE_URL"), "requires disposable PostgreSQL database")
class ExecutionDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        url = os.environ["MC_TEST_DATABASE_URL"]
        if not url.endswith("/mission_control_test"):
            self.fail("integration tests require the mission_control_test database")
        self.schema = f"mc_test_{uuid4().hex}"
        self.base_engine = create_async_engine(url)
        async with self.base_engine.begin() as connection:
            await connection.execute(sa.schema.CreateSchema(self.schema))
        self.engine = self.base_engine.execution_options(schema_translate_map={None: self.schema})
        async with self.engine.begin() as connection:
            await connection.run_sync(lambda sync: metadata.create_all(sync, tables=[
                tasks, events, event_outbox, execution_jobs, execution_provider_charges, task_action_requests
            ]))
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.settings = Settings(execution_enabled=True, agent_slugs="nox,metrics,writing", agent_homes_dir="/missing", agent_manifest_path="/missing")
        self.redis = SimpleNamespace(xadd=AsyncMock(return_value="1-0"), aclose=AsyncMock())
        with patch("mission_control_api.app.main.load_settings", return_value=self.settings), \
             patch("mission_control_api.app.main.create_engine", return_value=self.engine), \
             patch("mission_control_api.app.main.Redis.from_url", return_value=self.redis):
            self.app = create_app()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        async with self.base_engine.begin() as connection:
            await connection.execute(sa.schema.DropSchema(self.schema, cascade=True))
        await self.base_engine.dispose()

    async def submit(self, *, agent="nox", kind="main", **options) -> dict:
        response = await self.client.post("/v1/execution/jobs", json={
            "agent_slug": agent, "kind": kind, "idempotency_key": uuid4().hex, **options,
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def test_knowledge_role_batch_latest_validation_scope_and_audit(self):
        self.settings.auth_token = "admin"
        self.settings.knowledge_access_profiles = {
            hashlib.sha256(b"role-token").hexdigest(): {"agent_slug": "metrics", "risk_floor": "normal"}}
        async with self.engine.begin() as connection:
            await connection.run_sync(lambda sync: metadata.create_all(sync, tables=[
                table for table in metadata.tables.values() if table.name.startswith("knowledge_")
            ]))
        now = datetime.now(timezone.utc)
        definitions = [
            ("good", ["metrics"], [("rejected", -2, 10), ("approved", -1, 10)]),
            ("unapproved", ["metrics"], [("pending", -1, 10)]),
            ("expired", ["metrics"], [("approved", -1, -1)]),
            ("reverted", ["metrics"], [("approved", -2, 10), ("rejected", -1, 10)]),
            ("private-other-role", ["nox"], [("approved", -1, 10)]),
            ("no-validation", ["metrics"], []),
        ]
        async with self.factory() as session:
            for key, scope, validations in definitions:
                unit_id = uuid4()
                await session.execute(knowledge_units.insert().values(
                    id=unit_id, unit_key=key, title=key, content="weekly evidence", agent_scope=scope))
                for status, validated_offset, expiry_offset in validations:
                    await session.execute(knowledge_validations.insert().values(
                        id=uuid4(), unit_id=unit_id, validator="test", validation_status=status,
                        confidence=0.99, validated_at=now + timedelta(seconds=validated_offset),
                        expires_at=now + timedelta(days=expiry_offset)))
            await session.commit()
        statements = []
        def capture(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().startswith("SELECT") and "knowledge_validations" in statement:
                statements.append(statement)
        sa.event.listen(self.base_engine.sync_engine, "before_cursor_execute", capture)
        try:
            response = await self.client.post("/v1/knowledge/resolve", headers={"Authorization": "Bearer role-token"}, json={
                "task": "weekly evidence", "risk_level": "low", "require_approved_validation": False,
                "include_rejected": True, "retrieval_mode": "lexical"})
        finally:
            sa.event.remove(self.base_engine.sync_engine, "before_cursor_execute", capture)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["agent_slug"], "metrics")
        self.assertEqual(result["risk_level"], "normal")
        self.assertEqual([item["unit"]["unit_key"] for item in result["items"]], ["good"])
        self.assertEqual(result["rejected"], [])
        self.assertEqual(len(statements), 1)
        async with self.factory() as session:
            audits = (await session.execute(sa.select(knowledge_resolve_audits))).all()
        self.assertEqual(str(audits[0].id), result["audit_id"])
        self.assertEqual(audits[0].payload["authenticated_agent"], "metrics")
        denied = await self.client.post("/v1/knowledge/resolve", headers={"Authorization": "Bearer role-token"},
                                        json={"task": "test", "agent_slug": "nox"})
        self.assertEqual(denied.status_code, 403)
        denied_queue = await self.client.post("/v1/execution/claim", headers={"Authorization": "Bearer role-token"},
                                              json={"agent_slug": "metrics", "worker_id": "forbidden"})
        self.assertEqual(denied_queue.status_code, 403)

    async def test_voice_tts_feedback_preserves_source_device_id(self):
        from mission_control_api.app.models import events

        parsed = SimpleNamespace(outcome="rejected", command=None, normalized_text="unknown", prefix_used="指挥",
                                 reason="synthetic acceptance")
        event = {"type": "voice.asr.final", "agent": "nox",
                 "payload": {"text": "指挥 synthetic", "device_id": "desk", "event_key": "voice-event-1"}}
        headers = {"Idempotency-Key": "voice-ingress-stable"}
        with patch("mission_control_api.app.main.parse_voice_command", return_value=parsed):
            response = await self.client.post("/v1/events", headers=headers, json=event)
            replay = await self.client.post("/v1/events", headers=headers, json=event)
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(replay.json()["id"], response.json()["id"])
        self.assertEqual(response.status_code, 200, response.text)
        async with self.factory() as session:
            feedback_rows = (await session.execute(sa.select(events.c.payload).where(
                events.c.type == "voice.tts.requested",
            ))).all()
        feedback = next(row.payload for row in feedback_rows
                        if row.payload.get("source_voice_event_id") == response.json()["id"])
        self.assertEqual(len([row for row in feedback_rows
                      if row.payload.get("source_voice_event_id") == response.json()["id"]]), 1)
        self.assertEqual(feedback["device_id"], "desk")
        self.assertEqual(feedback["voice_event_key"], "voice-event-1")

    async def claim(self, agent="nox", kind="main") -> dict | None:
        response = await self.client.post("/v1/execution/claim", json={"agent_slug": agent, "kind": kind, "worker_id": uuid4().hex})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["job"]

    async def test_capability_filter_and_cancel_revoke_running_lease(self):
        unrelated = await self.submit(payload={"workflow": "other"}, priority=1)
        draft = await self.submit(payload={"workflow": "weekly-review"}, priority=100)
        response = await self.client.post("/v1/execution/claim", json={
            "agent_slug": "nox", "worker_id": "draft", "workflows": ["weekly-review"]})
        job = response.json()["job"]
        self.assertEqual(job["id"], draft["id"])
        cancelled = await self.client.post(f"/v1/execution/jobs/{job['id']}/cancel")
        self.assertEqual(cancelled.json()["status"], "CANCELLED")
        repeat = await self.client.post(f"/v1/execution/jobs/{job['id']}/cancel")
        self.assertEqual(repeat.json()["status"], "CANCELLED")
        stale = await self.client.post(f"/v1/execution/jobs/{job['id']}/heartbeat", json={"lease_token": job["lease_token"]})
        self.assertEqual(stale.status_code, 409)
        stale_finish = await self.client.post(f"/v1/execution/jobs/{job['id']}/finish", json={"lease_token": job["lease_token"]})
        self.assertEqual(stale_finish.status_code, 409)
        still_queued = await self.client.get(f"/v1/execution/jobs/{unrelated['id']}")
        self.assertEqual(still_queued.json()["status"], "QUEUED")

    async def test_concurrent_task_claim_has_one_owner(self) -> None:
        task = (await self.client.post("/v1/tasks", json={"title": "race"})).json()
        responses = await asyncio.gather(*[
            self.client.post(f"/v1/tasks/{task['id']}/claim", json={"agent_slug": agent}) for agent in ("nox", "metrics")
        ])
        self.assertEqual(sorted(response.status_code for response in responses), [200, 409])
        async with self.factory() as session:
            count = (await session.execute(sa.select(sa.func.count()).select_from(events).where(events.c.type == "task.claimed"))).scalar_one()
        self.assertEqual(count, 1)

    async def test_concurrent_submissions_are_idempotent_and_conflicts_rejected(self) -> None:
        body = {"agent_slug": "nox", "idempotency_key": "same", "payload": {"artifact": "one"}}
        responses = await asyncio.gather(*[self.client.post("/v1/execution/jobs", json=body) for _ in range(4)])
        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(len({response.json()["id"] for response in responses}), 1)
        conflict = await self.client.post("/v1/execution/jobs", json={**body, "payload": {"artifact": "two"}})
        self.assertEqual(conflict.status_code, 409)

    async def test_task_creation_and_completion_replay_without_duplicate_events(self) -> None:
        headers = {"Idempotency-Key": "create-once"}
        responses = await asyncio.gather(*[
            self.client.post("/v1/tasks", json={"title": "once"}, headers=headers) for _ in range(4)
        ])
        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(len({response.json()["id"] for response in responses}), 1)
        task_id = responses[0].json()["id"]
        conflict = await self.client.post("/v1/tasks", json={"title": "changed"}, headers=headers)
        self.assertEqual(conflict.status_code, 409)
        claimed = await self.client.post(f"/v1/tasks/{task_id}/claim", json={"agent_slug": "nox"})
        self.assertEqual(claimed.status_code, 200)
        completions = await asyncio.gather(*[
            self.client.post(f"/v1/tasks/{task_id}/complete", json={"agent_slug": "nox", "summary": "done"},
                             headers={"Idempotency-Key": "complete-once"}) for _ in range(3)
        ])
        self.assertTrue(all(response.status_code == 200 for response in completions))
        self.assertTrue(all(response.json()["status"] == "DONE" for response in completions))
        async with self.factory() as session:
            count = (await session.execute(sa.select(sa.func.count()).select_from(events).where(events.c.type == "task.done"))).scalar_one()
        self.assertEqual(count, 1)

    async def test_global_and_per_agent_budgets_under_concurrency(self) -> None:
        for agent in ("nox", "metrics"):
            for _ in range(4):
                await self.submit(agent=agent)
        claims = await asyncio.gather(*[self.claim(agent) for agent in ("nox", "metrics") for _ in range(4)])
        self.assertEqual(sum(job is not None for job in claims), 4)
        self.assertEqual(sum(job is not None and job["agent_slug"] == "nox" for job in claims), 2)

    async def test_maintenance_budget_and_priority(self) -> None:
        await self.submit(kind="maintenance", priority=200)
        preferred = await self.submit(kind="maintenance", priority=10)
        jobs = await asyncio.gather(self.claim(kind="maintenance"), self.claim(kind="maintenance"))
        taken = [job for job in jobs if job]
        self.assertEqual(len(taken), 1)
        self.assertEqual(taken[0]["id"], preferred["id"])

    async def test_provider_budget_is_reserved_across_workers(self) -> None:
        self.settings.execution_provider_rpm = 1
        await self.submit(provider="test", estimated_tokens=100)
        await self.submit(agent="metrics", provider="test", estimated_tokens=100)
        claims = await asyncio.gather(self.claim(), self.claim("metrics"))
        self.assertEqual(sum(job is not None for job in claims), 1)

    async def test_unclaimable_provider_job_is_rejected(self) -> None:
        for tokens in (0, self.settings.execution_provider_tpm + 1):
            response = await self.client.post("/v1/execution/jobs", json={
                "agent_slug": "nox", "idempotency_key": uuid4().hex, "provider": "test", "estimated_tokens": tokens,
            })
            self.assertEqual(response.status_code, 422)

    async def test_expired_lease_cannot_finish_and_is_recovered(self) -> None:
        await self.submit(max_attempts=1)
        job = await self.claim()
        async with self.factory.begin() as session:
            await session.execute(execution_jobs.update().where(execution_jobs.c.id == job["id"]).values(
                lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
            ))
        response = await self.client.post(f"/v1/execution/jobs/{job['id']}/finish", json={"lease_token": job["lease_token"]})
        self.assertEqual(response.status_code, 409)
        self.assertIsNone(await self.claim())
        response = await self.client.get(f"/v1/execution/jobs/{job['id']}")
        self.assertEqual(response.json()["status"], "FAILED")
        self.assertNotIn("lease_token", response.json())

    async def test_finish_and_bounded_retry(self) -> None:
        await self.submit(max_attempts=1)
        job = await self.claim()
        response = await self.client.post(f"/v1/execution/jobs/{job['id']}/finish", json={
            "lease_token": job["lease_token"], "success": False, "retry": True, "error": "test failure"
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "FAILED")

    async def test_outbox_survives_redis_failure_and_retries(self) -> None:
        self.redis.xadd.side_effect = ConnectionError("test outage")
        response = await self.client.post("/v1/tasks", json={"title": "durable"})
        self.assertEqual(response.status_code, 200, response.text)
        async with self.factory() as session:
            row = (await session.execute(sa.select(event_outbox))).one()
            self.assertIsNone(row.delivered_at)
        self.redis.xadd.side_effect = None
        outbox = EventOutbox(self.factory, self.redis, self.settings)
        self.assertEqual(await outbox.drain_once(), 1)
        self.assertEqual(await outbox.drain_once(), 0)
        response = await self.client.get("/v1/observability/outbox")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pending"], 0)
        self.assertEqual(response.json()["delivery"], "at-least-once")

    async def test_event_and_outbox_rollback_together(self) -> None:
        event = {"id": str(uuid4()), "type": "test", "payload": {}}
        async with self.factory() as session:
            await stage_event(session, event)
            await session.rollback()
        async with self.factory() as session:
            count = (await session.execute(sa.select(sa.func.count()).select_from(event_outbox))).scalar_one()
        self.assertEqual(count, 0)

    async def test_disabled_queue_and_auth_do_not_mutate_jobs(self) -> None:
        self.settings.execution_enabled = False
        response = await self.client.post("/v1/execution/claim", json={"agent_slug": "nox", "worker_id": "worker"})
        self.assertEqual(response.status_code, 503)
        self.settings.auth_token = "test-only"
        response = await self.client.get("/v1/execution/summary")
        self.assertEqual(response.status_code, 401)