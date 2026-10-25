from __future__ import annotations

import unittest
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneabackoffice"
TRANSLATIONS = MODULE / "translations" / "ko-KR"
NAMESPACE = {"x": "urn:oasis:names:tc:xliff:document:1.2"}

ORDERS_FEATURE_DESCRIPTION = (
    "Find all your orders on this page and access their main information in one click: "
    "check the cart total, the payment method, the shipping details, or if it comes from "
    "a new client. You can even update the status from the listing!"
)

OVERLAYS = {
    "Admin.Navigation.Menu": (
        "AdminNavigationMenu.ko-KR.xlf",
        {"Orders": "주문"},
    ),
    "Admin.Orderscustomers.Feature": (
        "AdminOrderscustomersFeature.ko-KR.xlf",
        {
            "Add new order": "새 주문 추가",
            "Change Order Status": "주문 상태 변경",
            "Manage your orders": "주문 관리",
            ORDERS_FEATURE_DESCRIPTION: (
                "이 페이지에서 모든 주문을 확인하고 주요 정보를 한 번에 볼 수 있습니다. "
                "장바구니 합계, 결제 방법, 배송 정보, 신규 고객의 주문 여부를 확인하고 "
                "목록에서 주문 상태도 변경할 수 있습니다."
            ),
        },
    ),
}


def translations(path: Path) -> dict[str, str]:
    root = ET.parse(path).getroot()
    return {
        unit.findtext("x:source", namespaces=NAMESPACE): unit.findtext(
            "x:target", namespaces=NAMESPACE
        )
        for unit in root.findall(".//x:trans-unit", NAMESPACE)
    }


class OrdersLocaleOverlayTests(unittest.TestCase):
    def test_admin_locale_subscriber_loads_the_orders_translation_domains(self) -> None:
        source = (MODULE / "src" / "AdminLocaleSubscriber.php").read_text(encoding="utf-8")
        mappings = dict(
            re.findall(r"'([^']+)'\s*=>\s*'([^']+\.ko-KR\.xlf)'", source)
        )

        for domain, (filename, _) in OVERLAYS.items():
            with self.subTest(domain=domain):
                self.assertEqual(filename, mappings.get(domain), f"missing overlay mapping for {domain}")

        self.assertIn(
            "$this->translator->addResource('xlf', $translationFile, $locale, $catalogueDomain)",
            source,
        )

    def test_orders_overlay_domains_are_normalized_before_registration(self) -> None:
        source = (MODULE / "src" / "AdminLocaleSubscriber.php").read_text(encoding="utf-8")

        self.assertIn(
            "use PrestaShop\\PrestaShop\\Core\\Translation\\Storage\\Normalizer\\DomainNormalizer;",
            source,
        )
        self.assertIn("$catalogueDomain = $domainNormalizer->normalize($domain);", source)
        self.assertIn(
            "$this->translator->addResource('xlf', $translationFile, $locale, $catalogueDomain)",
            source,
        )
        self.assertIn("$overlayFiles[$catalogueDomain] = $translationFile;", source)
        self.assertIn("$loader->load($translationFile, $locale, $catalogueDomain)", source)

    def test_orders_page_source_strings_have_korean_module_overlays(self) -> None:
        for domain, (filename, expected_translations) in OVERLAYS.items():
            with self.subTest(domain=domain):
                path = TRANSLATIONS / filename
                self.assertTrue(path.is_file(), f"missing Korean overlay for {domain}")
                actual_translations = translations(path)

                for source, expected_target in expected_translations.items():
                    with self.subTest(source=source):
                        self.assertIn(source, actual_translations)
                        target = actual_translations[source]
                        self.assertIsNotNone(target)
                        self.assertEqual(expected_target, target.strip())
                        self.assertNotIn(source, target)

    def test_orders_body_match_diagnostic_exposes_only_allowlisted_source_categories(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_admin_security_browser.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("body_match_source_categories=", browser)
        for category in (
            "toolbar",
            "breadcrumb",
            "navigation",
            "kpi",
            "grid_header",
            "grid_controls",
            "grid_actions",
            "grid_body",
            "modal",
            "alert",
            "empty_state",
            "other_visible_content",
        ):
            with self.subTest(category=category):
                self.assertIn(category, browser)

        self.assertIn(r're.search(r"\border(s)?\b", body_text, re.IGNORECASE)', browser)


if __name__ == "__main__":
    unittest.main()
