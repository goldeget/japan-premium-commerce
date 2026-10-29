from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

test_dir = Path(__file__).resolve().parent
repository_root = Path(__file__).resolve().parents[2]
for module_dir in (repository_root / "tools" / "release", test_dir):
    if (module_dir / "release_manifest.py").is_file():
        sys.path.insert(0, str(module_dir))
        break
import release_manifest


SHA_A = "a" * 64
SHA_B = "b" * 64


def run_git(path: Path, *args: str, config: bool = False) -> str:
    prefix = ["git", "-C", str(path)]
    if config:
        prefix += ["-c", "user.name=Release Manifest Tests", "-c", "user.email=release-tests@example.invalid"]
    completed = subprocess.run(
        prefix + list(args),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.theme_source = self.base / "theme-source"
        self.theme_source.mkdir()
        self.manifest_path = self.base / "release-manifest.json"

        run_git(self.theme_source, "init", "-b", "main")
        run_git(self.theme_source, "config", "user.name", "Test")
        run_git(self.theme_source, "config", "user.email", "test@example.invalid")
        (self.theme_source / "README.md").write_text("theme\n", encoding="utf-8")
        run_git(self.theme_source, "add", "README.md")
        run_git(self.theme_source, "commit", "-m", "theme seed", config=True)
        self.theme_sha = run_git(self.theme_source, "rev-parse", "HEAD")

        run_git(self.root, "init", "-b", "main")
        run_git(self.root, "config", "user.name", "Test")
        run_git(self.root, "config", "user.email", "test@example.invalid")
        (self.root / "release").mkdir()
        (self.root / "modules" / "ordenowaprocurement" / "upgrade").mkdir(parents=True)
        (self.root / "docs" / "evidence").mkdir(parents=True)
        (self.root / "release" / "app.oci.tar").write_bytes(b"opaque image archive fixture\n")
        (self.root / "modules" / "ordenowaprocurement" / "upgrade" / "upgrade-1.0.1.php").write_text(
            "<?php return true;\n", encoding="utf-8"
        )
        (self.root / "docs" / "evidence" / "smoke.txt").write_text("smoke passed\n", encoding="utf-8")
        run_git(
            self.root,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(self.theme_source),
            "themes/hummingbird",
        )
        run_git(self.root, "add", "-A")
        run_git(self.root, "commit", "-m", "release fixture", config=True)
        self.commit_sha = run_git(self.root, "rev-parse", "HEAD")

        archive = self.root / "release" / "app.oci.tar"
        migration = self.root / "modules" / "ordenowaprocurement" / "upgrade" / "upgrade-1.0.1.php"
        evidence = self.root / "docs" / "evidence" / "smoke.txt"
        self.manifest = {
            "schema_version": 1,
            "source": {
                "repository": "example/japan-premium-commerce",
                "commit_sha": self.commit_sha,
                "gitlink_path": "themes/hummingbird",
                "gitlink_sha": self.theme_sha,
            },
            "application": {
                "archive_path": "release/app.oci.tar",
                "archive_sha256": sha256(archive.read_bytes()),
            },
            "database_image_ref": "mariadb:10.11@sha256:" + SHA_A,
            "build_input_refs": [
                "docker.io/library/composer:2@sha256:" + SHA_B,
                "docker.io/library/php:8.3@sha256:" + SHA_A,
            ],
            "migrations": [{
                "path": "modules/ordenowaprocurement/upgrade/upgrade-1.0.1.php",
                "sha256": sha256(migration.read_bytes()),
            }],
            "evidence": [{
                "path": "docs/evidence/smoke.txt",
                "sha256": sha256(evidence.read_bytes()),
            }],
        }
        self.write_manifest()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_manifest(self) -> None:
        self.manifest_path.write_text(json.dumps(self.manifest, sort_keys=True), encoding="utf-8")

    def commit_current_tree(self) -> None:
        run_git(self.root, "add", "-A")
        run_git(self.root, "commit", "--allow-empty", "-m", "fixture change", config=True)
        self.manifest["source"]["commit_sha"] = run_git(self.root, "rev-parse", "HEAD")
        self.write_manifest()

    def assert_rejected(self, expected: str) -> None:
        with self.assertRaises(release_manifest.ValidationError) as caught:
            release_manifest.validate(self.root, self.manifest_path)
        self.assertIn(expected, str(caught.exception))

    def test_valid_manifest_verifies_source_files_and_archive_bytes(self) -> None:
        result = release_manifest.validate(self.root, self.manifest_path)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["archive_sha256_verified"])
        self.assertEqual(result["migration_files_verified"], 1)
        self.assertEqual(result["evidence_files_verified"], 1)
        self.assertEqual(result["registry_digest"], "not_recorded")
        self.assertEqual(result["oci_archive_internals"], "not_inspected")
        self.assertEqual(result["completeness"], "not_checked")
        self.assertFalse(result["deployment_authorized"])

    def test_empty_input_and_evidence_lists_do_not_claim_completeness(self) -> None:
        self.manifest["build_input_refs"] = []
        self.manifest["migrations"] = []
        self.manifest["evidence"] = []
        self.write_manifest()
        result = release_manifest.validate(self.root, self.manifest_path)
        self.assertEqual(result["completeness"], "not_checked")
        self.assertFalse(result["deployment_authorized"])

    def test_image_reference_grammar_checks_tag_and_registry_port(self) -> None:
        valid_refs = [
            "mariadb:10.11@sha256:" + SHA_A,
            "ghcr.io:5000/team/app:release_1@sha256:" + SHA_B,
            "ghcr.io/team/app:Release_1@sha256:" + SHA_B,
            "localhost:5000/app@sha256:" + SHA_A,
        ]
        for ref in valid_refs:
            with self.subTest(ref=ref):
                release_manifest.valid_image_ref(ref, "image")
        invalid_refs = [
            "foo:bar:baz@sha256:" + SHA_A,
            "registry:abc/ns/app@sha256:" + SHA_A,
            "registry.example.com:70000/ns/app@sha256:" + SHA_A,
            "registry.example.com:5000/ns//app@sha256:" + SHA_A,
            "team/BadName@sha256:" + SHA_A,
        ]
        for ref in invalid_refs:
            with self.subTest(ref=ref), self.assertRaises(release_manifest.ValidationError):
                release_manifest.valid_image_ref(ref, "image")

    def test_git_identity_process_has_a_bounded_timeout(self) -> None:
        timeout = subprocess.TimeoutExpired(cmd="git", timeout=15)
        with patch("release_manifest.subprocess.run", side_effect=timeout):
            with self.assertRaisesRegex(release_manifest.ValidationError, "timed out"):
                release_manifest.git(self.root, "rev-parse", "HEAD")

    def test_optional_registry_digest_is_explicitly_declaration_only(self) -> None:
        registry_digest = "sha256:" + SHA_B
        self.manifest["application"]["registry_image_ref"] = "ghcr.io/example/app@" + registry_digest
        self.manifest["application"]["registry_manifest_digest"] = registry_digest
        self.write_manifest()
        result = release_manifest.validate(self.root, self.manifest_path)
        self.assertEqual(result["registry_digest"], "declared_only")

    def test_mutable_database_image_reference_is_rejected(self) -> None:
        self.manifest["database_image_ref"] = "mariadb:10.11"
        self.write_manifest()
        self.assert_rejected("pinned by a sha256 digest")

    def test_mutable_build_input_reference_is_rejected(self) -> None:
        self.manifest["build_input_refs"][0] = "composer:latest"
        self.write_manifest()
        self.assert_rejected("pinned by a sha256 digest")

    def test_bad_digest_syntax_is_rejected(self) -> None:
        self.manifest["database_image_ref"] = "mariadb@sha256:" + ("A" * 64)
        self.write_manifest()
        self.assert_rejected("exact lowercase sha256 digest")

    def test_source_commit_must_match_exact_manifest_sha(self) -> None:
        self.manifest["source"]["commit_sha"] = "0" * 40
        self.write_manifest()
        self.assert_rejected("source commit does not match")

    def test_parent_gitlink_must_match_declared_theme_sha(self) -> None:
        self.manifest["source"]["gitlink_sha"] = "0" * 40
        self.write_manifest()
        self.assert_rejected("theme gitlink does not match")

    def test_wrong_gitlink_path_is_rejected(self) -> None:
        self.manifest["source"]["gitlink_path"] = "themes/other"
        self.write_manifest()
        self.assert_rejected("must name the required theme gitlink")

    def test_dirty_source_checkout_is_rejected(self) -> None:
        (self.root / "modules" / "ordenowaprocurement" / "upgrade" / "upgrade-1.0.1.php").write_text(
            "<?php return false;\n", encoding="utf-8"
        )
        self.assert_rejected("source worktree must be clean")

    def test_missing_archive_is_rejected_after_source_commit_is_updated(self) -> None:
        (self.root / "release" / "app.oci.tar").unlink()
        self.commit_current_tree()
        self.assert_rejected("application.archive_path is missing or escapes")

    def test_archive_content_hash_mismatch_is_rejected(self) -> None:
        (self.root / "release" / "app.oci.tar").write_bytes(b"changed archive bytes\n")
        self.commit_current_tree()
        self.assert_rejected("application archive file hash does not match")

    def test_migration_hash_mismatch_is_rejected(self) -> None:
        path = self.root / self.manifest["migrations"][0]["path"]
        path.write_text("<?php return false;\n", encoding="utf-8")
        self.commit_current_tree()
        self.assert_rejected("migrations[0] file hash does not match")

    def test_evidence_file_missing_is_rejected(self) -> None:
        path = self.root / self.manifest["evidence"][0]["path"]
        path.unlink()
        self.commit_current_tree()
        self.assert_rejected("evidence[0].path is missing or escapes")

    def test_parent_gitlink_entry_must_be_a_gitlink(self) -> None:
        # A normal tracked directory at the required path is not a submodule gitlink.
        run_git(self.root, "submodule", "deinit", "-f", "themes/hummingbird")
        run_git(self.root, "rm", "-f", "themes/hummingbird")
        (self.root / "themes" / "hummingbird").mkdir(parents=True)
        (self.root / "themes" / "hummingbird" / "README.md").write_text("not a gitlink\n", encoding="utf-8")
        self.commit_current_tree()
        self.assert_rejected("required theme path is not a parent-repository gitlink")

    def test_registry_reference_must_be_pinned_and_agree_with_declared_digest(self) -> None:
        self.manifest["application"]["registry_image_ref"] = "ghcr.io/example/app:latest"
        self.manifest["application"]["registry_manifest_digest"] = "sha256:" + SHA_B
        self.write_manifest()
        self.assert_rejected("pinned by a sha256 digest")
        self.manifest["application"]["registry_image_ref"] = "ghcr.io/example/app@sha256:" + SHA_A
        self.write_manifest()
        self.assert_rejected("registry image reference and registry manifest digest differ")

    def test_path_traversal_and_unknown_secret_fields_are_rejected(self) -> None:
        self.manifest["evidence"][0]["path"] = "../outside.txt"
        self.write_manifest()
        self.assert_rejected("safe repository-relative path")
        self.manifest["evidence"][0]["path"] = "docs/evidence/smoke.txt"
        self.manifest["environment"] = {"TOKEN": "never accepted"}
        self.write_manifest()
        self.assert_rejected("contains unsupported fields")

    def test_duplicate_json_keys_are_rejected(self) -> None:
        self.manifest_path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
        self.assert_rejected("duplicate JSON keys")

    def test_file_paths_cannot_be_listed_twice(self) -> None:
        self.manifest["evidence"].append(dict(self.manifest["migrations"][0]))
        self.write_manifest()
        self.assert_rejected("more than once")


if __name__ == "__main__":
    unittest.main()
