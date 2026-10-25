"""Parse the bounded diagnostic header from the isolated admin locale QA."""

from __future__ import annotations

import re


SAFE_ADMIN_LOCALE_RESPONSE_PATTERN = (
    r"(?:redirect=opaque|unavailable:(?:[A-Za-z][A-Za-z0-9_]{0,63}|invalid_diagnostic|missing_header)|"
    r"stage=(?:request_scope|redirect|not_admin_route|not_html|empty_body|content_unchanged|html_tag_count|rewritten);"
    r"main_request=[01];module_active=[01];admin_route=[01];is_redirect=[01];http_status=[1-5][0-9]{2};"
    r"is_html=(?:not_checked|[01]);body_present=(?:not_checked|[01]);"
    r"html_tags=(?:not_checked|[0-9]{1,4});html_replacements=(?:not_checked|[01]);"
    r"lang_before=(?:not_checked|none|other|korean);lang_after=(?:not_checked|none|other|korean);rewritten=[01])"
)


def parse_admin_locale_response_diagnostic(value: str | None) -> str:
    if value is None or value == "missing":
        return "unavailable:missing_header"
    if re.fullmatch(SAFE_ADMIN_LOCALE_RESPONSE_PATTERN, value):
        return value
    return "unavailable:invalid_diagnostic"
