#!/usr/bin/env python3
"""Exercise Hummingbird product variants and cart controls in isolated Chromium."""

from __future__ import annotations

import json
import ipaddress
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait


BASE = os.environ["SHOP_BASE_URL"].rstrip("/")
PRODUCT_ID = int(os.environ["CI_TEST_PRODUCT_ID"])
EXPECTED_GROSS_PRICE_JPY = 550
DEST = Path(os.environ["QA_ARTIFACT_DIR"])
DEST.mkdir(parents=True, exist_ok=True)
EXPECTED_SHOP_PORT = 18080

if PRODUCT_ID < 1:
    raise SystemExit("CI_TEST_PRODUCT_ID must be a positive isolated test product ID")


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
        raise ValueError("cart-controls QA requires its exact isolated GitHub Actions Compose project")


def validate_loopback_shop() -> None:
    try:
        parsed = urlparse(BASE)
        host = (parsed.hostname or "").casefold()
        port = parsed.port
    except ValueError:
        raise ValueError("SHOP_BASE_URL must be a valid isolated loopback URL") from None
    try:
        is_loopback = bool(host) and ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = host == "localhost"
    if (
        parsed.scheme != "http"
        or not is_loopback
        or port != EXPECTED_SHOP_PORT
        or parsed.path not in {"", "/"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"SHOP_BASE_URL must use the isolated loopback shop on port {EXPECTED_SHOP_PORT}")


def visible(driver: webdriver.Chrome, selector: str, timeout: int = 30):
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
    )


def parse_yen(raw_value: str) -> int:
    tokens = re.findall(r"\d[\d,]*(?:\.\d+)?", raw_value.replace("\u00a0", " "))
    if not tokens:
        raise AssertionError(f"could not read JPY from visible price {raw_value!r}")
    amount = float(tokens[0].replace(",", ""))
    if amount != int(amount):
        raise AssertionError(f"JPY price unexpectedly contains fractional yen: {raw_value!r}")
    return int(amount)


def visit(driver: webdriver.Chrome, path: str) -> None:
    driver.get(BASE + path)
    WebDriverWait(driver, 40).until(
        lambda browser: browser.execute_script("return document.readyState") == "complete"
    )


def product_url() -> str:
    return BASE + "/index.php?" + urlencode(
        {"controller": "product", "id_product": PRODUCT_ID}
    )


def radio_option_label(driver: webdriver.Chrome, label) -> str:
    return str(
        driver.execute_script(
            """
            const clone = arguments[0].cloneNode(true);
            clone.querySelectorAll('.visually-hidden').forEach((node) => node.remove());
            return clone.textContent.trim();
            """,
            label,
        )
    )


def current_product_attribute_id(driver: webdriver.Chrome) -> int | None:
    fields = driver.find_elements(
        By.CSS_SELECTOR, '#add-to-cart-or-refresh input[name="id_product_attribute"]'
    )
    if not fields:
        return None
    value = fields[0].get_attribute("value") or ""
    return int(value) if value.isascii() and value.isdigit() and int(value) > 0 else None


def select_variant_when_available(driver: webdriver.Chrome) -> dict[str, object]:
    """Select the fixture's non-default Color value and verify native combination selection."""
    fieldsets = driver.find_elements(By.CSS_SELECTOR, "fieldset.product-variant")
    if len(fieldsets) != 1:
        raise AssertionError("the CI variant fixture must expose exactly one native option group")

    legend = fieldsets[0].find_element(By.CSS_SELECTOR, "legend").text.strip()
    if legend != "Color":
        raise AssertionError("the isolated browser fixture must expose its Color option group")

    requested_label = ""
    before_attribute_id = current_product_attribute_id(driver)
    for fieldset in fieldsets:
        selects = fieldset.find_elements(By.CSS_SELECTOR, 'select[name^="group["]')
        if selects:
            select = Select(selects[0])
            current_option = select.first_selected_option
            current = current_option.get_attribute("value")
            if current_option.text.strip() != "Blue":
                raise AssertionError("the CI variant fixture must default to the Blue native combination")
            available = {
                option.text.strip()
                for option in select.options
                if option.is_enabled() and option.get_attribute("value")
            }
            if available != {"Blue", "Red"}:
                raise AssertionError("the CI Color option group must offer exactly Blue and Red")
            alternative = next(
                (
                    option
                    for option in select.options
                    if option.is_enabled()
                    and option.get_attribute("value")
                    and option.get_attribute("value") != current
                    and option.text.strip() == "Red"
                ),
                None,
            )
            if alternative is not None:
                requested_label = alternative.text.strip()
                select.select_by_value(alternative.get_attribute("value"))
                break

        radios = fieldset.find_elements(
            By.CSS_SELECTOR, 'input[type="radio"][name^="group["]'
        )
        radio_labels: dict[str, object] = {}
        for radio in radios:
            radio_id = radio.get_attribute("id")
            labels = (
                driver.find_elements(By.CSS_SELECTOR, f'label[for="{radio_id}"]')
                if radio_id
                else []
            )
            label = (
                radio_option_label(driver, labels[0])
                if labels
                else (radio.get_attribute("value") or "")
            )
            radio_labels[label] = (radio, labels[0] if labels else radio)
        if radio_labels and set(radio_labels) != {"Blue", "Red"}:
            raise AssertionError("the CI Color option group must offer exactly Blue and Red")
        selected_radio_labels = [
            label for label, (radio, _) in radio_labels.items() if radio.is_selected()
        ]
        if radios and selected_radio_labels != ["Blue"]:
            raise AssertionError("the CI variant fixture must default to the Blue native combination")
        alternative_radio = next(
            (
                radio for label, (radio, _) in radio_labels.items()
                if label == "Red" and radio.is_enabled() and not radio.is_selected()
            ),
            None,
        )
        if alternative_radio is not None:
            requested_label = "Red"
            option_label = radio_labels[requested_label][1]
            driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});",
                alternative_radio,
            )
            option_label.click()
            break

    if not requested_label:
        raise AssertionError("the CI Color fixture must have a selectable non-default value")

    def selected_state(browser: webdriver.Chrome) -> tuple[list[tuple[str, str]], int] | bool:
        selected: list[tuple[str, str]] = []
        for group in browser.find_elements(By.CSS_SELECTOR, "fieldset.product-variant"):
            group_name = " ".join(
                item.text.strip()
                for item in group.find_elements(By.CSS_SELECTOR, "legend")
                if item.text.strip()
            )
            select_fields = group.find_elements(By.CSS_SELECTOR, 'select[name^="group["]')
            if select_fields:
                option = Select(select_fields[0]).first_selected_option
                value = option.text.strip()
                if value:
                    selected.append((group_name, value))
                continue

            for radio in group.find_elements(
                By.CSS_SELECTOR, 'input[type="radio"][name^="group["]'
            ):
                if not radio.is_selected():
                    continue
                radio_id = radio.get_attribute("id")
                labels = browser.find_elements(By.CSS_SELECTOR, f'label[for="{radio_id}"]') if radio_id else []
                value = (
                    radio_option_label(browser, labels[0])
                    if labels
                    else (radio.get_attribute("value") or "")
                )
                if value:
                    selected.append((group_name, value))
                break
        attribute_id = current_product_attribute_id(browser)
        if not selected or attribute_id is None or (before_attribute_id is not None and attribute_id == before_attribute_id):
            return False
        return selected, attribute_id

    selected, attribute_id = WebDriverWait(driver, 20, poll_frequency=0.2).until(selected_state)
    if requested_label != "Red" or not any(value == requested_label for _, value in selected):
        raise AssertionError("the selected product option did not remain selected in the browser")

    return {
        "variant_status": "selected",
        "selected_labels": [value for _, value in selected],
        "product_attribute_id": attribute_id,
    }


def visible_product_line(driver: webdriver.Chrome, expected_attribute_id: int | None = None):
    for row in driver.find_elements(By.CSS_SELECTOR, ".cart__item"):
        remove_links = row.find_elements(
            By.CSS_SELECTOR, '[data-link-action="delete-from-cart"][data-id-product]'
        )
        if not remove_links or remove_links[0].get_attribute("data-id-product") != str(PRODUCT_ID):
            continue
        if expected_attribute_id is not None:
            actual_attribute_id = remove_links[0].get_attribute("data-id-product-attribute")
            if actual_attribute_id != str(expected_attribute_id):
                continue
        return row
    return False


def assert_cart_has_only_test_product(
    driver: webdriver.Chrome,
    expected_quantity: str,
    expected_attribute_id: int | None,
    selected_labels: list[str],
) -> None:
    def exact_line(browser: webdriver.Chrome):
        rows = browser.find_elements(By.CSS_SELECTOR, ".cart__item")
        row = visible_product_line(browser, expected_attribute_id)
        if not row or len(rows) != 1:
            return False
        qty_fields = row.find_elements(By.CSS_SELECTOR, ".js-cart-line-product-quantity")
        if not qty_fields or qty_fields[0].get_attribute("value") != expected_quantity:
            return False
        cart_attribute_values = [
            value.text.strip()
            for value in row.find_elements(By.CSS_SELECTOR, ".product-line__item-value")
            if value.text.strip()
        ]
        if any(label not in cart_attribute_values for label in selected_labels):
            return False
        unit_price_fields = row.find_elements(By.CSS_SELECTOR, ".product-line__item-price")
        line_total_fields = row.find_elements(By.CSS_SELECTOR, ".product-line__price")
        if not unit_price_fields or not line_total_fields:
            return False
        expected_line_total = EXPECTED_GROSS_PRICE_JPY * int(expected_quantity)
        if parse_yen(unit_price_fields[0].text) != EXPECTED_GROSS_PRICE_JPY:
            raise AssertionError("cart line does not display the tax-inclusive JPY 550 unit price")
        if parse_yen(line_total_fields[0].text) != expected_line_total:
            raise AssertionError("cart line total does not match the displayed tax-inclusive unit price and quantity")
        subtotal_fields = browser.find_elements(By.CSS_SELECTOR, "#cart-subtotal-products .cart-summary__value")
        if not subtotal_fields or parse_yen(subtotal_fields[0].text) != expected_line_total:
            raise AssertionError("cart product subtotal does not match its tax-inclusive unit price and quantity")
        return row

    WebDriverWait(
        driver,
        30,
        poll_frequency=0.2,
        ignored_exceptions=(StaleElementReferenceException,),
    ).until(exact_line)


def add_product_from_detail(
    driver: webdriver.Chrome,
    label: str,
    attempt: str,
) -> dict[str, object]:
    visit(driver, product_url())
    WebDriverWait(driver, 25).until(
        lambda browser: "[CI ONLY]" in browser.find_element(By.TAG_NAME, "body").text
    )
    variant_result = select_variant_when_available(driver)
    detail_price = parse_yen(visible(driver, ".product__price").text)
    if detail_price != EXPECTED_GROSS_PRICE_JPY:
        raise AssertionError(
            "product detail must show the fixture's tax-inclusive JPY 550 sale price; "
            f"visible price was JPY {detail_price}"
        )
    if variant_result["variant_status"] == "selected":
        driver.save_screenshot(
            str(DEST / f"cart-controls-{label}-{attempt}-variant-selected.png")
        )
    button = WebDriverWait(driver, 20).until(
        lambda browser: next(
            (
                item
                for item in browser.find_elements(
                    By.CSS_SELECTOR, 'button[data-ps-ref="add-to-cart"]'
                )
                if item.is_displayed() and item.is_enabled()
            ),
            False,
        ),
        message="the isolated CI test product has no active add-to-cart button",
    )
    button.click()
    modal = WebDriverWait(driver, 25).until(
        lambda browser: next(
            (
                item
                for item in browser.find_elements(By.CSS_SELECTOR, '[data-ps-ref="blockcart-modal"]')
                if item.is_displayed() and "[CI ONLY]" in item.text
            ),
            False,
        ),
        message="adding the isolated CI test product did not show the cart confirmation",
    )
    continue_shopping = modal.find_element(
        By.CSS_SELECTOR, 'button[data-bs-dismiss="modal"]'
    )
    continue_shopping.click()
    WebDriverWait(driver, 15).until(
        lambda browser: not any(
            item.is_displayed()
            for item in browser.find_elements(By.CSS_SELECTOR, '[data-ps-ref="blockcart-modal"]')
        ),
        message="the cart confirmation did not close after continuing shopping",
    )
    visit(driver, "/index.php?controller=cart&action=show")
    WebDriverWait(driver, 30).until(
        lambda browser: bool(visible_product_line(browser, variant_result["product_attribute_id"]))
    )
    return variant_result


def wait_for_empty_cart(driver: webdriver.Chrome) -> bool:
    def empty(browser: webdriver.Chrome) -> bool:
        if browser.find_elements(By.CSS_SELECTOR, ".cart__item"):
            return False
        return bool(browser.find_elements(By.CSS_SELECTOR, ".cart__empty"))

    return bool(
        WebDriverWait(driver, 30, poll_frequency=0.2).until(
            empty, message="removing the test item did not leave the cart empty"
        )
    )


def run_viewport(width: int, height: int, label: str) -> dict[str, object]:
    validate_isolated_ci_compose_project()
    validate_loopback_shop()
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--lang=ja-JP")
    driver: webdriver.Chrome | None = None
    stage = "chromium_startup"
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_window_size(width, height)
        stage = "initial_empty_cart"
        visit(driver, "/index.php?controller=cart&action=show")
        if driver.find_elements(By.CSS_SELECTOR, ".cart__item"):
            raise AssertionError("new isolated Chromium session unexpectedly has cart items")

        stage = "product_add"
        variant = add_product_from_detail(driver, label, "initial")
        if variant["variant_status"] != "selected" or not variant["product_attribute_id"]:
            raise AssertionError("the isolated variant fixture did not select a native product combination")
        selected_labels = list(variant["selected_labels"])
        attribute_id = variant["product_attribute_id"]
        assert_cart_has_only_test_product(driver, "1", attribute_id, selected_labels)
        driver.save_screenshot(str(DEST / f"cart-controls-{label}-initial.png"))

        stage = "cart_quantity_update"
        quantity = visible(driver, ".cart__item .js-cart-line-product-quantity")
        if quantity.get_attribute("value") != "1":
            raise AssertionError("newly added CI product did not start at quantity one")
        increment = visible(driver, ".cart__item .js-increment-button")
        increment.click()
        def quantity_updated(browser: webdriver.Chrome) -> bool:
            fields = browser.find_elements(
                By.CSS_SELECTOR, ".cart__item .js-cart-line-product-quantity"
            )
            return bool(fields and fields[0].get_attribute("value") == "2")

        WebDriverWait(
            driver,
            30,
            poll_frequency=0.2,
            ignored_exceptions=(StaleElementReferenceException,),
        ).until(
            quantity_updated,
            message="cart quantity did not update to two after using the increment control",
        )
        assert_cart_has_only_test_product(driver, "2", attribute_id, selected_labels)
        driver.save_screenshot(str(DEST / f"cart-controls-{label}-quantity-updated.png"))

        stage = "cart_line_removal"
        remove_link = visible(
            driver,
            '.cart__item [data-link-action="delete-from-cart"][data-id-product]',
        )
        if remove_link.get_attribute("data-id-product") != str(PRODUCT_ID):
            raise AssertionError("cart removal control does not belong to the isolated CI product")
        remove_link.click()
        wait_for_empty_cart(driver)
        driver.save_screenshot(str(DEST / f"cart-controls-{label}-empty.png"))

        stage = "cart_readd"
        readded_variant = add_product_from_detail(driver, label, "readded")
        if readded_variant["variant_status"] != "selected" or not readded_variant["product_attribute_id"]:
            raise AssertionError("re-adding the isolated variant fixture did not select a native combination")
        readded_labels = list(readded_variant["selected_labels"])
        readded_attribute_id = readded_variant["product_attribute_id"]
        assert_cart_has_only_test_product(driver, "1", readded_attribute_id, readded_labels)
        driver.save_screenshot(str(DEST / f"cart-controls-{label}-readded.png"))
        if variant["variant_status"] != readded_variant["variant_status"]:
            raise AssertionError("product variant support changed between cart add attempts")
        if variant["selected_labels"] != readded_variant["selected_labels"]:
            raise AssertionError("re-adding the product selected a different variant")

        overflow = driver.execute_script(
            "return document.documentElement.scrollWidth > window.innerWidth + 2"
        )
        if overflow:
            raise AssertionError(f"horizontal overflow at {width}px cart viewport")

        result = {
            "viewport": label,
            "product_id": PRODUCT_ID,
            "variant_status": variant["variant_status"],
            "selected_variant_labels": selected_labels,
            "product_attribute_id": attribute_id,
            "quantity_after_update": 2,
            "removed_to_empty_cart": True,
            "quantity_after_readd": 1,
        }
        (DEST / f"cart-controls-{label}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"PASS: {label} Chromium cart quantity update, removal and re-add; "
            f"variant QA={variant['variant_status']}"
        )
        return result
    except Exception as error:
        if driver is not None:
            try:
                driver.save_screenshot(str(DEST / f"cart-controls-{label}-failure.png"))
            except Exception:
                pass
        safe_stage = stage if re.fullmatch(r"[a-z][a-z0-9_]*", stage) else "unknown"
        exception_type = type(error).__name__
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", exception_type):
            exception_type = "Exception"
        print(
            f"FAIL: {label} cart controls at {safe_stage} ({exception_type})",
            file=sys.stderr,
        )
        print(
            f"::error title=ORDENOWA cart controls::{label} failed at {safe_stage} ({exception_type})",
            file=sys.stderr,
        )
        raise
    finally:
        if driver is not None:
            driver.quit()


def main() -> None:
    failures: list[str] = []
    for width, height, label in ((1440, 960, "desktop"), (390, 844, "mobile")):
        try:
            run_viewport(width, height, label)
        except Exception:
            failures.append(label)
    if failures:
        raise SystemExit("cart controls browser QA failed for: " + ", ".join(failures))


if __name__ == "__main__":
    main()
