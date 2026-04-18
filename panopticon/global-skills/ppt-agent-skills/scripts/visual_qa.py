#!/usr/bin/env python3
"""visual_qa.py — 自动化视觉质量断言脚本

在 subagent review 完成后，由主 agent 运行此脚本对 slide PNG 做客观检测。
检测项全部基于像素分析，不依赖 LLM 判断。

用法：
    # 检查单页
    python3 scripts/visual_qa.py OUTPUT_DIR/png/slide-1.png --planning OUTPUT_DIR/planning/planning1.json

    # 批量检查所有页
    python3 scripts/visual_qa.py OUTPUT_DIR/png --planning-dir OUTPUT_DIR/planning

退出码：
    0 = 全部通过
    1 = 存在 FAIL（致命缺陷，建议重跑该页）
    2 = 只有 WARN（品质警告，可交付但建议人工复查）
"""

import json
import os
import re
import statistics
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

# PIL 是唯一外部依赖；如缺失则给出友好提示
try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is required. Install with: pip install Pillow", file=sys.stderr)
    sys.exit(1)


class ImgTagParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        attr_map = {key: (value or "") for key, value in attrs}
        attr_map["_line"] = str(self.getpos()[0])
        self.images.append(attr_map)


def load_planning_page(planning_path: Path | None) -> dict | None:
    if not planning_path or not planning_path.exists():
        return None
    try:
        with open(planning_path, encoding="utf-8") as f:
            planning = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return planning.get("page", planning)


def infer_html_path(png_path: Path, planning_path: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    candidates.append(png_path.with_suffix(".html"))
    if png_path.parent.name == "png":
        candidates.append(png_path.parent.parent / "slides" / f"{png_path.stem}.html")
    if planning_path and planning_path.parent.name == "planning":
        slide_match = re.search(r"(\d+)", planning_path.stem)
        if slide_match:
            candidates.append(planning_path.parent.parent / "slides" / f"slide-{slide_match.group(1)}.html")
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            return resolved
    return None


def resolve_asset_path(raw: str, base_dir: Path) -> Path | None:
    value = raw.strip().strip('"\'')
    if not value or value.startswith(("data:", "http://", "https://", "#", "var(")):
        return None
    if value.startswith("file://"):
        value = value[7:]
    path = Path(value)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def parse_html_assets(html_path: Path | None) -> dict | None:
    if html_path is None or not html_path.exists():
        return None
    try:
        text = html_path.read_text(encoding="utf-8")
    except OSError:
        return None

    parser = ImgTagParser()
    parser.feed(text)

    img_assets = []
    for item in parser.images:
        src = item.get("src", "")
        asset_path = resolve_asset_path(src, html_path.parent)
        if asset_path is None:
            continue
        img_assets.append(
            {
                "src": src,
                "path": asset_path,
                "style": item.get("style", ""),
                "class": item.get("class", ""),
                "width": item.get("width", ""),
                "height": item.get("height", ""),
                "line": item.get("_line", "?"),
            }
        )

    background_assets = []
    for raw in re.findall(r"url\(([^)]+)\)", text, flags=re.IGNORECASE):
        asset_path = resolve_asset_path(raw, html_path.parent)
        if asset_path is not None:
            background_assets.append(asset_path)

    return {
        "text": text,
        "images": img_assets,
        "background_assets": background_assets,
    }


def get_expected_image_cards(planning_page: dict | None) -> list[dict]:
    if not planning_page:
        return []
    expected = []
    for card in planning_page.get("cards", []):
        image = card.get("image") or {}
        if image.get("mode") in {"provided", "generate"} and image.get("needed"):
            expected.append(card)
    return expected


def estimate_background_color(img: Image.Image) -> tuple[int, int, int]:
    w, h = img.size
    samples = []
    anchors = [(0, 0), (max(w - 6, 0), 0), (0, max(h - 6, 0)), (max(w - 6, 0), max(h - 6, 0))]
    for start_x, start_y in anchors:
        for x in range(start_x, min(start_x + 6, w)):
            for y in range(start_y, min(start_y + 6, h)):
                samples.append(img.getpixel((x, y))[:3])
    if not samples:
        return (0, 0, 0)
    return tuple(int(sum(channel) / len(samples)) for channel in zip(*samples))


def color_distance(rgb: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    return ((rgb[0] - bg[0]) ** 2 + (rgb[1] - bg[1]) ** 2 + (rgb[2] - bg[2]) ** 2) ** 0.5


def content_ratio_for_box(img: Image.Image, box: tuple[int, int, int, int], bg: tuple[int, int, int]) -> float:
    region = img.crop(box)
    pixels = list(region.getdata())
    if not pixels:
        return 0.0
    content_pixels = sum(1 for pixel in pixels if color_distance(pixel[:3], bg) > 28)
    return content_pixels / len(pixels)


def block_metrics(img: Image.Image, box: tuple[int, int, int, int]) -> dict[str, float]:
    region = img.crop(box).convert("L")
    values = list(region.getdata())
    if not values:
        return {
            "edge_h": 0.0,
            "edge_v": 0.0,
            "stddev": 0.0,
            "luma_range": 0.0,
            "bright_ratio": 0.0,
            "dark_ratio": 0.0,
        }

    pixels = region.load()
    width, height = region.size
    edge_h = 0
    edge_v = 0
    total_h = 0
    total_v = 0
    for y in range(height):
        for x in range(1, width):
            total_h += 1
            if abs(pixels[x, y] - pixels[x - 1, y]) > 12:
                edge_h += 1
    for y in range(1, height):
        for x in range(width):
            total_v += 1
            if abs(pixels[x, y] - pixels[x, y - 1]) > 12:
                edge_v += 1

    return {
        "edge_h": edge_h / total_h if total_h else 0.0,
        "edge_v": edge_v / total_v if total_v else 0.0,
        "stddev": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "luma_range": float(max(values) - min(values)),
        "bright_ratio": sum(1 for value in values if value > 180) / len(values),
        "dark_ratio": sum(1 for value in values if value < 70) / len(values),
    }


def clamp_box(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int] | None:
    x1, y1, x2, y2 = box
    x1 = max(0, min(width, int(x1)))
    y1 = max(0, min(height, int(y1)))
    x2 = max(0, min(width, int(x2)))
    y2 = max(0, min(height, int(y2)))
    if x2 - x1 < 24 or y2 - y1 < 16:
        return None
    return (x1, y1, x2, y2)


def get_image_scan_zones(planning_page: dict | None, width: int, height: int) -> list[tuple[str, tuple[int, int, int, int]]]:
    if not planning_page:
        return []

    zones: list[tuple[str, tuple[int, int, int, int]]] = []
    seen: set[tuple[int, int, int, int]] = set()
    for card in planning_page.get("cards", []):
        image = card.get("image") or {}
        if image.get("mode") not in {"provided", "generate"} or not image.get("needed"):
            continue

        placement = image.get("placement") or "inline"
        if placement == "right-half":
            raw_zone = (width * 0.52, height * 0.16, width * 0.94, height * 0.78)
        elif placement == "left-half":
            raw_zone = (width * 0.06, height * 0.16, width * 0.48, height * 0.78)
        elif placement == "full-bleed":
            raw_zone = (width * 0.04, height * 0.12, width * 0.96, height * 0.84)
        elif placement == "card-bg":
            raw_zone = (width * 0.14, height * 0.20, width * 0.86, height * 0.74)
        else:
            raw_zone = (width * 0.18, height * 0.20, width * 0.82, height * 0.76)

        zone = clamp_box(raw_zone, width, height)
        if zone and zone not in seen:
            zones.append((placement, zone))
            seen.add(zone)
    return zones


def footer_band_box(planning_page: dict | None, width: int, height: int) -> tuple[int, int, int, int] | None:
    if not planning_page:
        return None
    if planning_page.get("page_type") not in {"content", "toc", "section"}:
        return None
    return clamp_box((40, height - 44, width - 40, height - 8), width, height)


def header_band_box(planning_page: dict | None, width: int, height: int) -> tuple[int, int, int, int] | None:
    if not planning_page:
        return None
    if planning_page.get("page_type") not in {"content", "toc"}:
        return None
    return clamp_box((40, 20, width - 40, 78), width, height)


def has_footer_html_contract(html_assets: dict | None) -> tuple[bool, bool, bool]:
    if not html_assets:
        return False, False, False
    text = html_assets["text"]
    has_root = bool(re.search(r"<footer[^>]*class=([\"'])[^\"']*slide-footer[^\"']*\1", text, re.I))
    has_section = bool(re.search(r"class=([\"'])[^\"']*footer-section[^\"']*\1", text, re.I))
    has_page = bool(re.search(r"class=([\"'])[^\"']*footer-page[^\"']*\1", text, re.I))
    return has_root, has_section, has_page


def has_header_html_contract(html_assets: dict | None) -> tuple[bool, bool, bool]:
    if not html_assets:
        return False, False, False
    text = html_assets["text"]
    has_root = bool(re.search(r"<header[^>]*class=([\"'])[^\"']*slide-header[^\"']*\1", text, re.I))
    has_overline = bool(re.search(r"class=([\"'])[^\"']*overline[^\"']*\1", text, re.I))
    has_title = bool(re.search(r"class=([\"'])[^\"']*page-title[^\"']*\1", text, re.I))
    return has_root, has_overline, has_title


def extract_html_class_text(text: str, tag_name: str, class_name: str) -> str | None:
    match = re.search(
        rf"<{tag_name}[^>]*class=([\"'])[^\"']*{re.escape(class_name)}[^\"']*\1[^>]*>(.*?)</{tag_name}>",
        text,
        re.I | re.S,
    )
    if not match:
        return None
    inner = re.sub(r"<[^>]+>", " ", match.group(2))
    normalized = unescape(inner)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def has_semantic_text(text: str | None) -> bool:
    if not text:
        return False
    return bool(re.search(r"[A-Za-z0-9\u4e00-\u9fff]", text))


def union_box(boxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int] | None:
    if not boxes:
        return None
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def intersect_boxes(
    box_a: tuple[int, int, int, int] | None,
    box_b: tuple[int, int, int, int] | None,
) -> tuple[int, int, int, int] | None:
    if not box_a or not box_b:
        return None
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])
    if x2 - x1 < 24 or y2 - y1 < 16:
        return None
    return (x1, y1, x2, y2)


def expand_box(
    box: tuple[int, int, int, int] | None,
    pad_x: int,
    pad_y: int,
    width: int,
    height: int,
) -> tuple[int, int, int, int] | None:
    if not box:
        return None
    return clamp_box((box[0] - pad_x, box[1] - pad_y, box[2] + pad_x, box[3] + pad_y), width, height)


def iter_scan_boxes(
    zone: tuple[int, int, int, int],
    box_width: int,
    box_height: int,
    step_x: int,
    step_y: int,
) -> list[tuple[int, int, int, int]]:
    x1, y1, x2, y2 = zone
    zone_width = x2 - x1
    zone_height = y2 - y1
    actual_width = min(box_width, zone_width)
    actual_height = min(box_height, zone_height)
    if actual_width < 24 or actual_height < 16:
        return []

    x_positions = [x1]
    while x_positions[-1] + actual_width < x2:
        next_x = min(x_positions[-1] + step_x, x2 - actual_width)
        if next_x == x_positions[-1]:
            break
        x_positions.append(next_x)

    y_positions = [y1]
    while y_positions[-1] + actual_height < y2:
        next_y = min(y_positions[-1] + step_y, y2 - actual_height)
        if next_y == y_positions[-1]:
            break
        y_positions.append(next_y)

    return [(left, top, left + actual_width, top + actual_height) for top in y_positions for left in x_positions]


def summarize_boxes(label: str, boxes: list[tuple[int, int, int, int]]) -> str:
    snippets = [f"{label}@({x1},{y1},{x2},{y2})" for x1, y1, x2, y2 in boxes[:3]]
    return "; ".join(snippets)


def detect_text_boxes(
    img: Image.Image,
    zone: tuple[int, int, int, int] | None,
    box_width: int,
    box_height: int,
    step_x: int,
    step_y: int,
    *,
    min_edge_h: float,
    min_edge_v: float,
    min_luma_range: float,
    max_bright_ratio: float = 0.2,
) -> list[tuple[int, int, int, int]]:
    if not zone:
        return []
    candidates: list[tuple[int, int, int, int]] = []
    for box in iter_scan_boxes(zone, box_width, box_height, step_x, step_y):
        metrics = block_metrics(img, box)
        if metrics["edge_h"] < min_edge_h or metrics["edge_v"] < min_edge_v:
            continue
        if metrics["luma_range"] < min_luma_range or metrics["bright_ratio"] > max_bright_ratio:
            continue
        candidates.append(box)
    return merge_boxes(candidates)


def merge_boxes(
    boxes: list[tuple[int, int, int, int]],
    gap_x: int = 24,
    gap_y: int = 10,
) -> list[tuple[int, int, int, int]]:
    if not boxes:
        return []
    pending = sorted(boxes, key=lambda box: (box[1], box[0]))
    merged: list[list[int]] = []
    for box in pending:
        x1, y1, x2, y2 = box
        for current in merged:
            overlaps_x = x1 <= current[2] + gap_x and x2 >= current[0] - gap_x
            overlaps_y = y1 <= current[3] + gap_y and y2 >= current[1] - gap_y
            if overlaps_x and overlaps_y:
                current[0] = min(current[0], x1)
                current[1] = min(current[1], y1)
                current[2] = max(current[2], x2)
                current[3] = max(current[3], y2)
                break
        else:
            merged.append([x1, y1, x2, y2])
    return [tuple(item) for item in merged]


def detect_footer_slots(
    img: Image.Image,
    planning_page: dict | None,
) -> tuple[tuple[int, int, int, int] | None, list[tuple[int, int, int, int]], list[tuple[int, int, int, int]]]:
    width, height = img.size
    footer_box = footer_band_box(planning_page, width, height)
    if not footer_box:
        return None, [], []

    footer_left = clamp_box((40, footer_box[1], 320, footer_box[3]), width, height)
    footer_right = clamp_box((width - 320, footer_box[1], width - 40, footer_box[3]), width, height)
    left_boxes = detect_text_boxes(
        img,
        footer_left,
        160,
        30,
        24,
        8,
        min_edge_h=0.012,
        min_edge_v=0.010,
        min_luma_range=40,
    )
    right_boxes = detect_text_boxes(
        img,
        footer_right,
        160,
        30,
        24,
        8,
        min_edge_h=0.012,
        min_edge_v=0.010,
        min_luma_range=40,
    )
    return footer_box, left_boxes, right_boxes


def detect_header_slots(
    img: Image.Image,
    planning_page: dict | None,
) -> tuple[tuple[int, int, int, int] | None, list[tuple[int, int, int, int]], list[tuple[int, int, int, int]]]:
    width, height = img.size
    header_box = header_band_box(planning_page, width, height)
    if not header_box:
        return None, [], []

    overline_zone = clamp_box((40, header_box[1], min(width * 0.38, 420), header_box[1] + 28), width, height)
    title_zone = clamp_box((40, header_box[1] + 10, width - 120, header_box[3]), width, height)
    overline_boxes = detect_text_boxes(
        img,
        overline_zone,
        140,
        18,
        20,
        6,
        min_edge_h=0.010,
        min_edge_v=0.008,
        min_luma_range=32,
    )
    title_boxes = detect_text_boxes(
        img,
        title_zone,
        180,
        24,
        24,
        8,
        min_edge_h=0.010,
        min_edge_v=0.008,
        min_luma_range=34,
    )
    return header_box, overline_boxes, title_boxes


# ─────────────────────── 检测函数 ───────────────────────

def check_dimensions(img: Image.Image) -> dict:
    """检测截图分辨率是否为 16:9 比例，支持下层缩小图片"""
    w, h = img.size
    if abs(w / h - 16 / 9) < 0.05:
        if w >= 960:
            return {"id": "DIM-01", "status": "PASS", "msg": f"分辨率 {w}x{h} (比例正常)"}
        else:
            return {"id": "DIM-01", "status": "WARN", "msg": f"分辨率 {w}x{h} (较小但可接受)"}
    return {"id": "DIM-01", "status": "FAIL", "msg": f"分辨率 {w}x{h} 不符合 16:9 规格"}


def check_blank_ratio(img: Image.Image, threshold: float = 0.40) -> dict:
    """检测大面积空白/纯色区域是否超过阈值。

    策略：将图片缩放到小尺寸后统计主色占比。
    如果占比 > threshold 且主色极暗（背景色），再检查非背景区域是否太少。
    """
    # 缩放以加速
    small = img.resize((128, 72), Image.LANCZOS)
    pixels = list(small.getdata())
    total = len(pixels)

    # 统计颜色频率（降低精度到 8-bit 级别）
    color_count: dict[tuple, int] = {}
    for p in pixels:
        # 量化到 32 级
        quantized = (p[0] // 8 * 8, p[1] // 8 * 8, p[2] // 8 * 8)
        color_count[quantized] = color_count.get(quantized, 0) + 1

    # 找最高频色
    dominant_color = max(color_count, key=color_count.get)
    dominant_ratio = color_count[dominant_color] / total

    if dominant_ratio > threshold:
        # 检查这个 dominant 是不是背景色（暗色系）
        brightness = sum(dominant_color) / 3
        if brightness < 60:
            # 深色背景占比高可能正常（深色主题），但需要检查内容色占比
            content_pixels = sum(1 for p in pixels if sum(p) / 3 > 80)
            content_ratio = content_pixels / total
            if content_ratio < 0.15:
                return {"id": "BLANK-01", "status": "FAIL",
                        "msg": f"内容区域仅占 {content_ratio:.0%}，背景占 {dominant_ratio:.0%}（P0-3 大面积空白）"}
            return {"id": "BLANK-01", "status": "PASS",
                    "msg": f"深色背景 {dominant_ratio:.0%}，内容区 {content_ratio:.0%}"}
        else:
            return {"id": "BLANK-01", "status": "FAIL",
                    "msg": f"主色 RGB{dominant_color} 占比 {dominant_ratio:.0%}，疑似大面积空白（P0-3）"}

    return {"id": "BLANK-01", "status": "PASS",
            "msg": f"画面色彩分布正常，主色占比 {dominant_ratio:.0%}"}


def check_vertical_text(img: Image.Image) -> dict:
    """辅助检测：是否存在疑似竖排单字列。

    注意：此检测为辅助提示（WARN），不做最终判定。
    排版质量的真正判断应由 LLM view_file 看 PNG 截图完成。
    """
    w, h = img.size
    right_half = img.crop((w // 2, 0, w, h))
    small = right_half.resize((256, 144), Image.LANCZOS).convert("L")
    pixels = small.load()
    sw, sh = small.size

    threshold = 60
    suspect_regions = []

    x = 0
    while x < sw:
        col_content = sum(1 for y in range(sh) if pixels[x, y] > threshold)

        if col_content > sh * 0.25:  # 宽松阈值，宁可误报
            band_start = x
            band_end = x
            while band_end < sw - 1:
                next_content = sum(1 for y in range(sh) if pixels[band_end + 1, y] > threshold)
                if next_content > sh * 0.15:
                    band_end += 1
                else:
                    break

            band_width = band_end - band_start + 1
            content_rows = set()
            for bx in range(band_start, band_end + 1):
                for y in range(sh):
                    if pixels[bx, y] > threshold:
                        content_rows.add(y)

            content_height = (max(content_rows) - min(content_rows) + 1) if content_rows else 0
            width_ratio = band_width / sw
            height_ratio = content_height / sh

            if width_ratio < 0.06 and height_ratio > 0.35:
                suspect_regions.append(f"w={width_ratio:.1%} h={height_ratio:.1%}")

            x = band_end + 1
        else:
            x += 1

    if suspect_regions:
        return {"id": "VTXT-01", "status": "WARN",
                "msg": f"检测到 {len(suspect_regions)} 处疑似窄列内容带（{'; '.join(suspect_regions[:3])}），建议人工确认排版"}

    return {"id": "VTXT-01", "status": "PASS", "msg": "未检测到竖排异常"}


def check_overflow_cutoff(img: Image.Image) -> dict:
    """检测底部/右侧是否有内容被裁切痕迹。

    策略：检查底部和右侧边缘几行像素是否仍有非背景内容（提示被裁切）。
    """
    w, h = img.size
    pixels = img.load()

    # 检查底部最后 4 行
    bottom_content_pixels = 0
    bottom_total = w * 4
    for y in range(h - 4, h):
        for x in range(w):
            p = pixels[x, y]
            brightness = sum(p[:3]) / 3
            if brightness > 80:
                bottom_content_pixels += 1

    bottom_ratio = bottom_content_pixels / bottom_total if bottom_total > 0 else 0

    # 检查右侧最后 4 列
    right_content_pixels = 0
    right_total = h * 4
    for x in range(w - 4, w):
        for y in range(h):
            p = pixels[x, y]
            brightness = sum(p[:3]) / 3
            if brightness > 80:
                right_content_pixels += 1

    right_ratio = right_content_pixels / right_total if right_total > 0 else 0

    issues = []
    if bottom_ratio > 0.2:
        issues.append(f"底部边缘有 {bottom_ratio:.0%} 亮像素，疑似内容被裁切")
    if right_ratio > 0.15:
        issues.append(f"右侧边缘有 {right_ratio:.0%} 亮像素，疑似内容被裁切")

    if issues:
        return {"id": "CUT-01", "status": "WARN", "msg": " | ".join(issues)}

    return {"id": "CUT-01", "status": "PASS", "msg": "边缘无异常裁切痕迹"}


def check_contrast_zones(img: Image.Image) -> dict:
    """检测是否存在大面积低对比度区域（文字不可读）。

    策略：将图片分成 8x8 网格，对每个块计算亮度标准差。
    如果大量块的标准差极低（= 纯色块），且这些块不是背景色，则可能有对比度问题。
    """
    w, h = img.size
    grid_w, grid_h = 8, 8
    block_w = w // grid_w
    block_h = h // grid_h

    low_contrast_blocks = 0
    total_blocks = grid_w * grid_h

    for gx in range(grid_w):
        for gy in range(grid_h):
            block = img.crop((gx * block_w, gy * block_h, (gx + 1) * block_w, (gy + 1) * block_h))
            small_block = block.resize((16, 16), Image.LANCZOS)
            pixels = list(small_block.getdata())
            brightnesses = [sum(p[:3]) / 3 for p in pixels]

            avg = sum(brightnesses) / len(brightnesses)
            variance = sum((b - avg) ** 2 for b in brightnesses) / len(brightnesses)

            # 低方差 + 中等亮度 = 可能有文字被遮盖或对比度不足
            if variance < 25 and 40 < avg < 200:
                low_contrast_blocks += 1

    ratio = low_contrast_blocks / total_blocks
    if ratio > 0.6:
        return {"id": "CONT-01", "status": "WARN",
                "msg": f"{ratio:.0%} 的区块对比度极低，可能存在文字不可读区域"}

    return {"id": "CONT-01", "status": "PASS",
            "msg": f"对比度分布正常（低对比区块 {ratio:.0%}）"}


def check_file_size(png_path: Path) -> dict:
    """检测 PNG 文件大小是否合理。"""
    size = png_path.stat().st_size
    if size < 10_000:
        return {"id": "SIZE-01", "status": "FAIL",
                "msg": f"PNG 仅 {size:,} bytes，疑似空白页或截图失败"}
    if size < 50_000:
        return {"id": "SIZE-01", "status": "WARN",
                "msg": f"PNG {size:,} bytes，内容可能过少"}
    return {"id": "SIZE-01", "status": "PASS", "msg": f"PNG {size:,} bytes"}


def check_html_image_assets(png_path: Path, planning_path: Path | None = None, html_path: Path | None = None) -> dict:
    planning_page = load_planning_page(planning_path)
    expected_cards = get_expected_image_cards(planning_page)
    if not expected_cards:
        return {"id": "IMG-01", "status": "PASS", "msg": "planning 未要求真实图片资产"}

    html_path = html_path or infer_html_path(png_path, planning_path)
    html_assets = parse_html_assets(html_path)
    if html_assets is None:
        return {"id": "IMG-01", "status": "WARN", "msg": "未找到对应 HTML，无法核验图片资源落地"}

    local_assets = html_assets["images"] + [{"path": path} for path in html_assets["background_assets"]]
    if not local_assets:
        return {
            "id": "IMG-01",
            "status": "FAIL",
            "msg": f"planning 需要 {len(expected_cards)} 张真实图片，但 HTML 未发现 img/src 或 background-image 资产",
        }

    missing = sorted({str(item["path"]) for item in local_assets if not item["path"].exists()})
    if missing:
        preview = missing[:3]
        suffix = "..." if len(missing) > 3 else ""
        return {
            "id": "IMG-01",
            "status": "FAIL",
            "msg": f"发现 {len(missing)} 个不存在的本地图片资源: {preview}{suffix}",
        }

    return {
        "id": "IMG-01",
        "status": "PASS",
        "msg": f"HTML 已引用 {len(local_assets)} 个本地图片资源，满足 {len(expected_cards)} 张真实图片需求",
    }


def check_image_fit_contract(png_path: Path, planning_path: Path | None = None, html_path: Path | None = None) -> dict:
    planning_page = load_planning_page(planning_path)
    expected_cards = get_expected_image_cards(planning_page)
    if not expected_cards:
        return {"id": "IMG-02", "status": "PASS", "msg": "无真实图片卡片，不需要 object-fit 检查"}

    html_path = html_path or infer_html_path(png_path, planning_path)
    html_assets = parse_html_assets(html_path)
    if html_assets is None:
        return {"id": "IMG-02", "status": "WARN", "msg": "未找到对应 HTML，无法检查图片变形保护"}

    html_text = html_assets["text"].lower()
    img_assets = html_assets["images"]
    if not img_assets:
        return {"id": "IMG-02", "status": "WARN", "msg": "HTML 未使用 <img>，跳过 object-fit 检查"}

    has_global_object_fit = "object-fit" in html_text
    risky = []
    for item in img_assets:
        style = item.get("style", "").lower()
        has_width = bool(item.get("width")) or bool(re.search(r"(^|;)\s*width\s*:", style))
        has_height = bool(item.get("height")) or bool(re.search(r"(^|;)\s*height\s*:", style))
        has_local_fit = "object-fit" in style
        if has_width and has_height and not (has_local_fit or has_global_object_fit):
            risky.append(f"line {item.get('line', '?')}: {item.get('src', '')}")

    if risky:
        return {
            "id": "IMG-02",
            "status": "FAIL",
            "msg": f"发现 {len(risky)} 个 img 同时锁定宽高但未声明 object-fit，存在严重变形风险: {risky[:3]}",
        }

    if not has_global_object_fit:
        return {
            "id": "IMG-02",
            "status": "WARN",
            "msg": "页面存在真实图片，但未检测到显式 object-fit 保护，建议人工确认未被拉伸",
        }

    return {"id": "IMG-02", "status": "PASS", "msg": "检测到 object-fit / 宽高保护，图片变形风险可控"}


def check_safe_zone_intrusion(img: Image.Image, planning_path: Path | None = None) -> dict:
    planning_page = load_planning_page(planning_path)
    if planning_page and planning_page.get("page_type") in {"cover", "end"}:
        return {"id": "SAFE-01", "status": "PASS", "msg": "封面/结束页允许更自由出血，跳过内容页安全带检测"}

    w, h = img.size
    bg = estimate_background_color(img)
    bands = {
        "left": content_ratio_for_box(img, (0, 0, min(64, w), h), bg),
        "right": content_ratio_for_box(img, (max(w - 64, 0), 0, w, h), bg),
        "bottom": content_ratio_for_box(img, (0, max(h - 84, 0), w, h), bg),
    }
    worst_side = max(bands["left"], bands["right"])
    if bands["bottom"] > 0.16 or worst_side > 0.14:
        return {
            "id": "SAFE-01",
            "status": "FAIL",
            "msg": (
                f"安全带侵入明显：bottom={bands['bottom']:.0%}, "
                f"left={bands['left']:.0%}, right={bands['right']:.0%}"
            ),
        }
    if bands["bottom"] > 0.10 or worst_side > 0.08:
        return {
            "id": "SAFE-01",
            "status": "WARN",
            "msg": (
                f"安全带内容密度偏高：bottom={bands['bottom']:.0%}, "
                f"left={bands['left']:.0%}, right={bands['right']:.0%}"
            ),
        }
    return {
        "id": "SAFE-01",
        "status": "PASS",
        "msg": f"安全带内容密度正常：bottom={bands['bottom']:.0%}, left={bands['left']:.0%}, right={bands['right']:.0%}",
    }


def check_overlap_risk(
    png_path: Path,
    img: Image.Image,
    planning_path: Path | None = None,
    html_path: Path | None = None,
) -> dict:
    planning_page = load_planning_page(planning_path)
    expected_cards = get_expected_image_cards(planning_page)
    if not expected_cards:
        return {"id": "OVLP-01", "status": "PASS", "msg": "无真实图片卡片，不需要图文遮挡风险检查"}

    html_path = html_path or infer_html_path(png_path, planning_path)
    html_assets = parse_html_assets(html_path)
    if html_assets is None:
        return {"id": "OVLP-01", "status": "WARN", "msg": "未找到对应 HTML，无法评估图文叠放风险"}

    html_text = html_assets["text"].lower()
    absolute_count = len(re.findall(r"position\s*:\s*absolute", html_text))
    z_index_count = len(re.findall(r"z-index\s*:", html_text))

    w, h = img.size
    center_box = (w // 5, h // 5, w * 4 // 5, h * 4 // 5)
    center = img.crop(center_box).resize((96, 54), Image.LANCZOS).convert("L")
    pixels = center.load()
    sw, sh = center.size
    edge_pixels = 0
    total_pairs = 0
    for y in range(sh):
        for x in range(1, sw):
            total_pairs += 1
            if abs(pixels[x, y] - pixels[x - 1, y]) > 42:
                edge_pixels += 1
    edge_ratio = edge_pixels / total_pairs if total_pairs else 0.0

    if absolute_count >= 10 and z_index_count >= 6 and edge_ratio > 0.19:
        return {
            "id": "OVLP-01",
            "status": "WARN",
            "msg": (
                f"图文并茂页叠放风险偏高：absolute={absolute_count}, z-index={z_index_count}, "
                f"center-edge={edge_ratio:.0%}，请人工确认是否发生图文遮挡"
            ),
        }

    return {
        "id": "OVLP-01",
        "status": "PASS",
        "msg": f"未发现明显的图文遮挡高风险信号（absolute={absolute_count}, center-edge={edge_ratio:.0%}）",
    }


def check_caption_drift(img: Image.Image, planning_path: Path | None = None) -> dict:
    planning_page = load_planning_page(planning_path)
    zones = get_image_scan_zones(planning_page, *img.size)
    if not zones:
        return {"id": "CAP-01", "status": "PASS", "msg": "无真实图片卡片，不需要 caption 漂移检查"}

    width, height = img.size
    bg = estimate_background_color(img)
    footer_box = footer_band_box(planning_page, width, height)
    footer_top = footer_box[1] if footer_box else height - 20
    suspects: list[tuple[int, int, int, int]] = []

    for _, zone in zones:
        zone_x1, zone_y1, zone_x2, zone_y2 = zone
        search_zone = clamp_box(
            (zone_x1 - 24, max(zone_y2 - 12, height * 0.56), zone_x2 + 24, footer_top - 8),
            width,
            height,
        )
        if not search_zone:
            continue

        for box in iter_scan_boxes(search_zone, 280, 64, 56, 20):
            metrics = block_metrics(img, box)
            if metrics["edge_h"] < 0.040 or metrics["edge_v"] < 0.035:
                continue
            if metrics["bright_ratio"] > 0.12 or metrics["luma_range"] < 55:
                continue
            if metrics["luma_range"] < 180:
                continue

            above_box = clamp_box((box[0], box[1] - 96, box[2], box[1] - 12), width, height)
            above_content = content_ratio_for_box(img, above_box, bg) if above_box else 0.0
            above_std = block_metrics(img, above_box)["stddev"] if above_box else 0.0

            if box[1] > int(height * 0.80) or (above_content < 0.07 and above_std < 8.0):
                suspects.append(box)

    if suspects:
        return {
            "id": "CAP-01",
            "status": "WARN",
            "msg": f"检测到疑似 caption/source 漂移到底部或脱离图片区: {summarize_boxes('caption', suspects)}",
        }

    return {"id": "CAP-01", "status": "PASS", "msg": "未检测到明显的 caption/source 漂移信号"}


def check_footer_semantic_conflict(img: Image.Image, planning_path: Path | None = None) -> dict:
    planning_page = load_planning_page(planning_path)
    width, height = img.size
    footer_box, left_boxes, right_boxes = detect_footer_slots(img, planning_page)
    if not footer_box:
        return {"id": "FTR-01", "status": "PASS", "msg": "当前页型不要求统一页脚带，跳过页脚语义冲突检查"}

    image_zones = get_image_scan_zones(planning_page, width, height)

    drift_boxes: list[tuple[int, int, int, int]] = []
    source_boxes: list[tuple[int, int, int, int]] = []
    for _, zone in image_zones:
        image_footer_overlap = clamp_box((zone[0] - 24, footer_box[1], zone[2] + 24, footer_box[3]), width, height)
        drift_boxes.extend(
            detect_text_boxes(
                img,
                image_footer_overlap,
                180,
                30,
                24,
                8,
                min_edge_h=0.016,
                min_edge_v=0.012,
                min_luma_range=55,
            )
        )

        source_lane = clamp_box((zone[0] - 24, max(zone[3] - 8, height * 0.56), zone[2] + 24, footer_box[1] - 8), width, height)
        source_boxes.extend(
            detect_text_boxes(
                img,
                source_lane,
                220,
                34,
                28,
                10,
                min_edge_h=0.018,
                min_edge_v=0.014,
                min_luma_range=55,
            )
        )

    drift_boxes = [
        box
        for box in merge_boxes(drift_boxes)
        if width * 0.28 <= ((box[0] + box[2]) / 2) <= width * 0.72
    ]
    source_boxes = merge_boxes(source_boxes)

    footer_present = bool(left_boxes or right_boxes)
    if drift_boxes and footer_present:
        return {
            "id": "FTR-01",
            "status": "WARN",
            "msg": (
                "检测到页脚语义冲突：footer="
                f"{len(left_boxes) + len(right_boxes)} 组, source-lane={len(source_boxes)} 组, drift-in-footer={len(drift_boxes)} 组; "
                f"{summarize_boxes('footer-drift', drift_boxes)}"
            ),
        }
    if drift_boxes:
        return {
            "id": "FTR-01",
            "status": "WARN",
            "msg": (
                "检测到页脚带出现疑似 caption/source 文本，但未识别到稳定页脚骨架："
                f"drift-in-footer={len(drift_boxes)} 组; {summarize_boxes('footer-drift', drift_boxes)}"
            ),
        }

    return {
        "id": "FTR-01",
        "status": "PASS",
        "msg": (
            f"页脚语义分区正常：footer={len(left_boxes) + len(right_boxes)} 组, "
            f"source-lane={len(source_boxes)} 组, drift-in-footer=0 组"
        ),
    }


def check_footer_contract(
    png_path: Path,
    img: Image.Image,
    planning_path: Path | None = None,
    html_path: Path | None = None,
) -> dict:
    planning_page = load_planning_page(planning_path)
    footer_box, left_boxes, right_boxes = detect_footer_slots(img, planning_page)
    if not footer_box:
        return {"id": "FTR-02", "status": "PASS", "msg": "当前页型不要求统一页脚骨架，跳过 footer 合同检查"}

    html_path = html_path or infer_html_path(png_path, planning_path)
    html_assets = parse_html_assets(html_path)
    if html_assets is None:
        return {"id": "FTR-02", "status": "WARN", "msg": "未找到对应 HTML，无法核验 footer 骨架是否落地"}

    has_root, has_section, has_page = has_footer_html_contract(html_assets)
    if not has_root:
        return {"id": "FTR-02", "status": "FAIL", "msg": "content/toc/section 页缺少统一 footer.slide-footer 骨架"}
    if not has_section or not has_page:
        missing = []
        if not has_section:
            missing.append("footer-section")
        if not has_page:
            missing.append("footer-page")
        return {"id": "FTR-02", "status": "FAIL", "msg": f"页脚骨架不完整，缺少: {', '.join(missing)}"}

    issues = []
    if not left_boxes:
        issues.append("左侧 footer-section 槽位未检测到稳定页脚信号")
    if not right_boxes:
        issues.append("右侧 footer-page 槽位未检测到稳定页脚信号")

    if left_boxes:
        left_center = max((box[0] + box[2]) / 2 for box in left_boxes)
        if left_center > img.size[0] * 0.42:
            issues.append("左侧页脚信号明显内缩，疑似骨架失真")
    if right_boxes:
        right_center = min((box[0] + box[2]) / 2 for box in right_boxes)
        if right_center < img.size[0] * 0.58:
            issues.append("右侧页脚信号明显内缩，疑似骨架失真")

    if issues:
        return {"id": "FTR-02", "status": "WARN", "msg": "；".join(issues)}

    return {"id": "FTR-02", "status": "PASS", "msg": "检测到统一 footer 骨架且左右页脚槽位信号稳定"}


def check_header_contract(
    png_path: Path,
    img: Image.Image,
    planning_path: Path | None = None,
    html_path: Path | None = None,
) -> dict:
    planning_page = load_planning_page(planning_path)
    header_box, overline_boxes, title_boxes = detect_header_slots(img, planning_page)
    if not header_box:
        return {"id": "HDR-01", "status": "PASS", "msg": "当前页型不要求统一标题骨架，跳过 header 合同检查"}

    html_path = html_path or infer_html_path(png_path, planning_path)
    html_assets = parse_html_assets(html_path)
    if html_assets is None:
        return {"id": "HDR-01", "status": "WARN", "msg": "未找到对应 HTML，无法核验 header 骨架是否落地"}

    has_root, has_overline, has_title = has_header_html_contract(html_assets)
    if not has_root:
        return {"id": "HDR-01", "status": "FAIL", "msg": "content/toc 页缺少统一 header.slide-header 骨架"}
    if not has_overline or not has_title:
        missing = []
        if not has_overline:
            missing.append("overline")
        if not has_title:
            missing.append("page-title")
        return {"id": "HDR-01", "status": "FAIL", "msg": f"标题骨架不完整，缺少: {', '.join(missing)}"}

    issues = []
    if not title_boxes:
        issues.append("顶部标题带未检测到稳定 page-title 信号")
    else:
        title_left = min(box[0] for box in title_boxes)
        title_top = min(box[1] for box in title_boxes)
        if title_left > img.size[0] * 0.24:
            issues.append("page-title 明显右移/内缩，疑似标题骨架跑位")
        if title_top > header_box[1] + 18:
            issues.append("page-title 明显下沉，疑似标题骨架跑位")

    if overline_boxes:
        overline_left = min(box[0] for box in overline_boxes)
        overline_top = min(box[1] for box in overline_boxes)
        if overline_left > img.size[0] * 0.20:
            issues.append("overline 信号明显右移，疑似标题骨架跑位")
        if overline_top > header_box[1] + 10:
            issues.append("overline 信号明显下沉，疑似标题骨架跑位")

    if issues:
        return {"id": "HDR-01", "status": "WARN", "msg": "；".join(issues)}

    return {"id": "HDR-01", "status": "PASS", "msg": "检测到统一 header 骨架且顶部标题槽位信号稳定"}


def check_header_semantics(
    png_path: Path,
    img: Image.Image,
    planning_path: Path | None = None,
    html_path: Path | None = None,
) -> dict:
    planning_page = load_planning_page(planning_path)
    width, height = img.size
    header_box, overline_boxes, title_boxes = detect_header_slots(img, planning_page)
    if not header_box:
        return {"id": "HDR-02", "status": "PASS", "msg": "当前页型不要求统一标题语义带，跳过 header 语义检查"}

    issues: list[str] = []
    html_path = html_path or infer_html_path(png_path, planning_path)
    html_assets = parse_html_assets(html_path)
    if html_assets is not None:
        overline_text = extract_html_class_text(html_assets["text"], "span", "overline")
        title_text = extract_html_class_text(html_assets["text"], "h1", "page-title")
        if overline_text is not None and not has_semantic_text(overline_text):
            issues.append("overline 元素存在但内容为空壳")
        if title_text is not None and not has_semantic_text(title_text):
            issues.append("page-title 元素存在但内容为空壳")

    title_union = union_box(title_boxes)
    if title_union:
        if title_union[3] > 96:
            issues.append("page-title 信号下串进内容起始带")

        spill_zone = clamp_box(
            (max(140, title_union[0] - 40), max(header_box[3] + 10, 90), min(width - 120, title_union[2] + 72), 132),
            width,
            height,
        )
        spill_boxes = detect_text_boxes(
            img,
            spill_zone,
            220,
            28,
            24,
            8,
            min_edge_h=0.012,
            min_edge_v=0.010,
            min_luma_range=36,
        )
        spill_boxes = [box for box in spill_boxes if box[1] >= header_box[3] + 10]
        if spill_boxes:
            issues.append(f"标题区与内容区疑似串位: {summarize_boxes('header-spill', spill_boxes)}")

        image_zones = get_image_scan_zones(planning_page, width, height)
        if image_zones:
            title_visual_box = expand_box(title_union, 18, 14, width, height)
            if title_visual_box:
                metrics = block_metrics(img, title_visual_box)
                if metrics["stddev"] > 32.0 and metrics["edge_h"] > 0.070 and metrics["edge_v"] > 0.050:
                    issues.append("标题区背景复杂度过高，疑似被主视觉/高噪声纹理压住")

                overlap_boxes = []
                for _, zone in image_zones:
                    overlap = intersect_boxes(title_visual_box, zone)
                    if overlap is not None:
                        overlap_boxes.append(overlap)
                if overlap_boxes:
                    issues.append(f"标题带与主视觉规划区域发生几何重叠: {summarize_boxes('header-visual', overlap_boxes)}")

    if issues:
        return {"id": "HDR-02", "status": "WARN", "msg": "；".join(issues)}

    return {"id": "HDR-02", "status": "PASS", "msg": "未发现 overline 空壳、标题下串或标题受主视觉干扰的明显信号"}


def check_image_text_contrast(img: Image.Image, planning_path: Path | None = None) -> dict:
    planning_page = load_planning_page(planning_path)
    zones = get_image_scan_zones(planning_page, *img.size)
    if not zones:
        return {"id": "IMG-03", "status": "PASS", "msg": "无真实图片卡片，不需要图片区文字对比检查"}

    suspects: list[tuple[int, int, int, int]] = []
    for _, zone in zones:
        for box in iter_scan_boxes(zone, 180, 88, 60, 28):
            metrics = block_metrics(img, box)
            if metrics["stddev"] < 8.0 or metrics["stddev"] > 24.0:
                continue
            if metrics["luma_range"] > 95.0:
                continue
            if metrics["edge_h"] >= 0.036 and metrics["edge_v"] >= 0.029:
                suspects.append(box)

    if suspects:
        return {
            "id": "IMG-03",
            "status": "WARN",
            "msg": f"检测到疑似图片区文字对比不足: {summarize_boxes('image-text', suspects)}",
        }

    return {"id": "IMG-03", "status": "PASS", "msg": "未检测到明显的图片区文字低对比风险"}


def check_planning_cards_coverage(img: Image.Image, planning_path: Path) -> dict:
    """辅助检测：planning 卡片 vs 图片结构复杂度的粗略对比。

    注意：此检测为辅助提示。深色主题下边缘密度天然偏低，
    真正的卡片缺失判断应由 LLM 看图 + 对照 planning JSON 完成。
    """
    if not planning_path.exists():
        return {"id": "CARD-01", "status": "WARN", "msg": f"planning 文件不存在: {planning_path}"}

    try:
        with open(planning_path) as f:
            planning = json.load(f)
        page = planning.get("page", planning)
        cards = page.get("cards", [])
        card_count = len(cards)
    except (json.JSONDecodeError, KeyError):
        return {"id": "CARD-01", "status": "WARN", "msg": "planning JSON 解析失败"}

    if card_count == 0:
        return {"id": "CARD-01", "status": "PASS", "msg": "planning 无卡片定义"}

    w, h = img.size
    small = img.resize((64, 36), Image.LANCZOS).convert("L")
    pixels = small.load()
    sw, sh = small.size

    edge_count = 0
    for y in range(sh):
        for x in range(1, sw):
            diff = abs(pixels[x, y] - pixels[x - 1, y])
            if diff > 30:
                edge_count += 1

    edge_density = edge_count / (sw * sh)

    # 极低边缘密度 + 多卡片 = 疑似卡片缺失（辅助提示）
    if card_count >= 3 and edge_density < 0.015:
        return {"id": "CARD-01", "status": "WARN",
                "msg": f"planning 有 {card_count} 张卡片，但图片结构极简（边缘密度 {edge_density:.3f}），建议人工确认卡片完整性"}

    return {"id": "CARD-01", "status": "PASS",
            "msg": f"planning {card_count} 张卡片，图片边缘密度 {edge_density:.3f}"}


# ─────────────────────── 主逻辑 ───────────────────────

def run_checks(
    png_path: Path,
    planning_path: Path | None = None,
    html_path: Path | None = None,
) -> list[dict]:
    """对单张 PNG 运行全部检测。"""
    results = []
    resolved_html_path = html_path or infer_html_path(png_path, planning_path)

    # 文件级检查
    results.append(check_file_size(png_path))

    # 打开图片
    try:
        img = Image.open(png_path).convert("RGB")
    except Exception as e:
        results.append({"id": "OPEN-01", "status": "FAIL", "msg": f"无法打开 PNG: {e}"})
        return results

    # 像素级检查
    results.append(check_dimensions(img))
    results.append(check_blank_ratio(img))
    results.append(check_vertical_text(img))
    results.append(check_overflow_cutoff(img))
    results.append(check_contrast_zones(img))
    results.append(check_safe_zone_intrusion(img, planning_path))
    results.append(check_html_image_assets(png_path, planning_path, resolved_html_path))
    results.append(check_image_fit_contract(png_path, planning_path, resolved_html_path))
    results.append(check_image_text_contrast(img, planning_path))
    results.append(check_caption_drift(img, planning_path))
    results.append(check_header_contract(png_path, img, planning_path, resolved_html_path))
    results.append(check_header_semantics(png_path, img, planning_path, resolved_html_path))
    results.append(check_footer_contract(png_path, img, planning_path, resolved_html_path))
    results.append(check_footer_semantic_conflict(img, planning_path))
    results.append(check_overlap_risk(png_path, img, planning_path, resolved_html_path))

    # planning 对照检查
    if planning_path:
        results.append(check_planning_cards_coverage(img, planning_path))

    return results


def print_report(png_name: str, results: list[dict]) -> tuple[int, int]:
    """打印检测报告，返回 (fail_count, warn_count)。"""
    fails = sum(1 for r in results if r["status"] == "FAIL")
    warns = sum(1 for r in results if r["status"] == "WARN")

    print(f"\n{'─' * 60}")
    print(f"  {png_name}")
    print(f"{'─' * 60}")

    for r in results:
        icon = {"PASS": "OK", "WARN": "!!", "FAIL": "XX"}[r["status"]]
        print(f"  [{icon}] {r['id']}: {r['msg']}")

    verdict = "PASS" if fails == 0 and warns == 0 else ("FAIL" if fails > 0 else "WARN")
    print(f"\n  verdict: {verdict}  (FAIL={fails}, WARN={warns})")
    return fails, warns


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target = Path(sys.argv[1]).resolve()

    # 解析可选参数
    planning_path = None
    planning_dir = None
    html_path = None
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--planning" and i + 1 < len(args):
            planning_path = Path(args[i + 1]).resolve()
            i += 2
        elif args[i] == "--planning-dir" and i + 1 < len(args):
            planning_dir = Path(args[i + 1]).resolve()
            i += 2
        elif args[i] == "--html" and i + 1 < len(args):
            html_path = Path(args[i + 1]).resolve()
            i += 2
        else:
            i += 1

    # 收集要检查的 PNG
    if target.is_file():
        pngs = [target]
    elif target.is_dir():
        pngs = sorted(target.glob("slide-*.png"))
    else:
        print(f"ERROR: {target} 不存在", file=sys.stderr)
        sys.exit(1)

    if not pngs:
        print(f"ERROR: 未找到 slide-*.png 文件于 {target}", file=sys.stderr)
        sys.exit(1)

    total_fails = 0
    total_warns = 0

    for png in pngs:
        # 自动推断 planning 路径
        pp = planning_path
        if pp is None and planning_dir:
            # slide-3.png -> planning3.json
            import re
            m = re.search(r"slide-(\d+)", png.stem)
            if m:
                pp = planning_dir / f"planning{m.group(1)}.json"

        resolved_html = html_path if html_path and html_path.exists() else None
        results = run_checks(png, pp, resolved_html)
        f, w = print_report(png.name, results)
        total_fails += f
        total_warns += w

    print(f"\n{'=' * 60}")
    print(f"  TOTAL: {len(pngs)} pages, FAIL={total_fails}, WARN={total_warns}")
    if total_fails > 0:
        print(f"  EXIT 1 — 存在致命缺陷，建议重跑对应页面")
    elif total_warns > 0:
        print(f"  EXIT 2 — 存在品质警告，建议人工复查")
    else:
        print(f"  EXIT 0 — 全部通过")
    print(f"{'=' * 60}")

    sys.exit(1 if total_fails > 0 else (2 if total_warns > 0 else 0))


if __name__ == "__main__":
    main()
