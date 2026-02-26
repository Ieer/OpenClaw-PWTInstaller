#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUSES = ["INBOX", "ASSIGNED", "IN PROGRESS", "REVIEW", "DONE"]


def http_json(
    url: str,
    method: str = "GET",
    token: str = "",
    payload: dict[str, Any] | None = None,
    timeout: float = 8.0,
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Mission Control 5状态全面测试")
    parser.add_argument("--api-base", default=os.getenv("MISSION_CONTROL_API_URL", "http://127.0.0.1:18910"))
    parser.add_argument("--auth-token", default=os.getenv("MC_AUTH_TOKEN", ""))
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--output", default="panopticon/reports/task_statuses_report.json")
    parser.add_argument("--feed-limit", type=int, default=500)
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    token = args.auth_token.strip()
    now_text = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_base": api_base,
        "statuses": STATUSES,
        "created_tasks": [],
        "checks": [],
    }

    # 1) 创建每个状态的任务
    created_by_status: dict[str, str] = {}
    for status in STATUSES:
        task_payload = {
            "title": f"status-test-{status}-{now_text}",
            "status": status,
            "assignee": "nox" if status != "INBOX" else None,
            "tags": ["evaluation", "status-test", now_text],
        }
        code, data, err = http_json(
            f"{api_base}/v1/tasks", method="POST", token=token, payload=task_payload, timeout=args.timeout
        )
        ok = 200 <= code < 300 and isinstance(data, dict) and bool(data.get("id"))
        report["checks"].append(
            {"name": f"create_{status}", "ok": ok, "status": code, "error": err}
        )
        if ok:
            task_id = str(data["id"])
            created_by_status[status] = task_id
            report["created_tasks"].append(
                {
                    "status": status,
                    "id": task_id,
                    "title": data.get("title"),
                    "created_at": data.get("created_at"),
                }
            )

    # 2) 为每个任务写入事件，增强可追踪
    for status, task_id in created_by_status.items():
        event_payload = {
            "type": "task.status.tested",
            "agent": "nox",
            "task_id": task_id,
            "payload": {"status": status, "test": "comprehensive-status"},
        }
        code, _, err = http_json(
            f"{api_base}/v1/events", method="POST", token=token, payload=event_payload, timeout=args.timeout
        )
        report["checks"].append(
            {
                "name": f"event_for_{status}",
                "ok": 200 <= code < 300,
                "status": code,
                "error": err,
            }
        )

    # 3) 拉取看板并校验5个状态均可见
    time.sleep(0.2)
    code, board, err = http_json(f"{api_base}/v1/boards/default", token=token, timeout=args.timeout)
    board_ok = 200 <= code < 300 and isinstance(board, dict)
    report["checks"].append({"name": "fetch_board", "ok": board_ok, "status": code, "error": err})

    board_map: dict[str, set[str]] = {}
    if board_ok:
        for col in board.get("columns", []):
            title = str(col.get("title") or "")
            ids = {
                str(card.get("id"))
                for card in col.get("cards", [])
                if isinstance(card, dict) and card.get("id")
            }
            board_map[title] = ids

    for status in STATUSES:
        expected_id = created_by_status.get(status)
        ok = bool(expected_id and expected_id in board_map.get(status, set()))
        report["checks"].append(
            {
                "name": f"board_contains_{status}",
                "ok": ok,
                "expected_task_id": expected_id,
                "column_size": len(board_map.get(status, set())),
            }
        )

    # 4) 拉取feed并校验5个事件可见
    limit = max(100, min(args.feed_limit, 2000))
    code, feed, err = http_json(f"{api_base}/v1/feed?limit={limit}", token=token, timeout=args.timeout)
    feed_ok = 200 <= code < 300 and isinstance(feed, list)
    report["checks"].append({"name": "fetch_feed", "ok": feed_ok, "status": code, "error": err})

    feed_task_ids = set()
    if feed_ok:
        for item in feed:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "task.status.tested" and item.get("task_id"):
                feed_task_ids.add(str(item["task_id"]))

    for status in STATUSES:
        expected_id = created_by_status.get(status)
        ok = bool(expected_id and expected_id in feed_task_ids)
        report["checks"].append(
            {
                "name": f"feed_contains_{status}_event",
                "ok": ok,
                "expected_task_id": expected_id,
            }
        )

    passed = sum(1 for c in report["checks"] if c.get("ok"))
    total = len(report["checks"])
    all_passed = passed == total and total > 0
    report["summary"] = {
        "passed": passed,
        "total": total,
        "pass_rate_pct": round(passed / total * 100.0, 2) if total else 0.0,
        "all_passed": all_passed,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== 5状态全面测试 ===")
    print(f"通过: {passed}/{total} ({report['summary']['pass_rate_pct']}%)")
    print(f"结果: {'PASS' if all_passed else 'FAIL'}")
    print(f"报告: {out_path}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
