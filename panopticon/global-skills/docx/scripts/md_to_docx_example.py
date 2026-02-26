#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def parse_markdown_blocks(input_md: Path) -> list[dict[str, Any]]:
    lines = input_md.read_text(encoding="utf-8").splitlines()
    blocks: list[dict[str, Any]] = []

    in_code_block = False
    code_buffer: list[str] = []

    for raw in lines:
        line = raw.rstrip("\n")

        if line.strip().startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_buffer = []
            else:
                in_code_block = False
                code_text = "\n".join(code_buffer).strip()
                if code_text:
                    blocks.append({"type": "paragraph", "text": code_text})
            continue

        if in_code_block:
            code_buffer.append(line)
            continue

        if not line.strip():
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            level = min(len(heading_match.group(1)), 6)
            content = heading_match.group(2).strip()
            blocks.append({"type": "heading", "level": level, "text": content})
            continue

        bullet_match = re.match(r"^\s*[-*]\s+(.*)$", line)
        if bullet_match:
            blocks.append({"type": "bullet", "text": bullet_match.group(1).strip()})
            continue

        number_match = re.match(r"^\s*\d+\.\s+(.*)$", line)
        if number_match:
            blocks.append({"type": "number", "text": number_match.group(1).strip()})
            continue

        blocks.append({"type": "paragraph", "text": line.strip()})

    return blocks


def convert_with_pandoc(input_md: Path, output_docx: Path) -> tuple[bool, str]:
    pandoc = shutil.which("pandoc")
    if not pandoc:
        return False, "pandoc not found"

    try:
        subprocess.run(
            [pandoc, str(input_md), "-o", str(output_docx)],
            check=True,
            capture_output=True,
            text=True,
        )
        return True, "converted by pandoc"
    except subprocess.CalledProcessError as exc:
        msg = (exc.stderr or exc.stdout or str(exc)).strip()
        return False, f"pandoc failed: {msg[:300]}"


def convert_with_python_docx(input_md: Path, output_docx: Path) -> tuple[bool, str]:
    try:
        from docx import Document  # type: ignore
    except Exception:
        return False, "python-docx not installed"

    blocks = parse_markdown_blocks(input_md)
    doc = Document()

    for block in blocks:
        block_type = block["type"]
        text = block["text"]
        if block_type == "heading":
            doc.add_heading(text, level=int(block["level"]))
        elif block_type == "bullet":
            paragraph = doc.add_paragraph(text)
            paragraph.style = "List Bullet"
        elif block_type == "number":
            paragraph = doc.add_paragraph(text)
            paragraph.style = "List Number"
        else:
            doc.add_paragraph(text)

    output_docx.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_docx)
    return True, "converted by python-docx fallback"


def build_document_xml(blocks: list[dict[str, Any]]) -> str:
    paragraphs: list[str] = []

    for block in blocks:
        text = html.escape(str(block.get("text", "")))
        block_type = block.get("type")

        if block_type == "heading":
            level = int(block.get("level", 1))
            level = min(max(level, 1), 6)
            style_id = f"Heading{level}"
            paragraphs.append(
                "<w:p>"
                f"<w:pPr><w:pStyle w:val=\"{style_id}\"/></w:pPr>"
                f"<w:r><w:t>{text}</w:t></w:r>"
                "</w:p>"
            )
        elif block_type == "bullet":
            paragraphs.append(
                "<w:p>"
                "<w:pPr><w:numPr><w:ilvl w:val=\"0\"/><w:numId w:val=\"1\"/></w:numPr></w:pPr>"
                f"<w:r><w:t>{text}</w:t></w:r>"
                "</w:p>"
            )
        elif block_type == "number":
            paragraphs.append(
                "<w:p>"
                "<w:pPr><w:numPr><w:ilvl w:val=\"0\"/><w:numId w:val=\"2\"/></w:numPr></w:pPr>"
                f"<w:r><w:t>{text}</w:t></w:r>"
                "</w:p>"
            )
        else:
            paragraphs.append(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>")

    body_xml = "".join(paragraphs)
    sect_pr = (
        "<w:sectPr>"
        "<w:pgSz w:w=\"11906\" w:h=\"16838\"/>"
        "<w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\" "
        "w:header=\"708\" w:footer=\"708\" w:gutter=\"0\"/>"
        "</w:sectPr>"
    )

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
        f"<w:body>{body_xml}{sect_pr}</w:body>"
        "</w:document>"
    )


def build_styles_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:styles xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        "<w:style w:type=\"paragraph\" w:default=\"1\" w:styleId=\"Normal\">"
        "<w:name w:val=\"Normal\"/>"
        "<w:qFormat/>"
        "</w:style>"
        "<w:style w:type=\"paragraph\" w:styleId=\"Heading1\"><w:name w:val=\"heading 1\"/>"
        "<w:basedOn w:val=\"Normal\"/><w:qFormat/>"
        "<w:rPr><w:b/><w:sz w:val=\"32\"/></w:rPr></w:style>"
        "<w:style w:type=\"paragraph\" w:styleId=\"Heading2\"><w:name w:val=\"heading 2\"/>"
        "<w:basedOn w:val=\"Normal\"/><w:qFormat/>"
        "<w:rPr><w:b/><w:sz w:val=\"28\"/></w:rPr></w:style>"
        "<w:style w:type=\"paragraph\" w:styleId=\"Heading3\"><w:name w:val=\"heading 3\"/>"
        "<w:basedOn w:val=\"Normal\"/><w:qFormat/>"
        "<w:rPr><w:b/><w:sz w:val=\"24\"/></w:rPr></w:style>"
        "</w:styles>"
    )


def build_numbering_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:numbering xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        "<w:abstractNum w:abstractNumId=\"0\">"
        "<w:lvl w:ilvl=\"0\"><w:start w:val=\"1\"/><w:numFmt w:val=\"bullet\"/>"
        "<w:lvlText w:val=\"•\"/><w:lvlJc w:val=\"left\"/></w:lvl>"
        "</w:abstractNum>"
        "<w:abstractNum w:abstractNumId=\"1\">"
        "<w:lvl w:ilvl=\"0\"><w:start w:val=\"1\"/><w:numFmt w:val=\"decimal\"/>"
        "<w:lvlText w:val=\"%1.\"/><w:lvlJc w:val=\"left\"/></w:lvl>"
        "</w:abstractNum>"
        "<w:num w:numId=\"1\"><w:abstractNumId w:val=\"0\"/></w:num>"
        "<w:num w:numId=\"2\"><w:abstractNumId w:val=\"1\"/></w:num>"
        "</w:numbering>"
    )


def build_content_types_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
        "<Override PartName=\"/word/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml\"/>"
        "<Override PartName=\"/word/numbering.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml\"/>"
        "<Override PartName=\"/docProps/core.xml\" ContentType=\"application/vnd.openxmlformats-package.core-properties+xml\"/>"
        "<Override PartName=\"/docProps/app.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.extended-properties+xml\"/>"
        "</Types>"
    )


def build_root_rels_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>"
        "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties\" Target=\"docProps/core.xml\"/>"
        "<Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties\" Target=\"docProps/app.xml\"/>"
        "</Relationships>"
    )


def build_document_rels_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/>"
        "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering\" Target=\"numbering.xml\"/>"
        "</Relationships>"
    )


def build_core_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" "
        "xmlns:dc=\"http://purl.org/dc/elements/1.1/\" "
        "xmlns:dcterms=\"http://purl.org/dc/terms/\" "
        "xmlns:dcmitype=\"http://purl.org/dc/dcmitype/\" "
        "xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">"
        "<dc:title>Markdown to DOCX Example</dc:title>"
        "<dc:creator>OpenClaw DOCX Skill</dc:creator>"
        "</cp:coreProperties>"
    )


def build_app_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Properties xmlns=\"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties\" "
        "xmlns:vt=\"http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes\">"
        "<Application>OpenClaw DOCX Skill</Application>"
        "</Properties>"
    )


def convert_with_builtin_ooxml(input_md: Path, output_docx: Path) -> tuple[bool, str]:
    try:
        blocks = parse_markdown_blocks(input_md)
        output_docx.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(output_docx, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", build_content_types_xml())
            zf.writestr("_rels/.rels", build_root_rels_xml())
            zf.writestr("docProps/core.xml", build_core_xml())
            zf.writestr("docProps/app.xml", build_app_xml())
            zf.writestr("word/document.xml", build_document_xml(blocks))
            zf.writestr("word/styles.xml", build_styles_xml())
            zf.writestr("word/numbering.xml", build_numbering_xml())
            zf.writestr("word/_rels/document.xml.rels", build_document_rels_xml())

        return True, "converted by built-in OOXML fallback"
    except Exception as exc:
        return False, f"built-in fallback failed: {exc}"


def extract_used_paragraph_styles(document_xml: bytes) -> set[str]:
    root = ET.fromstring(document_xml)
    styles: set[str] = set()
    for p_style in root.findall(".//w:p/w:pPr/w:pStyle", NS):
        val = p_style.attrib.get(f"{{{W_NS}}}val")
        if val:
            styles.add(val)
    return styles


def style_check(docx_path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "docx": str(docx_path),
        "ok": False,
        "checks": {},
        "used_paragraph_styles": [],
        "warnings": [],
    }

    if not docx_path.exists():
        report["warnings"].append("docx file does not exist")
        return report

    try:
        with zipfile.ZipFile(docx_path, "r") as zf:
            names = set(zf.namelist())

            has_document_xml = "word/document.xml" in names
            has_styles_xml = "word/styles.xml" in names
            has_rels = "word/_rels/document.xml.rels" in names

            report["checks"]["has_word_document_xml"] = has_document_xml
            report["checks"]["has_word_styles_xml"] = has_styles_xml
            report["checks"]["has_document_rels"] = has_rels

            if not has_document_xml:
                report["warnings"].append("missing word/document.xml")
                return report

            document_xml = zf.read("word/document.xml")
            used_styles = sorted(extract_used_paragraph_styles(document_xml))
            report["used_paragraph_styles"] = used_styles

            has_heading_style = any(s.startswith("Heading") for s in used_styles)
            has_list_style = any(s.startswith("List") for s in used_styles)

            root = ET.fromstring(document_xml)
            has_numpr = root.find(".//w:numPr", NS) is not None

            report["checks"]["has_heading_style"] = has_heading_style
            report["checks"]["has_list_style_or_numpr"] = bool(has_list_style or has_numpr)

            if not has_heading_style:
                report["warnings"].append("no Heading* style found in paragraphs")
            if not (has_list_style or has_numpr):
                report["warnings"].append("no list style or numbering properties found")

            report["ok"] = all(report["checks"].values())
            return report
    except Exception as exc:
        report["warnings"].append(f"style check failed: {exc}")
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal Markdown -> DOCX example with style checks")
    parser.add_argument("--input", required=True, help="input markdown file path")
    parser.add_argument("--output", required=True, help="output docx file path")
    parser.add_argument("--report", default="", help="optional json report output path")
    args = parser.parse_args()

    input_md = Path(args.input)
    output_docx = Path(args.output)

    if not input_md.exists():
        print(f"[error] input markdown not found: {input_md}")
        return 1

    output_docx.parent.mkdir(parents=True, exist_ok=True)

    ok, message = convert_with_pandoc(input_md, output_docx)
    if not ok:
        ok, fallback_message = convert_with_python_docx(input_md, output_docx)
        message = f"{message}; fallback: {fallback_message}"
    if not ok:
        ok, builtin_message = convert_with_builtin_ooxml(input_md, output_docx)
        message = f"{message}; fallback2: {builtin_message}"

    if not ok:
        print("[error] conversion failed")
        print(f"[hint] {message}")
        print("[hint] install one of (optional):")
        print("  - pandoc")
        print("  - python-docx (pip install python-docx)")
        return 2

    check_report = style_check(output_docx)
    check_report["conversion_message"] = message

    print("[ok] generated:", output_docx)
    print("[check]", json.dumps(check_report, ensure_ascii=False, indent=2))

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(check_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("[ok] report:", report_path)

    return 0 if check_report.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
