from __future__ import annotations

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
        self.assertIn("loadLanguage", source)
        self.assertIn("addResource", source)
        self.assertIn("kernel.event_subscriber", services)
        self.assertTrue((MODULE / "translations" / "ko-KR" / "AdminActions.ko-KR.xlf").is_file())
        self.assertTrue((MODULE / "translations" / "ko-KR" / "messages.ko-KR.xlf").is_file())

    def test_admin_actions_overlay_fills_the_observed_back_to_gap(self) -> None:
        path = MODULE / "translations" / "ko-KR" / "AdminActions.ko-KR.xlf"
        self.assertTrue(path.is_file(), "missing module-owned Admin.Actions overlay")
        self.assertEqual("쇼핑몰로 돌아가기", translations(path).get("Back to"))

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

    def test_admin_login_hook_renders_the_official_logo(self) -> None:
        module_path = MODULE / "kuraneabackoffice.php"
        template_path = MODULE / "views" / "templates" / "hook" / "admin-login.tpl"
        self.assertTrue(module_path.is_file(), "missing Back Office branding module")
        self.assertTrue(template_path.is_file(), "missing admin login hook template")
        module_source = module_path.read_text()
        hook_template = template_path.read_text()
        logo = MODULE / "views" / "img" / "kuranea-logo.png"

        self.assertIn("displayAdminLogin", module_source)
        self.assertIn("hookDisplayAdminLogin", module_source)
        self.assertIn("kuranea-logo.png", module_source)
        self.assertIn("kuranea_backoffice_logo", hook_template)
        self.assertIn('alt="KURANEA"', hook_template)
        self.assertTrue(logo.is_file())
        self.assertEqual(b"\x89PNG\r\n\x1a\n", logo.read_bytes()[:8])


if __name__ == "__main__":
    unittest.main()
