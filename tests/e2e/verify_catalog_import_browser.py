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
    state['submitted_url_count'] = 0
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
    synthetic_entry = article(driver, AMAZON)
    if not synthetic_entry or not synthetic_entry.find_elements(By.CSS_SELECTOR, '.catalog-import-review-form'):
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


def safe_catalog_import_browser_state(driver, state):
    """Return only fixed labels, booleans, and bounded counters from the isolated synthetic page."""
    stage = state.get('stage', 'launch')
    last_completed_stage = state.get('last_completed_stage', 'not_started')
    last_completed_substage = state.get('last_completed_substage', 'not_started')
    if stage not in ALLOWED_STAGES:
        stage = 'unknown'
    if last_completed_stage not in ALLOWED_STAGES | {'not_started'}:
        last_completed_stage = 'unknown'
    if last_completed_substage not in ALLOWED_CLICK_SUBSTAGES | {'not_started', 'batch_complete', 'reject_status_readback', 'unknown'}:
        last_completed_substage = 'unknown'

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
        'batch_progress_container_visible': False,
        'progress_visible': False,
        'progress_value': None,
        'progress_max': None,
        'row_count': 0,
        'token_rejected_notice_visible': False,
        'mutation_access_denied_notice_visible': False,
        'empty_url_notice_visible': False,
        'batch_save_failure_notice_visible': False,
        'batch_created_notice_visible': False,
        'visible_alert_count': 0,
        'document_response_status': None,
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
                const navigation = performance.getEntriesByType('navigation')[0];
                const responseStatus = navigation && Number.isInteger(navigation.responseStatus)
                    && navigation.responseStatus >= 100 && navigation.responseStatus <= 599
                    ? navigation.responseStatus : null;
                const recognizedAlert = (text) => text === '관리자 보안 토큰이 올바르지 않습니다. 페이지를 새로고침한 후 다시 시도해 주세요.'
                    || text === '상품 수집·검수·등록 권한이 없습니다.'
                    || text === '상품 URL을 한 줄에 하나씩 입력해 주세요.'
                    || text === '상품 URL 일괄 등록을 저장하지 못했습니다. URL과 저장 공간을 확인해 주세요.'
                    || text === '상품 수집 작업은 편집·등록 권한이 있는 직원만 수행할 수 있습니다.'
                    || text === '상품 검수 대기열을 조회할 권한이 없습니다.'
                    || text === '검수 대기열을 불러오지 못했습니다. 저장소 설정을 확인해 주세요.'
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
                    empty_url_notice_visible: visibleAlerts.includes('상품 URL을 한 줄에 하나씩 입력해 주세요.'),
                    batch_save_failure_notice_visible: visibleAlerts.includes('상품 URL 일괄 등록을 저장하지 못했습니다. URL과 저장 공간을 확인해 주세요.'),
                    batch_created_notice_visible: visibleAlerts.some((text) => /^(?:[1-9]|10)개 고유 상품 URL을 수집 대기열에 추가했습니다[.]$/.test(text)),
                    unclassified_alert_visible: visibleAlerts.some((text) => !recognizedAlert(text)),
                    visible_alert_count: Math.min(visibleAlerts.length, 20),
                    document_response_status: responseStatus,
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
    batch_save_failed = bool(page.get('batch_save_failure_notice_visible'))
    batch_created = bool(page.get('batch_created_notice_visible'))
    unclassified_alert = bool(page.get('unclassified_alert_visible'))
    if access_denied:
        page_class = 'controller_access_denied'
    elif read_only:
        page_class = 'batch_capability_denied'
    elif queue_unavailable:
        page_class = 'queue_unavailable'
    elif token_rejected:
        page_class = 'mutation_token_rejected'
    elif mutation_access_denied:
        page_class = 'mutation_capability_denied'
    elif batch_save_failed:
        page_class = 'batch_save_error'
    elif batch_created and not bool(page.get('batch_progress_container_visible')):
        page_class = 'batch_created_without_progress'
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
        'empty_url_notice_visible': bool(page.get('empty_url_notice_visible')),
        'batch_save_failure_notice_visible': batch_save_failed,
        'batch_created_notice_visible': batch_created,
        'unclassified_alert_visible': unclassified_alert,
        'visible_alert_count': visible_alert_count,
        'document_response_status': response_status,
        'read_only_notice_visible': read_only,
        'access_denied_notice_visible': access_denied,
        'queue_unavailable_notice_visible': queue_unavailable,
    }


def save_safe_failure_screenshot(driver, path, state):
    """Capture synthetic batch progress, a fixed alert, or a scrubbed import form crop."""
    stage = state.get('stage', 'unknown') if isinstance(state, dict) else 'unknown'
    click = state.get('click_diagnostics') if isinstance(state, dict) else None
    if (stage == 'approve_amazon' and isinstance(click, dict)
            and click.get('attempted') is True and click.get('returned') is False):
        try:
            return capture_safe_click_crop(driver, path, state)
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
        'last_completed_substage': 'not_started',
        'click_diagnostics': None,
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
        state['last_completed_substage'] = 'reject_status_readback'
        driver.save_screenshot(str(DEST / 'catalog-import-rejected.png'))
        state['stage'] = 'approve_amazon'
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

        options_confirmation = form.find_element(By.NAME, 'confirm_options_supported')
        if not options_confirmation.is_selected():
            click_with_safe_diagnostics(
                driver, options_confirmation, state,
                'approve_options_confirmation', 'options_confirmation_checkbox'
            )
        else:
            state['last_completed_substage'] = 'approve_options_confirmation'
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
