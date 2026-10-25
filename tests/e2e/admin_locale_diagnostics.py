"""Parse the bounded diagnostic header from the isolated admin locale QA."""

from __future__ import annotations

import re


ORDER_LABEL_SOURCE_CATEGORIES = (
    "toolbar",
    "breadcrumb",
    "navigation",
    "kpi",
    "grid_header",
    "grid_controls",
    "grid_actions",
    "grid_body",
    "modal",
    "alert",
    "empty_state",
)


def format_orders_body_match_sources(categories: object, body_match: object) -> str:
    """Format only fixed UI categories; never return matched text, selectors, or values."""
    if (
        not isinstance(categories, dict)
        or set(categories) != set(ORDER_LABEL_SOURCE_CATEGORIES)
        or any(type(categories[name]) is not bool for name in ORDER_LABEL_SOURCE_CATEGORIES)
        or type(body_match) is not bool
    ):
        return "unknown"

    matches = [name for name in ORDER_LABEL_SOURCE_CATEGORIES if categories[name]]
    if matches:
        return ",".join(matches)
    return "other_visible_content" if body_match else "none"


_PHP_RESPONSE_PATTERN = (
    r"stage=(?:request_scope|redirect|not_admin_route|not_html|empty_body|content_unchanged|html_tag_count|rewritten);"
    r"main_request=[01];module_active=[01];admin_route=[01];is_redirect=[01];http_status=[1-5][0-9]{2};"
    r"is_html=(?:not_checked|[01]);body_present=(?:not_checked|[01]);"
    r"html_tags=(?:not_checked|[0-9]{1,4});html_replacements=(?:not_checked|[01]);"
    r"lang_before=(?:not_checked|none|other|korean);lang_after=(?:not_checked|none|other|korean);rewritten=[01];"
    r"response_listener=1;isolated_ci_gate=[01];probe_header=[01];probe_controller=[01];"
    r"server_ci=[01];server_actions=[01];server_run_id_valid=[01];server_run_attempt_valid=[01];"
    r"server_diagnostics=[01];server_project_match=[01];"
    r"env_ci=[01];env_actions=[01];env_run_id_valid=[01];env_run_attempt_valid=[01];"
    r"env_diagnostics=[01];env_project_match=[01]"
)
_DIAGNOSTIC_RESULT_PATTERN = (
    r"(?:redirect=opaque|unavailable:(?:[A-Za-z][A-Za-z0-9_]{0,63}|invalid_diagnostic|missing_header)|"
    + _PHP_RESPONSE_PATTERN
    + r")"
)
_BROWSER_RESPONSE_PATTERN = (
    r"browser_status=(?:unknown|[0-9]{1,3});"
    r"browser_type=(?:unknown|basic|cors|default|error|opaque|opaqueredirect);"
    r"browser_redirected=(?:unknown|true|false);browser_same_route=(?:unknown|true|false);"
    r"browser_url_exact=(?:unknown|true|false);document_lang=(?:korean|other|none|unavailable);"
    r"response_html_lang=(?:korean|other|none|unavailable);"
    r"document_sw_controlled=(?:unknown|true|false);navigation_worker_used=(?:unknown|true|false);"
    r"navigation_status=(?:unknown|[0-9]{1,3})"
)
_NAVIGATION_RESPONSE_PATTERN = (
    r"navigation_status=(?:unknown|[0-9]{1,3});navigation_route_match=(?:unknown|true|false);"
    r"navigation_url_exact=(?:unknown|true|false);"
    r"navigation_from_service_worker=(?:unknown|true|false);"
    r"navigation_from_disk_cache=(?:unknown|true|false);"
    r"navigation_from_prefetch_cache=(?:unknown|true|false);"
    r"document_lang=(?:korean|other|none|unavailable);"
    r"document_sw_controlled=(?:unknown|true|false);navigation_worker_used=(?:unknown|true|false)"
)
SAFE_ADMIN_LOCALE_RESPONSE_PATTERN = (
    r"(?:"
    + _DIAGNOSTIC_RESULT_PATTERN
    + r")(?:;(?:"
    + _BROWSER_RESPONSE_PATTERN
    + r"|"
    + _NAVIGATION_RESPONSE_PATTERN
    + r"))?"
)

_BROWSER_RESPONSE_TYPES = frozenset({"basic", "cors", "default", "error", "opaque", "opaqueredirect"})
_LANGUAGE_CATEGORIES = frozenset({"korean", "other", "none", "unavailable"})
_BOOLEAN_METADATA_FIELDS = frozenset(
    {
        "browser_redirected",
        "browser_same_route",
        "browser_url_exact",
        "navigation_route_match",
        "navigation_url_exact",
        "navigation_from_service_worker",
        "navigation_from_disk_cache",
        "navigation_from_prefetch_cache",
        "document_sw_controlled",
        "navigation_worker_used",
    }
)


def _safe_response_metadata_suffix(value: str) -> str:
    parts = value.split(";")
    first_name = parts[0].partition("=")[0] if parts else ""
    if first_name == "navigation_status":
        expected_names = (
            "navigation_status",
            "navigation_route_match",
            "navigation_url_exact",
            "navigation_from_service_worker",
            "navigation_from_disk_cache",
            "navigation_from_prefetch_cache",
            "document_lang",
            "document_sw_controlled",
            "navigation_worker_used",
        )
    elif first_name == "browser_status":
        expected_names = (
            "browser_status",
            "browser_type",
            "browser_redirected",
            "browser_same_route",
            "browser_url_exact",
            "document_lang",
            "response_html_lang",
            "document_sw_controlled",
            "navigation_worker_used",
            "navigation_status",
        )
    else:
        return ""

    values: dict[str, str] = {}
    if len(parts) == len(expected_names):
        for part, expected_name in zip(parts, expected_names):
            name, separator, content = part.partition("=")
            if separator and name == expected_name:
                values[name] = content

    safe_values: list[str] = []
    for name in expected_names:
        raw_value = values.get(name, "")
        if name in {"browser_status", "navigation_status"}:
            if raw_value.isascii() and raw_value.isdigit() and int(raw_value) <= 599:
                safe_value = str(int(raw_value))
            else:
                safe_value = "unknown"
        elif name == "browser_type":
            safe_value = raw_value if raw_value in _BROWSER_RESPONSE_TYPES else "unknown"
        elif name in _BOOLEAN_METADATA_FIELDS:
            safe_value = raw_value if raw_value in {"true", "false"} else "unknown"
        elif name in {"document_lang", "response_html_lang"}:
            safe_value = raw_value if raw_value in _LANGUAGE_CATEGORIES else "unavailable"
        else:
            safe_value = "unknown"
        safe_values.append(f"{name}={safe_value}")

    return ";".join(safe_values)


def parse_admin_locale_response_diagnostic(value: str | None) -> str:
    metadata_suffix = ""
    diagnostic_header = value
    if isinstance(value, str):
        browser_suffix_start = value.rfind(";browser_status=")
        suffix_start = browser_suffix_start if browser_suffix_start >= 0 else value.rfind(";navigation_status=")
        if suffix_start >= 0:
            diagnostic_header = value[:suffix_start]
            metadata_suffix = _safe_response_metadata_suffix(value[suffix_start + 1 :])

    if diagnostic_header is None or diagnostic_header == "missing":
        result = "unavailable:missing_header"
    elif isinstance(diagnostic_header, str) and (
        diagnostic_header == "redirect=opaque"
        or re.fullmatch(r"unavailable:[A-Za-z][A-Za-z0-9_]{0,63}", diagnostic_header)
        or re.fullmatch(_PHP_RESPONSE_PATTERN, diagnostic_header)
    ):
        result = diagnostic_header
    else:
        result = "unavailable:invalid_diagnostic"

    return result + (";" + metadata_suffix if metadata_suffix else "")
