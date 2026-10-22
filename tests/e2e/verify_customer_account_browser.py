#!/usr/bin/env python3
"""Exercise native customer account flows in an isolated PrestaShop CI shop."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from selenium import webdriver
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait


BASE = os.environ["SHOP_BASE_URL"].rstrip("/")
MAILPIT_API = os.environ["MAILPIT_API_URL"].rstrip("/")
DEST = Path(os.environ["QA_ARTIFACT_DIR"])
OFFICIAL_LOGO = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "brand"
    / "ordenowa"
    / "official_originals"
    / "ORDENOWA-logo.png"
)
RUN_ID = re.sub(r"[^0-9]", "", os.environ["GITHUB_RUN_ID"])
RUN_ATTEMPT = re.sub(r"[^0-9]", "", os.environ["GITHUB_RUN_ATTEMPT"])
DEST.mkdir(parents=True, exist_ok=True)

KOREAN_EMAIL_ACCESSIBLE_NAME = re.compile(
    r"(?:이메일|전자\s*우편|메일\s*주소)", re.IGNORECASE
)
USER_ID_LOOKUP_ACCESSIBLE_NAME = re.compile(
    r"(?:아이디|사용자\s*id|user\s*id|username)", re.IGNORECASE
)
PASSWORD_RESET_ACCESSIBLE_NAME = re.compile(r"(?:비밀번호|암호|password)", re.IGNORECASE)


class AnchorLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.hrefs.append(html.unescape(href))


def request_json(url: str) -> dict:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=5) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("unexpected mail capture response")
    return value


def request_bytes(url: str) -> bytes:
    request = Request(url, headers={"Accept": "*/*"})
    with urlopen(request, timeout=10) as response:
        return response.read()


def message_recipients(message: dict) -> set[str]:
    recipients = message.get("To", [])
    if isinstance(recipients, dict):
        recipients = [recipients]
    if isinstance(recipients, str):
        recipients = [recipients]
    result = set()
    for recipient in recipients if isinstance(recipients, list) else []:
        address = recipient.get("Address", "") if isinstance(recipient, dict) else recipient
        if isinstance(address, str):
            result.add(address.strip().lower())
    return result


def reset_link_for(email_address: str, timeout_seconds: int = 90) -> tuple[str, dict]:
    deadline = time.monotonic() + timeout_seconds
    base_location = urlparse(BASE)
    while time.monotonic() < deadline:
        try:
            listing = request_json(f"{MAILPIT_API}/api/v1/messages?{urlencode({'start': 0, 'limit': 100})}")
            for message in listing.get("messages", []):
                if not isinstance(message, dict) or email_address.lower() not in message_recipients(message):
                    continue
                message_id = message.get("ID") or message.get("Id")
                if not isinstance(message_id, str) or not message_id:
                    continue
                detail = request_json(f"{MAILPIT_API}/api/v1/message/{quote(message_id, safe='')}")
                link_parser = AnchorLinks()
                link_parser.feed(str(detail.get("HTML") or ""))
                candidates = link_parser.hrefs + re.findall(
                    r"https?://[^\s<>\"']+", str(detail.get("Text") or "")
                )
                for candidate in candidates:
                    candidate = html.unescape(candidate).rstrip(".,);]")
                    reset_url = urljoin(BASE + "/", candidate)
                    parsed = urlparse(reset_url)
                    query = {key.lower(): values for key, values in parse_qs(parsed.query).items()}
                    has_token = "token" in query or "reset_token" in query
                    is_password_route = "password" in parsed.path.lower() or query.get("controller") == ["password"]
                    matches_base_origin = (
                        parsed.scheme == base_location.scheme
                        and parsed.hostname == base_location.hostname
                        and parsed.port == base_location.port
                    )
                    if matches_base_origin and has_token and is_password_route:
                        return reset_url, detail
        except (OSError, URLError, ValueError, json.JSONDecodeError):
            pass
        time.sleep(0.5)
    raise TimeoutException("password reset email did not arrive in the isolated mailbox")


def visible(driver: webdriver.Chrome, selector: str):
    return WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))


def password_reset_link_snapshot(driver: webdriver.Chrome) -> dict[str, object]:
    """Capture safe link and document facts without retaining raw URL values."""
    try:
        snapshot = driver.execute_script(
            """
            const form = document.querySelector('#login-form');
            const anchors = [...(form?.querySelectorAll('a') || [])];
            const link = anchors.find(anchor => anchor.hasAttribute('href')) || anchors[0] || null;
            const navigation = performance.getEntriesByType('navigation')[0];
            const style = link ? window.getComputedStyle(link) : null;
            const clientRectCount = link ? link.getClientRects().length : 0;
            const visible = Boolean(
              style && clientRectCount > 0 && style.display !== 'none' &&
              style.visibility !== 'hidden' && Number(style.opacity) > 0
            );
            return {
              document_language: document.documentElement?.getAttribute('lang') || '',
              ready_state: document.readyState || '',
              anchor_count: anchors.length,
              href_present: Boolean(link && link.hasAttribute('href') && link.getAttribute('href')),
              href: link?.getAttribute('href') || '',
              visible,
              client_rect_count: clientRectCount,
              computed_display: style?.display || '',
              computed_visibility: style?.visibility || '',
              computed_opacity: style?.opacity || '',
              aria_label: link?.getAttribute('aria-label') || '',
              text: (link?.innerText || link?.textContent || '').replace(/\\s+/g, ' ').trim(),
              navigation_type: navigation?.type || '',
              navigation_redirect_count: Number.isInteger(navigation?.redirectCount) ? navigation.redirectCount : 0,
              navigation_response_end_ms: Number.isFinite(navigation?.responseEnd) ? Math.round(navigation.responseEnd) : 0,
              navigation_dom_interactive_ms: Number.isFinite(navigation?.domInteractive) ? Math.round(navigation.domInteractive) : 0,
              navigation_load_event_end_ms: Number.isFinite(navigation?.loadEventEnd) ? Math.round(navigation.loadEventEnd) : 0
            };
            """
        )
    except Exception as error:
        return {"snapshot_error_type": type(error).__name__}

    if not isinstance(snapshot, dict):
        return {"snapshot_error_type": "InvalidSnapshot"}

    href = snapshot.get("href")
    text = snapshot.get("text")
    aria_label = snapshot.get("aria_label")
    raw_text = text if isinstance(text, str) else ""
    raw_aria_label = aria_label if isinstance(aria_label, str) else ""
    computed_display = snapshot.get("computed_display")
    computed_visibility = snapshot.get("computed_visibility")
    computed_opacity = snapshot.get("computed_opacity")
    return {
        "document_language": safe_diagnostic_name(snapshot.get("document_language")),
        "ready_state": safe_diagnostic_name(snapshot.get("ready_state")),
        "anchor_count": min(snapshot.get("anchor_count", 0), 20)
        if isinstance(snapshot.get("anchor_count"), int)
        else 0,
        "href_present": snapshot.get("href_present") is True,
        "href_metadata": safe_url_metadata(urljoin(driver.current_url, href))
        if isinstance(href, str) and href
        else {},
        "visible": snapshot.get("visible") is True,
        "client_rect_count": min(snapshot.get("client_rect_count", 0), 20)
        if isinstance(snapshot.get("client_rect_count"), int)
        else 0,
        "computed_display": computed_display
        if isinstance(computed_display, str)
        and computed_display in {"block", "contents", "flex", "grid", "inline", "inline-block", "inline-flex", "none"}
        else "other",
        "computed_visibility": computed_visibility
        if isinstance(computed_visibility, str)
        and computed_visibility in {"collapse", "hidden", "visible"}
        else "other",
        "computed_opacity_zero": computed_opacity == "0",
        "aria_label_text_length": min(len(raw_aria_label), 200),
        "aria_label_identifies_password_reset": bool(PASSWORD_RESET_ACCESSIBLE_NAME.search(raw_aria_label)),
        "aria_label_implies_user_id_lookup": bool(USER_ID_LOOKUP_ACCESSIBLE_NAME.search(raw_aria_label)),
        "text_length": min(len(raw_text), 200),
        "text_identifies_password_reset": bool(PASSWORD_RESET_ACCESSIBLE_NAME.search(raw_text)),
        "text_implies_user_id_lookup": bool(USER_ID_LOOKUP_ACCESSIBLE_NAME.search(raw_text)),
        "navigation_type": safe_diagnostic_name(snapshot.get("navigation_type")),
        "navigation_redirect_count": min(snapshot.get("navigation_redirect_count", 0), 20)
        if isinstance(snapshot.get("navigation_redirect_count"), int)
        else 0,
        "navigation_response_end_ms": min(snapshot.get("navigation_response_end_ms", 0), 300_000)
        if isinstance(snapshot.get("navigation_response_end_ms"), int)
        else 0,
        "navigation_dom_interactive_ms": min(snapshot.get("navigation_dom_interactive_ms", 0), 300_000)
        if isinstance(snapshot.get("navigation_dom_interactive_ms"), int)
        else 0,
        "navigation_load_event_end_ms": min(snapshot.get("navigation_load_event_end_ms", 0), 300_000)
        if isinstance(snapshot.get("navigation_load_event_end_ms"), int)
        else 0,
    }


def install_reset_link_navigation_observer(driver: webdriver.Chrome) -> None:
    driver.execute_script(
        """
        const key = '__ordenowaKoreanLoginNavigation';
        try {
          sessionStorage.removeItem(key);
          const allowedKeys = new Set(['back', 'controller', 'id_lang', 'isolang', 'lang']);
          const capture = (eventName, persisted = false) => {
            try {
              const navigation = performance.getEntriesByType('navigation')[0];
              const event = {
                event: eventName,
                elapsed_ms: Math.round(performance.now()),
                pathname: window.location.pathname,
                query_key_names: [...new URLSearchParams(window.location.search).keys()]
                  .filter(name => allowedKeys.has(name)).slice(0, 8),
                document_language: document.documentElement?.getAttribute('lang') || '',
                ready_state: document.readyState || '',
                navigation_type: navigation?.type || '',
                navigation_redirect_count: Number.isInteger(navigation?.redirectCount) ? navigation.redirectCount : 0,
                navigation_response_end_ms: Number.isFinite(navigation?.responseEnd) ? Math.round(navigation.responseEnd) : 0,
                persisted: Boolean(persisted)
              };
              const events = JSON.parse(sessionStorage.getItem(key) || '[]');
              events.push(event);
              sessionStorage.setItem(key, JSON.stringify(events.slice(-4)));
            } catch (_) {}
          };
          window.addEventListener('beforeunload', () => capture('beforeunload'), { once: true });
          window.addEventListener('pagehide', event => capture('pagehide', Boolean(event.persisted)), { once: true });
        } catch (_) {}
        """
    )


def reset_link_navigation_timeline(driver: webdriver.Chrome) -> list[dict[str, object]]:
    try:
        raw_events = driver.execute_script(
            "return sessionStorage.getItem('__ordenowaKoreanLoginNavigation') || '[]';"
        )
        events = json.loads(raw_events) if isinstance(raw_events, str) else []
    except Exception:
        return []
    if not isinstance(events, list):
        return []

    allowed_events = {"beforeunload", "pagehide"}
    allowed_query_keys = {"back", "controller", "id_lang", "isolang", "lang"}
    safe_events: list[dict[str, object]] = []
    for event in events[-4:]:
        if not isinstance(event, dict) or event.get("event") not in allowed_events:
            continue
        pathname = event.get("pathname")
        if not isinstance(pathname, str):
            continue
        route_metadata = safe_url_metadata(urljoin(BASE + "/", pathname))
        query_keys = event.get("query_key_names")
        safe_query_keys = sorted(
            {key for key in query_keys if isinstance(key, str)} & allowed_query_keys
        ) if isinstance(query_keys, list) else []
        route_metadata["query_key_names"] = safe_query_keys
        route_metadata["id_lang_present"] = "id_lang" in safe_query_keys
        route_metadata["isolang_present"] = "isolang" in safe_query_keys
        route_metadata["controller_present"] = "controller" in safe_query_keys
        route_metadata["back_present"] = "back" in safe_query_keys
        safe_events.append(
            {
                "event": event["event"],
                "elapsed_ms": min(event.get("elapsed_ms", 0), 300_000)
                if isinstance(event.get("elapsed_ms"), int)
                else 0,
                "route_metadata": route_metadata,
                "document_language": safe_diagnostic_name(event.get("document_language")),
                "ready_state": safe_diagnostic_name(event.get("ready_state")),
                "navigation_type": safe_diagnostic_name(event.get("navigation_type")),
                "navigation_redirect_count": min(event.get("navigation_redirect_count", 0), 20)
                if isinstance(event.get("navigation_redirect_count"), int)
                else 0,
                "navigation_response_end_ms": min(event.get("navigation_response_end_ms", 0), 300_000)
                if isinstance(event.get("navigation_response_end_ms"), int)
                else 0,
                "persisted": event.get("persisted") is True,
            }
        )
    return safe_events


def assert_korean_email_login_form(driver: webdriver.Chrome, state: dict[str, object]) -> None:
    # Use PrestaShop's generated language and account links. The Korean route
    # slug is installation metadata and must not be guessed as `/ko/login`.
    def mark_stage(name: str) -> None:
        state["stage"] = name
        state["stage_started_at"] = time.monotonic()

    mark_stage("korean_storefront_home")
    driver.get(f"{BASE}/")
    mark_stage("korean_language_selector")
    korean_language_option = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'select.js-language-selector option[data-iso-code="ko"]')
        )
    )
    korean_language_href = korean_language_option.get_attribute("value") or ""
    if not korean_language_href:
        raise AssertionError("the PrestaShop language selector has no Korean destination")
    korean_language_url = urljoin(driver.current_url, korean_language_href)
    korean_language_location = urlparse(korean_language_url)
    base_location = urlparse(BASE)
    if (
        korean_language_location.scheme != base_location.scheme
        or korean_language_location.hostname != base_location.hostname
        or korean_language_location.port != base_location.port
    ):
        raise AssertionError("the Korean language selector changed the isolated shop origin")
    state["language_url_metadata"] = safe_url_metadata(korean_language_url)
    mark_stage("korean_language_destination")
    driver.get(korean_language_url)

    document_language = (driver.find_element(By.TAG_NAME, "html").get_attribute("lang") or "").lower()
    state["language_destination_document_language"] = safe_diagnostic_name(document_language)
    state["language_destination_url_metadata"] = safe_url_metadata(driver.current_url)
    if not document_language.startswith("ko"):
        raise AssertionError("the generated Korean language destination did not render Korean")

    mark_stage("korean_sign_in_link")
    sign_in_links = driver.find_elements(
        By.CSS_SELECTOR,
        '#_desktop_ps_customersignin a[href], #_mobile_ps_customersignin a[href]',
    )
    sign_in_href = next(
        (link.get_attribute("href") for link in sign_in_links if link.get_attribute("href")),
        "",
    )
    if not sign_in_href:
        raise AssertionError("the Korean storefront has no generated customer sign-in link")
    login_url = urljoin(driver.current_url, sign_in_href)
    login_location = urlparse(login_url)
    if (
        login_location.scheme != base_location.scheme
        or login_location.hostname != base_location.hostname
        or login_location.port != base_location.port
    ):
        raise AssertionError("the customer sign-in link changed the isolated shop origin")
    state["sign_in_url_metadata"] = safe_url_metadata(login_url)
    mark_stage("korean_login_page_navigation")
    clear_document_navigation_events(driver)
    login_navigation_started_at = time.monotonic()
    driver.get(login_url)
    login_navigation_completed_at = time.monotonic()
    state["login_navigation_started_at"] = login_navigation_started_at
    state["login_navigation_completed_at"] = login_navigation_completed_at
    state["login_navigation_elapsed_ms"] = min(
        300_000, max(0, int((login_navigation_completed_at - login_navigation_started_at) * 1000))
    )
    state["login_navigation_document_language"] = safe_diagnostic_name(
        (driver.find_element(By.TAG_NAME, "html").get_attribute("lang") or "").lower()
    )
    state["login_navigation_url_metadata"] = safe_url_metadata(driver.current_url)

    mark_stage("korean_login_form")
    visible(driver, "#login-form")
    state["login_form_document_language"] = safe_diagnostic_name(
        (driver.find_element(By.TAG_NAME, "html").get_attribute("lang") or "").lower()
    )
    state["login_form_url_metadata"] = safe_url_metadata(driver.current_url)
    mark_stage("korean_email_field")
    email_field = visible(driver, '#login-form input[type="email"]')
    if email_field.get_attribute("name") != "email":
        raise AssertionError("Korean customer login does not submit the email field")
    if email_field.get_attribute("type") != "email":
        raise AssertionError("Korean customer login is not email-based")

    document_language = (driver.find_element(By.TAG_NAME, "html").get_attribute("lang") or "").lower()
    if not document_language.startswith("ko"):
        raise AssertionError("the generated sign-in destination did not preserve Korean")

    email_field_id = email_field.get_attribute("id") or ""
    associated_label = next(
        (
            label
            for label in driver.find_elements(By.CSS_SELECTOR, "#login-form label[for]")
            if label.get_attribute("for") == email_field_id
        ),
        None,
    )
    aria_label = " ".join((email_field.get_attribute("aria-label") or "").split())
    visible_label = (
        " ".join((associated_label.text or "").split())
        if associated_label is not None and associated_label.is_displayed()
        else ""
    )
    email_accessible_name = aria_label or visible_label
    if not KOREAN_EMAIL_ACCESSIBLE_NAME.search(email_accessible_name):
        raise AssertionError("Korean login email field has no accessible label that identifies email")
    if USER_ID_LOOKUP_ACCESSIBLE_NAME.search(email_accessible_name):
        raise AssertionError("Korean login field's accessible label implies a separate user ID login")

    state["email_label_document_language"] = safe_diagnostic_name(
        (driver.find_element(By.TAG_NAME, "html").get_attribute("lang") or "").lower()
    )
    state["email_label_assertion_passed"] = True
    state["email_label_url_metadata"] = safe_url_metadata(driver.current_url)
    mark_stage("korean_password_reset_link")
    reset_wait_started_at = time.monotonic()
    reset_wait_start_url = driver.current_url
    state["reset_link_before_wait_url_metadata"] = safe_url_metadata(reset_wait_start_url)
    state["reset_link_before_wait_document_language"] = safe_diagnostic_name(
        (driver.find_element(By.TAG_NAME, "html").get_attribute("lang") or "").lower()
    )
    if isinstance(login_navigation_completed_at, float):
        state["login_navigation_to_reset_wait_elapsed_ms"] = min(
            300_000, max(0, int((reset_wait_started_at - login_navigation_completed_at) * 1000))
        )
    reset_link_snapshot = password_reset_link_snapshot(driver)
    state["reset_link_before_wait_anchor_count"] = reset_link_snapshot.get("anchor_count", 0)
    state["reset_link_before_wait_href_present"] = reset_link_snapshot.get("href_present", False)
    state["reset_link_before_wait_visible"] = reset_link_snapshot.get("visible", False)
    state["reset_link_before_wait_client_rect_count"] = reset_link_snapshot.get("client_rect_count", 0)
    state["reset_link_before_wait_computed_display"] = reset_link_snapshot.get("computed_display", "other")
    state["reset_link_before_wait_computed_visibility"] = reset_link_snapshot.get(
        "computed_visibility", "other"
    )
    state["reset_link_before_wait_computed_opacity_zero"] = reset_link_snapshot.get(
        "computed_opacity_zero", False
    )
    state["reset_link_before_wait_aria_label_text_length"] = reset_link_snapshot.get(
        "aria_label_text_length", 0
    )
    state["reset_link_before_wait_aria_label_identifies_password_reset"] = reset_link_snapshot.get(
        "aria_label_identifies_password_reset", False
    )
    state["reset_link_before_wait_aria_label_implies_user_id_lookup"] = reset_link_snapshot.get(
        "aria_label_implies_user_id_lookup", False
    )
    state["reset_link_before_wait_text_length"] = reset_link_snapshot.get("text_length", 0)
    state["reset_link_before_wait_text_identifies_password_reset"] = reset_link_snapshot.get(
        "text_identifies_password_reset", False
    )
    state["reset_link_before_wait_text_implies_user_id_lookup"] = reset_link_snapshot.get(
        "text_implies_user_id_lookup", False
    )
    state["reset_link_before_wait_href_metadata"] = reset_link_snapshot.get("href_metadata", {})
    state["reset_link_before_wait_navigation"] = {
        key: reset_link_snapshot[key]
        for key in (
            "ready_state",
            "navigation_type",
            "navigation_redirect_count",
            "navigation_response_end_ms",
            "navigation_dom_interactive_ms",
            "navigation_load_event_end_ms",
        )
        if key in reset_link_snapshot
    }
    install_reset_link_navigation_observer(driver)

    def reset_link_ready(browser: webdriver.Chrome):
        try:
            observed_url = browser.current_url
            if observed_url != reset_wait_start_url and state.get("reset_wait_navigation_elapsed_ms") is None:
                state["reset_wait_navigation_elapsed_ms"] = min(
                    300_000, max(0, int((time.monotonic() - reset_wait_started_at) * 1000))
                )
                state["reset_wait_navigation_url_metadata"] = safe_url_metadata(observed_url)
                state["reset_wait_navigation_document_language"] = safe_diagnostic_name(
                    (browser.find_element(By.TAG_NAME, "html").get_attribute("lang") or "").lower()
                )
                state["reset_link_navigation_timeline"] = reset_link_navigation_timeline(browser)
                state["document_navigation_events"] = document_navigation_events(browser)
            for anchor in browser.find_elements(By.CSS_SELECTOR, "#login-form a[href]"):
                if anchor.is_displayed():
                    return anchor
        except Exception:
            return False
        return False

    state["reset_wait_navigation_elapsed_ms"] = None
    state["reset_wait_navigation_url_metadata"] = {}
    state["reset_wait_navigation_document_language"] = ""
    password_reset_link = WebDriverWait(driver, 30, poll_frequency=0.25).until(reset_link_ready)
    password_reset_name = " ".join(
        (
            (password_reset_link.get_attribute("aria-label") or "")
            + " "
            + (password_reset_link.text or "")
        ).split()
    )
    if not PASSWORD_RESET_ACCESSIBLE_NAME.search(password_reset_name):
        raise AssertionError("Korean login recovery link is not identified as password reset")
    if USER_ID_LOOKUP_ACCESSIBLE_NAME.search(password_reset_name):
        raise AssertionError("Korean login recovery link implies user ID lookup instead of password reset")


def emit_korean_login_diagnostics(driver: webdriver.Chrome, state: dict[str, object]) -> None:
    """Report the exact Korean login wait and sanitized page markers on failure."""
    diagnostics: dict[str, object] = {
        "stage": safe_diagnostic_name(state.get("stage", "")),
        "path": safe_same_origin_path(getattr(driver, "current_url", "")),
        "final_url_metadata": safe_url_metadata(getattr(driver, "current_url", "")),
        "document_language": "",
        "language_selector_count": 0,
        "korean_language_option_count": 0,
        "customer_sign_in_link_count": 0,
        "login_form_count": 0,
        "login_form_visible": False,
        "email_field_count": 0,
        "email_field_visible": False,
        "email_field_name_matches": False,
        "email_field_type_matches": False,
        "email_label_present": False,
        "password_reset_link_count": 0,
        "language_url_metadata": state.get("language_url_metadata", {}),
        "language_destination_document_language": state.get("language_destination_document_language", ""),
        "language_destination_url_metadata": state.get("language_destination_url_metadata", {}),
        "sign_in_url_metadata": state.get("sign_in_url_metadata", {}),
        "login_navigation_document_language": state.get("login_navigation_document_language", ""),
        "login_navigation_url_metadata": state.get("login_navigation_url_metadata", {}),
        "login_form_document_language": state.get("login_form_document_language", ""),
        "login_form_url_metadata": state.get("login_form_url_metadata", {}),
        "email_label_document_language": state.get("email_label_document_language", ""),
        "email_label_assertion_passed": state.get("email_label_assertion_passed", False),
        "email_label_url_metadata": state.get("email_label_url_metadata", {}),
        "failed_stage_elapsed_ms": 0,
        "reset_link_before_wait_anchor_count": state.get("reset_link_before_wait_anchor_count", 0),
        "reset_link_before_wait_href_present": state.get("reset_link_before_wait_href_present", False),
        "reset_link_before_wait_visible": state.get("reset_link_before_wait_visible", False),
        "reset_link_before_wait_client_rect_count": state.get("reset_link_before_wait_client_rect_count", 0),
        "reset_link_before_wait_computed_display": state.get("reset_link_before_wait_computed_display", "other"),
        "reset_link_before_wait_computed_visibility": state.get("reset_link_before_wait_computed_visibility", "other"),
        "reset_link_before_wait_computed_opacity_zero": state.get(
            "reset_link_before_wait_computed_opacity_zero", False
        ),
        "reset_link_before_wait_aria_label_text_length": state.get(
            "reset_link_before_wait_aria_label_text_length", 0
        ),
        "reset_link_before_wait_aria_label_identifies_password_reset": state.get(
            "reset_link_before_wait_aria_label_identifies_password_reset", False
        ),
        "reset_link_before_wait_aria_label_implies_user_id_lookup": state.get(
            "reset_link_before_wait_aria_label_implies_user_id_lookup", False
        ),
        "reset_link_before_wait_text_length": state.get("reset_link_before_wait_text_length", 0),
        "reset_link_before_wait_text_identifies_password_reset": state.get(
            "reset_link_before_wait_text_identifies_password_reset", False
        ),
        "reset_link_before_wait_text_implies_user_id_lookup": state.get(
            "reset_link_before_wait_text_implies_user_id_lookup", False
        ),
        "reset_link_before_wait_url_metadata": state.get("reset_link_before_wait_url_metadata", {}),
        "reset_link_before_wait_href_metadata": state.get("reset_link_before_wait_href_metadata", {}),
        "reset_link_before_wait_navigation": state.get("reset_link_before_wait_navigation", {}),
        "reset_wait_navigation_elapsed_ms": state.get("reset_wait_navigation_elapsed_ms"),
        "reset_wait_navigation_url_metadata": state.get("reset_wait_navigation_url_metadata", {}),
        "reset_wait_navigation_document_language": state.get("reset_wait_navigation_document_language", ""),
        "reset_link_navigation_timeline": state.get("reset_link_navigation_timeline", []),
        "document_navigation_events": state.get("document_navigation_events", []),
    }
    stage_started_at = state.get("stage_started_at")
    if isinstance(stage_started_at, (int, float)):
        diagnostics["failed_stage_elapsed_ms"] = min(
            300_000, max(0, int((time.monotonic() - stage_started_at) * 1000))
        )
    if not diagnostics["reset_link_navigation_timeline"]:
        diagnostics["reset_link_navigation_timeline"] = reset_link_navigation_timeline(driver)
    if not diagnostics["document_navigation_events"]:
        diagnostics["document_navigation_events"] = document_navigation_events(driver)
    try:
        page_state = driver.execute_script(
            """
            const visible = element => Boolean(element && element.getClientRects().length);
            const form = document.querySelector('#login-form');
            const email = form?.querySelector('input[type=email]');
            const emailId = email?.id || '';
            const hasEmailLabel = Boolean(
              email?.getAttribute('aria-label') ||
              [...(form?.querySelectorAll('label[for]') || [])]
                .some(label => label.getAttribute('for') === emailId && label.innerText.trim())
            );
            return {
              document_language: document.documentElement?.getAttribute('lang') || '',
              language_selector_count: document.querySelectorAll('select.js-language-selector').length,
              korean_language_option_count: document.querySelectorAll('select.js-language-selector option[data-iso-code=ko]').length,
              customer_sign_in_link_count: document.querySelectorAll('#_desktop_ps_customersignin a[href], #_mobile_ps_customersignin a[href]').length,
              login_form_count: document.querySelectorAll('#login-form').length,
              login_form_visible: visible(form),
              email_field_count: form?.querySelectorAll('input[type=email]').length || 0,
              email_field_visible: visible(email),
              email_field_name_matches: email?.getAttribute('name') === 'email',
              email_field_type_matches: email?.getAttribute('type') === 'email',
              email_label_present: hasEmailLabel,
              password_reset_link_count: form?.querySelectorAll('a[href]').length || 0
            };
            """
        )
        if isinstance(page_state, dict):
            for key in (
                "document_language",
                "language_selector_count",
                "korean_language_option_count",
                "customer_sign_in_link_count",
                "login_form_count",
                "login_form_visible",
                "email_field_count",
                "email_field_visible",
                "email_field_name_matches",
                "email_field_type_matches",
                "email_label_present",
                "password_reset_link_count",
            ):
                value = page_state.get(key)
                if key == "document_language":
                    diagnostics[key] = re.sub(r"[^A-Za-z0-9-]", "", str(value or ""))[:12]
                elif key.endswith("_count"):
                    diagnostics[key] = value if isinstance(value, int) and not isinstance(value, bool) else 0
                else:
                    diagnostics[key] = value if isinstance(value, bool) else False
    except Exception as error:
        diagnostics["diagnostic_error_type"] = type(error).__name__

    state_json = json.dumps(diagnostics, ensure_ascii=True, sort_keys=True)
    print("ORDENOWA_KOREAN_LOGIN_SAFE_STATE=" + state_json, file=sys.stderr)
    annotation = state_json.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::error title=Korean customer login state::{annotation}", file=sys.stderr)


def click_centered(driver: webdriver.Chrome, element) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element)
    WebDriverWait(driver, 30).until(EC.element_to_be_clickable(element))
    WebDriverWait(driver, 10).until(
        lambda browser: browser.execute_script(
            """
            const element = arguments[0];
            const rect = element.getBoundingClientRect();
            const target = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
            return Boolean(target && (target === element || element.contains(target)));
            """,
            element,
        )
    )
    element.click()


def wait_for_registration_success(driver: webdriver.Chrome) -> None:
    result_page = WebDriverWait(driver, 30).until(
        lambda browser: browser.execute_script(
            """
            const accountLink = document.getElementById('identity_main_link');
            if (accountLink && accountLink.getClientRects().length) return 'account';
            return document.getElementById('userMenuButton') ? 'header' : false;
            """
        )
    )
    if result_page == "header":
        account_link, _ = my_account_link_from_header(driver)
        click_centered(driver, account_link)
        visible(driver, "#identity_main_link")


def my_account_link_from_header(driver: webdriver.Chrome, *, open_menu: bool = True):
    """Resolve the canonical My Page link, opening its menu only when needed for interaction."""
    account_selector = 'div.dropdown-menu[aria-labelledby="userMenuButton"] a[href]'
    if open_menu:
        button = visible(driver, "#userMenuButton")
        if button.get_attribute("aria-expanded") != "true":
            click_centered(driver, button)
        account_link = visible(driver, account_selector)
    else:
        # The hidden dropdown anchor is still rendered, so logout can read its URL
        # without opening an overlay above the separate My Page signout link.
        account_link = driver.find_element(By.CSS_SELECTOR, account_selector)

    href = account_link.get_attribute("href") or ""
    account_url = urljoin(driver.current_url, href)
    account_location = urlparse(account_url)
    base_location = urlparse(BASE)
    if (
        account_location.scheme != base_location.scheme
        or account_location.hostname != base_location.hostname
        or account_location.port != base_location.port
    ):
        raise AssertionError("the authenticated My Page link changed the base shop origin")

    return account_link, account_url


def assert_canonical_static_route(driver: webdriver.Chrome, route_slug: str) -> None:
    actual = urlparse(driver.current_url)
    base = urlparse(BASE)
    same_origin = (
        actual.scheme.lower(), actual.hostname, actual.port
    ) == (
        base.scheme.lower(), base.hostname, base.port
    )
    base_path = base.path.rstrip("/")
    expected_path = f"{base_path}/{route_slug}" or f"/{route_slug}"
    actual_path = unquote(actual.path, errors="strict").rstrip("/")
    if not same_origin or actual_path != expected_path:
        raise AssertionError(f"the {route_slug} page did not resolve to its canonical friendly route")


def set_registration_control(control: dict[str, str], name: str, field_type: str) -> None:
    control["name"] = re.sub(r"[^A-Za-z0-9_.\[\]-]", "_", name)[:80]
    control["type"] = re.sub(r"[^A-Za-z0-9_-]", "_", field_type)[:40]


def safe_diagnostic_name(value: object, *, field_type: bool = False) -> str:
    if not isinstance(value, str):
        return ""
    pattern = r"[^A-Za-z0-9_-]" if field_type else r"[^A-Za-z0-9_.\[\]-]"
    return re.sub(pattern, "_", value)[:80]


def safe_diagnostic_boolean(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def safe_same_origin_path(value: object) -> str:
    if not isinstance(value, str):
        return "/<unknown>"
    try:
        location = urlparse(value)
        base_location = urlparse(BASE)
        same_origin = (
            location.scheme == base_location.scheme
            and location.hostname == base_location.hostname
            and location.port == base_location.port
        )
        if not same_origin:
            return "/<other-origin>"
        path = unquote(location.path or "/")
    except (TypeError, ValueError):
        return "/<unknown>"

    if len(path) > 160:
        return "/<long-path>"
    known_static_segments = {
        "index.php",
        "ja",
        "ko",
        "en",
        "authentication",
        "login",
        "register",
        "registration",
        "identity",
        "order",
        "password",
        "password-reset",
        "history",
    }
    safe_segments = []
    for segment in path.split("/"):
        if not segment:
            safe_segments.append("")
        elif segment.lower() in known_static_segments:
            safe_segments.append(segment.lower())
        else:
            safe_segments.append("<redacted>")
    return "/".join(safe_segments)[:160] or "/"


def safe_url_metadata(value: object) -> dict[str, object]:
    """Return route shape without exposing URL values, tokens, or customer data."""
    metadata: dict[str, object] = {
        "same_origin": False,
        "path": "/<unknown>",
        "path_length": 0,
        "path_has_non_ascii": False,
        "path_has_ascii_letters": False,
        "path_has_digits": False,
        "path_has_percent_escape": False,
        "path_segment_count": 0,
        "query_key_names": [],
        "id_lang_present": False,
        "isolang_present": False,
        "controller_present": False,
        "back_present": False,
    }
    if not isinstance(value, str):
        return metadata
    try:
        location = urlparse(value)
        base_location = urlparse(BASE)
        same_origin = (
            location.scheme.lower() == base_location.scheme.lower()
            and location.hostname == base_location.hostname
            and location.port == base_location.port
        )
        if not same_origin:
            return metadata
        raw_path = location.path or "/"
        decoded_path = unquote(raw_path)
        query_keys = set(parse_qs(location.query, keep_blank_values=True).keys())
    except (TypeError, ValueError):
        return metadata

    allowlisted_query_keys = {"back", "controller", "id_lang", "isolang", "lang"}
    metadata.update(
        {
            "same_origin": True,
            "path": safe_same_origin_path(value),
            "path_length": min(len(decoded_path), 1000),
            "path_has_non_ascii": any(ord(character) > 127 for character in decoded_path),
            "path_has_ascii_letters": bool(re.search(r"[A-Za-z]", decoded_path)),
            "path_has_digits": bool(re.search(r"[0-9]", decoded_path)),
            "path_has_percent_escape": bool(re.search(r"%[0-9A-Fa-f]{2}", raw_path)),
            "path_segment_count": len([part for part in decoded_path.split("/") if part]),
            "query_key_names": sorted(query_keys & allowlisted_query_keys),
            "id_lang_present": "id_lang" in query_keys,
            "isolang_present": "isolang" in query_keys,
            "controller_present": "controller" in query_keys,
            "back_present": "back" in query_keys,
        }
    )
    return metadata


def clear_document_navigation_events(driver: webdriver.Chrome) -> None:
    try:
        driver.get_log("performance")
    except Exception:
        pass


def document_navigation_events(driver: webdriver.Chrome) -> list[dict[str, object]]:
    """Summarize same-tab document requests and redirects without URL values."""
    try:
        entries = driver.get_log("performance")
    except Exception as error:
        return [{"diagnostic_error_type": type(error).__name__}]

    responses: dict[str, int] = {}
    decoded_entries: list[dict[str, object]] = []
    for entry in entries:
        try:
            envelope = json.loads(entry.get("message", "{}"))
            message = envelope.get("message", {}) if isinstance(envelope, dict) else {}
            if not isinstance(message, dict):
                continue
            params = message.get("params", {})
            if not isinstance(params, dict) or params.get("type") != "Document":
                continue
            if message.get("method") == "Network.responseReceived":
                response = params.get("response", {})
                request_id = params.get("requestId")
                status = response.get("status") if isinstance(response, dict) else None
                if isinstance(request_id, str) and isinstance(status, (int, float)):
                    responses[request_id] = int(status)
            decoded_entries.append(message)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue

    safe_events: list[dict[str, object]] = []
    for message in decoded_entries:
        if message.get("method") != "Network.requestWillBeSent":
            continue
        params = message.get("params", {})
        if not isinstance(params, dict):
            continue
        request = params.get("request", {})
        request_url = request.get("url") if isinstance(request, dict) else None
        if not isinstance(request_url, str):
            continue
        route_metadata = safe_url_metadata(request_url)
        redirect_response = params.get("redirectResponse")
        redirect_metadata = (
            safe_url_metadata(redirect_response.get("url"))
            if isinstance(redirect_response, dict)
            else None
        )
        if not route_metadata["same_origin"] and not (
            isinstance(redirect_metadata, dict) and redirect_metadata["same_origin"]
        ):
            continue
        request_id = params.get("requestId")
        redirect_status = (
            redirect_response.get("status")
            if isinstance(redirect_response, dict)
            else responses.get(request_id) if isinstance(request_id, str) else None
        )
        safe_events.append(
            {
                "event": "document_redirect" if isinstance(redirect_response, dict) else "document_request",
                "route_metadata": route_metadata,
                "redirect_from_metadata": redirect_metadata or {},
                "status_code": int(redirect_status)
                if isinstance(redirect_status, (int, float)) and 0 <= redirect_status <= 599
                else 0,
            }
        )
    return safe_events[-16:]


def safe_registration_path(value: object) -> str:
    if isinstance(value, str) and value in {"/", "/index.php"}:
        return value
    return "/<other>"


def emit_registration_diagnostics(
    driver: webdriver.Chrome,
    stage: str,
    control: dict[str, str],
) -> None:
    diagnostics: dict[str, object] = {
        "registration_stage": stage,
        "registration_control_name": control.get("name") or "",
        "registration_control_type": control.get("type") or "",
        "pathname": "",
    }
    try:
        diagnostics["pathname"] = urlparse(driver.current_url).path
    except Exception as error:
        diagnostics["pathname_error_type"] = type(error).__name__

    try:
        browser_diagnostics = driver.execute_script(
            r"""
            const form = document.querySelector('#customer-form');
            const isVisible = element => Boolean(element && element.getClientRects().length);
            const invalid = form ? [...form.querySelectorAll(':invalid')].filter(isVisible) : [];
            const email = form?.querySelector('input[name="email"]');
            const passwords = form ? [...form.querySelectorAll('input[type="password"]')] : [];
            const submit = form?.querySelector('button.form-control-submit');
            const registrationLink = document.querySelector('a[data-link-action="display-register-form"]');
            const userMenuButton = document.querySelector('#userMenuButton');
            let registrationTarget = null;
            if (registrationLink) {
              const rect = registrationLink.getBoundingClientRect();
              if (rect.width > 0 && rect.height > 0) {
                registrationTarget = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
              }
            }
            const registrationTargetClass = registrationTarget && typeof registrationTarget.className === 'string'
              ? registrationTarget.className.slice(0, 120)
              : '';
            const firstInvalid = invalid[0];
            const bodyText = document.body?.innerText || '';
            return {
              registration_stage: arguments[0],
              registration_control_name: arguments[1].name || '',
              registration_control_type: arguments[1].type || '',
              registration_form_visible: isVisible(form),
              registration_link_visible: isVisible(registrationLink),
              registration_center_unobstructed: Boolean(registrationTarget && (registrationTarget === registrationLink || registrationLink.contains(registrationTarget))),
              registration_center_target_tag: registrationTarget?.tagName.toLowerCase() || '',
              registration_center_target_id: registrationTarget?.id || '',
              registration_center_target_class: registrationTargetClass,
              identity_link_visible: isVisible(document.querySelector('#identity_main_link')),
              login_form_visible: isVisible(document.querySelector('#login-form')),
              header_user_menu_button_present: Boolean(userMenuButton),
              header_user_menu_button_visible: isVisible(userMenuButton),
              submit_button_visible: isVisible(submit),
              submit_button_enabled: Boolean(submit && !submit.disabled),
              registration_form_valid: Boolean(form && form.checkValidity()),
              visible_invalid_control_count: invalid.length,
              first_invalid_control_name: firstInvalid?.getAttribute('name') || '',
              first_invalid_control_type: firstInvalid?.getAttribute('type') || firstInvalid?.tagName.toLowerCase() || '',
              email_type: email?.getAttribute('type') || '',
              email_valid: Boolean(email && email.checkValidity()),
              password_control_count: passwords.length,
              password_controls_valid: passwords.length > 0 && passwords.every(field => field.checkValidity()),
              alert_visible: isVisible(document.querySelector('.alert, [role="alert"], .help-block.error')),
              account_error_marker: /(?:already registered|already exists|invalid|required|error|failed|오류|필수|이미 사용|잘못)/i.test(bodyText),
              pathname: window.location.pathname
            };
            """,
            stage,
            control,
        )
        if not isinstance(browser_diagnostics, dict):
            raise TypeError("browser diagnostics response was not an object")
        diagnostics.update(browser_diagnostics)
    except Exception as error:
        diagnostics["diagnostics_collection_error"] = type(error).__name__

        def safe_visible(selector: str) -> bool:
            try:
                return any(element.is_displayed() for element in driver.find_elements(By.CSS_SELECTOR, selector))
            except Exception:
                return False

        for field, selector in (
            ("registration_form_visible", "#customer-form"),
            ("registration_link_visible", 'a[data-link-action="display-register-form"]'),
            ("identity_link_visible", "#identity_main_link"),
            ("login_form_visible", "#login-form"),
            ("header_user_menu_button_visible", "#userMenuButton"),
            ("submit_button_visible", "#customer-form button.form-control-submit"),
            ("alert_visible", '.alert, [role="alert"], .help-block.error'),
        ):
            diagnostics[field] = safe_visible(selector)
        try:
            diagnostics["header_user_menu_button_present"] = bool(driver.find_elements(By.ID, "userMenuButton"))
        except Exception:
            diagnostics["header_user_menu_button_present"] = False

    diagnostics["pathname"] = safe_registration_path(diagnostics.get("pathname"))
    safe_path = diagnostics.get("pathname")
    safe_path = safe_path if safe_path in {"/", "/index.php"} else "/<other>"
    invalid_count = diagnostics.get("visible_invalid_control_count")
    safe_state: dict[str, object] = {
        "stage": safe_diagnostic_name(stage),
        "path": safe_path,
        "registration_form_visible": safe_diagnostic_boolean(diagnostics.get("registration_form_visible")),
        "registration_form_valid": safe_diagnostic_boolean(diagnostics.get("registration_form_valid")),
        "visible_invalid_control_count": (
            invalid_count if isinstance(invalid_count, int) and not isinstance(invalid_count, bool) else None
        ),
        "first_invalid_control_name": safe_diagnostic_name(diagnostics.get("first_invalid_control_name")),
        "first_invalid_control_type": safe_diagnostic_name(
            diagnostics.get("first_invalid_control_type"), field_type=True
        ),
        "alert_visible": safe_diagnostic_boolean(diagnostics.get("alert_visible")),
        "registration_link_visible": safe_diagnostic_boolean(diagnostics.get("registration_link_visible")),
        "identity_link_visible": safe_diagnostic_boolean(diagnostics.get("identity_link_visible")),
        "login_form_visible": safe_diagnostic_boolean(diagnostics.get("login_form_visible")),
        "header_user_menu_button_visible": safe_diagnostic_boolean(
            diagnostics.get("header_user_menu_button_visible")
        ),
    }
    safe_state_json = json.dumps(safe_state, ensure_ascii=True, sort_keys=True)
    print("ORDENOWA_ACCOUNT_REGISTRATION_SAFE_STATE=" + safe_state_json, file=sys.stderr)
    annotation = safe_state_json.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::error title=Customer account registration response state::{annotation}", file=sys.stderr)


def collect_profile_update_diagnostics(
    driver: webdriver.Chrome,
    phase: str,
    expected_first_name: str,
) -> dict[str, object]:
    diagnostics: dict[str, object] = {}
    try:
        current_url = driver.current_url
    except Exception:
        current_url = ""
    try:
        browser_diagnostics = driver.execute_script(
            r"""
            const form = document.querySelector('#customer-form');
            const isVisible = element => Boolean(element && element.getClientRects().length);
            const invalid = form ? [...form.querySelectorAll(':invalid')].filter(isVisible) : [];
            const password = form?.querySelector('input[name="password"]');
            const firstName = form?.querySelector('input[name="firstname"]');
            const submit = form?.querySelector('button.form-control-submit');
            const alerts = [...document.querySelectorAll('.alert, [role="alert"], .help-block.error')].filter(isVisible);
            const classifyAlert = element => {
              const className = typeof element.className === 'string' ? element.className.toLowerCase() : '';
              if (/(^|\s)(alert-success|is-success)(\s|$)/.test(className)) return 'success';
              if (/(^|\s)(alert-danger|is-danger|error)(\s|$)/.test(className)) return 'danger';
              if (/(^|\s)(alert-warning|is-warning)(\s|$)/.test(className)) return 'warning';
              if (/(^|\s)(alert-info|is-info)(\s|$)/.test(className)) return 'info';
              return 'unknown';
            };
            const alertClassification = alerts.length ? classifyAlert(alerts[0]) : 'none';
            return {
              form_present: Boolean(form),
              form_visible: isVisible(form),
              submit_button_present: Boolean(submit),
              submit_button_visible: isVisible(submit),
              submit_button_enabled: Boolean(submit && !submit.disabled),
              form_valid: Boolean(form && form.checkValidity()),
              visible_invalid_control_count: Math.min(invalid.length, 99),
              visible_invalid_controls: invalid.slice(0, 6).map(control => ({
                name: control.getAttribute('name') || '',
                type: control.getAttribute('type') || control.tagName.toLowerCase()
              })),
              current_password_present: Boolean(password),
              current_password_type: password?.getAttribute('type') || '',
              current_password_required: Boolean(password && password.required),
              current_password_filled: Boolean(password && password.value.length > 0),
              first_name_present: Boolean(firstName),
              first_name_matches_expected: Boolean(firstName && firstName.value === arguments[0]),
              alert_classification: alertClassification
            };
            """,
            expected_first_name,
        )
        if isinstance(browser_diagnostics, dict):
            diagnostics = browser_diagnostics
    except Exception as error:
        diagnostics["collection_error_type"] = type(error).__name__

    invalid_controls = diagnostics.get("visible_invalid_controls")
    safe_invalid_controls: list[dict[str, str]] = []
    if isinstance(invalid_controls, list):
        for item in invalid_controls[:6]:
            if not isinstance(item, dict):
                continue
            safe_invalid_controls.append(
                {
                    "name": safe_diagnostic_name(item.get("name")),
                    "type": safe_diagnostic_name(item.get("type"), field_type=True),
                }
            )
    invalid_count = diagnostics.get("visible_invalid_control_count")
    if not isinstance(invalid_count, int) or isinstance(invalid_count, bool):
        invalid_count = None
    else:
        invalid_count = min(max(invalid_count, 0), 99)
    alert_classification = diagnostics.get("alert_classification")
    if alert_classification not in {"none", "success", "danger", "warning", "info", "unknown"}:
        alert_classification = "unavailable"

    safe_state: dict[str, object] = {
        "phase": safe_diagnostic_name(phase),
        "path": safe_same_origin_path(current_url),
        "form_present": safe_diagnostic_boolean(diagnostics.get("form_present")),
        "form_visible": safe_diagnostic_boolean(diagnostics.get("form_visible")),
        "submit_button_present": safe_diagnostic_boolean(diagnostics.get("submit_button_present")),
        "submit_button_visible": safe_diagnostic_boolean(diagnostics.get("submit_button_visible")),
        "submit_button_enabled": safe_diagnostic_boolean(diagnostics.get("submit_button_enabled")),
        "form_valid": safe_diagnostic_boolean(diagnostics.get("form_valid")),
        "visible_invalid_control_count": invalid_count,
        "visible_invalid_controls": safe_invalid_controls,
        "current_password_present": safe_diagnostic_boolean(diagnostics.get("current_password_present")),
        "current_password_type": safe_diagnostic_name(
            diagnostics.get("current_password_type"), field_type=True
        ),
        "current_password_required": safe_diagnostic_boolean(diagnostics.get("current_password_required")),
        "current_password_filled": safe_diagnostic_boolean(diagnostics.get("current_password_filled")),
        "first_name_present": safe_diagnostic_boolean(diagnostics.get("first_name_present")),
        "first_name_matches_expected": safe_diagnostic_boolean(
            diagnostics.get("first_name_matches_expected")
        ),
        "alert_classification": alert_classification,
    }
    collection_error = diagnostics.get("collection_error_type")
    if isinstance(collection_error, str):
        safe_state["collection_error_type"] = safe_diagnostic_name(collection_error, field_type=True)
    return safe_state


def emit_profile_update_diagnostics(
    driver: webdriver.Chrome,
    stage: str,
    pre_submit: dict[str, object] | None,
    expected_first_name: str,
) -> None:
    safe_state = {
        "pre_submit": pre_submit,
        "failure_state": collect_profile_update_diagnostics(driver, stage, expected_first_name),
    }
    safe_state_json = json.dumps(safe_state, ensure_ascii=True, sort_keys=True)
    print("ORDENOWA_ACCOUNT_PROFILE_UPDATE_SAFE_STATE=" + safe_state_json, file=sys.stderr)
    annotation = safe_state_json.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::error title=Customer account profile update safe state::{annotation}", file=sys.stderr)


def fill(driver: webdriver.Chrome, selector: str, value: str) -> None:
    element = visible(driver, selector)
    element.clear()
    element.send_keys(value)


def visible_signout_link(driver: webdriver.Chrome):
    return WebDriverWait(driver, 30).until(
        lambda browser: next(
            (
                link
                for link in browser.find_elements(By.CSS_SELECTOR, "a.account-menu__link--signout")
                if link.is_displayed() and link.is_enabled()
            ),
            False,
        )
    )


def assert_my_page(driver: webdriver.Chrome, expected_first_name: str) -> None:
    visible(driver, "#identity_main_link")
    visible_signout_link(driver)

    page_text = driver.find_element(By.TAG_NAME, "body").text
    if expected_first_name not in page_text or "Customer" not in page_text:
        raise AssertionError("My Page did not show the signed-in customer's saved name")


def click_required_checkbox_label(form, checkbox) -> None:
    checkbox_id = checkbox.get_attribute("id") or ""
    if not checkbox_id:
        raise AssertionError("required registration checkbox does not have an associated label id")

    label = next(
        (
            candidate
            for candidate in form.find_elements(By.CSS_SELECTOR, "label[for]")
            if candidate.get_attribute("for") == checkbox_id and candidate.is_displayed()
        ),
        None,
    )
    if label is None:
        raise AssertionError("required registration checkbox does not have a visible associated label")

    # Use the visible label as a customer would. If its pointer target is
    # intercepted, fall back to a native keyboard action on the checkbox.
    try:
        label.click()
    except ElementClickInterceptedException:
        if not checkbox.is_displayed() or not checkbox.is_enabled():
            raise
        if not checkbox.is_selected():
            checkbox.send_keys(Keys.SPACE)
    if not checkbox.is_selected():
        raise AssertionError("activating the required registration checkbox did not select it")


def prepare_required_registration_fields(
    driver: webdriver.Chrome,
    form,
    email_address: str,
    password: str,
    active_control: dict[str, str],
) -> None:
    for name, value in (("firstname", "CI"), ("lastname", "Customer"), ("email", email_address)):
        set_registration_control(active_control, name, "input")
        fields = form.find_elements(By.CSS_SELECTOR, f'input[name="{name}"]')
        if not fields:
            raise AssertionError(f"registration form is missing the required {name} field")
        visible_fields = [field for field in fields if field.is_displayed() and field.is_enabled()]
        if not visible_fields:
            raise AssertionError(f"registration form has no usable {name} field")
        for field in visible_fields:
            set_registration_control(
                active_control,
                name,
                field.get_attribute("type") or "input",
            )
            field.clear()
            field.send_keys(value)

    password_fields = form.find_elements(By.CSS_SELECTOR, 'input[type="password"]')
    usable_password_fields = [field for field in password_fields if field.is_displayed() and field.is_enabled()]
    if not usable_password_fields:
        set_registration_control(active_control, "password", "password")
        raise AssertionError("registration form does not expose a usable password field")
    for field in usable_password_fields:
        set_registration_control(
            active_control,
            field.get_attribute("name") or field.get_attribute("id") or "password",
            field.get_attribute("type") or "password",
        )
        field.clear()
        field.send_keys(password)

    selected_radio_groups: set[str] = set()
    for element in form.find_elements(By.CSS_SELECTOR, "input[required]"):
        if not element.is_displayed() or not element.is_enabled():
            continue
        field_type = (element.get_attribute("type") or "").lower()
        name = element.get_attribute("name") or ""
        set_registration_control(
            active_control,
            name or element.get_attribute("id") or "input",
            field_type or "input",
        )
        if field_type == "checkbox" and not element.is_selected():
            click_required_checkbox_label(form, element)
        elif field_type == "radio" and name not in selected_radio_groups:
            element.click()
            selected_radio_groups.add(name)
        elif not element.get_attribute("value"):
            fixture_values = {
                "date": "1990-01-01",
                "datetime-local": "1990-01-01T12:00",
                "email": email_address,
                "month": "1990-01",
                "number": element.get_attribute("min") or "1",
                "password": password,
                "search": "CI Test",
                "tel": "09012345678",
                "text": "CI Test",
                "time": "12:00",
                "url": "https://example.invalid",
                "week": "1990-W01",
            }
            fixture = fixture_values.get(field_type)
            if fixture is not None:
                element.clear()
                element.send_keys(fixture)

    for element in form.find_elements(By.CSS_SELECTOR, "textarea[required]"):
        if element.is_displayed() and element.is_enabled() and not element.get_attribute("value"):
            set_registration_control(
                active_control,
                element.get_attribute("name") or element.get_attribute("id") or "textarea",
                "textarea",
            )
            element.clear()
            element.send_keys("CI Test")

    for element in form.find_elements(By.CSS_SELECTOR, "select[required]"):
        if not element.is_displayed() or not element.is_enabled():
            continue
        set_registration_control(
            active_control,
            element.get_attribute("name") or element.get_attribute("id") or "select",
            "select",
        )
        select = Select(element)
        option = next(
            (
                item for item in select.options
                if (item.get_attribute("value") or "").strip() not in {"", "0"}
                and item.is_enabled()
            ),
            None,
        )
        if option is not None:
            select.select_by_value(option.get_attribute("value"))

    invalid_fields = []
    for element in form.find_elements(By.CSS_SELECTOR, ":invalid"):
        field_name = element.get_attribute("name") or element.get_attribute("id") or element.tag_name.lower()
        field_type = element.get_attribute("type") or element.tag_name.lower()
        if not invalid_fields:
            set_registration_control(active_control, field_name, field_type)
        invalid_fields.append(f"{field_name}:{field_type}")
    if invalid_fields:
        raise AssertionError("registration form has invalid controls: " + ", ".join(invalid_fields))


def accept_profile_update_disclosures(driver: webdriver.Chrome, form) -> None:
    """Accept only the synthetic CI customer's two required profile disclosures."""
    for name in ("customer_privacy", "psgdpr_consent_checkbox"):
        checkbox = visible(driver, f'#customer-form input[type="checkbox"][name="{name}"]')
        if not checkbox.is_displayed() or not checkbox.is_enabled():
            raise AssertionError(f"profile update disclosure {name} is not available for the CI customer")
        if not checkbox.is_selected():
            click_required_checkbox_label(form, checkbox)
        if not checkbox.is_selected():
            raise AssertionError(f"profile update disclosure {name} was not accepted by the CI customer")


def assert_native_form_valid(driver: webdriver.Chrome, form, form_label: str) -> None:
    invalid_fields = []
    for element in form.find_elements(By.CSS_SELECTOR, ":invalid"):
        field_name = element.get_attribute("name") or element.get_attribute("id") or element.tag_name.lower()
        field_type = element.get_attribute("type") or element.tag_name.lower()
        invalid_fields.append(f"{field_name}:{field_type}")

    if invalid_fields or not driver.execute_script("return arguments[0].checkValidity();", form):
        detail = ", ".join(invalid_fields) if invalid_fields else "unknown controls"
        raise AssertionError(f"{form_label} form has invalid controls: {detail}")


def submit_login(driver: webdriver.Chrome, email_address: str, password: str) -> None:
    driver.get(f"{BASE}/index.php?controller=authentication")
    fill(driver, '#login-form input[name="email"]', email_address)
    fill(driver, '#login-form input[name="password"]', password)
    visible(driver, "#submit-login").click()
    WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "identity_main_link")))


def assert_login_rejected(driver: webdriver.Chrome, email_address: str, password: str) -> None:
    driver.get(f"{BASE}/index.php?controller=authentication")
    fill(driver, '#login-form input[name="email"]', email_address)
    fill(driver, '#login-form input[name="password"]', password)
    visible(driver, "#submit-login").click()
    WebDriverWait(driver, 30).until(
        lambda browser: any(
            alert.is_displayed()
            for alert in browser.find_elements(By.CSS_SELECTOR, '.alert.alert-danger[role="alert"]')
        )
    )
    visible(driver, '#login-form input[name="email"]')
    if any(
        link.is_displayed()
        for link in driver.find_elements(By.CSS_SELECTOR, "a.account-menu__link--signout")
    ):
        raise AssertionError("the prior customer password still authenticates after password reset")
    if any(element.is_displayed() for element in driver.find_elements(By.ID, "identity_main_link")):
        raise AssertionError("the prior customer password opened My Page after password reset")


def logout(driver: webdriver.Chrome) -> None:
    _, account_url = my_account_link_from_header(driver, open_menu=False)
    link = visible_signout_link(driver)
    link.click()
    driver.get(account_url)
    WebDriverWait(driver, 30).until(
        lambda browser: bool(browser.find_elements(By.CSS_SELECTOR, '#login-form input[name="email"]'))
        or bool(browser.find_elements(By.ID, "identity_main_link"))
    )
    if driver.find_elements(By.ID, "identity_main_link"):
        raise AssertionError("the signed-out customer can still open My Page")
    visible(driver, '#login-form input[name="email"]')
    WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "submit-login")))
    if any(
        link.is_displayed()
        for link in driver.find_elements(By.CSS_SELECTOR, "a.account-menu__link--signout")
    ):
        raise AssertionError("the customer still has an authenticated My Page session after logout")


def run_viewport(width: int, height: int, label: str) -> bool:
    stage = "registration_link_load"
    failure_control = {"name": "display-register-form", "type": "anchor"}
    profile_pre_submit: dict[str, object] | None = None
    korean_login_state: dict[str, object] = {}
    expected_first_name = f"CI-{label.title()}"
    driver = None
    success = False
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(f"--window-size={width},{height}")
        options.add_argument("--lang=ja-JP")
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        driver = webdriver.Chrome(options=options)
        driver.set_window_size(width, height)
        stage = "korean_email_login_label"
        failure_control = {"name": "", "type": ""}
        assert_korean_email_login_form(driver, korean_login_state)
        driver.save_screenshot(str(DEST / f"{label}-korean-login-email.png"))

        account_email = f"qa-ordenowa-{RUN_ID}-{RUN_ATTEMPT}-{label}@example.invalid"
        initial_password = f"Ordenowa-CI-{RUN_ID}-{RUN_ATTEMPT}!"
        reset_password = f"Ordenowa-Reset-{RUN_ID}-{RUN_ATTEMPT}!"

        driver.get(f"{BASE}/index.php?controller=authentication")
        registration_link = visible(driver, 'a[data-link-action="display-register-form"]')
        stage = "registration_link_validation"
        registration_url = urljoin(driver.current_url, registration_link.get_attribute("href") or "")
        registration_location = urlparse(registration_url)
        base_location = urlparse(BASE)
        if (
            registration_location.scheme != base_location.scheme
            or registration_location.hostname != base_location.hostname
            or registration_location.port != base_location.port
        ):
            raise AssertionError("PrestaShop registration link is outside the isolated shop")
        stage = "registration_link_click"
        set_registration_control(failure_control, "display-register-form", "anchor")
        click_centered(driver, registration_link)
        stage = "registration_form_load"
        set_registration_control(failure_control, "customer-form", "form")
        form = visible(driver, "#customer-form")
        stage = "registration_required_controls"
        failure_control = {"name": "", "type": ""}
        prepare_required_registration_fields(
            driver,
            form,
            account_email,
            initial_password,
            failure_control,
        )
        stage = "registration_submit"
        set_registration_control(failure_control, "save-customer", "submit")
        submit_button = visible(driver, "#customer-form button.form-control-submit")
        click_centered(driver, submit_button)
        stage = "registration_post_submit"
        failure_control = {"name": "", "type": ""}
        wait_for_registration_success(driver)
        assert_my_page(driver, "CI")
        driver.save_screenshot(str(DEST / f"{label}-customer-account-created.png"))

        stage = "profile_update_route"
        driver.get(f"{BASE}/index.php?controller=identity")
        assert_canonical_static_route(driver, "identity")
        stage = "profile_update_first_name"
        first_name = visible(driver, '#customer-form input[name="firstname"]')
        first_name.clear()
        first_name.send_keys(expected_first_name)
        stage = "profile_update_current_password"
        # PrestaShop 9 requires the signed-in customer's current password before saving identity changes.
        fill(driver, '#customer-form input[name="password"]', initial_password)
        stage = "profile_update_required_disclosures"
        profile_form = visible(driver, "#customer-form")
        accept_profile_update_disclosures(driver, profile_form)
        assert_native_form_valid(driver, profile_form, "profile update")
        profile_pre_submit = collect_profile_update_diagnostics(
            driver, "pre_submit", expected_first_name
        )
        stage = "profile_update_submit"
        submit_button = visible(driver, "#customer-form button.form-control-submit")
        click_centered(driver, submit_button)
        stage = "profile_update_persist_wait"
        WebDriverWait(driver, 30).until(
            lambda browser: browser.find_element(By.CSS_SELECTOR, '#customer-form input[name="firstname"]').get_attribute("value")
            == expected_first_name
        )
        driver.save_screenshot(str(DEST / f"{label}-customer-account-profile.png"))

        stage = "email_login"
        logout(driver)
        driver.get(f"{BASE}/index.php?controller=authentication")
        email_field = visible(driver, '#login-form input[name="email"]')
        if email_field.get_attribute("type") != "email":
            raise AssertionError("customer login is not email-based")
        fill(driver, '#login-form input[name="email"]', account_email)
        fill(driver, '#login-form input[name="password"]', initial_password)
        visible(driver, "#submit-login").click()
        WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "identity_main_link")))
        assert_my_page(driver, f"CI-{label.title()}")
        driver.save_screenshot(str(DEST / f"{label}-customer-email-login.png"))

        stage = "password_reset_request"
        logout(driver)
        driver.get(f"{BASE}/index.php?controller=password")
        assert_canonical_static_route(driver, "password-reset")
        fill(driver, '#email', account_email)
        visible(driver, "#send-reset-link").click()
        driver.save_screenshot(str(DEST / f"{label}-password-reset-requested.png"))
        reset_url, reset_message = reset_link_for(account_email)
        if "cid:shop_logo" not in str(reset_message.get("HTML") or ""):
            raise AssertionError("password reset email does not render the approved inline ORDENOWA logo")
        logo_hash = hashlib.sha256(OFFICIAL_LOGO.read_bytes()).hexdigest()
        expected_logo = request_bytes(f"{BASE}/img/ordenowa/versions/{logo_hash}/email-logo.png")
        inline_logo = next(
            (
                attachment
                for attachment in reset_message.get("Inline", [])
                if isinstance(attachment, dict)
                and str(attachment.get("ContentID", "")).strip("<>").lower() == "shop_logo"
            ),
            None,
        )
        if not isinstance(inline_logo, dict) or inline_logo.get("ContentType") != "image/png":
            raise AssertionError("password reset email is missing the inline ORDENOWA PNG attachment")
        message_id = reset_message.get("ID") or reset_message.get("Id")
        part_id = inline_logo.get("PartID")
        if not isinstance(message_id, str) or not isinstance(part_id, str):
            raise AssertionError("Mailpit did not identify the inline ORDENOWA logo part")
        attachment_url = (
            f"{MAILPIT_API}/api/v1/message/{quote(message_id, safe='')}"
            f"/part/{quote(part_id, safe='')}"
        )
        sent_logo = request_bytes(attachment_url)
        if hashlib.sha256(sent_logo).digest() != hashlib.sha256(expected_logo).digest():
            raise AssertionError("password reset email logo bytes do not match the published ORDENOWA derivative")

        stage = "password_reset"
        parsed_reset = urlparse(reset_url)
        base = urlparse(BASE)
        if (
            parsed_reset.scheme != base.scheme
            or parsed_reset.hostname != base.hostname
            or parsed_reset.port != base.port
        ):
            raise AssertionError("password reset email points outside the isolated shop")
        driver.get(reset_url)
        assert_canonical_static_route(driver, "password-reset")
        fill(driver, '#field-password[name="passwd"]', reset_password)
        fill(driver, '#field-confirmation-passwd[name="confirmation"]', reset_password)
        visible(driver, 'button[type="submit"][name="submit"]').click()

        stage = "password_reset_old_password_rejected"
        assert_login_rejected(driver, account_email, initial_password)

        stage = "password_reset_login"
        submit_login(driver, account_email, reset_password)
        assert_my_page(driver, f"CI-{label.title()}")
        driver.save_screenshot(str(DEST / f"{label}-customer-password-reset-login.png"))
        logout(driver)
        print(f"PASS: {label} customer registration, profile update, email login/logout, and Mailpit password reset")
        success = True
    except Exception as error:
        if driver is not None:
            try:
                driver.save_screenshot(str(DEST / f"{label}-customer-account-failure.png"))
            except Exception:
                pass
            if stage.startswith("registration_"):
                try:
                    emit_registration_diagnostics(driver, stage, failure_control)
                except Exception:
                    pass
            elif stage == "korean_email_login_label":
                try:
                    emit_korean_login_diagnostics(driver, korean_login_state)
                except Exception:
                    pass
            elif stage.startswith("profile_update_"):
                try:
                    emit_profile_update_diagnostics(
                        driver, stage, profile_pre_submit, expected_first_name
                    )
                except Exception:
                    pass
        print(f"FAIL: {label} customer account flow at {stage} ({type(error).__name__})", file=sys.stderr)
        print(
            f"::error title=Customer account browser QA::{label} failed at {stage} "
            f"({type(error).__name__}); control_name={failure_control.get('name') or 'none'}; "
            f"control_type={failure_control.get('type') or 'none'}",
            file=sys.stderr,
        )
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception as error:
                print(f"FAIL: {label} customer account browser cleanup ({type(error).__name__})", file=sys.stderr)
                success = False
    return success


if __name__ == "__main__":
    failed_viewports = []
    for viewport in ((1440, 960, "desktop"), (390, 844, "mobile")):
        if not run_viewport(*viewport):
            failed_viewports.append(viewport[2])
    if failed_viewports:
        raise SystemExit(f"isolated customer account browser flow failed for: {', '.join(failed_viewports)}")
