#!/usr/bin/env python3
"""Verify run-scoped default category labels in the desktop storefront header."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait


BASE = os.environ["SHOP_BASE_URL"].rstrip("/")
DEST = Path(os.environ["QA_ARTIFACT_DIR"])
FIXTURE_REPORT = Path(os.environ["CI_CATEGORY_LOCALE_FIXTURE_REPORT"])
LANGUAGE_OPTIONS = "select.js-language-selector option[data-iso-code]"
QUERY_FIELDS = ("id_lang", "isolang", "lang")
DEST.mkdir(parents=True, exist_ok=True)

EXPECTED = {
    "ja": ("ja", {"衣料品", "アート"}, {"Clothes", "Art"}, "storefront-category-ja.png"),
    "en": ("en", {"Clothes", "Art"}, set(), "storefront-category-en.png"),
    "ko": ("ko", {"의류", "아트"}, {"Clothes", "Art"}, "storefront-category-ko.png"),
}


def assert_true(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def origin_parts(url: str) -> tuple[str, str, int] | None:
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        return parsed.scheme.lower(), parsed.hostname.lower(), port
    except (TypeError, ValueError):
        return None


def is_same_origin(url: str, reference_url: str) -> bool:
    destination_origin = origin_parts(url)
    reference_origin = origin_parts(reference_url)
    return destination_origin is not None and reference_origin is not None and destination_origin == reference_origin


def redact_pathname(pathname: str) -> str:
    try:
        segments = unquote(pathname or "/", errors="replace").split("/")
    except (TypeError, ValueError):
        return "/"

    safe_segments: list[str] = []
    for index, segment in enumerate(segments):
        if not segment:
            safe_segments.append("")
            continue
        previous = segments[index - 1] if index else ""
        if (
            previous in {"reset-password", "token", "auth"}
            or "@" in segment
            or "=" in segment
            or re.fullmatch(r"[0-9]{5,}", segment)
            or re.fullmatch(r"[a-fA-F0-9]{32,}", segment)
            or len(segment) > 96
            or not re.fullmatch(r"[\w._~-]{1,96}", segment, flags=re.UNICODE)
        ):
            safe_segments.append("[redacted]")
        else:
            safe_segments.append(segment)
    safe_pathname = "/".join(safe_segments)
    return safe_pathname if safe_pathname.startswith("/") else f"/{safe_pathname}"


def safe_query_fields(query: str) -> dict[str, dict[str, object]]:
    try:
        values = parse_qs(query[:4096], keep_blank_values=True, max_num_fields=64)
    except (TypeError, ValueError):
        values = {}

    safe_fields: dict[str, dict[str, object]] = {}
    for field in QUERY_FIELDS:
        field_values = values.get(field, [])
        value: str | None = None
        if len(field_values) == 1:
            candidate = field_values[0]
            if field == "id_lang":
                value = candidate if re.fullmatch(r"[0-9]{1,8}", candidate) else "[redacted]"
            else:
                value = candidate if re.fullmatch(r"[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})?", candidate) else "[redacted]"
        elif len(field_values) > 1:
            value = "[multiple]"
        safe_fields[field] = {"present": bool(field_values), "value": value}
    return safe_fields


def select_language(driver, locale: str) -> tuple[str, bool]:
    selector = driver.find_element(By.CSS_SELECTOR, "select.js-language-selector")
    options = selector.find_elements(By.CSS_SELECTOR, "option[data-iso-code]")
    matches = [
        option
        for option in options
        if (option.get_attribute("data-iso-code") or "").lower() == locale
    ]
    assert_true(len(matches) == 1, f"the storefront language selector has no unique {locale} option")

    option = matches[0]
    iso_code = (option.get_attribute("data-iso-code") or "").lower()
    assert_true(iso_code == locale, f"the storefront language selector returned an unexpected locale for {locale}")
    option_value = option.get_attribute("value") or ""
    assert_true(bool(option_value), f"the storefront language selector has no destination for {locale}")

    destination = urljoin(str(driver.current_url), option_value)
    same_origin = is_same_origin(destination, str(driver.current_url))
    if same_origin:
        Select(selector).select_by_value(option_value)
    return destination, same_origin


def failure_evidence(
    driver,
    locale: str,
    reference_url: str,
    screenshot_saved: bool,
    selector_destination: str | None,
    selector_destination_same_origin: bool | None,
) -> dict[str, object]:
    try:
        current_url = str(driver.current_url)
    except Exception:
        current_url = ""
    try:
        current_parts = urlparse(current_url)
        same_origin = is_same_origin(current_url, reference_url)
        pathname = redact_pathname(current_parts.path)
        approved_query = safe_query_fields(current_parts.query)
    except (TypeError, ValueError):
        same_origin = False
        pathname = "/"
        approved_query = safe_query_fields("")

    try:
        document_lang = str(driver.find_element(By.TAG_NAME, "html").get_attribute("lang") or "").lower()
    except Exception:
        document_lang = ""
    if not re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})?", document_lang):
        document_lang = "[redacted]" if document_lang else ""

    try:
        ready_state = str(driver.execute_script("return document.readyState") or "unknown")
    except Exception:
        ready_state = "unknown"
    if ready_state not in {"loading", "interactive", "complete"}:
        ready_state = "other"

    try:
        destination_parts = urlparse(selector_destination or "")
        destination_pathname = redact_pathname(destination_parts.path or "/")
        destination_query = safe_query_fields(destination_parts.query)
    except (TypeError, ValueError):
        destination_pathname = "/"
        destination_query = safe_query_fields("")

    return {
        "locale": locale if locale in EXPECTED else "unknown",
        "same_origin": same_origin,
        "pathname": pathname,
        "approved_query": approved_query,
        "selector_destination_same_origin": selector_destination_same_origin,
        "selector_destination_pathname": destination_pathname,
        "selector_destination_query": destination_query,
        "document_lang": document_lang,
        "ready_state": ready_state,
        "screenshot_saved": screenshot_saved,
    }


def main() -> None:
    fixture = json.loads(FIXTURE_REPORT.read_text(encoding="utf-8"))
    assert_true(fixture.get("database_isolated") is True, "category locale fixture is not marked as isolated")
    assert_true(fixture.get("created_categories") == 0, "category locale fixture must not create taxonomy rows")
    assert_true(fixture.get("updated_fields") == ["category_lang.name for ja and ko only"], "fixture changed unexpected fields")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,900")
    options.add_argument("--lang=ja-JP")
    driver = webdriver.Chrome(options=options)
    failed_locale = "unknown"
    failure_target: str | None = None
    failure_target_same_origin: bool | None = None
    reference_url = BASE
    failure_screenshot = "storefront-category-locale-failure.png"
    try:
        driver.get(BASE)
        reference_url = str(driver.current_url)
        for locale, (html_language, expected_labels, forbidden_labels, screenshot) in EXPECTED.items():
            failed_locale = locale
            failure_screenshot = screenshot
            failure_target, failure_target_same_origin = select_language(driver, locale)
            assert_true(
                failure_target_same_origin,
                f"the storefront language selector destination leaves the current origin for {locale}",
            )
            WebDriverWait(driver, 40).until(
                lambda browser: browser.execute_script("return document.readyState") == "complete"
            )
            assert_true(
                is_same_origin(str(driver.current_url), reference_url),
                f"the final storefront document left the shop origin for {locale}",
            )
            document_language = (driver.find_element(By.TAG_NAME, "html").get_attribute("lang") or "").lower()
            assert_true(
                document_language.split("-")[0] == html_language,
                f"storefront did not select the expected {locale} document language",
            )
            links = driver.find_elements(By.CSS_SELECTOR, "#top-menu .ps-mainmenu__tree-link")
            visible_labels = {
                " ".join(link.text.split())
                for link in links
                if link.is_displayed() and link.text.strip()
            }
            assert_true(
                expected_labels.issubset(visible_labels),
                f"default category labels are missing from the {locale} storefront navigation",
            )
            assert_true(
                not forbidden_labels.intersection(visible_labels),
                f"English default category labels remain in the {locale} storefront navigation",
            )
            driver.save_screenshot(str(DEST / screenshot))
            print(f"PASS: {locale} storefront navigation shows the expected category labels ({len(visible_labels)} visible).")
    except Exception:
        screenshot_saved = False
        try:
            screenshot_saved = bool(driver.save_screenshot(str(DEST / failure_screenshot)))
        except Exception:
            screenshot_saved = False
        evidence = failure_evidence(
            driver,
            failed_locale,
            reference_url,
            screenshot_saved,
            failure_target,
            failure_target_same_origin,
        )
        evidence_json = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
        try:
            (DEST / "storefront-category-locale-failure.json").write_text(evidence_json + "\n", encoding="utf-8")
        except OSError:
            pass
        print(f"ORDENOWA_CATEGORY_LOCALE_SAFE_STATE={evidence_json}", flush=True)
        raise AssertionError(f"storefront category locale browser check failed for {evidence['locale']}") from None
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
