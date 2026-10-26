#!/usr/bin/env python3
"""Search the existing CI-only Japanese variant; never create a cart or order.

Run after setup_ci_variant_product.php and native search indexing, with
CI_TEST_PRODUCT_ID set to its CI_TEST_VARIANT_PRODUCT_ID output. The checked-in
kuranea searchbar/listing and inherited Hummingbird miniature templates define
the selectors below. This verifier requires the disposable loopback CI shop.
"""

from __future__ import annotations

import json
import os
import re
from urllib.parse import parse_qs, urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from storefront_product_contract import product_page_failure_reason
from verify_cart_controls_browser import (
    BASE, DEST, PRODUCT_ID, click_at_center, visible,
    validate_isolated_ci_compose_project, validate_loopback_shop,
)


def assert_true(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_same_origin(destination: str) -> None:
    parsed, base = urlparse(destination), urlparse(BASE)
    assert_true(
        parsed.scheme == base.scheme and parsed.hostname == base.hostname
        and parsed.port == base.port and parsed.username is None and parsed.password is None,
        "Search navigation must remain on the isolated shop origin",
    )


def assert_product_destination(destination: str) -> None:
    assert_same_origin(destination)
    parsed = urlparse(destination)
    query = parse_qs(parsed.query, keep_blank_values=True)
    assert_true(set(query).issubset({'controller', 'id_product', 'id_lang', 'id_product_attribute'}),
                "Product link has unexpected navigation parameters")
    assert_true(all(len(values) == 1 for values in query.values()), "Product link has ambiguous parameters")
    if 'controller' in query or 'id_product' in query:
        assert_true(query.get('controller') == ['product'] and query.get('id_product') == [str(PRODUCT_ID)],
                    "Product link does not target the synthetic fixture")
    else:
        assert_true(bool(re.search(rf'/{PRODUCT_ID}-[^/]+\.html$', parsed.path)),
                    "Product link does not use the synthetic fixture route")


def assert_japanese_document(driver) -> None:
    assert_same_origin(driver.current_url)
    language = driver.find_element(By.TAG_NAME, 'html').get_attribute('lang') or ''
    assert_true(language.lower().split('-')[0] == 'ja', "Search lost the Japanese storefront locale")


def wait_document(driver) -> None:
    WebDriverWait(driver, 40).until(lambda browser: browser.execute_script('return document.readyState') == 'complete')


def search(driver, query: str, mobile: bool, result: dict) -> None:
    diagnostics = result["diagnostics"]
    if mobile:
        result["substage"] = "search_toggle"
        toggle = visible(driver, '[data-bs-target="#searchCanvas"]')
        diagnostics["search_toggle_visible"] = toggle.is_displayed()
        click_at_center(driver, toggle)
    result["substage"] = "search_field"
    field = visible(driver, '#ps_searchbar_input[name="s"]')
    diagnostics["search_field_visible"] = field.is_displayed()
    form = field.find_element(By.XPATH, './ancestor::form')
    result["substage"] = "search_form_method"
    diagnostics["form_method_get"] = (form.get_attribute('method') or '').lower() == 'get'
    assert_true(diagnostics["form_method_get"], "Search must use the native GET form")
    action = urljoin(driver.current_url, form.get_attribute('action') or '')
    result["substage"] = "search_form_origin"
    action_origin = urlparse(action)
    base_origin = urlparse(BASE)
    diagnostics["form_action_same_origin"] = (
        action_origin.scheme == base_origin.scheme
        and action_origin.hostname == base_origin.hostname
        and action_origin.port == base_origin.port
        and action_origin.username is None and action_origin.password is None
    )
    assert_true(diagnostics["form_action_same_origin"], "Search navigation must remain on the isolated shop origin")
    action_parts = urlparse(action)
    action_query = parse_qs(action_parts.query)
    diagnostics["form_action_native_search"] = (
        action_query.get('controller') == ['search']
        or (action_parts.path.rstrip('/').endswith('/search') and not action_query.get('controller'))
    )
    result["substage"] = "search_form_route"
    assert_true(diagnostics["form_action_native_search"], "Search form does not target the native search route")
    old_document = driver.find_element(By.TAG_NAME, 'html')
    field.clear()
    field.send_keys(query)
    result["substage"] = "search_submit"
    field.send_keys(Keys.ENTER)
    WebDriverWait(driver, 40).until(EC.staleness_of(old_document))
    diagnostics["document_changed"] = True
    wait_document(driver)
    result["substage"] = "search_result_document"
    response_status = driver.execute_script(
        "const entries=performance.getEntriesByType('navigation');const entry=entries.length?entries[0]:null;return entry&&Number.isInteger(entry.responseStatus)?entry.responseStatus:null;"
    )
    diagnostics["response_status"] = response_status if type(response_status) is int and 100 <= response_status <= 599 else None
    assert_japanese_document(driver)
    diagnostics["search_document"] = bool(driver.find_elements(By.CSS_SELECTOR, 'body#search'))
    assert_true(diagnostics["search_document"], "Search did not render its results document")
    result["substage"] = "search_query_readback"
    diagnostics["query_readback_matches"] = parse_qs(urlparse(driver.current_url).query).get('s') == [query]
    assert_true(diagnostics["query_readback_matches"], "Search changed the submitted Japanese query")
    field_value = driver.find_element(By.CSS_SELECTOR, '#ps_searchbar_input[name="s"]').get_attribute('value')
    diagnostics["input_readback_matches"] = field_value == query
    assert_true(diagnostics["input_readback_matches"], "Search input did not preserve the submitted Japanese query")


def verify_product(driver, expected_name: str) -> None:
    assert_japanese_document(driver)
    headings = driver.find_elements(By.CSS_SELECTOR, 'h1.product__name')
    heading = next((item for item in headings if item.is_displayed()), None)
    forms = driver.find_elements(By.CSS_SELECTOR, 'form#add-to-cart-or-refresh')
    ids = driver.find_elements(By.CSS_SELECTOR, "input#product_page_product_id[name='id_product']")
    buttons = driver.find_elements(By.CSS_SELECTOR, "button[data-button-action='add-to-cart']")
    reason = product_page_failure_reason(
        response_status=None,
        body_id=driver.find_element(By.TAG_NAME, 'body').get_attribute('id') or '',
        not_found_visible=any(item.is_displayed() for item in driver.find_elements(By.CSS_SELECTOR, '.page-content--not-found')),
        product_container_count=len(driver.find_elements(By.CSS_SELECTOR, '[data-ps-ref="product-container"]')),
        product_heading_count=len(headings), product_heading_visible=heading is not None,
        product_heading_text=heading.text if heading is not None else '',
        product_form_count=len(forms), product_id_value=ids[0].get_attribute('value') if len(ids) == 1 else None,
        expected_product_id=PRODUCT_ID,
        add_to_cart_visible=any(item.is_displayed() for item in buttons),
        add_to_cart_enabled=any(item.is_displayed() and item.is_enabled() for item in buttons),
    )
    assert_true(reason is None, f"Search product detail failed its fixture readback ({reason})")
    assert_true(heading is not None and heading.text.strip() == expected_name, "Search opened an unexpected product title")


def run_viewport(label: str, width: int, height: int, run_id: str, attempt: str) -> None:
    options = Options()
    for argument in ('--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--lang=ja-JP'):
        options.add_argument(argument)
    options.add_argument(f'--window-size={width},{height}')
    driver = None
    result = {'viewport': label, 'status': 'failed', 'stage': 'home', 'substage': 'browser_start', 'cases': [],
              'product_navigation': False, 'paid': False, 'payment_provider_called': False,
              'diagnostics': {
                  'search_toggle_visible': False, 'search_field_visible': False,
                  'form_method_get': False, 'form_action_same_origin': False,
                  'form_action_native_search': False, 'document_changed': False,
                  'response_status': None, 'search_document': False,
                  'query_readback_matches': False, 'input_readback_matches': False,
              }}
    expected_name = f'[CI ONLY] ORDENOWA カートオプション {run_id}-{attempt}'
    try:
        driver = webdriver.Chrome(options=options)
        # Hummingbird moves the language selector into mobile navigation.
        # Establish the locale while its desktop control is visible.
        driver.set_window_size(1440, 960)
        driver.get(BASE)
        wait_document(driver)
        selector = visible(driver, 'select.js-language-selector')
        matches = selector.find_elements(By.CSS_SELECTOR, 'option[data-iso-code="ja"]')
        assert_true(len(matches) == 1, "Storefront has no unique Japanese language option")
        value = matches[0].get_attribute('value') or ''
        assert_true(bool(value), "Japanese locale option has no destination")
        assert_same_origin(urljoin(driver.current_url, value))
        old_document = driver.find_element(By.TAG_NAME, 'html')
        already_selected = matches[0].is_selected()
        Select(selector).select_by_value(value)
        if not already_selected:
            WebDriverWait(driver, 40).until(EC.staleness_of(old_document))
        WebDriverWait(driver, 40).until(lambda browser: (browser.find_element(By.TAG_NAME, 'html').get_attribute('lang') or '').lower().split('-')[0] == 'ja')
        wait_document(driver)
        assert_japanese_document(driver)
        driver.set_window_size(width, height)
        for case, query in (
            ("exact", "カートオプション"),
            ("partial", "カートオプ"),
            ("missing", f"該当なし検索検証{run_id}試行{attempt}"),
        ):
            result['stage'] = case
            result['diagnostics'].update(
                search_toggle_visible=False, search_field_visible=False,
                form_method_get=False, form_action_same_origin=False,
                form_action_native_search=False, document_changed=False,
                response_status=None, search_document=False,
                query_readback_matches=False, input_readback_matches=False,
            )
            search(driver, query, width < 768, result)
            header = visible(driver, '#js-product-list-header')
            assert_true(query in header.text, "Search heading omitted the Japanese query")
            if case == 'missing':
                assert_true(not driver.find_elements(By.CSS_SELECTOR, '#products article[data-id-product]'), "No-result query returned product cards")
                assert_true('の商品は見つかりませんでした' in header.text, "Missing Japanese no-result heading")
                assert_true('検索条件に一致する商品が見つかりませんでした。' in visible(driver, '#js-product-list').text,
                            "Missing Japanese no-result guidance")
                assert_true(bool(driver.find_elements(By.CSS_SELECTOR, '#js-product-list a.btn-primary')), "No-result state has no recovery link")
            else:
                assert_true('の検索結果' in header.text, "Missing Japanese search result heading")
                card = visible(driver, f'#products article[data-id-product="{PRODUCT_ID}"]')
                title = card.find_element(By.CSS_SELECTOR, 'a.product-miniature__title')
                assert_true(title.text.strip() == expected_name, "Search card is not this run's Japanese fixture")
                assert_product_destination(title.get_attribute('href') or '')
                if case == 'partial':
                    driver.save_screenshot(str(DEST / f'storefront-search-{label}-{case}.png'))
                    result['stage'] = 'product'
                    click_at_center(driver, title)
                    wait_document(driver)
                    verify_product(driver, expected_name)
                    driver.save_screenshot(str(DEST / f'storefront-search-{label}-product.png'))
                    result['product_navigation'] = True
            if case != 'partial':
                driver.save_screenshot(str(DEST / f'storefront-search-{label}-{case}.png'))
            result['cases'].append(case)
        result.update(status='success', stage='complete')
        result['substage'] = 'complete'
        print(f'PASS: {label} Japanese exact/partial/missing search and isolated product navigation')
    except Exception:
        if driver is not None:
            try:
                driver.save_screenshot(str(DEST / f'storefront-search-{label}-failure.png'))
            except Exception:
                pass
        raise AssertionError(f'Japanese search failed at {label}/{result["stage"]}; see bounded result artifact') from None
    finally:
        (DEST / f'storefront-search-{label}-result.json').write_text(json.dumps(result, ensure_ascii=False) + '\n', encoding='utf-8')
        if driver is not None:
            driver.quit()


def main() -> None:
    validate_isolated_ci_compose_project()
    validate_loopback_shop()
    run_id, attempt = os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT']
    failures = []
    for label, width, height in (("desktop", 1440, 960), ("mobile", 390, 844)):
        try:
            run_viewport(label, width, height, run_id, attempt)
        except Exception:
            failures.append(label)
    if failures:
        raise SystemExit('Japanese search browser QA failed for: ' + ', '.join(failures))


if __name__ == '__main__':
    main()
