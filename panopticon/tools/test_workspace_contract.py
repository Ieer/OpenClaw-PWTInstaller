#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

REQUIRED_DIRS = ["inbox", "outbox", "artifacts", "state", "sources"]
DEFAULT_AGENTS = ["email", "growth", "health", "metrics", "nox", "personal", "trades", "writing"]


@dataclass
class AgentResult:
    agent: str
    workspace: Path
    checks: list[dict[str, Any]]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_agents(manifest_path: Path | None) -> list[str]:
    if manifest_path and manifest_path.exists() and yaml is not None:
        try:
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("agents"), list):
                out: list[str] = []
                for item in data["agents"]:
                    if not isinstance(item, dict):
                        continue
                    if not bool(item.get("enabled", True)):
                        continue
                    slug = str(item.get("slug") or "").strip()
                    if slug:
                        out.append(slug)
                if out:
                    return out
        except Exception:
            pass
    return DEFAULT_AGENTS


def record(checks: list[dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": ok, "detail": detail})


def ensure_dir(path: Path, auto_create: bool) -> tuple[bool, str]:
    if path.exists() and path.is_dir():
        return True, "exists"
    if not auto_create:
        return False, "missing"
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True, "created"
    except Exception as exc:
        return False, f"create failed: {exc}"


def rw_probe(path: Path) -> tuple[bool, str]:
    test_file = path / ".workspace_contract_probe.tmp"
    content = f"probe@{now_iso()}"
    try:
        test_file.write_text(content, encoding="utf-8")
        read_back = test_file.read_text(encoding="utf-8")
        if read_back != content:
            return False, "read-back mismatch"
        test_file.unlink(missing_ok=True)
        return True, "rw ok"
    except Exception as exc:
        try:
            test_file.unlink(missing_ok=True)
        except Exception:
            pass
        return False, str(exc)


def lifecycle_probe(workspace: Path) -> tuple[bool, str]:
    """
    模拟一次最小工作流：
    inbox -> outbox（消息流）
    artifacts/<task>/artifact.json + artifact.md
    state/<task>.json
    sources/<task>/index.json
    """
    task_id = f"assessment-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    temp_root = workspace / ".contract_test_tmp"

    try:
        inbox = workspace / "inbox"
        outbox = workspace / "outbox"
        artifacts = workspace / "artifacts" / task_id
        state = workspace / "state"
        sources = workspace / "sources" / task_id

        temp_root.mkdir(parents=True, exist_ok=True)

        msg_in = inbox / f"{task_id}.txt"
        msg_out = outbox / f"{task_id}.txt"

        msg_in.write_text("new task input", encoding="utf-8")
        shutil.copy2(msg_in, msg_out)

        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "artifact.json").write_text(
            json.dumps(
                {
                    "task_id": task_id,
                    "summary": "workspace contract lifecycle probe",
                    "generated_at": now_iso(),
                    "risk": "low",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (artifacts / "artifact.md").write_text("# Lifecycle Probe\n\nOK", encoding="utf-8")

        state.mkdir(parents=True, exist_ok=True)
        (state / f"{task_id}.json").write_text(
            json.dumps({"checkpoint": "DONE", "updated_at": now_iso()}, ensure_ascii=False),
            encoding="utf-8",
        )

        sources.mkdir(parents=True, exist_ok=True)
        (sources / "index.json").write_text(
            json.dumps(
                {
                    "task_id": task_id,
                    "sources": [
                        {"name": "probe", "path": f"sources/{task_id}/index.json", "freshness": "test"}
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # 验证关键产物存在
        required = [
            msg_in,
            msg_out,
            artifacts / "artifact.json",
            artifacts / "artifact.md",
            state / f"{task_id}.json",
            sources / "index.json",
        ]
        missing = [str(p) for p in required if not p.exists()]
        if missing:
            return False, f"missing generated files: {missing}"

        return True, task_id
    except Exception as exc:
        return False, str(exc)
    finally:
        # 保持 workspace 干净：只清理本次探针生成
        try:
            for sub in ["inbox", "outbox", "state"]:
                for p in (workspace / sub).glob("assessment-*.txt"):
                    p.unlink(missing_ok=True)
                for p in (workspace / sub).glob("assessment-*.json"):
                    p.unlink(missing_ok=True)
            shutil.rmtree(workspace / "artifacts" / task_id, ignore_errors=True)
            shutil.rmtree(workspace / "sources" / task_id, ignore_errors=True)
            shutil.rmtree(temp_root, ignore_errors=True)
        except Exception:
            pass


def test_agent_workspace(agent: str, workspaces_root: Path, auto_create: bool, with_lifecycle: bool) -> AgentResult:
    workspace = workspaces_root / agent
    checks: list[dict[str, Any]] = []

    ok_workspace, detail_workspace = ensure_dir(workspace, auto_create=auto_create)
    record(checks, "workspace_exists", ok_workspace, detail_workspace)

    if not ok_workspace:
        return AgentResult(agent=agent, workspace=workspace, checks=checks)

    for sub in REQUIRED_DIRS:
        sub_path = workspace / sub
        ok_exist, detail_exist = ensure_dir(sub_path, auto_create=auto_create)
        record(checks, f"{sub}_exists", ok_exist, detail_exist)
        if ok_exist:
            ok_rw, detail_rw = rw_probe(sub_path)
            record(checks, f"{sub}_rw", ok_rw, detail_rw)

    if with_lifecycle:
        ok_lifecycle, detail_lifecycle = lifecycle_probe(workspace)
        record(checks, "lifecycle_probe", ok_lifecycle, detail_lifecycle)

    return AgentResult(agent=agent, workspace=workspace, checks=checks)


def summarize(results: list[AgentResult]) -> dict[str, Any]:
    total_checks = 0
    passed_checks = 0
    per_agent: list[dict[str, Any]] = []

    for item in results:
        ok_count = sum(1 for c in item.checks if c["ok"])
        total = len(item.checks)
        total_checks += total
        passed_checks += ok_count
        per_agent.append(
            {
                "agent": item.agent,
                "workspace": str(item.workspace),
                "passed": ok_count,
                "total": total,
                "checks": item.checks,
            }
        )

    success_rate = (passed_checks / total_checks * 100.0) if total_checks else 0.0
    return {
        "generated_at": now_iso(),
        "summary": {
            "passed_checks": passed_checks,
            "total_checks": total_checks,
            "success_rate_pct": round(success_rate, 2),
            "all_passed": passed_checks == total_checks and total_checks > 0,
        },
        "agents": per_agent,
    }


def print_human(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("=== Workspace Contract 全面测试 ===")
    print(
        f"检查通过: {summary['passed_checks']}/{summary['total_checks']} "
        f"({summary['success_rate_pct']:.2f}%)"
    )
    print(f"总体结果: {'PASS' if summary['all_passed'] else 'FAIL'}")
    print("--- Agent 结果 ---")
    for agent in report["agents"]:
        print(f"{agent['agent']}: {agent['passed']}/{agent['total']}")
        failed = [c for c in agent["checks"] if not c["ok"]]
        for item in failed:
            print(f"  - FAIL {item['name']}: {item['detail']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="全面测试每个 workspace 的固定子结构与状态读写")
    parser.add_argument("--workspaces-root", default="panopticon/workspaces")
    parser.add_argument("--manifest", default="panopticon/agents.manifest.yaml")
    parser.add_argument("--agents", default="", help="逗号分隔，仅测试指定 agent")
    parser.add_argument("--auto-create", action="store_true", help="缺失目录时自动创建")
    parser.add_argument("--skip-lifecycle", action="store_true", help="跳过生命周期探针")
    parser.add_argument("--output", default="", help="输出 JSON 报告路径")
    args = parser.parse_args()

    workspaces_root = Path(args.workspaces_root)
    manifest_path = Path(args.manifest) if args.manifest else None

    agents = load_agents(manifest_path)
    if args.agents.strip():
        allow = {x.strip() for x in args.agents.split(",") if x.strip()}
        agents = [a for a in agents if a in allow]

    results = [
        test_agent_workspace(
            agent=agent,
            workspaces_root=workspaces_root,
            auto_create=args.auto_create,
            with_lifecycle=not args.skip_lifecycle,
        )
        for agent in agents
    ]

    report = summarize(results)
    print_human(report)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON 报告已写入: {output_path}")

    return 0 if report["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
