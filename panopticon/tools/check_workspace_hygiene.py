#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent

CORE_ROOT_FILES = {
    "AGENTS.md",
    "SOUL.md",
    "USER.md",
    "IDENTITY.md",
    "HEARTBEAT.md",
    "TOOLS.md",
    "MEMORY.md",
    "README.md",
    "RUNTIME_POLICY.md",
}

CONTRACT_DIRS = {"inbox", "outbox", "artifacts", "state", "sources", "memory", "skills"}
CLASSIFICATION_DIRS = {"docs", "media", "exports", "scripts", "runtime-assets", "staging", "archive", ".trash"}
SYSTEM_DIRS = {".openclaw", ".claude", ".release-state"}

ALLOWED_ROOT_DIRS = CONTRACT_DIRS | CLASSIFICATION_DIRS | SYSTEM_DIRS
DEFAULT_AGENTS = ["email", "growth", "health", "metrics", "nox", "personal", "trades", "writing"]

DOC_EXTENSIONS = {".md", ".mdx", ".txt", ".rst", ".mmd", ".drawio"}
MEDIA_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".mp3", ".wav", ".mp4", ".mov"}
EXPORT_EXTENSIONS = {".pdf", ".ppt", ".pptx", ".html", ".htm", ".zip", ".tar", ".gz", ".7z"}
SCRIPT_EXTENSIONS = {".py", ".sh", ".js", ".ts", ".mjs", ".cjs", ".ipynb"}
RUNTIME_EXTENSIONS = {".traineddata", ".ttf", ".otf", ".woff", ".woff2", ".whl"}
RUNTIME_FILES = {"package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "requirements.txt", "pyproject.toml"}


@dataclass
class Finding:
    agent: str
    path: str
    kind: str
    suggestion: str
    reason: str


def resolve_default_workspaces_root() -> Path:
    explicit = os.getenv("PANOPTICON_WORKSPACES_ROOT", "").strip()
    if explicit:
        return Path(explicit).expanduser()

    data_root = os.getenv("PANOPTICON_DATA_DIR", "").strip()
    if data_root:
        return Path(data_root).expanduser() / "workspaces"

    return ROOT / "workspaces"


def load_agents(manifest_path: Path | None, workspaces_root: Path) -> list[str]:
    if manifest_path and manifest_path.exists() and yaml is not None:
        try:
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("agents"), list):
                agents = []
                for item in data["agents"]:
                    if not isinstance(item, dict) or not bool(item.get("enabled", True)):
                        continue
                    slug = str(item.get("slug") or "").strip()
                    if slug:
                        agents.append(slug)
                if agents:
                    return agents
        except Exception:
            pass

    if workspaces_root.exists():
        dirs = [item.name for item in workspaces_root.iterdir() if item.is_dir() and not item.name.startswith(".")]
        if dirs:
            return sorted(dirs)

    return DEFAULT_AGENTS


def suggest_for_file(path: Path) -> tuple[str, str]:
    name = path.name
    lower = name.lower()
    suffix = path.suffix.lower()

    if lower in RUNTIME_FILES:
        return "runtime-assets/", "runtime/dependency metadata"
    if suffix in DOC_EXTENSIONS:
        return "docs/", f"document extension {suffix}"
    if suffix in MEDIA_EXTENSIONS:
        return "media/", f"media extension {suffix}"
    if suffix in EXPORT_EXTENSIONS:
        return "exports/", f"deliverable/export extension {suffix}"
    if suffix in SCRIPT_EXTENSIONS:
        return "scripts/", f"script/helper extension {suffix}"
    if suffix in RUNTIME_EXTENSIONS:
        return "runtime-assets/", f"runtime asset extension {suffix}"
    if suffix == ".log":
        return "staging/", "log file"
    if any(token in lower for token in ("tmp", "temp", "draft", "scratch", "test")):
        return "staging/", "temporary-looking name"
    return "staging/", "unknown root file"


def suggest_for_dir(path: Path) -> tuple[str, str]:
    name = path.name
    lower = name.lower()

    if lower in {"tmp", "temp", "cache", ".cache"}:
        return "staging/", "temporary/cache directory"
    if "venv" in lower or lower in {"node_modules", "dist", "build"}:
        return "runtime-assets/", "runtime/dependency directory"
    if lower in {"slides", "drafts", "notes"}:
        return "docs/", "draft/document source directory"
    if "thumbnail" in lower or lower in {"images", "screenshots"}:
        return "media/", "media directory"
    if "ppt" in lower or "output" in lower or "export" in lower:
        return "exports/", "output/export directory"
    if "backup" in lower or "disabled" in lower or lower.startswith("old"):
        return "archive/", "backup/archive-looking directory"
    return "archive/", "unknown root directory"


def scan_workspace(agent: str, workspace: Path, ensure_dirs: bool) -> list[Finding]:
    findings: list[Finding] = []

    if not workspace.exists():
        findings.append(
            Finding(agent, str(workspace), "missing_workspace", "create workspace", "workspace directory is missing")
        )
        return findings

    if ensure_dirs:
        for directory in sorted(CLASSIFICATION_DIRS):
            (workspace / directory).mkdir(parents=True, exist_ok=True)

    for item in sorted(workspace.iterdir(), key=lambda p: p.name.lower()):
        if item.is_file():
            if item.name in CORE_ROOT_FILES:
                continue
            suggestion, reason = suggest_for_file(item)
            findings.append(Finding(agent, item.name, "root_file", suggestion, reason))
        elif item.is_dir():
            if item.name in ALLOWED_ROOT_DIRS:
                continue
            suggestion, reason = suggest_for_dir(item)
            findings.append(Finding(agent, item.name + "/", "root_dir", suggestion, reason))
        else:
            findings.append(Finding(agent, item.name, "root_other", "staging/", "non-file non-directory root entry"))

    return findings


def as_dict(finding: Finding) -> dict[str, str]:
    return {
        "agent": finding.agent,
        "path": finding.path,
        "kind": finding.kind,
        "suggestion": finding.suggestion,
        "reason": finding.reason,
    }


def print_text_report(findings: list[Finding]) -> None:
    if not findings:
        print("Workspace hygiene: OK (no stray root entries found)")
        return

    print(f"Workspace hygiene: {len(findings)} stray root entr{'y' if len(findings) == 1 else 'ies'} found")
    current_agent = None
    for finding in findings:
        if finding.agent != current_agent:
            current_agent = finding.agent
            print(f"\n[{current_agent}]")
        print(f"- {finding.path} -> {finding.suggestion} ({finding.reason})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Report loose root files in Panopticon workspaces.")
    parser.add_argument("--workspaces-root", default=str(resolve_default_workspaces_root()))
    parser.add_argument("--manifest", default=str(ROOT / "agents.manifest.yaml"))
    parser.add_argument("--agent", action="append", default=[], help="Limit to one agent; may be repeated")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument("--ensure-dirs", action="store_true", help="Create classification folders if missing")
    parser.add_argument("--fail-on-stray", action="store_true", help="Exit 1 when stray root entries are found")
    args = parser.parse_args()

    workspaces_root = Path(args.workspaces_root).expanduser()
    manifest_path = Path(args.manifest).expanduser() if args.manifest else None
    agents = args.agent or load_agents(manifest_path, workspaces_root)

    findings: list[Finding] = []
    for agent in agents:
        findings.extend(scan_workspace(agent, workspaces_root / agent, ensure_dirs=args.ensure_dirs))

    if args.json:
        print(json.dumps({"findings": [as_dict(item) for item in findings]}, ensure_ascii=False, indent=2))
    else:
        print_text_report(findings)

    return 1 if args.fail_on_stray and findings else 0


if __name__ == "__main__":
    raise SystemExit(main())