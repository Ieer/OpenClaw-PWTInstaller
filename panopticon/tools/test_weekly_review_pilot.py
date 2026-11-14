from __future__ import annotations

import json
import sqlite3
import threading
import tempfile
import unittest
from pathlib import Path

import httpx
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from panopticon.tools.pilot_weekly_review import build_weekly_review_graph, validate_artifacts, wait_for_jobs
from panopticon.tools.weekly_review_router import WeeklyReviewRouter, RouteError, create_route_server


class WeeklyReviewPilotTests(unittest.TestCase):
    fixtures = {agent: {"artifact_refs": [f"artifact://{agent}"]} for agent in ("metrics", "nox", "writing")}

    def test_restart_resumes_at_human_review_without_duplicate_artifacts(self) -> None:
        config = {"configurable": {"thread_id": "weekly"}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoints.sqlite"
            with sqlite3.connect(path, check_same_thread=False) as connection:
                graph = build_weekly_review_graph(SqliteSaver(connection), fixtures=self.fixtures)
                result = graph.invoke({"input_refs": [], "artifact_refs": [], "approved": False}, config)
                self.assertEqual(result["__interrupt__"][0].value["kind"], "human_review")
                self.assertFalse(result["approved"])
            with sqlite3.connect(path, check_same_thread=False) as connection:
                graph = build_weekly_review_graph(SqliteSaver(connection), fixtures=self.fixtures)
                result = graph.invoke(Command(resume={"action": "approve"}), config)
                self.assertTrue(result["approved"])
                self.assertEqual(result["artifact_refs"], ["artifact://metrics", "artifact://nox", "artifact://writing"])

    def test_rejection_never_approves(self) -> None:
        with sqlite3.connect(":memory:", check_same_thread=False) as connection:
            graph = build_weekly_review_graph(SqliteSaver(connection), fixtures=self.fixtures)
            config = {"configurable": {"thread_id": "reject"}}
            graph.invoke({"input_refs": [], "artifact_refs": [], "approved": False}, config)
            result = graph.invoke(Command(resume={"action": "reject"}), config)
            self.assertFalse(result["approved"])

    def test_continue_cannot_approve_human_gate(self) -> None:
        with sqlite3.connect(":memory:", check_same_thread=False) as connection:
            graph = build_weekly_review_graph(SqliteSaver(connection), fixtures=self.fixtures)
            config = {"configurable": {"thread_id": "explicit"}}
            graph.invoke({"input_refs": [], "artifact_refs": [], "approved": False}, config)
            with self.assertRaises(ValueError):
                graph.invoke(Command(resume={"action": "continue"}), config)

    def test_queue_mode_reuses_job_and_waits_for_worker(self) -> None:
        submitted = []
        ready = [False]
        def handle(request):
            if request.method == "POST":
                body = json.loads(request.content)
                submitted.append(body)
                agent = body["agent_slug"]
                if agent == "metrics" and not ready[0]:
                    return httpx.Response(200, json={"id": "metrics-job", "status": "QUEUED"})
                return httpx.Response(200, json={"id": agent, "status": "SUCCEEDED", "result": self.fixtures[agent]})
            return httpx.Response(200, json={"id": "metrics-job", "status": "SUCCEEDED", "result": self.fixtures["metrics"]})
        with httpx.Client(transport=httpx.MockTransport(handle), base_url="http://test") as client, \
             sqlite3.connect(":memory:", check_same_thread=False) as connection:
            graph = build_weekly_review_graph(SqliteSaver(connection), client=client, provider="deepseek")
            config = {"configurable": {"thread_id": "queued"}}
            result = graph.invoke({"input_refs": ["artifact://input"], "artifact_refs": [], "approved": False}, config)
            self.assertEqual(result["__interrupt__"][0].value["kind"], "job_wait")
            ready[0] = True
            result = graph.invoke(Command(resume={"action": "continue"}), config)
            self.assertEqual(result["__interrupt__"][0].value["kind"], "human_review")
        self.assertEqual(submitted[0]["idempotency_key"], submitted[1]["idempotency_key"])
        self.assertTrue(all(body["max_attempts"] == 1 for body in submitted))
        self.assertEqual(submitted[-1]["payload"]["input_refs"], ["artifact://input", "artifact://metrics", "artifact://nox"])

    def test_wait_advances_all_stages_but_never_approves(self) -> None:
        submitted = []
        def handle(request):
            if request.method == "POST":
                body = json.loads(request.content)
                submitted.append(body)
                return httpx.Response(200, json={"id": body["agent_slug"], "status": "QUEUED"})
            agent = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"id": agent, "status": "SUCCEEDED", "result": self.fixtures[agent]})
        with httpx.Client(transport=httpx.MockTransport(handle), base_url="http://test") as client, \
             sqlite3.connect(":memory:", check_same_thread=False) as connection:
            graph = build_weekly_review_graph(SqliteSaver(connection), client=client, provider="deepseek")
            config = {"configurable": {"thread_id": "wait"}}
            result = graph.invoke({"input_refs": ["artifact://input"], "artifact_refs": [], "approved": False}, config)
            result = wait_for_jobs(graph, result, config, client)
            self.assertEqual(result["__interrupt__"][0].value["kind"], "human_review")
            self.assertFalse(result["approved"])
            self.assertEqual(result["artifact_refs"], ["artifact://metrics", "artifact://nox", "artifact://writing"])
        self.assertEqual({body["estimated_tokens"] for body in submitted}, {20000})

    def test_wait_timeout_keeps_checkpoint(self) -> None:
        def handle(request):
            return httpx.Response(200, json={"id": "pending", "status": "QUEUED"})
        with httpx.Client(transport=httpx.MockTransport(handle), base_url="http://test") as client, \
             sqlite3.connect(":memory:", check_same_thread=False) as connection:
            graph = build_weekly_review_graph(SqliteSaver(connection), client=client, provider="deepseek")
            config = {"configurable": {"thread_id": "timeout"}}
            result = graph.invoke({"input_refs": [], "artifact_refs": [], "approved": False}, config)
            with self.assertRaises(TimeoutError):
                wait_for_jobs(graph, result, config, client, timeout=0)
            self.assertTrue(graph.get_state(config).next)

    def test_missing_artifacts_are_rejected(self) -> None:
        for result in ({}, {"artifact_refs": []}, {"artifact_refs": [""]}):
            with self.assertRaises(ValueError):
                validate_artifacts(result)


class WeeklyRouteTests(unittest.TestCase):
    def make_router(self, directory):
        fixtures = WeeklyReviewPilotTests.fixtures
        return WeeklyReviewRouter(Path(directory), "http://unused", "admin", provider="test",
            graph_factory=lambda saver, client: build_weekly_review_graph(saver, fixtures=fixtures))

    def test_repeated_intake_has_one_checkpoint_and_stops_for_human(self):
        with tempfile.TemporaryDirectory() as directory:
            router = self.make_router(directory)
            body = {"request_id": "same-request", "input_text": "synthetic evidence", "allow_role_sharing": True}
            first = router.submit(body)
            router.threads["same-request"].join(timeout=5)
            second = router.submit(body)
            self.assertEqual(first["thread_id"], second["thread_id"])
            self.assertEqual(second["status"], "REVIEW")
            self.assertFalse(second["approved"])
            self.assertEqual(len(second["artifact_refs"]), 3)
            with self.assertRaises(RouteError) as caught:
                router.submit({**body, "input_text": "different"})
            self.assertEqual(caught.exception.status, 409)
            self.assertNotIn("input_text", second)
            router.close()

    def test_intake_requires_role_sharing_acknowledgement(self):
        with tempfile.TemporaryDirectory() as directory:
            router = self.make_router(directory)
            for body in ({"request_id": "id", "input_text": "private"},
                         {"request_id": "../bad", "input_text": "private", "allow_role_sharing": True}):
                with self.assertRaises(RouteError):
                    router.submit(body)
            router.close()

    def test_cancelled_review_is_not_approved_and_unknown_fields_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            router = self.make_router(directory)
            body = {"request_id": "cancel-test", "input_text": "test", "allow_role_sharing": True}
            with self.assertRaises(RouteError):
                router.submit({**body, "risk_level": "high"})
            router.submit(body)
            router.threads["cancel-test"].join(timeout=5)
            result = router.cancel("cancel-test")
            self.assertEqual(result["status"], "CANCELLED")
            self.assertFalse(result["approved"])
            self.assertEqual(router.cancel("cancel-test")["status"], "CANCELLED")
            router.close()
            with self.assertRaises(RouteError) as stopped:
                router.submit({**body, "request_id": "after-stop"})
            self.assertEqual(stopped.exception.status, 503)

    def test_route_credential_cannot_approve_and_unknown_token_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            router = self.make_router(directory)
            token = "route-only-" + "x" * 32
            server = create_route_server(router, token, host="127.0.0.1", port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False) as client:
                    denied = client.post("/v1/weekly-reviews", json={})
                    self.assertEqual(denied.status_code, 403)
                    approval = client.post("/v1/weekly-reviews/id/approve", headers={"Authorization": "Bearer " + token})
                    self.assertEqual(approval.status_code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                router.close()


if __name__ == "__main__":
    unittest.main()