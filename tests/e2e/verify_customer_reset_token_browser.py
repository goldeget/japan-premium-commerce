#!/usr/bin/env python3
"""Verify native PrestaShop reset tokens reject replayed and expired links."""

from __future__ import annotations

import json
import ipaddress
import os
import re
import subprocess
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
from selenium.webdriver.support.ui import WebDriverWait


BASE = os.environ["SHOP_BASE_URL"].rstrip("/")
MAILPIT_API = os.environ["MAILPIT_API_URL"].rstrip("/")
REPLAY_EMAIL = os.environ["REPLAY_CUSTOMER_EMAIL"].strip().lower()
EXPIRED_EMAIL = os.environ["EXPIRED_CUSTOMER_EMAIL"].strip().lower()
COMPOSE_PROJECT = os.environ["CI_COMPOSE_PROJECT_NAME"]
DEST = Path(os.environ["QA_ARTIFACT_DIR"])
DEST.mkdir(parents=True, exist_ok=True)

EXPECTED_SHOP_PORT = 18080
EXPECTED_MAILPIT_PORT = 8025


class ResetLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attributes = {name.lower(): value or "" for name, value in attrs}
        if attributes.get("href"):
            self.hrefs.append(attributes["href"])


def request_json(url: str) -> dict:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("isolated Mailpit response was not an object")
    return payload


def recipients(message: dict) -> set[str]:
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


def same_origin(candidate: str) -> bool:
    actual = urlparse(candidate)
    expected = urlparse(BASE)
    return (actual.scheme, actual.hostname, actual.port) == (
        expected.scheme,
        expected.hostname,
        expected.port,
    )


def wait_for_reset_url(email: str, expected_path: str, timeout_seconds: int = 90) -> str:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            listing = request_json(
                f"{MAILPIT_API}/api/v1/messages?{urlencode({'start': 0, 'limit': 100})}"
            )
            for message in listing.get("messages", []):
                if not isinstance(message, dict) or email not in recipients(message):
                    continue
                message_id = message.get("ID") or message.get("Id")
                if not isinstance(message_id, str) or not message_id:
                    continue
                detail = request_json(f"{MAILPIT_API}/api/v1/message/{quote(message_id, safe='')}")
                parser = ResetLinks()
                parser.feed(str(detail.get("HTML") or ""))
                candidates = list(parser.hrefs)
                if isinstance(detail.get("Text"), str):
                    import re

                    candidates.extend(re.findall(r"https?://[^\s<>\"']+", detail["Text"]))
                for candidate in candidates:
                    destination = urljoin(BASE + "/", candidate.rstrip(".,);]"))
                    parsed = urlparse(destination)
                    if not same_origin(destination):
                        continue
                    if unquoted_path(parsed.path) != unquoted_path(expected_path):
                        continue
                    query = parse_qs(parsed.query)
                    if "token" in query and ("reset_token" in query or "id_customer" in query):
                        return destination
        except (OSError, URLError, ValueError, json.JSONDecodeError):
            pass
        time.sleep(0.5)
    raise TimeoutException("the isolated reset-token link did not arrive in Mailpit")


def unquoted_path(path: str) -> str:
    from urllib.parse import unquote

    return unquote(path, errors="strict").rstrip("/") or "/"


def visible(driver: webdriver.Chrome, selector: str):
    return WebDriverWait(driver, 30).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
    )


def new_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,960")
    options.add_argument("--lang=ja-JP")
    return webdriver.Chrome(options=options)


def send_reset_request(driver: webdriver.Chrome, email: str) -> tuple[str, str]:
    validate_isolated_ci_compose_project()
    validate_loopback_endpoints()
    driver.get(BASE + "/")
    sign_in = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "#_desktop_ps_customersignin a[href], #_mobile_ps_customersignin a[href]")
        )
    )
    login_url = urljoin(driver.current_url, sign_in.get_attribute("href") or "")
    if not same_origin(login_url):
        raise AssertionError("the customer sign-in route left the isolated storefront")
    driver.get(login_url)
    recovery = visible(driver, "#login-form a[href]")
    recovery_url = urljoin(driver.current_url, recovery.get_attribute("href") or "")
    if not same_origin(recovery_url):
        raise AssertionError("the recovery route left the isolated storefront")
    expected_reset_path = urlparse(recovery_url).path
    driver.get(recovery_url)
    visible(driver, "#email").send_keys(email)
    visible(driver, "#send-reset-link").click()
    return wait_for_reset_url(email, expected_reset_path), expected_reset_path


def expire_reset_token_in_isolated_container(email: str) -> None:
    validate_isolated_ci_compose_project()
    validate_loopback_endpoints()
    php = r'''$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require_once '/var/www/html/config/config.inc.php';
$email = (string) getenv('ORDENOWA_RESET_TEST_EMAIL');
$customer = new Customer();
if (!$customer->getByEmail($email) || !(int) $customer->id || !$customer->reset_password_token) {
    fwrite(STDERR, "missing isolated reset-token fixture\n");
    exit(2);
}
if ($customer->getValidResetPasswordToken() !== $customer->reset_password_token) {
    fwrite(STDERR, "reset-token fixture was not valid before expiry\n");
    exit(3);
}
$customer->reset_password_validity = date('Y-m-d H:i:s', time() - 120);
if (!$customer->update()) {
    fwrite(STDERR, "could not expire isolated reset-token fixture\n");
    exit(4);
}
$reloaded = new Customer((int) $customer->id);
if ($reloaded->getValidResetPasswordToken() !== false) {
    fwrite(STDERR, "expired reset-token fixture remained valid\n");
    exit(5);
}
echo "PASS: isolated token fixture expired\n";'''
    command = [
        "docker",
        "compose",
        "-p",
        COMPOSE_PROJECT,
        "exec",
        "-T",
        "--user",
        "www-data",
        "--env",
        f"ORDENOWA_RESET_TEST_EMAIL={email}",
        "prestashop",
        "php",
        "-r",
        php,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0 or "PASS: isolated token fixture expired" not in result.stdout:
        raise RuntimeError("the reset-token expiry fixture could not be prepared in the isolated CI container")


def validate_isolated_ci_compose_project() -> None:
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    expected_project = f"kuranea-ci-{run_id}-{attempt}"
    if (
        os.environ.get("CI") != "true"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("KURANEA_ISOLATED_CI") != "1"
        or not run_id.isascii()
        or not run_id.isdecimal()
        or not attempt.isascii()
        or not attempt.isdecimal()
        or not COMPOSE_PROJECT
        or COMPOSE_PROJECT != expected_project
        or os.environ.get("CI_COMPOSE_PROJECT_NAME", "") != expected_project
    ):
        raise ValueError("reset-token expiry requires the exact isolated GitHub Actions Compose project")


def _validate_loopback_endpoint(value: str, expected_port: int, label: str) -> tuple[str, str, int]:
    try:
        parsed = urlparse(value)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        raise ValueError(f"{label} must be a valid isolated loopback URL") from None
    if host.lower() == "localhost":
        is_loopback = True
    else:
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            is_loopback = False
    if (
        parsed.scheme != "http"
        or not is_loopback
        or port != expected_port
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} must use its isolated loopback service on port {expected_port}")
    return parsed.scheme, host.lower(), port


def validate_loopback_endpoints() -> None:
    _validate_loopback_endpoint(BASE, EXPECTED_SHOP_PORT, "SHOP_BASE_URL")
    _validate_loopback_endpoint(MAILPIT_API, EXPECTED_MAILPIT_PORT, "MAILPIT_API_URL")


def is_native_expired_reset_message(message: str) -> bool:
    normalized = " ".join(message.split()).casefold()
    if "password change request expired" in normalized:
        return True
    if "パスワード" in message and any(marker in message for marker in ("期限", "有効期限", "期限切れ")):
        return True
    return "비밀번호" in message and any(marker in message for marker in ("만료", "유효기간", "기한"))


def assert_reset_link_rejected(
    driver: webdriver.Chrome,
    reset_url: str,
    expected_reset_path: str,
    artifact: str,
) -> None:
    if not same_origin(reset_url):
        raise AssertionError("the rejected reset link left the isolated shop origin")
    driver.get(reset_url)
    WebDriverWait(driver, 30).until(
        lambda browser: unquoted_path(urlparse(browser.current_url).path)
        == unquoted_path(expected_reset_path)
    )
    recovery_form = visible(driver, "form.forgotten-password #send-reset-link")
    danger = visible(driver, "form.forgotten-password .alert.alert-danger[role='alert']")
    if not is_native_expired_reset_message(danger.text):
        raise AssertionError("the native reset route did not report its expired password-change request")
    if driver.find_elements(By.CSS_SELECTOR, '#field-password[name="passwd"]'):
        raise AssertionError("the invalid reset token still opened a password change form")
    if not recovery_form.is_displayed() or not same_origin(driver.current_url):
        raise AssertionError("the rejected link did not return to the native password-recovery route")
    driver.save_screenshot(str(DEST / artifact))


def assert_customer_can_login_with_password(email: str, password: str) -> None:
    driver = new_driver()
    try:
        driver.get(BASE + "/")
        sign_in = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#_desktop_ps_customersignin a[href], #_mobile_ps_customersignin a[href]")
            )
        )
        login_url = urljoin(driver.current_url, sign_in.get_attribute("href") or "")
        if not same_origin(login_url):
            raise AssertionError("the reset-success login route left the isolated shop")
        driver.get(login_url)
        visible(driver, '#login-form input[name="email"]').send_keys(email)
        visible(driver, '#login-form input[name="password"]').send_keys(password)
        visible(driver, "#submit-login").click()
        visible(driver, "#userMenuButton")
        visible(driver, "#userMenuButton").click()
        account_link = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#_desktop_ps_customersignin .dropdown-menu a[href]")
            )
        )
        account_url = urljoin(driver.current_url, account_link.get_attribute("href") or "")
        if not same_origin(account_url):
            raise AssertionError("the reset-success account link left the isolated shop")
        driver.get(account_url)
        visible(driver, "#identity_main_link")
        visible(driver, "a.account-menu__link--signout")
    finally:
        driver.quit()


def replay_scenario() -> None:
    stage = "replay_request"
    request_driver = None
    replay_driver = None
    try:
        request_driver = new_driver()
        reset_url, expected_reset_path = send_reset_request(request_driver, REPLAY_EMAIL)
        stage = "first_reset_form"
        request_driver.get(reset_url)
        visible(request_driver, '#field-password[name="passwd"]')
        password = "ORDENOWA-CI-Replay-Token!2026"
        visible(request_driver, '#field-password[name="passwd"]').send_keys(password)
        visible(request_driver, '#field-confirmation-passwd[name="confirmation"]').send_keys(password)
        visible(request_driver, 'button[type="submit"][name="submit"]').click()
        assert_customer_can_login_with_password(REPLAY_EMAIL, password)
        request_driver.save_screenshot(str(DEST / "reset-token-first-use-success.png"))
        replay_driver = new_driver()
        stage = "replayed_reset_link_rejection"
        assert_reset_link_rejected(
            replay_driver,
            reset_url,
            expected_reset_path,
            "reset-token-replay-rejected.png",
        )
    except Exception as error:
        raise RuntimeError(f"replay scenario failed during {stage} ({type(error).__name__})") from None
    finally:
        for driver in (request_driver, replay_driver):
            if driver is not None:
                driver.quit()


def expiry_scenario() -> None:
    stage = "expiry_request"
    driver = None
    try:
        driver = new_driver()
        reset_url, expected_reset_path = send_reset_request(driver, EXPIRED_EMAIL)
        stage = "expire_live_test_token"
        expire_reset_token_in_isolated_container(EXPIRED_EMAIL)
        stage = "expired_reset_link_rejection"
        assert_reset_link_rejected(
            driver,
            reset_url,
            expected_reset_path,
            "reset-token-expired-rejected.png",
        )
    except Exception as error:
        raise RuntimeError(f"expiry scenario failed during {stage} ({type(error).__name__})") from None
    finally:
        if driver is not None:
            driver.quit()


def run() -> bool:
    try:
        validate_isolated_ci_compose_project()
        validate_loopback_endpoints()
        if not REPLAY_EMAIL.endswith("@example.invalid") or not EXPIRED_EMAIL.endswith("@example.invalid"):
            raise ValueError("reset-token QA requires disposable invalid-domain customer accounts")
        replay_scenario()
        expiry_scenario()
        print("PASS: native PrestaShop reset links reject replay after use and reject an expired token")
        return True
    except Exception as error:
        error_type = type(error).__name__
        if not error_type.isidentifier():
            error_type = "unexpected exception"
        message = str(error)
        safe_stage = message.replace("\n", " ")[:180]
        print(f"FAIL: reset-token browser QA ({error_type}) {safe_stage}", file=sys.stderr)
        print(f"::error title=ORDENOWA reset-token QA::{error_type}", file=sys.stderr)
        return False


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
