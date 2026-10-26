"""Contracts for resolving native contact routes from PrestaShop's own Link API."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "tests/e2e/native_contact_route.py"
PHP_FIXTURE = ROOT / "tests/business_profile/read_native_contact_route.php"
WORKFLOW = ROOT / ".github/workflows/fresh-install.yml"


class NativeContactRouteContractTests(unittest.TestCase):
    def module(self):
        spec = importlib.util.spec_from_file_location("native_contact_route", HELPER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_php_fixture_reads_routes_and_settings_without_mutating_the_shop(self):
        source = PHP_FIXTURE.read_text(encoding="utf-8")
        for required in (
            "WHERE page = 'contact'", "meta_lang", "PS_REWRITING_SETTINGS",
            "PS_CANONICAL_REDIRECT", "Module::isEnabled('contactform')",
            "getPageLink('contact', null, $idLang)", "urls_by_iso", "localized_rewrites",
            "KURANEA_ISOLATED_CI", "CI_COMPOSE_PROJECT_NAME",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        for forbidden in ("Configuration::updateValue", "$db->update(", "$db->insert(", "$db->delete("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_fixture_requires_same_origin_native_contact_routes_for_all_locales(self):
        module = self.module()
        payload = {
            "schema": 1,
            "contact_meta_present": True,
            "rewriting_enabled": True,
            "canonical_redirect_mode": 1,
            "contactform_enabled": True,
            "localized_rewrites": {"ja": True, "en": True, "ko": True},
            "urls_by_iso": {
                "ja": "http://localhost:18080/contact-us",
                "en": "http://localhost:18080/en/contact-us",
                "ko": "http://localhost:18080/ko/contact-us",
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            fixture_path = Path(temp) / "contact-route.json"
            fixture_path.write_text(json.dumps(payload), encoding="utf-8")
            for locale in ("ja", "en", "ko"):
                self.assertEqual(payload["urls_by_iso"][locale],
                                 module.contact_url_for_locale(fixture_path, "http://localhost:18080", locale))
            payload["urls_by_iso"]["ja"] = "http://outside.invalid/contact-us"
            fixture_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                module.read_contact_route_fixture(fixture_path, "http://localhost:18080")

    def test_fixture_rejects_ambiguous_controller_and_unexpected_query_values(self):
        module = self.module()
        for url in (
            "http://localhost:18080/index.php?controller=contact&controller=contact",
            "http://localhost:18080/index.php?controller=authentication",
        ):
            with self.subTest(url=url):
                self.assertEqual("other", module.contact_route_class(url, "http://localhost:18080"))

        for query in ("token=secret", "unexpected=1", "controller=contact&controller=contact"):
            payload = {
                "schema": 1, "contact_meta_present": True, "rewriting_enabled": True,
                "canonical_redirect_mode": 1, "contactform_enabled": True,
                "localized_rewrites": {"ja": True, "en": True, "ko": True},
                "urls_by_iso": {"ja": "http://localhost:18080/contact-us?" + query,
                                "en": "http://localhost:18080/en/contact-us",
                                "ko": "http://localhost:18080/ko/contact-us"},
            }
            with tempfile.TemporaryDirectory() as temp:
                fixture_path = Path(temp) / "contact-route.json"
                fixture_path.write_text(json.dumps(payload), encoding="utf-8")
                with self.subTest(query=query), self.assertRaises(ValueError):
                    module.read_contact_route_fixture(fixture_path, "http://localhost:18080")

    def test_workflow_creates_one_read_only_route_snapshot_for_pwa_and_support(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        step = workflow.split("- name: Read isolated native contact route", 1)[1].split("- name:", 1)[0]
        self.assertIn("id: native_contact_route_fixture", step)
        self.assertIn("read_native_contact_route.php", step)
        self.assertIn("ordenowa-contact-route.json", step)
        self.assertIn("continue-on-error: true", step)
        for name in ("Verify Chromium PWA lifecycle and private-route cache protection",
                     "Verify native customer support lifecycle in Chromium"):
            body = workflow.split(f"- name: {name}", 1)[1].split("- name:", 1)[0]
            self.assertIn("CONTACT_ROUTE_FIXTURE", body)
            self.assertIn("steps.native_contact_route_fixture.outcome == 'success'", body)


if __name__ == "__main__":
    unittest.main()
