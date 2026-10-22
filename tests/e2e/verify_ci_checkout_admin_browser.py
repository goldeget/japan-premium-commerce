#!/usr/bin/env python3
"""Place CI-only ps_checkpayment orders without contacting a live payment provider."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from checkout_admin_routes import is_legacy_admin_order_detail_url, is_modern_admin_order_detail_url


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


def assert_canonical_static_route(driver: webdriver.Chrome, route_slug: str) -> None:
    actual = urlparse(driver.current_url)
    base = urlparse(BASE)
    same_origin = (
        actual.scheme.lower(), actual.hostname, actual.port
    ) == (
        base.scheme.lower(), base.hostname, base.port
    )
    base_path = base.path.rstrip("/")
    expected_path = f"{base_path}/{route_slug}" or f"/{route_slug}"
    actual_path = unquote(actual.path, errors="strict").rstrip("/")
    if not same_origin or actual_path != expected_path:
        raise AssertionError(f"the {route_slug} page did not resolve to its canonical friendly route")


def assert_canonical_ascii_friendly_route(driver: webdriver.Chrome, controller: str) -> None:
    actual = urlparse(driver.current_url)
    base = urlparse(BASE)
    same_origin = (
        actual.scheme.lower(), actual.hostname, actual.port
    ) == (
        base.scheme.lower(), base.hostname, base.port
    )
    base_path = base.path.rstrip("/")
    path = unquote(actual.path, errors="strict").rstrip("/")
    inside_base = not base_path or path == base_path or path.startswith(base_path + "/")
    relative_path = path[len(base_path):] if base_path and inside_base else path
    route_segment = relative_path.rsplit("/", 1)[-1]
    if (
        not same_origin
        or not inside_base
        or not relative_path
        or relative_path == "/index.php"
        or not re.fullmatch(r"[A-Za-z0-9._~-]+", route_segment)
        or "controller" in parse_qs(actual.query)
    ):
        raise AssertionError(f"the {controller} page did not resolve to an ASCII friendly route")


def clear_checkout_network_events(driver: webdriver.Chrome) -> None:
    """Keep later performance records scoped to the order navigation."""
    try:
        driver.get_log("performance")
    except Exception:
        return


def _safe_checkout_navigation_path(raw_url: object) -> str | None:
    """Return a bounded same-origin path with query and fragment removed."""
    if not isinstance(raw_url, str):
        return None
    try:
        parsed = urlparse(raw_url)
        expected = urlparse(BASE)
        same_origin = (
            parsed.scheme.lower(),
            parsed.hostname,
            parsed.port,
        ) == (
            expected.scheme.lower(),
            expected.hostname,
            expected.port,
        )
    except ValueError:
        return None
    if not same_origin:
        return None

    source_path = parsed.path or "/"
    redacted_segments: list[str] = []
    for segment in source_path.split("/"):
        try:
            decoded_segment = unquote(segment, errors="strict")
        except (UnicodeDecodeError, ValueError):
            decoded_segment = segment
        if re.fullmatch(r"[A-Za-z0-9._~-]{24,}", decoded_segment):
            redacted_segments.append("redacted")
        else:
            redacted_segments.append(segment)
    source_path = "/".join(redacted_segments)

    safe_characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~/"
    safe_path: list[str] = []
    index = 0
    while index < len(source_path):
        current_length = sum(len(part) for part in safe_path)
        if current_length >= 240:
            break
        character = source_path[index]
        if character in safe_characters:
            safe_path.append(character)
            index += 1
        elif character == "%" and re.match(r"[0-9A-Fa-f]{2}", source_path[index + 1:index + 3]):
            if current_length + 3 > 240:
                break
            safe_path.append(source_path[index:index + 3])
            index += 3
        else:
            encoded_character = "".join(f"%{byte:02X}" for byte in character.encode("utf-8"))
            if current_length + len(encoded_character) > 240:
                break
            safe_path.append(encoded_character)
            index += 1

    return "".join(safe_path)


def _safe_checkout_http_status(value: object) -> int | None:
    try:
        status = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return status if 100 <= status <= 599 else None


def checkout_order_navigation_network_diagnostics(driver: webdriver.Chrome) -> dict[str, object]:
    """Capture bounded document navigation metadata without URLs' query values or response data."""
    try:
        events = driver.get_log("performance")
    except Exception:
        return {
            "available": False,
            "truncated": False,
            "request_path": None,
            "requested_order_controller": False,
            "response_status": None,
            "response_path": None,
            "redirects": [],
            "documents": [],
        }

    truncated = len(events) > 1000
    top_frame_id: str | None = None
    documents_by_request_id: dict[str, dict[str, object]] = {}
    document_request_ids: list[str] = []
    current_request_urls: dict[str, str] = {}
    redirects: list[dict[str, object]] = []

    for entry in events[:1000]:
        if not isinstance(entry, dict):
            continue
        try:
            envelope = json.loads(entry.get("message", ""))
        except (TypeError, ValueError):
            continue
        message = envelope.get("message", {}) if isinstance(envelope, dict) else {}
        if not isinstance(message, dict):
            continue
        event_name = message.get("method")
        params = message.get("params", {})
        if not isinstance(params, dict):
            continue
        request_id = params.get("requestId")
        if not isinstance(request_id, str):
            continue

        if event_name == "Network.requestWillBeSent":
            if params.get("type") != "Document":
                continue
            frame_id = params.get("frameId")
            if not isinstance(frame_id, str) or not frame_id:
                continue
            if top_frame_id is None:
                top_frame_id = frame_id
            elif frame_id != top_frame_id:
                continue
            request = params.get("request", {})
            if not isinstance(request, dict):
                continue
            request_url = request.get("url")
            request_url = request_url if isinstance(request_url, str) else ""
            if request_id not in documents_by_request_id:
                if len(document_request_ids) >= 8:
                    truncated = True
                    continue
                request_path = _safe_checkout_navigation_path(request_url)
                query = parse_qs(urlparse(request_url).query) if request_path is not None else {}
                documents_by_request_id[request_id] = {
                    "request_path": request_path,
                    "request_same_origin": request_path is not None,
                    "requested_order_controller": query.get("controller") == ["order"],
                    "response_status": None,
                    "response_path": None,
                    "response_same_origin": None,
                }
                document_request_ids.append(request_id)

            redirect_response = params.get("redirectResponse")
            if isinstance(redirect_response, dict):
                redirect_status = _safe_checkout_http_status(redirect_response.get("status"))
                redirect_url = redirect_response.get("url")
                if not isinstance(redirect_url, str):
                    redirect_url = current_request_urls.get(request_id, "")
                response_path = _safe_checkout_navigation_path(redirect_url)
                document = documents_by_request_id[request_id]
                document["response_status"] = redirect_status
                document["response_path"] = response_path
                document["response_same_origin"] = response_path is not None

                headers = redirect_response.get("headers", {})
                location = None
                if isinstance(headers, dict):
                    location = next(
                        (
                            value
                            for key, value in headers.items()
                            if isinstance(key, str) and key.lower() == "location"
                        ),
                        None,
                    )
                current_request_url = current_request_urls.get(request_id, redirect_url)
                target_url = urljoin(current_request_url, location) if isinstance(location, str) else ""
                target_path = _safe_checkout_navigation_path(target_url)
                if len(redirects) < 8:
                    redirects.append(
                        {
                            "status": redirect_status,
                            "target_path": target_path,
                            "target_same_origin": target_path is not None,
                        }
                    )
                else:
                    truncated = True
            current_request_urls[request_id] = request_url

        elif event_name == "Network.responseReceived" and request_id in documents_by_request_id:
            response = params.get("response", {})
            if isinstance(response, dict):
                response_path = _safe_checkout_navigation_path(response.get("url"))
                document = documents_by_request_id[request_id]
                document["response_status"] = _safe_checkout_http_status(response.get("status"))
                document["response_path"] = response_path
                document["response_same_origin"] = response_path is not None

    documents = [documents_by_request_id[request_id] for request_id in document_request_ids]
    if not documents:
        return {
            "available": True,
            "truncated": truncated,
            "request_path": None,
            "requested_order_controller": False,
            "response_status": None,
            "response_path": None,
            "redirects": [],
            "documents": [],
        }

    latest_response = next(
        (document for document in reversed(documents) if document["response_status"] is not None),
        documents[0],
    )
    first_document = documents[0]
    return {
        "available": True,
        "truncated": truncated,
        "request_path": first_document["request_path"],
        "requested_order_controller": first_document["requested_order_controller"],
        "response_status": latest_response["response_status"],
        "response_path": latest_response["response_path"],
        "redirects": redirects,
        "documents": documents,
    }


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


def emit_checkout_cart_diagnostics(
    driver: webdriver.Chrome,
    label: str,
    operation: str,
    pre_navigation_cart: dict[str, object] | None,
) -> None:
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
            )].map((element) => element.getAttribute('data-id-product'))
              .filter((productId) => /^\\d+$/.test(productId || ''));
            const modal = document.querySelector('[data-ps-ref="blockcart-modal"]');
            const modalName = modal?.querySelector('.blockcart-modal__name');
            const addToCartButtons = [...document.querySelectorAll(
              'button[data-ps-ref="add-to-cart"]'
            )].map((element) => ({visible: visible(element), disabled: element.disabled}));
            const controllerValue = new URLSearchParams(window.location.search).get('controller');
            const allowedControllers = ['order', 'order-opc', 'cart', 'authentication', 'index'];
            const controller = !controllerValue
              ? 'none'
              : allowedControllers.includes(controllerValue) ? controllerValue : 'other';
            const allowedPages = [
              'order', 'order-opc', 'cart', 'authentication', 'identity', 'index', 'pagenotfound', '404'
            ];
            const pageValue = document.body?.id || '';
            const bodyPage = allowedPages.includes(pageValue) ? pageValue : 'other';
            const currentCheckoutSteps = [...document.querySelectorAll('section.step--current')]
              .map((element) => element.id)
              .filter((stepId) => [
                'checkout-personal-information-step', 'checkout-addresses-step',
                'checkout-delivery-step', 'checkout-payment-step'
              ].includes(stepId));
            const emptyCart = Boolean(document.querySelector('.cart-grid') && cartRows.length === 0);
            const notFound = bodyPage === 'pagenotfound' || bodyPage === '404'
              || Boolean(document.querySelector('#pagenotfound, .page-not-found, [data-page="not-found"]'));
            const authentication = bodyPage === 'authentication'
              || Boolean(document.querySelector('#authentication, #login_form, #login-form, #customer-form, #checkout-guest-form, #checkout-login-form'));
            const shopHome = bodyPage === 'index';
            const title = (document.title || '').toLocaleLowerCase();
            const titleMarkers = {
              checkout: /checkout|order|注文|お届け先|お客様情報/.test(title),
              authentication: /login|sign in|ログイン/.test(title),
              not_found: /404|not found|見つかりません|該当するページ/.test(title),
              shop_brand: /ordenowa|オーデノワ/.test(title),
            };
            const destination = currentCheckoutSteps.length ? 'checkout'
              : notFound ? 'not_found'
              : emptyCart ? 'empty_cart'
              : authentication ? 'authentication'
              : shopHome ? 'shop_home'
              : controller === 'cart' || bodyPage === 'cart' ? 'cart'
              : controller === 'order' || controller === 'order-opc'
                || bodyPage === 'order' || bodyPage === 'order-opc' ? 'checkout_without_steps'
              : 'other';
            return {
              destination,
              controller,
              bodyPage,
              titleMarkers,
              readyState: document.readyState,
              cartProductIds,
              cartProductCount: cartProductIds.length,
              emptyCart,
              notFound,
              authentication,
              shopHome,
              ciOnlyInCart: cartRows.some((element) => element.textContent?.includes('[CI ONLY]')),
              blockcartModalVisible: visible(modal),
              ciOnlyInBlockcartModal: Boolean(visible(modalName) && modalName.textContent?.includes('[CI ONLY]')),
              addToCartButtons,
              currentCheckoutSteps,
            };
            """
        )
        if not isinstance(state, dict):
            raise TypeError("cart diagnostics response was not an object")
        network = checkout_order_navigation_network_diagnostics(driver)
        diagnostic_payload = {
            "viewport": label,
            "operation": operation,
            "pre_navigation_cart": pre_navigation_cart,
            "network": network,
            "state": state,
        }
        print(
            "ORDENOWA_CHECKOUT_CART_STATE="
            + json.dumps(
                diagnostic_payload,
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
    except Exception as diagnostic_error:
        diagnostic_payload = {
            "viewport": label,
            "operation": operation,
            "pre_navigation_cart": pre_navigation_cart,
            "state_collection_error": type(diagnostic_error).__name__,
            "network": checkout_order_navigation_network_diagnostics(driver),
        }
        print(
            "ORDENOWA_CHECKOUT_CART_STATE_UNAVAILABLE="
            + json.dumps(
                diagnostic_payload,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
    annotation_payload = json.dumps(diagnostic_payload, ensure_ascii=True, sort_keys=True)
    annotation_payload = annotation_payload.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    annotation = "::error title=ORDENOWA checkout cart diagnostics::" + annotation_payload
    print(annotation, file=sys.stdout)


def browser_options(width: int, height: int) -> Options:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--lang=ja-JP")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
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
    verified_pre_navigation_cart: dict[str, object] | None = None
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
        verified_cart_product_ids = [
            item.get_attribute("data-id-product")
            for item in driver.find_elements(
                By.CSS_SELECTOR,
                '.cart__item [data-link-action="delete-from-cart"][data-id-product]',
            )
        ]
        verified_pre_navigation_cart = {
            "cart_product_ids": [
                product_id for product_id in verified_cart_product_ids
                if product_id and product_id.isascii() and product_id.isdigit()
            ],
            "count": len(verified_cart_product_ids),
            "verified": verified_cart_product_ids == [str(PRODUCT_ID)] and "[CI ONLY]" in cart_text,
        }
        driver.save_screenshot(str(DEST / f"checkout-{label}-cart.png"))

        operation = "open_order_checkout"
        clear_checkout_network_events(driver)
        visit(driver, BASE + "/index.php?controller=order")
        assert_canonical_static_route(driver, "checkout")
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
        emit_checkout_cart_diagnostics(driver, label, operation, verified_pre_navigation_cart)
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


def emit_checkout_delivery_payment_diagnostics(
    driver: webdriver.Chrome,
    label: str,
    operation: str,
) -> None:
    """Emit bounded checkout controls state without customer values or page text."""
    path: str | None = None
    try:
        path = _safe_checkout_navigation_path(driver.current_url)
        state = driver.execute_script(
            """
            const isVisible = (element) => {
              if (!element) return false;
              const box = element.getBoundingClientRect();
              const style = window.getComputedStyle(element);
              return box.width > 0 && box.height > 0
                && style.display !== 'none' && style.visibility !== 'hidden';
            };
            const deliverySelector = "#js-delivery input[name^='delivery_option']";
            const deliveryRadios = [...document.querySelectorAll(deliverySelector)].slice(0, 20);
            const deliveryConfirm = document.querySelector(
              '#js-delivery button[name="confirmDeliveryOption"]'
            );
            const paymentOptions = [...document.querySelectorAll(
              'input[name="payment-option"]'
            )].slice(0, 20);
            const moduleNames = (options) => [...new Set(options
              .map((option) => option.getAttribute('data-module-name') || '')
              .filter(Boolean))].slice(0, 10);
            return {
              current_step_ids: [...document.querySelectorAll('section.step--current')]
                .map((step) => step.id)
                .filter((stepId) => [
                  'checkout-personal-information-step', 'checkout-addresses-step',
                  'checkout-delivery-step', 'checkout-payment-step'
                ].includes(stepId))
                .slice(0, 4),
              delivery_step_present: Boolean(document.querySelector('#checkout-delivery-step')),
              payment_step_present: Boolean(document.querySelector('#checkout-payment-step')),
              delivery_radio_count: document.querySelectorAll(deliverySelector).length,
              delivery_visible_count: deliveryRadios.filter(isVisible).length,
              delivery_enabled_count: deliveryRadios.filter((radio) => !radio.disabled).length,
              delivery_selected_count: deliveryRadios.filter((radio) => radio.checked).length,
              delivery_confirm_present: Boolean(deliveryConfirm),
              delivery_confirm_visible: isVisible(deliveryConfirm),
              delivery_confirm_enabled: Boolean(deliveryConfirm && !deliveryConfirm.disabled),
              payment_option_count: document.querySelectorAll(
                'input[name="payment-option"]'
              ).length,
              payment_option_visible_count: paymentOptions.filter(isVisible).length,
              payment_module_names: moduleNames(paymentOptions),
              payment_selected_count: paymentOptions.filter((option) => option.checked).length,
              ps_checkpayment_option_count: paymentOptions.filter(
                (option) => option.getAttribute('data-module-name') === 'ps_checkpayment'
              ).length,
              ps_checkpayment_selected_count: paymentOptions.filter(
                (option) => option.checked
                  && option.getAttribute('data-module-name') === 'ps_checkpayment'
              ).length,
              payment_selected_module_names: moduleNames(
                paymentOptions.filter((option) => option.checked)
              ),
            };
            """
        )
        if not isinstance(state, dict):
            state = {"state_error": "unexpected_browser_result"}
        diagnostic: dict[str, object] = {
            "viewport": label,
            "operation": operation,
            "path": path,
            **state,
        }
    except Exception as error:
        diagnostic = {
            "viewport": label,
            "operation": operation,
            "path": path,
            "diagnostic_error": type(error).__name__,
        }

    message = json.dumps(diagnostic, sort_keys=True, separators=(",", ":"))
    annotation_message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(
        "::error title=ORDENOWA checkout delivery/payment state::" + annotation_message,
        file=sys.stderr,
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
    operation = "wait_delivery_radios"
    try:
        delivery_radios = WebDriverWait(driver, 30).until(
            lambda browser: browser.find_elements(
                By.CSS_SELECTOR, "#js-delivery input[name^='delivery_option']"
            )
        )
        if not delivery_radios:
            raise AssertionError("no Japan delivery option is available for the test account")
        chosen_carrier = next((radio for radio in delivery_radios if radio.is_selected()), delivery_radios[0])
        if not chosen_carrier.is_selected():
            operation = "select_delivery_radio"
            click_at_center(driver, chosen_carrier)
        operation = "wait_delivery_confirm_button"
        continue_delivery = visible(driver, '#js-delivery button[name="confirmDeliveryOption"]')
        operation = "click_delivery_confirm_button"
        click_at_center(driver, continue_delivery)

        operation = "wait_ps_checkpayment_option"
        offline = WebDriverWait(driver, 35).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'input[name="payment-option"][data-module-name="ps_checkpayment"]')
            )
        )
        if not offline.is_selected():
            operation = "select_ps_checkpayment_option"
            click_at_center(driver, offline)
        operation = "wait_ps_checkpayment_selected"
        wait_for_offline_payment_selection(driver)
        operation = "verify_selected_payment_module"
        other_selected = [
            item.get_attribute("data-module-name")
            for item in driver.find_elements(By.CSS_SELECTOR, 'input[name="payment-option"]:checked')
            if item.get_attribute("data-module-name") != "ps_checkpayment"
        ]
        if other_selected:
            raise AssertionError("a payment provider other than offline ps_checkpayment was selected")

        operation = "accept_checkout_conditions"
        for condition in driver.find_elements(By.CSS_SELECTOR, '#conditions-to-approve input[type="checkbox"]'):
            if condition.is_displayed() and condition.is_enabled() and not condition.is_selected():
                click_at_center(driver, condition)
        operation = "save_payment_review_screenshot"
        driver.save_screenshot(str(DEST / f"checkout-{label}-offline-payment-review.png"))
    except Exception:
        emit_checkout_delivery_payment_diagnostics(driver, label, operation)
        raise


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
    assert_canonical_ascii_friendly_route(driver, "history")
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


def admin_login_diagnostics(driver: webdriver.Chrome) -> dict[str, object]:
    return {
        "path": _safe_checkout_navigation_path(driver.current_url),
        "login_form_present": bool(driver.find_elements(By.CSS_SELECTOR, "#login_form")),
        "email_field_count": len(
            driver.find_elements(By.CSS_SELECTOR, '#login_form input[name="email"], input[type="email"]')
        ),
        "password_field_count": len(
            driver.find_elements(
                By.CSS_SELECTOR,
                '#login_form input[name="passwd"], #login_form input[name="password"], input[type="password"]',
            )
        ),
        "submit_button_count": len(
            driver.find_elements(
                By.CSS_SELECTOR,
                '#login_form button[type="submit"], #login_form input[type="submit"], button[type="submit"]',
            )
        ),
        "alert_count": len(driver.find_elements(By.CSS_SELECTOR, '.alert-danger, .alert-error, [role="alert"]')),
        "admin_sidebar_present": bool(driver.find_elements(By.CSS_SELECTOR, "#nav-sidebar")),
    }


def admin_login(driver: webdriver.Chrome, set_stage=None) -> None:
    if set_stage:
        set_stage("navigation")
    visit(driver, ADMIN_LOGIN + "/login")
    if set_stage:
        set_stage("email_field")
    email = visible(
        driver,
        '#login_form input[name="email"], input[type="email"]',
    )
    if set_stage:
        set_stage("password_field")
    password = visible(
        driver,
        '#login_form input[name="passwd"], #login_form input[name="password"], input[type="password"]',
    )
    email.send_keys(ADMIN_EMAIL)
    password.send_keys(ADMIN_PASSWORD)
    if set_stage:
        set_stage("submit_button")
    visible(
        driver,
        '#login_form button[type="submit"], #login_form input[type="submit"], button[type="submit"]',
    ).click()
    if set_stage:
        set_stage("redirect")
    WebDriverWait(driver, 35).until(
        lambda browser: "/login" not in urlparse(browser.current_url).path
    )


def find_admin_detail_url(driver: webdriver.Chrome, order: dict) -> str:
    candidate_pages = (
        ADMIN_LOGIN + "/sell/orders",
        ADMIN_LOGIN + "/index.php?controller=AdminOrders",
    )
    rows_inspected = 0
    matching_rows = 0
    candidate_route_paths: list[str] = []
    matching_link_hints: list[dict[str, object]] = []
    for listing_url in candidate_pages:
        visit(driver, listing_url)
        try:
            WebDriverWait(driver, 25).until(
                lambda browser: bool(browser.find_elements(By.CSS_SELECTOR, "body"))
                and browser.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            continue
        safe_route_path = _safe_checkout_navigation_path(driver.current_url)
        if safe_route_path:
            candidate_route_paths.append(safe_route_path)
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
                safe_link_path = _safe_checkout_navigation_path(href)
                if safe_link_path:
                    query_keys = sorted(
                        key
                        for key in parse_qs(parsed.query, keep_blank_values=True)
                        if re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", key)
                    )
                    hint = {"path": safe_link_path, "query_keys": query_keys}
                    if hint not in matching_link_hints:
                        matching_link_hints.append(hint)
                if is_modern_admin_order_detail_url(href, order_id) or is_legacy_admin_order_detail_url(
                    href, order_id
                ):
                    return href
    diagnostic = {
        "listing_paths": candidate_route_paths,
        "matched_rows": matching_rows,
        "matched_row_link_hints": matching_link_hints[:30],
    }
    print(
        "::notice title=ORDENOWA admin order lookup routes::"
        + json.dumps(diagnostic, sort_keys=True),
        file=sys.stderr,
    )
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
        def set_login_stage(login_stage: str) -> None:
            nonlocal stage
            stage = f"administrator_login_{login_stage}"

        admin_login(driver, set_login_stage)
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
        if stage.startswith("administrator_login_"):
            try:
                print(
                    "ORDENOWA_ADMIN_LOGIN_DIAGNOSTICS="
                    + json.dumps(admin_login_diagnostics(driver), sort_keys=True),
                    file=sys.stderr,
                )
            except Exception:
                print("ORDENOWA_ADMIN_LOGIN_DIAGNOSTICS=unavailable", file=sys.stderr)
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
