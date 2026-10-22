#!/usr/bin/env python3
"""Verify Korean shipping settings link to native PrestaShop admin pages."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE = os.environ["SHOP_BASE_URL"].rstrip("/")
ADMIN_LOGIN = os.environ["ADMIN_LOGIN_URL"].rstrip("/")
ADMIN_EMAIL = os.environ["ADMIN_MAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWD"]
DEST = Path(os.environ["QA_ARTIFACT_DIR"])
DEST.mkdir(parents=True, exist_ok=True)


def visible(driver: webdriver.Chrome, selector: str):
    return WebDriverWait(driver, 30).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
    )


def same_origin(candidate: str) -> bool:
    actual = urlparse(candidate)
    expected = urlparse(BASE)
    return (actual.scheme, actual.hostname, actual.port) == (
        expected.scheme,
        expected.hostname,
        expected.port,
    )


def safe_failure_detail(error: Exception) -> str:
    """Describe the failure category without exposing exception text or page data."""
    if isinstance(error, TimeoutException):
        return "timed out waiting for the expected browser state"
    if isinstance(error, AssertionError):
        safe_messages = {
            "business profile menu link leaves the isolated Back Office origin",
            "native shipping admin links are not visible on a mobile viewport",
            "the Korean shipping settings section overflows the mobile viewport",
        }
        for controller in ("AdminCarriers", "AdminShipping"):
            safe_messages.update(
                {
                    f"{controller} link leaves the isolated Back Office origin",
                    f"{controller} link leaves the isolated admin directory",
                    f"shipping link does not target the expected {controller} controller",
                    f"{controller} native admin page did not return HTTP 200 in the admin session",
                    f"{controller} native admin page redirected outside the isolated shop",
                    f"{controller} native admin page redirected to the login form",
                    f"{controller} native admin page returned an empty document",
                }
            )
        if str(error) in safe_messages:
            return str(error)
        return "browser validation failed"
    error_type = type(error).__name__
    if not error_type.isidentifier():
        error_type = "unexpected exception"
    return f"browser operation failed ({error_type})"


def resolved_admin_page(driver: webdriver.Chrome, href: str, controller: str) -> dict[str, object]:
    if not same_origin(href):
        raise AssertionError(f"{controller} link leaves the isolated Back Office origin")
    parsed = urlparse(href)
    expected_admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
    if not parsed.path.startswith(expected_admin_path + "/"):
        raise AssertionError(f"{controller} link leaves the isolated admin directory")
    if parse_qs(parsed.query).get("controller") != [controller]:
        raise AssertionError(f"shipping link does not target the expected {controller} controller")

    response = driver.execute_async_script(
        """
        const url = arguments[0];
        const done = arguments[arguments.length - 1];
        fetch(url, {credentials: 'same-origin', redirect: 'follow', cache: 'no-store'})
          .then(async response => {
            const source = await response.text();
            const page = new DOMParser().parseFromString(source, 'text/html');
            done({
              status: response.status,
              finalUrl: response.url,
              titlePresent: Boolean((page.title || '').trim()),
              bodyTextLength: (page.body?.innerText || '').trim().length,
              loginFormPresent: Boolean(page.querySelector('#login_form, input[name="passwd"]'))
            });
          })
          .catch(() => done({status: 0, finalUrl: '', titlePresent: false, bodyTextLength: 0, loginFormPresent: false}));
        """,
        href,
    )
    if not isinstance(response, dict) or response.get("status") != 200:
        raise AssertionError(f"{controller} native admin page did not return HTTP 200 in the admin session")
    final_url = response.get("finalUrl")
    if not isinstance(final_url, str) or not same_origin(final_url):
        raise AssertionError(f"{controller} native admin page redirected outside the isolated shop")
    final_path = urlparse(final_url).path.lower()
    if "/login" in final_path or response.get("loginFormPresent") is True:
        raise AssertionError(f"{controller} native admin page redirected to the login form")
    if response.get("titlePresent") is not True or not isinstance(response.get("bodyTextLength"), int) or response["bodyTextLength"] < 1:
        raise AssertionError(f"{controller} native admin page returned an empty document")

    return {"controller": controller, "status": 200, "authenticated_page": True}


def run() -> None:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1000")
    driver = webdriver.Chrome(options=options)
    stage = "admin_login"
    try:
        stage = "admin_login_page_load"
        driver.set_window_size(1440, 1000)
        driver.get(ADMIN_LOGIN + "/login")

        stage = "admin_login_email_field"
        visible(driver, '#login_form input[name="email"]').send_keys(ADMIN_EMAIL)
        stage = "admin_login_password_field"
        visible(driver, '#login_form input[name="passwd"]').send_keys(ADMIN_PASSWORD)
        stage = "admin_login_submit"
        visible(driver, "#login_form button[type='submit'], #login_form input[type='submit']").click()
        stage = "admin_login_completion"
        WebDriverWait(driver, 30).until(lambda browser: "/login" not in urlparse(browser.current_url).path)

        stage = "find_korean_business_settings_link"
        settings_links = WebDriverWait(driver, 30).until(
            lambda browser: [
                link
                for link in browser.find_elements(By.CSS_SELECTOR, 'a[href*="controller=AdminBusinessProfile"]')
                if parse_qs(urlparse(link.get_attribute("href") or "").query).get("controller")
                == ["AdminBusinessProfile"]
            ]
        )
        stage = "validate_korean_business_settings_link"
        settings_url = settings_links[0].get_attribute("href")
        if not isinstance(settings_url, str) or not same_origin(settings_url):
            raise AssertionError("business profile menu link leaves the isolated Back Office origin")
        stage = "open_korean_business_settings"
        driver.get(settings_url)
        stage = "load_korean_business_settings_form"
        visible(driver, "form.ordenowa-profile-settings")

        stage = "load_shipping_settings_section"
        shipping = visible(driver, "#ordenowa-shipping")
        stage = "verify_shipping_policy_editor"
        visible(driver, '#ordenowa-shipping textarea[name="profile[shipping][ko-KR]"]')
        stage = "find_admin_carriers_link"
        carriers_link = visible(driver, "#ordenowa-shipping a.ordenowa-shipping-admin-carriers")
        stage = "find_admin_shipping_link"
        preferences_link = visible(driver, "#ordenowa-shipping a.ordenowa-shipping-admin-preferences")
        stage = "capture_shipping_settings_desktop"
        driver.save_screenshot(str(DEST / "shipping-admin-settings-desktop.png"))

        stage = "resolve_admin_carriers"
        resolved_admin_page(driver, carriers_link.get_attribute("href") or "", "AdminCarriers")
        stage = "resolve_admin_shipping"
        resolved_admin_page(driver, preferences_link.get_attribute("href") or "", "AdminShipping")

        stage = "set_mobile_viewport"
        driver.set_window_size(390, 844)
        stage = "scroll_to_mobile_shipping_settings"
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", shipping)
        stage = "verify_mobile_shipping_settings_links"
        if not carriers_link.is_displayed() or not preferences_link.is_displayed():
            raise AssertionError("native shipping admin links are not visible on a mobile viewport")
        stage = "verify_mobile_shipping_settings_overflow"
        if driver.execute_script(
            "return document.documentElement.scrollWidth > document.documentElement.clientWidth"
        ):
            raise AssertionError("the Korean shipping settings section overflows the mobile viewport")
        stage = "capture_shipping_settings_mobile"
        driver.save_screenshot(str(DEST / "shipping-admin-settings-mobile.png"))
        print("PASS: Korean shipping policy remains editable; authenticated AdminCarriers and AdminShipping links return HTTP 200")
    except (Exception, TimeoutException) as error:
        detail = safe_failure_detail(error)
        print(f"FAIL: Korean shipping admin links at {stage} ({detail})", file=sys.stderr)
        print(f"ORDENOWA_SHIPPING_ADMIN_STAGE={stage}", file=sys.stderr)
        print(f"ORDENOWA_SHIPPING_ADMIN_DETAIL={detail}", file=sys.stderr)
        print(f"::error title=ORDENOWA shipping admin browser QA::{stage}: {detail}")
        raise SystemExit(f"isolated shipping admin browser flow failed at {stage}") from None
    finally:
        driver.quit()


if __name__ == "__main__":
    run()
