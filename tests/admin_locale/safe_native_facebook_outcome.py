#!/usr/bin/env python3
"""Validate private native-Facebook probe output and emit a safe allowlist."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Any


SCHEMA = 1
MAX_INPUT_BYTES = 1_048_576
EXPECTED_MODULES = {
    "ps_facebook": "1.38.19",
    "kuraneabackoffice": "1.0.8",
}
EXPECTED_DEPENDENCIES = {
    "symfony/browser-kit": {
        "version": "6.4.44",
        "source_commit": "4f631476bb549d882a173c47bf693f3ef84c722d",
        "archive_sha256": "required",
    },
    "symfony/css-selector": {
        "version": "6.4.45",
        "source_commit": "5484e316cd8125f5215bbf829151e2211aa6d101",
        "archive_sha256": "required",
    },
    "symfony/dom-crawler": {
        "version": "6.4.44",
        "source_commit": "998855f6c3699f148b54096d1d7d2b8b0b0fc298",
        "archive_sha256": None,
    },
}
SHA1_RE = re.compile(r"[a-f0-9]{40}\Z")
SHA256_RE = re.compile(r"[a-f0-9]{64}\Z")
STAGE_RE = re.compile(r"[a-z_]{1,80}\Z")
EXCEPTION_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\\[A-Za-z_][A-Za-z0-9_]*){0,10}\Z")
FAILURE_STAGES = {
    "ci_guard",
    "admin_bootstrap_path",
    "bootstrap",
    "test_only_dependency_bootstrap",
    "admin_kernel_boot",
    "read_only_module_inventory",
    "native_facebook_api_and_subscriber_contract",
    "login_browser_fixture",
    "framework_generated_facebook_admin_link",
    "test_only_controller_listener",
    "unauthenticated_facebook_negative",
    "other_route_negative",
    "generic_facebook_exception_negative",
    "access_denied_negative",
    "actual_installed_curl_failure_positive",
    "assert_safe_korean_html",
}


class _DuplicateJsonKey(ValueError):
    pass


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey
        result[key] = value
    return result


def _reject_json_constant(_: str) -> None:
    raise ValueError


def _parse_object(raw_output: str | bytes) -> dict[str, Any]:
    if isinstance(raw_output, bytes):
        if len(raw_output) > MAX_INPUT_BYTES:
            raise ValueError
        text = raw_output.decode("utf-8", errors="strict")
    elif isinstance(raw_output, str):
        if len(raw_output.encode("utf-8", errors="strict")) > MAX_INPUT_BYTES:
            raise ValueError
        text = raw_output
    else:
        raise ValueError

    parsed = json.loads(
        text,
        object_pairs_hook=_object_without_duplicate_keys,
        parse_constant=_reject_json_constant,
    )
    if not isinstance(parsed, dict):
        raise ValueError
    return parsed


def _safe_failure(
    failure_code: str,
    helper_exit_status: int | None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "passed": False,
        "failure_code": failure_code,
    }
    if helper_exit_status is not None:
        result["helper_exit_status"] = helper_exit_status
    if payload is not None:
        stage = payload.get("failed_stage")
        if isinstance(stage, str) and STAGE_RE.fullmatch(stage) and stage in FAILURE_STAGES:
            result["failed_stage"] = stage
        exception_class = payload.get("exception_class")
        if isinstance(exception_class, str) and len(exception_class) <= 160 and EXCEPTION_RE.fullmatch(exception_class):
            result["exception_class"] = exception_class
        source = payload.get('failure_source')
        if isinstance(source, str) and re.fullmatch(r'native_facebook_transport_fallback\.php:[1-9][0-9]{0,5}', source):
            result['failure_source'] = source
    return result


def _safe_modules(value: Any) -> dict[str, dict[str, str | bool]] | None:
    if not isinstance(value, dict) or set(value) != set(EXPECTED_MODULES):
        return None

    modules: dict[str, dict[str, str | bool]] = {}
    for module, expected_version in EXPECTED_MODULES.items():
        actual = value.get(module)
        if not isinstance(actual, dict):
            return None
        if actual.get("installed") is not True or actual.get("active") is not True:
            return None
        version = actual.get("version")
        if type(version) is not str or version != expected_version:
            return None
        modules[module] = {"installed": True, "active": True, "version": expected_version}
    return modules


def _safe_dependencies(value: Any) -> dict[str, dict[str, str | None]] | None:
    if not isinstance(value, dict) or set(value) != set(EXPECTED_DEPENDENCIES):
        return None

    sources: dict[str, dict[str, str | None]] = {}
    for package, expected in EXPECTED_DEPENDENCIES.items():
        actual = value.get(package)
        if not isinstance(actual, dict):
            return None
        version = actual.get("version")
        commit = actual.get("source_commit")
        archive_digest = actual.get("archive_sha256")
        if type(version) is not str or version != expected["version"]:
            return None
        if type(commit) is not str or not SHA1_RE.fullmatch(commit) or commit != expected["source_commit"]:
            return None
        if expected["archive_sha256"] == "required":
            if type(archive_digest) is not str or not SHA256_RE.fullmatch(archive_digest):
                return None
        elif archive_digest is not None:
            return None
        sources[package] = {
            "version": expected["version"],
            "source_commit": expected["source_commit"],
            "archive_sha256": archive_digest,
        }
    return sources


def _safe_source_hashes(value: Any) -> dict[str, str] | None:
    required = {
        "facebook_http_client_sha256",
        "project_subscriber_sha256",
        "project_template_sha256",
    }
    if not isinstance(value, dict) or set(value) != required:
        return None
    if any(type(value[key]) is not str or not SHA256_RE.fullmatch(value[key]) for key in required):
        return None
    return {key: value[key] for key in sorted(required)}


def _safe_facebook_fallback(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    fixed_values: dict[str, str | bool | int] = {
        "mode": "authenticated_native_admin_kernel_browserkit",
        "native_admin_login_posted": True,
        "native_session_csrf_verified": True,
        "native_session_csrf_probe_count": 1,
        "native_authenticated_read_gate_verified": True,
        "framework_generated_legacy_link": True,
        "route": "admin_legacy_controller_route",
        "controller": "AdminPsfacebookModuleController",
        "controller_action": "read",
        "positive_failure_source": "installed_ps_facebook_HttpClient_cURL_exception",
        "actual_http_client_source_trace_verified_by_fallback": True,
        "known_facebook_request_controller_events": 3,
        "mismatched_facebook_route_events": 0,
        "disabled_mode_facebook_sentinels": 0,
        "test_transport_target": "run_owned_ipv4_loopback_bind_only",
        "stream_server_listen_used": False,
        "facebook_vendor_initContent_called_by_fixture": False,
        "script_initiated_external_transport_requests": 0,
        "installed_http_client_calls": 1,
        "response_status": 503,
        "korean_safe_title": True,
        "korean_safe_message": True,
        "fixed_error_fragment_excludes_token_and_transport_details": True,
        "unauthenticated_status_not_converted": True,
        "other_route_status_not_converted": True,
        "generic_facebook_runtime_status_not_converted": True,
        "access_denied_status_preserved": True,
        "script_business_data_mutations": False,
        "login_session_or_auth_audit_writes_possible": True,
        "kernel_bootstrap_database_network_side_effects_instrumented": False,
    }
    for key, expected in fixed_values.items():
        actual = value.get(key)
        if type(actual) is not type(expected) or actual != expected:
            return None

    language = value.get("korean_document_language")
    if type(language) is not str or re.fullmatch(r"ko(?:[-_]kr)?", language, re.IGNORECASE) is None:
        return None

    return {**fixed_values, "korean_document_language": language.lower().replace("_", "-")}


def collect_safe_outcome(raw_output: str | bytes, helper_exit_status: Any) -> dict[str, Any]:
    """Validate an exact helper result; rebuild output from safe fields only."""
    if type(helper_exit_status) is not int or not 0 <= helper_exit_status <= 255:
        return _safe_failure("invalid_exit_status", None)

    try:
        payload = _parse_object(raw_output)
    except (UnicodeError, ValueError, TypeError, json.JSONDecodeError, RecursionError):
        return _safe_failure("invalid_helper_json", helper_exit_status)

    if helper_exit_status != 0:
        return _safe_failure("helper_exit_nonzero", helper_exit_status, payload)
    if type(payload.get("schema")) is not int or payload.get("schema") != SCHEMA:
        return _safe_failure("outcome_contract_mismatch", helper_exit_status)
    if payload.get("passed") is not True:
        return _safe_failure("helper_reported_failure", helper_exit_status, payload)

    modules = _safe_modules(payload.get("module_inventory"))
    dependencies = _safe_dependencies(payload.get("test_dependencies"))
    source_hashes = _safe_source_hashes(payload.get("source_sha256"))
    fallback = _safe_facebook_fallback(payload.get("facebook_error_fallback"))
    if modules is None or dependencies is None or source_hashes is None or fallback is None:
        return _safe_failure("outcome_contract_mismatch", helper_exit_status)

    return {
        "schema": SCHEMA,
        "passed": True,
        "helper_exit_status": 0,
        "modules": modules,
        "test_dependencies": dependencies,
        "source_sha256": source_hashes,
        "facebook_error_fallback": fallback,
    }


def _read_private_input(path: Path) -> bytes:
    try:
        if path.is_symlink():
            raise OSError
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise OSError
            if os.name == "posix" and metadata.st_mode & 0o077:
                raise OSError
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(65536, MAX_INPUT_BYTES + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > MAX_INPUT_BYTES:
                    raise OSError
            return b"".join(chunks)
        finally:
            os.close(descriptor)
    except OSError as error:
        raise ValueError("private_input_unavailable") from error


def _same_file_or_path(input_path: Path, output_path: Path) -> bool:
    try:
        if input_path.resolve(strict=False) == output_path.resolve(strict=False):
            return True
        if input_path.exists() and output_path.exists():
            return os.path.samefile(input_path, output_path)
    except OSError:
        return True
    return False


def _write_safe_output(path: Path, value: dict[str, Any]) -> None:
    parent = path.parent
    if path.is_symlink() or not parent.is_dir():
        raise OSError

    safe_bytes = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".facebook-safe-outcome-", dir=parent)
    temporary_path = Path(temporary_name)
    try:
        if os.name == "posix":
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(safe_bytes)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
        if os.name == "posix":
            os.chmod(path, 0o600)
    except BaseException:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


class _QuietArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        self.exit(64, "safe_native_facebook_outcome: invalid arguments\n")


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = _QuietArgumentParser(add_help=False)
    parser.add_argument("--private-input", "--input", dest="private_input", required=True)
    parser.add_argument("--safe-output", "--output", dest="safe_output", required=True)
    parser.add_argument("--helper-exit-status", "--exit-status", dest="helper_exit_status", required=True)
    parser.add_argument("--help", action="help")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = _parse_arguments(argv)
    except SystemExit as error:
        return int(error.code) if isinstance(error.code, int) else 64

    status_text = arguments.helper_exit_status
    if not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})", status_text):
        sys.stderr.write("safe_native_facebook_outcome: invalid arguments\n")
        return 64
    helper_exit_status = int(status_text)
    if helper_exit_status > 255:
        sys.stderr.write("safe_native_facebook_outcome: invalid arguments\n")
        return 64

    input_path = Path(arguments.private_input)
    output_path = Path(arguments.safe_output)
    if _same_file_or_path(input_path, output_path):
        sys.stderr.write("safe_native_facebook_outcome: input and output must differ\n")
        return 64

    try:
        raw_output = _read_private_input(input_path)
        safe_outcome = collect_safe_outcome(raw_output, helper_exit_status)
    except ValueError:
        safe_outcome = _safe_failure("private_input_unavailable", helper_exit_status)

    try:
        _write_safe_output(output_path, safe_outcome)
    except (OSError, ValueError):
        sys.stderr.write("safe_native_facebook_outcome: safe output unavailable\n")
        return 2
    return 0 if safe_outcome["passed"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
