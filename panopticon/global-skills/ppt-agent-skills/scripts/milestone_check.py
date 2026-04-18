#!/usr/bin/env python3
"""Milestone checker for the PPT workflow.

Usage examples:
  python3 scripts/milestone_check.py 0
  python3 scripts/milestone_check.py 3.5
  python3 scripts/milestone_check.py 4
  python3 scripts/milestone_check.py preview
  python3 scripts/milestone_check.py 5 --output-dir /path/to/ppt-output
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from planning_validator import load_planning_pages
from speech_script import load_speech_page_entries


STAGE_ORDER = ("0", "1", "2", "3", "3.5", "4", "preview", "5")
STAGE_ALIAS = {
    "0": "0",
    "step0": "0",
    "step_0": "0",
    "step-0": "0",
    "1": "1",
    "step1": "1",
    "step_1": "1",
    "step-1": "1",
    "2": "2",
    "step2": "2",
    "step_2": "2",
    "step-2": "2",
    "3": "3",
    "step3": "3",
    "step_3": "3",
    "step-3": "3",
    "3.5": "3.5",
    "step3.5": "3.5",
    "step_3.5": "3.5",
    "step-3.5": "3.5",
    "4": "4",
    "step4": "4",
    "step_4": "4",
    "step-4": "4",
    "preview": "preview",
    "steppreview": "preview",
    "step_preview": "preview",
    "step-preview": "preview",
    "5": "5",
    "step5": "5",
    "step_5": "5",
    "step-5": "5",
}


def natural_sort_key(path: Path) -> tuple[object, ...]:
    parts = re.split(r"(\d+)", path.name)
    key: list[object] = []
    for part in parts:
        key.append(int(part) if part.isdigit() else part.lower())
    return tuple(key)


class Checker:
    def __init__(self, skill_dir: Path, output_dir: Path, target: str, quiet: bool = False):
        self.skill_dir = skill_dir
        self.output_dir = output_dir
        self.target = target
        self.target_idx = STAGE_ORDER.index(target)
        self.python = sys.executable or "python3"
        self.quiet = quiet
        self.pages: int | None = None

    def reached(self, stage: str) -> bool:
        return self.target_idx >= STAGE_ORDER.index(stage)

    def echo(self, message: str) -> None:
        if not self.quiet:
            print(message)

    def fail(self, message: str) -> None:
        raise RuntimeError(message)

    def must_file(self, path: Path) -> None:
        if not path.is_file():
            self.fail(f"missing file: {path}")

    def must_dir(self, path: Path) -> None:
        if not path.is_dir():
            self.fail(f"missing dir: {path}")

    def run_cmd(self, cmd: list[str], title: str) -> None:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            return
        details: list[str] = [f"{title} failed: {' '.join(cmd)}"]
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        if out:
            details.append(f"stdout:\n{out}")
        if err:
            details.append(f"stderr:\n{err}")
        self.fail("\n".join(details))

    def latest(self, pattern: str) -> Path:
        matches = sorted(self.output_dir.glob(pattern), key=natural_sort_key)
        if not matches:
            self.fail(f"missing {pattern} in {self.output_dir}")
        return matches[-1]

    def check_step0(self) -> None:
        self.echo("== Step 0 ==")
        self.echo("[OK] step 0")

    def check_step1(self) -> None:
        self.echo("== Step 1 ==")
        interview = self.output_dir / "interview-qa.txt"
        requirements = self.output_dir / "requirements-interview.txt"
        self.must_file(interview)
        self.must_file(requirements)
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "interview",
                str(interview),
            ],
            "contract_validator interview",
        )
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "requirements-interview",
                str(requirements),
            ],
            "contract_validator requirements-interview",
        )
        self.echo("[OK] step 1")

    def check_step2(self) -> None:
        self.echo("== Step 2 ==")
        search = self.output_dir / "search.txt"
        search_brief = self.output_dir / "search-brief.txt"
        source_brief = self.output_dir / "source-brief.txt"

        if search.is_file() and search_brief.is_file():
            # harness 执行证据
            self.must_file(self.output_dir / "runtime" / "prompt-research-synth.md")
            self.run_cmd(
                [
                    self.python,
                    str(self.skill_dir / "scripts/contract_validator.py"),
                    "search",
                    str(search),
                ],
                "contract_validator search",
            )
            self.run_cmd(
                [
                    self.python,
                    str(self.skill_dir / "scripts/contract_validator.py"),
                    "search-brief",
                    str(search_brief),
                ],
                "contract_validator search-brief",
            )
        elif source_brief.is_file():
            self.run_cmd(
                [
                    self.python,
                    str(self.skill_dir / "scripts/contract_validator.py"),
                    "source-brief",
                    str(source_brief),
                ],
                "contract_validator source-brief",
            )
        else:
            self.fail(
                "missing step 2 artifacts: expected search.txt + search-brief.txt "
                "or source-brief.txt"
            )
        self.echo("[OK] step 2")

    def check_step3(self) -> None:
        self.echo("== Step 3 ==")
        # harness 执行证据
        self.must_file(self.output_dir / "runtime" / "prompt-outline.md")
        outline = self.output_dir / "outline.txt"
        self.must_file(outline)
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "outline",
                str(outline),
            ],
            "contract_validator outline",
        )
        self.echo("[OK] step 3")

    def check_step4(self) -> None:
        self.echo("== Step 4 ==")
        images_dir = self.output_dir / "images"
        planning_dir = self.output_dir / "planning"
        slides_dir = self.output_dir / "slides"
        png_dir = self.output_dir / "png"
        runtime_dir = self.output_dir / "runtime"
        self.must_dir(planning_dir)
        # harness 执行证据：每页必须有对应的 runtime prompt
        pages = load_planning_pages(planning_dir)
        if pages:
            for i in range(1, len(pages) + 1):
                self.must_file(runtime_dir / f"prompt-page-{i}.md")
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/planning_validator.py"),
                str(planning_dir),
                "--refs",
                str(self.skill_dir / "references"),
            ],
            "planning_validator",
        )
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "images",
                str(planning_dir),
            ],
            "contract_validator images (step4)",
        )
        pages = load_planning_pages(planning_dir)
        if not pages:
            self.fail("planning pages must be > 0")
        self.pages = len(pages)
        needs_external_images = any(
            isinstance(card, dict)
            and isinstance(card.get("image"), dict)
            and bool(card.get("image", {}).get("needed"))
            for page in pages
            for card in (page.get("cards") if isinstance(page.get("cards"), list) else [])
        )
        if needs_external_images:
            self.must_dir(images_dir)
            self.run_cmd(
                [
                    self.python,
                    str(self.skill_dir / "scripts/contract_validator.py"),
                    "images",
                    str(planning_dir),
                    "--require-paths",
                ],
                "contract_validator images --require-paths",
            )

        self.must_dir(slides_dir)
        self.must_dir(png_dir)
        slides = sorted(slides_dir.glob("slide-*.html"), key=natural_sort_key)
        pngs = sorted(png_dir.glob("slide-*.png"), key=natural_sort_key)
        if len(slides) != self.pages:
            self.fail(f"slide count={len(slides)} != planning pages={self.pages}")
        if len(pngs) != self.pages:
            self.fail(f"png count={len(pngs)} != planning pages={self.pages}")
        self.echo(f"[OK] step 4 (pages={self.pages})")

    def ensure_pages(self) -> int:
        if self.pages is not None:
            return self.pages
        planning_dir = self.output_dir / "planning"
        self.must_dir(planning_dir)
        pages = load_planning_pages(planning_dir)
        if not pages:
            self.fail("planning pages must be > 0")
        self.pages = len(pages)
        return self.pages

    def check_step35(self) -> None:
        self.echo("== Step 3.5 ==")
        # harness 执行证据
        self.must_file(self.output_dir / "runtime" / "prompt-style.md")
        style = self.output_dir / "style.json"
        self.must_file(style)
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "style",
                str(style),
            ],
            "contract_validator style",
        )
        self.echo("[OK] step 3.5")

    def check_preview(self) -> None:
        self.echo("== Preview ==")
        self.must_file(self.output_dir / "preview.html")
        self.echo("[OK] preview")

    def check_step5(self) -> None:
        self.echo("== Step 5 ==")
        pages = self.ensure_pages()
        png_dir = self.output_dir / "png"
        svg_dir = self.output_dir / "svg"
        speech_script_json = self.output_dir / "speech-script.json"
        speech_script_md = self.output_dir / "speech-script.md"
        manifest = self.output_dir / "delivery-manifest.json"
        svg_export_report = self.output_dir / "svg-export-report.json"
        svg_pptx_report = self.output_dir / "presentation-svg.report.json"
        png_pptx_inspection = self.output_dir / "presentation-png.inspect.json"
        svg_pptx_inspection = self.output_dir / "presentation-svg.inspect.json"

        self.must_file(self.output_dir / "runtime" / "prompt-speech-orchestrator.md")
        self.must_file(self.output_dir / "preview.html")
        self.must_dir(png_dir)
        self.must_dir(svg_dir)
        self.must_file(speech_script_json)
        self.must_file(speech_script_md)
        self.must_file(self.output_dir / "presentation-png.pptx")
        self.must_file(self.output_dir / "presentation-svg.pptx")
        self.must_file(manifest)
        self.must_file(svg_export_report)
        self.must_file(svg_pptx_report)

        try:
            pptx_report_payload = json.loads(svg_pptx_report.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pptx_report_payload = None

        pngs = sorted(png_dir.glob("slide-*.png"), key=natural_sort_key)
        svgs = sorted(svg_dir.glob("slide-*.svg"), key=natural_sort_key)
        if len(pngs) != pages:
            self.fail(f"png count={len(pngs)} != planning pages={pages}")
        if len(svgs) != pages:
            self.fail(f"svg count={len(svgs)} != planning pages={pages}")

        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "speech-script",
                str(speech_script_json),
                "--expected-pages",
                str(pages),
            ],
            "contract_validator speech-script",
        )
        speech_pages = load_speech_page_entries(speech_script_json, expected_pages=pages)

        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "delivery-manifest",
                str(manifest),
                "--base-dir",
                str(self.output_dir),
            ],
            "contract_validator delivery-manifest",
        )
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "svg-export-report",
                str(svg_export_report),
                "--base-dir",
                str(self.output_dir),
            ],
            "contract_validator svg-export-report",
        )
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "pptx-export-report",
                str(svg_pptx_report),
                "--base-dir",
                str(self.output_dir),
            ],
            "contract_validator pptx-export-report",
        )
        if isinstance(pptx_report_payload, dict) and pptx_report_payload.get("update_mode") == "template_update":
            summary_obj = pptx_report_payload.get("summary") if isinstance(pptx_report_payload.get("summary"), dict) else {}
            target_slides = pptx_report_payload.get("target_slide_numbers") or []
            updated_blocks = summary_obj.get("updated_blocks_total")
            removed_shapes = summary_obj.get("template_removed_shapes_total")
            self.echo(
                "[INFO] template update: "
                f"scope={pptx_report_payload.get('template_update_scope') or 'block_update'}, "
                f"target_slides={target_slides}, "
                f"updated_blocks={updated_blocks}, "
                f"removed_shapes={removed_shapes}"
            )
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/inspect_pptx.py"),
                str(self.output_dir / "presentation-png.pptx"),
                "-o",
                str(png_pptx_inspection),
            ],
            "inspect_pptx presentation-png",
        )
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "pptx-inspection",
                str(png_pptx_inspection),
                "--base-dir",
                str(self.output_dir),
            ],
            "contract_validator presentation-png inspection",
        )
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/inspect_pptx.py"),
                str(self.output_dir / "presentation-svg.pptx"),
                "--source-report",
                str(svg_pptx_report),
                "-o",
                str(svg_pptx_inspection),
            ],
            "inspect_pptx presentation-svg",
        )
        self.run_cmd(
            [
                self.python,
                str(self.skill_dir / "scripts/contract_validator.py"),
                "pptx-inspection",
                str(svg_pptx_inspection),
                "--base-dir",
                str(self.output_dir),
            ],
            "contract_validator pptx-inspection",
        )
        try:
            png_inspection_payload = json.loads(png_pptx_inspection.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            png_inspection_payload = None
        try:
            inspection_payload = json.loads(svg_pptx_inspection.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            inspection_payload = None

        def note_lookup(payload: object) -> dict[int, bool]:
            if not isinstance(payload, dict):
                return {}
            slides = payload.get("slides") if isinstance(payload.get("slides"), list) else []
            return {
                int(slide.get("slide_number")): bool(slide.get("has_notes"))
                for slide in slides
                if isinstance(slide, dict) and isinstance(slide.get("slide_number"), int)
            }

        png_note_map = note_lookup(png_inspection_payload)
        svg_note_map = note_lookup(inspection_payload)
        expected_png_note_slides = list(range(1, len(speech_pages) + 1))
        if isinstance(pptx_report_payload, dict) and pptx_report_payload.get("update_mode") == "template_update":
            expected_svg_note_slides = [
                int(number)
                for number in (pptx_report_payload.get("target_slide_numbers") or [])
                if isinstance(number, int)
            ]
            if len(expected_svg_note_slides) != len(speech_pages):
                self.fail(
                    "speech-script page count does not match template-update target slides: "
                    f"speech_pages={len(speech_pages)}, target_slides={expected_svg_note_slides}"
                )
        else:
            expected_svg_note_slides = list(range(1, len(speech_pages) + 1))

        missing_png_notes = [number for number in expected_png_note_slides if not png_note_map.get(number)]
        missing_svg_notes = [number for number in expected_svg_note_slides if not svg_note_map.get(number)]
        if missing_png_notes:
            self.fail(f"presentation-png.pptx missing speaker notes on slides: {missing_png_notes}")
        if missing_svg_notes:
            self.fail(f"presentation-svg.pptx missing speaker notes on slides: {missing_svg_notes}")
        self.echo(
            "[INFO] speaker notes: "
            f"png={len(expected_png_note_slides) - len(missing_png_notes)}/{len(expected_png_note_slides)}, "
            f"svg={len(expected_svg_note_slides) - len(missing_svg_notes)}/{len(expected_svg_note_slides)}"
        )

        summary = inspection_payload.get("summary") if isinstance(inspection_payload, dict) and isinstance(inspection_payload.get("summary"), dict) else None
        if summary is not None:
            expected_regions = summary.get("expected_rendered_chart_regions_total")
            chart_groups = summary.get("chart_group_shapes_total")
            native_charts = summary.get("native_chart_shapes_total")
            structured_hits = summary.get("structured_chart_shapes_total")
            chart_group_rate = summary.get("chart_group_hit_rate")
            structured_rate = summary.get("structured_chart_hit_rate")
            if isinstance(expected_regions, int) and expected_regions > 0:
                self.echo(
                    "[INFO] chart promotion: "
                    f"structured={structured_hits}/{expected_regions} (rate={structured_rate}), "
                    f"chart_groups={chart_groups}/{expected_regions} (rate={chart_group_rate}), "
                    f"native_charts={native_charts}"
                )
        self.echo("[OK] step 5")

    def run(self) -> None:
        required_scripts = [
            self.skill_dir / "scripts/contract_validator.py",
            self.skill_dir / "scripts/planning_validator.py",
            self.skill_dir / "scripts/inspect_pptx.py",
        ]
        for path in required_scripts:
            self.must_file(path)

        if self.reached("0"):
            self.check_step0()
        if self.reached("1"):
            self.check_step1()
        if self.reached("2"):
            self.check_step2()
        if self.reached("3"):
            self.check_step3()
        if self.reached("3.5"):
            self.check_step35()
        if self.reached("4"):
            self.check_step4()
        if self.reached("preview"):
            self.check_preview()
        if self.reached("5"):
            self.check_step5()

        self.echo("[PASS] milestone checks passed")


def normalize_stage(raw: str) -> str:
    key = raw.strip().lower().replace(" ", "")
    stage = STAGE_ALIAS.get(key)
    if not stage:
        raise ValueError(f"unsupported stage: {raw!r}; expected one of {STAGE_ORDER}")
    return stage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run milestone acceptance checks for the PPT workflow")
    parser.add_argument("stage", help="Milestone target: 0/1/2/3/3.5/4/preview/5")
    parser.add_argument(
        "--skill-dir",
        default=str(Path(__file__).resolve().parent.parent),
        help="Skill root directory (default: auto-detected from this script)",
    )
    parser.add_argument(
        "--output-dir",
        default="ppt-output",
        help="Workflow output directory (default: ./ppt-output)",
    )
    parser.add_argument("--quiet", action="store_true", help="Only print failures")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        target = normalize_stage(args.stage)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    skill_dir = Path(args.skill_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    checker = Checker(skill_dir=skill_dir, output_dir=output_dir, target=target, quiet=bool(args.quiet))
    try:
        checker.run()
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
