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
            "localized_rewrite_by_iso",
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
            "localized_rewrite_by_iso": {"ja": "contact-us", "en": "contact-us", "ko": "contact-us"},
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
                "localized_rewrite_by_iso": {"ja": "contact-us", "en": "contact-us", "ko": "contact-us"},
                "urls_by_iso": {"ja": "http://localhost:18080/contact-us?" + query,
                                "en": "http://localhost:18080/en/contact-us",
                                "ko": "http://localhost:18080/ko/contact-us"},
            }
            with tempfile.TemporaryDirectory() as temp:
                fixture_path = Path(temp) / "contact-route.json"
                fixture_path.write_text(json.dumps(payload), encoding="utf-8")
                with self.subTest(query=query), self.assertRaises(ValueError):
                    module.read_contact_route_fixture(fixture_path, "http://localhost:18080")

    def test_dispatcher_controller_fallback_is_native_at_shop_or_locale_root(self):
        module = self.module()
        for locale, url in (
            ("ja", "http://localhost:18080/?controller=contact"),
            ("en", "http://localhost:18080/en/?controller=contact&id_lang=2"),
            ("ko", "http://localhost:18080/index.php?controller=contact&id_lang=3"),
        ):
            with self.subTest(locale=locale):
                self.assertEqual(
                    "contact", module.contact_route_class(url, "http://localhost:18080", locale=locale)
                )

    def test_language_specific_meta_rewrite_is_exactly_bounded(self):
        module = self.module()
        payload = {
            "schema": 1,
            "contact_meta_present": True,
            "rewriting_enabled": True,
            "canonical_redirect_mode": 1,
            "contactform_enabled": True,
            "localized_rewrites": {"ja": True, "en": True, "ko": True},
            "localized_rewrite_by_iso": {
                "ja": "お問い合わせ", "en": "contact-us", "ko": "문의하기",
            },
            "urls_by_iso": {
                "ja": "http://localhost:18080/ja/%E3%81%8A%E5%95%8F%E3%81%84%E5%90%88%E3%82%8F%E3%81%9B",
                "en": "http://localhost:18080/en/contact-us",
                "ko": "http://localhost:18080/ko/%EB%AC%B8%EC%9D%98%ED%95%98%EA%B8%B0",
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            fixture_path = Path(temp) / "contact-route.json"
            fixture_path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(3, len(module.read_contact_route_fixture(fixture_path, "http://localhost:18080")["urls_by_iso"]))
            payload["urls_by_iso"]["ja"] = "http://localhost:18080/ja/unrelated"
            fixture_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "locale=ja; component=path"):
                module.read_contact_route_fixture(fixture_path, "http://localhost:18080")

    def test_generated_route_mismatch_reports_only_scheme_host_port_or_path(self):
        module = self.module()
        self.assertEqual(
            "port",
            module.contact_route_mismatch("http://localhost:0/contact-us", "http://localhost"),
        )
        fixtures = (
            ("https://localhost:18080/contact-us", "scheme"),
            ("http://outside.invalid/contact-us", "host"),
            ("http://localhost:18081/contact-us", "port"),
            ("http://localhost:18080/unrelated", "path"),
        )
        for candidate, component in fixtures:
            payload = {
                "schema": 1, "contact_meta_present": True, "rewriting_enabled": True,
                "canonical_redirect_mode": 1, "contactform_enabled": True,
                "localized_rewrites": {"ja": True, "en": True, "ko": True},
                "localized_rewrite_by_iso": {"ja": "contact-us", "en": "contact-us", "ko": "contact-us"},
                "urls_by_iso": {"ja": candidate, "en": "http://localhost:18080/en/contact-us",
                                "ko": "http://localhost:18080/ko/contact-us"},
            }
            with tempfile.TemporaryDirectory() as temp:
                fixture_path = Path(temp) / "contact-route.json"
                fixture_path.write_text(json.dumps(payload), encoding="utf-8")
                with self.subTest(component=component), self.assertRaisesRegex(
                    ValueError, f"locale=ja; component={component}"
                ) as raised:
                    module.read_contact_route_fixture(fixture_path, "http://localhost:18080")
                self.assertNotIn(candidate, str(raised.exception))

    def test_localized_rewrite_must_be_one_safe_path_segment(self):
        module = self.module()
        for rewrite in (
            "../contact", "contact/extra", r"contact\extra", "contact%2fextra",
            "contact%252fextra", "contact?x=1", "contact#fragment", "contact\x01",
            ".", "..",
        ):
            with self.subTest(rewrite=repr(rewrite)):
                self.assertIsNone(module.safe_contact_rewrite_segment(rewrite))
                self.assertEqual(
                    "other",
                    module.contact_route_class(
                        "http://localhost:18080/contact-us",
                        "http://localhost:18080",
                        locale="ja",
                        localized_rewrite=rewrite,
                    ),
                )

    def test_fixture_rejects_unsafe_rewrite_without_echoing_it(self):
        module = self.module()
        payload = {
            "schema": 1, "contact_meta_present": True, "rewriting_enabled": True,
            "canonical_redirect_mode": 1, "contactform_enabled": True,
            "localized_rewrites": {"ja": True, "en": True, "ko": True},
            "localized_rewrite_by_iso": {"ja": "contact%252fextra", "en": "contact-us", "ko": "contact-us"},
            "urls_by_iso": {"ja": "http://localhost:18080/contact-us",
                            "en": "http://localhost:18080/en/contact-us",
                            "ko": "http://localhost:18080/ko/contact-us"},
        }
        with tempfile.TemporaryDirectory() as temp:
            fixture_path = Path(temp) / "contact-route.json"
            fixture_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "locale=ja; component=path") as raised:
                module.read_contact_route_fixture(fixture_path, "http://localhost:18080")
            self.assertNotIn("contact%252fextra", str(raised.exception))

    def test_workflow_creates_one_read_only_route_snapshot_for_pwa_and_support(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        step = workflow.split("- name: Read isolated native contact route", 1)[1].split("- name:", 1)[0]
        self.assertIn("id: native_contact_route_fixture", step)
        self.assertIn("read_native_contact_route.php", step)
        self.assertIn("ordenowa-contact-route.json", step)
        self.assertIn("continue-on-error: true", step)
        self.assertIn("localized_rewrite_by_iso", step)
        for name in ("Verify Chromium PWA lifecycle and private-route cache protection",
                     "Verify native customer support lifecycle in Chromium"):
            body = workflow.split(f"- name: {name}", 1)[1].split("- name:", 1)[0]
            self.assertIn("CONTACT_ROUTE_FIXTURE", body)
            self.assertIn("steps.native_contact_route_fixture.outcome == 'success'", body)


if __name__ == "__main__":
    unittest.main()
