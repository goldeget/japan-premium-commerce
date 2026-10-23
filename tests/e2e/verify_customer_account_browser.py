#!/usr/bin/env python3
"""Exercise native customer account flows in an isolated PrestaShop CI shop."""

from __future__ import annotations

import html
import json
import math
import os
import re
import sys
import time
from collections.abc import Callable
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


def reset_link_matches_route(candidate_url: str, expected_route_path: str) -> bool:
    base_location = urlparse(BASE)
    expected_url = urlparse(urljoin(BASE + "/", expected_route_path))
    reset_url = urljoin(BASE + "/", candidate_url)
    parsed_reset = urlparse(reset_url)
    query = {key.lower(): values for key, values in parse_qs(parsed_reset.query).items()}
    same_shop_origin = (
        parsed_reset.scheme == base_location.scheme
        and parsed_reset.hostname == base_location.hostname
        and parsed_reset.port == base_location.port
        and expected_url.scheme == base_location.scheme
        and expected_url.hostname == base_location.hostname
        and expected_url.port == base_location.port
    )
    try:
        actual_path = unquote(parsed_reset.path, errors="strict").rstrip("/") or "/"
        expected_path = unquote(expected_url.path, errors="strict").rstrip("/") or "/"
    except (UnicodeDecodeError, ValueError):
        return False
    has_reset_token = "token" in query or "reset_token" in query
    return same_shop_origin and actual_path == expected_path and has_reset_token


def reset_link_for(
    email_address: str,
    expected_route_path: str,
    timeout_seconds: int = 90,
) -> tuple[str, dict]:
    deadline = time.monotonic() + timeout_seconds
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
                    if reset_link_matches_route(reset_url, expected_route_path):
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
        r"""
        const key = '__ordenowaKoreanLoginNavigation';
        const interactionKey = '__ordenowaKoreanLoginInteractions';
        const refreshKey = '__ordenowaKoreanLoginMetaRefresh';
        try {
          sessionStorage.removeItem(key);
          sessionStorage.removeItem(interactionKey);
          sessionStorage.removeItem(refreshKey);
          const allowedKeys = new Set(['back', 'controller', 'id_lang', 'isolang', 'lang']);
          const refreshFacts = () => [...document.querySelectorAll('meta[http-equiv]')]
            .filter(meta => (meta.getAttribute('http-equiv') || '').trim().toLowerCase() === 'refresh')
            .slice(0, 3)
            .map(meta => {
              const content = meta.getAttribute('content') || '';
              const match = content.match(/^\s*(\d+(?:\.\d+)?)\s*;\s*url\s*=\s*(?:"([^"]*)"|'([^']*)'|(.+?))\s*$/i);
              const rawTarget = match ? (match[2] ?? match[3] ?? match[4] ?? '').trim() : '';
              const delay = match ? Number(match[1]) : NaN;
              let target = null;
              try { if (rawTarget) target = new URL(rawTarget, window.location.href); } catch (_) {}
              const controllerValues = target ? new URLSearchParams(target.search).getAll('controller') : [];
              const controller = controllerValues.length === 1 ? controllerValues[0].toLowerCase() : '';
              const controllerCategory = controller === 'authentication' || controller === 'password'
                ? controller : (controller ? 'other' : '');
              return {
                delay_ms: Number.isFinite(delay) ? Math.min(300000, Math.max(0, Math.round(delay * 1000))) : null,
                target_present: Boolean(rawTarget),
                target_same_origin: target ? target.origin === window.location.origin : null,
                target_index_php: target ? target.pathname.toLowerCase().endsWith('/index.php') : false,
                target_controller_category: controllerCategory,
                target_query_key_names: target
                  ? [...new URLSearchParams(target.search).keys()].filter(name => allowedKeys.has(name)).slice(0, 5)
                  : []
              };
            });
          const persistRefreshFacts = () => {
            try { sessionStorage.setItem(refreshKey, JSON.stringify(refreshFacts())); } catch (_) {}
          };
          persistRefreshFacts();
          if (document.documentElement) {
            const refreshObserver = new MutationObserver(persistRefreshFacts);
            refreshObserver.observe(document.documentElement, {
              subtree: true,
              childList: true,
              attributes: true,
              attributeFilter: ['http-equiv', 'content']
            });
          }
          const interactionState = {
            click_count: 0,
            trusted_click_count: 0,
            login_recovery_link_click_count: 0,
            login_form_submit_count: 0,
            other_form_submit_count: 0
          };
          const persistInteractions = () => {
            try { sessionStorage.setItem(interactionKey, JSON.stringify(interactionState)); } catch (_) {}
          };
          document.addEventListener('click', event => {
            const target = event.target instanceof Element ? event.target : null;
            interactionState.click_count = Math.min(20, interactionState.click_count + 1);
            if (event.isTrusted) {
              interactionState.trusted_click_count = Math.min(20, interactionState.trusted_click_count + 1);
            }
            if (target?.closest('#login-form a[href]')) {
              interactionState.login_recovery_link_click_count = Math.min(
                20, interactionState.login_recovery_link_click_count + 1
              );
            }
            persistInteractions();
          }, true);
          document.addEventListener('submit', event => {
            const form = event.target instanceof HTMLFormElement ? event.target : null;
            const keyName = form?.id === 'login-form' ? 'login_form_submit_count' : 'other_form_submit_count';
            interactionState[keyName] = Math.min(20, interactionState[keyName] + 1);
            persistInteractions();
          }, true);
          const capture = (eventName, persisted = false) => {
            try {
              const navigation = performance.getEntriesByType('navigation')[0];
              const interactions = JSON.parse(sessionStorage.getItem(interactionKey) || '{}');
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
                interaction_click_count: Number.isInteger(interactions.click_count) ? interactions.click_count : 0,
                interaction_trusted_click_count: Number.isInteger(interactions.trusted_click_count) ? interactions.trusted_click_count : 0,
                interaction_login_recovery_link_click_count: Number.isInteger(interactions.login_recovery_link_click_count) ? interactions.login_recovery_link_click_count : 0,
                interaction_login_form_submit_count: Number.isInteger(interactions.login_form_submit_count) ? interactions.login_form_submit_count : 0,
                interaction_other_form_submit_count: Number.isInteger(interactions.other_form_submit_count) ? interactions.other_form_submit_count : 0,
                meta_refresh_facts: refreshFacts(),
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
                "interaction_click_count": min(event.get("interaction_click_count", 0), 20)
                if isinstance(event.get("interaction_click_count"), int)
                else 0,
                "interaction_trusted_click_count": min(event.get("interaction_trusted_click_count", 0), 20)
                if isinstance(event.get("interaction_trusted_click_count"), int)
                else 0,
                "interaction_login_recovery_link_click_count": min(
                    event.get("interaction_login_recovery_link_click_count", 0), 20
                ) if isinstance(event.get("interaction_login_recovery_link_click_count"), int) else 0,
                "interaction_login_form_submit_count": min(
                    event.get("interaction_login_form_submit_count", 0), 20
                ) if isinstance(event.get("interaction_login_form_submit_count"), int) else 0,
                "interaction_other_form_submit_count": min(
                    event.get("interaction_other_form_submit_count", 0), 20
                ) if isinstance(event.get("interaction_other_form_submit_count"), int) else 0,
                "meta_refresh_facts": safe_meta_refresh_facts(event.get("meta_refresh_facts")),
                "persisted": event.get("persisted") is True,
            }
        )
    return safe_events


def assert_korean_email_login_form(driver: webdriver.Chrome, state: dict[str, object]) -> str:
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
                timeline = state["reset_link_navigation_timeline"]
                state["reset_wait_navigation_meta_refresh_facts"] = (
                    timeline[-1].get("meta_refresh_facts", [])
                    if isinstance(timeline, list) and timeline and isinstance(timeline[-1], dict)
                    else []
                )
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
    state["reset_wait_navigation_meta_refresh_facts"] = []
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
    return login_url


def emit_korean_login_diagnostics(driver: webdriver.Chrome, state: dict[str, object]) -> None:
    """Report the exact Korean login wait and sanitized page markers on failure."""
    diagnostics: dict[str, object] = {
        "stage": safe_diagnostic_name(state.get("stage", "")),
        "async_stack_capture_enabled": state.get("async_stack_capture_enabled") is True,
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
        "reset_wait_navigation_meta_refresh_facts": state.get("reset_wait_navigation_meta_refresh_facts", []),
        "document_navigation_events": state.get("document_navigation_events", []),
    }
    stage_started_at = state.get("stage_started_at")
    if isinstance(stage_started_at, (int, float)):
        diagnostics["failed_stage_elapsed_ms"] = min(
            300_000, max(0, int((time.monotonic() - stage_started_at) * 1000))
        )
    if not diagnostics["reset_link_navigation_timeline"]:
        diagnostics["reset_link_navigation_timeline"] = reset_link_navigation_timeline(driver)
    if not diagnostics["reset_wait_navigation_meta_refresh_facts"]:
        timeline = diagnostics["reset_link_navigation_timeline"]
        if isinstance(timeline, list) and timeline and isinstance(timeline[-1], dict):
            diagnostics["reset_wait_navigation_meta_refresh_facts"] = timeline[-1].get(
                "meta_refresh_facts", []
            )
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
    stage_json = json.dumps(
        compact_korean_login_failure_summary(diagnostics), ensure_ascii=True, sort_keys=True
    )
    print("ORDENOWA_KOREAN_LOGIN_STAGE_SAFE_STATE=" + stage_json, file=sys.stderr)
    stage_annotation = stage_json.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(
        f"::error title=Korean customer login wait details::{stage_annotation}",
        file=sys.stderr,
    )
    raw_events = diagnostics.get("document_navigation_events", [])
    navigation_events = []
    if isinstance(raw_events, list):
        for event in raw_events[-4:]:
            if not isinstance(event, dict):
                continue
            route = event.get("route_metadata", {})
            redirect_from = event.get("redirect_from_metadata", {})
            route = route if isinstance(route, dict) else {}
            redirect_from = redirect_from if isinstance(redirect_from, dict) else {}
            navigation_events.append(
                {
                    "event": event.get("event", ""),
                    "path": route.get("path", ""),
                    "controller_category": route.get("controller_category", ""),
                    "status_code": event.get("status_code", 0),
                    "redirect_status_code": event.get("redirect_status_code", 0),
                    "frame_scope": event.get("frame_scope", "unknown"),
                    "initiator_type": event.get("initiator_type", "unknown"),
                    "initiator_scope": event.get("initiator_scope", "unknown"),
                    "initiator_stack_depth": event.get("initiator_stack_depth", 0),
                    "initiator_async_parent_count": event.get("initiator_async_parent_count", 0),
                    "initiator_line_number": event.get("initiator_line_number"),
                    "initiator_column_number": event.get("initiator_column_number"),
                    "initiator_has_url": event.get("initiator_has_url", False),
                    "request_elapsed_ms": event.get("request_elapsed_ms"),
                    "response_elapsed_ms": event.get("response_elapsed_ms"),
                    "response_refresh": event.get("response_refresh", {}),
                    "redirect_from_path": redirect_from.get("path", ""),
                    "redirect_from_controller_category": redirect_from.get("controller_category", ""),
                }
            )
    navigation_json = json.dumps(navigation_events, ensure_ascii=True, sort_keys=True)
    print("ORDENOWA_KOREAN_LOGIN_NAVIGATION_SAFE_STATE=" + navigation_json, file=sys.stderr)
    navigation_annotation = navigation_json.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(
        f"::error title=Korean customer login navigation::{navigation_annotation}",
        file=sys.stderr,
    )


def click_centered(driver: webdriver.Chrome, element) -> bool:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element)
    WebDriverWait(driver, 30).until(EC.element_to_be_clickable(element))
    center_unobstructed = WebDriverWait(driver, 10).until(
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
    return bool(center_unobstructed)


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


def safe_account_route_classification(candidate_url: str) -> str:
    try:
        candidate = urlparse(candidate_url)
        base = urlparse(BASE)
    except ValueError:
        return "unavailable"
    if (candidate.scheme.lower(), candidate.hostname, candidate.port) != (
        base.scheme.lower(),
        base.hostname,
        base.port,
    ):
        return "outside_shop"

    try:
        path = unquote(candidate.path, errors="strict").rstrip("/") or "/"
        base_path = unquote(base.path, errors="strict").rstrip("/")
    except (UnicodeDecodeError, ValueError):
        return "unavailable"
    if base_path and path.startswith(base_path + "/"):
        path = path[len(base_path) :]
    elif base_path and path == base_path:
        path = "/"

    controllers = {value.lower() for value in parse_qs(candidate.query).get("controller", [])}
    if "identity" in controllers:
        return "identity"
    if controllers & {"my-account", "authentication"}:
        return "account"

    route_parts = [part.lower() for part in path.split("/") if part]
    if not route_parts:
        return "root"
    if route_parts[-1] in {"identity", "identite"}:
        return "identity"
    if route_parts[-1] in {"account", "authentication", "login", "my-account", "myaccount"}:
        return "account"
    return "other"


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


def assert_route_path_matches(driver: webdriver.Chrome, expected_route_path: str, route_label: str) -> None:
    actual = urlparse(driver.current_url)
    expected = urlparse(urljoin(BASE + "/", expected_route_path))
    base = urlparse(BASE)
    same_shop_origin = (
        actual.scheme.lower(), actual.hostname, actual.port
    ) == (
        base.scheme.lower(), base.hostname, base.port
    ) and (
        expected.scheme.lower(), expected.hostname, expected.port
    ) == (
        base.scheme.lower(), base.hostname, base.port
    )
    try:
        actual_path = unquote(actual.path, errors="strict").rstrip("/") or "/"
        expected_path = unquote(expected.path, errors="strict").rstrip("/") or "/"
    except (UnicodeDecodeError, ValueError):
        raise AssertionError(f"the {route_label} page did not resolve to the generated route") from None
    if not same_shop_origin or actual_path != expected_path:
        raise AssertionError(f"the {route_label} page did not resolve to the generated route")


def set_registration_control(control: dict[str, str], name: str, field_type: str) -> None:
    control["name"] = re.sub(r"[^A-Za-z0-9_.\[\]-]", "_", name)[:80]
    control["type"] = re.sub(r"[^A-Za-z0-9_-]", "_", field_type)[:40]


def safe_diagnostic_name(value: object, *, field_type: bool = False) -> str:
    if not isinstance(value, str):
        return ""
    pattern = r"[^A-Za-z0-9_-]" if field_type else r"[^A-Za-z0-9_.\[\]-]"
    return re.sub(pattern, "_", value)[:80]


KOREAN_LOGIN_STAGES = {
    "korean_storefront_home",
    "korean_language_selector",
    "korean_language_destination",
    "korean_sign_in_link",
    "korean_login_page_navigation",
    "korean_login_form",
    "korean_email_field",
    "korean_password_reset_link",
}


def safe_korean_login_stage(value: object) -> str:
    return value if isinstance(value, str) and value in KOREAN_LOGIN_STAGES else "unknown"


def safe_document_frame_scope(frame_id: object, main_frame_id: object) -> str:
    if not isinstance(frame_id, str) or not frame_id:
        return "unknown"
    if not isinstance(main_frame_id, str) or not main_frame_id:
        return "unknown"
    return "top_frame" if frame_id == main_frame_id else "subframe"


def top_level_frame_id(driver) -> str | None:
    try:
        frame_tree = driver.execute_cdp_cmd("Page.getFrameTree", {})
    except Exception:
        return None
    if not isinstance(frame_tree, dict):
        return None
    tree = frame_tree.get("frameTree")
    frame = tree.get("frame") if isinstance(tree, dict) else None
    frame_id = frame.get("id") if isinstance(frame, dict) else None
    return frame_id if isinstance(frame_id, str) and frame_id else None


def compact_korean_login_failure_summary(diagnostics: dict[str, object]) -> dict[str, object]:
    """Keep the decisive Korean login wait facts below the Actions annotation limit."""
    allowed_query_keys = {"back", "controller", "id_lang", "isolang", "lang"}
    allowed_controllers = {"authentication", "password", "other"}
    allowed_initiator_types = {
        "address_bar", "other", "parser", "preload", "script", "signedExchange", "serviceWorker"
    }
    allowed_initiator_scopes = {
        "external", "front_controller", "hummingbird_theme", "kuranea_module",
        "kuranea_theme", "prestashop_module", "same_origin_other", "unknown",
    }
    allowed_frame_scopes = {"top_frame", "subframe", "unknown"}

    def bounded_int(value: object, maximum: int) -> int | None:
        if not isinstance(value, int) or isinstance(value, bool):
            return None
        return min(max(value, 0), maximum)

    def safe_route(value: object) -> dict[str, object]:
        route = value if isinstance(value, dict) else {}
        path = route.get("path")
        if not isinstance(path, str) or len(path) > 160 or not path.isascii():
            path = "/<unknown>"
        else:
            path = re.sub(r"[^A-Za-z0-9_/< >-]", "_", path).replace(" ", "")
            if len(path) > 40:
                path = path[:37] + "..."
        controller = route.get("controller_category")
        query_names = route.get("query_key_names")
        return {
            "path": path,
            "controller_category": controller
            if isinstance(controller, str) and controller in allowed_controllers
            else "",
            "query_key_names": sorted(
                {key for key in query_names if isinstance(key, str)} & allowed_query_keys
            ) if isinstance(query_names, list) else [],
            "same_origin": route.get("same_origin") if isinstance(route.get("same_origin"), bool) else None,
            "path_has_non_ascii": route.get("path_has_non_ascii") is True,
            "path_has_percent_escape": route.get("path_has_percent_escape") is True,
            "back_present": route.get("back_present") is True,
        }

    def safe_language(value: object) -> str:
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,12}", value):
            return "unknown"
        return value

    def safe_refresh(value: object) -> dict[str, object]:
        refresh = value if isinstance(value, dict) else {}
        if refresh.get("present") is not True:
            return {"present": False}
        return {
            "present": True,
            "parseable": refresh.get("parseable") is True,
            "delay_ms": bounded_int(refresh.get("delay_ms"), 300_000),
            "target_route": safe_route(refresh.get("target_route")),
        }

    raw_navigation_events = diagnostics.get("document_navigation_events")
    navigation_events: list[dict[str, object]] = []
    if isinstance(raw_navigation_events, list):
        for event in raw_navigation_events[-2:]:
            if not isinstance(event, dict):
                continue
            route = safe_route(event.get("route_metadata"))
            redirect_from = safe_route(event.get("redirect_from_metadata"))
            initiator_type = event.get("initiator_type")
            initiator_scope = event.get("initiator_scope")
            frame_scope = event.get("frame_scope")
            event_name = event.get("event")
            navigation_event = {
                    "event": event_name
                    if isinstance(event_name, str) and event_name in {"document_request", "document_redirect"}
                    else "unknown",
                    "path": route["path"],
                    "controller_category": route["controller_category"],
                    "status_code": bounded_int(event.get("status_code"), 599) or 0,
                    "redirect_status_code": bounded_int(event.get("redirect_status_code"), 599) or 0,
                    "frame_scope": frame_scope
                    if isinstance(frame_scope, str) and frame_scope in allowed_frame_scopes
                    else "unknown",
                    "initiator_type": initiator_type
                    if isinstance(initiator_type, str) and initiator_type in allowed_initiator_types
                    else "unknown",
                    "initiator_scope": initiator_scope
                    if isinstance(initiator_scope, str) and initiator_scope in allowed_initiator_scopes
                    else "unknown",
                    "initiator_stack_depth": bounded_int(event.get("initiator_stack_depth"), 20) or 0,
                    "initiator_async_parent_count": bounded_int(
                        event.get("initiator_async_parent_count"), 8
                    ) or 0,
                    "initiator_has_url": event.get("initiator_has_url") is True,
                    "request_elapsed_ms": bounded_int(event.get("request_elapsed_ms"), 300_000),
                    "response_elapsed_ms": bounded_int(event.get("response_elapsed_ms"), 300_000),
                    "response_refresh": safe_refresh(event.get("response_refresh")),
                    "redirect_from_path": redirect_from["path"],
                    "redirect_from_controller_category": redirect_from["controller_category"],
                }
            for location_name in ("initiator_line_number", "initiator_column_number"):
                location_value = bounded_int(event.get(location_name), 1_000_000)
                if location_value is not None:
                    navigation_event[location_name] = location_value
            navigation_events.append(navigation_event)

    raw_timeline = diagnostics.get("reset_link_navigation_timeline")
    navigation_timeline: list[dict[str, object]] = []
    if isinstance(raw_timeline, list):
        # beforeunload and pagehide are duplicate observations of the same navigation;
        # keep the last one with the safe interaction counters to stay under the annotation limit.
        for event in raw_timeline[-1:]:
            if not isinstance(event, dict):
                continue
            event_name = event.get("event")
            if not isinstance(event_name, str) or event_name not in {"beforeunload", "pagehide"}:
                continue
            navigation_type = event.get("navigation_type")
            ready_state = event.get("ready_state")
            navigation_timeline.append(
                {
                    "event": event_name,
                    "elapsed_ms": bounded_int(event.get("elapsed_ms"), 300_000),
                    "route": safe_route(event.get("route_metadata")),
                    "document_language": safe_language(event.get("document_language")),
                    "ready_state": ready_state
                    if isinstance(ready_state, str) and ready_state in {"loading", "interactive", "complete"}
                    else "unknown",
                    "navigation_type": navigation_type
                    if isinstance(navigation_type, str)
                    and navigation_type in {"navigate", "reload", "back_forward", "prerender"}
                    else "unknown",
                    "navigation_redirect_count": bounded_int(event.get("navigation_redirect_count"), 20) or 0,
                    "interaction_click_count": bounded_int(event.get("interaction_click_count"), 20) or 0,
                    "interaction_trusted_click_count": bounded_int(event.get("interaction_trusted_click_count"), 20) or 0,
                    "interaction_login_recovery_link_click_count": bounded_int(
                        event.get("interaction_login_recovery_link_click_count"), 20
                    ) or 0,
                    "interaction_login_form_submit_count": bounded_int(
                        event.get("interaction_login_form_submit_count"), 20
                    ) or 0,
                    "interaction_other_form_submit_count": bounded_int(
                        event.get("interaction_other_form_submit_count"), 20
                    ) or 0,
                    "meta_refresh_facts": safe_meta_refresh_facts(event.get("meta_refresh_facts")),
                    "persisted": event.get("persisted") is True,
                }
            )

    display = diagnostics.get("reset_link_before_wait_computed_display")
    visibility = diagnostics.get("reset_link_before_wait_computed_visibility")
    return {
        "inner_stage": safe_korean_login_stage(diagnostics.get("stage")),
        "async_stack_capture_enabled": diagnostics.get("async_stack_capture_enabled") is True,
        "failed_stage_elapsed_ms": bounded_int(diagnostics.get("failed_stage_elapsed_ms"), 300_000),
        "document_language": safe_language(diagnostics.get("document_language")),
        "final_route": safe_route(diagnostics.get("final_url_metadata")),
        "reset_link_before_wait": {
            "anchor_count": bounded_int(diagnostics.get("reset_link_before_wait_anchor_count"), 20) or 0,
            "href_present": diagnostics.get("reset_link_before_wait_href_present") is True,
            "visible": diagnostics.get("reset_link_before_wait_visible") is True,
            "display": display if display in {"block", "contents", "flex", "grid", "inline", "inline-block", "inline-flex", "none"} else "other",
            "visibility": visibility if visibility in {"collapse", "hidden", "visible"} else "other",
            "text_identifies_password_reset": diagnostics.get("reset_link_before_wait_text_identifies_password_reset") is True,
            "aria_label_identifies_password_reset": diagnostics.get("reset_link_before_wait_aria_label_identifies_password_reset") is True,
            "href_route": safe_route(diagnostics.get("reset_link_before_wait_href_metadata")),
        },
        "reset_wait_navigation": {
            "elapsed_ms": bounded_int(diagnostics.get("reset_wait_navigation_elapsed_ms"), 300_000),
            "document_language": safe_language(diagnostics.get("reset_wait_navigation_document_language")),
            "route": safe_route(diagnostics.get("reset_wait_navigation_url_metadata")),
            "timeline": navigation_timeline,
        },
        "navigation_events": navigation_events,
    }


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


def safe_controller_category(value: object) -> str:
    """Expose only known front-controller names in browser route diagnostics."""
    if not isinstance(value, str):
        return ""
    try:
        values = parse_qs(urlparse(value).query, keep_blank_values=True).get("controller", [])
    except (TypeError, ValueError):
        return ""
    if not values:
        return ""
    if len(values) != 1:
        return "other"
    controller = values[0].strip().lower()
    return controller if controller in {"authentication", "password"} else "other"


def safe_initiator_scope(value: object) -> str:
    """Classify a Chrome initiator URL without logging its raw path or query."""
    if not isinstance(value, str) or not value:
        return "unknown"
    try:
        location = urlparse(value)
        base_location = urlparse(BASE)
        if (
            location.scheme.lower() != base_location.scheme.lower()
            or location.hostname != base_location.hostname
            or location.port != base_location.port
        ):
            return "external"
        path = unquote(location.path or "/").lower()
    except (TypeError, ValueError):
        return "unknown"
    if "/themes/kuranea/" in path:
        return "kuranea_theme"
    if "/themes/hummingbird/" in path:
        return "hummingbird_theme"
    if "/modules/kuranea" in path:
        return "kuranea_module"
    if "/modules/" in path:
        return "prestashop_module"
    if path.endswith("/index.php"):
        return "front_controller"
    return "same_origin_other"


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
        "controller_category": "",
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
            "controller_category": safe_controller_category(value),
            "back_present": "back" in query_keys,
        }
    )
    return metadata


def safe_generated_route_match(actual_url: object, expected_url: object) -> bool:
    """Compare generated same-shop routes without exposing their path or query values."""
    if not isinstance(actual_url, str) or not isinstance(expected_url, str):
        return False
    try:
        actual = urlparse(actual_url)
        expected = urlparse(expected_url)
        base = urlparse(BASE)
        actual_origin = (actual.scheme.lower(), actual.hostname, actual.port)
        expected_origin = (expected.scheme.lower(), expected.hostname, expected.port)
        base_origin = (base.scheme.lower(), base.hostname, base.port)
        if actual_origin != expected_origin or actual_origin != base_origin:
            return False
        actual_path = unquote(actual.path or "/", errors="strict").rstrip("/") or "/"
        expected_path = unquote(expected.path or "/", errors="strict").rstrip("/") or "/"
        if actual_path != expected_path:
            return False
        actual_query = parse_qs(actual.query, keep_blank_values=True)
        expected_query = parse_qs(expected.query, keep_blank_values=True)
        if actual_query.get("controller", []) != expected_query.get("controller", []):
            return False
        for key in ("id_lang", "isolang", "lang"):
            actual_language_values = actual_query.get(key, [])
            expected_language_values = expected_query.get(key, [])
            if key in {"isolang", "lang"}:
                actual_language_values = [value.casefold() for value in actual_language_values]
                expected_language_values = [value.casefold() for value in expected_language_values]
            if actual_language_values != expected_language_values:
                return False
        return True
    except (TypeError, UnicodeDecodeError, ValueError):
        return False


def safe_registration_navigation_summary(events: object) -> list[dict[str, object]]:
    """Keep only bounded route shapes and HTTP status codes from browser navigation events."""
    if not isinstance(events, list):
        return []

    def safe_route(metadata: object) -> dict[str, object]:
        if not isinstance(metadata, dict):
            metadata = {}
        path = metadata.get("path")
        if not isinstance(path, str) or len(path) > 160 or not path.isascii():
            path = "/<unknown>"
        elif re.fullmatch(r"/[A-Za-z0-9<>/_-]*", path) is None:
            path = "/<unknown>"
        else:
            allowed_segments = {
                "index.php", "ja", "ko", "en", "authentication", "login", "register",
                "registration", "identity", "order", "password", "password-reset", "history",
                "<redacted>", "<unknown>",
            }
            path = "/".join(
                segment.lower() if not segment or segment.lower() in allowed_segments else "<redacted>"
                for segment in path.split("/")
            )
        category = metadata.get("controller_category")
        if not isinstance(category, str) or category not in {"authentication", "password", "other"}:
            category = ""
        return {
            "same_origin": metadata.get("same_origin") is True,
            "path": path,
            "controller_category": category,
            "back_present": metadata.get("back_present") is True,
        }

    def safe_status(value: object) -> int:
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 599:
            return 0
        return int(value)

    summary: list[dict[str, object]] = []
    for event in events[-6:]:
        if not isinstance(event, dict):
            continue
        event_name = event.get("event")
        if not isinstance(event_name, str) or event_name not in {"document_request", "document_redirect"}:
            event_name = "other"
        summary.append(
            {
                "event": event_name,
                "route": safe_route(event.get("route_metadata")),
                "redirect_from": safe_route(event.get("redirect_from_metadata")),
                "status_code": safe_status(event.get("status_code")),
                "redirect_status_code": safe_status(event.get("redirect_status_code")),
            }
        )
    return summary


def safe_refresh_header_metadata(value: object, response_url: object) -> dict[str, object]:
    """Reduce a Refresh response header to a delay and sanitized destination route."""
    result: dict[str, object] = {
        "present": isinstance(value, str) and bool(value.strip()),
        "parseable": False,
        "delay_ms": None,
        "target_route": {},
    }
    if not result["present"] or not isinstance(value, str) or len(value) > 4096:
        return result
    match = re.fullmatch(
        r"\s*(\d+(?:\.\d+)?)\s*;\s*url\s*=\s*(.*?)\s*",
        value,
        flags=re.IGNORECASE,
    )
    if match is None:
        return result
    target = match.group(2).strip()
    if len(target) >= 2 and target[0] == target[-1] and target[0] in {"'", '"'}:
        target = target[1:-1].strip()
    if not target:
        return result
    try:
        seconds = float(match.group(1))
    except (OverflowError, ValueError):
        return result
    if not math.isfinite(seconds) or not isinstance(response_url, str):
        return result
    target_url = urljoin(response_url, target)
    result.update(
        {
            "parseable": True,
            "delay_ms": min(300_000, max(0, round(seconds * 1000))),
            "target_route": safe_url_metadata(target_url),
        }
    )
    return result


def safe_response_refresh_metadata(response: object) -> dict[str, object]:
    """Read only a Refresh header and discard all raw header/URL values."""
    absent = {
        "present": False,
        "parseable": False,
        "delay_ms": None,
        "target_route": {},
    }
    if not isinstance(response, dict):
        return absent
    headers = response.get("headers")
    response_url = response.get("url")
    if not isinstance(headers, dict):
        return absent
    for name, value in headers.items():
        if isinstance(name, str) and name.casefold() == "refresh":
            return safe_refresh_header_metadata(value, response_url)
    return absent


def safe_meta_refresh_facts(value: object) -> list[dict[str, object]]:
    """Keep only bounded metadata already extracted from rendered meta refresh tags."""
    allowed_query_keys = {"back", "controller", "id_lang", "isolang", "lang"}
    allowed_controllers = {"authentication", "password", "other"}
    if not isinstance(value, list):
        return []
    safe_facts: list[dict[str, object]] = []
    for fact in value[:3]:
        if not isinstance(fact, dict):
            continue
        delay_ms = fact.get("delay_ms")
        category = fact.get("target_controller_category")
        safe_facts.append(
            {
                "delay_ms": delay_ms
                if isinstance(delay_ms, int) and not isinstance(delay_ms, bool) and 0 <= delay_ms <= 300_000
                else None,
                "target_present": fact.get("target_present") is True,
                "target_same_origin": fact.get("target_same_origin")
                if isinstance(fact.get("target_same_origin"), bool)
                else None,
                "target_index_php": fact.get("target_index_php") is True,
                "target_controller_category": category
                if isinstance(category, str) and category in allowed_controllers
                else "other"
                if category
                else "",
                "target_query_key_names": sorted(
                    {key for key in fact.get("target_query_key_names", []) if isinstance(key, str)}
                    & allowed_query_keys
                )
                if isinstance(fact.get("target_query_key_names"), list)
                else [],
            }
        )
    return safe_facts


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

    # CDP reuses requestId across redirects. Associate responses with each
    # request event so a final 404 cannot overwrite an earlier redirect's 302.
    pending_requests: dict[str, int] = {}
    responses: dict[int, dict[str, object]] = {}
    response_timestamps: dict[int, float] = {}
    decoded_entries: list[dict[str, object]] = []
    request_timestamps: list[float] = []
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
                request_event_id = pending_requests.get(request_id) if isinstance(request_id, str) else None
                if request_event_id is not None and isinstance(status, (int, float)):
                    responses[request_event_id] = {"status": int(status), "response": response}
                    response_timestamp = params.get("timestamp")
                    if isinstance(response_timestamp, (int, float)) and not isinstance(response_timestamp, bool):
                        response_timestamps[request_event_id] = float(response_timestamp)
            if message.get("method") == "Network.requestWillBeSent":
                request = params.get("request", {})
                request_timestamp = params.get("timestamp")
                request_id = params.get("requestId")
                if isinstance(request_id, str):
                    previous_request_id = pending_requests.get(request_id)
                    redirect_response = params.get("redirectResponse")
                    if previous_request_id is not None and isinstance(redirect_response, dict):
                        responses[previous_request_id] = {
                            "status": redirect_response.get("status"),
                            "response": redirect_response,
                        }
                        if isinstance(request_timestamp, (int, float)) and not isinstance(request_timestamp, bool):
                            response_timestamps[previous_request_id] = float(request_timestamp)
                    pending_requests[request_id] = id(message)
                if (
                    isinstance(request, dict)
                    and isinstance(request_timestamp, (int, float))
                    and not isinstance(request_timestamp, bool)
                ):
                    request_timestamps.append(float(request_timestamp))
            decoded_entries.append(message)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue

    main_frame_id = top_level_frame_id(driver)
    navigation_start = min(request_timestamps) if request_timestamps else None
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
        response_info = responses.get(id(message))
        response_info = response_info if isinstance(response_info, dict) else {}
        response_obj = response_info.get("response")
        response_obj = response_obj if isinstance(response_obj, dict) else {}
        status = response_info.get("status")
        redirect_status = redirect_response.get("status") if isinstance(redirect_response, dict) else None
        response_for_refresh = response_obj
        request_timestamp = params.get("timestamp")
        response_timestamp = response_timestamps.get(id(message))
        request_elapsed_ms = (
            min(300_000, max(0, round((float(request_timestamp) - navigation_start) * 1000)))
            if isinstance(request_timestamp, (int, float))
            and not isinstance(request_timestamp, bool)
            and isinstance(navigation_start, float)
            else None
        )
        response_elapsed_ms = (
            min(300_000, max(0, round((response_timestamp - navigation_start) * 1000)))
            if isinstance(response_timestamp, float) and isinstance(navigation_start, float)
            else None
        )
        initiator = params.get("initiator", {})
        initiator = initiator if isinstance(initiator, dict) else {}
        initiator_type = initiator.get("type")
        allowed_initiator_types = {
            "address_bar", "other", "parser", "preload", "script", "signedExchange", "serviceWorker"
        }
        if not isinstance(initiator_type, str) or initiator_type not in allowed_initiator_types:
            initiator_type = "unknown"
        stack = initiator.get("stack", {})
        stack = stack if isinstance(stack, dict) else {}
        frames: list[dict[str, object]] = []
        async_parent_count = 0
        seen_stacks: set[int] = set()
        while isinstance(stack, dict) and id(stack) not in seen_stacks and len(seen_stacks) < 8:
            seen_stacks.add(id(stack))
            stack_frames = stack.get("callFrames", [])
            if isinstance(stack_frames, list):
                frames.extend(frame for frame in stack_frames if isinstance(frame, dict))
            parent_stack = stack.get("parent")
            if not isinstance(parent_stack, dict):
                break
            async_parent_count += 1
            stack = parent_stack
        first_frame = frames[0] if frames else {}
        initiator_url = first_frame.get("url") or initiator.get("url")
        line_number = first_frame.get("lineNumber", initiator.get("lineNumber"))
        column_number = first_frame.get("columnNumber", initiator.get("columnNumber"))
        line_number = (
            min(max(int(line_number), 0), 1_000_000)
            if isinstance(line_number, (int, float)) and not isinstance(line_number, bool)
            else None
        )
        column_number = (
            min(max(int(column_number), 0), 1_000_000)
            if isinstance(column_number, (int, float)) and not isinstance(column_number, bool)
            else None
        )
        safe_events.append(
            {
                "event": "document_redirect" if isinstance(redirect_response, dict) else "document_request",
                "route_metadata": route_metadata,
                "redirect_from_metadata": redirect_metadata or {},
                "frame_scope": safe_document_frame_scope(params.get("frameId"), main_frame_id),
                "initiator_type": initiator_type,
                "initiator_scope": safe_initiator_scope(initiator_url),
                "initiator_stack_depth": min(len(frames), 20),
                "initiator_async_parent_count": min(async_parent_count, 8),
                "initiator_line_number": line_number,
                "initiator_column_number": column_number,
                "initiator_has_url": isinstance(initiator_url, str) and bool(initiator_url),
                "request_elapsed_ms": request_elapsed_ms,
                "response_elapsed_ms": response_elapsed_ms,
                "response_refresh": safe_response_refresh_metadata(response_for_refresh),
                "status_code": int(status)
                if isinstance(status, (int, float)) and 0 <= status <= 599
                else 0,
                "redirect_status_code": int(redirect_status)
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
    state: dict[str, object],
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
        "registration_target_route_metadata": state.get("target_route_metadata", {}),
        "registration_before_click_route_metadata": state.get("before_click_route_metadata", {}),
        "registration_after_click_route_metadata": state.get("after_click_route_metadata", {}),
        "registration_target_route_matched": safe_diagnostic_boolean(
            state.get("target_route_matched")
        ),
        "registration_document_language": safe_diagnostic_name(
            state.get("document_language", "")
        ),
        "registration_url_changed": safe_diagnostic_boolean(state.get("url_changed")),
        "registration_center_unobstructed": safe_diagnostic_boolean(
            state.get("center_unobstructed", diagnostics.get("registration_center_unobstructed"))
        ),
        "registration_navigation_events": safe_registration_navigation_summary(
            state.get("navigation_events")
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


def accept_profile_update_disclosures(driver: webdriver.Chrome) -> None:
    """Accept only the synthetic CI customer's two required profile disclosures."""
    for name in ("customer_privacy", "psgdpr"):
        selector = f'#customer-form input[type="checkbox"][name="{name}"]'
        checkbox = visible(driver, selector)
        if not checkbox.is_displayed() or not checkbox.is_enabled():
            raise AssertionError(f"profile update disclosure {name} is not available for the CI customer")
        if not checkbox.is_selected():
            try:
                checkbox.click()
            except ElementClickInterceptedException:
                checkbox.send_keys(Keys.SPACE)
            try:
                WebDriverWait(driver, 5, poll_frequency=0.1).until(
                    lambda _browser: checkbox.is_selected()
                )
            except TimeoutException:
                checkbox = visible(driver, selector)
                if not checkbox.is_selected():
                    checkbox.send_keys(Keys.SPACE)
                WebDriverWait(driver, 5, poll_frequency=0.1).until(
                    lambda _browser: checkbox.is_selected()
                )
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
    fill(driver, '#login-form input[name="email"]', email_address)
    fill(driver, '#login-form input[name="password"]', password)
    visible(driver, "#submit-login").click()
    login_result = WebDriverWait(driver, 30).until(collect_email_login_result)
    if login_result == "rejected":
        raise AssertionError("customer email login was rejected")


def assert_login_rejected(driver: webdriver.Chrome, email_address: str, password: str) -> None:
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


def collect_email_login_result(driver: webdriver.Chrome) -> str | bool:
    return driver.execute_script(
        r"""
        const isVisible = element => Boolean(element && element.getClientRects().length);
        const identityLink = document.getElementById('identity_main_link');
        const signOutLink = document.querySelector('a.account-menu__link--signout');
        const loginForm = document.getElementById('login-form');
        const userMenuButton = document.getElementById('userMenuButton');
        const dangerAlerts = [...document.querySelectorAll('.alert.alert-danger[role="alert"]')]
          .filter(isVisible);
        if ((isVisible(identityLink) && isVisible(signOutLink)) || isVisible(userMenuButton)) return 'authenticated';
        if (isVisible(loginForm) && dangerAlerts.length) return 'rejected';
        if (!isVisible(loginForm) && document.readyState === 'complete') return 'transitioned';
        return false;
        """
    )


def collect_email_login_diagnostics(
    driver: webdriver.Chrome,
    substage: str,
    account_route_classification: str = "unavailable",
) -> dict[str, object]:
    try:
        current_url = driver.current_url
    except Exception:
        current_url = ""
    try:
        page_state = driver.execute_script(
            r"""
            const isVisible = element => Boolean(element && element.getClientRects().length);
            const alerts = [...document.querySelectorAll('.alert, [role="alert"]')].filter(isVisible);
            const alertClass = alerts[0]?.className;
            const alertClasses = typeof alertClass === 'string' ? alertClass.toLowerCase().split(/\s+/) : [];
            let alertClassification = 'none';
            if (alerts.length) {
              if (alertClasses.some(name => ['alert-danger', 'is-danger', 'error'].includes(name))) alertClassification = 'danger';
              else if (alertClasses.some(name => ['alert-success', 'is-success'].includes(name))) alertClassification = 'success';
              else if (alertClasses.some(name => ['alert-warning', 'is-warning'].includes(name))) alertClassification = 'warning';
              else if (alertClasses.some(name => ['alert-info', 'is-info'].includes(name))) alertClassification = 'info';
              else alertClassification = 'unknown';
            }
            const loginForm = document.getElementById('login-form');
            const emailField = loginForm?.querySelector('input[name="email"]');
            const submit = document.getElementById('submit-login');
            const identityLink = document.getElementById('identity_main_link');
            const signOutLink = document.querySelector('a.account-menu__link--signout');
            const userMenuButton = document.getElementById('userMenuButton');
            const dangerAlertVisible = alerts.some(alert => {
              const classes = typeof alert.className === 'string' ? alert.className.toLowerCase().split(/\s+/) : [];
              return classes.includes('alert-danger') || classes.includes('is-danger');
            });
            return {
              document_language: document.documentElement?.getAttribute('lang') || '',
              ready_state: document.readyState || '',
              login_form_visible: isVisible(loginForm),
              email_field_visible: isVisible(emailField),
              email_field_type_is_email: Boolean(emailField && emailField.getAttribute('type') === 'email'),
              login_submit_visible: isVisible(submit),
              login_submit_enabled: Boolean(submit && !submit.disabled),
              identity_link_visible: isVisible(identityLink),
              signout_link_visible: isVisible(signOutLink),
              user_menu_button_present: Boolean(userMenuButton),
              user_menu_button_visible: isVisible(userMenuButton),
              danger_alert_visible: dangerAlertVisible,
              visible_alert_count: Math.min(alerts.length, 20),
              alert_classification: alertClassification
            };
            """
        )
    except Exception as error:
        page_state = {"diagnostic_error_type": type(error).__name__}

    if not isinstance(page_state, dict):
        page_state = {"diagnostic_error_type": "InvalidSnapshot"}
    alert_classification = page_state.get("alert_classification")
    if alert_classification not in {"none", "success", "danger", "warning", "info", "unknown"}:
        alert_classification = "unavailable"
    visible_alert_count = page_state.get("visible_alert_count")
    if not isinstance(visible_alert_count, int) or isinstance(visible_alert_count, bool):
        visible_alert_count = None
    else:
        visible_alert_count = min(max(visible_alert_count, 0), 20)
    try:
        login_result = collect_email_login_result(driver)
        login_result_error_type = ""
    except Exception as error:
        login_result = "unavailable"
        login_result_error_type = safe_diagnostic_name(type(error).__name__, field_type=True)
    if login_result is False:
        login_result = "pending"
    elif login_result not in {"authenticated", "rejected", "unavailable"}:
        login_result = "unknown"
    if account_route_classification not in {
        "account",
        "identity",
        "other",
        "outside_shop",
        "root",
        "unavailable",
    }:
        account_route_classification = "unavailable"
    safe_state: dict[str, object] = {
        "substage": safe_diagnostic_name(substage),
        "path": safe_same_origin_path(current_url),
        "account_route_classification": account_route_classification,
        "login_result": login_result,
        "login_result_error_type": login_result_error_type,
        "document_language": re.sub(r"[^A-Za-z0-9-]", "", str(page_state.get("document_language") or ""))[:12],
        "ready_state": safe_diagnostic_name(page_state.get("ready_state")),
        "login_form_visible": safe_diagnostic_boolean(page_state.get("login_form_visible")),
        "email_field_visible": safe_diagnostic_boolean(page_state.get("email_field_visible")),
        "email_field_type_is_email": safe_diagnostic_boolean(page_state.get("email_field_type_is_email")),
        "login_submit_visible": safe_diagnostic_boolean(page_state.get("login_submit_visible")),
        "login_submit_enabled": safe_diagnostic_boolean(page_state.get("login_submit_enabled")),
        "identity_link_visible": safe_diagnostic_boolean(page_state.get("identity_link_visible")),
        "signout_link_visible": safe_diagnostic_boolean(page_state.get("signout_link_visible")),
        "user_menu_button_present": safe_diagnostic_boolean(page_state.get("user_menu_button_present")),
        "user_menu_button_visible": safe_diagnostic_boolean(page_state.get("user_menu_button_visible")),
        "danger_alert_visible": safe_diagnostic_boolean(page_state.get("danger_alert_visible")),
        "visible_alert_count": visible_alert_count,
        "alert_classification": alert_classification,
    }
    diagnostic_error = page_state.get("diagnostic_error_type")
    if isinstance(diagnostic_error, str):
        safe_state["diagnostic_error_type"] = safe_diagnostic_name(diagnostic_error, field_type=True)
    return safe_state


def emit_email_login_diagnostics(
    driver: webdriver.Chrome,
    substage: str,
    account_route_classification: str = "unavailable",
) -> None:
    safe_state_json = json.dumps(
        collect_email_login_diagnostics(driver, substage, account_route_classification),
        ensure_ascii=True,
        sort_keys=True,
    )
    print("ORDENOWA_ACCOUNT_EMAIL_LOGIN_SAFE_STATE=" + safe_state_json, file=sys.stderr)
    annotation = safe_state_json.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(
        f"::error title=Customer account email login safe state::{annotation}",
        file=sys.stderr,
    )


def wait_for_signed_out_state(driver: webdriver.Chrome) -> None:
    WebDriverWait(driver, 30).until(
        lambda browser: browser.execute_script(
            """
            const hasVisibleSignoutLink = [...document.querySelectorAll('a.account-menu__link--signout')]
              .some(link => link.getClientRects().length > 0);
            return !document.getElementById('userMenuButton') && !hasVisibleSignoutLink;
            """
        )
    )


def logout(
    driver: webdriver.Chrome,
    *,
    login_url: str,
    substage_callback: Callable[[str], None] | None = None,
    account_route_callback: Callable[[str], None] | None = None,
) -> str:
    def mark_substage(value: str) -> None:
        if substage_callback is not None:
            substage_callback(value)

    mark_substage("resolve_account_link")
    _, account_url = my_account_link_from_header(driver, open_menu=False)
    if account_route_callback is not None:
        account_route_callback(safe_account_route_classification(account_url))

    mark_substage("open_account")
    driver.get(account_url)
    mark_substage("wait_authenticated")
    visible(driver, "#identity_main_link")

    mark_substage("resolve_signout_link")
    link = visible_signout_link(driver)
    mark_substage("click_signout")
    link.click()
    mark_substage("wait_signed_out")
    wait_for_signed_out_state(driver)

    mark_substage("reopen_account")
    driver.get(account_url)
    mark_substage("verify_protected_route_signed_out")
    WebDriverWait(driver, 30).until(lambda browser: browser.execute_script("return document.readyState") == "complete")
    if any(element.is_displayed() for element in driver.find_elements(By.ID, "identity_main_link")):
        raise AssertionError("the signed-out customer can still open My Page")
    if any(element.is_displayed() for element in driver.find_elements(By.ID, "userMenuButton")):
        raise AssertionError("the protected account route still shows an authenticated user menu")

    if any(
        link.is_displayed()
        for link in driver.find_elements(By.CSS_SELECTOR, "a.account-menu__link--signout")
    ):
        raise AssertionError("the protected account route still shows an authenticated signout control")

    mark_substage("open_generated_login")
    driver.get(login_url)
    mark_substage("wait_login_form")
    visible(driver, '#login-form input[name="email"]')
    WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "submit-login")))
    return account_url


def run_viewport(width: int, height: int, label: str) -> bool:
    stage = "registration_link_load"
    failure_control = {"name": "display-register-form", "type": "anchor"}
    profile_pre_submit: dict[str, object] | None = None
    korean_login_state: dict[str, object] = {}
    registration_state: dict[str, object] = {}
    login_url = ""
    account_url = ""
    email_login_substage = ""
    email_login_account_route_classification = "unavailable"
    expected_first_name = f"CI-{label.title()}"
    driver = None
    success = False

    def mark_email_login_substage(value: str) -> None:
        nonlocal email_login_substage
        email_login_substage = value

    def mark_email_login_account_route_classification(value: str) -> None:
        nonlocal email_login_account_route_classification
        email_login_account_route_classification = value

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
        try:
            driver.execute_cdp_cmd("Debugger.enable", {})
            driver.execute_cdp_cmd("Debugger.setAsyncCallStackDepth", {"maxDepth": 16})
            korean_login_state["async_stack_capture_enabled"] = True
        except Exception:
            korean_login_state["async_stack_capture_enabled"] = False
        stage = "korean_email_login_label"
        failure_control = {"name": "", "type": ""}
        login_url = assert_korean_email_login_form(driver, korean_login_state)
        driver.save_screenshot(str(DEST / f"{label}-korean-login-email.png"))

        account_email = f"qa-ordenowa-{RUN_ID}-{RUN_ATTEMPT}-{label}@example.invalid"
        initial_password = f"Ordenowa-CI-{RUN_ID}-{RUN_ATTEMPT}!"
        reset_password = f"Ordenowa-Reset-{RUN_ID}-{RUN_ATTEMPT}!"

        stage = "registration_link_load"
        set_registration_control(failure_control, "display-register-form", "anchor")
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
        registration_state["target_route_metadata"] = safe_url_metadata(registration_url)
        registration_state["before_click_route_metadata"] = safe_url_metadata(driver.current_url)
        registration_pre_click_url = driver.current_url
        stage = "registration_link_click"
        set_registration_control(failure_control, "display-register-form", "anchor")
        clear_document_navigation_events(driver)
        try:
            registration_state["center_unobstructed"] = click_centered(driver, registration_link)
        finally:
            try:
                registration_after_click_url = driver.current_url
            except Exception:
                registration_after_click_url = ""
            registration_state["after_click_route_metadata"] = safe_url_metadata(
                registration_after_click_url
            )
            registration_state["url_changed"] = (
                bool(registration_after_click_url)
                and registration_after_click_url != registration_pre_click_url
            )
            registration_state["target_route_matched"] = safe_generated_route_match(
                registration_after_click_url, registration_url
            )
            registration_state["navigation_events"] = document_navigation_events(driver)
        stage = "registration_form_load"
        set_registration_control(failure_control, "customer-form", "form")
        registration_document_language = (
            driver.find_element(By.TAG_NAME, "html").get_attribute("lang") or ""
        ).lower()
        registration_state["document_language"] = safe_diagnostic_name(
            registration_document_language
        )
        if not registration_document_language.startswith("ko"):
            raise AssertionError("the generated registration route did not preserve Korean")
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
        accept_profile_update_disclosures(driver)
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
        email_login_substage = "logout"
        account_url = logout(
            driver,
            login_url=login_url,
            substage_callback=mark_email_login_substage,
            account_route_callback=mark_email_login_account_route_classification,
        )
        email_login_substage = "login_form"
        email_field = visible(driver, '#login-form input[name="email"]')
        if email_field.get_attribute("type") != "email":
            raise AssertionError("customer login is not email-based")
        fill(driver, '#login-form input[name="email"]', account_email)
        fill(driver, '#login-form input[name="password"]', initial_password)
        email_login_substage = "submit"
        visible(driver, "#submit-login").click()
        email_login_substage = "auth_result"
        login_result = WebDriverWait(driver, 30).until(collect_email_login_result)
        if login_result not in {"authenticated", "transitioned"}:
            raise AssertionError("customer email login was rejected")
        email_login_substage = "my_page"
        driver.get(account_url)
        assert_my_page(driver, f"CI-{label.title()}")
        driver.save_screenshot(str(DEST / f"{label}-customer-email-login.png"))

        stage = "password_reset_request"
        logout(driver, login_url=login_url)
        recovery_link = visible(driver, "#login-form a[href]")
        recovery_url = urljoin(driver.current_url, recovery_link.get_attribute("href") or "")
        recovery_location = urlparse(recovery_url)
        base_location = urlparse(BASE)
        if (
            recovery_location.scheme != base_location.scheme
            or recovery_location.hostname != base_location.hostname
            or recovery_location.port != base_location.port
        ):
            raise AssertionError("the password recovery link changed the isolated shop origin")
        recovery_route_path = urlparse(recovery_url).path
        click_centered(driver, recovery_link)
        assert_route_path_matches(driver, recovery_route_path, "password recovery")
        fill(driver, '#email', account_email)
        visible(driver, "#send-reset-link").click()
        driver.save_screenshot(str(DEST / f"{label}-password-reset-requested.png"))
        # The independent reset-email brand browser step verifies the inline logo.
        reset_url, _ = reset_link_for(account_email, recovery_route_path)

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
        assert_route_path_matches(driver, recovery_route_path, "password reset")
        fill(driver, '#field-password[name="passwd"]', reset_password)
        fill(driver, '#field-confirmation-passwd[name="confirmation"]', reset_password)
        visible(driver, 'button[type="submit"][name="submit"]').click()

        stage = "password_reset_old_password_rejected"
        driver.get(account_url)
        assert_my_page(driver, f"CI-{label.title()}")
        logout(driver, login_url=login_url)
        assert_login_rejected(driver, account_email, initial_password)

        stage = "password_reset_login"
        email_login_substage = "password_reset_submit"
        submit_login(driver, account_email, reset_password)
        email_login_substage = "password_reset_my_page"
        driver.get(account_url)
        assert_my_page(driver, f"CI-{label.title()}")
        driver.save_screenshot(str(DEST / f"{label}-customer-password-reset-login.png"))
        email_login_substage = "password_reset_logout"
        logout(
            driver,
            login_url=login_url,
            substage_callback=mark_email_login_substage,
        )
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
                    emit_registration_diagnostics(driver, stage, failure_control, registration_state)
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
            elif stage in {"email_login", "password_reset_login"}:
                try:
                    emit_email_login_diagnostics(
                        driver,
                        email_login_substage,
                        email_login_account_route_classification,
                    )
                except Exception:
                    pass
        inner_stage = (
            safe_korean_login_stage(korean_login_state.get("stage"))
            if stage == "korean_email_login_label"
            else ""
        )
        inner_stage_detail = f"; inner_stage={inner_stage}" if inner_stage else ""
        email_login_substage_detail = (
            f"; email_login_substage={safe_diagnostic_name(email_login_substage)}"
            if stage in {"email_login", "password_reset_login"} and email_login_substage
            else ""
        )
        print(
            f"FAIL: {label} customer account flow at {stage}{inner_stage_detail}{email_login_substage_detail} "
            f"({type(error).__name__})",
            file=sys.stderr,
        )
        print(
            f"::error title=Customer account browser QA::{label} failed at {stage} "
            f"({type(error).__name__}){inner_stage_detail}{email_login_substage_detail}; "
            f"control_name={failure_control.get('name') or 'none'}; "
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
