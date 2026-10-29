#!/usr/bin/env python3
"""Offline validator for a portable, immutable release record.

This tool checks local file hashes and Git source identity. It does not build,
publish, pull, deploy, or inspect OCI archive internals. A registry manifest
digest is only a recorded immutable reference unless verified by a registry
client in a separate authorized promotion step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
SAFE_IMAGE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]*\Z")
GITLINK_PATH = "themes/hummingbird"
REPOSITORY_COMPONENT = re.compile(r"[a-z0-9]+(?:(?:[._]|__|[-]+)[a-z0-9]+)*\Z")
TAG = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}\Z")
REGISTRY_HOST = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\Z")


class ValidationError(Exception):
    """A safe, user-facing validation failure."""


def fail(message: str) -> None:
    raise ValidationError(message)


def object_with_keys(value: Any, required: set[str], optional: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(where + " must be an object")
    keys = set(value)
    missing = required - keys
    unknown = keys - required - optional
    if missing:
        fail(where + " is missing required fields")
    if unknown:
        fail(where + " contains unsupported fields")
    return value


def string_value(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        fail(where + " must be a non-empty string")
    return value


def valid_image_ref(value: Any, where: str) -> str:
    ref = string_value(value, where)
    if ref.count("@") != 1:
        fail(where + " must be pinned by a sha256 digest")
    name, digest = ref.rsplit("@", 1)
    if not SHA256_DIGEST.fullmatch(digest):
        fail(where + " must use an exact lowercase sha256 digest")
    if not SAFE_IMAGE_NAME.fullmatch(name):
        fail(where + " has an invalid image name")
    path_parts = name.split("/")
    if any(not part for part in path_parts):
        fail(where + " has an invalid image name")
    last = path_parts[-1]
    if ":" in last:
        repository_last, tag = last.rsplit(":", 1)
        if not TAG.fullmatch(tag):
            fail(where + " has an invalid image tag")
        path_parts[-1] = repository_last
    if len(path_parts) > 1:
        first = path_parts[0]
        if "." in first or ":" in first or first == "localhost":
            host, colon, port = first.partition(":")
            if not REGISTRY_HOST.fullmatch(host):
                fail(where + " has an invalid registry host")
            if colon and (not port.isdigit() or not 1 <= int(port) <= 65535):
                fail(where + " has an invalid registry port")
            path_parts = path_parts[1:]
    if not path_parts or any(not REPOSITORY_COMPONENT.fullmatch(part) for part in path_parts):
        fail(where + " has an invalid repository path")
    return digest


def json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail("manifest contains duplicate JSON keys")
        result[key] = value
    return result


def read_manifest(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(stream, object_pairs_hook=json_object_without_duplicates)
    except ValidationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError):
        fail("manifest could not be read as UTF-8 JSON")
    if not isinstance(value, dict):
        fail("manifest root must be an object")
    return value


def safe_repo_file(root: Path, raw_path: Any, where: str) -> tuple[str, Path]:
    rel = string_value(raw_path, where)
    if "\\" in rel or rel.startswith("/") or ":" in rel:
        fail(where + " must be a safe repository-relative path")
    parts = rel.split("/")
    if any(part in ("", ".", "..") for part in parts):
        fail(where + " must be a safe repository-relative path")
    candidate = root
    for part in parts:
        candidate = candidate / part
        try:
            if candidate.is_symlink():
                fail(where + " must not traverse a symbolic link")
        except OSError:
            fail(where + " could not be inspected")
    try:
        candidate.resolve(strict=True).relative_to(root)
    except (OSError, ValueError):
        fail(where + " is missing or escapes the repository")
    if not candidate.is_file():
        fail(where + " must refer to a regular file")
    return rel, candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        fail("a declared release file could not be read")
    return digest.hexdigest()


def verify_file_record(root: Path, record: Any, where: str, seen: set[str]) -> None:
    item = object_with_keys(record, {"path", "sha256"}, set(), where)
    rel, path = safe_repo_file(root, item["path"], where + ".path")
    if rel in seen:
        fail("manifest lists a release file more than once")
    seen.add(rel)
    expected = string_value(item["sha256"], where + ".sha256")
    if not HEX64.fullmatch(expected):
        fail(where + ".sha256 must be exactly 64 lowercase hexadecimal characters")
    if sha256_file(path) != expected:
        fail(where + " file hash does not match")


def git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except OSError:
        fail("Git is required for source identity checks")
    except subprocess.TimeoutExpired:
        fail("Git source identity checks timed out")
    if result.returncode != 0:
        fail("Git source identity checks failed")
    return result.stdout.strip()


def verify_git_source(root: Path, source: dict[str, Any]) -> None:
    expected_commit = string_value(source["commit_sha"], "source.commit_sha")
    expected_gitlink = string_value(source["gitlink_sha"], "source.gitlink_sha")
    if not HEX40.fullmatch(expected_commit):
        fail("source.commit_sha must be exactly 40 lowercase hexadecimal characters")
    if not HEX40.fullmatch(expected_gitlink):
        fail("source.gitlink_sha must be exactly 40 lowercase hexadecimal characters")

    actual_root = Path(git(root, "rev-parse", "--show-toplevel")).resolve()
    if actual_root != root:
        fail("--root must name the Git repository root")
    actual_commit = git(root, "rev-parse", "HEAD")
    if actual_commit != expected_commit:
        fail("source commit does not match the manifest")
    if git(root, "status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"):
        fail("source worktree must be clean")

    tree = git(root, "ls-tree", "HEAD", "--", GITLINK_PATH)
    metadata, separator, path = tree.partition("\t")
    fields = metadata.split()
    if not separator or path != GITLINK_PATH or len(fields) != 3:
        fail("required theme gitlink is missing from the release source")
    mode, object_type, gitlink_sha = fields
    if mode != "160000" or object_type != "commit":
        fail("required theme path is not a parent-repository gitlink")
    if gitlink_sha != expected_gitlink:
        fail("theme gitlink does not match the manifest")

    theme = root / GITLINK_PATH
    if not theme.is_dir() or theme.is_symlink():
        fail("theme gitlink checkout is missing")
    if git(theme, "rev-parse", "HEAD") != expected_gitlink:
        fail("theme checkout does not match the parent gitlink")
    if git(theme, "status", "--porcelain=v1", "--untracked-files=all"):
        fail("theme worktree must be clean")


def validate(root_arg: Path, manifest_path: Path) -> dict[str, Any]:
    try:
        root = root_arg.resolve(strict=True)
    except OSError:
        fail("repository root does not exist")
    if not root.is_dir():
        fail("repository root must be a directory")

    manifest = read_manifest(manifest_path)
    manifest = object_with_keys(
        manifest,
        {"schema_version", "source", "application", "database_image_ref", "build_input_refs", "migrations", "evidence"},
        set(),
        "manifest",
    )
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        fail("schema_version must be integer 1")

    source = object_with_keys(
        manifest["source"],
        {"repository", "commit_sha", "gitlink_path", "gitlink_sha"},
        set(),
        "source",
    )
    repository = string_value(source["repository"], "source.repository")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        fail("source.repository must use owner/repository form")
    if source["gitlink_path"] != GITLINK_PATH:
        fail("source.gitlink_path must name the required theme gitlink")
    verify_git_source(root, source)

    application = object_with_keys(
        manifest["application"],
        {"archive_path", "archive_sha256"},
        {"registry_image_ref", "registry_manifest_digest"},
        "application",
    )
    if ("registry_image_ref" in application) != ("registry_manifest_digest" in application):
        fail("registry image reference and registry digest must be supplied together")
    seen: set[str] = set()
    archive_rel, archive_path = safe_repo_file(root, application["archive_path"], "application.archive_path")
    seen.add(archive_rel)
    archive_hash = string_value(application["archive_sha256"], "application.archive_sha256")
    if not HEX64.fullmatch(archive_hash):
        fail("application.archive_sha256 must be exactly 64 lowercase hexadecimal characters")
    if sha256_file(archive_path) != archive_hash:
        fail("application archive file hash does not match")
    registry_recorded = False
    if "registry_image_ref" in application:
        image_digest = valid_image_ref(application["registry_image_ref"], "application.registry_image_ref")
        recorded_digest = string_value(application["registry_manifest_digest"], "application.registry_manifest_digest")
        if not SHA256_DIGEST.fullmatch(recorded_digest):
            fail("application.registry_manifest_digest must be an exact sha256 digest")
        if image_digest != recorded_digest:
            fail("registry image reference and registry manifest digest differ")
        registry_recorded = True

    valid_image_ref(manifest["database_image_ref"], "database_image_ref")
    build_inputs = manifest["build_input_refs"]
    if not isinstance(build_inputs, list):
        fail("build_input_refs must be an array")
    for index, ref in enumerate(build_inputs):
        valid_image_ref(ref, "build_input_refs[" + str(index) + "]")

    for field in ("migrations", "evidence"):
        records = manifest[field]
        if not isinstance(records, list):
            fail(field + " must be an array")
        for index, record in enumerate(records):
            verify_file_record(root, record, field + "[" + str(index) + "]", seen)

    return {
        "status": "ok",
        "source_commit": source["commit_sha"],
        "archive_sha256_verified": True,
        "migration_files_verified": len(manifest["migrations"]),
        "evidence_files_verified": len(manifest["evidence"]),
        "registry_digest": "declared_only" if registry_recorded else "not_recorded",
        "oci_archive_internals": "not_inspected",
        "completeness": "not_checked",
        "deployment_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a local immutable release manifest.")
    parser.add_argument("--root", required=True, type=Path, help="clean Git repository root")
    parser.add_argument("--manifest", required=True, type=Path, help="UTF-8 JSON release manifest")
    args = parser.parse_args(argv)
    try:
        result = validate(args.root, args.manifest)
    except ValidationError as exc:
        print("verification failed: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
