from __future__ import annotations

import tempfile
import unittest
import importlib.util
import sys
from pathlib import Path

BACKUP_SCRIPT = Path(__file__).resolve().parent / "backup_panopticon.py"
SPEC = importlib.util.spec_from_file_location("backup_panopticon", BACKUP_SCRIPT)
if SPEC is None or SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f"cannot load {BACKUP_SCRIPT}")
backup = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = backup
SPEC.loader.exec_module(backup)


class BackupPanopticonTests(unittest.TestCase):
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
