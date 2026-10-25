#!/usr/bin/env python3
"""Verify run-scoped default category labels in the desktop storefront header."""

from __future__ import annotations

import json
import os
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


BASE = os.environ["SHOP_BASE_URL"].rstrip("/")
DEST = Path(os.environ["QA_ARTIFACT_DIR"])
FIXTURE_REPORT = Path(os.environ["CI_CATEGORY_LOCALE_FIXTURE_REPORT"])
DEST.mkdir(parents=True, exist_ok=True)

EXPECTED = {
    "ja": ("ja", {"衣料品", "アート"}, {"Clothes", "Art"}, "storefront-category-ja.png"),
    "en": ("en", {"Clothes", "Art"}, set(), "storefront-category-en.png"),
    "ko": ("ko", {"의류", "아트"}, {"Clothes", "Art"}, "storefront-category-ko.png"),
}


def assert_true(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    fixture = json.loads(FIXTURE_REPORT.read_text(encoding="utf-8"))
    assert_true(fixture.get("database_isolated") is True, "category locale fixture is not marked as isolated")
    assert_true(fixture.get("created_categories") == 0, "category locale fixture must not create taxonomy rows")
    assert_true(fixture.get("updated_fields") == ["category_lang.name for ja and ko only"], "fixture changed unexpected fields")
    language_ids = fixture.get("language_ids")
    assert_true(isinstance(language_ids, dict), "category locale fixture has no language ID map")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,900")
    options.add_argument("--lang=ja-JP")
    driver = webdriver.Chrome(options=options)
    try:
        for locale, (html_language, expected_labels, forbidden_labels, screenshot) in EXPECTED.items():
            language_id = language_ids.get(locale)
            assert_true(isinstance(language_id, int) and language_id > 0, f"{locale} language is missing from fixture")
            driver.get(f"{BASE}/index.php?id_lang={language_id}")
            WebDriverWait(driver, 40).until(
                lambda browser: browser.execute_script("return document.readyState") == "complete"
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
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
