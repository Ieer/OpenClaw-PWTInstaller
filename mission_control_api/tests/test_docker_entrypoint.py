from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = ROOT / "mission_control_api" / "docker-entrypoint.sh"


class DockerEntrypointTests(unittest.TestCase):
    def classify(self, text: str) -> str:
        env = dict(os.environ)
        env["MC_ENTRYPOINT_CLASSIFY_ONLY"] = "1"
        result = subprocess.run(
            ["sh", str(ENTRYPOINT)],
            input=text,
            text=True,
            capture_output=True,
            env=env,
            check=True,
        )
        return result.stdout.strip()

    def test_classifies_db_not_ready_as_retryable(self) -> None:
        self.assertEqual(
            self.classify("asyncpg.exceptions.CannotConnectNowError: database system is starting up"),
            "db-not-ready",
        )
        self.assertEqual(
            self.classify("ConnectionRefusedError: [Errno 111] Connection refused"),
            "db-not-ready",
        )

    def test_classifies_auth_failure_as_non_retryable(self) -> None:
        self.assertEqual(
            self.classify("asyncpg.exceptions.InvalidPasswordError: password authentication failed for user mission_control"),
            "db-auth",
        )

    def test_classifies_revision_failure_as_migration_error(self) -> None:
        self.assertEqual(
            self.classify("alembic.util.exc.CommandError: Can't locate revision identified by 'abc123'"),
            "migration-error",
        )

    def test_unknown_output_keeps_legacy_retry_behavior(self) -> None:
        self.assertEqual(self.classify("unexpected transient failure"), "unknown")


if __name__ == "__main__":
    unittest.main()
