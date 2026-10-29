import importlib.util
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("ci_owned_resources_cleanup.py")
SPEC = importlib.util.spec_from_file_location("ci_owned_resources_cleanup", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

IMAGE_REF = "local-only/ordenowa-procurement-ci:run-12345-2"
IMAGE_ID = "sha256:" + "a" * 64
RESTORE_NAME = "ordenowa-procurement-ci-12345-2-restore"
CONTAINER_ID = "b" * 64


class FakeDocker:
    """Return scripted Docker results; this test never invokes Docker."""

    def __init__(self):
        self.image_rows = ""
        self.container_rows = ""
        self.inspected_image_id = IMAGE_ID
        self.failures = set()
        self.keep_image_after_remove = False
        self.keep_container_after_remove = False
        self.commands = []

    def __call__(self, argv, timeout):
        self.commands.append((list(argv), timeout))
        self.assert_bounded_local_command(argv, timeout)
        args = list(argv[3:])
        if args[:2] == ["image", "ls"]:
            if "image_ls" in self.failures:
                return subprocess.CompletedProcess(argv, 1, "", "daemon unavailable")
            return subprocess.CompletedProcess(argv, 0, self.image_rows, "")
        if args[:2] == ["image", "inspect"]:
            if "image_inspect" in self.failures:
                return subprocess.CompletedProcess(argv, 1, "", "inspect failed")
            return subprocess.CompletedProcess(argv, 0, self.inspected_image_id + "\n", "")
        if args[:2] == ["image", "rm"]:
            if "image_rm" in self.failures:
                return subprocess.CompletedProcess(argv, 1, "", "remove failed")
            if not self.keep_image_after_remove:
                self.image_rows = ""
            return subprocess.CompletedProcess(argv, 0, "deleted\n", "")
        if args[:3] == ["container", "ls", "--all"]:
            if "container_ls" in self.failures:
                return subprocess.CompletedProcess(argv, 1, "", "daemon unavailable")
            return subprocess.CompletedProcess(argv, 0, self.container_rows, "")
        if args[:3] == ["container", "rm", "--force"]:
            if "container_rm" in self.failures:
                return subprocess.CompletedProcess(argv, 1, "", "remove failed")
            if not self.keep_container_after_remove:
                self.container_rows = ""
            return subprocess.CompletedProcess(argv, 0, CONTAINER_ID + "\n", "")
        raise AssertionError("unexpected mocked Docker command: " + " ".join(args))

    @staticmethod
    def assert_bounded_local_command(argv, timeout):
        if list(argv[:3]) != ["docker", "--context", "default"]:
            raise AssertionError("cleanup must explicitly use Docker's default context")
        if timeout <= 0 or timeout > 60:
            raise AssertionError("Docker cleanup command must have a bounded timeout")


class OwnedResourceCleanupTests(unittest.TestCase):
    def test_missing_run_image_is_success_only_after_successful_exact_list_query(self):
        runner = FakeDocker()
        self.assertEqual(MODULE.remove_owned_image(IMAGE_REF, IMAGE_ID, runner=runner), "absent")
        self.assertEqual(len(runner.commands), 1)
        argv, _ = runner.commands[0]
        self.assertIn("reference=" + IMAGE_REF, argv)

    def test_exact_run_image_is_inspected_removed_and_verified_absent(self):
        runner = FakeDocker()
        runner.image_rows = f"{IMAGE_REF} {IMAGE_ID}\n"

        self.assertEqual(MODULE.remove_owned_image(IMAGE_REF, IMAGE_ID, runner=runner), "removed")
        command_tails = [command[0][3:] for command in runner.commands]
        self.assertEqual([tail[:2] for tail in command_tails], [
            ["image", "ls"], ["image", "inspect"], ["image", "rm"], ["image", "ls"],
        ])
        self.assertEqual(command_tails[2][-1], IMAGE_REF)

    def test_filtered_prefix_or_other_tag_is_never_removed(self):
        runner = FakeDocker()
        runner.image_rows = f"{IMAGE_REF}-other {IMAGE_ID}\n"

        self.assertEqual(MODULE.remove_owned_image(IMAGE_REF, IMAGE_ID, runner=runner), "absent")
        self.assertFalse(any(command[0][3:5] == ["image", "rm"] for command in runner.commands))

    def test_image_list_daemon_error_is_failure_not_absence(self):
        runner = FakeDocker()
        runner.failures.add("image_ls")

        with self.assertRaisesRegex(MODULE.CleanupError, "docker_command_failed"):
            MODULE.remove_owned_image(IMAGE_REF, IMAGE_ID, runner=runner)

    def test_mismatched_or_uninspectable_image_is_not_removed(self):
        runner = FakeDocker()
        runner.image_rows = f"{IMAGE_REF} {'c' * 64}\n"
        with self.assertRaisesRegex(MODULE.CleanupError, "owned_image_id_mismatch"):
            MODULE.remove_owned_image(IMAGE_REF, IMAGE_ID, runner=runner)
        self.assertFalse(any(command[0][3:5] == ["image", "rm"] for command in runner.commands))

        runner = FakeDocker()
        runner.image_rows = f"{IMAGE_REF} {IMAGE_ID}\n"
        runner.failures.add("image_inspect")
        with self.assertRaisesRegex(MODULE.CleanupError, "docker_command_failed"):
            MODULE.remove_owned_image(IMAGE_REF, IMAGE_ID, runner=runner)
        self.assertFalse(any(command[0][3:5] == ["image", "rm"] for command in runner.commands))

    def test_image_remove_error_or_remaining_tag_fails_cleanup(self):
        runner = FakeDocker()
        runner.image_rows = f"{IMAGE_REF} {IMAGE_ID}\n"
        runner.failures.add("image_rm")
        with self.assertRaisesRegex(MODULE.CleanupError, "docker_command_failed"):
            MODULE.remove_owned_image(IMAGE_REF, IMAGE_ID, runner=runner)

        runner = FakeDocker()
        runner.image_rows = f"{IMAGE_REF} {IMAGE_ID}\n"
        runner.keep_image_after_remove = True
        with self.assertRaisesRegex(MODULE.CleanupError, "owned_image_remains"):
            MODULE.remove_owned_image(IMAGE_REF, IMAGE_ID, runner=runner)

    def test_restore_container_matching_uses_full_name_and_never_prefix(self):
        runner = FakeDocker()
        runner.container_rows = f"{RESTORE_NAME}-other {CONTAINER_ID}\n"

        self.assertEqual(MODULE.remove_owned_container(RESTORE_NAME, runner=runner), "absent")
        self.assertFalse(any(command[0][3:5] == ["container", "rm"] for command in runner.commands))

    def test_exact_restore_container_is_removed_by_id_and_verified_absent(self):
        runner = FakeDocker()
        runner.container_rows = f"{RESTORE_NAME} {CONTAINER_ID}\n"

        self.assertEqual(MODULE.remove_owned_container(RESTORE_NAME, runner=runner), "removed")
        command_tails = [command[0][3:] for command in runner.commands]
        self.assertEqual([tail[:3] for tail in command_tails], [
            ["container", "ls", "--all"], ["container", "rm", "--force"], ["container", "ls", "--all"],
        ])
        self.assertEqual(command_tails[1][-1], CONTAINER_ID)

    def test_restore_container_list_or_remove_failures_do_not_pass(self):
        runner = FakeDocker()
        runner.failures.add("container_ls")
        with self.assertRaisesRegex(MODULE.CleanupError, "docker_command_failed"):
            MODULE.remove_owned_container(RESTORE_NAME, runner=runner)

        runner = FakeDocker()
        runner.container_rows = f"{RESTORE_NAME} {CONTAINER_ID}\n"
        runner.failures.add("container_rm")
        with self.assertRaisesRegex(MODULE.CleanupError, "docker_command_failed"):
            MODULE.remove_owned_container(RESTORE_NAME, runner=runner)

        runner = FakeDocker()
        runner.container_rows = f"{RESTORE_NAME} {CONTAINER_ID}\n"
        runner.keep_container_after_remove = True
        with self.assertRaisesRegex(MODULE.CleanupError, "owned_container_remains"):
            MODULE.remove_owned_container(RESTORE_NAME, runner=runner)

    def test_cli_and_both_cleanup_call_sites_use_checked_helper(self):
        workflow = (ROOT / ".github/workflows/procurement-platform.yml").read_text(encoding="utf-8")
        restore = (ROOT / "tests/procurement/ci_restore.sh").read_text(encoding="utf-8")

        self.assertIn("ci_owned_resources_cleanup.py image", workflow)
        self.assertIn("ci_owned_resources_cleanup.py container", workflow)
        self.assertIn('python3 "$cleanup_helper" container', restore)
        self.assertIn('/ci_owned_resources_cleanup.py"', restore)
        self.assertNotIn('docker container inspect "$restore_container"', workflow)
        self.assertNotIn('docker image inspect --format', workflow)
        self.assertNotIn('docker container inspect "$restore_project"', restore)


if __name__ == "__main__":
    unittest.main()
