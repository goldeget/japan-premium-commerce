"""Ensure the CI browser proves tax-inclusive sale-price and free-shipping reconciliation."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "fresh-install.yml"
BROWSER = ROOT / "tests" / "e2e" / "verify_ci_free_shipping_browser.py"
ORDER_VERIFY = ROOT / "tests" / "postcode" / "verify_ci_free_shipping_order.php"


class TaxableCheckoutBrowserContractTests(unittest.TestCase):
    def test_browser_and_admin_reconcile_the_visible_tax_included_price(self) -> None:
        browser = BROWSER.read_text(encoding="utf-8")
        for marker in (
            "def run_japan_taxable_customer_checkout",
            '"taxable-customer"',
            "tax_fixture_scope",
            "synthetic 10% test rule",
            "not a legal tax rate or tax determination",
            "displayed_unit_price",
            "1100",
            "1000",
            "shipping-free-taxable-order.json",
            "def run_free_carrier_admin_order_view",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, browser)

        self.assertIn("tax", browser)
        self.assertIn("total_tax_incl", browser)
        self.assertIn("order_history_total", browser)
        self.assertIn("carrier_price != 0", browser)
        self.assertIn("ps_checkpayment", browser)

        verifier = ORDER_VERIFY.read_text(encoding="utf-8")
        for marker in ("$order->total_paid_tax_excl", "$order->total_paid_tax_incl", "shipping_cost_tax_incl"):
            self.assertIn(marker, verifier)

    def test_workflow_creates_tax_fixture_before_admin_and_taxable_browser_qa(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        steps = (
            "Create isolated synthetic tax product and reconcile native unpaid order",
            "Prepare isolated taxable variant fixture",
            "Verify Korean admin native product create and edit in Chromium",
            "Verify tax-included taxable Japan checkout with the free carrier",
            "Verify free-shipping orders and totals in the isolated database",
            "Verify free-shipping orders in a separate admin browser session",
        )
        positions = [workflow.index(f"- name: {step}") for step in steps]
        self.assertEqual(positions, sorted(positions))

        for marker in (
            "CI_TEST_TAX_RULES_GROUP_ID",
            "CI_TEST_TAX_PRODUCT_ID",
            "CI_TEST_VARIANT_PRODUCT_ID",
            "verify_product_tax_price.php",
            "setup_ci_variant_product.php",
            "verify_cart_controls_browser.py",
            "CI_TEST_PRODUCT_ID=$CI_TEST_VARIANT_PRODUCT_ID",
            "CI_TEST_PRODUCT_ID=$CI_TEST_TAX_PRODUCT_ID",
            "verify_ci_free_shipping_browser.py taxable-customer",
            "shipping-free-taxable-order.json",
            "test_taxable_checkout_browser_contract",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, workflow)


if __name__ == "__main__":
    unittest.main()
