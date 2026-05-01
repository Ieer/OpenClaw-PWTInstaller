#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

SCRIPT_PATH = Path(__file__).resolve()
SKILL_DIR = SCRIPT_PATH.parents[1]
WORKSPACE_ROOT = SCRIPT_PATH.parents[3]
REPO_ROOT = WORKSPACE_ROOT.parents[2]
AGENT_SLUG = WORKSPACE_ROOT.name
REGISTRY_PATH = SKILL_DIR / "items.yaml"
STATE_PATH = WORKSPACE_ROOT / "memory" / "heartbeat-state.json"

RISK_ORDER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}
SECRET_PATTERNS = [
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)((?:api[_-]?key|token|secret|linkSecret|password)\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(accessToken\"?\s*[:=]\s*\"?)[^\"\s,;]+"),
]


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timeout: bool = False


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact(text: str) -> str:
    out = str(text or "")
    for pattern in SECRET_PATTERNS:
        out = pattern.sub(r"\1<redacted>", out)
    return out


def load_registry(path: Path = REGISTRY_PATH) -> list[dict[str, Any]]:
    if yaml is None:
        raise SystemExit("PyYAML is required to read self-heal items.yaml")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"registry must be a mapping: {path}")
    items = payload.get("items")
    if not isinstance(items, list):
        raise SystemExit(f"registry must contain an items list: {path}")
    validate_items(items)
    return items


def validate_items(items: list[dict[str, Any]]) -> None:
    required = {
        "id",
        "title",
        "category",
        "owner_scope",
        "risk_level",
        "requires_review",
        "secret_policy",
        "timeout_seconds",
        "cooldown_seconds",
        "max_attempts_per_day",
        "probe",
        "success_criteria",
        "rollback_hint",
    }
    seen: set[str] = set()
    errors: list[str] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"item #{index} must be a mapping")
            continue
        item_id = str(item.get("id") or "").strip()
        if item_id in seen:
            errors.append(f"duplicate item id: {item_id}")
        if item_id:
            seen.add(item_id)
        missing = sorted(key for key in required if key not in item)
        if missing:
            errors.append(f"{item_id or f'item #{index}'} missing required fields: {', '.join(missing)}")
        risk = str(item.get("risk_level") or "").strip()
        if risk not in RISK_ORDER:
            errors.append(f"{item_id}: invalid risk_level {risk!r}")
        probe = item.get("probe")
        if not isinstance(probe, dict) or not str(probe.get("command") or "").strip():
            errors.append(f"{item_id}: probe.command is required")
        if RISK_ORDER.get(risk, 99) >= 3 and not bool(item.get("requires_review")):
            errors.append(f"{item_id}: L3/L4 items must set requires_review: true")
        secret_policy = str(item.get("secret_policy") or "").strip()
        if secret_policy not in {"none", "redact", "review_only", "forbidden"}:
            errors.append(f"{item_id}: invalid secret_policy {secret_policy!r}")
        for numeric in ("timeout_seconds", "cooldown_seconds", "max_attempts_per_day"):
            try:
                value = int(item.get(numeric))
            except Exception:
                errors.append(f"{item_id}: {numeric} must be an integer")
                continue
            if value < 0:
                errors.append(f"{item_id}: {numeric} must be >= 0")
    if errors:
        raise SystemExit("self-heal registry validation failed:\n- " + "\n- ".join(errors))


def item_by_id(items: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
    for item in items:
        if item.get("id") == item_id:
            return item
    raise SystemExit(f"unknown self-heal item: {item_id}")


def cwd_for(value: str | None) -> Path:
    if value == "repo":
        return REPO_ROOT
    if value == "skill":
        return SKILL_DIR
    return WORKSPACE_ROOT


def run_shell(command: str, *, cwd: Path, timeout_seconds: int) -> CommandResult:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=max(1, timeout_seconds),
            check=False,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        return CommandResult(
            ok=proc.returncode == 0,
            exit_code=int(proc.returncode),
            stdout=redact((proc.stdout or "").strip()),
            stderr=redact((proc.stderr or "").strip()),
            duration_ms=duration_ms,
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        return CommandResult(
            ok=False,
            exit_code=124,
            stdout=redact(str(exc.stdout or "").strip()),
            stderr=redact(str(exc.stderr or "").strip() or "timeout"),
            duration_ms=duration_ms,
            timeout=True,
        )


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"legacy_parse_error": True}
    return payload if isinstance(payload, dict) else {}


def write_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_self_heal_state(state: dict[str, Any]) -> dict[str, Any]:
    self_heal = state.get("self_heal")
    if not isinstance(self_heal, dict):
        self_heal = {}
        state["self_heal"] = self_heal
    self_heal.setdefault("schema_version", 1)
    checks = self_heal.get("checks")
    if not isinstance(checks, dict):
        self_heal["checks"] = {}
    repairs = self_heal.get("repairs")
    if not isinstance(repairs, list):
        self_heal["repairs"] = []
    return self_heal


def parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def repair_allowed(item: dict[str, Any], state: dict[str, Any], *, allow_l2: bool, review_approved: bool) -> tuple[bool, str]:
    item_id = str(item["id"])
    risk = str(item["risk_level"])
    if "repair" not in item:
        return False, "item has no repair command"
    if RISK_ORDER[risk] >= 4:
        return False, "L4 actions are diagnose-only in this runner"
    if RISK_ORDER[risk] == 2 and not allow_l2:
        return False, "L2 repair requires --allow-l2"
    if (RISK_ORDER[risk] >= 3 or bool(item.get("requires_review"))) and not review_approved:
        return False, "repair requires --review-approved"

    self_heal = ensure_self_heal_state(state)
    repairs = [entry for entry in self_heal.get("repairs", []) if isinstance(entry, dict) and entry.get("id") == item_id]
    cooldown_seconds = int(item.get("cooldown_seconds") or 0)
    if cooldown_seconds and repairs:
        last_at = parse_iso(str(repairs[-1].get("at") or ""))
        if last_at is not None:
            cooldown_until = last_at + timedelta(seconds=cooldown_seconds)
            if datetime.now(timezone.utc) < cooldown_until:
                return False, f"cooldown active until {cooldown_until.isoformat()}"

    max_attempts = int(item.get("max_attempts_per_day") or 0)
    if max_attempts > 0:
        today = datetime.now(timezone.utc).date()
        attempts_today = 0
        for entry in repairs:
            entry_at = parse_iso(str(entry.get("at") or ""))
            if entry_at is not None and entry_at.date() == today:
                attempts_today += 1
        if attempts_today >= max_attempts:
            return False, f"max attempts reached for today ({attempts_today}/{max_attempts})"
    return True, "allowed"


def command_spec(item: dict[str, Any], key: str) -> tuple[str, Path] | None:
    spec = item.get(key)
    if not isinstance(spec, dict):
        return None
    command = str(spec.get("command") or "").strip()
    if not command:
        return None
    return command, cwd_for(str(spec.get("cwd") or "workspace"))


def probe_item(item: dict[str, Any]) -> dict[str, Any]:
    spec = command_spec(item, "probe")
    if spec is None:
        raise RuntimeError(f"{item['id']}: missing probe command")
    command, cwd = spec
    result = run_shell(command, cwd=cwd, timeout_seconds=int(item.get("timeout_seconds") or 10))
    status = "ok" if result.ok else "degraded"
    return {
        "id": item["id"],
        "title": item["title"],
        "category": item["category"],
        "owner_scope": item["owner_scope"],
        "risk_level": item["risk_level"],
        "status": status,
        "ok": result.ok,
        "exit_code": result.exit_code,
        "timeout": result.timeout,
        "duration_ms": result.duration_ms,
        "stdout": result.stdout[-1000:],
        "stderr": result.stderr[-1000:],
        "success_criteria": item.get("success_criteria"),
        "requires_review": bool(item.get("requires_review")),
        "rollback_hint": item.get("rollback_hint"),
    }


def postcheck_item(item: dict[str, Any]) -> dict[str, Any] | None:
    spec = command_spec(item, "postcheck") or command_spec(item, "probe")
    if spec is None:
        return None
    command, cwd = spec
    result = run_shell(command, cwd=cwd, timeout_seconds=int(item.get("timeout_seconds") or 10))
    return {
        "ok": result.ok,
        "exit_code": result.exit_code,
        "timeout": result.timeout,
        "duration_ms": result.duration_ms,
        "stdout": result.stdout[-1000:],
        "stderr": result.stderr[-1000:],
    }


def run_repair(item: dict[str, Any], state: dict[str, Any], *, allow_l2: bool, review_approved: bool) -> dict[str, Any]:
    precheck = probe_item(item)
    allowed, reason = repair_allowed(item, state, allow_l2=allow_l2, review_approved=review_approved)
    if not allowed:
        return {"id": item["id"], "repaired": False, "skipped": True, "reason": reason, "precheck": precheck}

    spec = command_spec(item, "repair")
    if spec is None:
        return {"id": item["id"], "repaired": False, "skipped": True, "reason": "missing repair command", "precheck": precheck}
    command, cwd = spec
    repair_result = run_shell(command, cwd=cwd, timeout_seconds=int(item.get("timeout_seconds") or 30))
    postcheck = postcheck_item(item)
    repaired = repair_result.ok and bool(postcheck and postcheck.get("ok"))

    entry = {
        "at": now_iso(),
        "id": item["id"],
        "risk_level": item["risk_level"],
        "ok": repaired,
        "exit_code": repair_result.exit_code,
        "duration_ms": repair_result.duration_ms,
    }
    self_heal = ensure_self_heal_state(state)
    self_heal["repairs"].append(entry)

    return {
        "id": item["id"],
        "repaired": repaired,
        "skipped": False,
        "precheck": precheck,
        "repair": {
            "ok": repair_result.ok,
            "exit_code": repair_result.exit_code,
            "timeout": repair_result.timeout,
            "duration_ms": repair_result.duration_ms,
            "stdout": repair_result.stdout[-1000:],
            "stderr": repair_result.stderr[-1000:],
        },
        "postcheck": postcheck,
        "rollback_hint": item.get("rollback_hint"),
    }


def update_state_from_diagnosis(state: dict[str, Any], results: list[dict[str, Any]]) -> None:
    self_heal = ensure_self_heal_state(state)
    self_heal["last_run_at"] = now_iso()
    checks = self_heal["checks"]
    overall = "ok"
    review_required: list[str] = []
    for result in results:
        item_id = str(result["id"])
        previous = checks.get(item_id) if isinstance(checks.get(item_id), dict) else {}
        current = {
            **previous,
            "title": result.get("title"),
            "category": result.get("category"),
            "risk_level": result.get("risk_level"),
            "last_probe_at": self_heal["last_run_at"],
            "status": result.get("status"),
            "ok": result.get("ok"),
            "last_error": result.get("stderr") or ("" if result.get("ok") else result.get("stdout")),
        }
        if result.get("ok"):
            current["last_ok_at"] = self_heal["last_run_at"]
        else:
            overall = "degraded"
            if result.get("requires_review"):
                review_required.append(item_id)
        checks[item_id] = current
    self_heal["overall_status"] = "review_required" if review_required else overall
    self_heal["review_required"] = review_required


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    ok = sum(1 for item in results if item.get("ok") is True)
    degraded = total - ok
    review_required = [item["id"] for item in results if item.get("ok") is not True and item.get("requires_review")]
    status = "ok" if degraded == 0 else ("review_required" if review_required else "degraded")
    return {
        "generated_at": now_iso(),
        "agent": AGENT_SLUG,
        "overall_status": status,
        "ok": ok,
        "degraded": degraded,
        "total": total,
        "review_required": review_required,
    }


def print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def select_items(items: list[dict[str, Any]], item_id: str | None, max_level: str | None) -> list[dict[str, Any]]:
    selected = [item_by_id(items, item_id)] if item_id else list(items)
    if max_level:
        if max_level not in RISK_ORDER:
            raise SystemExit(f"invalid max level: {max_level}")
        selected = [item for item in selected if RISK_ORDER[str(item["risk_level"])] <= RISK_ORDER[max_level]]
    return selected


def cmd_list_items(args: argparse.Namespace) -> int:
    items = load_registry()
    rows = [
        {
            "id": item["id"],
            "title": item["title"],
            "category": item["category"],
            "owner_scope": item["owner_scope"],
            "risk_level": item["risk_level"],
            "requires_review": bool(item["requires_review"]),
            "has_repair": "repair" in item,
        }
        for item in select_items(items, args.item, args.max_level)
    ]
    print_json({"schema_version": 1, "items": rows})
    return 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    items = select_items(load_registry(), args.item, args.max_level)
    results = [probe_item(item) for item in items]
    summary = summarize(results)
    payload = {"summary": summary, "items": results}
    if not args.no_state:
        state = load_state()
        update_state_from_diagnosis(state, results)
        write_state(state)
    print_json(payload)
    return 0 if summary["overall_status"] == "ok" or args.exit_zero else 1


def cmd_repair(args: argparse.Namespace) -> int:
    items = select_items(load_registry(), args.item, args.max_level)
    state = load_state()
    results = [
        run_repair(item, state, allow_l2=args.allow_l2, review_approved=args.review_approved)
        for item in items
    ]
    post_results = []
    for item in items:
        post = probe_item(item)
        post_results.append(post)
    update_state_from_diagnosis(state, post_results)
    if not args.no_state:
        write_state(state)
    repaired = sum(1 for item in results if item.get("repaired") is True)
    skipped = sum(1 for item in results if item.get("skipped") is True)
    payload = {
        "summary": {
            "generated_at": now_iso(),
            "agent": AGENT_SLUG,
            "requested": len(results),
            "repaired": repaired,
            "skipped": skipped,
            "post_status": summarize(post_results)["overall_status"],
        },
        "repairs": results,
        "postcheck_items": post_results,
    }
    print_json(payload)
    return 0 if skipped == 0 and summarize(post_results)["overall_status"] == "ok" else 1


def cmd_status(_args: argparse.Namespace) -> int:
    state = load_state()
    print_json(state.get("self_heal", {"schema_version": 1, "overall_status": "unknown"}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="nox registry-driven self-heal runner")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list-items", help="List registered self-heal items")
    list_parser.add_argument("--item", default=None)
    list_parser.add_argument("--max-level", default=None, choices=sorted(RISK_ORDER))
    list_parser.set_defaults(func=cmd_list_items)

    diagnose_parser = sub.add_parser("diagnose", help="Run read-only probes")
    diagnose_parser.add_argument("--item", default=None)
    diagnose_parser.add_argument("--max-level", default=None, choices=sorted(RISK_ORDER))
    diagnose_parser.add_argument("--no-state", action="store_true", help="Do not update memory/heartbeat-state.json")
    diagnose_parser.add_argument("--exit-zero", action="store_true", help="Return 0 even when degraded")
    diagnose_parser.set_defaults(func=cmd_diagnose)

    repair_parser = sub.add_parser("repair", help="Run gated repair commands")
    repair_parser.add_argument("--item", required=True, help="Repair a single item by ID")
    repair_parser.add_argument("--max-level", default=None, choices=sorted(RISK_ORDER))
    repair_parser.add_argument("--allow-l2", action="store_true", help="Allow L2 service/runtime refresh repairs")
    repair_parser.add_argument("--review-approved", action="store_true", help="Confirm Review approval for L3/L4 or review-required items")
    repair_parser.add_argument("--no-state", action="store_true", help="Do not update memory/heartbeat-state.json")
    repair_parser.set_defaults(func=cmd_repair)

    status_parser = sub.add_parser("status", help="Show stored self-heal state")
    status_parser.set_defaults(func=cmd_status)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
