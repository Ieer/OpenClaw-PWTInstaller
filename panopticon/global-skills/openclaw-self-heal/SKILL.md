---
name: openclaw-self-heal
description: "OpenClaw/Panopticon self-healing protocol for health probes, repair item registries, risk-gated remediation, audit reports, Mission Control observability, and controlled rollout/rollback recovery. Use when services are degraded, a workspace heartbeat reports blockers, a new self-heal item must be added, or release/agent recovery needs a safe diagnostic-first workflow."
argument-hint: "Provide the target agent/workspace, symptom, desired mode (diagnose or repair), and max allowed risk level."
user-invocable: true
disable-model-invocation: false
---

# OpenClaw Self-Heal

A diagnostic-first self-healing protocol for OpenClaw agents, Panopticon services, workspace health, and release recovery.

## When to Use

Use this skill when:

- An OpenClaw agent is degraded, idle unexpectedly, unreachable, or missing runtime capabilities.
- A workspace heartbeat reports blocked infrastructure items.
- Mission Control shows endpoint, container, readiness, or observability failures.
- A release rollout or rollback needs preflight, version-gate, or recovery readiness checks.
- A new self-heal item must be added in a controlled, testable way.

Do not use this skill for destructive remediation without an explicit Review-approved decision.

## Quick Start

1. Start with diagnosis. Do not repair before collecting a health snapshot.
2. Identify the relevant registry item by `id`, `category`, `owner_scope`, and `risk_level`.
3. Run only the lowest risk level that can resolve the issue.
4. Require Review approval before any L3/L4 action or any action touching credentials, external services, rollout, rollback, deletion, or public commitments.
5. Write a report with precheck, action taken, postcheck, skipped actions, and rollback hints.
6. Promote only stable, reusable findings to long-term memory or documentation.

To scaffold the same self-heal pattern for another Panopticon agent, run the scaffold script in dry-run first:

- `scripts/scaffold_agent_self_heal.py --agent <slug> --dry-run`

Then run it without `--dry-run` only after confirming that the generated registry contains no nox-specific token, Rokid, ByPy, or wjx items.

## Execution Rules

### Risk levels

| Level | Meaning | Default execution policy |
| --- | --- | --- |
| L0 | Read-only diagnosis | Always allowed |
| L1 | Low-risk local repair | Allowed if idempotent and bounded |
| L2 | Service restart or local runtime refresh | Requires explicit allow flag, cooldown, and postcheck |
| L3 | Token, external service, or credential-adjacent repair | Requires Review-approved gate and redaction |
| L4 | Destructive, rollout, rollback, delete, publish, or external commitment | Diagnose only unless a separate Review-approved runbook authorizes execution |

### Item contract

Every self-heal item must declare:

- `id`: stable unique identifier, for example `python.pil_import`.
- `title`: human-readable label.
- `category`: one of `runtime`, `plugin`, `token`, `service`, `release`, `storage`, `config`, `knowledge`, `external_api`, `workspace`.
- `owner_scope`: `global`, `mission_control`, `agent`, or a workspace slug such as `nox`.
- `risk_level`: `L0`, `L1`, `L2`, `L3`, or `L4`.
- `probe`: read-only command or script.
- `repair`: optional idempotent remediation command or script.
- `postcheck`: validation after repair.
- `success_criteria`: what proves the item is healthy.
- `dependencies`: required files, commands, services, mounts, or environment variables.
- `timeout_seconds`, `cooldown_seconds`, and `max_attempts_per_day`.
- `requires_review` and `secret_policy`.
- `rollback_hint` and `evidence_paths`.

### New item intake

When adding a new item:

1. Define the item ID and category.
2. Choose the lowest accurate risk level.
3. Add a read-only probe first.
4. Add success criteria that do not rely only on process exit code.
5. Add repair and postcheck only if the repair is bounded and idempotent.
6. Add fixtures for dry-run success and at least one failure case.
7. Run the skill/registry validator.
8. Document Review Gate behavior for L2/L3/L4 items.

### Multi-agent portability

Use three portability tiers:

1. **Platform-generic items**: shared by all agents, for example Mission Control health, release dry-run, rollback metadata, and Panopticon service checks.
2. **Slug-parameterized items**: reusable after replacing the target agent slug, for example endpoint checks, workspace contract checks, and fast-panopticon rollout dry-run.
3. **Agent-specific items**: must be owned by one workspace, for example nox Rokid bridge, ByPy token, wjx-cli credentials, email provider tokens, trading risk gates, or health data privacy checks.

Do not copy an agent-specific item to another agent unless the target agent owns the same integration and has an explicit Review Gate.

Recommended first registry for every agent:

- `workspace.state_queue`
- `workspace.contract`
- `mission_control.api_health`
- `agent.<slug>_endpoint`
- `release.preflight_dry_run`
- `release.rollback_readiness`

Add role-specific items only after the generic registry runs cleanly.

## Deliverables

A self-heal run should produce:

- `artifacts/<task_id>/heal-report.md` — human-readable diagnosis and remediation summary.
- `artifacts/<task_id>/artifact.json` — structured result with per-item status.
- `sources/<task_id>/health-snapshot.json` — pre/post health evidence.
- `sources/<task_id>/repair-log.jsonl` — timestamped, redacted action log.

The summary should include:

- overall status: `ok`, `degraded`, `failed`, or `review_required`;
- checked item count, failed item count, repaired item count;
- skipped repair reasons;
- Review-required actions;
- rollback hints.

## Completeness Checklist

A self-heal implementation is complete enough to extend when it has:

- a machine-readable item registry;
- a runner that supports `list-items`, `diagnose`, `repair`, `status`, and `report`;
- risk gates for L2/L3/L4;
- cooldown and max-attempt enforcement;
- token and secret redaction;
- per-item state history;
- validator checks for registry schema;
- dry-run and failure fixtures for each new item;
- Mission Control or script-level observability summary.

Target maturity: 8.5/10 before enabling recurring repair automation.

## References

- Multi-agent portability assessment: `references/multi-agent-portability.md`
- Agent scaffold script: `scripts/scaffold_agent_self_heal.py`
