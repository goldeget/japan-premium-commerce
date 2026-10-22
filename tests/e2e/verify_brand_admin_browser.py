#!/usr/bin/env python3
"""Upload, preview, and publish the approved brand in a disposable CI shop."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
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
OFFICIAL_UPLOADS = {
    "primary_logo": SOURCES / "ORDENOWA-logo.png",
    "favicon_symbol": SOURCES / "ORDENOWA-favicon-source.png",
    "pwa_icon": SOURCES / "ORDENOWA-pwa-icon-source.png",
}
SEO_TITLE = "ORDENOWA CI QA"
SEO_DESCRIPTION = "ORDENOWA CI SEO description"


def expected_derivative_path(source: Path, filename: str) -> str:
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    return f"/img/ordenowa/versions/{source_hash}/{filename}"


def assert_uploaded_derivative_url(url: str, source: Path, filename: str, role: str) -> None:
    expected_path = expected_derivative_path(source, filename)
    if not urlparse(url).path.endswith(expected_path):
        raise AssertionError(f"published {role} does not use the uploaded official source derivative")


def find_asset_url(items: list[dict], rel: str, source: Path, filename: str) -> str:
    expected_path = expected_derivative_path(source, filename)
    return next(
        (
            item["href"]
            for item in items
            if item["rel"] == rel and urlparse(item["href"]).path.endswith(expected_path)
        ),
        "",
    )


def visible(driver: webdriver.Chrome, selector: str):
    return WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))


def asset_preview_url_for_field(driver: webdriver.Chrome, field_id: str) -> str:
    field = visible(driver, f"#{field_id}")
    return driver.execute_script(
        "return arguments[0].closest('.ordenowa-profile-field')?.querySelector('.ordenowa-asset-preview')?.src || '';",
        field,
    )


def public_brand_snapshot(driver: webdriver.Chrome) -> dict:
    driver.get(BASE + "/")
    snapshot = driver.execute_async_script(
        """
        const done = arguments[0];
        (async () => {
          const manifestHref = document.querySelector('link[rel="manifest"]')?.href || '';
          const manifest = manifestHref
            ? await (await fetch(manifestHref, {cache: 'no-store'})).json()
            : {};
          return {
            logo: document.querySelector('picture img.kuranea-brand__image')?.currentSrc || '',
            title: document.title,
            description: document.querySelector('meta[name="description"]')?.content || '',
            ogTitle: document.querySelector('meta[property="og:title"]')?.content || '',
            ogDescription: document.querySelector('meta[property="og:description"]')?.content || '',
            themeColor: document.querySelector('meta[name="theme-color"]')?.content || '',
            icons: [...document.querySelectorAll('link[rel="icon"],link[rel="apple-touch-icon"]')]
              .map(link => [link.rel, link.href]).sort(),
            ogImage: document.querySelector('meta[property="og:image"]')?.content || '',
            manifest: {
              name: manifest.name || '',
              short_name: manifest.short_name || '',
              theme_color: manifest.theme_color || '',
              background_color: manifest.background_color || '',
              icons: (manifest.icons || []).map(icon => [icon.src, icon.sizes || '', icon.purpose || ''])
            }
          };
        })().then(done).catch(error => done({error: String(error)}));
        """
    )
    if snapshot.get("error"):
        raise AssertionError("current public brand metadata could not be read before and after saving the draft")
    if not snapshot.get("logo") or not snapshot.get("title") or not snapshot.get("manifest", {}).get("name"):
        raise AssertionError("the current public brand logo, SEO title, or PWA metadata is missing")
    return snapshot


def click_centered(driver: webdriver.Chrome, element) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element)
    WebDriverWait(driver, 30).until(EC.element_to_be_clickable(element))
    WebDriverWait(driver, 10).until(
        lambda browser: browser.execute_script(
            """
            const element = arguments[0];
            const rect = element.getBoundingClientRect();
            const target = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
            return Boolean(target && (target === element || element.contains(target)));
            """,
            element,
        )
    )
    element.click()


def emit_publish_target_diagnostics(driver: webdriver.Chrome, selector: str) -> None:
    try:
        metadata = driver.execute_script(
            r"""
            const selector = arguments[0];
            const element = document.querySelector(selector);
            const safeTokens = value => String(value || '')
              .split(/[^A-Za-z0-9_-]+/)
              .filter(Boolean)
              .slice(0, 12);
            return {
              selector,
              present: Boolean(element),
              connected: Boolean(element && element.isConnected),
              tag: element ? element.tagName.toLowerCase() : '',
              id: safeTokens(element && element.id).join(' '),
              class: safeTokens(element && element.className)
            };
            """,
            selector,
        )
    except Exception:
        metadata = {
            "selector": selector,
            "present": False,
            "connected": False,
            "tag": "",
            "id": "",
            "class": [],
        }
    print(
        "ORDENOWA_PUBLISH_STALE_TARGET=" + json.dumps(metadata, ensure_ascii=True, sort_keys=True),
        file=sys.stderr,
    )


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
    assert_uploaded_derivative_url(
        logo["src"], OFFICIAL_UPLOADS["primary_logo"], expected_logo, label + " header logo"
    )

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
          for (const icon of manifest.icons || []) {
            icons.push({src: icon.src, sizes: icon.sizes, purpose: icon.purpose, ...await load(icon.src)});
          }
          const description = document.querySelector('meta[name="description"]')?.content || '';
          const ogTitle = document.querySelector('meta[property="og:title"]')?.content || '';
          const ogDescription = document.querySelector('meta[property="og:description"]')?.content || '';
          const themeColor = document.querySelector('meta[name="theme-color"]')?.content || '';
          return {assetLinks, og, ogImage, manifest, icons, title: document.title, description, ogTitle, ogDescription, themeColor};
        })().then(done).catch(error => done({error: String(error)}));
        """
    )
    if results.get("error"):
        raise AssertionError("brand favicon, Apple icon, OG image, or PWA asset failed browser decoding")
    rels = {item["rel"] for item in results["assetLinks"]}
    if "icon" not in rels or "apple-touch-icon" not in rels:
        raise AssertionError("favicon or Apple Touch Icon link is missing")
    assert_uploaded_derivative_url(
        find_asset_url(
            results["assetLinks"], "icon", OFFICIAL_UPLOADS["favicon_symbol"], "favicon.ico"
        ),
        OFFICIAL_UPLOADS["favicon_symbol"],
        "favicon.ico",
        "favicon",
    )
    for filename in ("favicon-16.png", "favicon-32.png"):
        assert_uploaded_derivative_url(
            find_asset_url(
                results["assetLinks"], "icon", OFFICIAL_UPLOADS["favicon_symbol"], filename
            ),
            OFFICIAL_UPLOADS["favicon_symbol"],
            filename,
            "favicon",
        )
    assert_uploaded_derivative_url(
        find_asset_url(
            results["assetLinks"], "apple-touch-icon", OFFICIAL_UPLOADS["pwa_icon"], "apple-touch-icon.png"
        ),
        OFFICIAL_UPLOADS["pwa_icon"],
        "apple-touch-icon.png",
        "Apple Touch Icon",
    )
    assert_uploaded_derivative_url(
        results["og"], OFFICIAL_UPLOADS["primary_logo"], "og-brand.png", "Open Graph image"
    )
    if results["ogImage"]["width"] != 1200 or results["ogImage"]["height"] != 630:
        raise AssertionError("the approved Open Graph image dimensions are incorrect")
    if len(results["icons"]) != 3 or not any(item["purpose"] == "maskable" for item in results["icons"]):
        raise AssertionError("PWA manifest does not expose the approved any and maskable icons")
    pwa_icon_expectations = (
        ("pwa-192.png", "192x192", "any", 192, 192),
        ("pwa-512.png", "512x512", "any", 512, 512),
        ("pwa-maskable-512.png", "512x512", "maskable", 512, 512),
    )
    for filename, declared_size, purpose, width, height in pwa_icon_expectations:
        icon_url = next(
            (
                item
                for item in results["icons"]
                if urlparse(item["src"]).path.endswith("/" + filename)
            ),
            None,
        )
        if icon_url is None:
            raise AssertionError("PWA manifest is missing " + filename)
        assert_uploaded_derivative_url(
            icon_url["src"], OFFICIAL_UPLOADS["pwa_icon"], filename, "PWA icon"
        )
        if (icon_url["sizes"], icon_url["purpose"], icon_url["width"], icon_url["height"]) != (
            declared_size,
            purpose,
            width,
            height,
        ):
            raise AssertionError(
                "PWA manifest size, purpose, or decoded dimensions are incorrect for " + filename
            )
    if SEO_TITLE not in results["title"]:
        raise AssertionError("Korean admin SEO title update did not publish to the customer page")
    if results["description"] != SEO_DESCRIPTION:
        raise AssertionError("Korean admin SEO description did not publish to the customer page")
    if results["ogTitle"] != SEO_TITLE:
        raise AssertionError("Korean admin SEO title did not publish to Open Graph metadata")
    if results["ogDescription"] != SEO_DESCRIPTION:
        raise AssertionError("Korean admin SEO description did not publish to Open Graph metadata")
    if (
        results["manifest"].get("name") != "ORDENOWA CI QA"
        or results["manifest"].get("short_name") != "ORDENOWA CI"
        or results["manifest"].get("theme_color") != "#244a7d"
        or results["manifest"].get("background_color") != "#f5f7fa"
    ):
        raise AssertionError("Korean admin PWA names or colors did not publish to the app manifest")
    if results["themeColor"] != "#244a7d":
        raise AssertionError("Korean admin PWA theme color did not publish to customer metadata")


def assert_seller_disclosures_remain_gated(driver: webdriver.Chrome, private_values: list[str]) -> None:
    driver.get(BASE + "/")
    legal_link = visible(driver, ".ordenowa-legal-page-link a")
    legal_url = urljoin(driver.current_url, legal_link.get_attribute("href") or "")
    if urlparse(legal_url).netloc != urlparse(BASE).netloc:
        raise AssertionError("published legal page link left the isolated storefront")

    driver.get(legal_url)
    page = visible(driver, ".ordenowa-legal-page")
    visible(driver, ".ordenowa-legal-page__closed")
    leaked_values = [value for value in private_values if value and value in page.text]
    if leaked_values:
        raise AssertionError("pending seller disclosures leaked to the customer legal page")
    driver.save_screenshot(str(DEST / "brand-legal-page-gated.png"))


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

        stage = "public_brand_baseline_before_draft"
        public_before_draft = public_brand_snapshot(driver)
        driver.save_screenshot(str(DEST / "brand-customer-before-draft.png"))
        driver.get(settings_url)
        visible(driver, "form.ordenowa-profile-settings")

        stage = "official_asset_upload"
        for slot, source in OFFICIAL_UPLOADS.items():
            if not source.is_file():
                raise AssertionError("official ORDENOWA source file is missing from the checkout")
            visible(driver, f'input[name="brand_uploads[{slot}]"]').send_keys(str(source.resolve()))

        title = visible(driver, 'input[name="profile[seo][title][ja-JP]"]')
        title.clear()
        title.send_keys(SEO_TITLE)
        pwa_name = visible(driver, 'input[name="profile[pwa][name][ja-JP]"]')
        pwa_name.clear()
        pwa_name.send_keys("ORDENOWA CI QA")
        ci_settings = {
            'input[name="profile[seller][legal_name][ja-JP]"]': "ORDENOWA CI SELLER JP",
            'input[name="profile[seller][legal_name][en-US]"]': "ORDENOWA CI SELLER EN",
            'input[name="profile[seller][legal_name][ko-KR]"]': "ORDENOWA CI SELLER KR",
            'input[name="profile[seller][corporate_number]"]': "1234567890123",
            'input[name="profile[seller][address][ja-JP]"]': "ORDENOWA CI SELLER ADDRESS JP",
            'input[name="profile[seller][address][en-US]"]': "ORDENOWA CI SELLER ADDRESS EN",
            'input[name="profile[seller][address][ko-KR]"]': "ORDENOWA CI SELLER ADDRESS KR",
            'input[name="profile[seller][representative][ja-JP]"]': "ORDENOWA CI REPRESENTATIVE JP",
            'input[name="profile[seller][representative][en-US]"]': "ORDENOWA CI REPRESENTATIVE EN",
            'input[name="profile[seller][representative][ko-KR]"]': "ORDENOWA CI REPRESENTATIVE KR",
            'input[name="profile[seller][responsible_person][ja-JP]"]': "ORDENOWA CI RESPONSIBLE JP",
            'input[name="profile[seller][responsible_person][en-US]"]': "ORDENOWA CI RESPONSIBLE EN",
            'input[name="profile[seller][responsible_person][ko-KR]"]': "ORDENOWA CI RESPONSIBLE KR",
            'input[name="profile[seller][support][phone]"]': "03-1111-2222",
            'input[name="profile[seller][support][email]"]': "seller-ci@example.invalid",
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
            'textarea[name="profile[seo][description][ja-JP]"]': SEO_DESCRIPTION,
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

        stage = "replace_logo_in_saved_draft"
        replacement_logo = visible(driver, 'input[name="brand_uploads[primary_logo]"]')
        replacement_logo.send_keys(str(OFFICIAL_UPLOADS["pwa_icon"].resolve()))
        visible(driver, 'form.ordenowa-profile-settings button[name="submitOrdenowaSaveDraft"]').click()
        WebDriverWait(driver, 30).until(
            lambda browser: "초안을 저장했습니다" in browser.find_element(By.TAG_NAME, "body").text
        )
        assert_uploaded_derivative_url(
            asset_preview_url_for_field(driver, "ordenowa-brand-assets-header_desktop"),
            OFFICIAL_UPLOADS["pwa_icon"],
            "header-desktop.png",
            "temporary replacement draft logo",
        )
        driver.save_screenshot(str(DEST / "brand-admin-replacement-draft.png"))
        stage = "public_brand_unchanged_after_replacement_draft"
        public_after_replacement = public_brand_snapshot(driver)
        if public_after_replacement != public_before_draft:
            raise AssertionError("saving an alternate-logo draft changed the current public storefront brand or SEO")
        driver.save_screenshot(str(DEST / "brand-customer-unpublished-replacement.png"))
        driver.get(settings_url)
        visible(driver, "form.ordenowa-profile-settings")

        stage = "restore_approved_logo_in_saved_draft"
        restored_logo = visible(driver, 'input[name="brand_uploads[primary_logo]"]')
        restored_logo.send_keys(str(OFFICIAL_UPLOADS["primary_logo"].resolve()))
        visible(driver, 'form.ordenowa-profile-settings button[name="submitOrdenowaSaveDraft"]').click()
        WebDriverWait(driver, 30).until(
            lambda browser: "초안을 저장했습니다" in browser.find_element(By.TAG_NAME, "body").text
        )
        assert_uploaded_derivative_url(
            asset_preview_url_for_field(driver, "ordenowa-brand-assets-header_desktop"),
            OFFICIAL_UPLOADS["primary_logo"],
            "header-desktop.png",
            "restored approved draft logo",
        )
        driver.save_screenshot(str(DEST / "brand-admin-uploaded-draft-restored.png"))

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
        preview_derivatives = (
            ("header-desktop.png", "primary_logo"),
            ("header-mobile.png", "primary_logo"),
            ("admin-login.png", "primary_logo"),
            ("email-logo.png", "primary_logo"),
            ("favicon-32.png", "favicon_symbol"),
            ("apple-touch-icon.png", "pwa_icon"),
            ("pwa-512.png", "pwa_icon"),
            ("og-brand.png", "primary_logo"),
        )
        preview_urls = [image.get_attribute("src") or "" for image in preview_images]
        for filename, slot in preview_derivatives:
            preview_url = next(
                (url for url in preview_urls if urlparse(url).path.endswith("/" + filename)),
                "",
            )
            assert_uploaded_derivative_url(
                preview_url, OFFICIAL_UPLOADS[slot], filename, "admin preview " + filename
            )
        WebDriverWait(driver, 30).until(
            lambda browser: all(
                int(image.get_attribute("naturalWidth") or 0) > 0
                for image in browser.find_elements(By.CSS_SELECTOR, ".ordenowa-profile-preview img")
            )
        )
        driver.save_screenshot(str(DEST / "brand-admin-private-preview.png"))

        publish_selector = 'form.ordenowa-profile-settings button[name="submitOrdenowaPublish"]'
        stage = "publish_button_find"
        publish_button = visible(driver, publish_selector)
        stage = "publish_button_click"
        try:
            click_centered(driver, publish_button)
        except StaleElementReferenceException:
            emit_publish_target_diagnostics(driver, publish_selector)
            raise
        stage = "publish_confirmation"
        WebDriverWait(driver, 30).until(lambda browser: "변경사항을 게시했습니다" in browser.find_element(By.TAG_NAME, "body").text)
        if "확인 대기" not in driver.find_element(By.ID, "ordenowa-company").text:
            raise AssertionError("seller authorization must remain pending after brand publication")
        for selector, expected in ci_settings.items():
            if visible(driver, selector).get_attribute("value") != expected:
                raise AssertionError("a Korean admin operating setting did not persist after publication")
        driver.save_screenshot(str(DEST / "brand-admin-published.png"))

        stage = "published_desktop_customer_brand"
        assert_public_brand_assets(driver, "desktop", "header-desktop.png")
        driver.save_screenshot(str(DEST / "brand-desktop-published.png"))

        stage = "published_mobile_customer_brand"
        driver.set_window_size(390, 844)
        assert_public_brand_assets(driver, "mobile", "header-mobile.png")
        driver.save_screenshot(str(DEST / "brand-mobile-published.png"))

        stage = "pending_seller_disclosures_remain_gated"
        private_disclosure_groups = ("seller", "company_reference", "customer_support", "shipping", "refund")
        private_values = [
            value
            for selector, value in ci_settings.items()
            if any(f"[{group}]" in selector for group in private_disclosure_groups)
        ]
        assert_seller_disclosures_remain_gated(driver, private_values)

        stage = "admin_login_after_publish"
        driver.delete_all_cookies()
        driver.get(ADMIN_LOGIN + "/login")
        login_logo = image_is_rendered(driver, ".ordenowa-admin-login-brand img")
        if login_logo["width"] < 1 or "admin-login.png" not in login_logo["src"]:
            raise AssertionError("published ORDENOWA admin login logo did not render")
        assert_uploaded_derivative_url(
            login_logo["src"], OFFICIAL_UPLOADS["primary_logo"], "admin-login.png", "admin login logo"
        )
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
