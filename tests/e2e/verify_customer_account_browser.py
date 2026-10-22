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


def assert_korean_email_login_form(driver: webdriver.Chrome) -> None:
    # Use PrestaShop's generated language and account links. The Korean route
    # slug is installation metadata and must not be guessed as `/ko/login`.
    driver.get(f"{BASE}/")
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
    driver.get(korean_language_url)

    document_language = (driver.find_element(By.TAG_NAME, "html").get_attribute("lang") or "").lower()
    if not document_language.startswith("ko"):
        raise AssertionError("the generated Korean language destination did not render Korean")

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
    driver.get(login_url)

    visible(driver, "#login-form")
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

    password_reset_link = visible(driver, '#login-form a[href]')
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
    safe_segments = []
    for segment in path.split("/"):
        token_like_segment = (
            len(segment) >= 16
            and re.fullmatch(r"[A-Za-z0-9_-]+", segment)
            and re.search(r"[A-Za-z]", segment)
            and re.search(r"[0-9]", segment)
        )
        if len(segment) > 20 or token_like_segment or "@" in segment:
            safe_segments.append("<redacted>")
        else:
            safe_segments.append(re.sub(r"[^A-Za-z0-9_.-]", "_", segment))
    return "/".join(safe_segments)[:160] or "/"


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
        driver = webdriver.Chrome(options=options)
        driver.set_window_size(width, height)
        stage = "korean_email_login_label"
        assert_korean_email_login_form(driver)
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
