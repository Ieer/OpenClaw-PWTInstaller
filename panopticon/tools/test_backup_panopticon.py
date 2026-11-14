from __future__ import annotations

import tempfile
import unittest
import importlib.util
import sys
import tarfile
import gzip
import json
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKUP_SCRIPT = Path(__file__).resolve().parent / "backup_panopticon.py"
SPEC = importlib.util.spec_from_file_location("backup_panopticon", BACKUP_SCRIPT)
if SPEC is None or SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f"cannot load {BACKUP_SCRIPT}")
backup = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = backup
SPEC.loader.exec_module(backup)


class BackupPanopticonTests(unittest.TestCase):
    def test_execution_state_and_overlay_are_in_backup_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "mission-control/execution-worker"
            state.mkdir(parents=True)
            (root / "docker-compose.execution-worker.yml").write_text("services: {}")
            ctx = SimpleNamespace(data_dir=root, env_values={}, knowledge_raw_sources_path=root / "missing")
            with patch.object(backup, "PANOPTICON_DIR", root), patch.dict("os.environ", {"MC_EXECUTION_WORKER_STATE_PATH": str(state)}):
                entries = {entry.arcname: entry.path for entry in backup.build_file_entries(ctx)}
            self.assertEqual(entries["data/execution-worker"], state)
            self.assertEqual(entries["config/docker-compose.execution-worker.yml"], root / "docker-compose.execution-worker.yml")

    def test_weekly_full_accepts_bounded_gzip_levels(self) -> None:
        parser = backup.build_parser()
        self.assertEqual(parser.parse_args(["weekly-full"]).gzip_level, 6)
        for level in (0, 1, 3, 9):
            with self.subTest(level=level):
                args = parser.parse_args(["weekly-full", "--gzip-level", str(level)])
                self.assertEqual(args.gzip_level, level)
        for level in (-1, 10):
            with self.subTest(level=level), patch("sys.stderr", new_callable=StringIO):
                with self.assertRaises(SystemExit):
                    parser.parse_args(["weekly-full", "--gzip-level", str(level)])

    def test_weekly_full_gzip_levels_preserve_payload_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture"
            source.mkdir()
            content = b"backup compression fixture\n" * 1024
            source_file = source / "payload.txt"
            source_file.write_bytes(content)
            source_file.chmod(0o640)
            (source / "symlink.txt").symlink_to("payload.txt")
            (source / "hardlink.txt").hardlink_to(source_file)
            for level in (0, 3, 6, 9):
                with self.subTest(level=level):
                    arguments = [
                        "--panopticon-dir", str(root), "--backup-root", str(root / "backups"),
                        "--dotenv-file", str(root / ".env"), "--run-id", f"level-{level}",
                        "weekly-full", "--no-stop", "--gzip-level", str(level),
                    ]
                    with patch.object(backup, "fingerprint", return_value={}), patch.object(
                        backup, "build_file_entries", return_value=[backup.FileEntry(source, "fixture")]
                    ), patch.object(backup, "create_postgres_dump", return_value=(None, None)), patch.object(
                        backup, "trigger_redis_snapshot", return_value=None
                    ), patch("sys.stdout", new_callable=StringIO):
                        self.assertEqual(backup.main(arguments), 0)
                    run_dir = root / "backups" / "runs" / f"level-{level}"
                    for report_name in ("manifest.json", "report.json"):
                        report = json.loads((run_dir / report_name).read_text())
                        self.assertEqual(report["compression"], {"format": "gzip", "level": level})
                    self.assertTrue(backup.verify_checksums(run_dir)[0])
                    self.assertTrue(backup.verify_tar(run_dir / "payload.tar.gz")[0])
                    with tarfile.open(run_dir / "payload.tar.gz", "r:gz") as archive:
                        self.assertEqual(archive.getmember("fixture/payload.txt").mode, 0o640)
                        self.assertTrue(archive.getmember("fixture/symlink.txt").issym())
                        for name in ("payload.txt", "hardlink.txt", "symlink.txt"):
                            extracted = archive.extractfile(f"fixture/{name}")
                            assert extracted is not None
                            with extracted:
                                self.assertEqual(extracted.read(), content)

    def test_generated_backup_services_use_low_resource_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {}, clear=True):
            root = Path(tmp)
            arguments = [
                "--panopticon-dir", str(root), "--backup-root", str(root / "backups"),
                "--dotenv-file", str(root / ".env"), "install-timers", "--systemd-dir", str(root / "units"),
            ]
            with patch("sys.stdout", new_callable=StringIO):
                self.assertEqual(backup.main(arguments), 0)
            for kind in ("daily", "weekly"):
                service = (root / "units" / f"openclaw-panopticon-backup-{kind}.service").read_text()
                self.assertIn("Nice=10\n", service)
                self.assertIn("IOSchedulingClass=best-effort\n", service)
                self.assertIn("IOSchedulingPriority=7\n", service)

    def test_verify_tar_does_not_materialize_all_member_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / "payload.tar.gz"
            with tarfile.open(payload, "w:gz") as archive:
                for name in (
                    "__backup_metadata/fingerprint.json",
                    "__backup_metadata/entries.json",
                    "workspaces/nox/MEMORY.md",
                ):
                    archive.addfile(tarfile.TarInfo(name))
            with patch.object(tarfile.TarFile, "getnames", side_effect=AssertionError("eager member list")):
                self.assertEqual(backup.verify_tar(payload), (True, ["payload entries: 3"]))

    def test_verify_tar_bounds_member_cache_and_counts_all_entries(self) -> None:
        original_next = tarfile.TarFile.next

        def checked_next(archive: tarfile.TarFile) -> tarfile.TarInfo | None:
            member = original_next(archive)
            self.assertLessEqual(len(archive.members), 1)
            return member

        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / "payload.tar.gz"
            with tarfile.open(payload, "w:gz") as archive:
                for index in range(512):
                    archive.addfile(tarfile.TarInfo(f"workspaces/nox/{index}/" + "x" * 150))
                archive.addfile(tarfile.TarInfo("__backup_metadata/fingerprint.json"))
                archive.addfile(tarfile.TarInfo("__backup_metadata/entries.json"))
                archive.addfile(tarfile.TarInfo("__backup_metadata/entries.json"))
            with patch.object(tarfile.TarFile, "next", checked_next):
                self.assertEqual(backup.verify_tar(payload), (True, ["payload entries: 515"]))

    def test_verify_tar_reports_missing_metadata(self) -> None:
        required = ["__backup_metadata/fingerprint.json", "__backup_metadata/entries.json"]
        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / "payload.tar.gz"
            for present in ([], required[:1], required[1:]):
                with self.subTest(present=present):
                    with tarfile.open(payload, "w:gz") as archive:
                        for name in present:
                            archive.addfile(tarfile.TarInfo(name))
                    missing = [name for name in required if name not in present]
                    self.assertEqual(
                        backup.verify_tar(payload),
                        (False, [f"payload missing metadata: {', '.join(missing)}"]),
                    )

    def test_verify_tar_rejects_corruption_after_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / "payload.tar.gz"
            with gzip.open(payload, "wb") as archive:
                archive.write(tarfile.TarInfo("__backup_metadata/fingerprint.json").tobuf())
                archive.write(tarfile.TarInfo("__backup_metadata/entries.json").tobuf())
                truncated = tarfile.TarInfo("workspaces/nox/MEMORY.md")
                truncated.size = 2048
                archive.write(truncated.tobuf())
                archive.write(b"!" * 16)
            with tarfile.open(payload, "r:gz") as archive:
                with self.assertRaises(tarfile.TarError):
                    archive.getnames()
            ok, messages = backup.verify_tar(payload)
            self.assertFalse(ok)
            self.assertTrue(messages[0].startswith("invalid tar payload:"))

    def test_backup_lock_rejects_overlap_and_releases_after_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "failed"):
                with backup.backup_run_lock(root):
                    with self.assertRaisesRegex(RuntimeError, "another backup"):
                        with backup.backup_run_lock(root):
                            self.fail("overlapping backup acquired lock")
                    raise ValueError("failed")
            with backup.backup_run_lock(root):
                self.assertTrue((root / ".backup.lock").exists())

    def test_main_does_not_start_backup_while_locked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            backup, "cmd_daily_incremental", return_value=0
        ) as run, patch("sys.stderr", new_callable=StringIO):
            arguments = ["--panopticon-dir", tmp, "--dry-run", "daily-incremental"]
            with backup.backup_run_lock(Path(tmp)):
                self.assertEqual(backup.main(arguments), 1)
                run.assert_not_called()
            self.assertEqual(backup.main(arguments), 0)
            run.assert_called_once()

    def test_load_env_file_handles_export_quotes_and_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# comment",
                        "export PANOPTICON_DATA_DIR='/srv/openclaw data' # inline comment",
                        'TOKEN="abc#still-token"',
                        "EMPTY=",
                    ]
                ),
                encoding="utf-8",
            )

            values = backup.load_env_file(env_path)

        self.assertEqual(values["PANOPTICON_DATA_DIR"], "/srv/openclaw data")
        self.assertEqual(values["TOKEN"], "abc#still-token")
        self.assertEqual(values["EMPTY"], "")

    def test_resolve_bind_path_uses_base_for_relative_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            resolved = backup.resolve_bind_path(base, "data", ".")
            self.assertEqual(resolved, base / "data")
            fallback = backup.resolve_bind_path(base, "", "mission-control/knowledge-sources")
            self.assertEqual(fallback, base / "mission-control" / "knowledge-sources")

    def test_is_excluded_matches_browser_locks_and_cache(self) -> None:
        root = Path("/tmp/root")
        self.assertTrue(backup.is_excluded(root / "agent-homes" / "nox" / "browser" / "SingletonLock", root))
        self.assertTrue(backup.is_excluded(root / "agent-homes" / "nox" / "browser" / "Default" / "Cache" / "x", root))
        self.assertTrue(backup.is_excluded(root / "workspaces" / "nox" / "node_modules" / "x.js", root))
        self.assertTrue(backup.is_excluded(root / "workspaces" / "metrics" / "runtime-assets" / "venv" / "bin" / "python", root))
        self.assertFalse(backup.is_excluded(root / "workspaces" / "nox" / "MEMORY.md", root))

    def test_manifest_inventory_does_not_expose_env_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_dir = Path(tmp)
            (env_dir / "nox.env").write_text("API_KEY=super-secret\nMODEL_ID=glm\n", encoding="utf-8")
            inventory = backup.env_file_inventory(env_dir)

        text = str(inventory)
        self.assertIn("API_KEY", text)
        self.assertIn("sensitive_key_count", text)
        self.assertNotIn("super-secret", text)


if __name__ == "__main__":
    unittest.main()
