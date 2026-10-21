from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tests" / "smoke" / "collect_failure_diagnostics.sh"


class FailureDiagnosticsScriptTests(unittest.TestCase):
    def test_logs_are_redacted_before_stdout_and_summary_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            docker = bin_dir / "docker"
            docker.write_text(
                "#!/bin/sh\n"
                "case \"$*\" in\n"
                "  *'logs --tail=160'*) printf '%s\\n' 'MARIADB_PASSWORD=ci-only-secret' 'startup cause: errno 28' ;;\n"
                "  *) printf '%s\\n' 'docker status: healthy' ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            docker.chmod(0o755)
            df = bin_dir / "df"
            df.write_text("#!/bin/sh\nprintf '%s\\n' 'filesystem: overlay'\n", encoding="utf-8")
            df.chmod(0o755)
            summary = temp / "summary.md"
            env = os.environ | {
                "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                "CI_COMPOSE_PROJECT_NAME": "kuranea-ci-test",
                "RUNNER_TEMP": str(temp),
                "GITHUB_STEP_SUMMARY": str(summary),
            }

            result = subprocess.run(
                ["bash", str(SCRIPT)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("startup cause: errno 28", result.stdout)
            self.assertIn("[REDACTED]", result.stdout)
            self.assertNotIn("ci-only-secret", result.stdout)
            self.assertIn("startup cause: errno 28", summary.read_text(encoding="utf-8"))
            self.assertNotIn("ci-only-secret", summary.read_text(encoding="utf-8"))
            artifact = temp / "kuranea-compose-startup-diagnostics-redacted.txt"
            self.assertTrue(artifact.is_file())
            self.assertNotIn("ci-only-secret", artifact.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
