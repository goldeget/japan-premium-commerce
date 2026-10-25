#!/usr/bin/env python3
"""Round-trip the existing synthetic CI return through the native Back Office form."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    UnexpectedAlertPresentException,
    WebDriverException,
)
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
WAITING_FOR_PACKAGE_STATE_ID = "2"
RMA_STATE_TRANSITION_PATH = (
    (WAITING_FOR_CONFIRMATION_STATE_ID, WAITING_FOR_PACKAGE_STATE_ID),
    (WAITING_FOR_PACKAGE_STATE_ID, WAITING_FOR_CONFIRMATION_STATE_ID),
)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
SAFE_DIAGNOSTIC_STAGES = (
    "none",
    "target_setup",
    "admin_login",
    "return_list",
    "target_rma",
    "edit_screen",
    "transition_1_to_2_select",
    "transition_1_to_2_save",
    "transition_1_to_2_readback",
    "transition_2_to_1_select",
    "transition_2_to_1_save",
    "transition_2_to_1_readback",
    "complete",
    "browser_shutdown",
)
SAFE_SELECTED_STATE_VALUES = ("1", "2", "unknown")
SAFE_FALLBACK_EXCEPTION_CLASS_NAME = "UnexpectedError"


class TargetGuardError(Exception):
    """Raised when the browser target is not this run's disposable shop."""


EXCEPTION_CLASS_ALLOWLIST = (
    (TargetGuardError, "TargetGuardError"),
    (TimeoutException, "TimeoutException"),
    (NoSuchElementException, "NoSuchElementException"),
    (StaleElementReferenceException, "StaleElementReferenceException"),
    (ElementClickInterceptedException, "ElementClickInterceptedException"),
    (ElementNotInteractableException, "ElementNotInteractableException"),
    (UnexpectedAlertPresentException, "UnexpectedAlertPresentException"),
    (WebDriverException, "WebDriverException"),
    (AssertionError, "AssertionError"),
    (OSError, "OSError"),
)


class StageTracker:
    def __init__(self) -> None:
        self.current_stage = "target_setup"
        self.last_completed_stage = "none"
        self.target_order_matches = False
        self.order_detail_link_matches = False
        self.target_rma_matches = False
        self.selected_state = "unknown"
        self.save_success_visible = False

    def begin(self, stage_name: str) -> None:
        if stage_name not in SAFE_DIAGNOSTIC_STAGES:
            raise ValueError("unsupported diagnostic stage")
        self.current_stage = stage_name

    def complete(self, stage_name: str | None = None) -> None:
        completed = stage_name or self.current_stage
        if completed not in SAFE_DIAGNOSTIC_STAGES:
            raise ValueError("unsupported diagnostic stage")
        self.current_stage = completed
        self.last_completed_stage = completed


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


def find_existing_return(
    driver: webdriver.Chrome,
    admin_root: str,
    expected_order_id: int,
    stage: StageTracker,
):
    visit(driver, admin_root + RETURN_LIST_SUFFIX)
    table = WebDriverWait(driver, 35).until(
        EC.presence_of_element_located((By.ID, RETURN_GRID_ID))
    )
    stage.complete("return_list")
    stage.begin("target_rma")

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

    stage.target_order_matches = True
    row, raw_return_id = matching_rows[0]
    return_id = positive_int(raw_return_id)
    edit_urls = []
    for link in row.find_elements(By.CSS_SELECTOR, "td.column-actions a[href]"):
        href = link.get_attribute("href") or ""
        if return_id_from_edit_url(href, admin_root) == return_id:
            edit_urls.append(href)
    if len(edit_urls) != 1:
        raise TargetGuardError

    stage.target_rma_matches = True
    stage.complete()
    return return_id, edit_urls[0]


def same_order_detail_link_matches(admin_root: str, expected_order_id: int, form) -> bool:
    expected_suffix = ["sell", "orders", str(expected_order_id), "view"]
    matching_links = 0
    for link in form.find_elements(By.CSS_SELECTOR, "a[href]"):
        href = link.get_attribute("href") or ""
        absolute_url = urljoin(admin_root + "/", href)
        parsed = urlparse(absolute_url)
        if (
            is_admin_origin(absolute_url, admin_root)
            and [segment for segment in parsed.path.rstrip("/").split("/") if segment][-4:]
            == expected_suffix
        ):
            matching_links += 1
    return matching_links == 1


def current_return_form(
    driver: webdriver.Chrome,
    admin_root: str,
    return_id: int,
    order_id: int,
    stage: StageTracker | None = None,
):
    if return_id_from_edit_url(driver.current_url, admin_root) != return_id:
        if stage is not None:
            stage.target_rma_matches = False
            stage.order_detail_link_matches = False
        return None
    if stage is not None:
        stage.target_rma_matches = True
    status_selects = driver.find_elements(
        By.CSS_SELECTOR,
        "select" + RETURN_STATE_SELECTOR,
    )
    if len(status_selects) != 1:
        if stage is not None:
            stage.order_detail_link_matches = False
        return None
    status_select = status_selects[0]
    form = status_select.find_element(By.XPATH, "./ancestor::form[1]")
    order_link_matches = same_order_detail_link_matches(admin_root, order_id, form)
    if stage is not None:
        stage.order_detail_link_matches = order_link_matches
    if not order_link_matches:
        if stage is not None:
            stage.target_order_matches = False
        return None
    if stage is not None:
        stage.target_order_matches = True
    return form, status_select


def selected_state_token(raw_state: str | None) -> str:
    return raw_state if raw_state in SAFE_SELECTED_STATE_VALUES[:2] else "unknown"


def save_and_verify_return_state_transition(
    driver: webdriver.Chrome,
    admin_root: str,
    return_id: int,
    order_id: int,
    previous_state_id: str,
    next_state_id: str,
    stage: StageTracker,
) -> None:
    transition = f"transition_{previous_state_id}_to_{next_state_id}"
    stage.begin(f"{transition}_select")
    form_state = WebDriverWait(driver, 35).until(
        lambda browser: current_return_form(browser, admin_root, return_id, order_id, stage)
    )
    form, status_select = form_state
    selected_state_before = Select(status_select).first_selected_option.get_attribute("value")
    stage.selected_state = selected_state_token(selected_state_before)
    if selected_state_before != previous_state_id:
        raise TargetGuardError

    Select(status_select).select_by_value(next_state_id)
    stage.selected_state = selected_state_token(next_state_id)
    stage.complete()
    stage.begin(f"{transition}_save")
    form.find_element(By.NAME, SAVE_AND_STAY_NAME).click()
    stage.complete()
    stage.begin(f"{transition}_readback")

    def target_state_saved(browser: webdriver.Chrome) -> bool:
        updated = current_return_form(browser, admin_root, return_id, order_id, stage)
        if updated is None:
            stage.save_success_visible = False
            return False
        updated_form, updated_status_select = updated
        selected_state_after = Select(updated_status_select).first_selected_option.get_attribute("value")
        stage.selected_state = selected_state_token(selected_state_after)
        success_notice = browser.find_elements(By.CSS_SELECTOR, 'div.alert.alert-success[role="alert"]')
        stage.save_success_visible = bool(success_notice)
        return (
            selected_state_after == next_state_id
            and stage.save_success_visible
            and same_order_detail_link_matches(admin_root, order_id, updated_form)
        )

    WebDriverWait(driver, 35).until(target_state_saved)
    stage.complete()


def verify_existing_synthetic_return(
    driver: webdriver.Chrome,
    admin_root: str,
    return_id: int,
    order_id: int,
    stage: StageTracker,
) -> None:
    stage.begin("edit_screen")
    form_state = WebDriverWait(driver, 35).until(
        lambda browser: current_return_form(browser, admin_root, return_id, order_id, stage)
    )
    form, status_select = form_state
    initial_state = Select(status_select).first_selected_option.get_attribute("value")
    stage.selected_state = selected_state_token(initial_state)
    if initial_state != WAITING_FOR_CONFIRMATION_STATE_ID:
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
    if not same_order_detail_link_matches(admin_root, order_id, form):
        raise TargetGuardError
    stage.complete()

    # Each real transition sends one message through the run-owned Mailpit configured by CI.
    # Move to the ordinary waiting-for-package state, then restore the fixture's original state.
    for previous_state_id, next_state_id in RMA_STATE_TRANSITION_PATH:
        save_and_verify_return_state_transition(
            driver,
            admin_root,
            return_id,
            order_id,
            previous_state_id,
            next_state_id,
            stage,
        )


def safe_exception_class_name(error: Exception) -> str:
    for exception_type, safe_name in EXCEPTION_CLASS_ALLOWLIST:
        if isinstance(error, exception_type):
            return safe_name
    return SAFE_FALLBACK_EXCEPTION_CLASS_NAME


def login_form_visible(driver: webdriver.Chrome | None) -> bool:
    if driver is None:
        return False
    try:
        email_fields = driver.find_elements(
            By.CSS_SELECTOR,
            '#login_form input[name="email"], input[type="email"]',
        )
        password_fields = driver.find_elements(
            By.CSS_SELECTOR,
            '#login_form input[name="passwd"], #login_form input[name="password"], input[type="password"]',
        )
        return (
            any(field.is_displayed() for field in email_fields)
            and any(field.is_displayed() for field in password_fields)
        )
    except Exception:
        return False


def build_safe_diagnostics(
    stage: StageTracker,
    exception_class: str,
    is_login_form_visible: bool,
    screenshot_captured: bool,
) -> dict[str, str | bool]:
    return {
        "last_completed_stage": stage.last_completed_stage,
        "failure_stage": stage.current_stage,
        "exception_class": exception_class,
        "target_order_matches": stage.target_order_matches,
        "order_detail_link_matches": stage.order_detail_link_matches,
        "target_rma_matches": stage.target_rma_matches,
        "login_form_visible": is_login_form_visible,
        "selected_state": stage.selected_state,
        "save_success_visible": stage.save_success_visible,
        "status_control_screenshot_captured": screenshot_captured,
    }


def capture_safe_status_screenshot(
    driver: webdriver.Chrome | None,
    admin_root: str | None,
    return_id: int | None,
    order_id: int | None,
    stage: StageTracker,
) -> bool:
    stage.selected_state = "unknown"
    stage.save_success_visible = False
    stage.order_detail_link_matches = False
    stage.target_rma_matches = False
    if driver is None or admin_root is None or return_id is None or order_id is None:
        return False
    try:
        verified_form = current_return_form(driver, admin_root, return_id, order_id, stage)
        if verified_form is None:
            return False
        form, status_select = verified_form
        if not same_order_detail_link_matches(admin_root, order_id, form):
            return False
        selected_state = Select(status_select).first_selected_option.get_attribute("value")
        if selected_state not in SAFE_SELECTED_STATE_VALUES[:2] or not status_select.is_displayed():
            return False
        stage.selected_state = selected_state_token(selected_state)
        if stage.current_stage.endswith("_readback"):
            stage.save_success_visible = bool(
                driver.find_elements(By.CSS_SELECTOR, 'div.alert.alert-success[role="alert"]')
            )
        artifact_directory = os.environ.get("QA_ARTIFACT_DIR")
        if not artifact_directory:
            return False
        screenshot_path = Path(artifact_directory) / "admin-return-state-control.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        return status_select.screenshot(str(screenshot_path)) is True and screenshot_path.is_file()
    except Exception:
        return False


def report_failure_diagnostics(diagnostics: dict[str, str | bool]) -> None:
    safe_line = (
        "stage={failure_stage} last_completed={last_completed_stage} "
        "exception={exception_class} order_match={target_order_matches} "
        "edit_order_link_match={order_detail_link_matches} "
        "rma_match={target_rma_matches} login_form={login_form_visible} "
        "selected_state={selected_state} save_success={save_success_visible} "
        "status_control_screenshot={status_control_screenshot_captured}"
    ).format(**diagnostics)
    sys.stdout.write("FAIL: native admin return browser stage diagnostics: " + safe_line + "\n")
    sys.stdout.write("::error title=ORDENOWA admin RMA browser::" + safe_line + "\n")

    artifact_directory = os.environ.get("QA_ARTIFACT_DIR")
    if artifact_directory:
        try:
            directory = Path(artifact_directory)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "admin-return-diagnostics.json").write_text(
                json.dumps(diagnostics, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        summary = (
            "### Admin RMA browser diagnostic\n"
            f"- Failure stage: `{diagnostics['failure_stage']}`\n"
            f"- Last completed stage: `{diagnostics['last_completed_stage']}`\n"
            f"- Exception class: `{diagnostics['exception_class']}`\n"
            f"- Target order matched: `{diagnostics['target_order_matches']}`\n"
            f"- Edit form order link matched: `{diagnostics['order_detail_link_matches']}`\n"
            f"- Target RMA matched: `{diagnostics['target_rma_matches']}`\n"
            f"- Login form visible: `{diagnostics['login_form_visible']}`\n"
            f"- Selected state: `{diagnostics['selected_state']}`\n"
            f"- Save success alert visible: `{diagnostics['save_success_visible']}`\n"
            f"- Status control screenshot captured: `{diagnostics['status_control_screenshot_captured']}`\n"
        )
        try:
            with Path(summary_path).open("a", encoding="utf-8") as summary_file:
                summary_file.write(summary)
        except OSError:
            pass


def run_admin_return_browser() -> int:
    stage = StageTracker()
    driver = None
    admin_root = None
    return_id = None
    expected_order_id = None
    outcome = 0
    try:
        expected_order_id, admin_root = read_target()
        stage.complete("target_setup")
        driver = webdriver.Chrome(
            options=browser_options(),
            service=Service(log_output=os.devnull),
        )
        stage.begin("admin_login")
        admin_login(driver, admin_root)
        stage.complete()
        stage.begin("return_list")
        return_id, edit_url = find_existing_return(
            driver,
            admin_root,
            expected_order_id,
            stage,
        )
        if return_id_from_edit_url(edit_url, admin_root) != return_id:
            raise TargetGuardError
        stage.begin("edit_screen")
        visit(driver, edit_url)
        verify_existing_synthetic_return(
            driver,
            admin_root,
            return_id,
            expected_order_id,
            stage,
        )
        stage.complete("complete")
    except Exception as error:
        screenshot_captured = capture_safe_status_screenshot(
            driver,
            admin_root,
            return_id,
            expected_order_id,
            stage,
        )
        diagnostics = build_safe_diagnostics(
            stage,
            safe_exception_class_name(error),
            login_form_visible(driver),
            screenshot_captured,
        )
        report_failure_diagnostics(diagnostics)
        outcome = 77 if isinstance(error, TargetGuardError) else 1
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception as error:
                if outcome == 0:
                    stage.begin("browser_shutdown")
                    diagnostics = build_safe_diagnostics(
                        stage,
                        safe_exception_class_name(error),
                        login_form_visible(driver),
                        capture_safe_status_screenshot(
                            driver,
                            admin_root,
                            return_id,
                            expected_order_id,
                            stage,
                        ),
                    )
                    report_failure_diagnostics(diagnostics)
                    outcome = 1
    return outcome


def main() -> int:
    outcome = run_admin_return_browser()
    if outcome == 77:
        print("BLOCKED: native admin return check requires the matching isolated synthetic fixture")
        return 77
    if outcome != 0:
        return 1

    print("PASS: native admin return form moved the run-scoped RMA to waiting-for-package and restored it to pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
