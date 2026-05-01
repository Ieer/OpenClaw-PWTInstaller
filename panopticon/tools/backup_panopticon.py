#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
PANOPTICON_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_ROOT = PANOPTICON_DIR / "backups"
DEFAULT_COMPOSE_FILE = PANOPTICON_DIR / "docker-compose.panopticon.yml"
DEFAULT_DOTENV_FILE = PANOPTICON_DIR / ".env"
RELEASE_FILE = REPO_ROOT / "openclaw-release.yaml"
MANIFEST_FILE = PANOPTICON_DIR / "agents.manifest.yaml"

POSTGRES_CONTAINER = "mc-postgres"
POSTGRES_USER = "mission_control"
POSTGRES_DB = "mission_control"
REDIS_CONTAINER = "mc-redis"

EXCLUDE_PATTERNS = [
    "**/.cache/**",
    "**/Cache/**",
    "**/Code Cache/**",
    "**/GPUCache/**",
    "**/tmp/**",
    "**/temp/**",
    "**/node_modules/**",
    "**/venv/**",
    "**/.venv/**",
    "**/extensions/**",
    "**/*.sock",
    "**/*.pid",
    "**/*.lock",
    "**/SingletonLock",
    "**/SingletonSocket",
    "**/SingletonCookie",
    "**/.workspace_contract_probe.tmp",
    "**/.DS_Store",
]

RESTIC_EXCLUDE_PATTERNS = [
    ".cache/**",
    "Cache/**",
    "Code Cache/**",
    "GPUCache/**",
    "tmp/**",
    "temp/**",
    "node_modules/**",
    "venv/**",
    ".venv/**",
    "extensions/**",
    "*.sock",
    "*.pid",
    "*.lock",
    "SingletonLock",
    "SingletonSocket",
    "SingletonCookie",
    ".workspace_contract_probe.tmp",
    ".DS_Store",
]

SENSITIVE_KEY_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH")


@dataclasses.dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    skipped: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def to_report(self) -> dict[str, Any]:
        return {
            "command": redact_command(self.command),
            "returncode": self.returncode,
            "stdout_tail": self.stdout[-4000:],
            "stderr_tail": self.stderr[-4000:],
            "skipped": self.skipped,
        }


@dataclasses.dataclass
class FileEntry:
    path: Path
    arcname: str
    required: bool = False


@dataclasses.dataclass
class BackupContext:
    backup_root: Path
    restic_repo: Path
    run_id: str
    run_dir: Path
    staging_dir: Path
    reports_dir: Path
    data_dir: Path
    usb_host_path: Path
    knowledge_raw_sources_path: Path
    env_values: dict[str, str]
    compose_file: Path = DEFAULT_COMPOSE_FILE
    dotenv_file: Path = DEFAULT_DOTENV_FILE

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "BackupContext":
        dotenv_file = Path(args.dotenv_file).expanduser().resolve()
        env_values = load_env_file(dotenv_file)
        panopticon_dir = Path(args.panopticon_dir).expanduser().resolve()
        data_dir = resolve_bind_path(
            panopticon_dir,
            args.data_dir or env_values.get("PANOPTICON_DATA_DIR", ""),
            ".",
        )
        usb_host_path = resolve_bind_path(
            panopticon_dir,
            args.usb_host_path or env_values.get("PANOPTICON_USB_HOST_PATH", ""),
            "shared-usb",
        )
        knowledge_raw_sources_path = resolve_bind_path(
            panopticon_dir,
            args.knowledge_raw_sources_path or env_values.get("PANOPTICON_KNOWLEDGE_RAW_SOURCES_PATH", ""),
            "mission-control/knowledge-sources",
        )
        backup_root = Path(args.backup_root).expanduser().resolve()
        restic_repo = Path(args.restic_repo).expanduser().resolve() if args.restic_repo else backup_root / "restic-repo"
        run_id = args.run_id or make_run_id(args.kind)
        run_dir = backup_root / "runs" / run_id
        staging_dir = run_dir / "staging"
        reports_dir = panopticon_dir / "reports" / "backup-runs"
        return cls(
            backup_root=backup_root,
            restic_repo=restic_repo,
            run_id=run_id,
            run_dir=run_dir,
            staging_dir=staging_dir,
            reports_dir=reports_dir,
            data_dir=data_dir,
            usb_host_path=usb_host_path,
            knowledge_raw_sources_path=knowledge_raw_sources_path,
            env_values=env_values,
            compose_file=Path(args.compose_file).expanduser().resolve(),
            dotenv_file=dotenv_file,
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id(kind: str) -> str:
    safe_kind = kind.replace("_", "-")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{socket.gethostname()}-{safe_kind}"


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = strip_inline_comment(value.strip())
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def strip_inline_comment(value: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    out: list[str] = []
    for char in value:
        if escaped:
            out.append(char)
            escaped = False
            continue
        if char == "\\" and in_double:
            out.append(char)
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            out.append(char)
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            out.append(char)
            continue
        if char == "#" and not in_single and not in_double:
            break
        out.append(char)
    return "".join(out).strip()


def resolve_bind_path(base: Path, raw_value: str, fallback_relative: str) -> Path:
    raw = str(raw_value or "").strip()
    candidate = Path(raw).expanduser() if raw else base / fallback_relative
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve()


def command_available(name: str) -> bool:
    return shutil.which(name) is not None


def redact_command(command: list[str]) -> list[str]:
    redacted: list[str] = []
    skip_next = False
    sensitive_options = {"--password", "--auth-token", "--token"}
    for item in command:
        if skip_next:
            redacted.append("<redacted>")
            skip_next = False
            continue
        lowered = item.lower()
        if lowered in sensitive_options:
            redacted.append(item)
            skip_next = True
            continue
        if any(hint.lower() in lowered for hint in SENSITIVE_KEY_HINTS) and "=" in item:
            key, _ = item.split("=", 1)
            redacted.append(f"{key}=<redacted>")
            continue
        redacted.append(item)
    return redacted


def run_command(
    command: list[str],
    *,
    cwd: Path = REPO_ROOT,
    dry_run: bool = False,
    env: dict[str, str] | None = None,
    stdout_path: Path | None = None,
    check: bool = True,
) -> CommandResult:
    if dry_run:
        print("[DRY-RUN]", " ".join(redact_command(command)))
        return CommandResult(command=command, returncode=0, skipped=True)

    print("[RUN]", " ".join(redact_command(command)))
    if stdout_path is not None:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        with stdout_path.open("wb") as stdout_file:
            proc = subprocess.run(
                command,
                cwd=str(cwd),
                env=env,
                stdout=stdout_file,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        result = CommandResult(command=command, returncode=proc.returncode, stderr=proc.stderr or "")
    else:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        result = CommandResult(
            command=command,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )

    if check and not result.ok:
        raise RuntimeError(
            "command failed: "
            + " ".join(redact_command(command))
            + f"\nreturncode={result.returncode}\n{result.stderr[-2000:]}"
        )
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def maybe_sha256(path: Path) -> str | None:
    if path.exists() and path.is_file():
        return sha256_file(path)
    return None


def load_release_version() -> str | None:
    if not RELEASE_FILE.exists():
        return None
    for line in RELEASE_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().startswith("openclaw_version:"):
            return line.split(":", 1)[1].strip().strip("'\"") or None
    return None


def capture_command_text(command: list[str], timeout: float = 5.0) -> str | None:
    if not command_available(command[0]):
        return None
    try:
        proc = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception:
        return None
    text = (proc.stdout or proc.stderr or "").strip()
    return text[:2000] if text else None


def git_head() -> str | None:
    return capture_command_text(["git", "rev-parse", "HEAD"])


def env_file_inventory(env_dir: Path) -> list[dict[str, Any]]:
    if not env_dir.exists():
        return []
    out = []
    for path in sorted(env_dir.glob("*.env*")):
        if not path.is_file():
            continue
        values = load_env_file(path)
        out.append(
            {
                "name": path.name,
                "sha256": maybe_sha256(path),
                "keys": sorted(values.keys()),
                "sensitive_key_count": sum(1 for key in values if any(hint in key.upper() for hint in SENSITIVE_KEY_HINTS)),
            }
        )
    return out


def fingerprint(ctx: BackupContext) -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "host": socket.gethostname(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "versions": {
            "openclaw_release": load_release_version(),
            "git_head": git_head(),
            "docker": capture_command_text(["docker", "--version"]),
            "docker_compose": capture_command_text(["docker", "compose", "version"]),
            "restic": capture_command_text(["restic", "version"]),
        },
        "paths": {
            "repo_root": str(REPO_ROOT),
            "panopticon_dir": str(PANOPTICON_DIR),
            "data_dir": str(ctx.data_dir),
            "usb_host_path": str(ctx.usb_host_path),
            "knowledge_raw_sources_path": str(ctx.knowledge_raw_sources_path),
            "backup_root": str(ctx.backup_root),
            "restic_repo": str(ctx.restic_repo),
        },
        "hashes": {
            "release_file_sha256": maybe_sha256(RELEASE_FILE),
            "agents_manifest_sha256": maybe_sha256(MANIFEST_FILE),
            "compose_sha256": maybe_sha256(ctx.compose_file),
            "dotenv_sha256": maybe_sha256(ctx.dotenv_file),
        },
        "env_files": env_file_inventory(PANOPTICON_DIR / "env"),
    }


def summarize_path(path: Path, *, max_files: int = 200_000) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "files": 0,
        "dirs": 0,
        "bytes": 0,
        "truncated": False,
    }
    if not path.exists():
        return summary
    if path.is_file():
        summary["files"] = 1
        summary["bytes"] = path.stat().st_size
        return summary
    for root, dirs, files in os.walk(path):
        root_path = Path(root)
        dirs[:] = [item for item in dirs if not is_excluded(root_path / item, path)]
        summary["dirs"] += len(dirs)
        for name in files:
            file_path = root_path / name
            if is_excluded(file_path, path):
                continue
            try:
                summary["files"] += 1
                summary["bytes"] += file_path.stat().st_size
            except OSError:
                continue
            if summary["files"] >= max_files:
                summary["truncated"] = True
                return summary
    return summary


def is_excluded(path: Path, root: Path | None = None) -> bool:
    text = path.as_posix()
    if root is not None:
        try:
            text = path.relative_to(root).as_posix()
        except ValueError:
            text = path.as_posix()
    name = path.name
    for pattern in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(text, pattern) or fnmatch.fnmatch(name, pattern):
            return True
    return False


def build_file_entries(ctx: BackupContext, *, include_redis_data: bool = False) -> list[FileEntry]:
    entries = [
        FileEntry(ctx.data_dir / "agent-homes", "data/agent-homes", required=True),
        FileEntry(ctx.data_dir / "workspaces", "data/workspaces", required=True),
        FileEntry(PANOPTICON_DIR / "env", "config/env", required=True),
        FileEntry(PANOPTICON_DIR / ".env", "config/.env", required=False),
        FileEntry(PANOPTICON_DIR / "agents.manifest.yaml", "config/agents.manifest.yaml", required=True),
        FileEntry(PANOPTICON_DIR / "global-skills", "config/global-skills", required=False),
        FileEntry(PANOPTICON_DIR / "templates", "config/templates", required=False),
        FileEntry(PANOPTICON_DIR / "reports", "config/reports", required=False),
    ]
    if ctx.knowledge_raw_sources_path.exists():
        entries.append(FileEntry(ctx.knowledge_raw_sources_path, "data/knowledge-sources", required=False))
    if include_redis_data:
        entries.append(FileEntry(ctx.data_dir / "mission-control" / "redis-data", "data/redis-data", required=False))
    return entries


def validate_required_entries(entries: list[FileEntry]) -> list[str]:
    return [f"missing required path: {entry.path}" for entry in entries if entry.required and not entry.path.exists()]


def ensure_run_dirs(ctx: BackupContext) -> None:
    ctx.backup_root.mkdir(parents=True, exist_ok=True)
    ctx.run_dir.mkdir(parents=True, exist_ok=True)
    ctx.staging_dir.mkdir(parents=True, exist_ok=True)
    ctx.reports_dir.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_run_report(ctx: BackupContext, report: dict[str, Any], *, mirror_reports: bool = True) -> None:
    report_path = ctx.run_dir / "report.json"
    write_json(report_path, report)
    if mirror_reports:
        write_json(ctx.reports_dir / f"{ctx.run_id}.json", report)


def create_postgres_dump(ctx: BackupContext, *, dry_run: bool, skip: bool) -> tuple[Path | None, CommandResult | None]:
    dump_path = ctx.staging_dir / "db" / "mission_control.dump"
    if skip:
        return None, CommandResult(["pg_dump"], returncode=0, skipped=True)
    if not command_available("docker"):
        raise RuntimeError("docker command is required for PostgreSQL logical backup")
    command = [
        "docker",
        "exec",
        POSTGRES_CONTAINER,
        "pg_dump",
        "-U",
        POSTGRES_USER,
        "-d",
        POSTGRES_DB,
        "-F",
        "c",
    ]
    result = run_command(command, dry_run=dry_run, stdout_path=dump_path, check=True)
    if not dry_run and not dump_path.exists():
        raise RuntimeError(f"PostgreSQL dump was not created: {dump_path}")
    return dump_path, result


def trigger_redis_snapshot(*, dry_run: bool, skip: bool) -> CommandResult | None:
    if skip:
        return CommandResult(["redis-cli", "BGSAVE"], returncode=0, skipped=True)
    if not command_available("docker"):
        raise RuntimeError("docker command is required for Redis snapshot")
    command = ["docker", "exec", REDIS_CONTAINER, "redis-cli", "BGSAVE"]
    return run_command(command, dry_run=dry_run, check=False)


def compose_down(ctx: BackupContext, *, dry_run: bool) -> CommandResult:
    return run_command(["docker", "compose", "-f", str(ctx.compose_file), "down"], dry_run=dry_run, check=True)


def compose_up(ctx: BackupContext, *, dry_run: bool) -> CommandResult:
    return run_command(["docker", "compose", "-f", str(ctx.compose_file), "up", "-d"], dry_run=dry_run, check=True)


def restic_env(ctx: BackupContext) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("RESTIC_REPOSITORY", str(ctx.restic_repo))
    return env


def ensure_restic_ready(ctx: BackupContext, *, init: bool, dry_run: bool) -> list[CommandResult]:
    if dry_run:
        return [CommandResult(["restic", "snapshots"], returncode=0, skipped=True)]
    if not command_available("restic"):
        raise RuntimeError("restic is not installed; install restic or run weekly-full tar backup")
    if not (os.getenv("RESTIC_PASSWORD") or os.getenv("RESTIC_PASSWORD_FILE")):
        raise RuntimeError("RESTIC_PASSWORD or RESTIC_PASSWORD_FILE must be set for encrypted restic backups")

    env = restic_env(ctx)
    results: list[CommandResult] = []
    snapshots = run_command(["restic", "snapshots"], env=env, dry_run=dry_run, check=False)
    results.append(snapshots)
    if snapshots.ok or dry_run:
        return results
    if not init:
        raise RuntimeError("restic repository is not initialized; rerun with --init-restic")
    results[-1] = CommandResult(
        command=snapshots.command,
        returncode=0,
        stdout=snapshots.stdout,
        stderr=snapshots.stderr,
        skipped=True,
    )
    ctx.restic_repo.mkdir(parents=True, exist_ok=True)
    init_result = run_command(["restic", "init"], env=env, dry_run=dry_run, check=True)
    results.append(init_result)
    return results


def restic_backup(ctx: BackupContext, entries: list[FileEntry], *, dry_run: bool, tags: list[str]) -> CommandResult:
    env = restic_env(ctx)
    paths = [str(entry.path) for entry in entries if entry.path.exists()]
    paths.append(str(ctx.staging_dir))
    command = ["restic", "backup", *paths]
    for tag in tags:
        command.extend(["--tag", tag])
    for pattern in RESTIC_EXCLUDE_PATTERNS:
        command.extend(["--exclude", pattern])
    return run_command(command, env=env, dry_run=dry_run, check=True)


def restic_check(ctx: BackupContext, *, dry_run: bool) -> CommandResult:
    return run_command(["restic", "check"], env=restic_env(ctx), dry_run=dry_run, check=True)


def restic_prune(ctx: BackupContext, args: argparse.Namespace) -> list[CommandResult]:
    ensure_restic_ready(ctx, init=False, dry_run=args.dry_run)
    forget_cmd = [
        "restic",
        "forget",
        "--keep-daily",
        str(args.keep_daily),
        "--keep-weekly",
        str(args.keep_weekly),
        "--keep-monthly",
        str(args.keep_monthly),
        "--prune",
    ]
    return [run_command(forget_cmd, env=restic_env(ctx), dry_run=args.dry_run, check=True)]


def add_to_tar(tar: tarfile.TarFile, source: Path, arcname: str, root_for_exclude: Path | None = None) -> None:
    if not source.exists():
        return
    root_for_exclude = root_for_exclude or source.parent

    def filter_member(member: tarfile.TarInfo) -> tarfile.TarInfo | None:
        member_path = Path(member.name)
        if any(fnmatch.fnmatch(member_path.as_posix(), pattern) for pattern in EXCLUDE_PATTERNS):
            return None
        return member

    if source.is_dir():
        for current_root, dirs, files in os.walk(source):
            current_path = Path(current_root)
            dirs[:] = [name for name in dirs if not is_excluded(current_path / name, root_for_exclude)]
            rel_dir = current_path.relative_to(source)
            dir_arcname = Path(arcname) / rel_dir if str(rel_dir) != "." else Path(arcname)
            tar.add(current_path, arcname=dir_arcname.as_posix(), recursive=False, filter=filter_member)
            for dirname in dirs:
                dir_path = current_path / dirname
                if not dir_path.is_symlink():
                    continue
                try:
                    rel_link = dir_path.relative_to(source)
                    tar.add(dir_path, arcname=(Path(arcname) / rel_link).as_posix(), recursive=False, filter=filter_member)
                except FileNotFoundError:
                    continue
            for name in files:
                file_path = current_path / name
                if is_excluded(file_path, root_for_exclude):
                    continue
                try:
                    rel_file = file_path.relative_to(source)
                    tar.add(file_path, arcname=(Path(arcname) / rel_file).as_posix(), recursive=False, filter=filter_member)
                except FileNotFoundError:
                    continue
    else:
        tar.add(source, arcname=arcname, recursive=False, filter=filter_member)


def create_full_tar(ctx: BackupContext, entries: list[FileEntry], *, dry_run: bool) -> Path:
    payload_path = ctx.run_dir / "payload.tar.gz"
    metadata_dir = ctx.staging_dir / "__backup_metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    write_json(metadata_dir / "fingerprint.json", fingerprint(ctx))
    entries_manifest = [
        {
            "arcname": entry.arcname,
            "path": str(entry.path),
            "required": entry.required,
            "summary": summarize_path(entry.path),
        }
        for entry in entries
    ]
    write_json(metadata_dir / "entries.json", {"entries": entries_manifest})

    if dry_run:
        print(f"[DRY-RUN] would create tar archive: {payload_path}")
        return payload_path

    with tarfile.open(payload_path, "w:gz") as tar:
        add_to_tar(tar, metadata_dir, "__backup_metadata")
        for entry in entries:
            add_to_tar(tar, entry.path, entry.arcname, entry.path.parent)
    return payload_path


def write_checksums(ctx: BackupContext, files: Iterable[Path]) -> dict[str, str]:
    checksums: dict[str, str] = {}
    lines: list[str] = []
    for path in files:
        if not path.exists() or not path.is_file():
            continue
        digest = sha256_file(path)
        checksums[path.name] = digest
        lines.append(f"{digest}  {path.name}\n")
    (ctx.run_dir / "checksums.sha256").write_text("".join(lines), encoding="utf-8")
    return checksums


def verify_checksums(backup_set: Path) -> tuple[bool, list[str]]:
    checksum_file = backup_set / "checksums.sha256"
    messages: list[str] = []
    if not checksum_file.exists():
        return False, [f"missing checksum file: {checksum_file}"]
    ok = True
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        target = backup_set / name.strip()
        if not target.exists():
            ok = False
            messages.append(f"missing checksum target: {target}")
            continue
        actual = sha256_file(target)
        if actual != digest:
            ok = False
            messages.append(f"checksum mismatch: {target.name}")
        else:
            messages.append(f"ok: {target.name}")
    return ok, messages


def verify_tar(payload_path: Path) -> tuple[bool, list[str]]:
    if not payload_path.exists():
        return False, [f"missing payload: {payload_path}"]
    try:
        with tarfile.open(payload_path, "r:gz") as tar:
            names = tar.getnames()
            required = ["__backup_metadata/fingerprint.json", "__backup_metadata/entries.json"]
            missing = [name for name in required if name not in names]
            if missing:
                return False, [f"payload missing metadata: {', '.join(missing)}"]
            return True, [f"payload entries: {len(names)}"]
    except tarfile.TarError as exc:
        return False, [f"invalid tar payload: {exc}"]


def build_base_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Panopticon 日常增量与全量冷备工具")
    parser.add_argument("--panopticon-dir", default=str(PANOPTICON_DIR), help="Panopticon 目录")
    parser.add_argument("--compose-file", default=str(DEFAULT_COMPOSE_FILE), help="docker compose 文件")
    parser.add_argument("--dotenv-file", default=str(DEFAULT_DOTENV_FILE), help="panopticon/.env 文件")
    parser.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT), help="备份根目录，建议指向 U 盘/openclaw-backups")
    parser.add_argument("--restic-repo", default="", help="restic repo 路径，默认 <backup-root>/restic-repo")
    parser.add_argument("--data-dir", default="", help="覆盖 PANOPTICON_DATA_DIR")
    parser.add_argument("--usb-host-path", default="", help="覆盖 PANOPTICON_USB_HOST_PATH")
    parser.add_argument("--knowledge-raw-sources-path", default="", help="覆盖 PANOPTICON_KNOWLEDGE_RAW_SOURCES_PATH")
    parser.add_argument("--run-id", default="", help="指定 run id，默认按时间生成")
    parser.add_argument("--dry-run", action="store_true", help="只打印动作，不执行外部命令或写入 payload")
    return parser


def add_common_backup_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--skip-postgres", action="store_true", help="跳过 PostgreSQL 逻辑备份，不推荐")
    parser.add_argument("--skip-redis", action="store_true", help="跳过 Redis BGSAVE")


def cmd_plan(args: argparse.Namespace) -> int:
    args.kind = "plan"
    ctx = BackupContext.from_args(args)
    entries = build_file_entries(ctx, include_redis_data=args.include_redis_data)
    missing = validate_required_entries(entries)
    plan = {
        "kind": "plan",
        "generated_at": now_iso(),
        "fingerprint": fingerprint(ctx),
        "entries": [
            {
                "arcname": entry.arcname,
                "path": str(entry.path),
                "required": entry.required,
                "summary": summarize_path(entry.path),
            }
            for entry in entries
        ],
        "missing_required": missing,
        "recommendations": [
            "日常不停机备份使用 daily-incremental + restic + pg_dump。",
            "迁移级备份使用 weekly-full，并在低峰期允许停 Compose。",
            "U 盘内只保存 restic repo 与 tar 包，不散装解压 OpenClaw 数据目录。",
        ],
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 1 if missing else 0


def cmd_daily_incremental(args: argparse.Namespace) -> int:
    args.kind = "daily-incremental"
    ctx = BackupContext.from_args(args)
    ensure_run_dirs(ctx)
    entries = build_file_entries(ctx, include_redis_data=args.include_redis_data)
    missing = validate_required_entries(entries)
    if missing:
        raise RuntimeError("; ".join(missing))

    commands: list[CommandResult] = []
    report: dict[str, Any] = {
        "kind": "daily-incremental",
        "run_id": ctx.run_id,
        "started_at": now_iso(),
        "backup_root": str(ctx.backup_root),
        "restic_repo": str(ctx.restic_repo),
        "entries": [dataclasses.asdict(entry) | {"path": str(entry.path)} for entry in entries],
        "commands": [],
        "warnings": [],
    }
    write_json(ctx.staging_dir / "fingerprint.json", fingerprint(ctx))

    dump_path, pg_result = create_postgres_dump(ctx, dry_run=args.dry_run, skip=args.skip_postgres)
    if pg_result:
        commands.append(pg_result)
    redis_result = trigger_redis_snapshot(dry_run=args.dry_run, skip=args.skip_redis)
    if redis_result:
        commands.append(redis_result)
        if not redis_result.ok and not redis_result.skipped:
            report["warnings"].append("Redis snapshot failed; Redis is treated as optional cache state")

    commands.extend(ensure_restic_ready(ctx, init=args.init_restic, dry_run=args.dry_run))
    commands.append(restic_backup(ctx, entries, dry_run=args.dry_run, tags=["openclaw", "panopticon", "daily-incremental"]))
    if args.restic_check:
        commands.append(restic_check(ctx, dry_run=args.dry_run))

    if not args.keep_staging and not args.dry_run:
        shutil.rmtree(ctx.staging_dir, ignore_errors=True)

    report["finished_at"] = now_iso()
    report["postgres_dump"] = str(dump_path) if dump_path else None
    report["commands"] = [item.to_report() for item in commands]
    report["success"] = all(item.ok for item in commands)
    write_run_report(ctx, report, mirror_reports=not args.dry_run)
    print(f"[OK] daily incremental report: {ctx.run_dir / 'report.json'}")
    return 0 if report["success"] else 1


def cmd_weekly_full(args: argparse.Namespace) -> int:
    args.kind = "weekly-full"
    ctx = BackupContext.from_args(args)
    ensure_run_dirs(ctx)
    print("[WARN] weekly-full payload contains env files, tokens, credentials and session state; store it on encrypted media")
    entries = build_file_entries(ctx, include_redis_data=args.include_redis_data)
    missing = validate_required_entries(entries)
    if missing:
        raise RuntimeError("; ".join(missing))
    if not args.dry_run and not args.no_stop and not args.yes:
        raise RuntimeError("weekly-full 默认需要停服务；请加 --yes 确认，或加 --no-stop 创建 warm full（不推荐作为迁移级备份）")

    commands: list[CommandResult] = []
    report: dict[str, Any] = {
        "kind": "weekly-full",
        "run_id": ctx.run_id,
        "started_at": now_iso(),
        "backup_root": str(ctx.backup_root),
        "entries": [dataclasses.asdict(entry) | {"path": str(entry.path)} for entry in entries],
        "commands": [],
        "warnings": [],
    }
    dump_path, pg_result = create_postgres_dump(ctx, dry_run=args.dry_run, skip=args.skip_postgres)
    if pg_result:
        commands.append(pg_result)
    redis_result = trigger_redis_snapshot(dry_run=args.dry_run, skip=args.skip_redis)
    if redis_result:
        commands.append(redis_result)

    stopped = False
    try:
        if not args.no_stop:
            commands.append(compose_down(ctx, dry_run=args.dry_run))
            stopped = True
        payload_path = create_full_tar(ctx, entries, dry_run=args.dry_run)
    finally:
        if stopped and args.restart_after:
            commands.append(compose_up(ctx, dry_run=args.dry_run))

    checksums = write_checksums(ctx, [payload_path] if not args.dry_run else [])
    manifest = {
        "kind": "weekly-full",
        "run_id": ctx.run_id,
        "generated_at": now_iso(),
        "payload": str(payload_path),
        "payload_sha256": checksums.get(payload_path.name),
        "postgres_dump_included": bool(dump_path),
        "fingerprint": fingerprint(ctx),
        "entries": [
            {
                "arcname": entry.arcname,
                "path": str(entry.path),
                "required": entry.required,
                "summary": summarize_path(entry.path),
            }
            for entry in entries
        ],
    }
    write_json(ctx.run_dir / "manifest.json", manifest)

    report["finished_at"] = now_iso()
    report["payload"] = str(payload_path)
    report["checksums"] = checksums
    report["commands"] = [item.to_report() for item in commands]
    report["success"] = all(item.ok for item in commands)
    write_run_report(ctx, report, mirror_reports=not args.dry_run)
    print(f"[OK] weekly full backup set: {ctx.run_dir}")
    return 0 if report["success"] else 1


def cmd_verify(args: argparse.Namespace) -> int:
    backup_set = Path(args.backup_set).expanduser().resolve()
    checks_ok, checksum_messages = verify_checksums(backup_set)
    payload_path = backup_set / "payload.tar.gz"
    tar_ok, tar_messages = verify_tar(payload_path) if payload_path.exists() else (True, ["no tar payload in backup set"])

    restic_messages: list[str] = []
    restic_ok = True
    if args.restic_check:
        args.kind = "verify"
        ctx = BackupContext.from_args(args)
        try:
            result = restic_check(ctx, dry_run=args.dry_run)
            restic_messages.append(json.dumps(result.to_report(), ensure_ascii=False))
            restic_ok = result.ok
        except Exception as exc:
            restic_ok = False
            restic_messages.append(str(exc))

    report = {
        "kind": "verify",
        "backup_set": str(backup_set),
        "generated_at": now_iso(),
        "checksums": {"ok": checks_ok, "messages": checksum_messages},
        "tar": {"ok": tar_ok, "messages": tar_messages},
        "restic": {"ok": restic_ok, "messages": restic_messages},
        "success": checks_ok and tar_ok and restic_ok,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


def cmd_prune(args: argparse.Namespace) -> int:
    args.kind = "prune"
    ctx = BackupContext.from_args(args)
    commands = restic_prune(ctx, args)
    report = {
        "kind": "prune",
        "generated_at": now_iso(),
        "restic_repo": str(ctx.restic_repo),
        "commands": [item.to_report() for item in commands],
        "success": all(item.ok for item in commands),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


def cmd_install_timers(args: argparse.Namespace) -> int:
    args.kind = "install-timers"
    ctx = BackupContext.from_args(args)
    systemd_dir = Path(args.systemd_dir).expanduser().resolve()
    python_exe = sys.executable
    script_path = Path(__file__).resolve()
    backup_args = [
        f"--backup-root={ctx.backup_root}",
        f"--restic-repo={ctx.restic_repo}",
        f"--dotenv-file={ctx.dotenv_file}",
        f"--compose-file={ctx.compose_file}",
    ]
    environment_lines = ""
    restic_password_file = os.getenv("RESTIC_PASSWORD_FILE", "").strip()
    if restic_password_file:
        environment_lines = f"Environment=RESTIC_PASSWORD_FILE={restic_password_file}\n"
    elif os.getenv("RESTIC_PASSWORD"):
        print("[WARN] RESTIC_PASSWORD is set in the current shell but will not be embedded in systemd units; prefer RESTIC_PASSWORD_FILE")
    daily_service = f"""[Unit]
Description=OpenClaw Panopticon daily incremental backup

[Service]
Type=oneshot
WorkingDirectory={REPO_ROOT}
{environment_lines}ExecStart={python_exe} {script_path} {' '.join(backup_args)} daily-incremental --restic-check
"""
    daily_timer = """[Unit]
Description=Run OpenClaw Panopticon daily incremental backup

[Timer]
OnCalendar=*-*-* 03:15:00
Persistent=true
RandomizedDelaySec=20m

[Install]
WantedBy=timers.target
"""
    weekly_service = f"""[Unit]
Description=OpenClaw Panopticon weekly full backup

[Service]
Type=oneshot
WorkingDirectory={REPO_ROOT}
{environment_lines}ExecStart={python_exe} {script_path} {' '.join(backup_args)} weekly-full --yes --restart-after
"""
    weekly_timer = """[Unit]
Description=Run OpenClaw Panopticon weekly full backup

[Timer]
OnCalendar=Sun *-*-* 04:15:00
Persistent=true
RandomizedDelaySec=30m

[Install]
WantedBy=timers.target
"""
    files = {
        "openclaw-panopticon-backup-daily.service": daily_service,
        "openclaw-panopticon-backup-daily.timer": daily_timer,
        "openclaw-panopticon-backup-weekly.service": weekly_service,
        "openclaw-panopticon-backup-weekly.timer": weekly_timer,
    }
    if args.dry_run:
        for name, content in files.items():
            print(f"--- {systemd_dir / name} ---")
            print(content)
        return 0
    systemd_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (systemd_dir / name).write_text(content, encoding="utf-8")
    print(f"[OK] timer units written to {systemd_dir}")
    print("[INFO] enable with: systemctl --user daemon-reload && systemctl --user enable --now openclaw-panopticon-backup-daily.timer openclaw-panopticon-backup-weekly.timer")
    return 0


def build_parser() -> argparse.ArgumentParser:
    base = build_base_parser()
    subparsers = base.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="输出备份计划和数据边界")
    plan.add_argument("--include-redis-data", action="store_true", help="把 redis-data 纳入路径计划")
    plan.set_defaults(func=cmd_plan)

    daily = subparsers.add_parser("daily-incremental", help="不停机日常增量备份")
    add_common_backup_args(daily)
    daily.add_argument("--init-restic", action="store_true", help="restic repo 不存在时初始化")
    daily.add_argument("--restic-check", action="store_true", help="备份后运行 restic check")
    daily.add_argument("--include-redis-data", action="store_true", help="将 redis-data 也纳入 restic 文件快照")
    daily.add_argument("--keep-staging", action="store_true", help="保留 pg_dump staging 文件，默认备份成功后删除")
    daily.set_defaults(func=cmd_daily_incremental)

    weekly = subparsers.add_parser("weekly-full", help="定期全量冷备 tar 包")
    add_common_backup_args(weekly)
    weekly.add_argument("--yes", action="store_true", help="确认允许停止 docker compose 服务")
    weekly.add_argument("--no-stop", action="store_true", help="不停止服务创建 warm full，不推荐作为迁移级备份")
    weekly.add_argument("--restart-after", action="store_true", help="停服备份后自动 docker compose up -d")
    weekly.add_argument("--include-redis-data", action="store_true", help="把 redis-data 纳入全量 tar，默认不含")
    weekly.set_defaults(func=cmd_weekly_full)

    verify = subparsers.add_parser("verify", help="校验全量备份集或 restic repo")
    verify.add_argument("--backup-set", required=True, help="weekly-full 生成的 run 目录")
    verify.add_argument("--restic-check", action="store_true", help="同时运行 restic check")
    verify.set_defaults(func=cmd_verify)

    prune = subparsers.add_parser("prune", help="按保留策略清理 restic 快照")
    prune.add_argument("--keep-daily", type=int, default=30)
    prune.add_argument("--keep-weekly", type=int, default=8)
    prune.add_argument("--keep-monthly", type=int, default=12)
    prune.set_defaults(func=cmd_prune)

    timers = subparsers.add_parser("install-timers", help="写入 systemd user timer 模板")
    timers.add_argument("--systemd-dir", default="~/.config/systemd/user", help="systemd user unit 目录")
    timers.set_defaults(func=cmd_install_timers)

    return base


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("[ERROR] interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
