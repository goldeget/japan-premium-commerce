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

from admin_return_navigation import (
    SAFE_COMPROMISED_PAGE_CLASSIFICATIONS,
    compromised_page_facts,
    return_menu_link_facts,
    return_list_path_matches,
    security_page_failure_reason,
    token_comparison_classification,
)
from safe_admin_browser_diagnostics import (
    safe_admin_pathname,
    safe_document_response_status,
)


RETURN_LIST_SUFFIX = "/sell/customer-service/merchandise-return/"
RETURN_GRID_ID = "merchandise_return_grid_table"
SECURITY_COMPROMISED_PAGE_ID = "security-compromised-page"
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
    "return_menu_link",
    "return_list_navigation",
    "return_tokenless_probe",
    "return_tokenized_restore",
    "return_grid",
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
SAFE_PAGE_CLASSES = (
    "unknown",
    "outside_admin",
    "same_origin_non_admin",
    "admin_login",
    "admin_return_list",
    "admin_return_edit",
    "prestashop_security_compromised",
    "security_path_without_marker",
    "security_marker_off_path",
    "other_admin",
)
SAFE_DOCUMENT_READY_STATES = ("unknown", "loading", "interactive", "complete", "other")
SAFE_FALLBACK_EXCEPTION_CLASS_NAME = "UnexpectedError"
SAFE_TOKEN_COMPARISONS = (
    "not_available",
    "tokenless_compromised_tokenized_clear",
    "tokenless_clear_tokenized_clear",
    "tokenless_compromised_tokenized_compromised",
    "tokenless_clear_tokenized_compromised",
    "tokenless_login_tokenized_clear",
    "tokenless_login_tokenized_compromised",
    "tokenless_other_admin_tokenized_clear",
    "tokenless_other_admin_tokenized_compromised",
    "inconclusive",
)
SAFE_RETURN_MENU_NAVIGATION_METHODS = ("not_started", "click", "generated_href")


class TargetGuardError(Exception):
    """Raised when the browser target is not this run's disposable shop."""


class PrestaShopSecurityCompromisedPageError(Exception):
    """Raised when PrestaShop shows its native CSRF-compromised page."""


class CompromisedPageSignalMismatchError(Exception):
    """Raised when the native page marker and expected static route disagree."""


class TokenRouteComparisonInconclusiveError(Exception):
    """Raised when safe route evidence cannot resolve the tokenized comparison."""


EXCEPTION_CLASS_ALLOWLIST = (
    (TargetGuardError, "TargetGuardError"),
    (PrestaShopSecurityCompromisedPageError, "PrestaShopSecurityCompromisedPageError"),
    (CompromisedPageSignalMismatchError, "CompromisedPageSignalMismatchError"),
    (TokenRouteComparisonInconclusiveError, "TokenRouteComparisonInconclusiveError"),
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
        self.same_admin_origin = False
        self.admin_path_matches = False
        self.safe_page_class = "unknown"
        self.document_ready_state = "unknown"
        self.visible_error_marker = False
        self.compromised_static_path_matches = False
        self.compromised_page_marker_present = False
        self.compromised_page_marker_visible = False
        self.compromised_page_classification = "none"
        self.compromised_page_screenshot_captured = False
        self.compromised_page_screenshot_stage = "none"
        self.requested_pathname = "unknown"
        self.observed_pathname = "unknown"
        self.document_response_status = "unknown"
        self.return_menu_link_found = False
        self.return_menu_link_same_origin = False
        self.return_menu_link_admin_path = False
        self.return_menu_link_return_path = False
        self.return_menu_link_session_token_present = False
        self.return_menu_link_visible = False
        self.return_menu_navigation_method = "not_started"
        self.tokenless_probe_pathname = "unknown"
        self.tokenless_probe_document_response_status = "unknown"
        self.tokenless_probe_same_admin_origin = False
        self.tokenless_probe_admin_path_matches = False
        self.tokenless_probe_compromised_static_path_matches = False
        self.tokenless_probe_page_marker_present = False
        self.tokenless_probe_page_marker_visible = False
        self.tokenless_probe_classification = "none"
        self.tokenless_probe_page_class = "unknown"
        self.tokenized_menu_classification = "none"
        self.tokenized_restore_classification = "none"
        self.token_comparison = "not_available"
        self.return_grid_present = False
        self.target_order_matches = False
        self.order_detail_link_matches = False
        self.target_rma_matches = False
        self.selected_state = "unknown"
        self.save_success_visible = False
        self.initial_state = "unknown"
        self.final_state = "unknown"
        self.original_state_restored = False
        self.transition_results: list[dict[str, str | bool]] = []

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


def same_admin_origin(url: str, admin_root: str) -> bool:
    candidate = urlparse(url)
    expected = urlparse(admin_root)
    candidate_hostname = (candidate.hostname or "").lower()
    expected_hostname = (expected.hostname or "").lower()
    try:
        candidate_port = candidate.port or 80
        expected_port = expected.port or 80
    except ValueError:
        return False
    return (
        candidate.scheme == expected.scheme == "http"
        and candidate_hostname in LOCAL_HOSTS
        and candidate_hostname == expected_hostname
        and candidate_port == expected_port
    )


def is_admin_path(url: str, admin_root: str) -> bool:
    candidate_path = urlparse(url).path
    expected_path = urlparse(admin_root).path.rstrip("/")
    return candidate_path == expected_path or candidate_path.startswith(expected_path + "/")


def is_admin_origin(url: str, admin_root: str) -> bool:
    return same_admin_origin(url, admin_root) and is_admin_path(url, admin_root)


def safe_page_class(
    url: str,
    admin_root: str,
    compromised_classification: str = "none",
) -> str:
    if not same_admin_origin(url, admin_root):
        return "outside_admin"
    if not is_admin_path(url, admin_root):
        return "same_origin_non_admin"
    if (
        compromised_classification in SAFE_COMPROMISED_PAGE_CLASSIFICATIONS
        and compromised_classification != "none"
    ):
        return compromised_classification

    candidate_path = urlparse(url).path
    base_path = urlparse(admin_root).path.rstrip("/")
    relative_path = candidate_path[len(base_path):]
    if relative_path in {"/login", "/login/"}:
        return "admin_login"
    if return_list_path_matches(candidate_path, admin_root):
        return "admin_return_list"
    if re.fullmatch(
        r"/sell/customer-service/merchandise-return/[1-9][0-9]{0,11}/edit/?",
        relative_path,
    ):
        return "admin_return_edit"
    return "other_admin"


def reject_security_page_signal(classification: str) -> None:
    failure_reason = security_page_failure_reason(classification)
    if failure_reason == "native_compromised_page":
        raise PrestaShopSecurityCompromisedPageError
    if failure_reason == "security_signal_mismatch":
        raise CompromisedPageSignalMismatchError


def collect_safe_page_diagnostics(
    stage: StageTracker,
    driver: webdriver.Chrome | None,
    admin_root: str | None,
) -> None:
    stage.same_admin_origin = False
    stage.admin_path_matches = False
    stage.safe_page_class = "unknown"
    stage.document_ready_state = "unknown"
    stage.visible_error_marker = False
    stage.compromised_static_path_matches = False
    stage.compromised_page_marker_present = False
    stage.compromised_page_marker_visible = False
    stage.compromised_page_classification = "none"
    stage.observed_pathname = "unknown"
    stage.document_response_status = "unknown"
    stage.return_grid_present = False
    if driver is None or admin_root is None:
        return
    try:
        current_url = driver.current_url
        stage.same_admin_origin = same_admin_origin(current_url, admin_root)
        stage.admin_path_matches = is_admin_path(current_url, admin_root)
        stage.observed_pathname = safe_admin_pathname(current_url, admin_root)
        compromised_page_elements = driver.find_elements(By.ID, SECURITY_COMPROMISED_PAGE_ID)
        stage.compromised_page_marker_present = bool(compromised_page_elements)
        stage.compromised_page_marker_visible = any(
            element.is_displayed() for element in compromised_page_elements
        )
        compromised_facts = compromised_page_facts(
            current_url,
            admin_root,
            stage.compromised_page_marker_present,
        )
        stage.compromised_static_path_matches = compromised_facts["static_path_matches"] is True
        stage.compromised_page_classification = compromised_facts["classification"]
        page_class = safe_page_class(
            current_url,
            admin_root,
            stage.compromised_page_classification,
        )
        stage.safe_page_class = page_class if page_class in SAFE_PAGE_CLASSES else "unknown"
    except Exception:
        return

    try:
        ready_state = driver.execute_script("return document.readyState")
        stage.document_ready_state = (
            ready_state if ready_state in SAFE_DOCUMENT_READY_STATES[1:-1] else "other"
        )
    except Exception:
        pass

    try:
        response_status = driver.execute_script(
            "const navigation = performance.getEntriesByType('navigation')[0]; "
            "return navigation ? navigation.responseStatus : null;"
        )
        stage.document_response_status = safe_document_response_status(response_status)
    except Exception:
        pass

    try:
        structural_error_markers = driver.find_elements(
            By.CSS_SELECTOR, ".page-not-found, [data-error-page]"
        )
        heading_or_alerts = driver.find_elements(By.CSS_SELECTOR, "h1, .alert-danger")
        error_phrases = (
            "page not found",
            "not found",
            "page unavailable",
            "access denied",
            "internal server error",
        )
        stage.visible_error_marker = any(
            element.is_displayed() for element in structural_error_markers
        ) or any(
            element.is_displayed()
            and any(phrase in (element.text or "").casefold() for phrase in error_phrases)
            for element in heading_or_alerts
        )
    except Exception:
        pass

    if stage.safe_page_class == "admin_return_list":
        try:
            stage.return_grid_present = len(
                driver.find_elements(By.ID, RETURN_GRID_ID)
            ) == 1
        except Exception:
            pass


def generated_return_menu_link(
    driver: webdriver.Chrome,
    admin_root: str,
    stage: StageTracker,
):
    route_candidates = []
    valid_candidates = {}
    for link in driver.find_elements(By.CSS_SELECTOR, "#nav-sidebar a[href]"):
        href = link.get_attribute("href") or ""
        facts = return_menu_link_facts(href, admin_root)
        if not facts["return_path"]:
            continue
        route_candidates.append((link, href, facts))
        if facts["valid"]:
            previous = valid_candidates.get(href)
            visible = link.is_displayed() and link.is_enabled()
            if previous is None or (visible and not previous[1]):
                valid_candidates[href] = (link, visible)

    stage.return_menu_link_found = bool(route_candidates)
    if route_candidates:
        _, _, diagnostic_facts = max(
            route_candidates,
            key=lambda item: sum(
                item[2][key]
                for key in ("same_origin", "admin_path", "return_path", "session_token_present")
            ),
        )
        stage.return_menu_link_same_origin = diagnostic_facts["same_origin"] is True
        stage.return_menu_link_admin_path = diagnostic_facts["admin_path"] is True
        stage.return_menu_link_return_path = diagnostic_facts["return_path"] is True
        stage.return_menu_link_session_token_present = (
            diagnostic_facts["session_token_present"] is True
        )

    if len(valid_candidates) != 1:
        raise TargetGuardError
    href, (link, visible) = next(iter(valid_candidates.items()))
    stage.return_menu_link_visible = visible
    return link, href


def copy_tokenless_probe_diagnostics(stage: StageTracker) -> None:
    stage.tokenless_probe_pathname = stage.observed_pathname
    stage.tokenless_probe_document_response_status = stage.document_response_status
    stage.tokenless_probe_same_admin_origin = stage.same_admin_origin
    stage.tokenless_probe_admin_path_matches = stage.admin_path_matches
    stage.tokenless_probe_compromised_static_path_matches = stage.compromised_static_path_matches
    stage.tokenless_probe_page_marker_present = stage.compromised_page_marker_present
    stage.tokenless_probe_page_marker_visible = stage.compromised_page_marker_visible
    stage.tokenless_probe_classification = stage.compromised_page_classification
    stage.tokenless_probe_page_class = stage.safe_page_class


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
    stage.begin("return_menu_link")
    menu_link, menu_url = generated_return_menu_link(driver, admin_root, stage)
    stage.requested_pathname = safe_admin_pathname(menu_url, admin_root)
    stage.complete()

    stage.begin("return_list_navigation")
    stage.requested_pathname = safe_admin_pathname(menu_url, admin_root)
    if menu_link.is_displayed() and menu_link.is_enabled():
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", menu_link)
        menu_link.click()
        WebDriverWait(driver, 35).until(
            lambda browser: browser.execute_script("return document.readyState") == "complete"
        )
        stage.return_menu_navigation_method = "click"
    else:
        # Match the existing Back Office route probe pattern: navigate to the
        # exact validated href emitted by the menu, keeping its session token in memory.
        visit(driver, menu_url)
        stage.return_menu_navigation_method = "generated_href"
    collect_safe_page_diagnostics(stage, driver, admin_root)
    capture_safe_compromised_page_screenshot(driver, admin_root, stage)
    stage.tokenized_menu_classification = stage.compromised_page_classification
    reject_security_page_signal(stage.compromised_page_classification)
    if (
        not stage.same_admin_origin
        or not stage.admin_path_matches
        or stage.safe_page_class != "admin_return_list"
    ):
        raise TargetGuardError
    stage.complete()

    stage.begin("return_tokenless_probe")
    tokenless_url = admin_root + RETURN_LIST_SUFFIX
    stage.requested_pathname = safe_admin_pathname(tokenless_url, admin_root)
    visit(driver, tokenless_url)
    collect_safe_page_diagnostics(stage, driver, admin_root)
    capture_safe_compromised_page_screenshot(driver, admin_root, stage)
    copy_tokenless_probe_diagnostics(stage)
    if not stage.tokenless_probe_same_admin_origin or not stage.tokenless_probe_admin_path_matches:
        raise TargetGuardError
    if security_page_failure_reason(stage.tokenless_probe_classification) == "security_signal_mismatch":
        raise CompromisedPageSignalMismatchError
    stage.complete()

    stage.begin("return_tokenized_restore")
    stage.requested_pathname = safe_admin_pathname(menu_url, admin_root)
    visit(driver, menu_url)
    collect_safe_page_diagnostics(stage, driver, admin_root)
    capture_safe_compromised_page_screenshot(driver, admin_root, stage)
    stage.tokenized_restore_classification = stage.compromised_page_classification
    stage.token_comparison = token_comparison_classification(
        stage.tokenless_probe_classification,
        stage.tokenized_restore_classification,
        stage.tokenless_probe_page_class,
        stage.safe_page_class,
    )
    reject_security_page_signal(stage.compromised_page_classification)
    if stage.token_comparison == "inconclusive":
        raise TokenRouteComparisonInconclusiveError
    if (
        not stage.same_admin_origin
        or not stage.admin_path_matches
        or stage.safe_page_class != "admin_return_list"
    ):
        raise TargetGuardError
    stage.complete()

    stage.begin("return_grid")
    table = WebDriverWait(driver, 35).until(
        EC.presence_of_element_located((By.ID, RETURN_GRID_ID))
    )
    stage.return_grid_present = True
    stage.complete()
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
    if stage is not None:
        stage.target_rma_matches = False
        stage.target_order_matches = False
        stage.order_detail_link_matches = False
    if return_id_from_edit_url(driver.current_url, admin_root) != return_id:
        return None
    if stage is not None:
        stage.target_rma_matches = True
    status_selects = driver.find_elements(
        By.CSS_SELECTOR,
        "select" + RETURN_STATE_SELECTOR,
    )
    if len(status_selects) != 1:
        return None
    status_select = status_selects[0]
    form = status_select.find_element(By.XPATH, "./ancestor::form[1]")
    order_link_matches = same_order_detail_link_matches(admin_root, order_id, form)
    if stage is not None:
        stage.order_detail_link_matches = order_link_matches
    if not order_link_matches:
        return None
    if stage is not None:
        stage.target_order_matches = True
    return form, status_select


def selected_state_token(raw_state: str | None) -> str:
    return raw_state if raw_state in SAFE_SELECTED_STATE_VALUES[:2] else "unknown"


def save_and_verify_return_state_transition(
    driver: webdriver.Chrome,
    admin_root: str,
    edit_url: str,
    return_id: int,
    order_id: int,
    previous_state_id: str,
    next_state_id: str,
    stage: StageTracker,
) -> None:
    transition = f"{previous_state_id}_to_{next_state_id}"
    evidence: dict[str, str | bool] = {
        "transition": transition,
        "native_save_submitted": False,
        "new_post_save_document_observed": False,
        "save_success_visible": False,
        "fresh_get_completed": False,
        "target_rma_matches": False,
        "target_order_matches": False,
        "order_detail_link_matches": False,
        "readback_state": "unknown",
    }
    stage.transition_results.append(evidence)
    stage_name = f"transition_{transition}"
    stage.begin(f"{stage_name}_select")
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
    stage.begin(f"{stage_name}_save")
    pre_save_document_time_origin = driver.execute_script("return performance.timeOrigin")
    save_control = form.find_element(By.NAME, SAVE_AND_STAY_NAME)
    if (form.get_attribute("method") or "").upper() != "POST":
        raise TargetGuardError
    if (save_control.get_attribute("type") or "").lower() != "submit":
        raise TargetGuardError
    action_url = save_control.get_attribute("formaction") or form.get_attribute("action") or driver.current_url
    action_url = urljoin(driver.current_url, action_url)
    if not is_admin_origin(action_url, admin_root):
        raise TargetGuardError
    stage.requested_pathname = safe_admin_pathname(action_url, admin_root)
    save_control.click()
    evidence["native_save_submitted"] = True
    WebDriverWait(driver, 35).until(
        lambda browser: browser.execute_script("return performance.timeOrigin") != pre_save_document_time_origin
    )
    WebDriverWait(driver, 35).until(EC.staleness_of(form))
    WebDriverWait(driver, 35).until(
        lambda browser: browser.execute_script("return document.readyState") == "complete"
    )
    evidence["new_post_save_document_observed"] = True

    updated_form, updated_status_select = WebDriverWait(driver, 35).until(
        lambda browser: current_return_form(browser, admin_root, return_id, order_id, stage)
    )
    updated_state = Select(updated_status_select).first_selected_option.get_attribute("value")
    stage.selected_state = selected_state_token(updated_state)
    stage.save_success_visible = bool(
        WebDriverWait(driver, 35).until(
            lambda browser: browser.find_elements(
                By.CSS_SELECTOR, 'div.alert.alert-success[role="alert"]'
            )
        )
    )
    evidence["save_success_visible"] = stage.save_success_visible
    if (
        updated_state != next_state_id
        or not stage.save_success_visible
        or not stage.target_rma_matches
        or not stage.target_order_matches
        or not same_order_detail_link_matches(admin_root, order_id, updated_form)
    ):
        raise TargetGuardError
    evidence["target_rma_matches"] = stage.target_rma_matches
    evidence["target_order_matches"] = stage.target_order_matches
    evidence["order_detail_link_matches"] = stage.order_detail_link_matches
    stage.complete()

    stage.begin(f"{stage_name}_readback")
    stage.requested_pathname = safe_admin_pathname(edit_url, admin_root)
    visit(driver, edit_url)
    evidence["fresh_get_completed"] = True
    readback_form, readback_select = WebDriverWait(driver, 35).until(
        lambda browser: current_return_form(browser, admin_root, return_id, order_id, stage)
    )
    readback_state = Select(readback_select).first_selected_option.get_attribute("value")
    stage.selected_state = selected_state_token(readback_state)
    evidence["target_rma_matches"] = stage.target_rma_matches
    evidence["target_order_matches"] = stage.target_order_matches
    evidence["order_detail_link_matches"] = stage.order_detail_link_matches
    evidence["readback_state"] = stage.selected_state
    if (
        readback_state != next_state_id
        or not stage.target_rma_matches
        or not stage.target_order_matches
        or not same_order_detail_link_matches(admin_root, order_id, readback_form)
    ):
        raise TargetGuardError
    stage.final_state = stage.selected_state
    stage.original_state_restored = stage.final_state == stage.initial_state
    stage.complete()


def verify_existing_synthetic_return(
    driver: webdriver.Chrome,
    admin_root: str,
    return_id: int,
    order_id: int,
    edit_url: str,
    stage: StageTracker,
) -> None:
    stage.begin("edit_screen")
    form_state = WebDriverWait(driver, 35).until(
        lambda browser: current_return_form(browser, admin_root, return_id, order_id, stage)
    )
    form, status_select = form_state
    initial_state = Select(status_select).first_selected_option.get_attribute("value")
    stage.selected_state = selected_state_token(initial_state)
    stage.initial_state = stage.selected_state
    stage.final_state = stage.selected_state
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
            edit_url,
            return_id,
            order_id,
            previous_state_id,
            next_state_id,
            stage,
        )
    stage.original_state_restored = (
        stage.initial_state == WAITING_FOR_CONFIRMATION_STATE_ID
        and stage.final_state == stage.initial_state
    )
    if not stage.original_state_restored:
        raise TargetGuardError


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
) -> dict[str, object]:
    return {
        "last_completed_stage": stage.last_completed_stage,
        "failure_stage": stage.current_stage,
        "exception_class": exception_class,
        "same_admin_origin": stage.same_admin_origin,
        "admin_path_matches": stage.admin_path_matches,
        "safe_page_class": stage.safe_page_class,
        "document_ready_state": stage.document_ready_state,
        "visible_error_marker": stage.visible_error_marker,
        "compromised_static_path_matches": stage.compromised_static_path_matches,
        "compromised_page_marker_present": stage.compromised_page_marker_present,
        "compromised_page_marker_visible": stage.compromised_page_marker_visible,
        "compromised_page_classification": stage.compromised_page_classification,
        "compromised_page_screenshot_captured": stage.compromised_page_screenshot_captured,
        "compromised_page_screenshot_stage": stage.compromised_page_screenshot_stage,
        "requested_pathname": stage.requested_pathname,
        "observed_pathname": stage.observed_pathname,
        "document_response_status": stage.document_response_status,
        "return_menu_link_found": stage.return_menu_link_found,
        "return_menu_link_same_origin": stage.return_menu_link_same_origin,
        "return_menu_link_admin_path": stage.return_menu_link_admin_path,
        "return_menu_link_return_path": stage.return_menu_link_return_path,
        "return_menu_link_session_token_present": stage.return_menu_link_session_token_present,
        "return_menu_link_visible": stage.return_menu_link_visible,
        "return_menu_navigation_method": stage.return_menu_navigation_method,
        "tokenless_probe_pathname": stage.tokenless_probe_pathname,
        "tokenless_probe_document_response_status": stage.tokenless_probe_document_response_status,
        "tokenless_probe_same_admin_origin": stage.tokenless_probe_same_admin_origin,
        "tokenless_probe_admin_path_matches": stage.tokenless_probe_admin_path_matches,
        "tokenless_probe_compromised_static_path_matches": stage.tokenless_probe_compromised_static_path_matches,
        "tokenless_probe_page_marker_present": stage.tokenless_probe_page_marker_present,
        "tokenless_probe_page_marker_visible": stage.tokenless_probe_page_marker_visible,
        "tokenless_probe_classification": stage.tokenless_probe_classification,
        "tokenless_probe_page_class": stage.tokenless_probe_page_class,
        "tokenized_menu_classification": stage.tokenized_menu_classification,
        "tokenized_restore_classification": stage.tokenized_restore_classification,
        "token_comparison": stage.token_comparison,
        "return_grid_present": stage.return_grid_present,
        "target_order_matches": stage.target_order_matches,
        "order_detail_link_matches": stage.order_detail_link_matches,
        "target_rma_matches": stage.target_rma_matches,
        "login_form_visible": is_login_form_visible,
        "selected_state": stage.selected_state,
        "save_success_visible": stage.save_success_visible,
        "status_control_screenshot_captured": screenshot_captured,
        "initial_state": stage.initial_state,
        "final_state": stage.final_state,
        "original_state_restored": stage.original_state_restored,
        "transition_results": stage.transition_results,
    }


def capture_safe_status_screenshot(
    driver: webdriver.Chrome | None,
    admin_root: str | None,
    return_id: int | None,
    order_id: int | None,
    stage: StageTracker,
) -> bool:
    if driver is None or admin_root is None or return_id is None or order_id is None:
        return False
    try:
        screenshot_observation = StageTracker()
        verified_form = current_return_form(
            driver,
            admin_root,
            return_id,
            order_id,
            screenshot_observation,
        )
        if verified_form is None:
            return False
        form, status_select = verified_form
        if not same_order_detail_link_matches(admin_root, order_id, form):
            return False
        selected_state = Select(status_select).first_selected_option.get_attribute("value")
        if selected_state not in SAFE_SELECTED_STATE_VALUES[:2] or not status_select.is_displayed():
            return False
        artifact_directory = os.environ.get("QA_ARTIFACT_DIR")
        if not artifact_directory:
            return False
        screenshot_path = Path(artifact_directory) / "admin-return-state-control.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        return status_select.screenshot(str(screenshot_path)) is True and screenshot_path.is_file()
    except Exception:
        return False


def capture_safe_compromised_page_screenshot(
    driver: webdriver.Chrome | None,
    admin_root: str | None,
    stage: StageTracker,
) -> bool:
    if (
        driver is None
        or admin_root is None
        or not stage.compromised_static_path_matches
        or not stage.compromised_page_marker_present
        or not stage.compromised_page_marker_visible
        or stage.compromised_page_classification != "prestashop_security_compromised"
    ):
        return False
    try:
        current_url = driver.current_url
        page_elements = driver.find_elements(By.ID, SECURITY_COMPROMISED_PAGE_ID)
        marker_present = bool(page_elements)
        visible_page_elements = [element for element in page_elements if element.is_displayed()]
        current_facts = compromised_page_facts(current_url, admin_root, marker_present)
        if current_facts["classification"] != "prestashop_security_compromised" or not visible_page_elements:
            return False
        page_element = visible_page_elements[0]
        artifact_directory = os.environ.get("QA_ARTIFACT_DIR")
        if not artifact_directory:
            return False
        screenshot_path = Path(artifact_directory) / "admin-return-security-compromised.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        captured = page_element.screenshot(str(screenshot_path)) is True and screenshot_path.is_file()
        if captured:
            stage.compromised_page_screenshot_captured = True
            stage.compromised_page_screenshot_stage = stage.current_stage
        return captured
    except Exception:
        return False


def transition_evidence_lines(diagnostics: dict[str, object]) -> list[str]:
    lines = []
    for result in diagnostics["transition_results"]:
        if not isinstance(result, dict):
            continue
        lines.append(
            "transition={transition} native_save_submitted={native_save_submitted} "
            "new_post_save_document_observed={new_post_save_document_observed} "
            "save_success_visible={save_success_visible} fresh_get_completed={fresh_get_completed} "
            "rma_match={target_rma_matches} order_match={target_order_matches} "
            "order_link_match={order_detail_link_matches} readback_state={readback_state}".format(
                **result
            )
        )
    return lines


def report_failure_diagnostics(diagnostics: dict[str, object]) -> None:
    safe_line = (
        "stage={failure_stage} last_completed={last_completed_stage} "
        "exception={exception_class} order_match={target_order_matches} "
        "edit_order_link_match={order_detail_link_matches} "
        "rma_match={target_rma_matches} login_form={login_form_visible} "
        "same_admin_origin={same_admin_origin} admin_path={admin_path_matches} "
        "page_class={safe_page_class} ready_state={document_ready_state} "
        "visible_error_marker={visible_error_marker} "
        "compromised_path_match={compromised_static_path_matches} "
        "compromised_marker={compromised_page_marker_present} "
        "compromised_marker_visible={compromised_page_marker_visible} "
        "compromised_class={compromised_page_classification} "
        "compromised_screenshot={compromised_page_screenshot_captured} "
        "compromised_screenshot_stage={compromised_page_screenshot_stage} "
        "requested_path={requested_pathname} observed_path={observed_pathname} "
        "document_status={document_response_status} "
        "return_menu_link_found={return_menu_link_found} "
        "return_menu_same_origin={return_menu_link_same_origin} "
        "return_menu_admin_path={return_menu_link_admin_path} "
        "return_menu_return_path={return_menu_link_return_path} "
        "return_menu_session_token_present={return_menu_link_session_token_present} "
        "return_menu_link_visible={return_menu_link_visible} "
        "return_menu_navigation={return_menu_navigation_method} "
        "tokenless_probe_path={tokenless_probe_pathname} "
        "tokenless_probe_status={tokenless_probe_document_response_status} "
        "tokenless_probe_admin_origin={tokenless_probe_same_admin_origin} "
        "tokenless_probe_admin_path={tokenless_probe_admin_path_matches} "
        "tokenless_compromised_path={tokenless_probe_compromised_static_path_matches} "
        "tokenless_compromised_marker={tokenless_probe_page_marker_present} "
        "tokenless_marker_visible={tokenless_probe_page_marker_visible} "
        "tokenless_class={tokenless_probe_classification} "
        "tokenless_page_class={tokenless_probe_page_class} "
        "tokenized_menu_class={tokenized_menu_classification} "
        "tokenized_restore_class={tokenized_restore_classification} "
        "token_comparison={token_comparison} "
        "return_grid_present={return_grid_present} "
        "selected_state={selected_state} save_success={save_success_visible} "
        "status_control_screenshot={status_control_screenshot_captured} "
        "initial_state={initial_state} final_state={final_state} "
        "original_state_restored={original_state_restored}"
    ).format(**diagnostics)
    sys.stdout.write("FAIL: native admin return browser stage diagnostics: " + safe_line + "\n")
    sys.stdout.write("::error title=ORDENOWA admin RMA browser::" + safe_line + "\n")
    for evidence_line in transition_evidence_lines(diagnostics):
        sys.stdout.write("RMA transition evidence: " + evidence_line + "\n")
        sys.stdout.write("::error title=ORDENOWA RMA transition evidence::" + evidence_line + "\n")

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
            f"- Same admin origin: `{diagnostics['same_admin_origin']}`\n"
            f"- Admin path matched: `{diagnostics['admin_path_matches']}`\n"
            f"- Safe page class: `{diagnostics['safe_page_class']}`\n"
            f"- Document ready state: `{diagnostics['document_ready_state']}`\n"
            f"- Visible error marker: `{diagnostics['visible_error_marker']}`\n"
            f"- Compromised static path matched: `{diagnostics['compromised_static_path_matches']}`\n"
            f"- Compromised page marker present: `{diagnostics['compromised_page_marker_present']}`\n"
            f"- Compromised page marker visible: `{diagnostics['compromised_page_marker_visible']}`\n"
            f"- Compromised page classification: `{diagnostics['compromised_page_classification']}`\n"
            f"- Compromised page screenshot: captured=`{diagnostics['compromised_page_screenshot_captured']}`, stage=`{diagnostics['compromised_page_screenshot_stage']}`\n"
            f"- Requested pathname: `{diagnostics['requested_pathname']}`\n"
            f"- Observed pathname: `{diagnostics['observed_pathname']}`\n"
            f"- Document response status: `{diagnostics['document_response_status']}`\n"
            f"- Generated return menu link found: `{diagnostics['return_menu_link_found']}`\n"
            f"- Generated return menu link checks: origin=`{diagnostics['return_menu_link_same_origin']}`, admin_path=`{diagnostics['return_menu_link_admin_path']}`, return_path=`{diagnostics['return_menu_link_return_path']}`, session_token_present=`{diagnostics['return_menu_link_session_token_present']}`, visible=`{diagnostics['return_menu_link_visible']}`\n"
            f"- Generated menu navigation method: `{diagnostics['return_menu_navigation_method']}`\n"
            f"- Tokenless probe: path=`{diagnostics['tokenless_probe_pathname']}`, status=`{diagnostics['tokenless_probe_document_response_status']}`, same_admin_origin=`{diagnostics['tokenless_probe_same_admin_origin']}`, admin_path=`{diagnostics['tokenless_probe_admin_path_matches']}`, compromised_path=`{diagnostics['tokenless_probe_compromised_static_path_matches']}`, marker=`{diagnostics['tokenless_probe_page_marker_present']}`, marker_visible=`{diagnostics['tokenless_probe_page_marker_visible']}`, class=`{diagnostics['tokenless_probe_classification']}`\n"
            f"- Tokenless final page class: `{diagnostics['tokenless_probe_page_class']}`\n"
            f"- Tokenized menu route class: `{diagnostics['tokenized_menu_classification']}`; restored class: `{diagnostics['tokenized_restore_classification']}`; comparison: `{diagnostics['token_comparison']}`\n"
            f"- Return grid present: `{diagnostics['return_grid_present']}`\n"
            f"- Target order matched: `{diagnostics['target_order_matches']}`\n"
            f"- Edit form order link matched: `{diagnostics['order_detail_link_matches']}`\n"
            f"- Target RMA matched: `{diagnostics['target_rma_matches']}`\n"
            f"- Login form visible: `{diagnostics['login_form_visible']}`\n"
            f"- Selected state: `{diagnostics['selected_state']}`\n"
            f"- Save success alert visible: `{diagnostics['save_success_visible']}`\n"
            f"- Status control screenshot captured: `{diagnostics['status_control_screenshot_captured']}`\n"
            f"- Initial state: `{diagnostics['initial_state']}`\n"
            f"- Final state: `{diagnostics['final_state']}`\n"
            f"- Original state restored: `{diagnostics['original_state_restored']}`\n"
            "\n".join(f"- `{line}`" for line in transition_evidence_lines(diagnostics))
            + "\n"
        )
        try:
            with Path(summary_path).open("a", encoding="utf-8") as summary_file:
                summary_file.write(summary)
        except OSError:
            pass


def report_success_diagnostics(stage: StageTracker) -> None:
    diagnostics = {
        "initial_state": stage.initial_state,
        "final_state": stage.final_state,
        "original_state_restored": stage.original_state_restored,
        "transition_results": stage.transition_results,
    }
    lines = transition_evidence_lines(diagnostics)
    sys.stdout.write(
        "PASS: native admin RMA state readback; "
        f"initial_state={stage.initial_state} final_state={stage.final_state} "
        f"original_state_restored={stage.original_state_restored} "
        f"return_menu_origin={stage.return_menu_link_same_origin} "
        f"return_menu_admin_path={stage.return_menu_link_admin_path} "
        f"return_menu_path={stage.return_menu_link_return_path} "
        f"return_menu_session_token_present={stage.return_menu_link_session_token_present} "
        f"tokenless_class={stage.tokenless_probe_classification} "
        f"tokenless_page_class={stage.tokenless_probe_page_class} "
        f"tokenless_marker_visible={stage.tokenless_probe_page_marker_visible} "
        f"tokenized_menu_class={stage.tokenized_menu_classification} "
        f"token_comparison={stage.token_comparison} "
        f"compromised_screenshot={stage.compromised_page_screenshot_captured} "
        f"compromised_screenshot_stage={stage.compromised_page_screenshot_stage}\n"
    )
    for evidence_line in lines:
        sys.stdout.write("RMA transition evidence: " + evidence_line + "\n")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        summary = (
            "### Admin RMA browser transition verification\n"
            f"- Initial state: `{stage.initial_state}`\n"
            f"- Final state: `{stage.final_state}`\n"
            f"- Original state restored: `{stage.original_state_restored}`\n"
            f"- Compromised page screenshot: captured=`{stage.compromised_page_screenshot_captured}`, stage=`{stage.compromised_page_screenshot_stage}`\n"
            f"- Generated return menu link checks: origin=`{stage.return_menu_link_same_origin}`, admin_path=`{stage.return_menu_link_admin_path}`, return_path=`{stage.return_menu_link_return_path}`, session_token_present=`{stage.return_menu_link_session_token_present}`\n"
            f"- Tokenless probe classification: `{stage.tokenless_probe_classification}`\n"
            f"- Tokenless marker visible: `{stage.tokenless_probe_page_marker_visible}`\n"
            f"- Tokenless final page class: `{stage.tokenless_probe_page_class}`\n"
            f"- Tokenized menu classification: `{stage.tokenized_menu_classification}`\n"
            f"- Token comparison: `{stage.token_comparison}`\n"
            + "\n".join(f"- `{line}`" for line in lines)
            + "\n"
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
        stage.requested_pathname = safe_admin_pathname(admin_root + "/login", admin_root)
        admin_login(driver, admin_root)
        stage.complete()
        stage.begin("return_list_navigation")
        return_id, edit_url = find_existing_return(
            driver,
            admin_root,
            expected_order_id,
            stage,
        )
        if return_id_from_edit_url(edit_url, admin_root) != return_id:
            raise TargetGuardError
        stage.begin("edit_screen")
        stage.requested_pathname = safe_admin_pathname(edit_url, admin_root)
        visit(driver, edit_url)
        verify_existing_synthetic_return(
            driver,
            admin_root,
            return_id,
            expected_order_id,
            edit_url,
            stage,
        )
        stage.complete("complete")
    except Exception as error:
        collect_safe_page_diagnostics(stage, driver, admin_root)
        capture_safe_compromised_page_screenshot(driver, admin_root, stage)
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
                    collect_safe_page_diagnostics(stage, driver, admin_root)
                    capture_safe_compromised_page_screenshot(driver, admin_root, stage)
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
    if outcome == 0:
        report_success_diagnostics(stage)
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
