#!/usr/bin/env python3
"""Create and edit a synthetic inactive native product in Chromium."""

from __future__ import annotations

import base64
import json
import os
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


def product_form_diagnostics(driver: webdriver.Chrome) -> dict[str, object]:
    """Return bounded form shape/field state without reading submitted values or tokens."""
    return driver.execute_script(
        """
        const submitButton = document.querySelector('button[name="submitKuraneaProductSave"]');
        const form = submitButton?.form || document.querySelector('#name_ja')?.closest('form');
        if (!form) {
            return {
                login_form_present: Boolean(document.querySelector('#login_form')),
                manager_route_present: new URLSearchParams(window.location.search)
                    .get('controller') === 'AdminOrdenowaProductManager',
                product_form_present: false,
                product_list_present: Array.from(document.querySelectorAll('h3')).some(
                    (heading) => heading.innerText.trim() === 'ORDENOWA 관리 상품'
                ),
            };
        }

        const action = new URL(form.action, document.baseURI);
        const hiddenToken = form.querySelector('input[name="token"]')?.value || '';
        const actionToken = action.searchParams.get('token') || '';
        const safeFields = [
            'name_ja', 'name_ko', 'price_jpy', 'quantity', 'category_ids',
            'options', 'description_ja', 'description_ko', 'product_images',
        ];
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
            action_targets_manager: new URLSearchParams(action.search).get('controller') === 'AdminOrdenowaProductManager',
            action_token_present: Boolean(actionToken),
            hidden_token_present: Boolean(hiddenToken),
            hidden_token_matches_action: Boolean(hiddenToken && actionToken && hiddenToken === actionToken),
            submit_control_present: Boolean(submitButton),
            populated_field_names: safeFields.filter(hasValue),
            field_error_names: invalidNames,
            selected_category_count: form.querySelectorAll('input[name="category_ids[]"]:checked').length,
            selected_file_count: form.querySelector('#product_images')?.files?.length || 0,
        };
        """
    )


def product_save_result(driver: webdriver.Chrome):
    """Return success or a sanitized visible alert outcome after product POST."""
    return driver.execute_script(
        """
        const bodyText = document.body?.innerText || '';
        if (bodyText.includes('상품 ID') && bodyText.includes('저장했습니다')) {
            return {status: 'success'};
        }
        const alert = Array.from(document.querySelectorAll('.alert')).find((candidate) => {
            const style = window.getComputedStyle(candidate);
            return style.display !== 'none' && style.visibility !== 'hidden' && candidate.getClientRects().length > 0;
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

    return {
        **page_diagnostics,
        "form_before_submit": form_before_submit or {},
        "form_after_response": product_form_diagnostics(driver),
        "save_status": save_result.get("status", "no_visible_response"),
        "alert_class": save_result.get("alert_class"),
        "error_markers": save_result.get("error_markers", []),
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


def run() -> None:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,960")
    options.add_argument("--lang=ja-JP")
    driver: webdriver.Chrome | None = None
    stage = "chromium_startup"
    create_operation = "not_started"
    manager_page_state: dict[str, str | bool] | None = None
    form_before_submit: dict[str, object] | None = None
    save_diagnostics: dict[str, object] | None = None
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
        with tempfile.NamedTemporaryFile(prefix="ordenowa-product-", suffix=".png") as image_file:
            image_file.write(png)
            image_file.flush()
            create_operation = "upload_image"
            visible(driver, "#product_images").send_keys(image_file.name)
            create_operation = "submit_product"
            form_before_submit = product_form_diagnostics(driver)
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
            ("#quantity", "3"),
            ("#options", "色:青|赤\nサイズ:S|M"),
        ):
            if visible(driver, selector).get_attribute("value") != expected:
                raise AssertionError("a product create field did not persist through PrestaShop")
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
        edit_link = WebDriverWait(driver, 30).until(lambda browser: next(iter(product_links(browser, product_id)), False))
        driver.get(edit_link.get_attribute("href"))
        visible(driver, "#name_ja")
        if visible(driver, "#name_ja").get_attribute("value") != japanese_name:
            raise AssertionError("the existing product was not loaded into the edit form")
        old_image_checkbox = visible(driver, 'input[name="remove_image_ids[]"]')
        old_image_id = old_image_checkbox.get_attribute("value")
        old_image_checkbox.click()
        fill(driver, "#name_ja", japanese_name + " 수정")
        fill(driver, "#name_ko", korean_name + " 수정")
        fill(driver, "#price_jpy", "1490")
        fill(driver, "#quantity", "5")
        edited_options = "色:青|緑\nサイズ:S|M"
        fill(driver, "#options", edited_options)
        fill(driver, "#description_ja", "更新した説明")
        fill(driver, "#description_ko", "수정한 상세 설명")
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
        for box in category_boxes:
            category_id = box.get_attribute("value")
            if box.is_selected() != (category_id in expected_category_ids):
                box.click()
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGNU8qplYGBgYmBgYGBgAAAKuwDtbIwH5AAAAABJRU5ErkJggg=="
        )
        with tempfile.NamedTemporaryFile(prefix="ordenowa-product-replacement-", suffix=".png") as image_file:
            image_file.write(png)
            image_file.flush()
            visible(driver, "#product_images").send_keys(image_file.name)
            visible(driver, 'button[name="submitKuraneaProductSave"]').click()

        WebDriverWait(driver, 45).until(
            lambda browser: "수정했습니다" in browser.find_element(By.TAG_NAME, "body").text
            or "저장했습니다" in browser.find_element(By.TAG_NAME, "body").text
        )
        if visible(driver, "#name_ja").get_attribute("value") != japanese_name + " 수정":
            raise AssertionError("product name edit did not persist")
        if visible(driver, "#name_ko").get_attribute("value") != korean_name + " 수정":
            raise AssertionError("Korean product name edit did not persist")
        if visible(driver, "#price_jpy").get_attribute("value") != "1490":
            raise AssertionError("product price edit did not persist")
        if visible(driver, "#quantity").get_attribute("value") != "5":
            raise AssertionError("product stock edit did not persist")
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

        print(f"PASS: Chromium created and edited inactive native product ID={product_id}; image {old_image_id} replaced.")
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
        if driver is not None:
            driver.quit()


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
