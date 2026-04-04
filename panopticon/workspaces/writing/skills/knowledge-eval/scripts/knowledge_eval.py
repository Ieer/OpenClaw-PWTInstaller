#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


VALID_RISK_LEVELS = {"low", "normal", "high", "critical"}
VALID_RETRIEVAL_MODES = {"lexical", "semantic", "hybrid"}
DEFAULT_LIMIT = 5


@dataclass
class EvalConfig:
    resolve_url: str
    token: str = ""
    default_agent_slug: str = ""
    default_risk_level: str = "normal"
    default_limit: int = DEFAULT_LIMIT


def normalize_api_base(raw_url: str) -> str:
    text = (raw_url or "").strip().rstrip("/")
    if not text:
        return ""
    suffixes = (
        "/v1/knowledge/resolve",
        "/v1/events",
        "/v1",
    )
    for suffix in suffixes:
        if text.endswith(suffix):
            return text[: -len(suffix)].rstrip("/")
    return text


def resolve_endpoint_from_env() -> str:
    explicit = (os.getenv("KNOWLEDGE_RESOLVE_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")

    base = (
        os.getenv("MISSION_CONTROL_API_URL")
        or os.getenv("EVENT_HTTP_URL")
        or ""
    )
    normalized_base = normalize_api_base(base)
    if not normalized_base:
        return ""
    return f"{normalized_base}/v1/knowledge/resolve"


def parse_tags(raw_tags: str | None) -> list[str]:
    if not raw_tags:
        return []
    return [item.strip() for item in raw_tags.split(",") if item.strip()]


def clamp_limit(value: int) -> int:
    return min(max(int(value), 1), 100)


def load_config() -> EvalConfig:
    default_risk_level = (os.getenv("KNOWLEDGE_EVAL_DEFAULT_RISK") or "normal").strip().lower() or "normal"
    if default_risk_level not in VALID_RISK_LEVELS:
        default_risk_level = "normal"

    try:
        default_limit = clamp_limit(int(os.getenv("KNOWLEDGE_EVAL_DEFAULT_LIMIT") or DEFAULT_LIMIT))
    except ValueError:
        default_limit = DEFAULT_LIMIT

    return EvalConfig(
        resolve_url=resolve_endpoint_from_env(),
        token=(os.getenv("EVENT_HTTP_TOKEN") or "").strip(),
        default_agent_slug=(os.getenv("AGENT_SLUG") or "").strip(),
        default_risk_level=default_risk_level,
        default_limit=default_limit,
    )


def build_payload(
    *,
    task: str,
    agent_slug: str | None,
    risk_level: str | None,
    tags: list[str] | None,
    limit: int | None,
    retrieval_mode: str | None,
    ranking_profile: str | None,
    source_type: str | None,
    semantic_query: str | None,
    semantic_limit: int | None,
    min_semantic_similarity: float | None,
    min_score: float | None,
    require_approved_validation: bool | None,
    include_rejected: bool,
    config: EvalConfig,
) -> dict[str, Any]:
    normalized_task = task.strip()
    if not normalized_task:
        raise ValueError("task is required")

    normalized_agent_slug = (agent_slug or config.default_agent_slug or "").strip()
    if not normalized_agent_slug:
        raise ValueError("agent_slug is required via argument or AGENT_SLUG env")

    normalized_risk_level = (risk_level or config.default_risk_level).strip().lower()
    if normalized_risk_level not in VALID_RISK_LEVELS:
        raise ValueError(f"risk_level must be one of {sorted(VALID_RISK_LEVELS)}")

    normalized_limit = clamp_limit(limit if limit is not None else config.default_limit)
    normalized_retrieval_mode = (retrieval_mode or "hybrid").strip().lower()
    if normalized_retrieval_mode not in VALID_RETRIEVAL_MODES:
        raise ValueError(f"retrieval_mode must be one of {sorted(VALID_RETRIEVAL_MODES)}")

    payload: dict[str, Any] = {
        "task": normalized_task,
        "agent_slug": normalized_agent_slug,
        "risk_level": normalized_risk_level,
        "tags": tags or [],
        "limit": normalized_limit,
        "retrieval_mode": normalized_retrieval_mode,
        "ranking_profile": (ranking_profile or "balanced").strip().lower() or "balanced",
        "include_rejected": bool(include_rejected),
    }
    if source_type:
        payload["source_type"] = source_type.strip()
    if semantic_query:
        payload["semantic_query"] = semantic_query.strip()
    if semantic_limit is not None:
        payload["semantic_limit"] = clamp_limit(semantic_limit)
    if min_semantic_similarity is not None:
        payload["min_semantic_similarity"] = float(min_semantic_similarity)
    if min_score is not None:
        payload["min_score"] = float(min_score)
    if require_approved_validation is not None:
        payload["require_approved_validation"] = bool(require_approved_validation)
    return payload


def http_post_json(url: str, token: str, payload: dict[str, Any], timeout: float) -> tuple[int, dict[str, Any] | None, str | None]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url=url,
        method="POST",
        headers=headers,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            if not raw:
                return int(response.status), {}, None
            return int(response.status), json.loads(raw), None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), None, raw[:500] if raw else "http error"
    except Exception as exc:
        return 0, None, str(exc)


def summarize_response(response: dict[str, Any] | None, error: str | None) -> dict[str, Any]:
    if error:
        return {
            "status": "service_error",
            "selected_count": 0,
            "top_items": [],
            "confidence_signals": [],
            "constraints": [error],
            "recommended_action": "检查 Mission Control API 地址、token 与服务可用性后重试。",
            "fallback_reason": error,
        }

    items = list((response or {}).get("items") or [])
    rejected = list((response or {}).get("rejected") or [])
    if not items and rejected:
        return {
            "status": "rejected_only",
            "selected_count": 0,
            "top_items": [],
            "confidence_signals": [],
            "constraints": [entry.get("reason", "rejected") for entry in rejected[:5]],
            "recommended_action": "没有可直接采用的知识条目，需检查 validation、risk_level 或标签过滤。",
            "fallback_reason": "all_candidates_rejected",
        }
    if not items:
        return {
            "status": "no_hit",
            "selected_count": 0,
            "top_items": [],
            "confidence_signals": [],
            "constraints": ["no knowledge items selected"],
            "recommended_action": "改写 task 描述或放宽 tags/source_type 后重新评估。",
            "fallback_reason": "no_candidates_selected",
        }

    top_items: list[dict[str, Any]] = []
    confidence_signals: list[str] = []
    constraints: list[str] = []
    approved_hits = 0
    for item in items[:5]:
        unit = item.get("unit") or {}
        validation_status = item.get("validation_status")
        if validation_status == "approved":
            approved_hits += 1
        retrieval_channels = item.get("retrieval_channels") or []
        top_items.append(
            {
                "unit_key": unit.get("unit_key"),
                "title": unit.get("title"),
                "score": item.get("score"),
                "validation_status": validation_status,
                "retrieval_channels": retrieval_channels,
                "risk_level": unit.get("risk_level"),
            }
        )
        if validation_status:
            confidence_signals.append(f"{unit.get('unit_key')}: validation={validation_status}")
        if retrieval_channels:
            confidence_signals.append(f"{unit.get('unit_key')}: channels={','.join(retrieval_channels)}")
        if validation_status and validation_status != "approved":
            constraints.append(f"{unit.get('unit_key')} validation_status={validation_status}")

    status = "ok" if approved_hits > 0 else "weak_hit"
    if status == "weak_hit" and not constraints:
        constraints.append("命中条目存在，但缺少 approved validation。")

    recommended_action = (
        "可以基于命中知识继续输出正式结论，同时保留约束说明。"
        if status == "ok"
        else "命中资料可作为参考，但正式决策前应补充更高可信度或已审批知识。"
    )

    return {
        "status": status,
        "selected_count": len(items),
        "top_items": top_items,
        "confidence_signals": confidence_signals,
        "constraints": constraints,
        "recommended_action": recommended_action,
        "fallback_reason": None,
    }


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Shared wrapper for Mission Control knowledge resolve")
    parser.add_argument("--task", required=True, help="完整任务描述")
    parser.add_argument("--agent-slug", default="", help="agent slug; fallback to AGENT_SLUG")
    parser.add_argument("--risk-level", default="", help="low|normal|high|critical")
    parser.add_argument("--tags", default="", help="comma-separated tags")
    parser.add_argument("--limit", type=int, default=None, help="knowledge item limit")
    parser.add_argument("--retrieval-mode", default="", help="lexical|semantic|hybrid")
    parser.add_argument("--ranking-profile", default="", help="ranking profile key")
    parser.add_argument("--source-type", default="", help="optional source_type filter")
    parser.add_argument("--semantic-query", default="", help="optional semantic query override")
    parser.add_argument("--semantic-limit", type=int, default=None, help="semantic candidate limit")
    parser.add_argument("--min-semantic-similarity", type=float, default=None, help="minimum semantic similarity")
    parser.add_argument("--min-score", type=float, default=None, help="minimum final score")
    parser.add_argument("--require-approved-validation", action="store_true", help="force approved validation")
    parser.add_argument("--include-rejected", action="store_true", help="include rejected candidates")
    parser.add_argument("--timeout", type=float, default=8.0, help="HTTP timeout in seconds")
    parser.add_argument("--resolve-url", default="", help="override resolve endpoint")
    parser.add_argument("--token", default="", help="override bearer token")
    return parser


def main() -> int:
    parser = create_argument_parser()
    args = parser.parse_args()
    config = load_config()

    if args.resolve_url:
        config.resolve_url = args.resolve_url.strip().rstrip("/")
    if args.token:
        config.token = args.token.strip()

    try:
        payload = build_payload(
            task=args.task,
            agent_slug=args.agent_slug,
            risk_level=args.risk_level,
            tags=parse_tags(args.tags),
            limit=args.limit,
            retrieval_mode=args.retrieval_mode,
            ranking_profile=args.ranking_profile,
            source_type=args.source_type,
            semantic_query=args.semantic_query,
            semantic_limit=args.semantic_limit,
            min_semantic_similarity=args.min_semantic_similarity,
            min_score=args.min_score,
            require_approved_validation=True if args.require_approved_validation else None,
            include_rejected=args.include_rejected,
            config=config,
        )
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "request": None, "summary": None, "raw": None}, ensure_ascii=False, indent=2))
        return 2

    if not config.resolve_url:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "resolve endpoint not configured; set KNOWLEDGE_RESOLVE_URL, MISSION_CONTROL_API_URL, or EVENT_HTTP_URL",
                    "request": payload,
                    "summary": None,
                    "raw": None,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    status_code, response, error = http_post_json(config.resolve_url, config.token, payload, args.timeout)
    ok = 200 <= status_code < 300 and response is not None and error is None
    if not ok and not error:
        error = f"request failed with status={status_code}"

    result = {
        "ok": ok,
        "request": payload,
        "summary": summarize_response(response, error),
        "raw": response,
        "error": error,
        "meta": {
            "resolve_url": config.resolve_url,
            "status_code": status_code,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())