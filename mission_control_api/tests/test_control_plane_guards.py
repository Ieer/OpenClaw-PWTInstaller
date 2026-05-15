from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from mission_control_api.app.config import Settings
from mission_control_api.app.main import (
    _build_agent_skills_detail,
    _compute_lexical_overlap,
    _default_validation_policy,
    _forward_agent_control,
    _lifecycle_score_adjustment,
    _mapping_by_agent,
    _normalize_control_ui_origin,
    _policy_specificity_score,
    _rewrite_control_ui_ws_request,
    _sanitize_connect_auth,
    _scan_global_skills,
    _scan_workspace_skills,
    _task_pattern_matches,
)
from mission_control_api.app.schemas import AgentSkillMappingOut


def _write_skill(root: Path, slug: str, *, name: str | None = None) -> None:
    skill_dir = root / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\n"
        f"name: {name or slug}\n"
        f"description: {slug} test skill\n"
        "---\n\n"
        f"# {name or slug}\n",
        encoding="utf-8",
    )


class ChatProxyHelperTests(unittest.TestCase):
    def test_control_ui_origin_normalizes_loopback_without_changing_lan_hosts(self) -> None:
        self.assertEqual(
            _normalize_control_ui_origin("http://127.0.0.1:18920"),
            "http://localhost:18920",
        )
        self.assertEqual(
            _normalize_control_ui_origin("https://127.0.0.1:18920"),
            "https://localhost:18920",
        )
        self.assertEqual(
            _normalize_control_ui_origin("http://192.168.1.3:18920"),
            "http://192.168.1.3:18920",
        )
        self.assertIsNone(_normalize_control_ui_origin(None))

    def test_connect_auth_sanitizer_strips_stale_device_fields_and_injects_token(self) -> None:
        raw = json.dumps(
            {
                "type": "req",
                "method": "connect",
                "params": {
                    "deviceId": "old-device",
                    "client_id": "old-client",
                    "auth": {
                        "deviceToken": "stale",
                        "token": "old-token",
                    },
                },
            }
        )

        rewritten = json.loads(_sanitize_connect_auth(raw, "fresh-token"))
        self.assertEqual(rewritten["params"]["auth"], {"token": "fresh-token"})
        self.assertNotIn("deviceId", rewritten["params"])
        self.assertNotIn("client_id", rewritten["params"])

    def test_control_ui_ws_request_rewrite_caps_expensive_initial_requests(self) -> None:
        settings = Settings(chat_history_limit=5, chat_sessions_include_unknown=False)

        history = json.loads(
            _rewrite_control_ui_ws_request(
                json.dumps({"type": "req", "method": "chat.history", "params": {"limit": 500}}),
                settings,
            )
        )
        sessions = json.loads(
            _rewrite_control_ui_ws_request(
                json.dumps({"type": "req", "method": "sessions.list", "params": {"includeUnknown": True}}),
                settings,
            )
        )

        self.assertEqual(history["params"]["limit"], 5)
        self.assertIs(sessions["params"]["includeUnknown"], False)


class SkillsDriftTests(unittest.TestCase):
    def test_agent_skills_detail_reports_missing_mapped_and_overlapping_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            global_root = root / "global-skills"
            agent_homes = root / "agent-homes"
            workspaces = root / "workspaces"

            _write_skill(global_root, "artifact", name="Global Artifact")
            _write_skill(agent_homes / "nox" / "skills", "artifact", name="Workspace Artifact")
            _write_skill(workspaces / "nox" / "runtime-skills", "artifact", name="Runtime Artifact")
            agent_homes.joinpath("nox", "openclaw.json").write_text(
                json.dumps({"skills": {"load": {"extraDirs": ["/home/node/.openclaw/workspace/runtime-skills"]}}}),
                encoding="utf-8",
            )

            settings = Settings(
                global_skills_dir=str(global_root),
                agent_homes_dir=str(agent_homes),
                workspaces_dir=str(workspaces),
                agent_manifest_path="/missing-agent-manifest.yaml",
            )
            global_skills = _scan_global_skills(settings)
            workspace_groups = _scan_workspace_skills(settings)
            mapping_rows = [
                AgentSkillMappingOut(id=uuid4(), agent_slug="nox", skill_slug="artifact", created_at=datetime.now(timezone.utc)),
                AgentSkillMappingOut(id=uuid4(), agent_slug="nox", skill_slug="missing-global", created_at=datetime.now(timezone.utc)),
            ]

            detail = _build_agent_skills_detail(
                settings,
                agent_slug="nox",
                label_map={"nox": "Nox"},
                global_by_slug={item.slug: item for item in global_skills},
                workspace_by_agent={group.agent_slug: list(group.skills) for group in workspace_groups},
                mapping_by_agent=_mapping_by_agent(mapping_rows),
            )

        categories = {item.category for item in detail.drift}
        self.assertIn("mapped_global_skill_missing", categories)
        self.assertIn("workspace_overrides_global", categories)
        self.assertIn("runtime_overlaps_existing", categories)
        self.assertEqual(detail.runtime_skills[0].slug, "artifact")
        self.assertIn("Restart", detail.restart_hint)


class KnowledgePolicyResolveHelperTests(unittest.TestCase):
    def test_default_validation_policy_returns_copy_and_high_risk_guardrails(self) -> None:
        policy = _default_validation_policy("critical")
        self.assertTrue(policy["require_validation"])
        self.assertTrue(policy["require_approved"])
        self.assertTrue(policy["require_not_expired"])
        self.assertEqual(policy["min_confidence"], 0.85)

        policy["min_confidence"] = 0.1
        self.assertEqual(_default_validation_policy("critical")["min_confidence"], 0.85)

    def test_policy_matching_and_specificity_prioritize_targeted_rules(self) -> None:
        self.assertTrue(_task_pattern_matches("roadmap * launch", "Q2 roadmap mobile launch"))
        self.assertFalse(_task_pattern_matches("billing", "Q2 roadmap mobile launch"))
        self.assertEqual(
            _policy_specificity_score({"task_pattern": "roadmap*", "agent_slug": "nox", "source_type": "doc"}),
            7,
        )
        self.assertGreater(
            _policy_specificity_score({"task_pattern": "roadmap*", "agent_slug": "nox"}),
            _policy_specificity_score({"source_type": "doc"}),
        )

    def test_resolve_scoring_helpers_capture_lexical_and_lifecycle_signals(self) -> None:
        self.assertEqual(
            _compute_lexical_overlap("launch retention", "Retention launch plan", "", ["growth"]),
            1.0,
        )
        self.assertEqual(_compute_lexical_overlap("launch retention", "Finance notes", "", []), 0.0)
        self.assertGreater(_lifecycle_score_adjustment("preferred"), 0.0)
        self.assertLess(_lifecycle_score_adjustment("deprecated"), 0.0)
        self.assertEqual(_lifecycle_score_adjustment("active"), 0.0)


class AgentControlGuardTests(unittest.TestCase):
    def test_forward_agent_control_requires_controller_url_and_token(self) -> None:
        missing_url = Settings(agent_controller_url="", agent_controller_auth_token="controller-token")
        with self.assertRaises(HTTPException) as url_error:
            asyncio.run(_forward_agent_control(missing_url, agent="nox", action="restart"))
        self.assertEqual(url_error.exception.status_code, 503)
        self.assertIn("not configured", str(url_error.exception.detail))

        missing_token = Settings(agent_controller_url="http://controller:9091", agent_controller_auth_token=None)
        with self.assertRaises(HTTPException) as token_error:
            asyncio.run(_forward_agent_control(missing_token, agent="nox", action="restart"))
        self.assertEqual(token_error.exception.status_code, 503)
        self.assertIn("auth token", str(token_error.exception.detail))


if __name__ == "__main__":
    unittest.main()