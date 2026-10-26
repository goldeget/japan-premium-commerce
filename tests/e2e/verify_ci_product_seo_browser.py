#!/usr/bin/env python3
"""Compare product-page Product/Offer JSON-LD with an isolated active fixture.

Run after ``prepare_ci_free_shipping_product.php`` in its disposable GitHub
Actions shop. The verifier only reads the product page; it never adds a cart
line, creates an order, or changes product state.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from verify_cart_controls_browser import (
    BASE,
    DEST,
    PRODUCT_ID,
    parse_yen,
    validate_isolated_ci_compose_project,
    validate_loopback_shop,
)


RUN_ID = os.environ["GITHUB_RUN_ID"]
RUN_ATTEMPT = os.environ["GITHUB_RUN_ATTEMPT"]
EXPECTED_REFERENCE = f"KURANEA-CI-{RUN_ID}-{RUN_ATTEMPT}"
EXPECTED_NAME = f"[CI ONLY] ORDENOWA free shipping product {RUN_ID}-{RUN_ATTEMPT}"
EXPECTED_PRICE_JPY = Decimal("1100")
EXPECTED_CURRENCY = "JPY"
RESULT_PATH = DEST / "product-seo-result.json"
SCREENSHOT_PATH = DEST / "product-seo-desktop.png"


def assert_true(value: object, message: str) -> None:
    if not value:
        raise AssertionError(message)


def same_origin(destination: str) -> bool:
    try:
        parsed = urlparse(destination)
        base = urlparse(BASE)
        return (
            parsed.scheme == base.scheme
            and parsed.hostname == base.hostname
            and parsed.port == base.port
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False


def jsonld_nodes(value: Any):
    """Yield JSON-LD objects at the root, @graph, or nested-property levels."""
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from jsonld_nodes(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from jsonld_nodes(nested)


def has_schema_type(value: dict[str, Any], expected: str) -> bool:
    schema_type = value.get("@type")
    if isinstance(schema_type, str):
        return schema_type.rsplit("/", 1)[-1] == expected
    return isinstance(schema_type, list) and any(
        isinstance(item, str) and item.rsplit("/", 1)[-1] == expected
        for item in schema_type
    )


def decimal_value(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def has_schema_org_context(product: dict[str, Any]) -> bool:
    context = product.get("@context")
    if not isinstance(context, str):
        return False
    try:
        parsed = urlparse(context)
        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname is not None
            and parsed.hostname.casefold() == "schema.org"
            and parsed.username is None
            and parsed.password is None
            and parsed.port is None
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


def schema_product_for_reference(scripts: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    parsed_documents: list[Any] = []
    for source in scripts:
        try:
            parsed_documents.append(json.loads(source))
        except (TypeError, ValueError):
            raise AssertionError("product page emitted invalid JSON-LD") from None

    products = [node for document in parsed_documents for node in jsonld_nodes(document)
                if has_schema_type(node, "Product")]
    matching = [node for node in products if node.get("sku") == EXPECTED_REFERENCE]
    assert_true(len(matching) == 1, "JSON-LD did not identify exactly one run-scoped synthetic product")
    offers = matching[0].get("offers")
    if isinstance(offers, dict):
        offer_nodes = [offers]
    elif isinstance(offers, list):
        offer_nodes = [item for item in offers if isinstance(item, dict)]
    else:
        offer_nodes = []
    assert_true(len(offer_nodes) == 1, "JSON-LD did not contain exactly one Product Offer")
    return matching[0], offer_nodes[0]


def product_id_matches_url(destination: str) -> bool:
    if not same_origin(destination):
        return False
    parsed = urlparse(destination)
    from urllib.parse import parse_qs

    query_ids = parse_qs(parsed.query, keep_blank_values=True).get("id_product", [])
    if query_ids:
        return query_ids == [str(PRODUCT_ID)]
    return any(
        segment.startswith(f"{PRODUCT_ID}-") and segment.endswith(".html")
        for segment in parsed.path.split("/")
    )


def read_product_page(driver: webdriver.Chrome, result: dict[str, Any]) -> dict[str, Any]:
    result["stage"] = "product_document"
    result["substage"] = "navigation"
    driver.get(BASE + "/index.php?" + urlencode({"controller": "product", "id_product": PRODUCT_ID}))
    WebDriverWait(driver, 40).until(
        lambda browser: browser.execute_script("return document.readyState") == "complete"
    )

    response_status = driver.execute_script(
        """
        const entries = performance.getEntriesByType('navigation');
        const entry = entries.length ? entries[0] : null;
        return entry && Number.isInteger(entry.responseStatus) ? entry.responseStatus : null;
        """
    )
    result["response_status"] = response_status if type(response_status) is int and 100 <= response_status <= 599 else None
    result["substage"] = "response_status"
    assert_true(response_status in (None, 200), "synthetic product document did not return HTTP 200")
    result["same_origin"] = same_origin(driver.current_url)
    result["substage"] = "origin"
    assert_true(result["same_origin"], "product page left the isolated shop origin")
    result["substage"] = "document_locale"
    document_language = (driver.find_element(By.TAG_NAME, "html").get_attribute("lang") or "").lower().split("-")[0]
    result["japanese_document"] = document_language == "ja"
    assert_true(
        result["japanese_document"],
        "product page did not retain the Japanese customer locale",
    )

    result["stage"] = "visible_product_identity"
    product_ids = driver.find_elements(By.CSS_SELECTOR, "input#product_page_product_id[name='id_product']")
    headings = driver.find_elements(By.CSS_SELECTOR, "h1.product__name")
    visible_headings = [item for item in headings if item.is_displayed()]
    assert_true(
        len(product_ids) == 1 and product_ids[0].get_attribute("value") == str(PRODUCT_ID),
        "visible product page is not bound to the expected synthetic product ID",
    )
    assert_true(len(visible_headings) == 1, "product page has no unique visible product name")
    visible_name = " ".join(visible_headings[0].text.split())
    assert_true(visible_name == EXPECTED_NAME, "visible product name differs from the run-scoped fixture")

    result["stage"] = "visible_product_price"
    price_elements = driver.find_elements(By.CSS_SELECTOR, ".product__price")
    visible_prices = [item for item in price_elements if item.is_displayed()]
    assert_true(len(visible_prices) == 1, "product page has no unique visible sale price")
    visible_price_text = visible_prices[0].text
    visible_price = Decimal(parse_yen(visible_price_text))
    has_yen_symbol = "¥" in visible_price_text or "￥" in visible_price_text
    assert_true(has_yen_symbol, "visible product price does not show a JPY currency symbol")

    result["stage"] = "visible_product_availability"
    add_buttons = driver.find_elements(By.CSS_SELECTOR, "button[data-ps-ref='add-to-cart']")
    visible_add_buttons = [item for item in add_buttons if item.is_displayed()]
    assert_true(len(visible_add_buttons) == 1, "synthetic product has no unique visible add-to-cart control")
    purchasable = visible_add_buttons[0].is_enabled() and visible_add_buttons[0].get_attribute("aria-disabled") != "true"

    result["stage"] = "rendered_product_offer"
    canonical_links = driver.find_elements(By.CSS_SELECTOR, "link[rel='canonical']")
    assert_true(len(canonical_links) == 1, "product page has no unique canonical URL")
    canonical_url = canonical_links[0].get_attribute("href") or ""
    assert_true(product_id_matches_url(canonical_url), "canonical URL does not identify the fixture on the isolated shop origin")
    scripts = driver.execute_script(
        "return [...document.querySelectorAll('script[type=\"application/ld+json\"]')].map(item => item.textContent || '')"
    )
    assert_true(isinstance(scripts, list) and bool(scripts), "product page has no JSON-LD scripts")
    product, offer = schema_product_for_reference(scripts)

    checks = {
        "product_id_matches_visible_field": True,
        "schema_org_context_matches_product": has_schema_org_context(product),
        "sku_matches_run_scoped_reference": product.get("sku") == EXPECTED_REFERENCE,
        "name_matches_visible_heading": product.get("name") == visible_name,
        "offer_price_matches_visible_price": decimal_value(offer.get("price")) == visible_price == EXPECTED_PRICE_JPY,
        "currency_matches_visible_yen_and_fixture": offer.get("priceCurrency") == EXPECTED_CURRENCY and has_yen_symbol,
        "offer_url_matches_canonical": offer.get("url") == canonical_url,
        "availability_matches_purchasable_ui": (
            isinstance(offer.get("availability"), str)
            and offer["availability"].rstrip("/").rsplit("/", 1)[-1] == "InStock"
            and purchasable
        ),
    }
    assert_true(all(checks.values()), "Product/Offer JSON-LD did not match its visible synthetic product UI")
    return {
        "status": "success",
        "stage": "complete",
        "response_status": response_status if isinstance(response_status, int) else None,
        "checks": checks,
        "observed_price_jpy": int(visible_price),
        "observed_currency": EXPECTED_CURRENCY,
        "availability_class": "in_stock" if purchasable else "not_purchasable",
    }


def main() -> None:
    validate_isolated_ci_compose_project()
    validate_loopback_shop()
    assert_true(PRODUCT_ID > 0, "CI_TEST_PRODUCT_ID must identify the active synthetic CI fixture")

    options = Options()
    for argument in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--lang=ja-JP"):
        options.add_argument(argument)
    options.add_argument("--window-size=1440,960")

    result: dict[str, Any] = {"status": "failure", "stage": "browser_start", "substage": "browser_start", "checks": {}}
    driver: webdriver.Chrome | None = None
    try:
        driver = webdriver.Chrome(options=options)
        result.update(read_product_page(driver, result))
        result["stage"] = "complete"
        result["substage"] = "complete"
        driver.save_screenshot(str(SCREENSHOT_PATH))
        result["screenshot_saved"] = True
        print("PASS: synthetic product identity, name, JPY Offer, canonical URL, and availability match rendered UI")
    except Exception as error:
        result["status"] = "failure"
        result["exception_class"] = type(error).__name__
        if driver is not None:
            try:
                driver.save_screenshot(str(SCREENSHOT_PATH))
            except Exception:
                result["screenshot_saved"] = False
            else:
                result["screenshot_saved"] = True
        raise AssertionError(
            f"synthetic product SEO browser failed at {result.get('stage', 'unknown')} ({type(error).__name__})"
        ) from None
    finally:
        try:
            if driver is not None:
                driver.quit()
        finally:
            RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
