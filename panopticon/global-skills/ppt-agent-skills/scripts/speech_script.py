#!/usr/bin/env python3
"""Helpers for speech-script artifacts and PPTX speaker notes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from planning_validator import load_jsonish


NOTES_PLACEHOLDER_IDX = 3
SLIDE_IMAGE_PLACEHOLDER_IDX = 2
SLIDE_NUMBER_PLACEHOLDER_IDX = 5


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_speech_script_payload(path: str | Path) -> dict[str, Any]:
    speech_path = Path(path)
    payload = load_jsonish(speech_path)
    if not isinstance(payload, dict):
        raise ValueError("speech-script must be a JSON object")
    return payload


def load_speech_page_entries(path: str | Path, expected_pages: int | None = None) -> list[dict[str, Any]]:
    payload = load_speech_script_payload(path)
    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("speech-script.pages must be a non-empty list")

    normalized_pages: list[dict[str, Any]] = []
    page_numbers: set[int] = set()
    for entry in pages:
        if not isinstance(entry, dict):
            raise ValueError("speech-script.pages[] must be an object")
        page_number = entry.get("page")
        if not isinstance(page_number, int) or page_number <= 0:
            raise ValueError("speech-script.pages[].page must be a positive integer")
        if page_number in page_numbers:
            raise ValueError(f"speech-script duplicate page number: {page_number}")
        slide_title = normalize_text(entry.get("slide_title"))
        if not slide_title:
            raise ValueError(f"speech-script page {page_number}: slide_title must be non-empty")
        speaker_notes = normalize_text(entry.get("speaker_notes"))
        if not speaker_notes:
            raise ValueError(f"speech-script page {page_number}: speaker_notes must be non-empty")
        normalized = dict(entry)
        normalized["page"] = page_number
        normalized["slide_title"] = slide_title
        normalized["speaker_notes"] = speaker_notes
        normalized_pages.append(normalized)
        page_numbers.add(page_number)

    normalized_pages.sort(key=lambda item: int(item["page"]))
    ordered_numbers = [int(item["page"]) for item in normalized_pages]
    expected_sequence = list(range(1, len(normalized_pages) + 1))
    if ordered_numbers != expected_sequence:
        raise ValueError(
            "speech-script page numbers must be contiguous starting at 1: "
            f"expected {expected_sequence}, got {ordered_numbers}"
        )
    if expected_pages is not None and len(normalized_pages) != expected_pages:
        raise ValueError(
            f"speech-script page count mismatch: expected {expected_pages}, got {len(normalized_pages)}"
        )
    return normalized_pages


def render_speech_markdown(payload: dict[str, Any]) -> str:
    pages = load_speech_page_entries_from_payload(payload)
    deck_title = normalize_text(payload.get("deck_title")) or "Speech Script"
    language = normalize_text(payload.get("language"))
    summary = normalize_text(payload.get("summary"))
    total_estimated_seconds = sum(
        int(page.get("estimated_seconds"))
        for page in pages
        if isinstance(page.get("estimated_seconds"), int) and int(page.get("estimated_seconds")) > 0
    )

    lines: list[str] = [f"# 演讲稿：{deck_title}", ""]
    if language:
        lines.append(f"- language: {language}")
    lines.append(f"- total_pages: {len(pages)}")
    if total_estimated_seconds > 0:
        lines.append(f"- estimated_total_seconds: {total_estimated_seconds}")
    if summary:
        lines.extend(["", summary])

    for page in pages:
        lines.extend(["", f"## 第 {page['page']} 页 · {page['slide_title']}"])
        if isinstance(page.get("estimated_seconds"), int) and int(page.get("estimated_seconds")) > 0:
            lines.append(f"预计时长：{int(page['estimated_seconds'])} 秒")
        transition = normalize_text(page.get("transition_to_next"))
        if transition:
            lines.append(f"转场衔接：{transition}")
        lines.extend(["", page["speaker_notes"]])

    return "\n".join(lines).strip() + "\n"


def load_speech_page_entries_from_payload(payload: dict[str, Any], expected_pages: int | None = None) -> list[dict[str, Any]]:
    temp_path = Path("speech-script.json")
    if not isinstance(payload, dict):
        raise ValueError("speech-script must be a JSON object")
    pages = payload.get("pages")
    if not isinstance(pages, list):
        raise ValueError("speech-script.pages must be a list")
    normalized_pages: list[dict[str, Any]] = []
    page_numbers: set[int] = set()
    for entry in pages:
        if not isinstance(entry, dict):
            raise ValueError(f"{temp_path}: speech-script.pages[] must be an object")
        page_number = entry.get("page")
        if not isinstance(page_number, int) or page_number <= 0:
            raise ValueError(f"{temp_path}: speech-script.pages[].page must be a positive integer")
        if page_number in page_numbers:
            raise ValueError(f"{temp_path}: speech-script duplicate page number: {page_number}")
        slide_title = normalize_text(entry.get("slide_title"))
        if not slide_title:
            raise ValueError(f"{temp_path}: speech-script page {page_number}: slide_title must be non-empty")
        speaker_notes = normalize_text(entry.get("speaker_notes"))
        if not speaker_notes:
            raise ValueError(f"{temp_path}: speech-script page {page_number}: speaker_notes must be non-empty")
        normalized = dict(entry)
        normalized["page"] = page_number
        normalized["slide_title"] = slide_title
        normalized["speaker_notes"] = speaker_notes
        normalized_pages.append(normalized)
        page_numbers.add(page_number)
    normalized_pages.sort(key=lambda item: int(item["page"]))
    ordered_numbers = [int(item["page"]) for item in normalized_pages]
    expected_sequence = list(range(1, len(normalized_pages) + 1))
    if ordered_numbers != expected_sequence:
        raise ValueError(
            "speech-script page numbers must be contiguous starting at 1: "
            f"expected {expected_sequence}, got {ordered_numbers}"
        )
    if expected_pages is not None and len(normalized_pages) != expected_pages:
        raise ValueError(
            f"speech-script page count mismatch: expected {expected_pages}, got {len(normalized_pages)}"
        )
    return normalized_pages


def _placeholder_idx(shape: Any) -> int | None:
    try:
        return int(shape.placeholder_format.idx)
    except Exception:
        return None


def _resolve_notes_shape(slide) -> Any | None:
    notes_slide = slide.notes_slide
    for shape in notes_slide.placeholders:
        if _placeholder_idx(shape) == NOTES_PLACEHOLDER_IDX and getattr(shape, "has_text_frame", False):
            return shape
    for shape in notes_slide.shapes:
        idx = _placeholder_idx(shape)
        if idx in (SLIDE_IMAGE_PLACEHOLDER_IDX, SLIDE_NUMBER_PLACEHOLDER_IDX):
            continue
        if getattr(shape, "has_text_frame", False):
            return shape
    return None


def write_slide_speaker_notes(slide, notes_text: Any) -> None:
    normalized = normalize_text(notes_text)
    shape = _resolve_notes_shape(slide)
    if shape is None:
        raise ValueError("notes slide is missing a writable notes placeholder")
    shape.text = normalized


def extract_slide_speaker_notes(slide) -> str:
    shape = _resolve_notes_shape(slide)
    if shape is None or not getattr(shape, "has_text_frame", False):
        return ""
    return normalize_text(shape.text_frame.text)