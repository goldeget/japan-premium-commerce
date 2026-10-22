#!/usr/bin/env python3
"""Place CI-only ps_checkpayment orders without contacting a live payment provider."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from checkout_admin_routes import is_legacy_admin_order_detail_url


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


def emit_checkout_cart_diagnostics(driver: webdriver.Chrome, label: str, operation: str) -> None:
    try:
        state = driver.execute_script(
            """
            const visible = (element) => {
              if (!element) return false;
              const box = element.getBoundingClientRect();
              const style = window.getComputedStyle(element);
              return box.width > 0 && box.height > 0
                && style.display !== 'none' && style.visibility !== 'hidden';
            };
            const cartRows = [...document.querySelectorAll('.cart__item')];
            const cartProductIds = [...document.querySelectorAll(
              '.cart__item [data-link-action="delete-from-cart"][data-id-product]'
            )].map((element) => element.getAttribute('data-id-product'));
            const modal = document.querySelector('[data-ps-ref="blockcart-modal"]');
            const modalName = modal?.querySelector('.blockcart-modal__name');
            const addToCartButtons = [...document.querySelectorAll(
              'button[data-ps-ref="add-to-cart"]'
            )].map((element) => ({visible: visible(element), disabled: element.disabled}));
            return {
              pathname: window.location.pathname,
              queryKeys: [...new URLSearchParams(window.location.search).keys()].sort(),
              readyState: document.readyState,
              cartProductIds,
              ciOnlyInCart: cartRows.some((element) => element.textContent?.includes('[CI ONLY]')),
              blockcartModalVisible: visible(modal),
              ciOnlyInBlockcartModal: Boolean(visible(modalName) && modalName.textContent?.includes('[CI ONLY]')),
              addToCartButtons,
              currentCheckoutSteps: [...document.querySelectorAll('section.step--current')]
                .map((element) => element.id),
            };
            """
        )
        print(
            "ORDENOWA_CHECKOUT_CART_STATE="
            + json.dumps(
                {"viewport": label, "operation": operation, "state": state},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
    except Exception as diagnostic_error:
        print(
            "ORDENOWA_CHECKOUT_CART_STATE_UNAVAILABLE="
            + json.dumps(
                {
                    "viewport": label,
                    "operation": operation,
                    "error": type(diagnostic_error).__name__,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )


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
            # The fixture title includes this full-length indexed word. "CI" is
            # too short for a reliable PrestaShop search term, and Hummingbird
            # renders AJAX autocomplete results instead of submitting on Enter.
            search.send_keys("postcode")
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

    result_id = f"result_product_option_{PRODUCT_ID}"

    def result(browser: webdriver.Chrome):
        for product_link in browser.find_elements(By.ID, result_id):
            if product_link.is_displayed():
                return product_link
        return False

    product_link = WebDriverWait(
        driver,
        35,
        poll_frequency=0.2,
        ignored_exceptions=(StaleElementReferenceException,),
    ).until(result)
    product_name = product_link.get_attribute("aria-label") or product_link.text
    if "[CI ONLY]" not in product_name or "[CI ONLY]" not in product_link.text:
        raise AssertionError("the live search result is not the clearly marked CI-only product")
    product_url = urlparse(product_link.get_attribute("href"))
    click_at_center(driver, product_link)
    WebDriverWait(driver, 30).until(
        lambda browser: (
            urlparse(browser.current_url).netloc == product_url.netloc
            and urlparse(browser.current_url).path == product_url.path
            and urlparse(browser.current_url).query == product_url.query
        ),
        message=f"clicking the exact search result for product {PRODUCT_ID} did not open its detail page",
    )
    if "[CI ONLY]" not in driver.find_element(By.TAG_NAME, "body").text:
        raise AssertionError("the selected search result did not open the CI-only product detail")
    driver.save_screenshot(str(DEST / f"checkout-{label}-search-product.png"))


def add_product_and_open_checkout(driver: webdriver.Chrome, label: str) -> None:
    operation = "locate_add_to_cart_button"
    try:
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
            message="the searched CI product has no active Hummingbird add-to-cart button",
        )
        operation = "click_add_to_cart_button"
        click_at_center(driver, button)

        operation = "wait_for_ci_only_blockcart_modal"

        def ci_only_modal(browser: webdriver.Chrome):
            for modal in browser.find_elements(By.CSS_SELECTOR, '[data-ps-ref="blockcart-modal"]'):
                if not modal.is_displayed():
                    continue
                names = modal.find_elements(By.CSS_SELECTOR, ".blockcart-modal__name")
                if names and "[CI ONLY]" in names[0].text:
                    return modal
            return False

        modal = WebDriverWait(
            driver,
            25,
            poll_frequency=0.2,
            ignored_exceptions=(StaleElementReferenceException,),
        ).until(
            ci_only_modal,
            message="adding the searched CI product did not show its Hummingbird cart confirmation",
        )

        operation = "follow_blockcart_proceed_to_checkout_link"
        proceed_links = modal.find_elements(By.CSS_SELECTOR, ".modal-footer > a.btn-primary")
        proceed_link = next(
            (link for link in proceed_links if link.is_displayed() and link.is_enabled()),
            None,
        )
        if proceed_link is None:
            raise AssertionError("the Hummingbird cart confirmation has no visible proceed-to-checkout link")
        proceed_link.click()

        operation = "wait_for_exact_cart_product_id"

        def exact_cart_product(browser: webdriver.Chrome) -> bool:
            cart_product_ids = [
                item.get_attribute("data-id-product")
                for item in browser.find_elements(
                    By.CSS_SELECTOR,
                    '.cart__item [data-link-action="delete-from-cart"][data-id-product]',
                )
            ]
            return cart_product_ids == [str(PRODUCT_ID)]

        WebDriverWait(driver, 30, poll_frequency=0.2).until(
            exact_cart_product,
            message=f"the browser cart did not contain only product {PRODUCT_ID}",
        )
        cart_text = driver.find_element(By.TAG_NAME, "body").text
        if "[CI ONLY]" not in cart_text:
            raise AssertionError("the real browser cart does not contain the searched CI-only product")
        driver.save_screenshot(str(DEST / f"checkout-{label}-cart.png"))

        operation = "open_order_checkout"
        visit(driver, BASE + "/index.php?controller=order")
        operation = "wait_for_initial_checkout_step"
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
    except Exception:
        emit_checkout_cart_diagnostics(driver, label, operation)
        raise


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


def emit_checkout_payment_diagnostics(driver: webdriver.Chrome) -> None:
    payment_selector = 'input[name="payment-option"][data-module-name="ps_checkpayment"]'
    try:
        offline_options = driver.find_elements(By.CSS_SELECTOR, payment_selector)
        selected_options = driver.find_elements(
            By.CSS_SELECTOR, 'input[name="payment-option"]:checked'
        )
        diagnostics = {
            "path": urlparse(driver.current_url).path,
            "offline_selected": any(option.is_selected() for option in offline_options),
            "selected_modules": [
                module
                for module in (
                    option.get_attribute("data-module-name") for option in selected_options
                )
                if module
            ][:10],
        }
    except Exception as error:
        diagnostics = {"diagnostic_error": type(error).__name__}
    print(
        "::error title=ORDENOWA checkout payment state::"
        + json.dumps(diagnostics, sort_keys=True),
        file=sys.stderr,
    )


def wait_for_offline_payment_selection(driver: webdriver.Chrome) -> None:
    payment_selector = 'input[name="payment-option"][data-module-name="ps_checkpayment"]'

    def offline_payment_selected(browser: webdriver.Chrome) -> bool:
        try:
            return any(
                option.is_selected()
                for option in browser.find_elements(By.CSS_SELECTOR, payment_selector)
            )
        except StaleElementReferenceException:
            return False

    try:
        WebDriverWait(driver, 15, poll_frequency=0.25).until(offline_payment_selected)
    except TimeoutException:
        emit_checkout_payment_diagnostics(driver)
        raise AssertionError(
            "offline ps_checkpayment radio did not become selected before order review"
        ) from None


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
    wait_for_offline_payment_selection(driver)
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
    rows_inspected = 0
    matching_rows = 0
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
            rows_inspected += 1
            row_text = row.text
            if order["reference"] not in row_text and order["email"] not in row_text:
                continue
            matching_rows += 1
            for link in row.find_elements(By.CSS_SELECTOR, "a[href]"):
                href = link.get_attribute("href") or ""
                parsed = urlparse(href)
                order_id = str(order["order_id"])
                modern_detail = re.search(
                    rf"/sell/orders/orders/{re.escape(order_id)}(?:/view)?/?$",
                    parsed.path,
                )
                if modern_detail or is_legacy_admin_order_detail_url(href, order_id):
                    return href
    print(
        "::error title=ORDENOWA admin order lookup::"
        "No matching Back Office order-list result with a detail link was found "
        f"after inspecting {len(candidate_pages)} routes and {rows_inspected} rows "
        f"({matching_rows} rows matched the expected reference or customer email).",
        file=sys.stderr,
    )
    raise AssertionError(
        "no matching Back Office order-list result was found for the expected order reference or email"
    )


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
