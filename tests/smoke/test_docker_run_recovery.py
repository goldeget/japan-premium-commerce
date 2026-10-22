"""Regression tests for PrestaShop 9.2's repeated installer cleanup."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATCHER = ROOT / "docker" / "patch-docker-run.sh"
DOCKERFILE = ROOT / "docker" / "Dockerfile"
ENTRYPOINT = ROOT / "docker" / "kuranea-entrypoint.sh"
INIT_HOOK = ROOT / "docker" / "init" / "10-kuranea-bootstrap.sh"
SMOKE = ROOT / "tests" / "smoke" / "fresh_install.sh"

UPSTREAM_INSTALL_RM = "            rm -r /var/www/html/$PS_FOLDER_INSTALL/"
UPSTREAM_LOCK_RM = "    rm ./install.lock"


class DockerRunRecoveryTests(unittest.TestCase):
    def run_patcher(self, script: Path, webroot: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sh", str(PATCHER), str(script), str(webroot)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_patcher_is_idempotent_and_missing_install_artifacts_do_not_skip_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            webroot = temp / "webroot"
            webroot.mkdir()
            fixture = temp / "docker_run.sh"
            trace = temp / "hook-trace.txt"
            fixture.write_text(
                "#!/bin/sh\n"
                "set -e\n"
                "PS_FOLDER_INSTALL=install\n"
                f"{UPSTREAM_INSTALL_RM}\n"
                "echo 'install cleanup returned'\n"
                f"echo post-install >> '{trace}'\n"
                f"{UPSTREAM_LOCK_RM}\n"
                "echo 'setup completed'\n",
                encoding="utf-8",
            )
            fixture.chmod(0o755)

            first_patch = self.run_patcher(fixture, webroot)
            self.assertEqual(first_patch.returncode, 0, first_patch.stderr)
            patched_once = fixture.read_text(encoding="utf-8")
            second_patch = self.run_patcher(fixture, webroot)
            self.assertEqual(second_patch.returncode, 0, second_patch.stderr)
            self.assertEqual(fixture.read_text(encoding="utf-8"), patched_once)

            env = os.environ | {"PS_FOLDER_INSTALL": "install"}
            absent = subprocess.run(
                ["sh", str(fixture)],
                cwd=temp,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(absent.returncode, 0, absent.stderr)
            self.assertIn("setup completed", absent.stdout)
            self.assertEqual(trace.read_text(encoding="utf-8").splitlines(), ["post-install"])
            self.assertFalse((temp / "install.lock").exists())

            (webroot / "install").mkdir()
            (temp / "install.lock").write_text("", encoding="utf-8")
            trace.unlink()
            present = subprocess.run(
                ["sh", str(fixture)],
                cwd=temp,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(present.returncode, 0, present.stderr)
            self.assertFalse((webroot / "install").exists())
            self.assertFalse((temp / "install.lock").exists())
            self.assertEqual(trace.read_text(encoding="utf-8").splitlines(), ["post-install"])

    def test_patcher_fails_closed_when_upstream_script_shape_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            fixture = temp / "docker_run.sh"
            original = "#!/bin/sh\nset -e\nrm -rf /var/www/html/install\n"
            fixture.write_text(original, encoding="utf-8")

            result = self.run_patcher(fixture, temp / "webroot")

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(fixture.read_text(encoding="utf-8"), original)

    def test_image_runs_bootstrap_from_init_hook_on_first_install_and_restart(self) -> None:
        dockerfile = DOCKERFILE.read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        entrypoint = ENTRYPOINT.read_text(encoding="utf-8")
        smoke = SMOKE.read_text(encoding="utf-8")

        self.assertIn("docker/patch-docker-run.sh", dockerfile)
        self.assertIn("/tmp/init-scripts/10-kuranea-bootstrap.sh", dockerfile)
        self.assertTrue(INIT_HOOK.is_file())
        self.assertIn("kuranea-patch-docker-run", entrypoint)
        self.assertIn("tests/smoke/test_docker_run_recovery.py", workflow)
        self.assertIn("ORDENOWA bootstrap: storefront=ja, en/ko=enabled, admin=ko, theme=kuranea", smoke)
        self.assertIn("KURANEA bootstrap already completed.", smoke)
        self.assertIn("admin_status_after_restart", smoke)
        self.assertIn("/var/www/html/var/cache/prod/appParameters.php", smoke)
        self.assertIn("/var/www/html/var/.kuranea-bootstrap-v2", smoke)
        self.assertIn("compose restart mariadb prestashop", smoke)


if __name__ == "__main__":
    unittest.main()
