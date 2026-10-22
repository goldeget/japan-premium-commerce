#!/usr/bin/env python3
"""Create and edit a synthetic inactive native product in Chromium."""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE = os.environ["SHOP_BASE_URL"].rstrip("/")
ADMIN_LOGIN = os.environ["ADMIN_LOGIN_URL"].rstrip("/")
ADMIN_EMAIL = os.environ["ADMIN_MAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWD"]
ADMIN_PATH = urlparse(ADMIN_LOGIN).path.rstrip("/")
DEST = Path(os.environ["QA_ARTIFACT_DIR"])
DEST.mkdir(parents=True, exist_ok=True)


def visible(driver: webdriver.Chrome, selector: str):
    return WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))


def manager_link(driver: webdriver.Chrome):
    for link in driver.find_elements(By.CSS_SELECTOR, 'a[href*="controller="]'):
        href = link.get_attribute("href") or ""
        if parse_qs(urlparse(href).query).get("controller", []) == ["AdminOrdenowaProductManager"]:
            return href
    return False


def manager_page_diagnostics(driver: webdriver.Chrome) -> dict[str, bool]:
    return driver.execute_script(
        """
        const bodyText = document.body?.innerText || '';
        const nameField = document.querySelector('#name_ja');
        const managerRoutePresent = new URLSearchParams(window.location.search)
            .get('controller') === 'AdminOrdenowaProductManager';
        return {
            product_heading: Array.from(document.querySelectorAll('h3')).some(
                (heading) => heading.innerText.trim() === '새 상품 등록'
            ),
            name_ja_present: Boolean(nameField),
            denied_marker: bodyText.includes('상품을 조회할 권한이 없습니다.'),
            add_denied_marker: bodyText.includes('상품을 등록할 권한이 없습니다.'),
            edit_denied_marker: bodyText.includes('상품을 수정할 권한이 없습니다.'),
            load_error_marker: bodyText.includes('상품 관리 화면을 불러오지 못했습니다.'),
            login_form_present: Boolean(document.querySelector('#login_form')),
            product_form_present: Boolean(nameField && nameField.closest('form')),
            product_list_present: Array.from(document.querySelectorAll('h3')).some(
                (heading) => heading.innerText.trim() === 'ORDENOWA 관리 상품'
            ),
            manager_route_present: managerRoutePresent,
        };
        """
    )


def clear_product_browser_network_events(driver: webdriver.Chrome) -> bool:
    """Discard earlier browser traffic so later records cover only the product POST."""
    try:
        driver.get_log("performance")
    except Exception:
        return False
    return True


def _safe_network_url_metadata(raw_url: object) -> dict[str, object]:
    """Reduce a browser URL to a sanitized path and route booleans; omit query values."""
    if not isinstance(raw_url, str):
        raw_url = ""
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
        parsed = urlparse("")
        same_origin = False

    path = re.sub(r"[^A-Za-z0-9._~/-]", "_", parsed.path or "/")[:240]
    query_controller = parse_qs(parsed.query).get("controller", [""])[0]
    controller_is_manager = query_controller == "AdminOrdenowaProductManager"
    is_admin_path = bool(
        ADMIN_PATH
        and (parsed.path == ADMIN_PATH or parsed.path.startswith(ADMIN_PATH + "/"))
    )
    return {
        "path": path,
        "origin_matches_shop": same_origin,
        "is_admin_path": is_admin_path,
        "controller_is_manager": controller_is_manager,
    }


def _safe_http_status(value: object) -> int | None:
    try:
        status = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return status if 100 <= status <= 599 else None


def _safe_network_failure_category(value: object) -> str:
    categories = {
        "net::ERR_ABORTED": "aborted",
        "net::ERR_CONNECTION_REFUSED": "connection_refused",
        "net::ERR_CONNECTION_RESET": "connection_reset",
        "net::ERR_NAME_NOT_RESOLVED": "dns_failure",
        "net::ERR_TIMED_OUT": "timeout",
    }
    if not isinstance(value, str):
        return "other_failure"
    category = categories.get(value)
    if category is not None:
        return category
    prefix = "net::ERR_"
    if not value.startswith(prefix):
        return "other_failure"
    error_name = value[len(prefix) :]
    if (
        not error_name
        or len(error_name) > 64
        or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for character in error_name)
    ):
        return "other_failure"
    return f"net_error_{error_name.lower()}"


def product_post_network_diagnostics(driver: webdriver.Chrome) -> dict[str, object]:
    """Return bounded request/redirect metadata without headers, cookies, query values, or bodies."""
    try:
        events = driver.get_log("performance")
    except Exception:
        return {"available": False, "truncated": False, "records": []}

    records_by_id: dict[str, dict[str, object]] = {}
    current_methods: dict[str, str] = {}
    truncated = len(events) > 2000
    for entry in events[:2000]:
        if not isinstance(entry, dict):
            continue
        try:
            envelope = json.loads(entry.get("message", ""))
        except (TypeError, ValueError):
            continue
        event = envelope.get("message", {}) if isinstance(envelope, dict) else {}
        if not isinstance(event, dict):
            continue
        event_name = event.get("method")
        params = event.get("params", {})
        if not isinstance(params, dict):
            continue
        request_id = params.get("requestId")
        if not isinstance(request_id, str):
            continue

        if event_name == "Network.requestWillBeSent":
            request = params.get("request", {})
            if not isinstance(request, dict):
                continue
            request_method = request.get("method", "")
            request_method = request_method.upper() if isinstance(request_method, str) else ""
            metadata = _safe_network_url_metadata(request.get("url"))
            record = records_by_id.get(request_id)
            redirect_response = params.get("redirectResponse")
            if record is not None and isinstance(redirect_response, dict):
                redirect_status = _safe_http_status(redirect_response.get("status"))
                if current_methods.get(request_id) == "POST" and record["post_response_status"] is None:
                    record["post_response_status"] = redirect_status
                redirects = record["redirects"]
                if isinstance(redirects, list) and len(redirects) < 3:
                    redirects.append(
                        {
                            "status": redirect_status,
                            "redirect_target_path": metadata["path"],
                            "redirect_target_origin_matches_shop": metadata["origin_matches_shop"],
                            "redirect_target_is_admin_path": metadata["is_admin_path"],
                            "redirect_target_controller_is_manager": metadata["controller_is_manager"],
                        }
                    )
                elif isinstance(redirects, list):
                    truncated = True

            if request_method == "POST" and record is None and len(records_by_id) < 8:
                record = {
                    "method": "POST",
                    "path": metadata["path"],
                    "origin_matches_shop": metadata["origin_matches_shop"],
                    "is_admin_path": metadata["is_admin_path"],
                    "controller_is_manager": metadata["controller_is_manager"],
                    "post_response_status": None,
                    "redirects": [],
                    "failure_category": None,
                }
                records_by_id[request_id] = record
            elif request_method == "POST" and record is None:
                truncated = True
            if record is not None:
                current_methods[request_id] = request_method

        elif event_name == "Network.responseReceived":
            record = records_by_id.get(request_id)
            response = params.get("response", {})
            if record is not None and current_methods.get(request_id) == "POST" and isinstance(response, dict):
                status = _safe_http_status(response.get("status"))
                if status is not None:
                    record["post_response_status"] = status

        elif event_name == "Network.loadingFailed":
            record = records_by_id.get(request_id)
            if record is not None:
                record["failure_category"] = _safe_network_failure_category(params.get("errorText"))

    return {
        "available": True,
        "truncated": truncated,
        "records": list(records_by_id.values())[:8],
    }


def product_form_diagnostics(driver: webdriver.Chrome) -> dict[str, object]:
    """Return bounded form shape/state without emitting submitted values or tokens."""
    return driver.execute_script(
        r"""
        const submitButton = document.querySelector('button[name="submitKuraneaProductSave"]');
        const form = submitButton?.form || document.querySelector('#name_ja')?.closest('form');
        const shopOrigin = new URL(arguments[0], document.baseURI).origin;
        const adminPath = String(arguments[1] || '').replace(/\/+$/, '');
        const safePath = (value) => String(value || '/').slice(0, 240).replace(/[^A-Za-z0-9._~/-]/g, '_');
        if (!form) {
            return {
                login_form_present: Boolean(document.querySelector('#login_form')),
                manager_route_present: new URLSearchParams(window.location.search)
                    .get('controller') === 'AdminOrdenowaProductManager',
                product_form_present: false,
                product_list_present: Array.from(document.querySelectorAll('h3')).some(
                    (heading) => heading.innerText.trim() === 'ORDENOWA 관리 상품'
                ),
                action_origin_matches_current: false,
                action_origin_matches_shop: false,
                action_path: null,
                action_is_admin_path: false,
                action_controller_is_manager: false,
            };
        }

        const action = new URL(form.action, document.baseURI);
        const actionControllerIsManager = new URLSearchParams(action.search).get('controller')
            === 'AdminOrdenowaProductManager';
        const actionIsAdminPath = Boolean(
            adminPath && (action.pathname === adminPath || action.pathname.startsWith(`${adminPath}/`))
        );
        const hiddenToken = form.querySelector('input[name="token"]')?.value || '';
        const actionToken = action.searchParams.get('token') || '';
        const safeFields = [
            'name_ja', 'name_ko', 'price_jpy', 'quantity', 'category_ids',
            'options', 'description_ja', 'description_ko', 'product_images',
        ];
        const combinationStockFields = Array.from(
            form.querySelectorAll('input[name^="combination_quantities["]')
        );
        const invalidCombinationStockCount = combinationStockFields.filter(
            (field) => field.willValidate && !field.validity.valid
        ).length;
        const hasValue = (name) => Array.from(form.querySelectorAll(`[name="${name}"], [name="${name}[]"]`)).some((field) => {
            if (field.type === 'checkbox' || field.type === 'radio') return field.checked;
            if (field.type === 'file') return Boolean(field.files?.length);
            return String(field.value || '').trim() !== '';
        });
        const invalidNames = safeFields.filter((name) =>
            Array.from(form.querySelectorAll(`[name="${name}"], [name="${name}[]"]`)).some(
                (field) => field.willValidate && !field.validity.valid
            )
        );
        return {
            login_form_present: Boolean(document.querySelector('#login_form')),
            manager_route_present: new URLSearchParams(window.location.search)
                .get('controller') === 'AdminOrdenowaProductManager',
            product_form_present: true,
            product_list_present: Array.from(document.querySelectorAll('h3')).some(
                (heading) => heading.innerText.trim() === 'ORDENOWA 관리 상품'
            ),
            form_method_post: form.method.toLowerCase() === 'post',
            multipart_form: form.enctype.toLowerCase() === 'multipart/form-data',
            action_origin_matches_current: action.origin === window.location.origin,
            action_origin_matches_shop: action.origin === shopOrigin,
            action_path: safePath(action.pathname),
            action_is_admin_path: actionIsAdminPath,
            action_controller_is_manager: actionControllerIsManager,
            action_targets_manager: actionControllerIsManager,
            action_token_present: Boolean(actionToken),
            hidden_token_present: Boolean(hiddenToken),
            hidden_token_matches_action: Boolean(hiddenToken && actionToken && hiddenToken === actionToken),
            submit_control_present: Boolean(submitButton),
            populated_field_names: safeFields.filter(hasValue),
            field_error_names: invalidNames,
            combination_stock_input_count: combinationStockFields.length,
            invalid_combination_stock_input_count: invalidCombinationStockCount,
            selected_category_count: form.querySelectorAll('input[name="category_ids[]"]:checked').length,
            selected_file_count: form.querySelector('#product_images')?.files?.length || 0,
        };
        """,
        BASE,
        ADMIN_PATH,
    )


def product_save_result(driver: webdriver.Chrome):
    """Return success or a sanitized visible alert outcome after product POST."""
    return driver.execute_script(
        """
        const bodyText = document.body?.innerText || '';
        if (bodyText.includes('상품 ID') && bodyText.includes('저장했습니다')) {
            return {status: 'success'};
        }
        const alerts = Array.from(document.querySelectorAll('.alert')).filter((candidate) => {
            const style = window.getComputedStyle(candidate);
            return style.display !== 'none' && style.visibility !== 'hidden' && candidate.getClientRects().length > 0;
        });
        const alert = alerts.find((candidate) => {
            const text = (candidate.innerText || candidate.textContent || '').trim();
            const isExpectedInformationalBanner = candidate.classList.contains('alert-info')
                && text.includes('상품은 기본적으로 비활성·비노출·주문 불가 상태로 저장됩니다.');
            return !isExpectedInformationalBanner;
        });
        if (!alert) return false;

        const text = (alert.innerText || alert.textContent || '').trim();
        const alertClass = ['success', 'danger', 'warning', 'info'].find(
            (name) => alert.classList.contains(`alert-${name}`)
        ) || 'unknown';
        const knownErrors = [
            ['admin_token_invalid', '관리자 보안 토큰이 올바르지 않습니다.'],
            ['product_add_permission_denied', '상품을 등록할 권한이 없습니다.'],
            ['product_edit_permission_denied', '상품을 수정할 권한이 없습니다.'],
            ['product_name_ja_invalid', '일본어 상품명'],
            ['product_name_ko_invalid', '한국어 상품명'],
            ['price_jpy_invalid', 'JPY 가격'],
            ['quantity_invalid', '재고는'],
            ['category_ids_missing', '카테고리를 하나 이상'],
            ['category_ids_invalid', '카테고리 선택값'],
            ['product_category_unavailable', '선택한 카테고리 중'],
            ['product_options_invalid', '상품 옵션'],
            ['product_option_format_invalid', '옵션은 그룹명:'],
            ['product_option_group_invalid', '옵션 그룹'],
            ['product_option_value_invalid', '옵션 값'],
            ['product_option_combination_limit', '옵션 조합은 최대'],
            ['product_image_invalid', '상품 이미지는'],
            ['product_image_removal_invalid', '삭제할 상품 이미지'],
            ['managed_product_protected', '판매 보호 상태'],
            ['native_product_creation_failed', '비활성 상품을 생성하지 못했습니다.'],
            ['native_product_update_failed', '상품 내용을 저장하지 못했습니다.'],
            ['native_product_save_failed', '상품 저장에 실패했습니다.'],
            ['manager_load_failed', '상품 관리 화면을 불러오지 못했습니다.'],
        ];
        const errorMarkers = knownErrors
            .filter(([, phrase]) => text.includes(phrase))
            .map(([marker]) => marker);
        const fieldForMarker = {
            product_name_ja_invalid: 'name_ja',
            product_name_ko_invalid: 'name_ko',
            price_jpy_invalid: 'price_jpy',
            quantity_invalid: 'quantity',
            category_ids_missing: 'category_ids',
            category_ids_invalid: 'category_ids',
            product_category_unavailable: 'category_ids',
            product_options_invalid: 'options',
            product_option_format_invalid: 'options',
            product_option_group_invalid: 'options',
            product_option_value_invalid: 'options',
            product_option_combination_limit: 'options',
            product_image_invalid: 'product_images',
            product_image_removal_invalid: 'remove_image_ids',
        };
        const fieldErrorNames = [...new Set(errorMarkers.map((marker) => fieldForMarker[marker]).filter(Boolean))];
        let messageCategory = 'unknown';
        if (errorMarkers.includes('admin_token_invalid')) {
            messageCategory = 'security_token';
        } else if (errorMarkers.some((marker) => marker.endsWith('permission_denied'))) {
            messageCategory = 'permission_denied';
        } else if (fieldErrorNames.length > 0) {
            messageCategory = 'validation_error';
        } else if (errorMarkers.some((marker) => marker.includes('creation_failed') || marker.includes('update_failed') || marker.includes('save_failed'))) {
            messageCategory = 'save_error';
        }
        if (errorMarkers.length === 0) errorMarkers.push('unknown_controller_error');
        return {
            status: 'alert',
            alert_class: alertClass,
            message_category: messageCategory,
            error_markers: errorMarkers,
            field_error_names: fieldErrorNames,
        };
        """
    )


def product_post_failure_diagnostics(
    driver: webdriver.Chrome,
    form_before_submit: dict[str, object] | None = None,
) -> dict[str, object]:
    """Return an allowlisted page summary without exposing query tokens or page text."""
    page_diagnostics = driver.execute_script(
        """
        const params = new URLSearchParams(window.location.search);
        const rawController = params.get('controller') || '';
        const controller = /^[A-Za-z0-9_-]{1,80}$/.test(rawController) ? rawController : null;
        const pagePath = String(window.location.pathname || '')
            .slice(0, 240)
            .replace(/[^A-Za-z0-9._~/-]/g, '_');
        const pageTitle = String(document.title || '')
            .replace(/[\\u0000-\\u001f\\u007f]/g, ' ')
            .replace(/\\s+/g, ' ')
            .trim()
            .slice(0, 160);
        const navigation = performance.getEntriesByType('navigation')[0];
        const candidateStatus = Number(navigation?.responseStatus);
        const responseStatus = Number.isInteger(candidateStatus)
            && candidateStatus >= 100
            && candidateStatus <= 599
            ? candidateStatus
            : null;
        const safeMarkerText = [
            pageTitle,
            ...Array.from(document.querySelectorAll('h1, h2, [role="alert"]'))
                .filter((element) => element.getClientRects().length > 0)
                .map((element) => element.innerText || element.textContent || ''),
        ].join(' ').slice(0, 2000).toLowerCase();
        const pageMarkers = [];
        if (responseStatus === 404 || /\\b404\\b|not found|page not found|ページが見つかりません/.test(safeMarkerText)) {
            pageMarkers.push('not_found');
        }
        if (responseStatus >= 500 || /\\b500\\b|internal server error|bad gateway|service unavailable/.test(safeMarkerText)) {
            pageMarkers.push('server_error');
        }
        if (/fatal error|uncaught (?:exception|error)|symfony exception|oops! an error occurred|whoops, looks like something went wrong/.test(safeMarkerText)) {
            pageMarkers.push('fatal_error');
        }

        const nameField = document.querySelector('#name_ja');
        const headings = Array.from(document.querySelectorAll('h3')).map((heading) => heading.innerText.trim());
        const bodyText = document.body?.innerText || '';
        return {
            page_path: pagePath,
            query_controller: controller,
            page_title: pageTitle,
            response_status: responseStatus,
            page_markers: pageMarkers,
            login_form_present: Boolean(document.querySelector('#login_form')),
            product_form_present: Boolean(nameField && nameField.closest('form')),
            manager_route_present: controller === 'AdminOrdenowaProductManager',
            manager_heading_present: headings.includes('새 상품 등록') || headings.includes('상품 수정'),
            product_list_present: headings.includes('ORDENOWA 관리 상품'),
            add_denied_marker: bodyText.includes('상품을 등록할 권한이 없습니다.'),
            edit_denied_marker: bodyText.includes('상품을 수정할 권한이 없습니다.'),
            manager_load_error_marker: bodyText.includes('상품 관리 화면을 불러오지 못했습니다.'),
        };
        """
    )
    save_result = product_save_result(driver)
    if not isinstance(save_result, dict):
        save_result = {}
    network_diagnostics = product_post_network_diagnostics(driver)

    return {
        **page_diagnostics,
        "form_before_submit": form_before_submit or {},
        "form_after_response": product_form_diagnostics(driver),
        "save_status": save_result.get("status", "no_visible_response"),
        "alert_class": save_result.get("alert_class"),
        "error_markers": save_result.get("error_markers", []),
        "post_network_capture_available": network_diagnostics["available"],
        "post_network_records_truncated": network_diagnostics["truncated"],
        "post_network_records": network_diagnostics["records"],
    }


def _safe_category_ids(values: object) -> list[int]:
    if not isinstance(values, (list, tuple, set)):
        return []

    safe_ids: set[int] = set()
    for value in list(values)[:100]:
        if isinstance(value, bool):
            continue
        try:
            category_id = int(value)
        except (TypeError, ValueError):
            continue
        if 0 < category_id <= 2_147_483_647:
            safe_ids.add(category_id)

    return sorted(safe_ids)[:20]


def product_edit_failure_diagnostics(
    driver: webdriver.Chrome,
    product_id: int,
    expected_field_values: dict[str, str],
    category_ids_before_submit: object,
) -> dict[str, object]:
    """Return bounded edit state, excluding product values, page text, and tokens."""
    page_state = driver.execute_script(
        """
        const expectedProductId = Number(arguments[0]);
        const expectedFields = arguments[1] || {};
        const params = new URLSearchParams(window.location.search);
        const productField = document.querySelector('form #name_ja');
        const productForm = productField?.closest('form') || null;
        const idField = productForm?.querySelector('input[name="id_product"]');
        const currentProductId = Number(idField?.value || 0);
        const selectedCategoryIds = Array.from(
            document.querySelectorAll('input[name="category_ids[]"]:checked')
        )
            .map((field) => Number(field.value))
            .filter((id) => Number.isSafeInteger(id) && id > 0 && id <= 2147483647)
            .slice(0, 20);
        const expectedFieldEntries = Object.entries(expectedFields);
        const finalFieldMatch = expectedFieldEntries.length > 0
            && Boolean(productForm)
            && expectedFieldEntries.every(
            ([selector, expected]) => {
                const field = document.querySelector(selector);
                return Boolean(field) && field.value === expected;
            }
        );

        return {
            manager_route_present: params.get('controller') === 'AdminOrdenowaProductManager',
            product_form_present: Boolean(productForm),
            product_id_present: Number.isSafeInteger(currentProductId) && currentProductId > 0,
            product_id_matches: expectedProductId > 0 && currentProductId === expectedProductId,
            category_ids_after_response: selectedCategoryIds,
            final_field_match: finalFieldMatch,
        };
        """,
        int(product_id or 0),
        expected_field_values,
    )
    if not isinstance(page_state, dict):
        page_state = {}

    save_result = product_save_result(driver)
    if isinstance(save_result, dict) and save_result.get("status") == "success":
        save_result_category = "success"
    elif isinstance(save_result, dict) and save_result.get("status") == "alert":
        save_result_category = save_result.get("message_category")
    else:
        save_result_category = "none"

    allowed_error_markers = {
        "admin_token_invalid",
        "product_add_permission_denied",
        "product_edit_permission_denied",
        "product_name_ja_invalid",
        "product_name_ko_invalid",
        "price_jpy_invalid",
        "quantity_invalid",
        "category_ids_missing",
        "category_ids_invalid",
        "product_category_unavailable",
        "product_options_invalid",
        "product_option_format_invalid",
        "product_option_group_invalid",
        "product_option_value_invalid",
        "product_option_combination_limit",
        "product_image_invalid",
        "product_image_removal_invalid",
        "managed_product_protected",
        "native_product_creation_failed",
        "native_product_update_failed",
        "native_product_save_failed",
        "manager_load_failed",
        "unknown_controller_error",
    }
    raw_markers = save_result.get("error_markers", []) if isinstance(save_result, dict) else []
    error_markers = [marker for marker in raw_markers if isinstance(marker, str) and marker in allowed_error_markers][:12]
    network_diagnostics = product_post_network_diagnostics(driver)

    return {
        "manager_route_present": bool(page_state.get("manager_route_present")),
        "product_form_present": bool(page_state.get("product_form_present")),
        "product_id_present": bool(page_state.get("product_id_present")),
        "product_id_matches": bool(page_state.get("product_id_matches")),
        "category_ids_before_submit": _safe_category_ids(category_ids_before_submit),
        "category_ids_after_response": _safe_category_ids(page_state.get("category_ids_after_response")),
        "save_result_category": save_result_category if isinstance(save_result_category, str) else "unknown",
        "error_markers": error_markers,
        "final_field_match": bool(page_state.get("final_field_match")),
        "post_network_capture_available": bool(network_diagnostics.get("available")),
        "post_network_records_truncated": bool(network_diagnostics.get("truncated")),
        "post_network_records": network_diagnostics.get("records", [])[:8],
    }


def product_links(driver: webdriver.Chrome, product_id: int):
    return [
        link
        for link in driver.find_elements(By.CSS_SELECTOR, 'a[href*="id_product="]')
        if parse_qs(urlparse(link.get_attribute("href") or "").query).get("id_product") == [str(product_id)]
    ]


def usable_category_boxes(driver: webdriver.Chrome):
    # PrestaShop's fresh-install tree starts with the technical Root category
    # (id 1), followed by the shop's Home/default category (id 2). Root is
    # active but is not a customer-facing product category.
    return [
        box
        for box in driver.find_elements(By.CSS_SELECTOR, 'input[name="category_ids[]"]')
        if box.get_attribute("value") != "1"
    ]


def default_category_box(driver: webdriver.Chrome):
    categories = usable_category_boxes(driver)
    if not categories:
        raise AssertionError("no usable native product categories are available")
    return next((box for box in categories if box.get_attribute("value") == "2"), categories[0])


def fill(driver: webdriver.Chrome, selector: str, value: str) -> None:
    field = visible(driver, selector)
    field.clear()
    field.send_keys(value)


def assert_javascript_image_loaded(driver: webdriver.Chrome, selector: str) -> None:
    image = visible(driver, selector)
    dimensions = driver.execute_script(
        "return {width: arguments[0].naturalWidth, height: arguments[0].naturalHeight};", image
    )
    if dimensions["width"] < 1 or dimensions["height"] < 1:
        raise AssertionError("uploaded product image preview did not render")


def write_temporary_png(contents: bytes, prefix: str) -> Path:
    """Write a browser upload fixture whose path remains available until cleanup."""
    image_file = tempfile.NamedTemporaryFile(prefix=prefix, suffix=".png", delete=False)
    image_path = Path(image_file.name)
    write_completed = False
    try:
        with image_file:
            image_file.write(contents)
            image_file.flush()
        write_completed = True
        return image_path
    finally:
        if not write_completed:
            image_path.unlink(missing_ok=True)


def run() -> None:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,960")
    options.add_argument("--lang=ja-JP")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver: webdriver.Chrome | None = None
    stage = "chromium_startup"
    create_operation = "not_started"
    edit_operation = "not_started"
    product_id = 0
    expected_edit_fields: dict[str, str] = {}
    edit_category_ids_before_submit: list[str] = []
    expected_category_ids: set[str] = set()
    manager_page_state: dict[str, str | bool] | None = None
    form_before_submit: dict[str, object] | None = None
    save_diagnostics: dict[str, object] | None = None
    temporary_upload_paths: list[Path] = []
    try:
        driver = webdriver.Chrome(options=options)
        stage = "administrator_login"
        driver.get(ADMIN_LOGIN + "/login")
        email = visible(driver, '#login_form input[name="email"], input[type="email"]')
        password = visible(driver, '#login_form input[name="passwd"], #login_form input[name="password"], input[type="password"]')
        email.send_keys(ADMIN_EMAIL)
        password.send_keys(ADMIN_PASSWORD)
        visible(driver, '#login_form button[type="submit"], #login_form input[type="submit"], button[type="submit"]').click()
        WebDriverWait(driver, 30).until(lambda browser: "/login" not in urlparse(browser.current_url).path)

        stage = "korean_product_manager_link"
        href = WebDriverWait(driver, 30).until(manager_link)
        parsed = urlparse(href)
        if parsed.hostname not in {"localhost", "127.0.0.1"} or not parsed.path.startswith("/admin-kuranea/"):
            raise AssertionError("product manager link is outside the isolated Back Office")
        driver.get(href)
        stage = "korean_product_manager_form"
        driver.save_screenshot(str(DEST / "product-admin-manager-navigation.png"))
        manager_page_state = manager_page_diagnostics(driver)
        if not manager_page_state["product_heading"] or not manager_page_state["product_form_present"]:
            raise AssertionError("Korean product registration and management UI is missing")
        visible(driver, 'form #name_ja')
        if "판매 활성화 기능이 없습니다" not in driver.find_element(By.TAG_NAME, "body").text:
            raise AssertionError("the product page must state that its entries remain inactive")
        for selector in (
            "#name_ja", "#name_ko", "#price_jpy", "#quantity", "#options",
            "#description_ja", "#description_ko", "#product_images", 'input[name="category_ids[]"]',
        ):
            visible(driver, selector)
        if driver.find_elements(By.CSS_SELECTOR, 'input[name^="combination_quantities["]'):
            raise AssertionError("new product options should not expose stock rows before native combinations exist")
        driver.save_screenshot(str(DEST / "product-admin-empty-desktop.png"))

        stage = "native_product_create"
        suffix = os.environ.get("GITHUB_RUN_ID", "local")
        japanese_name = f"ORDENOWA CI 合成商品 {suffix}"
        korean_name = f"ORDENOWA CI 합성 상품 {suffix}"
        create_operation = "fill_name_ja"
        fill(driver, "#name_ja", japanese_name)
        create_operation = "fill_name_ko"
        fill(driver, "#name_ko", korean_name)
        create_operation = "fill_price_jpy"
        fill(driver, "#price_jpy", "1280")
        create_operation = "fill_quantity"
        fill(driver, "#quantity", "3")
        create_operation = "fill_options"
        fill(driver, "#options", "色:青|赤\nサイズ:S|M")
        create_operation = "fill_description_ja"
        fill(driver, "#description_ja", "CI用の商品説明")
        create_operation = "fill_description_ko"
        fill(driver, "#description_ko", "CI용 상세 설명")
        create_operation = "select_default_category"
        initial_category = default_category_box(driver)
        initial_category_id = initial_category.get_attribute("value")
        if not initial_category.is_selected():
            initial_category.click()

        create_operation = "prepare_image_file"
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGNU8qplYGBgYmBgYGBgAAAKuwDtbIwH5AAAAABJRU5ErkJggg=="
        )
        image_path = write_temporary_png(png, "ordenowa-product-")
        temporary_upload_paths.append(image_path)
        create_operation = "upload_image"
        visible(driver, "#product_images").send_keys(str(image_path))
        create_operation = "submit_product"
        form_before_submit = product_form_diagnostics(driver)
        clear_product_browser_network_events(driver)
        visible(driver, 'button[name="submitKuraneaProductSave"]').click()

        create_operation = "wait_for_save_confirmation"
        save_result = WebDriverWait(driver, 45).until(product_save_result)
        if save_result["status"] == "alert":
            save_diagnostics = product_post_failure_diagnostics(driver, form_before_submit)
            raise AssertionError("native product save displayed an alert")
        if save_result["status"] != "success":
            raise AssertionError("native product save did not return a verified success response")
        create_operation = "read_saved_product_id"
        product_id = int(
            WebDriverWait(driver, 30)
            .until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="id_product"]')))
            .get_attribute("value")
        )
        if product_id < 1:
            raise AssertionError("the saved product did not receive a native PrestaShop ID")
        for selector, expected in (
            ("#name_ja", japanese_name),
            ("#name_ko", korean_name),
            ("#price_jpy", "1280"),
            ("#quantity", "0"),
            ("#options", "色:青|赤\nサイズ:S|M"),
            ("#description_ja", "CI用の商品説明"),
            ("#description_ko", "CI용 상세 설명"),
        ):
            if visible(driver, selector).get_attribute("value") != expected:
                raise AssertionError("a product create field did not persist through PrestaShop")
        created_stock_inputs = driver.find_elements(By.CSS_SELECTOR, 'input[name^="combination_quantities["]')
        if len(created_stock_inputs) != 4 or [field.get_attribute("value") for field in created_stock_inputs] != ["3"] * 4:
            raise AssertionError("the editor did not expose the saved stock for all four native combinations")
        if len(driver.find_elements(By.CSS_SELECTOR, ".ordenowa-product-image img")) != 1:
            raise AssertionError("the new product image is missing from the admin preview")
        created_category_ids = {
            checkbox.get_attribute("value")
            for checkbox in driver.find_elements(By.CSS_SELECTOR, 'input[name="category_ids[]"]')
            if checkbox.is_selected()
        }
        if created_category_ids != {initial_category_id}:
            raise AssertionError("the product did not retain the selected non-root default category")
        assert_javascript_image_loaded(driver, ".ordenowa-product-image img")
        created_links = product_links(driver, product_id)
        if len(created_links) != 1 or created_links[0].text.strip() not in {japanese_name, korean_name}:
            raise AssertionError("the native product list should show one localized title for the created product")
        driver.save_screenshot(str(DEST / "product-admin-created-desktop.png"))

        stage = "native_product_edit"
        edit_operation = "find_edit_link"
        edit_link = WebDriverWait(driver, 30).until(lambda browser: next(iter(product_links(browser, product_id)), False))
        edit_operation = "open_edit_link"
        driver.get(edit_link.get_attribute("href"))
        edit_operation = "wait_for_edit_form"
        visible(driver, "#name_ja")
        edit_operation = "verify_initial_edit_data"
        if visible(driver, "#name_ja").get_attribute("value") != japanese_name:
            raise AssertionError("the existing product was not loaded into the edit form")
        edit_operation = "remove_old_image"
        old_image_checkbox = visible(driver, 'input[name="remove_image_ids[]"]')
        old_image_id = old_image_checkbox.get_attribute("value")
        old_image_checkbox.click()
        edit_operation = "fill_name_ja"
        fill(driver, "#name_ja", japanese_name + " 수정")
        edit_operation = "fill_name_ko"
        fill(driver, "#name_ko", korean_name + " 수정")
        edit_operation = "fill_price_jpy"
        fill(driver, "#price_jpy", "1490")
        edit_operation = "fill_quantity"
        fill(driver, "#quantity", "5")
        edited_options = "色:青|緑\nサイズ:S|M"
        edit_operation = "fill_options"
        fill(driver, "#options", edited_options)
        edit_operation = "fill_description_ja"
        fill(driver, "#description_ja", "更新した説明")
        edit_operation = "fill_description_ko"
        fill(driver, "#description_ko", "수정한 상세 설명")
        expected_edit_fields = {
            "#name_ja": japanese_name + " 수정",
            "#name_ko": korean_name + " 수정",
            "#price_jpy": "1490",
            "#quantity": "5",
            "#options": edited_options,
            "#description_ja": "更新した説明",
            "#description_ko": "수정한 상세 설명",
        }
        edit_operation = "read_edit_categories"
        category_boxes = driver.find_elements(By.CSS_SELECTOR, 'input[name="category_ids[]"]')
        usable_ids = {box.get_attribute("value") for box in usable_category_boxes(driver)}
        if not usable_ids:
            raise AssertionError("no usable native product categories are available for editing")
        currently_selected = {box.get_attribute("value") for box in category_boxes if box.is_selected()}
        run_id = os.environ.get("GITHUB_RUN_ID", "local")
        run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
        edit_category_name = f"ORDENOWA CI EDIT CATEGORY {run_id}-{run_attempt}"
        alternate_categories = [
            box.get_attribute("value")
            for box in category_boxes
            if box.get_attribute("value") in usable_ids
            and box.get_attribute("value") not in currently_selected
        ]
        if not alternate_categories:
            raise AssertionError("category edit must select the isolated CI category")
        edit_category = next(
            (
                box
                for box in category_boxes
                if box.get_attribute("value") in alternate_categories
                and edit_category_name in box.find_element(By.XPATH, "./ancestor::label[1]").text
            ),
            None,
        )
        if edit_category is None:
            raise AssertionError("the isolated CI product edit category is missing from the admin form")
        edit_category_id = edit_category.get_attribute("value")
        if not edit_category_id or edit_category_id == initial_category_id:
            raise AssertionError("the isolated CI edit category must differ from the created product category")
        expected_category_ids = {edit_category_id}
        edit_operation = "select_edit_category"
        for box in category_boxes:
            category_id = box.get_attribute("value")
            if box.is_selected() != (category_id in expected_category_ids):
                box.click()
        edit_category_ids_before_submit = [
            box.get_attribute("value") for box in category_boxes if box.is_selected()
        ]
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGNU8qplYGBgYmBgYGBgAAAKuwDtbIwH5AAAAABJRU5ErkJggg=="
        )
        image_path = write_temporary_png(png, "ordenowa-product-replacement-")
        temporary_upload_paths.append(image_path)
        edit_operation = "upload_replacement_image"
        visible(driver, "#product_images").send_keys(str(image_path))
        edit_operation = "submit_edit"
        clear_product_browser_network_events(driver)
        visible(driver, 'button[name="submitKuraneaProductSave"]').click()

        edit_operation = "wait_edit_save_confirmation"
        edit_save_result = WebDriverWait(driver, 45).until(product_save_result)
        if not isinstance(edit_save_result, dict) or edit_save_result.get("status") != "success":
            raise AssertionError("native product edit did not return a verified success response")
        edit_operation = "verify_edited_fields"
        expected_edit_fields["#quantity"] = "0"
        if visible(driver, "#name_ja").get_attribute("value") != japanese_name + " 수정":
            raise AssertionError("product name edit did not persist")
        if visible(driver, "#name_ko").get_attribute("value") != korean_name + " 수정":
            raise AssertionError("Korean product name edit did not persist")
        if visible(driver, "#price_jpy").get_attribute("value") != "1490":
            raise AssertionError("product price edit did not persist")
        if visible(driver, "#quantity").get_attribute("value") != "0":
            raise AssertionError("the product-level default stock must remain separate from option stocks")
        if visible(driver, "#options").get_attribute("value") != edited_options:
            raise AssertionError("product option edit did not persist")
        if visible(driver, "#description_ja").get_attribute("value") != "更新した説明":
            raise AssertionError("Japanese product detail edit did not persist")
        if visible(driver, "#description_ko").get_attribute("value") != "수정한 상세 설명":
            raise AssertionError("Korean product detail edit did not persist")
        saved_category_ids = {
            checkbox.get_attribute("value")
            for checkbox in driver.find_elements(By.CSS_SELECTOR, 'input[name="category_ids[]"]')
            if checkbox.is_selected()
        }
        edit_operation = "verify_edited_categories"
        if saved_category_ids != expected_category_ids:
            raise AssertionError("product category edit did not persist")
        if len(driver.find_elements(By.CSS_SELECTOR, ".ordenowa-product-image img")) != 1:
            raise AssertionError("product image replacement did not leave exactly one image")
        remaining_image_checkbox = visible(driver, 'input[name="remove_image_ids[]"]')
        if remaining_image_checkbox.get_attribute("value") == old_image_id:
            raise AssertionError("the old product image was not replaced")
        assert_javascript_image_loaded(driver, ".ordenowa-product-image img")
        edited_links = product_links(driver, product_id)
        if len(edited_links) != 1 or edited_links[0].text.strip() not in {japanese_name + " 수정", korean_name + " 수정"}:
            raise AssertionError("the product list should show one updated localized title after editing")
        edited_record = edited_links[0].find_element(By.XPATH, "./ancestor::li[contains(@class, 'well')]")
        if f"ID {product_id}" not in edited_record.text:
            raise AssertionError("the updated product list record does not identify the edited native product")
        driver.save_screenshot(str(DEST / "product-admin-edited-desktop.png"))

        edit_operation = "verify_distinct_option_stock_controls"
        combination_stock_inputs = driver.find_elements(By.CSS_SELECTOR, 'input[name^="combination_quantities["]')
        if len(combination_stock_inputs) != 4 or [field.get_attribute("value") for field in combination_stock_inputs] != ["5"] * 4:
            raise AssertionError("changed options should receive the submitted default stock before per-combination editing")
        expected_combination_quantities = ["0", "2", "4", "6"]
        edit_operation = "set_distinct_option_stock"
        for field, quantity in zip(combination_stock_inputs, expected_combination_quantities, strict=True):
            field.clear()
            field.send_keys(quantity)
        if [field.get_attribute("value") for field in combination_stock_inputs] != expected_combination_quantities:
            raise AssertionError("distinct option stock values could not be entered for each native combination")
        edit_operation = "submit_distinct_option_stock"
        clear_product_browser_network_events(driver)
        visible(driver, 'button[name="submitKuraneaProductSave"]').click()
        distinct_stock_result = WebDriverWait(driver, 45).until(product_save_result)
        if not isinstance(distinct_stock_result, dict) or distinct_stock_result.get("status") != "success":
            raise AssertionError("distinct option stock did not save successfully")
        edit_operation = "verify_distinct_option_stock"
        saved_combination_stock_inputs = driver.find_elements(By.CSS_SELECTOR, 'input[name^="combination_quantities["]')
        if [field.get_attribute("value") for field in saved_combination_stock_inputs] != expected_combination_quantities:
            raise AssertionError("distinct option stock did not persist for every native combination")
        if visible(driver, "#quantity").get_attribute("value") != "0":
            raise AssertionError("per-combination stock editing changed the product-level default quantity")
        driver.save_screenshot(str(DEST / "product-admin-distinct-combination-stock-desktop.png"))

        print(f"PASS: Chromium created and edited inactive native product ID={product_id}; image {old_image_id} replaced; distinct combination stock saved.")
    except Exception as error:
        if driver is not None:
            try:
                driver.save_screenshot(str(DEST / "product-admin-failure.png"))
            except Exception:
                pass
        exception_class = type(error).__name__
        diagnostic = f"ORDENOWA_PRODUCT_ADMIN_STAGE={stage}; exception_class={exception_class}"
        if stage == "native_product_create":
            diagnostic += f"; operation={create_operation}"
            if driver is not None and save_diagnostics is None:
                try:
                    save_diagnostics = product_post_failure_diagnostics(driver, form_before_submit)
                except Exception:
                    save_diagnostics = {"diagnostics_unavailable": True}
            if save_diagnostics is not None:
                diagnostic += "; save_diagnostics=" + json.dumps(save_diagnostics, ensure_ascii=False, sort_keys=True)
        if stage == "native_product_edit":
            diagnostic += f"; operation={edit_operation}"
            if driver is not None:
                try:
                    edit_diagnostics = product_edit_failure_diagnostics(
                        driver,
                        product_id,
                        expected_edit_fields,
                        edit_category_ids_before_submit,
                    )
                except Exception:
                    edit_diagnostics = {"diagnostics_unavailable": True}
                diagnostic += "; edit_diagnostics=" + json.dumps(
                    edit_diagnostics, ensure_ascii=False, sort_keys=True
                )
        if stage == "korean_product_manager_form" and driver is not None:
            try:
                manager_page_state = manager_page_diagnostics(driver)
            except Exception:
                pass
            if manager_page_state is not None:
                page_state = json.dumps(manager_page_state, ensure_ascii=False, sort_keys=True)
                diagnostic += f"; page_state={page_state}"
        annotation_message = diagnostic.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        annotation = f"::error title=ORDENOWA product admin browser::{annotation_message}"
        print(diagnostic, file=sys.stderr)
        print(annotation, file=sys.stdout)
        raise SystemExit(f"product admin browser scenario failed at {stage} ({exception_class})") from None
    finally:
        try:
            if driver is not None:
                driver.quit()
        finally:
            for image_path in temporary_upload_paths:
                image_path.unlink(missing_ok=True)


def run_mobile_layout() -> None:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=390,844")
    options.add_argument("--lang=ja-JP")
    driver: webdriver.Chrome | None = None
    stage = "mobile_chromium_startup"
    manager_page_state: dict[str, str | bool] | None = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_window_size(390, 844)
        stage = "mobile_administrator_login"
        driver.get(ADMIN_LOGIN + "/login")
        email = visible(driver, '#login_form input[name="email"], input[type="email"]')
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
        WebDriverWait(driver, 30).until(lambda browser: "/login" not in urlparse(browser.current_url).path)

        stage = "mobile_korean_product_manager_link"
        href = WebDriverWait(driver, 30).until(manager_link)
        parsed = urlparse(href)
        if parsed.hostname not in {"localhost", "127.0.0.1"} or not parsed.path.startswith("/admin-kuranea/"):
            raise AssertionError("product manager link is outside the isolated Back Office")
        driver.get(href)
        stage = "mobile_korean_product_manager_form"
        driver.save_screenshot(str(DEST / "product-admin-mobile-manager-navigation.png"))
        manager_page_state = manager_page_diagnostics(driver)
        if not manager_page_state["product_heading"] or not manager_page_state["product_form_present"]:
            raise AssertionError("Korean product registration and management UI is missing at mobile width")
        visible(driver, 'form #name_ja')
        if "판매 활성화 기능이 없습니다" not in driver.find_element(By.TAG_NAME, "body").text:
            raise AssertionError("the product page must state that its entries remain inactive")
        overflow = driver.execute_script("return document.documentElement.scrollWidth > window.innerWidth + 2")
        if overflow:
            raise AssertionError("Korean product manager form overflows the mobile viewport")
        driver.save_screenshot(str(DEST / "product-admin-mobile.png"))
        print("PASS: Chromium loaded the Korean product manager form without horizontal overflow at 390px.")
    except Exception as error:
        if driver is not None:
            try:
                driver.save_screenshot(str(DEST / "product-admin-mobile-failure.png"))
            except Exception:
                pass
        exception_class = type(error).__name__
        diagnostic = f"ORDENOWA_PRODUCT_ADMIN_STAGE={stage}; exception_class={exception_class}"
        if stage == "mobile_korean_product_manager_form" and driver is not None:
            try:
                manager_page_state = manager_page_diagnostics(driver)
            except Exception:
                pass
            if manager_page_state is not None:
                page_state = json.dumps(manager_page_state, ensure_ascii=False, sort_keys=True)
                diagnostic += f"; page_state={page_state}"
        annotation_message = diagnostic.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print(diagnostic, file=sys.stderr)
        print(f"::error title=ORDENOWA mobile product admin browser::{annotation_message}", file=sys.stdout)
        raise SystemExit(f"mobile product admin browser scenario failed at {stage} ({exception_class})") from None
    finally:
        if driver is not None:
            driver.quit()


def run_all() -> None:
    failures = []
    for label, scenario in (("desktop", run), ("mobile", run_mobile_layout)):
        try:
            scenario()
        except SystemExit:
            failures.append(label)
            print(f"FAIL: {label} product admin browser scenario", file=sys.stderr)
        except Exception as error:
            failures.append(label)
            print(f"FAIL: {label} product admin browser scenario ({type(error).__name__})", file=sys.stderr)

    if failures:
        raise SystemExit("product admin browser scenarios failed: " + ", ".join(failures)) from None


if __name__ == "__main__":
    run_all()
