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
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

import verify_ci_checkout_admin_browser as checkout
from checkout_total_math import reconcile_cart_totals
from shipping_admin_routes import carrier_action_url, matches_admin_controller_url


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


def _fill_free_carrier_form(
    driver,
    name: str,
    stage_callback: Callable[[str], None] | None = None,
) -> None:
    mark_stage = stage_callback or (lambda _stage: None)
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
    shipping_tab = _wait_visible(
        driver,
        'a[href="#carrier_shipping_settings-tab"]',
    )
    checkout.click_at_center(driver, shipping_tab)

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


def _assert_free_carrier_form(driver, carrier: dict[str, object]) -> dict[str, object]:
    name = _wait_visible(driver, 'input[name="carrier[general_settings][name]"]')
    if name.get_attribute("value") != carrier["name"]:
        raise AssertionError("the saved free carrier name did not persist")

    if not _switch_is_selected(driver, "carrier[general_settings][active]", True):
        raise AssertionError("the saved Japan free carrier is not active")
    if not _switch_is_selected(driver, "carrier[shipping_settings][is_free]", True):
        raise AssertionError("the saved carrier is not marked as free shipping in AdminCarriers")

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
    checkout.click_at_center(driver, save_button)

    WebDriverWait(driver, 35).until(
        lambda browser: re.search(
            r"/index\.php/improve/shipping/carriers/([0-9]+)/edit(?:[/?#]|$)", browser.current_url
        ) is not None
        or bool(browser.find_elements(By.CSS_SELECTOR, ".alert-danger, .alert-error, [role='alert']"))
    )
    match = re.search(
        r"/index\.php/improve/shipping/carriers/([0-9]+)/edit(?:[/?#]|$)",
        driver.current_url,
    )
    if match is None:
        errors = [
            element.text.strip()[:300]
            for element in driver.find_elements(By.CSS_SELECTOR, ".alert-danger, .alert-error, [role='alert']")
            if element.is_displayed() and element.text.strip()
        ]
        raise AssertionError(f"AdminCarriers did not save the free carrier during {operation}: {errors[:3]}")
    return int(match.group(1))


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

        stage = "edit_and_save_free_japan_carrier"
        checkout.visit(driver, _carrier_edit_url(carriers_list_url, carrier_id))
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
        checkout.visit(driver, _carrier_edit_url(carriers_list_url, carrier_id))
        observed = _assert_free_carrier_form(driver, {"name": final_name})
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
        _emit_failure(stage, error, driver)
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
        checkout.visit(driver, _carrier_edit_url(carriers_list_url, int(config["id"])))
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


def _add_quantity_and_open_checkout(driver, label: str, quantity_requested: int) -> int:
    checkout.search_for_product(driver, label)
    displayed_unit_price = _parse_yen(_visible_text(driver, ".product__price"))
    quantity = _wait_visible(driver, "#quantity_wanted")
    quantity.clear()
    quantity.send_keys(str(quantity_requested))
    if quantity.get_attribute("value") != str(quantity_requested):
        raise AssertionError("product detail did not accept the requested test quantity")

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
) -> dict[str, int]:
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

    total_amounts: list[int] = []
    tax_amounts: list[int] = []
    for label, value in lines:
        amount = _parse_yen(value)
        if _is_tax_summary_label(label):
            tax_amounts.append(amount)
        if _is_total_summary_label(label):
            total_amounts.append(amount)
    if not total_amounts:
        total_amounts.append(_parse_yen(lines[-1][1]))

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
    return reconcile_cart_totals(
        products_tax_incl=product_total,
        shipping_tax_incl=shipping_total,
        discounts_tax_incl=discount_total,
        tax=tax_total,
        total_tax_incl=total_incl,
        total_tax_excl=total_excl,
        pre_discount_tax=tax_total if pre_discount_tax_total is None else pre_discount_tax_total,
    )


def _find_free_carrier_option(driver, carrier: dict[str, object]):
    for item in driver.find_elements(By.CSS_SELECTOR, ".delivery-option__item"):
        if not item.is_displayed():
            continue
        names = item.find_elements(By.CSS_SELECTOR, ".delivery-option__carrier-name")
        if names and str(carrier["name"]) in names[0].text:
            return item
    return None


def _select_free_carrier_and_assert_zero(
    driver,
    carrier: dict[str, object],
    tax_rule_group_id: int | None = None,
    pre_discount_tax_total: int | None = None,
) -> dict[str, int]:
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


def _order_confirmation_totals(driver) -> dict[str, int]:
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
    total_amounts = [
        _parse_yen(value)
        for label, value in total_lines
        if _is_total_summary_label(label)
    ]
    if not total_amounts:
        raise AssertionError(
            "order confirmation did not display a recognizable final total; "
            f"visible labels were {[label for label, _value in total_lines]}"
        )

    return {
        "products_tax_incl": sum(product_totals),
        "shipping_tax_incl": _parse_yen(shipping_lines[0]),
        "tax": sum(tax_amounts),
        "total_tax_incl": total_amounts[-1],
    }


def _place_unpaid_order_and_verify_confirmation(
    driver,
    label: str,
    email: str,
    expected_totals: dict[str, int],
    screenshot_name: str,
) -> tuple[dict[str, object], dict[str, int]]:
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

    observed = _order_confirmation_totals(driver)
    expected = {
        "products_tax_incl": int(expected_totals["products_tax_incl"]),
        "shipping_tax_incl": 0,
        "tax": int(expected_totals["tax"]),
        "total_tax_incl": int(expected_totals["total_tax_incl"]),
    }
    if observed != expected:
        raise AssertionError(
            f"{label} order confirmation totals {observed} differ from verified checkout {expected}"
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
    checkout.wait_for_autocomplete_fields(driver, form)

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


def run_japan_customer_checkout() -> None:
    validate_isolated_ci_compose_project()
    validate_loopback_admin_targets()
    carrier = _read_config()
    driver = checkout.webdriver.Chrome(options=checkout.browser_options(1440, 960))
    stage = "product_search_and_quantity"
    try:
        unit_price = _add_quantity_and_open_checkout(driver, "shipping-free", 2)
        stage = "coupon_condition"
        coupon = _apply_coupon_if_configured(driver)
        if not coupon["applied"]:
            raise AssertionError(str(coupon["coupon_condition"]))
        stage = "customer_registration"
        email = checkout.register_checkout_account(driver, "shipping-free")
        stage = "japan_delivery_address"
        checkout.select_japan_address(driver, "shipping-free")

        stage = "japan_free_carrier_checkout"
        browser_totals = _select_free_carrier_and_assert_zero(driver, carrier)
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
        driver.save_screenshot(str(QA_DIR / "shipping-free-checkout-desktop.png"))
        driver.set_window_size(390, 844)
        mobile_totals = _cart_snapshot(driver)
        if mobile_totals != {
            key: browser_totals[key]
            for key in mobile_totals
        }:
            raise AssertionError("mobile checkout totals differ from the verified desktop totals")
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
                "CI fixture product with no assigned tax rule (id_tax_rules_group=0); "
                "no trustworthy Japan tax-inclusive fixture is configured in this fresh-install CI database"
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
        unit_price = _add_quantity_and_open_checkout(driver, "shipping-free-mobile", 1)
        stage = "mobile_customer_registration"
        email = checkout.register_checkout_account(driver, "shipping-free-mobile")
        stage = "supported_osaka_delivery_address"
        _select_osaka_address(driver)

        stage = "osaka_free_carrier_checkout"
        browser_totals = _select_free_carrier_and_assert_zero(driver, carrier)
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
            "tax_fixture_scope": "CI fixture product with no assigned tax rule (id_tax_rules_group=0)",
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
        unit_price = _add_quantity_and_open_checkout(driver, "shipping-free-taxable", 1)
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
        )
        expected_pre_coupon_totals = {
            "products_tax_incl": 1100,
            "products_tax_excl": 1000,
            "shipping_tax_incl": 0,
            "shipping_tax_excl": 0,
            "discounts_tax_incl": 0,
            "discounts_tax_excl": 0,
            "tax": 100,
            "total_tax_incl": 1100,
            "total_tax_excl": 1000,
        }
        if pre_coupon_totals != expected_pre_coupon_totals:
            raise AssertionError(
                "taxable checkout before the coupon did not reconcile to the CI-only included-tax fixture: "
                f"observed={pre_coupon_totals}, expected={expected_pre_coupon_totals}"
            )

        stage = "taxable_coupon_condition"
        coupon = _apply_coupon_if_configured(driver)
        if not coupon["applied"]:
            raise AssertionError(str(coupon["coupon_condition"]))

        stage = "taxable_discounted_free_carrier_checkout"
        browser_totals = _select_free_carrier_and_assert_zero(
            driver,
            carrier,
            tax_rule_group_id=PRODUCT_TAX_RULE_GROUP_ID,
            pre_discount_tax_total=pre_coupon_totals["tax"],
        )
        expected_totals = {
            "products_tax_incl": 1100,
            "products_tax_excl": 1000,
            "shipping_tax_incl": 0,
            "shipping_tax_excl": 0,
            "discounts_tax_incl": 550,
            "discounts_tax_excl": 500,
            "tax": 50,
            "total_tax_incl": 550,
            "total_tax_excl": 500,
        }
        if browser_totals != expected_totals:
            raise AssertionError(
                "taxable coupon checkout did not reconcile to the CI-only included-tax fixture: "
                f"observed={browser_totals}, expected={expected_totals}"
            )
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
            "PASS: Chromium reconciled the ¥1,100 tax-included product, ¥550 tax-inclusive run-scoped coupon, "
            "¥50 synthetic CI tax, ¥550 unpaid JPY order, and ¥0 Japan shipping."
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


def _parse_order_amount(driver, selector: str) -> int:
    return _parse_yen(_wait_present(driver, selector).text)


def run_free_carrier_admin_order_view() -> None:
    validate_isolated_ci_compose_project()
    validate_loopback_admin_targets()
    order_paths = (
        ("tokyo", ORDER_PATH),
        ("osaka", QA_DIR / "shipping-free-mobile-order.json"),
        ("taxable", QA_DIR / "shipping-free-taxable-order.json"),
    )
    driver = checkout.webdriver.Chrome(options=checkout.browser_options(1440, 960))
    stage = "separate_administrator_login"
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
            expected = {
                "products": int(browser_totals["products_tax_incl"]),
                "shipping": 0,
                "tax": int(browser_totals["tax"]),
                "total": int(browser_totals["total_tax_incl"]),
            }
            selectors = {
                "products": "#orderProductsTotal",
                "shipping": "#orderShippingTotal",
                "tax": "#orderTaxesTotal",
                "total": "#orderTotal",
            }
            actual = {key: _parse_order_amount(driver, selector) for key, selector in selectors.items()}
            if actual != expected:
                raise AssertionError(
                    f"{order_kind} Back Office totals {actual} differ from customer checkout {expected}"
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

        driver.set_window_size(390, 844)
        driver.save_screenshot(str(QA_DIR / "shipping-free-order-admin-mobile.png"))
        print(
            "PASS: separate admin login reconciled Tokyo, Osaka, and taxable orders, each with ¥0 shipping."
        )
    except Exception as error:
        try:
            driver.save_screenshot(str(QA_DIR / "shipping-free-order-admin-failure.png"))
        except Exception:
            pass
        _emit_failure(stage, error, driver)
        raise SystemExit(f"free-carrier admin order browser failed at {stage}") from None
    finally:
        driver.quit()


def _emit_failure(stage: str, error: Exception, driver=None) -> None:
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
    print(
        f"FAIL: free shipping browser QA at {safe_stage} ({exception_type}); path={safe_path}",
        file=sys.stderr,
    )
    print(
        f"::error title=ORDENOWA free shipping QA::{safe_stage} ({exception_type}); path={safe_path}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    modes = {
        "configure": configure_free_carrier,
        "readback": readback_free_carrier,
        "customer": run_japan_customer_checkout,
        "osaka-mobile": run_japan_mobile_osaka_checkout,
        "taxable-customer": run_japan_taxable_customer_checkout,
        "admin": run_free_carrier_admin_order_view,
    }
    if len(sys.argv) != 2 or sys.argv[1] not in modes:
        raise SystemExit(
            "Usage: verify_ci_free_shipping_browser.py configure|readback|customer|osaka-mobile|taxable-customer|admin"
        )
    modes[sys.argv[1]]()
