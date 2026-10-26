#!/usr/bin/env python3
"""Exercise synthetic import and human review in the existing disposable shop.

No source URLs are navigated: they are submitted as text to the guarded adapter.
Only fixed stage labels, numeric IDs and sanitized readback are logged.
"""
from __future__ import annotations

import json
import base64
import os
import re
import struct
import sys
import tempfile
import zlib
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from verify_product_admin_browser import (
    ADMIN_LOGIN, ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_PATH, DEST, TAX_RULES_GROUP_ID,
    validate_isolated_ci_compose_project, validate_loopback_admin_targets, visible,
)

AMAZON = 'https://www.amazon.co.jp/dp/B0KURANEA1'
RAKUTEN = 'https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/'
BLOCKED = 'https://www.amazon.co.jp/dp/B0KURANEA2'
UNSUPPORTED = 'https://example.invalid/not-a-supported-product'
INVALID_URL_NOTICE = '상품 URL을 등록할 수 없습니다. Amazon Japan 또는 Rakuten의 지원 상품 주소를 1~10개 입력해 주세요.'
REJECTED_RAKUTEN_SNAPSHOT_NAME = '[TEST FIXTURE] 合成収納ケース B'
REJECTED_OPTION_GUARD_MESSAGE = (
    '현재 수집기는 여러 옵션 그룹의 실제 조합·조합별 가격·재고를 검증할 수 없어 '
    '이 상품 초안 등록을 지원하지 않습니다. 원본에서 확인된 단일 옵션 그룹만 사용해 주세요.'
)
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
ALLOWED_READBACK_SUBSTAGES = {
    'not_started', 'approved_product_link', 'manager_navigation',
    'native_editor_id_presence', 'native_editor_form_check', 'native_editor_readback',
    'manager_edit_fields', 'manager_edit_save_click', 'manager_edit_save_confirmation',
    'manager_edit_fresh_navigation', 'manager_edit_fresh_readback',
    'reimport_navigation', 'reimport_editor_id_presence', 'reimport_editor_form_check',
    'reimport_editor_readback', 'reject_guard_readback', 'reject_status_readback',
}
ALLOWED_COMPLETED_SUBSTAGES = {
    'not_started', 'batch_complete', 'reject_guard_readback', 'reject_status_readback',
    'manager_edit_fields', 'manager_edit_save_click', 'manager_edit_save_confirmation',
    'manager_edit_fresh_readback', 'unknown',
}
CLICK_TARGETS = {
    'category_checkbox': 'approve_category_checkbox',
    'translation_en_checkbox': 'approve_translation_review_en',
    'translation_ko_checkbox': 'approve_translation_review_ko',
    'options_confirmation_checkbox': 'approve_options_confirmation',
    'image_rights_confirmation_checkbox': 'approve_image_rights_confirmation',
    'native_draft_submit': 'approve_submit',
}
ALLOWED_CLICK_SUBSTAGES = set(CLICK_TARGETS.values()) | {'reject_rakuten_submit'}
ALLOWED_CLICK_RELATIONS = {
    'target', 'target_descendant', 'target_label', 'modal', 'backdrop', 'alert',
    'fixed_navigation', 'other', 'unknown', 'outside_viewport',
}
ALLOWED_OCCLUDER_CATEGORIES = {
    'none', 'label', 'modal', 'modal_backdrop', 'alert', 'fixed_header',
    'fixed_navigation', 'other', 'unknown',
}
ALLOWED_MANAGER_LINK_PATH_CLASSES = {
    'admin_directory', 'admin_directory_slash', 'admin_index_php', 'other', 'unknown',
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


def manager_admin_path_class(path):
    """Classify only the admin directory and the two native legacy entry paths."""
    admin_path = ADMIN_PATH.rstrip('/')
    if admin_path.endswith('/index.php'):
        admin_path = admin_path[:-len('/index.php')]
    if not admin_path or not isinstance(path, str):
        return 'unknown'
    if path == admin_path:
        return 'admin_directory'
    if path == admin_path + '/':
        return 'admin_directory_slash'
    if path == admin_path + '/index.php':
        return 'admin_index_php'
    return 'other'


def safe_manager_link_diagnostics(href):
    """Describe the approved link using only allowlisted booleans and a path class."""
    expected = urlparse(ADMIN_LOGIN)
    try:
        parsed = urlparse(href if isinstance(href, str) else '')
        query = parse_qs(parsed.query, keep_blank_values=True)
        same_origin = (parsed.scheme.lower(), parsed.netloc.lower()) == (
            expected.scheme.lower(), expected.netloc.lower()
        )
        path_class = manager_admin_path_class(parsed.path)
        if parsed.params:
            path_class = 'other'
    except (TypeError, ValueError):
        query = {}
        same_origin = False
        path_class = 'unknown'
    controller_values = query.get('controller', [])
    product_ids = query.get('id_product', [])
    product_id_valid = (
        len(product_ids) == 1 and product_ids[0].isdecimal() and int(product_ids[0]) > 0
    )
    return {
        'manager_link_same_origin': same_origin,
        'manager_link_path_class': path_class,
        'manager_link_path_matches': path_class in {
            'admin_directory', 'admin_directory_slash', 'admin_index_php',
        },
        'manager_link_controller_parameter_present': 'controller' in query,
        'manager_link_controller_matches': controller_values == ['AdminOrdenowaProductManager'],
        'manager_link_product_id_parameter_present': 'id_product' in query,
        'manager_link_product_id_valid': product_id_valid,
    }


def validated_product_id_from_manager_link(href):
    """Accept only a same-origin native admin entry route with one positive product key."""
    diagnostics = safe_manager_link_diagnostics(href)
    if not all((
        diagnostics['manager_link_same_origin'], diagnostics['manager_link_path_matches'],
        diagnostics['manager_link_controller_matches'], diagnostics['manager_link_product_id_valid'],
    )):
        raise AssertionError('approved product manager link did not match the isolated shop route')
    query = parse_qs(urlparse(href).query, keep_blank_values=True)
    product_ids = query['id_product']
    return int(product_ids[0])


def fill(form, name, value):
    field = form.find_element(By.NAME, name)
    field.clear()
    field.send_keys(value)


def article(driver, source_url):
    try:
        entries = driver.find_elements(By.CSS_SELECTOR, 'article[data-catalog-key]')
    except StaleElementReferenceException:
        return False
    for entry in entries:
        try:
            if source_url in entry.text:
                return entry
        except StaleElementReferenceException:
            # A review row can be replaced during the native postback. The caller's
            # existing WebDriverWait will query the new document/card again.
            continue
    return False


def rejection_form_for_source(driver, source_url):
    """Return the separate visible rejection form, retrying through a replaced card."""
    try:
        entry = article(driver, source_url)
        if not entry or not entry.is_displayed():
            return False
        forms = entry.find_elements(By.CSS_SELECTOR, 'form.catalog-review-reject')
        if len(forms) == 1 and forms[0].is_displayed():
            return forms[0]
    except StaleElementReferenceException:
        return False
    return False


def rejected_option_guard_state(driver, source_url):
    """Read fixed feedback and pending-card state without exposing page text."""
    try:
        result = driver.execute_script("""
            const sourceUrl = arguments[0];
            const expectedMessage = arguments[1];
            const visible = (element) => {
                if (!element) return false;
                const style = getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden'
                    && rect.width > 0 && rect.height > 0;
            };
            const card = Array.from(document.querySelectorAll('article[data-catalog-key]'))
                .find((element) => (element.innerText || '').includes(sourceUrl)) || null;
            const guardVisible = Array.from(document.querySelectorAll('#content .alert-danger'))
                .some((element) => visible(element) && element.innerText.trim() === expectedMessage);
            const approvedStatus = document.querySelector('section[data-catalog-review-status="approved"]');
            const productManagerLink = card && card.querySelector('a[href*="id_product="]');
            return {
                review_card_visible: visible(card),
                guard_notice_visible: Boolean(guardVisible),
                review_form_visible: visible(card && card.querySelector('.catalog-import-review-form')),
                approved_status_visible: visible(approvedStatus),
                product_manager_link_visible: visible(productManagerLink)
            };
        """, source_url, REJECTED_OPTION_GUARD_MESSAGE)
    except StaleElementReferenceException:
        return None
    if (not isinstance(result, dict)
            or set(result) != {
                'review_card_visible', 'guard_notice_visible', 'review_form_visible',
                'approved_status_visible', 'product_manager_link_visible',
            }
            or any(type(value) is not bool for value in result.values())):
        return None
    return result


def wait_for_rejected_option_guard(driver, state):
    state['current_substage'] = 'reject_guard_readback'

    def guard_is_ready(current_driver):
        result = rejected_option_guard_state(current_driver, RAKUTEN)
        if (result and result['review_card_visible'] and result['guard_notice_visible']
                and result['review_form_visible'] and not result['approved_status_visible']
                and not result['product_manager_link_visible']):
            return result
        return False

    result = WebDriverWait(driver, 30).until(guard_is_ready)
    state['last_completed_substage'] = 'reject_guard_readback'
    state['current_substage'] = 'not_started'
    return result


def wait_for_rejected_status(driver, state):
    state['current_substage'] = 'reject_status_readback'

    def rejection_is_ready(current_driver):
        try:
            return current_driver.execute_script("""
                const visible = (element) => {
                    if (!element) return false;
                    const style = getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden'
                        && rect.width > 0 && rect.height > 0;
                };
                const statuses = Array.from(document.querySelectorAll(
                    'section[data-catalog-review-status="rejected"]'
                )).filter((element) => {
                    const titleMatches = Array.from(element.querySelectorAll('p'))
                        .some((paragraph) => paragraph.textContent.trim()
                            === `상품명: ${arguments[0]}`);
                    return titleMatches && visible(element);
                });
                return statuses.length === 1;
            """, REJECTED_RAKUTEN_SNAPSHOT_NAME) is True
        except StaleElementReferenceException:
            return False

    WebDriverWait(driver, 30).until(rejection_is_ready)
    state['last_completed_substage'] = 'reject_status_readback'
    state['current_substage'] = 'not_started'


def submit_batch(driver, review_url, urls, state, prefix='batch'):
    state['submit_attempted'] = False
    state['submit_returned'] = False
    state['submitted_url_count'] = 0
    state['current_substage'] = 'not_started'
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
    state['submitted_url_count'] = min(len(urls), 10)
    state['last_completed_stage'] = state['stage']
    state['stage'] = f'{prefix}_completion_wait'
    WebDriverWait(driver, 60).until(lambda d: d.find_elements(
        By.CSS_SELECTOR, '#catalog-import-progress progress[value="' + str(len(urls)) + '"]'))
    state['last_completed_stage'] = state['stage']
    state['stage'] = f'{prefix}_progress_readback'
    progress_text = visible(driver, '#catalog-import-progress').text
    state['last_completed_stage'] = state['stage']
    return progress_text


def reject_unsupported_product_url(driver, review_url, state):
    """Verify the admin rejects unsupported synthetic URLs without storing a batch."""
    state['stage'] = 'batch_review_navigation'
    driver.get(review_url)
    state['last_completed_stage'] = state['stage']
    state['stage'] = 'batch_url_field'
    visible(driver, '#product_urls').send_keys(UNSUPPORTED)
    state['last_completed_stage'] = state['stage']
    state['stage'] = 'batch_submit_control'
    submit_button = visible(driver, '[name="submitKuraneaCatalogImportBatch"]')
    state['last_completed_stage'] = state['stage']
    state['stage'] = 'batch_submit_click'
    state['submit_attempted'] = True
    state['submitted_url_count'] = 1
    submit_button.click()
    state['submit_returned'] = True
    state['last_completed_stage'] = state['stage']
    state['stage'] = 'batch_progress_readback'

    def has_expected_notice(current_driver):
        return any(
            alert.is_displayed() and alert.text.strip() == INVALID_URL_NOTICE
            for alert in current_driver.find_elements(By.CSS_SELECTOR, '.alert.alert-danger')
        )

    WebDriverWait(driver, 20).until(has_expected_notice)
    notice = visible(driver, '.alert.alert-danger').text.strip()
    assert notice == INVALID_URL_NOTICE
    assert 'example.invalid' not in notice
    assert not driver.find_elements(By.ID, 'catalog-import-progress')
    driver.save_screenshot(str(DEST / 'catalog-import-unsupported-url.png'))
    state['last_completed_stage'] = state['stage']


def _safe_rect(value):
    if not isinstance(value, list) or len(value) != 4:
        return None
    if any(type(item) is not int for item in value):
        return None
    if not (-2000 <= value[0] <= 2000 and -2000 <= value[1] <= 2000
            and 0 <= value[2] <= 2000 and 0 <= value[3] <= 2000):
        return None
    return value


def _safe_click_geometry(driver, element):
    """Read only bounded geometry and fixed structural labels; never return DOM identifiers or text."""
    empty = {
        'target_rect': None,
        'occluder_rect': None,
        'visible': False,
        'enabled': False,
        'center_in_viewport': False,
        'center_hit_relation': 'unknown',
        'occluder_category': 'unknown',
    }
    try:
        raw = driver.execute_script("""
        const target = arguments[0];
        const asRect = (rect) => [rect.left, rect.top, rect.width, rect.height]
            .map((value) => Math.max(-2000, Math.min(2000, Math.round(value))));
        const rect = target.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;
        const inViewport = x >= 0 && y >= 0 && x < window.innerWidth && y < window.innerHeight;
        const hit = inViewport ? document.elementFromPoint(x, y) : null;
        const visible = (() => {
            const style = getComputedStyle(target);
            return style.display !== 'none' && style.visibility !== 'hidden'
                && Number(style.opacity) !== 0 && rect.width > 0 && rect.height > 0;
        })();
        let relation = 'unknown';
        let category = 'unknown';
        let blockerRect = null;
        if (!inViewport) {
            relation = 'outside_viewport';
        } else if (hit === target) {
            relation = 'target';
            category = 'none';
        } else if (hit && target.contains(hit)) {
            relation = 'target_descendant';
            category = 'none';
        } else if (hit && hit.closest('label') &&
            (hit.closest('label').control === target || hit.closest('label').contains(target))) {
            relation = 'target_label';
            category = 'label';
            blockerRect = hit.closest('label').getBoundingClientRect();
        } else if (hit) {
            const semanticOverlay = hit.closest('dialog, [role="dialog"], .modal-backdrop, [data-modal-backdrop="true"], [role="alert"], .alert');
            if (semanticOverlay) {
                blockerRect = semanticOverlay.getBoundingClientRect();
                if (semanticOverlay.matches('.modal-backdrop, [data-modal-backdrop="true"]')) {
                    relation = 'backdrop';
                    category = 'modal_backdrop';
                } else if (semanticOverlay.matches('dialog, [role="dialog"]')) {
                    relation = 'modal';
                    category = 'modal';
                } else {
                    relation = 'alert';
                    category = 'alert';
                }
            } else {
                let positioned = hit;
                while (positioned && positioned !== document.documentElement
                    && getComputedStyle(positioned).position !== 'fixed') {
                    positioned = positioned.parentElement;
                }
                if (positioned && positioned !== document.documentElement) {
                    blockerRect = positioned.getBoundingClientRect();
                    const blocker = blockerRect;
                    if (blocker.top + blocker.height / 2 >= window.innerHeight / 2) {
                        relation = 'fixed_navigation';
                        category = 'fixed_navigation';
                    } else {
                        relation = 'other';
                        category = 'fixed_header';
                    }
                } else {
                    relation = 'other';
                    category = 'other';
                    blockerRect = hit.getBoundingClientRect();
                }
            }
        }
        return {
            target_rect: asRect(rect),
            occluder_rect: blockerRect ? asRect(blockerRect) : null,
            visible,
            enabled: !target.disabled,
            center_in_viewport: inViewport,
            center_hit_relation: relation,
            occluder_category: category,
        };
        """, element)
    except Exception:
        try:
            rect = element.rect
            empty.update({
                'target_rect': _safe_rect([
                    round(rect.get('x', 0)), round(rect.get('y', 0)),
                    round(rect.get('width', 0)), round(rect.get('height', 0)),
                ]),
                'visible': element.is_displayed() is True,
                'enabled': element.is_enabled() is True,
            })
        except Exception:
            pass
        return empty
    if not isinstance(raw, dict):
        return empty
    result = {
        'target_rect': _safe_rect(raw.get('target_rect')),
        'occluder_rect': _safe_rect(raw.get('occluder_rect')),
        'visible': raw.get('visible') is True,
        'enabled': raw.get('enabled') is True,
        'center_in_viewport': raw.get('center_in_viewport') is True,
        'center_hit_relation': raw.get('center_hit_relation'),
        'occluder_category': raw.get('occluder_category'),
    }
    if result['center_hit_relation'] not in ALLOWED_CLICK_RELATIONS:
        result['center_hit_relation'] = 'unknown'
    if result['occluder_category'] not in ALLOWED_OCCLUDER_CATEGORIES:
        result['occluder_category'] = 'unknown'
    return result


def click_with_safe_diagnostics(driver, element, state, substage, target):
    """Attempt one native WebDriver click and retain a secret-free obstruction record."""
    if substage not in ALLOWED_CLICK_SUBSTAGES or target not in set(CLICK_TARGETS) | {'rejection_submit'}:
        raise ValueError('catalog import click diagnostic label is invalid')
    state['last_completed_substage'] = state.get('last_completed_substage', 'not_started')
    diagnostic = {
        'substage': substage,
        'target': target,
        'action': 'native_click',
        'attempted': False,
        'returned': False,
        'visible': False,
        'enabled': False,
        'target_rect': None,
        'occluder_rect': None,
        'center_in_viewport': False,
        'center_hit_relation': 'unknown',
        'occluder_category': 'unknown',
    }
    try:
        geometry = _safe_click_geometry(driver, element)
        diagnostic.update(geometry)
    except Exception:
        pass
    state['click_diagnostics'] = diagnostic
    diagnostic['attempted'] = True
    try:
        element.click()
    except Exception:
        try:
            diagnostic.update(_safe_click_geometry(driver, element))
            diagnostic['attempted'] = True
            diagnostic['returned'] = False
            state['click_diagnostics'] = diagnostic
        except Exception:
            pass
        raise
    diagnostic['returned'] = True
    state['click_diagnostics'] = diagnostic
    if target.endswith('_checkbox') and not element.is_selected():
        raise AssertionError('review confirmation checkbox did not become selected')
    state['last_completed_substage'] = substage


def capture_safe_click_crop(driver, path, state):
    """Save only the target/obstruction crop from the isolated synthetic review form."""
    click = state.get('click_diagnostics')
    if not isinstance(click, dict) or not click.get('attempted') or click.get('returned'):
        return False
    current = urlparse(driver.current_url)
    expected = urlparse(ADMIN_LOGIN)
    query = parse_qs(current.query, keep_blank_values=True)
    if ((current.scheme.lower(), current.netloc.lower()) != (expected.scheme.lower(), expected.netloc.lower())
            or not (current.path == ADMIN_PATH.rstrip('/')
                    or current.path.startswith(ADMIN_PATH.rstrip('/') + '/'))
            or query.get('controller') != ['AdminKuraneaCatalogReview']):
        return False
    source_url = state.get('review_source', AMAZON) if isinstance(state, dict) else AMAZON
    if source_url not in {AMAZON, RAKUTEN}:
        return False
    synthetic_entry = article(driver, source_url)
    forms = synthetic_entry.find_elements(By.CSS_SELECTOR, '.catalog-import-review-form') if synthetic_entry else []
    if len(forms) != 1 or not forms[0].is_displayed():
        return False
    target_fields = {
        'category_checkbox': 'category_ids[]',
        'translation_en_checkbox': 'translation_reviewed_en',
        'translation_ko_checkbox': 'translation_reviewed_ko',
        'options_confirmation_checkbox': 'confirm_options_supported',
        'image_rights_confirmation_checkbox': 'confirm_image_rights',
        'native_draft_submit': 'submitKuraneaCatalogImportedDraft',
    }
    target_field_name = target_fields.get(click.get('target'))
    if target_field_name is None or not any(
        field.is_displayed() for field in forms[0].find_elements(By.NAME, target_field_name)
    ):
        return False
    target = click.get('target_rect')
    blocker = click.get('occluder_rect')
    if not _safe_rect(target):
        return False
    viewport = driver.execute_script(
        'return {width: window.innerWidth, height: window.innerHeight, '
        'scrollX: Math.round(window.scrollX), scrollY: Math.round(window.scrollY)};'
    )
    if not isinstance(viewport, dict):
        return False
    width = viewport.get('width')
    height = viewport.get('height')
    scroll_x = viewport.get('scrollX')
    scroll_y = viewport.get('scrollY')
    if (type(width) is not int or type(height) is not int
            or not (0 < width <= 2000 and 0 < height <= 2000)
            or type(scroll_x) is not int or type(scroll_y) is not int
            or not (0 <= scroll_x <= 1_000_000 and 0 <= scroll_y <= 1_000_000)):
        return False
    rects = [target]
    if _safe_rect(blocker):
        rects.append(blocker)
    left = max(0, min(rect[0] for rect in rects) - 12)
    top = max(0, min(rect[1] for rect in rects) - 12)
    right = min(width, max(rect[0] + rect[2] for rect in rects) + 12)
    bottom = min(height, max(rect[1] + rect[3] for rect in rects) + 220)
    if right - left > 640:
        center_x = target[0] + target[2] // 2
        left = max(0, min(width - 640, center_x - 320))
        right = min(width, left + 640)
    if bottom - top > 480:
        center_y = target[1] + target[3] // 2
        top = max(0, min(height - 480, center_y - 240))
        bottom = min(height, top + 480)
    if right <= left or bottom <= top:
        return False
    screenshot = driver.execute_cdp_cmd('Page.captureScreenshot', {
        'format': 'png',
        'fromSurface': True,
        'captureBeyondViewport': True,
        'clip': {
            # getBoundingClientRect() and the click diagnostics are viewport-relative;
            # Page.captureScreenshot clips in document coordinates.
            'x': left + scroll_x,
            'y': top + scroll_y,
            'width': right - left,
            'height': bottom - top,
            'scale': 1,
        },
    })
    image_data = screenshot.get('data') if isinstance(screenshot, dict) else None
    if not isinstance(image_data, str):
        return False
    image = base64.b64decode(image_data, validate=True)
    if not image.startswith(b'\x89PNG\r\n\x1a\n'):
        return False
    if len(image) < 24:
        return False
    image_width, image_height = struct.unpack('!II', image[16:24])
    if image_width < 320 or image_height < 180 or image_width > 640 or image_height > 480:
        return False
    path.write_bytes(image)
    return path.is_file() and path.stat().st_size > 0


def capture_safe_option_guard_notice(driver, path, state):
    """Capture only the exact synthetic multigroup-option server guard message."""
    try:
        if (not isinstance(state, dict) or state.get('stage') != 'reject_rakuten'
                or state.get('review_source') != RAKUTEN):
            return False
        parsed = urlparse(driver.current_url)
        expected = urlparse(ADMIN_LOGIN)
        query = parse_qs(parsed.query, keep_blank_values=True)
        admin_path = ADMIN_PATH.rstrip('/')
        if ((parsed.scheme.lower(), parsed.netloc.lower()) != (
                expected.scheme.lower(), expected.netloc.lower())
                or not (parsed.path == admin_path or parsed.path.startswith(admin_path + '/'))
                or query.get('controller') != ['AdminKuraneaCatalogReview']):
            return False

        entry = article(driver, RAKUTEN)
        if not entry or not entry.is_displayed():
            return False
        forms = entry.find_elements(By.CSS_SELECTOR, '.catalog-import-review-form')
        notices = driver.find_elements(By.CSS_SELECTOR, '#content .alert-danger')
        matching_notices = [notice for notice in notices
                            if notice.is_displayed()
                            and notice.text.strip() == REJECTED_OPTION_GUARD_MESSAGE]
        if (len(forms) != 1 or not forms[0].is_displayed() or len(matching_notices) != 1
                or entry.find_elements(By.CSS_SELECTOR, '[data-catalog-review-status="approved"]')
                or entry.find_elements(By.CSS_SELECTOR, 'a[href*="id_product="]')):
            return False

        notice = matching_notices[0]
        original_style = notice.get_attribute('style')
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", notice)
        driver.execute_script("""
            const notice = arguments[0];
            notice.style.boxSizing = 'border-box';
            notice.style.width = '640px';
            notice.style.maxWidth = '640px';
            notice.style.minHeight = '180px';
            notice.style.height = 'auto';
            notice.style.padding = '24px';
            notice.style.whiteSpace = 'normal';
            notice.style.overflowWrap = 'anywhere';
            notice.style.overflow = 'visible';
        """, notice)
        try:
            bounds = notice.size
            if (type(bounds.get('width')) is not int or type(bounds.get('height')) is not int
                    or not (320 <= bounds['width'] <= 640 and 180 <= bounds['height'] <= 480)):
                return False
            if not notice.screenshot(str(path)) or not path.is_file() or path.stat().st_size == 0:
                return False
            image = path.read_bytes()
            if len(image) < 24 or not image.startswith(b'\x89PNG\r\n\x1a\n'):
                path.unlink(missing_ok=True)
                return False
            width, height = struct.unpack('!II', image[16:24])
            if not (320 <= width <= 640 and 180 <= height <= 480):
                path.unlink(missing_ok=True)
                return False
            return True
        finally:
            if original_style:
                driver.execute_script("arguments[0].setAttribute('style', arguments[1]);", notice, original_style)
            else:
                driver.execute_script("arguments[0].removeAttribute('style');", notice)
    except Exception:
        return False


def capture_safe_approval_context_crop(driver, path, state, source_url=AMAZON):
    """Capture only the known synthetic option field and its blocking/confirmation UI."""
    expected_stage = 'approve_amazon' if source_url == AMAZON else 'reject_rakuten'
    if source_url not in {AMAZON, RAKUTEN} or not isinstance(state, dict):
        return False
    if state.get('stage') != expected_stage:
        return False
    try:
        parsed = urlparse(driver.current_url)
        expected = urlparse(ADMIN_LOGIN)
        query = parse_qs(parsed.query, keep_blank_values=True)
        admin_path = ADMIN_PATH.rstrip('/')
        same_origin = (parsed.scheme.lower(), parsed.netloc.lower()) == (
            expected.scheme.lower(), expected.netloc.lower()
        )
        admin_path_matches = parsed.path == admin_path or parsed.path.startswith(admin_path + '/')
        if not (same_origin and admin_path_matches
                and query.get('controller') == ['AdminKuraneaCatalogReview']):
            return False

        entry = article(driver, source_url)
        if not entry or not entry.is_displayed():
            return False
        forms = entry.find_elements(By.CSS_SELECTOR, '.catalog-import-review-form')
        if len(forms) != 1 or not forms[0].is_displayed():
            return False
        form = forms[0]
        option_fields = form.find_elements(By.NAME, 'options')
        warnings = form.find_elements(By.CSS_SELECTOR, '.alert-warning')
        confirmations = form.find_elements(By.NAME, 'confirm_options_supported')
        if len(option_fields) != 1 or not option_fields[0].is_displayed():
            return False
        option_value = option_fields[0].get_attribute('value')
        if source_url == RAKUTEN:
            if (option_value != '色:生成り\n容量:12L' or len(warnings) != 1 or confirmations
                    or warnings[0].text.strip() != (
                        '현재 수집기는 여러 옵션 그룹 사이의 실제 판매 조합·조합별 가격·재고를 '
                        '확인하지 못합니다. 이 상품은 옵션 연결을 지원하지 않아 초안 등록이 차단됩니다.'
                    )):
                return False
            context = warnings[0]
        else:
            if option_value != 'サイズ:M|L' or warnings or len(confirmations) != 1:
                return False
            context = driver.execute_script(
                "return arguments[0].closest('.form-group') || arguments[0].closest('label') || arguments[0];",
                confirmations[0],
            )
            if context is None:
                return False

        # Bring the relevant part into view before reading viewport-relative rects.
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
            option_fields[0],
        )
        geometry = driver.execute_script("""
            const rect = (element) => {
                const value = element.getBoundingClientRect();
                return [value.left + window.scrollX, value.top + window.scrollY,
                        value.width, value.height]
                    .map((part) => Math.round(part));
            };
            const visible = (element) => {
                const style = getComputedStyle(element);
                const value = element.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden'
                    && Number(style.opacity) !== 0 && value.width > 0 && value.height > 0;
            };
            return {
                width: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
                height: Math.max(document.documentElement.scrollHeight, document.body.scrollHeight),
                scrollX: Math.round(window.scrollX),
                scrollY: Math.round(window.scrollY),
                optionRect: rect(arguments[0]),
                contextRect: rect(arguments[1]),
                optionVisible: visible(arguments[0]),
                contextVisible: visible(arguments[1]),
            };
        """, option_fields[0], context)
        if not isinstance(geometry, dict):
            return False
        document_width = geometry.get('width')
        document_height = geometry.get('height')
        scroll_x = geometry.get('scrollX')
        scroll_y = geometry.get('scrollY')
        option_rect = geometry.get('optionRect')
        context_rect = geometry.get('contextRect')
        if (type(document_width) is not int or type(document_height) is not int
                or not (320 <= document_width <= 10000 and 180 <= document_height <= 50000)
                or type(scroll_x) is not int or type(scroll_y) is not int
                or not (0 <= scroll_x <= 1_000_000 and 0 <= scroll_y <= 1_000_000)
                or geometry.get('optionVisible') is not True
                or geometry.get('contextVisible') is not True
                or not _safe_document_rect(option_rect, document_width, document_height)
                or not _safe_document_rect(context_rect, document_width, document_height)):
            return False

        rects = [option_rect, context_rect]
        left = max(0, min(rect[0] for rect in rects) - 20)
        top = max(0, min(rect[1] for rect in rects) - 20)
        right = min(document_width, max(rect[0] + rect[2] for rect in rects) + 20)
        bottom = min(document_height, max(rect[1] + rect[3] for rect in rects) + 20)
        if right - left > 640:
            left = max(0, min(document_width - 640, min(rect[0] for rect in rects) - 12))
            right = min(document_width, left + 640)
        if bottom - top > 480:
            center_y = (min(rect[1] for rect in rects) + max(
                rect[1] + rect[3] for rect in rects
            )) // 2
            top = max(0, min(document_height - 480, center_y - 240))
            bottom = min(document_height, top + 480)
        if right - left < 320 or bottom - top < 180:
            center_x = option_rect[0] + option_rect[2] // 2
            center_y = option_rect[1] + option_rect[3] // 2
            left = max(0, min(document_width - 320, center_x - 160))
            top = max(0, min(document_height - 180, center_y - 90))
            right = min(document_width, left + 320)
            bottom = min(document_height, top + 180)
        if (right - left < 320 or bottom - top < 180
                or right - left > 640 or bottom - top > 480):
            return False

        screenshot = driver.execute_cdp_cmd('Page.captureScreenshot', {
            'format': 'png',
            'fromSurface': True,
            'captureBeyondViewport': True,
            'clip': {
                'x': left,
                'y': top,
                'width': right - left,
                'height': bottom - top,
                'scale': 1,
            },
        })
        image_data = screenshot.get('data') if isinstance(screenshot, dict) else None
        if not isinstance(image_data, str):
            return False
        image = base64.b64decode(image_data, validate=True)
        if len(image) < 24 or not image.startswith(b'\x89PNG\r\n\x1a\n'):
            return False
        image_width, image_height = struct.unpack('!II', image[16:24])
        if image_width < 320 or image_height < 180 or image_width > 640 or image_height > 480:
            return False
        path.write_bytes(image)
        return path.is_file() and path.stat().st_size > 0
    except Exception:
        return False


def _safe_document_rect(value, width, height):
    if not isinstance(value, list) or len(value) != 4:
        return False
    if any(type(item) is not int for item in value):
        return False
    x, y, rect_width, rect_height = value
    return (0 <= x <= width and 0 <= y <= height
            and 0 < rect_width <= width and 0 < rect_height <= height
            and x + rect_width <= width and y + rect_height <= height)


def safe_catalog_import_browser_state(driver, state):
    """Return only fixed labels, booleans, and bounded counters from the isolated synthetic page."""
    stage = state.get('stage', 'launch')
    last_completed_stage = state.get('last_completed_stage', 'not_started')
    last_completed_substage = state.get('last_completed_substage', 'not_started')
    if stage not in ALLOWED_STAGES:
        stage = 'unknown'
    if last_completed_stage not in ALLOWED_STAGES | {'not_started'}:
        last_completed_stage = 'unknown'
    if last_completed_substage not in ALLOWED_CLICK_SUBSTAGES | ALLOWED_COMPLETED_SUBSTAGES:
        last_completed_substage = 'unknown'
    current_substage = state.get('current_substage', 'not_started')
    if current_substage not in ALLOWED_READBACK_SUBSTAGES:
        current_substage = 'unknown'

    raw_click = state.get('click_diagnostics')
    click_diagnostics = None
    if isinstance(raw_click, dict):
        candidate = {
            'substage': raw_click.get('substage'),
            'target': raw_click.get('target'),
            'action': raw_click.get('action'),
            'attempted': raw_click.get('attempted') is True,
            'returned': raw_click.get('returned') is True,
            'visible': raw_click.get('visible') is True,
            'enabled': raw_click.get('enabled') is True,
            'target_rect': _safe_rect(raw_click.get('target_rect')),
            'occluder_rect': _safe_rect(raw_click.get('occluder_rect')),
            'center_in_viewport': raw_click.get('center_in_viewport') is True,
            'center_hit_relation': raw_click.get('center_hit_relation'),
            'occluder_category': raw_click.get('occluder_category'),
        }
        if (candidate['substage'] in ALLOWED_CLICK_SUBSTAGES
                and candidate['target'] in set(CLICK_TARGETS) | {'rejection_submit'}
                and candidate['action'] == 'native_click'):
            if candidate['center_hit_relation'] not in ALLOWED_CLICK_RELATIONS:
                candidate['center_hit_relation'] = 'unknown'
            if candidate['occluder_category'] not in ALLOWED_OCCLUDER_CATEGORIES:
                candidate['occluder_category'] = 'unknown'
            click_diagnostics = candidate

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
    link_diagnostics = state.get('manager_link_diagnostics')
    if not isinstance(link_diagnostics, dict):
        link_diagnostics = {}
    manager_link_path_class = link_diagnostics.get('manager_link_path_class')
    if manager_link_path_class not in ALLOWED_MANAGER_LINK_PATH_CLASSES:
        manager_link_path_class = 'unknown'
    controller_parameter_present = 'controller' in query
    controller_value = query.get('controller', [''])[0]
    controller_allowed = controller_value in ALLOWED_CONTROLLERS
    controller = controller_value if controller_value in ALLOWED_CONTROLLERS else (
        'other_admin' if parsed.path.startswith(ADMIN_PATH.rstrip('/') + '/') else 'unknown'
    )
    expected_admin_path = ADMIN_PATH.rstrip('/')
    admin_path_matches = parsed.path == expected_admin_path or parsed.path.startswith(expected_admin_path + '/')
    manager_route_matches = (
        current_origin == expected_origin
        and not parsed.params
        and manager_admin_path_class(parsed.path) in {
            'admin_directory', 'admin_directory_slash', 'admin_index_php',
        }
        and query.get('controller') == ['AdminOrdenowaProductManager']
    )
    expected_product_id = state.get('native_product_id')
    expected_product_id_text = str(expected_product_id) if type(expected_product_id) is int and expected_product_id > 0 else ''
    query_product_ids = query.get('id_product', [])
    manager_product_id_parameter_present = 'id_product' in query
    manager_product_id_parameter_matches = (
        expected_product_id_text != '' and query_product_ids == [expected_product_id_text]
    )

    page = {
        'document_ready_state': 'unknown',
        'login_form_visible': False,
        'product_url_field_visible': False,
        'submit_control_visible': False,
        'batch_progress_container_visible': False,
        'progress_visible': False,
        'progress_value': None,
        'progress_max': None,
        'row_count': 0,
        'token_rejected_notice_visible': False,
        'mutation_access_denied_notice_visible': False,
        'invalid_url_notice_visible': False,
        'empty_url_notice_visible': False,
        'batch_save_failure_notice_visible': False,
        'batch_created_notice_visible': False,
        'visible_alert_count': 0,
        'document_response_status': None,
        'read_only_notice_visible': False,
        'access_denied_notice_visible': False,
        'queue_unavailable_notice_visible': False,
        'manager_id_field_present': False,
        'manager_id_field_hidden': False,
        'manager_product_id_field_matches': False,
        'manager_editor_visible': False,
        'manager_load_failure_notice_visible': False,
        'manager_permission_denied_notice_visible': False,
        'manager_inactive_notice_visible': False,
        'manager_save_success_notice_visible': False,
        'option_guard_notice_visible': False,
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
                const navigation = performance.getEntriesByType('navigation')[0];
                const responseStatus = navigation && Number.isInteger(navigation.responseStatus)
                    && navigation.responseStatus >= 100 && navigation.responseStatus <= 599
                    ? navigation.responseStatus : null;
                const managerForm = Array.from(document.querySelectorAll('#content form')).find(
                    (form) => form.querySelector('[name="submitKuraneaProductSave"]')) || null;
                const managerSaveButton = managerForm
                    ? managerForm.querySelector('[name="submitKuraneaProductSave"]') : null;
                const managerIdField = managerForm
                    ? managerForm.querySelector('input[name="id_product"]') : null;
                const visibleElement = (element) => {
                    if (!element) return false;
                    const style = getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden'
                        && rect.width > 0 && rect.height > 0;
                };
                const managerFormVisible = Boolean(managerForm && visibleElement(managerForm)
                    && visibleElement(managerSaveButton));
                const expectedProductId = arguments[0];
                const managerLoadFailure = '상품 관리 화면을 불러오지 못했습니다. 쇼핑몰 설정과 권한을 확인해 주세요.';
                const managerPermissionDenied = '상품을 조회할 권한이 없습니다.';
                const managerInactiveNotice = '상품은 기본적으로 비활성·비노출·주문 불가 상태로 저장됩니다. 이 화면에는 판매 활성화 기능이 없습니다.';
                const managerSaveSuccessNotice = expectedProductId
                    ? `상품 ID ${expectedProductId}를 비활성 상태로 저장했습니다.` : '';
                const optionGuardNotice = '현재 수집기는 여러 옵션 그룹의 실제 조합·조합별 가격·재고를 검증할 수 없어 이 상품 초안 등록을 지원하지 않습니다. 원본에서 확인된 단일 옵션 그룹만 사용해 주세요.';
                const invalidUrlNotice = '상품 URL을 등록할 수 없습니다. Amazon Japan 또는 Rakuten의 지원 상품 주소를 1~10개 입력해 주세요.';
                const recognizedAlert = (text) => text === '관리자 보안 토큰이 올바르지 않습니다. 페이지를 새로고침한 후 다시 시도해 주세요.'
                    || text === '상품 수집·검수·등록 권한이 없습니다.'
                    || text === invalidUrlNotice
                    || text === '상품 URL을 한 줄에 하나씩 입력해 주세요.'
                    || text === '상품 URL 일괄 등록을 저장하지 못했습니다. URL과 저장 공간을 확인해 주세요.'
                    || text === '상품 수집 작업은 편집·등록 권한이 있는 직원만 수행할 수 있습니다.'
                    || text === '상품 검수 대기열을 조회할 권한이 없습니다.'
                    || text === '검수 대기열을 불러오지 못했습니다. 저장소 설정을 확인해 주세요.'
                    || text === managerLoadFailure
                    || text === managerPermissionDenied
                    || text === managerInactiveNotice
                    || (managerSaveSuccessNotice && text === managerSaveSuccessNotice)
                    || text === optionGuardNotice
                    || text === '상품 수집 항목을 반려했습니다. 사유와 담당자 기록을 보존했습니다.'
                    || text === '기존 TEST/DEMO 등록 경로는 별도 서버 게이트로 비활성화되어 있습니다.'
                    || /^(?:[1-9]|10)개 고유 상품 URL을 수집 대기열에 추가했습니다[.]$/.test(text);
                const numberOrNull = (value) => /^[0-9]{1,6}$/.test(value || '') ? Number(value) : null;
                return {
                    document_ready_state: document.readyState,
                    login_form_visible: visible('#login_form'),
                    product_url_field_visible: visible('#product_urls'),
                    submit_control_visible: visible('[name="submitKuraneaCatalogImportBatch"]'),
                    batch_progress_container_visible: visible('#catalog-import-progress'),
                    progress_visible: visible('#catalog-import-progress progress'),
                    progress_value: progress ? numberOrNull(progress.getAttribute('value')) : null,
                    progress_max: progress ? numberOrNull(progress.getAttribute('max')) : null,
                    row_count: Math.min(rows.length, 1000),
                    token_rejected_notice_visible: visibleAlerts.includes('관리자 보안 토큰이 올바르지 않습니다. 페이지를 새로고침한 후 다시 시도해 주세요.'),
                    mutation_access_denied_notice_visible: visibleAlerts.includes('상품 수집·검수·등록 권한이 없습니다.'),
                    invalid_url_notice_visible: visibleAlerts.includes(invalidUrlNotice),
                    empty_url_notice_visible: visibleAlerts.includes('상품 URL을 한 줄에 하나씩 입력해 주세요.'),
                    batch_save_failure_notice_visible: visibleAlerts.includes('상품 URL 일괄 등록을 저장하지 못했습니다. URL과 저장 공간을 확인해 주세요.'),
                    batch_created_notice_visible: visibleAlerts.some((text) => /^(?:[1-9]|10)개 고유 상품 URL을 수집 대기열에 추가했습니다[.]$/.test(text)),
                    unclassified_alert_visible: visibleAlerts.some((text) => !recognizedAlert(text)),
                    visible_alert_count: Math.min(visibleAlerts.length, 20),
                    document_response_status: responseStatus,
                    read_only_notice_visible: visibleAlerts.includes('상품 수집 작업은 편집·등록 권한이 있는 직원만 수행할 수 있습니다.'),
                    access_denied_notice_visible: visibleAlerts.includes('상품 검수 대기열을 조회할 권한이 없습니다.'),
                    queue_unavailable_notice_visible: visibleAlerts.includes('검수 대기열을 불러오지 못했습니다. 저장소 설정을 확인해 주세요.'),
                    manager_id_field_present: Boolean(managerIdField),
                    manager_id_field_hidden: Boolean(managerIdField && managerIdField.type === 'hidden'),
                    manager_product_id_field_matches: Boolean(managerIdField && expectedProductId
                        && managerIdField.value === expectedProductId),
                    manager_editor_visible: managerFormVisible,
                    manager_load_failure_notice_visible: visibleAlerts.includes(managerLoadFailure),
                    manager_permission_denied_notice_visible: visibleAlerts.includes(managerPermissionDenied),
                    manager_inactive_notice_visible: visibleAlerts.includes(managerInactiveNotice),
                    manager_save_success_notice_visible: visibleAlerts.includes(managerSaveSuccessNotice),
                    option_guard_notice_visible: visibleAlerts.includes(optionGuardNotice)
                };
            """, expected_product_id_text)
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
    visible_alert_count = page.get('visible_alert_count')
    response_status = page.get('document_response_status')
    if type(progress_value) is not int or not 0 <= progress_value <= 1_000_000:
        progress_value = None
    if type(progress_max) is not int or not 0 <= progress_max <= 1_000_000:
        progress_max = None
    if type(row_count) is not int or not 0 <= row_count <= 1000:
        row_count = 0
    if type(visible_alert_count) is not int or not 0 <= visible_alert_count <= 20:
        visible_alert_count = 0
    if type(response_status) is not int or not 100 <= response_status <= 599:
        response_status = None

    access_denied = bool(page.get('access_denied_notice_visible'))
    read_only = bool(page.get('read_only_notice_visible'))
    queue_unavailable = bool(page.get('queue_unavailable_notice_visible'))
    token_rejected = bool(page.get('token_rejected_notice_visible'))
    mutation_access_denied = bool(page.get('mutation_access_denied_notice_visible'))
    invalid_url_notice = bool(page.get('invalid_url_notice_visible'))
    batch_save_failed = bool(page.get('batch_save_failure_notice_visible'))
    batch_created = bool(page.get('batch_created_notice_visible'))
    unclassified_alert = bool(page.get('unclassified_alert_visible'))
    manager_load_failure = bool(page.get('manager_load_failure_notice_visible'))
    manager_permission_denied = bool(page.get('manager_permission_denied_notice_visible'))
    if manager_route_matches and manager_permission_denied:
        page_class = 'manager_access_denied'
    elif manager_route_matches and manager_load_failure:
        page_class = 'manager_load_error'
    elif manager_route_matches and bool(page.get('manager_editor_visible')):
        page_class = 'manager_editor'
    elif manager_route_matches and unclassified_alert:
        page_class = 'unclassified_alert'
    elif manager_route_matches:
        page_class = 'manager_editor_missing'
    elif access_denied:
        page_class = 'controller_access_denied'
    elif read_only:
        page_class = 'batch_capability_denied'
    elif queue_unavailable:
        page_class = 'queue_unavailable'
    elif token_rejected:
        page_class = 'mutation_token_rejected'
    elif mutation_access_denied:
        page_class = 'mutation_capability_denied'
    elif invalid_url_notice:
        page_class = 'invalid_url_rejected'
    elif batch_save_failed:
        page_class = 'batch_save_error'
    elif batch_created and not bool(page.get('batch_progress_container_visible')):
        page_class = 'batch_created_without_progress'
    elif bool(page.get('option_guard_notice_visible')):
        page_class = 'unsupported_options_guard'
    elif unclassified_alert:
        page_class = 'unclassified_alert'
    elif bool(page.get('login_form_visible')):
        page_class = 'login_form'
    elif bool(page.get('product_url_field_visible')):
        page_class = 'catalog_import_form'
    else:
        page_class = 'other_admin'

    return {
        'stage': stage,
        'last_completed_stage': last_completed_stage,
        'last_completed_substage': last_completed_substage,
        'current_substage': current_substage,
        'click_diagnostics': click_diagnostics,
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
        'submitted_url_count': state.get('submitted_url_count') if type(state.get('submitted_url_count')) is int else 0,
        'batch_progress_container_visible': bool(page.get('batch_progress_container_visible')),
        'progress_visible': bool(page.get('progress_visible')),
        'progress_value': progress_value,
        'progress_max': progress_max,
        'row_count': row_count,
        'token_rejected_notice_visible': token_rejected,
        'mutation_access_denied_notice_visible': mutation_access_denied,
        'invalid_url_notice_visible': invalid_url_notice,
        'empty_url_notice_visible': bool(page.get('empty_url_notice_visible')),
        'batch_save_failure_notice_visible': batch_save_failed,
        'batch_created_notice_visible': batch_created,
        'option_guard_notice_visible': bool(page.get('option_guard_notice_visible')),
        'unclassified_alert_visible': unclassified_alert,
        'visible_alert_count': visible_alert_count,
        'document_response_status': response_status,
        'read_only_notice_visible': read_only,
        'access_denied_notice_visible': access_denied,
        'queue_unavailable_notice_visible': queue_unavailable,
        'manager_route_matches': manager_route_matches,
        'manager_product_id_parameter_present': manager_product_id_parameter_present,
        'manager_product_id_parameter_matches': manager_product_id_parameter_matches,
        'manager_link_same_origin': link_diagnostics.get('manager_link_same_origin') is True,
        'manager_link_path_class': manager_link_path_class,
        'manager_link_path_matches': link_diagnostics.get('manager_link_path_matches') is True,
        'manager_link_controller_parameter_present': (
            link_diagnostics.get('manager_link_controller_parameter_present') is True
        ),
        'manager_link_controller_matches': (
            link_diagnostics.get('manager_link_controller_matches') is True
        ),
        'manager_link_product_id_parameter_present': (
            link_diagnostics.get('manager_link_product_id_parameter_present') is True
        ),
        'manager_link_product_id_valid': link_diagnostics.get('manager_link_product_id_valid') is True,
        'manager_id_field_present': bool(page.get('manager_id_field_present')),
        'manager_id_field_hidden': bool(page.get('manager_id_field_hidden')),
        'manager_product_id_field_matches': bool(page.get('manager_product_id_field_matches')),
        'manager_editor_visible': bool(page.get('manager_editor_visible')),
        'manager_load_failure_notice_visible': manager_load_failure,
        'manager_permission_denied_notice_visible': manager_permission_denied,
        'manager_inactive_notice_visible': bool(page.get('manager_inactive_notice_visible')),
        'manager_save_success_notice_visible': bool(page.get('manager_save_success_notice_visible')),
    }


def capture_safe_manager_readback_crop(driver, path, state):
    """Capture one allowlisted manager notice without surrounding product fields."""
    try:
        if not isinstance(state, dict) or state.get('stage') != 'native_readback':
            return False
        expected_id = state.get('native_product_id')
        if type(expected_id) is not int or expected_id <= 0:
            return False

        parsed = urlparse(driver.current_url)
        expected = urlparse(ADMIN_LOGIN)
        query = parse_qs(parsed.query, keep_blank_values=True)
        same_origin = (parsed.scheme.lower(), parsed.netloc.lower()) == (
            expected.scheme.lower(), expected.netloc.lower()
        )
        admin_path_matches = not parsed.params and manager_admin_path_class(parsed.path) in {
            'admin_directory', 'admin_directory_slash', 'admin_index_php',
        }
        if (not same_origin or not admin_path_matches
                or query.get('controller') != ['AdminOrdenowaProductManager']):
            return False

        query_id_matches = query.get('id_product') == [str(expected_id)]
        postback_id_fields = driver.find_elements(By.CSS_SELECTOR, '#content form input[name="id_product"]')
        postback_id_matches = (
            len(postback_id_fields) == 1
            and postback_id_fields[0].get_attribute('type') == 'hidden'
            and postback_id_fields[0].get_attribute('value') == str(expected_id)
        )
        route_id_matches = (
            query_id_matches if 'id_product' in query else postback_id_matches
        )
        if not route_id_matches:
            return False

        safe_messages = {
            '상품 관리 화면을 불러오지 못했습니다. 쇼핑몰 설정과 권한을 확인해 주세요.',
            '상품을 조회할 권한이 없습니다.',
            '상품 저장에 실패했습니다. 입력값, 이미지 파일 및 PrestaShop 상품 설정을 확인해 주세요.',
        }
        notice = next((element for element in driver.find_elements(By.CSS_SELECTOR, '#content .alert-danger')
                       if element.is_displayed() and element.text.strip() in safe_messages), None)
        if notice is None:
            forms = driver.find_elements(By.CSS_SELECTOR, '#content form')
            form = next((candidate for candidate in forms
                         if candidate.is_displayed()
                         and candidate.find_elements(By.NAME, 'submitKuraneaProductSave')), None)
            if form is None:
                return False
            panel = form.find_element(By.XPATH, './ancestor::section[contains(@class,"panel")]')
            heading = panel.find_element(By.TAG_NAME, 'h3')
            notice = panel.find_element(By.CSS_SELECTOR, '.alert-info')
            if (heading.text.strip() != '상품 수정'
                    or notice.text.strip() != (
                        '상품은 기본적으로 비활성·비노출·주문 불가 상태로 저장됩니다. '
                        '이 화면에는 판매 활성화 기능이 없습니다.'
                    )):
                return False

        original_style = notice.get_attribute('style')
        driver.execute_script("""
            const notice = arguments[0];
            notice.style.boxSizing = 'border-box';
            notice.style.width = '640px';
            notice.style.maxWidth = '640px';
            notice.style.minHeight = '180px';
            notice.style.padding = '24px';
            notice.style.display = 'flex';
            notice.style.alignItems = 'center';
        """, notice)
        try:
            bounds = notice.size
            if (type(bounds.get('width')) is not int or type(bounds.get('height')) is not int
                    or not (320 <= bounds['width'] <= 640 and 180 <= bounds['height'] <= 480)):
                return False
            return bool(notice.screenshot(str(path))) and path.is_file() and path.stat().st_size > 0
        finally:
            if original_style:
                driver.execute_script("arguments[0].setAttribute('style', arguments[1]);", notice, original_style)
            else:
                driver.execute_script("arguments[0].removeAttribute('style');", notice)
    except Exception:
        return False


def save_safe_failure_screenshot(driver, path, state):
    """Capture synthetic batch progress, a fixed alert, or a scrubbed import form crop."""
    stage = state.get('stage', 'unknown') if isinstance(state, dict) else 'unknown'
    click = state.get('click_diagnostics') if isinstance(state, dict) else None
    if stage == 'native_readback':
        return capture_safe_manager_readback_crop(driver, path, state)
    if stage in {'approve_amazon', 'reject_rakuten'}:
        source_url = RAKUTEN if stage == 'reject_rakuten' else AMAZON
        if stage == 'reject_rakuten':
            try:
                if capture_safe_option_guard_notice(driver, path, state):
                    return True
            except Exception:
                pass
            if (isinstance(click, dict) and click.get('target') == 'native_draft_submit'
                    and click.get('returned') is True):
                # After the guard-form POST, a pre-submit screenshot would not be
                # evidence of the server response. Require the exact fixed notice.
                return False
        if (isinstance(click, dict) and click.get('attempted') is True
                and click.get('returned') is False):
            try:
                if capture_safe_click_crop(driver, path, state):
                    return True
            except Exception:
                pass
        try:
            return capture_safe_approval_context_crop(driver, path, state, source_url)
        except Exception:
            return False

    safe_route = False
    form = None
    try:
        parsed = urlparse(driver.current_url)
        expected = urlparse(ADMIN_LOGIN)
        query = parse_qs(parsed.query, keep_blank_values=True)
        admin_path = ADMIN_PATH.rstrip('/')
        same_origin = (parsed.scheme.lower(), parsed.netloc.lower()) == (
            expected.scheme.lower(), expected.netloc.lower()
        )
        admin_path_matches = parsed.path == admin_path or parsed.path.startswith(admin_path + '/')
        safe_route = same_origin and admin_path_matches and query.get('controller') == ['AdminKuraneaCatalogReview']

        if safe_route and stage in {'batch_completion_wait', 'reimport_completion_wait'}:
            progress_panel = driver.find_element(By.ID, 'catalog-import-progress')
            if progress_panel.is_displayed():
                unsafe_elements = progress_panel.find_elements(
                    By.CSS_SELECTOR, 'a, img, select, iframe, canvas, svg, video, object, [contenteditable="true"]'
                )
                fields = progress_panel.find_elements(By.CSS_SELECTOR, 'input, textarea')
                fields_are_safe = all(field.get_attribute('name') in {'token', 'catalog_batch_id'} for field in fields)
                if not unsafe_elements and fields_are_safe:
                    driver.execute_script("""
                        for (const field of arguments[0].querySelectorAll('input, textarea')) {
                            field.value = '';
                            field.textContent = '';
                            field.removeAttribute('value');
                        }
                        for (const form of arguments[0].querySelectorAll('form')) {
                            form.style.visibility = 'hidden';
                        }
                    """, progress_panel)
                    scrubbed = driver.execute_script("""
                        const fields = Array.from(arguments[0].querySelectorAll('input, textarea'));
                        const forms = Array.from(arguments[0].querySelectorAll('form'));
                        return fields.every((field) => field.value === '' && !field.hasAttribute('value'))
                            && forms.every((form) => getComputedStyle(form).visibility === 'hidden');
                    """, progress_panel)
                    if scrubbed is True:
                        return bool(progress_panel.screenshot(str(path)))
    except Exception:
        pass

    safe_messages = {
        '관리자 보안 토큰이 올바르지 않습니다. 페이지를 새로고침한 후 다시 시도해 주세요.',
        '상품 수집·검수·등록 권한이 없습니다.',
        INVALID_URL_NOTICE,
        '상품 URL을 한 줄에 하나씩 입력해 주세요.',
        '상품 URL 일괄 등록을 저장하지 못했습니다. URL과 저장 공간을 확인해 주세요.',
        '상품 수집 작업은 편집·등록 권한이 있는 직원만 수행할 수 있습니다.',
        '상품 검수 대기열을 조회할 권한이 없습니다.',
        '검수 대기열을 불러오지 못했습니다. 저장소 설정을 확인해 주세요.',
        '상품 수집 항목을 반려했습니다. 사유와 담당자 기록을 보존했습니다.',
        '기존 TEST/DEMO 등록 경로는 별도 서버 게이트로 비활성화되어 있습니다.',
    }
    if safe_route:
        for alert in driver.find_elements(By.CSS_SELECTOR, '.alert'):
            try:
                alert_text = alert.text.strip()
                safe_batch_created_notice = re.fullmatch(
                    r'(?:[1-9]|10)개 고유 상품 URL을 수집 대기열에 추가했습니다\.', alert_text
                ) is not None
                if alert.is_displayed() and (alert_text in safe_messages or safe_batch_created_notice):
                    dynamic_children = alert.find_elements(By.CSS_SELECTOR, 'a, input, textarea, table, img')
                    if not dynamic_children:
                        return bool(alert.screenshot(str(path)))
            except Exception:
                continue

    if safe_route:
        try:
            url_field = driver.find_element(By.ID, 'product_urls')
            form = url_field.find_element(By.XPATH, './ancestor::form')
            if form.is_displayed():
                fields = form.find_elements(By.CSS_SELECTOR, 'input, textarea')
                fields_are_safe = all(field.get_attribute('name') in {'token', 'product_urls'} for field in fields)
                dynamic_elements = form.find_elements(
                    By.CSS_SELECTOR, 'a, table, img, select, iframe, canvas, svg, video, object, [contenteditable="true"]'
                )
                if not fields_are_safe or dynamic_elements:
                    return False
                driver.execute_script("""
                    for (const field of arguments[0].querySelectorAll('input, textarea')) {
                        field.value = '';
                        field.textContent = '';
                        field.removeAttribute('value');
                    }
                """, form)
                cleared = driver.execute_script("""
                    return Array.from(arguments[0].querySelectorAll('input, textarea'))
                        .every((field) => field.value === '' && !field.hasAttribute('value'));
                """, form)
                if cleared is True:
                    return bool(form.screenshot(str(path)))
        except Exception:
            pass
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


def read_native(
    driver, product_id, expected_category_ids, state, *, phase='initial', expected_fields=None,
    expected_combination_quantities=None, expected_image_ids=None, expected_combination_field_names=None,
):
    phase_substages = {
        'initial': ('manager_navigation', 'native_editor_form_check', 'native_editor_id_presence', 'native_editor_readback'),
        'manager_edit': (
            'manager_edit_fresh_navigation', 'manager_edit_fresh_readback',
            'manager_edit_fresh_readback', 'manager_edit_fresh_readback',
        ),
        'reimport': ('reimport_navigation', 'reimport_editor_form_check', 'reimport_editor_id_presence', 'reimport_editor_readback'),
    }
    if phase not in phase_substages:
        raise ValueError('unknown imported product readback phase')
    navigation_substage, form_substage, id_substage, values_substage = phase_substages[phase]
    state['current_substage'] = navigation_substage
    assert validated_product_id_from_manager_link(driver.current_url) == product_id
    state['current_substage'] = form_substage
    save_button = WebDriverWait(driver, 30).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, '#content form [name="submitKuraneaProductSave"]'))
    )
    manager_form = save_button.find_element(By.XPATH, './ancestor::form')
    assert manager_form.is_displayed()
    state['current_substage'] = id_substage
    id_fields = manager_form.find_elements(By.NAME, 'id_product')
    assert len(id_fields) == 1
    id_field = id_fields[0]
    state['current_substage'] = values_substage
    state['manager_product_id_field_matches'] = id_field.get_attribute('value') == str(product_id)
    assert state['manager_product_id_field_matches']
    manager_page = safe_catalog_import_browser_state(driver, state)
    for field in (
        'manager_route_matches', 'manager_product_id_parameter_matches',
        'manager_id_field_present', 'manager_product_id_field_matches', 'manager_editor_visible',
    ):
        assert manager_page[field], field
    assert manager_page['page_class'] == 'manager_editor'
    assert not manager_page['manager_load_failure_notice_visible']
    assert not manager_page['manager_permission_denied_notice_visible']
    category_ids = sorted(
        int(box.get_attribute('value'))
        for box in driver.find_elements(By.CSS_SELECTOR, 'input[name="category_ids[]"]')
        if box.is_selected()
    )
    assert category_ids == expected_category_ids
    form_values = {
        name: driver.find_element(By.NAME, name).get_attribute('value')
        for name in (
            'name_ja', 'name_en', 'name_ko', 'description_ja', 'description_en',
            'description_ko', 'quantity', 'tax_rules_group_id', 'price_jpy',
        )
    }
    expected = {
        'name_ja': '[TEST FIXTURE] 合成キッチンツール A',
        'name_en': 'ORDENOWA synthetic kitchen tool', 'name_ko': 'ORDENOWA 합성 주방 도구',
        'description_ja': '合成データです。Amazon または実在商品から取得した情報ではありません。',
        'description_en': 'Synthetic test data reviewed for English.',
        'description_ko': '한국어 검수를 완료한 합성 테스트 데이터입니다.', 'quantity': '0',
        'tax_rules_group_id': str(TAX_RULES_GROUP_ID), 'price_jpy': '6600',
    }
    if expected_fields is not None:
        expected.update(expected_fields)
    for name, value in expected.items():
        assert form_values[name] == value, name
    option_values = driver.find_element(By.NAME, 'options').get_attribute('value')
    assert 'M|L' in option_values
    combinations = driver.find_elements(By.CSS_SELECTOR, 'input[name^="combination_quantities["]')
    assert len(combinations) == 2
    combination_quantity_values = [field.get_attribute('value') for field in combinations]
    if expected_combination_quantities is None:
        expected_combination_quantities = ['7', '7']
    assert combination_quantity_values == expected_combination_quantities
    combination_field_names = sorted(field.get_attribute('name') for field in combinations)
    if expected_combination_field_names is not None:
        assert combination_field_names == expected_combination_field_names
    images = driver.find_elements(By.NAME, 'remove_image_ids[]')
    assert len(images) == 1
    image_ids = sorted(field.get_attribute('value') for field in images)
    if expected_image_ids is not None:
        assert image_ids == expected_image_ids
    image_results = driver.execute_script('return Array.from(document.querySelectorAll(".ordenowa-product-image img")).map(i => ({complete:i.complete,width:i.naturalWidth}))')
    assert len(image_results) == 1 and all(image['complete'] and image['width'] > 0 for image in image_results)
    assert '비활성 · 비노출 · 주문 불가' in driver.find_element(By.TAG_NAME, 'body').text
    return {'linked_product_id': product_id, 'category_ids': category_ids, 'form_values': form_values,
            'option_values': option_values, 'combination_quantity_values': combination_quantity_values,
            '_combination_field_names': combination_field_names, '_image_ids': image_ids,
            'image_identity_preserved': expected_image_ids is None or image_ids == expected_image_ids,
            'combination_identity_preserved': (
                expected_combination_field_names is None or combination_field_names == expected_combination_field_names
            ),
            'image_count': len(images), 'combination_count': len(combinations),
            'unique_product_ids': manager_ids(driver),
            'manager_page': {
                'same_admin_origin': manager_page['same_admin_origin'],
                'admin_path_matches': manager_page['admin_path_matches'],
                'controller': manager_page['admin_controller'],
                'route_matches': manager_page['manager_route_matches'],
                'query_id_matches': manager_page['manager_product_id_parameter_matches'],
                'approved_link_same_origin': manager_page['manager_link_same_origin'],
                'approved_link_path_class': manager_page['manager_link_path_class'],
                'approved_link_path_matches': manager_page['manager_link_path_matches'],
                'approved_link_controller_matches': manager_page['manager_link_controller_matches'],
                'approved_link_product_id_valid': manager_page['manager_link_product_id_valid'],
                'id_field_present': manager_page['manager_id_field_present'],
                'id_field_hidden': manager_page['manager_id_field_hidden'],
                'id_field_matches': manager_page['manager_product_id_field_matches'],
                'editor_visible': manager_page['manager_editor_visible'],
                'inactive_notice_visible': manager_page['manager_inactive_notice_visible'],
                'unclassified_alert_visible': manager_page['unclassified_alert_visible'],
            }}


def manager_save_confirmation(browser, expected_notice):
    """Read visible save alerts from one DOM snapshot so a postback cannot stale element handles."""
    return browser.execute_script("""
        const expectedNotice = arguments[0];
        const isVisible = (element) => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden'
                && rect.width > 0 && rect.height > 0;
        };
        return Array.from(document.querySelectorAll('#content .alert-success')).some((element) => {
            const notice = (element.innerText || element.textContent || '').trim();
            return isVisible(element) && notice === expectedNotice;
        });
    """, expected_notice) is True


def edit_imported_draft(driver, manager_link, product_id, expected_category_ids, initial_readback, state):
    """Save synthetic manager edits to the linked inactive draft and verify a new GET."""
    expected_fields = {
        'name_en': 'ORDENOWA synthetic kitchen tool edited',
        'name_ko': 'ORDENOWA 합성 주방 도구 수정',
        'description_ko': '관리자에서 저장한 합성 설명입니다.',
        'price_jpy': '6780',
    }
    expected_combination_quantities = ['5', '5']
    state['current_substage'] = 'manager_edit_fields'
    save_button = visible(driver, '#content form [name="submitKuraneaProductSave"]')
    form = save_button.find_element(By.XPATH, './ancestor::form')
    id_fields = form.find_elements(By.NAME, 'id_product')
    assert len(id_fields) == 1 and id_fields[0].get_attribute('value') == str(product_id)
    assert form.find_element(By.NAME, 'options').get_attribute('value') == initial_readback['option_values']
    assert 'M|L' in initial_readback['option_values']
    category_ids = sorted(
        int(box.get_attribute('value'))
        for box in form.find_elements(By.CSS_SELECTOR, 'input[name="category_ids[]"]')
        if box.is_selected()
    )
    assert category_ids == expected_category_ids
    image_controls = form.find_elements(By.NAME, 'remove_image_ids[]')
    assert len(image_controls) == 1 and not any(field.is_selected() for field in image_controls)
    fill(form, 'name_en', expected_fields['name_en'])
    fill(form, 'name_ko', expected_fields['name_ko'])
    fill(form, 'description_ko', expected_fields['description_ko'])
    fill(form, 'price_jpy', expected_fields['price_jpy'])
    assert form.find_element(By.NAME, 'quantity').get_attribute('value') == '0'
    assert form.find_element(By.NAME, 'tax_rules_group_id').get_attribute('value') == str(TAX_RULES_GROUP_ID)
    combination_fields = form.find_elements(By.CSS_SELECTOR, 'input[name^="combination_quantities["]')
    assert len(combination_fields) == len(expected_combination_quantities) == 2
    for field, quantity in zip(combination_fields, expected_combination_quantities, strict=True):
        field.clear()
        field.send_keys(quantity)
    assert [field.get_attribute('value') for field in combination_fields] == expected_combination_quantities
    state['last_completed_substage'] = 'manager_edit_fields'

    state['current_substage'] = 'manager_edit_save_click'
    state['manager_product_id_field_matches'] = id_fields[0].get_attribute('value') == str(product_id)
    assert state['manager_product_id_field_matches']
    save_button.click()
    state['last_completed_substage'] = 'manager_edit_save_click'

    state['current_substage'] = 'manager_edit_save_confirmation'
    expected_notice = f'상품 ID {product_id}를 비활성 상태로 저장했습니다.'

    assert WebDriverWait(driver, 45).until(
        lambda browser: manager_save_confirmation(browser, expected_notice)
    )
    state['last_completed_substage'] = 'manager_edit_save_confirmation'

    state['manager_link_diagnostics'] = safe_manager_link_diagnostics(manager_link)
    assert validated_product_id_from_manager_link(manager_link) == product_id
    state['current_substage'] = 'manager_edit_fresh_navigation'
    driver.get(manager_link)
    state['native_product_id'] = product_id
    fresh_readback = read_native(
        driver, product_id, expected_category_ids, state, phase='manager_edit',
        expected_fields=expected_fields,
        expected_combination_quantities=expected_combination_quantities,
        expected_image_ids=initial_readback['_image_ids'],
        expected_combination_field_names=initial_readback['_combination_field_names'],
    )
    assert fresh_readback['option_values'] == initial_readback['option_values']
    assert fresh_readback['image_identity_preserved']
    assert fresh_readback['combination_identity_preserved']
    assert fresh_readback['unique_product_ids'] == initial_readback['unique_product_ids']
    state['last_completed_substage'] = 'manager_edit_fresh_readback'
    driver.save_screenshot(str(DEST / 'catalog-import-manager-edited.png'))
    return fresh_readback


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
        'last_completed_substage': 'not_started',
        'current_substage': 'not_started',
        'click_diagnostics': None,
        'manager_link_diagnostics': None,
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
        reject_unsupported_product_url(driver, review_url, state)
        before_ids = manager_ids(driver)
        status = submit_batch(driver, review_url, [AMAZON, RAKUTEN, BLOCKED], state)
        assert '성공 2건' in status and '실패 1건' in status and '대기 0건' in status
        blocked_row = next(row for row in driver.find_elements(By.CSS_SELECTOR, '#catalog-import-progress tbody tr')
                           if 'B0KURANEA2' in row.text)
        assert '실패' in blocked_row.text and '판매처에서 상품 정보 접근을 제한했습니다.' in blocked_row.text
        driver.save_screenshot(str(DEST / 'catalog-import-batch.png'))
        state['stage'] = 'reject_rakuten'
        state['review_source'] = RAKUTEN
        rejected = article(driver, RAKUTEN)
        assert rejected
        rejected_form = rejected.find_element(By.CSS_SELECTOR, '.catalog-import-review-form')
        rejected_options = rejected_form.find_element(By.NAME, 'options')
        assert rejected_options.get_attribute('value') == '色:生成り\n容量:12L'
        rejected_warnings = rejected_form.find_elements(By.CSS_SELECTOR, '.alert-warning')
        assert len(rejected_warnings) == 1
        assert '옵션 연결을 지원하지 않아 초안 등록이 차단됩니다.' in rejected_warnings[0].text
        options_confirmations = rejected_form.find_elements(By.NAME, 'confirm_options_supported')
        assert not options_confirmations
        assert capture_safe_approval_context_crop(
            driver, DEST / 'catalog-import-blocked-options.png', state, RAKUTEN
        )

        for name, value in {
            'name_en': 'Synthetic Rakuten storage case',
            'name_ko': '합성 라쿠텐 수납 케이스',
            'description_en': 'Synthetic negative option fixture; no real product data.',
            'description_ko': '실제 상품 정보가 아닌 합성 다중 옵션 차단 fixture입니다.',
        }.items():
            fill(rejected_form, name, value)
        for name, substage, target in (
            ('translation_reviewed_en', 'approve_translation_review_en', 'translation_en_checkbox'),
            ('translation_reviewed_ko', 'approve_translation_review_ko', 'translation_ko_checkbox'),
        ):
            field = rejected_form.find_element(By.NAME, name)
            if not field.is_selected():
                click_with_safe_diagnostics(driver, field, state, substage, target)
        fill(rejected_form, 'sale_price_jpy', '2480')
        Select(rejected_form.find_element(By.NAME, 'tax_rules_group_id')).select_by_value(str(TAX_RULES_GROUP_ID))
        Select(rejected_form.find_element(By.NAME, 'tax_treatment')).select_by_value('taxable')
        fill(rejected_form, 'tax_evidence_reference', 'CI synthetic fixture; not a legal tax determination')
        fill(rejected_form, 'own_quantity', '7')
        rejected_categories = rejected_form.find_elements(By.CSS_SELECTOR, 'input[name="category_ids[]"]')
        assert rejected_categories
        rejected_category = next((box for box in rejected_categories if box.is_enabled()), None)
        assert rejected_category is not None
        if not rejected_category.is_selected():
            click_with_safe_diagnostics(
                driver, rejected_category, state, 'approve_category_checkbox', 'category_checkbox'
            )
        click_with_safe_diagnostics(
            driver,
            rejected_form.find_element(By.NAME, 'submitKuraneaCatalogImportedDraft'),
            state,
            'reject_rakuten_submit',
            'native_draft_submit',
        )
        guard_state = wait_for_rejected_option_guard(driver, state)
        assert guard_state['review_card_visible']
        assert guard_state['guard_notice_visible']
        assert guard_state['review_form_visible']
        assert not guard_state['approved_status_visible']
        assert not guard_state['product_manager_link_visible']
        assert capture_safe_option_guard_notice(
            driver, DEST / 'catalog-import-blocked-submit.png', state
        )
        rejected_form = WebDriverWait(driver, 30).until(lambda d: rejection_form_for_source(d, RAKUTEN))

        fill(rejected_form, 'rejection_reason', 'Synthetic CI rejection: operator declined this fixture.')
        state['current_substage'] = 'reject_status_readback'
        rejected_form.find_element(By.NAME, 'submitKuraneaCatalogReject').click()
        wait_for_rejected_status(driver, state)
        state['last_completed_stage'] = state['stage']
        state['last_completed_substage'] = 'reject_status_readback'
        driver.save_screenshot(str(DEST / 'catalog-import-rejected.png'))
        state['stage'] = 'approve_amazon'
        state['review_source'] = AMAZON
        state['click_diagnostics'] = None
        entry = WebDriverWait(driver, 30).until(lambda d: article(d, AMAZON))
        form = entry.find_element(By.CSS_SELECTOR, '.catalog-import-review-form')
        for name, value in {
            'name_en': 'ORDENOWA synthetic kitchen tool',
            'name_ko': 'ORDENOWA 합성 주방 도구',
            'description_en': 'Synthetic test data reviewed for English.',
            'description_ko': '한국어 검수를 완료한 합성 테스트 데이터입니다.',
        }.items():
            fill(form, name, value)
        translation_confirmations = {
            'translation_reviewed_en': ('approve_translation_review_en', 'translation_en_checkbox'),
            'translation_reviewed_ko': ('approve_translation_review_ko', 'translation_ko_checkbox'),
        }
        for name, (substage, target) in translation_confirmations.items():
            field = form.find_element(By.NAME, name)
            if not field.is_selected():
                click_with_safe_diagnostics(driver, field, state, substage, target)
            else:
                state['last_completed_substage'] = substage

        fill(form, 'sale_price_jpy', '6600')
        Select(form.find_element(By.NAME, 'tax_rules_group_id')).select_by_value(str(TAX_RULES_GROUP_ID))
        Select(form.find_element(By.NAME, 'tax_treatment')).select_by_value('taxable')
        fill(form, 'tax_evidence_reference', 'CI synthetic taxable fixture; not a legal tax determination')
        fill(form, 'own_quantity', '7')

        category_boxes = form.find_elements(By.CSS_SELECTOR, 'input[name="category_ids[]"]')
        if not category_boxes:
            raise AssertionError('No active shop category is available for the synthetic import fixture.')
        first_category = next((box for box in category_boxes if box.is_enabled()), None)
        if first_category is None:
            raise AssertionError('No enabled shop category is available for the synthetic import fixture.')
        if not first_category.is_selected():
            click_with_safe_diagnostics(
                driver, first_category, state, 'approve_category_checkbox', 'category_checkbox'
            )
        else:
            state['last_completed_substage'] = 'approve_category_checkbox'
        expected_category_ids = sorted(
            int(box.get_attribute('value')) for box in category_boxes if box.is_selected()
        )
        if not expected_category_ids:
            raise AssertionError('The synthetic import fixture requires at least one selected category.')

        options_field = form.find_element(By.NAME, 'options')
        assert options_field.get_attribute('value') == 'サイズ:M|L'
        options_confirmation = form.find_element(By.NAME, 'confirm_options_supported')
        assert options_confirmation.is_displayed() and options_confirmation.is_enabled()
        if not options_confirmation.is_selected():
            click_with_safe_diagnostics(
                driver, options_confirmation, state,
                'approve_options_confirmation', 'options_confirmation_checkbox'
            )
        else:
            state['last_completed_substage'] = 'approve_options_confirmation'
        assert options_confirmation.is_selected()
        assert capture_safe_approval_context_crop(
            driver, DEST / 'catalog-import-review-options.png', state, AMAZON
        )
        with tempfile.TemporaryDirectory(prefix='ordenowa-import-') as temp:
            image = Path(temp) / 'original-synthetic.png'
            tiny_png(image)
            form.find_element(By.NAME, 'import_product_images[]').send_keys(str(image))
            Select(form.find_element(By.NAME, 'image_rights_basis')).select_by_value('synthetic_ci_fixture')
            fill(form, 'image_rights_reference', 'CI locally generated original PNG; synthetic fixture only')
            rights_confirmation = form.find_element(By.NAME, 'confirm_image_rights')
            if not rights_confirmation.is_selected():
                click_with_safe_diagnostics(
                    driver, rights_confirmation, state,
                    'approve_image_rights_confirmation', 'image_rights_confirmation_checkbox'
                )
            else:
                state['last_completed_substage'] = 'approve_image_rights_confirmation'
            click_with_safe_diagnostics(
                driver,
                form.find_element(By.NAME, 'submitKuraneaCatalogImportedDraft'),
                state,
                'approve_submit',
                'native_draft_submit',
            )
            approved = visible(driver, '[data-catalog-review-status="approved"]')
        state['last_completed_stage'] = state['stage']
        product_link = approved.find_element(By.CSS_SELECTOR, 'a[href*="id_product="]').get_attribute('href')
        state['stage'] = 'native_readback'
        state['current_substage'] = 'approved_product_link'
        state['manager_link_diagnostics'] = safe_manager_link_diagnostics(product_link)
        product_id = validated_product_id_from_manager_link(product_link)
        state['current_substage'] = 'approved_product_link'
        state['native_product_id'] = product_id
        state['current_substage'] = 'manager_navigation'
        driver.get(product_link)
        readback = read_native(driver, product_id, expected_category_ids, state)
        assert readback['unique_product_ids'] == sorted(before_ids + [product_id])
        state['last_completed_stage'] = state['stage']
        driver.save_screenshot(str(DEST / 'catalog-import-draft.png'))
        edited_readback = edit_imported_draft(
            driver, product_link, product_id, expected_category_ids, readback, state
        )
        state['last_completed_stage'] = state['stage']
        readback = edited_readback
        status = submit_batch(driver, review_url, [AMAZON], state, prefix='reimport')
        assert '성공 1건' in status and '실패 0건' in status
        # Identical fixture content remains approved and creates no second review form.
        assert not article(driver, AMAZON)
        state['stage'] = 'reimport'
        state['last_completed_stage'] = state['stage']
        driver.save_screenshot(str(DEST / 'catalog-import-reimport.png'))
        state['stage'] = 'native_readback'
        state['native_product_id'] = product_id
        state['current_substage'] = 'reimport_navigation'
        driver.get(product_link)
        after = read_native(
            driver, product_id, expected_category_ids, state, phase='reimport',
            expected_fields=readback['form_values'],
            expected_combination_quantities=readback['combination_quantity_values'],
            expected_image_ids=readback['_image_ids'],
            expected_combination_field_names=readback['_combination_field_names'],
        )
        assert {key: value for key, value in after.items() if key != 'manager_page'} == {
            key: value for key, value in readback.items() if key != 'manager_page'
        }
        readback['reimport_same_product'] = True
        readback['reimport_preserved_manager_edits'] = True
        readback['manager_edit'] = {
            'save_confirmation_observed': True,
            'fresh_get_readback': True,
            'same_product_id': after['linked_product_id'] == product_id,
            'fields': readback['form_values'],
            'option_values': readback['option_values'],
            'combination_quantity_values': readback['combination_quantity_values'],
            'image_count': readback['image_count'],
            'image_identity_preserved': readback['image_identity_preserved'],
            'combination_identity_preserved': readback['combination_identity_preserved'],
            'inactive_notice_visible': readback['manager_page']['inactive_notice_visible'],
        }
        readback.pop('_image_ids')
        readback.pop('_combination_field_names')
        (DEST / 'catalog-import-readback.json').write_text(json.dumps(readback, sort_keys=True) + '\n')
        print('PASS: synthetic batch, rejection, manager edit save, fresh readback and edit-preserving reimport.')
    except Exception as error:
        diagnostics = safe_catalog_import_browser_state(driver, state)
        diagnostics['exception_class'] = safe_exception_class(error)
        if driver is not None:
            try:
                diagnostics['failure_screenshot_captured'] = save_safe_failure_screenshot(
                    driver, DEST / 'catalog-import-failure.png', state
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
            f"last_completed_substage={diagnostics['last_completed_substage']}; "
            f"exception_class={diagnostics['exception_class']}",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    finally:
        if driver is not None:
            driver.quit()


if __name__ == '__main__':
    run()
