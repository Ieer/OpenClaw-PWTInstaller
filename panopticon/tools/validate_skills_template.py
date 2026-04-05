from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GLOBAL_SKILLS_DIR = ROOT / "global-skills"
DEFAULT_WORKSPACES_DIR = ROOT / "workspaces"

GLOBAL_TEMPLATE_REQUIREMENTS = {
    "use guidance": (
        "## Use Cases",
        "## Use When",
        "## When to Use",
        "## When to Use This Skill",
    ),
    "execution guidance": (
        "## Run",
        "## Workflow",
        "## Quick Start",
        "## Quick Reference",
    ),
    "output contract": ("## Outputs", "## Output", "## Deliverables"),
    "safety or operating constraints": (
        "## Safety",
        "## Safety Rules",
        "## Execution Rules",
        "## Notes",
    ),
}

WORKSPACE_TEMPLATE_HEADERS = (
    "## Trigger",
    "## Steps",
    "## Output",
    "## Review Gate",
)

WORKSPACE_KNOWLEDGE_EVAL_SCRIPT = "scripts/run_eval_artifact.py"
WORKSPACE_KNOWLEDGE_EVAL_OUTPUTS = (
    "artifacts/<task_id>/artifact.md",
    "artifacts/<task_id>/artifact.json",
    "sources/<task_id>/resolve-response.json",
)


def find_global_skill_files(skills_dir: Path) -> list[Path]:
    return sorted(path for path in skills_dir.glob("*/SKILL.md") if path.is_file())


def find_workspace_skill_files(workspaces_dir: Path) -> list[Path]:
    return sorted(
        path for path in workspaces_dir.glob("*/skills/*/SKILL.md") if path.is_file()
    )


def extract_sections(content: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_header: str | None = None
    for line in content.splitlines():
        if line.startswith("## "):
            current_header = line.strip()
            sections.setdefault(current_header, [])
            continue
        if current_header is not None:
            sections[current_header].append(line)
    return {header: "\n".join(lines).strip() for header, lines in sections.items()}


def detect_template_type(path: Path, content: str) -> str:
    workspace_hits = sum(header in content for header in WORKSPACE_TEMPLATE_HEADERS)
    if workspace_hits >= 2 or "## Trigger" in content or "## Review Gate" in content:
        return "workspace"
    if "workspaces" in path.parts:
        return "workspace-legacy"
    return "global"


def validate_global_template(path: Path, content: str) -> list[str]:
    errors: list[str] = []
    rel = path.relative_to(ROOT)
    for label, alternatives in GLOBAL_TEMPLATE_REQUIREMENTS.items():
        if not any(token in content for token in alternatives):
            choices = ", ".join(alternatives)
            errors.append(f"{rel}: missing {label} (expected one of: {choices})")
    return errors


def validate_workspace_template(path: Path, content: str, sections: dict[str, str]) -> list[str]:
    errors: list[str] = []
    rel = path.relative_to(ROOT)

    for header in WORKSPACE_TEMPLATE_HEADERS:
        if header not in content:
            errors.append(f"{rel}: missing workspace section {header}")

    if path.parent.name == "knowledge-eval":
        script_path = path.parent / "scripts" / "run_eval_artifact.py"
        if not script_path.is_file():
            errors.append(
                f"{rel}: missing required script {script_path.relative_to(ROOT)}"
            )

        steps_section = sections.get("## Steps", "")
        if WORKSPACE_KNOWLEDGE_EVAL_SCRIPT not in steps_section:
            errors.append(
                f"{rel}: Steps must reference {WORKSPACE_KNOWLEDGE_EVAL_SCRIPT}"
            )

        output_section = sections.get("## Output", "")
        for expected_output in WORKSPACE_KNOWLEDGE_EVAL_OUTPUTS:
            if expected_output not in output_section:
                errors.append(
                    f"{rel}: Output must include {expected_output}"
                )

    return errors


def validate_skill_file(path: Path) -> tuple[str, list[str]]:
    content = path.read_text(encoding="utf-8")
    template_type = detect_template_type(path, content)
    sections = extract_sections(content)

    if template_type == "workspace":
        return template_type, validate_workspace_template(path, content, sections)
    return template_type, validate_global_template(path, content)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Panopticon global skills and workspace-local skills against "
            "their minimum documentation contracts"
        )
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=None,
        help=(
            "Deprecated legacy alias for validating a single skills directory only; "
            "if set, workspace scanning is skipped"
        ),
    )
    parser.add_argument(
        "--global-skills-dir",
        type=Path,
        default=DEFAULT_GLOBAL_SKILLS_DIR,
        help="Path to global skills directory (default: panopticon/global-skills)",
    )
    parser.add_argument(
        "--workspaces-dir",
        type=Path,
        default=DEFAULT_WORKSPACES_DIR,
        help="Path to workspaces directory (default: panopticon/workspaces)",
    )
    args = parser.parse_args()

    errors: list[str] = []
    skill_files: list[Path] = []

    if args.skills_dir is not None:
        skills_dir = args.skills_dir.resolve()
        if not skills_dir.exists() or not skills_dir.is_dir():
            print(f"Validation failed:\n- skills directory not found: {skills_dir}")
            return 1
        skill_files = find_global_skill_files(skills_dir)
        if not skill_files:
            print(f"Validation failed:\n- no SKILL.md files found under: {skills_dir}")
            return 1
    else:
        global_skills_dir = args.global_skills_dir.resolve()
        workspaces_dir = args.workspaces_dir.resolve()

        if not global_skills_dir.exists() or not global_skills_dir.is_dir():
            errors.append(f"global skills directory not found: {global_skills_dir}")
        if not workspaces_dir.exists() or not workspaces_dir.is_dir():
            errors.append(f"workspaces directory not found: {workspaces_dir}")
        if errors:
            print("Validation failed:")
            for item in errors:
                print(f"- {item}")
            return 1

        skill_files.extend(find_global_skill_files(global_skills_dir))
        skill_files.extend(find_workspace_skill_files(workspaces_dir))

        if not skill_files:
            print(
                "Validation failed:\n"
                f"- no SKILL.md files found under: {global_skills_dir}\n"
                f"- no SKILL.md files found under: {workspaces_dir}"
            )
            return 1

    template_counts = {"global": 0, "workspace": 0, "workspace-legacy": 0}
    for skill_file in skill_files:
        template_type, file_errors = validate_skill_file(skill_file)
        template_counts[template_type] = template_counts.get(template_type, 0) + 1
        errors.extend(file_errors)

    if errors:
        print("Validation failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    checked_roots: list[str] = []
    if args.skills_dir is not None:
        checked_roots.append(args.skills_dir.resolve().relative_to(ROOT).as_posix())
    else:
        checked_roots.append(args.global_skills_dir.resolve().relative_to(ROOT).as_posix())
        checked_roots.append(args.workspaces_dir.resolve().relative_to(ROOT).as_posix())

    print(
        "Validation passed. "
        f"Checked {len(skill_files)} SKILL.md files across {', '.join(checked_roots)} "
        f"(global-style: {template_counts['global'] + template_counts['workspace-legacy']}, "
        f"workspace-contract: {template_counts['workspace']})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
