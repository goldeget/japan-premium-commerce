#!/usr/bin/env python3
"""Upload, preview, and publish the approved brand in a disposable CI shop."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE = os.environ["SHOP_BASE_URL"].rstrip("/")
ADMIN_LOGIN = os.environ["ADMIN_LOGIN_URL"].rstrip("/")
ADMIN_EMAIL = os.environ["ADMIN_MAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWD"]
DEST = Path(os.environ["QA_ARTIFACT_DIR"])
ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "assets" / "brand" / "ordenowa" / "official_originals"
DEST.mkdir(parents=True, exist_ok=True)


def visible(driver: webdriver.Chrome, selector: str):
    return WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))


def image_is_rendered(driver: webdriver.Chrome, selector: str) -> dict:
    image = visible(driver, selector)
    return driver.execute_script(
        "return {src: arguments[0].currentSrc || arguments[0].src, width: arguments[0].naturalWidth, height: arguments[0].naturalHeight};",
        image,
    )


def emit_brand_settings_diagnostics(driver: webdriver.Chrome) -> None:
    diagnostics = driver.execute_script(
        r"""
        const bodyText = document.body?.innerText || '';
        const brandSection = document.querySelector('#ordenowa-brand');
        const visible = element => Boolean(element && element.getClientRects().length);
        return {
          settings_form_visible: visible(document.querySelector('form.ordenowa-profile-settings')),
          brand_section_visible: Boolean(visible(brandSection) && /브랜드·로고/.test(brandSection.innerText || '')),
          access_denied_marker: /(?:access denied|permission denied|you do not have permission|forbidden|권한이 없습니다|접근이 거부|\b403\b)/i.test(bodyText),
          controller_load_error_marker: /(?:controller|module).{0,120}(?:not found|missing|could not be loaded|failed to load|does not exist)|(?:not found|missing|could not be loaded|failed to load|does not exist).{0,120}(?:controller|module)/i.test(bodyText),
          general_error_marker: /(?:internal server error|server error|fatal error|uncaught exception|whoops!?|oops!? an error occurred|something went wrong|\b500\b)/i.test(bodyText),
          login_form_visible: visible(document.querySelector('#login_form, #login-form, form[action*="/login"], input[type="password"]')),
          pathname: window.location.pathname,
          title: document.title
        };
        """
    )
    print(
        "ORDENOWA_BRAND_SETTINGS_DIAGNOSTICS=" + json.dumps(diagnostics, ensure_ascii=False, sort_keys=True),
        file=sys.stderr,
    )


def assert_public_brand_assets(driver: webdriver.Chrome, label: str, expected_logo: str) -> None:
    driver.get(BASE + "/")
    logo = image_is_rendered(driver, "picture img.kuranea-brand__image")
    if logo["width"] < 1 or expected_logo not in logo["src"]:
        raise AssertionError("approved ORDENOWA header logo did not render for " + label)

    results = driver.execute_async_script(
        """
        const done = arguments[0];
        (async () => {
          const assetLinks = [...document.querySelectorAll('link[rel="icon"],link[rel="apple-touch-icon"]')]
            .map(link => ({rel: link.rel, href: link.href}));
          const og = document.querySelector('meta[property="og:image"]')?.content || '';
          const manifestLink = document.querySelector('link[rel="manifest"]')?.href || '';
          const load = async url => {
            const image = new Image(); image.src = url;
            await image.decode();
            return {width: image.naturalWidth, height: image.naturalHeight};
          };
          const decoded = [];
          for (const item of assetLinks) decoded.push({rel: item.rel, ...await load(item.href)});
          const ogImage = await load(og);
          const manifest = await (await fetch(manifestLink, {cache: 'no-store'})).json();
          const icons = [];
          for (const icon of manifest.icons || []) icons.push({sizes: icon.sizes, purpose: icon.purpose, ...await load(icon.src)});
          const description = document.querySelector('meta[name="description"]')?.content || '';
          const themeColor = document.querySelector('meta[name="theme-color"]')?.content || '';
          return {assetLinks, og, ogImage, manifest, icons, title: document.title, description, themeColor};
        })().then(done).catch(error => done({error: String(error)}));
        """
    )
    if results.get("error"):
        raise AssertionError("brand favicon, Apple icon, OG image, or PWA asset failed browser decoding")
    rels = {item["rel"] for item in results["assetLinks"]}
    if "icon" not in rels or "apple-touch-icon" not in rels:
        raise AssertionError("favicon or Apple Touch Icon link is missing")
    if results["ogImage"]["width"] != 1200 or results["ogImage"]["height"] != 630:
        raise AssertionError("the approved Open Graph image dimensions are incorrect")
    if len(results["icons"]) != 3 or not any(item["purpose"] == "maskable" for item in results["icons"]):
        raise AssertionError("PWA manifest does not expose the approved any and maskable icons")
    if "ORDENOWA CI QA" not in results["title"]:
        raise AssertionError("Korean admin SEO title update did not publish to the customer page")
    if results["description"] != "ORDENOWA CI SEO description":
        raise AssertionError("Korean admin SEO description did not publish to the customer page")
    if (
        results["manifest"].get("name") != "ORDENOWA CI QA"
        or results["manifest"].get("short_name") != "ORDENOWA CI"
        or results["manifest"].get("theme_color") != "#244a7d"
        or results["manifest"].get("background_color") != "#f5f7fa"
    ):
        raise AssertionError("Korean admin PWA names or colors did not publish to the app manifest")
    if results["themeColor"] != "#244a7d":
        raise AssertionError("Korean admin PWA theme color did not publish to customer metadata")


def run() -> None:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,960")
    options.add_argument("--lang=ja-JP")
    driver = webdriver.Chrome(options=options)
    stage = "administrator_login"
    try:
        driver.get(ADMIN_LOGIN + "/login")
        login_logo = image_is_rendered(driver, ".ordenowa-admin-login-brand img")
        if login_logo["width"] < 1 or "official-admin-login.png" not in login_logo["src"]:
            raise AssertionError("approved ORDENOWA admin login logo did not render")
        driver.save_screenshot(str(DEST / "brand-admin-login.png"))

        email_fields = driver.find_elements(By.CSS_SELECTOR, '#login_form input[name="email"], input[type="email"]')
        password_fields = driver.find_elements(By.CSS_SELECTOR, '#login_form input[name="passwd"], #login_form input[name="password"], input[type="password"]')
        if not email_fields or not password_fields:
            raise AssertionError("Back Office login form fields are unavailable")
        email_fields[0].send_keys(ADMIN_EMAIL)
        password_fields[0].send_keys(ADMIN_PASSWORD)
        submit = visible(driver, '#login_form button[type="submit"], #login_form input[type="submit"], button[type="submit"]')
        submit.click()
        WebDriverWait(driver, 30).until(lambda browser: "/login" not in urlparse(browser.current_url).path)

        stage = "admin_settings_menu_link"

        def business_profile_links(browser: webdriver.Chrome):
            matches = []
            for link in browser.find_elements(By.CSS_SELECTOR, 'a[href*="controller="]'):
                href = link.get_attribute("href") or ""
                controller = parse_qs(urlparse(href).query).get("controller", [])
                if controller == ["AdminBusinessProfile"]:
                    matches.append(link)
            return matches

        links = WebDriverWait(driver, 30).until(business_profile_links)
        settings_url = urljoin(driver.current_url, links[0].get_attribute("href"))
        settings_location = urlparse(settings_url)
        if settings_location.hostname not in {"localhost", "127.0.0.1"} or not settings_location.path.startswith("/admin-kuranea/"):
            raise AssertionError("business profile menu link is outside this isolated Back Office")

        stage = "korean_brand_settings_form"
        driver.get(settings_url)
        driver.save_screenshot(str(DEST / "brand-settings-after-navigation.png"))
        try:
            visible(driver, "form.ordenowa-profile-settings")
            if "브랜드·로고" not in driver.find_element(By.ID, "ordenowa-brand").text:
                raise AssertionError("Korean brand settings section is missing")
        except Exception:
            emit_brand_settings_diagnostics(driver)
            raise

        stage = "official_asset_upload"
        uploads = {
            "primary_logo": SOURCES / "ORDENOWA-logo.png",
            "favicon_symbol": SOURCES / "ORDENOWA-favicon-source.png",
            "pwa_icon": SOURCES / "ORDENOWA-pwa-icon-source.png",
        }
        for slot, source in uploads.items():
            if not source.is_file():
                raise AssertionError("official ORDENOWA source file is missing from the checkout")
            visible(driver, f'input[name="brand_uploads[{slot}]"]').send_keys(str(source.resolve()))

        title = visible(driver, 'input[name="profile[seo][title][ja-JP]"]')
        title.clear()
        title.send_keys("ORDENOWA CI QA")
        pwa_name = visible(driver, 'input[name="profile[pwa][name][ja-JP]"]')
        pwa_name.clear()
        pwa_name.send_keys("ORDENOWA CI QA")
        ci_settings = {
            'input[name="profile[company_reference][name][ja-JP]"]': "ORDENOWA CI REFERENCE",
            'input[name="profile[company_reference][corporate_number]"]': "0000000000000",
            'input[name="profile[company_reference][postal_code]"]': "000-0000",
            'input[name="profile[company_reference][address]"]': "ORDENOWA CI REFERENCE ADDRESS",
            'input[name="profile[company_reference][phone]"]': "000-0000-0000",
            'input[name="profile[company_reference][representative]"]': "ORDENOWA CI REFERENCE CONTACT",
            'input[name="profile[company_reference][source_url]"]': "https://example.invalid/ci",
            'select[name="profile[company_reference][verification_status]"]': "user_provided_reference",
            'input[name="profile[customer_support][phone]"]': "000-0000-0000",
            'input[name="profile[customer_support][email]"]': "ci-test@example.invalid",
            'input[name="profile[customer_support][hours][ja-JP]"]': "ORDENOWA CI SUPPORT HOURS",
            'textarea[name="profile[shipping][ja-JP]"]': "ORDENOWA CI SHIPPING POLICY",
            'textarea[name="profile[refund][ja-JP]"]': "ORDENOWA CI REFUND POLICY",
            'textarea[name="profile[seo][description][ja-JP]"]': "ORDENOWA CI SEO description",
            'input[name="profile[pwa][short_name][ja-JP]"]': "ORDENOWA CI",
            'input[name="profile[pwa][theme_color]"]': "#244a7d",
            'input[name="profile[pwa][background_color]"]': "#f5f7fa",
        }
        for selector, value in ci_settings.items():
            field = visible(driver, selector)
            if field.tag_name.lower() == "select":
                Select(field).select_by_value(value)
            else:
                field.clear()
                field.send_keys(value)
        visible(driver, 'form.ordenowa-profile-settings button[name="submitOrdenowaSaveDraft"]').click()
        WebDriverWait(driver, 30).until(lambda browser: "초안을 저장했습니다" in browser.find_element(By.TAG_NAME, "body").text)
        for selector, expected in ci_settings.items():
            if visible(driver, selector).get_attribute("value") != expected:
                raise AssertionError("a Korean admin operating setting did not persist in its draft")
        driver.save_screenshot(str(DEST / "brand-admin-uploaded-draft.png"))

        stage = "private_admin_preview"
        current_draft_row = WebDriverWait(driver, 30).until(
            lambda browser: next(
                row for row in browser.find_elements(By.CSS_SELECTOR, ".ordenowa-profile-history tbody tr")
                if "현재 초안" in row.text
            )
        )
        current_draft_row.find_element(By.CSS_SELECTOR, 'button[name="submitOrdenowaPreview"]').click()
        preview = visible(driver, ".ordenowa-profile-preview")
        for expected in ("000-0000-0000", "ORDENOWA CI SHIPPING POLICY", "ORDENOWA CI REFUND POLICY"):
            if expected not in preview.text:
                raise AssertionError("Korean admin operating settings are missing from the private preview")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", preview)
        preview_images = preview.find_elements(By.TAG_NAME, "img")
        if len(preview_images) < 7:
            raise AssertionError("saved brand preview does not show desktop, mobile, email, favicon, Apple, PWA, and OG assets")
        WebDriverWait(driver, 30).until(
            lambda browser: all(
                int(image.get_attribute("naturalWidth") or 0) > 0
                for image in browser.find_elements(By.CSS_SELECTOR, ".ordenowa-profile-preview img")
            )
        )
        driver.save_screenshot(str(DEST / "brand-admin-private-preview.png"))

        stage = "publish_approved_brand"
        visible(driver, 'form.ordenowa-profile-settings button[name="submitOrdenowaPublish"]').click()
        WebDriverWait(driver, 30).until(lambda browser: "변경사항을 게시했습니다" in browser.find_element(By.TAG_NAME, "body").text)
        if "확인 대기" not in driver.find_element(By.ID, "ordenowa-company").text:
            raise AssertionError("seller authorization must remain pending after brand publication")
        driver.save_screenshot(str(DEST / "brand-admin-published.png"))

        stage = "published_desktop_customer_brand"
        assert_public_brand_assets(driver, "desktop", "header-desktop.png")
        driver.save_screenshot(str(DEST / "brand-desktop-published.png"))

        stage = "published_mobile_customer_brand"
        driver.set_window_size(390, 844)
        assert_public_brand_assets(driver, "mobile", "header-mobile.png")
        driver.save_screenshot(str(DEST / "brand-mobile-published.png"))

        stage = "admin_login_after_publish"
        driver.delete_all_cookies()
        driver.get(ADMIN_LOGIN + "/login")
        login_logo = image_is_rendered(driver, ".ordenowa-admin-login-brand img")
        if login_logo["width"] < 1 or "admin-login.png" not in login_logo["src"]:
            raise AssertionError("published ORDENOWA admin login logo did not render")
        driver.save_screenshot(str(DEST / "brand-admin-login-after-publish.png"))

        print("PASS: official ORDENOWA uploads, Korean draft preview, publish, PC/mobile logos, admin login, favicon, Apple icon, PWA, OG, and SEO")
    except Exception as error:
        try:
            driver.save_screenshot(str(DEST / "brand-admin-failure.png"))
        except Exception:
            pass
        print(f"FAIL: ORDENOWA brand browser flow at {stage} ({type(error).__name__})", file=sys.stderr)
        print(f"::error title=ORDENOWA brand browser QA::{stage} ({type(error).__name__})", file=sys.stderr)
        raise SystemExit("isolated ORDENOWA brand browser flow failed") from None
    finally:
        driver.quit()


if __name__ == "__main__":
    run()
