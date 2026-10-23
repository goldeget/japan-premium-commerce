from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
FORM = ROOT / "modules/kuraneabusinessprofile/src/Admin/AdminProfileForm.php"
CONTROLLER = ROOT / "modules/kuraneabusinessprofile/controllers/admin/AdminBusinessProfileController.php"
BROWSER = ROOT / "tests/e2e/verify_shipping_admin_links_browser.py"
ROUTES = ROOT / "tests/e2e/shipping_admin_routes.py"
WORKFLOW = ROOT / ".github/workflows/fresh-install.yml"


class ShippingAdminLinksContractTests(unittest.TestCase):
    def test_shipping_policy_stays_editable_and_links_are_escaped_in_shipping_section(self) -> None:
        form = FORM.read_text(encoding="utf-8")
        self.assertIn("$localized(['shipping'], '배송 조건 및 안내', 'textarea')", form)
        self.assertIn("string $carriersAdminUrl = ''", form)
        self.assertIn("string $shippingPreferencesAdminUrl = ''", form)
        self.assertIn("if ($section['key'] === 'shipping'", form)
        self.assertIn('class="alert alert-info ordenowa-shipping-admin-links"', form)
        self.assertIn("self::escape($carriersAdminUrl)", form)
        self.assertIn("self::escape($shippingPreferencesAdminUrl)", form)
        self.assertIn("배송사·배송료 관리", form)
        self.assertIn("배송 기본 설정", form)

    def test_server_generates_links_for_prestashop_92_shipping_controllers(self) -> None:
        controller = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("getAdminLink('AdminCarriers')", controller)
        self.assertIn("getAdminLink('AdminShipping')", controller)
        self.assertIn("$carriersAdminUrl", controller)
        self.assertIn("$shippingPreferencesAdminUrl", controller)

    def test_ci_browser_check_resolves_both_links_in_the_authenticated_admin_session(self) -> None:
        self.assertTrue(BROWSER.is_file(), "a dedicated isolated Back Office link browser check is required")
        browser = BROWSER.read_text(encoding="utf-8")
        self.assertIn(
            "from shipping_admin_routes import is_korean_admin_language, matches_admin_controller_url",
            browser,
        )
        self.assertIn("matches_admin_controller_url(href, controller, expected_admin_path)", browser)
        self.assertIn("ordenowa-shipping-admin-carriers", browser)
        self.assertIn("ordenowa-shipping-admin-preferences", browser)
        self.assertIn("AdminCarriers", browser)
        self.assertIn("AdminShipping", browser)
        self.assertIn("credentials: 'same-origin'", browser)
        self.assertIn("shipping-admin-settings-desktop.png", browser)
        self.assertIn("shipping-admin-settings-mobile.png", browser)

        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Verify Korean admin shipping links resolve in Chromium", workflow)
        self.assertIn("shipping_admin_browser_qa", workflow)
        self.assertIn("shipping-admin-e2e.log", workflow)

    def test_modern_and_legacy_shipping_admin_urls_match_their_controllers(self) -> None:
        self.assertTrue(ROUTES.is_file(), "shipping admin URLs must use a dependency-free route matcher")
        spec = spec_from_file_location("shipping_admin_routes", ROUTES)
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        route_helper = module_from_spec(spec)
        spec.loader.exec_module(route_helper)
        matches = route_helper.matches_admin_controller_url

        for controller, route in (
            ("AdminCarriers", "improve/shipping/carriers"),
            ("AdminShipping", "improve/shipping/preferences"),
        ):
            with self.subTest(controller=controller, form="modern path"):
                self.assertTrue(
                    matches(
                        f"http://shop.test/admin-kuranea/{route}",
                        controller,
                        "/admin-kuranea",
                    )
                )
            with self.subTest(controller=controller, form="modern index.php path and trailing slash"):
                self.assertTrue(
                    matches(
                        f"http://shop.test/admin-kuranea/index.php/{route}/",
                        controller,
                        "/admin-kuranea",
                    )
                )
            with self.subTest(controller=controller, form="legacy controller query"):
                self.assertTrue(
                    matches(
                        f"http://shop.test/admin-kuranea/index.php?controller={controller}&token=ci-token",
                        controller,
                        "/admin-kuranea",
                    )
                )

        self.assertFalse(
            matches(
                "http://shop.test/admin-kuranea/improve/shipping/preferences",
                "AdminCarriers",
                "/admin-kuranea",
            )
        )
        self.assertFalse(
            matches(
                "http://shop.test/elsewhere/improve/shipping/carriers",
                "AdminCarriers",
                "/admin-kuranea",
            )
        )

    def test_carrier_action_urls_preserve_the_authenticated_admin_token(self) -> None:
        spec = spec_from_file_location("shipping_admin_routes_actions", ROUTES)
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        route_helper = module_from_spec(spec)
        spec.loader.exec_module(route_helper)

        modern = "http://shop.test/admin-kuranea/index.php/improve/shipping/carriers?token=ci-token"
        self.assertEqual(
            route_helper.carrier_action_url(modern, "create"),
            "http://shop.test/admin-kuranea/index.php/improve/shipping/carriers/create?token=ci-token",
        )
        self.assertEqual(
            route_helper.carrier_action_url(modern, "edit", 42),
            "http://shop.test/admin-kuranea/index.php/improve/shipping/carriers/42/edit?token=ci-token",
        )

        legacy = "http://shop.test/admin-kuranea/index.php?controller=AdminCarriers&token=ci-token"
        self.assertEqual(
            route_helper.carrier_action_url(legacy, "create"),
            "http://shop.test/admin-kuranea/index.php?controller=AdminCarriers&token=ci-token&addcarrier=1",
        )
        self.assertEqual(
            route_helper.carrier_action_url(legacy, "edit", 42),
            "http://shop.test/admin-kuranea/index.php?controller=AdminCarriers&token=ci-token&id_carrier=42&updatecarrier=1",
        )

    def test_authenticated_shipping_pages_require_a_korean_document_language(self) -> None:
        self.assertTrue(ROUTES.is_file(), "shipping admin locale validation must be dependency-free")
        spec = spec_from_file_location("shipping_admin_routes_locale", ROUTES)
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        route_helper = module_from_spec(spec)
        spec.loader.exec_module(route_helper)

        for language in ("ko", "ko-KR", "KO-kr"):
            with self.subTest(language=language):
                self.assertTrue(route_helper.is_korean_admin_language(language))
        for language in ("", "en-US", "ja-JP", "ko-KP"):
            with self.subTest(language=language):
                self.assertFalse(route_helper.is_korean_admin_language(language))

        browser = BROWSER.read_text(encoding="utf-8")
        self.assertIn('documentLanguage: page.documentElement?.getAttribute("lang") || ""', browser)
        self.assertIn("is_korean_admin_language(document_language)", browser)
        self.assertIn("did not use Korean interface locale", browser)

    def test_browser_failure_reports_exact_stage_and_safe_detail_to_github(self) -> None:
        browser = BROWSER.read_text(encoding="utf-8")
        self.assertIn('stage = "resolve_admin_carriers"', browser)
        self.assertIn('stage = "resolve_admin_shipping"', browser)
        self.assertIn("::error title=ORDENOWA shipping admin browser QA::", browser)
        self.assertIn("safe_failure_detail(error)", browser)
        self.assertIn('return "timed out waiting for the expected browser state"', browser)
        self.assertIn('f"{controller} native admin page did not return HTTP 200 in the admin session"', browser)
        self.assertNotIn("{error}", browser)
        self.assertIn("ORDENOWA_SHIPPING_ADMIN_DETAIL=", browser)

        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("detail_line=$(rg '^ORDENOWA_SHIPPING_ADMIN_DETAIL='", workflow)


if __name__ == "__main__":
    unittest.main()
