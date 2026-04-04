#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from knowledge_eval import build_payload
from knowledge_eval import http_post_json
from knowledge_eval import load_config
from knowledge_eval import parse_tags
from knowledge_eval import summarize_response


def slugify(value: str) -> str:
    output = []
    for char in value.lower():
        if char.isalnum():
            output.append(char)
        elif char in {" ", "-", "_", "/"}:
            output.append("-")
    slug = "".join(output).strip("-")
    return slug or "knowledge-eval-demo"


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run workspace knowledge eval and write artifact/source files")
    parser.add_argument("--task-id", default="", help="artifact task id; default uses UTC timestamp")
    parser.add_argument("--task", required=True, help="evaluation task description")
    parser.add_argument("--risk-level", default="", help="low|normal|high|critical")
    parser.add_argument("--tags", default="", help="comma-separated tags")
    parser.add_argument("--retrieval-mode", default="hybrid", help="lexical|semantic|hybrid")
    parser.add_argument("--ranking-profile", default="balanced", help="ranking profile key")
    parser.add_argument("--source-type", default="", help="optional source_type filter")
    parser.add_argument("--timeout", type=float, default=8.0, help="HTTP timeout in seconds")
    return parser


def main() -> int:
    args = create_parser().parse_args()
    workspace_root = Path(__file__).resolve().parents[3]
    config = load_config()
    payload = build_payload(
        task=args.task,
        agent_slug="",
        risk_level=args.risk_level,
        tags=parse_tags(args.tags),
        limit=None,
        retrieval_mode=args.retrieval_mode,
        ranking_profile=args.ranking_profile,
        source_type=args.source_type,
        semantic_query=None,
        semantic_limit=None,
        min_semantic_similarity=None,
        min_score=None,
        require_approved_validation=None,
        include_rejected=False,
        config=config,
    )

    task_id = args.task_id.strip() or f"knowledge-eval-{slugify(config.default_agent_slug)}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    status_code, response, error = http_post_json(config.resolve_url, config.token, payload, args.timeout)
    summary = summarize_response(response, error)

    artifact_dir = workspace_root / "artifacts" / task_id
    source_dir = workspace_root / "sources" / task_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)

    payload_out = {
        "task_id": task_id,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "request": payload,
        "summary": summary,
        "raw": response,
        "error": error,
        "meta": {
            "status_code": status_code,
            "resolve_url": config.resolve_url,
            "agent_slug": config.default_agent_slug,
        },
    }
    (artifact_dir / "artifact.json").write_text(json.dumps(payload_out, ensure_ascii=False, indent=2), encoding="utf-8")
    (source_dir / "resolve-response.json").write_text(json.dumps(response or {}, ensure_ascii=False, indent=2), encoding="utf-8")

    top_items = summary.get("top_items") or []
    constraints = summary.get("constraints") or []
    lines = [
        f"# Knowledge Eval Artifact - {task_id}",
        "",
        "## Request",
        f"- Agent: {config.default_agent_slug}",
        f"- Task: {payload['task']}",
        f"- Risk: {payload['risk_level']}",
        f"- Retrieval: {payload['retrieval_mode']}",
        f"- Tags: {', '.join(payload.get('tags') or []) if payload.get('tags') else '(none)'}",
        "",
        "## Summary",
        f"- Status: {summary.get('status')}",
        f"- Selected Count: {summary.get('selected_count')}",
        f"- Recommended Action: {summary.get('recommended_action')}",
        "",
        "## Top Items",
    ]
    if top_items:
        for index, item in enumerate(top_items, start=1):
            lines.append(
                f"- {index}. {item.get('title') or item.get('unit_key')} | score={item.get('score')} | validation={item.get('validation_status')} | channels={','.join(item.get('retrieval_channels') or [])}"
            )
    else:
        lines.append("- (none)")
    lines.extend([
        "",
        "## Constraints",
    ])
    if constraints:
        for item in constraints:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")
    (artifact_dir / "artifact.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"ok": error is None and 200 <= status_code < 300, "task_id": task_id, "artifact_dir": str(artifact_dir), "source_dir": str(source_dir), "status": summary.get("status")}, ensure_ascii=False, indent=2))
    return 0 if error is None and 200 <= status_code < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())