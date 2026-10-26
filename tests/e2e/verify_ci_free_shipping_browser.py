#!/usr/bin/env python3
"""Verify the free Japan carrier policy in an isolated PrestaShop checkout."""

from __future__ import annotations

import json
import ipaddress
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

import verify_ci_checkout_admin_browser as checkout
from checkout_total_math import (
    is_tax_exclusive_total_label as _is_tax_exclusive_total_label,
    is_tax_inclusive_total_label as _is_tax_inclusive_total_label,
    labeled_tax_total_amounts,
    reconcile_cart_totals,
    reconcile_inclusive_and_exclusive_totals,
    reconcile_no_assigned_tax_rule_display,
    reconcile_order_confirmation_total_rows,
    reconcile_explicit_zero_rate_checkout,
    reconcile_tax_included_display,
)
from shipping_admin_routes import carrier_action_url, carrier_id_from_edit_url, matches_admin_controller_url


BASE = os.environ["SHOP_BASE_URL"].rstrip("/")
ADMIN_LOGIN = os.environ["ADMIN_LOGIN_URL"].rstrip("/")
QA_DIR = Path(os.environ["QA_ARTIFACT_DIR"])
QA_DIR.mkdir(parents=True, exist_ok=True)
RUN_ID = re.sub(r"[^0-9]", "", os.environ["GITHUB_RUN_ID"])
RUN_ATTEMPT = re.sub(r"[^0-9]", "", os.environ["GITHUB_RUN_ATTEMPT"])
JAPAN_ZONE_ID = int(os.environ["CI_JAPAN_ZONE_ID"])
PRODUCT_TAX_RULE_GROUP_ID = int(os.environ["CI_TEST_PRODUCT_TAX_GROUP"])
CONFIG_PATH = QA_DIR / "shipping-free-carrier.json"
ORDER_PATH = QA_DIR / "shipping-free-order.json"
EXPECTED_SHOP_PORT = 18080
CARRIER_READBACK_SUBSTAGES = {
    'native_edit_navigation', 'name_field_visible', 'shipping_tab_visible',
    'shipping_tab_active', 'free_toggle_readback', 'zone_control_readback',
}


TRACKING_BROWSER_CONTEXTS = {'admin', 'customer'}
ADMIN_ORDER_DETAIL_ROUTE_CLASSES = {'modern_order_detail', 'legacy_order_detail'}
ADMIN_DOCUMENT_WAIT_ROUTE_CLASSES = ADMIN_ORDER_DETAIL_ROUTE_CLASSES | {
    'origin_mismatch', 'admin_folder_mismatch', 'other_admin_route', 'invalid_url', 'unknown',
}
ADMIN_DOCUMENT_WAIT_BODY_STATES = {'not_read', 'read', 'stale'}
TRACKING_SUBSTAGES = {
    'not_started', 'admin_target_route', 'admin_target_document_wait',
    'admin_history_tab', 'admin_history_tab_target', 'admin_history_tab_panel',
    'admin_history_tab_click', 'admin_history_tab_wait', 'admin_history_status_readback',
    'admin_shipping_tab', 'admin_shipping_tab_target', 'admin_shipping_tab_panel',
    'admin_shipping_tab_click', 'admin_shipping_tab_wait',
    'admin_shipping_row_readback', 'admin_edit_link_readback', 'admin_modal_open',
    'admin_modal_fields_readback', 'admin_tracking_submit', 'admin_post_save_document_wait',
    'admin_post_save_shipping_tab', 'admin_post_save_row_readback', 'admin_fresh_get_setup',
    'admin_fresh_get_document_wait', 'admin_fresh_history_readback', 'admin_fresh_shipping_tab',
    'admin_tracking_fresh_readback', 'admin_tracking_capture', 'customer_login_navigation',
    'customer_login_form', 'customer_login_submit', 'customer_login_success_wait',
    'customer_password_clear', 'customer_history_navigation', 'customer_history_route',
    'customer_history_rows_readback', 'customer_order_link_readback', 'customer_order_detail_click',
    'customer_detail_document_wait', 'customer_detail_route_readback', 'customer_japanese_labels',
    'customer_tracking_cell_readback', 'customer_tracking_link_check', 'customer_summary_capture',
    'customer_tracking_scroll', 'customer_tracking_table_capture',
}


def _safe_tracking_pathname(driver) -> str:
    """Return a query-free ASCII pathname with numeric resource IDs masked."""
    try:
        page_path = urlparse(driver.current_url).path
        if not re.fullmatch(r"/[A-Za-z0-9._/-]*", page_path):
            return 'unknown'
        masked_path = re.sub(r"(?<=/)[0-9]+(?=/|$)", 'id', page_path)
        return masked_path[:240]
    except Exception:
        return 'unknown'


def _set_tracking_diagnostic(state, browser_context, substage, driver) -> None:
    """Store fixed location enums, a safe pathname, and the active WebDriver in memory."""
    if not isinstance(state, dict):
        return
    state['browser_context'] = (
        browser_context if type(browser_context) is str and browser_context in TRACKING_BROWSER_CONTEXTS else 'unknown'
    )
    state['substage'] = substage if type(substage) is str and substage in TRACKING_SUBSTAGES else 'unknown'
    state['_active_driver'] = driver
    state['safe_pathname'] = _safe_tracking_pathname(driver)


def validate_isolated_ci_compose_project() -> None:
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    expected_project = f"kuranea-ci-{run_id}-{attempt}"
    if (
        os.environ.get("CI") != "true"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("KURANEA_ISOLATED_CI") != "1"
        or re.fullmatch(r"[0-9]+", run_id) is None
        or re.fullmatch(r"[0-9]+", attempt) is None
        or os.environ.get("CI_COMPOSE_PROJECT_NAME", "") != expected_project
    ):
        raise ValueError("free-shipping QA requires its exact isolated GitHub Actions Compose project")


def _loopback_http_origin(value: str, label: str) -> tuple[str, str, int]:
    try:
        parsed = urlparse(value)
        host = (parsed.hostname or "").casefold()
        port = parsed.port
    except ValueError:
        raise ValueError(f"{label} must be a valid isolated loopback URL") from None
    try:
        is_loopback = bool(host) and ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = host == "localhost"
    if (
        parsed.scheme != "http"
        or not is_loopback
        or port != EXPECTED_SHOP_PORT
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} must use the isolated loopback shop on port {EXPECTED_SHOP_PORT}")
    return parsed.scheme, host, port


def validate_loopback_admin_targets() -> None:
    shop = urlparse(BASE)
    admin = urlparse(ADMIN_LOGIN)
    shop_origin = _loopback_http_origin(BASE, "SHOP_BASE_URL")
    admin_origin = _loopback_http_origin(ADMIN_LOGIN, "ADMIN_LOGIN_URL")
    if shop_origin != admin_origin or shop.path not in {"", "/"}:
        raise ValueError("free-shipping QA requires one loopback shop origin and no shop subpath")
    if admin.path.rstrip("/") != "/admin-kuranea":
        raise ValueError("free-shipping AdminCarriers QA must use the isolated /admin-kuranea Back Office")


def _wait_visible(driver, selector: str, timeout: int = 30):
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
    )


def _wait_present(driver, selector: str, timeout: int = 30):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
    )


def _set_text(driver, selector: str, value: str, root=None) -> None:
    scope = root or driver
    element = WebDriverWait(driver, 20).until(
        lambda _browser: next(
            (
                candidate
                for candidate in scope.find_elements(By.CSS_SELECTOR, selector)
                if candidate.is_displayed() and candidate.is_enabled()
            ),
            False,
        )
    )
    element.clear()
    element.send_keys(value)


def _switch_controls(driver, name: str) -> tuple[str, list[object]]:
    checkboxes = driver.find_elements(
        By.CSS_SELECTOR,
        f'input[type="checkbox"][name="{name}"]',
    )
    if checkboxes:
        if len(checkboxes) != 1:
            raise AssertionError(f"AdminCarriers has an ambiguous checkbox field {name}")
        return "checkbox", checkboxes

    # PrestaShop 9.2 SwitchType renders two radio choices in definition order:
    # No (false), then Yes (true). Keep actual checkboxes supported for older forms.
    radios = driver.find_elements(
        By.CSS_SELECTOR,
        f'input[type="radio"][name="{name}"]',
    )
    if len(radios) != 2:
        raise AssertionError(f"AdminCarriers is missing a boolean switch field {name}")
    return "radio", radios


def _switch_option(driver, name: str, checked: bool):
    control_type, controls = _switch_controls(driver, name)
    return controls[0] if control_type == "checkbox" else controls[1 if checked else 0]


def _switch_is_selected(driver, name: str, checked: bool) -> bool:
    control_type, controls = _switch_controls(driver, name)
    if control_type == "checkbox":
        return controls[0].is_selected() == checked
    return controls[1 if checked else 0].is_selected()


def _set_switch(driver, name: str, checked: bool) -> None:
    if _switch_is_selected(driver, name, checked):
        return
    option = _switch_option(driver, name, checked)
    option_id = option.get_attribute("id") or ""
    label = next(
        (
            candidate
            for candidate in driver.find_elements(By.CSS_SELECTOR, "label[for]")
            if option_id
            and candidate.get_attribute("for") == option_id
            and candidate.is_displayed()
        ),
        None,
    )
    checkout.click_at_center(driver, label or option)
    WebDriverWait(driver, 8).until(
        lambda _browser: _switch_is_selected(driver, name, checked)
    )


def _select_japan_zone(driver, zone_id: int) -> str:
    selector = _wait_visible(driver, "#carrier_shipping_settings_zones")
    option = next(
        (
            item
            for item in selector.find_elements(By.TAG_NAME, "option")
            if item.get_attribute("value") == str(zone_id)
        ),
        None,
    )
    if option is None:
        raise AssertionError(f"AdminCarriers has no active Japan zone option for zone {zone_id}")
    zone_name = option.text.strip()
    zone_control = Select(selector)
    if selector.get_attribute("multiple") is not None:
        zone_control.deselect_all()
    zone_control.select_by_value(str(zone_id))
    WebDriverWait(driver, 12).until(
        lambda _browser: any(
            item.get_attribute("value") == str(zone_id) and item.is_selected()
            for item in selector.find_elements(By.TAG_NAME, "option")
        )
    )
    return zone_name


def _open_shipping_settings_tab(driver, stage_callback=None) -> None:
    mark_stage = stage_callback or (lambda _stage: None)
    mark_stage("shipping_tab_visible")
    shipping_tab = _wait_visible(
        driver,
        'a[href="#carrier_shipping_settings-tab"]',
    )
    mark_stage("shipping_tab_active")
    checkout.click_at_center(driver, shipping_tab)


def _open_general_settings_tab(driver) -> None:
    general_tab = _wait_visible(
        driver,
        'a[href="#carrier_general_settings-tab"]',
    )
    checkout.click_at_center(driver, general_tab)


def _fill_free_carrier_form(
    driver,
    name: str,
    stage_callback: Callable[[str], None] | None = None,
) -> None:
    mark_stage = stage_callback or (lambda _stage: None)
    mark_stage("open_general_settings_tab")
    _open_general_settings_tab(driver)

    mark_stage("set_carrier_name")
    _set_text(driver, 'input[name="carrier[general_settings][name]"]', name)

    mark_stage("set_carrier_grade")
    grade_fields = driver.find_elements(By.CSS_SELECTOR, 'input[name="carrier[general_settings][grade]"]')
    if grade_fields and grade_fields[0].is_displayed() and grade_fields[0].is_enabled():
        grade_fields[0].clear()
        grade_fields[0].send_keys("5")

    mark_stage("set_carrier_delay")
    delay_fields = driver.find_elements(
        By.CSS_SELECTOR,
        'input[name^="carrier[general_settings][localized_delay]"]',
    )
    for delay in delay_fields:
        if delay.is_displayed() and delay.is_enabled():
            delay.clear()
            delay.send_keys("CI test only; no physical dispatch")

    mark_stage("activate_carrier")
    _set_switch(driver, "carrier[general_settings][active]", True)

    # CarrierType is rendered as a three-tab NavigationTabType form. The
    # shipping controls exist in the DOM while hidden until this tab is active.
    mark_stage("open_shipping_settings_tab")
    _open_shipping_settings_tab(driver)

    mark_stage("select_japan_zone")
    _select_japan_zone(driver, JAPAN_ZONE_ID)

    mark_stage("enable_free_shipping")
    _set_switch(driver, "carrier[shipping_settings][is_free]", True)

    mark_stage("set_carrier_limits")
    for field_name, value in (
        ("carrier[size_weight_settings][max_width]", "0"),
        ("carrier[size_weight_settings][max_height]", "0"),
        ("carrier[size_weight_settings][max_depth]", "0"),
        ("carrier[size_weight_settings][max_weight]", "1000"),
    ):
        fields = driver.find_elements(By.CSS_SELECTOR, f'input[name="{field_name}"]')
        if fields and fields[0].is_displayed() and fields[0].is_enabled():
            fields[0].clear()
            fields[0].send_keys(value)


def _assert_free_carrier_form(
    driver, carrier: dict[str, object], stage_callback=None,
) -> dict[str, object]:
    mark_stage = stage_callback or (lambda _stage: None)
    mark_stage("name_field_visible")
    name = _wait_visible(driver, 'input[name="carrier[general_settings][name]"]')
    if name.get_attribute("value") != carrier["name"]:
        raise AssertionError("the saved free carrier name did not persist")

    if not _switch_is_selected(driver, "carrier[general_settings][active]", True):
        raise AssertionError("the saved Japan free carrier is not active")

    # PrestaShop opens carrier edit pages on the general tab. Activate shipping
    # settings before waiting for its zone selector or reading the free switch.
    _open_shipping_settings_tab(driver, stage_callback)
    mark_stage("free_toggle_readback")
    if not _switch_is_selected(driver, "carrier[shipping_settings][is_free]", True):
        raise AssertionError("the saved carrier is not marked as free shipping in AdminCarriers")

    mark_stage("zone_control_readback")
    zone_select = _wait_visible(driver, "#carrier_shipping_settings_zones")
    selected_zone_ids = [
        item.get_attribute("value")
        for item in zone_select.find_elements(By.TAG_NAME, "option")
        if item.is_selected()
    ]
    if selected_zone_ids != [str(JAPAN_ZONE_ID)]:
        raise AssertionError(
            "the saved free carrier must serve only the run-scoped Japan zone; "
            f"selected zones were {selected_zone_ids}"
        )

    tax_selects = driver.find_elements(By.CSS_SELECTOR, "#carrier_shipping_settings_id_tax_rule_group")
    tax_rule_group_id = None
    if tax_selects:
        tax_rule_group_id = Select(tax_selects[0]).first_selected_option.get_attribute("value")

    return {
        "name": name.get_attribute("value"),
        "active": True,
        "is_free": True,
        "selected_zone_ids": selected_zone_ids,
        "japan_zone_id": JAPAN_ZONE_ID,
        "carrier_tax_rule_group_id": tax_rule_group_id,
    }


def _carrier_list_url(driver) -> str:
    settings_links = WebDriverWait(driver, 30).until(
        lambda browser: [
            link
            for link in browser.find_elements(By.CSS_SELECTOR, 'a[href*="controller=AdminBusinessProfile"]')
            if parse_qs(urlparse(link.get_attribute("href") or "").query).get("controller")
            == ["AdminBusinessProfile"]
        ]
    )
    settings_url = settings_links[0].get_attribute("href") or ""
    settings = urlparse(settings_url)
    base = urlparse(BASE)
    admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
    if (
        (settings.scheme, settings.hostname, settings.port) != (base.scheme, base.hostname, base.port)
        or not settings.path.startswith(admin_path + "/")
    ):
        raise AssertionError("the Korean business settings link leaves the isolated Back Office")
    checkout.visit(driver, settings_url)
    _wait_visible(driver, "form.ordenowa-profile-settings")
    carriers_link = _wait_visible(driver, "#ordenowa-shipping a.ordenowa-shipping-admin-carriers")
    carriers_url = carriers_link.get_attribute("href") or ""
    carriers = urlparse(carriers_url)
    if (
        (carriers.scheme, carriers.hostname, carriers.port) != (base.scheme, base.hostname, base.port)
        or not carriers.path.startswith(admin_path + "/")
        or not matches_admin_controller_url(carriers_url, "AdminCarriers", admin_path)
    ):
        raise AssertionError("the Korean shipping settings link is not an authenticated AdminCarriers route")
    return carriers_url


def _carrier_edit_url(carriers_list_url: str, carrier_id: int) -> str:
    return carrier_action_url(carriers_list_url, "edit", carrier_id)


def _visit_carrier_form(driver, url: str, stage_callback=None) -> None:
    """Wait for the carrier form itself instead of unrelated page-load readiness."""
    mark_stage = stage_callback or (lambda _stage: None)
    mark_stage("native_edit_navigation")
    driver.get(url)
    mark_stage("name_field_visible")
    _wait_visible(driver, 'input[name="carrier[general_settings][name]"]')


def _save_carrier_form(driver, operation: str) -> int:
    save_button = next(
        (
            button
            for button in driver.find_elements(
                By.CSS_SELECTOR,
                "form button[type='submit'], form input[type='submit']",
            )
            if button.is_displayed() and button.is_enabled()
        ),
        None,
    )
    if save_button is None:
        raise AssertionError("AdminCarriers carrier form has no visible Save button")
    try:
        checkout.click_at_center(driver, save_button)
    except StaleElementReferenceException:
        # AdminCarriers can replace the submit button while completing its POST
        # redirect. Confirm the saved edit route below instead of resubmitting.
        pass

    admin_path = urlparse(ADMIN_LOGIN).path.rstrip("/")
    WebDriverWait(driver, 35).until(
        lambda browser: carrier_id_from_edit_url(browser.current_url, admin_path) is not None
        or bool(browser.find_elements(By.CSS_SELECTOR, ".alert-danger, .alert-error"))
    )
    carrier_id = carrier_id_from_edit_url(driver.current_url, admin_path)
    if carrier_id is None:
        errors = [
            element.text.strip()[:300]
            for element in driver.find_elements(By.CSS_SELECTOR, ".alert-danger, .alert-error")
            if element.is_displayed() and element.text.strip()
        ]
        raise AssertionError(f"AdminCarriers did not save the free carrier during {operation}: {errors[:3]}")
    return carrier_id


def configure_free_carrier() -> None:
    validate_isolated_ci_compose_project()
    validate_loopback_admin_targets()
    suffix = f"{RUN_ID}-{RUN_ATTEMPT}"
    draft_name = f"ORDENOWA CI Free JP Draft {suffix}"
    final_name = f"ORDENOWA CI Free JP {suffix}"
    driver = checkout.webdriver.Chrome(options=checkout.browser_options(1440, 960))
    stage = "administrator_login"

    def stage_callback(prefix: str) -> Callable[[str], None]:
        def update_stage(detail: str) -> None:
            nonlocal stage
            stage = f"{prefix}.{detail}"

        return update_stage

    try:
        checkout.admin_login(driver)
        stage = "resolve_authenticated_admin_carriers_link"
        carriers_list_url = _carrier_list_url(driver)
        stage = "create_free_japan_carrier"
        checkout.visit(driver, carrier_action_url(carriers_list_url, "create"))
        stage = "wait_for_carrier_create_form"
        _wait_visible(driver, 'input[name="carrier[general_settings][name]"]')
        stage = "fill_draft_free_japan_carrier"
        _fill_free_carrier_form(
            driver,
            draft_name,
            stage_callback("create_free_japan_carrier"),
        )
        stage = "save_draft_free_japan_carrier"
        carrier_id = _save_carrier_form(driver, "create")

        stage = "navigate_to_saved_free_japan_carrier"
        _visit_carrier_form(driver, _carrier_edit_url(carriers_list_url, carrier_id))
        stage = "verify_draft_free_japan_carrier"
        _assert_free_carrier_form(
            driver,
            {"name": draft_name},
        )
        _fill_free_carrier_form(
            driver,
            final_name,
            stage_callback("edit_free_japan_carrier"),
        )
        stage = "save_final_free_japan_carrier"
        _save_carrier_form(driver, "edit")

        # A fresh page load verifies that the browser form rereads the saved row.
        stage = "verify_admin_saved_carrier"
        readback_stage = stage_callback("verify_admin_saved_carrier")
        _visit_carrier_form(driver, _carrier_edit_url(carriers_list_url, carrier_id), readback_stage)
        observed = _assert_free_carrier_form(driver, {"name": final_name}, readback_stage)
        observed.update({"id": carrier_id, "draft_name": draft_name})
        CONFIG_PATH.write_text(
            json.dumps(observed, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        driver.save_screenshot(str(QA_DIR / "shipping-free-carrier-admin-saved.png"))
        print(
            "PASS: Chromium AdminCarriers created, edited, saved, and reread an active free Japan carrier; "
            f"carrier_tax_rule_group_id={observed['carrier_tax_rule_group_id']!r} was preserved."
        )
    except Exception as error:
        try:
            driver.save_screenshot(str(QA_DIR / "shipping-free-carrier-configure-failure.png"))
        except Exception:
            pass
        _emit_failure(
            stage, error, driver,
            carrier_diagnostics=(
                {"expected_id": carrier_id, "expected_name": final_name}
                if stage.startswith("verify_admin_saved_carrier.") else None
            ),
        )
        raise SystemExit(f"isolated free carrier setup failed at {stage}") from None
    finally:
        driver.quit()


def _read_config() -> dict[str, object]:
    if not CONFIG_PATH.is_file():
        raise AssertionError("shipping-free-carrier.json was not produced by AdminCarriers setup")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if (
        int(config.get("japan_zone_id", 0)) != JAPAN_ZONE_ID
        or int(config.get("id", 0)) < 1
        or config.get("is_free") is not True
        or config.get("active") is not True
        or not isinstance(config.get("name"), str)
    ):
        raise AssertionError("saved CI carrier config is incomplete or violates the free Japan policy")
    return config


def readback_free_carrier() -> None:
    validate_isolated_ci_compose_project()
    validate_loopback_admin_targets()
    config = _read_config()
    driver = checkout.webdriver.Chrome(options=checkout.browser_options(1440, 960))
    stage = "fresh_administrator_login"
    try:
        checkout.admin_login(driver)
        stage = "resolve_authenticated_admin_carriers_link"
        carriers_list_url = _carrier_list_url(driver)
        stage = "readback_free_carrier_after_restart"
        _visit_carrier_form(driver, _carrier_edit_url(carriers_list_url, int(config["id"])))
        observed = _assert_free_carrier_form(driver, config)
        if observed["carrier_tax_rule_group_id"] != config["carrier_tax_rule_group_id"]:
            raise AssertionError("the carrier tax-rule selection changed after the PrestaShop restart")
        driver.save_screenshot(str(QA_DIR / "shipping-free-carrier-admin-restart-readback.png"))
        print(
            "PASS: a new admin login after the PrestaShop restart read back the saved free Japan carrier and zone."
        )
    except Exception as error:
        try:
            driver.save_screenshot(str(QA_DIR / "shipping-free-carrier-readback-failure.png"))
        except Exception:
            pass
        _emit_failure(stage, error, driver)
        raise SystemExit(f"free carrier restart readback failed at {stage}") from None
    finally:
        driver.quit()


def _parse_yen(raw_value: str) -> int:
    if re.search(r"free|無料", raw_value, re.IGNORECASE):
        return 0
    tokens = re.findall(r"\d[\d,]*(?:\.\d+)?", raw_value.replace("\u00a0", " "))
    if not tokens:
        raise AssertionError(f"could not read JPY amount from visible browser text {raw_value!r}")
    amount = float(tokens[0].replace(",", ""))
    if amount != int(amount):
        raise AssertionError(f"JPY amount unexpectedly has fractional yen: {raw_value!r}")
    return int(amount)


def _is_tax_summary_label(label: str) -> bool:
    normalized = label.casefold()
    is_total = any(marker in normalized for marker in ("total", "合計", "総計", "総額"))
    return not is_total and ("tax" in normalized or "税" in label)


def _is_total_summary_label(label: str) -> bool:
    normalized = label.casefold()
    return any(marker in normalized for marker in ("total", "合計", "総計", "総額"))


def _is_shipping_summary_label(label: str) -> bool:
    normalized = label.casefold()
    return any(
        marker in normalized
        for marker in ("shipping", "delivery", "送料", "配送", "発送", "배송")
    )


def _visible_text(driver, selector: str, timeout: int = 20) -> str:
    element = WebDriverWait(driver, timeout).until(
        lambda _browser: next(
            (item for item in driver.find_elements(By.CSS_SELECTOR, selector) if item.is_displayed()),
            False,
        )
    )
    return element.text.strip()


def _add_quantity_and_open_checkout(
    driver,
    label: str,
    quantity_requested: int,
    search_term: str,
) -> int:
    checkout.search_for_product(driver, label, search_term=search_term)
    displayed_unit_price = _parse_yen(_visible_text(driver, ".product__price"))
    quantity = _wait_visible(driver, "#quantity_wanted")
    # Keyboard input focuses this field without a pointer click. On mobile the
    # fixed navigation can overlap the input after Selenium scrolls it into view.
    quantity.send_keys(Keys.CONTROL, "a")
    quantity.send_keys(str(quantity_requested))
    WebDriverWait(driver, 5, poll_frequency=0.1).until(
        lambda browser: any(
            item.is_displayed()
            and item.get_attribute("value") == str(quantity_requested)
            for item in browser.find_elements(By.ID, "quantity_wanted")
        ),
        message="product detail did not accept the requested test quantity",
    )

    add_button = _wait_visible(driver, 'button[data-ps-ref="add-to-cart"]')
    checkout.click_at_center(driver, add_button)
    modal = WebDriverWait(
        driver,
        25,
        poll_frequency=0.2,
        ignored_exceptions=(StaleElementReferenceException,),
    ).until(
        lambda browser: next(
            (
                candidate
                for candidate in browser.find_elements(By.CSS_SELECTOR, '[data-ps-ref="blockcart-modal"]')
                if candidate.is_displayed()
                and candidate.find_elements(By.CSS_SELECTOR, ".blockcart-modal__name")
                and "[CI ONLY]" in candidate.find_element(By.CSS_SELECTOR, ".blockcart-modal__name").text
            ),
            False,
        ),
        message="the CI product quantity was not added to the cart",
    )
    proceed = next(
        (
            link
            for link in modal.find_elements(By.CSS_SELECTOR, ".modal-footer > a.btn-primary")
            if link.is_displayed() and link.is_enabled()
        ),
        None,
    )
    if proceed is None:
        raise AssertionError("the cart confirmation has no visible proceed-to-checkout link")
    proceed.click()
    WebDriverWait(driver, 30, poll_frequency=0.2).until(
        lambda browser: [
            item.get_attribute("data-id-product")
            for item in browser.find_elements(
                By.CSS_SELECTOR,
                '.cart__item [data-link-action="delete-from-cart"][data-id-product]',
            )
        ] == [str(checkout.PRODUCT_ID)]
    )
    driver.save_screenshot(str(QA_DIR / f"shipping-free-customer-cart-{label}.png"))
    checkout.clear_checkout_network_events(driver)
    checkout.visit(driver, BASE + "/index.php?controller=order")
    checkout.assert_canonical_static_route(driver, "checkout")
    WebDriverWait(driver, 30).until(
        lambda browser: any(
            section.is_displayed()
            for section in browser.find_elements(By.CSS_SELECTOR, "section.step--current")
        )
    )
    return displayed_unit_price


def _apply_coupon_if_configured(driver) -> dict[str, object]:
    code = os.environ.get("CI_COUPON_CODE", "").strip()
    if not code:
        return {
            "code": None,
            "applied": False,
            "coupon_condition": "BLOCKED: no run-scoped disposable coupon fixture was supplied",
        }

    toggle = _wait_visible(driver, 'button[data-ps-ref="voucher-accordion-button"]')
    checkout.click_at_center(driver, toggle)
    coupon_input = _wait_visible(driver, 'input[name="discount_name"]')
    coupon_input.clear()
    coupon_input.send_keys(code)
    submit = _wait_visible(driver, '[data-ps-ref="voucher-form"] button[type="submit"]')
    checkout.click_at_center(driver, submit)
    WebDriverWait(driver, 25).until(
        lambda browser: bool(browser.find_elements(By.CSS_SELECTOR, ".cart-summary__line#cart-subtotal-discount"))
        or any(
            item.is_displayed() and item.text.strip()
            for item in browser.find_elements(By.CSS_SELECTOR, '[data-ps-ref="voucher-error"]')
        )
    )
    errors = [
        item.text.strip()
        for item in driver.find_elements(By.CSS_SELECTOR, '[data-ps-ref="voucher-error"]')
        if item.is_displayed() and item.text.strip()
    ]
    if errors:
        raise AssertionError(f"the configured disposable CI coupon was rejected: {errors[:2]}")
    return {"code": code, "applied": True, "coupon_condition": "configured CI coupon applied"}


def _cart_snapshot(
    driver,
    tax_rule_group_id: int | None = None,
    pre_discount_tax_total: int | None = None,
    explicit_zero_rate_rule: bool = False,
) -> dict[str, int | None | bool | str]:
    tax_rule_group_id = PRODUCT_TAX_RULE_GROUP_ID if tax_rule_group_id is None else tax_rule_group_id
    product_text = _visible_text(driver, "#cart-subtotal-products .cart-summary__value")
    shipping_text = _visible_text(driver, "#cart-subtotal-shipping .cart-summary__value")
    product_total = _parse_yen(product_text)
    shipping_total = _parse_yen(shipping_text)

    discount_total = 0
    discounts = driver.find_elements(By.CSS_SELECTOR, "#cart-subtotal-discount .cart-summary__value")
    if discounts:
        discount_total = _parse_yen(discounts[0].text)

    lines = []
    for line in driver.find_elements(By.CSS_SELECTOR, ".js-cart-summary-totals .cart-summary__line"):
        if not line.is_displayed():
            continue
        labels = line.find_elements(By.CSS_SELECTOR, ".cart-summary__label")
        values = line.find_elements(By.CSS_SELECTOR, ".cart-summary__value")
        if labels and values:
            lines.append((labels[0].text.strip(), values[0].text.strip()))
    if not lines:
        raise AssertionError("checkout did not display the cart total")

    total_rows: list[tuple[str, int]] = []
    tax_amounts: list[int] = []
    for label, value in lines:
        amount = _parse_yen(value)
        if _is_tax_summary_label(label):
            tax_amounts.append(amount)
        if _is_total_summary_label(label):
            total_rows.append((label, amount))
    if not total_rows:
        total_rows.append((lines[-1][0], _parse_yen(lines[-1][1])))

    total_amounts = [amount for _label, amount in total_rows]
    if explicit_zero_rate_rule:
        labeled_totals = labeled_tax_total_amounts(total_rows)
        total_tax_incl = labeled_totals["total_tax_incl"]
        if total_tax_incl is None:
            total_tax_incl = total_amounts[-1]
        return reconcile_explicit_zero_rate_checkout(
            products_tax_incl=product_total,
            shipping_tax_incl=shipping_total,
            discounts_tax_incl=discount_total,
            total_tax_incl=total_tax_incl,
            total_tax_excl=labeled_totals["total_tax_excl"],
            explicit_tax_rules_group_id=tax_rule_group_id,
            resolved_tax_rate_percent=0.0,
            tax_amounts=tax_amounts,
        )
    if tax_rule_group_id == 0:
        if any(amount != 0 for amount in tax_amounts):
            raise AssertionError("the fixture with no assigned tax rule displayed a nonzero tax row")
        labeled_totals = labeled_tax_total_amounts(total_rows)
        total_tax_incl = labeled_totals["total_tax_incl"]
        return reconcile_no_assigned_tax_rule_display(
            products_tax_incl=product_total,
            shipping_tax_incl=shipping_total,
            discounts_tax_incl=discount_total,
            total_tax_incl=total_amounts[-1] if total_tax_incl is None else total_tax_incl,
            tax_breakdown_displayed=bool(tax_amounts),
        )

    if tax_rule_group_id > 0 and not tax_amounts:
        if len(total_rows) == 1:
            total_label, total_incl = total_rows[-1]
            if _is_tax_inclusive_total_label(total_label):
                return reconcile_tax_included_display(
                    products_tax_incl=product_total,
                    shipping_tax_incl=shipping_total,
                    discounts_tax_incl=discount_total,
                    total_tax_incl=total_incl,
                    total_label=total_label,
                )
        elif len(total_rows) == 2 and pre_discount_tax_total is not None:
            labeled_totals = labeled_tax_total_amounts(total_rows)
            if labeled_totals["total_tax_incl"] is not None and labeled_totals["total_tax_excl"] is not None:
                return reconcile_inclusive_and_exclusive_totals(
                    products_tax_incl=product_total,
                    shipping_tax_incl=shipping_total,
                    discounts_tax_incl=discount_total,
                    total_tax_incl=labeled_totals["total_tax_incl"],
                    total_tax_excl=labeled_totals["total_tax_excl"],
                    pre_discount_tax=pre_discount_tax_total,
                )

    total = total_amounts[-1]
    if len(total_amounts) > 1:
        total_excl, total_incl = total_amounts[-2], total_amounts[-1]
    else:
        total_incl = total
        total_excl = total - (tax_amounts[0] if tax_amounts else 0)
    tax_total = tax_amounts[0] if tax_amounts else 0
    if tax_rule_group_id == 0:
        if tax_total != 0 or total_incl != total_excl:
            raise AssertionError(
                "the CI fixture with no assigned tax rule must not create a tax line or alter totals: "
                f"{lines}"
            )
    elif tax_rule_group_id > 0:
        if tax_total <= 0 or total_incl - total_excl != tax_total:
            raise AssertionError(
                "the explicitly taxable CI product must show its configured tax inside the sale total: "
                f"{lines}"
            )
    else:
        raise AssertionError("the product tax-rule group must be read from the isolated product fixture")
    if shipping_total != 0:
        raise AssertionError(f"the free Japan carrier added {shipping_total} JPY to checkout")
    totals = reconcile_cart_totals(
        products_tax_incl=product_total,
        shipping_tax_incl=shipping_total,
        discounts_tax_incl=discount_total,
        tax=tax_total,
        total_tax_incl=total_incl,
        total_tax_excl=total_excl,
        pre_discount_tax=tax_total if pre_discount_tax_total is None else pre_discount_tax_total,
    )
    totals["tax_breakdown_displayed"] = bool(tax_amounts)
    totals["tax_display_mode"] = "detailed_breakdown" if tax_amounts else "no_assigned_tax_rule"
    return totals


def _find_free_carrier_option(driver, carrier: dict[str, object]):
    for item in driver.find_elements(By.CSS_SELECTOR, ".delivery-option__item"):
        if not item.is_displayed():
            continue
        names = item.find_elements(By.CSS_SELECTOR, ".delivery-option__carrier-name")
        if names and str(carrier["name"]) in names[0].text:
            return item
    return None


def _assert_taxable_visible_totals(
    totals: dict[str, int | None | bool | str],
    *,
    discount_tax_incl: int,
    final_tax_incl: int,
    tax: int,
    discount_tax_excl: int,
    final_tax_excl: int,
) -> None:
    expected_visible = {
        "products_tax_incl": 1100,
        "shipping_tax_incl": 0,
        "discounts_tax_incl": discount_tax_incl,
        "total_tax_incl": final_tax_incl,
    }
    observed_visible = {key: totals.get(key) for key in expected_visible}
    if observed_visible != expected_visible:
        raise AssertionError(
            "tax-inclusive customer amounts do not reconcile before saving the native order: "
            f"observed={observed_visible}, expected={expected_visible}"
        )

    if totals.get("tax") is None:
        if (
            totals.get("tax_display_mode") != "inclusive_total_only"
            or totals.get("tax_breakdown_displayed") is not False
            or any(totals.get(key) is not None for key in (
                "products_tax_excl",
                "discounts_tax_excl",
                "total_tax_excl",
            ))
        ):
            raise AssertionError(
                "an omitted tax row must stay unknown in the browser artifact; it cannot be recorded as ¥0"
            )
        return

    expected_detail = {
        "products_tax_excl": 1000,
        "discounts_tax_excl": discount_tax_excl,
        "tax": tax,
        "total_tax_excl": final_tax_excl,
    }
    observed_detail = {key: totals.get(key) for key in expected_detail}
    if observed_detail != expected_detail:
        raise AssertionError(
            "the displayed synthetic tax breakdown differs from the isolated fixture: "
            f"observed={observed_detail}, expected={expected_detail}"
        )
    expected_display_modes = {
        "detailed_breakdown": True,
        "tax_inclusive_and_exclusive_totals": False,
    }
    display_mode = str(totals.get("tax_display_mode"))
    if (
        display_mode not in expected_display_modes
        or totals.get("tax_breakdown_displayed") is not expected_display_modes[display_mode]
    ):
        raise AssertionError(
            "a known tax amount must identify whether a tax row or labeled net/gross totals were displayed"
        )


def _assert_synthetic_taxable_totals(
    totals: dict[str, int | None | bool | str],
    *,
    quantity: int,
    coupon_applied: bool,
) -> None:
    """Reconcile the CI-only gross/net test price through cart and coupon arithmetic.

    A storefront that shows only an explicitly inclusive final price must keep
    tax decomposition unknown here. The native order verifier then checks the
    positive saved tax row and exact net/gross values.
    """
    if quantity < 1:
        raise AssertionError("synthetic taxable order quantity must be positive")
    discount_gross = quantity * 550 if coupon_applied else 0
    discount_net = quantity * 500 if coupon_applied else 0
    final_gross = quantity * 1100 - discount_gross
    final_net = quantity * 1000 - discount_net
    expected_visible = {
        "products_tax_incl": quantity * 1100,
        "shipping_tax_incl": 0,
        "discounts_tax_incl": discount_gross,
        "total_tax_incl": final_gross,
    }
    observed_visible = {key: totals.get(key) for key in expected_visible}
    if observed_visible != expected_visible:
        raise AssertionError(
            "synthetic taxable order gross totals do not match quantity, coupon, and free shipping: "
            f"observed={observed_visible}, expected={expected_visible}"
        )

    if totals.get("tax") is None:
        expected_unknown = {
            "tax_display_mode": "inclusive_total_only",
            "tax_breakdown_displayed": False,
            "products_tax_excl": None,
            "discounts_tax_excl": None,
            "total_tax_excl": None,
        }
        observed_unknown = {key: totals.get(key) for key in expected_unknown}
        if observed_unknown != expected_unknown:
            raise AssertionError(
                "synthetic taxable order must preserve hidden tax as unknown, never as zero: "
                f"observed={observed_unknown}"
            )
        return

    expected_tax = final_gross - final_net
    expected_detail = {
        "products_tax_excl": quantity * 1000,
        "shipping_tax_excl": 0,
        "discounts_tax_excl": discount_net,
        "tax": expected_tax,
        "total_tax_excl": final_net,
    }
    observed_detail = {key: totals.get(key) for key in expected_detail}
    if observed_detail != expected_detail or expected_tax <= 0:
        raise AssertionError(
            "synthetic taxable order net totals and positive tax do not reconcile: "
            f"observed={observed_detail}, expected={expected_detail}"
        )
    expected_display_modes = {
        "detailed_breakdown": True,
        "tax_inclusive_and_exclusive_totals": False,
    }
    display_mode = str(totals.get("tax_display_mode"))
    if (
        display_mode not in expected_display_modes
        or totals.get("tax_breakdown_displayed") is not expected_display_modes[display_mode]
    ):
        raise AssertionError(
            "synthetic taxable order must identify whether tax came from a row or labeled gross/net totals"
        )


def _select_free_carrier_and_assert_zero(
    driver,
    carrier: dict[str, object],
    tax_rule_group_id: int | None = None,
    pre_discount_tax_total: int | None = None,
    explicit_zero_rate_rule: bool = False,
) -> dict[str, int | None | bool | str]:
    available_options = [
        item for item in driver.find_elements(By.CSS_SELECTOR, ".delivery-option__item")
        if item.is_displayed()
    ]
    if not available_options:
        raise AssertionError("Japanese checkout did not display an available carrier")
    option_prices = [
        _parse_yen(item.find_element(By.CSS_SELECTOR, ".delivery-option__price").text)
        for item in available_options
    ]
    if any(price != 0 for price in option_prices):
        raise AssertionError(f"Japanese checkout exposed a nonzero delivery price: {option_prices}")

    item = WebDriverWait(driver, 20).until(
        lambda _browser: _find_free_carrier_option(driver, carrier) or False,
        message="Japan checkout did not offer the free carrier saved through AdminCarriers",
    )
    shown_shipping = _parse_yen(item.find_element(By.CSS_SELECTOR, ".delivery-option__price").text)
    if shown_shipping != 0:
        raise AssertionError(f"customer checkout displayed ¥{shown_shipping} for the free Japan carrier")
    radio = item.find_element(By.CSS_SELECTOR, 'input[type="radio"][name^="delivery_option"]')
    if not radio.is_selected():
        checkout.click_at_center(driver, radio)
    WebDriverWait(driver, 20, poll_frequency=0.2).until(lambda _browser: radio.is_selected())
    totals = WebDriverWait(driver, 20, poll_frequency=0.2).until(
        lambda _browser: (
            snapshot
            if (snapshot := _cart_snapshot(
                driver,
                tax_rule_group_id,
                pre_discount_tax_total,
                explicit_zero_rate_rule,
            ))["shipping_tax_incl"] == 0
            else False
        ),
        message="checkout did not keep shipping at ¥0 after selecting the free Japan carrier",
    )
    return totals


def _order_history_total(driver, reference: str) -> int:
    rows = WebDriverWait(driver, 20).until(
        lambda browser: browser.find_elements(By.CSS_SELECTOR, ".order-history__row")
    )
    row = next(
        (
            item
            for item in rows
            if item.is_displayed()
            and reference in item.find_element(By.CSS_SELECTOR, ".order-history__cell--reference").text
        ),
        None,
    )
    if row is None:
        raise AssertionError("customer order history did not contain the new free-shipping order")
    return _parse_yen(row.find_element(By.CSS_SELECTOR, ".order-history__cell--total").text)


def _order_confirmation_totals(
    driver,
    *,
    allow_unassigned_tax_rule: bool = False,
    explicit_zero_rate_tax_rules_group_id: int | None = None,
) -> dict[str, int | None | bool | str]:
    """Read the rendered Hummingbird confirmation amounts without leaving the page."""
    _wait_present(driver, ".order-confirmation__table")
    product_totals = [
        _parse_yen(item.text)
        for item in driver.find_elements(By.CSS_SELECTOR, ".order-confirmation__product-total")
        if item.is_displayed()
    ]
    if not product_totals:
        raise AssertionError("order confirmation did not display a product total")

    def read_lines(selector: str) -> list[tuple[str, str]]:
        lines: list[tuple[str, str]] = []
        for line in driver.find_elements(By.CSS_SELECTOR, selector):
            if not line.is_displayed():
                continue
            labels = line.find_elements(By.CSS_SELECTOR, ".order-confirmation__line-label")
            values = line.find_elements(By.CSS_SELECTOR, ".order-confirmation__line-value")
            if labels and values:
                lines.append((labels[0].text.strip(), values[0].text.strip()))
        return lines

    subtotal_lines = read_lines(".order-confirmation__subtotals .order-confirmation__line")
    shipping_lines = [
        value
        for label, value in subtotal_lines
        if _is_shipping_summary_label(label)
    ]
    if len(shipping_lines) != 1:
        raise AssertionError(
            "order confirmation must show exactly one localized shipping subtotal; "
            f"visible labels were {[label for label, _value in subtotal_lines]}"
        )

    total_lines = read_lines(".order-confirmation__totals .order-confirmation__line")
    tax_amounts = [
        _parse_yen(value)
        for label, value in total_lines
        if _is_tax_summary_label(label)
    ]
    total_rows = [
        (label, _parse_yen(value))
        for label, value in total_lines
        if _is_total_summary_label(label)
    ]
    if not total_rows:
        raise AssertionError(
            "order confirmation did not display a recognizable final total; "
            f"visible labels were {[label for label, _value in total_lines]}"
        )
    displayed_totals = reconcile_order_confirmation_total_rows(
        total_rows=total_rows,
        tax_amounts=tax_amounts,
        allow_unassigned_tax_rule=allow_unassigned_tax_rule,
        explicit_zero_rate_tax_rules_group_id=explicit_zero_rate_tax_rules_group_id,
    )

    return {
        "products_tax_incl": sum(product_totals),
        "shipping_tax_incl": _parse_yen(shipping_lines[0]),
        **displayed_totals,
    }


def _place_unpaid_order_and_verify_confirmation(
    driver,
    label: str,
    email: str,
    expected_totals: dict[str, int | None | bool | str],
    screenshot_name: str,
) -> tuple[dict[str, object], dict[str, int | None | bool | str]]:
    """Verify the customer-facing confirmation before navigating to order history."""
    place_order = checkout.visible(driver, "#payment-confirmation button", timeout=35)
    checkout.click_at_center(driver, place_order)
    WebDriverWait(driver, 60).until(
        lambda browser: (
            "order-confirmation" in browser.current_url.lower()
            or bool(browser.find_elements(By.CSS_SELECTOR, ".order-confirmation__details-list"))
        )
    )
    confirmation = driver.find_element(By.TAG_NAME, "body").text
    if "[CI ONLY]" not in confirmation:
        raise AssertionError("order confirmation does not contain the clearly marked CI-only product")
    _assert_japanese_checkpayment_confirmation(driver)

    explicit_zero_rate_group_id = (
        int(expected_totals["tax_rules_group_id"])
        if expected_totals.get("tax_display_mode") == "explicit_zero_rate_rule"
        else None
    )
    observed = _order_confirmation_totals(
        driver,
        allow_unassigned_tax_rule=expected_totals.get("tax_display_mode") == "no_assigned_tax_rule",
        explicit_zero_rate_tax_rules_group_id=explicit_zero_rate_group_id,
    )
    expected = {
        "products_tax_incl": int(expected_totals["products_tax_incl"]),
        "shipping_tax_incl": 0,
        "total_tax_incl": int(expected_totals["total_tax_incl"]),
    }
    comparable = {
        key: observed[key]
        for key in ("products_tax_incl", "shipping_tax_incl", "total_tax_incl")
    }
    expected_tax_excl = expected_totals.get("total_tax_excl")
    if expected_tax_excl is not None and observed.get("total_tax_excl") is not None:
        expected["total_tax_excl"] = int(expected_tax_excl)
        comparable["total_tax_excl"] = int(observed["total_tax_excl"])
    expected_tax = expected_totals.get("tax")
    if expected_tax is not None and observed["tax"] is not None:
        expected["tax"] = int(expected_tax)
        comparable["tax"] = observed["tax"]
    if observed["tax"] is not None and int(observed["tax"]) < 0:
        raise AssertionError("order confirmation displayed a negative tax amount")
    if (
        expected_totals.get("tax_display_mode") == "inclusive_total_only"
        and observed["tax"] is None
        and observed["tax_display_mode"] != "inclusive_total_only"
    ):
        raise AssertionError("taxable order confirmation did not label its final amount as tax-inclusive")
    if comparable != expected:
        raise AssertionError(
            f"{label} order confirmation visible totals {comparable} differ from verified checkout {expected}"
        )
    driver.save_screenshot(str(QA_DIR / screenshot_name))

    checkout.visit(driver, BASE + "/index.php?controller=history")
    checkout.assert_canonical_ascii_friendly_route(driver, "history")
    rows = WebDriverWait(driver, 35).until(
        lambda browser: browser.find_elements(By.CSS_SELECTOR, ".order-history__row")
    )
    row = next((item for item in rows if item.is_displayed()), None)
    if row is None:
        raise AssertionError("the test customer's my page has no saved browser order")
    reference = row.find_element(By.CSS_SELECTOR, ".order-history__cell--reference").text.strip()
    detail_link = row.find_element(By.CSS_SELECTOR, 'a[data-link-action="view-order-details"]')
    detail_url = detail_link.get_attribute("href") or ""
    query = parse_qs(urlparse(detail_url).query)
    order_ids = query.get("id_order", [])
    if not order_ids:
        match = re.search(r"/([0-9]+)(?:/|$)", urlparse(detail_url).path)
        order_ids = [match.group(1)] if match else []
    if not reference or not order_ids or int(order_ids[0]) < 1:
        raise AssertionError("the saved order-history row did not expose its reference and native order ID")

    order = {
        "viewport": label,
        "order_id": int(order_ids[0]),
        "reference": reference,
        "email": email,
        "product_id": checkout.PRODUCT_ID,
        "payment_module": "ps_checkpayment",
        "order_confirmation_totals": observed,
    }
    return order, observed


def _assert_japanese_checkpayment_confirmation(driver) -> None:
    confirmation = driver.find_element(By.TAG_NAME, "body").text
    required_copy = (
        "お支払い情報",
        "小切手でのお支払い",
        "お支払い金額",
        "送付先",
        "注文番号",
        "商品を発送します。",
    )
    missing = [copy for copy in required_copy if copy not in confirmation]
    if missing:
        raise AssertionError(
            "Japanese CI payment confirmation is missing localized copy: " + ", ".join(missing)
        )


def _select_osaka_address(driver) -> None:
    form = _wait_visible(driver, "#delivery-address form")
    country_fields = form.find_elements(By.CSS_SELECTOR, 'select[name="id_country"]')
    if not country_fields:
        raise AssertionError("the Osaka fixture checkout has no Japan country field")
    japan_option = next(
        (
            option
            for option in Select(country_fields[0]).options
            if option.get_attribute("value")
            and ("japan" in option.text.casefold() or "日本" in option.text)
        ),
        None,
    )
    if japan_option is None:
        raise AssertionError("the checkout address form has no Japan option for the Osaka fixture")
    Select(country_fields[0]).select_by_value(japan_option.get_attribute("value"))

    search = _wait_visible(driver, '#delivery-address input[name="kuraneapostcode_search"]')
    search.clear()
    search.send_keys("5300001")
    candidate = WebDriverWait(driver, 30).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, '#delivery-address button[role="option"]'))
    )
    if not all(part in candidate.text for part in ("大阪府", "大阪市北区", "梅田")):
        raise AssertionError("the isolated 5300001 fixture did not resolve to Osaka / Kita / Umeda")
    checkout.click_at_center(driver, candidate)
    checkout.wait_for_autocomplete_fields(
        driver,
        form,
        {
            "postcode": "530-0001",
            "city": "大阪市北区",
            "address1": "梅田",
        },
    )

    for name, value in (
        ("alias", "ORDENOWA CI shipping free Osaka"),
        ("firstname", "ORDENOWA"),
        ("lastname", "CI Shipping Osaka"),
        ("postcode", "530-0001"),
        ("city", "大阪市北区"),
        ("address1", "梅田1-2-3"),
        ("address2", "ORDENOWA CI SHIPPING-FREE MOBILE TEST BUILDING 101"),
        ("phone", "0661234567"),
        ("phone_mobile", "0661234567"),
    ):
        fields = form.find_elements(By.CSS_SELECTOR, f'input[name="{name}"]')
        if fields and fields[0].is_displayed() and fields[0].is_enabled():
            fields[0].clear()
            fields[0].send_keys(value)

    driver.save_screenshot(str(QA_DIR / "shipping-free-mobile-osaka-address.png"))
    confirm = _wait_visible(driver, '#delivery-address button[name="confirm-addresses"]')
    checkout.click_at_center(driver, confirm)
    WebDriverWait(driver, 40).until(
        lambda browser: bool(browser.find_elements(By.CSS_SELECTOR, "#js-delivery input[name^='delivery_option']"))
        or bool(browser.find_elements(By.CSS_SELECTOR, "#checkout-delivery-step.step--current"))
    )


def _click_offline_payment(driver) -> None:
    confirm = _wait_visible(driver, '#js-delivery button[name="confirmDeliveryOption"]')
    checkout.click_at_center(driver, confirm)
    WebDriverWait(driver, 30).until(
        lambda browser: browser.find_elements(
            By.CSS_SELECTOR,
            'input[name="payment-option"][data-module-name="ps_checkpayment"]',
        )
    )
    offline = driver.find_element(
        By.CSS_SELECTOR,
        'input[name="payment-option"][data-module-name="ps_checkpayment"]',
    )
    payment_label = offline.find_element(By.XPATH, "following-sibling::label")
    if "小切手でのお支払い" not in (payment_label.text or ""):
        raise AssertionError("Japanese checkout did not translate the synthetic check-payment option")
    if not offline.is_selected():
        checkout.click_at_center(driver, offline)
    checkout.wait_for_offline_payment_selection(driver)
    for checkbox in driver.find_elements(By.CSS_SELECTOR, '#conditions-to-approve input[type="checkbox"]'):
        if checkbox.is_displayed() and checkbox.is_enabled() and not checkbox.is_selected():
            checkout.click_required_checkbox_label(
                driver,
                checkbox.find_element(By.XPATH, "ancestor::form[1]"),
                checkbox,
            )
    place_order = _wait_visible(driver, "#payment-confirmation button")
    if "注文を確定する" not in (place_order.text or ""):
        raise AssertionError("Japanese checkout did not translate the place-order action")


def _assert_mobile_checkout_controls_visible(driver) -> None:
    state = driver.execute_script(
        """
        const button = document.querySelector('#checkout-delivery-step.step--current .js-back');
        const nav = document.querySelector('.kuranea-mobile-nav');
        const navStyle = nav ? window.getComputedStyle(nav) : null;
        const navRect = nav ? nav.getBoundingClientRect() : null;
        const navVisible = Boolean(nav && navStyle && navStyle.display !== 'none'
          && navStyle.visibility !== 'hidden' && navRect.width > 0 && navRect.height > 0);
        if (button) button.scrollIntoView({block: 'nearest', inline: 'nearest'});
        const buttonRect = button ? button.getBoundingClientRect() : null;
        const overlaps = Boolean(navVisible && buttonRect && navRect
          && buttonRect.bottom > navRect.top && buttonRect.top < navRect.bottom
          && buttonRect.right > navRect.left && buttonRect.left < navRect.right);
        return {
          checkoutPage: document.body.id === 'checkout',
          buttonVisible: Boolean(button && buttonRect && buttonRect.width > 0 && buttonRect.height > 0),
          buttonWithinViewport: Boolean(buttonRect && buttonRect.top >= 0
            && buttonRect.bottom <= window.innerHeight),
          navVisible,
          overlapsMobileNavigation: overlaps,
        };
        """
    )
    if (
        not isinstance(state, dict)
        or state.get("checkoutPage") is not True
        or state.get("buttonVisible") is not True
        or state.get("buttonWithinViewport") is not True
        or state.get("navVisible") is not False
        or state.get("overlapsMobileNavigation") is not False
    ):
        summary = ", ".join(
            f"{key}={state.get(key)!r}" for key in (
                "checkoutPage",
                "buttonVisible",
                "buttonWithinViewport",
                "navVisible",
                "overlapsMobileNavigation",
            )
        ) if isinstance(state, dict) else "diagnostic_unavailable=true"
        raise AssertionError(f"mobile checkout back control is covered by navigation or outside view: {summary}")


def _assert_japanese_checkout_copy(driver) -> None:
    body_copy = driver.find_element(By.TAG_NAME, "body").text
    required_copy = ("住所に戻る", "お支払いへ進む", "注文に関するコメント")
    missing = [copy for copy in required_copy if copy not in body_copy]
    if missing:
        raise AssertionError("Japanese checkout is missing localized copy: " + ", ".join(missing))


def _assert_japanese_cart_details_copy(driver) -> None:
    button = _wait_visible(
        driver,
        ".cart-summary__products-accordion .accordion-header button",
    )
    if " ".join((button.text or "").split()) != "詳細を表示":
        raise AssertionError("Japanese checkout cart summary has an untranslated details action")
    if button.get_attribute("aria-label") != "カートの詳細を表示":
        raise AssertionError("Japanese checkout cart details action has an untranslated accessible label")


def run_japan_customer_checkout() -> None:
    validate_isolated_ci_compose_project()
    validate_loopback_admin_targets()
    carrier = _read_config()
    driver = checkout.webdriver.Chrome(options=checkout.browser_options(1440, 960))
    stage = "product_search_and_quantity"
    try:
        unit_price = _add_quantity_and_open_checkout(driver, "shipping-free", 2, "shipping")
        stage = "coupon_condition"
        coupon = _apply_coupon_if_configured(driver)
        if not coupon["applied"]:
            raise AssertionError(str(coupon["coupon_condition"]))
        stage = "customer_registration"
        email = checkout.register_checkout_account(driver, "shipping-free")
        stage = "japan_delivery_address"
        checkout.select_japan_address(driver, "shipping-free")

        stage = "japan_free_carrier_checkout"
        browser_totals = _select_free_carrier_and_assert_zero(
            driver,
            carrier,
            tax_rule_group_id=PRODUCT_TAX_RULE_GROUP_ID,
            pre_discount_tax_total=200,
        )
        _assert_synthetic_taxable_totals(browser_totals, quantity=2, coupon_applied=True)
        if browser_totals["discounts_tax_incl"] <= 0:
            raise AssertionError("the seeded CI coupon did not reduce this customer's product total")
        if browser_totals["products_tax_incl"] != unit_price * 2:
            raise AssertionError(
                "cart product subtotal differs from the displayed per-item price and quantity: "
                f"{unit_price} x 2 != {browser_totals['products_tax_incl']}"
            )
        browser_totals.update({
            "displayed_unit_price": unit_price,
            "quantity": 2,
            "coupon_condition": coupon["coupon_condition"],
        })
        _assert_japanese_cart_details_copy(driver)
        driver.save_screenshot(str(QA_DIR / "shipping-free-checkout-desktop.png"))
        driver.set_window_size(390, 844)
        mobile_totals = _cart_snapshot(
            driver,
            tax_rule_group_id=PRODUCT_TAX_RULE_GROUP_ID,
            pre_discount_tax_total=200,
        )
        if mobile_totals != {
            key: browser_totals[key]
            for key in mobile_totals
        }:
            raise AssertionError("mobile checkout totals differ from the verified desktop totals")
        _assert_mobile_checkout_controls_visible(driver)
        _assert_japanese_checkout_copy(driver)
        driver.save_screenshot(str(QA_DIR / "shipping-free-checkout-mobile.png"))
        driver.set_window_size(1440, 960)

        stage = "offline_payment"
        _click_offline_payment(driver)
        stage = "place_unpaid_order"
        order, confirmation_totals = _place_unpaid_order_and_verify_confirmation(
            driver,
            "shipping-free",
            email,
            browser_totals,
            "shipping-free-order-confirmation-desktop.png",
        )
        history_total = _order_history_total(driver, order["reference"])
        if history_total != browser_totals["total_tax_incl"]:
            raise AssertionError(
                f"customer order history shows ¥{history_total}; checkout showed ¥{browser_totals['total_tax_incl']}"
            )
        order.update({
            "carrier_id": int(carrier["id"]),
            "carrier_name": str(carrier["name"]),
            "expected_shipping_fee": 0,
            "quantity": 2,
            "browser_totals": browser_totals,
            "order_history_total": history_total,
            "order_confirmation_totals": confirmation_totals,
            "coupon": coupon,
            "carrier_tax_rule_group_id": carrier["carrier_tax_rule_group_id"],
            "product_tax_rule_group_id": PRODUCT_TAX_RULE_GROUP_ID,
            "tax_fixture_scope": (
                "run-scoped CI-only synthetic 10% tax-inclusive test price: ¥1,100 gross / ¥1,000 net per item; "
                "not a legal tax rate or tax determination"
            ),
            "destination_scope": "synthetic Tokyo address 100-0004, served through the run-scoped Japan-only zone",
            "destination": {
                "postcode": "100-0004",
                "city": "千代田区",
                "state_iso_code": "JP-13",
                "address1_fragment": "大手町",
            },
        })
        ORDER_PATH.write_text(
            json.dumps(order, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            "PASS: Japan checkout selected the saved free carrier and retained ¥0 shipping for "
            f"quantity=2; order history total ¥{history_total}; "
            f"coupon_condition={coupon['coupon_condition']}."
        )
    except Exception as error:
        try:
            driver.save_screenshot(str(QA_DIR / "shipping-free-checkout-failure.png"))
        except Exception:
            pass
        _emit_failure(stage, error, driver)
        raise SystemExit(f"isolated Japan free-shipping checkout failed at {stage}") from None
    finally:
        driver.quit()


def run_japan_mobile_osaka_checkout() -> None:
    """Place a distinct one-unit mobile order to the synthetic supported Osaka region."""
    validate_isolated_ci_compose_project()
    validate_loopback_admin_targets()
    carrier = _read_config()
    driver = checkout.webdriver.Chrome(options=checkout.browser_options(390, 844))
    stage = "mobile_product_search_and_quantity"
    try:
        unit_price = _add_quantity_and_open_checkout(
            driver,
            "shipping-free-mobile",
            1,
            "shipping",
        )
        stage = "mobile_customer_registration"
        email = checkout.register_checkout_account(driver, "shipping-free-mobile")
        stage = "supported_osaka_delivery_address"
        _select_osaka_address(driver)

        stage = "osaka_free_carrier_checkout"
        browser_totals = _select_free_carrier_and_assert_zero(
            driver,
            carrier,
            tax_rule_group_id=PRODUCT_TAX_RULE_GROUP_ID,
            pre_discount_tax_total=100,
        )
        _assert_synthetic_taxable_totals(browser_totals, quantity=1, coupon_applied=False)
        if browser_totals["products_tax_incl"] != unit_price:
            raise AssertionError(
                f"Osaka mobile cart does not show one displayed product price: ¥{unit_price} vs "
                f"¥{browser_totals['products_tax_incl']}"
            )
        browser_totals.update({
            "displayed_unit_price": unit_price,
            "quantity": 1,
            "coupon_condition": "not applied on the quantity-one Osaka region fixture",
        })
        driver.save_screenshot(str(QA_DIR / "shipping-free-checkout-osaka-mobile.png"))

        stage = "mobile_offline_payment"
        _click_offline_payment(driver)
        stage = "place_mobile_unpaid_order"
        order, confirmation_totals = _place_unpaid_order_and_verify_confirmation(
            driver,
            "shipping-free-mobile",
            email,
            browser_totals,
            "shipping-free-osaka-order-confirmation-mobile.png",
        )
        history_total = _order_history_total(driver, order["reference"])
        if history_total != browser_totals["total_tax_incl"]:
            raise AssertionError(
                f"Osaka customer order history shows ¥{history_total}; checkout showed "
                f"¥{browser_totals['total_tax_incl']}"
            )
        order.update({
            "carrier_id": int(carrier["id"]),
            "carrier_name": str(carrier["name"]),
            "carrier_tax_rule_group_id": carrier["carrier_tax_rule_group_id"],
            "expected_shipping_fee": 0,
            "quantity": 1,
            "browser_totals": browser_totals,
            "order_history_total": history_total,
            "order_confirmation_totals": confirmation_totals,
            "coupon": {"code": None, "applied": False, "coupon_condition": "not applicable to this second region/quantity check"},
            "product_tax_rule_group_id": PRODUCT_TAX_RULE_GROUP_ID,
            "tax_fixture_scope": (
                "run-scoped CI-only synthetic 10% tax-inclusive test price: ¥1,100 gross / ¥1,000 net per item; "
                "not a legal tax rate or tax determination"
            ),
            "destination_scope": "synthetic Osaka address 530-0001, served through the run-scoped Japan-only zone",
            "destination": {
                "postcode": "530-0001",
                "city": "大阪市北区",
                "state_iso_code": "JP-27",
                "address1_fragment": "梅田",
            },
        })
        mobile_order_path = QA_DIR / "shipping-free-mobile-order.json"
        mobile_order_path.write_text(
            json.dumps(order, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            "PASS: mobile Osaka checkout saved quantity 1 with the same free Japan carrier, ¥0 shipping, "
            f"and customer history total ¥{history_total}."
        )
    except Exception as error:
        try:
            driver.save_screenshot(str(QA_DIR / "shipping-free-osaka-mobile-failure.png"))
        except Exception:
            pass
        _emit_failure(stage, error, driver)
        raise SystemExit(f"isolated Osaka mobile free-shipping checkout failed at {stage}") from None
    finally:
        driver.quit()


def run_japan_taxable_customer_checkout() -> None:
    """Reconcile an included synthetic CI tax amount through the real customer browser."""
    validate_isolated_ci_compose_project()
    validate_loopback_admin_targets()
    if PRODUCT_TAX_RULE_GROUP_ID <= 0:
        raise AssertionError("the taxable browser fixture requires an explicit positive native tax group")
    carrier = _read_config()
    driver = checkout.webdriver.Chrome(options=checkout.browser_options(1440, 960))
    stage = "taxable_product_search_and_price"
    try:
        unit_price = _add_quantity_and_open_checkout(
            driver,
            "shipping-free-taxable",
            1,
            "synthetic",
        )
        if unit_price != 1100:
            raise AssertionError(
                "the taxable product page did not display the fixture's ¥1,100 tax-included price; "
                f"visible unit price was ¥{unit_price}"
            )

        stage = "taxable_customer_registration"
        email = checkout.register_checkout_account(driver, "shipping-free-taxable")
        stage = "taxable_japan_address"
        checkout.select_japan_address(driver, "shipping-free-taxable")
        stage = "taxable_pre_coupon_free_carrier_checkout"
        pre_coupon_totals = _select_free_carrier_and_assert_zero(
            driver,
            carrier,
            tax_rule_group_id=PRODUCT_TAX_RULE_GROUP_ID,
            pre_discount_tax_total=100,
        )
        _assert_taxable_visible_totals(
            pre_coupon_totals,
            discount_tax_incl=0,
            final_tax_incl=1100,
            tax=100,
            discount_tax_excl=0,
            final_tax_excl=1000,
        )
        _assert_synthetic_taxable_totals(pre_coupon_totals, quantity=1, coupon_applied=False)

        stage = "taxable_coupon_condition"
        coupon = _apply_coupon_if_configured(driver)
        if not coupon["applied"]:
            raise AssertionError(str(coupon["coupon_condition"]))

        stage = "taxable_discounted_free_carrier_checkout"
        browser_totals = _select_free_carrier_and_assert_zero(
            driver,
            carrier,
            tax_rule_group_id=PRODUCT_TAX_RULE_GROUP_ID,
            # This is the explicitly synthetic fixture amount; it is only
            # used if the storefront displays a full tax breakdown. A missing
            # UI tax row remains null and is checked against the saved order.
            pre_discount_tax_total=100,
        )
        _assert_taxable_visible_totals(
            browser_totals,
            discount_tax_incl=550,
            final_tax_incl=550,
            tax=50,
            discount_tax_excl=500,
            final_tax_excl=500,
        )
        _assert_synthetic_taxable_totals(browser_totals, quantity=1, coupon_applied=True)
        browser_totals.update({
            "displayed_unit_price": unit_price,
            "quantity": 1,
            "coupon_condition": coupon["coupon_condition"],
        })
        driver.save_screenshot(str(QA_DIR / "shipping-free-taxable-checkout-desktop.png"))

        stage = "taxable_offline_payment"
        _click_offline_payment(driver)
        stage = "taxable_unpaid_order"
        order, confirmation_totals = _place_unpaid_order_and_verify_confirmation(
            driver,
            "shipping-free-taxable",
            email,
            browser_totals,
            "shipping-free-taxable-order-confirmation-desktop.png",
        )
        history_total = _order_history_total(driver, order["reference"])
        if history_total != 550 or history_total != browser_totals["total_tax_incl"]:
            raise AssertionError(
                f"taxable customer history shows ¥{history_total}; discounted checkout final price was ¥550"
            )
        order.update({
            "carrier_id": int(carrier["id"]),
            "carrier_name": str(carrier["name"]),
            "carrier_tax_rule_group_id": carrier["carrier_tax_rule_group_id"],
            "expected_shipping_fee": 0,
            "quantity": 1,
            "browser_totals": browser_totals,
            "order_history_total": history_total,
            "order_confirmation_totals": confirmation_totals,
            "pre_coupon_browser_totals": pre_coupon_totals,
            "coupon": coupon,
            "product_tax_rule_group_id": PRODUCT_TAX_RULE_GROUP_ID,
            "tax_fixture_scope": (
                "CI-only synthetic 10% test rule; ¥1,100 tax-included is ¥1,000 before tax plus ¥100 test tax; "
                "the run-scoped 50% tax-inclusive coupon leaves ¥550 including ¥50 synthetic test tax; "
                "not a legal tax rate or tax determination"
            ),
            "destination_scope": "synthetic Tokyo 100-0004, served through the run-scoped Japan-only free carrier",
            "destination": {
                "postcode": "100-0004",
                "city": "千代田区",
                "state_iso_code": "JP-13",
                "address1_fragment": "大手町",
            },
        })
        taxable_order_path = QA_DIR / "shipping-free-taxable-order.json"
        taxable_order_path.write_text(
            json.dumps(order, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            "PASS: Chromium verified the ¥1,100 tax-inclusive sale amount, ¥550 customer total after the "
            "tax-inclusive coupon, and ¥0 Japan shipping. The native saved-order check verifies the actual "
            "tax rule and amount separately."
        )
    except Exception as error:
        try:
            driver.save_screenshot(str(QA_DIR / "shipping-free-taxable-checkout-failure.png"))
        except Exception:
            pass
        _emit_failure(stage, error, driver)
        raise SystemExit(f"isolated taxable free-shipping checkout failed at {stage}") from None
    finally:
        driver.quit()


def run_japan_explicit_exemption_customer_checkout() -> None:
    """Exercise an explicit CI-only zero-rate Japan rule through an unpaid order."""
    validate_isolated_ci_compose_project()
    validate_loopback_admin_targets()
    if PRODUCT_TAX_RULE_GROUP_ID < 1:
        raise AssertionError("the exemption scenario requires its positive run-scoped zero-rate group ID")
    carrier = _read_config()
    driver = checkout.webdriver.Chrome(options=checkout.browser_options(1440, 960))
    stage = "explicit_exemption_product_search_and_price"
    try:
        unit_price = _add_quantity_and_open_checkout(
            driver,
            "shipping-free-explicit-exemption",
            1,
            "exemption",
        )
        if unit_price != 1000:
            raise AssertionError(
                f"the explicit zero-rate product detail showed ¥{unit_price}; expected its ¥1,000 TTC price"
            )

        stage = "explicit_exemption_customer_registration"

        def set_registration_stage(registration_stage: str) -> None:
            nonlocal stage
            if re.fullmatch(r"[a-z][a-z0-9_.]{0,127}", registration_stage):
                stage = f"explicit_exemption_customer_registration.{registration_stage}"
            else:
                stage = "explicit_exemption_customer_registration.unknown"

        email = checkout.register_checkout_account(
            driver,
            "shipping-free-explicit-exemption",
            stage_callback=set_registration_stage,
        )
        stage = "explicit_exemption_japan_address"
        checkout.select_japan_address(driver, "shipping-free-explicit-exemption")
        stage = "explicit_exemption_free_carrier_checkout"
        browser_totals = _select_free_carrier_and_assert_zero(
            driver,
            carrier,
            tax_rule_group_id=PRODUCT_TAX_RULE_GROUP_ID,
            explicit_zero_rate_rule=True,
        )
        expected_totals = {
            "products_tax_incl": 1000,
            "products_tax_excl": 1000,
            "shipping_tax_incl": 0,
            "shipping_tax_excl": 0,
            "discounts_tax_incl": 0,
            "discounts_tax_excl": 0,
            "tax": 0,
            "total_tax_incl": 1000,
            "total_tax_excl": 1000,
            "tax_display_mode": "explicit_zero_rate_rule",
            "tax_rules_group_id": PRODUCT_TAX_RULE_GROUP_ID,
        }
        for key, expected in expected_totals.items():
            if browser_totals.get(key) != expected:
                raise AssertionError(
                    f"explicit exemption checkout {key}={browser_totals.get(key)!r}; expected {expected!r}"
                )
        if browser_totals["products_tax_incl"] != unit_price:
            raise AssertionError("the explicit exemption cart subtotal differs from the product detail price")
        browser_totals.update({
            "displayed_unit_price": unit_price,
            "quantity": 1,
            "tax_status": "explicit_exemption_test",
        })
        driver.save_screenshot(str(QA_DIR / "shipping-free-exemption-checkout-desktop.png"))

        stage = "explicit_exemption_offline_payment"
        _click_offline_payment(driver)
        stage = "explicit_exemption_unpaid_order"
        order, confirmation_totals = _place_unpaid_order_and_verify_confirmation(
            driver,
            "shipping-free-explicit-exemption",
            email,
            browser_totals,
            "shipping-free-exemption-order-confirmation-desktop.png",
        )
        history_total = _order_history_total(driver, order["reference"])
        if history_total != 1000 or history_total != browser_totals["total_tax_incl"]:
            raise AssertionError(
                f"explicit exemption customer history shows ¥{history_total}; checkout showed ¥1,000"
            )
        order.update({
            "carrier_id": int(carrier["id"]),
            "carrier_name": str(carrier["name"]),
            "carrier_tax_rule_group_id": carrier["carrier_tax_rule_group_id"],
            "expected_shipping_fee": 0,
            "quantity": 1,
            "displayed_unit_price": unit_price,
            "browser_totals": browser_totals,
            "order_history_total": history_total,
            "order_confirmation_totals": confirmation_totals,
            "coupon": {"code": None, "applied": False},
            "product_tax_rule_group_id": PRODUCT_TAX_RULE_GROUP_ID,
            "tax_status": "explicit_exemption_test",
            "tax_rate_percent": 0,
            "tax_fixture_scope": (
                "CI-only explicit zero-rate exemption test fixture; not a legal tax rate or tax determination"
            ),
            "destination_scope": "synthetic Tokyo address 100-0004, served through the run-scoped Japan-only zone",
            "destination": {
                "postcode": "100-0004",
                "city": "千代田区",
                "state_iso_code": "JP-13",
                "address1_fragment": "大手町",
            },
        })
        exemption_order_path = QA_DIR / "shipping-free-exemption-order.json"
        exemption_order_path.write_text(
            json.dumps(order, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            "PASS: explicit CI-only Japan zero-rate rule preserved ¥1,000 product/checkout/confirmation/history "
            "totals and ¥0 shipping; actual order tax is verified separately in the isolated database."
        )
    except Exception as error:
        try:
            driver.save_screenshot(str(QA_DIR / "shipping-free-exemption-checkout-failure.png"))
        except Exception:
            pass
        checkout_registration_state = None
        if stage.startswith("explicit_exemption_customer_registration."):
            checkout_registration_state = checkout.safe_checkout_registration_state(driver)
        _emit_failure(stage, error, driver, checkout_registration_state)
        raise SystemExit(f"explicit exemption free-shipping checkout failed at {stage}") from None
    finally:
        driver.quit()


def _parse_order_amount(driver, selector: str) -> int:
    return _parse_yen(_wait_present(driver, selector).text)


def _expected_admin_order_totals(
    order: dict[str, object],
    verified: dict[str, object],
) -> dict[str, int]:
    browser_totals = order["browser_totals"]
    native_tax = round(
        float(verified["total_paid_tax_incl"]) - float(verified["total_paid_tax_excl"])
    )
    if native_tax < 0:
        raise AssertionError("the native saved order has a negative tax amount")

    product_tax_group_id = int(order.get("product_tax_rule_group_id", 0))
    browser_tax = browser_totals.get("tax")
    expected = {
        "products": int(browser_totals["products_tax_incl"]),
        "shipping": 0,
        "total": int(browser_totals["total_tax_incl"]),
    }
    if product_tax_group_id > 0:
        if order.get("tax_status") == "explicit_exemption_test":
            if native_tax != 0 or browser_tax != 0:
                raise AssertionError("the explicit zero-rate group must resolve to zero native/browser tax")
            expected["tax"] = 0
        else:
            if native_tax <= 0:
                raise AssertionError("the configured taxable order has no persisted tax amount")
            if browser_tax is not None and int(browser_tax) != native_tax:
                raise AssertionError(
                    f"displayed tax amount ¥{browser_tax} differs from native saved tax ¥{native_tax}"
                )
            expected["tax"] = native_tax
    else:
        if native_tax != 0:
            raise AssertionError(
                "the unassigned product tax rule has persisted tax; it must not be classified as exempt"
            )
        if browser_tax is not None:
            raise AssertionError(
                "unassigned tax must remain unknown in customer checkout totals, not be recorded as an amount"
            )
    return expected


def _assert_unknown_admin_tax_display(tax_values: list[int]) -> None:
    if tax_values:
        raise AssertionError(
            "unassigned tax must remain unknown in the Back Office, with no zero or nonzero tax line"
        )


def _reconcile_admin_shipping_total(
    shown_shipping: int | None,
    browser_shipping: int,
    verified: dict[str, object],
) -> int:
    if (
        browser_shipping != 0
        or float(verified["total_shipping_tax_excl"]) != 0
        or float(verified["total_shipping_tax_incl"]) != 0
    ):
        raise AssertionError("browser and native saved order must confirm ¥0 shipping")
    if shown_shipping is not None and shown_shipping != 0:
        raise AssertionError("the Back Office shipping total must remain zero")
    return 0


def _admin_order_state_id(driver) -> int:
    state_select = _wait_visible(
        driver,
        'form.card-details-form select[name="update_order_status[new_order_status_id]"]',
    )
    selected_value = Select(state_select).first_selected_option.get_attribute("value") or ""
    if re.fullmatch(r"[0-9]+", selected_value) is None or int(selected_value) < 1:
        raise AssertionError("the native order detail did not expose a positive current state ID")
    return int(selected_value)


def _classify_isolated_admin_order_detail_url(href: str, expected_order_id: int) -> str:
    """Return a safe route class after checking the configured Back Office origin/folder."""
    try:
        actual = urlparse(href)
        configured_admin = urlparse(ADMIN_LOGIN)
        actual_port = actual.port
        configured_port = configured_admin.port
    except ValueError:
        return "invalid_url"
    admin_folder = configured_admin.path.rstrip("/")
    if (
        actual.scheme.lower() != configured_admin.scheme.lower()
        or (actual.hostname or "").casefold() != (configured_admin.hostname or "").casefold()
        or actual_port != configured_port
        or actual.username is not None
        or actual.password is not None
        or actual.fragment
    ):
        return "origin_mismatch"
    if not admin_folder or not actual.path.startswith(admin_folder + "/"):
        return "admin_folder_mismatch"
    order_id = str(expected_order_id)
    if checkout.is_modern_admin_order_detail_url(href, order_id):
        return "modern_order_detail"
    if checkout.is_legacy_admin_order_detail_url(href, order_id):
        return "legacy_order_detail"
    return "other_admin_route"


def _matches_isolated_admin_order_detail_url(href: str, expected_order_id: int) -> bool:
    return _classify_isolated_admin_order_detail_url(href, expected_order_id) in {
        "modern_order_detail",
        "legacy_order_detail",
    }


def _matching_admin_order_document(
    browser, expected_reference: object, expected_order_id: int, diagnostics: dict
) -> bool:
    """Poll only through a transient stale body read; require the exact order and admin route."""
    attempt_count = diagnostics.get('attempt_count', 0)
    if type(attempt_count) is not int or attempt_count < 0:
        attempt_count = 0
    diagnostics['attempt_count'] = min(attempt_count + 1, 9999)
    diagnostics['stale_seen'] = diagnostics.get('stale_seen') is True

    route_class = _classify_isolated_admin_order_detail_url(browser.current_url, expected_order_id)
    diagnostics['route_class'] = (
        route_class if route_class in ADMIN_DOCUMENT_WAIT_ROUTE_CLASSES else 'unknown'
    )
    diagnostics['body_text_read'] = 'not_read'
    diagnostics['body_reference_matches'] = False
    if type(expected_reference) is not str or not expected_reference:
        return False
    try:
        body_text = browser.find_element(By.TAG_NAME, 'body').text
    except StaleElementReferenceException:
        diagnostics['body_text_read'] = 'stale'
        diagnostics['stale_seen'] = True
        return False

    body_reference_matches = expected_reference in body_text
    diagnostics['body_text_read'] = 'read'
    diagnostics['body_reference_matches'] = body_reference_matches
    return body_reference_matches and route_class in ADMIN_ORDER_DETAIL_ROUTE_CLASSES


def _observed_admin_order_document_get(driver, expected_order_id: int) -> bool:
    """Confirm a document GET for this order without retaining or emitting its URL."""
    for entry in driver.get_log("performance"):
        try:
            message = json.loads(entry.get("message", "")).get("message", {})
            params = message.get("params", {})
            request = params.get("request", {})
            route_class = _classify_isolated_admin_order_detail_url(
                str(request.get("url", "")),
                expected_order_id,
            )
        except (AttributeError, TypeError, ValueError):
            continue
        if (
            message.get("method") == "Network.requestWillBeSent"
            and params.get("type") == "Document"
            and request.get("method") == "GET"
            and route_class in {"modern_order_detail", "legacy_order_detail"}
        ):
            return True
    return False


def _activate_admin_order_tab(
    driver,
    tab_selector: str,
    panel_selector: str,
    tracking_diagnostics: dict[str, object] | None = None,
) -> None:
    """Open a native order tab and wait until its panel is the active visible pane."""
    tab_kind = 'history' if tab_selector == '#historyTab' else 'shipping'
    _set_tracking_diagnostic(
        tracking_diagnostics, 'admin', f'admin_{tab_kind}_tab_target', driver
    )
    tab = _wait_visible(driver, tab_selector)
    _set_tracking_diagnostic(
        tracking_diagnostics, 'admin', f'admin_{tab_kind}_tab_panel', driver
    )
    panel = driver.find_element(By.CSS_SELECTOR, panel_selector)
    tab_classes = (tab.get_attribute("class") or "").split()
    panel_classes = (panel.get_attribute("class") or "").split()
    if "active" not in tab_classes or "active" not in panel_classes or not panel.is_displayed():
        _set_tracking_diagnostic(
            tracking_diagnostics, 'admin', f'admin_{tab_kind}_tab_click', driver
        )
        checkout.click_at_center(driver, tab)
    _set_tracking_diagnostic(
        tracking_diagnostics, 'admin', f'admin_{tab_kind}_tab_wait', driver
    )
    WebDriverWait(driver, 15).until(
        lambda browser: (
            "active" in (browser.find_element(By.CSS_SELECTOR, tab_selector).get_attribute("class") or "").split()
            and "active" in (browser.find_element(By.CSS_SELECTOR, panel_selector).get_attribute("class") or "").split()
            and browser.find_element(By.CSS_SELECTOR, panel_selector).is_displayed()
        )
    )


def _assign_tracking_number_through_admin_ui(
    driver,
    order: dict[str, object],
    verified: dict[str, object],
    expected_totals: dict[str, int],
    tracking_diagnostics: dict[str, object] | None = None,
) -> dict[str, object]:
    """Update one run-scoped synthetic order through PrestaShop's native AdminOrders form."""
    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_target_route', driver)
    order_id = int(order.get("order_id", 0))
    carrier_id = int(order.get("carrier_id", 0))
    expected_email = checkout.checkout_registration_email("shipping-free", RUN_ID, RUN_ATTEMPT)
    admin_initial_route_class = _classify_isolated_admin_order_detail_url(driver.current_url, order_id)
    if (
        admin_initial_route_class not in {"modern_order_detail", "legacy_order_detail"}
        or order.get("viewport") != "shipping-free"
        or order_id < 1
        or int(verified.get("order_id", 0)) != order_id
        or verified.get("reference") != order.get("reference")
        or order.get("email") != expected_email
        or verified.get("email") != expected_email
        or verified.get("payment_module") != "ps_checkpayment"
        or order.get("payment_module") != "ps_checkpayment"
        or float(verified.get("total_paid_real", -1)) != 0.0
        or verified.get("order_state_paid") is not False
        or int(verified.get("order_state_id", 0)) < 1
        or verified.get("carrier_url_configured") is not False
        or carrier_id < 1
        or int(verified.get("carrier_id", 0)) != carrier_id
        or float(verified.get("total_shipping_tax_incl", -1)) != 0.0
        or int(expected_totals.get("shipping", -1)) != 0
    ):
        raise AssertionError("tracking acceptance target is not the matching unpaid CI order with free shipping")

    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_history_tab', driver)
    _activate_admin_order_tab(
        driver, "#historyTab", "#historyTabContent", tracking_diagnostics
    )
    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_history_status_readback', driver)
    status_before_tracking_update = _admin_order_state_id(driver)
    if status_before_tracking_update != int(verified["order_state_id"]):
        raise AssertionError("the admin order status does not match the unpaid native order readback")

    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_shipping_tab', driver)
    _activate_admin_order_tab(
        driver, "#orderShippingTab", "#orderShippingTabContent", tracking_diagnostics
    )
    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_shipping_row_readback', driver)
    shipping_rows = [
        row
        for row in driver.find_elements(By.CSS_SELECTOR, "#shipping-grid-table tbody tr")
        if row.is_displayed()
    ]
    if len(shipping_rows) != 1:
        raise AssertionError("the synthetic order does not have exactly one editable native carrier row")
    row = shipping_rows[0]
    carrier_name = row.find_element(By.CSS_SELECTOR, ".carrier-name").text.strip()
    carrier_price = _parse_yen(row.find_element(By.CSS_SELECTOR, ".carrier-price").text)
    current_tracking = row.find_element(By.CSS_SELECTOR, ".carrier-tracking-number").text.strip()
    if (
        carrier_name != order.get("carrier_name")
        or carrier_price != 0
        or current_tracking
    ):
        raise AssertionError("the matching synthetic carrier row is not in its expected free, unassigned state")

    tracking_number = f"ORDENOWA-CI-TRACK-{RUN_ID[-20:]}-{RUN_ATTEMPT[-4:]}"
    if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", tracking_number):
        raise AssertionError("the run-scoped synthetic tracking fixture is invalid")

    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_edit_link_readback', driver)
    edit_link = _wait_visible(driver, "#shipping-grid-table tbody tr .js-update-shipping-btn")
    if (edit_link.get_attribute("data-carrier-id") or "") != str(carrier_id):
        raise AssertionError("the native tracking edit link points at a different carrier")
    order_carrier_id = edit_link.get_attribute("data-order-carrier-id") or ""
    if re.fullmatch(r"[0-9]+", order_carrier_id) is None or int(order_carrier_id) < 1:
        raise AssertionError("the native tracking edit link omitted its order-carrier identity")

    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_modal_open', driver)
    checkout.click_at_center(driver, edit_link)
    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_modal_fields_readback', driver)
    tracking_input = _wait_visible(driver, "#update_order_shipping_tracking_number")
    current_carrier_input = driver.find_element(By.CSS_SELECTOR, "#update_order_shipping_current_order_carrier_id")
    if current_carrier_input.get_attribute("value") != order_carrier_id:
        raise AssertionError("the native shipping form did not retain the matching order-carrier identity")
    # The native form uses Select2; the backing <select> is hidden after the modal opens.
    carrier_select = driver.find_element(By.CSS_SELECTOR, "#update_order_shipping_new_carrier_id")
    if Select(carrier_select).first_selected_option.get_attribute("value") != str(carrier_id):
        raise AssertionError("the native shipping form did not preserve the existing free carrier")
    tracking_input.clear()
    tracking_input.send_keys(tracking_number)
    update_button = _wait_visible(driver, "#updateOrderShippingModal button[type='submit']")
    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_tracking_submit', driver)
    checkout.click_at_center(driver, update_button)

    document_wait_state = {
        'attempt_count': 0,
        'route_class': 'unknown',
        'body_text_read': 'not_read',
        'body_reference_matches': False,
        'stale_seen': False,
    }
    if isinstance(tracking_diagnostics, dict):
        tracking_diagnostics['document_wait_predicate'] = document_wait_state

    def matching_order_document(browser) -> bool:
        return _matching_admin_order_document(
            browser, order.get("reference"), order_id, document_wait_state
        )

    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_post_save_document_wait', driver)
    WebDriverWait(driver, 35).until(matching_order_document)
    post_save_document_wait = dict(document_wait_state)
    admin_route_class_after_save = _classify_isolated_admin_order_detail_url(driver.current_url, order_id)
    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_post_save_shipping_tab', driver)
    _activate_admin_order_tab(
        driver, "#orderShippingTab", "#orderShippingTabContent", tracking_diagnostics
    )

    def tracking_saved(browser) -> bool:
        rows = [
            row
            for row in browser.find_elements(By.CSS_SELECTOR, "#shipping-grid-table tbody tr")
            if row.is_displayed()
        ]
        return (
            len(rows) == 1
            and rows[0].find_element(By.CSS_SELECTOR, ".carrier-tracking-number").text.strip() == tracking_number
        )

    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_post_save_row_readback', driver)
    WebDriverWait(driver, 35).until(tracking_saved)
    # Reload the exact native order page so the assertion reads persisted state from a new document.
    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_fresh_get_setup', driver)
    driver.execute_cdp_cmd("Network.enable", {})
    driver.get_log("performance")
    driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
    driver.refresh()
    document_wait_state = {
        'attempt_count': 0,
        'route_class': 'unknown',
        'body_text_read': 'not_read',
        'body_reference_matches': False,
        'stale_seen': False,
    }
    if isinstance(tracking_diagnostics, dict):
        tracking_diagnostics['document_wait_predicate'] = document_wait_state
    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_fresh_get_document_wait', driver)
    WebDriverWait(driver, 35).until(matching_order_document)
    fresh_get_document_wait = dict(document_wait_state)
    admin_fresh_get_method_get = _observed_admin_order_document_get(driver, order_id)
    if not admin_fresh_get_method_get:
        raise AssertionError("the fresh native order document did not produce a matching GET request")
    admin_route_class_after_fresh_get = _classify_isolated_admin_order_detail_url(driver.current_url, order_id)
    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_fresh_history_readback', driver)
    _activate_admin_order_tab(
        driver, "#historyTab", "#historyTabContent", tracking_diagnostics
    )

    status_after_tracking_update = _admin_order_state_id(driver)
    order_total_after = _parse_order_amount(driver, "#orderTotal")

    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_fresh_shipping_tab', driver)
    _activate_admin_order_tab(
        driver, "#orderShippingTab", "#orderShippingTabContent", tracking_diagnostics
    )
    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_tracking_fresh_readback', driver)
    WebDriverWait(driver, 35).until(tracking_saved)
    shipping_total_element = _wait_present(driver, "#orderShippingTotal")
    shipping_total_text = (shipping_total_element.get_attribute("textContent") or "").strip()
    shown_shipping_total = _parse_yen(shipping_total_text) if shipping_total_text else None
    shipping_total_after = _reconcile_admin_shipping_total(
        shown_shipping_total,
        int(expected_totals["shipping"]),
        verified,
    )
    carrier_name_after = _wait_visible(driver, "#shipping-grid-table .carrier-name").text.strip()
    carrier_price_after = _parse_yen(_wait_visible(driver, "#shipping-grid-table .carrier-price").text)
    carrier_link_after = _wait_visible(driver, "#shipping-grid-table tbody tr .js-update-shipping-btn")
    carrier_id_after = carrier_link_after.get_attribute("data-carrier-id") or ""
    if (
        status_after_tracking_update != status_before_tracking_update
        or status_after_tracking_update != int(verified["order_state_id"])
        or carrier_name_after != order.get("carrier_name")
        or carrier_id_after != str(carrier_id)
        or carrier_price_after != 0
        or shipping_total_after != 0
        or order_total_after != int(expected_totals["total"])
    ):
        raise AssertionError("the native tracking update changed the unpaid status or free-shipping order totals")

    _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_tracking_capture', driver)
    driver.save_screenshot(str(QA_DIR / "shipping-free-order-tracking-admin.png"))
    return {
        "order_id": order_id,
        "carrier_id": carrier_id,
        "order_carrier_id": int(order_carrier_id),
        "tracking_number": tracking_number,
        "admin_route_class_before_update": admin_initial_route_class,
        "admin_route_class_after_save": admin_route_class_after_save,
        "admin_route_class_after_fresh_get": admin_route_class_after_fresh_get,
        "admin_origin_matches": True,
        "admin_folder_matches": True,
        "admin_order_id_matches": True,
        "admin_post_save_order_id_matches": True,
        "admin_fresh_get_order_id_matches": True,
        "admin_fresh_get_method_get": admin_fresh_get_method_get,
        "admin_post_save_document_wait": post_save_document_wait,
        "admin_fresh_get_document_wait": fresh_get_document_wait,
        "admin_fresh_get_method_get": admin_fresh_get_method_get,
        "admin_order_state_id_before": status_before_tracking_update,
        "admin_order_state_id_after": status_after_tracking_update,
        "admin_order_state_preserved": status_after_tracking_update == status_before_tracking_update,
        "admin_order_total": order_total_after,
        "admin_shipping_total": shipping_total_after,
    }


def _customer_order_detail_link_matches(href: str, expected_order_id: int) -> bool:
    try:
        actual = urlparse(href)
        base = urlparse(BASE)
        actual_port = actual.port
        base_port = base.port
    except ValueError:
        return False
    if (
        actual.scheme.lower() != base.scheme.lower()
        or (actual.hostname or "").casefold() != (base.hostname or "").casefold()
        or actual_port != base_port
        or actual.username is not None
        or actual.password is not None
        or actual.fragment
    ):
        return False
    base_path = base.path.rstrip("/")
    if base_path and not (actual.path == base_path or actual.path.startswith(base_path + "/")):
        return False
    query = parse_qs(actual.query, keep_blank_values=True)
    order_ids = query.get("id_order", [])
    if order_ids != [str(expected_order_id)]:
        return False
    controller = query.get("controller", [])
    if controller and controller != ["order-detail"]:
        return False
    route_path = actual.path.rstrip("/").casefold()
    return controller == ["order-detail"] or route_path.endswith("/order-detail")


def _customer_order_detail_route_class(href: str, expected_order_id: int) -> str:
    if not _customer_order_detail_link_matches(href, expected_order_id):
        return "other_customer_route"
    query = parse_qs(urlparse(href).query, keep_blank_values=True)
    if query.get("controller") == ["order-detail"]:
        return "order_detail_controller"
    return "friendly_order_detail"


def _clear_customer_password_fields(driver) -> bool:
    """Clear all customer password inputs and confirm the DOM contains no value."""
    return bool(
        driver.execute_script(
            """
            const fields = Array.from(document.querySelectorAll('input[type="password"]'));
            for (const field of fields) {
              field.value = '';
              field.dispatchEvent(new Event('input', {bubbles: true}));
              field.dispatchEvent(new Event('change', {bubbles: true}));
            }
            return fields.every((field) => field.value === '');
            """
        )
    )


def _save_customer_tracking_screenshot(driver, filename: str) -> bool:
    """Save customer evidence only after clearing and checking every password input."""
    if not _clear_customer_password_fields(driver):
        return False
    return bool(driver.save_screenshot(str(QA_DIR / filename)))


def _assert_japanese_order_detail_copy(driver) -> None:
    """Check only the static Japanese labels on this same synthetic customer order page."""
    expected_language = "ja-JP"
    document_language = driver.find_element(By.TAG_NAME, "html").get_attribute("lang") or ""
    if not document_language.lower().startswith(expected_language.split("-")[0].lower()):
        raise AssertionError("customer order detail did not render in Japanese")

    reference = driver.find_element(By.CSS_SELECTOR, ".order-infos__reference").text.strip()
    if not reference.startswith("注文番号:") or " - 注文日:" not in reference:
        raise AssertionError("Japanese order detail reference labels are missing")

    payment = driver.find_element(By.CSS_SELECTOR, ".order-infos__payment").text.strip()
    if not payment.startswith("お支払い方法:"):
        raise AssertionError("Japanese order detail payment label is missing")

    for carrier in driver.find_elements(By.CSS_SELECTOR, ".order-infos__carrier"):
        if not carrier.text.strip().startswith("配送業者:"):
            raise AssertionError("Japanese order detail carrier label is missing")

    tracking_heading = driver.find_element(By.CSS_SELECTOR, "#order_carriers_heading").text.strip()
    if tracking_heading != "配送追跡情報":
        raise AssertionError("Japanese shipment tracking heading is missing")

    tracking_table = driver.find_element(By.CSS_SELECTOR, ".order-carriers [role='table']")
    if tracking_table.get_attribute("aria-label") != "注文の配送状況":
        raise AssertionError("Japanese order tracking table label is missing")

    carrier_headers = driver.find_elements(By.CSS_SELECTOR, '.order-carriers [role="columnheader"]')
    if not any(header.text.strip() == "配送業者" for header in carrier_headers):
        raise AssertionError("Japanese tracking table carrier label is missing")


def _verify_customer_order_tracking_detail(
    driver,
    order: dict[str, object],
    tracking_number: str,
    order_id: int,
    tracking_diagnostics: dict[str, object] | None = None,
) -> str:
    _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_history_navigation', driver)
    checkout.visit(driver, BASE + "/index.php?controller=history")
    _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_history_route', driver)
    checkout.assert_canonical_ascii_friendly_route(driver, "history")
    _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_history_rows_readback', driver)
    history_rows = WebDriverWait(driver, 30).until(
        lambda browser: browser.find_elements(By.CSS_SELECTOR, ".order-history__row")
    )
    _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_order_link_readback', driver)
    matched_links = []
    for history_row in history_rows:
        reference_cells = history_row.find_elements(By.CSS_SELECTOR, ".order-history__cell--reference")
        if not reference_cells or reference_cells[0].text.strip() != order.get("reference"):
            continue
        matched_links.extend(
            link
            for link in history_row.find_elements(By.CSS_SELECTOR, "a[data-link-action='view-order-details']")
            if _customer_order_detail_link_matches(link.get_attribute("href") or "", order_id)
        )
    if len(matched_links) != 1:
        raise AssertionError("customer order history did not expose one same-origin detail link for this order")

    _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_order_detail_click', driver)
    checkout.click_at_center(driver, matched_links[0])
    _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_detail_document_wait', driver)
    WebDriverWait(driver, 35).until(
        lambda browser: order.get("reference") in browser.find_element(By.TAG_NAME, "body").text
        and bool(browser.find_elements(By.CSS_SELECTOR, "#order_carriers_heading"))
    )
    _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_detail_route_readback', driver)
    customer_route_class = _customer_order_detail_route_class(driver.current_url, order_id)
    if customer_route_class == "other_customer_route":
        raise AssertionError("customer order detail did not retain the matching native order identity")
    _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_japanese_labels', driver)
    _assert_japanese_order_detail_copy(driver)

    _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_tracking_cell_readback', driver)
    tracking_cells = [
        cell
        for cell in driver.find_elements(By.CSS_SELECTOR, ".order-carriers .grid-table__row .grid-table__cell")
        if cell.is_displayed() and cell.text.strip() == tracking_number
    ]
    if len(tracking_cells) != 1:
        raise AssertionError("customer order detail did not display the saved tracking number for this order")
    _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_tracking_link_check', driver)
    if tracking_cells[0].find_elements(By.CSS_SELECTOR, "a"):
        raise AssertionError("the CI-only carrier unexpectedly exposed an external tracking destination")
    _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_summary_capture', driver)
    if not _save_customer_tracking_screenshot(driver, "shipping-free-order-tracking-customer.png"):
        raise AssertionError("customer tracking screenshot could not be saved with password fields cleared")
    _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_tracking_scroll', driver)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", tracking_cells[0])
    _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_tracking_table_capture', driver)
    if not _save_customer_tracking_screenshot(driver, "shipping-free-order-tracking-customer-table.png"):
        raise AssertionError("customer tracking table screenshot could not be saved with password fields cleared")
    return customer_route_class


def _verify_customer_order_tracking(
    driver,
    order: dict[str, object],
    tracking_number: str,
    tracking_diagnostics: dict[str, object] | None = None,
) -> str:
    """Login as the matching run-scoped customer and follow its native history link."""
    order_id = int(order.get("order_id", 0))
    expected_email = checkout.checkout_registration_email("shipping-free", RUN_ID, RUN_ATTEMPT)
    if order_id < 1 or order.get("email") != expected_email or not order.get("reference"):
        raise AssertionError("customer tracking readback did not receive the matching CI order identity")

    customer_password = f"ORDENOWA-CI-{RUN_ID}-{RUN_ATTEMPT}-Aa1!"
    _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_login_navigation', driver)
    try:
        checkout.visit(driver, BASE + "/index.php?controller=authentication")
        _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_login_form', driver)
        checkout.visible(driver, '#login-form input[name="email"]').send_keys(expected_email)
        checkout.visible(driver, '#login-form input[name="password"]').send_keys(customer_password)
        _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_login_submit', driver)
        checkout.visible(driver, "#submit-login").click()
        _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_login_success_wait', driver)
        WebDriverWait(driver, 35).until(
            lambda browser: any(
                element.is_displayed()
                for element in browser.find_elements(By.ID, "userMenuButton")
            )
        )
        _set_tracking_diagnostic(tracking_diagnostics, 'customer', 'customer_password_clear', driver)
        if not _clear_customer_password_fields(driver):
            raise AssertionError("customer login succeeded but the synthetic password remained in the browser DOM")
        return _verify_customer_order_tracking_detail(
            driver, order, tracking_number, order_id, tracking_diagnostics
        )
    except Exception:
        # This screenshot is permitted only after every password input was emptied and checked.
        if isinstance(tracking_diagnostics, dict):
            tracking_diagnostics['safe_pathname'] = _safe_tracking_pathname(driver)
        try:
            _save_customer_tracking_screenshot(driver, "shipping-free-order-tracking-customer-failure.png")
        except Exception:
            pass
        raise


def _verify_synthetic_order_tracking(
    admin_driver,
    order: dict[str, object],
    verified: dict[str, object],
    expected_totals: dict[str, int],
    tracking_diagnostics: dict[str, object] | None = None,
) -> dict[str, object]:
    admin_readback = _assign_tracking_number_through_admin_ui(
        admin_driver,
        order,
        verified,
        expected_totals,
        tracking_diagnostics,
    )
    customer_driver = checkout.webdriver.Chrome(options=checkout.browser_options(1440, 960))
    try:
        customer_route_class = _verify_customer_order_tracking(
            customer_driver,
            order,
            str(admin_readback["tracking_number"]),
            tracking_diagnostics,
        )
    finally:
        customer_driver.quit()

    result = {
        "synthetic_ci_only": True,
        "order_id": int(order["order_id"]),
        "order_reference": str(order["reference"]),
        "carrier_id": int(order["carrier_id"]),
        "order_carrier_id": int(admin_readback["order_carrier_id"]),
        "tracking_number": str(admin_readback["tracking_number"]),
        "admin_route_class_before_update": admin_readback["admin_route_class_before_update"],
        "admin_route_class_after_save": admin_readback["admin_route_class_after_save"],
        "admin_route_class_after_fresh_get": admin_readback["admin_route_class_after_fresh_get"],
        "customer_detail_route_class": customer_route_class,
        "admin_origin_matches": admin_readback["admin_origin_matches"],
        "admin_folder_matches": admin_readback["admin_folder_matches"],
        "admin_order_id_matches": admin_readback["admin_order_id_matches"],
        "admin_post_save_order_id_matches": admin_readback["admin_post_save_order_id_matches"],
        "admin_fresh_get_order_id_matches": admin_readback["admin_fresh_get_order_id_matches"],
        "admin_fresh_get_method_get": admin_readback["admin_fresh_get_method_get"],
        "customer_origin_matches": True,
        "customer_order_id_matches": True,
        "admin_and_customer_order_ids_match": int(order["order_id"]) == int(admin_readback["order_id"]),
        "admin_and_customer_tracking_number_matches": True,
        "admin_order_state_id_before": admin_readback["admin_order_state_id_before"],
        "admin_order_state_id_after": admin_readback["admin_order_state_id_after"],
        "admin_order_state_preserved": admin_readback["admin_order_state_preserved"],
        "admin_order_total": admin_readback["admin_order_total"],
        "admin_shipping_total": admin_readback["admin_shipping_total"],
        "admin_fresh_document_readback": True,
        "customer_same_order_detail_readback": True,
        "order_state_id": int(verified["order_state_id"]),
        "order_state_paid": False,
        "unpaid_status_preserved": True,
        "payment_module": "ps_checkpayment",
        "total_paid_real": 0,
        "shipping_total": 0,
        "free_shipping_preserved": True,
        "physical_dispatch_performed": False,
        "carrier_scan_performed": False,
    }
    (QA_DIR / "shipping-free-order-tracking-verified.json").write_text(
        json.dumps(result, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def run_free_carrier_admin_order_view() -> None:
    validate_isolated_ci_compose_project()
    validate_loopback_admin_targets()
    order_paths = (
        ("tokyo", ORDER_PATH),
        ("osaka", QA_DIR / "shipping-free-mobile-order.json"),
        ("taxable", QA_DIR / "shipping-free-taxable-order.json"),
        ("exemption", QA_DIR / "shipping-free-exemption-order.json"),
    )
    driver = checkout.webdriver.Chrome(options=checkout.browser_options(1440, 960))
    stage = "separate_administrator_login"
    tracking_target: tuple[str, dict[str, object], dict[str, object], dict[str, int]] | None = None
    tracking_diagnostics: dict[str, object] = {
        "browser_context": "admin",
        "substage": "not_started",
        "_active_driver": driver,
    }
    try:
        checkout.admin_login(driver)
        for order_kind, order_path in order_paths:
            stage = f"open_{order_kind}_admin_order"
            if not order_path.is_file():
                raise AssertionError(f"{order_kind} browser order artifact is missing")
            order = json.loads(order_path.read_text(encoding="utf-8"))
            browser_totals = order["browser_totals"]
            detail_url = checkout.find_admin_detail_url(driver, order)
            parsed = urlparse(detail_url)
            if parsed.hostname not in {"localhost", "127.0.0.1"} or not parsed.path.startswith("/admin-kuranea/"):
                raise AssertionError("the order detail resolved outside the isolated admin folder")
            checkout.visit(driver, detail_url)
            WebDriverWait(driver, 30).until(
                lambda browser: order["reference"] in browser.find_element(By.TAG_NAME, "body").text
            )

            stage = f"reconcile_{order_kind}_admin_order_totals"
            verified_path = QA_DIR / f"shipping-free-{order_kind}-verified.json"
            if not verified_path.is_file():
                raise AssertionError(f"{order_kind} native order verification artifact is missing")
            verified = json.loads(verified_path.read_text(encoding="utf-8"))
            expected = _expected_admin_order_totals(order, verified)
            selectors = {
                "products": "#orderProductsTotal",
                "shipping": "#orderShippingTotal",
                "tax": "#orderTaxesTotal",
                "total": "#orderTotal",
            }
            actual = {}
            for key, selector in selectors.items():
                if key == "shipping":
                    shipping_element = _wait_present(driver, selector)
                    shipping_text = shipping_element.text.strip()
                    if not shipping_text:
                        shipping_text = (shipping_element.get_attribute("textContent") or "").strip()
                    shown_shipping = _parse_yen(shipping_text) if shipping_text else None
                    actual[key] = _reconcile_admin_shipping_total(
                        shown_shipping,
                        int(browser_totals["shipping_tax_incl"]),
                        verified,
                    )
                    continue
                if key == "tax" and order.get("tax_status") == "explicit_exemption_test":
                    tax_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    tax_values = [
                        _parse_yen(text)
                        for element in tax_elements
                        if element.is_displayed() and (text := element.text.strip())
                    ]
                    if any(value != 0 for value in tax_values):
                        raise AssertionError("the Back Office displayed positive tax for the explicit zero-rate fixture")
                    continue
                if key not in expected:
                    tax_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    _assert_unknown_admin_tax_display(
                        [
                            _parse_yen(text)
                            for element in tax_elements
                            if element.is_displayed() and (text := element.text.strip())
                        ]
                    )
                    continue
                actual[key] = _parse_order_amount(driver, selector)
            expected_display_totals = dict(expected)
            if order.get("tax_status") == "explicit_exemption_test":
                expected_display_totals.pop("tax", None)
            if actual != expected_display_totals:
                raise AssertionError(
                    f"{order_kind} Back Office totals {actual} differ from customer checkout {expected_display_totals}"
                )

            stage = f"verify_{order_kind}_admin_carrier_line"
            shipping_tab = _wait_visible(driver, "#orderShippingTab")
            checkout.click_at_center(driver, shipping_tab)
            carrier_name = _wait_visible(driver, "#shipping-grid-table .carrier-name").text.strip()
            carrier_price = _parse_yen(_wait_visible(driver, "#shipping-grid-table .carrier-price").text)
            if carrier_name != order["carrier_name"] or carrier_price != 0:
                raise AssertionError(
                    f"{order_kind} Back Office carrier line is not ¥0: {carrier_name!r}, ¥{carrier_price}"
                )
            driver.save_screenshot(str(QA_DIR / f"shipping-free-order-admin-{order_kind}-desktop.png"))
            if order_kind == "tokyo":
                tracking_target = (detail_url, order, verified, expected)

        if tracking_target is None:
            raise AssertionError("the matching Tokyo CI order was not available for tracking acceptance")
        stage = "verify_tracking_order"
        tracking_detail_url, tracking_order, tracking_verified, tracking_expected = tracking_target
        _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_target_route', driver)
        if not _matches_isolated_admin_order_detail_url(
            tracking_detail_url,
            int(tracking_order.get("order_id", 0)),
        ):
            raise AssertionError("the Tokyo tracking target is not a matching route inside the configured admin origin")
        _set_tracking_diagnostic(tracking_diagnostics, 'admin', 'admin_target_document_wait', driver)
        checkout.visit(driver, tracking_detail_url)
        WebDriverWait(driver, 30).until(
            lambda browser: tracking_order["reference"] in browser.find_element(By.TAG_NAME, "body").text
        )
        tracking_result = _verify_synthetic_order_tracking(
            driver,
            tracking_order,
            tracking_verified,
            tracking_expected,
            tracking_diagnostics,
        )

        driver.set_window_size(390, 844)
        driver.save_screenshot(str(QA_DIR / "shipping-free-order-admin-mobile.png"))
        print(
            "PASS: separate admin login reconciled Tokyo, Osaka, taxable, and explicit exemption orders with ¥0 shipping; "
            "the same unpaid Tokyo order saved and reread its synthetic tracking number in AdminOrders and customer order detail; "
            f"tracking_result={tracking_result['admin_fresh_document_readback'] and tracking_result['customer_same_order_detail_readback']}, "
            "no physical dispatch or carrier scan was performed."
        )
    except Exception as error:
        if tracking_diagnostics.get('browser_context') != 'customer':
            try:
                driver.save_screenshot(str(QA_DIR / "shipping-free-order-admin-failure.png"))
            except Exception:
                pass
        _emit_failure(stage, error, driver, tracking_diagnostics=tracking_diagnostics)
        raise SystemExit(f"free-carrier admin order browser failed at {stage}") from None
    finally:
        driver.quit()


def _carrier_readback_failure_facts(driver, expected: dict[str, object]) -> dict[str, object]:
    """Read only fixed route, readiness, and form indicators; never serialize page values."""
    facts: dict[str, object] = {
        "route_class": "unknown", "ready_state": "unknown", "tab": "unknown",
        "same_positive_carrier_id": False,
    }
    try:
        current = urlparse(driver.current_url)
        admin = urlparse(ADMIN_LOGIN)
        admin_path = admin.path.rstrip("/")
        if (current.scheme, current.netloc) != (admin.scheme, admin.netloc):
            facts["route_class"] = "origin_mismatch"
        elif not current.path.startswith(admin_path + "/"):
            facts["route_class"] = "outside_admin"
        elif carrier_id_from_edit_url(driver.current_url, admin_path) is not None:
            facts["route_class"] = "carrier_edit"
            observed_id = carrier_id_from_edit_url(driver.current_url, admin_path)
            expected_id = expected.get("expected_id")
            facts["same_positive_carrier_id"] = (
                type(expected_id) is int and expected_id > 0 and observed_id == expected_id
            )
        else:
            facts["route_class"] = "other_admin_route"
    except Exception:
        pass
    try:
        ready_state = driver.execute_script("return document.readyState")
        if ready_state in ("loading", "interactive", "complete"):
            facts["ready_state"] = ready_state
    except Exception:
        pass
    for key, selector in (
        ("name_field", 'input[name="carrier[general_settings][name]"]'),
        ("shipping_tab", 'a[href="#carrier_shipping_settings-tab"]'),
        ("free_toggle", 'input[name="carrier[shipping_settings][is_free]"]'),
        ("zone_control", "#carrier_shipping_settings_zones"),
    ):
        state = {"read": False, "exists": False, "visible": False, "multiple": False}
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            state.update(read=True, exists=bool(elements), multiple=len(elements) > 1)
            state["visible"] = any(element.is_displayed() for element in elements)
        except Exception:
            state["read"] = False
        facts[key] = state
    try:
        active_tabs = [
            name for name in ("general", "shipping")
            if driver.find_elements(By.CSS_SELECTOR, f"#carrier_{name}_settings-tab.active")
        ]
        facts["tab"] = active_tabs[0] if len(active_tabs) == 1 else "other"
    except Exception:
        pass
    for key in ("name_readback", "active_readback", "free_readback", "japan_zone_readback"):
        state = {"read": False, "matches_expected": False}
        try:
            if key == "name_readback":
                names = driver.find_elements(By.CSS_SELECTOR, 'input[name="carrier[general_settings][name]"]')
                matches = bool(names) and names[0].get_attribute("value") == expected.get("expected_name")
            elif key == "japan_zone_readback":
                zones = driver.find_elements(By.CSS_SELECTOR, "#carrier_shipping_settings_zones")
                matches = bool(zones) and [
                    option.get_attribute("value")
                    for option in zones[0].find_elements(By.TAG_NAME, "option") if option.is_selected()
                ] == [str(JAPAN_ZONE_ID)]
            else:
                field = (
                    "carrier[general_settings][active]" if key == "active_readback"
                    else "carrier[shipping_settings][is_free]"
                )
                matches = _switch_is_selected(driver, field, True)
            state.update(read=True, matches_expected=bool(matches))
        except Exception:
            pass
        facts[key] = state
    return facts


def _emit_failure(
    stage: str,
    error: Exception,
    driver=None,
    checkout_registration_state: dict[str, object] | None = None,
    tracking_diagnostics: dict[str, object] | None = None,
    carrier_diagnostics: dict[str, object] | None = None,
) -> None:
    exception_type = type(error).__name__
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", exception_type):
        exception_type = "Exception"
    safe_stage = stage if re.fullmatch(r"[a-z][a-z0-9_.]*", stage) else "unknown"
    safe_path = "unknown"
    if driver is not None:
        try:
            page_path = urlparse(driver.current_url).path
            if re.fullmatch(r"/[A-Za-z0-9._/-]*", page_path):
                safe_path = page_path[:240]
        except Exception:
            pass
    safe_detail = ""
    if isinstance(error, AssertionError):
        detail = " ".join(str(error).split())
        detail = re.sub(r"(?i)\btoken\s*[=:]\s*[^\s,;&]+", "token=[REDACTED]", detail)
        safe_detail = detail[:600]
    detail_suffix = f"; detail={safe_detail}" if safe_detail else ""
    registration_suffix = ""
    route_suffix = f"; path={safe_path}"
    if checkout_registration_state is not None:
        safe_state = checkout.sanitize_checkout_registration_state(checkout_registration_state)
        registration_suffix = "; checkout_state=" + json.dumps(
            safe_state,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        # The registration state already contains the bounded checkout indicators;
        # omit the route path and free-form assertion detail from this annotation.
        route_suffix = ""
        detail_suffix = ""
    tracking_suffix = ""
    if tracking_diagnostics is not None:
        browser_context = tracking_diagnostics.get('browser_context')
        if type(browser_context) is not str or browser_context not in TRACKING_BROWSER_CONTEXTS:
            browser_context = 'unknown'
        tracking_substage = tracking_diagnostics.get('substage')
        if type(tracking_substage) is not str or tracking_substage not in TRACKING_SUBSTAGES:
            tracking_substage = 'unknown'
        active_driver = tracking_diagnostics.get('_active_driver')
        active_path = _safe_tracking_pathname(active_driver) if active_driver is not None else 'unknown'
        stored_path = tracking_diagnostics.get('safe_pathname')
        if active_path != 'unknown':
            safe_path = active_path
        elif type(stored_path) is str and re.fullmatch(r"/[A-Za-z0-9._/-]*", stored_path):
            safe_path = stored_path
        else:
            safe_path = 'unknown'
        route_suffix = f"; path={safe_path}"
        tracking_suffix = f"; browser_context={browser_context}; tracking_substage={tracking_substage}"
        if tracking_substage in {"admin_post_save_document_wait", "admin_fresh_get_document_wait"}:
            predicate = tracking_diagnostics.get('document_wait_predicate')
            if isinstance(predicate, dict):
                attempt_count = predicate.get('attempt_count')
                if type(attempt_count) is not int or attempt_count < 0:
                    attempt_count = 0
                route_class = predicate.get('route_class')
                if type(route_class) is not str or route_class not in ADMIN_DOCUMENT_WAIT_ROUTE_CLASSES:
                    route_class = 'unknown'
                body_text_read = predicate.get('body_text_read')
                if type(body_text_read) is not str or body_text_read not in ADMIN_DOCUMENT_WAIT_BODY_STATES:
                    body_text_read = 'not_read'
                safe_predicate = {
                    'attempt_count': min(attempt_count, 9999),
                    'body_reference_matches': predicate.get('body_reference_matches') is True,
                    'body_text_read': body_text_read,
                    'route_class': route_class,
                    'stale_seen': predicate.get('stale_seen') is True,
                }
                tracking_suffix += '; document_wait=' + json.dumps(
                    safe_predicate, sort_keys=True, separators=(',', ':')
                )
        # Tracking-stage diagnostics are enums; avoid free-form exception details.
        detail_suffix = ""
    if carrier_diagnostics is not None:
        substage = stage.removeprefix("verify_admin_saved_carrier.")
        safe_stage = "verify_admin_saved_carrier." + (
            substage if substage in CARRIER_READBACK_SUBSTAGES else "unknown"
        )
        if exception_type not in {
            "TimeoutException", "AssertionError", "StaleElementReferenceException", "WebDriverException",
        }:
            exception_type = "Exception"
        route_suffix = "; carrier_state=" + json.dumps(
            _carrier_readback_failure_facts(driver, carrier_diagnostics), sort_keys=True, separators=(",", ":")
        )
        detail_suffix = ""
    print(
        f"FAIL: free shipping browser QA at {safe_stage} ({exception_type}){route_suffix}{detail_suffix}{registration_suffix}{tracking_suffix}",
        file=sys.stderr,
    )
    print(
        f"::error title=ORDENOWA free shipping QA::{safe_stage} ({exception_type}){route_suffix}{detail_suffix}{registration_suffix}{tracking_suffix}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    modes = {
        "configure": configure_free_carrier,
        "readback": readback_free_carrier,
        "customer": run_japan_customer_checkout,
        "osaka-mobile": run_japan_mobile_osaka_checkout,
        "taxable-customer": run_japan_taxable_customer_checkout,
        "explicit-exemption-customer": run_japan_explicit_exemption_customer_checkout,
        "admin": run_free_carrier_admin_order_view,
    }
    if len(sys.argv) != 2 or sys.argv[1] not in modes:
        raise SystemExit(
            "Usage: verify_ci_free_shipping_browser.py configure|readback|customer|osaka-mobile|taxable-customer|explicit-exemption-customer|admin"
        )
    modes[sys.argv[1]]()
