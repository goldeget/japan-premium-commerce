#!/usr/bin/env python3
"""Place CI-only ps_checkpayment orders without contacting a live payment provider."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait


BASE = os.environ["SHOP_BASE_URL"].rstrip("/")
ADMIN_LOGIN = os.environ["ADMIN_LOGIN_URL"].rstrip("/")
ADMIN_EMAIL = os.environ["ADMIN_MAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWD"]
PRODUCT_ID = int(os.environ["CI_TEST_PRODUCT_ID"])
RUN_ID = re.sub(r"[^0-9]", "", os.environ["GITHUB_RUN_ID"])
RUN_ATTEMPT = re.sub(r"[^0-9]", "", os.environ["GITHUB_RUN_ATTEMPT"])
DEST = Path(os.environ["QA_ARTIFACT_DIR"])
DEST.mkdir(parents=True, exist_ok=True)


def visible(driver: webdriver.Chrome, selector: str, timeout: int = 30):
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
    )


def visit(driver: webdriver.Chrome, url: str) -> None:
    driver.get(url)
    WebDriverWait(driver, 40).until(
        lambda browser: browser.execute_script("return document.readyState") == "complete"
    )


def fill(driver: webdriver.Chrome, selector: str, value: str, root=None) -> None:
    scope = root or driver
    element = WebDriverWait(driver, 30).until(
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


def click_at_center(driver: webdriver.Chrome, element) -> None:
    driver.execute_script(
        "arguments[0].scrollIntoView({behavior:'instant', block:'center', inline:'nearest'});",
        element,
    )
    WebDriverWait(driver, 15, poll_frequency=0.25).until(
        lambda browser: browser.execute_script(
            """
            const el = arguments[0], box = el.getBoundingClientRect();
            const x = box.left + box.width / 2, y = box.top + box.height / 2;
            if (x < 0 || x >= innerWidth || y < 70 || y >= innerHeight - 90) return false;
            const target = document.elementFromPoint(x, y);
            return target === el || el.contains(target);
            """,
            element,
        )
    )
    element.click()


def browser_options(width: int, height: int) -> Options:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--lang=ja-JP")
    return options


def wait_for_autocomplete_fields(driver: webdriver.Chrome, form) -> None:
    expected_fields = {
        "postcode": "100-0004",
        "city": "千代田区",
        "address1": "大手町",
    }

    def autocomplete_fields_applied(_browser: webdriver.Chrome) -> bool:
        for name, expected in expected_fields.items():
            fields = form.find_elements(By.CSS_SELECTOR, f'input[name="{name}"]')
            if not fields or fields[0].get_attribute("value") != expected:
                return False

        state_fields = form.find_elements(By.CSS_SELECTOR, 'select[name="id_state"]')
        return bool(
            state_fields
            and Select(state_fields[0]).first_selected_option.get_attribute("value")
        )

    WebDriverWait(driver, 15, poll_frequency=0.2).until(autocomplete_fields_applied)


def click_required_checkbox_label(driver: webdriver.Chrome, form, checkbox) -> None:
    checkbox_id = checkbox.get_attribute("id") or ""
    if not checkbox_id:
        raise AssertionError("required checkout checkbox has no associated label id")

    label = next(
        (
            candidate
            for candidate in form.find_elements(By.CSS_SELECTOR, "label[for]")
            if candidate.get_attribute("for") == checkbox_id and candidate.is_displayed()
        ),
        None,
    )
    if label is None:
        raise AssertionError("required checkout checkbox has no visible associated label")

    click_at_center(driver, label)
    WebDriverWait(driver, 5, poll_frequency=0.1).until(
        lambda _browser: checkbox.is_selected(),
        message="clicking the required checkout checkbox label did not select it",
    )


def enter_product_search_query(driver: webdriver.Chrome) -> None:
    for attempt in range(2):
        search = visible(driver, 'input[name="s"]')
        try:
            search.clear()
            search.send_keys("CI ONLY")
            search.send_keys(Keys.ENTER)
        except StaleElementReferenceException:
            if attempt == 1:
                raise
            continue
        return


def prepare_required_customer_fields(driver: webdriver.Chrome, form, email: str, password: str) -> None:
    for name, value in (("firstname", "ORDENOWA"), ("lastname", "CI Checkout"), ("email", email)):
        fields = form.find_elements(By.CSS_SELECTOR, f'input[name="{name}"]')
        if fields:
            fields[0].clear()
            fields[0].send_keys(value)

    create_account = form.find_elements(By.CSS_SELECTOR, "#password-form__check")
    if not create_account:
        raise AssertionError("checkout customer form did not offer account creation")
    account_checkbox = create_account[0]
    account_label = form.find_elements(By.CSS_SELECTOR, 'label[for="password-form__check"]')
    if not account_label:
        raise AssertionError("checkout account creation checkbox has no associated label")
    if not account_checkbox.is_selected():
        click_at_center(driver, account_label[0])
    WebDriverWait(driver, 5, poll_frequency=0.1).until(
        lambda _browser: account_checkbox.is_selected(),
        message="checkout account creation checkbox was not selected",
    )

    password_fields = form.find_elements(By.CSS_SELECTOR, 'input[type="password"]')
    if not password_fields:
        raise AssertionError("checkout customer form did not expose a password field for account creation")
    password_fields[0].clear()
    password_fields[0].send_keys(password)

    selected_radio_groups: set[str] = set()
    for field in form.find_elements(By.CSS_SELECTOR, "input[required]"):
        if not field.is_displayed() or not field.is_enabled():
            continue
        field_type = (field.get_attribute("type") or "").lower()
        name = field.get_attribute("name") or ""
        if field_type == "checkbox" and not field.is_selected():
            click_required_checkbox_label(driver, form, field)
        elif field_type == "radio" and name not in selected_radio_groups:
            click_at_center(driver, field)
            selected_radio_groups.add(name)

    for field in form.find_elements(By.CSS_SELECTOR, "select[required]"):
        if not field.is_displayed() or not field.is_enabled():
            continue
        select = Select(field)
        option = next((item for item in select.options if item.get_attribute("value")), None)
        if option is not None:
            select.select_by_value(option.get_attribute("value"))


def search_for_product(driver: webdriver.Chrome, label: str) -> None:
    visit(driver, BASE + "/")
    if label == "mobile":
        search_toggle = visible(driver, '.ps-searchbar--mobile [data-bs-target="#searchCanvas"]')
        search_toggle.click()
    enter_product_search_query(driver)

    def result(browser: webdriver.Chrome):
        for miniature in browser.find_elements(By.CSS_SELECTOR, ".product-miniature[data-id-product]"):
            if miniature.get_attribute("data-id-product") == str(PRODUCT_ID):
                return miniature
        return False

    miniature = WebDriverWait(
        driver,
        35,
        poll_frequency=0.2,
        ignored_exceptions=(StaleElementReferenceException,),
    ).until(result)
    title_link = miniature.find_element(By.CSS_SELECTOR, "a.product-miniature__title")
    if "[CI ONLY]" not in miniature.text:
        raise AssertionError("the live search result is not the clearly marked CI-only product")
    click_at_center(driver, title_link)
    WebDriverWait(driver, 30).until(
        lambda browser: f"id_product={PRODUCT_ID}" in browser.current_url
        or f"/{PRODUCT_ID}-" in browser.current_url
        or "[CI ONLY]" in browser.find_element(By.TAG_NAME, "body").text
    )
    if "[CI ONLY]" not in driver.find_element(By.TAG_NAME, "body").text:
        raise AssertionError("the selected search result did not open the CI-only product detail")
    driver.save_screenshot(str(DEST / f"checkout-{label}-search-product.png"))


def add_product_and_open_checkout(driver: webdriver.Chrome, label: str) -> None:
    buttons = driver.find_elements(
        By.CSS_SELECTOR, "button[data-button-action='add-to-cart'], .add-to-cart"
    )
    button = next(
        (item for item in buttons if item.is_displayed() and item.is_enabled()),
        None,
    )
    if button is None:
        raise AssertionError("the searched CI product has no active add-to-cart control")
    click_at_center(driver, button)
    time.sleep(2)
    visit(driver, BASE + "/index.php?controller=cart&action=show")
    cart_text = driver.find_element(By.TAG_NAME, "body").text
    if "[CI ONLY]" not in cart_text:
        raise AssertionError("the real browser cart does not contain the searched CI-only product")
    driver.save_screenshot(str(DEST / f"checkout-{label}-cart.png"))
    visit(driver, BASE + "/index.php?controller=order")
    current = WebDriverWait(driver, 30).until(
        lambda browser: next(
            (
                section
                for section in browser.find_elements(By.CSS_SELECTOR, "section.step--current")
                if section.is_displayed()
            ),
            False,
        )
    )
    if not current.get_attribute("id"):
        raise AssertionError("the authorized isolated customer checkout did not open")


def register_checkout_account(driver: webdriver.Chrome, label: str) -> str:
    email = f"qa-ordenowa-checkout-{RUN_ID}-{RUN_ATTEMPT}-{label}@example.invalid"
    password = f"ORDENOWA-CI-{RUN_ID}-{RUN_ATTEMPT}-Aa1!"
    stage_form = visible(driver, "#checkout-guest-form #customer-form")
    prepare_required_customer_fields(driver, stage_form, email, password)
    submit = visible(driver, '#checkout-guest-form button[name="continue"]')
    click_at_center(driver, submit)

    WebDriverWait(driver, 35).until(
        lambda browser: bool(browser.find_elements(By.CSS_SELECTOR, "#delivery-address form, #delivery-addresses"))
        or bool(browser.find_elements(By.ID, "checkout-continue-form"))
    )
    if not driver.find_elements(By.CSS_SELECTOR, "#delivery-address form, #delivery-addresses"):
        # Hummingbird renders this form only after account creation succeeds;
        # submit it to proceed from personal information to the address step.
        continuation = visible(driver, "#checkout-continue-form button")
        click_at_center(driver, continuation)
    WebDriverWait(driver, 35).until(
        lambda browser: (
            bool(browser.find_elements(By.CSS_SELECTOR, "#delivery-address form"))
            or bool(browser.find_elements(By.CSS_SELECTOR, "#delivery-addresses"))
        )
    )
    driver.save_screenshot(str(DEST / f"checkout-{label}-customer-registered.png"))
    return email


def select_japan_address(driver: webdriver.Chrome, label: str) -> None:
    form = visible(driver, "#delivery-address form")
    countries = form.find_elements(By.CSS_SELECTOR, 'select[name="id_country"]')
    if countries and countries[0].is_displayed():
        country_select = Select(countries[0])
        japan_option = next(
            (
                option
                for option in country_select.options
                if option.get_attribute("value")
                and ("japan" in option.text.lower() or "日本" in option.text)
            ),
            None,
        )
        if japan_option is None:
            raise AssertionError("the delivery address form has no Japan country option")
        country_select.select_by_value(japan_option.get_attribute("value"))

    search = visible(driver, '#delivery-address input[name="kuraneapostcode_search"]')
    search.clear()
    search.send_keys("1000004")
    candidate = WebDriverWait(driver, 30).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, '#delivery-address button[role="option"]'))
    )
    if not all(part in candidate.text for part in ("東京都", "千代田区", "大手町")):
        raise AssertionError("the address lookup did not return the synthetic Tokyo / Chiyoda / Otemachi result")
    click_at_center(driver, candidate)
    wait_for_autocomplete_fields(driver, form)

    for name, value in (
        ("alias", f"ORDENOWA CI {label}"),
        ("firstname", "ORDENOWA"),
        ("lastname", "CI Checkout"),
        ("postcode", "100-0004"),
        ("city", "千代田区"),
        ("address1", "大手町1-2-3"),
        ("address2", f"ORDENOWA CI {label.upper()} TEST BUILDING 101"),
        ("phone", "0312345678"),
        ("phone_mobile", "0312345678"),
    ):
        fields = form.find_elements(By.CSS_SELECTOR, f'input[name="{name}"]')
        if fields and fields[0].is_displayed() and fields[0].is_enabled():
            fields[0].clear()
            fields[0].send_keys(value)

    driver.save_screenshot(str(DEST / f"checkout-{label}-japan-address.png"))

    confirm = visible(driver, '#delivery-address button[name="confirm-addresses"]')
    click_at_center(driver, confirm)
    WebDriverWait(driver, 40).until(
        lambda browser: (
            bool(browser.find_elements(By.CSS_SELECTOR, "#js-delivery input[name^='delivery_option']"))
            or bool(browser.find_elements(By.CSS_SELECTOR, "#checkout-delivery-step.step--current"))
        )
    )


def choose_delivery_and_offline_payment(driver: webdriver.Chrome, label: str) -> None:
    delivery_radios = WebDriverWait(driver, 30).until(
        lambda browser: browser.find_elements(
            By.CSS_SELECTOR, "#js-delivery input[name^='delivery_option']"
        )
    )
    if not delivery_radios:
        raise AssertionError("no Japan delivery option is available for the test account")
    chosen_carrier = next((radio for radio in delivery_radios if radio.is_selected()), delivery_radios[0])
    if not chosen_carrier.is_selected():
        click_at_center(driver, chosen_carrier)
    continue_delivery = visible(driver, '#js-delivery button[name="confirmDeliveryOption"]')
    click_at_center(driver, continue_delivery)

    offline = WebDriverWait(driver, 35).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'input[name="payment-option"][data-module-name="ps_checkpayment"]')
        )
    )
    if not offline.is_selected():
        click_at_center(driver, offline)
    other_selected = [
        item.get_attribute("data-module-name")
        for item in driver.find_elements(By.CSS_SELECTOR, 'input[name="payment-option"]:checked')
        if item.get_attribute("data-module-name") != "ps_checkpayment"
    ]
    if other_selected:
        raise AssertionError("a payment provider other than offline ps_checkpayment was selected")

    for condition in driver.find_elements(By.CSS_SELECTOR, '#conditions-to-approve input[type="checkbox"]'):
        if condition.is_displayed() and condition.is_enabled() and not condition.is_selected():
            click_at_center(driver, condition)
    driver.save_screenshot(str(DEST / f"checkout-{label}-offline-payment-review.png"))


def place_unpaid_order(driver: webdriver.Chrome, label: str, email: str) -> dict:
    place_order = visible(driver, "#payment-confirmation button", timeout=35)
    click_at_center(driver, place_order)
    WebDriverWait(driver, 60).until(
        lambda browser: (
            "order-confirmation" in browser.current_url.lower()
            or bool(browser.find_elements(By.CSS_SELECTOR, ".order-confirmation__details-list"))
        )
    )
    confirmation = driver.find_element(By.TAG_NAME, "body").text
    if "[CI ONLY]" not in confirmation:
        raise AssertionError("order confirmation does not contain the clearly marked CI-only product")
    driver.save_screenshot(str(DEST / f"checkout-{label}.png"))

    visit(driver, BASE + "/index.php?controller=history")
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

    result = {
        "viewport": label,
        "order_id": int(order_ids[0]),
        "reference": reference,
        "email": email,
        "product_id": PRODUCT_ID,
        "payment_module": "ps_checkpayment",
    }
    (DEST / f"ci-checkout-{label}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"PASS: {label} customer searched for product {PRODUCT_ID}, saved Japanese address, "
        f"and placed unpaid offline order {reference}"
    )
    return result


def run_customer_checkout(width: int, height: int, label: str) -> None:
    driver = webdriver.Chrome(options=browser_options(width, height))
    stage = "product_search"
    try:
        driver.set_window_size(width, height)
        search_for_product(driver, label)
        stage = "cart"
        add_product_and_open_checkout(driver, label)
        stage = "customer_registration"
        email = register_checkout_account(driver, label)
        stage = "Japanese_address_lookup_and_save"
        select_japan_address(driver, label)
        stage = "carrier_and_offline_payment"
        choose_delivery_and_offline_payment(driver, label)
        stage = "unpaid_order_confirmation"
        place_unpaid_order(driver, label, email)
        overflow = driver.execute_script(
            "return document.documentElement.scrollWidth > window.innerWidth + 2"
        )
        if overflow:
            raise AssertionError(f"horizontal overflow at {width}px checkout viewport")
    except Exception as error:
        try:
            driver.save_screenshot(str(DEST / f"checkout-{label}-failure.png"))
        except Exception:
            pass
        print(
            f"FAIL: isolated {label} customer checkout at {stage} ({type(error).__name__})",
            file=sys.stderr,
        )
        print(
            f"::error title=ORDENOWA browser checkout::{label} failed at {stage} ({type(error).__name__})",
            file=sys.stderr,
        )
        raise SystemExit(f"isolated {label} customer checkout failed") from None
    finally:
        driver.quit()


def run_customer_checkouts() -> None:
    failures: list[str] = []
    for width, height, label in ((1440, 960, "desktop"), (390, 844, "mobile")):
        try:
            run_customer_checkout(width, height, label)
        except SystemExit:
            failures.append(label)
        except Exception as error:
            failures.append(label)
            print(
                f"FAIL: isolated {label} customer checkout startup ({type(error).__name__})",
                file=sys.stderr,
            )
            print(
                f"::error title=ORDENOWA browser checkout::{label} startup ({type(error).__name__})",
                file=sys.stderr,
            )

    if failures:
        failed_viewports = ", ".join(failures)
        raise SystemExit(f"isolated customer checkout failed for: {failed_viewports}")


def admin_login(driver: webdriver.Chrome) -> None:
    visit(driver, ADMIN_LOGIN + "/login")
    email = visible(
        driver,
        '#login_form input[name="email"], input[type="email"]',
    )
    password = visible(
        driver,
        '#login_form input[name="passwd"], #login_form input[name="password"], input[type="password"]',
    )
    email.send_keys(ADMIN_EMAIL)
    password.send_keys(ADMIN_PASSWORD)
    visible(
        driver,
        '#login_form button[type="submit"], #login_form input[type="submit"], button[type="submit"]',
    ).click()
    WebDriverWait(driver, 35).until(
        lambda browser: "/login" not in urlparse(browser.current_url).path
    )


def find_admin_detail_url(driver: webdriver.Chrome, order: dict) -> str:
    candidate_pages = (
        ADMIN_LOGIN + "/sell/orders/orders",
        ADMIN_LOGIN + "/index.php?controller=AdminOrders",
    )
    for listing_url in candidate_pages:
        visit(driver, listing_url)
        try:
            WebDriverWait(driver, 25).until(
                lambda browser: bool(browser.find_elements(By.CSS_SELECTOR, "body"))
                and browser.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            continue
        if "/login" in urlparse(driver.current_url).path:
            continue
        for row in driver.find_elements(By.CSS_SELECTOR, "tr, [role='row']"):
            row_text = row.text
            if order["reference"] not in row_text and order["email"] not in row_text:
                continue
            for link in row.find_elements(By.CSS_SELECTOR, "a[href]"):
                href = link.get_attribute("href") or ""
                parsed = urlparse(href)
                query = parse_qs(parsed.query)
                if (
                    order["reference"] in link.text
                    or str(order["order_id"]) in href
                    or query.get("id_order") == [str(order["order_id"])]
                ):
                    return href
            for link in row.find_elements(By.CSS_SELECTOR, "a[href]"):
                href = link.get_attribute("href") or ""
                if "/sell/orders/orders/" in href or "controller=AdminOrders" in href:
                    return href

        legacy_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="controller=AdminOrders"]')
        for link in legacy_links:
            href = link.get_attribute("href") or ""
            token = parse_qs(urlparse(href).query).get("token", [])
            if token:
                return (
                    ADMIN_LOGIN + "/index.php"
                    + "?controller=AdminOrders&vieworder&id_order="
                    + str(order["order_id"])
                    + "&token="
                    + token[0]
                )

    # The modern Symfony order detail route is stable in the pinned
    # PrestaShop release even when its list markup changes between versions.
    return ADMIN_LOGIN + f"/sell/orders/orders/{order['order_id']}/view"


def run_admin_order_view() -> None:
    options = browser_options(1440, 960)
    driver = webdriver.Chrome(options=options)
    stage = "administrator_login"
    try:
        admin_login(driver)
        driver.save_screenshot(str(DEST / "checkout-admin-login.png"))
        orders = [
            json.loads((DEST / f"ci-checkout-{label}.json").read_text(encoding="utf-8"))
            for label in ("desktop", "mobile")
        ]
        for order in orders:
            stage = f"admin_order_{order['viewport']}_open"
            detail_url = find_admin_detail_url(driver, order)
            parsed = urlparse(detail_url)
            if parsed.hostname not in {"localhost", "127.0.0.1"} or not parsed.path.startswith("/admin-kuranea/"):
                raise AssertionError("Back Office order detail resolved outside the isolated admin folder")
            visit(driver, detail_url)
            WebDriverWait(driver, 35).until(
                lambda browser: order["reference"] in browser.find_element(By.TAG_NAME, "body").text
            )
            page_text = driver.find_element(By.TAG_NAME, "body").text
            expected_building = (
                f"ORDENOWA CI {order['viewport'].upper()} TEST BUILDING 101"
            )
            for expected in (
                order["email"],
                "100-0004",
                "千代田区",
                "大手町",
                "1-2-3",
                expected_building,
            ):
                if expected not in page_text:
                    raise AssertionError(
                        f"Back Office order view omitted {expected!r} for {order['reference']}"
                    )
            driver.save_screenshot(
                str(DEST / f"checkout-admin-order-{order['viewport']}-detail.png")
            )
            driver.set_window_size(390, 844)
            driver.save_screenshot(
                str(DEST / f"checkout-admin-order-{order['viewport']}-detail-mobile.png")
            )
            driver.set_window_size(1440, 960)
            print(
                f"PASS: separate Back Office session opened unpaid browser order {order['reference']} "
                f"and read its Japanese delivery address"
            )
    except Exception as error:
        try:
            driver.save_screenshot(str(DEST / "checkout-admin-order-failure.png"))
        except Exception:
            pass
        print(
            f"FAIL: isolated administrator order view at {stage} ({type(error).__name__})",
            file=sys.stderr,
        )
        print(
            f"::error title=ORDENOWA admin order QA::{stage} ({type(error).__name__})",
            file=sys.stderr,
        )
        raise SystemExit("isolated administrator order view failed") from None
    finally:
        driver.quit()


if __name__ == "__main__":
    if sys.argv[1:] == ["customer"]:
        run_customer_checkouts()
    elif sys.argv[1:] == ["admin"]:
        run_admin_order_view()
    else:
        raise SystemExit("Usage: verify_ci_checkout_admin_browser.py customer|admin")
