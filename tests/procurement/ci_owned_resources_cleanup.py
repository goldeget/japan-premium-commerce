#!/usr/bin/env python3
"""Remove only run-owned Docker resources and fail closed on query errors."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from typing import Any, Callable, Sequence


IMAGE_REF = re.compile(r"local-only/ordenowa-procurement-ci:run-[0-9]+-[0-9]+\Z")
IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
RESTORE_NAME = re.compile(r"ordenowa-procurement-ci-[0-9]+-[0-9]+-restore\Z")
CONTAINER_ID = re.compile(r"[0-9a-f]{64}\Z")
TIMEOUT_SECONDS = 30
Runner = Callable[[Sequence[str], int], subprocess.CompletedProcess[str]]


class CleanupError(Exception):
    """A fixed cleanup failure safe for a public CI log."""


def _run(argv: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
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


def _checked_docker(docker: str, args: Sequence[str], runner: Runner) -> str:
    argv = [docker, "--context", "default", *args]
    try:
        result = runner(argv, TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        raise CleanupError("docker_command_failed") from None
    if result.returncode != 0 or not isinstance(result.stdout, str):
        raise CleanupError("docker_command_failed")
    return result.stdout


def _rows(output: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        fields = stripped.split()
        if len(fields) != 2:
            raise CleanupError("docker_list_output_invalid")
        rows.append((fields[0], fields[1]))
    return rows


def _image_rows(docker: str, image_ref: str, runner: Runner) -> list[tuple[str, str]]:
    output = _checked_docker(
        docker,
        [
            "image", "ls", "--no-trunc",
            "--format", "{{.Repository}}:{{.Tag}} {{.ID}}",
            "--filter", "reference=" + image_ref,
        ],
        runner,
    )
    return _rows(output)


def _exact_image_row(rows: list[tuple[str, str]], image_ref: str) -> tuple[str, str] | None:
    matches = [row for row in rows if row[0] == image_ref]
    if not matches:
        return None
    if len(matches) != 1:
        raise CleanupError("owned_image_record_ambiguous")
    return matches[0]


def remove_owned_image(
    image_ref: str,
    expected_image_id: str,
    *,
    docker: str = "docker",
    runner: Runner = _run,
) -> str:
    """Remove this run's image tag; return absent/removed only after checked queries."""
    if not isinstance(image_ref, str) or not IMAGE_REF.fullmatch(image_ref):
        raise CleanupError("owned_image_ref_invalid")
    if not isinstance(expected_image_id, str) or not IMAGE_ID.fullmatch(expected_image_id):
        raise CleanupError("owned_image_id_invalid")

    row = _exact_image_row(_image_rows(docker, image_ref, runner), image_ref)
    if row is None:
        return "absent"
    _, listed_image_id = row
    if listed_image_id != expected_image_id:
        raise CleanupError("owned_image_id_mismatch")

    inspected = _checked_docker(
        docker,
        ["image", "inspect", "--format", "{{.Id}}", image_ref],
        runner,
    )
    inspect_lines = [line.strip() for line in inspected.splitlines() if line.strip()]
    if inspect_lines != [expected_image_id]:
        raise CleanupError("owned_image_id_mismatch")

    _checked_docker(docker, ["image", "rm", image_ref], runner)
    remaining = _exact_image_row(_image_rows(docker, image_ref, runner), image_ref)
    if remaining is not None:
        raise CleanupError("owned_image_remains")
    return "removed"


def _container_rows(docker: str, container_name: str, runner: Runner) -> list[tuple[str, str]]:
    output = _checked_docker(
        docker,
        [
            "container", "ls", "--all", "--no-trunc",
            "--format", "{{.Names}} {{.ID}}",
            "--filter", "name=" + container_name,
        ],
        runner,
    )
    return _rows(output)


def remove_owned_container(
    container_name: str,
    *,
    docker: str = "docker",
    runner: Runner = _run,
) -> str:
    """Remove only the exactly named run-owned restore container."""
    if not isinstance(container_name, str) or not RESTORE_NAME.fullmatch(container_name):
        raise CleanupError("owned_container_name_invalid")

    matches = [row for row in _container_rows(docker, container_name, runner) if row[0] == container_name]
    if not matches:
        return "absent"
    if len(matches) != 1 or not CONTAINER_ID.fullmatch(matches[0][1]):
        raise CleanupError("owned_container_record_invalid")

    container_id = matches[0][1]
    _checked_docker(docker, ["container", "rm", "--force", container_id], runner)
    remaining = [row for row in _container_rows(docker, container_name, runner) if row[0] == container_name]
    if remaining:
        raise CleanupError("owned_container_remains")
    return "removed"


class _QuietArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        self.exit(64, "CI owned-resource cleanup: invalid arguments\n")


def main(argv: list[str] | None = None) -> int:
    parser = _QuietArgumentParser(description="Clean only exact run-owned Docker resources.")
    commands = parser.add_subparsers(dest="resource", required=True)
    image = commands.add_parser("image")
    image.add_argument("--image-ref", required=True)
    image.add_argument("--image-id", required=True)
    image.add_argument("--docker", default="docker")
    container = commands.add_parser("container")
    container.add_argument("--container-name", required=True)
    container.add_argument("--docker", default="docker")

    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code) if isinstance(error.code, int) else 64

    try:
        if args.resource == "image":
            status = remove_owned_image(args.image_ref, args.image_id, docker=args.docker)
        else:
            status = remove_owned_container(args.container_name, docker=args.docker)
    except CleanupError as error:
        print("CI owned-resource cleanup failed: " + str(error), file=sys.stderr)
        return 1
    print("PASS CI owned-resource cleanup resource=" + args.resource + " status=" + status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
