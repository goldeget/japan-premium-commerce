#!/usr/bin/env python3
"""Render a private systemd timer for Ordenowa's notification CLI.

This utility only writes unit files into an explicitly supplied output
directory. It never calls systemctl, Docker, or the notification CLI.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


_SAFE_ABSOLUTE_PATH = re.compile(r"^/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+$")
_SAFE_ACCOUNT = re.compile(r"^[a-z_][a-z0-9_-]{0,30}$")
_SAFE_COMPOSE_PROJECT = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
_DECIMAL_INTEGER = re.compile(r"^[0-9]+$")
_CHANNEL_SETS = {"mail", "push", "mail,push"}
_CLI_PATH = "/var/www/html/modules/ordenowaprocurement/bin/dispatch-notifications.php"


@dataclass(frozen=True)
class Config:
    project_dir: str
    project_name: str
    docker_bin: str
    shop_id: int
    limit: int
    channels: str
    host_user: str
    host_group: str
    timeout_seconds: int


def validate_runtime_path(name: str, value: str) -> str:
    if not isinstance(value, str) or not _SAFE_ABSOLUTE_PATH.fullmatch(value):
        raise ValueError(
            f"{name} must be an absolute POSIX path containing only letters, "
            "digits, underscore, dot, slash, and hyphen"
        )
    if any(part in {".", ".."} for part in value.split("/")[1:]):
        raise ValueError(f"{name} cannot contain dot or parent path components")
    if value == "/":
        raise ValueError(f"{name} must name a non-root path")
    return value


def validate_account(name: str, value: str) -> str:
    if not isinstance(value, str) or not _SAFE_ACCOUNT.fullmatch(value) or value == "root":
        raise ValueError(f"{name} must be a valid non-root system account name")
    return value


def validate_project_name(value: str) -> str:
    if not isinstance(value, str) or not _SAFE_COMPOSE_PROJECT.fullmatch(value):
        raise ValueError("Compose project name must be 1..63 characters matching [a-z0-9][a-z0-9_-]*")
    return value


def parse_decimal_integer(name: str, value: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, str) or not _DECIMAL_INTEGER.fullmatch(value):
        raise ValueError(f"{name} must be a base-10 integer from {minimum} through {maximum}")
    parsed = int(value, 10)
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be a base-10 integer from {minimum} through {maximum}")
    return parsed


def build_config(
    *,
    project_dir: str,
    project_name: str,
    docker_bin: str = "/usr/bin/docker",
    shop_id: str,
    limit: str = "25",
    channels: str = "mail,push",
    host_user: str,
    host_group: str,
    timeout_seconds: str = "600",
) -> Config:
    project_dir = validate_runtime_path("project directory", project_dir)
    project_name = validate_project_name(project_name)
    docker_bin = validate_runtime_path("Docker executable", docker_bin)
    host_user = validate_account("host user", host_user)
    host_group = validate_account("host group", host_group)

    parsed_shop = parse_decimal_integer("shop ID", shop_id, 1, 2_147_483_647)
    parsed_limit = parse_decimal_integer("limit", limit, 1, 100)
    parsed_timeout = parse_decimal_integer("timeout", timeout_seconds, 60, 3_600)

    if channels not in _CHANNEL_SETS:
        raise ValueError("channels must be exactly mail, push, or mail,push")

    return Config(
        project_dir=project_dir,
        project_name=project_name,
        docker_bin=docker_bin,
        shop_id=parsed_shop,
        limit=parsed_limit,
        channels=channels,
        host_user=host_user,
        host_group=host_group,
        timeout_seconds=parsed_timeout,
    )


def render_units(config: Config) -> dict[str, str]:
    """Return one service and timer; a shop has only one scheduled dispatcher."""
    base = f"ordenowa-{config.project_name}-notify-shop{config.shop_id}"
    compose_file = f"{config.project_dir}/compose.yaml"
    command = " ".join(
        (
            config.docker_bin,
            "--context=default",
            "compose",
            f"--project-name={config.project_name}",
            f"--project-directory={config.project_dir}",
            f"--file={compose_file}",
            "exec",
            "-T",
            "--user",
            "www-data",
            "prestashop",
            "php",
            _CLI_PATH,
            f"--shop={config.shop_id}",
            f"--channels={config.channels}",
            f"--limit={config.limit}",
        )
    )
    service = f"""[Unit]
Description=Ordenowa procurement notification dispatch for shop {config.shop_id}

[Service]
Type=oneshot
User={config.host_user}
Group={config.host_group}
WorkingDirectory=/
UMask=0077
ExecStart={command}
TimeoutStartSec={config.timeout_seconds}s
TimeoutStopSec=30s
KillSignal=SIGTERM
KillMode=control-group
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
StandardOutput=journal
StandardError=journal
SyslogIdentifier={base}
"""
    timer = f"""[Unit]
Description=Run Ordenowa procurement notification dispatch after a one-minute idle interval for shop {config.shop_id}

[Timer]
OnBootSec=60s
OnUnitInactiveSec=60s
RandomizedDelaySec=3s
AccuracySec=1s
Unit={base}.service

[Install]
WantedBy=timers.target
"""
    return {f"{base}.service": service, f"{base}.timer": timer}


def _is_live_systemd_destination(path: Path) -> bool:
    if os.name != "posix":
        return False
    parts = path.parts
    return any(
        parts[index] == "systemd" and parts[index + 1] in {"system", "user"}
        for index in range(len(parts) - 1)
    )


def write_units(output_dir: str, config: Config) -> list[Path]:
    supplied_destination = Path(output_dir).expanduser()
    if supplied_destination.is_symlink():
        raise ValueError("output directory cannot be a symbolic link")
    destination = supplied_destination.resolve()
    if _is_live_systemd_destination(destination):
        raise ValueError("output directory must not be a live systemd unit directory")
    if not destination.is_dir():
        raise ValueError("output directory must already exist")

    rendered = render_units(config)
    targets = [destination / name for name in rendered]
    for target in targets:
        if target.exists() or target.is_symlink():
            raise ValueError(f"refusing to overwrite existing unit: {target.name}")

    created: list[Path] = []
    try:
        for name, contents in rendered.items():
            target = destination / name
            with target.open("x", encoding="utf-8", newline="\n") as unit_file:
                unit_file.write(contents)
            created.append(target)
    except OSError:
        for target in created:
            target.unlink(missing_ok=True)
        raise
    return targets


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True, help="absolute Linux directory containing compose.yaml and .env")
    parser.add_argument("--project-name", required=True, help="explicit Compose project name for the running application stack")
    parser.add_argument("--docker-bin", default="/usr/bin/docker", help="absolute Docker CLI path on the host")
    parser.add_argument("--shop-id", required=True, help="explicit PrestaShop shop ID")
    parser.add_argument("--limit", default="25", help="dispatch batch size (1..100; default 25)")
    parser.add_argument("--channels", default="mail,push", help="mail, push, or mail,push (default: mail,push)")
    parser.add_argument("--host-user", required=True, help="non-root host account with access to the Docker daemon")
    parser.add_argument("--host-group", required=True, help="non-root host group granting the required Docker access")
    parser.add_argument("--timeout-seconds", default="600", help="oneshot start timeout (60..3600; default 600)")
    parser.add_argument("--output-dir", required=True, help="existing directory for rendered unit files")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = build_config(
            project_dir=args.project_dir,
            project_name=args.project_name,
            docker_bin=args.docker_bin,
            shop_id=args.shop_id,
            limit=args.limit,
            channels=args.channels,
            host_user=args.host_user,
            host_group=args.host_group,
            timeout_seconds=args.timeout_seconds,
        )
        paths = write_units(args.output_dir, config)
    except (OSError, ValueError) as error:
        print(f"unit generation failed: {error}", file=sys.stderr)
        return 2
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
