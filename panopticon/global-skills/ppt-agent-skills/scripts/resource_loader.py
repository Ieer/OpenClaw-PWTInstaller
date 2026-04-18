#!/usr/bin/env python3
"""Resource router -- dynamic resource loading for PPT workflow.

Three modes:
  menu    -- Extract # title + > blockquote from all resources (for planning)
  resolve -- Load full body of resources referenced in planning JSON (for HTML)
  images  -- Enumerate available local image assets (for planning/html correction)

Usage:
  # Planning stage: get resource menu
  python3 resource_loader.py menu --refs-dir references

  # HTML stage: load only needed resources based on planning JSON
  python3 resource_loader.py resolve --refs-dir references --planning planning3.json

  # Planning/HTML stage: list all local image assets
  python3 resource_loader.py images --images-dir OUTPUT_DIR/images
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


# ── Field-to-directory routing table ────────────────────────────────────────
# Planning JSON field -> resource directory -> match logic
FIELD_ROUTES = {
    # Page-level fields
    "layout_hint": "layouts",
    "page_type": "page-templates",
    # Card-level fields
    "card_type": "blocks",
    "chart_type": "charts",
}

# Always-include resources when certain conditions are met
ALWAYS_INCLUDE = {
    "blocks/card-styles.md": lambda pages: any(
        card.get("card_style")
        for page in pages
        for card in _as_list(page.get("cards"))
        if isinstance(card, dict)
    ),
    # Data type mapping tables -- always include for planning context
    "design-runtime/data-type-visual-mapping.md": lambda pages: True,
    "design-runtime/data-type-decoration-mapping.md": lambda pages: True,
    # Canvas specs (1280x720 hard constraint) -- MUST always inject
    "design-runtime/design-specs.md": lambda pages: True,
    # CSS advanced techniques (W1-W12) -- always inject so HTML subagent can use without planning preselection
    "design-runtime/css-weapons.md": lambda pages: True,
    # Director command rules -- always inject so HTML subagent understands director_command field conventions
    "design-runtime/director-command-rules.md": lambda pages: True,
}

# Explicit ref fields in planning JSON resources section
REF_FIELD_ROUTES = {
    "layout_refs": "layouts",
    "block_refs": "blocks",
    "chart_refs": "charts",
    "principle_refs": "principles",
}

# Categories to scan for menu
MENU_CATEGORIES = [
    "layouts",
    "blocks",
    "charts",
    "styles",
    "principles",
    "page-templates",
    "design-runtime",
]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}


def _as_list(val: Any) -> list:
    return val if isinstance(val, list) else []


def _natural_text_key(value: str) -> tuple[Any, ...]:
    parts = re.split(r"(\d+)", value)
    key: list[Any] = []
    for part in parts:
        key.append(int(part) if part.isdigit() else part.lower())
    return tuple(key)


def _parse_svg_length(raw: str | None) -> float | None:
    if raw is None:
        return None
    match = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)", str(raw))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _svg_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return None

    width = _parse_svg_length(root.attrib.get("width"))
    height = _parse_svg_length(root.attrib.get("height"))
    if width and height:
        return int(round(width)), int(round(height))

    view_box = root.attrib.get("viewBox")
    if view_box:
        parts = [part for part in re.split(r"[\s,]+", view_box.strip()) if part]
        if len(parts) == 4:
            try:
                return int(round(float(parts[2]))), int(round(float(parts[3])))
            except ValueError:
                return None
    return None


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
    except OSError:
        return None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", header[16:24])


def _gif_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(10)
    except OSError:
        return None
    if len(header) < 10 or header[:3] != b"GIF":
        return None
    return struct.unpack("<HH", header[6:10])


def _jpeg_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            if handle.read(2) != b"\xff\xd8":
                return None
            while True:
                marker_prefix = handle.read(1)
                if not marker_prefix:
                    return None
                if marker_prefix != b"\xff":
                    continue
                marker = handle.read(1)
                while marker == b"\xff":
                    marker = handle.read(1)
                if not marker or marker in {b"\xd8", b"\xd9"}:
                    continue
                size_bytes = handle.read(2)
                if len(size_bytes) != 2:
                    return None
                block_size = struct.unpack(">H", size_bytes)[0]
                if marker in {
                    b"\xc0", b"\xc1", b"\xc2", b"\xc3",
                    b"\xc5", b"\xc6", b"\xc7",
                    b"\xc9", b"\xca", b"\xcb",
                    b"\xcd", b"\xce", b"\xcf",
                }:
                    block = handle.read(block_size - 2)
                    if len(block) < 5:
                        return None
                    height, width = struct.unpack(">HH", block[1:5])
                    return width, height
                handle.seek(block_size - 2, 1)
    except OSError:
        return None


def _webp_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(40)
    except OSError:
        return None
    if len(header) < 16 or header[:4] != b"RIFF" or header[8:12] != b"WEBP":
        return None

    chunk = header[12:16]
    if chunk == b"VP8X" and len(header) >= 30:
        width = 1 + int.from_bytes(header[24:27], "little")
        height = 1 + int.from_bytes(header[27:30], "little")
        return width, height
    if chunk == b"VP8L" and len(header) >= 25:
        bits = int.from_bytes(header[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    if chunk == b"VP8 " and len(header) >= 30:
        width = int.from_bytes(header[26:28], "little")
        height = int.from_bytes(header[28:30], "little")
        return width, height
    return None


def inspect_image(path: Path) -> dict[str, Any]:
    ext = path.suffix.lower()
    dimensions: tuple[int, int] | None = None

    if ext == ".svg":
        dimensions = _svg_dimensions(path)
    elif ext == ".png":
        dimensions = _png_dimensions(path)
    elif ext == ".gif":
        dimensions = _gif_dimensions(path)
    elif ext in {".jpg", ".jpeg"}:
        dimensions = _jpeg_dimensions(path)
    elif ext == ".webp":
        dimensions = _webp_dimensions(path)

    width = height = None
    aspect_ratio = None
    orientation = "unknown"
    if dimensions and dimensions[0] > 0 and dimensions[1] > 0:
        width, height = dimensions
        aspect_ratio = width / height
        if 0.9 <= aspect_ratio <= 1.1:
            orientation = "square"
        elif aspect_ratio > 1.1:
            orientation = "landscape"
        else:
            orientation = "portrait"

    return {
        "format": ext.lstrip("."),
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio,
        "orientation": orientation,
    }


# ── Menu mode: extract titles + blockquotes ─────────────────────────────────

def extract_menu_entry(filepath: Path) -> dict[str, str] | None:
    """Extract # title and all consecutive > blockquote lines from a resource file."""
    try:
        text = filepath.read_text(encoding="utf-8")
    except Exception:
        return None

    lines = text.split("\n")
    title = ""
    quote_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not title and stripped.startswith("# "):
            title = stripped[2:].strip()
        elif title and stripped.startswith("> "):
            quote_lines.append(stripped[2:].strip())
        elif title and stripped == ">":
            # Empty blockquote continuation line
            quote_lines.append("")
        elif title and quote_lines:
            # First non-quote line after quote block = done
            break
        elif title and stripped and not stripped.startswith(">"):
            # Non-empty non-quote line after title means no blockquote
            break

    if not title:
        return None

    return {
        "file": filepath.name,
        "id": filepath.stem,
        "title": title,
        "quote": "\n".join(quote_lines).strip(),
    }


def generate_menu(refs_dir: Path, categories: list[str] | None = None) -> str:
    """Generate resource menu with titles + full blockquotes organized by category."""
    cats = categories or MENU_CATEGORIES
    sections: list[str] = []

    for cat in cats:
        cat_dir = refs_dir / cat
        if not cat_dir.is_dir():
            continue

        entries: list[dict[str, str]] = []
        for md_file in sorted(cat_dir.glob("*.md")):
            if md_file.name.lower() == "readme.md":
                continue
            # Skip runtime-only files
            if md_file.name.startswith("runtime-"):
                continue
            entry = extract_menu_entry(md_file)
            if entry:
                entries.append(entry)

        if entries:
            cat_lines = [f"### {cat}/"]
            for e in entries:
                cat_lines.append(f"\n#### {e['id']}")
                cat_lines.append(f"**{e['title']}**")
                if e["quote"]:
                    # Indent multi-line quotes for readability
                    for q_line in e["quote"].split("\n"):
                        cat_lines.append(f"> {q_line}" if q_line else ">")
            sections.append("\n".join(cat_lines))

    return "\n\n".join(sections)


# ── Resolve mode: load resource bodies based on planning JSON ───────────────

def extract_body(filepath: Path) -> str:
    """Extract body content (everything after the > blockquote line)."""
    try:
        text = filepath.read_text(encoding="utf-8")
    except Exception:
        return ""

    lines = text.split("\n")
    body_start = 0
    found_title = False
    found_quote = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not found_title and stripped.startswith("# "):
            found_title = True
            continue
        if found_title and stripped.startswith("> "):
            found_quote = True
            continue
        if found_title and (found_quote or (stripped and not stripped.startswith(">"))):
            body_start = i
            break

    # Skip leading blank lines
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1

    body = "\n".join(lines[body_start:]).strip()
    return body


def normalize_ref(value: str) -> str:
    """Normalize a resource reference to a filename stem."""
    raw = value.strip().strip("`").strip()
    # Remove path prefixes
    if "/" in raw:
        raw = raw.rsplit("/", 1)[-1]
    # Remove .md extension
    if raw.endswith(".md"):
        raw = raw[:-3]
    # Normalize underscores to hyphens
    return raw.replace("_", "-")


def collect_resource_refs(pages: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Collect all resource references from planning pages, grouped by directory."""
    refs: dict[str, set[str]] = {d: set() for d in set(FIELD_ROUTES.values()) | set(REF_FIELD_ROUTES.values())}

    for page in pages:
        # Page-level fields
        for field, directory in FIELD_ROUTES.items():
            if field == "chart_type":
                continue  # handled at card level
            val = page.get(field)
            if isinstance(val, str) and val.strip():
                refs[directory].add(normalize_ref(val))

        # Card-level fields
        for card in _as_list(page.get("cards")):
            if not isinstance(card, dict):
                continue

            # card_type -> blocks/
            card_type = card.get("card_type")
            if isinstance(card_type, str) and card_type.strip():
                refs["blocks"].add(normalize_ref(card_type))

            # chart.chart_type -> charts/
            chart = card.get("chart")
            if isinstance(chart, dict):
                chart_type = chart.get("chart_type")
                if isinstance(chart_type, str) and chart_type.strip():
                    refs["charts"].add(normalize_ref(chart_type))

            # Card-level resource_ref
            resource_ref = card.get("resource_ref")
            if isinstance(resource_ref, dict):
                for key, directory in [("block", "blocks"), ("chart", "charts"), ("principle", "principles")]:
                    val = resource_ref.get(key)
                    if isinstance(val, str) and val.strip():
                        refs[directory].add(normalize_ref(val))

        # Explicit resources section
        resources = page.get("resources")
        if isinstance(resources, dict):
            # page_template
            pt = resources.get("page_template")
            if isinstance(pt, str) and pt.strip():
                refs["page-templates"].add(normalize_ref(pt))

            # Ref lists
            for field, directory in REF_FIELD_ROUTES.items():
                for item in _as_list(resources.get(field)):
                    if isinstance(item, str) and item.strip():
                        refs[directory].add(normalize_ref(item))

    return refs


def load_planning_pages(path: Path) -> list[dict[str, Any]]:
    """Load planning pages from a JSON file or directory."""
    text = path.read_text(encoding="utf-8").strip()

    # Try direct JSON parse
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        # Try extracting from fenced block
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
        if match:
            payload = json.loads(match.group(1))
        else:
            first, last = text.find("{"), text.rfind("}")
            if first != -1 and last > first:
                payload = json.loads(text[first:last + 1])
            else:
                raise ValueError(f"Cannot parse planning JSON: {path}")

    if isinstance(payload, dict) and "ppt_planning" in payload:
        return _as_list(payload["ppt_planning"].get("pages"))
    if isinstance(payload, dict):
        page = payload.get("page", payload)
        if isinstance(page, dict) and ("slide_number" in page or "page_number" in page):
            return [page]
    return []


def resolve_resources(refs_dir: Path, planning_path: Path) -> str:
    """Load full resource bodies based on planning JSON field references."""
    pages = load_planning_pages(planning_path)
    if not pages:
        print("WARN: no planning pages found", file=sys.stderr)
        return ""

    resource_refs = collect_resource_refs(pages)
    sections: list[str] = []
    loaded_files: set[str] = set()

    for directory, ref_ids in sorted(resource_refs.items()):
        dir_path = refs_dir / directory
        if not dir_path.is_dir():
            continue

        for ref_id in sorted(ref_ids):
            # Try multiple filename patterns
            candidates = [
                dir_path / f"{ref_id}.md",
                dir_path / f"{ref_id.replace('-', '_')}.md",
            ]
            for candidate in candidates:
                if candidate.exists() and str(candidate) not in loaded_files:
                    loaded_files.add(str(candidate))
                    title_line = ""
                    for line in candidate.read_text(encoding="utf-8").split("\n"):
                        if line.strip().startswith("# "):
                            title_line = line.strip()
                            break
                    body = extract_body(candidate)
                    if body:
                        sections.append(f"{title_line}\n\n{body}")
                    break

    # Always-include resources
    for rel_path, condition in ALWAYS_INCLUDE.items():
        full_path = refs_dir / rel_path
        if full_path.exists() and str(full_path) not in loaded_files and condition(pages):
            loaded_files.add(str(full_path))
            title_line = ""
            for line in full_path.read_text(encoding="utf-8").split("\n"):
                if line.strip().startswith("# "):
                    title_line = line.strip()
                    break
            body = extract_body(full_path)
            if body:
                sections.append(f"{title_line}\n\n{body}")

    return "\n\n---\n\n".join(sections)


def generate_image_inventory(images_dir: Path) -> str:
    """Generate deterministic local image inventory for subagent correction loops."""
    image_files: list[Path] = []
    if images_dir.is_dir():
        image_files = [
            path for path in images_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ]
        image_files.sort(key=lambda p: _natural_text_key(str(p.relative_to(images_dir)).replace("\\", "/")))

    lines: list[str] = [
        "# Image Asset Inventory",
        "",
        f"images_dir: {images_dir.resolve()}",
        f"exists: {images_dir.is_dir()}",
        f"count: {len(image_files)}",
        "",
        "## Assets",
    ]
    if not image_files:
        lines.append("(empty)")
        lines.append("")
        lines.append("当前没有可直接绑定的本地图片。")
        lines.append("如果本页走 AI 文生图，可先在 planning 中规划未来落盘路径，再在图片阶段生成。")
        lines.append("如果本页走 manual_slot / decorate，可继续后续 HTML，不必等待图片文件。")
        return "\n".join(lines)

    for idx, file_path in enumerate(image_files, start=1):
        rel = file_path.relative_to(images_dir).as_posix()
        abs_path = file_path.resolve().as_posix()
        metadata = inspect_image(file_path)
        lines.append(f"{idx}. rel={rel}")
        lines.append(f"   abs={abs_path}")
        lines.append(f"   format={metadata['format']}")
        if metadata["width"] and metadata["height"]:
            lines.append(f"   dimensions={metadata['width']}x{metadata['height']}")
            lines.append(f"   aspect_ratio={metadata['aspect_ratio']:.3f}")
            lines.append(f"   orientation={metadata['orientation']}")
        else:
            lines.append("   dimensions=unknown")
            lines.append("   aspect_ratio=unknown")
            lines.append("   orientation=unknown")

    lines.append("")
    lines.append("约束：当 planning 选择 provided 模式时，image.source_hint 必须引用上面清单中的本地路径。")
    lines.append("建议：横图优先用于 full-bleed / hero / side-hero，竖图优先用于侧栏人物图或 inset，方图优先用于卡片内嵌。")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Dynamic resource loader for PPT workflow")
    subparsers = parser.add_subparsers(dest="mode")

    # Menu mode
    menu_parser = subparsers.add_parser("menu", help="Generate resource menu (titles + blockquotes)")
    menu_parser.add_argument("--refs-dir", required=True, help="Path to references directory")
    menu_parser.add_argument("--categories", help="Comma-separated list of categories (default: all)")
    menu_parser.add_argument("--output", help="Output file path (default: stdout)")

    # Resolve mode
    resolve_parser = subparsers.add_parser("resolve", help="Load resource bodies based on planning JSON")
    resolve_parser.add_argument("--refs-dir", required=True, help="Path to references directory")
    resolve_parser.add_argument("--planning", required=True, help="Path to planning JSON file")
    resolve_parser.add_argument("--output", help="Output file path (default: stdout)")

    # Images mode
    images_parser = subparsers.add_parser("images", help="Generate local image inventory for planning/html stages")
    images_parser.add_argument("--images-dir", required=True, help="Path to local images directory")
    images_parser.add_argument("--output", help="Output file path (default: stdout)")

    args = parser.parse_args()
    if not args.mode:
        parser.print_help()
        return 1

    if args.mode == "menu":
        refs_dir = Path(args.refs_dir)
        if not refs_dir.is_dir():
            print(f"ERROR: refs-dir not found: {refs_dir}", file=sys.stderr)
            return 1
        cats = args.categories.split(",") if args.categories else None
        result = generate_menu(refs_dir, cats)

    elif args.mode == "resolve":
        refs_dir = Path(args.refs_dir)
        planning_path = Path(args.planning)
        if not refs_dir.is_dir():
            print(f"ERROR: refs-dir not found: {refs_dir}", file=sys.stderr)
            return 1
        if not planning_path.exists():
            print(f"ERROR: planning file not found: {planning_path}", file=sys.stderr)
            return 1
        result = resolve_resources(refs_dir, planning_path)
    elif args.mode == "images":
        images_dir = Path(args.images_dir)
        result = generate_image_inventory(images_dir)
    else:
        parser.print_help()
        return 1

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result, encoding="utf-8")
        print(f"Written to {out} ({len(result)} chars)", file=sys.stderr)
    else:
        print(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
