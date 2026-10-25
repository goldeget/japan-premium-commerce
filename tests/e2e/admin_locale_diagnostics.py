"""Parse the bounded diagnostic header from the isolated admin locale QA."""

from __future__ import annotations

import re


_PHP_RESPONSE_PATTERN = (
    r"stage=(?:request_scope|redirect|not_admin_route|not_html|empty_body|content_unchanged|html_tag_count|rewritten);"
    r"main_request=[01];module_active=[01];admin_route=[01];is_redirect=[01];http_status=[1-5][0-9]{2};"
    r"is_html=(?:not_checked|[01]);body_present=(?:not_checked|[01]);"
    r"html_tags=(?:not_checked|[0-9]{1,4});html_replacements=(?:not_checked|[01]);"
    r"lang_before=(?:not_checked|none|other|korean);lang_after=(?:not_checked|none|other|korean);rewritten=[01];"
    r"response_listener=1;probe_header=[01];probe_controller=[01];"
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
    r"browser_redirected=(?:unknown|true|false);browser_same_route=(?:unknown|true|false)"
)
SAFE_ADMIN_LOCALE_RESPONSE_PATTERN = (
    r"(?:"
    + _DIAGNOSTIC_RESULT_PATTERN
    + r")(?:;"
    + _BROWSER_RESPONSE_PATTERN
    + r")?"
)

_BROWSER_RESPONSE_TYPES = frozenset({"basic", "cors", "default", "error", "opaque", "opaqueredirect"})


def _safe_browser_response_suffix(value: str) -> str:
    parts = value.split(";")
    expected_names = (
        "browser_status",
        "browser_type",
        "browser_redirected",
        "browser_same_route",
    )
    values: dict[str, str] = {}
    if len(parts) == len(expected_names):
        for part, expected_name in zip(parts, expected_names):
            name, separator, content = part.partition("=")
            if separator and name == expected_name:
                values[name] = content

    status_value = values.get("browser_status", "")
    if status_value.isascii() and status_value.isdigit() and int(status_value) <= 599:
        browser_status = str(int(status_value))
    else:
        browser_status = "unknown"

    browser_type = values.get("browser_type", "")
    if browser_type not in _BROWSER_RESPONSE_TYPES:
        browser_type = "unknown"

    browser_redirected = values.get("browser_redirected", "")
    if browser_redirected not in {"true", "false"}:
        browser_redirected = "unknown"

    browser_same_route = values.get("browser_same_route", "")
    if browser_same_route not in {"true", "false"}:
        browser_same_route = "unknown"

    return ";".join(
        (
            f"browser_status={browser_status}",
            f"browser_type={browser_type}",
            f"browser_redirected={browser_redirected}",
            f"browser_same_route={browser_same_route}",
        )
    )


def parse_admin_locale_response_diagnostic(value: str | None) -> str:
    browser_suffix = ""
    diagnostic_header = value
    if isinstance(value, str):
        suffix_start = value.rfind(";browser_status=")
        if suffix_start >= 0:
            diagnostic_header = value[:suffix_start]
            browser_suffix = _safe_browser_response_suffix(value[suffix_start + 1 :])

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

    return result + (";" + browser_suffix if browser_suffix else "")
