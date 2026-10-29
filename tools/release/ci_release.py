#!/usr/bin/env python3
"""Bind one locally loaded release archive to the isolated procurement CI run.

This helper never publishes or deploys an image. It selects a run-owned tag for
the image ID produced by package_release.py, verifies Compose uses that tag,
records the running container's immutable image ID, and emits a JSON binding
only after the existing acceptance and cleanup gates pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Sequence

import release_manifest

GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
RUN_ID = re.compile(r"[0-9]+\Z")
RUN_IMAGE_REF = re.compile(r"local-only/ordenowa-procurement-ci:run-[0-9]+-[0-9]+\Z")
RUN_TAG_PREFIX = "local-only/ordenowa-procurement-ci:run-"
TIMEOUT_SECONDS = 60

REQUIRED_PHASES = (
    "image_build", "fresh_install", "native_source", "module_seed", "native_gallery",
    "requests_database", "requests_behavior", "requests_concurrency", "points_behavior",
    "points_concurrency", "notifications_behavior", "notifications_native",
    "notifications_concurrency", "notifications_health", "native_boundary",
    "native_push_settings", "policies_behavior", "policies_concurrency", "policies_smarty",
    "support_database", "support_concurrency_review", "support_controller", "support_smarty",
    "customer_ui", "customer_smarty", "navigation_smarty", "signin_smarty", "pwa_worker",
    "pwa_registration", "native_browser", "native_notifications", "native_push_provider",
    "native_accounts", "native_acl", "native_quality", "durable_readback", "restart_readback",
    "restart_source", "restore",
)


class CiReleaseError(Exception):
    """Safe, bounded error suitable for a public CI log."""


Runner = Callable[[Sequence[str], int], subprocess.CompletedProcess[str]]


def _run(argv: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", timeout=timeout, check=False,
    )


def run_checked(runner: Runner, argv: Sequence[str], description: str) -> str:
    try:
        result = runner(argv, TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        raise CiReleaseError(description) from None
    if result.returncode != 0:
        raise CiReleaseError(description)
    return result.stdout.strip()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CiReleaseError("duplicate_json_key")
        result[key] = value
    return result


def read_json(path: Path, failure: str) -> dict[str, Any]:
    if path.is_symlink():
        raise CiReleaseError(failure)
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(stream, object_pairs_hook=_unique_object)
    except CiReleaseError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise CiReleaseError(failure) from None
    if not isinstance(value, dict):
        raise CiReleaseError(failure)
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        raise CiReleaseError("archive_unreadable") from None
    return digest.hexdigest()


def file_hash(path: Path) -> str:
    return sha256_file(path)


def _regular_under(root: Path, path: Path) -> Path:
    if path.is_symlink():
        raise CiReleaseError("release_file_symlink")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        raise CiReleaseError("release_file_missing_or_outside_checkout") from None
    if not resolved.is_file():
        raise CiReleaseError("release_file_missing_or_outside_checkout")
    return resolved


def _expect_bool(mapping: Any, key: str, expected: bool, failure: str) -> None:
    if not isinstance(mapping, dict) or mapping.get(key) is not expected:
        raise CiReleaseError(failure)


def verify_package_records(
    root_arg: Path,
    proof_path_arg: Path,
    manifest_path_arg: Path,
    archive_path_arg: Path,
    expected_source_sha: str,
    *,
    manifest_validator: Callable[[Path, Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not GIT_SHA.fullmatch(expected_source_sha):
        raise CiReleaseError("source_sha_invalid")
    try:
        root = root_arg.resolve(strict=True)
        artifacts = (root / "release-artifacts").resolve(strict=True)
    except OSError:
        raise CiReleaseError("checkout_or_release_artifacts_missing") from None
    if not root.is_dir() or not artifacts.is_dir() or artifacts != root / "release-artifacts":
        raise CiReleaseError("release_artifacts_path_invalid")

    prefix = "ordenowa-prestashop-sha-" + expected_source_sha
    expected_proof = artifacts / (prefix + ".package.json")
    expected_manifest = artifacts / (prefix + ".release.json")
    expected_archive = artifacts / (prefix + ".docker.tar")
    proof_path = _regular_under(root, proof_path_arg)
    manifest_path = _regular_under(root, manifest_path_arg)
    archive_path = _regular_under(root, archive_path_arg)
    if (proof_path, manifest_path, archive_path) != (expected_proof, expected_manifest, expected_archive):
        raise CiReleaseError("release_file_names_do_not_match_source_sha")

    proof = read_json(proof_path, "package_proof_invalid")
    manifest = read_json(manifest_path, "release_manifest_invalid")
    source = proof.get("source")
    release_source = manifest.get("source")
    if not isinstance(source, dict) or not isinstance(release_source, dict):
        raise CiReleaseError("release_source_missing")
    if source.get("commit_sha") != expected_source_sha or release_source.get("commit_sha") != expected_source_sha:
        raise CiReleaseError("release_source_sha_mismatch")
    if proof.get("schema_version") != 1 or source.get("gitlink_path") != "themes/hummingbird":
        raise CiReleaseError("package_proof_schema_invalid")
    gitlink_sha = source.get("gitlink_sha")
    if not isinstance(gitlink_sha, str) or not GIT_SHA.fullmatch(gitlink_sha):
        raise CiReleaseError("release_gitlink_invalid")
    if release_source.get("gitlink_sha") != gitlink_sha or release_source.get("gitlink_path") != "themes/hummingbird":
        raise CiReleaseError("release_gitlink_mismatch")
    if proof.get("release_manifest_file") != manifest_path.name:
        raise CiReleaseError("package_manifest_name_mismatch")

    package_app = proof.get("application")
    release_app = manifest.get("application")
    if not isinstance(package_app, dict) or not isinstance(release_app, dict):
        raise CiReleaseError("release_application_missing")
    archive_name = archive_path.name
    archive_relative = "release-artifacts/" + archive_name
    if package_app.get("archive_file") != archive_name or package_app.get("archive_path") != archive_relative:
        raise CiReleaseError("package_archive_name_mismatch")
    if release_app.get("archive_path") != archive_relative:
        raise CiReleaseError("manifest_archive_path_mismatch")
    archive_sha = package_app.get("archive_sha256")
    if not isinstance(archive_sha, str) or not HEX64.fullmatch(archive_sha):
        raise CiReleaseError("archive_hash_invalid")
    if release_app.get("archive_sha256") != archive_sha or sha256_file(archive_path) != archive_sha:
        raise CiReleaseError("archive_hash_mismatch")

    image_id = package_app.get("docker_image_config_digest")
    if not isinstance(image_id, str) or not SHA256.fullmatch(image_id):
        raise CiReleaseError("image_config_digest_invalid")
    verification = proof.get("verification")
    for key in (
        "archive_untagged_image_id_checked", "archive_config_digest_checked",
        "removed_built_tag_before_load", "loaded_without_rebuild", "loaded_config_digest_matches",
        "loaded_image_id_inspected",
    ):
        _expect_bool(verification, key, True, "package_roundtrip_incomplete")
    if not isinstance(verification, dict) or type(verification.get("archive_layer_references_present")) is not int or verification["archive_layer_references_present"] < 1:
        raise CiReleaseError("package_archive_layers_missing")
    if verification.get("load_verification_scope") != "same_local_daemon_after_tag_removal":
        raise CiReleaseError("package_load_scope_unexpected")
    if proof.get("runtime_acceptance") != "not_checked" or proof.get("deployment_authorized") is not False:
        raise CiReleaseError("package_claim_scope_unexpected")
    registry = proof.get("registry_manifest_digest")
    if not isinstance(registry, dict) or registry.get("status") != "not_published_or_checked" or registry.get("value") is not None:
        raise CiReleaseError("package_registry_claim_unexpected")

    database_ref = manifest.get("database_image_ref")
    build_refs = manifest.get("build_input_refs")
    package_build = proof.get("build_inputs")
    if not isinstance(database_ref, str) or "@sha256:" not in database_ref:
        raise CiReleaseError("database_image_not_digest_pinned")
    if not isinstance(build_refs, list) or not build_refs or any(not isinstance(ref, str) or "@sha256:" not in ref for ref in build_refs):
        raise CiReleaseError("build_inputs_not_digest_pinned")
    if not isinstance(package_build, dict) or package_build.get("base_image_refs") != build_refs:
        raise CiReleaseError("build_input_record_mismatch")
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("migrations"), list) or not isinstance(manifest.get("evidence"), list):
        raise CiReleaseError("release_manifest_schema_invalid")

    validate_manifest = manifest_validator or release_manifest.validate
    try:
        validation = validate_manifest(root, manifest_path)
    except Exception:
        raise CiReleaseError("release_manifest_validation_failed") from None
    if not isinstance(validation, dict) or validation.get("status") != "ok" or validation.get("deployment_authorized") is not False:
        raise CiReleaseError("release_manifest_validation_failed")

    return {
        "source_sha": expected_source_sha,
        "gitlink_sha": gitlink_sha,
        "archive_path": archive_path,
        "archive_sha256": archive_sha,
        "image_id": image_id,
        "package_proof_path": proof_path,
        "release_manifest_path": manifest_path,
        "package_proof": proof,
        "release_manifest": manifest,
    }


def inspect_image(docker: str, image: str, runner: Runner, description: str) -> dict[str, Any]:
    raw = run_checked(
        runner,
        [docker, "--context", "default", "image", "inspect", "--format", "{{json .}}", image],
        description,
    )
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        raise CiReleaseError(description) from None
    if not isinstance(value, dict):
        raise CiReleaseError(description)
    return value


def _check_image(value: dict[str, Any], expected: dict[str, Any], ref: str | None) -> None:
    if value.get("Id") != expected["image_id"]:
        raise CiReleaseError("image_id_mismatch")
    config = value.get("Config")
    labels = config.get("Labels") if isinstance(config, dict) else None
    if not isinstance(labels, dict):
        raise CiReleaseError("image_release_labels_missing")
    if labels.get("org.opencontainers.image.revision") != expected["source_sha"]:
        raise CiReleaseError("image_source_label_mismatch")
    if labels.get("com.ordenowa.theme.gitlink") != expected["gitlink_sha"]:
        raise CiReleaseError("image_gitlink_label_mismatch")
    tags = value.get("RepoTags")
    if ref is None:
        if tags not in (None, []):
            raise CiReleaseError("loaded_release_image_unexpectedly_tagged")
    elif tags != [ref]:
        raise CiReleaseError("run_image_tag_mismatch")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    if path.is_symlink():
        raise CiReleaseError("output_file_is_symlink")
    temp_name: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(prefix=".ci-release-", suffix=".tmp", dir=path.parent)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except OSError:
        raise CiReleaseError("output_write_failed") from None
    finally:
        if temp_name is not None:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass


def _github_env(path: Path, values: dict[str, str]) -> None:
    if path.is_symlink() or any("\n" in value or "\r" in value for value in values.values()):
        raise CiReleaseError("github_environment_file_invalid")
    try:
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            for key, value in values.items():
                stream.write(key + "=" + value + "\n")
    except OSError:
        raise CiReleaseError("github_environment_write_failed") from None


def prepare_ci_image(
    root: Path,
    proof_path: Path,
    manifest_path: Path,
    archive_path: Path,
    expected_source_sha: str,
    run_id: str,
    run_attempt: str,
    artifact_dir: Path,
    github_env: Path,
    docker: str = "docker",
    runner: Runner = _run,
    manifest_validator: Callable[[Path, Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not RUN_ID.fullmatch(run_id) or not RUN_ID.fullmatch(run_attempt):
        raise CiReleaseError("run_identity_invalid")
    details = verify_package_records(
        root, proof_path, manifest_path, archive_path, expected_source_sha,
        manifest_validator=manifest_validator,
    )
    if artifact_dir.is_symlink():
        raise CiReleaseError("qa_artifact_directory_invalid")
    try:
        artifact_dir = artifact_dir.resolve(strict=True)
    except OSError:
        raise CiReleaseError("qa_artifact_directory_missing") from None
    if not artifact_dir.is_dir() or artifact_dir.is_symlink():
        raise CiReleaseError("qa_artifact_directory_invalid")

    image_ref = RUN_TAG_PREFIX + run_id + "-" + run_attempt
    existing = run_checked(
        runner,
        [docker, "--context", "default", "image", "ls", "--quiet", "--filter", "reference=" + image_ref],
        "run_image_tag_check_failed",
    )
    if existing:
        raise CiReleaseError("run_image_tag_already_exists")
    loaded = inspect_image(docker, details["image_id"], runner, "loaded_package_image_inspection_failed")
    _check_image(loaded, details, None)

    selection_path = artifact_dir / "ci-package-selection.json"
    selection = {
        "schema_version": 1,
        "passed": False,
        "source_sha": details["source_sha"],
        "gitlink_sha": details["gitlink_sha"],
        "archive_sha256": details["archive_sha256"],
        "docker_image_config_digest": details["image_id"],
        "image_ref": image_ref,
        "package_proof_file": details["package_proof_path"].name,
        "release_manifest_file": details["release_manifest_path"].name,
        "load_verification_scope": "same_local_daemon_after_tag_removal",
    }
    _write_json(selection_path, selection)
    _github_env(github_env, {
        "ORDENOWA_CI_SOURCE_SHA": details["source_sha"],
        "ORDENOWA_CI_ARCHIVE_SHA256": details["archive_sha256"],
        "ORDENOWA_CI_IMAGE_ID": details["image_id"],
        "ORDENOWA_CI_IMAGE_REF": image_ref,
        "ORDENOWA_CI_PACKAGE_PROOF": str(details["package_proof_path"]),
        "ORDENOWA_CI_RELEASE_MANIFEST": str(details["release_manifest_path"]),
        "ORDENOWA_CI_ARCHIVE_PATH": str(details["archive_path"]),
        "ORDENOWA_CI_PACKAGE_SELECTION": str(selection_path),
    })
    try:
        run_checked(runner, [docker, "--context", "default", "image", "tag", details["image_id"], image_ref], "run_image_tag_creation_failed")
        tagged = inspect_image(docker, image_ref, runner, "tagged_package_image_inspection_failed")
        _check_image(tagged, details, image_ref)
    except CiReleaseError:
        # Only remove the tag if it still points at the image this package owns.
        try:
            current = inspect_image(docker, image_ref, runner, "run_image_tag_cleanup_inspection_failed")
            if current.get("Id") == details["image_id"] and current.get("RepoTags") == [image_ref]:
                runner([docker, "--context", "default", "image", "rm", image_ref], TIMEOUT_SECONDS)
        except (CiReleaseError, OSError, subprocess.TimeoutExpired):
            pass
        raise

    selection["passed"] = True
    _write_json(selection_path, selection)
    return selection


def verify_prepared_image(
    root: Path,
    proof_path: Path,
    manifest_path: Path,
    archive_path: Path,
    source_sha: str,
    image_ref: str,
    image_id: str,
    selection_path: Path,
    compose_config_path: Path,
    docker: str = "docker",
    runner: Runner = _run,
    manifest_validator: Callable[[Path, Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    details = verify_package_records(root, proof_path, manifest_path, archive_path, source_sha, manifest_validator=manifest_validator)
    if image_id != details["image_id"] or not RUN_IMAGE_REF.fullmatch(image_ref):
        raise CiReleaseError("prepared_image_identity_mismatch")
    selection = read_json(selection_path, "package_selection_missing")
    for key, expected in (
        ("passed", True), ("source_sha", source_sha), ("archive_sha256", details["archive_sha256"]),
        ("docker_image_config_digest", details["image_id"]), ("image_ref", image_ref),
        ("schema_version", 1), ("load_verification_scope", "same_local_daemon_after_tag_removal"),
        ("gitlink_sha", details["gitlink_sha"]),
    ):
        if selection.get(key) != expected:
            raise CiReleaseError("package_selection_mismatch")
    compose_config = read_json(compose_config_path, "compose_config_invalid")
    services = compose_config.get("services")
    app = services.get("prestashop") if isinstance(services, dict) else None
    if not isinstance(app, dict) or app.get("image") != image_ref:
        raise CiReleaseError("compose_does_not_select_package_image")
    tagged = inspect_image(docker, image_ref, runner, "selected_package_image_inspection_failed")
    _check_image(tagged, details, image_ref)
    return selection


def record_runtime_binding(
    selection_path: Path,
    output_path: Path,
    observed_image_id: str,
    observed_image_ref: str,
    application_hot_copy: bool,
) -> dict[str, Any]:
    selection = read_json(selection_path, "package_selection_missing")
    if selection.get("passed") is not True:
        raise CiReleaseError("package_selection_not_passed")
    if application_hot_copy is not False:
        raise CiReleaseError("application_hot_copy_not_allowed_for_package")
    if observed_image_id != selection.get("docker_image_config_digest") or observed_image_ref != selection.get("image_ref"):
        raise CiReleaseError("runtime_container_image_mismatch")
    binding = {
        "schema_version": 1,
        "passed": True,
        "source_sha": selection["source_sha"],
        "gitlink_sha": selection["gitlink_sha"],
        "archive_sha256": selection["archive_sha256"],
        "docker_image_config_digest": selection["docker_image_config_digest"],
        "runtime_container_image_id": observed_image_id,
        "runtime_container_image_ref": observed_image_ref,
        "application_hot_copy": False,
    }
    _write_json(output_path, binding)
    return binding


def _passed_restore(path: Path) -> dict[str, Any]:
    value = read_json(path, "encrypted_restore_outcome_missing")
    expected = {
        "passed": True,
        "decrypt_roundtrip_verified": True,
        "ciphertext_tamper_rejected": True,
        "wrong_identity_rejected": True,
        "database_restore_verified": True,
    }
    if any(value.get(key) is not expected_value for key, expected_value in expected.items()):
        raise CiReleaseError("encrypted_restore_not_passed")
    return value


def bind_qa(
    *,
    root: Path,
    proof_path: Path,
    manifest_path: Path,
    archive_path: Path,
    expected_source_sha: str,
    selection_path: Path,
    runtime_binding_path: Path,
    qa_outcome_path: Path,
    restore_outcome_path: Path,
    output_path: Path,
    package_status: str,
    acceptance_status: str,
    cleanup_status: str,
    manifest_validator: Callable[[Path, Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if package_status != "success" or acceptance_status != "success" or cleanup_status != "success":
        raise CiReleaseError("workflow_gate_not_passed")
    details = verify_package_records(root, proof_path, manifest_path, archive_path, expected_source_sha, manifest_validator=manifest_validator)
    selection = read_json(selection_path, "package_selection_missing")
    runtime = read_json(runtime_binding_path, "runtime_binding_missing")
    qa = read_json(qa_outcome_path, "qa_outcome_missing")
    restore = _passed_restore(restore_outcome_path)

    expected_identity = {
        "passed": True,
        "source_sha": details["source_sha"],
        "gitlink_sha": details["gitlink_sha"],
        "archive_sha256": details["archive_sha256"],
        "docker_image_config_digest": details["image_id"],
    }
    if any(selection.get(key) != expected for key, expected in expected_identity.items()):
        raise CiReleaseError("package_selection_binding_mismatch")
    if any(runtime.get(key) != expected for key, expected in expected_identity.items()):
        raise CiReleaseError("runtime_binding_identity_mismatch")
    if runtime.get("application_hot_copy") is not False:
        raise CiReleaseError("runtime_application_hot_copy_not_false")
    if runtime.get("runtime_container_image_id") != details["image_id"] or runtime.get("runtime_container_image_ref") != selection.get("image_ref"):
        raise CiReleaseError("runtime_image_not_the_packaged_image")
    if qa.get("passed") is not True or qa.get("cleanup") != "success":
        raise CiReleaseError("qa_aggregate_not_passed")
    phases = qa.get("phases")
    if not isinstance(phases, dict) or set(phases) != set(REQUIRED_PHASES) or len(phases) != len(REQUIRED_PHASES):
        raise CiReleaseError("qa_phase_set_mismatch")
    if any(phases.get(phase) != "passed" for phase in REQUIRED_PHASES):
        raise CiReleaseError("qa_phase_not_passed")

    ancillary: dict[str, str] = {}
    for label, path in (
        ("qa_outcome_sha256", qa_outcome_path),
        ("encrypted_restore_outcome_sha256", restore_outcome_path),
        ("package_selection_sha256", selection_path),
        ("runtime_binding_sha256", runtime_binding_path),
        ("package_proof_sha256", proof_path),
        ("release_manifest_sha256", manifest_path),
    ):
        ancillary[label] = file_hash(path)

    result = {
        "schema_version": 1,
        "passed": True,
        "source": {"commit_sha": details["source_sha"], "gitlink_sha": details["gitlink_sha"]},
        "application": {
            "archive_sha256": details["archive_sha256"],
            "docker_image_config_digest": details["image_id"],
            "runtime_image_ref": selection["image_ref"],
            "application_hot_copy": False,
        },
        "qa": {
            "acceptance_status": acceptance_status,
            "cleanup_status": cleanup_status,
            "phase_count": len(REQUIRED_PHASES),
            "all_required_phases_passed": True,
            "encrypted_restore_passed": True,
            "runtime_container_image_matches_package": True,
            **ancillary,
        },
        "registry_manifest_digest": "not_published_or_checked",
        "release_completeness": "not_checked",
        "runtime_acceptance_scope": "isolated_fresh_install_restart_and_encrypted_database_restore",
        "deployment_authorized": False,
    }
    _write_json(output_path, result)
    return result


def _add_common_package_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--package-proof", required=True, type=Path)
    parser.add_argument("--release-manifest", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--source-sha", required=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare and bind an offline package to isolated CI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="validate a loaded package and tag its image ID for this run")
    _add_common_package_args(prepare)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--run-attempt", required=True)
    prepare.add_argument("--artifact-dir", required=True, type=Path)
    prepare.add_argument("--github-env", required=True, type=Path)
    prepare.add_argument("--docker", default="docker")

    verify = subparsers.add_parser("verify", help="revalidate package records and the Compose-selected image")
    _add_common_package_args(verify)
    verify.add_argument("--image-ref", required=True)
    verify.add_argument("--image-id", required=True)
    verify.add_argument("--selection", required=True, type=Path)
    verify.add_argument("--compose-config", required=True, type=Path)
    verify.add_argument("--docker", default="docker")

    attest = subparsers.add_parser("attest-runtime", help="record that the fresh-install container uses the packaged image ID")
    attest.add_argument("--selection", required=True, type=Path)
    attest.add_argument("--output", required=True, type=Path)
    attest.add_argument("--image-id", required=True)
    attest.add_argument("--image-ref", required=True)
    attest.add_argument("--application-hot-copy", required=True, choices=("false",))

    bind = subparsers.add_parser("bind", help="bind final package, runtime, QA, restore, and cleanup records")
    _add_common_package_args(bind)
    bind.add_argument("--selection", required=True, type=Path)
    bind.add_argument("--runtime-binding", required=True, type=Path)
    bind.add_argument("--qa-outcome", required=True, type=Path)
    bind.add_argument("--restore-outcome", required=True, type=Path)
    bind.add_argument("--output", required=True, type=Path)
    bind.add_argument("--package-status", required=True)
    bind.add_argument("--acceptance-status", required=True)
    bind.add_argument("--cleanup-status", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare_ci_image(
                args.root, args.package_proof, args.release_manifest, args.archive,
                args.source_sha, args.run_id, args.run_attempt, args.artifact_dir,
                args.github_env, args.docker,
            )
        elif args.command == "verify":
            result = verify_prepared_image(
                args.root, args.package_proof, args.release_manifest, args.archive,
                args.source_sha, args.image_ref, args.image_id, args.selection,
                args.compose_config, args.docker,
            )
        elif args.command == "attest-runtime":
            result = record_runtime_binding(
                args.selection, args.output, args.image_id, args.image_ref,
                application_hot_copy=(args.application_hot_copy == "true"),
            )
        else:
            result = bind_qa(
                root=args.root, proof_path=args.package_proof, manifest_path=args.release_manifest,
                archive_path=args.archive, expected_source_sha=args.source_sha,
                selection_path=args.selection, runtime_binding_path=args.runtime_binding,
                qa_outcome_path=args.qa_outcome, restore_outcome_path=args.restore_outcome,
                output_path=args.output, package_status=args.package_status,
                acceptance_status=args.acceptance_status, cleanup_status=args.cleanup_status,
            )
    except CiReleaseError as exc:
        if args.command == "bind":
            try:
                _write_json(args.output, {
                    "schema_version": 1,
                    "passed": False,
                    "failure_code": str(exc),
                    "source_sha": args.source_sha if GIT_SHA.fullmatch(args.source_sha) else None,
                    "deployment_authorized": False,
                })
            except CiReleaseError:
                pass
        print("CI release binding failed: " + str(exc), file=sys.stderr)
        return 1
    if args.command == "prepare":
        print(json.dumps({
            "passed": result["passed"],
            "source_sha": result["source_sha"],
            "archive_sha256": result["archive_sha256"],
            "docker_image_config_digest": result["docker_image_config_digest"],
            "image_ref": result["image_ref"],
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
