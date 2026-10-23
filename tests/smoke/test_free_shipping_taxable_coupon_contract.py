"""Protect taxable coupon reconciliation in isolated checkout QA."""
from __future__ import annotations

import unittest
from pathlib import Path

from tests.e2e.checkout_total_math import reconcile_cart_totals

ROOT = Path(__file__).resolve().parents[2]


class TaxableCouponCheckoutContractTest(unittest.TestCase):
    def test_tax_inclusive_coupon_preserves_pre_and_post_discount_tax_breakdown(self) -> None:
        # Hand-derived from the CI-only synthetic fixture: ¥1,100 TTC is
        # ¥1,000 net + ¥100 test tax; a 50% TTC discount leaves ¥550 TTC,
        # consisting of ¥500 net + ¥50 test tax.
        totals = reconcile_cart_totals(
            products_tax_incl=1100,
            shipping_tax_incl=0,
            discounts_tax_incl=550,
            tax=50,
            total_tax_incl=550,
            total_tax_excl=500,
            pre_discount_tax=100,
        )

        self.assertEqual(
            totals,
            {
                "products_tax_incl": 1100,
                "products_tax_excl": 1000,
                "shipping_tax_incl": 0,
                "shipping_tax_excl": 0,
                "discounts_tax_incl": 550,
                "discounts_tax_excl": 500,
                "tax": 50,
                "total_tax_incl": 550,
                "total_tax_excl": 500,
            },
        )

    def test_tax_inclusive_coupon_rejects_a_false_zero_tax_total(self) -> None:
        with self.assertRaisesRegex(AssertionError, "tax-inclusive total"):
            reconcile_cart_totals(
                products_tax_incl=1100,
                shipping_tax_incl=0,
                discounts_tax_incl=550,
                tax=0,
                total_tax_incl=550,
                total_tax_excl=500,
                pre_discount_tax=100,
            )

    def test_native_tax_rows_are_reconciled_after_the_order_discount(self) -> None:
        verifier = (ROOT / "tests/postcode/verify_ci_free_shipping_order.php").read_text(encoding="utf-8")
        self.assertIn("$discountedProductTaxBase", verifier)
        self.assertIn("$discountedProductTaxBase * $storedTaxRate / 100", verifier)
        self.assertIn("$storedTaxTotal - $nativeTaxes", verifier)

    def test_taxable_browser_order_uses_second_run_scoped_coupon_customer(self) -> None:
        browser = (ROOT / "tests/e2e/verify_ci_free_shipping_browser.py").read_text(encoding="utf-8")
        taxable_flow = browser.split("def run_japan_taxable_customer_checkout", 1)[1].split(
            "def _parse_order_amount", 1
        )[0]
        self.assertLess(
            taxable_flow.index("pre_coupon_totals = _select_free_carrier_and_assert_zero("),
            taxable_flow.index("coupon = _apply_coupon_if_configured(driver)"),
        )
        self.assertIn('pre_discount_tax_total=pre_coupon_totals["tax"]', taxable_flow)
        self.assertIn('"discounts_tax_incl": 550', taxable_flow)
        self.assertIn('"discounts_tax_excl": 500', taxable_flow)
        self.assertIn('"tax": 50', taxable_flow)
        self.assertIn('if history_total != 550', taxable_flow)

        fixture = (ROOT / "tests/postcode/seed_ci_shipping_coupon.php").read_text(encoding="utf-8")
        self.assertIn("$rule->quantity = 2", fixture)
        self.assertIn("$rule->quantity_per_user = 1", fixture)
        self.assertIn("$rule->reduction_tax = 1", fixture)
        self.assertIn("$rule->free_shipping = 0", fixture)
        self.assertIn("$rule->product_restriction = 0", fixture)

    def test_contract_runs_in_ci_before_docker_build_for_work_and_pull_request_changes(self) -> None:
        workflow = (ROOT / ".github/workflows/fresh-install.yml").read_text(encoding="utf-8")
        self.assertGreaterEqual(workflow.count("tests/smoke/test_free_shipping_taxable_coupon_contract.py"), 2)
        contract_step = workflow.split("- name: Verify fresh-install workflow contracts", 1)[1].split(
            "- name:", 1
        )[0]
        self.assertIn("tests.smoke.test_free_shipping_taxable_coupon_contract", contract_step)
        self.assertLess(
            workflow.index("tests.smoke.test_free_shipping_taxable_coupon_contract"),
            workflow.index("- name: Build the PrestaShop image"),
        )

if __name__ == "__main__":
    unittest.main()
