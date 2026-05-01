---
name: self-heal
description: "nox workspace self-healing skill for Python packages, Rokid bridge, ByPy token, wjx-cli, workspace queues, Mission Control probes, release readiness, and future registry-driven repair items. Use when nox heartbeat, services, runtime tools, or release gates are degraded."
argument-hint: "Provide mode (diagnose/status/repair), optional item ID, and maximum risk level allowed."
---

# nox Self-Heal

This skill turns nox's heartbeat infrastructure recovery rules into a registry-driven, auditable self-healing workflow.

## Trigger

Use this skill when:

- The user asks for nox 自愈、恢复、巡检、修复、健康检查、降级分析, or repair planning.
- `HEARTBEAT.md` reports Python package, Rokid plugin, ByPy token, or wjx-cli issues.
- Mission Control reports nox degraded, stale, unreachable, or endpoint/container health failures.
- A release/rollback issue affects nox and needs safe dry-run diagnosis first.
- A new self-heal item needs to be added to nox.

Do not use this skill for unrelated roadmap advice unless infrastructure health is part of the task.

## Steps

1. Read the current constraints from `HEARTBEAT.md`, `memory/infra.md`, and this skill.
2. List available registry items with `scripts/self_heal_runner.py list-items` when the target item is unclear.
3. Run diagnosis before repair: `scripts/self_heal_runner.py diagnose` or `scripts/self_heal_runner.py diagnose --item <id>`.
4. Classify failures by risk level:
   - L0: read-only checks;
   - L1: local idempotent repair;
   - L2: container/service restart or runtime refresh;
   - L3: token or external service recovery;
   - L4: rollout, rollback, destructive, or external-commit actions.
5. For repair, use the narrowest item and the lowest allowed risk level. Do not run broad repair if a single item is enough.
6. For L2 repair, require explicit L2 allowance and enforce cooldown/max-attempts.
7. For L3/L4 repair, require Review-approved input, redact all secrets, and write audit evidence.
8. After any repair, run postcheck and update `memory/heartbeat-state.json` with per-item status.
9. Produce a short report: healthy items, degraded items, repaired items, skipped items, Review-required items, and rollback hints.

## Output

- `artifacts/<task_id>/heal-report.md`
- `artifacts/<task_id>/artifact.json`
- `sources/<task_id>/health-snapshot.json`
- `sources/<task_id>/repair-log.jsonl`
- `memory/heartbeat-state.json` per-item health summary

When the caller only needs a quick heartbeat check, a compact JSON diagnosis is acceptable.

## Review Gate

Review is required before:

- ByPy token restore, wjx credential restore, OAuth flow, or any credential-adjacent operation.
- nox container restart through `agent-controller` or Docker.
- release rollout, release rollback, image retagging, or runtime replacement.
- deletion, overwrite, public posting, external commitment, or irreversible change.
- Any repair item with `requires_review: true` or risk level L3/L4.

Never record token, API key, `Authorization`, `linkSecret`, cookie, or credential payloads in logs. Use redaction.
