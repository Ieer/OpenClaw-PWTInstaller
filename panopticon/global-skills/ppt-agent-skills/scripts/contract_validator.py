#!/usr/bin/env python3
"""Validate v4 workflow contracts.

Supported contracts:
- interview-qa.txt
- requirements-interview.txt
- search.txt
- search-brief.txt
- source-brief.txt
- outline.txt
- style.json
- speech-script.json
- planning image contracts
- per-page review result
- delivery-manifest.json
- svg-export-report.json
- presentation-svg.report.json
- presentation-svg.inspect.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from planning_validator import load_jsonish, load_planning_pages


PASS_WORDS = {"pass", "passed", "通过", "已通过", "ok"}
FAIL_WORDS = {"fail", "failed", "不通过", "未通过", "reject", "rejected"}
SVG_EXPORT_METHODS = {
    "dom_to_svg_editable",
    "png_wrapper_raster",
    "pdf2svg_pathified",
    "failed",
}


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    @property
    def ok(self) -> bool:
        return not self.errors


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def parse_iso_timestamp(label: str, value: Any, result: ValidationResult) -> datetime | None:
    if not is_non_empty_string(value):
        result.error(f"{label}: must be a non-empty ISO timestamp string")
        return None
    raw = str(value).strip()
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        result.error(f"{label}: invalid ISO timestamp {value!r}")
        return None


def parse_non_negative_int(label: str, value: Any, result: ValidationResult) -> int | None:
    if not isinstance(value, int) or value < 0:
        result.error(f"{label}: must be a non-negative integer")
        return None
    return value


def parse_optional_non_negative_int(label: str, value: Any, result: ValidationResult) -> int | None:
    if value is None:
        return None
    return parse_non_negative_int(label, value, result)


def parse_optional_ratio(label: str, value: Any, result: ValidationResult) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        result.error(f"{label}: must be a non-negative number or null")
        return None
    numeric = float(value)
    if numeric < 0:
        result.error(f"{label}: must be >= 0 when provided")
        return None
    return numeric


def is_managed_inspection_slide(slide: dict[str, Any]) -> bool:
    return slide.get("expected_rendered_charts") is not None or slide.get("expected_structured_charts") is not None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def basic_text_gate(path: Path, label: str, min_chars: int = 40, min_lines: int = 2) -> tuple[ValidationResult, dict[str, Any], str]:
    result = ValidationResult()
    text = read_text(path)
    if not text:
        result.error(f"{label}: file is empty")
        return result, {"chars": 0, "lines": 0, "errors": 1, "warnings": 0}, text

    chars = len(text)
    lines = len([line for line in text.splitlines() if line.strip()])
    if chars < min_chars:
        result.error(f"{label}: must contain at least {min_chars} characters")
    if lines < min_lines:
        result.error(f"{label}: must contain at least {min_lines} non-empty lines")

    summary = {
        "chars": chars,
        "lines": lines,
        "errors": len(result.errors),
        "warnings": len(result.warnings),
    }
    return result, summary, text


def contains_any(text: str, words: list[str]) -> bool:
    lowered = text.lower()
    return any(word.lower() in lowered for word in words)


def validate_topics_coverage(text: str, result: ValidationResult, label: str) -> list[str]:
    # 每个维度同时支持中文标题（tpl-interview.md 规范格式）和英文键名（LLM 自由格式兼容）
    required_dimensions = [
        ("scene", ["场景", "使用场景", "应用场景", "scenario"]),
        ("audience", ["受众", "听众", "对象", "audience"]),
        ("target_action", ["目标动作", "希望动作", "行动", "target_action"]),
        ("page_density", ["页数", "密度", "信息密度", "page_density"]),
        ("style", ["风格", "视觉风格", "style:"]),
        ("brand", ["品牌", "logo", "品牌色", "brand:"]),
        ("must_include", ["必含", "必须包含", "必须有", "must_include"]),
        ("must_avoid", ["必避", "避免", "禁用", "must_avoid"]),
        ("language", ["语言", "中文", "英文", "中英", "language:"]),
        ("imagery", ["配图", "图片", "图像", "插图", "imagery", "image_mode"]),
        ("material_strategy", ["资料使用策略", "资料策略", "素材使用", "引用策略", "material_strategy", "materials_strategy"]),
    ]

    matched: list[str] = []
    for key, keywords in required_dimensions:
        if contains_any(text, keywords):
            matched.append(key)
        else:
            result.error(f"{label}: missing required interview dimension `{key}`")
    return matched


def validate_interview(path: Path) -> tuple[ValidationResult, dict[str, Any]]:
    result, summary, text = basic_text_gate(path, "interview-qa", min_chars=120, min_lines=8)
    if not result.errors:
        matched = validate_topics_coverage(text, result, "interview-qa")
        summary["matched_dimensions"] = matched
    summary["errors"] = len(result.errors)
    summary["warnings"] = len(result.warnings)
    return result, summary


def validate_requirements_interview(path: Path) -> tuple[ValidationResult, dict[str, Any]]:
    result, summary, text = basic_text_gate(path, "requirements-interview", min_chars=120, min_lines=8)
    matched = validate_topics_coverage(text, result, "requirements-interview")

    if not contains_any(text, ["branch", "分支", "research", "直接制作", "现有资料"]):
        result.warn("requirements-interview: branch decision is not explicit")

    summary["matched_dimensions"] = matched
    summary["errors"] = len(result.errors)
    summary["warnings"] = len(result.warnings)
    return result, summary


def validate_search(path: Path) -> tuple[ValidationResult, dict[str, Any]]:
    result, summary, text = basic_text_gate(path, "search", min_chars=180, min_lines=8)
    if not contains_any(text, ["http://", "https://", "来源", "source"]):
        result.warn("search: no obvious source marker detected")
    summary["errors"] = len(result.errors)
    summary["warnings"] = len(result.warnings)
    return result, summary


def validate_search_brief(path: Path) -> tuple[ValidationResult, dict[str, Any]]:
    result, summary, text = basic_text_gate(path, "search-brief", min_chars=120, min_lines=6)
    if not contains_any(text, ["结论", "summary", "要点", "insight"]):
        result.warn("search-brief: no explicit summary cue detected")
    summary["errors"] = len(result.errors)
    summary["warnings"] = len(result.warnings)
    return result, summary


def validate_source_brief(path: Path) -> tuple[ValidationResult, dict[str, Any]]:
    result, summary, text = basic_text_gate(path, "source-brief", min_chars=120, min_lines=6)
    if not contains_any(text, ["主题", "topic", "适用", "风险", "限制"]):
        result.warn("source-brief: topic/risk/constraints signals look weak")
    summary["errors"] = len(result.errors)
    summary["warnings"] = len(result.warnings)
    return result, summary


def validate_outline(path: Path) -> tuple[ValidationResult, dict[str, Any]]:
    result, summary, text = basic_text_gate(path, "outline", min_chars=180, min_lines=8)

    page_markers = re.findall(r"(?:第\s*\d+\s*页|slide\s*\d+|p\d+\.|s\d+)", text, flags=re.IGNORECASE)
    if not page_markers:
        result.error("outline: no page-level marker detected (e.g. 第1页 / slide 1)")

    if not contains_any(text, ["自审通过", "SELF_REVIEW_PASS", "outline-self-review", "自审"]):
        result.warn("outline: no explicit self-review marker detected")

    summary["page_markers"] = len(page_markers)
    summary["errors"] = len(result.errors)
    summary["warnings"] = len(result.warnings)
    return result, summary


def parse_pass_fail_from_text(text: str) -> tuple[bool | None, str]:
    lowered = text.lower()
    has_pass = any(token in lowered for token in PASS_WORDS)
    has_fail = any(token in lowered for token in FAIL_WORDS)

    if has_pass and not has_fail:
        return True, "pass-token"
    if has_fail and not has_pass:
        return False, "fail-token"
    if has_pass and has_fail:
        return None, "mixed-pass-fail"
    return None, "no-pass-fail-token"


def validate_page_review(path: Path, require_pass: bool) -> tuple[ValidationResult, dict[str, Any]]:
    result = ValidationResult()
    text = read_text(path)
    verdict: str | None = None
    reason = ""

    parsed_json: Any | None = None
    if path.suffix.lower() == ".json":
        try:
            parsed_json = load_jsonish(path)
        except Exception as exc:
            result.error(f"page-review: invalid JSON payload: {exc}")

    if isinstance(parsed_json, dict):
        candidate_fields = [
            parsed_json.get("verdict"),
            parsed_json.get("status"),
            parsed_json.get("result"),
            parsed_json.get("review", {}).get("verdict") if isinstance(parsed_json.get("review"), dict) else None,
        ]
        for item in candidate_fields:
            if not is_non_empty_string(item):
                continue
            token = str(item).strip().lower()
            if token in {"pass", "passed", "ok", "通过", "已通过"}:
                verdict = "pass"
                reason = "json-verdict"
                break
            if token in {"fail", "failed", "reject", "rejected", "不通过", "未通过"}:
                verdict = "fail"
                reason = "json-verdict"
                break

    if verdict is None:
        pass_result, token_reason = parse_pass_fail_from_text(text)
        reason = token_reason
        if pass_result is True:
            verdict = "pass"
        elif pass_result is False:
            verdict = "fail"

    if verdict is None:
        result.error("page-review: could not infer pass/fail verdict")
    elif require_pass and verdict != "pass":
        result.error("page-review: verdict is not pass")

    summary = {
        "verdict": verdict,
        "reason": reason,
        "errors": len(result.errors),
        "warnings": len(result.warnings),
    }
    return result, summary


def resolve_artifact_path(base_dir: Path, raw_path: Any) -> Path | None:
    if not is_non_empty_string(raw_path):
        return None
    p = Path(str(raw_path).strip())
    if p.is_absolute():
        return p
    return (base_dir / p).resolve()


def validate_delivery_manifest(path: Path, base_dir: Path | None) -> tuple[ValidationResult, dict[str, Any]]:
    result = ValidationResult()
    payload = load_jsonish(path)
    if not isinstance(payload, dict):
        raise ValueError("delivery-manifest must be a JSON object")

    manifest = payload.get("delivery_manifest") if isinstance(payload.get("delivery_manifest"), dict) else payload
    if not isinstance(manifest, dict):
        raise ValueError("delivery_manifest payload must be an object")

    for field_name in ("run_id", "generated_at", "artifacts"):
        if field_name not in manifest:
            result.error(f"missing required field: {field_name}")

    run_id = manifest.get("run_id")
    if not is_non_empty_string(run_id):
        result.error("run_id: must be a non-empty string")

    parse_iso_timestamp("generated_at", manifest.get("generated_at"), result)

    summary_obj = manifest.get("summary")
    if summary_obj is not None and not isinstance(summary_obj, dict):
        result.error("summary: must be an object when provided")
    if isinstance(summary_obj, dict):
        total_pages = summary_obj.get("total_pages")
        if total_pages is not None and (not isinstance(total_pages, int) or total_pages <= 0):
            result.error("summary.total_pages: must be a positive integer when provided")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        result.error("artifacts: must be an object")
        artifacts = {}

    required_artifacts = (
        "preview_html",
        "speech_script_json",
        "speech_script_md",
        "presentation_png_pptx",
        "presentation_svg_pptx",
    )
    existing_count = 0
    for key in required_artifacts:
        raw_path = artifacts.get(key)
        if not is_non_empty_string(raw_path):
            result.error(f"artifacts.{key}: must be a non-empty path string")
            continue
        if base_dir is None:
            continue
        resolved = resolve_artifact_path(base_dir, raw_path)
        if resolved is None or not resolved.exists():
            result.error(f"artifacts.{key}: path does not exist -> {raw_path}")
        else:
            existing_count += 1

    pages = manifest.get("pages")
    if pages is not None and not isinstance(pages, list):
        result.error("pages: must be a list when provided")

    summary = {
        "run_id": run_id,
        "artifacts_checked": list(required_artifacts),
        "existing_artifacts": existing_count,
        "errors": len(result.errors),
        "warnings": len(result.warnings),
    }
    return result, summary


def validate_speech_script(path: Path, expected_pages: int | None = None) -> tuple[ValidationResult, dict[str, Any]]:
    result = ValidationResult()
    payload = load_jsonish(path)
    if not isinstance(payload, dict):
        raise ValueError("speech-script must be a JSON object")

    if not is_non_empty_string(payload.get("deck_title")):
        result.error("deck_title: must be a non-empty string")
    if not is_non_empty_string(payload.get("language")):
        result.error("language: must be a non-empty string")
    if payload.get("summary") is not None and not is_non_empty_string(payload.get("summary")):
        result.error("summary: must be a non-empty string when provided")

    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        result.error("pages: must be a non-empty list")
        pages = []

    page_numbers: set[int] = set()
    short_notes = 0
    estimated_total_seconds = 0

    for entry in pages:
        if not isinstance(entry, dict):
            result.error("pages[]: each item must be an object")
            continue

        page_number = parse_non_negative_int("pages[].page", entry.get("page"), result)
        if page_number is not None:
            if page_number <= 0:
                result.error("pages[].page: must be >= 1")
            elif page_number in page_numbers:
                result.error(f"duplicate page number: {page_number}")
            else:
                page_numbers.add(page_number)

        if not is_non_empty_string(entry.get("slide_title")):
            result.error("pages[].slide_title: must be a non-empty string")

        notes_text = entry.get("speaker_notes")
        if not is_non_empty_string(notes_text):
            result.error("pages[].speaker_notes: must be a non-empty string")
        else:
            stripped_notes = str(notes_text).strip()
            if len(stripped_notes) < 40:
                result.warn("pages[].speaker_notes: looks too short to be a usable talk track")
                short_notes += 1

        estimated_seconds = entry.get("estimated_seconds")
        if estimated_seconds is not None:
            estimated_value = parse_non_negative_int("pages[].estimated_seconds", estimated_seconds, result)
            if estimated_value is not None:
                if estimated_value <= 0:
                    result.error("pages[].estimated_seconds: must be >= 1 when provided")
                else:
                    estimated_total_seconds += estimated_value
                    if estimated_value < 15 or estimated_value > 180:
                        result.warn(
                            "pages[].estimated_seconds: unusual per-slide duration "
                            f"{estimated_value}s (expected 15-180s)"
                        )

        if entry.get("transition_to_next") is not None and not is_non_empty_string(entry.get("transition_to_next")):
            result.error("pages[].transition_to_next: must be a non-empty string when provided")

    ordered_numbers = sorted(page_numbers)
    expected_sequence = list(range(1, len(ordered_numbers) + 1))
    if ordered_numbers and ordered_numbers != expected_sequence:
        result.error(
            "pages[].page: numbering must be contiguous starting at 1; "
            f"expected {expected_sequence}, got {ordered_numbers}"
        )

    total_pages = len(ordered_numbers)
    if expected_pages is not None and total_pages != expected_pages:
        result.error(f"pages: expected {expected_pages}, got {total_pages}")

    if payload.get("total_pages") is not None:
        total_pages_value = parse_non_negative_int("total_pages", payload.get("total_pages"), result)
        if total_pages_value is not None and total_pages_value != total_pages:
            result.error(f"total_pages: expected {total_pages}, got {total_pages_value}")

    summary = {
        "deck_title": payload.get("deck_title"),
        "language": payload.get("language"),
        "total_pages": total_pages,
        "short_notes": short_notes,
        "estimated_total_seconds": estimated_total_seconds,
        "errors": len(result.errors),
        "warnings": len(result.warnings),
    }
    return result, summary


def validate_svg_export_report(path: Path, base_dir: Path | None) -> tuple[ValidationResult, dict[str, Any]]:
    result = ValidationResult()
    payload = load_jsonish(path)
    if not isinstance(payload, dict):
        raise ValueError("svg-export-report must be a JSON object")

    for field_name in ("generated_at", "html_input", "svg_output_dir", "summary", "pages"):
        if field_name not in payload:
            result.error(f"missing required field: {field_name}")

    parse_iso_timestamp("generated_at", payload.get("generated_at"), result)

    summary_obj = payload.get("summary")
    if not isinstance(summary_obj, dict):
        result.error("summary: must be an object")
        summary_obj = {}

    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        result.error("pages: must be a non-empty list")
        pages = []

    page_numbers: set[int] = set()
    editable_pages = 0
    raster_pages = 0
    pathified_pages = 0
    failed_pages = 0
    warning_pages = 0

    for page in pages:
        if not isinstance(page, dict):
            result.error("pages[]: each item must be an object")
            continue
        page_number = page.get("page_number")
        page_number_value = parse_non_negative_int("pages[].page_number", page_number, result)
        if page_number_value is not None:
            if page_number_value <= 0:
                result.error("pages[].page_number: must be >= 1")
            elif page_number_value in page_numbers:
                result.error(f"duplicate page_number: {page_number_value}")
            else:
                page_numbers.add(page_number_value)

        for field_name in ("page_name", "source_html", "source_svg", "method"):
            if not is_non_empty_string(page.get(field_name)):
                result.error(f"pages[].{field_name}: must be a non-empty string")

        method = page.get("method")
        if method not in SVG_EXPORT_METHODS:
            result.error(f"pages[].method: unsupported value {method!r}")

        editable = page.get("editable")
        success = page.get("success")
        if not isinstance(editable, bool):
            result.error("pages[].editable: must be a boolean")
        if not isinstance(success, bool):
            result.error("pages[].success: must be a boolean")

        if method == "dom_to_svg_editable" and (editable is not True or success is not True):
            result.error("pages[].method=dom_to_svg_editable requires editable=true and success=true")
        if method in {"png_wrapper_raster", "pdf2svg_pathified"} and (editable is not False or success is not True):
            result.error(f"pages[].method={method} requires editable=false and success=true")
        if method == "failed" and (editable is not False or success is not False):
            result.error("pages[].method=failed requires editable=false and success=false")

        for field_name in ("text_count", "image_count", "path_count"):
            parse_non_negative_int(f"pages[].{field_name}", page.get(field_name), result)

        warning = page.get("warning")
        if warning is not None and not is_non_empty_string(warning):
            result.error("pages[].warning: must be a non-empty string when provided")

        if editable is True:
            editable_pages += 1
        if method == "png_wrapper_raster":
            raster_pages += 1
        if method == "pdf2svg_pathified":
            pathified_pages += 1
        if success is False:
            failed_pages += 1
        if warning:
            warning_pages += 1

        if base_dir is not None:
            source_html = resolve_artifact_path(base_dir, page.get("source_html"))
            source_svg = resolve_artifact_path(base_dir, page.get("source_svg"))
            if source_html is None or not source_html.exists():
                result.error(f"pages[].source_html: path does not exist -> {page.get('source_html')}")
            if success is True and (source_svg is None or not source_svg.exists()):
                result.error(f"pages[].source_svg: path does not exist -> {page.get('source_svg')}")

    total_pages = parse_non_negative_int("summary.total_pages", summary_obj.get("total_pages"), result)
    expected_counts = {
        "editable_pages": editable_pages,
        "raster_fallback_pages": raster_pages,
        "pathified_pages": pathified_pages,
        "failed_pages": failed_pages,
        "warning_pages": warning_pages,
    }
    for field_name, expected_value in expected_counts.items():
        actual = parse_non_negative_int(f"summary.{field_name}", summary_obj.get(field_name), result)
        if actual is not None and actual != expected_value:
            result.error(f"summary.{field_name}: expected {expected_value}, got {actual}")
    if total_pages is not None and total_pages != len(pages):
        result.error(f"summary.total_pages: expected {len(pages)}, got {total_pages}")

    summary = {
        "total_pages": len(pages),
        "editable_pages": editable_pages,
        "raster_fallback_pages": raster_pages,
        "pathified_pages": pathified_pages,
        "failed_pages": failed_pages,
        "warning_pages": warning_pages,
        "errors": len(result.errors),
        "warnings": len(result.warnings),
    }
    if raster_pages > 0 or pathified_pages > 0 or failed_pages > 0:
        result.warn(
            "svg-export-report: export contains degraded pages "
            f"(raster={raster_pages}, pathified={pathified_pages}, failed={failed_pages})"
        )
    summary["warnings"] = len(result.warnings)
    return result, summary


def validate_pptx_export_report(path: Path, base_dir: Path | None) -> tuple[ValidationResult, dict[str, Any]]:
    result = ValidationResult()
    payload = load_jsonish(path)
    if not isinstance(payload, dict):
        raise ValueError("pptx-export-report must be a JSON object")

    for field_name in ("generated_at", "presentation_path", "summary", "pages"):
        if field_name not in payload:
            result.error(f"missing required field: {field_name}")

    parse_iso_timestamp("generated_at", payload.get("generated_at"), result)

    presentation_path = payload.get("presentation_path")
    if not is_non_empty_string(presentation_path):
        result.error("presentation_path: must be a non-empty string")
    elif base_dir is not None:
        resolved = resolve_artifact_path(base_dir, presentation_path)
        if resolved is None or not resolved.exists():
            result.error(f"presentation_path: path does not exist -> {presentation_path}")

    warnings_obj = payload.get("warnings")
    if warnings_obj is not None and (not isinstance(warnings_obj, list) or any(not is_non_empty_string(item) for item in warnings_obj)):
        result.error("warnings: must be a list of non-empty strings when provided")

    update_mode = payload.get("update_mode")
    if update_mode is None:
        update_mode = "new_presentation"
    elif update_mode not in {"new_presentation", "template_update"}:
        result.error("update_mode: must be 'new_presentation' or 'template_update'")

    template_update_scope = payload.get("template_update_scope")
    if template_update_scope is not None and template_update_scope not in {"block_update"}:
        result.error("template_update_scope: unsupported value")

    template_pptx_path = payload.get("template_pptx_path")
    if update_mode == "template_update":
        if not is_non_empty_string(template_pptx_path):
            result.error("template_pptx_path: must be a non-empty string in template_update mode")
        else:
            candidate = Path(template_pptx_path)
            if not candidate.is_absolute() and base_dir is not None:
                candidate = (base_dir / candidate).resolve()
            elif not candidate.is_absolute():
                candidate = candidate.resolve()
            if not candidate.exists():
                result.error(f"template_pptx_path: path does not exist -> {template_pptx_path}")

    target_slide_numbers_obj = payload.get("target_slide_numbers")
    target_slide_numbers: list[int] = []
    if target_slide_numbers_obj is not None:
        if not isinstance(target_slide_numbers_obj, list):
            result.error("target_slide_numbers: must be a list when provided")
        else:
            seen_target_slides: set[int] = set()
            for slide_number in target_slide_numbers_obj:
                parsed = parse_non_negative_int("target_slide_numbers[]", slide_number, result)
                if parsed is None:
                    continue
                if parsed <= 0:
                    result.error("target_slide_numbers[]: must be >= 1")
                    continue
                if parsed in seen_target_slides:
                    result.error(f"target_slide_numbers[]: duplicate slide number {parsed}")
                    continue
                seen_target_slides.add(parsed)
                target_slide_numbers.append(parsed)
    if update_mode == "template_update" and not target_slide_numbers:
        result.error("target_slide_numbers: must be a non-empty list in template_update mode")

    preserve_template_background = payload.get("preserve_template_background")
    if preserve_template_background is not None and not isinstance(preserve_template_background, bool):
        result.error("preserve_template_background: must be boolean when provided")

    summary_obj = payload.get("summary")
    if not isinstance(summary_obj, dict):
        result.error("summary: must be an object")
        summary_obj = {}

    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        result.error("pages: must be a non-empty list")
        pages = []

    page_numbers: set[int] = set()
    editable_pages = 0
    raster_pages = 0
    pathified_pages = 0
    failed_pages = 0
    unknown_pages = 0
    pptx_shapes_total = 0
    pptx_skipped_total = 0
    pptx_errors_total = 0
    rendered_chart_regions_total = 0
    native_charts_total = 0
    structured_chart_groups_total = 0
    structured_chart_hits_total = 0
    updated_blocks_total = 0
    template_removed_shapes_total = 0
    template_removed_slot_shapes_total = 0
    template_removed_managed_shapes_total = 0

    for page in pages:
        if not isinstance(page, dict):
            result.error("pages[]: each item must be an object")
            continue
        slide_number = parse_non_negative_int("pages[].slide_number", page.get("slide_number"), result)
        if slide_number is not None:
            if slide_number <= 0:
                result.error("pages[].slide_number: must be >= 1")
            elif slide_number in page_numbers:
                result.error(f"duplicate slide_number: {slide_number}")
            else:
                page_numbers.add(slide_number)

        if not is_non_empty_string(page.get("svg_file")):
            result.error("pages[].svg_file: must be a non-empty string")

        source_method = page.get("source_method")
        if not is_non_empty_string(source_method):
            result.error("pages[].source_method: must be a non-empty string")
            source_method = "unknown"

        source_editable = page.get("source_editable")
        if source_method == "unknown":
            if source_editable is not None and not isinstance(source_editable, bool):
                result.error("pages[].source_editable: must be boolean or null")
        elif not isinstance(source_editable, bool):
            result.error("pages[].source_editable: must be a boolean for known source_method")

        source_text_count = page.get("source_text_count")
        if source_text_count is not None:
            parse_non_negative_int("pages[].source_text_count", source_text_count, result)

        pptx_shapes = parse_non_negative_int("pages[].pptx_shapes", page.get("pptx_shapes"), result)
        pptx_skipped = parse_non_negative_int("pages[].pptx_skipped", page.get("pptx_skipped"), result)
        pptx_errors = parse_non_negative_int("pages[].pptx_errors", page.get("pptx_errors"), result)
        rendered_charts = parse_optional_non_negative_int("pages[].rendered_charts", page.get("rendered_charts"), result)
        native_charts = parse_optional_non_negative_int("pages[].native_charts", page.get("native_charts"), result)
        structured_chart_groups = parse_optional_non_negative_int(
            "pages[].structured_chart_groups", page.get("structured_chart_groups"), result
        )
        updated_block_ids_obj = page.get("updated_block_ids")
        updated_block_ids: list[str] = []
        if updated_block_ids_obj is not None:
            if not isinstance(updated_block_ids_obj, list) or any(not is_non_empty_string(item) for item in updated_block_ids_obj):
                result.error("pages[].updated_block_ids: must be a list of non-empty strings when provided")
            else:
                updated_block_ids = [str(item) for item in updated_block_ids_obj]
                if len(set(updated_block_ids)) != len(updated_block_ids):
                    result.error("pages[].updated_block_ids: duplicate block ids are not allowed")
        template_update_scope_page = page.get("template_update_scope")
        if template_update_scope_page is not None and template_update_scope_page not in {"block_update"}:
            result.error("pages[].template_update_scope: unsupported value")
        template_removed_shapes = parse_optional_non_negative_int(
            "pages[].template_removed_shapes", page.get("template_removed_shapes"), result
        )
        template_removed_slot_shapes = parse_optional_non_negative_int(
            "pages[].template_removed_slot_shapes", page.get("template_removed_slot_shapes"), result
        )
        template_removed_managed_shapes = parse_optional_non_negative_int(
            "pages[].template_removed_managed_shapes", page.get("template_removed_managed_shapes"), result
        )
        page_warnings = page.get("warnings")
        if page_warnings is not None and (not isinstance(page_warnings, list) or any(not is_non_empty_string(item) for item in page_warnings)):
            result.error("pages[].warnings: must be a list of non-empty strings when provided")

        if source_method == "dom_to_svg_editable":
            editable_pages += 1
        elif source_method == "png_wrapper_raster":
            raster_pages += 1
        elif source_method == "pdf2svg_pathified":
            pathified_pages += 1
        elif source_method == "failed":
            failed_pages += 1
        else:
            unknown_pages += 1

        if pptx_shapes is not None:
            pptx_shapes_total += pptx_shapes
        if pptx_skipped is not None:
            pptx_skipped_total += pptx_skipped
        if pptx_errors is not None:
            pptx_errors_total += pptx_errors
        if rendered_charts is not None:
            rendered_chart_regions_total += rendered_charts
        if native_charts is not None:
            native_charts_total += native_charts
        if structured_chart_groups is not None:
            structured_chart_groups_total += structured_chart_groups
        structured_chart_hits_total += (native_charts or 0) + (structured_chart_groups or 0)
        updated_blocks_total += len(updated_block_ids)
        template_removed_shapes_total += template_removed_shapes or 0
        template_removed_slot_shapes_total += template_removed_slot_shapes or 0
        template_removed_managed_shapes_total += template_removed_managed_shapes or 0

    total_slides = parse_non_negative_int("summary.total_slides", summary_obj.get("total_slides"), result)
    expected_counts = {
        "source_editable_slides": editable_pages,
        "source_raster_slides": raster_pages,
        "source_pathified_slides": pathified_pages,
        "source_failed_slides": failed_pages,
        "source_unknown_slides": unknown_pages,
        "pptx_shapes_total": pptx_shapes_total,
        "pptx_skipped_total": pptx_skipped_total,
        "pptx_errors_total": pptx_errors_total,
        "rendered_chart_regions_total": rendered_chart_regions_total,
        "native_charts_total": native_charts_total,
        "structured_chart_groups_total": structured_chart_groups_total,
        "structured_chart_hits_total": structured_chart_hits_total,
    }
    for field_name, expected_value in expected_counts.items():
        actual = parse_non_negative_int(f"summary.{field_name}", summary_obj.get(field_name), result)
        if actual is not None and actual != expected_value:
            result.error(f"summary.{field_name}: expected {expected_value}, got {actual}")
    template_expected_counts = {
        "updated_blocks_total": updated_blocks_total,
        "template_removed_shapes_total": template_removed_shapes_total,
        "template_removed_slot_shapes_total": template_removed_slot_shapes_total,
        "template_removed_managed_shapes_total": template_removed_managed_shapes_total,
    }
    for field_name, expected_value in template_expected_counts.items():
        parser = parse_non_negative_int if update_mode == "template_update" else parse_optional_non_negative_int
        actual = parser(f"summary.{field_name}", summary_obj.get(field_name), result)
        if actual is not None and actual != expected_value:
            result.error(f"summary.{field_name}: expected {expected_value}, got {actual}")
    structured_chart_hit_rate = parse_optional_ratio(
        "summary.structured_chart_hit_rate", summary_obj.get("structured_chart_hit_rate"), result
    )
    expected_structured_chart_hit_rate = round(
        structured_chart_hits_total / rendered_chart_regions_total, 4
    ) if rendered_chart_regions_total else None
    if expected_structured_chart_hit_rate is None:
        if structured_chart_hit_rate is not None:
            result.error("summary.structured_chart_hit_rate: expected null when rendered_chart_regions_total is 0")
    elif structured_chart_hit_rate is None or round(structured_chart_hit_rate, 4) != expected_structured_chart_hit_rate:
        result.error(
            "summary.structured_chart_hit_rate: expected "
            f"{expected_structured_chart_hit_rate}, got {structured_chart_hit_rate}"
        )
    if total_slides is not None and total_slides != len(pages):
        result.error(f"summary.total_slides: expected {len(pages)}, got {total_slides}")
    if update_mode == "template_update" and target_slide_numbers and page_numbers != set(target_slide_numbers):
        result.error(
            "target_slide_numbers: expected to match pages[].slide_number set "
            f"({sorted(page_numbers)} != {sorted(target_slide_numbers)})"
        )

    summary = {
        "total_slides": len(pages),
        "source_editable_slides": editable_pages,
        "source_raster_slides": raster_pages,
        "source_pathified_slides": pathified_pages,
        "source_failed_slides": failed_pages,
        "source_unknown_slides": unknown_pages,
        "pptx_shapes_total": pptx_shapes_total,
        "pptx_skipped_total": pptx_skipped_total,
        "pptx_errors_total": pptx_errors_total,
        "rendered_chart_regions_total": rendered_chart_regions_total,
        "native_charts_total": native_charts_total,
        "structured_chart_groups_total": structured_chart_groups_total,
        "structured_chart_hits_total": structured_chart_hits_total,
        "updated_blocks_total": updated_blocks_total,
        "template_removed_shapes_total": template_removed_shapes_total,
        "template_removed_slot_shapes_total": template_removed_slot_shapes_total,
        "template_removed_managed_shapes_total": template_removed_managed_shapes_total,
        "structured_chart_hit_rate": expected_structured_chart_hit_rate,
        "errors": len(result.errors),
        "warnings": len(result.warnings),
    }
    if raster_pages > 0 or pathified_pages > 0 or failed_pages > 0:
        result.warn(
            "pptx-export-report: source export includes degraded slides "
            f"(raster={raster_pages}, pathified={pathified_pages}, failed={failed_pages})"
        )
    summary["warnings"] = len(result.warnings)
    return result, summary


def validate_pptx_inspection(path: Path, base_dir: Path | None) -> tuple[ValidationResult, dict[str, Any]]:
    result = ValidationResult()
    payload = load_jsonish(path)
    if not isinstance(payload, dict):
        raise ValueError("pptx-inspection must be a JSON object")

    for field_name in ("generated_at", "pptx_path", "summary", "slides"):
        if field_name not in payload:
            result.error(f"missing required field: {field_name}")

    parse_iso_timestamp("generated_at", payload.get("generated_at"), result)

    pptx_path = payload.get("pptx_path")
    if not is_non_empty_string(pptx_path):
        result.error("pptx_path: must be a non-empty string")
    elif base_dir is not None:
        resolved = resolve_artifact_path(base_dir, pptx_path)
        if resolved is None or not resolved.exists():
            result.error(f"pptx_path: path does not exist -> {pptx_path}")

    slide_size = payload.get("slide_size")
    if not isinstance(slide_size, dict):
        result.error("slide_size: must be an object")
    else:
        parse_non_negative_int("slide_size.width", slide_size.get("width"), result)
        parse_non_negative_int("slide_size.height", slide_size.get("height"), result)

    summary_obj = payload.get("summary")
    if not isinstance(summary_obj, dict):
        result.error("summary: must be an object")
        summary_obj = {}

    slides = payload.get("slides")
    if not isinstance(slides, list) or not slides:
        result.error("slides: must be a non-empty list")
        slides = []

    slide_numbers: set[int] = set()
    total_shapes = 0
    slides_with_notes = 0
    notes_char_total = 0
    picture_only_slides = 0
    full_slide_picture_slides = 0
    degraded_slides = 0
    table_slides = 0
    chart_slides = 0
    chart_group_slides = 0
    native_chart_slides = 0
    chart_group_shapes_total = 0
    native_chart_shapes_total = 0
    structured_chart_shapes_total = 0
    expected_rendered_chart_regions_total = 0
    expected_chart_groups_total = 0
    expected_native_charts_total = 0
    expected_structured_chart_shapes_total = 0
    managed_chart_slide_count = 0

    managed_scope: list[dict[str, Any]] = []

    for slide in slides:
        if not isinstance(slide, dict):
            result.error("slides[]: each item must be an object")
            continue
        slide_number = parse_non_negative_int("slides[].slide_number", slide.get("slide_number"), result)
        if slide_number is not None:
            if slide_number <= 0:
                result.error("slides[].slide_number: must be >= 1")
            elif slide_number in slide_numbers:
                result.error(f"duplicate slide_number: {slide_number}")
            else:
                slide_numbers.add(slide_number)

        for field_name in (
            "shape_count",
            "picture_count",
            "text_shape_count",
            "auto_shape_count",
            "table_count",
            "chart_count",
            "group_count",
            "chart_group_count",
            "native_chart_count",
            "structured_chart_count",
            "connector_count",
            "other_count",
            "full_slide_picture_count",
            "notes_char_count",
        ):
            parse_non_negative_int(f"slides[].{field_name}", slide.get(field_name), result)

        for field_name in (
            "expected_rendered_charts",
            "expected_chart_groups",
            "expected_native_charts",
            "expected_structured_charts",
        ):
            parse_optional_non_negative_int(f"slides[].{field_name}", slide.get(field_name), result)

        for field_name in ("chart_group_hit_rate", "structured_chart_hit_rate"):
            parse_optional_ratio(f"slides[].{field_name}", slide.get(field_name), result)

        if not isinstance(slide.get("degraded_full_slide_picture"), bool):
            result.error("slides[].degraded_full_slide_picture: must be a boolean")
        if not isinstance(slide.get("has_notes"), bool):
            result.error("slides[].has_notes: must be a boolean")
        if not isinstance(slide.get("shape_type_breakdown"), dict):
            result.error("slides[].shape_type_breakdown: must be an object")
        else:
            for key, value in slide["shape_type_breakdown"].items():
                if not is_non_empty_string(key):
                    result.error("slides[].shape_type_breakdown: keys must be non-empty strings")
                parse_non_negative_int("slides[].shape_type_breakdown.*", value, result)

        shape_count = slide.get("shape_count") if isinstance(slide.get("shape_count"), int) else 0
        picture_count = slide.get("picture_count") if isinstance(slide.get("picture_count"), int) else 0
        full_slide_picture_count = slide.get("full_slide_picture_count") if isinstance(slide.get("full_slide_picture_count"), int) else 0
        table_count = slide.get("table_count") if isinstance(slide.get("table_count"), int) else 0
        chart_count = slide.get("chart_count") if isinstance(slide.get("chart_count"), int) else 0
        chart_group_count = slide.get("chart_group_count") if isinstance(slide.get("chart_group_count"), int) else 0
        native_chart_count = slide.get("native_chart_count") if isinstance(slide.get("native_chart_count"), int) else 0
        structured_chart_count = slide.get("structured_chart_count") if isinstance(slide.get("structured_chart_count"), int) else 0
        notes_char_count = slide.get("notes_char_count") if isinstance(slide.get("notes_char_count"), int) else 0
        expected_rendered_charts = slide.get("expected_rendered_charts") if isinstance(slide.get("expected_rendered_charts"), int) else None
        expected_chart_groups = slide.get("expected_chart_groups") if isinstance(slide.get("expected_chart_groups"), int) else None
        expected_native_charts = slide.get("expected_native_charts") if isinstance(slide.get("expected_native_charts"), int) else None
        expected_structured_charts = slide.get("expected_structured_charts") if isinstance(slide.get("expected_structured_charts"), int) else None
        chart_group_hit_rate = slide.get("chart_group_hit_rate") if isinstance(slide.get("chart_group_hit_rate"), (int, float)) else None
        structured_chart_hit_rate = slide.get("structured_chart_hit_rate") if isinstance(slide.get("structured_chart_hit_rate"), (int, float)) else None

        total_shapes += shape_count
        if bool(slide.get("has_notes")):
            slides_with_notes += 1
        notes_char_total += notes_char_count
        if shape_count > 0 and picture_count == shape_count:
            picture_only_slides += 1
        if full_slide_picture_count > 0:
            full_slide_picture_slides += 1
        if bool(slide.get("degraded_full_slide_picture")):
            degraded_slides += 1
        if table_count > 0:
            table_slides += 1
        if chart_count > 0:
            chart_slides += 1
        if is_managed_inspection_slide(slide):
            managed_scope.append(slide)
            managed_chart_slide_count += 1

        if structured_chart_count != chart_group_count + native_chart_count:
            result.error(
                "slides[].structured_chart_count: expected "
                f"{chart_group_count + native_chart_count}, got {structured_chart_count}"
            )
        if expected_chart_groups is not None and chart_group_count != expected_chart_groups:
            result.error(
                "slides[].chart_group_count: expected source-report count "
                f"{expected_chart_groups}, got {chart_group_count}"
            )
        if expected_native_charts is not None and native_chart_count != expected_native_charts:
            result.error(
                "slides[].native_chart_count: expected source-report count "
                f"{expected_native_charts}, got {native_chart_count}"
            )
        if expected_structured_charts is not None and structured_chart_count != expected_structured_charts:
            result.error(
                "slides[].structured_chart_count: expected source-report count "
                f"{expected_structured_charts}, got {structured_chart_count}"
            )
        if expected_rendered_charts is not None:
            expected_group_rate = round(chart_group_count / expected_rendered_charts, 4) if expected_rendered_charts > 0 else None
            expected_structured_rate = round(structured_chart_count / expected_rendered_charts, 4) if expected_rendered_charts > 0 else None
            if expected_group_rate is None:
                if chart_group_hit_rate is not None:
                    result.error("slides[].chart_group_hit_rate: expected null when expected_rendered_charts is 0")
            elif chart_group_hit_rate is None or round(float(chart_group_hit_rate), 4) != expected_group_rate:
                result.error(
                    "slides[].chart_group_hit_rate: expected "
                    f"{expected_group_rate}, got {chart_group_hit_rate}"
                )
            if expected_structured_rate is None:
                if structured_chart_hit_rate is not None:
                    result.error("slides[].structured_chart_hit_rate: expected null when expected_rendered_charts is 0")
            elif structured_chart_hit_rate is None or round(float(structured_chart_hit_rate), 4) != expected_structured_rate:
                result.error(
                    "slides[].structured_chart_hit_rate: expected "
                    f"{expected_structured_rate}, got {structured_chart_hit_rate}"
                )
        if bool(slide.get("has_notes")) != (notes_char_count > 0):
            result.error(
                "slides[].has_notes: expected notes_char_count to be > 0 when true and 0 when false"
            )

    chart_scope = managed_scope if managed_scope else slides
    chart_group_slides = sum(1 for slide in chart_scope if int(slide.get("chart_group_count") or 0) > 0)
    native_chart_slides = sum(1 for slide in chart_scope if int(slide.get("native_chart_count") or 0) > 0)
    chart_group_shapes_total = sum(int(slide.get("chart_group_count") or 0) for slide in chart_scope)
    native_chart_shapes_total = sum(int(slide.get("native_chart_count") or 0) for slide in chart_scope)
    structured_chart_shapes_total = sum(int(slide.get("structured_chart_count") or 0) for slide in chart_scope)
    expected_rendered_chart_regions_total = sum(int(slide.get("expected_rendered_charts") or 0) for slide in chart_scope)
    expected_chart_groups_total = sum(int(slide.get("expected_chart_groups") or 0) for slide in chart_scope)
    expected_native_charts_total = sum(int(slide.get("expected_native_charts") or 0) for slide in chart_scope)
    expected_structured_chart_shapes_total = sum(int(slide.get("expected_structured_charts") or 0) for slide in chart_scope)

    total_slides = parse_non_negative_int("summary.total_slides", summary_obj.get("total_slides"), result)
    expected_counts = {
        "total_shapes": total_shapes,
        "slides_with_notes": slides_with_notes,
        "notes_char_total": notes_char_total,
        "picture_only_slides": picture_only_slides,
        "full_slide_picture_slides": full_slide_picture_slides,
        "degraded_full_slide_picture_slides": degraded_slides,
        "table_slides": table_slides,
        "chart_slides": chart_slides,
        "managed_structured_chart_slides": len(chart_scope),
        "chart_group_slides": chart_group_slides,
        "native_chart_slides": native_chart_slides,
        "chart_group_shapes_total": chart_group_shapes_total,
        "native_chart_shapes_total": native_chart_shapes_total,
        "structured_chart_shapes_total": structured_chart_shapes_total,
        "expected_rendered_chart_regions_total": expected_rendered_chart_regions_total,
        "expected_chart_groups_total": expected_chart_groups_total,
        "expected_native_charts_total": expected_native_charts_total,
        "expected_structured_chart_shapes_total": expected_structured_chart_shapes_total,
    }
    for field_name, expected_value in expected_counts.items():
        actual = parse_non_negative_int(f"summary.{field_name}", summary_obj.get(field_name), result)
        if actual is not None and actual != expected_value:
            result.error(f"summary.{field_name}: expected {expected_value}, got {actual}")

    summary_chart_group_hit_rate = parse_optional_ratio("summary.chart_group_hit_rate", summary_obj.get("chart_group_hit_rate"), result)
    summary_structured_chart_hit_rate = parse_optional_ratio("summary.structured_chart_hit_rate", summary_obj.get("structured_chart_hit_rate"), result)

    expected_group_rate = round(chart_group_shapes_total / expected_rendered_chart_regions_total, 4) if expected_rendered_chart_regions_total > 0 else None
    expected_structured_rate = round(structured_chart_shapes_total / expected_rendered_chart_regions_total, 4) if expected_rendered_chart_regions_total > 0 else None
    if expected_group_rate is None:
        if summary_chart_group_hit_rate is not None:
            result.error("summary.chart_group_hit_rate: expected null when expected_rendered_chart_regions_total is 0")
    elif summary_chart_group_hit_rate is None or round(summary_chart_group_hit_rate, 4) != expected_group_rate:
        result.error(f"summary.chart_group_hit_rate: expected {expected_group_rate}, got {summary_chart_group_hit_rate}")
    if expected_structured_rate is None:
        if summary_structured_chart_hit_rate is not None:
            result.error("summary.structured_chart_hit_rate: expected null when expected_rendered_chart_regions_total is 0")
    elif summary_structured_chart_hit_rate is None or round(summary_structured_chart_hit_rate, 4) != expected_structured_rate:
        result.error(
            f"summary.structured_chart_hit_rate: expected {expected_structured_rate}, got {summary_structured_chart_hit_rate}"
        )
    if total_slides is not None and total_slides != len(slides):
        result.error(f"summary.total_slides: expected {len(slides)}, got {total_slides}")

    summary = {
        "total_slides": len(slides),
        "slides_with_notes": slides_with_notes,
        "notes_char_total": notes_char_total,
        "degraded_full_slide_picture_slides": degraded_slides,
        "table_slides": table_slides,
        "chart_slides": chart_slides,
        "chart_group_shapes_total": chart_group_shapes_total,
        "native_chart_shapes_total": native_chart_shapes_total,
        "structured_chart_shapes_total": structured_chart_shapes_total,
        "expected_rendered_chart_regions_total": expected_rendered_chart_regions_total,
        "chart_group_hit_rate": expected_group_rate,
        "structured_chart_hit_rate": expected_structured_rate,
        "errors": len(result.errors),
        "warnings": len(result.warnings),
    }
    if degraded_slides > 0:
        result.warn(
            "pptx-inspection: detected slides that degrade to a full-slide picture "
            f"({degraded_slides}/{len(slides)})"
        )
    if expected_rendered_chart_regions_total > 0 and structured_chart_shapes_total < expected_rendered_chart_regions_total:
        result.warn(
            "pptx-inspection: some rendered chart regions were not promoted into structured PPT objects "
            f"(structured={structured_chart_shapes_total}/{expected_rendered_chart_regions_total}, "
            f"chart_groups={chart_group_shapes_total}, native_charts={native_chart_shapes_total})"
        )
    summary["warnings"] = len(result.warnings)
    return result, summary


def validate_style(path: Path) -> tuple[ValidationResult, dict[str, Any]]:
    """Validate style.json contains required global style fields."""
    result = ValidationResult()
    try:
        payload = load_jsonish(path)
    except Exception as exc:
        result.error(f"style: failed to parse JSON: {exc}")
        return result, {"errors": 1, "warnings": 0}

    if not isinstance(payload, dict):
        result.error("style: root must be a JSON object")
        return result, {"errors": 1, "warnings": 0}

    style_id = payload.get("style_id")
    if not is_non_empty_string(style_id):
        result.error("style: missing non-empty 'style_id'")

    style_name = payload.get("style_name")
    if not is_non_empty_string(style_name):
        result.error("style: missing non-empty 'style_name'")

    mood_keywords = payload.get("mood_keywords")
    if not isinstance(mood_keywords, list):
        result.error("style: missing 'mood_keywords' list")
        mood_count = 0
    else:
        cleaned_keywords = [item.strip() for item in mood_keywords if is_non_empty_string(item)]
        mood_count = len(cleaned_keywords)
        if mood_count != len(mood_keywords):
            result.error("style: 'mood_keywords' must contain only non-empty strings")
        if mood_count < 3 or mood_count > 5:
            result.error("style: 'mood_keywords' must contain 3-5 items")

    design_soul = payload.get("design_soul") or payload.get("soul") or payload.get("mood") or payload.get("灵魂宣言")
    if not is_non_empty_string(design_soul):
        result.error("style: missing non-empty 'design_soul'")

    variation_strategy = payload.get("variation_strategy")
    if not is_non_empty_string(variation_strategy):
        result.error("style: missing non-empty 'variation_strategy'")

    decoration = payload.get("decoration_dna") or payload.get("decoration")
    if not isinstance(decoration, dict):
        result.error("style: missing object 'decoration_dna'")
    else:
        signature_move = decoration.get("signature_move")
        if not is_non_empty_string(signature_move):
            result.error("style: decoration_dna missing non-empty 'signature_move'")

        forbidden = decoration.get("forbidden")
        if not isinstance(forbidden, list):
            result.error("style: decoration_dna missing 'forbidden' list")
        else:
            cleaned_forbidden = [item.strip() for item in forbidden if is_non_empty_string(item)]
            if len(cleaned_forbidden) != len(forbidden):
                result.error("style: decoration_dna.forbidden must contain only non-empty strings")
            if len(cleaned_forbidden) < 2 or len(cleaned_forbidden) > 5:
                result.error("style: decoration_dna.forbidden must contain 2-5 items")

        combos = decoration.get("recommended_combos")
        if not isinstance(combos, list):
            result.error("style: decoration_dna missing 'recommended_combos' list")
        else:
            cleaned_combos = [item.strip() for item in combos if is_non_empty_string(item)]
            if len(cleaned_combos) != len(combos):
                result.error("style: decoration_dna.recommended_combos must contain only non-empty strings")
            if len(cleaned_combos) < 2 or len(cleaned_combos) > 4:
                result.error("style: decoration_dna.recommended_combos must contain 2-4 items")

    css_vars = payload.get("css_variables") or payload.get("css_vars")
    required_css_keys = [
        "bg_primary",
        "bg_secondary",
        "card_bg_from",
        "card_bg_to",
        "card_border",
        "card_radius",
        "text_primary",
        "text_secondary",
        "accent_1",
        "accent_2",
        "accent_3",
        "accent_4",
    ]
    if not isinstance(css_vars, dict):
        result.error("style: missing object 'css_variables'")
    else:
        for key in required_css_keys:
            if not is_non_empty_string(css_vars.get(key)):
                result.error(f"style: css_variables missing non-empty '{key}'")

    font_family = payload.get("font_family")
    legacy_font = payload.get("font") or payload.get("fonts") or payload.get("typography")
    if not is_non_empty_string(font_family):
        if legacy_font:
            result.warn("style: prefer 'font_family' over legacy font fields")
        else:
            result.error("style: missing non-empty 'font_family'")

    css_snippets = payload.get("css_snippets")
    if css_snippets is not None and not isinstance(css_snippets, dict):
        result.error("style: 'css_snippets' must be an object when provided")

    summary = {
        "style_id": style_id if is_non_empty_string(style_id) else None,
        "style_name": style_name if is_non_empty_string(style_name) else None,
        "mood_keywords": mood_count,
        "has_design_soul": bool(is_non_empty_string(design_soul)),
        "has_variation_strategy": bool(is_non_empty_string(variation_strategy)),
        "has_css_vars": bool(css_vars),
        "has_font_family": bool(is_non_empty_string(font_family)),
        "has_decoration": isinstance(decoration, dict),
        "has_css_snippets": isinstance(css_snippets, dict),
        "errors": len(result.errors),
        "warnings": len(result.warnings),
    }
    return result, summary


def _resolve_local_path_candidates(planning_path: Path, raw: str) -> list[Path]:
    source = raw.strip()
    candidate = Path(source)
    if candidate.is_absolute():
        return [candidate]

    planning_dir = planning_path if planning_path.is_dir() else planning_path.parent
    output_dir = planning_dir.parent
    return [
        (planning_dir / source).resolve(),
        (output_dir / source).resolve(),
    ]


def validate_images(path: Path, require_paths: bool) -> tuple[ValidationResult, dict[str, Any]]:
    """Validate image contracts from planning payload(s).

    - default mode: ensure image contract objects are structurally complete
    - --require-paths: for image.needed=true, require local source_hint path exists
    """
    result = ValidationResult()
    pages = load_planning_pages(path)
    if not pages:
        result.error("images: no planning pages found")
        return result, {"errors": 1, "warnings": 0}

    total_cards = 0
    needed_cards = 0
    hinted_cards = 0
    resolved_hints = 0

    for page in pages:
        slide_number = page.get("slide_number")
        page_label = f"slide {slide_number if slide_number is not None else '?'}"
        cards = page.get("cards") if isinstance(page.get("cards"), list) else []

        for index, card in enumerate(cards, start=1):
            if not isinstance(card, dict):
                continue
            total_cards += 1
            card_label = f"{page_label} card[{index}]"
            image = card.get("image")
            if not isinstance(image, dict):
                result.error(f"{card_label}: missing image contract")
                continue

            if not image.get("needed"):
                source_hint = image.get("source_hint")
                if source_hint not in (None, "", "null"):
                    result.warn(f"{card_label}: image.needed=false so image.source_hint should be null")
                continue

            needed_cards += 1
            for field_name in ("usage", "placement", "content_description", "source_hint"):
                if not is_non_empty_string(image.get(field_name)):
                    result.error(f"{card_label}: image.needed=true but image.{field_name} is empty")

            source_hint_raw = image.get("source_hint")
            if is_non_empty_string(source_hint_raw):
                hinted_cards += 1
            else:
                continue

            if not require_paths:
                continue

            source_hint = str(source_hint_raw).strip()
            lowered = source_hint.lower()
            if lowered.startswith(("http://", "https://", "data:")):
                result.error(f"{card_label}: image.source_hint must be a local file path when --require-paths")
                continue

            candidates = _resolve_local_path_candidates(path, source_hint)
            if any(item.exists() and item.is_file() for item in candidates):
                resolved_hints += 1
            else:
                result.error(f"{card_label}: image.source_hint path does not exist -> {source_hint}")

    summary = {
        "pages": len(pages),
        "cards": total_cards,
        "image_needed_cards": needed_cards,
        "cards_with_source_hint": hinted_cards,
        "resolved_source_hints": resolved_hints,
        "require_paths": require_paths,
        "errors": len(result.errors),
        "warnings": len(result.warnings),
    }
    return result, summary


def print_messages(result: ValidationResult) -> None:
    for item in result.errors:
        print(f"ERROR: {item}")
    for item in result.warnings:
        print(f"WARN:  {item}")


def write_report(path: str | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate v4 workflow contracts")
    subparsers = parser.add_subparsers(dest="command")

    text_contracts = {
        "interview": "Validate interview-qa.txt",
        "requirements-interview": "Validate requirements-interview.txt",
        "search": "Validate search.txt",
        "search-brief": "Validate search-brief.txt",
        "source-brief": "Validate source-brief.txt",
        "outline": "Validate outline.txt",
    }
    for name, help_text in text_contracts.items():
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("path", help="Path to the target text file")
        sub.add_argument("--strict", action="store_true", help="Treat warnings as failures")
        sub.add_argument("--report", help="Optional JSON report path")

    style_parser = subparsers.add_parser("style", help="Validate style.json")
    style_parser.add_argument("path", help="Path to style.json")
    style_parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    style_parser.add_argument("--report", help="Optional JSON report path")

    speech_parser = subparsers.add_parser("speech-script", help="Validate speech-script.json")
    speech_parser.add_argument("path", help="Path to speech-script.json")
    speech_parser.add_argument("--expected-pages", type=int, default=None, help="Expected number of page entries")
    speech_parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    speech_parser.add_argument("--report", help="Optional JSON report path")

    images = subparsers.add_parser("images", help="Validate image contracts in planning JSON")
    images.add_argument("path", help="Path to planning JSON file or directory")
    images.add_argument(
        "--require-paths",
        action="store_true",
        help="Require local source_hint file paths for cards with image.needed=true",
    )
    images.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    images.add_argument("--report", help="Optional JSON report path")

    review = subparsers.add_parser("page-review", help="Validate one review round result")
    review.add_argument("path", help="Path to review result (.txt or .json)")
    review.add_argument("--require-pass", action="store_true", help="Fail unless verdict=pass")
    review.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    review.add_argument("--report", help="Optional JSON report path")

    manifest = subparsers.add_parser("delivery-manifest", help="Validate delivery-manifest.json")
    manifest.add_argument("path", help="Path to delivery-manifest.json")
    manifest.add_argument("--base-dir", help="Base directory for resolving relative artifact paths")
    manifest.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    manifest.add_argument("--report", help="Optional JSON report path")

    svg_export = subparsers.add_parser("svg-export-report", help="Validate svg-export-report.json")
    svg_export.add_argument("path", help="Path to svg-export-report.json")
    svg_export.add_argument("--base-dir", help="Base directory for resolving relative artifact paths")
    svg_export.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    svg_export.add_argument("--report", help="Optional JSON report path")

    pptx_export = subparsers.add_parser("pptx-export-report", help="Validate presentation-svg.report.json")
    pptx_export.add_argument("path", help="Path to presentation-svg.report.json")
    pptx_export.add_argument("--base-dir", help="Base directory for resolving relative artifact paths")
    pptx_export.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    pptx_export.add_argument("--report", help="Optional JSON report path")

    pptx_inspection = subparsers.add_parser("pptx-inspection", help="Validate presentation-svg.inspect.json")
    pptx_inspection.add_argument("path", help="Path to presentation-svg.inspect.json")
    pptx_inspection.add_argument("--base-dir", help="Base directory for resolving relative artifact paths")
    pptx_inspection.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    pptx_inspection.add_argument("--report", help="Optional JSON report path")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    target = Path(args.path)
    if not target.exists():
        print(f"ERROR: path not found: {target}", file=sys.stderr)
        return 1

    try:
        if args.command == "interview":
            result, payload = validate_interview(target)
        elif args.command == "requirements-interview":
            result, payload = validate_requirements_interview(target)
        elif args.command == "search":
            result, payload = validate_search(target)
        elif args.command == "search-brief":
            result, payload = validate_search_brief(target)
        elif args.command == "source-brief":
            result, payload = validate_source_brief(target)
        elif args.command == "outline":
            result, payload = validate_outline(target)
        elif args.command == "style":
            result, payload = validate_style(target)
        elif args.command == "speech-script":
            result, payload = validate_speech_script(target, args.expected_pages)
        elif args.command == "images":
            result, payload = validate_images(target, bool(args.require_paths))
        elif args.command == "page-review":
            result, payload = validate_page_review(target, bool(args.require_pass))
        elif args.command == "svg-export-report":
            base_dir = Path(args.base_dir).resolve() if args.base_dir else target.parent.resolve()
            result, payload = validate_svg_export_report(target, base_dir)
        elif args.command == "pptx-export-report":
            base_dir = Path(args.base_dir).resolve() if args.base_dir else target.parent.resolve()
            result, payload = validate_pptx_export_report(target, base_dir)
        elif args.command == "pptx-inspection":
            base_dir = Path(args.base_dir).resolve() if args.base_dir else target.parent.resolve()
            result, payload = validate_pptx_inspection(target, base_dir)
        else:
            base_dir = Path(args.base_dir).resolve() if args.base_dir else target.parent.resolve()
            result, payload = validate_delivery_manifest(target, base_dir)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print_messages(result)
    if not result.errors and not result.warnings:
        print("OK")

    ok = result.ok and (not args.strict or not result.warnings)
    write_report(
        args.report,
        {
            "command": args.command,
            "ok": ok,
            "summary": payload,
            "errors": result.errors,
            "warnings": result.warnings,
        },
    )

    if result.errors:
        return 1
    if args.strict and result.warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
