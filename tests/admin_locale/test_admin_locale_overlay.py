from __future__ import annotations

import hashlib
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneabackoffice"
NAMESPACE = {"x": "urn:oasis:names:tc:xliff:document:1.2"}


def translations(path: Path) -> dict[str, str]:
    root = ET.parse(path).getroot()
    return {
        unit.findtext("x:source", namespaces=NAMESPACE): unit.findtext(
            "x:target", namespaces=NAMESPACE
        )
        for unit in root.findall(".//x:trans-unit", NAMESPACE)
    }


class AdminLocaleOverlayContractTests(unittest.TestCase):
    def test_anonymous_login_uses_korean_admin_language_context(self) -> None:
        path = MODULE / "src" / "AdminLocaleSubscriber.php"
        self.assertTrue(path.is_file(), "missing request-scoped locale subscriber")
        source = path.read_text()

        self.assertIn("admin_login", source)
        self.assertIn("ko-KR", source)
        self.assertIn("setDefaultLocale", source)
        self.assertIn("setLocale", source)
        self.assertIn("LanguageContextBuilder", source)
        self.assertIn("setLanguageId", source)
        self.assertIn("getOneByLocaleOrIsoCode", source)
        self.assertIn("PRIORITY = 14", source)

    def test_overlay_resources_use_prestashop_translator_loader(self) -> None:
        source_path = MODULE / "src" / "AdminLocaleSubscriber.php"
        services_path = MODULE / "config" / "services.yml"
        self.assertTrue(source_path.is_file(), "missing request-scoped locale subscriber")
        self.assertTrue(services_path.is_file(), "missing PrestaShop service registration")
        source = source_path.read_text()
        services = services_path.read_text()

        self.assertIn("TranslatorLanguageLoader", source)
        self.assertIn("XliffFileLoader", source)
        self.assertIn("getCatalogue", source)
        self.assertIn("addCatalogue", source)
        self.assertIn("loadLanguage", source)
        self.assertIn("addResource", source)
        self.assertIn("kernel.event_subscriber", services)
        self.assertIn("Admin.Global", source)
        self.assertIn("Admin.Actions", source)
        self.assertIn("Admin.Navigation.Header", source)
        self.assertIn("AdminGlobal.ko-KR.xlf", source)
        self.assertTrue((MODULE / "translations" / "ko-KR" / "AdminNavigationHeader.ko-KR.xlf").is_file())
        self.assertTrue((MODULE / "translations" / "ko-KR" / "AdminActions.ko-KR.xlf").is_file())
        self.assertTrue((MODULE / "translations" / "ko-KR" / "AdminGlobal.ko-KR.xlf").is_file())
        self.assertTrue((MODULE / "translations" / "ko-KR" / "messages.ko-KR.xlf").is_file())

    def test_admin_dashboard_date_range_is_localized_by_module_asset(self) -> None:
        module_source = (MODULE / "kuraneabackoffice.php").read_text()
        javascript_path = MODULE / "views" / "js" / "dashboard-korean.js"
        self.assertIn("actionAdminControllerSetMedia", module_source)
        self.assertIn("dashboard-korean.js", module_source)
        self.assertTrue(javascript_path.is_file(), "missing module-owned dashboard locale asset")
        javascript = javascript_path.read_text()
        self.assertIn("시작일", javascript)
        self.assertIn("종료일", javascript)
        self.assertIn("date_from", javascript)
        self.assertIn("compare_date_to", javascript)

    def test_admin_actions_overlay_fills_the_observed_back_to_gap(self) -> None:
        path = MODULE / "translations" / "ko-KR" / "AdminActions.ko-KR.xlf"
        self.assertTrue(path.is_file(), "missing module-owned Admin.Actions overlay")
        self.assertEqual("쇼핑몰로 돌아가기", translations(path).get("Back to"))

    def test_admin_global_overlay_translates_the_observed_password_gap(self) -> None:
        path = MODULE / "translations" / "ko-KR" / "AdminGlobal.ko-KR.xlf"
        self.assertTrue(path.is_file(), "missing module-owned Admin.Global overlay")
        entries = translations(path)
        self.assertEqual("비밀번호", entries.get("Password"))
        self.assertEqual("시작일", entries.get("From"))
        self.assertEqual("종료일", entries.get("To"))

    def test_admin_navigation_header_overlay_translates_view_store_action(self) -> None:
        subscriber = (MODULE / "src" / "AdminLocaleSubscriber.php").read_text()
        self.assertIn("AdminNavigationHeader.ko-KR.xlf", subscriber)
        path = MODULE / "translations" / "ko-KR" / "AdminNavigationHeader.ko-KR.xlf"
        self.assertTrue(path.is_file(), "missing module-owned Admin.Navigation.Header overlay")
        self.assertEqual("내 쇼핑몰 보기", translations(path).get("View my store"))

    def test_psgdpr_overlay_translates_the_observed_admin_gaps(self) -> None:
        path = MODULE / "translations" / "ko-KR" / "messages.ko-KR.xlf"
        self.assertTrue(path.is_file(), "missing module-owned psgdpr fallback overlay")
        observed = {
            "Data visualization and automatic actions",
            "Compliant module list",
            "Search for a customer name OR email",
            "Remove data",
            "Download invoices",
        }

        translated = translations(path)
        for source in observed:
            with self.subTest(source=source):
                self.assertTrue(translated.get(source), f"missing Korean overlay for {source!r}")
                self.assertNotEqual(source, translated[source])

    def test_admin_login_hook_uses_official_ordenowa_logo_without_legacy_fallback(self) -> None:
        module_path = MODULE / "kuraneabackoffice.php"
        template_path = MODULE / "views" / "templates" / "hook" / "admin-login.tpl"
        self.assertTrue(module_path.is_file(), "missing Back Office branding module")
        self.assertTrue(template_path.is_file(), "missing admin login hook template")
        module_source = module_path.read_text()
        hook_template = template_path.read_text()
        logo = MODULE / "views" / "img" / "kuranea-logo.png"

        self.assertIn("displayAdminLogin", module_source)
        self.assertIn("hookDisplayAdminLogin", module_source)
        self.assertIn("ordenowa_backoffice_brand_name", module_source)
        self.assertIn("ordenowa_backoffice_brand_name", hook_template)
        self.assertIn("ProfileDefaults::initial()", module_source)
        self.assertIn("ORDENOWA", module_source)
        self.assertNotIn("kuranea-logo.png", module_source)
        self.assertNotIn("KURANEA", hook_template)
        self.assertIn("#login-header", hook_template)
        self.assertIn("#login-footer", hook_template)
        self.assertIn("#shop-img img", hook_template)
        self.assertIn("display: none !important", hook_template)
        self.assertIn("content: \"←\";", hook_template)
        # Preserve the original outside the served module webroot.
        source_logo = ROOT / "assets" / "brand" / "source" / "kuranea-logo.png"
        source_manifest = ROOT / "assets" / "brand" / "source" / "SHA256SUMS.txt"
        self.assertFalse(logo.exists(), "legacy KURANEA logo must not remain in the public module webroot")
        self.assertTrue(source_logo.is_file(), "preserved KURANEA source logo is missing")
        source_bytes = source_logo.read_bytes()
        self.assertEqual(b"\x89PNG\r\n\x1a\n", source_bytes[:8])
        source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        self.assertEqual(
            "ae54c1ae9042cbef7de8c0a81a9d8d9e819f060b90ee2d46841a88f8f498de69",
            source_sha256,
            "preserved KURANEA source logo no longer matches the verified original",
        )
        self.assertIn(
            f"{source_sha256}  kuranea-logo.png",
            source_manifest.read_text(encoding="utf-8").splitlines(),
        )


if __name__ == "__main__":
    unittest.main()
