from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "release"))
import package_release


COMMIT = "1" * 40
THEME = "2" * 40
CONFIG = b'{"architecture":"amd64","os":"linux"}'
IMAGE_ID = "sha256:" + hashlib.sha256(CONFIG).hexdigest()
BASE_1 = "composer:2@sha256:" + "a" * 64
BASE_2 = "prestashop/prestashop:9.2.0@sha256:" + "b" * 64


def tar_bytes(tag: str | None, config: bytes, layer: bytes = b"layer bytes") -> bytes:
    repo_tags = [tag] if tag else None
    manifest = [{"Config": "config.json", "RepoTags": repo_tags, "Layers": ["layer.tar"]}]
    result = BytesIO()
    with tarfile.open(fileobj=result, mode="w:") as archive:
        for name, content in (
            ("manifest.json", json.dumps(manifest).encode("utf-8")),
            ("config.json", config),
            ("layer.tar", layer),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, BytesIO(content))
    return result.getvalue()


class FakeRunner:
    def __init__(self, root: Path, archive_bytes: bytes, *, context: str = "unix:///var/run/docker.sock") -> None:
        self.root = root
        self.archive_bytes = archive_bytes
        self.context = context
        self.commands: list[list[str]] = []
        self.loaded = False
        self.built = False
        self.tag_removed = False
        self.inspect_count = 0
        self.mutate_tag_after_first_inspect = False

    def __call__(self, argv: list[str] | tuple[str, ...], timeout: int) -> subprocess.CompletedProcess[str]:
        command = list(argv)
        self.commands.append(command)
        if command[0] == "git":
            target = Path(command[command.index("-C") + 1])
            args = command[command.index("-C") + 2:]
            if args == ["rev-parse", "--show-toplevel"]:
                output = str(target)
            elif args == ["rev-parse", "HEAD"]:
                output = THEME if target.name == "hummingbird" else COMMIT
            elif args[:2] == ["status", "--porcelain=v1"]:
                output = ""
            elif args[:2] == ["ls-tree", "HEAD"]:
                output = "160000 commit " + THEME + "\tthemes/hummingbird"
            elif args == ["check-ignore", "-q", "release-artifacts/"]:
                output = ""
            elif args == ["remote", "get-url", "origin"]:
                output = "https://github.com/goldeget/japan-premium-commerce.git"
            else:
                raise AssertionError("unexpected Git command: " + repr(command))
            return subprocess.CompletedProcess(command, 0, output, "")

        if "context" in command and "inspect" in command:
            output = self.context
        elif "image" in command and "ls" in command:
            output = ""
        elif "build" in command:
            self.built = True
            output = "build output must not be surfaced"
        elif "inspect" in command and "image" in command:
            if not self.built and not self.loaded:
                return subprocess.CompletedProcess(command, 1, "", "missing")
            self.inspect_count += 1
            tag = command[-1]
            value = {
                "Id": IMAGE_ID,
                "RepoTags": [] if self.loaded else [package_release.IMAGE_PREFIX + COMMIT],
                "Os": "linux",
                "Architecture": "amd64",
                "Config": {"Labels": {
                    "org.opencontainers.image.revision": COMMIT,
                    "com.ordenowa.theme.gitlink": THEME,
                }},
            }
            if self.mutate_tag_after_first_inspect and self.inspect_count == 2:
                value["Id"] = "sha256:" + "f" * 64
            output = json.dumps(value)
        elif "save" in command:
            output_file = Path(command[command.index("--output") + 1])
            output_file.write_bytes(self.archive_bytes)
            output = ""
        elif "rm" in command and "image" in command:
            self.tag_removed = True
            self.built = False
            output = ""
        elif "load" in command and "image" in command:
            archive = Path(command[command.index("--input") + 1])
            assert self.tag_removed and archive.is_file()
            self.loaded = True
            output = "Loaded image"
        else:
            raise AssertionError("unexpected Docker command: " + repr(command))
        return subprocess.CompletedProcess(command, 0, output, "")


class PackageReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "checkout"
        (self.root / "docker").mkdir(parents=True)
        (self.root / "themes" / "hummingbird").mkdir(parents=True)
        (self.root / ".gitignore").write_text("release-artifacts/\n", encoding="utf-8")
        (self.root / ".dockerignore").write_text("release-artifacts/\n", encoding="utf-8")
        (self.root / "compose.yaml").write_text(
            "services:\n  mariadb:\n    image: mariadb:10.11@sha256:" + "c" * 64 + "\n",
            encoding="utf-8",
        )
        self.output = self.root / "release-artifacts"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def source_runner(self, *, context: str = "unix:///var/run/docker.sock", archive: bytes | None = None) -> FakeRunner:
        if archive is None:
            archive = tar_bytes(None, CONFIG)
        return FakeRunner(self.root, archive, context=context)

    def test_current_dockerfile_inputs_are_pinned_and_frontend_is_recorded(self) -> None:
        dockerfile = self.root / "Dockerfile"
        dockerfile.write_text(
            "# syntax=docker/dockerfile:1\n"
            "FROM " + BASE_1 + " AS deps\n"
            "FROM scratch AS files\n"
            "FROM " + BASE_2 + "\n",
            encoding="utf-8",
        )
        result = package_release.dockerfile_inputs(dockerfile)
        self.assertEqual(result["base_image_refs"], [BASE_1, BASE_2])
        self.assertEqual(result["syntax_frontend_ref"], "docker/dockerfile:1")
        self.assertFalse(result["syntax_frontend_sha256_pinned"])

    def test_mutable_external_from_is_rejected(self) -> None:
        dockerfile = self.root / "Dockerfile"
        dockerfile.write_text("FROM prestashop/prestashop:9.2.0\n", encoding="utf-8")
        with self.assertRaisesRegex(package_release.PackageError, "sha256 digest"):
            package_release.dockerfile_inputs(dockerfile)

    def test_origin_repository_is_normalized_without_credentials(self) -> None:
        def credentialed_url_runner(argv, timeout):
            return subprocess.CompletedProcess(
                argv,
                0,
                "https://operator:private-value@github.com/goldeget/japan-premium-commerce.git",
                "",
            )

        repository = package_release.source_repository(self.root, credentialed_url_runner)
        self.assertEqual(repository, "goldeget/japan-premium-commerce")
        self.assertNotIn("operator", repository)
        self.assertNotIn("private-value", repository)

    def test_real_git_ignores_release_directory_before_it_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / ".gitignore").write_text("release-artifacts/\n", encoding="utf-8")
            (root / ".dockerignore").write_text("release-artifacts/\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(root), "init", "-b", "main"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            output = package_release.validate_release_output_dir(
                root, root / "release-artifacts", package_release._run_command
            )
            self.assertEqual(output, root / "release-artifacts")
            self.assertFalse(output.exists())

    def test_docker_archive_checks_untagged_config_and_layer_reference(self) -> None:
        config = CONFIG
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "test.docker.tar"
            archive_path.write_bytes(tar_bytes(None, config))
            result = package_release.verify_docker_archive(
                archive_path, "sha256:" + hashlib.sha256(config).hexdigest()
            )
        self.assertEqual(result["layer_count"], 1)

    def test_docker_archive_rejects_wrong_config_digest(self) -> None:
        config = CONFIG
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "test.docker.tar"
            archive_path.write_bytes(tar_bytes(None, config))
            with self.assertRaisesRegex(package_release.PackageError, "config digest differs"):
                package_release.verify_docker_archive(archive_path, "sha256:" + "f" * 64)

    def test_docker_archive_rejects_traversal_members(self) -> None:
        result = BytesIO()
        with tarfile.open(fileobj=result, mode="w:") as archive:
            member = tarfile.TarInfo("../escape")
            member.size = 1
            archive.addfile(member, BytesIO(b"x"))
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "unsafe.docker.tar"
            archive_path.write_bytes(result.getvalue())
            with self.assertRaisesRegex(package_release.PackageError, "unsafe member path"):
                package_release.verify_docker_archive(archive_path, IMAGE_ID)

    def test_docker_archive_rejects_any_repository_tags_for_image_id_export(self) -> None:
        tag = package_release.IMAGE_PREFIX + COMMIT
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "tagged.docker.tar"
            archive_path.write_bytes(tar_bytes(tag, CONFIG))
            with self.assertRaisesRegex(package_release.PackageError, "mutable repository tags"):
                package_release.verify_docker_archive(archive_path, IMAGE_ID)

    def test_local_package_builds_saves_removes_tag_loads_and_records_hashes(self) -> None:
        (self.root / "docker" / "Dockerfile").write_text(
            "# syntax=docker/dockerfile:1\nFROM " + BASE_1 + "\nFROM " + BASE_2 + "\n",
            encoding="utf-8",
        )
        config = CONFIG
        tag = package_release.IMAGE_PREFIX + COMMIT
        runner = self.source_runner(archive=tar_bytes(None, config))
        progress: list[str] = []
        result = package_release.package_release(
            self.root, self.output, runner=runner, progress=progress.append
        )
        self.assertTrue(runner.loaded)
        self.assertTrue(runner.tag_removed)
        self.assertEqual(result["source"]["commit_sha"], COMMIT)
        self.assertEqual(result["source"]["gitlink_sha"], THEME)
        self.assertEqual(result["build_inputs"]["base_image_refs"], [BASE_1, BASE_2])
        self.assertEqual(result["application"]["archive_sha256"], hashlib.sha256(tar_bytes(None, config)).hexdigest())
        self.assertEqual(result["application"]["docker_image_config_digest"], IMAGE_ID)
        self.assertEqual(result["registry_manifest_digest"]["value"], None)
        self.assertFalse(result["deployment_authorized"])
        self.assertEqual(result["runtime_acceptance"], "not_checked")
        self.assertEqual(len(progress), 7)
        manifest_name = "ordenowa-prestashop-sha-" + COMMIT + ".release.json"
        written = json.loads((self.output / manifest_name).read_text(encoding="utf-8"))
        self.assertEqual(written["application"]["archive_sha256"], result["application"]["archive_sha256"])
        self.assertEqual(written["source"]["repository"], "goldeget/japan-premium-commerce")
        self.assertEqual(written["database_image_ref"], "mariadb:10.11@sha256:" + "c" * 64)
        self.assertEqual(written["build_input_refs"], [BASE_1, BASE_2])
        self.assertEqual(written["migrations"], [])
        self.assertEqual(written["evidence"], [])
        self.assertEqual(
            set(written),
            {"schema_version", "source", "application", "database_image_ref", "build_input_refs", "migrations", "evidence"},
        )
        self.assertEqual(
            set(written["application"]),
            {"archive_path", "archive_sha256"},
        )
        self.assertFalse(any("push" in command for command in runner.commands))
        self.assertFalse(any("compose" in command for command in runner.commands))
        save_command = next(command for command in runner.commands if "save" in command)
        self.assertEqual(save_command[-1], IMAGE_ID)
        build_command = next(command for command in runner.commands if "build" in command)
        self.assertIn("--tag", build_command)
        self.assertIn(package_release.IMAGE_PREFIX + COMMIT, build_command)
        self.assertNotIn("--build-arg", build_command)
        self.assertNotIn("--secret", build_command)
        load_inspections = [command[-1] for command in runner.commands if "inspect" in command and "image" in command]
        self.assertIn(IMAGE_ID, load_inspections)
        self.assertEqual(result["verification"]["load_verification_scope"], "same_local_daemon_after_tag_removal")
        self.assertEqual(next(command for command in runner.commands if "rm" in command and "image" in command)[-1], tag)

    def test_tag_change_during_export_preserves_archive_and_stops_before_removal(self) -> None:
        (self.root / "docker" / "Dockerfile").write_text("FROM " + BASE_1 + "\n", encoding="utf-8")
        tag = package_release.IMAGE_PREFIX + COMMIT
        runner = self.source_runner(archive=tar_bytes(None, CONFIG))
        runner.mutate_tag_after_first_inspect = True
        with self.assertRaisesRegex(package_release.PackageError, "changed during export"):
            package_release.package_release(self.root, self.output, runner=runner, progress=lambda _: None)
        archive_path = self.output / ("ordenowa-prestashop-sha-" + COMMIT + ".docker.tar")
        self.assertTrue(archive_path.is_file())
        self.assertFalse(runner.tag_removed)
        self.assertFalse(runner.loaded)

    def test_remote_docker_context_is_refused_before_build(self) -> None:
        (self.root / "docker" / "Dockerfile").write_text("FROM " + BASE_1 + "\n", encoding="utf-8")
        runner = self.source_runner(context="ssh://deploy.example.invalid")
        with self.assertRaisesRegex(package_release.PackageError, "remote daemons are refused"):
            package_release.package_release(self.root, self.output, runner=runner, progress=lambda _: None)
        self.assertFalse(any("build" in command for command in runner.commands))

    def test_existing_source_tag_is_not_overwritten(self) -> None:
        (self.root / "docker" / "Dockerfile").write_text("FROM " + BASE_1 + "\n", encoding="utf-8")

        class ExistingTagRunner(FakeRunner):
            def __call__(self, argv, timeout):
                command = list(argv)
                if "image" in command and "ls" in command:
                    self.commands.append(command)
                    return subprocess.CompletedProcess(command, 0, "sha256:existing", "")
                return super().__call__(argv, timeout)

        runner = ExistingTagRunner(self.root, self.source_runner().archive_bytes)
        with self.assertRaisesRegex(package_release.PackageError, "already exists locally"):
            package_release.package_release(self.root, self.output, runner=runner, progress=lambda _: None)
        self.assertFalse(any("build" in command for command in runner.commands))

    def test_output_directory_must_be_the_dual_ignored_release_directory(self) -> None:
        (self.root / "docker" / "Dockerfile").write_text("FROM " + BASE_1 + "\n", encoding="utf-8")
        with self.assertRaisesRegex(package_release.PackageError, "checkout's release-artifacts"):
            package_release.package_release(self.root, self.root / "other-output", runner=self.source_runner())

    def test_symlinked_output_directory_is_refused(self) -> None:
        (self.root / "docker" / "Dockerfile").write_text("FROM " + BASE_1 + "\n", encoding="utf-8")
        original_is_symlink = Path.is_symlink

        def marked_symlink(path: Path) -> bool:
            return path == self.output or original_is_symlink(path)

        with patch.object(Path, "is_symlink", marked_symlink):
            with self.assertRaisesRegex(package_release.PackageError, "must not be a symbolic link"):
                package_release.package_release(self.root, self.output, runner=self.source_runner())

    def test_dangling_archive_symlink_is_an_output_collision(self) -> None:
        (self.root / "docker" / "Dockerfile").write_text("FROM " + BASE_1 + "\n", encoding="utf-8")
        self.output.mkdir()
        archive_path = self.output / ("ordenowa-prestashop-sha-" + COMMIT + ".docker.tar")
        runner = self.source_runner()
        original_exists = Path.exists
        original_is_symlink = Path.is_symlink

        def dangling_exists(path: Path) -> bool:
            return False if path == archive_path else original_exists(path)

        def dangling_is_symlink(path: Path) -> bool:
            return True if path == archive_path else original_is_symlink(path)

        with patch.object(Path, "exists", dangling_exists), patch.object(Path, "is_symlink", dangling_is_symlink):
            with self.assertRaisesRegex(package_release.PackageError, "refusing to overwrite"):
                package_release.package_release(self.root, self.output, runner=runner)
        self.assertFalse(any(command[0] == "docker" for command in runner.commands))

    def test_duplicate_output_for_same_source_is_not_overwritten(self) -> None:
        (self.root / "docker" / "Dockerfile").write_text("FROM " + BASE_1 + "\n", encoding="utf-8")
        self.output.mkdir()
        (self.output / ("ordenowa-prestashop-sha-" + COMMIT + ".docker.tar")).write_bytes(b"keep")
        runner = self.source_runner()
        with self.assertRaisesRegex(package_release.PackageError, "refusing to overwrite"):
            package_release.package_release(self.root, self.output, runner=runner)
        self.assertFalse(any(command[0] == "docker" for command in runner.commands))


if __name__ == "__main__":
    unittest.main()
