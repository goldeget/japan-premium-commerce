"""Verify the CI wrapper redacts raw updater failures before reporting them."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tests" / "smoke" / "run_postal_updater.sh"


class PostalUpdaterRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = tempfile.TemporaryDirectory(prefix="kuranea-postal-runner-test-")
        self.root = Path(self.temp_root.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.summary = self.root / "step-summary.md"
        self.docker_args = self.root / "docker-args"
        docker = self.bin_dir / "docker"
        docker.write_text(
            """#!/bin/sh
set -eu
printf '%s\\n' "$@" > "$DOCKER_ARGS"
printf '%s\\n' "${DOCKER_OUTPUT:-updater completed}"
exit "${DOCKER_EXIT:-0}"
""",
            encoding="utf-8",
        )
        docker.chmod(0o755)
        self.env = os.environ.copy()
        self.env.update(
            {
                "PATH": f"{self.bin_dir}:{os.environ['PATH']}",
                "DOCKER_ARGS": str(self.docker_args),
                "GITHUB_STEP_SUMMARY": str(self.summary),
                "RUNNER_TEMP": str(self.root),
            }
        )

    def tearDown(self) -> None:
        self.temp_root.cleanup()

    def _run(self, **environment: str) -> subprocess.CompletedProcess[str]:
        self.assertTrue(RUNNER.is_file(), "the workflow should use the tested postal updater wrapper")
        return subprocess.run(
            ["bash", str(RUNNER), "kuranea-ci-test"],
            check=False,
            capture_output=True,
            text=True,
            env={**self.env, **environment},
        )

    def test_download_diagnostic_is_the_only_failure_detail_exposed(self) -> None:
        safe = "KURANEA_POSTAL_DOWNLOAD_FAILURE curl_exit=22 http_status=403 effective_host=www.post.japanpost.jp"
        result = self._run(
            DOCKER_EXIT="1",
            DOCKER_OUTPUT=f"upstream private body\n{safe}\ncredential=do-not-show",
        )

        self.assertNotEqual(0, result.returncode)
        self.assertEqual(f"::error title=Japan Post postcode update::{safe}\n", result.stdout)
        self.assertEqual(f"{safe}\n", self.summary.read_text(encoding="utf-8"))
        self.assertNotIn("upstream private body", result.stdout)
        self.assertNotIn("credential=", result.stdout)
        self.assertNotIn("upstream private body", result.stderr)
        self.assertFalse(list(self.root.glob("kuranea-postal-updater.*")), "captured raw output should be removed")

    def test_other_updater_failures_use_only_a_generic_safe_message(self) -> None:
        result = self._run(DOCKER_EXIT="1", DOCKER_OUTPUT="Import failed: sensitive database detail")
        generic = "Japan Post address data updater/import failed; raw updater output was suppressed."

        self.assertNotEqual(0, result.returncode)
        self.assertEqual(f"::error title=Japan Post postcode update::{generic}\n", result.stdout)
        self.assertEqual(f"{generic}\n", self.summary.read_text(encoding="utf-8"))
        self.assertNotIn("sensitive database detail", result.stdout)
        self.assertNotIn("sensitive database detail", result.stderr)

    def test_successful_updater_output_is_preserved(self) -> None:
        result = self._run(DOCKER_OUTPUT="Imported official CSV rows.")

        self.assertEqual(0, result.returncode)
        self.assertEqual("Imported official CSV rows.\n", result.stdout)
        self.assertFalse(self.summary.exists())


if __name__ == "__main__":
    unittest.main()
