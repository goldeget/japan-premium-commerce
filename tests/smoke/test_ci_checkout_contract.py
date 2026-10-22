"""Keep the unpaid customer order exercise inside isolated GitHub Actions."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "fresh-install.yml"
COMPOSE = ROOT / "compose.yaml"
CHECKOUT_FLOW = ROOT / "tests" / "e2e" / "verify_ci_checkout_admin_browser.py"
STOREFRONT_FLOW = ROOT / "tests" / "e2e" / "verify_storefront_browser.py"
GATE = ROOT / "modules" / "kuraneabusinessprofile" / "src" / "Customer" / "CommerceGate.php"
SHOP_MODULE = ROOT / "modules" / "kuraneabusinessprofile" / "kuraneabusinessprofile.php"


class IsolatedCheckoutContractTests(unittest.TestCase):
    def test_checkout_bypass_is_limited_to_the_matching_disposable_github_project(self) -> None:
        gate = GATE.read_text(encoding="utf-8")
        module = SHOP_MODULE.read_text(encoding="utf-8")
        self.assertIn("function isIsolatedCiCheckoutEnabled()", gate)
        for condition in (
            "getenv('CI') === 'true'",
            "getenv('GITHUB_ACTIONS') === 'true'",
            "getenv('KURANEA_ISOLATED_CI') === '1'",
            "getenv('GITHUB_RUN_ID')",
            "getenv('GITHUB_RUN_ATTEMPT')",
            "'kuranea-ci-' . $runId . '-' . $runAttempt",
        ):
            self.assertIn(condition, gate)
        hook = module.split("public function hookActionFrontControllerInitBefore", 1)[1].split("public function ", 1)[0]
        self.assertIn("CommerceGate::isIsolatedCiCheckoutEnabled()", hook)
        self.assertIn("CommerceGate::isEnabled($profile, $this->externalAuthorizationConfirmed())", hook)

    def test_workflow_passes_only_run_scoped_ci_checkout_environment(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        compose = COMPOSE.read_text(encoding="utf-8")
        overlay = (ROOT / "tests" / "fixtures" / "ci-checkout.compose.yaml").read_text(encoding="utf-8")
        self.assertIn('CI: "false"', compose)
        self.assertIn('GITHUB_ACTIONS: "false"', compose)
        self.assertIn('KURANEA_ISOLATED_CI: "0"', compose)
        self.assertIn('CI: "true"', overlay)
        self.assertIn('GITHUB_ACTIONS: "true"', overlay)
        self.assertIn("GITHUB_RUN_ID:", overlay)
        self.assertIn("GITHUB_RUN_ATTEMPT:", overlay)
        self.assertIn("KURANEA_CI_PROJECT_NAME:", overlay)
        self.assertIn("Enable run-scoped checkout only for the isolated order browser QA", workflow)
        self.assertIn("tests/e2e/verify_ci_checkout_admin_browser.py customer", workflow)
        self.assertIn("tests/e2e/verify_ci_checkout_admin_browser.py admin", workflow)
        self.assertIn("tests.business_profile.test_admin_tab_navigation_contract", workflow)
        self.assertIn("tests.business_profile.test_admin_access_source_contract", workflow)
        self.assertIn("tests/postcode/verify_ci_browser_checkout_order.php", workflow)
        self.assertIn("ci-checkout-admin-e2e.log", workflow)
        self.assertIn("verify_storefront_browser.py", workflow, "the production checkout gate smoke test must remain active")
        self.assertNotIn("ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED=1", workflow)
        self.assertLess(
            workflow.index("Verify real product detail and cart in Chromium"),
            workflow.index("Enable run-scoped checkout only for the isolated order browser QA"),
        )
        self.assertLess(
            workflow.index("Restore the fail-closed base checkout environment"),
            workflow.index("Recheck storefront checkout stays gated after unpaid CI order QA"),
        )
        self.assertLess(
            workflow.index("Verify ORDENOWA business profile installation and admin access"),
            workflow.index("Prepare Chromium browser smoke environment"),
        )

    def test_browser_flow_uses_unpaid_native_payment_and_separate_admin_session(self) -> None:
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        order_verifier = (ROOT / "tests" / "postcode" / "verify_ci_browser_checkout_order.php").read_text(encoding="utf-8")
        for required in (
            "ps_checkpayment",
            "payment-option",
            "100-0004",
            "kuraneapostcode_search",
            "confirm-addresses",
            "order-history__cell--reference",
            "total_paid_real",
            "ADMIN_LOGIN_URL",
            "checkout-admin-order-{order['viewport']}-detail.png",
            "checkout-{label}.png",
        ):
            self.assertIn(required, flow + order_verifier)
        self.assertGreaterEqual(flow.count("webdriver.Chrome("), 2)
        self.assertIn("def run_admin_order_view()", flow)
        self.assertIn("GITHUB_RUN_ID", flow)
        self.assertIn("@example.invalid", flow)
        self.assertIn("live payment", flow.lower())

    def test_public_checkout_gate_rejects_order_path_and_controller_query(self) -> None:
        flow = STOREFRONT_FLOW.read_text(encoding="utf-8")
        gate_check = flow.split('visit(driver, "/index.php?controller=order")', 1)[1].split(
            'driver.save_screenshot', 1
        )[0]
        self.assertIn(
            'not re.search(r"(order|checkout)", urlparse(driver.current_url).path.lower())',
            gate_check,
        )
        self.assertIn(
            'and "controller=order" not in urlparse(driver.current_url).query.lower()',
            gate_check,
        )
        self.assertNotIn(
            'or "controller=order" not in urlparse(driver.current_url).query.lower()',
            gate_check,
        )

    def test_checkout_registration_and_admin_routes_follow_rendered_prestashop_flow(self) -> None:
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        registration = flow.split("def register_checkout_account", 1)[1].split("def select_japan_address", 1)[0]
        admin_detail = flow.split("def find_admin_detail_url", 1)[1].split("def run_admin_order_view", 1)[0]
        self.assertIn("#checkout-continue-form button", registration)
        self.assertNotIn("identity_main_link", registration)
        self.assertIn('ADMIN_LOGIN + "/sell/orders/orders"', admin_detail)
        self.assertIn('ADMIN_LOGIN + f"/sell/orders/orders/{order[\'order_id\']}/view"', admin_detail)
        self.assertNotIn('root + "/sell/orders/orders"', admin_detail)


if __name__ == "__main__":
    unittest.main()
