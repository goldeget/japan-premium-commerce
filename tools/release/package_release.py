#!/usr/bin/env python3
"""Build and round-trip a local Docker archive for an explicitly chosen commit.

This does not use Compose, push to a registry, deploy, or collect environment
values. It records only the local Docker archive hash, image config digest,
source Git commit, theme gitlink, and observed build references.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import urlsplit
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Sequence

GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
BASE_REF = re.compile(r"\S+@sha256:[0-9a-f]{64}\Z")
GITLINK_PATH = "themes/hummingbird"
IMAGE_PREFIX = "local-only/ordenowa-prestashop:sha-"
COMMAND_TIMEOUT_SECONDS = 3600
GIT_TIMEOUT_SECONDS = 15


class PackageError(Exception):
    """Safe operational failure without subprocess output or environment data."""


CommandRunner = Callable[[Sequence[str], int], subprocess.CompletedProcess[str]]
Progress = Callable[[str], None]


def _run_command(argv: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def run_checked(
    runner: CommandRunner,
    argv: Sequence[str],
    phase: str,
    timeout: int = COMMAND_TIMEOUT_SECONDS,
) -> str:
    try:
        result = runner(argv, timeout)
    except subprocess.TimeoutExpired:
        raise PackageError(phase + " timed out") from None
    except OSError:
        raise PackageError(phase + " could not start") from None
    if result.returncode != 0:
        raise PackageError(phase + " failed (exit " + str(result.returncode) + ")")
    return result.stdout.strip()


def git(root: Path, runner: CommandRunner, *args: str) -> str:
    return run_checked(runner, ["git", "-C", str(root), *args], "Git source check", GIT_TIMEOUT_SECONDS)


def source_identity(root: Path, runner: CommandRunner) -> dict[str, str]:
    try:
        resolved_root = root.resolve(strict=True)
    except OSError:
        raise PackageError("source checkout does not exist") from None
    if not resolved_root.is_dir():
        raise PackageError("source checkout must be a directory")
    git_root = Path(git(resolved_root, runner, "rev-parse", "--show-toplevel")).resolve()
    if git_root != resolved_root:
        raise PackageError("--root must be the Git checkout root")
    commit = git(resolved_root, runner, "rev-parse", "HEAD")
    if not GIT_SHA.fullmatch(commit):
        raise PackageError("source checkout must use a 40-character Git commit SHA")
    if git(resolved_root, runner, "status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"):
        raise PackageError("source checkout must be clean before packaging")

    tree_line = git(resolved_root, runner, "ls-tree", "HEAD", "--", GITLINK_PATH)
    metadata, separator, path = tree_line.partition("\t")
    fields = metadata.split()
    if not separator or path != GITLINK_PATH or len(fields) != 3:
        raise PackageError("required theme parent gitlink is missing")
    mode, object_type, theme_commit = fields
    if mode != "160000" or object_type != "commit" or not GIT_SHA.fullmatch(theme_commit):
        raise PackageError("required theme path is not a valid Git submodule gitlink")
    theme = resolved_root / GITLINK_PATH
    if theme.is_symlink() or not theme.is_dir():
        raise PackageError("theme submodule checkout is missing")
    if git(theme, runner, "rev-parse", "HEAD") != theme_commit:
        raise PackageError("theme checkout does not match parent gitlink")
    if git(theme, runner, "status", "--porcelain=v1", "--untracked-files=all"):
        raise PackageError("theme submodule checkout must be clean")
    return {"commit_sha": commit, "gitlink_path": GITLINK_PATH, "gitlink_sha": theme_commit}


def dockerfile_inputs(dockerfile: Path) -> dict[str, Any]:
    try:
        lines = dockerfile.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise PackageError("Dockerfile could not be read as UTF-8") from None

    bases: list[str] = []
    aliases: set[str] = set()
    syntax_frontend: str | None = None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        syntax = re.match(r"^#\s*syntax\s*=\s*(\S+)\s*$", line, re.IGNORECASE)
        if syntax:
            syntax_frontend = syntax.group(1)
            continue
        if line.startswith("#"):
            continue
        parts = line.split()
        if parts[0].upper() != "FROM":
            continue
        index = 1
        while index < len(parts) and parts[index].startswith("--"):
            if not parts[index].startswith("--platform="):
                raise PackageError("unsupported FROM option in Dockerfile")
            index += 1
        if index >= len(parts):
            raise PackageError("malformed FROM instruction in Dockerfile")
        image = parts[index]
        index += 1
        alias: str | None = None
        if index < len(parts):
            if index + 2 != len(parts) or parts[index].upper() != "AS":
                raise PackageError("malformed FROM alias in Dockerfile")
            alias = parts[index + 1]
        if image.lower() != "scratch" and image not in aliases:
            if not BASE_REF.fullmatch(image):
                raise PackageError("every external Dockerfile base must use a sha256 digest")
            bases.append(image)
        if alias:
            aliases.add(alias)

    if not bases:
        raise PackageError("Dockerfile has no external pinned base images")
    return {
        "base_image_refs": bases,
        "syntax_frontend_ref": syntax_frontend,
        "syntax_frontend_sha256_pinned": bool(syntax_frontend and BASE_REF.fullmatch(syntax_frontend)),
    }


def source_repository(root: Path, runner: CommandRunner) -> str:
    remote = git(root, runner, "remote", "get-url", "origin")
    if not remote or "\n" in remote:
        raise PackageError("origin remote does not identify one source repository")
    if "://" in remote:
        parsed = urlsplit(remote)
        repository_path = parsed.path.lstrip("/")
    else:
        match = re.fullmatch(r"(?:[^@/]+@)?[^:/]+:(.+)", remote)
        if not match:
            raise PackageError("origin remote does not identify an owner/repository path")
        repository_path = match.group(1)
    repository_path = repository_path.removesuffix(".git").strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository_path):
        raise PackageError("origin remote does not identify an owner/repository path")
    return repository_path


def database_image_ref(compose_file: Path) -> str:
    try:
        lines = compose_file.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise PackageError("compose.yaml could not be read as UTF-8") from None
    in_services = False
    in_database = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            in_services = stripped == "services:"
            in_database = False
            continue
        if not in_services:
            continue
        if indent == 2 and stripped.endswith(":"):
            in_database = stripped[:-1] == "mariadb"
            continue
        if in_database and indent == 4 and stripped.startswith("image:"):
            value = stripped[len("image:"):].strip().strip("\"'")
            if not BASE_REF.fullmatch(value):
                raise PackageError("MariaDB compose image must be pinned by sha256")
            return value
    raise PackageError("compose.yaml has no pinned mariadb service image")


def local_docker_context(docker: str, runner: CommandRunner) -> str:
    host = run_checked(
        runner,
        [docker, "--context", "default", "context", "inspect", "default", "--format", "{{.Endpoints.docker.Host}}"],
        "Docker context check",
        30,
    )
    is_local = host.startswith(("unix://", "npipe://"))
    if host.startswith("tcp://"):
        endpoint = host[len("tcp://"):].split("/", 1)[0]
        hostname = endpoint.rsplit(":", 1)[0].strip("[]").lower()
        is_local = hostname in ("localhost", "127.0.0.1", "::1")
    if not is_local:
        raise PackageError("default Docker context is not a local endpoint; remote daemons are refused")
    return host.split(":", 1)[0]


def inspect_image(docker: str, tag: str, runner: CommandRunner, phase: str) -> dict[str, Any]:
    raw = run_checked(
        runner,
        [docker, "--context", "default", "image", "inspect", "--format", "{{json .}}", tag],
        phase,
    )
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        raise PackageError(phase + " returned invalid JSON") from None
    if not isinstance(value, dict):
        raise PackageError(phase + " returned an invalid image record")
    image_id = value.get("Id")
    if not isinstance(image_id, str) or not SHA256.fullmatch(image_id):
        raise PackageError(phase + " returned an invalid Docker image config digest")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        raise PackageError("saved Docker archive could not be read") from None
    return digest.hexdigest()


def _archive_member_name(raw_name: str) -> str:
    if "\\" in raw_name or raw_name.startswith("/"):
        raise PackageError("Docker archive contains an unsafe member path")
    parts = [part for part in PurePosixPath(raw_name).parts if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise PackageError("Docker archive contains an unsafe member path")
    return "/".join(parts)


def verify_docker_archive(path: Path, expected_image_id: str) -> dict[str, Any]:
    try:
        with tarfile.open(path, mode="r:") as archive:
            members: dict[str, tarfile.TarInfo] = {}
            for member in archive.getmembers():
                name = _archive_member_name(member.name)
                if name in members:
                    raise PackageError("Docker archive contains duplicate members")
                if not (member.isfile() or member.isdir()):
                    raise PackageError("Docker archive contains a link or special file")
                members[name] = member
            manifest_member = members.get("manifest.json")
            if manifest_member is None or not manifest_member.isfile():
                raise PackageError("Docker archive has no manifest.json")
            manifest_file = archive.extractfile(manifest_member)
            if manifest_file is None:
                raise PackageError("Docker archive manifest could not be read")
            manifest_bytes = manifest_file.read(4 * 1024 * 1024 + 1)
            if len(manifest_bytes) > 4 * 1024 * 1024:
                raise PackageError("Docker archive manifest is too large")
            try:
                records = json.loads(manifest_bytes)
            except (UnicodeError, json.JSONDecodeError):
                raise PackageError("Docker archive manifest is invalid JSON") from None
            if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
                raise PackageError("Docker archive must contain exactly one image record")
            record = records[0]
            repo_tags = record.get("RepoTags")
            if repo_tags not in (None, []):
                raise PackageError("image-ID export unexpectedly contains mutable repository tags")
            config_name_raw = record.get("Config")
            if not isinstance(config_name_raw, str):
                raise PackageError("Docker archive manifest has no config filename")
            config_name = _archive_member_name(config_name_raw)
            config_member = members.get(config_name)
            if config_member is None or not config_member.isfile() or config_member.size > 64 * 1024 * 1024:
                raise PackageError("Docker archive image config is missing or too large")
            config_file = archive.extractfile(config_member)
            if config_file is None:
                raise PackageError("Docker archive image config could not be read")
            config_digest = "sha256:" + hashlib.sha256(config_file.read()).hexdigest()
            if config_digest != expected_image_id:
                raise PackageError("Docker archive image config digest differs from the built image")
            layer_names = record.get("Layers")
            if not isinstance(layer_names, list) or not layer_names:
                raise PackageError("Docker archive manifest has no image layers")
            for layer_raw in layer_names:
                if not isinstance(layer_raw, str):
                    raise PackageError("Docker archive manifest has an invalid layer path")
                layer_name = _archive_member_name(layer_raw)
                layer_member = members.get(layer_name)
                if layer_member is None or not layer_member.isfile():
                    raise PackageError("Docker archive is missing a referenced layer")
    except PackageError:
        raise
    except (OSError, tarfile.TarError):
        raise PackageError("saved file is not a readable Docker image archive") from None
    return {"docker_image_config_digest": config_digest, "layer_count": len(layer_names)}


def _validate_inspect(value: dict[str, Any], tag: str | None, source: dict[str, str]) -> None:
    repo_tags = value.get("RepoTags")
    config = value.get("Config")
    labels = config.get("Labels") if isinstance(config, dict) else None
    if tag is not None and (not isinstance(repo_tags, list) or repo_tags != [tag]):
        raise PackageError("Docker image must have only the source-SHA tag before archive round-trip")
    if tag is None and repo_tags not in (None, []):
        raise PackageError("loaded image ID is unexpectedly tagged")
    if not isinstance(labels, dict):
        raise PackageError("Docker image does not expose expected release labels")
    if labels.get("org.opencontainers.image.revision") != source["commit_sha"]:
        raise PackageError("Docker image source revision label does not match checkout")
    if labels.get("com.ordenowa.theme.gitlink") != source["gitlink_sha"]:
        raise PackageError("Docker image theme gitlink label does not match checkout")


def validate_release_output_dir(root: Path, output: Path, runner: CommandRunner) -> Path:
    expected = root / "release-artifacts"
    if output.is_symlink():
        raise PackageError("release-artifacts must not be a symbolic link")
    try:
        resolved_output = output.resolve()
    except OSError:
        raise PackageError("release-artifacts path could not be resolved") from None
    if resolved_output != expected.resolve():
        raise PackageError("output directory must be the checkout's release-artifacts directory")
    for filename in (".gitignore", ".dockerignore"):
        path = root / filename
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            raise PackageError(filename + " is required to exclude release artifacts") from None
        if "release-artifacts/" not in lines:
            raise PackageError(filename + " must exclude release-artifacts/")
    try:
        run_checked(
            runner,
            ["git", "-C", str(root), "check-ignore", "-q", "release-artifacts/"],
            "Git output-ignore check",
            GIT_TIMEOUT_SECONDS,
        )
    except PackageError:
        raise PackageError("release-artifacts must be ignored by Git before packaging") from None
    return resolved_output


def link_no_replace(source: Path, destination: Path) -> None:
    try:
        os.link(source, destination)
    except FileExistsError:
        raise PackageError("release artifact appeared during packaging; refusing to overwrite") from None
    except OSError:
        raise PackageError("filesystem does not support safe no-overwrite release artifact promotion") from None
    source.unlink()


def write_json_no_replace(path: Path, value: dict[str, Any]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".release-record-", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        link_no_replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def package_release(
    root_arg: Path,
    output_arg: Path,
    docker: str = "docker",
    runner: CommandRunner = _run_command,
    progress: Progress = print,
) -> dict[str, Any]:
    try:
        root = root_arg.resolve(strict=True)
    except OSError:
        raise PackageError("source checkout does not exist") from None
    source = source_identity(root, runner)
    repository = source_repository(root, runner)
    database_ref = database_image_ref(root / "compose.yaml")
    dockerfile = root / "docker" / "Dockerfile"
    if not dockerfile.is_file() or dockerfile.is_symlink():
        raise PackageError("expected docker/Dockerfile is missing or unsafe")
    inputs = dockerfile_inputs(dockerfile)
    validate_release_output_dir(root, output_arg, runner)
    output = (root / "release-artifacts").resolve()
    tag = IMAGE_PREFIX + source["commit_sha"]
    archive_path = output / ("ordenowa-prestashop-sha-" + source["commit_sha"] + ".docker.tar")
    release_manifest_path = output / ("ordenowa-prestashop-sha-" + source["commit_sha"] + ".release.json")
    package_proof_path = output / ("ordenowa-prestashop-sha-" + source["commit_sha"] + ".package.json")
    if any(path.exists() or path.is_symlink() for path in (archive_path, release_manifest_path, package_proof_path)):
        raise PackageError("release output for this source SHA already exists; refusing to overwrite")

    progress("[1/7] Confirm local Docker context")
    docker_context = local_docker_context(docker, runner)
    progress("[2/7] Check that the source-SHA image tag is unused")
    existing = run_checked(
        runner,
        [docker, "--context", "default", "image", "ls", "--quiet", "--filter", "reference=" + tag],
        "Docker image tag check",
    )
    if existing:
        raise PackageError("source-SHA image tag already exists locally; refusing to replace it")

    output.mkdir(parents=True, exist_ok=True)
    progress("[3/7] Build the application image from the clean checkout")
    build_args = [
        docker, "--context", "default", "build",
        "--file", str(dockerfile),
        "--tag", tag,
        "--label", "org.opencontainers.image.revision=" + source["commit_sha"],
        "--label", "com.ordenowa.theme.gitlink=" + source["gitlink_sha"],
        str(root),
    ]
    run_checked(runner, build_args, "Docker build")

    progress("[4/7] Inspect and verify source labels")
    before = inspect_image(docker, tag, runner, "Built image inspection")
    _validate_inspect(before, tag, source)
    image_id = before["Id"]

    descriptor, temporary_name = tempfile.mkstemp(prefix=".ordenowa-release-", suffix=".docker.tar", dir=output)
    os.close(descriptor)
    temporary_archive = Path(temporary_name)
    temporary_archive.unlink()
    try:
        progress("[5/7] Export and verify the Docker archive bytes")
        run_checked(
            runner,
            [docker, "--context", "default", "image", "save", "--output", str(temporary_archive), image_id],
            "Docker image export",
        )
        if not temporary_archive.is_file() or temporary_archive.is_symlink() or temporary_archive.stat().st_size == 0:
            raise PackageError("Docker image export did not produce a regular non-empty archive")
        archive_sha256 = file_sha256(temporary_archive)
        archive_facts = verify_docker_archive(temporary_archive, image_id)
        link_no_replace(temporary_archive, archive_path)

        progress("[6/7] Remove only the just-built tag, then load the archive without rebuilding")
        latest = inspect_image(docker, tag, runner, "Pre-load image inspection")
        _validate_inspect(latest, tag, source)
        if latest["Id"] != image_id:
            raise PackageError("source-SHA image tag changed during export; archive was preserved")
        run_checked(runner, [docker, "--context", "default", "image", "rm", tag], "Built image tag removal")
        run_checked(
            runner,
            [docker, "--context", "default", "image", "load", "--input", str(archive_path)],
            "Docker archive load",
        )
        loaded_by_id = inspect_image(docker, image_id, runner, "Loaded image ID inspection")
        _validate_inspect(loaded_by_id, None, source)
        if loaded_by_id["Id"] != image_id:
            raise PackageError("loaded Docker image ID inspection returned a different config digest")
        if file_sha256(archive_path) != archive_sha256:
            raise PackageError("Docker archive bytes changed during the load verification")

        progress("[7/7] Write the release record")
        release_manifest = {
            "schema_version": 1,
            "source": {
                "repository": repository,
                **source,
            },
            "application": {
                "archive_path": "release-artifacts/" + archive_path.name,
                "archive_sha256": archive_sha256,
            },
            "database_image_ref": database_ref,
            "build_input_refs": inputs["base_image_refs"],
            "migrations": [],
            "evidence": [],
        }
        package_proof = {
            "schema_version": 1,
            "archive_format": "docker-save-tar",
            "source": source,
            "release_manifest_file": release_manifest_path.name,
            "application": {
                "local_image_tag": tag,
                "archive_file": archive_path.name,
                "archive_path": "release-artifacts/" + archive_path.name,
                "archive_sha256": archive_sha256,
                "docker_image_config_digest": image_id,
                "platform": {
                    "os": before.get("Os"),
                    "architecture": before.get("Architecture"),
                },
            },
            "build_inputs": inputs,
            "verification": {
                "archive_untagged_image_id_checked": True,
                "archive_config_digest_checked": True,
                "archive_layer_references_present": archive_facts["layer_count"],
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
        write_json_no_replace(release_manifest_path, release_manifest)
        write_json_no_replace(package_proof_path, package_proof)
        return package_proof
    except Exception:
        # Preserve an already-promoted archive for manual recovery/inspection;
        # only discard the incomplete temporary export.
        try:
            temporary_archive.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build, export, and locally reload one source-SHA-tagged Docker image.")
    parser.add_argument("--root", required=True, type=Path, help="explicit, clean Git checkout root")
    parser.add_argument("--output-dir", required=True, type=Path, help="checkout/release-artifacts directory")
    parser.add_argument("--docker", default="docker", help="Docker CLI executable")
    args = parser.parse_args(argv)
    try:
        manifest = package_release(args.root, args.output_dir, args.docker)
    except (PackageError, OSError):
        print("release packaging failed; review the last phase and verify the local Docker engine", file=sys.stderr)
        return 1
    print(json.dumps({
        "status": "packaged_and_load_verified",
        "archive_file": manifest["application"]["archive_file"],
        "archive_sha256": manifest["application"]["archive_sha256"],
        "docker_image_config_digest": manifest["application"]["docker_image_config_digest"],
        "registry_manifest_digest": manifest["registry_manifest_digest"]["status"],
        "runtime_acceptance": manifest["runtime_acceptance"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
