from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADMIN_FLOW = ROOT / "tests" / "e2e" / "verify_ci_checkout_admin_browser.py"
LIFECYCLE_VERIFIER = ROOT / "tests" / "postcode" / "verify_ci_native_order_lifecycle.php"
BROWSER_ORDER_VERIFIER = ROOT / "tests" / "postcode" / "verify_ci_browser_checkout_order.php"
WORKFLOW = ROOT / ".github" / "workflows" / "fresh-install.yml"


class CiAdminOrderStatusContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ADMIN_FLOW.is_file():
            raise AssertionError("the CI admin checkout browser flow is missing")
        if not LIFECYCLE_VERIFIER.is_file():
            raise AssertionError("the CI native order lifecycle verifier is missing")
        if not BROWSER_ORDER_VERIFIER.is_file():
            raise AssertionError("the CI browser order verifier is missing")
        if not WORKFLOW.is_file():
            raise AssertionError("the isolated fresh-install workflow is missing")
        cls.admin_source = ADMIN_FLOW.read_text(encoding="utf-8")
        cls.lifecycle_source = LIFECYCLE_VERIFIER.read_text(encoding="utf-8")
        cls.browser_order_source = BROWSER_ORDER_VERIFIER.read_text(encoding="utf-8")
        cls.workflow_source = WORKFLOW.read_text(encoding="utf-8")

    def assertContains(self, source: str, required: str) -> None:
        if required not in source:
            self.fail(f"missing required contract: {required}")

    def assertDoesNotContain(self, source: str, forbidden: str) -> None:
        if forbidden in source:
            self.fail(f"unexpected mutating cancellation API remains: {forbidden}")

    def test_admin_flow_cancels_only_the_verified_unpaid_desktop_order(self) -> None:
        self.assertContains(self.admin_source, "def cancel_unpaid_desktop_order_through_admin(")
        helper = self.admin_source.split(
            "def cancel_unpaid_desktop_order_through_admin(", 1
        )[1].split("\ndef ", 1)[0]
        for required in (
            'order.get("viewport") != "desktop"',
            'int(order.get("order_id", 0)) < 1',
            'expected_email = checkout_registration_email("desktop", RUN_ID, RUN_ATTEMPT)',
            'order.get("email") != expected_email',
            'verified_order.get("payment_module") != "ps_checkpayment"',
            'float(verified_order.get("total_paid_real", -1)) != 0.0',
            'cancelled_state_id = str(int(verified_order["cancelled_state_id"]))',
            'select[name="update_order_status[new_order_status_id]"]',
            'select2-selection',
            'option.get_attribute("value") == cancelled_state_id',
            'button.update-status',
            'table[data-role="history-grid-table"] tbody tr:first-child ',
            'td[data-role="status-column"] span',
        ):
            with self.subTest(required=required):
                self.assertContains(helper, required)

        admin_flow = self.admin_source.split("def run_admin_order_view()", 1)[1]
        self.assertContains(admin_flow, 'if order["viewport"] == "desktop":')
        self.assertContains(admin_flow, "cancel_unpaid_desktop_order_through_admin(")
        self.assertContains(admin_flow, 'verified_orders["desktop"]')
        self.assertContains(admin_flow, 'checkout-admin-order-desktop-canceled.png')

    def test_order_verification_exposes_the_native_cancelled_state_id(self) -> None:
        for required in (
            "Configuration::get('PS_OS_CANCELED')",
            "'cancelled_state_id' => $cancelledStateId",
        ):
            with self.subTest(required=required):
                self.assertContains(self.browser_order_source, required)

    def test_lifecycle_verifier_checks_ui_cancellation_without_mutating_status(self) -> None:
        for required in (
            "SELECT `id_order_state`, `id_employee` FROM `",
            "ORDER BY `date_add` DESC, `id_order_history` DESC LIMIT 2",
            "$unpaidHistory[0]['id_order_state']",
            "$unpaidHistory[1]['id_order_state']",
            "$cancelledOrder->current_state",
            "$cancelledOrder->total_paid_real",
        ):
            with self.subTest(required=required):
                self.assertContains(self.lifecycle_source, required)

        for forbidden in (
            "new OrderHistory()",
            "changeIdOrderState(",
            "->addWithemail(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertDoesNotContain(self.lifecycle_source, forbidden)

    def test_admin_cancel_screenshot_is_required_in_successful_checkout_artifacts(self) -> None:
        admin_artifacts = self.workflow_source.split(
            'if [[ "$CHECKOUT_ADMIN_BROWSER_QA_OUTCOME" == success ]]; then', 1
        )[1].split("fi", 1)[0]
        self.assertContains(admin_artifacts, "checkout-admin-order-desktop-canceled.png")
        self.assertContains(self.workflow_source, "tests.e2e.test_ci_admin_order_status_contract")


if __name__ == "__main__":
    unittest.main()
