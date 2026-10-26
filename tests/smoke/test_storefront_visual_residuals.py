"""Targeted checks for the latest storefront visual QA findings."""

from __future__ import annotations

import re
import runpy
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "themes" / "kuranea"


class StorefrontVisualResidualTests(unittest.TestCase):
    @staticmethod
    def _translation_targets(path: Path) -> dict[str, str]:
        root = ET.parse(path).getroot()
        ns = {"x": "urn:oasis:names:tc:xliff:document:1.2"}
        return {
            source: target
            for unit in root.findall(".//x:trans-unit", ns)
            if (source := unit.findtext("x:source", namespaces=ns))
            and (target := unit.findtext("x:target", namespaces=ns))
        }

    def test_korean_account_sidebar_has_localized_heading_and_browser_assertion(self) -> None:
        locale_path = THEME / "translations" / "ko-KR" / "ShopThemeCustomeraccount.ko-KR.xlf"
        self.assertTrue(locale_path.is_file(), "Korean customer account needs its theme translation catalog")
        translations = self._translation_targets(locale_path)
        self.assertEqual(translations.get("My Account"), "내 계정")
        self.assertEqual(translations.get("My account navigation sidebar"), "내 계정 메뉴")
        self.assertEqual(
            translations.get("Manage your addresses for billing and delivery to streamline your future orders."),
            "청구 및 배송 주소를 관리하여 다음 주문을 더 간편하게 진행하세요.",
        )
        self.assertEqual(
            translations.get("Add a new address to your account."),
            "계정에 새 주소를 등록할 수 있습니다.",
        )

        browser = (ROOT / "tests" / "e2e" / "verify_pwa_browser.py").read_text(encoding="utf-8")
        self.assertIn("def _assert_customer_account_chrome", browser)
        self.assertIn("_assert_customer_account_chrome(driver, locale, device)", browser)

    def test_mobile_product_breadcrumb_wraps_the_long_current_item(self) -> None:
        css = (THEME / "assets" / "css" / "custom.css").read_text(encoding="utf-8")
        mobile_rules = css.split("@media (max-width: 767.98px) {", 1)[1].split(
            "@media (min-width: 768px)", 1
        )[0]
        current_item = re.search(r"body#product \.breadcrumb-item:last-child\s*\{([^}]*)\}", mobile_rules)
        self.assertIsNotNone(current_item, "the mobile product breadcrumb needs a current-title override")
        current_rules = current_item.group(1)
        self.assertIn("white-space: normal", current_rules)
        self.assertIn("overflow-wrap: anywhere", current_rules)
        self.assertIn("min-width: 0", current_rules)
        self.assertRegex(
            mobile_rules,
            r"body#product \.breadcrumb\s*\{[^}]*flex-wrap: wrap;[^}]*overflow-x: visible;",
        )

        browser = (ROOT / "tests" / "e2e" / "verify_storefront_browser.py").read_text(encoding="utf-8")
        self.assertIn("def assert_mobile_product_breadcrumb", browser)
        self.assertIn("assert_mobile_product_breadcrumb(driver)", browser)

    def test_long_mobile_breadcrumb_contract_rejects_clipped_titles(self) -> None:
        namespace = runpy.run_path(str(ROOT / "tests" / "e2e" / "storefront_product_contract.py"))
        evaluator = namespace.get("mobile_product_breadcrumb_failure_reason")
        self.assertTrue(callable(evaluator), "a pure long-title breadcrumb contract is required")

        valid = {
            "title_matches_heading": True,
            "title_length": 54,
            "breadcrumb_client_width": 350,
            "breadcrumb_scroll_width": 350,
            "current_item_client_width": 350,
            "current_item_scroll_width": 350,
            "within_breadcrumb_bounds": True,
        }
        self.assertIsNone(evaluator(**valid))
        self.assertEqual(
            evaluator(**{**valid, "current_item_scroll_width": 410}),
            "breadcrumb_text_overflow",
        )


if __name__ == "__main__":
    unittest.main()
