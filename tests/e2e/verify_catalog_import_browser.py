#!/usr/bin/env python3
"""Exercise synthetic import and human review in the existing disposable shop.

No source URLs are navigated: they are submitted as text to the guarded adapter.
Only fixed stage labels, numeric IDs and sanitized readback are logged.
"""
from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import zlib
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

from verify_product_admin_browser import (
    ADMIN_LOGIN, ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_PATH, DEST, TAX_RULES_GROUP_ID,
    validate_isolated_ci_compose_project, validate_loopback_admin_targets, visible,
)

AMAZON = 'https://www.amazon.co.jp/dp/B0KURANEA1'
RAKUTEN = 'https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/'
BLOCKED = 'https://www.amazon.co.jp/dp/B0KURANEA2'
ALLOWED_CONTROLLERS = {'AdminKuraneaCatalogReview', 'AdminOrdenowaProductManager'}
ALLOWED_STAGES = {
    'launch', 'login', 'review_menu_route', 'manager_menu_route', 'manager_navigation',
    'batch_review_navigation', 'batch_url_field', 'batch_submit_control', 'batch_submit_click',
    'batch_completion_wait', 'batch_progress_readback', 'reject_rakuten', 'approve_amazon',
    'native_readback', 'reimport_review_navigation', 'reimport_url_field',
    'reimport_submit_control', 'reimport_submit_click', 'reimport_completion_wait',
    'reimport_progress_readback', 'reimport',
}
ALLOWED_EXCEPTION_CLASSES = {
    'AssertionError', 'ElementClickInterceptedException', 'ElementNotInteractableException',
    'NoSuchElementException', 'OSError', 'RuntimeError', 'StaleElementReferenceException',
    'TimeoutException', 'ValueError', 'WebDriverException', 'Exception',
}


def tiny_png(path: Path) -> None:
    """Generate an original opaque 8px PNG without a remote image or library."""
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    pixels = b''.join(b'\x00' + b'\x20\x60\xa0' * 8 for _ in range(8))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 8, 8, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))


def route_link(driver, controller):
    for link in driver.find_elements(By.CSS_SELECTOR, 'a[href*="controller="]'):
        href = link.get_attribute('href') or ''
        parsed = urlparse(href)
        if parse_qs(parsed.query).get('controller') == [controller]:
            if (parsed.scheme, parsed.netloc) != (urlparse(ADMIN_LOGIN).scheme, urlparse(ADMIN_LOGIN).netloc):
                raise AssertionError('admin route escaped disposable shop')
            return href
    return False


def fill(form, name, value):
    field = form.find_element(By.NAME, name)
    field.clear()
    field.send_keys(value)


def article(driver, source_url):
    for entry in driver.find_elements(By.CSS_SELECTOR, 'article[data-catalog-key]'):
        if source_url in entry.text:
            return entry
    return False


def submit_batch(driver, review_url, urls, state, prefix='batch'):
    state['submit_attempted'] = False
    state['submit_returned'] = False
    state['stage'] = f'{prefix}_review_navigation'
    driver.get(review_url)
    state['last_completed_stage'] = state['stage']
    state['stage'] = f'{prefix}_url_field'
    url_field = visible(driver, '#product_urls')
    url_field.send_keys('\n'.join(urls))
    state['last_completed_stage'] = state['stage']
    state['stage'] = f'{prefix}_submit_control'
    submit_button = visible(driver, '[name="submitKuraneaCatalogImportBatch"]')
    state['last_completed_stage'] = state['stage']
    state['stage'] = f'{prefix}_submit_click'
    state['submit_attempted'] = True
    submit_button.click()
    state['submit_returned'] = True
    state['last_completed_stage'] = state['stage']
    state['stage'] = f'{prefix}_completion_wait'
    WebDriverWait(driver, 60).until(lambda d: d.find_elements(
        By.CSS_SELECTOR, '#catalog-import-progress progress[value="' + str(len(urls)) + '"]'))
    state['last_completed_stage'] = state['stage']
    state['stage'] = f'{prefix}_progress_readback'
    progress_text = visible(driver, '#catalog-import-progress').text
    state['last_completed_stage'] = state['stage']
    return progress_text


def safe_catalog_import_browser_state(driver, state):
    """Return only fixed labels, booleans, and bounded counters from the isolated synthetic page."""
    stage = state.get('stage', 'launch')
    last_completed_stage = state.get('last_completed_stage', 'not_started')
    if stage not in ALLOWED_STAGES:
        stage = 'unknown'
    if last_completed_stage not in ALLOWED_STAGES | {'not_started'}:
        last_completed_stage = 'unknown'

    current_url = ''
    if driver is not None:
        try:
            # Take one URL sample for every location-derived field; never serialize the URL or query.
            current_url = driver.current_url
        except Exception:
            current_url = ''
    parsed = urlparse(current_url)
    expected = urlparse(ADMIN_LOGIN)
    current_origin = (parsed.scheme.lower(), parsed.netloc.lower())
    expected_origin = (expected.scheme.lower(), expected.netloc.lower())
    query = parse_qs(parsed.query, keep_blank_values=True)
    controller_parameter_present = 'controller' in query
    controller_value = query.get('controller', [''])[0]
    controller_allowed = controller_value in ALLOWED_CONTROLLERS
    controller = controller_value if controller_value in ALLOWED_CONTROLLERS else (
        'other_admin' if parsed.path.startswith(ADMIN_PATH.rstrip('/') + '/') else 'unknown'
    )
    expected_admin_path = ADMIN_PATH.rstrip('/')
    admin_path_matches = parsed.path == expected_admin_path or parsed.path.startswith(expected_admin_path + '/')

    page = {
        'document_ready_state': 'unknown',
        'login_form_visible': False,
        'product_url_field_visible': False,
        'submit_control_visible': False,
        'progress_visible': False,
        'progress_value': None,
        'progress_max': None,
        'row_count': 0,
        'read_only_notice_visible': False,
        'access_denied_notice_visible': False,
        'queue_unavailable_notice_visible': False,
    }
    if driver is not None:
        try:
            page = driver.execute_script("""
                const visible = (selector) => {
                    const element = document.querySelector(selector);
                    if (!element) return false;
                    const style = getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden'
                        && rect.width > 0 && rect.height > 0;
                };
                const visibleAlerts = Array.from(document.querySelectorAll('.alert'))
                    .filter((element) => {
                        const style = getComputedStyle(element);
                        const rect = element.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden'
                            && rect.width > 0 && rect.height > 0;
                    })
                    .map((element) => element.innerText.trim());
                const progress = document.querySelector('#catalog-import-progress progress');
                const rows = document.querySelectorAll('#catalog-import-progress tbody tr');
                const numberOrNull = (value) => /^\\d{1,6}$/.test(value || '') ? Number(value) : null;
                return {
                    document_ready_state: document.readyState,
                    login_form_visible: visible('#login_form'),
                    product_url_field_visible: visible('#product_urls'),
                    submit_control_visible: visible('[name="submitKuraneaCatalogImportBatch"]'),
                    progress_visible: visible('#catalog-import-progress progress'),
                    progress_value: progress ? numberOrNull(progress.getAttribute('value')) : null,
                    progress_max: progress ? numberOrNull(progress.getAttribute('max')) : null,
                    row_count: Math.min(rows.length, 1000),
                    read_only_notice_visible: visibleAlerts.includes('상품 수집 작업은 편집·등록 권한이 있는 직원만 수행할 수 있습니다.'),
                    access_denied_notice_visible: visibleAlerts.includes('상품 검수 대기열을 조회할 권한이 없습니다.'),
                    queue_unavailable_notice_visible: visibleAlerts.includes('검수 대기열을 불러오지 못했습니다. 저장소 설정을 확인해 주세요.')
                };
            """)
            if not isinstance(page, dict):
                page = {}
        except Exception:
            page = {}

    ready_state = page.get('document_ready_state')
    if ready_state not in {'loading', 'interactive', 'complete'}:
        ready_state = 'unknown'
    progress_value = page.get('progress_value')
    progress_max = page.get('progress_max')
    row_count = page.get('row_count')
    if type(progress_value) is not int or not 0 <= progress_value <= 1_000_000:
        progress_value = None
    if type(progress_max) is not int or not 0 <= progress_max <= 1_000_000:
        progress_max = None
    if type(row_count) is not int or not 0 <= row_count <= 1000:
        row_count = 0

    access_denied = bool(page.get('access_denied_notice_visible'))
    read_only = bool(page.get('read_only_notice_visible'))
    queue_unavailable = bool(page.get('queue_unavailable_notice_visible'))
    if access_denied:
        page_class = 'controller_access_denied'
    elif read_only:
        page_class = 'batch_capability_denied'
    elif queue_unavailable:
        page_class = 'queue_unavailable'
    elif bool(page.get('login_form_visible')):
        page_class = 'login_form'
    elif bool(page.get('product_url_field_visible')):
        page_class = 'catalog_import_form'
    else:
        page_class = 'other_admin'

    return {
        'stage': stage,
        'last_completed_stage': last_completed_stage,
        'same_admin_origin': current_origin == expected_origin,
        'admin_path_matches': admin_path_matches,
        'controller_parameter_present': controller_parameter_present,
        'controller_allowed': controller_allowed,
        'admin_controller': controller,
        'page_class': page_class,
        'document_ready_state': ready_state,
        'login_form_visible': bool(page.get('login_form_visible')),
        'product_url_field_visible': bool(page.get('product_url_field_visible')),
        'submit_control_visible': bool(page.get('submit_control_visible')),
        'submit_attempted': state.get('submit_attempted') is True,
        'submit_returned': state.get('submit_returned') is True,
        'progress_visible': bool(page.get('progress_visible')),
        'progress_value': progress_value,
        'progress_max': progress_max,
        'row_count': row_count,
        'read_only_notice_visible': read_only,
        'access_denied_notice_visible': access_denied,
        'queue_unavailable_notice_visible': queue_unavailable,
    }


def save_safe_failure_screenshot(driver, path):
    """Capture only a fixed, visible status alert; skip pages with dynamic content."""
    safe_messages = {
        '상품 수집 작업은 편집·등록 권한이 있는 직원만 수행할 수 있습니다.',
        '상품 검수 대기열을 조회할 권한이 없습니다.',
        '검수 대기열을 불러오지 못했습니다. 저장소 설정을 확인해 주세요.',
    }
    for alert in driver.find_elements(By.CSS_SELECTOR, '.alert'):
        try:
            if alert.is_displayed() and alert.text.strip() in safe_messages:
                dynamic_children = alert.find_elements(By.CSS_SELECTOR, 'a, input, textarea, table, img')
                if not dynamic_children:
                    return bool(alert.screenshot(str(path)))
        except Exception:
            continue
    return False


def safe_exception_class(error):
    name = type(error).__name__
    return name if name in ALLOWED_EXCEPTION_CLASSES else 'Exception'


def manager_ids(driver):
    ids = []
    for link in driver.find_elements(By.CSS_SELECTOR, 'li.well a[href*="id_product="]'):
        raw = parse_qs(urlparse(link.get_attribute('href')).query).get('id_product', [''])[0]
        if raw.isdecimal():
            ids.append(int(raw))
    return sorted(set(ids))


def read_native(driver, product_id, expected_category_ids):
    assert visible(driver, '[name="id_product"]').get_attribute('value') == str(product_id)
    category_ids = sorted(
        int(box.get_attribute('value'))
        for box in driver.find_elements(By.CSS_SELECTOR, 'input[name="category_ids[]"]')
        if box.is_selected()
    )
    assert category_ids == expected_category_ids
    expected = {'name_en': 'ORDENOWA synthetic kitchen tool', 'name_ko': 'ORDENOWA 합성 주방 도구',
                'description_en': 'Synthetic test data reviewed for English.',
                'description_ko': '한국어 검수를 완료한 합성 테스트 데이터입니다.', 'quantity': '0',
                'tax_rules_group_id': str(TAX_RULES_GROUP_ID), 'price_jpy': '6600'}
    for name, value in expected.items():
        assert driver.find_element(By.NAME, name).get_attribute('value') == value, name
    assert 'M|L' in driver.find_element(By.NAME, 'options').get_attribute('value')
    combinations = driver.find_elements(By.CSS_SELECTOR, 'input[name^="combination_quantities["]')
    assert len(combinations) == 2
    assert [field.get_attribute('value') for field in combinations] == ['7', '7']
    images = driver.find_elements(By.NAME, 'remove_image_ids[]')
    assert len(images) == 1
    image_results = driver.execute_script('return Array.from(document.querySelectorAll(".ordenowa-product-image img")).map(i => ({complete:i.complete,width:i.naturalWidth}))')
    assert len(image_results) == 1 and all(image['complete'] and image['width'] > 0 for image in image_results)
    assert '비활성 · 비노출 · 주문 불가' in driver.find_element(By.TAG_NAME, 'body').text
    return {'linked_product_id': product_id, 'category_ids': category_ids,
            'image_count': len(images), 'combination_count': len(combinations),
            'unique_product_ids': manager_ids(driver)}


def run():
    validate_isolated_ci_compose_project()
    validate_loopback_admin_targets()
    options = Options()
    for flag in ('--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,1200'):
        options.add_argument(flag)
    driver = None
    state = {
        'stage': 'launch',
        'last_completed_stage': 'not_started',
        'submit_attempted': False,
        'submit_returned': False,
    }
    try:
        driver = webdriver.Chrome(options=options)
        state['stage'] = 'login'
        driver.get(ADMIN_LOGIN + '/login')
        visible(driver, '#login_form input[name="email"], input[type="email"]').send_keys(ADMIN_EMAIL)
        visible(driver, '#login_form input[name="passwd"], #login_form input[name="password"], input[type="password"]').send_keys(ADMIN_PASSWORD)
        visible(driver, '#login_form button[type="submit"], #login_form input[type="submit"], button[type="submit"]').click()
        WebDriverWait(driver, 30).until(lambda d: '/login' not in urlparse(d.current_url).path)
        state['last_completed_stage'] = 'login'
        state['stage'] = 'review_menu_route'
        review_url = WebDriverWait(driver, 30).until(lambda d: route_link(d, 'AdminKuraneaCatalogReview'))
        state['last_completed_stage'] = state['stage']
        state['stage'] = 'manager_menu_route'
        manager_url = WebDriverWait(driver, 30).until(lambda d: route_link(d, 'AdminOrdenowaProductManager'))
        state['last_completed_stage'] = state['stage']
        state['stage'] = 'manager_navigation'
        driver.get(manager_url)
        state['last_completed_stage'] = state['stage']
        before_ids = manager_ids(driver)
        status = submit_batch(driver, review_url, [AMAZON, RAKUTEN, BLOCKED], state)
        assert '성공 2건' in status and '실패 1건' in status and '대기 0건' in status
        blocked_row = next(row for row in driver.find_elements(By.CSS_SELECTOR, '#catalog-import-progress tbody tr')
                           if 'B0KURANEA2' in row.text)
        assert '실패' in blocked_row.text and '판매처에서 상품 정보 접근을 제한했습니다.' in blocked_row.text
        driver.save_screenshot(str(DEST / 'catalog-import-batch.png'))
        state['stage'] = 'reject_rakuten'
        rejected = article(driver, RAKUTEN)
        assert rejected
        fill(rejected, 'rejection_reason', 'Synthetic CI rejection: operator declined this fixture.')
        rejected.find_element(By.NAME, 'submitKuraneaCatalogReject').click()
        visible(driver, '[data-catalog-review-status="rejected"]')
        state['last_completed_stage'] = state['stage']
        driver.save_screenshot(str(DEST / 'catalog-import-rejected.png'))
        state['stage'] = 'approve_amazon'
        entry = WebDriverWait(driver, 30).until(lambda d: article(d, AMAZON))
        form = entry.find_element(By.CSS_SELECTOR, '.catalog-import-review-form')
        category_boxes = form.find_elements(By.CSS_SELECTOR, 'input[name="category_ids[]"]')
        if not category_boxes:
            raise AssertionError('No active shop category is available for the synthetic import fixture.')
        first_category = next((box for box in category_boxes if box.is_enabled()), None)
        if first_category is None:
            raise AssertionError('No enabled shop category is available for the synthetic import fixture.')
        if not first_category.is_selected():
            first_category.click()
        expected_category_ids = sorted(
            int(box.get_attribute('value')) for box in category_boxes if box.is_selected()
        )
        if not expected_category_ids:
            raise AssertionError('The synthetic import fixture requires at least one selected category.')
        for name, value in {'name_en': 'ORDENOWA synthetic kitchen tool', 'name_ko': 'ORDENOWA 합성 주방 도구',
                            'description_en': 'Synthetic test data reviewed for English.',
                            'description_ko': '한국어 검수를 완료한 합성 테스트 데이터입니다.',
                            'sale_price_jpy': '6600', 'own_quantity': '7',
                            'tax_evidence_reference': 'CI synthetic taxable fixture; not a legal tax determination',
                            'image_rights_reference': 'CI locally generated original PNG; synthetic fixture only'}.items():
            fill(form, name, value)
        Select(form.find_element(By.NAME, 'tax_rules_group_id')).select_by_value(str(TAX_RULES_GROUP_ID))
        Select(form.find_element(By.NAME, 'tax_treatment')).select_by_value('taxable')
        Select(form.find_element(By.NAME, 'image_rights_basis')).select_by_value('synthetic_ci_fixture')
        for name in ('translation_reviewed_en', 'translation_reviewed_ko', 'confirm_options_supported', 'confirm_image_rights'):
            field = form.find_element(By.NAME, name)
            if not field.is_selected():
                field.click()
        with tempfile.TemporaryDirectory(prefix='ordenowa-import-') as temp:
            image = Path(temp) / 'original-synthetic.png'
            tiny_png(image)
            form.find_element(By.NAME, 'import_product_images[]').send_keys(str(image))
            form.find_element(By.NAME, 'submitKuraneaCatalogImportedDraft').click()
            approved = visible(driver, '[data-catalog-review-status="approved"]')
        state['last_completed_stage'] = state['stage']
        product_link = approved.find_element(By.CSS_SELECTOR, 'a[href*="id_product="]').get_attribute('href')
        product_id = int(parse_qs(urlparse(product_link).query)['id_product'][0])
        state['stage'] = 'native_readback'
        driver.get(product_link)
        readback = read_native(driver, product_id, expected_category_ids)
        assert readback['unique_product_ids'] == sorted(before_ids + [product_id])
        state['last_completed_stage'] = state['stage']
        driver.save_screenshot(str(DEST / 'catalog-import-draft.png'))
        status = submit_batch(driver, review_url, [AMAZON], state, prefix='reimport')
        assert '성공 1건' in status and '실패 0건' in status
        # Identical fixture content remains approved and creates no second review form.
        assert not article(driver, AMAZON)
        state['stage'] = 'reimport'
        state['last_completed_stage'] = state['stage']
        driver.save_screenshot(str(DEST / 'catalog-import-reimport.png'))
        driver.get(product_link)
        after = read_native(driver, product_id, expected_category_ids)
        assert after == readback
        readback['reimport_same_product'] = True
        (DEST / 'catalog-import-readback.json').write_text(json.dumps(readback, sort_keys=True) + '\n')
        print(f'PASS: synthetic batch, rejection, reviewed draft, local image and reimport; linked_product_id={product_id}')
    except Exception as error:
        diagnostics = safe_catalog_import_browser_state(driver, state)
        diagnostics['exception_class'] = safe_exception_class(error)
        if driver is not None:
            try:
                diagnostics['failure_screenshot_captured'] = save_safe_failure_screenshot(
                    driver, DEST / 'catalog-import-failure.png'
                )
            except Exception:
                diagnostics['failure_screenshot_captured'] = False
        else:
            diagnostics['failure_screenshot_captured'] = False
        diagnostics_path = DEST / 'catalog-import-failure-diagnostics.json'
        diagnostics_path.write_text(json.dumps(diagnostics, sort_keys=True) + '\n', encoding='utf-8')
        print('ORDENOWA_CATALOG_IMPORT_SAFE_DIAGNOSTICS=' + json.dumps(diagnostics, sort_keys=True), file=sys.stderr)
        print(
            f"ORDENOWA_CATALOG_IMPORT stage={diagnostics['stage']}; "
            f"last_completed_stage={diagnostics['last_completed_stage']}; "
            f"exception_class={diagnostics['exception_class']}",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    finally:
        if driver is not None:
            driver.quit()


if __name__ == '__main__':
    run()
