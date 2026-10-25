"""Safety contracts for the isolated backup/restore drill runner."""
from __future__ import annotations

import io
import os
from pathlib import Path
import re
import shlex
import subprocess
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tests" / "smoke" / "backup_restore_drill.sh"
DIAGNOSTICS = ROOT / "tests" / "smoke" / "backup_restore_diagnostics.sh"


def file_tree_comparator_program() -> str:
    source = SCRIPT.read_text(encoding="utf-8")
    match = re.search(
        r"(?ms)^compare_file_tree_archives\(\) \{.*?^  python3 - \"\$1\" \"\$2\" <<'FILE_TREE_COMPARATOR_PY'\n(.*?)^FILE_TREE_COMPARATOR_PY$",
        source,
    )
    if match is None:
        raise AssertionError("the backup runner must define its private file-tree archive comparator")
    return match.group(1)


def write_tree_archive(path: Path, entries: list[dict[str, object]], *, archive_format: int) -> None:
    with tarfile.open(path, "w", format=archive_format) as archive:
        for entry in entries:
            info = tarfile.TarInfo(str(entry["name"]))
            info.mode = int(entry.get("mode", 0o640))
            info.uid = int(entry.get("uid", 1000))
            info.gid = int(entry.get("gid", 1000))
            info.mtime = float(entry.get("mtime", 1_700_000_000))
            info.uname = str(entry.get("uname", "backup-user"))
            info.gname = str(entry.get("gname", "backup-group"))
            pax_headers = dict(entry.get("pax_headers", {}))
            if entry.get("pax_comment"):
                pax_headers["comment"] = str(entry["pax_comment"])
            if pax_headers:
                info.pax_headers = pax_headers

            kind = entry.get("kind", "file")
            if kind == "file":
                payload = bytes(entry.get("payload", b""))
                info.type = tarfile.REGTYPE
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
            elif kind == "directory":
                info.type = tarfile.DIRTYPE
                info.size = 0
                archive.addfile(info)
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = str(entry["target"])
                info.size = 0
                archive.addfile(info)
            elif kind == "hardlink":
                info.type = tarfile.LNKTYPE
                info.linkname = str(entry["target"])
                info.size = 0
                archive.addfile(info)
            else:
                raise AssertionError(f"unsupported test archive member kind: {kind}")


def compare_file_tree_archives(first: Path, second: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [os.environ.get("PYTHON", "python3"), "-c", file_tree_comparator_program(), str(first), str(second)],
        text=True,
        capture_output=True,
        check=False,
    )


class BackupRestoreDrillContractTests(unittest.TestCase):
    def run_drill(self, temp: Path, *, project: str, collide_restore_volume: bool = False) -> tuple[subprocess.CompletedProcess[str], str]:
        bin_dir = temp / "bin"
        bin_dir.mkdir(exist_ok=True)
        docker_log = temp / "docker-calls.log"
        docker = bin_dir / "docker"
        collision = "kuranea-ci-123-1-restore_mariadb_data" if collide_restore_volume else "never-collide"
        docker.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> \"$FAKE_DOCKER_LOG\"\n"
            f"case \"$*\" in *'volume ls --format {{.Name}} --filter name={collision}'*) printf '%s\\n' '{collision}'; exit 0 ;; esac\n"
            "exit 1\n",
            encoding="utf-8",
        )
        docker.chmod(0o755)
        runner_temp = temp / "runner-temp"
        runner_temp.mkdir(exist_ok=True)
        github_output = runner_temp / "github-output"
        env = os.environ | {
            "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            "FAKE_DOCKER_LOG": str(docker_log),
            "GITHUB_ACTIONS": "true",
            "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "1",
            "KURANEA_ISOLATED_CI": "1",
            "CI_COMPOSE_PROJECT_NAME": project,
            "SHOP_PORT": "18080",
            "RUNNER_TEMP": str(runner_temp),
            "GITHUB_OUTPUT": str(github_output),
        }
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        return result, docker_log.read_text(encoding="utf-8") if docker_log.exists() else ""

    def test_mismatched_run_project_is_rejected_before_docker_is_called(self) -> None:
        self.assertTrue(SCRIPT.is_file(), "the CI-only backup/restore drill script must exist")
        with tempfile.TemporaryDirectory() as temp_dir:
            result, docker_calls = self.run_drill(Path(temp_dir), project="kuranea")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(docker_calls, "")
        self.assertNotIn("kuranea-ci-123-1", result.stdout + result.stderr)

    def test_existing_restore_volume_stops_before_source_is_stopped_or_written(self) -> None:
        self.assertTrue(SCRIPT.is_file(), "the CI-only backup/restore drill script must exist")
        with tempfile.TemporaryDirectory() as temp_dir:
            result, docker_calls = self.run_drill(
                Path(temp_dir),
                project="kuranea-ci-123-1",
                collide_restore_volume=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("volume ls --format {{.Name}} --filter name=kuranea-ci-123-1-restore_mariadb_data", docker_calls)
        self.assertNotIn("stop kuranea-ci-123-1 prestashop", docker_calls)
        self.assertNotIn("down -v", docker_calls)

    def test_docker_preflight_errors_fail_closed_without_claiming_cleanup_ownership(self) -> None:
        self.assertTrue(SCRIPT.is_file(), "the CI-only backup/restore drill script must exist")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            result, docker_calls = self.run_drill(temp, project="kuranea-ci-123-1")
            github_output = temp / "runner-temp" / "github-output"
            output_text = github_output.read_text(encoding="utf-8") if github_output.exists() else ""

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            docker_calls.strip().splitlines(),
            ["volume ls --format {{.Name}} --filter name=kuranea-ci-123-1-restore_mariadb_data"],
        )
        self.assertNotIn("stop kuranea-ci-123-1 prestashop", docker_calls)
        self.assertNotIn("restore_project_owned=true", output_text)
        self.assertNotIn("down -v", docker_calls)

    def test_restore_volume_configuration_and_labels_are_checked_before_target_writes(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        resource_lookup = source.split("docker_resource_exists() {", 1)[1].split("\n}", 1)[0]
        self.assertIn("ls --format '{{.Name}}'", resource_lookup)
        compose_config = source.index('docker compose -p "$restore_project" config --format json')
        create_mariadb = source.index("create_restore_service mariadb")
        create_prestashop = source.index("create_restore_service prestashop")
        db_volume = source.index('assert_compose_volume "$restore_db_volume" mariadb_data "$restore_project"')
        app_volume = source.index('assert_compose_volume "$restore_app_volume" prestashop_html "$restore_project"')
        queue_volume = source.index('assert_compose_volume "$restore_queue_volume" catalog_review_data "$restore_project"')
        start_database = source.index('docker compose -p "$restore_project" up -d --wait --wait-timeout 300 mariadb')
        clear_target_files = source.index('find /var/www/html -mindepth 1 -maxdepth 1 -exec rm -rf')

        self.assertLess(compose_config, create_mariadb)
        self.assertLess(create_mariadb, create_prestashop)
        self.assertLess(create_prestashop, db_volume)
        self.assertLess(db_volume, app_volume)
        self.assertLess(app_volume, queue_volume)
        self.assertLess(queue_volume, start_database)
        self.assertLess(start_database, clear_target_files)

    def test_restore_create_uses_supported_compose_238_arguments(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        helper = source.split("create_restore_service() {", 1)[1].split("\n}", 1)[0]
        command = next(line.strip() for line in helper.splitlines() if line.strip().startswith("if docker compose "))
        arguments = shlex.split(command.split(' >"$stdout_path"', 1)[0])[1:]

        self.assertEqual(arguments[:5], ["docker", "compose", "-p", "$restore_project", "create"])
        self.assertIn("$service", arguments[5:])
        self.assertNotIn(
            "--no-deps", arguments[5:],
            "Compose 2.38.2 create does not support --no-deps (unlike up and run)",
        )

    def test_restore_create_error_reports_service_and_both_safe_stream_categories(self) -> None:
        self.assertTrue(DIAGNOSTICS.is_file(), "restore container failure needs a dedicated safe classifier")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            stdout_path = temp / "compose-create.stdout"
            stderr_path = temp / "compose-create.stderr"
            stdout_path.write_text("no space left on device password=private-stdout", encoding="utf-8")
            stderr_path.write_text(
                "Error response from daemon: failed to create container token=private-stderr",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    'source "$1"; format_compose_create_failure "$2" "$3" "$4" "$5"',
                    "diagnostics-test",
                    str(DIAGNOSTICS),
                    "prestashop",
                    "125",
                    str(stdout_path),
                    str(stderr_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "service=prestashop; exit=125; stdout=storage_capacity; stderr=daemon_create",
        )
        self.assertNotIn("private-stdout", result.stdout + result.stderr)
        self.assertNotIn("private-stderr", result.stdout + result.stderr)

    def test_classifier_keeps_unrelated_status_and_conflict_text_unclassified(self) -> None:
        self.assertTrue(DIAGNOSTICS.is_file(), "restore container failure needs a dedicated safe classifier")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            stdout_path = temp / "compose-create.stdout"
            stderr_path = temp / "compose-create.stderr"
            stdout_path.write_text("unrelated application response code 429", encoding="utf-8")
            stderr_path.write_text("generic conflict in unrelated diagnostic", encoding="utf-8")
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    'source "$1"; format_compose_create_failure "$2" "$3" "$4" "$5"',
                    "diagnostics-test",
                    str(DIAGNOSTICS),
                    "mariadb",
                    "1",
                    str(stdout_path),
                    str(stderr_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "service=mariadb; exit=1; stdout=unclassified; stderr=unclassified",
        )

    def test_restore_create_failure_adds_allowlisted_versions_and_partial_resource_states(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            docker_log = temp / "docker-calls.log"
            docker = bin_dir / "docker"
            docker.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$*\" >> \"$FAKE_DOCKER_LOG\"\n"
                "case \"$1\" in\n"
                "  version) printf '28.0.1|1.51|28.0.1|1.51\\n' ;;\n"
                "  compose)\n"
                "    if [ \"$2\" = version ]; then printf 'v2.34.0\\n'; exit 0; fi\n"
                "    if [ \"$4\" = ps ] && [ \"$7\" = mariadb ]; then printf 'aaaaaaaaaaaa\\n'; exit 0; fi\n"
                "    if [ \"$4\" = ps ] && [ \"$7\" = prestashop ]; then exit 0; fi\n"
                "    exit 1 ;;\n"
                "  ps) printf 'aaaaaaaaaaaa\\nbbbbbbbbbbbb\\n' ;;\n"
                "  volume) printf 'private-volume-name\\n' ;;\n"
                "  network) printf 'private-network-name\\n' ;;\n"
                "  inspect) printf 'created\\n' ;;\n"
                "  *) exit 1 ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            docker.chmod(0o755)
            stdout_path = temp / "compose-create.stdout"
            stderr_path = temp / "compose-create.stderr"
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("create failed token=private-create-stderr", encoding="utf-8")

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    'source "$1"; format_compose_create_failure "$2" "$3" "$4" "$5" "$6"',
                    "diagnostics-test",
                    str(DIAGNOSTICS),
                    "mariadb",
                    "1",
                    str(stdout_path),
                    str(stderr_path),
                    "kuranea-ci-123-1-restore",
                ],
                env=os.environ | {
                    "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                    "FAKE_DOCKER_LOG": str(docker_log),
                },
                text=True,
                capture_output=True,
                check=False,
            )
            docker_calls = docker_log.read_text(encoding="utf-8") if docker_log.exists() else ""

        self.assertEqual(result.returncode, 0, result.stderr)
        summary = result.stdout.strip()
        for field in (
            "service=mariadb; exit=1; stdout=no_diagnostic; stderr=unclassified",
            "docker_client_version=28.0.1",
            "docker_client_api=1.51",
            "docker_server_version=28.0.1",
            "docker_server_api=1.51",
            "compose_version=v2.34.0",
            "restore_containers=2",
            "restore_volumes=1",
            "restore_networks=1",
            "mariadb_state=created",
            "prestashop_state=none",
        ):
            self.assertIn(field, summary)
        for private_value in (
            "private-create-stderr",
            "private-volume-name",
            "private-network-name",
            "aaaaaaaaaaaa",
            "bbbbbbbbbbbb",
            "kuranea-ci-123-1-restore",
        ):
            self.assertNotIn(private_value, summary)
        self.assertIn("label=com.docker.compose.project=kuranea-ci-123-1-restore", docker_calls)

    def test_restore_create_failure_context_uses_unavailable_markers_when_probes_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            docker = bin_dir / "docker"
            docker.write_text(
                "#!/bin/sh\n"
                "case \"$1\" in\n"
                "  version) printf 'private-daemon-output password=private-version\\n'; exit 1 ;;\n"
                "  compose) printf 'private-compose-output\\n' >&2; exit 1 ;;\n"
                "  ps|volume|network) printf 'private-resource-id\\n'; exit 1 ;;\n"
                "  inspect) printf 'private-state\\n'; exit 1 ;;\n"
                "  *) exit 1 ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            docker.chmod(0o755)
            stdout_path = temp / "compose-create.stdout"
            stderr_path = temp / "compose-create.stderr"
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("docker create private-create-stderr", encoding="utf-8")

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    'source "$1"; format_compose_create_failure "$2" "$3" "$4" "$5" "$6"',
                    "diagnostics-test",
                    str(DIAGNOSTICS),
                    "mariadb",
                    "1",
                    str(stdout_path),
                    str(stderr_path),
                    "kuranea-ci-123-1-restore",
                ],
                env=os.environ | {
                    "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                },
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        summary = result.stdout.strip()
        for field in (
            "service=mariadb; exit=1; stdout=no_diagnostic; stderr=unclassified",
            "docker_client_version=unavailable",
            "docker_client_api=unavailable",
            "docker_server_version=unavailable",
            "docker_server_api=unavailable",
            "compose_version=unavailable",
            "restore_containers=unavailable",
            "restore_volumes=unavailable",
            "restore_networks=unavailable",
            "mariadb_state=unavailable",
            "prestashop_state=unavailable",
        ):
            self.assertIn(field, summary)
        for private_value in (
            "private-daemon-output",
            "private-version",
            "private-compose-output",
            "private-resource-id",
            "private-state",
            "private-create-stderr",
        ):
            self.assertNotIn(private_value, summary)

    def test_restored_prestart_file_trees_are_compared_without_output(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("restored_app_archive", source)
        self.assertIn("restored_queue_archive", source)
        self.assertIn('compare_file_tree_archives "$app_archive" "$restored_app_archive"', source)
        self.assertIn('compare_file_tree_archives "$queue_archive" "$restored_queue_archive"', source)
        self.assertNotIn('cmp -s "$app_archive" "$restored_app_archive"', source)
        self.assertNotIn('cmp -s "$queue_archive" "$restored_queue_archive"', source)

    def test_equivalent_file_trees_ignore_tar_order_headers_and_directory_timestamps(self) -> None:
        comparator = file_tree_comparator_program()
        self.assertTrue(comparator.strip())
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            original = temp / "original.tar"
            restored = temp / "restored.tar"
            write_tree_archive(
                original,
                [
                    {"name": ".", "kind": "directory", "mode": 0o755, "uid": 0, "gid": 0, "mtime": 1_700_000_000},
                    {"name": "./assets", "kind": "directory", "mode": 0o750, "uid": 1000, "gid": 1000, "mtime": 1_700_000_001},
                    {"name": "./assets/logo.bin", "payload": b"private-image-bytes", "mtime": 1_700_000_002},
                    {"name": "./assets/current", "kind": "symlink", "target": "logo.bin", "mtime": 1_700_000_003},
                ],
                archive_format=tarfile.USTAR_FORMAT,
            )
            write_tree_archive(
                restored,
                [
                    {"name": "assets/current", "kind": "symlink", "target": "logo.bin", "mtime": 1_700_000_003, "pax_comment": "different-header"},
                    {"name": "assets/logo.bin", "payload": b"private-image-bytes", "mtime": 1_700_000_002, "pax_comment": "different-header"},
                    {"name": "assets", "kind": "directory", "mode": 0o750, "uid": 1000, "gid": 1000, "mtime": 1_799_999_999, "pax_comment": "different-header"},
                    {"name": "", "kind": "directory", "mode": 0o755, "uid": 0, "gid": 0, "mtime": 1_799_999_999, "pax_comment": "different-header"},
                ],
                archive_format=tarfile.PAX_FORMAT,
            )

            result = compare_file_tree_archives(original, restored)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_root_directory_names_are_canonical_and_root_metadata_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            expected = temp / "expected.tar"
            write_tree_archive(
                expected,
                [
                    {"name": ".", "kind": "directory", "mode": 0o755, "uid": 0, "gid": 0},
                    {"name": "shop.txt", "payload": b"same", "mtime": 1_700_000_000},
                ],
                archive_format=tarfile.USTAR_FORMAT,
            )
            equivalent = temp / "equivalent.tar"
            write_tree_archive(
                equivalent,
                [
                    {"name": "", "kind": "directory", "mode": 0o755, "uid": 0, "gid": 0, "mtime": 1_799_999_999, "pax_comment": "different-header"},
                    {"name": "shop.txt", "payload": b"same", "mtime": 1_700_000_000, "pax_comment": "different-header"},
                ],
                archive_format=tarfile.PAX_FORMAT,
            )

            equivalent_result = compare_file_tree_archives(expected, equivalent)
            self.assertEqual(equivalent_result.returncode, 0, equivalent_result.stderr)
            self.assertEqual(equivalent_result.stdout, "")
            self.assertEqual(equivalent_result.stderr, "")

            for mismatch, root_metadata in (
                ("mode", {"mode": 0o700, "uid": 0, "gid": 0}),
                ("ownership", {"mode": 0o755, "uid": 1000, "gid": 0}),
            ):
                with self.subTest(root_metadata=mismatch):
                    changed_root = temp / f"root-{mismatch}.tar"
                    write_tree_archive(
                        changed_root,
                        [
                            {"name": "", "kind": "directory", **root_metadata},
                            {"name": "shop.txt", "payload": b"same", "mtime": 1_700_000_000},
                        ],
                        archive_format=tarfile.PAX_FORMAT,
                    )

                    result = compare_file_tree_archives(expected, changed_root)

                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "")

    def test_archive_member_paths_reject_absolute_and_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            for unsafe_name in ("/absolute.txt", "folder/../outside.txt"):
                with self.subTest(path_kind=unsafe_name.startswith("/")):
                    archive = temp / f"unsafe-{len(unsafe_name)}.tar"
                    write_tree_archive(
                        archive,
                        [{"name": unsafe_name, "payload": b"private-path-fixture"}],
                        archive_format=tarfile.PAX_FORMAT,
                    )

                    result = compare_file_tree_archives(archive, archive)

                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "")

    def test_archive_member_paths_reject_duplicate_canonical_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "duplicate.tar"
            write_tree_archive(
                archive,
                [
                    {"name": "./file.txt", "payload": b"first"},
                    {"name": "file.txt", "payload": b"second"},
                ],
                archive_format=tarfile.PAX_FORMAT,
            )

            result = compare_file_tree_archives(archive, archive)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_archive_rejects_hard_links_with_unsafe_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            for unsafe_target in ("../outside.txt", "/absolute-target.txt"):
                with self.subTest(target_kind=unsafe_target.startswith("/")):
                    archive = temp / f"hardlink-{len(unsafe_target)}.tar"
                    write_tree_archive(
                        archive,
                        [{"name": "link.txt", "kind": "hardlink", "target": unsafe_target}],
                        archive_format=tarfile.PAX_FORMAT,
                    )

                    result = compare_file_tree_archives(archive, archive)

                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "")

    def test_changed_content_missing_entries_or_required_metadata_are_rejected_silently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            expected = temp / "expected.tar"
            write_tree_archive(
                expected,
                [
                    {"name": "file.txt", "payload": b"private-original-content", "mode": 0o640, "uid": 1000, "gid": 1000, "mtime": 1_700_000_000},
                    {"name": "shortcut", "kind": "symlink", "target": "file.txt", "mode": 0o777},
                ],
                archive_format=tarfile.PAX_FORMAT,
            )
            mismatches = {
                "changed content": [
                    {"name": "file.txt", "payload": b"private-changed-content", "mode": 0o640, "uid": 1000, "gid": 1000, "mtime": 1_700_000_000},
                    {"name": "shortcut", "kind": "symlink", "target": "file.txt", "mode": 0o777},
                ],
                "missing entry": [
                    {"name": "file.txt", "payload": b"private-original-content", "mode": 0o640, "uid": 1000, "gid": 1000, "mtime": 1_700_000_000},
                ],
                "mode": [
                    {"name": "file.txt", "payload": b"private-original-content", "mode": 0o600, "uid": 1000, "gid": 1000, "mtime": 1_700_000_000},
                    {"name": "shortcut", "kind": "symlink", "target": "file.txt", "mode": 0o777},
                ],
                "ownership": [
                    {"name": "file.txt", "payload": b"private-original-content", "mode": 0o640, "uid": 1001, "gid": 1000, "mtime": 1_700_000_000},
                    {"name": "shortcut", "kind": "symlink", "target": "file.txt", "mode": 0o777},
                ],
                "group ownership": [
                    {"name": "file.txt", "payload": b"private-original-content", "mode": 0o640, "uid": 1000, "gid": 1001, "mtime": 1_700_000_000},
                    {"name": "shortcut", "kind": "symlink", "target": "file.txt", "mode": 0o777},
                ],
                "modification time": [
                    {"name": "file.txt", "payload": b"private-original-content", "mode": 0o640, "uid": 1000, "gid": 1000, "mtime": 1_700_000_001},
                    {"name": "shortcut", "kind": "symlink", "target": "file.txt", "mode": 0o777},
                ],
                "extended attribute": [
                    {"name": "file.txt", "payload": b"private-original-content", "mode": 0o640, "uid": 1000, "gid": 1000, "mtime": 1_700_000_000, "pax_headers": {"SCHILY.xattr.user.label": "original"}},
                    {"name": "shortcut", "kind": "symlink", "target": "file.txt", "mode": 0o777},
                ],
                "symlink target": [
                    {"name": "file.txt", "payload": b"private-original-content", "mode": 0o640, "uid": 1000, "gid": 1000, "mtime": 1_700_000_000},
                    {"name": "shortcut", "kind": "symlink", "target": "different-target", "mode": 0o777},
                ],
            }

            for name, entries in mismatches.items():
                with self.subTest(mismatch=name):
                    actual = temp / f"{name.replace(' ', '-')}.tar"
                    write_tree_archive(actual, entries, archive_format=tarfile.PAX_FORMAT)

                    result = compare_file_tree_archives(expected, actual)

                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "")

    def test_final_cleanup_attempts_main_project_even_if_restore_cleanup_fails(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        cleanup = workflow.split("- name: Remove only this run's containers and volumes", 1)[1]
        target_down = cleanup.index('if ! docker compose -p "$restore_project" down -v --remove-orphans')
        mailpit_cleanup = cleanup.index('docker rm -f "${BASH_REMATCH[1]}"')
        source_down = cleanup.index('docker compose -p "$CI_COMPOSE_PROJECT_NAME" down -v --remove-orphans')

        self.assertLess(target_down, mailpit_cleanup)
        self.assertLess(mailpit_cleanup, source_down)
        self.assertIn("cleanup_failed=1", cleanup)

    def test_workflow_requires_restore_drill_and_retains_only_its_safe_log(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        step = workflow.split("- name: Verify run-scoped CI backup and isolated restore", 1)[1].split("- name:", 1)[0]
        aggregate = workflow.split("- name: Aggregate browser QA and postal verification failures", 1)[1]
        coverage = workflow.split("- name: Verify browser QA screenshot coverage", 1)[1].split("- name:", 1)[0]
        cleanup = workflow.split("- name: Remove only this run's containers and volumes", 1)[1]

        self.assertIn("id: backup_restore_drill", step)
        self.assertIn("tests/smoke/backup_restore_drill.sh", step)
        self.assertIn("backup-restore-drill.log", step)
        self.assertIn("BACKUP_RESTORE_DRILL_OUTCOME: ${{ steps.backup_restore_drill.outcome }}", aggregate)
        self.assertIn('"backup_restore_drill=$BACKUP_RESTORE_DRILL_OUTCOME"', aggregate)
        self.assertIn("backup-restore-drill.log", coverage)
        self.assertIn("steps.backup_restore_drill.outputs.restore_project_owned", cleanup)
        self.assertIn("tests/smoke/test_backup_restore_drill_contract.py", workflow)
        self.assertIn("tests/smoke/backup_restore_diagnostics.sh", workflow)
        self.assertEqual(workflow.count("'tests/smoke/test_backup_restore_drill_contract.py'"), 2)


if __name__ == "__main__":
    unittest.main()
