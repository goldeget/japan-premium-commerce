from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "tools" / "release" / "scheduler"
SCRIPT = ROOT / "generate_units.py"
SPEC = importlib.util.spec_from_file_location("generate_units", SCRIPT)
assert SPEC and SPEC.loader
generator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generator
SPEC.loader.exec_module(generator)


def valid_config(**overrides):
    values = {
        "project_dir": "/srv/ordenowa",
        "project_name": "ordenowa-prod",
        "docker_bin": "/usr/bin/true",
        "shop_id": "1",
        "limit": "25",
        "channels": "mail,push",
        "host_user": "ordenowa-worker",
        "host_group": "docker",
        "timeout_seconds": "600",
    }
    values.update(overrides)
    return generator.build_config(**values)


class UnitGeneratorTests(unittest.TestCase):
    def test_default_renders_a_single_shop_timer_for_both_channels(self):
        units = generator.render_units(valid_config())
        self.assertEqual(
            set(units),
            {"ordenowa-ordenowa-prod-notify-shop1.service", "ordenowa-ordenowa-prod-notify-shop1.timer"},
        )
        service = units["ordenowa-ordenowa-prod-notify-shop1.service"]
        self.assertIn("Type=oneshot", service)
        self.assertIn("TimeoutStartSec=600s", service)
        self.assertIn("TimeoutStopSec=30s", service)
        self.assertIn("User=ordenowa-worker\nGroup=docker", service)
        self.assertIn("/usr/bin/true --context=default compose --project-name=ordenowa-prod", service)
        self.assertIn("exec -T --user www-data prestashop php", service)
        self.assertIn("--shop=1 --channels=mail,push --limit=25", service)
        timer = units["ordenowa-ordenowa-prod-notify-shop1.timer"]
        self.assertIn("OnBootSec=60s", timer)
        self.assertIn("OnUnitInactiveSec=60s", timer)
        self.assertNotIn("OnCalendar=", timer)
        self.assertNotIn("Persistent=", timer)
        self.assertIn("SyslogIdentifier=ordenowa-ordenowa-prod-notify-shop1", service)

    def test_channel_selection_is_allowlisted_and_keeps_one_timer(self):
        for channel in ("mail", "push", "mail,push"):
            with self.subTest(channel=channel):
                self.assertIn(
                    f"--channels={channel}",
                    generator.render_units(valid_config(channels=channel))[
                        "ordenowa-ordenowa-prod-notify-shop1.service"
                    ],
                )
        for channel in ("push,mail", "mail,,push", "mail;touch /tmp/pwned", ""):
            with self.subTest(channel=channel), self.assertRaises(ValueError):
                valid_config(channels=channel)

    def test_paths_reject_relative_traversal_whitespace_specifiers_and_shell_syntax(self):
        bad_project_paths = (
            "srv/ordenowa",
            "/srv/../etc",
            "/srv/ordenowa;touch /tmp/pwned",
            "/srv/ordenowa%n",
            "/srv/ordenowa\nExecStart=/tmp/pwned",
            "/",
        )
        for path in bad_project_paths:
            with self.subTest(path=path), self.assertRaises(ValueError):
                valid_config(project_dir=path)
        with self.assertRaises(ValueError):
            valid_config(docker_bin="docker")
        with self.assertRaises(ValueError):
            valid_config(docker_bin="/usr/bin/docker;touch /tmp/pwned")

    def test_compose_project_name_is_required_safe_and_explicit(self):
        self.assertEqual(valid_config(project_name="9-shop_a").project_name, "9-shop_a")
        self.assertEqual(valid_config(project_name="a" * 63).project_name, "a" * 63)
        for value in ("", "-bad", "_bad", "Uppercase", "bad name", "prod;touch", "prod\nExecStart=x", "a" * 64):
            with self.subTest(project_name=value), self.assertRaises(ValueError):
                valid_config(project_name=value)

    def test_values_reject_invalid_integer_ranges_and_host_accounts(self):
        invalid = (
            {"shop_id": "0"},
            {"shop_id": "1;touch /tmp/pwned"},
            {"shop_id": "+1"},
            {"shop_id": " 1"},
            {"limit": "101"},
            {"limit": "25\nExecStart=/tmp/pwned"},
            {"timeout_seconds": "59"},
            {"timeout_seconds": "3601"},
            {"timeout_seconds": "600;touch /tmp/pwned"},
            {"host_user": "root"},
            {"host_user": "worker\nExecStart=/tmp/pwned"},
            {"host_group": "docker;touch"},
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValueError):
                valid_config(**values)
        self.assertEqual(valid_config(timeout_seconds="60").timeout_seconds, 60)
        self.assertEqual(valid_config(timeout_seconds="3600").timeout_seconds, 3600)

    def test_unit_text_contains_no_environment_secrets_or_retry_ack_arguments(self):
        service = generator.render_units(valid_config())["ordenowa-ordenowa-prod-notify-shop1.service"]
        self.assertNotIn("Environment=", service)
        self.assertNotIn("EnvironmentFile=", service)
        self.assertNotIn("MARIADB_PASSWORD", service)
        self.assertNotIn("ORDENOWA_PUSH_VAPID_PRIVATE_KEY", service)
        self.assertNotIn("supersecret", service)
        self.assertNotIn("--retry-uncertain", service)
        self.assertNotIn("--ack-possible-duplicate", service)

    def test_writer_creates_files_only_in_requested_directory_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "generated"
            output.mkdir()
            paths = generator.write_units(str(output), valid_config())
            self.assertEqual(len(paths), 2)
            self.assertTrue(all(path.parent == output for path in paths))
            with self.assertRaises(ValueError):
                generator.write_units(str(output), valid_config())

    def test_sample_units_match_generator_output(self):
        sample_config = valid_config(
            project_name="kuranea",
            docker_bin="/usr/bin/docker",
        )
        expected = generator.render_units(sample_config)
        generated_dir = ROOT / "generated"
        self.assertEqual(
            {path.name: path.read_text(encoding="utf-8") for path in generated_dir.iterdir()},
            expected,
        )

    def test_two_compose_projects_with_same_shop_get_distinct_unit_names(self):
        production = generator.render_units(valid_config(project_name="kuranea"))
        staging = generator.render_units(valid_config(project_name="kuranea-stage"))
        self.assertTrue(set(production).isdisjoint(staging))
        self.assertIn("ordenowa-kuranea-notify-shop1.service", production)
        self.assertIn("ordenowa-kuranea-stage-notify-shop1.service", staging)

    def test_writer_rejects_missing_directory_and_live_systemd_destination(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "not-created"
            with self.assertRaisesRegex(ValueError, "must already exist"):
                generator.write_units(str(missing), valid_config())
        if os.name == "posix":
            protected = (
                "/etc/systemd/system",
                "/etc/systemd/user",
                "/run/systemd/system",
                "/usr/lib/systemd/system",
                "/usr/local/lib/systemd/system",
                "/lib/systemd/system",
                "/usr/lib/systemd/user",
                "/usr/local/lib/systemd/user",
                "/lib/systemd/user",
                "/home/deployer/.config/systemd/user",
                "/usr/lib/systemd/system/ordenowa",
            )
            for path in protected:
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, "live systemd unit directory"):
                    generator.write_units(path, valid_config())

    @unittest.skipUnless(os.name == "posix", "symlink test uses POSIX path semantics")
    def test_writer_rejects_symlink_output_directory(self):
        with tempfile.TemporaryDirectory(prefix="ordenowa-symlink-") as temp_dir:
            root = Path(temp_dir)
            target = root / "real"
            target.mkdir()
            link = root / "link"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                generator.write_units(str(link), valid_config())

    def test_cli_rejects_command_injection_without_creating_marker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            out = Path(temp_dir)
            marker = out / "injected"
            injected_path = f"/srv/ordenowa;touch {marker}"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--project-dir",
                    injected_path,
                    "--project-name",
                    "ordenowa-prod",
                    "--shop-id",
                    "1",
                    "--host-user",
                    "ordenowa-worker",
                    "--host-group",
                    "docker",
                    "--output-dir",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertFalse(marker.exists())
            self.assertEqual(list(out.iterdir()), [])

    @unittest.skipUnless(os.name == "posix" and __import__("shutil").which("systemd-analyze"), "systemd-analyze is available in Linux CI")
    def test_generated_units_pass_systemd_analyze_verify(self):
        with tempfile.TemporaryDirectory(prefix="ordenowa-units-") as temp_dir:
            paths = generator.write_units(temp_dir, valid_config())
            completed = subprocess.run(
                ["systemd-analyze", "verify", *(str(path) for path in paths)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                msg=completed.stdout + completed.stderr,
            )


if __name__ == "__main__":
    unittest.main()
