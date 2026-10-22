#!/usr/bin/env python3
"""Exercise native customer account flows in an isolated PrestaShop CI shop."""

from __future__ import annotations

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


def fill(driver: webdriver.Chrome, selector: str, value: str) -> None:
    element = visible(driver, selector)
    element.clear()
    element.send_keys(value)


def prepare_required_registration_fields(driver: webdriver.Chrome, email_address: str, password: str) -> None:
    form = visible(driver, "#customer-form")
    for name, value in (("firstname", "CI"), ("lastname", "Customer"), ("email", email_address)):
        fields = form.find_elements(By.CSS_SELECTOR, f'input[name="{name}"]')
        if fields:
            fields[0].clear()
            fields[0].send_keys(value)

    password_fields = form.find_elements(By.CSS_SELECTOR, 'input[type="password"]')
    if not password_fields:
        raise AssertionError("registration form does not expose a password field")
    password_fields[0].clear()
    password_fields[0].send_keys(password)

    selected_radio_groups: set[str] = set()
    for element in form.find_elements(By.CSS_SELECTOR, "input[required]"):
        if not element.is_displayed() or not element.is_enabled():
            continue
        field_type = (element.get_attribute("type") or "").lower()
        name = element.get_attribute("name") or ""
        if field_type == "checkbox" and not element.is_selected():
            element.click()
        elif field_type == "radio" and name not in selected_radio_groups:
            element.click()
            selected_radio_groups.add(name)

    for element in form.find_elements(By.CSS_SELECTOR, "select[required]"):
        if not element.is_displayed() or not element.is_enabled():
            continue
        select = Select(element)
        option = next((item for item in select.options if item.get_attribute("value")), None)
        if option is not None:
            select.select_by_value(option.get_attribute("value"))


def submit_login(driver: webdriver.Chrome, email_address: str, password: str) -> None:
    driver.get(f"{BASE}/index.php?controller=authentication")
    fill(driver, '#login-form input[name="email"]', email_address)
    fill(driver, '#login-form input[name="password"]', password)
    visible(driver, "#submit-login").click()
    WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "identity_main_link")))


def logout(driver: webdriver.Chrome) -> None:
    link = visible(driver, "a.account-menu__link--signout")
    link.click()
    WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "submit-login")))


def run_viewport(width: int, height: int, label: str) -> None:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--lang=ja-JP")
    driver = webdriver.Chrome(options=options)
    stage = "registration"
    try:
        driver.set_window_size(width, height)
        account_email = f"qa-ordenowa-{RUN_ID}-{RUN_ATTEMPT}-{label}@example.invalid"
        initial_password = f"Ordenowa-CI-{RUN_ID}-{RUN_ATTEMPT}!"
        reset_password = f"Ordenowa-Reset-{RUN_ID}-{RUN_ATTEMPT}!"

        driver.get(f"{BASE}/index.php?controller=authentication&create_account=1")
        prepare_required_registration_fields(driver, account_email, initial_password)
        visible(driver, "#customer-form button.form-control-submit").click()
        WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "identity_main_link")))
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

        stage = "password_reset"
        parsed_reset = urlparse(reset_url)
        base = urlparse(BASE)
        if parsed_reset.hostname not in {"localhost", "127.0.0.1"} or parsed_reset.port != base.port:
            raise AssertionError("password reset email points outside the isolated shop")
        driver.get(reset_url)
        fill(driver, '#field-password[name="passwd"]', reset_password)
        fill(driver, '#field-confirmation-passwd[name="confirmation"]', reset_password)
        visible(driver, 'button[type="submit"][name="submit"]').click()

        stage = "password_reset_login"
        submit_login(driver, account_email, reset_password)
        driver.save_screenshot(str(DEST / f"{label}-customer-password-reset-login.png"))
        logout(driver)
        print(f"PASS: {label} customer registration, profile update, email login/logout, and Mailpit password reset")
    except Exception as error:
        try:
            driver.save_screenshot(str(DEST / f"{label}-customer-account-failure.png"))
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
