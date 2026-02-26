#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

DEFAULT_AGENTS = [
    "nox",
    "metrics",
    "email",
    "growth",
    "trades",
    "health",
    "writing",
    "personal",
]


@dataclass
class AgentEndpoint:
    slug: str
    enabled: bool
    gateway_host_port: int


@dataclass
class MetricResult:
    name: str
    value: float | None
    threshold: float | None
    passed: bool | None
    weight: float
    note: str = ""


def _iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _http_json(
    url: str,
    method: str = "GET",
    token: str = "",
    payload: dict[str, Any] | None = None,
    timeout: float = 6.0,
) -> tuple[int, dict[str, Any] | list[Any] | None, str | None]:
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url=url, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = int(resp.status)
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw:
                return status, None, None
            try:
                return status, json.loads(raw), None
            except json.JSONDecodeError:
                return status, None, f"non-json response: {raw[:200]}"
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), None, raw[:200] if raw else "http error"
    except Exception as exc:  # pragma: no cover
        return 0, None, str(exc)


def _http_head_or_get(url: str, timeout: float = 4.0) -> tuple[int, str | None]:
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url=url, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return int(resp.status), None
        except urllib.error.HTTPError as exc:
            return int(exc.code), None
        except Exception as exc:
            if method == "GET":
                return 0, str(exc)
    return 0, "unreachable"


def _event_http_endpoint(raw_url: str) -> str:
    base = (raw_url or "").strip().rstrip("/")
    if not base:
        return ""
    if base.endswith("/v1/events"):
        return base
    return f"{base}/v1/events"


def load_agent_endpoints(manifest_path: Path | None) -> list[AgentEndpoint]:
    if manifest_path and manifest_path.exists() and yaml is not None:
        try:
            payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            agents = payload.get("agents", []) if isinstance(payload, dict) else []
            out: list[AgentEndpoint] = []
            for item in agents:
                if not isinstance(item, dict):
                    continue
                slug = str(item.get("slug") or "").strip()
                if not slug:
                    continue
                enabled = bool(item.get("enabled", True))
                port = int(item.get("gateway_host_port") or 0)
                if port <= 0:
                    continue
                out.append(AgentEndpoint(slug=slug, enabled=enabled, gateway_host_port=port))
            if out:
                return out
        except Exception:
            pass

    return [
        AgentEndpoint(slug=slug, enabled=True, gateway_host_port=18801 + i * 10)
        for i, slug in enumerate(DEFAULT_AGENTS)
    ]


def normalize_score(value: float | None, threshold: float | None, smaller_is_better: bool = False) -> float | None:
    if value is None or threshold is None:
        return None
    if smaller_is_better:
        if value <= threshold:
            return 100.0
        if threshold <= 0:
            return 0.0
        return max(0.0, 100.0 * (threshold / value))

    if threshold <= 0:
        return 0.0
    if value >= threshold:
        return 100.0
    return max(0.0, 100.0 * (value / threshold))


def weighted_total(metrics: list[MetricResult], smaller_is_better: set[str]) -> tuple[float, float]:
    score_sum = 0.0
    weight_sum = 0.0
    for metric in metrics:
        normalized = normalize_score(
            metric.value,
            metric.threshold,
            smaller_is_better=metric.name in smaller_is_better,
        )
        if normalized is None:
            continue
        score_sum += normalized * metric.weight
        weight_sum += metric.weight
    if weight_sum == 0:
        return 0.0, 0.0
    return score_sum / weight_sum, weight_sum


def run_lyric_case(
    base_url: str,
    token: str,
    timeout: float,
    event_http_url: str = "",
    event_http_token: str = "",
) -> dict[str, Any]:
    created: dict[str, Any] = {"task_id": None, "events": []}
    key_event_push: list[dict[str, Any]] = []

    task_payload = {
        "title": "歌词协作演练：智能体人类新时代（市场调研后判断）",
        "status": "INBOX",
        "assignee": "metrics",
        "tags": ["evaluation", "lyrics-case", "market"],
    }
    status, task_json, err = _http_json(
        f"{base_url}/v1/tasks", method="POST", token=token, payload=task_payload, timeout=timeout
    )
    if status < 200 or status >= 300 or not isinstance(task_json, dict):
        return {"ok": False, "error": f"create task failed: status={status} err={err}"}

    task_id = str(task_json.get("id"))
    created["task_id"] = task_id

    events = [
        {
            "type": "task.status",
            "agent": "metrics",
            "task_id": task_id,
            "payload": {
                "new_status": "ASSIGNED",
                "reason": "任务已分配给 metrics",
            },
        },
        {
            "type": "task.assigned",
            "agent": "metrics",
            "task_id": task_id,
            "payload": {
                "phase": "research",
                "deliverable": "market_report",
                "expected_output": "artifact.json + artifact.md",
            },
        },
        {
            "type": "task.handoff",
            "agent": "metrics",
            "task_id": task_id,
            "payload": {
                "to": "growth",
                "problem": "基于市场行情判断智能体新时代特征",
                "context": "已完成AI市场行情摘要",
                "artifact_refs": ["market_report"],
                "expected_output": "judgment_report",
                "review_gate": True,
            },
        },
        {
            "type": "task.status",
            "agent": "growth",
            "task_id": task_id,
            "payload": {
                "new_status": "IN PROGRESS",
                "reason": "growth 接手执行",
            },
        },
        {
            "type": "task.handoff",
            "agent": "growth",
            "task_id": task_id,
            "payload": {
                "to": "writing",
                "problem": "根据调研与判断结果创作歌词",
                "context": "已形成趋势判断与风险提示",
                "artifact_refs": ["market_report", "judgment_report"],
                "expected_output": "lyrics_v1",
                "review_gate": True,
            },
        },
        {
            "type": "artifact.created",
            "agent": "writing",
            "task_id": task_id,
            "payload": {
                "artifact": "lyrics_v1",
                "format": ["json", "md"],
                "sources_linked": True,
            },
        },
        {
            "type": "task.review.requested",
            "agent": "writing",
            "task_id": task_id,
            "payload": {"reason": "歌词发布前审查", "risk": "medium"},
        },
        {
            "type": "task.status",
            "agent": "writing",
            "task_id": task_id,
            "payload": {
                "new_status": "REVIEW",
                "reason": "已提交 Review",
            },
        },
    ]

    event_http_endpoint = _event_http_endpoint(event_http_url)
    key_types = {"artifact.created", "task.status", "task.review.requested"}

    for event in events:
        status, event_json, err = _http_json(
            f"{base_url}/v1/events", method="POST", token=token, payload=event, timeout=timeout
        )
        created["events"].append(
            {
                "type": event["type"],
                "status": status,
                "ok": 200 <= status < 300,
                "id": event_json.get("id") if isinstance(event_json, dict) else None,
                "error": err,
            }
        )

        if event_http_endpoint and event["type"] in key_types:
            mirror_status, _, mirror_err = _http_json(
                event_http_endpoint,
                method="POST",
                token=event_http_token,
                payload=event,
                timeout=timeout,
            )
            key_event_push.append(
                {
                    "type": event["type"],
                    "status": mirror_status,
                    "ok": 200 <= mirror_status < 300,
                    "error": mirror_err,
                    "target": event_http_endpoint,
                }
            )

    if event_http_endpoint:
        created["event_http_push"] = {
            "endpoint": event_http_endpoint,
            "items": key_event_push,
            "ok": all(item["ok"] for item in key_event_push) if key_event_push else False,
        }

    return {"ok": True, **created}


def measure_probe_latency(base_url: str, token: str, timeout: float, max_wait: float) -> tuple[float | None, str | None]:
    probe_id = str(uuid4())
    payload = {
        "type": "assessment.probe",
        "agent": "metrics",
        "payload": {"probe_id": probe_id},
    }
    t0 = time.time()
    status, _, err = _http_json(
        f"{base_url}/v1/events", method="POST", token=token, payload=payload, timeout=timeout
    )
    if status < 200 or status >= 300:
        return None, f"probe publish failed: status={status} err={err}"

    while time.time() - t0 <= max_wait:
        status, feed_json, err = _http_json(
            f"{base_url}/v1/feed?limit=80", method="GET", token=token, timeout=timeout
        )
        if status < 200 or status >= 300 or not isinstance(feed_json, list):
            time.sleep(0.3)
            continue

        for item in feed_json:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "assessment.probe":
                continue
            probe = (item.get("payload") or {}).get("probe_id")
            if probe == probe_id:
                return time.time() - t0, None
        time.sleep(0.25)

    return None, "probe timeout"


def run_workspace_contract(
    repo_root: Path,
    manifest_path: Path,
    auto_create: bool,
    timeout: float,
) -> dict[str, Any]:
    script_path = repo_root / "panopticon" / "tools" / "test_workspace_contract.py"
    output_path = repo_root / "panopticon" / "reports" / "workspace_contract_embedded.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not script_path.exists():
        return {
            "ok": False,
            "error": f"workspace contract script not found: {script_path}",
            "exit_code": -1,
        }

    cmd = [
        sys.executable,
        str(script_path),
        "--workspaces-root",
        str(repo_root / "panopticon" / "workspaces"),
        "--manifest",
        str(manifest_path),
        "--output",
        str(output_path),
    ]
    if auto_create:
        cmd.append("--auto-create")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=max(30.0, timeout * 6),
            check=False,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc), "exit_code": -2}

    embedded_report = None
    if output_path.exists():
        try:
            embedded_report = json.loads(output_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {
                "ok": False,
                "error": f"failed to parse workspace report: {exc}",
                "exit_code": result.returncode,
                "stdout": (result.stdout or "")[-1200:],
                "stderr": (result.stderr or "")[-1200:],
            }

    summary = (embedded_report or {}).get("summary", {})
    success_rate = summary.get("success_rate_pct")

    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "success_rate_pct": success_rate,
        "summary": summary,
        "report_path": str(output_path),
        "stdout": (result.stdout or "")[-1200:],
        "stderr": (result.stderr or "")[-1200:],
        "report": embedded_report,
    }


def run_status_comprehensive_test(
    repo_root: Path,
    api_base: str,
    token: str,
    feed_limit: int,
    timeout: float,
) -> dict[str, Any]:
    script_path = repo_root / "panopticon" / "tools" / "test_task_statuses.py"
    output_path = repo_root / "panopticon" / "reports" / "task_statuses_embedded.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not script_path.exists():
        return {
            "ok": False,
            "error": f"status test script not found: {script_path}",
            "exit_code": -1,
        }

    cmd = [
        sys.executable,
        str(script_path),
        "--api-base",
        api_base,
        "--feed-limit",
        str(feed_limit),
        "--output",
        str(output_path),
    ]
    if token:
        cmd.extend(["--auth-token", token])

    try:
        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=max(30.0, timeout * 6),
            check=False,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc), "exit_code": -2}

    embedded_report = None
    if output_path.exists():
        try:
            embedded_report = json.loads(output_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {
                "ok": False,
                "error": f"failed to parse status report: {exc}",
                "exit_code": result.returncode,
                "stdout": (result.stdout or "")[-1200:],
                "stderr": (result.stderr or "")[-1200:],
            }

    summary = (embedded_report or {}).get("summary", {})
    pass_rate = summary.get("pass_rate_pct")

    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "pass_rate_pct": pass_rate,
        "summary": summary,
        "report_path": str(output_path),
        "stdout": (result.stdout or "")[-1200:],
        "stderr": (result.stderr or "")[-1200:],
        "report": embedded_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Panopticon 8-Agent + Mission Control 综合评估")
    parser.add_argument("--api-base", default=os.getenv("MISSION_CONTROL_API_URL", "http://127.0.0.1:18910"))
    parser.add_argument("--ui-base", default=os.getenv("MISSION_CONTROL_UI_URL", "http://127.0.0.1:18920"))
    parser.add_argument("--auth-token", default=os.getenv("MC_AUTH_TOKEN", ""))
    parser.add_argument("--manifest", default="panopticon/agents.manifest.yaml")
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--heartbeat-window-minutes", type=int, default=30)
    parser.add_argument("--probe-max-wait", type=float, default=15.0)
    parser.add_argument("--feed-limit", type=int, default=500)
    parser.add_argument("--run-lyric-case", action="store_true", help="执行歌词协作演练事件写入")
    parser.add_argument(
        "--event-http-url",
        default=os.getenv("EVENT_HTTP_URL", ""),
        help="可选：验证 agent 侧事件上报接入地址（base 或 /v1/events）",
    )
    parser.add_argument(
        "--event-http-token",
        default=os.getenv("EVENT_HTTP_TOKEN", ""),
        help="可选：EVENT_HTTP_URL 对应 Bearer token",
    )
    parser.add_argument("--skip-probe", action="store_true", help="跳过评估探针延迟测量")
    parser.add_argument("--skip-status-test", action="store_true", help="跳过5状态全面测试")
    parser.add_argument("--skip-workspace-contract", action="store_true", help="跳过 workspace 状态测试")
    parser.add_argument("--workspace-auto-create", action="store_true", help="workspace 测试时自动补齐缺失目录")
    parser.add_argument("--output", default="", help="写入 JSON 报告文件")
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    ui_base = args.ui_base.rstrip("/")
    token = args.auth_token.strip()
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = repo_root / manifest_path

    endpoints = load_agent_endpoints(manifest_path)
    endpoints = [item for item in endpoints if item.enabled]

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_base": api_base,
        "ui_base": ui_base,
        "agents_expected": [item.slug for item in endpoints],
    }

    status, health_json, health_err = _http_json(f"{api_base}/health", token=token, timeout=args.timeout)
    api_ok = status == 200 and isinstance(health_json, dict) and bool(health_json.get("ok"))
    report["api_health"] = {"status": status, "ok": api_ok, "error": health_err}

    ui_status, ui_err = _http_head_or_get(ui_base, timeout=4.0)
    ui_ok = 200 <= ui_status < 400
    report["ui_health"] = {"status": ui_status, "ok": ui_ok, "error": ui_err}

    lyric_case = None
    if args.run_lyric_case and api_ok:
        lyric_case = run_lyric_case(
            api_base,
            token,
            timeout=args.timeout,
            event_http_url=args.event_http_url,
            event_http_token=args.event_http_token,
        )
        # 让刚写入的任务/事件在 board/feed 查询中可见
        time.sleep(0.2)

    gateway_checks: list[dict[str, Any]] = []
    for item in endpoints:
        url = f"http://127.0.0.1:{item.gateway_host_port}"
        code, err = _http_head_or_get(url, timeout=3.0)
        ok = 100 <= code <= 599
        gateway_checks.append({"agent": item.slug, "url": url, "status": code, "ok": ok, "error": err})
    report["agent_gateway_checks"] = gateway_checks

    status, board_json, board_err = _http_json(f"{api_base}/v1/boards/default", token=token, timeout=args.timeout)
    feed_limit = max(50, min(args.feed_limit, 2000))
    status_feed, feed_json, feed_err = _http_json(
        f"{api_base}/v1/feed?limit={feed_limit}", token=token, timeout=args.timeout
    )
    report["board_fetch"] = {"status": status, "error": board_err}
    report["feed_fetch"] = {"status": status_feed, "error": feed_err}

    tasks: list[dict[str, Any]] = []
    if isinstance(board_json, dict):
        for col in board_json.get("columns", []):
            for card in col.get("cards", []):
                if isinstance(card, dict):
                    tasks.append(card)
    report["task_count"] = len(tasks)

    events: list[dict[str, Any]] = feed_json if isinstance(feed_json, list) else []
    report["event_count"] = len(events)

    now = datetime.now(timezone.utc)
    window = now - timedelta(minutes=max(args.heartbeat_window_minutes, 1))

    done_tasks = sum(1 for t in tasks if t.get("status") == "DONE")
    success_rate = (done_tasks / len(tasks) * 100.0) if tasks else None

    event_task_ids = {str(e.get("task_id")) for e in events if e.get("task_id")}
    lifecycle_covered = sum(1 for t in tasks if str(t.get("id")) in event_task_ids)
    lifecycle_coverage = (lifecycle_covered / len(tasks) * 100.0) if tasks else None

    heartbeat_recent_agents: set[str] = set()
    for e in events:
        if e.get("type") != "agent.heartbeat":
            continue
        created_at = _iso_to_dt(e.get("created_at"))
        if created_at and created_at >= window and e.get("agent"):
            heartbeat_recent_agents.add(str(e.get("agent")))
    heartbeat_ratio = (
        len(heartbeat_recent_agents.intersection({a.slug for a in endpoints})) / len(endpoints) * 100.0
        if endpoints
        else None
    )

    feed_latest_dt = max((_iso_to_dt(e.get("created_at")) for e in events), default=None)
    feed_freshness_sec = (now - feed_latest_dt).total_seconds() if feed_latest_dt else None

    handoff_events = [e for e in events if str(e.get("type", "")).startswith("task.handoff")]
    required_fields = {"to", "problem", "context", "artifact_refs", "expected_output", "review_gate"}
    handoff_complete = 0
    for e in handoff_events:
        payload = e.get("payload") or {}
        if (
            all(field in payload for field in required_fields)
            and isinstance(payload.get("artifact_refs"), list)
            and len(payload.get("artifact_refs")) > 0
            and isinstance(payload.get("review_gate"), bool)
        ):
            handoff_complete += 1
    handoff_completeness = (handoff_complete / len(handoff_events) * 100.0) if handoff_events else None

    high_risk_tasks = [t for t in tasks if "high-risk" in (t.get("tags") or [])]
    high_risk_ids = {str(t.get("id")) for t in high_risk_tasks}
    reviewed_ids = {str(e.get("task_id")) for e in events if str(e.get("type", "")).startswith("task.review") and e.get("task_id")}
    bypass_rate = None
    if high_risk_ids:
        bypass_rate = (len(high_risk_ids - reviewed_ids) / len(high_risk_ids)) * 100.0

    probe_latency = None
    probe_error = None
    if not args.skip_probe and api_ok:
        probe_latency, probe_error = measure_probe_latency(
            api_base, token, timeout=args.timeout, max_wait=max(args.probe_max_wait, 1.0)
        )

    metrics = [
        MetricResult("task_success_rate_pct", success_rate, 70.0, None, 0.20, "DONE/全部任务"),
        MetricResult("lifecycle_coverage_pct", lifecycle_coverage, 95.0, None, 0.20, "任务是否具备事件证据"),
        MetricResult("handoff_completeness_pct", handoff_completeness, 90.0, None, 0.15, "handoff 关键字段完整率"),
        MetricResult("heartbeat_continuity_pct", heartbeat_ratio, 99.0, None, 0.10, "窗口内心跳覆盖率"),
        MetricResult("feed_freshness_sec", feed_freshness_sec, 120.0, None, 0.10, "事件新鲜度，越小越好"),
        MetricResult("probe_event_latency_sec", probe_latency, 2.0, None, 0.15, "探针写入到 feed 可见延迟，越小越好"),
        MetricResult("review_gate_bypass_rate_pct", bypass_rate, 0.0, None, 0.10, "高风险任务绕过 Review 比率，越小越好"),
    ]

    smaller_is_better = {"feed_freshness_sec", "probe_event_latency_sec", "review_gate_bypass_rate_pct"}

    for metric in metrics:
        if metric.value is None or metric.threshold is None:
            metric.passed = None
            continue
        if metric.name in smaller_is_better:
            metric.passed = metric.value <= metric.threshold
        else:
            metric.passed = metric.value >= metric.threshold

    total_score, weight_used = weighted_total(metrics, smaller_is_better)

    report["metrics"] = [
        {
            "name": m.name,
            "value": m.value,
            "threshold": m.threshold,
            "passed": m.passed,
            "weight": m.weight,
            "note": m.note,
        }
        for m in metrics
    ]
    report["probe"] = {"latency_sec": probe_latency, "error": probe_error}
    report["lyric_case"] = lyric_case

    status_test = None
    if not args.skip_status_test and api_ok:
        status_test = run_status_comprehensive_test(
            repo_root=repo_root,
            api_base=api_base,
            token=token,
            feed_limit=feed_limit,
            timeout=args.timeout,
        )
    report["status_test"] = status_test

    workspace_contract = None
    if not args.skip_workspace_contract:
        workspace_contract = run_workspace_contract(
            repo_root=repo_root,
            manifest_path=manifest_path,
            auto_create=args.workspace_auto_create,
            timeout=args.timeout,
        )
    report["workspace_contract"] = workspace_contract

    collaboration_score = round(total_score, 2)
    workspace_score = None
    status_score = None
    overall_score = collaboration_score
    if workspace_contract and isinstance(workspace_contract.get("success_rate_pct"), (int, float)):
        workspace_score = float(workspace_contract["success_rate_pct"])
    if status_test and isinstance(status_test.get("pass_rate_pct"), (int, float)):
        status_score = float(status_test["pass_rate_pct"])

    if workspace_score is not None and status_score is not None:
        overall_score = round(collaboration_score * 0.7 + workspace_score * 0.15 + status_score * 0.15, 2)
    elif workspace_score is not None:
        overall_score = round(collaboration_score * 0.8 + workspace_score * 0.2, 2)
    elif status_score is not None:
        overall_score = round(collaboration_score * 0.8 + status_score * 0.2, 2)

    report["summary"] = {
        "score": collaboration_score,
        "overall_score": overall_score,
        "collaboration_score": collaboration_score,
        "workspace_score": workspace_score,
        "status_score": status_score,
        "weight_used": round(weight_used, 2),
        "api_ok": api_ok,
        "ui_ok": ui_ok,
        "gateway_ok_count": sum(1 for i in gateway_checks if i["ok"]),
        "gateway_total": len(gateway_checks),
    }

    lines = []
    lines.append("=== Panopticon 综合评估报告 ===")
    lines.append(f"API健康: {'OK' if api_ok else 'FAIL'} (status={status})")
    lines.append(f"UI健康 : {'OK' if ui_ok else 'FAIL'} (status={ui_status})")
    lines.append(
        f"Agent网关: {report['summary']['gateway_ok_count']}/{report['summary']['gateway_total']} reachable"
    )
    lines.append(f"协作评分: {report['summary']['score']} / 100 (有效权重={report['summary']['weight_used']})")
    if workspace_contract:
        wc_status = "PASS" if workspace_contract.get("ok") else "FAIL"
        wc_value = workspace_contract.get("success_rate_pct")
        wc_value_text = "N/A" if wc_value is None else f"{wc_value:.2f}"
        lines.append(f"Workspace状态测试: {wc_status} ({wc_value_text}%)")
    if status_test:
        st_status = "PASS" if status_test.get("ok") else "FAIL"
        st_value = status_test.get("pass_rate_pct")
        st_value_text = "N/A" if st_value is None else f"{st_value:.2f}"
        lines.append(f"任务状态测试(INBOX..DONE): {st_status} ({st_value_text}%)")
    if workspace_contract or status_test:
        lines.append(f"总评分(含状态/Workspace加权): {report['summary']['overall_score']} / 100")
    else:
        lines.append(f"综合得分: {report['summary']['score']} / 100")
    lines.append("--- 指标 ---")
    for m in report["metrics"]:
        value = "N/A" if m["value"] is None else f"{m['value']:.2f}"
        threshold = "N/A" if m["threshold"] is None else f"{m['threshold']:.2f}"
        status_text = "PASS" if m["passed"] is True else ("FAIL" if m["passed"] is False else "N/A")
        lines.append(f"{m['name']}: {value} (阈值 {threshold}) -> {status_text}")

    if lyric_case:
        lines.append("--- 歌词协作演练 ---")
        lines.append(f"演练状态: {'OK' if lyric_case.get('ok') else 'FAIL'}")
        if lyric_case.get("task_id"):
            lines.append(f"task_id: {lyric_case['task_id']}")
        event_http_push = lyric_case.get("event_http_push")
        if isinstance(event_http_push, dict):
            push_ok = bool(event_http_push.get("ok"))
            lines.append(f"EVENT_HTTP_URL关键事件上报: {'OK' if push_ok else 'FAIL'}")
            lines.append(f"endpoint: {event_http_push.get('endpoint')}")

    if workspace_contract:
        lines.append("--- Workspace 状态测试 ---")
        lines.append(f"exit_code: {workspace_contract.get('exit_code')}")
        if workspace_contract.get("report_path"):
            lines.append(f"report: {workspace_contract['report_path']}")

    if status_test:
        lines.append("--- 任务状态全面测试 ---")
        lines.append(f"exit_code: {status_test.get('exit_code')}")
        if status_test.get("report_path"):
            lines.append(f"report: {status_test['report_path']}")

    text_report = "\n".join(lines)
    print(text_report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON 报告已写入: {out_path}")

    # 仅当核心链路不可用时返回非零，评估指标失败不阻断命令本身
    if not api_ok:
        return 2
    if not ui_ok:
        return 3
    if workspace_contract and not workspace_contract.get("ok") and not args.workspace_auto_create:
        return 4
    if status_test and not status_test.get("ok"):
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
