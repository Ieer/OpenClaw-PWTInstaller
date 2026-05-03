from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from mission_control_api.app.config import Settings, load_settings
from mission_control_api.app.main import (
    _build_chat_inject_script,
    _build_handoff_task_update,
    _build_task_claim_update,
    _build_task_completion_update,
    _build_task_review_update,
    _normalize_gateway_agent_slug,
    _rewrite_avatar_paths,
    _rewrite_control_ui_config,
    _rewrite_inline_assistant_avatar_vars,
    _suggest_task_route,
    publish_event,
)


class _FakeRedisStream:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, dict]] = []

    async def xadd(self, stream_key: str, fields: dict, **kwargs):
        self.calls.append((stream_key, fields, kwargs))
        return "1-0"


class OrchestrationGuardTests(unittest.TestCase):
    def test_gateway_agent_slug_accepts_known_agent_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "nox").mkdir()
            settings = Settings(agent_homes_dir=tmp, agent_manifest_path="/missing")

            self.assertEqual(_normalize_gateway_agent_slug(settings, "NOX"), "nox")

    def test_gateway_agent_slug_rejects_unknown_or_invalid_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "nox").mkdir()
            settings = Settings(agent_homes_dir=tmp, agent_manifest_path="/missing")

            with self.assertRaises(HTTPException) as unknown:
                _normalize_gateway_agent_slug(settings, "metrics")
            self.assertEqual(unknown.exception.status_code, 404)

            with self.assertRaises(HTTPException) as invalid:
                _normalize_gateway_agent_slug(settings, "nox.example")
            self.assertEqual(invalid.exception.status_code, 400)

    def test_handoff_task_update_assigns_target_agent(self) -> None:
        payload, errors = _build_handoff_task_update(
            current_status="IN PROGRESS",
            current_assignee="metrics",
            target_agent="writing",
        )

        self.assertEqual(errors, [])
        self.assertEqual(payload["previous_assignee"], "metrics")
        self.assertEqual(payload["previous_status"], "IN PROGRESS")
        self.assertEqual(payload["new_assignee"], "writing")
        self.assertEqual(payload["new_status"], "ASSIGNED")
        self.assertTrue(payload["handoff_applied"])

    def test_handoff_task_update_rejects_done_task(self) -> None:
        payload, errors = _build_handoff_task_update(
            current_status="DONE",
            current_assignee="metrics",
            target_agent="writing",
        )

        self.assertIn("cannot handoff DONE task", errors)
        self.assertFalse(payload["handoff_applied"])

    def test_task_claim_update_moves_task_in_progress(self) -> None:
        payload, errors = _build_task_claim_update(
            current_status="ASSIGNED",
            current_assignee="metrics",
            agent_slug="metrics",
        )

        self.assertEqual(errors, [])
        self.assertEqual(payload["previous_assignee"], "metrics")
        self.assertEqual(payload["previous_status"], "ASSIGNED")
        self.assertEqual(payload["new_assignee"], "metrics")
        self.assertEqual(payload["new_status"], "IN PROGRESS")
        self.assertTrue(payload["claim_applied"])

    def test_task_claim_update_rejects_other_assignee_without_force(self) -> None:
        payload, errors = _build_task_claim_update(
            current_status="ASSIGNED",
            current_assignee="metrics",
            agent_slug="writing",
        )

        self.assertIn("task already assigned to another agent: metrics", errors)
        self.assertFalse(payload["claim_applied"])

    def test_task_claim_update_force_reassigns_other_assignee(self) -> None:
        payload, errors = _build_task_claim_update(
            current_status="REVIEW",
            current_assignee="metrics",
            agent_slug="writing",
            force=True,
        )

        self.assertEqual(errors, [])
        self.assertEqual(payload["previous_status"], "REVIEW")
        self.assertEqual(payload["new_assignee"], "writing")
        self.assertEqual(payload["new_status"], "IN PROGRESS")
        self.assertTrue(payload["force"])

    def test_task_completion_update_marks_done_with_artifacts(self) -> None:
        payload, errors = _build_task_completion_update(
            current_status="IN PROGRESS",
            current_assignee="writing",
            agent_slug="writing",
            summary="Draft is ready",
            artifact_refs=["artifact://weekly-summary"],
        )

        self.assertEqual(errors, [])
        self.assertEqual(payload["previous_status"], "IN PROGRESS")
        self.assertEqual(payload["new_status"], "DONE")
        self.assertEqual(payload["summary"], "Draft is ready")
        self.assertEqual(payload["artifact_refs"], ["artifact://weekly-summary"])
        self.assertTrue(payload["completion_applied"])
        self.assertFalse(payload["review_requested"])

    def test_task_completion_update_review_gate_requests_review(self) -> None:
        payload, errors = _build_task_completion_update(
            current_status="IN PROGRESS",
            current_assignee="writing",
            agent_slug="writing",
            review_gate=True,
        )

        self.assertEqual(errors, [])
        self.assertEqual(payload["new_status"], "REVIEW")
        self.assertTrue(payload["review_gate"])
        self.assertTrue(payload["review_requested"])

    def test_task_completion_update_rejects_inbox_without_force(self) -> None:
        payload, errors = _build_task_completion_update(
            current_status="INBOX",
            current_assignee=None,
            agent_slug="nox",
        )

        self.assertIn("task must be IN PROGRESS or REVIEW before completion", errors)
        self.assertFalse(payload["completion_applied"])

    def test_task_completion_update_rejects_other_assignee_without_force(self) -> None:
        payload, errors = _build_task_completion_update(
            current_status="IN PROGRESS",
            current_assignee="metrics",
            agent_slug="writing",
        )

        self.assertIn("task assigned to another agent: metrics", errors)
        self.assertFalse(payload["completion_applied"])

    def test_task_completion_update_force_override(self) -> None:
        payload, errors = _build_task_completion_update(
            current_status="ASSIGNED",
            current_assignee="metrics",
            agent_slug="writing",
            force=True,
        )

        self.assertEqual(errors, [])
        self.assertEqual(payload["previous_status"], "ASSIGNED")
        self.assertEqual(payload["new_assignee"], "writing")
        self.assertEqual(payload["new_status"], "DONE")
        self.assertTrue(payload["force"])

    def test_task_completion_update_rejects_blank_artifact_ref(self) -> None:
        payload, errors = _build_task_completion_update(
            current_status="IN PROGRESS",
            current_assignee="writing",
            agent_slug="writing",
            artifact_refs=["artifact://ok", ""],
        )

        self.assertIn("artifact_refs must contain non-empty strings", errors)
        self.assertEqual(payload["artifact_refs"], ["artifact://ok"])
        self.assertFalse(payload["completion_applied"])

    def test_task_review_update_approves_review_to_done(self) -> None:
        payload, errors = _build_task_review_update(
            current_status="REVIEW",
            current_assignee="writing",
            reviewer_slug="nox",
            decision="approve",
            notes="Looks good",
        )

        self.assertEqual(errors, [])
        self.assertEqual(payload["previous_status"], "REVIEW")
        self.assertEqual(payload["new_status"], "DONE")
        self.assertEqual(payload["new_assignee"], "writing")
        self.assertEqual(payload["reviewer"], "nox")
        self.assertEqual(payload["decision"], "approve")
        self.assertEqual(payload["notes"], "Looks good")
        self.assertTrue(payload["review_applied"])

    def test_task_review_update_requests_changes_to_in_progress(self) -> None:
        payload, errors = _build_task_review_update(
            current_status="REVIEW",
            current_assignee="writing",
            reviewer_slug="nox",
            decision="changes requested",
            artifact_refs=["artifact://review-notes"],
        )

        self.assertEqual(errors, [])
        self.assertEqual(payload["new_status"], "IN PROGRESS")
        self.assertEqual(payload["decision"], "changes_requested")
        self.assertEqual(payload["artifact_refs"], ["artifact://review-notes"])

    def test_task_review_update_rejects_non_review_without_force(self) -> None:
        payload, errors = _build_task_review_update(
            current_status="IN PROGRESS",
            current_assignee="writing",
            reviewer_slug="nox",
            decision="approve",
        )

        self.assertIn("task must be REVIEW before review decision", errors)
        self.assertFalse(payload["review_applied"])

    def test_task_review_update_force_allows_non_review_transition(self) -> None:
        payload, errors = _build_task_review_update(
            current_status="IN PROGRESS",
            current_assignee="writing",
            reviewer_slug="nox",
            decision="done",
            force=True,
        )

        self.assertEqual(errors, [])
        self.assertEqual(payload["new_status"], "DONE")
        self.assertTrue(payload["force"])

    def test_task_review_update_rejects_invalid_decision(self) -> None:
        payload, errors = _build_task_review_update(
            current_status="REVIEW",
            current_assignee="writing",
            reviewer_slug="nox",
            decision="maybe",
        )

        self.assertTrue(any(error.startswith("review decision invalid") for error in errors))
        self.assertFalse(payload["review_applied"])

    def test_task_route_preview_prefers_explicit_assignee(self) -> None:
        preview = _suggest_task_route(
            title="统计过去 7 天各 Agent 活跃度",
            tags=["reporting", "panopticon"],
            assignee="metrics",
            known_agents={"nox", "metrics"},
        )

        self.assertEqual(preview.suggested_assignee, "metrics")
        self.assertEqual(preview.confidence, 1.0)
        self.assertEqual(preview.matched_rules, ["explicit_assignee"])

    def test_task_route_preview_suggests_agent_from_tags_and_title(self) -> None:
        preview = _suggest_task_route(
            title="生成本周增长实验转化分析",
            tags=["growth", "experiment", "conversion"],
            known_agents={"nox", "growth", "metrics"},
        )

        self.assertEqual(preview.suggested_assignee, "growth")
        self.assertGreater(preview.confidence, 0.5)
        self.assertIn("keyword:growth", preview.matched_rules)

    def test_task_route_preview_rejects_unknown_explicit_assignee(self) -> None:
        preview = _suggest_task_route(
            title="整理周报",
            tags=["writing"],
            assignee="unknown",
            known_agents={"writing"},
        )

        self.assertIsNone(preview.suggested_assignee)
        self.assertEqual(preview.confidence, 0.0)
        self.assertEqual(preview.matched_rules, ["explicit_assignee_unknown"])

    def test_rewrite_control_ui_config_prefixes_existing_avatar(self) -> None:
        payload = {
            "basePath": "",
            "assistantName": "Northstar Nox",
            "assistantAvatar": "/avatar/main",
            "assistantAvatarStatus": "local",
        }

        updated = json.loads(_rewrite_control_ui_config(json.dumps(payload).encode("utf-8"), "nox"))

        self.assertEqual(updated["basePath"], "/chat/nox")
        self.assertEqual(updated["assistantAvatar"], "/chat/nox/avatar/main")
        self.assertEqual(updated["assistantAvatarStatus"], "local")

    def test_rewrite_control_ui_config_uses_data_fallback_for_missing_avatar(self) -> None:
        payload = {
            "basePath": "",
            "assistantName": "Northstar Nox",
            "assistantAvatar": "/avatar/main",
            "assistantAvatarSource": "avatars/nox.png",
            "assistantAvatarStatus": "none",
            "assistantAvatarReason": "missing",
        }

        updated = json.loads(_rewrite_control_ui_config(json.dumps(payload).encode("utf-8"), "nox"))

        self.assertEqual(updated["basePath"], "/chat/nox")
        self.assertTrue(updated["assistantAvatar"].startswith("data:image/svg+xml;base64,"))
        self.assertEqual(updated["assistantAvatarStatus"], "data")
        self.assertIsNone(updated["assistantAvatarReason"])

    def test_rewrite_inline_assistant_avatar_vars_prefixes_without_clearing(self) -> None:
        html = '<script>window.__OPENCLAW_ASSISTANT_AVATAR__="/avatar/main";</script>'

        updated = _rewrite_inline_assistant_avatar_vars(html, "nox")

        self.assertIn('window.__OPENCLAW_ASSISTANT_AVATAR__="/chat/nox/avatar/main"', updated)
        self.assertNotIn('window.__OPENCLAW_ASSISTANT_AVATAR__=""', updated)

    def test_rewrite_avatar_paths_uses_data_fallback_for_missing_identity(self) -> None:
        payload = {
            "result": {
                "name": "Northstar Nox",
                "avatar": "/avatar/main",
                "avatarSource": "avatars/nox.png",
                "avatarStatus": "none",
                "avatarReason": "missing",
            }
        }

        updated = _rewrite_avatar_paths(payload, "nox")

        identity = updated["result"]
        self.assertTrue(identity["avatar"].startswith("data:image/svg+xml;base64,"))
        self.assertEqual(identity["avatarStatus"], "data")
        self.assertIsNone(identity["avatarReason"])

    def test_chat_inject_script_handles_logo_avatar_fallback(self) -> None:
        script = _build_chat_inject_script("nox", "secret", dom_avatar_rewrite=True)

        self.assertIn("chat-avatar--logo", script)
        self.assertIn("classList.remove", script)
        self.assertIn("normalizeAvatar", script)
        self.assertIn("openclaw-app", script)
        self.assertIn("setInterval", script)

    def test_publish_event_applies_stream_maxlen(self) -> None:
        redis = _FakeRedisStream()

        asyncio.run(publish_event(redis, "mc:events", {"type": "test.event"}, maxlen=123))

        self.assertEqual(len(redis.calls), 1)
        stream_key, fields, kwargs = redis.calls[0]
        self.assertEqual(stream_key, "mc:events")
        self.assertEqual(json.loads(fields["event"]), {"type": "test.event"})
        self.assertEqual(kwargs, {"maxlen": 123, "approximate": True})

    def test_publish_event_allows_unbounded_stream_when_maxlen_disabled(self) -> None:
        redis = _FakeRedisStream()

        asyncio.run(publish_event(redis, "mc:events", {"type": "test.event"}, maxlen=0))

        self.assertEqual(redis.calls[0][2], {})

    def test_load_settings_reads_redis_stream_maxlen(self) -> None:
        with patch.dict(os.environ, {"MC_REDIS_STREAM_MAXLEN": "42"}):
            self.assertEqual(load_settings().redis_stream_maxlen, 42)

        with patch.dict(os.environ, {"MC_REDIS_STREAM_MAXLEN": "invalid"}):
            self.assertEqual(load_settings().redis_stream_maxlen, 10000)


if __name__ == "__main__":
    unittest.main()
