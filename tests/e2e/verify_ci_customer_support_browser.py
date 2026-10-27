#!/usr/bin/env python3
"""Exercise PrestaShop's native order-associated customer-thread lifecycle in isolated CI."""

# Native controls are pinned to the PrestaShop 9.2.0 admin_customer_threads
# routes, CustomerThread view/reply/forward templates, and contactform module.
# See tests/e2e/test_ci_customer_support_browser_contract.py for the checked
# route, form, thread identity, and attachment boundaries.

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import secrets
import struct
import sys
import tempfile
import time
import zlib
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
try:
    from native_contact_route import contact_route_class, probe_contact_route, read_contact_route_fixture
except ModuleNotFoundError:
    from tests.e2e.native_contact_route import contact_route_class, probe_contact_route, read_contact_route_fixture

try:
    from selenium import webdriver
    from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.select import Select
    from selenium.webdriver.support.ui import WebDriverWait
except ModuleNotFoundError:  # Pure contract helpers remain importable without local browser extras.
    webdriver = None
    TimeoutException = TimeoutError
    StaleElementReferenceException = RuntimeError
    Options = None
    By = None
    EC = None
    Select = None
    WebDriverWait = None


EXPECTED_SHOP_PORT = 18080
EXPECTED_MAILPIT_PORT = 8025
THREAD_TOKEN_PATTERN = re.compile(r"#ct([1-9][0-9]{0,9})\s+#tc([A-Za-z0-9]{12})")
SAFE_STAGES = {
    "fixture", "customer_login", "contact_form", "submit_inquiry", "mailpit_confirmation",
    "foreign_customer_denial", "admin_login", "admin_thread_lookup", "attachment_readback",
    "private_forward_note", "close_thread", "reopen_thread", "admin_public_reply",
    "mailpit_public_reply", "customer_followup", "thread_fresh_readback", "assignment_lookup",
    "assignment_create", "assignment_reassign", "assignment_history_readback",
    "limited_staff_denial", "assignment_limited_denial", "rejected_attachment", "image_attachment_readback", "orderless_inquiry", "foreign_valid_thread",
    "foreign_orderless_post", "orderless_readback", "complete",
}
SAFE_RESULT_KEYS = {
    "status", "stage", "exception_type", "customer_submitted", "order_association_verified",
    "attachment_admin_readback", "private_note_admin_only", "status_close_reopen", "admin_public_reply",
    "customer_followup_same_thread", "foreign_customer_denied", "limited_employee_denied",
    "mailpit_provider", "paid", "payment_provider_called", "assignment_created",
    "assignment_reassigned", "assignment_actor_history", "assignment_limited_employee_denied",
    "image_attachment_admin_readback", "image_attachment_foreign_denied", "disallowed_attachment_rejected",
    "foreign_valid_thread_denied", "foreign_orderless_post_denied", "orderless_thread_unchanged",
    "contact_document_status", "contact_same_origin", "contact_native_route",
    "contact_form_count", "contact_form_visible", "support_denial_status",
    "support_denial_form_count", "support_denial_redirected", "support_denial_same_origin",
    "customer_service_route_candidate_count", "customer_service_route_safe_count",
    "customer_service_route_modern_count", "customer_service_route_legacy_count",
    "customer_service_route_invalid_count",
    "admin_thread_message_marker_present", "admin_thread_order_association_present",
    "browser_substage",
}
RESULT_BOOLEAN_KEYS = SAFE_RESULT_KEYS - {
    "status", "stage", "exception_type", "mailpit_provider",
    "contact_document_status", "contact_form_count", "support_denial_status",
    "support_denial_form_count", "customer_service_route_candidate_count",
    "customer_service_route_safe_count", "customer_service_route_modern_count",
    "customer_service_route_legacy_count", "customer_service_route_invalid_count", "browser_substage",
}
SAFE_EXCEPTION_TYPES = {
    "AssertionError", "TimeoutException", "ValueError", "RuntimeError", "URLError", "OSError",
    "StaleElementReferenceException", "ElementClickInterceptedException", "NoSuchElementException", "OtherError",
}
SAFE_BROWSER_SUBSTAGES = {
    "not_applicable", "contact_form_navigation", "order_select_lookup", "order_option_scan",
    "admin_login_completed", "admin_service_route_discovery",
    "order_owner_assertion", "order_select_scroll", "order_select_hit_test",
    "order_select_native_option", "order_select_readback",
    "foreign_invalid_token_probe", "foreign_owned_thread_probe", "foreign_orderless_thread_probe",
    "foreign_orderless_post_probe",
    "admin_route_candidate_navigation", "admin_route_exact_thread_readback",
    "admin_thread_detail_navigation", "admin_thread_detail_readback",
    "admin_thread_message_readback", "admin_thread_order_association_readback",
    "status_action_lookup", "status_action_click", "status_action_readback",
    "contact_field_lookup", "contact_id_readback", "attachment_control_lookup", "attachment_send_keys",
    "accepted_attachment_fixture_validation", "accepted_attachment_file_readback", "message_field_lookup",
    "message_send_keys", "submit_control_lookup", "submit_control_scroll", "submit_control_hit_test",
    "submit_button_click", "response_alert_wait", "rejection_assertion", "rejection_verified",
}


@dataclass(frozen=True)
class Context:
    run_id: str
    attempt: str
    project: str
    shop: str
    contact_url: str
    contact_route_metadata: dict[str, Any]
    admin: str
    mailpit: str
    artifact_dir: Path
    admin_email: str
    admin_password: str
    view_only_email: str
    customer_password: str
    buyer: dict[str, Any]
    foreign: dict[str, Any]


class MessageLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if isinstance(href, str) and href:
            self.hrefs.append(href)


def validate_loopback_url(value: str, port: int, label: str) -> str:
    try:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        actual_port = parsed.port
        loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except (ValueError, TypeError):
        raise ValueError(f"{label} must be a valid isolated loopback endpoint") from None
    if (
        parsed.scheme != "http" or not loopback or actual_port != port
        or parsed.username is not None or parsed.password is not None
        or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
    ):
        raise ValueError(f"{label} must use the isolated loopback port {port}")
    return f"http://{host}:{port}"


def validate_admin_url(value: str, shop: str) -> str:
    try:
        parsed = urlparse(value)
        expected = urlparse(shop)
    except ValueError:
        raise ValueError("ADMIN_LOGIN_URL is invalid for the isolated Back Office") from None
    if (
        (parsed.scheme, parsed.hostname, parsed.port) != (expected.scheme, expected.hostname, expected.port)
        or parsed.path.rstrip("/") != "/admin-kuranea"
        or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment
    ):
        raise ValueError("ADMIN_LOGIN_URL must use the isolated shop's exact Back Office path")
    return value.rstrip("/")


def load_order(artifact_dir: Path, viewport: str, run_id: str, attempt: str) -> dict[str, Any]:
    browser_path = artifact_dir / f"ci-checkout-{viewport}.json"
    verified_path = artifact_dir / f"ci-checkout-{viewport}-verified.json"
    try:
        browser_order = json.loads(browser_path.read_text(encoding="utf-8"))
        verified_order = json.loads(verified_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        raise ValueError(f"the isolated {viewport} order fixture is missing or invalid") from None
    expected_email = f"qa-ordenowa-checkout-{run_id}-{attempt}-{viewport}@example.invalid"
    order_id = browser_order.get("order_id")
    reference = browser_order.get("reference")
    if (
        browser_order.get("viewport") != viewport
        or type(order_id) is not int or order_id < 1
        or browser_order.get("email") != expected_email
        or not isinstance(reference, str) or re.fullmatch(r"[A-Z0-9]{8,16}", reference) is None
        or verified_order.get("order_id") != order_id
        or verified_order.get("reference") != reference
        or verified_order.get("email") != expected_email
        or verified_order.get("payment_module") != "ps_checkpayment"
        or verified_order.get("total_paid_real") != 0
    ):
        raise ValueError(f"the isolated {viewport} order is not the matching run-scoped unpaid offline order")
    return {"order_id": order_id, "reference": reference, "email": expected_email}


def load_context(environ: dict[str, str] | None = None) -> Context:
    values = os.environ if environ is None else environ
    run_id = values.get("GITHUB_RUN_ID", "")
    attempt = values.get("GITHUB_RUN_ATTEMPT", "")
    project = f"kuranea-ci-{run_id}-{attempt}"
    if (
        values.get("CI") != "true" or values.get("GITHUB_ACTIONS") != "true"
        or values.get("KURANEA_ISOLATED_CI") != "1"
        or re.fullmatch(r"[0-9]+", run_id) is None
        or re.fullmatch(r"[0-9]+", attempt) is None
        or values.get("CI_COMPOSE_PROJECT_NAME") != project
        or values.get("KURANEA_CI_PROJECT_NAME") != project
    ):
        raise ValueError("customer support browser QA requires its exact disposable Actions project")
    shop = validate_loopback_url(values.get("SHOP_BASE_URL", ""), EXPECTED_SHOP_PORT, "SHOP_BASE_URL")
    route_fixture_path = values.get("CONTACT_ROUTE_FIXTURE", "")
    if not route_fixture_path:
        raise ValueError("customer support browser QA requires the read-only native contact route fixture")
    route_fixture = read_contact_route_fixture(route_fixture_path, shop)
    mailpit = validate_loopback_url(values.get("MAILPIT_API_URL", ""), EXPECTED_MAILPIT_PORT, "MAILPIT_API_URL")
    admin = validate_admin_url(values.get("ADMIN_LOGIN_URL", ""), shop)
    artifact_text = values.get("QA_ARTIFACT_DIR", "")
    runner_temp = values.get("RUNNER_TEMP", "")
    if not artifact_text or not runner_temp:
        raise ValueError("customer support artifacts require an explicit runner temporary directory")
    artifact_dir = Path(artifact_text).resolve()
    temp_dir = Path(runner_temp).resolve()
    try:
        artifact_dir.relative_to(temp_dir)
    except ValueError:
        raise ValueError("customer support artifacts must remain inside RUNNER_TEMP") from None
    if artifact_dir == temp_dir:
        raise ValueError("customer support artifacts require a run-specific child directory")

    admin_email = values.get("ADMIN_MAIL", "").strip().lower()
    password = values.get("ADMIN_PASSWD", "")
    view_email = values.get("VIEW_ONLY_EMAIL", "").strip().lower()
    expected_view = rf"ordenowa-security-view-{re.escape(run_id)}-{re.escape(attempt)}-[a-f0-9]+@example\.invalid"
    if admin_email != "ci-ordenowa@example.invalid" or not password or re.fullmatch(expected_view, view_email) is None:
        raise ValueError("customer support browser QA requires the run-scoped admin and limited-employee fixtures")

    artifact_dir.mkdir(parents=True, exist_ok=True)
    buyer = load_order(artifact_dir, "desktop", run_id, attempt)
    foreign = load_order(artifact_dir, "mobile", run_id, attempt)
    if buyer["order_id"] == foreign["order_id"] or buyer["email"] == foreign["email"]:
        raise ValueError("support ownership fixtures must identify two distinct native customers and orders")
    return Context(
        run_id=run_id, attempt=attempt, project=project, shop=shop,
        contact_url=route_fixture["urls_by_iso"]["ja"],
        contact_route_metadata={
            "contact_meta_present": route_fixture["contact_meta_present"],
            "rewriting_enabled": route_fixture["rewriting_enabled"],
            "canonical_redirect_mode": route_fixture["canonical_redirect_mode"],
            "contactform_enabled": route_fixture["contactform_enabled"],
            "localized_rewrites": route_fixture["localized_rewrites"],
            "localized_rewrite_by_iso": route_fixture["localized_rewrite_by_iso"],
        },
        admin=admin,
        mailpit=mailpit, artifact_dir=artifact_dir, admin_email=admin_email,
        admin_password=password, view_only_email=view_email,
        customer_password=f"ORDENOWA-CI-{run_id}-{attempt}-Aa1!", buyer=buyer, foreign=foreign,
    )


def same_origin(first: str, second: str) -> bool:
    a = urlparse(first)
    b = urlparse(urljoin(first.rstrip("/") + "/", second))
    return (a.scheme, a.hostname, a.port) == (b.scheme, b.hostname, b.port)


def contact_page_evidence(
    driver, shop_url: str, *, locale: str, localized_rewrite: str | None
) -> dict[str, Any]:
    """Return response status and bounded route/form facts; never persist the URL or page text."""
    response_status = driver.execute_script("""
      const entries = performance.getEntriesByType('navigation');
      const entry = entries.length ? entries[0] : null;
      return entry && Number.isInteger(entry.responseStatus) ? entry.responseStatus : null;
    """)
    if type(response_status) is not int or not 100 <= response_status <= 599:
        response_status = None
    origin_matches = same_origin(driver.current_url, shop_url)
    native_route = origin_matches and contact_route_class(
        driver.current_url,
        shop_url,
        locale=locale,
        localized_rewrite=localized_rewrite,
    ) == "contact"
    forms = driver.find_elements(By.CSS_SELECTOR, '.contact-form form')
    return {
        'contact_document_status': response_status,
        'contact_same_origin': origin_matches,
        'contact_native_route': native_route,
        'contact_form_count': len(forms),
        'contact_form_visible': any(form.is_displayed() for form in forms),
    }


def safe_admin_path(value: str, admin_url: str) -> bool:
    candidate = urlparse(urljoin(admin_url.rstrip("/") + "/", value))
    expected = urlparse(admin_url)
    root = expected.path.rstrip("/")
    return (
        (candidate.scheme, candidate.hostname, candidate.port) == (expected.scheme, expected.hostname, expected.port)
        and (candidate.path == root or candidate.path.startswith(root + "/"))
        and candidate.username is None and candidate.password is None and not candidate.fragment
    )


def customer_threads_navigation_identity(value: str, admin_url: str) -> tuple[str, str] | None:
    """Identify one exact native route while treating query order and path aliases as equivalent."""
    if not safe_admin_path(value, admin_url):
        return None
    expected = urlparse(admin_url)
    root = expected.path.rstrip("/")
    candidate = urlparse(urljoin(admin_url.rstrip("/") + "/", value))
    try:
        pairs = parse_qsl(candidate.query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None
    if not pairs or any(not key for key, _value in pairs):
        return None
    query: dict[str, str] = {}
    for key, query_value in pairs:
        if key in query:
            return None
        query[key] = query_value

    token = query.get("token", "")
    if not token.strip():
        return None
    path = candidate.path.rstrip("/")
    modern_paths = {
        root + "/sell/customer-service/customer-threads",
        root + "/index.php/sell/customer-service/customer-threads",
    }
    if path in modern_paths and set(query) == {"token"}:
        return "modern", token

    legacy_paths = {root, root + "/index.php"}
    if (
        path in legacy_paths
        and set(query) == {"controller", "token"}
        and query.get("controller") == "AdminCustomerThreads"
    ):
        return "legacy", token
    return None


def modern_thread_route_id(path: str, admin_url: str, endpoint: str) -> int | None:
    admin_root = urlparse(admin_url).path.rstrip("/")
    prefixes = (admin_root, admin_root + "/index.php")
    for prefix in prefixes:
        match = re.fullmatch(
            re.escape(prefix)
            + rf"/sell/customer-service/customer-threads/([1-9][0-9]{{0,9}})/{re.escape(endpoint)}/?",
            path,
        )
        if match is not None:
            return int(match.group(1))
    return None


def thread_route_identity(value: str, admin_url: str) -> tuple[str, int] | None:
    if not safe_admin_path(value, admin_url):
        return None
    parsed = urlparse(urljoin(admin_url.rstrip("/") + "/", value))
    query = parse_qs(parsed.query, keep_blank_values=True)
    if query.get("controller") == ["AdminCustomerThreads"]:
        candidates = query.get("id_customer_thread", [])
        if query.get("viewcustomer_thread") in (["1"], [""]) and len(candidates) == 1 and candidates[0].isdigit():
            thread_id = int(candidates[0])
            return ("legacy_thread_view", thread_id) if thread_id > 0 else None
    thread_id = modern_thread_route_id(parsed.path, admin_url, "view")
    if thread_id is not None:
        return "modern_thread_view", thread_id
    return None


def thread_action_route_identity(value: str, admin_url: str) -> tuple[str, int] | None:
    """Identify an exact native thread target for view and forward form actions."""
    identity = thread_route_identity(value, admin_url)
    if identity is not None:
        return identity
    if not safe_admin_path(value, admin_url):
        return None
    parsed = urlparse(urljoin(admin_url.rstrip("/") + "/", value))
    thread_id = modern_thread_route_id(parsed.path, admin_url, "forward")
    return ("modern_thread_view", thread_id) if thread_id is not None else None


def customer_thread_forward_target(route_kind: str) -> str:
    if route_kind == "modern_thread_view":
        return "#forwardThreadModal"
    if route_kind == "legacy_thread_view":
        return "#myModal"
    raise ValueError("the customer thread route kind is not a supported native view")


def customer_thread_forward_visible_modal(route_kind: str) -> str:
    if route_kind == "modern_thread_view":
        return "#forwardThreadModal.show"
    if route_kind == "legacy_thread_view":
        # The pinned PrestaShop 9.2 Back Office uses Bootstrap 3, which opens
        # this legacy modal with .in. The modern Twig modal uses Bootstrap 5 .show.
        return "#myModal.in"
    raise ValueError("the customer thread route kind is not a supported native view")


def customer_thread_forward_forms(modal, route_kind: str):
    if route_kind == "modern_thread_view":
        return modal.find_elements(By.CSS_SELECTOR, "form")
    if route_kind == "legacy_thread_view":
        return modal.find_elements(By.XPATH, "./ancestor::form[1]")
    raise ValueError("the customer thread route kind is not a supported native view")


def parse_thread_email_subject(subject: object) -> tuple[int, str] | None:
    if not isinstance(subject, str):
        return None
    match = THREAD_TOKEN_PATTERN.search(subject)
    return (int(match.group(1)), match.group(2)) if match else None


def validate_customer_thread_url(
    candidate: str, shop_url: str, expected_thread_id: int, *,
    locale: str | None = None, localized_rewrite: str | None = None,
) -> bool:
    try:
        destination = urljoin(shop_url.rstrip("/") + "/", candidate)
        parsed = urlparse(destination)
        expected = urlparse(shop_url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        route_query = [
            (key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key not in {"id_customer_thread", "token"}
        ]
        route = urlunparse(parsed._replace(query=urlencode(route_query)))
        native_contact_route = contact_route_class(
            route, shop_url, locale=locale, localized_rewrite=localized_rewrite
        ) == "contact"
        same_shop = (parsed.scheme, parsed.hostname, parsed.port) == (expected.scheme, expected.hostname, expected.port)
    except (TypeError, ValueError):
        return False
    return (
        same_shop and native_contact_route
        and query.get("id_customer_thread") == [str(expected_thread_id)]
        and len(query.get("token", [])) == 1
        and re.fullmatch(r"[A-Za-z0-9]{12}", query["token"][0]) is not None
        and parsed.username is None and parsed.password is None and not parsed.fragment
    )


def native_customer_thread_url(
    contact_url: str, shop_url: str, thread_id: int, token: str, *,
    locale: str, localized_rewrite: str | None,
) -> str:
    """Append native thread identity to the exact contact route read from the shop."""
    try:
        parsed = urlparse(urljoin(shop_url.rstrip("/") + "/", contact_url))
        expected = urlparse(shop_url)
        query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
        keys = [key for key, _value in query]
        base_route = urlunparse(parsed._replace(query=urlencode(query)))
        same_shop = (parsed.scheme, parsed.hostname, parsed.port) == (expected.scheme, expected.hostname, expected.port)
    except (TypeError, ValueError):
        raise ValueError("native customer thread URL did not match the contact route fixture") from None
    if (
        not same_shop
        or parsed.username is not None or parsed.password is not None or parsed.fragment
        or len(keys) != len(set(keys))
        or set(keys) & {"id_customer_thread", "token"}
        or contact_route_class(
            base_route, shop_url, locale=locale, localized_rewrite=localized_rewrite
        ) != "contact"
        or type(thread_id) is not int or thread_id < 1
        or re.fullmatch(r"[A-Za-z0-9]{12}", token) is None
    ):
        raise ValueError("native customer thread URL did not match the contact route fixture")
    candidate = urlunparse(parsed._replace(query=urlencode([
        *query, ("id_customer_thread", str(thread_id)), ("token", token),
    ])))
    if not validate_customer_thread_url(
        candidate, shop_url, thread_id, locale=locale, localized_rewrite=localized_rewrite
    ):
        raise ValueError("native customer thread URL did not retain the exact contact route")
    return candidate


def recipients(message: dict[str, Any]) -> set[str]:
    values = message.get("To", [])
    if isinstance(values, (str, dict)):
        values = [values]
    found: set[str] = set()
    if isinstance(values, list):
        for item in values:
            address = item.get("Address", "") if isinstance(item, dict) else item
            if isinstance(address, str):
                found.add(address.strip().lower())
    return found


def mailpit_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Mailpit returned an unexpected response")
    return payload


def mail_ids(mailpit_url: str) -> set[str]:
    result = mailpit_json(f"{mailpit_url}/api/v1/messages?{urlencode({'start': 0, 'limit': 100})}")
    messages = result.get("messages", [])
    if not isinstance(messages, list):
        return set()
    return {str(row.get("ID") or row.get("Id")) for row in messages if isinstance(row, dict) and (row.get("ID") or row.get("Id"))}


def wait_for_thread_email(
    mailpit_url: str, expected_recipient: str, previous_ids: set[str], timeout_seconds: int = 45
) -> tuple[int, str, dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            listing = mailpit_json(f"{mailpit_url}/api/v1/messages?{urlencode({'start': 0, 'limit': 100})}")
            for summary in listing.get("messages", []):
                if not isinstance(summary, dict):
                    continue
                message_id = summary.get("ID") or summary.get("Id")
                if not isinstance(message_id, str) or message_id in previous_ids or expected_recipient.lower() not in recipients(summary):
                    continue
                detail = mailpit_json(f"{mailpit_url}/api/v1/message/{message_id}")
                identity = parse_thread_email_subject(detail.get("Subject"))
                if identity:
                    return identity[0], identity[1], detail
        except (OSError, URLError, ValueError, json.JSONDecodeError):
            pass
        time.sleep(0.4)
    raise TimeoutError("the isolated customer-thread email did not arrive in Mailpit")


def thread_link_from_email(message: dict[str, Any], shop_url: str, expected_thread_id: int) -> str:
    parser = MessageLinks()
    html_body = message.get("HTML")
    if isinstance(html_body, str):
        parser.feed(html_body)
    candidates = list(parser.hrefs)
    text_body = message.get("Text")
    if isinstance(text_body, str):
        candidates.extend(re.findall(r"https?://[^\s<>\"']+", text_body))
    for candidate in candidates:
        candidate = candidate.strip().rstrip(".,);]")
        if validate_customer_thread_url(candidate, shop_url, expected_thread_id):
            return urljoin(shop_url.rstrip("/") + "/", candidate)
    raise ValueError("the native customer reply email did not contain a valid same-shop thread link")


def new_driver(width: int = 1440, height: int = 960, download_dir: Path | None = None):
    if webdriver is None or Options is None:
        raise RuntimeError("Selenium browser dependencies are unavailable")
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--lang=ja-JP")
    if download_dir is not None:
        download_dir.mkdir(parents=True, exist_ok=True)
        options.add_experimental_option("prefs", {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        })
    return webdriver.Chrome(options=options)


def visible(driver, selector: str, timeout: int = 30):
    return WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))


def mark_browser_substage(result: dict[str, Any] | None, substage: str) -> None:
    if not isinstance(substage, str) or substage not in SAFE_BROWSER_SUBSTAGES:
        raise ValueError("customer support browser substage is not allowlisted")
    if result is not None:
        result["browser_substage"] = substage


def center_native_control(
    driver, element, control_name: str, *, diagnostic_result: dict[str, Any] | None = None,
    scroll_substage: str, hit_test_substage: str,
) -> None:
    """Scroll one exact native control clear of sticky viewport overlays."""
    mark_browser_substage(diagnostic_result, scroll_substage)
    driver.execute_script(
        "arguments[0].scrollIntoView({behavior: 'instant', block: 'center', inline: 'nearest'});",
        element,
    )
    mark_browser_substage(diagnostic_result, hit_test_substage)
    unobscured = driver.execute_script("""
      const element = arguments[0];
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const target = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
      return target === element || element.contains(target);
    """, element)
    if unobscured is not True:
        raise AssertionError(f"native support {control_name} control is obstructed")


def select_contact_order(
    driver, select_element, value: str, *, diagnostic_result: dict[str, Any] | None = None
) -> None:
    """Select the exact native option and verify the form control's value."""
    mark_browser_substage(diagnostic_result, "order_option_scan")
    options = select_element.find_elements(By.TAG_NAME, "option")
    matching_indices = [
        index for index, option in enumerate(options)
        if option.get_attribute("value") == value
    ]
    if len(matching_indices) != 1 or not options[matching_indices[0]].is_enabled():
        raise AssertionError("native contact form did not expose one selectable order option")
    center_native_control(
        driver,
        select_element,
        "order selection",
        diagnostic_result=diagnostic_result,
        scroll_substage="order_select_scroll",
        hit_test_substage="order_select_hit_test",
    )
    mark_browser_substage(diagnostic_result, "order_select_native_option")
    Select(select_element).select_by_value(value)
    mark_browser_substage(diagnostic_result, "order_select_readback")
    if select_element.get_attribute("value") != value:
        raise AssertionError("native contact form did not select the exact requested order")


def visit(driver, url: str, timeout: float = 35) -> None:
    bounded_timeout = max(0.1, float(timeout))
    if hasattr(driver, "set_page_load_timeout"):
        driver.set_page_load_timeout(bounded_timeout)
    driver.get(url)
    WebDriverWait(driver, bounded_timeout).until(lambda browser: browser.execute_script("return document.readyState") == "complete")


def clear_password_inputs(driver) -> bool:
    return bool(driver.execute_script("""
      const fields = Array.from(document.querySelectorAll('input[type="password"]'));
      for (const field of fields) field.value = '';
      return fields.every(field => field.value === '');
    """))


def customer_login(driver, ctx: Context, account: dict[str, Any]) -> None:
    visit(driver, ctx.shop + "/index.php?controller=authentication")
    visible(driver, "#login-form input[name='email']").send_keys(account["email"])
    visible(driver, "#login-form input[name='password']").send_keys(ctx.customer_password)
    visible(driver, "#submit-login").click()
    WebDriverWait(driver, 35).until(lambda browser: bool(browser.find_elements(By.ID, "userMenuButton")))
    if not clear_password_inputs(driver):
        raise AssertionError("synthetic customer password remained in the browser DOM")


def synthetic_support_png(marker: str) -> bytes:
    """Generate a one-pixel RGB PNG containing only a bounded synthetic marker."""
    if re.fullmatch(r"[A-Za-z0-9_]{1,128}", marker, flags=re.ASCII) is None:
        raise ValueError("support image fixture requires a bounded synthetic marker")

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"tEXt", b"Comment\x00" + marker.encode("ascii"))
        + chunk(b"IDAT", zlib.compress(b"\x00\x24\x65\xab"))
        + chunk(b"IEND", b"")
    )


def validate_synthetic_upload(filename: str, content: bytes, mime: str) -> None:
    """Validate this acceptance's fixtures, independently of native upload policy."""
    if re.fullmatch(r"[A-Za-z0-9_-]{1,80}\.(png|txt)", filename, flags=re.ASCII) is None or not 0 < len(content) <= 4096:
        raise ValueError("support fixture filename or size is invalid")
    if filename.endswith(".txt"):
        if mime != "text/plain" or re.fullmatch(rb"[A-Za-z0-9_]{1,128}", content) is None:
            raise ValueError("support text fixture MIME or content is invalid")
        return
    if mime != "image/png" or not content.startswith(b"\x89PNG\r\n\x1a\n") or len(content) < 57:
        raise ValueError("support image fixture MIME or signature is invalid")
    # The generator puts its sole metadata chunk immediately after IHDR.
    text_size = struct.unpack(">I", content[33:37])[0]
    try:
        marker = content[49:41 + text_size].decode("ascii")
        expected = synthetic_support_png(marker)
    except (UnicodeDecodeError, ValueError):
        raise ValueError("support image fixture metadata is invalid") from None
    if content != expected:
        raise ValueError("support image fixture bytes are invalid")


def assert_image_attachment_filename(href: str) -> None:
    names = parse_qs(urlparse(href).query).get("fileName", [])
    if len(names) != 1 or re.fullmatch(r"[A-Za-z0-9_-]{1,100}\.png", names[0], flags=re.ASCII) is None:
        raise AssertionError("native support image link did not identify one safe PNG filename")


def assert_image_attachment_response(result: Any, expected: bytes) -> None:
    if (
        not isinstance(result, dict) or result.get("status") != 200
        or result.get("size") != len(expected)
        or result.get("sha256") != hashlib.sha256(expected).hexdigest()
        or result.get("mime") != "image/png"
        or result.get("pngSignature") is not True or result.get("safeFilename") is not True
    ):
        raise AssertionError("authenticated support image readback did not match its synthetic PNG metadata")


def read_native_image_attachment(driver, href: str, expected: bytes) -> None:
    # The pinned native SecuredFileReaderController renders PNG as image/png.
    assert_image_attachment_filename(href)
    # Only nonsecret metadata returns to Python; response bytes and raw headers stay in-browser.
    result = driver.execute_async_script(r"""
      const [url, done] = arguments;
      fetch(url, {credentials: 'same-origin', redirect: 'follow'})
        .then(async response => {
          const bytes = new Uint8Array(await response.arrayBuffer());
          const hash = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
          const disposition = response.headers.get('Content-Disposition') || '';
          const filename = disposition.match(/(?:^|;)\s*filename="?([^";]+)"?/i);
          const safeFilename = !disposition || (filename && /^[A-Za-z0-9_-]{1,100}\.png$/.test(filename[1]));
          done({status: response.status, size: bytes.length,
            sha256: Array.from(hash, b => b.toString(16).padStart(2, '0')).join(''),
            mime: (response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase(),
            pngSignature: [137,80,78,71,13,10,26,10].every((b, i) => bytes[i] === b),
            safeFilename: Boolean(safeFilename)});
        })
        .catch(() => done({status: 0}));
    """, href)
    assert_image_attachment_response(result, expected)


def contact_form(driver, url: str):
    visit(driver, url)
    return visible(driver, ".contact-form form")


def submit_contact_message(
    driver, ctx: Context, order: dict[str, Any], marker: str, attachment_path: Path | None,
    thread_url: str | None = None, *, expected_rejection: bool = False, order_linked: bool = True,
    diagnostic_result: dict[str, Any] | None = None,
) -> None:
    mark_browser_substage(diagnostic_result, "contact_form_navigation")
    form = contact_form(driver, thread_url or ctx.contact_url)
    mark_browser_substage(diagnostic_result, "order_select_lookup")
    order_selects = form.find_elements(By.CSS_SELECTOR, "select#contact-us-id-order-select[name='id_order']")
    if not order_selects:
        raise AssertionError("native contact form did not expose the customer's order selection")
    order_select = Select(order_selects[0])
    mark_browser_substage(diagnostic_result, "order_option_scan")
    matching_options = [option for option in order_select.options if option.get_attribute("value") == str(order["order_id"])]
    mark_browser_substage(diagnostic_result, "order_owner_assertion")
    if order_linked:
        if len(matching_options) != 1 or order["reference"] not in matching_options[0].text:
            raise AssertionError("native contact form did not offer the exact customer-owned order")
        select_contact_order(
            driver, order_selects[0], str(order["order_id"]), diagnostic_result=diagnostic_result
        )
    else:
        select_contact_order(driver, order_selects[0], "", diagnostic_result=diagnostic_result)

    mark_browser_substage(diagnostic_result, "contact_field_lookup")
    contact_fields = form.find_elements(By.NAME, "id_contact")
    if len(contact_fields) != 1:
        raise AssertionError("native contact form must select exactly one support contact")
    mark_browser_substage(diagnostic_result, "contact_id_readback")
    contact_value = contact_fields[0].get_attribute("value")
    if not isinstance(contact_value, str) or not contact_value.isdigit() or int(contact_value) < 1:
        raise AssertionError("native contact form did not select a valid contact")
    mark_browser_substage(diagnostic_result, "attachment_control_lookup")
    file_fields = form.find_elements(By.CSS_SELECTOR, "input[type='file'][name='fileUpload']")
    if attachment_path is not None:
        if len(file_fields) != 1 or not file_fields[0].is_displayed():
            raise AssertionError("native contact form did not expose the enabled attachment control")
        expected_mime = "image/png" if attachment_path.suffix == ".png" else "text/plain"
        if not expected_rejection:
            mark_browser_substage(diagnostic_result, "accepted_attachment_fixture_validation")
            validate_synthetic_upload(attachment_path.name, attachment_path.read_bytes(), expected_mime)
        mark_browser_substage(diagnostic_result, "attachment_send_keys")
        file_fields[0].send_keys(str(attachment_path))
        if not expected_rejection:
            mark_browser_substage(diagnostic_result, "accepted_attachment_file_readback")
            metadata = driver.execute_script("""
              const file = arguments[0].files[0];
              return file ? {name: file.name, mime: file.type, size: file.size} : null;
            """, file_fields[0])
            if (not isinstance(metadata, dict) or metadata.get("name") != attachment_path.name
                or metadata.get("mime") != expected_mime or metadata.get("size") != attachment_path.stat().st_size):
                raise AssertionError("native contact upload did not select the exact bounded synthetic fixture")
    mark_browser_substage(diagnostic_result, "message_field_lookup")
    message_field = visible(driver, "#contact-us-message-textarea")
    mark_browser_substage(diagnostic_result, "message_send_keys")
    message_field.send_keys(marker)
    mark_browser_substage(diagnostic_result, "submit_control_lookup")
    submit = visible(driver, "button[name='submitMessage']")
    center_native_control(
        driver,
        submit,
        "message submit",
        diagnostic_result=diagnostic_result,
        scroll_substage="submit_control_scroll",
        hit_test_substage="submit_control_hit_test",
    )
    mark_browser_substage(diagnostic_result, "submit_button_click")
    submit.click()
    mark_browser_substage(diagnostic_result, "response_alert_wait")
    WebDriverWait(driver, 35).until(lambda browser: bool(browser.find_elements(By.CSS_SELECTOR, ".contact-form .alert.alert-success, .contact-form .alert.alert-danger")))
    if expected_rejection:
        mark_browser_substage(diagnostic_result, "rejection_assertion")
        if (not driver.find_elements(By.CSS_SELECTOR, ".contact-form .alert.alert-danger")
            or driver.find_elements(By.CSS_SELECTOR, ".contact-form .alert.alert-success")):
            raise AssertionError("native contact form accepted a disallowed attachment extension")
        mark_browser_substage(diagnostic_result, "rejection_verified")
        return
    if driver.find_elements(By.CSS_SELECTOR, ".contact-form .alert.alert-danger"):
        raise AssertionError("native contact form reported a failed inquiry submission")


def assert_support_denied_response(response: Any, diagnostic_result: dict[str, Any] | None = None) -> None:
    if not isinstance(response, dict):
        raise AssertionError("cross-customer support request did not return bounded denial evidence")
    status = response.get("status")
    form_count = response.get("formCount")
    redirected = response.get("redirected")
    same_origin = response.get("sameOrigin")
    if diagnostic_result is not None:
        if type(status) is int and 100 <= status <= 599:
            diagnostic_result["support_denial_status"] = status
        if type(form_count) is int and form_count >= 0:
            diagnostic_result["support_denial_form_count"] = form_count
        if type(redirected) is bool:
            diagnostic_result["support_denial_redirected"] = redirected
        if type(same_origin) is bool:
            diagnostic_result["support_denial_same_origin"] = same_origin
    if (
        type(status) is not int or status != 403
        or type(form_count) is not int or form_count != 0
        or redirected is not False or same_origin is not True
    ):
        raise AssertionError("cross-customer support request was not denied before native form rendering")


def begin_support_denial_probe(diagnostic_result: dict[str, Any] | None, probe_substage: str) -> None:
    mark_browser_substage(diagnostic_result, probe_substage)
    if diagnostic_result is not None:
        diagnostic_result["support_denial_status"] = None
        diagnostic_result["support_denial_form_count"] = 0
        diagnostic_result["support_denial_redirected"] = True
        diagnostic_result["support_denial_same_origin"] = False


def assert_foreign_thread_denied(
    driver, href: str, *, diagnostic_result: dict[str, Any] | None = None,
    probe_substage: str,
) -> None:
    begin_support_denial_probe(diagnostic_result, probe_substage)
    response = driver.execute_async_script("""
      const [url, done] = arguments;
      fetch(url, {credentials: 'same-origin', redirect: 'follow'})
        .then(async response => {
          const document = new DOMParser().parseFromString(await response.text(), 'text/html');
          done({status: response.status,
            formCount: document.querySelectorAll('.contact-form').length,
            redirected: response.redirected,
            sameOrigin: new URL(response.url, location.href).origin === location.origin});
        }).catch(() => done({status: 0}));
    """, href)
    assert_support_denied_response(response, diagnostic_result)


def assert_foreign_orderless_post_denied(
    driver, ctx: Context, marker: str, *, diagnostic_result: dict[str, Any] | None = None,
) -> None:
    begin_support_denial_probe(diagnostic_result, "foreign_orderless_post_probe")
    form = contact_form(driver, ctx.contact_url)
    response = driver.execute_async_script("""
      const [form, victimEmail, marker, done] = arguments;
      const data = new FormData(form);
      data.set('from', victimEmail);
      data.set('id_order', '0');
      data.set('message', marker);
      data.set('submitMessage', '1');
      // Preserve the sender session's native CSRF field and cookies.
      fetch(form.action, {method: 'POST', body: data, credentials: 'same-origin', redirect: 'follow'})
        .then(async response => {
          const document = new DOMParser().parseFromString(await response.text(), 'text/html');
          done({status: response.status,
            formCount: document.querySelectorAll('.contact-form').length,
            redirected: response.redirected,
            sameOrigin: new URL(response.url, location.href).origin === location.origin});
        }).catch(() => done({status: 0}));
    """, form, ctx.buyer["email"], marker)
    assert_support_denied_response(response, diagnostic_result)


def generated_customer_threads_links(
    driver, admin_url: str, diagnostic_result: dict[str, Any] | None = None
) -> list[str]:
    expected = urlparse(admin_url)
    root = expected.path.rstrip("/")
    candidates: set[str] = set()
    safe_candidates: set[str] = set()
    modern_candidates: dict[tuple[str, str], str] = {}
    legacy_candidates: dict[tuple[str, str], str] = {}
    invalid_candidates: set[str] = set()
    for link in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
        href = link.get_attribute("href") or ""
        parsed = urlparse(href)
        query = parse_qs(parsed.query, keep_blank_values=True)
        legacy_marker = "AdminCustomerThreads" in query.get("controller", [])
        modern_suffix = re.search(r"/sell/customer-service/customer-threads/?$", parsed.path) is not None
        route_match = legacy_marker or modern_suffix
        if route_match:
            candidates.add(href)
            if not safe_admin_path(href, admin_url):
                continue
            safe_candidates.add(href)
            identity = customer_threads_navigation_identity(href, admin_url)
            if identity is not None and identity[0] == "modern" and not legacy_marker:
                existing = modern_candidates.get(identity)
                if existing is None or (urlparse(href).path.endswith("/index.php/sell/customer-service/customer-threads"), href) < (
                    urlparse(existing).path.endswith("/index.php/sell/customer-service/customer-threads"), existing
                ):
                    modern_candidates[identity] = href
            elif identity is not None and identity[0] == "legacy" and legacy_marker and not modern_suffix:
                existing = legacy_candidates.get(identity)
                if existing is None or (urlparse(href).path != root + "/index.php", href) < (
                    urlparse(existing).path != root + "/index.php", existing
                ):
                    legacy_candidates[identity] = href
            else:
                invalid_candidates.add(href)
    if diagnostic_result is not None:
        diagnostic_result["customer_service_route_candidate_count"] = min(len(candidates), 20)
        diagnostic_result["customer_service_route_safe_count"] = min(len(safe_candidates), 20)
        diagnostic_result["customer_service_route_modern_count"] = min(len(modern_candidates), 20)
        diagnostic_result["customer_service_route_legacy_count"] = min(len(legacy_candidates), 20)
        diagnostic_result["customer_service_route_invalid_count"] = min(len(invalid_candidates), 20)
    if len(safe_candidates) != len(candidates):
        raise AssertionError("native Customer service navigation left the isolated Back Office")
    if invalid_candidates:
        raise AssertionError("native Customer service navigation exposed a noncanonical route")
    if not modern_candidates and not legacy_candidates:
        raise AssertionError("the authenticated administrator did not expose a native Customer service route")
    if len(modern_candidates) + len(legacy_candidates) > 20:
        raise AssertionError("native Customer service navigation exposed too many route candidates")

    root = expected.path.rstrip("/")
    ordered: list[tuple[int, int, str]] = []
    for href in modern_candidates.values():
        path = urlparse(href).path
        ordered.append((0, int(path.endswith("/index.php/sell/customer-service/customer-threads")), href))
    for href in legacy_candidates.values():
        path = urlparse(href).path
        ordered.append((1, int(path != root + "/index.php"), href))
    return [href for _route_kind, _alias_rank, href in sorted(ordered)]


def admin_login(driver, ctx: Context, email: str) -> None:
    visit(driver, ctx.admin + "/login")
    visible(driver, '#login_form input[name="email"], input[type="email"]').send_keys(email)
    visible(driver, '#login_form input[name="passwd"], #login_form input[name="password"], input[type="password"]').send_keys(ctx.admin_password)
    visible(driver, '#login_form button[type="submit"], #login_form input[type="submit"], button[type="submit"]').click()
    WebDriverWait(driver, 35).until(lambda browser: "/login" not in urlparse(browser.current_url).path)
    if not clear_password_inputs(driver):
        raise AssertionError("Back Office password remained in the browser DOM")


def view_link_from_index(
    driver, ctx: Context, buyer: dict[str, Any], expected_thread_id: int | None = None, timeout: float = 40,
) -> tuple[str, int]:
    WebDriverWait(driver, max(0.1, float(timeout))).until(lambda browser: bool(
        browser.find_elements(By.CSS_SELECTOR, "table tbody tr")
        or browser.find_elements(By.CSS_SELECTOR, '#login_form input[name="email"], #login_form input[name="passwd"]')
    ))
    if driver.find_elements(By.CSS_SELECTOR, '#login_form input[name="email"], #login_form input[name="passwd"]'):
        raise AssertionError("native Customer service candidate did not retain the authenticated admin session")
    links: set[str] = set()
    for row in driver.find_elements(By.CSS_SELECTOR, "table tbody tr"):
        text = row.text
        # PrestaShop 9.2 limits the grid's last-message cell to 32 characters,
        # so the random inquiry marker is intentionally not used as a row key.
        row_matches = buyer["email"] in text
        if not row_matches:
            continue
        for link in row.find_elements(By.CSS_SELECTOR, "a[href]"):
            href = link.get_attribute("href") or ""
            identity = thread_route_identity(href, ctx.admin)
            if identity is not None and (expected_thread_id is None or identity[1] == expected_thread_id):
                links.add(href)
    if len(links) != 1:
        raise AssertionError("native Customer service list did not identify one thread for the submitted order")
    thread_url = next(iter(links))
    identity = thread_route_identity(thread_url, ctx.admin)
    if identity is None or identity[1] < 1:
        raise AssertionError("native Customer service row did not link to a valid thread view")
    return thread_url, identity[1]


def resolve_customer_threads_index(
    driver, ctx: Context, buyer: dict[str, Any], expected_thread_id: int, candidates: list[str],
    diagnostic_result: dict[str, Any] | None = None, timeout: float = 40,
) -> tuple[str, str, int]:
    """Accept a safe admin route only after it links the exact expected native thread."""
    deadline = time.monotonic() + max(0.1, float(timeout))
    for candidate_index, index_url in enumerate(candidates):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        candidate_budget = remaining / (len(candidates) - candidate_index)
        navigation_budget = min(10.0, max(0.1, candidate_budget / 2))
        candidate_started = time.monotonic()
        mark_browser_substage(diagnostic_result, "admin_route_candidate_navigation")
        try:
            visit(driver, index_url, timeout=navigation_budget)
            remaining = deadline - time.monotonic()
            candidate_remaining = candidate_budget - (time.monotonic() - candidate_started)
            readback_budget = min(remaining, max(0.1, candidate_remaining))
            if readback_budget <= 0:
                continue
            mark_browser_substage(diagnostic_result, "admin_route_exact_thread_readback")
            thread_url, thread_id = view_link_from_index(
                driver, ctx, buyer, expected_thread_id, timeout=readback_budget
            )
        except (AssertionError, TimeoutException):
            continue
        if thread_id == expected_thread_id:
            return index_url, thread_url, thread_id

    raise AssertionError("no safe native Customer service route linked the exact expected thread within the existing lookup timeout")


def visit_exact_customer_thread_detail(
    driver, thread_url: str, admin_url: str, expected_thread_id: int,
    diagnostic_result: dict[str, Any] | None = None, timeout: float = 35,
):
    """Read the exact thread page within one bounded navigation and DOM-readback budget."""
    requested_identity = thread_route_identity(thread_url, admin_url)
    if requested_identity is None or requested_identity[1] != expected_thread_id:
        raise AssertionError("the selected native customer thread route did not match the expected thread")
    thread_selector = customer_thread_detail_selector(requested_identity[0])

    deadline = time.monotonic() + max(0.1, float(timeout))
    navigation_budget = max(0.1, min(17.5, float(timeout) / 2))
    mark_browser_substage(diagnostic_result, "admin_thread_detail_navigation")
    if hasattr(driver, "set_page_load_timeout"):
        driver.set_page_load_timeout(navigation_budget)
    try:
        driver.get(thread_url)
    except TimeoutException:
        # Chromium may complete the exact document after Selenium's page-load wait;
        # the remaining shared budget must still prove route identity and thread DOM.
        pass

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutException("the exact customer thread page exhausted its bounded navigation budget")
    mark_browser_substage(diagnostic_result, "admin_thread_detail_readback")

    def exact_thread_loaded(browser):
        identity = thread_route_identity(browser.current_url, admin_url)
        if identity != requested_identity or identity[1] != expected_thread_id:
            return False
        if browser.execute_script("return document.readyState") not in {"interactive", "complete"}:
            return False
        elements = browser.find_elements(By.CSS_SELECTOR, thread_selector)
        return elements[0] if len(elements) == 1 and elements[0].is_displayed() else False

    return WebDriverWait(driver, max(0.1, remaining)).until(exact_thread_loaded)


def customer_thread_detail_selector(route_kind: str) -> str:
    if route_kind == "modern_thread_view":
        return "[data-role='messages-thread']"
    if route_kind == "legacy_thread_view":
        # PrestaShop 9.2's native legacy customer_threads view renders the original
        # customer message inside .message-item-initial; it has no modern thread role.
        return ".message-item-initial"
    raise ValueError("the customer thread route kind is not a supported native view")


def customer_thread_content_selector(route_kind: str) -> str:
    if route_kind == "modern_thread_view":
        return "[data-role='messages-thread']"
    if route_kind == "legacy_thread_view":
        return ".message-item-initial, [data-role='thread-messages']"
    raise ValueError("the customer thread route kind is not a supported native view")


def customer_thread_message_text_selector(route_kind: str) -> str:
    if route_kind == "modern_thread_view":
        return "[data-role='messages-thread'] p.thread-message"
    if route_kind == "legacy_thread_view":
        return ".message-item-initial .message-item-text, [data-role='thread-messages'] .message-item-text"
    raise ValueError("the customer thread route kind is not a supported native view")


def read_customer_thread_text(
    driver, route_kind: str, expected_thread_id: int, admin_url: str, *, timeout: float = 30,
) -> str:
    selector = customer_thread_content_selector(route_kind)

    def visible_exact_thread(browser):
        identity = thread_route_identity(browser.current_url, admin_url)
        if identity is None or identity[1] != expected_thread_id or identity[0] != route_kind:
            return False
        elements = browser.find_elements(By.CSS_SELECTOR, selector)
        visible_text = []
        for element in elements:
            try:
                if element.is_displayed():
                    visible_text.append(element.text)
            except StaleElementReferenceException:
                return False
        return "\n".join(visible_text) if visible_text else False

    return WebDriverWait(driver, max(0.1, timeout)).until(visible_exact_thread)


def customer_thread_text_contains(
    driver, route_kind: str, expected_thread_id: int, admin_url: str, marker: str,
) -> bool:
    try:
        return marker in read_customer_thread_text(
            driver, route_kind, expected_thread_id, admin_url, timeout=0.2
        )
    except TimeoutException:
        return False


def customer_thread_reply_form(driver, route_kind: str, expected_thread_id: int, admin_url: str):
    identity = thread_route_identity(driver.current_url, admin_url)
    if identity is None or identity[1] != expected_thread_id or identity[0] != route_kind:
        raise AssertionError("native customer reply form left the exact customer thread route")

    matches = []
    if route_kind == "modern_thread_view":
        reply_card = visible(driver, "[data-role='employee-answer']")
        reply_form = reply_card.find_element(By.XPATH, "./ancestor::form[1]")
        textareas = reply_form.find_elements(By.CSS_SELECTOR, "textarea[name$='[reply_message]']")
        buttons = reply_form.find_elements(By.CSS_SELECTOR, "button")
        if len(textareas) == 1 and len(buttons) == 1:
            matches.append((reply_form, textareas[0], buttons[0]))
    elif route_kind == "legacy_thread_view":
        for reply_form in driver.find_elements(By.CSS_SELECTOR, "form"):
            action = reply_form.get_attribute("action") or ""
            action_identity = thread_route_identity(urljoin(driver.current_url, action), admin_url)
            textareas = reply_form.find_elements(By.CSS_SELECTOR, "textarea[name='reply_message']")
            buttons = reply_form.find_elements(By.CSS_SELECTOR, "button[name='submitReply']")
            if action_identity == identity and len(textareas) == 1 and len(buttons) == 1:
                matches.append((reply_form, textareas[0], buttons[0]))
    else:
        raise ValueError("the customer thread route kind is not a supported native view")

    if len(matches) != 1:
        raise AssertionError("native customer thread did not expose one exact-thread public reply form")
    reply_form, textarea, button = matches[0]
    if not textarea.is_displayed() or not button.is_displayed() or not button.is_enabled():
        raise AssertionError("native customer thread reply controls are not visible and enabled")
    return reply_form, textarea, button


def has_thread_order_link(driver, expected_order_id: int, admin_url: str) -> bool:
    if type(expected_order_id) is not int or expected_order_id < 1:
        raise ValueError("a positive native order identity is required")
    admin_root = urlparse(admin_url).path.rstrip("/")
    for link in driver.find_elements(By.CSS_SELECTOR, "[data-role='messages_timeline'] a[href]"):
        try:
            if not link.is_displayed():
                continue
        except StaleElementReferenceException:
            continue
        href = link.get_attribute("href") or ""
        if not safe_admin_path(href, admin_url):
            continue
        parsed = urlparse(urljoin(admin_url.rstrip("/") + "/", href))
        query = parse_qs(parsed.query)
        candidates = query.get("id_order", [])
        native_order_route = (
            parsed.path in {admin_root, admin_root + "/index.php"}
            and query.get("controller") == ["AdminOrders"]
            and query.get("vieworder") == ["1"]
        )
        if not native_order_route:
            native_order_route = re.fullmatch(
                re.escape(admin_root) + rf"(?:/index\.php)?/sell/orders/{expected_order_id}(?:/view)?/?",
                parsed.path,
            ) is not None
            if native_order_route:
                candidates = [str(expected_order_id)]
        if native_order_route and candidates == [str(expected_order_id)]:
            return True
    return False


def has_thread_order_association(
    driver, expected_order_id: int, route_kind: str, expected_thread_id: int, admin_url: str,
) -> bool:
    if type(expected_order_id) is not int or expected_order_id < 1:
        raise ValueError("a positive native order identity is required")
    if type(expected_thread_id) is not int or expected_thread_id < 1:
        raise ValueError("a positive native customer thread identity is required")
    if thread_route_identity(driver.current_url, admin_url) != (route_kind, expected_thread_id):
        return False
    if route_kind == "modern_thread_view":
        return has_thread_order_link(driver, expected_order_id, admin_url)
    if route_kind != "legacy_thread_view":
        raise ValueError("the customer thread route kind is not a supported native view")

    expected_order_marker = re.compile(rf"(?<![0-9])#\s*{expected_order_id}(?![0-9])")
    for item in driver.find_elements(By.CSS_SELECTOR, "#orders-and-messages-block .timeline-item"):
        if item.is_displayed() and expected_order_marker.search(item.text):
            return True
    return False


def find_attachment_link(driver, admin_url: str, buyer_marker: str, route_kind: str) -> str:
    message = None
    for candidate in driver.find_elements(By.CSS_SELECTOR, customer_thread_message_text_selector(route_kind)):
        if buyer_marker in candidate.text:
            message = candidate
            break
    if message is None:
        raise AssertionError("native customer message with the uploaded attachment is missing")
    message_row = message.find_element(
        By.XPATH,
        "./ancestor::li[1]" if route_kind == "modern_thread_view"
        else "./ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' message-body ')][1]",
    )
    found = [
        link.get_attribute("href") or ""
        for link in message_row.find_elements(By.CSS_SELECTOR, "a[href]")
    ]
    if len(set(found)) != 1:
        raise AssertionError("native customer message did not expose exactly one owned attachment")
    href = found[0]
    if not safe_admin_path(href, admin_url):
        raise AssertionError("native support attachment link left the authenticated Back Office")
    return href


def attachment_visible_to_session(driver, href: str, expected_content: str) -> bool:
    result = driver.execute_async_script("""
      const [url, marker, done] = arguments;
      fetch(url, {credentials: 'same-origin', redirect: 'follow'})
        .then(async response => {
          const body = await response.text();
          done({status: response.status, contentMatch: body.includes(marker)});
        })
        .catch(() => done({status: 0, contentMatch: false}));
    """, href, expected_content)
    if (
        not isinstance(result, dict)
        or type(result.get("status")) is not int
        or type(result.get("contentMatch")) is not bool
    ):
        raise AssertionError("support attachment privacy probe returned an invalid response")
    if result["contentMatch"]:
        return True
    if result["status"] not in {200, 401, 403, 404}:
        raise AssertionError("support attachment privacy probe did not complete a verifiable access check")
    return False


def open_native_attachment(driver, href: str, expected_content: str, download_dir: Path) -> None:
    previous = set(driver.window_handles)
    original_handle = driver.current_window_handle
    link = next((element for element in driver.find_elements(By.CSS_SELECTOR, "a[href]") if element.get_attribute("href") == href), None)
    if link is None:
        raise AssertionError("the owned attachment link disappeared before readback")
    for child in download_dir.iterdir():
        if child.is_file():
            child.unlink()
    link.click()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        download = next((path for path in download_dir.iterdir() if path.is_file() and not path.name.endswith(".crdownload")), None)
        if download is not None:
            if expected_content not in download.read_text(encoding="utf-8", errors="replace"):
                raise AssertionError("authenticated native attachment download did not return the uploaded fixture content")
            return
        new_handles = [handle for handle in driver.window_handles if handle not in previous]
        if new_handles:
            driver.switch_to.window(new_handles[0])
            if driver.execute_script("return document.readyState") == "complete":
                try:
                    page_text = driver.find_element(By.TAG_NAME, "body").text
                except Exception:
                    page_text = ""
                if expected_content in page_text:
                    driver.close()
                    driver.switch_to.window(original_handle)
                    return
            driver.switch_to.window(original_handle)
        elif driver.current_url == href and driver.execute_script("return document.readyState") == "complete":
            if expected_content in driver.find_element(By.TAG_NAME, "body").text:
                return
        time.sleep(0.2)
    raise TimeoutError("authenticated native attachment readback did not complete")


def status_action_form(driver, status: str, route_kind: str, expected_thread_id: int, admin_url: str):
    identity = thread_route_identity(driver.current_url, admin_url)
    if identity is None or identity[1] != expected_thread_id or identity[0] != route_kind:
        raise AssertionError("native support status action left the exact customer thread route")

    matches = []
    if route_kind == "modern_thread_view":
        for form in driver.find_elements(By.CSS_SELECTOR, "[data-role='messages-thread'] form"):
            fields = form.find_elements(By.CSS_SELECTOR, f"input[name='newStatus'][value='{status}']")
            buttons = form.find_elements(By.CSS_SELECTOR, "button")
            if fields and len(buttons) == 1:
                matches.append((form, buttons[0]))
    elif route_kind == "legacy_thread_view":
        status_value = {"open": "1", "closed": "2"}.get(status)
        if status_value is None:
            raise ValueError("the requested customer thread status is not supported")
        for form in driver.find_elements(By.CSS_SELECTOR, "form"):
            action = form.get_attribute("action") or ""
            action_identity = thread_route_identity(urljoin(driver.current_url, action), admin_url)
            buttons = form.find_elements(By.CSS_SELECTOR, f"button[name='setstatus'][value='{status_value}']")
            if action_identity == identity and buttons:
                matches.append((form, buttons[0]))
    else:
        raise ValueError("the customer thread route kind is not a supported native view")

    if len(matches) != 1:
        raise AssertionError(f"native support thread did not expose the expected {status} status action")
    return matches[0]


def update_thread_status(
    driver, status: str, expected_next_action: str, route_kind: str, expected_thread_id: int, admin_url: str,
    diagnostic_result: dict[str, Any] | None = None,
) -> None:
    mark_browser_substage(diagnostic_result, "status_action_lookup")
    _form, button = status_action_form(driver, status, route_kind, expected_thread_id, admin_url)
    # This is the sole mutating action. Never replay it if the click or navigation is stale.
    mark_browser_substage(diagnostic_result, "status_action_click")
    button.click()
    mark_browser_substage(diagnostic_result, "status_action_readback")

    def next_action_visible(browser):
        identity = thread_route_identity(browser.current_url, admin_url)
        if identity is None or identity[1] != expected_thread_id or identity[0] != route_kind:
            return False
        try:
            status_action_form(browser, expected_next_action, route_kind, expected_thread_id, admin_url)
        except StaleElementReferenceException:
            # The native status action replaces the thread DOM after its POST. A stale
            # element during this read-only poll means reacquire within the existing wait.
            return False
        except AssertionError:
            return False
        return True

    WebDriverWait(driver, 25).until(next_action_visible)


def _status_action_available(
    driver, status: str, route_kind: str, expected_thread_id: int, admin_url: str,
) -> bool:
    try:
        status_action_form(driver, status, route_kind, expected_thread_id, admin_url)
    except AssertionError:
        return False
    return True


def employee_scoped_thread_url(driver, source_url: str, admin_url: str) -> str:
    identity = thread_route_identity(source_url, admin_url)
    if identity is not None and identity[0] == "modern_thread_view":
        target = urlparse(source_url)
        query = parse_qs(target.query, keep_blank_values=True)
        query.pop("token", None)
        query.pop("_token", None)
        return urlunparse((target.scheme, target.netloc, target.path, target.params, urlencode(query, doseq=True), ""))

    employee_token = ""
    candidates = [driver.current_url]
    candidates.extend(link.get_attribute("href") or "" for link in driver.find_elements(By.CSS_SELECTOR, "a[href]"))
    for candidate in candidates:
        if not safe_admin_path(candidate, admin_url):
            continue
        tokens = parse_qs(urlparse(candidate).query, keep_blank_values=True).get("token", [])
        if len(tokens) == 1 and tokens[0]:
            employee_token = tokens[0]
            break
    if not employee_token:
        raise AssertionError("limited employee session did not expose its own native admin token")
    target = urlparse(source_url)
    expected = urlparse(admin_url)
    if (target.scheme, target.hostname, target.port) != (expected.scheme, expected.hostname, expected.port) or not safe_admin_path(source_url, admin_url):
        raise AssertionError("customer thread target left the isolated Back Office")
    query = parse_qs(target.query, keep_blank_values=True)
    query.pop("token", None)
    query["token"] = [employee_token]
    return urlunparse((target.scheme, target.netloc, target.path, target.params, urlencode(query, doseq=True), ""))


def employee_scoped_legacy_controller_url(driver, controller: str, admin_url: str) -> str:
    if controller not in {"AdminKuraneaSupportAssignments"}:
        raise ValueError("legacy Back Office controller is outside the support test allowlist")
    employee_token = ""
    candidates = [driver.current_url]
    candidates.extend(link.get_attribute("href") or "" for link in driver.find_elements(By.CSS_SELECTOR, "a[href]"))
    for candidate in candidates:
        if not safe_admin_path(candidate, admin_url):
            continue
        parsed = urlparse(candidate)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if len(query.get("token", [])) == 1 and query["token"][0]:
            employee_token = query["token"][0]
            break
    if not employee_token:
        raise AssertionError("employee session did not expose its own native Back Office token")
    root = urlparse(admin_url)
    path = root.path.rstrip("/") + "/index.php"
    return urlunparse((root.scheme, root.netloc, path, "", urlencode({"controller": controller, "token": employee_token}), ""))


def generated_support_assignment_link(driver, admin_url: str) -> str:
    candidates = set()
    for link in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
        href = link.get_attribute("href") or ""
        if parse_qs(urlparse(href).query).get("controller") == ["AdminKuraneaSupportAssignments"]:
            if not safe_admin_path(href, admin_url):
                raise AssertionError("support assignment navigation left the isolated Back Office")
            candidates.add(href)
    if len(candidates) != 1:
        raise AssertionError("the administrator did not expose one native support-assignment navigation link")
    return next(iter(candidates))


def assignment_row(driver, thread_id: int):
    WebDriverWait(driver, 30).until(lambda browser: bool(browser.find_elements(By.CSS_SELECTOR, ".table tbody tr")))
    matches = []
    for row in driver.find_elements(By.CSS_SELECTOR, ".table tbody tr"):
        cells = row.find_elements(By.CSS_SELECTOR, "td")
        if cells and cells[0].text.strip() == str(thread_id):
            matches.append(row)
    if len(matches) != 1:
        raise AssertionError("support assignment list did not identify exactly one same-shop thread")
    return matches[0]


def assign_thread(driver, thread_id: int, employee_id: str) -> None:
    row = assignment_row(driver, thread_id)
    selects = row.find_elements(By.CSS_SELECTOR, "select[name='id_employee']")
    if len(selects) != 1 or not any(option.get_attribute("value") == employee_id for option in Select(selects[0]).options):
        raise AssertionError("support assignment did not offer the selected active employee")
    Select(selects[0]).select_by_value(employee_id)
    submit = row.find_element(By.CSS_SELECTOR, "button[name='submitOrdenowaSupportAssignment']")
    if not submit.is_displayed() or not submit.is_enabled():
        raise AssertionError("support assignment save control is not available to the administrator")
    submit.click()
    visible(driver, ".alert.alert-success", timeout=20)


def selected_assignment_employee(driver, thread_id: int) -> str:
    row = assignment_row(driver, thread_id)
    selects = row.find_elements(By.CSS_SELECTOR, "select[name='id_employee']")
    if len(selects) != 1:
        raise AssertionError("saved support assignment does not expose one employee selector")
    value = Select(selects[0]).first_selected_option.get_attribute("value")
    if not isinstance(value, str) or not value.isdigit() or int(value) < 1:
        raise AssertionError("saved support assignment did not resolve to a positive employee ID")
    return value


def assignment_history_link(driver, thread_id: int, admin_url: str) -> str:
    row = assignment_row(driver, thread_id)
    links = [
        link.get_attribute("href") or ""
        for link in row.find_elements(By.CSS_SELECTOR, "a[href]")
        if "변경 이력 보기" in link.text
    ]
    if len(set(links)) != 1 or not safe_admin_path(links[0], admin_url):
        raise AssertionError("same-shop thread did not expose one safe assignment-history route")
    query = parse_qs(urlparse(links[0]).query, keep_blank_values=True)
    if query.get("id_customer_thread") != [str(thread_id)]:
        raise AssertionError("assignment-history route did not retain the same native thread identity")
    return links[0]


def assert_assignment_history(driver, thread_id: int, first_name: str, second_name: str) -> None:
    heading_text = f"문의 #{thread_id} 담당자 변경 이력"
    heading = next((item for item in driver.find_elements(By.CSS_SELECTOR, "h3") if item.text.strip() == heading_text), None)
    if heading is None:
        raise AssertionError("support assignment history did not identify the same native thread")
    table = heading.find_element(By.XPATH, "following::table[1]")
    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    if len(rows) < 2:
        raise AssertionError("support assignment history did not retain create and reassign events")
    cells = rows[0].find_elements(By.CSS_SELECTOR, "td")
    if len(cells) != 4 or cells[1].text.strip() != first_name or cells[2].text.strip() != second_name or not cells[3].text.strip():
        raise AssertionError("latest support assignment history did not retain prior, new, and acting employees")
    first_event = rows[1].find_elements(By.CSS_SELECTOR, "td")
    if len(first_event) != 4 or first_event[1].text.strip() != "최초 지정" or first_event[2].text.strip() != first_name or not first_event[3].text.strip():
        raise AssertionError("initial support assignment history did not retain the new and acting employees")


def write_result(path: Path, result: dict[str, Any]) -> None:
    if (
        set(result) != SAFE_RESULT_KEYS
        or result.get("stage") not in SAFE_STAGES
        or result.get("status") not in {"success", "failure"}
        or any(type(result.get(key)) is not bool for key in RESULT_BOOLEAN_KEYS)
        or (result.get("contact_document_status") is not None and (
            type(result.get("contact_document_status")) is not int
            or not 100 <= result["contact_document_status"] <= 599
        ))
        or (result.get("support_denial_status") is not None and (
            type(result.get("support_denial_status")) is not int
            or not 100 <= result["support_denial_status"] <= 599
        ))
        or type(result.get("contact_form_count")) is not int or result["contact_form_count"] < 0
        or type(result.get("support_denial_form_count")) is not int or result["support_denial_form_count"] < 0
        or type(result.get("customer_service_route_candidate_count")) is not int
        or not 0 <= result["customer_service_route_candidate_count"] <= 20
        or type(result.get("customer_service_route_safe_count")) is not int
        or not 0 <= result["customer_service_route_safe_count"] <= 20
        or type(result.get("customer_service_route_modern_count")) is not int
        or not 0 <= result["customer_service_route_modern_count"] <= 20
        or type(result.get("customer_service_route_legacy_count")) is not int
        or not 0 <= result["customer_service_route_legacy_count"] <= 20
        or type(result.get("customer_service_route_invalid_count")) is not int
        or not 0 <= result["customer_service_route_invalid_count"] <= 20
        or not isinstance(result.get("browser_substage"), str)
        or result["browser_substage"] not in SAFE_BROWSER_SUBSTAGES
        or result.get("mailpit_provider") != "isolated_only"
        or (result.get("exception_type") is not None and result.get("exception_type") not in SAFE_EXCEPTION_TYPES)
        or (result.get("status") == "success" and (
            result.get("exception_type") is not None
            or any(result.get(key) is not True for key in RESULT_BOOLEAN_KEYS - {
                "paid", "payment_provider_called", "support_denial_redirected",
            })
            or result.get("paid") is not False
            or result.get("payment_provider_called") is not False
            or result.get("support_denial_status") != 403
            or result.get("support_denial_form_count") != 0
            or result.get("support_denial_redirected") is not False
            or result.get("support_denial_same_origin") is not True
        ))
    ):
        raise ValueError("customer support diagnostics did not match the allowlisted result schema")
    path.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def run() -> None:
    ctx = load_context()
    stage = "fixture"
    result: dict[str, Any] = {
        "status": "failure", "stage": stage, "exception_type": None,
        "browser_substage": "not_applicable",
        "customer_submitted": False, "order_association_verified": False,
        "attachment_admin_readback": False, "private_note_admin_only": False,
        "status_close_reopen": False, "admin_public_reply": False,
        "customer_followup_same_thread": False, "foreign_customer_denied": False,
        "limited_employee_denied": False, "mailpit_provider": "isolated_only",
        "paid": False, "payment_provider_called": False, "assignment_created": False,
        "assignment_reassigned": False, "assignment_actor_history": False,
        "assignment_limited_employee_denied": False,
        "image_attachment_admin_readback": False, "image_attachment_foreign_denied": False,
        "disallowed_attachment_rejected": False,
        "foreign_valid_thread_denied": False, "foreign_orderless_post_denied": False,
        "orderless_thread_unchanged": False, "contact_document_status": None,
        "contact_same_origin": False, "contact_native_route": False,
        "contact_form_count": 0, "contact_form_visible": False,
        "support_denial_status": None, "support_denial_form_count": 0,
        "support_denial_redirected": True, "support_denial_same_origin": False,
        "customer_service_route_candidate_count": 0, "customer_service_route_safe_count": 0,
        "customer_service_route_modern_count": 0, "customer_service_route_legacy_count": 0,
        "customer_service_route_invalid_count": 0,
        "admin_thread_message_marker_present": False, "admin_thread_order_association_present": False,
    }
    customer = admin = foreign = limited = None
    buyer_marker = f"[CI ONLY] ORDENOWA support inquiry {ctx.run_id}-{ctx.attempt}-{secrets.token_hex(5)}"
    reply_marker = f"[CI ONLY] ORDENOWA public support reply {ctx.run_id}-{ctx.attempt}-{secrets.token_hex(5)}"
    followup_marker = f"[CI ONLY] ORDENOWA customer follow-up {ctx.run_id}-{ctx.attempt}-{secrets.token_hex(5)}"
    private_marker = f"[CI ONLY] ORDENOWA internal note {ctx.run_id}-{ctx.attempt}-{secrets.token_hex(5)}"
    attachment_marker = f"ORDENOWA_SUPPORT_ATTACHMENT_{ctx.run_id}_{ctx.attempt}_{secrets.token_hex(5)}"
    image_marker = f"ORDENOWA_SUPPORT_IMAGE_{ctx.run_id}_{ctx.attempt}_{secrets.token_hex(5)}"
    rejected_marker = f"[CI ONLY] ORDENOWA rejected upload {ctx.run_id}-{ctx.attempt}-{secrets.token_hex(5)}"
    orderless_marker = f"[CI ONLY] ORDENOWA orderless inquiry {ctx.run_id}-{ctx.attempt}-{secrets.token_hex(5)}"
    attack_marker = f"[CI ONLY] ORDENOWA denied foreign reply {ctx.run_id}-{ctx.attempt}-{secrets.token_hex(5)}"
    image_bytes = synthetic_support_png(image_marker)
    attachment_file = image_file = rejected_file = None
    download_dir = None
    try:
        stage = result["stage"] = "customer_login"
        customer = new_driver()
        customer_login(customer, ctx, ctx.buyer)

        stage = result["stage"] = "contact_form"
        query_route = ctx.shop + "/index.php?controller=contact"
        metadata = ctx.contact_route_metadata
        contact_rewrite = metadata["localized_rewrite_by_iso"]["ja"]
        query_probe = probe_contact_route(
            customer, query_route, ctx.shop, locale="ja", localized_rewrite=contact_rewrite
        )
        generated_probe = probe_contact_route(
            customer, ctx.contact_url, ctx.shop, locale="ja", localized_rewrite=contact_rewrite
        )
        print(
            "CONTACT_ROUTE_DIAGNOSTIC "
            f"meta_present={str(metadata['contact_meta_present']).lower()} "
            f"rewrite_enabled={str(metadata['rewriting_enabled']).lower()} "
            f"canonical_mode={metadata['canonical_redirect_mode']} "
            f"contactform_enabled={str(metadata['contactform_enabled']).lower()} "
            f"localized_rewrites={'/'.join(locale for locale, present in metadata['localized_rewrites'].items() if present) or 'none'} "
            f"query_status={query_probe['status'] or 'unavailable'} "
            f"query_page={query_probe['page_class']} query_form_count={query_probe['form_count']} "
            f"generated_status={generated_probe['status'] or 'unavailable'} "
            f"generated_page={generated_probe['page_class']} generated_form_count={generated_probe['form_count']}"
        )
        customer.get(ctx.contact_url)
        result.update(contact_page_evidence(
            customer, ctx.shop, locale="ja", localized_rewrite=contact_rewrite
        ))
        visible(customer, ".contact-form form")
        baseline_mail = mail_ids(ctx.mailpit)
        with tempfile.NamedTemporaryFile(prefix="ordenowa-support-", suffix=".txt", mode="w", encoding="utf-8", delete=False) as file:
            file.write(attachment_marker)
            attachment_file = Path(file.name)
        with tempfile.NamedTemporaryFile(prefix="ordenowa-support-", suffix=".png", delete=False) as file:
            file.write(image_bytes)
            image_file = Path(file.name)
        with tempfile.NamedTemporaryFile(prefix="ordenowa-support-", suffix=".php", delete=False) as file:
            # Inert bytes; the negative case tests the disallowed extension, not executable content.
            file.write(b"ORDENOWA_CI_INERT_DISALLOWED_EXTENSION")
            rejected_file = Path(file.name)
        stage = result["stage"] = "rejected_attachment"
        submit_contact_message(
            customer, ctx, ctx.buyer, rejected_marker, rejected_file,
            expected_rejection=True, diagnostic_result=result,
        )
        result["disallowed_attachment_rejected"] = True
        mark_browser_substage(result, "not_applicable")
        stage = result["stage"] = "submit_inquiry"
        submit_contact_message(customer, ctx, ctx.buyer, buyer_marker, attachment_file)
        result["customer_submitted"] = True
        customer.save_screenshot(str(ctx.artifact_dir / "customer-support-inquiry-submitted.png"))

        stage = result["stage"] = "mailpit_confirmation"
        first_thread_id, thread_token, _confirmation = wait_for_thread_email(ctx.mailpit, ctx.buyer["email"], baseline_mail)
        localized_rewrite = ctx.contact_route_metadata["localized_rewrite_by_iso"]["ja"]
        valid_customer_thread_url = native_customer_thread_url(
            ctx.contact_url, ctx.shop, first_thread_id, thread_token,
            locale="ja", localized_rewrite=localized_rewrite,
        )
        if not validate_customer_thread_url(
            valid_customer_thread_url, ctx.shop, first_thread_id,
            locale="ja", localized_rewrite=localized_rewrite,
        ):
            raise AssertionError("native customer confirmation did not produce a bounded thread URL")

        stage = result["stage"] = "orderless_inquiry"
        before_orderless = mail_ids(ctx.mailpit)
        submit_contact_message(customer, ctx, ctx.buyer, orderless_marker, None, order_linked=False)
        orderless_id, orderless_token, _orderless_confirmation = wait_for_thread_email(ctx.mailpit, ctx.buyer["email"], before_orderless)
        if orderless_id == first_thread_id:
            raise AssertionError("orderless fixture must use a distinct native inquiry")
        orderless_url = native_customer_thread_url(
            ctx.contact_url, ctx.shop, orderless_id, orderless_token,
            locale="ja", localized_rewrite=localized_rewrite,
        )
        stage = result["stage"] = "foreign_customer_denial"
        foreign = new_driver()
        customer_login(foreign, ctx, ctx.foreign)
        invalid_token = "".join(secrets.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(12))
        if invalid_token == thread_token:
            replacement = "A" if thread_token[0] != "A" else "B"
            invalid_token = replacement + thread_token[1:]
        invalid_url = native_customer_thread_url(
            ctx.contact_url, ctx.shop, first_thread_id, invalid_token,
            locale="ja", localized_rewrite=localized_rewrite,
        )
        assert_foreign_thread_denied(
            foreign, invalid_url, diagnostic_result=result,
            probe_substage="foreign_invalid_token_probe",
        )
        result["foreign_customer_denied"] = True
        stage = result["stage"] = "foreign_valid_thread"
        assert_foreign_thread_denied(
            foreign, valid_customer_thread_url, diagnostic_result=result,
            probe_substage="foreign_owned_thread_probe",
        )
        assert_foreign_thread_denied(
            foreign, orderless_url, diagnostic_result=result,
            probe_substage="foreign_orderless_thread_probe",
        )
        result["foreign_valid_thread_denied"] = True
        stage = result["stage"] = "foreign_orderless_post"
        assert_foreign_orderless_post_denied(foreign, ctx, attack_marker, diagnostic_result=result)
        result["foreign_orderless_post_denied"] = True
        foreign.get(valid_customer_thread_url)
        foreign.save_screenshot(str(ctx.artifact_dir / "customer-support-foreign-denied.png"))

        stage = result["stage"] = "admin_login"
        download_dir = Path(tempfile.mkdtemp(prefix="ordenowa-support-download-"))
        admin = new_driver(download_dir=download_dir)
        admin_login(admin, ctx, ctx.admin_email)
        mark_browser_substage(result, "admin_login_completed")
        stage = result["stage"] = "admin_thread_lookup"
        mark_browser_substage(result, "admin_service_route_discovery")
        index_candidates = generated_customer_threads_links(admin, ctx.admin, result)
        index_link, index_thread_view_url, thread_id = resolve_customer_threads_index(
            admin, ctx, ctx.buyer, first_thread_id, index_candidates, result
        )
        if thread_id != first_thread_id:
            raise AssertionError("native customer service page did not open the confirmation's same thread")
        if thread_route_identity(index_thread_view_url, ctx.admin) not in {
            ("legacy_thread_view", thread_id), ("modern_thread_view", thread_id),
        }:
            raise AssertionError("the selected Customer service row lost its exact native thread identity")
        # Keep the exact native detail link returned by the authenticated thread row.
        # Legacy and modern views expose the same association through different markup.
        thread_view_url = index_thread_view_url
        thread_element = visit_exact_customer_thread_detail(
            admin, thread_view_url, ctx.admin, thread_id, result
        )
        thread_identity = thread_route_identity(admin.current_url, ctx.admin)
        requested_identity = thread_route_identity(thread_view_url, ctx.admin)
        if thread_identity is None or thread_identity != requested_identity or thread_identity[1] != thread_id:
            raise AssertionError("native customer thread detail route lost its validated identity")
        thread_route_kind = thread_identity[0]
        thread_body = read_customer_thread_text(admin, thread_route_kind, thread_id, ctx.admin)
        mark_browser_substage(result, "admin_thread_message_readback")
        result["admin_thread_message_marker_present"] = buyer_marker in thread_body
        if not result["admin_thread_message_marker_present"]:
            raise AssertionError("native administrator thread did not show the submitted customer inquiry")
        mark_browser_substage(result, "admin_thread_order_association_readback")
        result["admin_thread_order_association_present"] = has_thread_order_association(
            admin, int(ctx.buyer["order_id"]), thread_route_kind, thread_id, ctx.admin
        )
        if not result["admin_thread_order_association_present"]:
            raise AssertionError("native customer thread did not show the same associated order")
        result["order_association_verified"] = True
        admin.save_screenshot(str(ctx.artifact_dir / "customer-support-admin-thread.png"))

        stage = result["stage"] = "orderless_readback"
        visit(admin, index_link)
        orderless_view_url, orderless_thread_id = view_link_from_index(admin, ctx, ctx.buyer, orderless_id)
        if orderless_thread_id != orderless_id:
            raise AssertionError("native orderless inquiry detail did not retain its exact thread identity")
        orderless_identity = thread_route_identity(orderless_view_url, ctx.admin)
        if orderless_identity is None or orderless_identity[1] != orderless_id:
            raise AssertionError("native orderless inquiry route did not match its exact thread identity")
        visit(admin, orderless_view_url)
        orderless_body = read_customer_thread_text(
            admin, orderless_identity[0], orderless_id, ctx.admin
        )
        if orderless_marker not in orderless_body or attack_marker in orderless_body:
            raise AssertionError("a foreign sender changed the native orderless inquiry")
        result["orderless_thread_unchanged"] = True
        visit(admin, thread_view_url)
        stage = result["stage"] = "attachment_readback"
        attachment_url = find_attachment_link(admin, ctx.admin, buyer_marker, thread_route_kind)
        open_native_attachment(admin, attachment_url, attachment_marker, download_dir)
        if attachment_visible_to_session(foreign, attachment_url, attachment_marker):
            raise AssertionError("a different customer session could read the private support attachment")
        result["attachment_admin_readback"] = True

        stage = result["stage"] = "private_forward_note"
        forward_target = customer_thread_forward_target(thread_route_kind)
        forward_button = visible(admin, f'button[data-target="{forward_target}"]')
        forward_button.click()
        modal_selector = customer_thread_forward_visible_modal(thread_route_kind)
        modal = visible(admin, modal_selector)
        if thread_route_kind == "modern_thread_view":
            employee_selects = modal.find_elements(By.CSS_SELECTOR, "select[name$='[employee_id]']")
            note_fields = modal.find_elements(By.CSS_SELECTOR, "textarea[name$='[comment]']")
        else:
            employee_selects = modal.find_elements(By.CSS_SELECTOR, "select[name='id_employee_forward']")
            note_fields = modal.find_elements(By.CSS_SELECTOR, "textarea[name='message_forward']")
        if len(employee_selects) != 1 or len(note_fields) != 1:
            raise AssertionError("native forward form did not expose employee and internal comment fields")
        forward_forms = customer_thread_forward_forms(modal, thread_route_kind)
        exact_forward_forms = []
        for form in forward_forms:
            forward_action = form.get_attribute("action") or ""
            forward_identity = thread_action_route_identity(urljoin(admin.current_url, forward_action), ctx.admin)
            if forward_identity is not None and forward_identity == (thread_route_kind, thread_id):
                exact_forward_forms.append(form)
        if len(exact_forward_forms) != 1:
            raise AssertionError("native internal note form did not target the exact customer thread")
        forward_form = exact_forward_forms[0]
        employee_select = Select(employee_selects[0])
        if not any(option.get_attribute("value") == "1" for option in employee_select.options):
            raise AssertionError("the native internal-note recipient is not the isolated primary administrator")
        employee_select.select_by_value("1")
        note_fields[0].send_keys(private_marker)
        forward_submit = modal.find_element(By.CSS_SELECTOR, "button[type='submit']")
        if not forward_submit.is_displayed() or not forward_submit.is_enabled():
            raise AssertionError("native internal note submit control is not visible and enabled")
        forward_submit.click()
        WebDriverWait(admin, 30).until(lambda browser: customer_thread_text_contains(
            browser, thread_route_kind, thread_id, ctx.admin, private_marker
        ))
        result["private_note_admin_only"] = True

        stage = result["stage"] = "close_thread"
        update_thread_status(admin, "closed", "open", thread_route_kind, thread_id, ctx.admin, result)
        stage = result["stage"] = "reopen_thread"
        update_thread_status(admin, "open", "closed", thread_route_kind, thread_id, ctx.admin, result)
        result["status_close_reopen"] = True

        stage = result["stage"] = "admin_public_reply"
        before_reply = mail_ids(ctx.mailpit)
        reply_form, reply_textarea, reply_button = customer_thread_reply_form(
            admin, thread_route_kind, thread_id, ctx.admin
        )
        reply_textarea.send_keys(reply_marker)
        reply_button.click()
        WebDriverWait(admin, 35).until(lambda browser: _status_action_available(
            browser, "closed", thread_route_kind, thread_id, ctx.admin
        ))
        stage = result["stage"] = "mailpit_public_reply"
        reply_thread_id, reply_token, reply_message = wait_for_thread_email(ctx.mailpit, ctx.buyer["email"], before_reply)
        if reply_thread_id != first_thread_id:
            raise AssertionError("native admin reply email did not retain the original thread identity")
        reply_body = str(reply_message.get("HTML") or "") + str(reply_message.get("Text") or "")
        if reply_marker not in reply_body:
            raise AssertionError("the customer-facing native reply email did not contain its public reply")
        if private_marker in reply_body:
            raise AssertionError("the customer-facing reply email exposed an administrator-only note")
        customer_reply_url = thread_link_from_email(reply_message, ctx.shop, first_thread_id)
        query = parse_qs(urlparse(customer_reply_url).query)
        if query.get("token") != [reply_token]:
            raise AssertionError("native admin reply link and message identity disagree")
        result["admin_public_reply"] = True

        stage = result["stage"] = "customer_followup"
        before_followup = mail_ids(ctx.mailpit)
        submit_contact_message(customer, ctx, ctx.buyer, followup_marker, image_file, customer_reply_url)
        followup_id, _followup_token, _followup_mail = wait_for_thread_email(
            ctx.mailpit, ctx.buyer["email"], before_followup
        )
        if followup_id != first_thread_id:
            raise AssertionError("customer follow-up did not retain the original native thread identity")
        if private_marker in customer.page_source:
            raise AssertionError("the customer-facing contact page exposed the administrator's private note")
        result["customer_followup_same_thread"] = True

        stage = result["stage"] = "thread_fresh_readback"
        visit(admin, thread_view_url)
        fresh_body = read_customer_thread_text(admin, thread_route_kind, thread_id, ctx.admin)
        if followup_marker not in fresh_body or private_marker not in fresh_body or buyer_marker not in fresh_body:
            raise AssertionError("fresh native thread readback did not preserve public/private/customer messages")

        stage = result["stage"] = "image_attachment_readback"
        image_url = find_attachment_link(admin, ctx.admin, followup_marker, thread_route_kind)
        read_native_image_attachment(admin, image_url, image_bytes)
        result["image_attachment_admin_readback"] = True
        if attachment_visible_to_session(foreign, image_url, image_marker):
            raise AssertionError("a different customer session could read the private support image")
        result["image_attachment_foreign_denied"] = True
        if rejected_marker in fresh_body:
            raise AssertionError("the rejected extension inquiry was unexpectedly stored in the native thread")
        stage = result["stage"] = "assignment_lookup"
        assignment_url = generated_support_assignment_link(admin, ctx.admin)
        visit(admin, assignment_url)
        initial_assignment_row = assignment_row(admin, thread_id)
        initial_cells = initial_assignment_row.find_elements(By.CSS_SELECTOR, "td")
        if len(initial_cells) < 5 or initial_cells[3].text.strip() != "미지정":
            raise AssertionError("new synthetic support thread already has an unexpected employee assignment")
        employee_selects = initial_assignment_row.find_elements(By.CSS_SELECTOR, "select[name='id_employee']")
        if len(employee_selects) != 1:
            raise AssertionError("same-shop support assignment did not expose one writable employee selector")
        employee_options = [
            (option.get_attribute("value") or "", option.text.strip())
            for option in Select(employee_selects[0]).options
        ]
        employee_options = [(value, name) for value, name in employee_options if value.isdigit() and int(value) > 0 and name]
        distinct_options = list(dict.fromkeys(employee_options))
        if len(distinct_options) < 2 or distinct_options[0][0] == distinct_options[1][0]:
            raise AssertionError("isolated same-shop support fixture needs two active employee choices for reassignment")
        first_employee_id, first_employee_name = distinct_options[0]
        second_employee_id, second_employee_name = distinct_options[1]

        stage = result["stage"] = "assignment_create"
        assign_thread(admin, thread_id, first_employee_id)
        result["assignment_created"] = True
        admin.save_screenshot(str(ctx.artifact_dir / "customer-support-assignment-created.png"))
        visit(admin, assignment_url)
        if selected_assignment_employee(admin, thread_id) != first_employee_id:
            raise AssertionError("fresh support assignment GET did not persist the first employee")

        stage = result["stage"] = "assignment_reassign"
        assign_thread(admin, thread_id, second_employee_id)
        result["assignment_reassigned"] = True
        visit(admin, assignment_url)
        if selected_assignment_employee(admin, thread_id) != second_employee_id:
            raise AssertionError("fresh support assignment GET did not persist the reassigned employee")

        stage = result["stage"] = "assignment_history_readback"
        history_url = assignment_history_link(admin, thread_id, ctx.admin)
        visit(admin, history_url)
        assert_assignment_history(admin, thread_id, first_employee_name, second_employee_name)
        result["assignment_actor_history"] = True
        admin.save_screenshot(str(ctx.artifact_dir / "customer-support-assignment-history.png"))

        stage = result["stage"] = "limited_staff_denial"
        limited = new_driver()
        admin_login(limited, ctx, ctx.view_only_email)
        limited_assignment_target = employee_scoped_legacy_controller_url(
            limited, "AdminKuraneaSupportAssignments", ctx.admin
        )
        limited_target = employee_scoped_thread_url(limited, thread_view_url, ctx.admin)
        visit(limited, limited_target)
        limited_body = limited.find_element(By.TAG_NAME, "body").text
        if limited.find_elements(By.CSS_SELECTOR, customer_thread_content_selector(thread_route_kind)) or buyer_marker in limited_body or private_marker in limited_body:
            raise AssertionError("limited-privilege employee could view a protected customer support thread")
        result["limited_employee_denied"] = True

        stage = result["stage"] = "assignment_limited_denial"
        visit(limited, limited_assignment_target)
        denied_assignment_body = limited.find_element(By.TAG_NAME, "body").text
        visible_thread_row = any(
            (cells := row.find_elements(By.CSS_SELECTOR, "td"))
            and cells[0].text.strip() == str(thread_id)
            for row in limited.find_elements(By.CSS_SELECTOR, ".table tbody tr")
        )
        if (
            "고객 문의 담당자 지정" in denied_assignment_body or visible_thread_row
            or limited.find_elements(By.CSS_SELECTOR, "form select[name='id_employee']")
            or buyer_marker in denied_assignment_body or private_marker in denied_assignment_body
        ):
            raise AssertionError("limited-privilege employee could view or modify support assignment data")
        result["assignment_limited_employee_denied"] = True
        result["status"] = "success"
        result["stage"] = "complete"
        print("PASS: native order-linked support inquiry, attachment, private note, reply, status, and access gates verified")
    except Exception as error:
        result["exception_type"] = type(error).__name__ if type(error).__name__ in {
            "AssertionError", "TimeoutException", "ValueError", "RuntimeError", "URLError", "OSError",
            "StaleElementReferenceException", "ElementClickInterceptedException", "NoSuchElementException",
        } else "OtherError"
        contact_status = result.get("contact_document_status")
        if type(contact_status) is not int or not 100 <= contact_status <= 599:
            contact_status = "unavailable"
        print(
            f"FAIL: isolated customer support QA; stage={stage}; exception={result['exception_type']}; "
            f"browser_substage={result['browser_substage']}; "
            f"contact_status={contact_status}; "
            f"support_denial_status={result['support_denial_status'] or 'unavailable'}; "
            f"support_denial_form_count={result['support_denial_form_count']}; "
            f"support_denial_redirected={str(result['support_denial_redirected']).lower()}; "
            f"support_denial_same_origin={str(result['support_denial_same_origin']).lower()}; "
            f"admin_route_candidates={result['customer_service_route_candidate_count']}; "
            f"admin_route_safe={result['customer_service_route_safe_count']}; "
            f"admin_route_modern={result['customer_service_route_modern_count']}; "
            f"admin_route_legacy={result['customer_service_route_legacy_count']}; "
            f"admin_route_invalid={result['customer_service_route_invalid_count']}; "
            f"admin_thread_message_marker_present={str(result['admin_thread_message_marker_present']).lower()}; "
            f"admin_thread_order_association_present={str(result['admin_thread_order_association_present']).lower()}; "
            f"same_origin={str(result['contact_same_origin']).lower()}; "
            f"native_route={str(result['contact_native_route']).lower()}; "
            f"form_count={result['contact_form_count']}; "
            f"form_visible={str(result['contact_form_visible']).lower()}",
            file=sys.stderr,
        )
        try:
            target = ctx.artifact_dir / "customer-support-browser-result.json"
            write_result(target, result)
        except Exception:
            pass
        raise RuntimeError("isolated customer support browser acceptance failed") from None
    finally:
        for fixture_file in (attachment_file, image_file, rejected_file):
            if fixture_file is not None:
                try:
                    fixture_file.unlink(missing_ok=True)
                except OSError:
                    pass
        if download_dir is not None:
            try:
                for child in download_dir.iterdir():
                    if child.is_file():
                        child.unlink()
                download_dir.rmdir()
            except OSError:
                pass
        for browser in (limited, foreign, admin, customer):
            if browser is not None:
                try:
                    browser.quit()
                except Exception:
                    pass
        if result.get("status") == "success":
            write_result(ctx.artifact_dir / "customer-support-browser-result.json", result)


if __name__ == "__main__":
    run()
