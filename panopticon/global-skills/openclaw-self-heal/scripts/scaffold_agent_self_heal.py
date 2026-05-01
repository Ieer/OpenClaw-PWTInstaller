#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parents[4]
MANIFEST_PATH = ROOT / "panopticon" / "agents.manifest.yaml"
NOX_RUNNER = ROOT / "panopticon" / "workspaces" / "nox" / "skills" / "self-heal" / "scripts" / "self_heal_runner.py"


def load_enabled_agents() -> set[str]:
    if yaml is None:
        raise SystemExit("PyYAML is required to read panopticon/agents.manifest.yaml")
    payload = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("agents"), list):
        raise SystemExit(f"invalid manifest: {MANIFEST_PATH}")
    out: set[str] = set()
    for item in payload["agents"]:
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        slug = str(item.get("slug") or "").strip()
        if slug:
            out.add(slug)
    return out


def skill_doc(slug: str) -> str:
    return f"""---
name: self-heal
description: \"{slug} workspace self-healing skill generated from openclaw-self-heal. Use for endpoint, workspace contract, Mission Control, release dry-run, and future registry-driven repair items.\"
argument-hint: \"Provide mode (diagnose/status/repair), optional item ID, and maximum risk level allowed.\"
---

# {slug} Self-Heal

This workspace skill is generated from the global `openclaw-self-heal` protocol.

## Trigger

Use this skill when:

- `{slug}` is degraded, idle unexpectedly, unreachable, or missing runtime capabilities.
- Mission Control reports `{slug}` endpoint/container health failures.
- A release/rollback issue affects `{slug}` and needs dry-run diagnosis.
- A new `{slug}` self-heal item needs to be added to the registry.

## Steps

1. Start with `scripts/self_heal_runner.py diagnose --max-level L0 --exit-zero`.
2. Use `scripts/self_heal_runner.py list-items` to inspect registered checks.
3. Repair only the narrowest failing item.
4. Require Review approval for L3/L4 or credential/external-service actions.
5. After repair, run postcheck and update `memory/heartbeat-state.json`.
6. Add future items through `items.yaml`; do not hard-code one-off checks in heartbeat text.

## Output

- `artifacts/<task_id>/heal-report.md`
- `artifacts/<task_id>/artifact.json`
- `sources/<task_id>/health-snapshot.json`
- `sources/<task_id>/repair-log.jsonl`
- `memory/heartbeat-state.json`

## Review Gate

Review is required before:

- credential, token, OAuth, cookie, or external API repair;
- container restart through Docker or `agent-controller`;
- rollout, rollback, image retagging, deletion, overwrite, publish, or external commitment;
- any item with `requires_review: true` or risk level L3/L4.
"""


def registry_doc(slug: str) -> str:
    endpoint_id = f"agent.{slug}_endpoint"
    return f"""schema_version: 1
items:
  - id: workspace.state_queue
    title: {slug} state queue and Review gates
    category: workspace
    owner_scope: {slug}
    risk_level: L0
    requires_review: false
    secret_policy: none
    timeout_seconds: 10
    cooldown_seconds: 0
    max_attempts_per_day: 0
    dependencies:
      files:
        - state
    probe:
      command: test -d state && find state -maxdepth 2 -type f | wc -l >/dev/null
    success_criteria: state directory is readable and can be scanned for pending gates.
    rollback_hint: Recreate state directory from workspace skeleton if missing.
    evidence_paths:
      - state

  - id: workspace.contract
    title: {slug} workspace contract probe
    category: workspace
    owner_scope: {slug}
    risk_level: L1
    requires_review: false
    secret_policy: none
    timeout_seconds: 30
    cooldown_seconds: 3600
    max_attempts_per_day: 3
    dependencies:
      commands: [python3]
      files:
        - panopticon/tools/test_workspace_contract.py
    probe:
      command: python3 panopticon/tools/test_workspace_contract.py --agents {slug} --skip-lifecycle
      cwd: repo
    success_criteria: Workspace required directories exist and are writable.
    rollback_hint: Run the workspace contract test with --auto-create after confirming no unexpected data loss.
    evidence_paths:
      - artifacts
      - sources
      - state

  - id: mission_control.api_health
    title: Mission Control API health endpoint
    category: service
    owner_scope: mission_control
    risk_level: L0
    requires_review: false
    secret_policy: none
    timeout_seconds: 10
    cooldown_seconds: 0
    max_attempts_per_day: 0
    dependencies:
      commands: [curl]
    probe:
      command: curl -fsS --max-time 5 http://localhost:18910/health >/dev/null
      cwd: repo
    success_criteria: Mission Control API /health returns success.
    rollback_hint: Use panopticon/tools/recover_mission_control_gateway.sh for gateway/API repair after checking logs.
    evidence_paths:
      - panopticon/tools/check_panopticon_services.sh

  - id: {endpoint_id}
    title: {slug} Gateway and Bridge endpoints
    category: service
    owner_scope: {slug}
    risk_level: L0
    requires_review: false
    secret_policy: none
    timeout_seconds: 30
    cooldown_seconds: 0
    max_attempts_per_day: 0
    dependencies:
      files:
        - panopticon/tools/check_agent_endpoints.sh
    probe:
      command: bash panopticon/tools/check_agent_endpoints.sh {slug}
      cwd: repo
    success_criteria: {slug} gateway and bridge TCP endpoints are reachable.
    rollback_hint: Restart {slug} only after endpoint failure is confirmed and L2 Review policy is satisfied.
    evidence_paths:
      - panopticon/tools/check_agent_endpoints.sh

  - id: release.preflight_dry_run
    title: Release rollout preflight dry-run for {slug}
    category: release
    owner_scope: global
    risk_level: L0
    requires_review: false
    secret_policy: none
    timeout_seconds: 60
    cooldown_seconds: 0
    max_attempts_per_day: 0
    dependencies:
      commands: [python3]
      files:
        - tools/rollout_release_upgrade.py
        - openclaw-release.yaml
        - panopticon/agents.manifest.yaml
    probe:
      command: python3 tools/rollout_release_upgrade.py --mode fast-panopticon --dry-run {slug}
      cwd: repo
    success_criteria: Release rollout plan can be generated without changing containers.
    rollback_hint: Do not run rollout or rollback from self-heal without a separate Review-approved release action.
    evidence_paths:
      - .release-state

  - id: release.rollback_readiness
    title: Release rollback metadata readiness
    category: release
    owner_scope: global
    risk_level: L0
    requires_review: false
    secret_policy: none
    timeout_seconds: 10
    cooldown_seconds: 0
    max_attempts_per_day: 0
    dependencies:
      files:
        - tools/rollback_release_upgrade.py
    probe:
      command: test -f .release-state/last-rollout.json
      cwd: repo
    success_criteria: Last rollout metadata exists before rollback is considered.
    rollback_hint: If metadata is missing, reconstruct rollback inputs manually before taking action.
    evidence_paths:
      - .release-state/last-rollout.json
"""


def write_file(path: Path, content: str, *, dry_run: bool, force: bool) -> None:
    if path.exists() and not force:
        raise SystemExit(f"refusing to overwrite existing file without --force: {path}")
    if dry_run:
        print(f"[DRY-RUN] would write {path.relative_to(ROOT)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def copy_runner(target: Path, *, dry_run: bool, force: bool) -> None:
    if not NOX_RUNNER.exists():
        raise SystemExit(f"runner template not found: {NOX_RUNNER}")
    if target.exists() and not force:
        raise SystemExit(f"refusing to overwrite existing file without --force: {target}")
    if dry_run:
        print(f"[DRY-RUN] would copy runner to {target.relative_to(ROOT)}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(NOX_RUNNER, target)
    print(f"copied {target.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a workspace-local self-heal skill for a Panopticon agent")
    parser.add_argument("--agent", required=True, help="Enabled agent slug from panopticon/agents.manifest.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Print planned files without writing")
    parser.add_argument("--force", action="store_true", help="Overwrite existing generated files")
    args = parser.parse_args()

    slug = args.agent.strip()
    enabled_agents = load_enabled_agents()
    if slug not in enabled_agents:
        raise SystemExit(f"unknown or disabled agent: {slug}; enabled agents: {', '.join(sorted(enabled_agents))}")

    skill_dir = ROOT / "panopticon" / "workspaces" / slug / "skills" / "self-heal"
    write_file(skill_dir / "SKILL.md", skill_doc(slug), dry_run=args.dry_run, force=args.force)
    write_file(skill_dir / "items.yaml", registry_doc(slug), dry_run=args.dry_run, force=args.force)
    copy_runner(skill_dir / "scripts" / "self_heal_runner.py", dry_run=args.dry_run, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
