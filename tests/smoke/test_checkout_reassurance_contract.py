"""Contracts for the module supplied checkout reassurance copy."""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "themes" / "kuranea"
REASSURANCE_OVERRIDE = (
    THEME
    / "modules"
    / "blockreassurance"
    / "views"
    / "templates"
    / "hook"
    / "displayBlockProduct.tpl"
)


class CheckoutReassuranceContractTests(unittest.TestCase):
    def test_checkout_renderer_translates_only_stock_titles_and_removes_editor_copy(self) -> None:
        self.assertTrue(REASSURANCE_OVERRIDE.is_file(), "the active checkout hook needs a child-theme override")
        template = REASSURANCE_OVERRIDE.read_text(encoding="utf-8")
        for expected in (
            "(edit with the Customer Reassurance module)",
            "Modules.Blockreassurance.Shop",
            "$block['title']",
            "$block['description']",
            "|strip_tags|replace:'&nbsp;':' '|replace:'&#160;':' '|trim",
            "visibleBlockCount",
            "blockreassurance--{$page.page_name}",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, template)
        for title in ("Security policy", "Delivery policy", "Return policy"):
            self.assertIn(f"s='{title}' d='Modules.Blockreassurance.Shop'", template)
        self.assertIn("$block['title']|escape:'htmlall':'UTF-8'", template)
        self.assertIn("$cleanedDescription nofilter", template)
        self.assertNotIn("conditions_to_approve", template)

    def test_generic_reassurance_titles_have_japanese_and_korean_translations(self) -> None:
        translations = {
            "ja-JP": {
                "Security policy": "セキュリティポリシー",
                "Delivery policy": "配送ポリシー",
                "Return policy": "返品ポリシー",
            },
            "ko-KR": {
                "Security policy": "보안 정책",
                "Delivery policy": "배송 정책",
                "Return policy": "반품 정책",
            },
        }
        namespace = {"x": "urn:oasis:names:tc:xliff:document:1.2"}
        for locale, expected in translations.items():
            path = THEME / "translations" / locale / f"ModulesBlockreassuranceShop.{locale}.xlf"
            self.assertTrue(path.is_file(), f"{locale} reassurance heading translations are missing")
            root = ET.parse(path).getroot()
            actual = {
                unit.findtext("x:source", namespaces=namespace): unit.findtext("x:target", namespaces=namespace)
                for unit in root.findall(".//x:trans-unit", namespace)
            }
            for source, target in expected.items():
                with self.subTest(locale=locale, source=source):
                    self.assertEqual(actual.get(source), target)

    def test_native_checkout_terms_remain_required_and_separate(self) -> None:
        payment = (
            ROOT
            / "themes"
            / "hummingbird"
            / "templates"
            / "checkout"
            / "_partials"
            / "steps"
            / "payment.tpl"
        ).read_text(encoding="utf-8")
        self.assertIn("{foreach from=$conditions_to_approve", payment)
        self.assertIn("id=\"conditions-to-approve\"", payment)
        self.assertIn("required", payment)
        self.assertIn("{$condition nofilter}", payment)

        browser = (ROOT / "tests" / "e2e" / "verify_ci_checkout_admin_browser.py").read_text(encoding="utf-8")
        self.assertIn("def assert_checkout_reassurance_copy", browser)
        self.assertIn("blockreassurance--checkout", browser)
        self.assertIn("edit with the Customer Reassurance module", browser)
        self.assertIn("conditions-to-approve", browser)

    def test_runtime_report_is_read_only_and_isolated(self) -> None:
        report = ROOT / "tests" / "catalog" / "verify_ci_blockreassurance_runtime.php"
        self.assertTrue(report.is_file(), "CI needs a read-only module version/hook/seed probe")
        source = report.read_text(encoding="utf-8")
        for expected in (
            "KURANEA_ISOLATED_CI",
            "KURANEA_CI_RUN_ID",
            "KURANEA_CI_RUN_ATTEMPT",
            "SELECT DATABASE()",
            "blockreassurance",
            "psreassurance_lang",
            "displayReassurance",
            "displayBlockProduct.tpl",
            "ja",
            "en",
            "ko",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)
        self.assertNotIn("Db::getInstance()->update", source)
        self.assertNotIn("password", source.casefold())
        self.assertNotIn("email", source.casefold())

    def test_checkout_browser_screens_are_required_in_artifact_coverage(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        self.assertIn("Verify installed Customer Reassurance module source and localized seed", workflow)
        self.assertIn("verify_ci_blockreassurance_runtime.php", workflow)
        self.assertIn("checkout-desktop-offline-payment-review.png", workflow)
        self.assertIn("checkout-mobile-offline-payment-review.png", workflow)
        self.assertIn("blockreassurance-runtime.json", workflow)


if __name__ == "__main__":
    unittest.main()
