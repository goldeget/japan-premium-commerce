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


def manager_page_diagnostics(driver: webdriver.Chrome) -> dict[str, str | bool]:
    return driver.execute_script(
        """
        const bodyText = document.body?.innerText || '';
        const nameField = document.querySelector('#name_ja');
        return {
            product_heading: Array.from(document.querySelectorAll('h3')).some(
                (heading) => heading.innerText.trim() === '새 상품 등록'
            ),
            name_ja_present: Boolean(nameField),
            denied_marker: bodyText.includes('상품을 조회할 권한이 없습니다.'),
            load_error_marker: bodyText.includes('상품 관리 화면을 불러오지 못했습니다.'),
            login_form_present: Boolean(document.querySelector('#login_form')),
            product_form_present: Boolean(nameField && nameField.closest('form')),
            pathname: window.location.pathname,
            title: document.title,
        };
        """
    )


def product_links(driver: webdriver.Chrome, product_id: int):
    return [
        link
        for link in driver.find_elements(By.CSS_SELECTOR, 'a[href*="id_product="]')
        if parse_qs(urlparse(link.get_attribute("href") or "").query).get("id_product") == [str(product_id)]
    ]


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
    manager_page_state: dict[str, str | bool] | None = None
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
        fill(driver, "#name_ja", japanese_name)
        fill(driver, "#name_ko", korean_name)
        fill(driver, "#price_jpy", "1280")
        fill(driver, "#quantity", "3")
        fill(driver, "#options", "色:青|赤\nサイズ:S|M")
        fill(driver, "#description_ja", "CI用の商品説明")
        fill(driver, "#description_ko", "CI용 상세 설명")
        categories = driver.find_elements(By.CSS_SELECTOR, 'input[name="category_ids[]"]')
        if not categories:
            raise AssertionError("no active native product categories are available")
        initial_category_id = categories[0].get_attribute("value")
        if not categories[0].is_selected():
            categories[0].click()

        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGNU8qplYGBgYmBgYGBgAAAKuwDtbIwH5AAAAABJRU5ErkJggg=="
        )
        with tempfile.NamedTemporaryFile(prefix="ordenowa-product-", suffix=".png") as image_file:
            image_file.write(png)
            image_file.flush()
            visible(driver, "#product_images").send_keys(image_file.name)
            visible(driver, 'button[name="submitKuraneaProductSave"]').click()

        WebDriverWait(driver, 45).until(
            lambda browser: "상품 ID" in browser.find_element(By.TAG_NAME, "body").text
            and "저장했습니다" in browser.find_element(By.TAG_NAME, "body").text
        )
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
        currently_selected = {box.get_attribute("value") for box in category_boxes if box.is_selected()}
        alternate_categories = [box.get_attribute("value") for box in category_boxes if box.get_attribute("value") not in currently_selected]
        expected_category_ids = {alternate_categories[0]} if alternate_categories else currently_selected
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
        driver.save_screenshot(str(DEST / "product-admin-edited-desktop.png"))

        stage = "mobile_product_admin_layout"
        driver.set_window_size(390, 844)
        driver.execute_script("window.scrollTo(0, 0)")
        visible(driver, "#name_ja")
        overflow = driver.execute_script("return document.documentElement.scrollWidth > window.innerWidth + 2")
        if overflow:
            raise AssertionError("Korean product manager form overflows the mobile viewport")
        driver.save_screenshot(str(DEST / "product-admin-mobile.png"))
        print(f"PASS: Chromium created and edited inactive native product ID={product_id}; image {old_image_id} replaced.")
    except Exception as error:
        diagnostic = f"ORDENOWA_PRODUCT_ADMIN_STAGE={stage}; error={type(error).__name__}: {error}"
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
        raise
    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    run()
