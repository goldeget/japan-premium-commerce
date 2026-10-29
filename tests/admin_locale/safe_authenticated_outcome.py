#!/usr/bin/env python3
"""Turn a private native-admin helper capture into a minimal safe result."""

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
    'native_login_get', 'native_login_get_redirects', 'native_login_post', 'native_login_post_redirects',
    "ci_guard",
    "admin_bootstrap_path",
    "bootstrap",
    "test_only_dependency_bootstrap",
    "admin_kernel_boot",
    "module_inventory",
    "native_route_services",
    "install_test_only_provider",
    "browserkit_authenticated_login",
    "native_authenticated_error_route",
    "assert_authenticated_korean_error",
}
CAUSE_CLASS_RE = re.compile(r"[A-Za-z0-9_\\]{1,160}\Z")
FAILURE_SOURCE_RE = re.compile(r"[A-Za-z0-9_.-]{1,165}\.php:[1-9][0-9]{0,6}\Z")
TWIG_TEMPLATE_RE = re.compile(
    r"@(?:PrestaShop/Admin|PrestaShopCore|Modules/(?:ps_mbo|ps_facebook))/(?:[A-Za-z0-9_-]+/)*"
    r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.twig\Z"
)
AUTH_LANDING_KEYS = {
    "post_status", "redirect_count", "final_status", "final_path_kind",
    "final_controller_kind", "redirect_token_kind", "body_token_kind", "body_page_kind",
}
AUTH_PATH_KINDS = {"login", "index", "other_admin"}
AUTH_CONTROLLER_KINDS = {"login", "dashboard", "other", "none"}
AUTH_TOKEN_KINDS = {"missing", "masked", "plain_hex32", "plain_uri_safe", "other"}
AUTH_PAGE_KINDS = {"login", "dashboard", "security_warning", "other"}
MBO_FAILURE_ASSERTIONS = {
    "native_kernel_browser_target_request_count_invalid",
    "native_mbo_response_status_not_503",
    "native_mbo_injected_header_missing",
    "native_mbo_content_type_not_html",
    "native_mbo_document_language_not_korean",
    "native_mbo_korean_message_occurrences_insufficient",
    "native_mbo_english_source_message_present",
    "native_mbo_provider_invocation_count_invalid",
    "native_mbo_session_csrf_probe_count_invalid",
    "native_mbo_session_csrf_not_verified",
}
MBO_FAILURE_FACT_KEYS = {
    "response_status", "injected_header_present", "html_content_type",
    "korean_document_language", "korean_message_occurrences", "english_source_present",
    "provider_calls", "csrf_verified", "csrf_probe_count", "body_token_present",
}
NATIVE_EXCEPTION_OBSERVATION_KEYS = {"phase", "chain"}
NATIVE_EXCEPTION_PHASES = {"main_request", "error_subrequest"}
NATIVE_EXCEPTION_ENTRY_KEYS = {"class", "source", "http_status", "twig_template", "twig_line"}


class _DuplicateJsonKey(ValueError):
    pass


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey
        result[key] = value
    return result


def _safe_auth_landing_facts(value: Any) -> dict[str, Any] | None:
    """Accept only the fixed, enum-only native-login landing diagnostics."""
    if not isinstance(value, dict) or set(value) != AUTH_LANDING_KEYS:
        return None
    for key in ("post_status", "final_status"):
        status = value[key]
        if type(status) is not int or not 100 <= status <= 599:
            return None
    redirect_count = value["redirect_count"]
    if type(redirect_count) is not int or not 0 <= redirect_count <= 6:
        return None
    if not isinstance(value["final_path_kind"], str) or value["final_path_kind"] not in AUTH_PATH_KINDS:
        return None
    if not isinstance(value["final_controller_kind"], str) or value["final_controller_kind"] not in AUTH_CONTROLLER_KINDS:
        return None
    if not isinstance(value["redirect_token_kind"], str) or value["redirect_token_kind"] not in AUTH_TOKEN_KINDS:
        return None
    if not isinstance(value["body_token_kind"], str) or value["body_token_kind"] not in AUTH_TOKEN_KINDS:
        return None
    if not isinstance(value["body_page_kind"], str) or value["body_page_kind"] not in AUTH_PAGE_KINDS:
        return None
    return {key: value[key] for key in (
        "post_status", "redirect_count", "final_status", "final_path_kind",
        "final_controller_kind", "redirect_token_kind", "body_token_kind", "body_page_kind",
    )}


def _safe_mbo_failure_facts(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or set(value) != MBO_FAILURE_FACT_KEYS:
        return None
    status = value["response_status"]
    if type(status) is not int or not 100 <= status <= 599:
        return None
    for key in (
        "injected_header_present", "html_content_type", "korean_document_language",
        "english_source_present", "csrf_verified", "body_token_present",
    ):
        if type(value[key]) is not bool:
            return None
    for key, maximum in (("korean_message_occurrences", 10), ("provider_calls", 100), ("csrf_probe_count", 100)):
        if type(value[key]) is not int or not 0 <= value[key] <= maximum:
            return None
    return {key: value[key] for key in (
        "response_status", "injected_header_present", "html_content_type",
        "korean_document_language", "korean_message_occurrences", "english_source_present",
        "provider_calls", "csrf_verified", "csrf_probe_count", "body_token_present",
    )}


def _safe_native_exception_observation(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or set(value) != NATIVE_EXCEPTION_OBSERVATION_KEYS:
        return None
    phase = value["phase"]
    chain = value["chain"]
    if not isinstance(phase, str) or phase not in NATIVE_EXCEPTION_PHASES:
        return None
    if not isinstance(chain, list) or len(chain) > 4:
        return None

    safe_chain = []
    for entry in chain:
        if not isinstance(entry, dict) or set(entry) != NATIVE_EXCEPTION_ENTRY_KEYS:
            return None
        class_name = entry["class"]
        source = entry["source"]
        status = entry["http_status"]
        template = entry["twig_template"]
        twig_line = entry["twig_line"]
        if not isinstance(class_name, str) or not EXCEPTION_RE.fullmatch(class_name):
            return None
        if not isinstance(source, str) or not FAILURE_SOURCE_RE.fullmatch(source):
            return None
        if int(source.rsplit(":", 1)[1]) > 1_000_000:
            return None
        if status is not None and (type(status) is not int or not 100 <= status <= 599):
            return None
        if template is None or twig_line is None:
            if template is not None or twig_line is not None:
                return None
        elif (not isinstance(template, str) or not TWIG_TEMPLATE_RE.fullmatch(template)
              or type(twig_line) is not int or not 1 <= twig_line <= 100_000):
            return None
        safe_chain.append({
            "class": class_name,
            "source": source,
            "http_status": status,
            "twig_template": template,
            "twig_line": twig_line,
        })
    return {"phase": phase, "chain": safe_chain}


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
    *,
    include_details: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "passed": False,
        "failure_code": failure_code,
    }
    if helper_exit_status is not None:
        result["helper_exit_status"] = helper_exit_status

    if include_details and payload is not None:
        stage = payload.get("failed_stage")
        if isinstance(stage, str) and STAGE_RE.fullmatch(stage) and stage in FAILURE_STAGES:
            result["failed_stage"] = stage
        exception_class = payload.get("exception_class")
        if isinstance(exception_class, str) and len(exception_class) <= 160 and EXCEPTION_RE.fullmatch(exception_class):
            result["exception_class"] = exception_class
        frames = payload.get('failure_trace')
        if isinstance(frames, list) and len(frames) <= 8:
            safe_frames = []
            for frame in frames:
                if not isinstance(frame, dict):
                    continue
                class_name, function, source = (frame.get(key) for key in ('class', 'function', 'source'))
                if (isinstance(class_name, str) and len(class_name) <= 160 and EXCEPTION_RE.fullmatch(class_name)
                        and isinstance(function, str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', function)
                        and isinstance(source, str) and len(source) <= 140 and FAILURE_SOURCE_RE.fullmatch(source)
                        and int(source.rsplit(':', 1)[1]) <= 1_000_000):
                    safe_frames.append({'class': class_name, 'function': function, 'source': source})
            result['failure_trace'] = safe_frames
        cause_class = payload.get("cause_class")
        if isinstance(cause_class, str) and CAUSE_CLASS_RE.fullmatch(cause_class):
            result["cause_class"] = cause_class
        failure_source = payload.get("failure_source")
        source_match = FAILURE_SOURCE_RE.fullmatch(failure_source) if isinstance(failure_source, str) else None
        if source_match is not None and len(failure_source) <= 180:
            source_line = int(failure_source.rsplit(":", 1)[1])
            if source_line <= 1_000_000:
                result["failure_source"] = failure_source
        twig_template = payload.get("twig_template")
        if isinstance(twig_template, str) and TWIG_TEMPLATE_RE.fullmatch(twig_template):
            result["twig_template"] = twig_template
            twig_line = payload.get("twig_template_line")
            if type(twig_line) is int and 1 <= twig_line <= 100_000:
                result["twig_template_line"] = twig_line
        auth_landing = _safe_auth_landing_facts(payload.get("auth_landing"))
        if auth_landing is not None:
            result["auth_landing"] = auth_landing
        failed_assertion = payload.get("failed_assertion")
        if isinstance(failed_assertion, str) and failed_assertion in MBO_FAILURE_ASSERTIONS:
            result["failed_assertion"] = failed_assertion
        failure_facts = _safe_mbo_failure_facts(payload.get("failure_facts"))
        if failure_facts is not None:
            result["failure_facts"] = failure_facts
        exception_observation = _safe_native_exception_observation(payload.get("exception_observation"))
        if exception_observation is not None:
            result["exception_observation"] = exception_observation
    return result


def _safe_dependency_sources(value: Any) -> dict[str, dict[str, str | None]] | None:
    if not isinstance(value, dict) or set(value) != set(EXPECTED_DEPENDENCIES):
        return None

    safe_sources: dict[str, dict[str, str | None]] = {}
    for package, expected in EXPECTED_DEPENDENCIES.items():
        actual = value.get(package)
        if not isinstance(actual, dict):
            return None
        version = actual.get("version")
        commit = actual.get("source_commit")
        archive_digest = actual.get("archive_sha256")
        if version != expected["version"] or not isinstance(version, str):
            return None
        if not isinstance(commit, str) or not SHA1_RE.fullmatch(commit):
            return None
        if commit != expected["source_commit"]:
            return None

        if expected["archive_sha256"] == "required":
            if not isinstance(archive_digest, str) or not SHA256_RE.fullmatch(archive_digest):
                return None
        elif archive_digest is not None:
            return None

        safe_sources[package] = {
            "version": version,
            "source_commit": commit,
            "archive_sha256": archive_digest,
        }
    return safe_sources


def _safe_mbo_error_render(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    fixed_values: dict[str, str | bool | int] = {
        "mode": "authenticated_production_kernel_browserkit_request",
        "actual_admin_login_form_post": True,
        "native_login_transport": "loopback_http_native_front_controller",
        "kernel_browser_target_request_count": 1,
        "native_route": "admin_mbo_catalog_theme",
        "controller": "ThemeCatalogController::indexAction",
        "response_status": 503,
        "injected_header_verified": True,
        "full_native_layout": True,
        "korean_document_language": True,
        "english_source_absent": True,
        "injected_provider_invocations": 1,
        "injected_provider_http_calls": 0,
        "browser_socket_requests": 0,
        "script_initiated_business_mutations": False,
        "authentication_session_or_audit_writes_possible": True,
        "bootstrap_database_side_effects_instrumented": False,
        "bootstrap_network_side_effects_instrumented": False,
        "native_session_csrf_verified": True,
        "native_session_csrf_probe_count": 1,
    }

    for key, expected in fixed_values.items():
        actual = value.get(key)
        if type(actual) is not type(expected) or actual != expected:
            return None

    occurrences = value.get("korean_message_occurrences")
    if type(occurrences) is not int or not 2 <= occurrences <= 10:
        return None

    loopback_requests = value.get("native_login_loopback_http_requests")
    if type(loopback_requests) is not int or not 3 <= loopback_requests <= 14:
        return None
    cookie_count = value.get("native_login_cookie_count")
    if type(cookie_count) is not int or not 1 <= cookie_count <= 20:
        return None
    snapshot_hash = value.get('private_response_snapshot_sha256')
    if not isinstance(snapshot_hash, str) or re.fullmatch(r'[0-9a-f]{64}', snapshot_hash) is None:
        return None

    safe_render: dict[str, Any] = dict(fixed_values)
    safe_render["korean_message_occurrences"] = occurrences
    safe_render["native_login_loopback_http_requests"] = loopback_requests
    safe_render["native_login_cookie_count"] = cookie_count
    safe_render['private_response_snapshot_sha256'] = snapshot_hash
    return safe_render


def collect_safe_outcome(raw_output: str | bytes, helper_exit_status: Any) -> dict[str, Any]:
    """Validate an exact helper result and return only safe, allowlisted fields."""
    if type(helper_exit_status) is not int or not 0 <= helper_exit_status <= 255:
        return _safe_failure("invalid_exit_status", None)

    try:
        payload = _parse_object(raw_output)
    except (UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return _safe_failure("invalid_helper_json", helper_exit_status)

    if helper_exit_status != 0:
        return _safe_failure(
            "helper_exit_nonzero",
            helper_exit_status,
            payload,
            include_details=True,
        )
    if payload.get("schema") != SCHEMA or type(payload.get("schema")) is not int:
        return _safe_failure("outcome_contract_mismatch", helper_exit_status)
    if payload.get("passed") is not True:
        return _safe_failure(
            "helper_reported_failure",
            helper_exit_status,
            payload,
            include_details=True,
        )

    dependencies = _safe_dependency_sources(payload.get("test_dependency_sources"))
    mbo_error_render = _safe_mbo_error_render(payload.get("mbo_error_render"))
    if dependencies is None or mbo_error_render is None:
        return _safe_failure("outcome_contract_mismatch", helper_exit_status)

    return {
        "schema": SCHEMA,
        "passed": True,
        "helper_exit_status": 0,
        "test_dependency_sources": dependencies,
        "mbo_error_render": mbo_error_render,
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
    descriptor, temporary_name = tempfile.mkstemp(prefix=".safe-outcome-", dir=parent)
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
        self.exit(64, "safe_authenticated_outcome: invalid arguments\n")


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
        sys.stderr.write("safe_authenticated_outcome: invalid arguments\n")
        return 64
    helper_exit_status = int(status_text)
    if helper_exit_status > 255:
        sys.stderr.write("safe_authenticated_outcome: invalid arguments\n")
        return 64

    input_path = Path(arguments.private_input)
    output_path = Path(arguments.safe_output)
    if _same_file_or_path(input_path, output_path):
        sys.stderr.write("safe_authenticated_outcome: input and output must differ\n")
        return 64

    try:
        raw_output = _read_private_input(input_path)
        safe_outcome = collect_safe_outcome(raw_output, helper_exit_status)
    except ValueError:
        safe_outcome = _safe_failure("private_input_unavailable", helper_exit_status)

    try:
        _write_safe_output(output_path, safe_outcome)
    except (OSError, ValueError):
        sys.stderr.write("safe_authenticated_outcome: safe output unavailable\n")
        return 2
    return 0 if safe_outcome["passed"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
