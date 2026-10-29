from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "release"))
import ci_release


SOURCE_SHA = "a" * 40
GITLINK_SHA = "b" * 40
IMAGE_ID = "sha256:" + "c" * 64
BASE_REF = "composer:2@sha256:" + "d" * 64
DATABASE_REF = "mariadb:10.11@sha256:" + "e" * 64
MANIFEST_VALID = lambda root, path: {"status": "ok", "deployment_authorized": False}


class FakeDocker:
    def __init__(self, *, occupied: bool = False, wrong_labels: bool = False) -> None:
        self.occupied = occupied
        self.wrong_labels = wrong_labels
        self.tagged = False
        self.commands: list[list[str]] = []

    def __call__(self, argv: Any, timeout: int) -> subprocess.CompletedProcess[str]:
        command = list(argv)
        self.commands.append(command)
        if "image" in command and "ls" in command:
            out = IMAGE_ID if self.occupied else ""
            return subprocess.CompletedProcess(command, 0, out, "")
        if "image" in command and "tag" in command:
            self.tagged = True
            return subprocess.CompletedProcess(command, 0, "", "")
        if "image" in command and "rm" in command:
            self.tagged = False
            return subprocess.CompletedProcess(command, 0, "", "")
        if "image" in command and "inspect" in command:
            image = command[-1]
            is_tag = image.startswith(ci_release.RUN_TAG_PREFIX)
            labels = {
                "org.opencontainers.image.revision": "f" * 40 if self.wrong_labels else SOURCE_SHA,
                "com.ordenowa.theme.gitlink": GITLINK_SHA,
            }
            value = {
                "Id": IMAGE_ID,
                "RepoTags": [image] if is_tag and self.tagged else [],
                "Os": "linux",
                "Architecture": "amd64",
                "Config": {"Labels": labels},
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(value), "")
        raise AssertionError("unexpected Docker invocation: " + repr(command))


class CiReleasePackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "checkout"
        self.artifacts = self.root / "release-artifacts"
        self.artifacts.mkdir(parents=True)
        self.qa = Path(self.temporary.name) / "qa"
        self.qa.mkdir()
        self.env_file = Path(self.temporary.name) / "github-env"
        self.env_file.write_text("", encoding="utf-8")
        prefix = "ordenowa-prestashop-sha-" + SOURCE_SHA
        self.proof_path = self.artifacts / (prefix + ".package.json")
        self.manifest_path = self.artifacts / (prefix + ".release.json")
        self.archive_path = self.artifacts / (prefix + ".docker.tar")
        self.archive_path.write_bytes(b"synthetic docker-save archive bytes")
        archive_hash = hashlib.sha256(self.archive_path.read_bytes()).hexdigest()
        self.proof = {
            "schema_version": 1,
            "source": {"commit_sha": SOURCE_SHA, "gitlink_path": "themes/hummingbird", "gitlink_sha": GITLINK_SHA},
            "release_manifest_file": self.manifest_path.name,
            "application": {
                "archive_file": self.archive_path.name,
                "archive_path": "release-artifacts/" + self.archive_path.name,
                "archive_sha256": archive_hash,
                "docker_image_config_digest": IMAGE_ID,
            },
            "build_inputs": {"base_image_refs": [BASE_REF], "syntax_frontend_ref": "docker/dockerfile:1", "syntax_frontend_sha256_pinned": False},
            "verification": {
                "archive_untagged_image_id_checked": True,
                "archive_config_digest_checked": True,
                "archive_layer_references_present": 4,
                "removed_built_tag_before_load": True,
                "loaded_without_rebuild": True,
                "loaded_config_digest_matches": True,
                "loaded_image_id_inspected": True,
                "load_verification_scope": "same_local_daemon_after_tag_removal",
            },
            "registry_manifest_digest": {"status": "not_published_or_checked", "value": None},
            "runtime_acceptance": "not_checked",
            "deployment_authorized": False,
        }
        self.manifest = {
            "schema_version": 1,
            "source": {
                "repository": "goldeget/japan-premium-commerce",
                "commit_sha": SOURCE_SHA,
                "gitlink_path": "themes/hummingbird",
                "gitlink_sha": GITLINK_SHA,
            },
            "application": {
                "archive_path": "release-artifacts/" + self.archive_path.name,
                "archive_sha256": archive_hash,
            },
            "database_image_ref": DATABASE_REF,
            "build_input_refs": [BASE_REF],
            "migrations": [],
            "evidence": [],
        }
        self.proof_path.write_text(json.dumps(self.proof), encoding="utf-8")
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def _verify_records(self) -> dict[str, Any]:
        return ci_release.verify_package_records(
            self.root, self.proof_path, self.manifest_path, self.archive_path,
            SOURCE_SHA, manifest_validator=MANIFEST_VALID,
        )

    def _prepare(self, runner: FakeDocker | None = None) -> dict[str, Any]:
        return ci_release.prepare_ci_image(
            self.root, self.proof_path, self.manifest_path, self.archive_path,
            SOURCE_SHA, "431", "2", self.qa, self.env_file,
            runner=runner or FakeDocker(), manifest_validator=MANIFEST_VALID,
        )

    def test_preparation_tags_only_the_loaded_image_id_and_exports_allowlisted_values(self) -> None:
        runner = FakeDocker()
        selection = self._prepare(runner)
        self.assertTrue(selection["passed"])
        self.assertEqual(selection["source_sha"], SOURCE_SHA)
        self.assertEqual(selection["docker_image_config_digest"], IMAGE_ID)
        tag_calls = [call for call in runner.commands if "image" in call and "tag" in call]
        self.assertEqual(len(tag_calls), 1)
        self.assertEqual(tag_calls[0][-2:], [IMAGE_ID, selection["image_ref"]])
        env_lines = self.env_file.read_text(encoding="utf-8").splitlines()
        self.assertIn("ORDENOWA_CI_IMAGE_ID=" + IMAGE_ID, env_lines)
        self.assertIn("ORDENOWA_CI_SOURCE_SHA=" + SOURCE_SHA, env_lines)
        self.assertNotIn("MARIADB_PASSWORD", self.env_file.read_text(encoding="utf-8"))
        self.assertTrue((self.qa / "ci-package-selection.json").is_file())

    def test_archive_hash_or_source_mismatch_fails_before_tagging(self) -> None:
        runner = FakeDocker()
        self.archive_path.write_bytes(b"changed after package proof")
        with self.assertRaisesRegex(ci_release.CiReleaseError, "archive_hash_mismatch"):
            self._prepare(runner)
        self.assertFalse(any("tag" in command for command in runner.commands))

    def test_package_commit_mismatch_fails_before_tagging(self) -> None:
        self.proof["source"]["commit_sha"] = "f" * 40
        self.proof_path.write_text(json.dumps(self.proof), encoding="utf-8")
        runner = FakeDocker()
        with self.assertRaisesRegex(ci_release.CiReleaseError, "release_source_sha_mismatch"):
            self._prepare(runner)
        self.assertFalse(any("tag" in command for command in runner.commands))

    def test_existing_run_tag_is_never_replaced(self) -> None:
        runner = FakeDocker(occupied=True)
        with self.assertRaisesRegex(ci_release.CiReleaseError, "run_image_tag_already_exists"):
            self._prepare(runner)
        self.assertFalse(any("tag" in command for command in runner.commands))

    def test_image_source_label_mismatch_stops_before_tagging(self) -> None:
        runner = FakeDocker(wrong_labels=True)
        with self.assertRaisesRegex(ci_release.CiReleaseError, "image_source_label_mismatch"):
            self._prepare(runner)
        self.assertFalse(any("tag" in command for command in runner.commands))

    def test_compose_selection_and_runtime_image_id_must_match_package(self) -> None:
        runner = FakeDocker()
        selection = self._prepare(runner)
        compose_config = self.qa / "compose-config.json"
        compose_config.write_text(json.dumps({"services": {"prestashop": {"image": selection["image_ref"]}}}), encoding="utf-8")
        ci_release.verify_prepared_image(
            self.root, self.proof_path, self.manifest_path, self.archive_path,
            SOURCE_SHA, selection["image_ref"], IMAGE_ID,
            self.qa / "ci-package-selection.json", compose_config,
            runner=runner, manifest_validator=MANIFEST_VALID,
        )
        with self.assertRaisesRegex(ci_release.CiReleaseError, "compose_does_not_select_package_image"):
            compose_config.write_text(json.dumps({"services": {"prestashop": {"image": "mutable:latest"}}}), encoding="utf-8")
            ci_release.verify_prepared_image(
                self.root, self.proof_path, self.manifest_path, self.archive_path,
                SOURCE_SHA, selection["image_ref"], IMAGE_ID,
                self.qa / "ci-package-selection.json", compose_config,
                runner=runner, manifest_validator=MANIFEST_VALID,
            )
        with self.assertRaisesRegex(ci_release.CiReleaseError, "runtime_container_image_mismatch"):
            ci_release.record_runtime_binding(
                self.qa / "ci-package-selection.json", self.qa / "runtime.json",
                "sha256:" + "f" * 64, selection["image_ref"], application_hot_copy=False,
            )
        with self.assertRaisesRegex(ci_release.CiReleaseError, "application_hot_copy_not_allowed_for_package"):
            ci_release.record_runtime_binding(
                self.qa / "ci-package-selection.json", self.qa / "runtime-hot-copy.json",
                IMAGE_ID, selection["image_ref"], application_hot_copy=True,
            )

    def test_final_binding_requires_all_39_phases_cleanup_and_verified_restore(self) -> None:
        selection = self._prepare()
        ci_release.record_runtime_binding(
            self.qa / "ci-package-selection.json", self.qa / "package-runtime-binding.json",
            IMAGE_ID, selection["image_ref"], application_hot_copy=False,
        )
        qa = {"passed": True, "cleanup": "success", "phases": {phase: "passed" for phase in ci_release.REQUIRED_PHASES}}
        qa_path = self.qa / "outcome.json"
        qa_path.write_text(json.dumps(qa), encoding="utf-8")
        restore_path = self.qa / "encrypted-restore-outcome.json"
        restore_path.write_text(json.dumps({
            "passed": True, "decrypt_roundtrip_verified": True,
            "ciphertext_tamper_rejected": True, "wrong_identity_rejected": True,
            "database_restore_verified": True,
        }), encoding="utf-8")
        output = self.qa / "release-qa-binding.json"
        result = ci_release.bind_qa(
            root=self.root, proof_path=self.proof_path, manifest_path=self.manifest_path,
            archive_path=self.archive_path, expected_source_sha=SOURCE_SHA,
            selection_path=self.qa / "ci-package-selection.json",
            runtime_binding_path=self.qa / "package-runtime-binding.json",
            qa_outcome_path=qa_path, restore_outcome_path=restore_path,
            output_path=output, package_status="success", acceptance_status="success",
            cleanup_status="success", manifest_validator=MANIFEST_VALID,
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["qa"]["phase_count"], 39)
        self.assertTrue(result["qa"]["encrypted_restore_passed"])
        self.assertFalse(result["application"]["application_hot_copy"])
        self.assertFalse(result["deployment_authorized"])
        runtime_binding_path = self.qa / "package-runtime-binding.json"
        runtime_binding = json.loads(runtime_binding_path.read_text(encoding="utf-8"))
        runtime_binding["application_hot_copy"] = True
        runtime_binding_path.write_text(json.dumps(runtime_binding), encoding="utf-8")
        with self.assertRaisesRegex(ci_release.CiReleaseError, "runtime_application_hot_copy_not_false"):
            ci_release.bind_qa(
                root=self.root, proof_path=self.proof_path, manifest_path=self.manifest_path,
                archive_path=self.archive_path, expected_source_sha=SOURCE_SHA,
                selection_path=self.qa / "ci-package-selection.json",
                runtime_binding_path=runtime_binding_path,
                qa_outcome_path=qa_path, restore_outcome_path=restore_path,
                output_path=output, package_status="success", acceptance_status="success",
                cleanup_status="success", manifest_validator=MANIFEST_VALID,
            )
        runtime_binding["application_hot_copy"] = False
        runtime_binding_path.write_text(json.dumps(runtime_binding), encoding="utf-8")
        qa["phases"]["restore"] = "failed"
        qa_path.write_text(json.dumps(qa), encoding="utf-8")
        with self.assertRaisesRegex(ci_release.CiReleaseError, "qa_aggregate_not_passed|qa_phase_not_passed"):
            ci_release.bind_qa(
                root=self.root, proof_path=self.proof_path, manifest_path=self.manifest_path,
                archive_path=self.archive_path, expected_source_sha=SOURCE_SHA,
                selection_path=self.qa / "ci-package-selection.json",
                runtime_binding_path=self.qa / "package-runtime-binding.json",
                qa_outcome_path=qa_path, restore_outcome_path=restore_path,
                output_path=output, package_status="success", acceptance_status="success",
                cleanup_status="success", manifest_validator=MANIFEST_VALID,
            )

    def test_contract_keeps_legacy_build_mode_and_uses_package_for_ci_runtime(self) -> None:
        stage_root = Path(__file__).resolve().parents[2]
        acceptance = (stage_root / "tests/procurement/ci_acceptance.sh").read_text(encoding="utf-8")
        restore = (stage_root / "tests/procurement/ci_restore.sh").read_text(encoding="utf-8")
        overlay = (stage_root / "tests/procurement/ci.package.compose.yaml").read_text(encoding="utf-8")
        workflow = (stage_root / ".github/workflows/procurement-platform.yml").read_text(encoding="utf-8")
        package_workflow = (stage_root / ".github/workflows/release-package.yml").read_text(encoding="utf-8")
        copy_helper = (stage_root / "tests/procurement/ci_acceptance_copy.sh").read_text(encoding="utf-8")
        self.assertIn("tests/procurement/ci.package.compose.yaml", acceptance)
        self.assertIn("tests/procurement/ci.package.compose.yaml", restore)
        self.assertIn("ci_release.py verify", acceptance)
        self.assertIn("ci_release.py attest-runtime", acceptance)
        self.assertIn("source tests/procurement/ci_acceptance_copy.sh", acceptance)
        self.assertIn("copy_acceptance_files", acceptance)
        self.assertLess(acceptance.index("copy_acceptance_files"), acceptance.index("ci_release.py attest-runtime"))
        self.assertNotIn("compose cp modules/ordenowaprocurement/.", acceptance)
        self.assertIn("ORDENOWA_APPLICATION_HOT_COPY", acceptance)
        self.assertIn('if [[ -n ${ORDENOWA_CI_IMAGE_REF:-} ]]; then', copy_helper)
        self.assertIn("ORDENOWA_APPLICATION_HOT_COPY=false", copy_helper)
        self.assertIn("ORDENOWA_APPLICATION_HOT_COPY=true", copy_helper)
        self.assertIn("compose cp modules/ordenowaprocurement/.", copy_helper)
        self.assertIn("compose build prestashop", acceptance)
        self.assertIn("compose up --detach --no-build", acceptance)
        self.assertIn("image: ${ORDENOWA_CI_IMAGE_REF", overlay)
        self.assertIn("pull_policy: never", overlay)
        self.assertLess(workflow.index("id: release_package"), workflow.index("id: acceptance"))
        self.assertIn("tools/release/package_release.py", workflow)
        self.assertIn("tools/release/ci_release.py prepare", workflow)
        self.assertIn("ci_release.py bind", workflow)
        self.assertIn("DOCKER_CONTEXT: default", workflow)
        self.assertIn("      - '.gitattributes'", workflow)
        self.assertIn("test_checkout_line_endings.py", workflow)
        self.assertIn("ORDENOWA_CI_IMAGE_ID", workflow)
        upload_section = workflow[workflow.index("name: Upload redacted outcomes and captures"):workflow.index("name: Remove the private release archive")]
        self.assertIn("*.package.json", upload_section)
        self.assertIn("*.release.json", upload_section)
        self.assertNotIn("*.docker.tar", upload_section)
        self.assertIn("workflow_dispatch:", package_workflow)
        self.assertNotIn("\n  push:", package_workflow)
        required = re.search(r"required = \((.*?)\)", acceptance, re.DOTALL)
        self.assertIsNotNone(required)
        self.assertEqual(tuple(re.findall(r"'([^']+)'", required.group(1))), ci_release.REQUIRED_PHASES)
        self.assertEqual(len(ci_release.REQUIRED_PHASES), 39)

    def test_package_mode_copies_test_fixtures_but_never_hot_copies_application(self) -> None:
        stage_root = Path(__file__).resolve().parents[2]
        helper = stage_root / "tests/procurement/ci_acceptance_copy.sh"
        bash = None
        if os.name == "nt":
            git_bash = Path("C:/Program Files/Git/bin/bash.exe")
            bash = str(git_bash) if git_bash.is_file() else None
        if bash is None:
            bash = shutil.which("bash")
        if bash is None:
            self.skipTest("Bash is required to execute the copy branch contract")
        helper_path = helper.as_posix()
        if os.name == "nt" and re.match(r"^[A-Za-z]:/", helper_path):
            helper_path = "/" + helper_path[0].lower() + helper_path[2:]
        script = (
            'source "$CI_COPY_HELPER"\n'
            'compose() { printf "%s\\n" "$*" >> "$MOCK_COMPOSE_LOG"; }\n'
            'copy_acceptance_files\n'
            'printf "hot_copy=%s\\n" "$ORDENOWA_APPLICATION_HOT_COPY"\n'
        )

        package_log = self.qa / "package-compose.log"
        package_env = os.environ.copy()
        package_env.update({
            "CI_COPY_HELPER": helper_path,
            "MOCK_COMPOSE_LOG": str(package_log),
            "ORDENOWA_CI_IMAGE_REF": "local-only/ordenowa-procurement-ci:run-1-1",
        })
        package_result = subprocess.run([bash, "-c", script], cwd=stage_root, env=package_env, text=True, capture_output=True)
        self.assertEqual(package_result.returncode, 0, package_result.stderr)
        self.assertIn("hot_copy=false", package_result.stdout)
        package_commands = package_log.read_text(encoding="utf-8")
        self.assertNotIn("modules/ordenowaprocurement", package_commands)
        self.assertNotIn("themes/kuranea", package_commands)
        self.assertIn("/var/www/html/tests/procurement/", package_commands)
        self.assertIn("tests/catalog/", package_commands)
        self.assertIn("chmod", package_commands)
        self.assertNotIn("chown -R www-data:www-data /var/www/html/modules/ordenowaprocurement", package_commands)

        legacy_log = self.qa / "legacy-compose.log"
        legacy_env = os.environ.copy()
        legacy_env.update({"CI_COPY_HELPER": helper_path, "MOCK_COMPOSE_LOG": str(legacy_log)})
        legacy_env.pop("ORDENOWA_CI_IMAGE_REF", None)
        legacy_result = subprocess.run([bash, "-c", script], cwd=stage_root, env=legacy_env, text=True, capture_output=True)
        self.assertEqual(legacy_result.returncode, 0, legacy_result.stderr)
        self.assertIn("hot_copy=true", legacy_result.stdout)
        legacy_commands = legacy_log.read_text(encoding="utf-8")
        self.assertIn("modules/ordenowaprocurement", legacy_commands)
        self.assertIn("themes/kuranea/templates/_partials/footer.tpl", legacy_commands)
        self.assertIn("chown -R www-data:www-data /var/www/html/modules/ordenowaprocurement", legacy_commands)


if __name__ == "__main__":
    unittest.main()
