#!/usr/bin/env python3
"""Upload, preview, and publish the approved brand in a disposable CI shop."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import sys
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urljoin, urlparse

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
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
ASSET_MANIFEST = ROOT / "assets" / "brand" / "ordenowa" / "asset-manifest.json"
APPROVED_DERIVED_ASSETS = json.loads(ASSET_MANIFEST.read_text(encoding="utf-8"))["derived"]
DEST.mkdir(parents=True, exist_ok=True)
EXPECTED_SHOP_PORT = 18080
OFFICIAL_UPLOADS = {
    "primary_logo": SOURCES / "ORDENOWA-logo.png",
    "favicon_symbol": SOURCES / "ORDENOWA-favicon-source.png",
    "pwa_icon": SOURCES / "ORDENOWA-pwa-icon-source.png",
}
SEO_TITLE = 'ORDENOWA CI QA " </title><meta id="ordenowa-seo-title-inert-sentinel">'
SEO_DESCRIPTION = 'ORDENOWA CI SEO description "><meta id="ordenowa-seo-description-inert-sentinel">'
SEO_TITLE_EN = "ORDENOWA CI SEO TITLE EN"
SEO_DESCRIPTION_EN = "ORDENOWA CI SEO DESCRIPTION EN"
SEO_TITLE_KO = "ORDENOWA CI SEO TITLE KO"
SEO_DESCRIPTION_KO = "ORDENOWA CI SEO DESCRIPTION KO"
SEO_JSONLD_BRAND_NAME = 'ORDENOWA CI BRAND JP </script><meta id="ordenowa-jsonld-inert-sentinel">'
BRAND_DRAFT_REPLACEMENT_ATTEMPTS = 3
BRAND_DIAGNOSTIC_MAX_MATCHES = 5
BRAND_DIAGNOSTIC_CONTEXT_CHARS = 64
BRAND_DIAGNOSTIC_SNIPPET_CHARS = 160


def validate_isolated_ci_compose_project() -> None:
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    expected_project = f"kuranea-ci-{run_id}-{attempt}"
    if (
        os.environ.get("CI") != "true"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("KURANEA_ISOLATED_CI") != "1"
        or not run_id.isascii()
        or not run_id.isdecimal()
        or not attempt.isascii()
        or not attempt.isdecimal()
        or os.environ.get("CI_COMPOSE_PROJECT_NAME", "") != expected_project
        or not ADMIN_EMAIL.strip().lower().endswith("@example.invalid")
    ):
        raise ValueError("brand admin QA requires its exact isolated GitHub Actions Compose project")


def _loopback_http_origin(value: str, label: str) -> tuple[str, str, int]:
    try:
        parsed = urlparse(value)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        raise ValueError(f"{label} must be a valid isolated loopback URL") from None
    if host.lower() == "localhost":
        is_loopback = True
    else:
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            is_loopback = False
    if (
        parsed.scheme != "http"
        or not is_loopback
        or port != EXPECTED_SHOP_PORT
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} must use the isolated loopback shop origin on port {EXPECTED_SHOP_PORT}")
    return parsed.scheme, host.lower(), port


def validate_loopback_admin_targets() -> None:
    shop = urlparse(BASE)
    admin = urlparse(ADMIN_LOGIN)
    if shop.path not in ("", "/"):
        raise ValueError("SHOP_BASE_URL must be the isolated shop root")
    shop_origin = _loopback_http_origin(BASE, "SHOP_BASE_URL")
    admin_origin = _loopback_http_origin(ADMIN_LOGIN, "ADMIN_LOGIN_URL")
    if (
        admin_origin != shop_origin
        or admin.path.rstrip("/") != "/admin-kuranea"
    ):
        raise ValueError("ADMIN_LOGIN_URL must share the isolated shop origin and name its Back Office path")


def expected_derivative_path(source: Path, filename: str) -> str:
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    return f"/img/ordenowa/versions/{source_hash}/{filename}"


def assert_uploaded_derivative_url(url: str, source: Path, filename: str, role: str) -> None:
    expected_path = expected_derivative_path(source, filename)
    if not urlparse(url).path.endswith(expected_path):
        raise AssertionError(f"published {role} does not use the uploaded official source derivative")


def json_contains_string(value: object, expected: str) -> bool:
    if isinstance(value, str):
        return value == expected
    if isinstance(value, list):
        return any(json_contains_string(item, expected) for item in value)
    if isinstance(value, dict):
        return any(json_contains_string(item, expected) for item in value.values())
    return False


def assert_hostile_seo_and_jsonld_rendering(
    results: dict,
    expected_title: str,
    expected_description: str,
    expected_jsonld_brand_name: str,
    stage_callback: Callable[[str], None],
) -> None:
    stage_callback("hostile_seo_title")
    if results.get("title") != expected_title:
        raise AssertionError("Smarty did not preserve the complete SEO title as inert title text")

    stage_callback("hostile_seo_description")
    if results.get("description") != expected_description:
        raise AssertionError("Smarty did not preserve the complete SEO description attribute value")

    stage_callback("hostile_seo_open_graph")
    if results.get("ogTitle") != expected_title or results.get("ogDescription") != expected_description:
        raise AssertionError("Smarty did not preserve the complete Open Graph metadata attribute values")

    stage_callback("hostile_seo_dom_sentinels")
    sentinels = results.get("inertSentinels") or []
    if sentinels:
        raise AssertionError("hostile SEO input created inert HTML elements: " + ", ".join(sentinels))

    stage_callback("hostile_seo_jsonld_present")
    scripts = results.get("jsonLdScripts") or []
    if not scripts:
        raise AssertionError("the rendered customer page has no JSON-LD for the script-safe serialization check")
    parsed_scripts = []
    for script_source in scripts:
        stage_callback("hostile_seo_jsonld_parse")
        try:
            parsed_scripts.append(json.loads(script_source))
        except (TypeError, ValueError):
            raise AssertionError("Smarty emitted invalid JSON-LD script text") from None

    stage_callback("hostile_seo_jsonld_value")
    if not any(json_contains_string(script, expected_jsonld_brand_name) for script in parsed_scripts):
        raise AssertionError("JSON-LD did not preserve the hostile brand name as a decoded string value")


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


def same_storefront_origin(url: str) -> bool:
    def origin_parts(value: str) -> tuple[str, str, int] | None:
        parsed = urlparse(value)
        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").lower()
        if scheme not in ("http", "https") or not hostname:
            return None
        port = parsed.port
        if port is None:
            port = 443 if scheme == "https" else 80
        return scheme, hostname, port

    try:
        url_origin = origin_parts(url)
        base_origin = origin_parts(BASE)
        return url_origin is not None and url_origin == base_origin
    except ValueError:
        return False


def generated_storefront_language_url(driver: webdriver.Chrome, iso_code: str) -> str:
    driver.get(BASE + "/")
    selector = f'select.js-language-selector option[data-iso-code="{iso_code}"]'
    option = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
    )
    href = option.get_attribute("value")
    if not href:
        raise AssertionError("the storefront language selector has no generated destination")
    language_url = urljoin(driver.current_url, href)
    if not same_storefront_origin(language_url):
        raise AssertionError("the storefront language selector left the isolated storefront")
    return language_url


def visible(driver: webdriver.Chrome, selector: str):
    return WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))


def restore_approved_logo_after_failure(
    driver: webdriver.Chrome,
    settings_url: str,
    stage_callback: Callable[[str], None],
) -> None:
    """Republish the approved source if a replacement test aborts mid-flight."""
    driver.delete_all_cookies()
    driver.get(ADMIN_LOGIN + "/login")
    restore_admin_session(driver, stage_callback, "replacement_failure_cleanup_admin_login")
    settings_url = business_profile_settings_url(driver)
    driver.get(settings_url)
    visible(driver, "form.ordenowa-profile-settings")
    replace_primary_logo_in_saved_draft(
        driver,
        settings_url,
        OFFICIAL_UPLOADS["primary_logo"],
        "failure cleanup restore approved logo",
    )
    publish_saved_brand_draft(driver, stage_callback, "replacement_failure_cleanup_publish")
    alternate_source = OFFICIAL_UPLOADS["pwa_icon"]
    assert_published_logo_source(
        driver,
        OFFICIAL_UPLOADS["primary_logo"],
        expected_previous_header_logos={
            "desktop": urljoin(BASE, expected_derivative_path(alternate_source, "header-desktop.png")),
            "mobile": urljoin(BASE, expected_derivative_path(alternate_source, "header-mobile.png")),
        },
        expected_previous_admin_login_logo=urljoin(
            BASE, expected_derivative_path(alternate_source, "admin-login.png")
        ),
        stage_callback=stage_callback,
        stage_prefix="replacement_failure_cleanup_verify",
    )


def wait_for_draft_save_confirmation(driver: webdriver.Chrome) -> None:
    def confirmation_is_visible(browser: webdriver.Chrome) -> bool:
        try:
            return "초안을 저장했습니다" in browser.find_element(By.TAG_NAME, "body").text
        except StaleElementReferenceException:
            return False

    WebDriverWait(driver, 30).until(
        confirmation_is_visible
    )


def wait_for_publish_confirmation(driver: webdriver.Chrome) -> None:
    def publication_is_visible(browser: webdriver.Chrome) -> bool:
        try:
            success_alert = any(
                alert.is_displayed() and "변경사항을 게시했습니다." in alert.text
                for alert in browser.find_elements(By.CSS_SELECTOR, ".alert.alert-success")
            )
            company = browser.find_element(By.ID, "ordenowa-company")
            return success_alert and "확인 대기" in company.text
        except StaleElementReferenceException:
            return False

    WebDriverWait(driver, 30).until(publication_is_visible)


def wait_for_restore_confirmation(driver: webdriver.Chrome) -> None:
    def restoration_is_visible(browser: webdriver.Chrome) -> bool:
        try:
            return any(
                alert.is_displayed()
                and "이전 설정을 새 초안으로 복원했습니다" in alert.text
                for alert in browser.find_elements(By.CSS_SELECTOR, ".alert.alert-success")
            )
        except StaleElementReferenceException:
            return False

    WebDriverWait(driver, 30).until(restoration_is_visible)


def assert_saved_primary_logo(driver: webdriver.Chrome, source: Path, role: str) -> None:
    assert_uploaded_derivative_url(
        asset_preview_url_for_field(driver, "ordenowa-brand-assets-header_desktop"),
        source,
        "header-desktop.png",
        role,
    )


def replace_primary_logo_in_saved_draft(
    driver: webdriver.Chrome,
    settings_url: str,
    source: Path,
    role: str,
    stage_callback: Callable[[str], None] | None = None,
    stage_prefix: str = "replacement_draft",
) -> None:
    upload_selector = 'input[name="brand_uploads[primary_logo]"]'
    save_selector = 'form.ordenowa-profile-settings button[name="submitOrdenowaSaveDraft"]'
    last_stale: StaleElementReferenceException | None = None

    def report(stage_name: str) -> None:
        if stage_callback is not None:
            stage_callback(stage_prefix + "_" + stage_name)

    def wait_for_settings_form(stage_name: str) -> None:
        report(stage_name)
        try:
            visible(driver, "form.ordenowa-profile-settings")
        except TimeoutException:
            try:
                emit_brand_settings_diagnostics(driver)
            except Exception:
                pass
            raise

    # Reload to discard stale references and any confirmation left by the previous draft save.
    report("initial_reload")
    driver.get(settings_url)
    wait_for_settings_form("draft_form_wait")

    for attempt in range(1, BRAND_DRAFT_REPLACEMENT_ATTEMPTS + 1):
        try:
            report(f"upload_input_wait_attempt_{attempt}")
            upload_input = visible(driver, upload_selector)
            report(f"upload_attempt_{attempt}")
            upload_input.send_keys(str(source.resolve()))
        except StaleElementReferenceException as error:
            last_stale = error
            if attempt == BRAND_DRAFT_REPLACEMENT_ATTEMPTS:
                break
            report(f"stale_upload_retry_reload_attempt_{attempt}")
            driver.get(settings_url)
            wait_for_settings_form(f"stale_upload_retry_form_wait_attempt_{attempt}")
            continue

        stale_during_save = False
        try:
            report(f"save_button_wait_attempt_{attempt}")
            save_button = visible(driver, save_selector)
            report(f"save_attempt_{attempt}")
            save_button.click()
        except StaleElementReferenceException as error:
            last_stale = error
            stale_during_save = True
            try:
                report(f"save_confirmation_attempt_{attempt}")
                wait_for_draft_save_confirmation(driver)
            except TimeoutException:
                if attempt == BRAND_DRAFT_REPLACEMENT_ATTEMPTS:
                    break
                report(f"stale_save_retry_reload_attempt_{attempt}")
                driver.get(settings_url)
                wait_for_settings_form(f"stale_save_retry_form_wait_attempt_{attempt}")
                continue
        else:
            report(f"save_confirmation_attempt_{attempt}")
            wait_for_draft_save_confirmation(driver)

        try:
            report(f"saved_derivative_requery_attempt_{attempt}")
            assert_saved_primary_logo(driver, source, role)
        except AssertionError:
            if not stale_during_save or attempt == BRAND_DRAFT_REPLACEMENT_ATTEMPTS:
                raise
            report(f"stale_derivative_retry_reload_attempt_{attempt}")
            driver.get(settings_url)
            wait_for_settings_form(f"stale_derivative_retry_form_wait_attempt_{attempt}")
            continue

        # A reload proves the draft preview is persisted, not just changed in the upload form.
        report("persisted_draft_reload")
        driver.get(settings_url)
        wait_for_settings_form("persisted_form_wait")
        report("persisted_derivative_requery")
        assert_saved_primary_logo(driver, source, role)
        return

    if last_stale is not None:
        raise last_stale
    raise AssertionError("could not replace the primary logo in the saved draft")


def replace_brand_asset_in_saved_draft(
    driver: webdriver.Chrome,
    settings_url: str,
    slot: str,
    preview_field_id: str,
    source: Path,
    filename: str,
    role: str,
    stage_callback: Callable[[str], None],
    stage_prefix: str,
) -> None:
    upload_selector = f'input[name="brand_uploads[{slot}]"]'
    save_selector = 'form.ordenowa-profile-settings button[name="submitOrdenowaSaveDraft"]'

    for attempt in range(1, BRAND_DRAFT_REPLACEMENT_ATTEMPTS + 1):
        stage_callback(f"{stage_prefix}_draft_form_attempt_{attempt}")
        driver.get(settings_url)
        visible(driver, "form.ordenowa-profile-settings")

        try:
            stage_callback(f"{stage_prefix}_upload_attempt_{attempt}")
            visible(driver, upload_selector).send_keys(str(source.resolve()))
            stage_callback(f"{stage_prefix}_save_attempt_{attempt}")
            visible(driver, save_selector).click()
        except StaleElementReferenceException:
            if attempt == BRAND_DRAFT_REPLACEMENT_ATTEMPTS:
                raise
            continue

        try:
            stage_callback(f"{stage_prefix}_save_confirmation_attempt_{attempt}")
            wait_for_draft_save_confirmation(driver)
        except TimeoutException:
            if attempt == BRAND_DRAFT_REPLACEMENT_ATTEMPTS:
                raise
            continue

        stage_callback(f"{stage_prefix}_saved_preview_attempt_{attempt}")
        driver.get(settings_url)
        visible(driver, "form.ordenowa-profile-settings")
        assert_uploaded_derivative_url(
            asset_preview_url_for_field(driver, preview_field_id),
            source,
            filename,
            role + " saved draft preview",
        )
        return

    raise AssertionError("could not replace " + role + " in the saved draft")


def current_draft_history_row(driver: webdriver.Chrome):
    for row in driver.find_elements(By.CSS_SELECTOR, ".ordenowa-profile-history tbody tr"):
        try:
            if "현재 초안" in row.text:
                return row
        except StaleElementReferenceException:
            continue
    return False


def history_row_with_status(driver: webdriver.Chrome, status: str):
    for row in driver.find_elements(By.CSS_SELECTOR, ".ordenowa-profile-history tbody tr"):
        try:
            cells = row.find_elements(By.CSS_SELECTOR, "td")
            if len(cells) >= 4 and status in cells[3].text:
                return row
        except StaleElementReferenceException:
            continue
    return False


def verify_profile_change_row(row, label: str, previous_value: str, current_value: str) -> None:
    details = row.find_element(By.CSS_SELECTOR, "details.ordenowa-history-field-changes")
    if not details.get_attribute("open"):
        details.find_element(By.TAG_NAME, "summary").click()
    for changed_row in details.find_elements(By.CSS_SELECTOR, "tbody tr"):
        if changed_row.find_element(By.CSS_SELECTOR, "th").text.strip() != label:
            continue
        values = changed_row.find_elements(By.CSS_SELECTOR, "td")
        if len(values) < 2 or previous_value not in values[0].text or current_value not in values[1].text:
            raise AssertionError("the profile history did not show the expected previous and current field values")
        return

    raise AssertionError("the profile history omitted a changed field")


def restore_published_history_version_as_draft(
    driver: webdriver.Chrome,
    settings_url: str,
    expected_settings: dict[str, str],
    published_public_snapshot: dict,
    stage_callback: Callable[[str], None],
) -> None:
    """Restore the published history row and prove the customer output remains unchanged."""
    driver.get(settings_url)
    visible(driver, "form.ordenowa-profile-settings")
    stage_callback("history_restore_published_row_wait")
    published_row = WebDriverWait(driver, 30).until(
        lambda browser: history_row_with_status(browser, "게시 중")
    )
    cells = published_row.find_elements(By.CSS_SELECTOR, "td")
    source_version_id = cells[0].text.strip().lstrip("#")
    status = cells[3].text
    if not source_version_id or "현재 초안" in status:
        raise AssertionError("the history restore source must be an older published version")

    restore_button = published_row.find_element(By.CSS_SELECTOR, 'button[name="submitOrdenowaRestore"]')
    if not restore_button.is_enabled():
        raise AssertionError("the older published history version cannot be restored as a draft")
    stage_callback("history_restore_published_row_click")
    restore_button.click()

    stage_callback("history_restore_confirmation")
    wait_for_restore_confirmation(driver)
    visible(driver, "form.ordenowa-profile-settings")

    stage_callback("history_restore_new_draft_check")
    restored_row = WebDriverWait(driver, 30).until(current_draft_history_row)
    restored_cells = restored_row.find_elements(By.CSS_SELECTOR, "td")
    restored_version_id = restored_cells[0].text.strip().lstrip("#")
    if not restored_version_id or source_version_id == restored_version_id:
        raise AssertionError("restoring a historical setting must create a new draft version")
    if "현재 초안" not in restored_cells[3].text:
        raise AssertionError("the restored version is not marked as the current draft")

    source_row_status = ""
    for row in driver.find_elements(By.CSS_SELECTOR, ".ordenowa-profile-history tbody tr"):
        try:
            row_cells = row.find_elements(By.CSS_SELECTOR, "td")
            if len(row_cells) >= 4 and row_cells[0].text.strip().lstrip("#") == source_version_id:
                source_row_status = row_cells[3].text
                break
        except StaleElementReferenceException:
            continue
    if "게시 중" not in source_row_status:
        raise AssertionError("restoring a version changed the published history pointer")

    stage_callback("history_restore_form_values")
    for selector, expected in expected_settings.items():
        if visible(driver, selector).get_attribute("value") != expected:
            raise AssertionError("history restore did not return the published setting to the new draft")

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", restored_row)
    driver.save_screenshot(str(DEST / "brand-admin-history-restore-confirmation.png"))

    stage_callback("history_restore_customer_output_unchanged")
    if public_brand_snapshot(driver) != published_public_snapshot:
        raise AssertionError("restoring a history version changed customer output before publication")

    driver.get(settings_url)
    visible(driver, "form.ordenowa-profile-settings")


def preview_current_draft_brand_assets(
    driver: webdriver.Chrome,
    expected_assets: tuple[tuple[str, Path], ...],
    stage_callback: Callable[[str], None],
    stage_prefix: str,
) -> None:
    stage_callback(stage_prefix + "_draft_preview")
    current_draft_row = WebDriverWait(driver, 30).until(current_draft_history_row)
    current_draft_row.find_element(By.CSS_SELECTOR, 'button[name="submitOrdenowaPreview"]').click()
    preview = visible(driver, ".ordenowa-profile-preview")
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", preview)
    preview_images = preview.find_elements(By.TAG_NAME, "img")
    preview_urls = [image.get_attribute("src") or "" for image in preview_images]

    for filename, source in expected_assets:
        preview_url = next(
            (url for url in preview_urls if urlparse(url).path.endswith("/" + filename)),
            "",
        )
        assert_uploaded_derivative_url(preview_url, source, filename, "admin draft preview " + filename)

    WebDriverWait(driver, 30).until(
        lambda browser: all(
            int(image.get_attribute("naturalWidth") or 0) > 0
            for image in browser.find_elements(By.CSS_SELECTOR, ".ordenowa-profile-preview img")
        )
    )
    driver.save_screenshot(str(DEST / f"brand-admin-{stage_prefix}-draft-preview.png"))


def asset_preview_url_for_field(driver: webdriver.Chrome, field_id: str) -> str:
    field = visible(driver, f"#{field_id}")
    return driver.execute_script(
        "return arguments[0].closest('.ordenowa-profile-field')?.querySelector('.ordenowa-asset-preview')?.src || '';",
        field,
    )


def public_brand_snapshot(driver: webdriver.Chrome, *, include_mobile: bool = True) -> dict:
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
              id: manifest.id || '',
              name: manifest.name || '',
              short_name: manifest.short_name || '',
              start_url: manifest.start_url || '',
              scope: manifest.scope || '',
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
    if include_mobile:
        original_size = driver.get_window_size()
        try:
            driver.set_window_size(390, 844)
            snapshot["mobile"] = public_brand_snapshot(driver, include_mobile=False)
        finally:
            driver.set_window_size(original_size["width"], original_size["height"])
            driver.get(BASE + "/")
    return snapshot


def assert_manifest_base_path(manifest: dict) -> None:
    shop_path = urlparse(BASE).path.rstrip("/")
    expected_path = (shop_path or "") + "/"
    for field in ("id", "start_url", "scope"):
        if manifest.get(field) != expected_path:
            raise AssertionError("served PWA manifest " + field + " does not match the storefront base path")


def public_brand_slot_urls(snapshot: dict, slot: str) -> tuple[str, ...]:
    if slot == "favicon_symbol":
        return tuple(sorted(href for rel, href in snapshot["icons"] if rel == "icon"))
    if slot == "pwa_icon":
        apple_icons = [href for rel, href in snapshot["icons"] if rel == "apple-touch-icon"]
        manifest_icons = [icon[0] for icon in snapshot["manifest"]["icons"]]
        return tuple(sorted(apple_icons + manifest_icons))
    raise AssertionError("unsupported replaceable brand icon slot")


def verify_browser_asset_bytes(
    driver: webdriver.Chrome,
    expected_assets: list[dict[str, str | int]],
) -> None:
    facts = driver.execute_async_script(
        """
        const [assets, done] = arguments;
        (async () => {
          const facts = [];
          for (const asset of assets) {
            const response = await fetch(asset.url, {cache: 'no-store'});
            if (!response.ok) throw new Error('asset fetch failed');
            const bytes = await response.arrayBuffer();
            const hashBuffer = await crypto.subtle.digest('SHA-256', bytes);
            const sha256 = [...new Uint8Array(hashBuffer)]
              .map(value => value.toString(16).padStart(2, '0')).join('');
            const objectUrl = URL.createObjectURL(new Blob([bytes]));
            const image = new Image();
            try {
              image.src = objectUrl;
              await image.decode();
              facts.push({
                role: asset.role,
                sha256,
                bytes: bytes.byteLength,
                width: image.naturalWidth,
                height: image.naturalHeight
              });
            } finally {
              URL.revokeObjectURL(objectUrl);
            }
          }
          return facts;
        })().then(done).catch(() => done({error: true}));
        """,
        expected_assets,
    )
    if not isinstance(facts, list) or len(facts) != len(expected_assets):
        raise AssertionError("the browser could not decode every installed official brand image")

    facts_by_role = {
        fact.get("role"): fact
        for fact in facts
        if isinstance(fact, dict) and isinstance(fact.get("role"), str)
    }
    for expected in expected_assets:
        fact = facts_by_role.get(expected["role"])
        if not isinstance(fact, dict):
            raise AssertionError("the browser did not verify an installed official brand image")
        if (
            fact.get("sha256") != expected["sha256"]
            or fact.get("bytes") != expected["bytes"]
            or int(fact.get("width") or 0) < 1
            or int(fact.get("height") or 0) < 1
        ):
            raise AssertionError("an installed official brand image differs from its approved derivative")


def assert_initial_official_brand_assets(
    driver: webdriver.Chrome,
    stage_callback: Callable[[str], None],
    admin_login_logo_url: str,
) -> dict:
    """Verify the fresh-install public brand before the browser uploads any sources."""
    expected_assets: list[dict[str, str | int]] = []

    def expect_asset(
        role: str,
        url: str,
        source: Path,
        installed_filename: str,
        packaged_filename: str,
    ) -> None:
        assert_uploaded_derivative_url(url, source, installed_filename, role)
        packaged = APPROVED_DERIVED_ASSETS.get(packaged_filename)
        if not isinstance(packaged, dict):
            raise AssertionError("the approved asset manifest omits " + packaged_filename)
        expected_assets.append(
            {
                "role": role,
                "url": url,
                "sha256": packaged["sha256"],
                "bytes": packaged["bytes"],
            }
        )

    stage_callback("initial_public_brand_snapshot")
    snapshot = public_brand_snapshot(driver)
    assert_manifest_base_path(snapshot["manifest"])

    stage_callback("initial_desktop_header_logo")
    expect_asset(
        "desktop header logo",
        snapshot["logo"],
        OFFICIAL_UPLOADS["primary_logo"],
        "official-header-desktop.png",
        "logo-desktop.png",
    )
    stage_callback("initial_mobile_header_logo")
    expect_asset(
        "mobile header logo",
        snapshot["mobile"]["logo"],
        OFFICIAL_UPLOADS["primary_logo"],
        "official-header-mobile.png",
        "logo-mobile.png",
    )

    icon_links = [{"rel": rel, "href": href} for rel, href in snapshot["icons"]]
    for role, filename, packaged_filename in (
        ("favicon ICO", "official-favicon.ico", "favicon.ico"),
        ("16 pixel favicon", "official-favicon-16.png", "favicon-16x16.png"),
        ("32 pixel favicon", "official-favicon-32.png", "favicon-32x32.png"),
    ):
        stage_callback("initial_" + role.replace(" ", "_"))
        expect_asset(
            role,
            find_asset_url(icon_links, "icon", OFFICIAL_UPLOADS["favicon_symbol"], filename),
            OFFICIAL_UPLOADS["favicon_symbol"],
            filename,
            packaged_filename,
        )

    stage_callback("initial_apple_touch_icon")
    expect_asset(
        "Apple Touch icon",
        find_asset_url(
            icon_links,
            "apple-touch-icon",
            OFFICIAL_UPLOADS["pwa_icon"],
            "official-apple-touch-icon.png",
        ),
        OFFICIAL_UPLOADS["pwa_icon"],
        "official-apple-touch-icon.png",
        "apple-touch-icon.png",
    )

    pwa_icon_expectations = (
        ("official-pwa-192.png", "192x192", "any", "pwa-192x192.png"),
        ("official-pwa-512.png", "512x512", "any", "pwa-512x512.png"),
        ("official-pwa-maskable-512.png", "512x512", "maskable", "pwa-maskable-512x512.png"),
    )
    for filename, size, purpose, packaged_filename in pwa_icon_expectations:
        stage_callback("initial_" + filename.removesuffix(".png"))
        manifest_icon = next(
            (
                (url, declared_size, declared_purpose)
                for url, declared_size, declared_purpose in snapshot["manifest"]["icons"]
                if urlparse(url).path.endswith("/" + filename)
            ),
            None,
        )
        if manifest_icon is None or manifest_icon[1:] != (size, purpose):
            raise AssertionError("the initial PWA manifest does not map the approved " + filename)
        expect_asset(
            "PWA " + purpose + " " + size + " icon",
            manifest_icon[0],
            OFFICIAL_UPLOADS["pwa_icon"],
            filename,
            packaged_filename,
        )

    stage_callback("initial_open_graph_image")
    expect_asset(
        "Open Graph image",
        snapshot["ogImage"],
        OFFICIAL_UPLOADS["primary_logo"],
        "official-og-brand.png",
        "og-1200x630.png",
    )

    stage_callback("initial_admin_login_logo")
    expect_asset(
        "admin login logo",
        admin_login_logo_url,
        OFFICIAL_UPLOADS["primary_logo"],
        "official-admin-login.png",
        "logo-desktop.png",
    )

    stage_callback("initial_official_asset_hash_and_decode")
    driver.get(BASE + "/")
    verify_browser_asset_bytes(driver, expected_assets)
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


def publish_saved_brand_draft(
    driver: webdriver.Chrome,
    stage_callback: Callable[[str], None],
    stage_prefix: str,
) -> None:
    publish_selector = 'form.ordenowa-profile-settings button[name="submitOrdenowaPublish"]'
    stage_callback(stage_prefix + "_button_find")
    publish_button = visible(driver, publish_selector)
    stage_callback(stage_prefix + "_button_click")
    try:
        click_centered(driver, publish_button)
    except StaleElementReferenceException:
        emit_publish_target_diagnostics(driver, publish_selector)
        raise
    stage_callback(stage_prefix + "_confirmation")
    wait_for_publish_confirmation(driver)


def restore_admin_session(
    driver: webdriver.Chrome,
    stage_callback: Callable[[str], None],
    stage_name: str,
) -> None:
    stage_callback(stage_name)
    email_fields = driver.find_elements(By.CSS_SELECTOR, '#login_form input[name="email"], input[type="email"]')
    password_fields = driver.find_elements(
        By.CSS_SELECTOR,
        '#login_form input[name="passwd"], #login_form input[name="password"], input[type="password"]',
    )
    if not email_fields or not password_fields:
        raise AssertionError("Back Office login form fields are unavailable after checking the published logo")
    email_fields[0].send_keys(ADMIN_EMAIL)
    password_fields[0].send_keys(ADMIN_PASSWORD)
    visible(
        driver,
        '#login_form button[type="submit"], #login_form input[type="submit"], button[type="submit"]',
    ).click()
    WebDriverWait(driver, 30).until(lambda browser: "/login" not in urlparse(browser.current_url).path)


def business_profile_settings_url(driver: webdriver.Chrome) -> str:
    def business_profile_link(browser: webdriver.Chrome):
        for link in browser.find_elements(By.CSS_SELECTOR, 'a[href*="controller="]'):
            href = link.get_attribute("href") or ""
            if parse_qs(urlparse(href).query).get("controller", []) == ["AdminBusinessProfile"]:
                return href
        return False

    href = WebDriverWait(driver, 30).until(business_profile_link)
    settings_url = urljoin(driver.current_url, href)
    settings_location = urlparse(settings_url)
    if settings_location.hostname not in {"localhost", "127.0.0.1"} or not settings_location.path.startswith("/admin-kuranea/"):
        raise AssertionError("business profile menu link is outside this isolated Back Office")
    return settings_url


def assert_published_logo_source(
    driver: webdriver.Chrome,
    source: Path,
    *,
    expected_previous_header_logos: dict[str, str],
    expected_previous_admin_login_logo: str,
    stage_callback: Callable[[str], None],
    stage_prefix: str,
) -> dict[str, str]:
    observed: dict[str, str] = {}
    for viewport, size, filename in (
        ("desktop", (1440, 960), "header-desktop.png"),
        ("mobile", (390, 844), "header-mobile.png"),
    ):
        stage_callback(stage_prefix + "_" + viewport + "_header_logo")
        driver.set_window_size(*size)
        driver.get(BASE + "/")
        logo = image_is_rendered(driver, "picture img.kuranea-brand__image")
        if logo["width"] < 1 or filename not in logo["src"]:
            raise AssertionError("published replacement logo did not decode for " + viewport)
        assert_uploaded_derivative_url(logo["src"], source, filename, viewport + " header logo")
        if logo["src"] == expected_previous_header_logos[viewport]:
            raise AssertionError("publishing the replacement did not switch the " + viewport + " header logo")
        assert_no_legacy_brand_in_rendered_page(driver, stage_prefix + " " + viewport + " storefront")
        observed[viewport + "_header"] = logo["src"]
        driver.save_screenshot(str(DEST / f"brand-{stage_prefix}-{viewport}.png"))

    stage_callback(stage_prefix + "_admin_login_logo")
    driver.delete_all_cookies()
    driver.get(ADMIN_LOGIN + "/login")
    login_logo = image_is_rendered(driver, ".ordenowa-admin-login-brand img")
    if login_logo["width"] < 1 or "admin-login.png" not in login_logo["src"]:
        raise AssertionError("published replacement admin login logo did not decode")
    assert_uploaded_derivative_url(login_logo["src"], source, "admin-login.png", "admin login logo")
    if login_logo["src"] == expected_previous_admin_login_logo:
        raise AssertionError("publishing the replacement did not switch the admin login logo")
    assert_no_legacy_brand_in_rendered_page(driver, stage_prefix + " admin login")
    observed["admin_login"] = login_logo["src"]
    driver.save_screenshot(str(DEST / f"brand-{stage_prefix}-admin-login.png"))

    restore_admin_session(driver, stage_callback, stage_prefix + "_admin_session_restore")
    return observed


def sanitize_brand_diagnostic_text(value: str) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value or ""))
    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[email]", text, flags=re.I)
    text = re.sub(r"https?://\S+|\bwww\.\S+", "[url]", text, flags=re.I)
    text = re.sub(r"(?<!\w)\+?\d[\d\s().-]{5,}\d(?!\w)", "[number]", text)
    return " ".join(text.split())[:BRAND_DIAGNOSTIC_SNIPPET_CHARS]


def sanitize_brand_diagnostic_path(value: str) -> str:
    try:
        path = urlparse(str(value or "")).path
    except ValueError:
        return "/[redacted]"

    safe_segments: list[str] = []
    for segment in path.split("/"):
        if not segment:
            continue
        if re.fullmatch(r"[A-Za-z_-]{1,48}(?:\.[A-Za-z]{1,8})?", segment):
            safe_segments.append(segment)
        else:
            safe_segments.append("[redacted]")
    return "/" + "/".join(safe_segments)


def emit_brand_admin_login_diagnostics(driver: webdriver.Chrome, stage: str) -> None:
    selector = ".ordenowa-admin-login-brand img"
    try:
        raw = driver.execute_script(
            r"""
            const selector = arguments[0];
            const logo = document.querySelector(selector);
            const visible = element => Boolean(element && element.getClientRects().length
              && getComputedStyle(element).display !== 'none'
              && getComputedStyle(element).visibility !== 'hidden');
            const loginForm = document.querySelector(
              '#login_form, #login-form, form[action*="/login"], input[type="password"]'
            );
            return {
              page_path: window.location.pathname,
              page_title: document.title,
              login_form_present: Boolean(loginForm),
              login_form_visible: visible(loginForm),
              logo_present: Boolean(logo),
              logo_visible: visible(logo),
              logo_natural_width: logo ? logo.naturalWidth : 0,
              logo_natural_height: logo ? logo.naturalHeight : 0,
              logo_src: logo ? (logo.currentSrc || logo.src || '') : ''
            };
            """,
            selector,
        )
    except Exception:
        raw = {}

    def natural_dimension(value: object) -> int:
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0

    diagnostics = {
        "stage": stage,
        "page_path": sanitize_brand_diagnostic_path(raw.get("page_path", "")),
        "page_title": sanitize_brand_diagnostic_text(raw.get("page_title", "")),
        "login_form_present": bool(raw.get("login_form_present", False)),
        "login_form_visible": bool(raw.get("login_form_visible", False)),
        "logo_selector": selector,
        "logo_present": bool(raw.get("logo_present", False)),
        "logo_visible": bool(raw.get("logo_visible", False)),
        "logo_natural_width": natural_dimension(raw.get("logo_natural_width")),
        "logo_natural_height": natural_dimension(raw.get("logo_natural_height")),
        "logo_path": sanitize_brand_diagnostic_path(raw.get("logo_src", "")),
    }
    print(
        "ORDENOWA_BRAND_ADMIN_LOGIN_SAFE_STATE=" + json.dumps(diagnostics, ensure_ascii=True, sort_keys=True),
        file=sys.stderr,
    )


def assert_no_legacy_brand_in_rendered_page(driver: webdriver.Chrome, label: str) -> None:
    diagnostics = driver.execute_script(
        r"""
        const title = document.title || '';
        const visibleBody = document.body?.innerText || '';
        const matches = [];
        const collect = (value, source) => {
          const pattern = /kuranea/gi;
          let match;
          while (matches.length < arguments[0] && (match = pattern.exec(value))) {
            const start = Math.max(0, match.index - arguments[1]);
            const end = Math.min(value.length, match.index + match[0].length + arguments[1]);
            matches.push({source, snippet: value.slice(start, end)});
          }
        };
        collect(title, 'page_title');
        collect(visibleBody, 'visible_body');
        return {title, matches};
        """,
        BRAND_DIAGNOSTIC_MAX_MATCHES,
        BRAND_DIAGNOSTIC_CONTEXT_CHARS,
    )
    if diagnostics.get("matches"):
        safe_diagnostics = {
            "label": sanitize_brand_diagnostic_text(label),
            "page_title": sanitize_brand_diagnostic_text(diagnostics.get("title", "")),
            "matches": [
                {
                    "source": item.get("source", "unknown"),
                    "snippet": sanitize_brand_diagnostic_text(item.get("snippet", "")),
                }
                for item in diagnostics["matches"][:BRAND_DIAGNOSTIC_MAX_MATCHES]
                if isinstance(item, dict)
            ],
        }
        diagnostic_json = json.dumps(safe_diagnostics, ensure_ascii=True, sort_keys=True)
        print("ORDENOWA_LEGACY_BRAND_MATCH=" + diagnostic_json, file=sys.stderr)
        workflow_data = diagnostic_json.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(
            "::error title=ORDENOWA legacy brand visible text::" + workflow_data,
            file=sys.stderr,
        )
        raise AssertionError("legacy KURANEA brand was rendered on " + label)


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


def assert_public_brand_assets(
    driver: webdriver.Chrome,
    label: str,
    expected_logo: str,
    *,
    locale_path: str = "/",
    locale_url: str | None = None,
    expected_html_lang: str = "ja-JP",
    seo_title: str = SEO_TITLE,
    seo_description: str = SEO_DESCRIPTION,
    jsonld_brand_name: str = SEO_JSONLD_BRAND_NAME,
    pwa_name: str = "ORDENOWA CI QA",
    pwa_short_name: str = "ORDENOWA CI",
    favicon_source: Path | None = None,
    pwa_source: Path | None = None,
    stage_prefix: str,
    stage_callback: Callable[[str], None],
) -> None:
    favicon_source = favicon_source or OFFICIAL_UPLOADS["favicon_symbol"]
    pwa_source = pwa_source or OFFICIAL_UPLOADS["pwa_icon"]

    def set_assertion_stage(phase: str) -> None:
        stage_callback(stage_prefix + "_" + phase)

    set_assertion_stage("customer_route")
    customer_url = urljoin(BASE + "/", locale_path.lstrip("/"))
    if locale_url is not None:
        customer_url = locale_url
    if not same_storefront_origin(customer_url):
        raise AssertionError("the customer locale route left the isolated storefront")
    driver.get(customer_url)

    set_assertion_stage("header_logo_src_decode")
    logo = image_is_rendered(driver, "picture img.kuranea-brand__image")
    if logo["width"] < 1 or expected_logo not in logo["src"]:
        raise AssertionError("approved ORDENOWA header logo did not render for " + label)

    set_assertion_stage("visible_brand_text")
    assert_no_legacy_brand_in_rendered_page(driver, label + " storefront")

    set_assertion_stage("public_asset_derivative_paths")
    assert_uploaded_derivative_url(
        logo["src"], OFFICIAL_UPLOADS["primary_logo"], expected_logo, label + " header logo"
    )

    set_assertion_stage("public_asset_decode")
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
          const jsonLdScripts = [...document.querySelectorAll('script[type="application/ld+json"]')]
            .map(script => script.textContent || '');
          const inertSentinels = [
            'ordenowa-seo-title-inert-sentinel',
            'ordenowa-seo-description-inert-sentinel',
            'ordenowa-jsonld-inert-sentinel'
          ].filter(marker => document.getElementById(marker));
          return {assetLinks, og, ogImage, manifest, icons, title: document.title, htmlLang: document.documentElement.lang, description, ogTitle, ogDescription, themeColor, jsonLdScripts, inertSentinels};
        })().then(done).catch(error => done({error: String(error)}));
        """
    )
    if results.get("error"):
        raise AssertionError("brand favicon, Apple icon, OG image, or PWA asset failed browser decoding")

    assert_hostile_seo_and_jsonld_rendering(
        results,
        seo_title,
        seo_description,
        jsonld_brand_name,
        set_assertion_stage,
    )

    set_assertion_stage("public_asset_derivative_paths")
    rels = {item["rel"] for item in results["assetLinks"]}
    if "icon" not in rels or "apple-touch-icon" not in rels:
        raise AssertionError("favicon or Apple Touch Icon link is missing")
    assert_uploaded_derivative_url(
        find_asset_url(
            results["assetLinks"], "icon", favicon_source, "favicon.ico"
        ),
        favicon_source,
        "favicon.ico",
        "favicon",
    )
    for filename in ("favicon-16.png", "favicon-32.png"):
        assert_uploaded_derivative_url(
            find_asset_url(
                results["assetLinks"], "icon", favicon_source, filename
            ),
            favicon_source,
            filename,
            "favicon",
        )
    assert_uploaded_derivative_url(
        find_asset_url(
            results["assetLinks"], "apple-touch-icon", pwa_source, "apple-touch-icon.png"
        ),
        pwa_source,
        "apple-touch-icon.png",
        "Apple Touch Icon",
    )
    assert_uploaded_derivative_url(
        results["og"], OFFICIAL_UPLOADS["primary_logo"], "og-brand.png", "Open Graph image"
    )

    set_assertion_stage("metadata_contract")
    if results["ogImage"]["width"] != 1200 or results["ogImage"]["height"] != 630:
        raise AssertionError("the approved Open Graph image dimensions are incorrect")
    assert_manifest_base_path(results["manifest"])
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
            icon_url["src"], pwa_source, filename, "PWA icon"
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

    if results["htmlLang"] != expected_html_lang:
        raise AssertionError("the customer locale route did not render the expected language")
    if seo_title not in results["title"]:
        raise AssertionError("Korean admin SEO title update did not publish to the customer page")
    if results["description"] != seo_description:
        raise AssertionError("Korean admin SEO description did not publish to the customer page")
    if results["ogTitle"] != seo_title:
        raise AssertionError("Korean admin SEO title did not publish to Open Graph metadata")
    if results["ogDescription"] != seo_description:
        raise AssertionError("Korean admin SEO description did not publish to Open Graph metadata")
    if (
        results["manifest"].get("name") != pwa_name
        or results["manifest"].get("short_name") != pwa_short_name
        or results["manifest"].get("theme_color") != "#244a7d"
        or results["manifest"].get("background_color") != "#f5f7fa"
    ):
        raise AssertionError("Korean admin PWA names or colors did not publish to the app manifest")
    if results["themeColor"] != "#244a7d":
        raise AssertionError("Korean admin PWA theme color did not publish to customer metadata")


def restore_approved_brand_icon_after_failure(
    driver: webdriver.Chrome,
    settings_url: str,
    *,
    slot: str,
    approved_source: Path,
    preview_field_id: str,
    form_preview_filename: str,
    approved_previews: tuple[tuple[str, Path], ...],
    public_before_draft: dict,
    stage_callback: Callable[[str], None],
    stage_prefix: str,
) -> None:
    # Recover authentication and a fresh CSRF-protected settings URL even when
    # the original failure was a login redirect or an expired admin session.
    driver.delete_all_cookies()
    driver.get(ADMIN_LOGIN + "/login")
    restore_admin_session(driver, stage_callback, stage_prefix + "_failure_restore_admin_login")
    settings_url = business_profile_settings_url(driver)
    stage_callback(stage_prefix + "_failure_restore_save_draft")
    replace_brand_asset_in_saved_draft(
        driver,
        settings_url,
        slot,
        preview_field_id,
        approved_source,
        form_preview_filename,
        slot + " failure restore",
        stage_callback,
        stage_prefix + "_failure_restore",
    )
    # A failed private preview must not prevent publishing the approved source.
    stage_callback(stage_prefix + "_failure_restore_publish")
    driver.get(settings_url)
    visible(driver, "form.ordenowa-profile-settings")
    publish_saved_brand_draft(driver, stage_callback, stage_prefix + "_failure_restore_publish")
    assert_public_brand_assets(
        driver,
        "desktop",
        "header-desktop.png",
        stage_prefix=stage_prefix + "_failure_restored_assets",
        stage_callback=stage_callback,
    )
    restored = public_brand_snapshot(driver)
    if public_brand_slot_urls(restored, slot) != public_brand_slot_urls(public_before_draft, slot):
        raise AssertionError("failure cleanup did not restore the approved " + slot + " public image")


def replace_publish_restore_brand_icon(
    driver: webdriver.Chrome,
    settings_url: str,
    *,
    slot: str,
    replacement_source: Path,
    approved_source: Path,
    preview_field_id: str,
    form_preview_filename: str,
    replacement_previews: tuple[tuple[str, Path], ...],
    approved_previews: tuple[tuple[str, Path], ...],
    stage_callback: Callable[[str], None],
) -> None:
    stage_prefix = slot + "_replacement"
    public_before_draft = public_brand_snapshot(driver)
    if not public_brand_slot_urls(public_before_draft, slot):
        raise AssertionError("published brand " + slot + " assets are missing before replacement")

    restore_required = False
    try:
        restore_required = True
        stage_callback(stage_prefix + "_save_replacement_draft")
        replace_brand_asset_in_saved_draft(
            driver,
            settings_url,
            slot,
            preview_field_id,
            replacement_source,
            form_preview_filename,
            slot,
            stage_callback,
            stage_prefix + "_replacement",
        )
        preview_current_draft_brand_assets(
            driver,
            replacement_previews,
            stage_callback,
            stage_prefix + "_replacement",
        )
        public_after_replacement_draft = public_brand_snapshot(driver)
        if public_after_replacement_draft != public_before_draft:
            raise AssertionError("saving a " + slot + " draft changed public brand assets before publish")

        stage_callback(stage_prefix + "_publish_replacement")
        driver.get(settings_url)
        visible(driver, "form.ordenowa-profile-settings")
        publish_saved_brand_draft(driver, stage_callback, stage_prefix + "_replacement_publish")
        assert_public_brand_assets(
            driver,
            "desktop",
            "header-desktop.png",
            favicon_source=replacement_source if slot == "favicon_symbol" else None,
            pwa_source=replacement_source if slot == "pwa_icon" else None,
            stage_prefix=stage_prefix + "_published_replacement",
            stage_callback=stage_callback,
        )
        public_after_replacement = public_brand_snapshot(driver)
        if public_brand_slot_urls(public_after_replacement, slot) == public_brand_slot_urls(public_before_draft, slot):
            raise AssertionError("publishing the " + slot + " replacement did not change its public image URLs")

        stage_callback(stage_prefix + "_save_approved_restore_draft")
        replace_brand_asset_in_saved_draft(
            driver,
            settings_url,
            slot,
            preview_field_id,
            approved_source,
            form_preview_filename,
            slot + " approved restore",
            stage_callback,
            stage_prefix + "_restore",
        )
        preview_current_draft_brand_assets(
            driver,
            approved_previews,
            stage_callback,
            stage_prefix + "_approved_restore",
        )
        public_after_restore_draft = public_brand_snapshot(driver)
        if public_after_restore_draft != public_after_replacement:
            raise AssertionError("saving the approved " + slot + " restore changed public brand assets before publish")

        stage_callback(stage_prefix + "_publish_approved_restore")
        driver.get(settings_url)
        visible(driver, "form.ordenowa-profile-settings")
        publish_saved_brand_draft(driver, stage_callback, stage_prefix + "_approved_restore_publish")
        assert_public_brand_assets(
            driver,
            "desktop",
            "header-desktop.png",
            stage_prefix=stage_prefix + "_published_approved_restore",
            stage_callback=stage_callback,
        )
        public_after_restore = public_brand_snapshot(driver)
        if public_brand_slot_urls(public_after_restore, slot) != public_brand_slot_urls(public_before_draft, slot):
            raise AssertionError("republishing the approved " + slot + " source did not restore public image URLs")
        restore_required = False
        driver.save_screenshot(str(DEST / f"brand-admin-{slot}-approved-restored.png"))
    except Exception:
        if restore_required:
            cleanup_stage = {"value": stage_prefix + "_failure_restore_start"}

            try:
                restore_approved_brand_icon_after_failure(
                    driver,
                    settings_url,
                    slot=slot,
                    approved_source=approved_source,
                    preview_field_id=preview_field_id,
                    form_preview_filename=form_preview_filename,
                    approved_previews=approved_previews,
                    public_before_draft=public_before_draft,
                    stage_callback=lambda cleanup_assertion_stage: cleanup_stage.update(
                        value=cleanup_assertion_stage
                    ),
                    stage_prefix=stage_prefix,
                )
                print("ORDENOWA_BRAND_ICON_RESTORE_CLEANUP=passed", file=sys.stderr)
            except Exception as cleanup_error:
                print(
                    "ORDENOWA_BRAND_ICON_RESTORE_CLEANUP=failed at "
                    + cleanup_stage["value"][:96]
                    + " ("
                    + type(cleanup_error).__name__
                    + ")",
                    file=sys.stderr,
                )
        raise


def assert_seller_disclosures_remain_gated(driver: webdriver.Chrome, private_values: list[str]) -> None:
    customer_url = urljoin(BASE + "/", "ko/")
    driver.get(customer_url)
    legal_link = visible(driver, ".ordenowa-legal-page-link a")
    legal_url = urljoin(driver.current_url, legal_link.get_attribute("href") or "")
    if urlparse(legal_url).netloc != urlparse(BASE).netloc:
        raise AssertionError("published legal page link left the isolated storefront")

    driver.get(legal_url)
    page = visible(driver, ".ordenowa-legal-page")
    if page.get_attribute("lang") != "ko-KR":
        raise AssertionError("the company profile gate check did not load the Korean customer information page")
    visible(driver, ".ordenowa-legal-page__closed")
    leaked_values = [value for value in private_values if value and value in page.text]
    if leaked_values:
        raise AssertionError("pending seller disclosures leaked to the customer legal page")
    driver.save_screenshot(str(DEST / "brand-legal-page-gated.png"))


def run() -> None:
    validate_isolated_ci_compose_project()
    validate_loopback_admin_targets()
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,960")
    options.add_argument("--lang=ja-JP")
    driver = webdriver.Chrome(options=options)
    stage = "administrator_login"
    settings_url = ""
    replacement_publish_started = False

    def set_brand_assertion_stage(assertion_stage: str) -> None:
        nonlocal stage
        stage = assertion_stage

    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
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

        settings_url = business_profile_settings_url(driver)

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
        public_before_draft = assert_initial_official_brand_assets(
            driver,
            set_brand_assertion_stage,
            login_logo["src"],
        )
        driver.save_screenshot(str(DEST / "brand-customer-before-draft.png"))
        driver.get(settings_url)
        visible(driver, "form.ordenowa-profile-settings")

        stage = "official_asset_upload"
        for slot, source in OFFICIAL_UPLOADS.items():
            if not source.is_file():
                raise AssertionError("official ORDENOWA source file is missing from the checkout")
            visible(driver, f'input[name="brand_uploads[{slot}]"]').send_keys(str(source.resolve()))

        company_profile_ja = "ORDENOWA CI COMPANY PROFILE JA"
        company_profile_ko = "ORDENOWA CI 한국어 회사소개"
        ci_settings = {
            'input[name="profile[brand][name][ja-JP]"]': SEO_JSONLD_BRAND_NAME,
            'input[name="profile[brand][name][en-US]"]': "ORDENOWA CI BRAND EN",
            'input[name="profile[brand][name][ko-KR]"]': "ORDENOWA CI BRAND KO",
            'input[name="profile[brand][description][ja-JP]"]': "ORDENOWA CI BRAND DESCRIPTION JP",
            'input[name="profile[brand][description][en-US]"]': "ORDENOWA CI BRAND DESCRIPTION EN",
            'input[name="profile[brand][description][ko-KR]"]': "ORDENOWA CI BRAND DESCRIPTION KO",
            'input[name="profile[brand][slogan][ja-JP]"]': "ORDENOWA CI BRAND SLOGAN JP",
            'input[name="profile[brand][slogan][en-US]"]': "ORDENOWA CI BRAND SLOGAN EN",
            'input[name="profile[brand][slogan][ko-KR]"]': "ORDENOWA CI BRAND SLOGAN KO",
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
            'input[name="profile[company_reference][name][en-US]"]': "ORDENOWA CI REFERENCE EN",
            'input[name="profile[company_reference][name][ko-KR]"]': "ORDENOWA CI REFERENCE KO",
            'input[name="profile[company_reference][corporate_number]"]': "0000000000000",
            'input[name="profile[company_reference][postal_code]"]': "000-0000",
            'input[name="profile[company_reference][address]"]': "ORDENOWA CI REFERENCE ADDRESS",
            'input[name="profile[company_reference][phone]"]': "000-0000-0000",
            'input[name="profile[company_reference][representative]"]': "ORDENOWA CI REFERENCE CONTACT",
            'input[name="profile[company_reference][source_url]"]': "https://example.invalid/ci",
            'select[name="profile[company_reference][verification_status]"]': "user_provided_reference",
            'input[name="profile[customer_support][phone]"]': "000-0000-0000",
            'input[name="profile[customer_support][email]"]': "ci-test@example.invalid",
            'input[name="profile[customer_support][hours][ja-JP]"]': "ORDENOWA CI SUPPORT HOURS JP",
            'input[name="profile[customer_support][hours][en-US]"]': "ORDENOWA CI SUPPORT HOURS EN",
            'input[name="profile[customer_support][hours][ko-KR]"]': "ORDENOWA CI SUPPORT HOURS KO",
            'textarea[name="profile[shipping][ja-JP]"]': "ORDENOWA CI SHIPPING POLICY",
            'textarea[name="profile[shipping][en-US]"]': "ORDENOWA CI SHIPPING POLICY EN",
            'textarea[name="profile[shipping][ko-KR]"]': "ORDENOWA CI SHIPPING POLICY KO",
            'textarea[name="profile[refund][ja-JP]"]': "ORDENOWA CI REFUND POLICY",
            'textarea[name="profile[refund][en-US]"]': "ORDENOWA CI REFUND POLICY EN",
            'textarea[name="profile[refund][ko-KR]"]': "ORDENOWA CI REFUND POLICY KO",
            'input[name="profile[seo][title][ja-JP]"]': SEO_TITLE,
            'input[name="profile[seo][title][en-US]"]': SEO_TITLE_EN,
            'input[name="profile[seo][title][ko-KR]"]': SEO_TITLE_KO,
            'textarea[name="profile[seo][description][ja-JP]"]': SEO_DESCRIPTION,
            'textarea[name="profile[seo][description][en-US]"]': SEO_DESCRIPTION_EN,
            'textarea[name="profile[seo][description][ko-KR]"]': SEO_DESCRIPTION_KO,
            'input[name="profile[pwa][name][ja-JP]"]': "ORDENOWA CI QA",
            'input[name="profile[pwa][name][en-US]"]': "ORDENOWA CI APP EN",
            'input[name="profile[pwa][name][ko-KR]"]': "ORDENOWA CI APP KO",
            'input[name="profile[pwa][short_name][ja-JP]"]': "ORDENOWA CI",
            'input[name="profile[pwa][short_name][en-US]"]': "ORDENOWA EN",
            'input[name="profile[pwa][short_name][ko-KR]"]': "ORDENOWA KO",
            'input[name="profile[pwa][theme_color]"]': "#244a7d",
            'input[name="profile[pwa][background_color]"]': "#f5f7fa",
            'textarea[name="profile[content][company_profile][ja-JP]"]': company_profile_ja,
            'textarea[name="profile[content][company_profile][ko-KR]"]': company_profile_ko,
        }
        policy_settings = {
            'textarea[name="profile[content][terms][ja-JP]"]': "ORDENOWA CI TERMS JA",
            'textarea[name="profile[content][terms][en-US]"]': "ORDENOWA CI TERMS EN",
            'textarea[name="profile[content][terms][ko-KR]"]': "ORDENOWA CI TERMS KO",
            'textarea[name="profile[content][privacy][ja-JP]"]': "ORDENOWA CI PRIVACY JA",
            'textarea[name="profile[content][privacy][en-US]"]': "ORDENOWA CI PRIVACY EN",
            'textarea[name="profile[content][privacy][ko-KR]"]': "ORDENOWA CI PRIVACY KO",
            'textarea[name="profile[content][specified_commercial_act][ja-JP]"]': "ORDENOWA CI SPECIFIED ACT JA",
            'textarea[name="profile[content][specified_commercial_act][en-US]"]': "ORDENOWA CI SPECIFIED ACT EN",
            'textarea[name="profile[content][specified_commercial_act][ko-KR]"]': "ORDENOWA CI SPECIFIED ACT KO",
        }
        ci_settings.update(policy_settings)
        specified_act_preview_value = policy_settings[
            'textarea[name="profile[content][specified_commercial_act][ja-JP]"]'
        ]
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

        stage = "company_profile_draft_reload"
        driver.get(settings_url)
        visible(driver, "form.ordenowa-profile-settings")
        company_profile_selector = 'textarea[name="profile[content][company_profile][ko-KR]"]'
        if visible(driver, company_profile_selector).get_attribute("value") != company_profile_ko:
            raise AssertionError("the Korean company profile did not persist after reloading the admin settings")
        for selector, expected in ci_settings.items():
            if visible(driver, selector).get_attribute("value") != expected:
                raise AssertionError("a Korean admin operating setting did not persist after reloading its draft")
        driver.save_screenshot(str(DEST / "brand-company-profile-draft-reloaded.png"))
        driver.save_screenshot(str(DEST / "brand-admin-uploaded-draft.png"))
        stage = "profile_history_field_change_diff"
        history_row = WebDriverWait(driver, 30).until(current_draft_history_row)
        verify_profile_change_row(
            history_row,
            "브랜드 · 이름 · 한국어",
            "오데노와",
            "ORDENOWA CI BRAND KO",
        )
        driver.save_screenshot(str(DEST / "brand-admin-history-change-diff.png"))

        stage = "replace_logo_in_saved_draft"
        replace_primary_logo_in_saved_draft(
            driver,
            settings_url,
            OFFICIAL_UPLOADS["pwa_icon"],
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
        replace_primary_logo_in_saved_draft(
            driver,
            settings_url,
            OFFICIAL_UPLOADS["primary_logo"],
            "restored approved draft logo",
        )
        driver.save_screenshot(str(DEST / "brand-admin-uploaded-draft-restored.png"))

        stage = "private_admin_preview"
        current_draft_row = WebDriverWait(driver, 30).until(current_draft_history_row)
        current_draft_row.find_element(By.CSS_SELECTOR, 'button[name="submitOrdenowaPreview"]').click()
        preview = visible(driver, ".ordenowa-profile-preview")
        for expected in (
            "ORDENOWA CI BRAND JP",
            "ORDENOWA CI BRAND DESCRIPTION JP",
            "ORDENOWA CI BRAND SLOGAN JP",
            "000-0000-0000",
            "ORDENOWA CI SHIPPING POLICY",
            "ORDENOWA CI REFUND POLICY",
            company_profile_ja,
            specified_act_preview_value,
        ):
            if expected not in preview.text:
                raise AssertionError("Korean admin operating settings are missing from the private preview")
        for selector, expected in policy_settings.items():
            if visible(driver, selector).get_attribute("value") != expected:
                raise AssertionError("a policy field changed while opening the private preview")
        if company_profile_ko not in visible(driver, company_profile_selector).get_attribute("value"):
            raise AssertionError("the Korean company profile was not retained in the draft before preview")
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
        wait_for_publish_confirmation(driver)
        for selector, expected in ci_settings.items():
            if visible(driver, selector).get_attribute("value") != expected:
                raise AssertionError("a Korean admin operating setting did not persist after publication")
        driver.save_screenshot(str(DEST / "brand-admin-published.png"))

        stage = "published_policy_fields_reload"
        driver.get(settings_url)
        visible(driver, "form.ordenowa-profile-settings")
        for selector, expected in policy_settings.items():
            if visible(driver, selector).get_attribute("value") != expected:
                raise AssertionError("a legal or policy field did not persist after publication and reload")
        driver.save_screenshot(str(DEST / "brand-admin-policies-published-reloaded.png"))

        stage = "published_desktop_customer_brand"
        assert_public_brand_assets(
            driver,
            "desktop",
            "header-desktop.png",
            stage_prefix="published_desktop_customer_brand",
            stage_callback=set_brand_assertion_stage,
        )
        driver.save_screenshot(str(DEST / "brand-desktop-published.png"))

        stage = "published_mobile_customer_brand"
        driver.set_window_size(390, 844)
        assert_public_brand_assets(
            driver,
            "mobile",
            "header-mobile.png",
            stage_prefix="published_mobile_customer_brand",
            stage_callback=set_brand_assertion_stage,
        )
        driver.save_screenshot(str(DEST / "brand-mobile-published.png"))

        stage = "published_korean_customer_brand"
        driver.set_window_size(1440, 960)
        assert_public_brand_assets(
            driver,
            "Korean",
            "header-desktop.png",
            locale_path="/ko/",
            expected_html_lang="ko-KR",
            seo_title=SEO_TITLE_KO,
            seo_description=SEO_DESCRIPTION_KO,
            jsonld_brand_name="ORDENOWA CI BRAND KO",
            pwa_name="ORDENOWA CI APP KO",
            pwa_short_name="ORDENOWA KO",
            stage_prefix="published_korean_customer_brand",
            stage_callback=set_brand_assertion_stage,
        )
        driver.save_screenshot(str(DEST / "brand-korean-published.png"))

        stage = "published_english_customer_brand"
        english_url = generated_storefront_language_url(driver, "en")
        assert_public_brand_assets(
            driver,
            "English",
            "header-desktop.png",
            locale_url=english_url,
            expected_html_lang="en-US",
            seo_title=SEO_TITLE_EN,
            seo_description=SEO_DESCRIPTION_EN,
            jsonld_brand_name="ORDENOWA CI BRAND EN",
            pwa_name="ORDENOWA CI APP EN",
            pwa_short_name="ORDENOWA EN",
            stage_prefix="published_english_customer_brand",
            stage_callback=set_brand_assertion_stage,
        )
        driver.save_screenshot(str(DEST / "brand-english-published.png"))

        stage = "published_company_profile_and_seller_disclosures_remain_gated"
        private_disclosure_groups = (
            "seller", "company_reference", "customer_support", "shipping", "refund", "company_profile"
        )
        private_values = [
            value
            for selector, value in ci_settings.items()
            if any(f"[{group}]" in selector for group in private_disclosure_groups)
        ]
        assert_seller_disclosures_remain_gated(driver, private_values)

        stage = "prepare_history_restore_distinguishable_draft"
        published_public_snapshot = public_brand_snapshot(driver)
        driver.get(settings_url)
        visible(driver, "form.ordenowa-profile-settings")
        temporary_terms_selector = 'textarea[name="profile[content][terms][ko-KR]"]'
        temporary_terms_value = "ORDENOWA CI TEMPORARY TERMS DRAFT"
        temporary_terms = visible(driver, temporary_terms_selector)
        temporary_terms.clear()
        temporary_terms.send_keys(temporary_terms_value)
        visible(driver, 'form.ordenowa-profile-settings button[name="submitOrdenowaSaveDraft"]').click()
        wait_for_draft_save_confirmation(driver)
        driver.get(settings_url)
        visible(driver, "form.ordenowa-profile-settings")
        if visible(driver, temporary_terms_selector).get_attribute("value") != temporary_terms_value:
            raise AssertionError("the temporary policy draft did not persist before history restoration")
        if public_brand_snapshot(driver) != published_public_snapshot:
            raise AssertionError("saving a policy draft changed customer output before publication")

        stage = "restore_published_history_as_draft"
        restore_published_history_version_as_draft(
            driver,
            settings_url,
            ci_settings,
            published_public_snapshot,
            set_brand_assertion_stage,
        )
        driver.save_screenshot(str(DEST / "brand-admin-history-restored-draft.png"))

        stage = "admin_login_after_publish"
        stage = "admin_login_after_publish_navigation"
        driver.delete_all_cookies()
        driver.get(ADMIN_LOGIN + "/login")
        stage = "admin_login_after_publish_logo_wait"
        try:
            login_logo = image_is_rendered(driver, ".ordenowa-admin-login-brand img")
        except TimeoutException:
            emit_brand_admin_login_diagnostics(driver, stage)
            raise
        if login_logo["width"] < 1 or "admin-login.png" not in login_logo["src"]:
            raise AssertionError("published ORDENOWA admin login logo did not render")
        assert_uploaded_derivative_url(
            login_logo["src"], OFFICIAL_UPLOADS["primary_logo"], "admin-login.png", "admin login logo"
        )
        assert_no_legacy_brand_in_rendered_page(driver, "admin login")
        driver.save_screenshot(str(DEST / "brand-admin-login-after-publish.png"))
        official_admin_login_logo = login_logo["src"]
        stage = "admin_login_after_publish_session_restore"
        restore_admin_session(
            driver,
            set_brand_assertion_stage,
            "admin_login_after_publish_session_restore",
        )
        stage = "admin_login_after_publish_settings_link"
        settings_url = business_profile_settings_url(driver)

        stage = "record_official_published_mobile_header_logo"
        driver.set_window_size(390, 844)
        driver.get(BASE + "/")
        official_mobile_header_logo = image_is_rendered(driver, "picture img.kuranea-brand__image")["src"]
        driver.set_window_size(1440, 960)
        stage = "record_official_published_header_logo"
        official_header_logo = public_brand_snapshot(driver)["logo"]

        stage = "favicon_symbol_replacement_publish_restore"
        replace_publish_restore_brand_icon(
            driver,
            settings_url,
            slot="favicon_symbol",
            replacement_source=OFFICIAL_UPLOADS["pwa_icon"],
            approved_source=OFFICIAL_UPLOADS["favicon_symbol"],
            preview_field_id="ordenowa-brand-assets-favicon",
            form_preview_filename="favicon.ico",
            replacement_previews=(("favicon-32.png", OFFICIAL_UPLOADS["pwa_icon"]),),
            approved_previews=(("favicon-32.png", OFFICIAL_UPLOADS["favicon_symbol"]),),
            stage_callback=set_brand_assertion_stage,
        )

        stage = "pwa_icon_replacement_publish_restore"
        replace_publish_restore_brand_icon(
            driver,
            settings_url,
            slot="pwa_icon",
            replacement_source=OFFICIAL_UPLOADS["favicon_symbol"],
            approved_source=OFFICIAL_UPLOADS["pwa_icon"],
            preview_field_id="ordenowa-brand-assets-pwa_512",
            form_preview_filename="pwa-512.png",
            replacement_previews=(
                ("apple-touch-icon.png", OFFICIAL_UPLOADS["favicon_symbol"]),
                ("pwa-512.png", OFFICIAL_UPLOADS["favicon_symbol"]),
            ),
            approved_previews=(
                ("apple-touch-icon.png", OFFICIAL_UPLOADS["pwa_icon"]),
                ("pwa-512.png", OFFICIAL_UPLOADS["pwa_icon"]),
            ),
            stage_callback=set_brand_assertion_stage,
        )

        stage = "replace_published_logo_in_saved_draft"
        public_before_logo_draft = public_brand_snapshot(driver)
        replace_primary_logo_in_saved_draft(
            driver,
            settings_url,
            OFFICIAL_UPLOADS["pwa_icon"],
            "temporary replacement logo for publication",
            stage_callback=set_brand_assertion_stage,
            stage_prefix="replace_published_logo_in_saved_draft",
        )
        driver.save_screenshot(str(DEST / "brand-admin-replacement-before-publish.png"))
        if public_brand_snapshot(driver) != public_before_logo_draft:
            raise AssertionError("saving a replacement-logo draft changed the public brand before publish")
        driver.get(settings_url)
        visible(driver, "form.ordenowa-profile-settings")

        stage = "publish_replacement_logo"
        # Set this before clicking because the server may publish successfully
        # even if the confirmation page or following assertion fails.
        replacement_publish_started = True
        publish_saved_brand_draft(driver, set_brand_assertion_stage, "replacement_publish")
        driver.save_screenshot(str(DEST / "brand-admin-replacement-published.png"))

        stage = "published_replacement_logo"
        replacement_logos = assert_published_logo_source(
            driver,
            OFFICIAL_UPLOADS["pwa_icon"],
            expected_previous_header_logos={
                "desktop": official_header_logo,
                "mobile": official_mobile_header_logo,
            },
            expected_previous_admin_login_logo=official_admin_login_logo,
            stage_callback=set_brand_assertion_stage,
            stage_prefix="published_replacement_logo",
        )
        settings_url = business_profile_settings_url(driver)

        stage = "restore_approved_logo_after_replacement_publish"
        replace_primary_logo_in_saved_draft(
            driver,
            settings_url,
            OFFICIAL_UPLOADS["primary_logo"],
            "restore approved logo after replacement publication",
        )
        driver.save_screenshot(str(DEST / "brand-admin-approved-logo-before-republish.png"))

        stage = "publish_restored_approved_logo"
        publish_saved_brand_draft(driver, set_brand_assertion_stage, "restored_publish")
        driver.save_screenshot(str(DEST / "brand-admin-approved-logo-republished.png"))

        stage = "published_restored_approved_logo"
        restored_logos = assert_published_logo_source(
            driver,
            OFFICIAL_UPLOADS["primary_logo"],
            expected_previous_header_logos={
                "desktop": replacement_logos["desktop_header"],
                "mobile": replacement_logos["mobile_header"],
            },
            expected_previous_admin_login_logo=replacement_logos["admin_login"],
            stage_callback=set_brand_assertion_stage,
            stage_prefix="published_restored_approved_logo",
        )
        settings_url = business_profile_settings_url(driver)
        if restored_logos["desktop_header"] != official_header_logo:
            raise AssertionError("republishing the approved source did not restore the original desktop logo URL")
        if restored_logos["mobile_header"] != official_mobile_header_logo:
            raise AssertionError("republishing the approved source did not restore the original mobile logo URL")
        if restored_logos["admin_login"] != official_admin_login_logo:
            raise AssertionError("republishing the approved source did not restore the original admin login logo URL")
        replacement_publish_started = False

        print("PASS: official ORDENOWA uploads, history restore as draft, replacement publish and restoration, Korean operating and legal settings draft/reload/preview/publish, closed storefront gate, PC/mobile logos, admin login, favicon, Apple icon, PWA, OG, and SEO")
    except Exception as error:
        try:
            driver.save_screenshot(str(DEST / "brand-admin-failure.png"))
        except Exception:
            pass
        print(f"FAIL: ORDENOWA brand browser flow at {stage} ({type(error).__name__})", file=sys.stderr)
        print(f"::error title=ORDENOWA brand browser QA::{stage} ({type(error).__name__})", file=sys.stderr)
        raise SystemExit("isolated ORDENOWA brand browser flow failed") from None
    finally:
        if replacement_publish_started and settings_url:
            try:
                restore_approved_logo_after_failure(driver, settings_url, set_brand_assertion_stage)
                print("ORDENOWA_BRAND_RESTORE_CLEANUP=passed", file=sys.stderr)
            except Exception as cleanup_error:
                print(
                    "ORDENOWA_BRAND_RESTORE_CLEANUP=failed (" + type(cleanup_error).__name__ + ")",
                    file=sys.stderr,
                )
        driver.quit()


if __name__ == "__main__":
    run()
