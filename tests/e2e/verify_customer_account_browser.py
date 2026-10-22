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
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
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
                    allowed_host = parsed.hostname in {"localhost", "127.0.0.1"}
                    if allowed_host and has_token and is_password_route:
                        return reset_url, detail
        except (OSError, URLError, ValueError, json.JSONDecodeError):
            pass
        time.sleep(0.5)
    raise TimeoutException("password reset email did not arrive in the isolated mailbox")


def visible(driver: webdriver.Chrome, selector: str):
    return WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))


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


def set_registration_control(control: dict[str, str], name: str, field_type: str) -> None:
    control["name"] = re.sub(r"[^A-Za-z0-9_.\[\]-]", "_", name)[:80]
    control["type"] = re.sub(r"[^A-Za-z0-9_-]", "_", field_type)[:40]


def emit_registration_diagnostics(
    driver: webdriver.Chrome,
    stage: str,
    control: dict[str, str],
) -> None:
    diagnostics = driver.execute_script(
        r"""
        const form = document.querySelector('#customer-form');
        const isVisible = element => Boolean(element && element.getClientRects().length);
        const invalid = form ? [...form.querySelectorAll(':invalid')].filter(isVisible) : [];
        const email = form?.querySelector('input[name="email"]');
        const passwords = form ? [...form.querySelectorAll('input[type="password"]')] : [];
        const submit = form?.querySelector('button.form-control-submit');
        const registrationLink = document.querySelector('a[data-link-action="display-register-form"]');
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
    print(
        "ORDENOWA_ACCOUNT_REGISTRATION_DIAGNOSTICS=" + json.dumps(diagnostics, ensure_ascii=False, sort_keys=True),
        file=sys.stderr,
    )


def fill(driver: webdriver.Chrome, selector: str, value: str) -> None:
    element = visible(driver, selector)
    element.clear()
    element.send_keys(value)


def assert_my_page(driver: webdriver.Chrome, expected_first_name: str) -> None:
    for selector in ("#identity_main_link", "#signout_link"):
        visible(driver, selector)

    page_text = driver.find_element(By.TAG_NAME, "body").text
    if expected_first_name not in page_text or "Customer" not in page_text:
        raise AssertionError("My Page did not show the signed-in customer's saved name")


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
            element.click()
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


def submit_login(driver: webdriver.Chrome, email_address: str, password: str) -> None:
    driver.get(f"{BASE}/index.php?controller=authentication")
    fill(driver, '#login-form input[name="email"]', email_address)
    fill(driver, '#login-form input[name="password"]', password)
    visible(driver, "#submit-login").click()
    WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "identity_main_link")))


def logout(driver: webdriver.Chrome) -> None:
    link = visible(driver, "a.account-menu__link--signout")
    link.click()
    driver.get(f"{BASE}/index.php?controller=my-account")
    WebDriverWait(driver, 30).until(
        lambda browser: bool(browser.find_elements(By.CSS_SELECTOR, '#login-form input[name="email"]'))
        or bool(browser.find_elements(By.ID, "identity_main_link"))
    )
    if driver.find_elements(By.ID, "identity_main_link"):
        raise AssertionError("the signed-out customer can still open My Page")
    visible(driver, '#login-form input[name="email"]')
    WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "submit-login")))
    if driver.find_elements(By.ID, "signout_link") or driver.find_elements(By.CSS_SELECTOR, "a.account-menu__link--signout"):
        raise AssertionError("the customer still has an authenticated My Page session after logout")


def run_viewport(width: int, height: int, label: str) -> None:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--lang=ja-JP")
    driver = webdriver.Chrome(options=options)
    stage = "registration_link_load"
    failure_control = {"name": "display-register-form", "type": "anchor"}
    try:
        driver.set_window_size(width, height)
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
            or registration_location.hostname not in {"localhost", "127.0.0.1"}
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
        visible(driver, "#customer-form button.form-control-submit").click()
        stage = "registration_post_submit"
        failure_control = {"name": "", "type": ""}
        WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "identity_main_link")))
        assert_my_page(driver, "CI")
        driver.save_screenshot(str(DEST / f"{label}-customer-account-created.png"))

        stage = "profile_update"
        driver.get(f"{BASE}/index.php?controller=identity")
        first_name = visible(driver, '#customer-form input[name="firstname"]')
        first_name.clear()
        first_name.send_keys(f"CI-{label.title()}")
        visible(driver, "#customer-form button.form-control-submit").click()
        WebDriverWait(driver, 30).until(
            lambda browser: browser.find_element(By.CSS_SELECTOR, '#customer-form input[name="firstname"]').get_attribute("value")
            == f"CI-{label.title()}"
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
            or parsed_reset.hostname not in {"localhost", "127.0.0.1"}
            or parsed_reset.port != base.port
        ):
            raise AssertionError("password reset email points outside the isolated shop")
        driver.get(reset_url)
        fill(driver, '#field-password[name="passwd"]', reset_password)
        fill(driver, '#field-confirmation-passwd[name="confirmation"]', reset_password)
        visible(driver, 'button[type="submit"][name="submit"]').click()

        stage = "password_reset_login"
        submit_login(driver, account_email, reset_password)
        assert_my_page(driver, f"CI-{label.title()}")
        driver.save_screenshot(str(DEST / f"{label}-customer-password-reset-login.png"))
        logout(driver)
        print(f"PASS: {label} customer registration, profile update, email login/logout, and Mailpit password reset")
    except Exception as error:
        try:
            driver.save_screenshot(str(DEST / f"{label}-customer-account-failure.png"))
        except Exception:
            pass
        if stage.startswith("registration_"):
            try:
                emit_registration_diagnostics(driver, stage, failure_control)
            except Exception:
                pass
        print(f"FAIL: {label} customer account flow at {stage} ({type(error).__name__})", file=sys.stderr)
        print(f"::error title=Customer account browser QA::{label} failed at {stage} ({type(error).__name__})", file=sys.stderr)
        raise SystemExit("isolated customer account browser flow failed") from None
    finally:
        driver.quit()


if __name__ == "__main__":
    for viewport in ((1440, 960, "desktop"), (390, 844, "mobile")):
        run_viewport(*viewport)
