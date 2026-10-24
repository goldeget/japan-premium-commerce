"""Guard cache policy coverage for PrestaShop customer-data controllers."""
from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneabusinessprofile" / "kuraneabusinessprofile.php"
PWA_BROWSER = ROOT / "tests" / "e2e" / "verify_pwa_browser.py"
REQUIRED_PRIVATE_ROUTES = {
    "address",
    "addresses",
    "authentication",
    "cart",
    "discount",
    "getfile",
    "guest-tracking",
    "history",
    "identity",
    "my-account",
    "order",
    "order-confirmation",
    "order-detail",
    "order-follow",
    "order-opc",
    "order-return",
    "order-slip",
    "password",
    "pdf-invoice",
    "pdf-order-return",
    "pdf-order-slip",
    "registration",
}


def method_source(source: str, method_name: str) -> str:
    start = source.index(f"function {method_name}")
    next_method = source.find("\n    public function ", start + 1)
    return source[start: next_method if next_method >= 0 else len(source)]


class PrivateCustomerCacheRouteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.hook = method_source(
            MODULE.read_text(encoding="utf-8"),
            "hookActionFrontControllerInitBefore",
        )
        cls.pwa = PWA_BROWSER.read_text(encoding="utf-8")

    def test_customer_data_controllers_receive_private_no_store_headers_early(self) -> None:
        route_match = re.search(
            r"if \(in_array\(\$controllerName, \[(.*?)\], true\)\)",
            self.hook,
            re.DOTALL,
        )
        self.assertIsNotNone(route_match, "early private response route list must remain explicit")
        routes = set(re.findall(r"'([a-z][a-z-]*)'", route_match.group(1)))
        self.assertTrue(
            REQUIRED_PRIVATE_ROUTES.issubset(routes),
            f"missing private customer-data route(s): {sorted(REQUIRED_PRIVATE_ROUTES - routes)}",
        )
        self.assertLess(
            self.hook.index("header('Cache-Control: private, no-store, max-age=0'"),
            self.hook.index("CommerceGate::isEnabled"),
            "cache policy must be applied before order authorization redirects",
        )

    def test_getfile_uses_only_the_verified_core_controller_type_fallback(self) -> None:
        self.assertIn("$controller->php_self ?? ''", self.hook)
        self.assertRegex(
            self.hook,
            re.compile(
                r"if \(\s*\$controllerName === ''\s*"
                r"&& is_object\(\$controller\)\s*"
                r"&& is_a\(\$controller, 'GetFileControllerCore'\)\s*\)\s*\{"
                r"\s*\$controllerName = 'getfile';",
                re.DOTALL,
            ),
            (
                "GetFileControllerCore has no php_self; only its verified runtime type "
                "may map it to getfile"
            ),
        )

    def test_logout_action_gets_private_no_store_headers_without_marking_the_homepage_private(self) -> None:
        self.assertRegex(
            self.hook,
            re.compile(
                r"\$isLogoutAction\s*=\s*\$controllerName\s*===\s*'index'\s*"
                r"&&\s*array_key_exists\('mylogout',\s*\$_GET\);",
                re.DOTALL,
            ),
        )
        self.assertIn("if (in_array($controllerName, [", self.hook)
        self.assertIn("|| $isLogoutAction)", self.hook)
        private_route_list = re.search(
            r"if \(in_array\(\$controllerName, \[(.*?)\], true\)\)",
            self.hook,
            re.DOTALL,
        )
        self.assertIsNotNone(private_route_list)
        routes = set(re.findall(r"'([a-z][a-z-]*)'", private_route_list.group(1)))
        self.assertNotIn("index", routes, "the public homepage must not inherit customer cache headers")

    def test_isolated_pwa_checks_logged_out_customer_routes_without_logging_urls(self) -> None:
        self.assertIn("def verify_logged_out_private_routes(", self.pwa)
        start = self.pwa.index("def verify_logged_out_private_routes(")
        end = self.pwa.find("\ndef ", start + 1)
        route_check = self.pwa[start: end if end >= 0 else len(self.pwa)]
        for controller in ("addresses", "history", "order-detail", "guest-tracking"):
            with self.subTest(controller=controller):
                self.assertIn(f'"{controller}"', route_check)
        self.assertIn("expected_status", route_check)
        self.assertIn("navigate_private_document(", route_check)
        for route_case in (
            '("addresses", "addresses", 302)',
            '("history", "history", 302)',
            '("order_detail", "order-detail", 302)',
            '("guest_tracking", "guest-tracking", None)',
        ):
            with self.subTest(route_case=route_case):
                self.assertIn(route_case, route_check)
        self.assertIn('observed.get("status") != 200', route_check)
        self.assertIn('wait_visible(driver, "#guestOrderTrackingForm")', route_check)
        navigate_start = self.pwa.index("def navigate_private_document(")
        navigate_end = self.pwa.find("\ndef ", navigate_start + 1)
        navigate = self.pwa[navigate_start:navigate_end]
        self.assertIn("assert_private_document_cache_headers", navigate)
        self.assertNotIn("current_url", route_check)
        self.assertNotIn("print(", route_check)
        self.assertIn('"logged-out account"', self.pwa)
        self.assertIn('account_response.get("status") != 302', self.pwa)


if __name__ == "__main__":
    unittest.main()
