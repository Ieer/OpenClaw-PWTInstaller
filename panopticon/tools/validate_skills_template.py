from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILLS_DIR = ROOT / "global-skills"

REQUIRED_SECTIONS = [
    "## Use Cases",
    "## Run",
    "## Inputs",
    "## Outputs",
    "## Safety",
    "## Version",
]


def find_skill_files(skills_dir: Path) -> list[Path]:
    return sorted(path for path in skills_dir.glob("*/SKILL.md") if path.is_file())


def validate_skill_file(path: Path) -> list[str]:
    content = path.read_text(encoding="utf-8")
    missing: list[str] = []
    for header in REQUIRED_SECTIONS:
        if header not in content:
            missing.append(header)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate global skill SKILL.md files for required template sections"
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=DEFAULT_SKILLS_DIR,
        help="Path to global skills directory (default: panopticon/global-skills)",
    )
    args = parser.parse_args()

    skills_dir = args.skills_dir.resolve()
    if not skills_dir.exists() or not skills_dir.is_dir():
        print(f"Validation failed:\n- skills directory not found: {skills_dir}")
        return 1

    skill_files = find_skill_files(skills_dir)
    if not skill_files:
        print(f"Validation failed:\n- no SKILL.md files found under: {skills_dir}")
        return 1

    errors: list[str] = []
    for skill_file in skill_files:
        missing = validate_skill_file(skill_file)
        if missing:
            rel = skill_file.relative_to(ROOT)
            for section in missing:
                errors.append(f"{rel}: missing section {section}")

    if errors:
        print("Validation failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    print(
        f"Validation passed. Checked {len(skill_files)} SKILL.md files under {skills_dir.relative_to(ROOT)}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
