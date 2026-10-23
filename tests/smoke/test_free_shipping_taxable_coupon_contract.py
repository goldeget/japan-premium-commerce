"""Protect taxable coupon reconciliation in isolated checkout QA."""
from __future__ import annotations

import unittest
from pathlib import Path

from tests.e2e.checkout_total_math import (
    labeled_tax_total_amounts,
    reconcile_cart_totals,
    reconcile_inclusive_and_exclusive_totals,
    reconcile_no_assigned_tax_rule_display,
    reconcile_order_confirmation_total_rows,
    reconcile_tax_included_display,
)

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

    def test_tax_inclusive_ui_keeps_undisplayed_tax_unknown(self) -> None:
        totals = reconcile_tax_included_display(
            products_tax_incl=1100,
            shipping_tax_incl=0,
            discounts_tax_incl=550,
            total_tax_incl=550,
            total_label="合計（税込）",
        )

        self.assertEqual(totals["products_tax_incl"], 1100)
        self.assertEqual(totals["shipping_tax_incl"], 0)
        self.assertEqual(totals["discounts_tax_incl"], 550)
        self.assertEqual(totals["total_tax_incl"], 550)
        self.assertIsNone(totals["tax"])
        self.assertIsNone(totals["total_tax_excl"])
        self.assertFalse(totals["tax_breakdown_displayed"])
        self.assertEqual(totals["tax_display_mode"], "inclusive_total_only")

    def test_tax_inclusive_ui_rejects_a_missing_inclusive_label_or_platform_fee(self) -> None:
        with self.assertRaisesRegex(AssertionError, "label its final total as tax-inclusive"):
            reconcile_tax_included_display(
                products_tax_incl=1100,
                shipping_tax_incl=0,
                discounts_tax_incl=0,
                total_tax_incl=1100,
                total_label="合計",
            )
        with self.assertRaisesRegex(AssertionError, "possible platform fee"):
            reconcile_tax_included_display(
                products_tax_incl=1100,
                shipping_tax_incl=0,
                discounts_tax_incl=550,
                total_tax_incl=551,
                total_label="合計（税込）",
            )

    def test_labeled_inclusive_and_exclusive_totals_establish_tax_without_tax_row(self) -> None:
        totals = reconcile_inclusive_and_exclusive_totals(
            products_tax_incl=1100,
            shipping_tax_incl=0,
            discounts_tax_incl=550,
            total_tax_incl=550,
            total_tax_excl=500,
            pre_discount_tax=100,
        )

        self.assertEqual(totals["tax"], 50)
        self.assertEqual(totals["products_tax_excl"], 1000)
        self.assertEqual(totals["discounts_tax_excl"], 500)
        self.assertFalse(totals["tax_breakdown_displayed"])
        self.assertEqual(totals["tax_display_mode"], "tax_inclusive_and_exclusive_totals")

    def test_labeled_totals_cannot_turn_missing_tax_into_zero(self) -> None:
        with self.assertRaisesRegex(AssertionError, "positive tax amount"):
            reconcile_inclusive_and_exclusive_totals(
                products_tax_incl=1100,
                shipping_tax_incl=0,
                discounts_tax_incl=550,
                total_tax_incl=550,
                total_tax_excl=550,
                pre_discount_tax=100,
            )

    def test_confirmation_selects_gross_total_by_label_when_rows_are_reversed(self) -> None:
        total_rows = [("合計（税込）", 550), ("合計（税抜）", 500)]
        self.assertEqual(
            labeled_tax_total_amounts(total_rows),
            {"total_tax_incl": 550, "total_tax_excl": 500},
        )
        totals = reconcile_order_confirmation_total_rows(total_rows=total_rows, tax_amounts=[])

        self.assertEqual(totals["total_tax_incl"], 550)
        self.assertEqual(totals["total_tax_excl"], 500)
        self.assertEqual(totals["tax"], 50)
        self.assertFalse(totals["tax_breakdown_displayed"])
        self.assertEqual(totals["tax_display_mode"], "tax_inclusive_and_exclusive_totals")

    def test_confirmation_inclusive_only_keeps_missing_tax_unknown(self) -> None:
        totals = reconcile_order_confirmation_total_rows(
            total_rows=[("合計（税込）", 550)],
            tax_amounts=[],
        )

        self.assertEqual(totals["total_tax_incl"], 550)
        self.assertIsNone(totals["total_tax_excl"])
        self.assertIsNone(totals["tax"])
        self.assertEqual(totals["tax_display_mode"], "inclusive_total_only")

    def test_confirmation_without_inclusive_label_stays_unclassified_for_unassigned_rule(self) -> None:
        totals = reconcile_order_confirmation_total_rows(
            total_rows=[("合計", 1100)],
            tax_amounts=[],
            allow_unassigned_tax_rule=True,
        )

        self.assertEqual(totals["total_tax_incl"], 1100)
        self.assertIsNone(totals["tax"])
        self.assertEqual(totals["tax_display_mode"], "no_assigned_tax_rule")

    def test_unassigned_tax_rule_never_records_a_displayed_zero_tax_as_tax(self) -> None:
        totals = reconcile_order_confirmation_total_rows(
            total_rows=[("合計", 1100)],
            tax_amounts=[0],
            allow_unassigned_tax_rule=True,
        )

        self.assertIsNone(totals["tax"])
        self.assertTrue(totals["tax_breakdown_displayed"])
        self.assertEqual(totals["tax_display_mode"], "no_assigned_tax_rule")

        with self.assertRaisesRegex(AssertionError, "despite the fixture"):
            reconcile_order_confirmation_total_rows(
                total_rows=[("合計（税込）", 1100)],
                tax_amounts=[100],
                allow_unassigned_tax_rule=True,
            )

    def test_unassigned_tax_rule_does_not_claim_a_zero_tax_amount(self) -> None:
        totals = reconcile_no_assigned_tax_rule_display(
            products_tax_incl=1100,
            shipping_tax_incl=0,
            discounts_tax_incl=0,
            total_tax_incl=1100,
        )

        self.assertIsNone(totals["tax"])
        self.assertIsNone(totals["products_tax_excl"])
        self.assertIsNone(totals["total_tax_excl"])
        self.assertEqual(totals["tax_display_mode"], "no_assigned_tax_rule")

    def test_native_tax_rows_are_reconciled_after_the_order_discount(self) -> None:
        verifier = (ROOT / "tests/postcode/verify_ci_free_shipping_order.php").read_text(encoding="utf-8")
        self.assertIn("$discountedProductTaxBase", verifier)
        self.assertIn("$discountedProductTaxBase * $storedTaxRate / 100", verifier)
        self.assertIn("$storedTaxTotal - $nativeTaxes", verifier)
        for marker in (
            "unit_price_tax_excl",
            "unit_price_tax_incl",
            "'shipping-free' => [",
            "'shipping-free-mobile' => [",
            "'shipping-free-taxable' => [",
            "'native final tax-exclusive amount' =>",
            "'native final tax-inclusive amount' =>",
            "'native saved synthetic tax' => [$nativeTaxes, $scenarioExpected['tax']]",
            "'saved synthetic order-detail tax' => [$storedTaxTotal, $scenarioExpected['tax']]",
            "inclusive_total_only",
            "not a legal tax rate or tax determination",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, verifier)

    def test_taxable_browser_order_uses_second_run_scoped_coupon_customer(self) -> None:
        browser = (ROOT / "tests/e2e/verify_ci_free_shipping_browser.py").read_text(encoding="utf-8")
        taxable_flow = browser.split("def run_japan_taxable_customer_checkout", 1)[1].split(
            "def _parse_order_amount", 1
        )[0]
        self.assertLess(
            taxable_flow.index("pre_coupon_totals = _select_free_carrier_and_assert_zero("),
            taxable_flow.index("coupon = _apply_coupon_if_configured(driver)"),
        )
        self.assertIn("pre_discount_tax_total=100", taxable_flow)
        self.assertGreaterEqual(taxable_flow.count("pre_discount_tax_total=100"), 2)
        self.assertIn("discount_tax_incl=550", taxable_flow)
        self.assertIn("discount_tax_excl=500", taxable_flow)
        self.assertIn("tax=50", taxable_flow)
        self.assertIn('if history_total != 550', taxable_flow)
        self.assertIn('"pre_coupon_browser_totals": pre_coupon_totals', taxable_flow)
        self.assertIn("_assert_taxable_visible_totals(", taxable_flow)
        self.assertIn("native saved-order check verifies the actual", browser.lower())

        self.assertIn("tax_inclusive_and_exclusive_totals", browser)
        self.assertIn("labeled_tax_total_amounts(total_rows)", browser)
        self.assertIn("reconcile_order_confirmation_total_rows(", browser)

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
