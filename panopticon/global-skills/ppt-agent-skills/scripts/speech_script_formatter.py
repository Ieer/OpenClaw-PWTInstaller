#!/usr/bin/env python3
"""Render speech-script.json into a readable Markdown script."""

from __future__ import annotations

import argparse
from pathlib import Path

from speech_script import load_speech_script_payload, render_speech_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Render speech-script.json into Markdown")
    parser.add_argument("speech_script", help="Path to speech-script.json")
    parser.add_argument("-o", "--output", default=None, help="Path to write speech-script.md")
    args = parser.parse_args()

    source_path = Path(args.speech_script).resolve()
    if not source_path.exists():
        raise SystemExit(f"ERROR: path not found: {source_path}")

    payload = load_speech_script_payload(source_path)
    rendered = render_speech_markdown(payload)
    output_path = Path(args.output).resolve() if args.output else source_path.with_suffix(".md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    print(f"Saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())