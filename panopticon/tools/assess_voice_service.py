#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_BRIDGE_REQUIRED_STATES = ["listening", "thinking", "speaking"]
DEFAULT_BRIDGE_REQUIRED_EVENT_TYPES = ["voice.asr.final", "voice.tts.start"]


@dataclass
class ShellResult:
    exit_code: int
    stdout: str
    stderr: str


def _env_text(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    text = raw.strip()
    return text if text else default


def _csv_list(raw: str | None) -> list[str]:
    if raw is None:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _first_item(items: list[str], default: str) -> str:
    for item in items:
        if item:
            return item
    return default


def _iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _http_json(
    url: str,
    *,
    method: str = "GET",
    token: str = "",
    payload: dict[str, Any] | None = None,
    timeout: float = 6.0,
) -> tuple[int, dict[str, Any] | list[Any] | None, str | None]:
    headers = {"Accept": "application/json"}
    body = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request_obj = urllib.request.Request(url=url, method=method, headers=headers, data=body)
    try:
        with urllib.request.urlopen(request_obj, timeout=timeout) as response:
            status = int(response.status)
            raw = response.read().decode("utf-8", errors="replace")
            if not raw:
                return status, None, None
            try:
                return status, json.loads(raw), None
            except json.JSONDecodeError:
                return status, None, f"non-json response: {raw[:200]}"
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), None, raw[:200] if raw else "http error"
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        return 0, None, str(exc)


def _docker_ps_running(container: str) -> bool:
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    names = {line.strip() for line in (result.stdout or "").splitlines() if line.strip()}
    return container in names


def _docker_exec(container: str, command: str, *, timeout: float = 30.0) -> ShellResult:
    try:
        result = subprocess.run(
            ["docker", "exec", container, "bash", "-lc", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return ShellResult(exit_code=result.returncode, stdout=result.stdout or "", stderr=result.stderr or "")
    except subprocess.TimeoutExpired as exc:
        return ShellResult(exit_code=124, stdout=exc.stdout or "", stderr=(exc.stderr or "") + "\ntimeout")
    except FileNotFoundError:
        return ShellResult(exit_code=127, stdout="", stderr="docker not found")


def _fetch_voice_events(
    api_base: str,
    token: str,
    *,
    agent: str,
    since: datetime,
    limit: int,
    timeout: float,
) -> tuple[int, list[dict[str, Any]], str | None]:
    status, payload, err = _http_json(f"{api_base}/v1/feed?limit={limit}", token=token, timeout=timeout)
    if status < 200 or status >= 300 or not isinstance(payload, list):
        return status, [], err

    cutoff = since - timedelta(seconds=2)
    selected: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        if str(item.get("agent") or "") != agent:
            continue
        event_type = str(item.get("type") or "")
        if not (event_type.startswith("voice.") or event_type.startswith("task.")):
            continue
        created_at = _iso_to_dt(str(item.get("created_at") or ""))
        if created_at is None or created_at < cutoff:
            continue
        selected.append(item)
    return status, selected, None


def _contains_marker(value: Any, marker: str) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return marker in value
    if isinstance(value, dict):
        return any(_contains_marker(item, marker) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_marker(item, marker) for item in value)
    return marker in str(value)


def _compact_events(events: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for event in events[:limit]:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        compact.append(
            {
                "type": event.get("type"),
                "created_at": event.get("created_at"),
                "task_id": event.get("task_id"),
                "payload": {
                    key: payload.get(key)
                    for key in (
                        "state",
                        "text",
                        "title",
                        "status",
                        "assignee",
                        "summary",
                        "raw_text",
                        "normalized_text",
                        "command_type",
                    )
                    if key in payload
                },
            }
        )
    return compact


def _format_status(status: str) -> str:
    return {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}.get(status, status.upper())


def _command_prefix_from_env() -> str:
    prefixes = _csv_list(os.getenv("MC_VOICE_COMMAND_PREFIXES"))
    return _first_item(prefixes, "指挥")


def _run_bridge_smoke(
    *,
    api_base: str,
    token: str,
    agent: str,
    container: str,
    topic_wakeup: str,
    topic_asr: str,
    topic_text_response: str,
    topic_tts: str,
    required_states: list[str],
    required_event_types: list[str],
    timeout: float,
    feed_limit: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": "bridge_smoke",
        "status": "skip",
        "required_states": required_states,
        "required_event_types": required_event_types,
    }

    if not _docker_ps_running(container):
        result.update(
            {
                "status": "skip",
                "reason": f"container not running: {container}",
            }
        )
        return result

    topics_result = _docker_exec(
        container,
        "set -eo pipefail\n"
        "source /opt/ros/humble/setup.bash\n"
        "ros2 topic list 2>/dev/null || true",
        timeout=max(10.0, timeout),
    )
    if topics_result.exit_code != 0:
        result.update(
            {
                "status": "fail",
                "reason": "failed to list ROS2 topics",
                "stderr": topics_result.stderr[-1200:],
                "stdout": topics_result.stdout[-1200:],
            }
        )
        return result

    visible_topics = [line.strip() for line in (topics_result.stdout or "").splitlines() if line.strip()]
    expected_topics = [f"/{topic_wakeup.lstrip('/')}", f"/{topic_asr.lstrip('/')}", f"/{topic_text_response.lstrip('/')}", f"/{topic_tts.lstrip('/')}"]
    missing_topics = [topic for topic in expected_topics if topic not in visible_topics]
    result["visible_topics"] = visible_topics
    result["missing_topics"] = missing_topics
    if missing_topics:
        result.update(
            {
                "status": "fail",
                "reason": f"missing required ROS2 topics: {', '.join(missing_topics)}",
            }
        )
        return result

    smoke_marker = uuid4().hex[:8]
    smoke_text = f"voice bridge smoke {smoke_marker}"
    topic_specs = [
        (f"/{topic_wakeup.lstrip('/')}", "std_msgs/msg/Bool", "{data: true}"),
        (f"/{topic_asr.lstrip('/')}", "std_msgs/msg/String", f"{{data: {smoke_text}}}"),
        (f"/{topic_text_response.lstrip('/')}", "std_msgs/msg/String", f"{{data: {smoke_text}}}"),
        (f"/{topic_tts.lstrip('/')}", "std_msgs/msg/String", f"{{data: {smoke_text}}}"),
    ]
    publish_script = (
        "set -eo pipefail\n"
        "source /opt/ros/humble/setup.bash\n"
        "python3 - <<'PY'\n"
        "import subprocess\n"
        f"TOPICS = {repr(topic_specs)}\n"
        "for topic, msg_type, message in TOPICS:\n"
        "    subprocess.run(['ros2', 'topic', 'pub', '-1', topic, msg_type, message], check=True)\n"
        "PY\n"
    )

    started_at = datetime.now(timezone.utc)
    publish_result = _docker_exec(container, publish_script, timeout=max(20.0, timeout))
    if publish_result.exit_code != 0:
        result.update(
            {
                "status": "fail",
                "reason": "failed to publish synthetic ROS2 events",
                "stderr": publish_result.stderr[-1200:],
                "stdout": publish_result.stdout[-1200:],
            }
        )
        return result

    deadline = time.monotonic() + timeout
    seen_states: set[str] = set()
    seen_event_types: set[str] = set()
    matched_events: list[dict[str, Any]] = []
    llm_first_token_seen = False
    latency: float | None = None

    while time.monotonic() < deadline:
        status, events, _err = _fetch_voice_events(
            api_base,
            token,
            agent=agent,
            since=started_at,
            limit=feed_limit,
            timeout=min(4.0, timeout),
        )
        if status < 200 or status >= 300:
            time.sleep(0.4)
            continue

        matched_events = events
        seen_event_types = {str(item.get("type") or "") for item in events}
        seen_states = {
            str((item.get("payload") or {}).get("state") or "")
            for item in events
            if str(item.get("type") or "") == "voice.state"
            and str((item.get("payload") or {}).get("state") or "")
        }
        llm_first_token_seen = any(str(item.get("type") or "") == "voice.llm.first_token" for item in events)

        if set(required_event_types).issubset(seen_event_types) and set(required_states).issubset(seen_states):
            latency = round(time.monotonic() - (deadline - timeout), 3)
            break
        time.sleep(0.4)

    result["seen_event_types"] = sorted(seen_event_types)
    result["seen_states"] = sorted(seen_states)
    result["llm_first_token_seen"] = llm_first_token_seen
    result["events"] = _compact_events(matched_events)
    if latency is not None:
        result["latency_sec"] = latency

    missing_event_types = sorted(set(required_event_types) - seen_event_types)
    missing_states = sorted(set(required_states) - seen_states)
    if missing_event_types or missing_states:
        result.update(
            {
                "status": "fail",
                "reason": "bridge smoke did not produce the expected voice events",
                "missing_event_types": missing_event_types,
                "missing_states": missing_states,
            }
        )
        return result

    result.update({"status": "pass", "smoke_text": smoke_text})
    return result


def _run_command_closure(
    *,
    api_base: str,
    token: str,
    agent: str,
    timeout: float,
    feed_limit: int,
    command_template: str,
    assignee: str,
    title_prefix: str,
    status_value: str,
    tags: list[str],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": "command_closure",
        "status": "skip",
        "assignee": assignee,
        "tags": tags,
    }

    marker = uuid4().hex[:8]
    title = f"{title_prefix} {marker}".strip()
    command_text = command_template.format(
        marker=marker,
        prefix=_command_prefix_from_env(),
        assignee=assignee,
        title=title,
        status=status_value,
        tags=",".join(tags),
    )
    source_event = {
        "type": "voice.asr.final",
        "agent": agent,
        "payload": {"text": command_text},
    }

    started_at = datetime.now(timezone.utc)
    post_status, _post_json, post_err = _http_json(
        f"{api_base}/v1/events",
        method="POST",
        token=token,
        payload=source_event,
        timeout=max(6.0, timeout),
    )
    result["command_text"] = command_text
    result["post_status"] = post_status
    if post_status < 200 or post_status >= 300:
        result.update(
            {
                "status": "fail",
                "reason": f"failed to post voice.asr.final event: status={post_status}",
                "error": post_err,
            }
        )
        return result

    deadline = time.monotonic() + timeout
    matched_events: list[dict[str, Any]] = []
    executed_event: dict[str, Any] | None = None
    created_task_event: dict[str, Any] | None = None
    rejected_event: dict[str, Any] | None = None
    latency: float | None = None

    while time.monotonic() < deadline:
        status, events, _err = _fetch_voice_events(
            api_base,
            token,
            agent=agent,
            since=started_at,
            limit=feed_limit,
            timeout=min(4.0, timeout),
        )
        if status < 200 or status >= 300:
            time.sleep(0.4)
            continue

        matched_events = events
        for item in events:
            item_type = str(item.get("type") or "")
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            if item_type == "voice.command.rejected" and _contains_marker(payload, marker):
                rejected_event = item
            if item_type == "voice.command.executed" and _contains_marker(payload, marker):
                executed_event = item
            if item_type == "task.created" and _contains_marker(payload, marker):
                created_task_event = item

        if executed_event and created_task_event:
            executed_task_id = str(executed_event.get("task_id") or "").strip()
            created_task_id = str(created_task_event.get("task_id") or "").strip()
            if executed_task_id and executed_task_id == created_task_id:
                latency = round(time.monotonic() - (deadline - timeout), 3)
                break
        if rejected_event:
            break

        time.sleep(0.4)

    result["events"] = _compact_events(matched_events)
    if latency is not None:
        result["latency_sec"] = latency

    if rejected_event and not executed_event:
        result.update(
            {
                "status": "fail",
                "reason": "voice command was rejected",
                "rejected_event": _compact_events([rejected_event], limit=1)[0],
            }
        )
        return result

    if not executed_event or not created_task_event:
        result.update(
            {
                "status": "fail",
                "reason": "voice command did not reach task creation",
                "missing": [
                    name
                    for name, item in (("voice.command.executed", executed_event), ("task.created", created_task_event))
                    if item is None
                ],
            }
        )
        return result

    executed_payload = executed_event.get("payload") if isinstance(executed_event.get("payload"), dict) else {}
    created_payload = created_task_event.get("payload") if isinstance(created_task_event.get("payload"), dict) else {}

    result.update(
        {
            "status": "pass",
            "task_id": executed_event.get("task_id"),
            "command_type": executed_payload.get("command_type"),
            "summary": executed_payload.get("summary"),
            "created_task": {
                "title": created_payload.get("title"),
                "status": created_payload.get("status"),
                "assignee": created_payload.get("assignee"),
                "tags": created_payload.get("tags"),
            },
        }
    )
    return result


def _print_check(check: dict[str, Any]) -> None:
    status = _format_status(str(check.get("status") or "fail"))
    name = str(check.get("name") or "check")
    detail_parts: list[str] = []

    if name == "api_health":
        detail_parts.append(f"status={check.get('http_status')}")
    elif name == "bridge_container":
        detail_parts.append(f"container={check.get('container')}")
    elif name == "bridge_smoke":
        if check.get("seen_states"):
            detail_parts.append(f"states={','.join(check.get('seen_states'))}")
        if check.get("seen_event_types"):
            detail_parts.append(f"events={','.join(check.get('seen_event_types'))}")
        if check.get("latency_sec") is not None:
            detail_parts.append(f"latency={check.get('latency_sec')}s")
    elif name == "command_closure":
        created = check.get("created_task") if isinstance(check.get("created_task"), dict) else {}
        if created:
            detail_parts.append(f"task={created.get('title')}")
            detail_parts.append(f"status={created.get('status')}")
        if check.get("latency_sec") is not None:
            detail_parts.append(f"latency={check.get('latency_sec')}s")
    else:
        if check.get("reason"):
            detail_parts.append(str(check.get("reason")))

    detail = " ".join(part for part in detail_parts if part)
    if detail:
        print(f"[{status}] {name}: {detail}")
    else:
        print(f"[{status}] {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess Mission Control voice service at layered proof levels")
    parser.add_argument("--api-base", default=_env_text("MC_API_URL", _env_text("MISSION_CONTROL_API_URL", "http://127.0.0.1:18910")))
    parser.add_argument("--auth-token", default=_env_text("MC_AUTH_TOKEN", ""))
    parser.add_argument("--voice-agent", default=_env_text("MC_VOICE_AGENT", "voice-engine"))
    parser.add_argument("--voice-container", default=_env_text("MC_VOICE_BRIDGE_CONTAINER", "mission-control-voice-bridge"))
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(
            _env_text(
                "MC_VOICE_ASSESS_TIMEOUT_S",
                _env_text("MC_VOICE_LIVE_TIMEOUT_S", _env_text("MC_VOICE_E2E_TIMEOUT_S", "20")),
            )
        ),
    )
    parser.add_argument("--feed-limit", type=int, default=int(_env_text("MC_VOICE_ASSESS_FEED_LIMIT", "200")))
    parser.add_argument("--topic-wakeup", default=_env_text("MC_VOICE_TOPIC_WAKEUP", "wakeup"))
    parser.add_argument("--topic-asr", default=_env_text("MC_VOICE_TOPIC_ASR", "asr"))
    parser.add_argument("--topic-text-response", default=_env_text("MC_VOICE_TOPIC_TEXT_RESPONSE", "text_response"))
    parser.add_argument("--topic-tts", default=_env_text("MC_VOICE_TOPIC_TTS", "tts_topic"))
    parser.add_argument(
        "--bridge-required-states",
        default=_env_text("MC_VOICE_EXPECT_EVENT_STATES", ",".join(DEFAULT_BRIDGE_REQUIRED_STATES)),
        help="Comma-separated voice.state payload values required for the bridge smoke",
    )
    parser.add_argument(
        "--bridge-required-event-types",
        default=_env_text("MC_VOICE_EXPECT_EVENT_TYPES", ",".join(DEFAULT_BRIDGE_REQUIRED_EVENT_TYPES)),
        help="Comma-separated event types required for the bridge smoke",
    )
    parser.add_argument("--skip-bridge-smoke", action="store_true", help="Skip ROS2 bridge smoke publication and observation")
    parser.add_argument("--skip-command-closure", action="store_true", help="Skip direct voice command closure check")
    parser.add_argument(
        "--command-template",
        default=_env_text(
            "MC_VOICE_COMMAND_TEMPLATE",
            "{prefix} 创建任务 给 {assignee}：{title}；状态：DONE；标签：voice-assessment,smoke",
        ),
        help="Template for the synthetic voice command. Supports {marker}, {prefix}, {assignee}, {title}, {status}, {tags}",
    )
    parser.add_argument("--command-assignee", default=_env_text("MC_VOICE_COMMAND_ASSIGNEE", "metrics"))
    parser.add_argument("--command-title-prefix", default=_env_text("MC_VOICE_COMMAND_TITLE_PREFIX", "语音服务评估 smoke"))
    parser.add_argument("--command-status", default=_env_text("MC_VOICE_COMMAND_STATUS", "DONE"))
    parser.add_argument(
        "--command-tags",
        default=_env_text("MC_VOICE_COMMAND_TAGS", "voice-assessment,smoke"),
        help="Comma-separated tags used by the synthetic voice command",
    )
    parser.add_argument("--output", default="", help="Optional JSON report path")
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    token = args.auth_token.strip()
    required_states = _csv_list(args.bridge_required_states)
    required_event_types = _csv_list(args.bridge_required_event_types)
    command_tags = _csv_list(args.command_tags)

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_base": api_base,
        "voice_agent": args.voice_agent,
        "voice_container": args.voice_container,
        "checks": [],
    }

    checks: list[dict[str, Any]] = report["checks"]

    status, payload, err = _http_json(f"{api_base}/health", token=token, timeout=min(6.0, args.timeout))
    api_ok = status == 200 and isinstance(payload, dict) and bool(payload.get("ok"))
    checks.append(
        {
            "name": "api_health",
            "status": "pass" if api_ok else "fail",
            "http_status": status,
            "ok": api_ok,
            "error": err,
        }
    )

    if args.skip_bridge_smoke:
        checks.append(
            {
                "name": "bridge_container",
                "status": "skip",
                "container": args.voice_container,
                "reason": "bridge smoke skipped by flag",
            }
        )
        checks.append(
            {
                "name": "bridge_smoke",
                "status": "skip",
                "reason": "bridge smoke skipped by flag",
                "required_states": required_states,
                "required_event_types": required_event_types,
            }
        )
    else:
        container_running = _docker_ps_running(args.voice_container)
        checks.append(
            {
                "name": "bridge_container",
                "status": "pass" if container_running else "fail",
                "container": args.voice_container,
                "running": container_running,
                "reason": None if container_running else f"container not running: {args.voice_container}",
            }
        )
        bridge_result = _run_bridge_smoke(
            api_base=api_base,
            token=token,
            agent=args.voice_agent,
            container=args.voice_container,
            topic_wakeup=args.topic_wakeup,
            topic_asr=args.topic_asr,
            topic_text_response=args.topic_text_response,
            topic_tts=args.topic_tts,
            required_states=required_states,
            required_event_types=required_event_types,
            timeout=args.timeout,
            feed_limit=args.feed_limit,
        )
        checks.append(bridge_result)

    if args.skip_command_closure:
        checks.append(
            {
                "name": "command_closure",
                "status": "skip",
                "reason": "command closure skipped by flag",
            }
        )
    else:
        command_result = _run_command_closure(
            api_base=api_base,
            token=token,
            agent=args.voice_agent,
            timeout=args.timeout,
            feed_limit=args.feed_limit,
            command_template=args.command_template,
            assignee=args.command_assignee,
            title_prefix=args.command_title_prefix,
            status_value=args.command_status,
            tags=command_tags,
        )
        checks.append(command_result)

    failed_checks = [check for check in checks if str(check.get("status")) == "fail"]
    skipped_checks = [check for check in checks if str(check.get("status")) == "skip"]
    passed_checks = [check for check in checks if str(check.get("status")) == "pass"]

    report["summary"] = {
        "ok": not failed_checks,
        "passed": len(passed_checks),
        "failed": len(failed_checks),
        "skipped": len(skipped_checks),
        "total": len(checks),
    }

    print("=== Voice Service Assessment ===")
    print(f"API: {api_base}")
    print(f"Agent: {args.voice_agent}")
    print(f"Container: {args.voice_container}")
    print()
    for check in checks:
        _print_check(check)
    print()
    if report["summary"]["ok"]:
        print(
            f"[PASS] voice service assessment complete: {report['summary']['passed']}/{report['summary']['total']} checks passed"
        )
    else:
        print(
            f"[FAIL] voice service assessment incomplete: {report['summary']['failed']} failed, {report['summary']['skipped']} skipped"
        )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0 if report["summary"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())