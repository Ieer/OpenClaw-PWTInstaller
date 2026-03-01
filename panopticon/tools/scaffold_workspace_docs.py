#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_DIR = ROOT / "templates" / "workspace-skeleton"
DEFAULT_WORKSPACES_DIR = ROOT / "workspaces"
REQUIRED_DIRS = ["inbox", "outbox", "artifacts", "state", "sources"]


def build_replacements(args: argparse.Namespace) -> dict[str, str]:
    today = dt.date.today().isoformat()
    agent = args.agent.strip()
    return {
        "{{AGENT_SLUG}}": agent,
        "{{IDENTITY_NAME}}": args.identity_name or f"{agent.title()} Assistant",
        "{{IDENTITY_CREATURE}}": args.identity_creature or "Ghost in the machine",
        "{{IDENTITY_VIBE}}": args.identity_vibe or "Calm, precise, and helpful",
        "{{IDENTITY_EMOJI}}": args.identity_emoji or "🧠",
        "{{IDENTITY_AVATAR}}": args.identity_avatar or f"avatars/{agent}.png",
        "{{TODAY}}": today,
    }


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".txt", ".json", ".yaml", ".yml"}


def render_text(content: str, replacements: dict[str, str]) -> str:
    output = content
    for key, value in replacements.items():
        output = output.replace(key, value)
    return output


def target_for(src_rel: Path, target_dir: Path, replacements: dict[str, str]) -> Path:
    destination = target_dir / src_rel
    if src_rel.name == "YYYY-MM-DD.md":
        return destination.with_name(f"{replacements['{{TODAY}}']}.md")
    return destination


def copy_tree(
    template_dir: Path,
    target_dir: Path,
    replacements: dict[str, str],
    force: bool,
    dry_run: bool,
) -> tuple[int, int, int]:
    created = 0
    overwritten = 0
    skipped = 0

    for source in template_dir.rglob("*"):
        relative_path = source.relative_to(template_dir)
        destination = target_for(relative_path, target_dir, replacements)

        if source.is_dir():
            if not dry_run:
                destination.mkdir(parents=True, exist_ok=True)
            continue

        exists_before = destination.exists()
        if exists_before and not force:
            skipped += 1
            continue

        if dry_run:
            if exists_before:
                overwritten += 1
            else:
                created += 1
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)

        if is_text_file(source):
            rendered = render_text(source.read_text(encoding="utf-8"), replacements)
            destination.write_text(rendered, encoding="utf-8")
        else:
            shutil.copy2(source, destination)

        if exists_before:
            overwritten += 1
        else:
            created += 1

    return created, overwritten, skipped


def ensure_contract_dirs(target_dir: Path, dry_run: bool) -> int:
    created = 0
    for name in REQUIRED_DIRS:
        path = target_dir / name
        if path.exists():
            continue
        if not dry_run:
            path.mkdir(parents=True, exist_ok=True)
        created += 1
    return created


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scaffold workspace docs from panopticon workspace skeleton template."
    )
    parser.add_argument("--agent", required=True, help="Agent slug, e.g. email/growth/nox")
    parser.add_argument(
        "--template-dir",
        type=Path,
        default=DEFAULT_TEMPLATE_DIR,
        help=f"Template directory (default: {DEFAULT_TEMPLATE_DIR})",
    )
    parser.add_argument(
        "--workspaces-dir",
        type=Path,
        default=DEFAULT_WORKSPACES_DIR,
        help=f"Workspace root (default: {DEFAULT_WORKSPACES_DIR})",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")

    parser.add_argument("--identity-name", default="", help="Override identity name")
    parser.add_argument("--identity-creature", default="", help="Override identity creature")
    parser.add_argument("--identity-vibe", default="", help="Override identity vibe")
    parser.add_argument("--identity-emoji", default="", help="Override identity emoji")
    parser.add_argument("--identity-avatar", default="", help="Override identity avatar")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    template_dir = args.template_dir.resolve()

    if not template_dir.exists() or not template_dir.is_dir():
        raise SystemExit(f"Template directory not found: {template_dir}")

    agent = args.agent.strip()
    if not agent:
        raise SystemExit("--agent must be non-empty")

    target_dir = args.workspaces_dir.resolve() / agent
    replacements = build_replacements(args)

    created, overwritten, skipped = copy_tree(
        template_dir=template_dir,
        target_dir=target_dir,
        replacements=replacements,
        force=args.force,
        dry_run=args.dry_run,
    )
    created_dirs = ensure_contract_dirs(target_dir=target_dir, dry_run=args.dry_run)
    created += created_dirs

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(f"[{mode}] workspace={target_dir}")
    print(f"created={created} overwritten={overwritten} skipped={skipped}")


if __name__ == "__main__":
    main()
