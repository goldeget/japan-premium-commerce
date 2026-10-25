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
    ADMIN_LOGIN, ADMIN_EMAIL, ADMIN_PASSWORD, DEST, TAX_RULES_GROUP_ID,
    validate_isolated_ci_compose_project, validate_loopback_admin_targets, visible,
)

AMAZON = 'https://www.amazon.co.jp/dp/B0KURANEA1'
RAKUTEN = 'https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/'
BLOCKED = 'https://www.amazon.co.jp/dp/B0KURANEA2'


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


def submit_batch(driver, review_url, urls):
    driver.get(review_url)
    visible(driver, '#product_urls').send_keys('\n'.join(urls))
    visible(driver, '[name="submitKuraneaCatalogImportBatch"]').click()
    WebDriverWait(driver, 60).until(lambda d: d.find_elements(
        By.CSS_SELECTOR, '#catalog-import-progress progress[value="' + str(len(urls)) + '"]'))
    return visible(driver, '#catalog-import-progress').text


def manager_ids(driver):
    ids = []
    for link in driver.find_elements(By.CSS_SELECTOR, 'li.well a[href*="id_product="]'):
        raw = parse_qs(urlparse(link.get_attribute('href')).query).get('id_product', [''])[0]
        if raw.isdecimal():
            ids.append(int(raw))
    return sorted(set(ids))


def read_native(driver, product_id):
    assert visible(driver, '[name="id_product"]').get_attribute('value') == str(product_id)
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
    return {'linked_product_id': product_id, 'image_count': len(images), 'combination_count': len(combinations),
            'unique_product_ids': manager_ids(driver)}


def run():
    validate_isolated_ci_compose_project()
    validate_loopback_admin_targets()
    options = Options()
    for flag in ('--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,1200'):
        options.add_argument(flag)
    driver = None
    stage = 'launch'
    try:
        driver = webdriver.Chrome(options=options)
        stage = 'login'
        driver.get(ADMIN_LOGIN + '/login')
        visible(driver, '#login_form input[name="email"], input[type="email"]').send_keys(ADMIN_EMAIL)
        visible(driver, '#login_form input[name="passwd"], #login_form input[name="password"], input[type="password"]').send_keys(ADMIN_PASSWORD)
        visible(driver, '#login_form button[type="submit"], #login_form input[type="submit"], button[type="submit"]').click()
        WebDriverWait(driver, 30).until(lambda d: '/login' not in urlparse(d.current_url).path)
        review_url = WebDriverWait(driver, 30).until(lambda d: route_link(d, 'AdminKuraneaCatalogReview'))
        manager_url = WebDriverWait(driver, 30).until(lambda d: route_link(d, 'AdminOrdenowaProductManager'))
        driver.get(manager_url)
        before_ids = manager_ids(driver)
        stage = 'batch'
        status = submit_batch(driver, review_url, [AMAZON, RAKUTEN, BLOCKED])
        assert '성공 2건' in status and '실패 1건' in status and '대기 0건' in status
        blocked_row = next(row for row in driver.find_elements(By.CSS_SELECTOR, '#catalog-import-progress tbody tr')
                           if 'B0KURANEA2' in row.text)
        assert '실패' in blocked_row.text and '판매처에서 상품 정보 접근을 제한했습니다.' in blocked_row.text
        driver.save_screenshot(str(DEST / 'catalog-import-batch.png'))
        stage = 'reject_rakuten'
        rejected = article(driver, RAKUTEN)
        assert rejected
        fill(rejected, 'rejection_reason', 'Synthetic CI rejection: operator declined this fixture.')
        rejected.find_element(By.NAME, 'submitKuraneaCatalogReject').click()
        visible(driver, '[data-catalog-review-status="rejected"]')
        driver.save_screenshot(str(DEST / 'catalog-import-rejected.png'))
        stage = 'approve_amazon'
        entry = WebDriverWait(driver, 30).until(lambda d: article(d, AMAZON))
        form = entry.find_element(By.CSS_SELECTOR, '.catalog-import-review-form')
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
        product_link = approved.find_element(By.CSS_SELECTOR, 'a[href*="id_product="]').get_attribute('href')
        product_id = int(parse_qs(urlparse(product_link).query)['id_product'][0])
        stage = 'native_readback'
        driver.get(product_link)
        readback = read_native(driver, product_id)
        assert readback['unique_product_ids'] == sorted(before_ids + [product_id])
        driver.save_screenshot(str(DEST / 'catalog-import-draft.png'))
        stage = 'reimport'
        status = submit_batch(driver, review_url, [AMAZON])
        assert '성공 1건' in status and '실패 0건' in status
        # Identical fixture content remains approved and creates no second review form.
        assert not article(driver, AMAZON)
        driver.save_screenshot(str(DEST / 'catalog-import-reimport.png'))
        driver.get(product_link)
        after = read_native(driver, product_id)
        assert after == readback
        readback['reimport_same_product'] = True
        (DEST / 'catalog-import-readback.json').write_text(json.dumps(readback, sort_keys=True) + '\n')
        print(f'PASS: synthetic batch, rejection, reviewed draft, local image and reimport; linked_product_id={product_id}')
    except Exception as error:
        if driver is not None and stage != 'login':
            try:
                driver.save_screenshot(str(DEST / 'catalog-import-failure.png'))
            except Exception:
                pass
        print(f'ORDENOWA_CATALOG_IMPORT stage={stage}; exception_class={type(error).__name__}', file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        if driver is not None:
            driver.quit()


if __name__ == '__main__':
    run()
