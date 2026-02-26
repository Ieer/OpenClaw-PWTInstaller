#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PARAM_HINTS = {
    "start_time": "开始时间（ISO8601，如 2026-02-01T00:00:00Z）",
    "end_time": "结束时间（ISO8601，如 2026-02-08T00:00:00Z）",
    "day_start": "自然日开始时间",
    "day_end": "自然日结束时间",
    "week_start": "周开始时间",
    "week_end": "周结束时间",
    "top_n": "返回前N条（整数，如 10）",
    "campaign_id": "活动ID",
    "batch_id": "批次ID",
    "experiment_id": "实验ID",
    "feature_key": "功能标识（字符串）",
    "stock_threshold": "库存阈值（数值）",
    "amount_threshold": "金额阈值（数值）",
    "step_a_event": "漏斗步骤A事件名",
    "step_b_event": "漏斗步骤B事件名",
    "retention_day_offset": "留存天数偏移（1 或 7）",
    "cohort_start": "cohort起始时间",
    "cohort_end": "cohort结束时间",
    "active_start": "活跃窗口开始时间",
    "active_end": "活跃窗口结束时间",
    "usage_start": "功能使用窗口开始时间",
    "usage_end": "功能使用窗口结束时间",
    "refund_start": "退款统计开始时间",
    "refund_end": "退款统计结束时间",
    "order_start": "订单统计开始时间",
    "order_end": "订单统计结束时间"
}


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    alnum_tokens = re.findall(r"[a-z0-9_]+", text)

    cjk_chars = re.findall(r"[\u4e00-\u9fff]", text)
    cjk_bigrams = []
    for i in range(len(cjk_chars) - 1):
        cjk_bigrams.append(cjk_chars[i] + cjk_chars[i + 1])

    return alnum_tokens + cjk_chars + cjk_bigrams


def build_template_text(t: dict[str, Any]) -> str:
    intent = t.get("intent", "")
    examples = " ".join(t.get("question_examples", []) or [])
    table_names = " ".join(t.get("required_tables", []) or [])
    return f"{intent} {examples} {table_names}"


@dataclass
class MatchResult:
    template_id: str
    score: float
    intent: str
    params_order: list[str]
    params_hint: list[dict[str, str]]
    required_tables: list[str]
    sql_template: str
    matched_tokens: list[str]


def score_template(query: str, template: dict[str, Any]) -> tuple[float, list[str]]:
    q_tokens = tokenize(query)
    t_tokens = tokenize(build_template_text(template))

    if not q_tokens or not t_tokens:
        return 0.0, []

    q_set = set(q_tokens)
    t_set = set(t_tokens)
    overlap = q_set & t_set

    # 基础分：查询命中率 + 模板覆盖率
    q_cover = len(overlap) / max(1, len(q_set))
    t_cover = len(overlap) / max(1, len(t_set))
    base_score = 0.75 * q_cover + 0.25 * t_cover

    # 意图短语加权
    intent = (template.get("intent") or "").lower()
    phrase_bonus = 0.0
    for key in ["新增用户", "转化", "留存", "退款", "订单", "活动", "实验", "库存", "错误率", "工单"]:
        if key in query and key in intent:
            phrase_bonus += 0.08

    score = min(1.0, base_score + phrase_bonus)
    return score, sorted(overlap)


def build_param_hints(params_order: list[str]) -> list[dict[str, str]]:
    out = []
    for name in params_order:
        out.append({"name": name, "hint": PARAM_HINTS.get(name, "请按业务上下文提供该参数")})
    return out


def route_query(
    query: str,
    templates: list[dict[str, Any]],
    top_k: int = 3,
    min_score: float = 0.15,
) -> list[MatchResult]:
    scored: list[MatchResult] = []
    for t in templates:
        score, matched = score_template(query, t)
        if score < min_score:
            continue

        params_order = list(t.get("params_order", []) or [])
        scored.append(
            MatchResult(
                template_id=t.get("id", ""),
                score=round(score, 4),
                intent=t.get("intent", ""),
                params_order=params_order,
                params_hint=build_param_hints(params_order),
                required_tables=list(t.get("required_tables", []) or []),
                sql_template=t.get("sql_template", ""),
                matched_tokens=matched,
            )
        )

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[: max(1, top_k)]


def parse_allowlist(value: str) -> set[str]:
    return {item.strip() for item in (value or "").split(",") if item.strip()}


def filter_templates_by_allowlist(
    templates: list[dict[str, Any]],
    allowed_tables: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    kept: list[dict[str, Any]] = []
    dropped_ids: list[str] = []

    for t in templates:
        required = set(t.get("required_tables", []) or [])
        if required.issubset(allowed_tables):
            kept.append(t)
        else:
            dropped_ids.append(str(t.get("id", "")))

    return kept, dropped_ids


def load_templates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    templates = payload.get("templates")
    if not isinstance(templates, list):
        raise ValueError("invalid template file: templates must be list")
    return templates


def main() -> int:
    parser = argparse.ArgumentParser(description="NL2SQL router for PostgreSQL skill templates")
    parser.add_argument("--query", required=True, help="natural language question")
    parser.add_argument("--templates", default=str(Path(__file__).resolve().parents[1] / "nl2sql_templates.json"))
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=0.15)
    parser.add_argument(
        "--strict-allowlist",
        default="",
        help="comma-separated available tables; templates requiring tables outside this set are filtered out",
    )
    args = parser.parse_args()

    templates_path = Path(args.templates)
    if not templates_path.exists():
        print(json.dumps({"success": False, "error": f"templates not found: {templates_path}"}, ensure_ascii=False, indent=2))
        return 1

    try:
        templates = load_templates(templates_path)
        strict_allowlist_tables = parse_allowlist(args.strict_allowlist)
        filtered_out_ids: list[str] = []
        if strict_allowlist_tables:
            templates, filtered_out_ids = filter_templates_by_allowlist(templates, strict_allowlist_tables)

        matches = route_query(args.query, templates, top_k=args.top_k, min_score=args.min_score)
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"router failed: {exc}"}, ensure_ascii=False, indent=2))
        return 2

    out = {
        "success": True,
        "query": args.query,
        "templates_path": str(templates_path),
        "top_k": args.top_k,
        "strict_allowlist": sorted(list(parse_allowlist(args.strict_allowlist))) if args.strict_allowlist else [],
        "filtered_template_count": len(filtered_out_ids) if args.strict_allowlist else 0,
        "filtered_template_ids": filtered_out_ids if args.strict_allowlist else [],
        "matches": [
            {
                "template_id": m.template_id,
                "score": m.score,
                "intent": m.intent,
                "required_tables": m.required_tables,
                "params_order": m.params_order,
                "params_hint": m.params_hint,
                "sql_template": m.sql_template,
                "matched_tokens": m.matched_tokens,
            }
            for m in matches
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
