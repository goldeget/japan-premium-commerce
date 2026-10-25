#!/usr/bin/env python3
"""Round-trip the existing synthetic CI return through the native Back Office form."""

from __future__ import annotations

import os
import re
import sys
from urllib.parse import urljoin, urlparse, urlunparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait


RETURN_LIST_SUFFIX = "/sell/customer-service/merchandise-return/"
RETURN_GRID_ID = "merchandise_return_grid_table"
RETURN_STATE_SELECTOR = "[name$='[order_return_state]']"
SAVE_AND_STAY_NAME = "submitAddorder_returnAndStay"
WAITING_FOR_CONFIRMATION_STATE_ID = "1"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class TargetGuardError(Exception):
    """Raised when the browser target is not this run's disposable shop."""


def positive_int(raw_value: str | None) -> int:
    if raw_value is None or re.fullmatch(r"[1-9][0-9]{0,11}", raw_value) is None:
        raise TargetGuardError
    return int(raw_value)


def local_http_url(raw_url: str | None):
    if not raw_url:
        raise TargetGuardError
    parsed = urlparse(raw_url)
    if (
        parsed.scheme != "http"
        or (parsed.hostname or "").lower() not in LOCAL_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise TargetGuardError
    try:
        port = parsed.port or 80
    except ValueError as error:
        raise TargetGuardError from error
    return parsed, port


def read_target():
    if (
        os.environ.get("CI") != "true"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("KURANEA_ISOLATED_CI") != "1"
    ):
        raise TargetGuardError

    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    if re.fullmatch(r"[0-9]+", run_id) is None or re.fullmatch(r"[0-9]+", run_attempt) is None:
        raise TargetGuardError
    expected_project_name = f"kuranea-ci-{run_id}-{run_attempt}"
    if os.environ.get("KURANEA_CI_PROJECT_NAME") != expected_project_name:
        raise TargetGuardError

    expected_order_id = positive_int(os.environ.get("PAID_LIKE_ORDER_ID"))
    shop, shop_port = local_http_url(os.environ.get("SHOP_BASE_URL"))
    admin, admin_port = local_http_url(os.environ.get("ADMIN_LOGIN_URL"))
    if shop_port != admin_port or (shop.path not in {"", "/"}):
        raise TargetGuardError
    admin_path = admin.path.rstrip("/")
    if admin_path != "/admin-kuranea":
        raise TargetGuardError
    if not os.environ.get("ADMIN_MAIL") or not os.environ.get("ADMIN_PASSWD"):
        raise TargetGuardError

    admin_root = urlunparse((admin.scheme, admin.netloc, admin_path, "", "", ""))
    return expected_order_id, admin_root


def browser_options() -> Options:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,960")
    options.add_argument("--lang=ko-KR")
    return options


def visit(driver: webdriver.Chrome, url: str) -> None:
    driver.get(url)
    WebDriverWait(driver, 40).until(
        lambda browser: browser.execute_script("return document.readyState") == "complete"
    )


def admin_login(driver: webdriver.Chrome, admin_root: str) -> None:
    visit(driver, admin_root + "/login")
    email = WebDriverWait(driver, 30).until(
        EC.visibility_of_element_located(
            (By.CSS_SELECTOR, '#login_form input[name="email"], input[type="email"]')
        )
    )
    password = WebDriverWait(driver, 30).until(
        EC.visibility_of_element_located(
            (
                By.CSS_SELECTOR,
                '#login_form input[name="passwd"], #login_form input[name="password"], input[type="password"]',
            )
        )
    )
    email.send_keys(os.environ["ADMIN_MAIL"])
    password.send_keys(os.environ["ADMIN_PASSWD"])
    driver.find_element(
        By.CSS_SELECTOR,
        '#login_form button[type="submit"], #login_form input[type="submit"], button[type="submit"]',
    ).click()
    WebDriverWait(driver, 35).until(
        lambda browser: "/login" not in urlparse(browser.current_url).path
    )


def is_admin_origin(url: str, admin_root: str) -> bool:
    candidate = urlparse(url)
    expected = urlparse(admin_root)
    try:
        candidate_port = candidate.port or 80
        expected_port = expected.port or 80
    except ValueError:
        return False
    return (
        candidate.scheme == expected.scheme == "http"
        and (candidate.hostname or "").lower() in LOCAL_HOSTS
        and (expected.hostname or "").lower() in LOCAL_HOSTS
        and candidate_port == expected_port
        and candidate.path.startswith(expected.path.rstrip("/") + "/")
    )


def return_id_from_edit_url(href: str, admin_root: str) -> int | None:
    absolute_url = urljoin(admin_root + "/", href)
    if not is_admin_origin(absolute_url, admin_root):
        return None
    base_path = urlparse(admin_root).path.rstrip("/")
    candidate_path = urlparse(absolute_url).path
    route = candidate_path[len(base_path):]
    match = re.fullmatch(
        r"/sell/customer-service/merchandise-return/([1-9][0-9]{0,11})/edit/?",
        route,
    )
    return int(match.group(1)) if match else None


def find_existing_return(driver: webdriver.Chrome, admin_root: str, expected_order_id: int):
    visit(driver, admin_root + RETURN_LIST_SUFFIX)
    table = WebDriverWait(driver, 35).until(
        EC.presence_of_element_located((By.ID, RETURN_GRID_ID))
    )

    matching_rows = []
    for row in table.find_elements(By.CSS_SELECTOR, "tbody tr"):
        return_cells = row.find_elements(By.CSS_SELECTOR, "td.column-id_order_return")
        order_cells = row.find_elements(By.CSS_SELECTOR, "td.column-id_order")
        if len(return_cells) != 1 or len(order_cells) != 1:
            continue
        if order_cells[0].text.strip() == str(expected_order_id):
            matching_rows.append((row, return_cells[0].text.strip()))

    if len(matching_rows) != 1:
        raise TargetGuardError

    row, raw_return_id = matching_rows[0]
    return_id = positive_int(raw_return_id)
    edit_urls = []
    for link in row.find_elements(By.CSS_SELECTOR, "td.column-actions a[href]"):
        href = link.get_attribute("href") or ""
        if return_id_from_edit_url(href, admin_root) == return_id:
            edit_urls.append(href)
    if len(edit_urls) != 1:
        raise TargetGuardError

    return return_id, edit_urls[0]


def same_order_detail_url(admin_root: str, expected_order_id: int, form):
    expected_suffix = ["sell", "orders", str(expected_order_id), "view"]
    matching_urls = []
    for link in form.find_elements(By.CSS_SELECTOR, "a[href]"):
        href = link.get_attribute("href") or ""
        absolute_url = urljoin(admin_root + "/", href)
        parsed = urlparse(absolute_url)
        if (
            is_admin_origin(absolute_url, admin_root)
            and [segment for segment in parsed.path.rstrip("/").split("/") if segment][-4:]
            == expected_suffix
        ):
            matching_urls.append(absolute_url)
    return matching_urls[0] if len(matching_urls) == 1 else None


def current_return_form(driver: webdriver.Chrome, admin_root: str, return_id: int, order_id: int):
    if return_id_from_edit_url(driver.current_url, admin_root) != return_id:
        return None
    status_selects = driver.find_elements(
        By.CSS_SELECTOR,
        "select" + RETURN_STATE_SELECTOR,
    )
    if len(status_selects) != 1:
        return None
    status_select = status_selects[0]
    form = status_select.find_element(By.XPATH, "./ancestor::form[1]")
    if same_order_detail_url(admin_root, order_id, form) is None:
        return None
    return form, status_select


def verify_existing_synthetic_return(
    driver: webdriver.Chrome,
    admin_root: str,
    return_id: int,
    order_id: int,
) -> None:
    form_state = WebDriverWait(driver, 35).until(
        lambda browser: current_return_form(browser, admin_root, return_id, order_id)
    )
    form, status_select = form_state
    if Select(status_select).first_selected_option.get_attribute("value") != WAITING_FOR_CONFIRMATION_STATE_ID:
        raise TargetGuardError

    page_text = driver.find_element(By.TAG_NAME, "body").text
    if "[CI ONLY]" not in page_text:
        raise TargetGuardError
    product_table = driver.find_elements(By.CSS_SELECTOR, 'table[data-role="order-return-products"]')
    if len(product_table) != 1:
        raise TargetGuardError
    product_rows = product_table[0].find_elements(By.CSS_SELECTOR, "tbody tr[data-role='order-return-product-row']")
    if not product_rows or not any(
        any(cell.text.strip().startswith("KURANEA-CI-") for cell in row.find_elements(By.CSS_SELECTOR, "td"))
        for row in product_rows
    ):
        raise TargetGuardError
    if same_order_detail_url(admin_root, order_id, form) is None:
        raise TargetGuardError

    selected_state_before = Select(status_select).first_selected_option.get_attribute("value")
    if selected_state_before != WAITING_FOR_CONFIRMATION_STATE_ID:
        raise TargetGuardError

    # PrestaShop 9.2 only notifies on an actual state change; retaining the current state keeps
    # this native form round-trip free of customer mail and other order side effects.
    form.find_element(By.NAME, SAVE_AND_STAY_NAME).click()

    def same_state_saved(browser: webdriver.Chrome) -> bool:
        updated = current_return_form(browser, admin_root, return_id, order_id)
        if updated is None:
            return False
        updated_form, updated_status_select = updated
        selected_state_after = Select(updated_status_select).first_selected_option.get_attribute("value")
        success_notice = browser.find_elements(By.CSS_SELECTOR, 'div.alert.alert-success[role="alert"]')
        return (
            selected_state_after == selected_state_before
            and bool(success_notice)
            and same_order_detail_url(admin_root, order_id, updated_form) is not None
        )

    WebDriverWait(driver, 35).until(same_state_saved)


def run_admin_return_browser() -> None:
    expected_order_id, admin_root = read_target()
    driver = webdriver.Chrome(
        options=browser_options(),
        service=Service(log_output=os.devnull),
    )
    try:
        admin_login(driver, admin_root)
        return_id, edit_url = find_existing_return(driver, admin_root, expected_order_id)
        if return_id_from_edit_url(edit_url, admin_root) != return_id:
            raise TargetGuardError
        visit(driver, edit_url)
        verify_existing_synthetic_return(driver, admin_root, return_id, expected_order_id)
    finally:
        driver.quit()


def main() -> int:
    try:
        run_admin_return_browser()
    except TargetGuardError:
        print("BLOCKED: native admin return check requires the matching isolated synthetic fixture")
        return 77
    except Exception:
        print("FAIL: native admin return form did not preserve the run-scoped return")
        return 1

    print("PASS: native admin return form saved the existing run-scoped RMA without changing its state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
