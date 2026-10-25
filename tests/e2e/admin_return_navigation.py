from __future__ import annotations

from urllib.parse import parse_qs, urljoin, urlsplit


RETURN_LIST_PATH = "/sell/customer-service/merchandise-return"
SAFE_COMPROMISED_PAGE_CLASSIFICATIONS = (
    "none",
    "prestashop_security_compromised",
    "security_path_without_marker",
    "security_marker_off_path",
)


def _origin(parts):
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return None
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        return None
    return parts.scheme.lower(), parts.hostname.lower(), port


def _admin_root_parts(admin_root: str):
    try:
        parts = urlsplit(admin_root)
    except ValueError:
        return None
    if parts.username is not None or parts.password is not None or parts.query or parts.fragment:
        return None
    origin = _origin(parts)
    admin_path = parts.path.rstrip("/")
    if origin is None or not admin_path.startswith("/") or admin_path == "/":
        return None
    return parts, origin, admin_path


def compromised_page_facts(candidate_url: str, admin_root: str, page_marker_present: bool) -> dict[str, object]:
    root = _admin_root_parts(admin_root)
    try:
        candidate = urlsplit(candidate_url)
    except ValueError:
        candidate = None

    static_path_matches = False
    if root is not None and candidate is not None:
        _, expected_origin, admin_path = root
        candidate_path = candidate.path
        expected_compromised_path = admin_path + "/security/compromised"
        static_path_matches = (
            _origin(candidate) == expected_origin
            and candidate.username is None
            and candidate.password is None
            and (candidate_path == admin_path or candidate_path.startswith(admin_path + "/"))
            and candidate_path in {expected_compromised_path, expected_compromised_path + "/"}
        )

    marker_present = page_marker_present is True
    if static_path_matches and marker_present:
        classification = "prestashop_security_compromised"
    elif static_path_matches:
        classification = "security_path_without_marker"
    elif marker_present:
        classification = "security_marker_off_path"
    else:
        classification = "none"
    return {
        "static_path_matches": static_path_matches,
        "page_marker_present": marker_present,
        "classification": classification,
    }


def security_page_failure_reason(classification: str) -> str:
    if classification == "none":
        return "clear"
    if classification == "prestashop_security_compromised":
        return "native_compromised_page"
    return "security_signal_mismatch"


def token_comparison_classification(
    tokenless_classification: str,
    tokenized_classification: str,
    tokenless_page_class: str,
    tokenized_page_class: str,
) -> str:
    if tokenized_classification == "prestashop_security_compromised" and tokenized_page_class == "prestashop_security_compromised":
        tokenized_result = "compromised"
    elif tokenized_classification == "none" and tokenized_page_class == "admin_return_list":
        tokenized_result = "clear"
    else:
        return "inconclusive"

    if tokenless_classification == "prestashop_security_compromised" and tokenless_page_class == "prestashop_security_compromised":
        tokenless_result = "compromised"
    elif tokenless_classification == "none" and tokenless_page_class == "admin_return_list":
        tokenless_result = "clear"
    elif tokenless_classification == "none" and tokenless_page_class == "admin_login":
        tokenless_result = "login"
    elif tokenless_classification == "none" and tokenless_page_class in {
        "admin_return_edit",
        "other_admin",
    }:
        tokenless_result = "other_admin"
    else:
        return "inconclusive"

    return f"tokenless_{tokenless_result}_tokenized_{tokenized_result}"


def return_list_path_matches(candidate_path: str, admin_root: str) -> bool:
    root = _admin_root_parts(admin_root)
    if root is None or not isinstance(candidate_path, str):
        return False
    _, _, admin_root_path = root
    expected_path = admin_root_path + RETURN_LIST_PATH
    return candidate_path in {expected_path, expected_path + "/"}


def return_menu_link_facts(href: str, admin_root: str) -> dict[str, bool]:
    root = _admin_root_parts(admin_root)
    candidate = None
    if root is not None and isinstance(href, str) and href:
        try:
            candidate = urlsplit(urljoin(admin_root.rstrip("/") + "/", href))
        except ValueError:
            candidate = None

    same_origin = False
    admin_path = False
    return_path = False
    session_token_present = False
    no_userinfo_or_fragment = False
    if root is not None and candidate is not None:
        _, expected_origin, admin_root_path = root
        same_origin = _origin(candidate) == expected_origin
        candidate_path = candidate.path
        admin_path = candidate_path == admin_root_path or candidate_path.startswith(admin_root_path + "/")
        return_path = return_list_path_matches(candidate_path, admin_root)
        no_userinfo_or_fragment = (
            candidate.username is None and candidate.password is None and not candidate.fragment
        )
        query = parse_qs(candidate.query, keep_blank_values=True)
        tokens = [*query.get("token", []), *query.get("_token", [])]
        session_token_present = len(tokens) == 1 and bool(tokens[0].strip())

    valid = (
        same_origin
        and admin_path
        and return_path
        and session_token_present
        and no_userinfo_or_fragment
    )
    return {
        "same_origin": same_origin,
        "admin_path": admin_path,
        "return_path": return_path,
        "session_token_present": session_token_present,
        "valid": valid,
    }
