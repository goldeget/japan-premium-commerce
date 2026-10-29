#!/usr/bin/env python3
"""Fail-closed allowlist collector for five isolated native Facebook probes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any


SCHEMA = 4
MAX_INPUT_BYTES = 1_048_576
CASES = ("unauthenticated", "other_route", "generic_facebook", "access_denied", "curl_transport")
MODULES = {"ps_facebook": "1.38.19", "kuraneabackoffice": "1.0.8"}
DEPENDENCIES = {
    "symfony/browser-kit": ("6.4.44", "4f631476bb549d882a173c47bf693f3ef84c722d", True),
    "symfony/css-selector": ("6.4.45", "5484e316cd8125f5215bbf829151e2211aa6d101", True),
    "symfony/dom-crawler": ("6.4.44", "998855f6c3699f148b54096d1d7d2b8b0b0fc298", False),
}
SHA256_RE = re.compile(r"[a-f0-9]{64}\Z")


class _DuplicateKey(ValueError):
    pass


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey
        result[key] = value
    return result


def _no_constant(_: str) -> None:
    raise ValueError


def _parse(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError
    value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_object, parse_constant=_no_constant)
    if not isinstance(value, dict):
        raise ValueError
    return value


def _read_private(path_text: str) -> bytes:
    from safe_authenticated_outcome import _read_private_input
    return _read_private_input(Path(path_text))


def _validate_modules(value: Any) -> dict[str, dict[str, str | bool]]:
    if not isinstance(value, dict) or set(value) != set(MODULES):
        raise ValueError
    result: dict[str, dict[str, str | bool]] = {}
    for name, version in MODULES.items():
        module = value[name]
        if not isinstance(module, dict) or set(module) != {"installed", "active", "version"}:
            raise ValueError
        if module["installed"] is not True or module["active"] is not True or module["version"] != version:
            raise ValueError
        result[name] = {"installed": True, "active": True, "version": version}
    return result


def _validate_dependencies(value: Any) -> dict[str, dict[str, str | None]]:
    if not isinstance(value, dict) or set(value) != set(DEPENDENCIES):
        raise ValueError
    result: dict[str, dict[str, str | None]] = {}
    for name, (version, commit, has_archive) in DEPENDENCIES.items():
        item = value[name]
        if not isinstance(item, dict) or set(item) != {"version", "source_commit", "archive_sha256"}:
            raise ValueError
        digest = item["archive_sha256"]
        if item["version"] != version or item["source_commit"] != commit:
            raise ValueError
        if has_archive:
            if type(digest) is not str or not SHA256_RE.fullmatch(digest):
                raise ValueError
        elif digest is not None:
            raise ValueError
        result[name] = {"version": version, "source_commit": commit, "archive_sha256": digest}
    return result


def _validate_hashes(value: Any) -> dict[str, str]:
    keys = {"facebook_http_client_sha256", "project_subscriber_sha256", "project_template_sha256"}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError
    if any(type(value[key]) is not str or not SHA256_RE.fullmatch(value[key]) for key in keys):
        raise ValueError
    return {key: value[key] for key in sorted(keys)}


def _validate_case_facts(case_name: str, value: Any) -> dict[str, Any]:
    keys = {
        "native_login_transport", "native_login_form_posted", "native_login_http_requests",
        "native_login_stages_verified", "native_http_body_token_applied",
        "framework_generated_legacy_link", "framework_link_has_token",
        "unauthenticated_link_token_validity_claimed", "case", "browserkit_target_get_count",
        "attempted_route", "attempted_controller", "route_observation", "route", "controller", "controller_action",
        "authenticated_read_gate_passes", "authenticated_full_gate_passes",
        "known_facebook_request_controller_events", "mismatched_facebook_route_events",
        "disabled_mode_facebook_sentinels", "other_route_exception_count", "generic_facebook_exception_count",
        "native_legacy_access_denied_exception_count", "native_acl_denial_preconditions_verified",
        "read_permission_row_removed_before_request", "read_permission_row_restored",
        "native_access_denied_from_legacy_controller", "test_transport_target", "stream_server_listen_used",
        "facebook_vendor_initContent_called_by_fixture", "script_initiated_external_transport_requests",
        "installed_http_client_calls", "response_status", "unauthenticated_status_not_converted",
        "unauthenticated_auth_rejection",
        "other_route_status_not_converted", "generic_facebook_runtime_status_not_converted",
        "access_denied_status_preserved", "korean_safe_title", "korean_safe_message",
        "korean_document_language", "fixed_error_fragment_excludes_token_and_transport_details",
        "native_session_csrf_verified", "native_session_csrf_probe_count", "positive_response_snapshot_sha256",
        "script_business_data_mutations", "login_session_or_auth_audit_writes_possible",
        "kernel_bootstrap_database_network_side_effects_instrumented",
    }
    if not isinstance(value, dict) or set(value) != keys or value.get("case") != case_name:
        raise ValueError

    authenticated = case_name != "unauthenticated"
    is_other = case_name == "other_route"
    is_generic = case_name == "generic_facebook"
    is_denied = case_name == "access_denied"
    is_positive = case_name == "curl_transport"
    expected_login_transport = "loopback_http_native_front_controller" if authenticated else "none"
    if value["native_login_transport"] != expected_login_transport:
        raise ValueError
    if type(value["native_login_form_posted"]) is not bool or value["native_login_form_posted"] is not authenticated:
        raise ValueError
    requests = value["native_login_http_requests"]
    if type(requests) is not int or (not authenticated and requests != 0) or (authenticated and not 2 <= requests <= 20):
        raise ValueError
    if value["native_login_stages_verified"] is not True:
        raise ValueError
    if type(value["native_http_body_token_applied"]) is not bool or value["native_http_body_token_applied"] is not authenticated:
        raise ValueError
    if type(value["framework_generated_legacy_link"]) is not bool or not value["framework_generated_legacy_link"]:
        raise ValueError
    if type(value["framework_link_has_token"]) is not bool or (authenticated and not value["framework_link_has_token"]):
        raise ValueError
    if value["unauthenticated_link_token_validity_claimed"] is not False:
        raise ValueError
    if value["browserkit_target_get_count"] != 1 or type(value["browserkit_target_get_count"]) is not int:
        raise ValueError

    expected_attempted_route = "dashboard_admin_link" if is_other else "facebook_admin_link"
    expected_attempted_controller = "AdminDashboard" if is_other else "AdminPsfacebookModule"
    if (value["attempted_route"], value["attempted_controller"]) != (
        expected_attempted_route, expected_attempted_controller
    ):
        raise ValueError
    if case_name == "unauthenticated":
        expected_observation = ("not_observed", "not_observed", "not_observed", "not_observed")
    elif is_other:
        if (value["route_observation"], value["controller"], value["controller_action"]) != (
            "controller_event", "AdminDashboard", "not_applicable"
        ) or value["route"] not in {
            "admin_dashboard", "admin_dashboard_index", "admin_legacy_controller_route", "not_observed"
        }:
            raise ValueError
        expected_observation = None
    else:
        expected_observation = (
            "controller_event",
            "admin_legacy_controller_route",
            "AdminPsfacebookModuleController",
            "read",
        )
    if expected_observation is not None and (
        value["route_observation"], value["route"], value["controller"], value["controller_action"]
    ) != expected_observation:
        raise ValueError
    expected_full_gate = 1 if case_name in {"generic_facebook", "access_denied", "curl_transport"} else 0
    expected_read_gate = 1 if case_name in {"generic_facebook", "curl_transport"} else 0
    if type(value["authenticated_full_gate_passes"]) is not int or value["authenticated_full_gate_passes"] != expected_full_gate:
        raise ValueError
    if type(value["authenticated_read_gate_passes"]) is not int or value["authenticated_read_gate_passes"] != expected_read_gate:
        raise ValueError
    for key in ("known_facebook_request_controller_events", "mismatched_facebook_route_events", "disabled_mode_facebook_sentinels"):
        expected = 1 if key == "known_facebook_request_controller_events" and expected_full_gate else 0
        if type(value[key]) is not int or value[key] != expected:
            raise ValueError
    for key, should_inject in (
        ("other_route_exception_count", is_other),
        ("generic_facebook_exception_count", is_generic),
        ("native_legacy_access_denied_exception_count", is_denied),
    ):
        if type(value[key]) is not int or value[key] != int(should_inject):
            raise ValueError

    fixed = {
        "test_transport_target": "run_owned_ipv4_loopback_bind_only",
        "stream_server_listen_used": False,
        "facebook_vendor_initContent_called_by_fixture": False,
        "script_initiated_external_transport_requests": 0,
        "installed_http_client_calls": int(is_positive),
        "other_route_status_not_converted": is_other,
        "generic_facebook_runtime_status_not_converted": is_generic,
        "access_denied_status_preserved": is_denied,
        "native_acl_denial_preconditions_verified": is_denied,
        "read_permission_row_removed_before_request": is_denied,
        "read_permission_row_restored": is_denied,
        "native_access_denied_from_legacy_controller": is_denied,
        "korean_safe_title": is_positive,
        "korean_safe_message": is_positive,
        "fixed_error_fragment_excludes_token_and_transport_details": is_positive,
        "native_session_csrf_verified": is_positive,
        "native_session_csrf_probe_count": int(is_positive),
        "script_business_data_mutations": False,
        "login_session_or_auth_audit_writes_possible": authenticated,
        "kernel_bootstrap_database_network_side_effects_instrumented": False,
    }
    for key, expected in fixed.items():
        actual = value[key]
        if type(actual) is not type(expected) or actual != expected:
            raise ValueError
    if type(value["response_status"]) is not int or not 100 <= value["response_status"] <= 599:
        raise ValueError
    rejection = value["unauthenticated_auth_rejection"]
    if case_name == "unauthenticated":
        allowed_rejections = {
            "local_admin_login_redirect": {301, 302, 303, 307, 308},
            "local_admin_login_form": {200},
            "http_401": {401},
            "http_403": {403},
        }
        if rejection not in allowed_rejections or value["response_status"] not in allowed_rejections[rejection]:
            raise ValueError
        if type(value["unauthenticated_status_not_converted"]) is not bool or not value["unauthenticated_status_not_converted"]:
            raise ValueError
    elif rejection != "not_applicable" or value["unauthenticated_status_not_converted"] is not False:
        raise ValueError
    if is_positive and value["response_status"] != 503:
        raise ValueError
    if is_denied and value["response_status"] != 403:
        raise ValueError
    if case_name in {"unauthenticated", "other_route", "generic_facebook"} and value["response_status"] == 503:
        raise ValueError
    language = value["korean_document_language"]
    if is_positive:
        if type(language) is not str or re.fullmatch(r"ko(?:[-_]kr)?", language, re.I) is None:
            raise ValueError
        language = language.lower().replace("_", "-")
    elif language != "":
        raise ValueError
    snapshot_hash = value["positive_response_snapshot_sha256"]
    if is_positive:
        if type(snapshot_hash) is not str or not SHA256_RE.fullmatch(snapshot_hash):
            raise ValueError
    elif snapshot_hash is not None:
        raise ValueError

    return {
        "case": case_name,
        "response_status": value["response_status"],
        "native_login_transport": expected_login_transport,
        "native_login_form_posted": authenticated,
        "native_login_http_requests": requests,
        "native_http_body_token_applied": authenticated,
        "framework_generated_legacy_link": True,
        "framework_link_has_token": value["framework_link_has_token"],
        "unauthenticated_link_token_validity_claimed": False,
        "attempted_route": value["attempted_route"],
        "attempted_controller": value["attempted_controller"],
        "route_observation": value["route_observation"],
        "browserkit_target_get_count": 1,
        "route": value["route"],
        "controller": value["controller"],
        "controller_action": value["controller_action"],
        "authenticated_read_gate_passes": expected_read_gate,
        "authenticated_full_gate_passes": expected_full_gate,
        "native_acl_denial_preconditions_verified": is_denied,
        "read_permission_row_removed_before_request": is_denied,
        "read_permission_row_restored": is_denied,
        "native_access_denied_from_legacy_controller": is_denied,
        "native_legacy_access_denied_exception_count": int(is_denied),
        "vendor_initContent_called_by_fixture": False,
        "script_initiated_external_transport_requests": 0,
        "installed_http_client_calls": int(is_positive),
        "native_session_csrf_verified": is_positive,
        "korean_fallback_verified": is_positive,
        "unauthenticated_auth_rejection": rejection,
        "korean_document_language": language,
        "positive_response_snapshot_sha256": snapshot_hash,
    }


def _validate_payload(case_name: str, raw: bytes, exit_status: int) -> tuple[dict[str, Any], dict[str, Any]]:
    if exit_status != 0:
        raise RuntimeError("helper_nonzero")
    payload = _parse(raw)
    required = {"schema", "passed", "case", "module_inventory", "source_sha256", "facebook_case_facts", "test_dependencies"}
    if set(payload) != required or type(payload["schema"]) is not int or payload["schema"] != SCHEMA:
        raise ValueError
    if payload["passed"] is not True or payload["case"] != case_name:
        raise ValueError
    modules = _validate_modules(payload["module_inventory"])
    hashes = _validate_hashes(payload["source_sha256"])
    dependencies = _validate_dependencies(payload["test_dependencies"])
    facts = _validate_case_facts(case_name, payload["facebook_case_facts"])
    return ({"modules": modules, "source_sha256": hashes, "test_dependencies": dependencies}, facts)


def collect_cases(raw_cases: dict[str, bytes], statuses: dict[str, int]) -> dict[str, Any]:
    """Validate exact isolated case set and rebuild only public-safe evidence."""
    if set(raw_cases) != set(CASES) or set(statuses) != set(CASES):
        return {"schema": 1, "passed": False, "failure_code": "case_set_mismatch"}
    validated: dict[str, dict[str, Any]] = {}
    canonical: dict[str, Any] | None = None
    for name in CASES:
        try:
            pins, facts = _validate_payload(name, raw_cases[name], statuses[name])
        except RuntimeError:
            result = {"schema": 1, "passed": False, "failure_code": "helper_nonzero", "failed_case": name}
            # Reuse the identifier-only sanitizer, never exception text, raw
            # headers/cookies, or trace arguments. Fixed FB stage names extend
            # the shared set without permitting arbitrary strings.
            try:
                from safe_authenticated_outcome import _safe_failure
                payload = _parse(raw_cases[name])
                details = _safe_failure('helper_nonzero', statuses[name], payload, include_details=True)
                for key in (
                    'exception_class', 'cause_class', 'failure_source', 'failure_trace',
                    'auth_landing',
                ):
                    if key in details: result[key] = details[key]
                if 'twig_template' in details and 'twig_template_line' in details:
                    result['twig_template'] = details['twig_template']
                    result['twig_template_line'] = details['twig_template_line']
                stage = payload.get('failed_stage')
                allowed_stages = {
                    'ci_guard', 'admin_bootstrap_path', 'native_http_admin_login',
                    'native_login_get', 'native_login_get_redirects', 'native_login_post', 'native_login_post_redirects',
                    'bootstrap', 'test_only_dependency_bootstrap', 'admin_kernel_boot', 'read_only_module_inventory',
                    'native_facebook_api_and_subscriber_contract', 'native_admin_kernel_browser_fixture',
                    'framework_generated_facebook_admin_link', 'test_only_controller_listener',
                    'single_fresh_process_case_request', 'case_specific_semantic_assertions',
                }
                if isinstance(stage, str) and stage in allowed_stages: result['failed_stage'] = stage
                if name == 'generic_facebook' and payload.get('failed_assertion') == 'generic_facebook_exception_was_converted':
                    result['failed_assertion'] = 'generic_facebook_exception_was_converted'
                elif name == 'access_denied' and payload.get('failed_assertion') == 'native_access_denied_was_converted_or_not_preserved':
                    result['failed_assertion'] = 'native_access_denied_was_converted_or_not_preserved'
                generic_facts = payload.get('generic_facebook_case_facts')
                if name == 'generic_facebook' and isinstance(generic_facts, dict) and set(generic_facts) == {
                    'authenticated_full_gate_passes', 'authenticated_read_gate_passes',
                    'generic_exception_count', 'response_status', 'safe_error_title_present',
                }:
                    if (all(type(generic_facts[key]) is int and 0 <= generic_facts[key] <= 100
                            for key in ('authenticated_full_gate_passes', 'authenticated_read_gate_passes', 'generic_exception_count'))
                            and type(generic_facts['response_status']) is int
                            and 100 <= generic_facts['response_status'] <= 599
                            and type(generic_facts['safe_error_title_present']) is bool):
                        result['generic_facebook_case_facts'] = generic_facts
                access_facts = payload.get('access_denied_case_facts')
                if name == 'access_denied' and isinstance(access_facts, dict) and set(access_facts) == {
                    'authenticated_full_gate_passes', 'authenticated_read_gate_passes',
                    'known_facebook_request_controller_events', 'native_acl_denial_preconditions_verified',
                    'read_permission_row_removed_before_request', 'read_permission_row_restored',
                    'native_access_denied_exception_count', 'native_access_denied_from_legacy_controller',
                    'response_status', 'safe_error_title_present',
                }:
                    count_keys = (
                        'authenticated_full_gate_passes', 'authenticated_read_gate_passes',
                        'known_facebook_request_controller_events', 'native_access_denied_exception_count',
                    )
                    bool_keys = (
                        'native_acl_denial_preconditions_verified', 'read_permission_row_removed_before_request',
                        'read_permission_row_restored', 'native_access_denied_from_legacy_controller',
                        'safe_error_title_present',
                    )
                    if (all(type(access_facts[key]) is int and 0 <= access_facts[key] <= 100 for key in count_keys)
                            and all(type(access_facts[key]) is bool for key in bool_keys)
                            and type(access_facts['response_status']) is int
                            and 100 <= access_facts['response_status'] <= 599):
                        result['access_denied_case_facts'] = access_facts
            except (ValueError, TypeError, UnicodeError, RecursionError):
                pass
            return result
        except (ValueError, TypeError, UnicodeError, json.JSONDecodeError, RecursionError):
            return {"schema": 1, "passed": False, "failure_code": "case_contract_mismatch", "failed_case": name}
        if canonical is None:
            canonical = pins
        elif canonical != pins:
            return {"schema": 1, "passed": False, "failure_code": "case_source_pins_mismatch", "failed_case": name}
        validated[name] = facts
    assert canonical is not None
    total_login_requests = sum(validated[name]["native_login_http_requests"] for name in CASES)
    positive = validated["curl_transport"]
    return {
        "schema": 1,
        "passed": True,
        "execution": {
            "mode": "five_fresh_php_processes_each_with_one_kernelbrowser_get",
            "case_order": list(CASES),
            "fresh_php_processes": len(CASES),
            "browserkit_target_gets": sum(item["browserkit_target_get_count"] for item in validated.values()),
            "native_login_transport": "loopback_http_native_front_controller",
            "native_login_http_requests": total_login_requests,
            "external_transport_requests_in_fixture": 0,
            "business_data_mutations_in_fixture": False,
            "login_session_or_auth_audit_writes_possible": True,
            "kernel_bootstrap_database_network_side_effects_instrumented": False,
        },
        "modules": canonical["modules"],
        "source_sha256": canonical["source_sha256"],
        "test_dependencies": canonical["test_dependencies"],
        "cases": validated,
        "facebook_transport_fallback": {
            "positive_case": "curl_transport",
            "positive_failure_source": "installed_ps_facebook_HttpClient_cURL_exception",
            "native_authenticated_read_gate_verified": positive["authenticated_read_gate_passes"] == 1,
            "response_status": positive["response_status"],
            "korean_safe_response_verified": positive["korean_fallback_verified"],
            "native_session_csrf_verified": positive["native_session_csrf_verified"],
            "private_response_snapshot_sha256": positive["positive_response_snapshot_sha256"],
            "unauthenticated_status_not_converted": validated["unauthenticated"]["response_status"] != 503,
            "other_route_status_not_converted": validated["other_route"]["response_status"] != 503,
            "generic_facebook_status_not_converted": validated["generic_facebook"]["response_status"] != 503,
            "access_denied_status_preserved": validated["access_denied"]["response_status"] == 403
                and validated["access_denied"]["native_acl_denial_preconditions_verified"]
                and validated["access_denied"]["read_permission_row_removed_before_request"]
                and validated["access_denied"]["read_permission_row_restored"]
                and validated["access_denied"]["native_access_denied_from_legacy_controller"]
                and validated["access_denied"]["native_legacy_access_denied_exception_count"] == 1,
            "native_legacy_acl_denial_verified": validated["access_denied"]["native_access_denied_from_legacy_controller"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-input", action="append", default=[], metavar="NAME=PRIVATE_JSON")
    parser.add_argument("--case-status", action="append", default=[], metavar="NAME=EXIT_STATUS")
    parser.add_argument("--safe-output", required=True)
    args = parser.parse_args(argv)
    raw_cases: dict[str, bytes] = {}
    statuses: dict[str, int] = {}
    try:
        for item in args.case_input:
            name, separator, path = item.partition("=")
            if not separator or name not in CASES or name in raw_cases or not path:
                raise ValueError
            raw_cases[name] = _read_private(path)
        for item in args.case_status:
            name, separator, status_text = item.partition("=")
            if not separator or name not in CASES or name in statuses or not status_text.isdigit():
                raise ValueError
            status = int(status_text)
            if status > 255:
                raise ValueError
            statuses[name] = status
        result = collect_cases(raw_cases, statuses)
    except (OSError, ValueError, TypeError):
        result = {"schema": 1, "passed": False, "failure_code": "private_input_invalid"}

    destination = Path(args.safe_output)
    try:
        if destination.is_symlink() or destination.exists():
            raise OSError
        parent = destination.parent.resolve(strict=True)
        if destination.parent.is_symlink() or parent != destination.parent.resolve():
            raise OSError
        data = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        descriptor = os.open(destination, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            os.chmod(destination, 0o600)
    except OSError:
        print("safe output could not be created", file=sys.stderr)
        return 2
    return 0 if result.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
