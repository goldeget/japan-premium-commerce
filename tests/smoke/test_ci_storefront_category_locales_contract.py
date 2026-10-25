"""Contracts for localized labels on existing default categories in disposable CI."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "fresh-install.yml"


class StorefrontCategoryLocalesContractTests(unittest.TestCase):
    def test_fixture_changes_only_names_on_exact_existing_isolated_category_rows(self) -> None:
        fixture = ROOT / "tests" / "catalog" / "prepare_ci_storefront_locale_fixtures.php"
        self.assertTrue(fixture.is_file(), "the CI-only category locale fixture is missing")
        source = fixture.read_text(encoding="utf-8")
        for expected in (
            "KURANEA_ISOLATED_CI",
            "KURANEA_CI_RUN_ID",
            "KURANEA_CI_RUN_ATTEMPT",
            "SELECT DATABASE()",
            "category_shop",
            "category_lang",
            "cl.`name`",
            "Clothes",
            "Art",
            "衣料品",
            "アート",
            "의류",
            "아트",
            "['name' => pSQL($localizedNames[$isoCode])]",
            "link_rewrite_preserved",
            "other_languages_preserved",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)
        self.assertNotIn("new Category()", source)
        self.assertNotIn("DELETE FROM", source)
        self.assertNotIn("id_parent` =", source)

    def test_browser_checks_visible_navigation_labels_in_all_three_locales(self) -> None:
        browser = ROOT / "tests" / "e2e" / "verify_storefront_category_locale_browser.py"
        self.assertTrue(browser.is_file(), "the category locale browser check is missing")
        source = browser.read_text(encoding="utf-8")
        for expected in (
            "衣料品",
            "アート",
            "Clothes",
            "Art",
            "의류",
            "아트",
            "#top-menu .ps-mainmenu__tree-link",
            "storefront-category-ja.png",
            "storefront-category-en.png",
            "storefront-category-ko.png",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)

    def test_workflow_runs_fixture_after_install_and_captures_its_browser_results(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Prepare isolated default category locale data", workflow)
        self.assertIn("Verify JA/EN/KO default category labels in Chromium", workflow)
        self.assertIn("prepare_ci_storefront_locale_fixtures.php", workflow)
        self.assertIn("verify_storefront_category_locale_browser.py", workflow)
        self.assertIn("storefront-category-ja.png", workflow)
        self.assertIn("storefront-category-en.png", workflow)
        self.assertIn("storefront-category-ko.png", workflow)
        self.assertLess(workflow.index("Start the empty-volume shop"), workflow.index("Prepare isolated default category locale data"))
        self.assertLess(workflow.index("Prepare isolated default category locale data"), workflow.index("Verify JA/EN/KO default category labels in Chromium"))


if __name__ == "__main__":
    unittest.main()
