#!/usr/bin/env python3
"""Exercise real Back Office authorization and CSRF rejection in isolated CI."""

from __future__ import annotations

import ipaddress
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE = os.environ["SHOP_BASE_URL"].rstrip("/")
ADMIN_LOGIN = os.environ["ADMIN_LOGIN_URL"].rstrip("/")
ADMIN_EMAIL = os.environ["ADMIN_MAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWD"]
VIEW_ONLY_EMAIL = os.environ["VIEW_ONLY_EMPLOYEE_EMAIL"]
COMPOSE_PROJECT = os.environ.get("CI_COMPOSE_PROJECT_NAME", "")
DEST = Path(os.environ["QA_ARTIFACT_DIR"])
DEST.mkdir(parents=True, exist_ok=True)

EXPECTED_SHOP_PORT = 18080
SETTING_FIELD = "profile[brand][name][ko-KR]"
MUTATION_SENTINEL = "ORDENOWA CI security rejection sentinel"


def visible(driver: webdriver.Chrome, selector: str):
    return WebDriverWait(driver, 30).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
    )


def login(driver: webdriver.Chrome, email: str) -> None:
    driver.get(ADMIN_LOGIN + "/login")
    visible(driver, '#login_form input[name="email"]').send_keys(email)
    visible(driver, '#login_form input[name="passwd"]').send_keys(ADMIN_PASSWORD)
    visible(driver, "#login_form button[type='submit'], #login_form input[type='submit']").click()
    WebDriverWait(driver, 30).until(lambda browser: "/login" not in urlparse(browser.current_url).path)


def settings_url(driver: webdriver.Chrome) -> str:
    links = WebDriverWait(driver, 30).until(
        lambda browser: [
            link
            for link in browser.find_elements(By.CSS_SELECTOR, 'a[href*="controller=AdminBusinessProfile"]')
            if parse_qs(urlparse(link.get_attribute("href") or "").query).get("controller")
            == ["AdminBusinessProfile"]
        ]
    )
    href = links[0].get_attribute("href") or ""
    actual = urlparse(href)
    expected = urlparse(BASE)
    admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
    if (actual.scheme, actual.hostname, actual.port) != (
        expected.scheme,
        expected.hostname,
        expected.port,
    ):
        raise AssertionError("business profile settings left the isolated shop origin")
    if not actual.path.startswith(admin_path + "/"):
        raise AssertionError("business profile settings left the isolated Back Office directory")
    return href


def current_setting(driver: webdriver.Chrome) -> str:
    return visible(driver, f'input[name="{SETTING_FIELD}"]').get_attribute("value") or ""


def current_draft_pointer(driver: webdriver.Chrome) -> str:
    for row in driver.find_elements(By.CSS_SELECTOR, ".ordenowa-profile-history tbody tr"):
        if "현재 초안" not in row.text:
            continue
        cells = row.find_elements(By.CSS_SELECTOR, "td")
        match = re.fullmatch(r"#([1-9][0-9]*)", cells[0].text.strip()) if cells else None
        if match is None:
            raise AssertionError("the current draft version row did not contain a valid version ID")
        return match.group(1)
    raise AssertionError("the business profile history did not identify the current draft version")


def validate_isolated_ci_project() -> None:
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
        or not ADMIN_EMAIL.strip().lower().endswith("@example.invalid")
        or not VIEW_ONLY_EMAIL.strip().lower().endswith("@example.invalid")
    ):
        raise ValueError("admin security QA requires its exact isolated GitHub Actions Compose project")


def _loopback_http_origin(value: str, label: str) -> tuple[str, str, int]:
    try:
        parsed = urlparse(value)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        raise ValueError(f"{label} must be a valid isolated loopback URL") from None
    if host.lower() == "localhost":
        loopback = True
    else:
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = False
    if (
        parsed.scheme != "http"
        or not loopback
        or port != EXPECTED_SHOP_PORT
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} must use the isolated loopback shop origin on port {EXPECTED_SHOP_PORT}")
    return parsed.scheme, host.lower(), port


def validate_loopback_admin_targets() -> None:
    shop = urlparse(BASE)
    if shop.path not in ("", "/"):
        raise ValueError("SHOP_BASE_URL must be the isolated shop root")
    shop_origin = _loopback_http_origin(BASE, "SHOP_BASE_URL")
    admin_origin = _loopback_http_origin(ADMIN_LOGIN, "ADMIN_LOGIN_URL")
    admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
    if admin_origin != shop_origin or not admin_path.startswith("/") or admin_path == "":
        raise ValueError("ADMIN_LOGIN_URL must share the isolated shop origin and name its Back Office path")


def submit_settings_attempt(driver: webdriver.Chrome, mode: str) -> None:
    result = driver.execute_async_script(
        """
        const mode = arguments[0];
        const sentinel = arguments[1];
        const done = arguments[arguments.length - 1];
        const form = document.querySelector('form.ordenowa-profile-settings');
        if (!form) {
          done({formPresent: false});
          return;
        }
        const data = new FormData(form);
        data.set('profile[brand][name][ko-KR]', sentinel);
        data.set('submitOrdenowaSaveDraft', '1');
        const action = new URL(form.action || window.location.href, window.location.href);
        if (mode === 'missing') {
          action.searchParams.delete('token');
          data.delete('token');
        } else if (mode === 'invalid') {
          action.searchParams.set('token', 'invalid-ci-security-token');
          data.set('token', 'invalid-ci-security-token');
        }
        fetch(action.href, {
          method: 'POST',
          body: data,
          credentials: 'same-origin',
          redirect: 'follow',
          cache: 'no-store'
        }).then(async response => {
          const responseBody = await response.text();
          done({
            formPresent: true,
            status: response.status,
            responseUrl: response.url,
            bodyHasSettingsForm: responseBody.includes('ordenowa-profile-settings'),
            bodyHasDangerAlert: responseBody.includes('alert-danger'),
            bodyHasViewOnlyDenial: responseBody.includes('설정 초안을 수정할 권한이 없습니다.')
          });
        })
          .catch(() => done({formPresent: true, status: 0}));
        """,
        mode,
        MUTATION_SENTINEL,
    )
    if not isinstance(result, dict) or result.get("formPresent") is not True:
        raise AssertionError("the isolated settings form was not available for the security attempt")
    status = result.get("status")
    if not isinstance(status, int) or status < 200 or status >= 500:
        raise AssertionError("the isolated admin security request did not receive a usable response")
    if status == 404:
        raise AssertionError("the admin security request did not reach a registered Back Office handler")

    response_url = result.get("responseUrl")
    if not isinstance(response_url, str):
        raise AssertionError("the admin security response did not identify its final route")
    response_location = urlparse(response_url)
    base_location = urlparse(BASE)
    admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
    if (
        (response_location.scheme, response_location.hostname, response_location.port)
        != (base_location.scheme, base_location.hostname, base_location.port)
        or not response_location.path.startswith(admin_path + "/")
    ):
        raise AssertionError("the admin security response left the isolated Back Office route")

    framework_rejection = status in {400, 401, 403}
    admin_page_rejection = (
        result.get("bodyHasSettingsForm") is True
        and result.get("bodyHasDangerAlert") is True
    )
    if mode == "view_only" and not framework_rejection and result.get("bodyHasViewOnlyDenial") is not True:
        raise AssertionError("the valid-token employee request did not reach the view-only denial handler")
    if mode in {"missing", "invalid"} and not framework_rejection and not admin_page_rejection:
        raise AssertionError("the token rejection response did not show the business-profile handler error")


def assert_draft_pointer_unchanged(driver: webdriver.Chrome, expected: str, label: str) -> None:
    actual = current_draft_pointer(driver)
    if actual != expected:
        raise AssertionError(f"{label} changed the business profile draft version pointer")


def assert_setting_unchanged(
    driver: webdriver.Chrome,
    expected: str,
    expected_draft_pointer: str,
    label: str,
) -> None:
    page = settings_url(driver)
    driver.get(page)
    visible(driver, "form.ordenowa-profile-settings")
    actual = current_setting(driver)
    if actual != expected:
        raise AssertionError(f"{label} changed a saved Korean brand setting")
    assert_draft_pointer_unchanged(driver, expected_draft_pointer, label)
    driver.save_screenshot(str(DEST / f"admin-security-{label}.png"))


def new_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1000")
    return webdriver.Chrome(options=options)


def run() -> bool:
    stage = "isolated_ci_guard"
    admin_driver = None
    restricted_driver = None
    try:
        validate_isolated_ci_project()
        validate_loopback_admin_targets()
        stage = "admin_login"
        admin_driver = new_driver()
        login(admin_driver, ADMIN_EMAIL)
        stage = "admin_settings_load"
        admin_settings_url = settings_url(admin_driver)
        admin_driver.get(admin_settings_url)
        visible(admin_driver, "form.ordenowa-profile-settings")
        original_value = current_setting(admin_driver)
        original_draft_pointer = current_draft_pointer(admin_driver)

        for mode in ("missing", "invalid"):
            stage = f"admin_{mode}_token_post"
            submit_settings_attempt(admin_driver, mode)
            stage = f"admin_{mode}_token_state_recheck"
            assert_setting_unchanged(
                admin_driver,
                original_value,
                original_draft_pointer,
                f"{mode}-token",
            )

        stage = "view_only_employee_login"
        restricted_driver = new_driver()
        login(restricted_driver, VIEW_ONLY_EMAIL)
        stage = "view_only_employee_settings_load"
        restricted_settings_url = settings_url(restricted_driver)
        restricted_driver.get(restricted_settings_url)
        visible(restricted_driver, "form.ordenowa-profile-settings")
        restricted_original_value = current_setting(restricted_driver)
        restricted_draft_pointer = current_draft_pointer(restricted_driver)
        stage = "view_only_employee_valid_token_post"
        submit_settings_attempt(restricted_driver, "view_only")
        stage = "view_only_employee_state_recheck"
        assert_setting_unchanged(
            restricted_driver,
            restricted_original_value,
            restricted_draft_pointer,
            "view-only",
        )

        print(
            "PASS: Back Office rejects missing and invalid admin tokens and a view-only employee cannot save settings"
        )
        return True
    except Exception as error:
        error_type = type(error).__name__
        if not error_type.isidentifier():
            error_type = "unexpected exception"
        print(f"FAIL: isolated admin security check at {stage} ({error_type})", file=sys.stderr)
        print(f"ORDENOWA_ADMIN_SECURITY_STAGE={stage}", file=sys.stderr)
        return False
    finally:
        for driver in (admin_driver, restricted_driver):
            if driver is not None:
                driver.quit()


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
