"""Guard explicit exemption handling in disposable free-shipping checkout QA."""
from __future__ import annotations

import unittest
import inspect
from pathlib import Path

from tests.e2e import checkout_total_math


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "fresh-install.yml"
BROWSER = ROOT / "tests" / "e2e" / "verify_ci_free_shipping_browser.py"
CHECKOUT_HELPER = ROOT / "tests" / "e2e" / "verify_ci_checkout_admin_browser.py"
ORDER_VERIFY = ROOT / "tests" / "postcode" / "verify_ci_free_shipping_exemption_order.php"
FIXTURE = ROOT / "tests" / "catalog" / "prepare_ci_free_shipping_exemption_product.php"


class FreeShippingExplicitExemptionContractTests(unittest.TestCase):
    def test_explicit_zero_rate_checkout_is_known_only_for_a_positive_matching_group(self) -> None:
        self.assertTrue(hasattr(checkout_total_math, "reconcile_explicit_zero_rate_checkout"))
        totals = checkout_total_math.reconcile_explicit_zero_rate_checkout(
            products_tax_incl=1000,
            shipping_tax_incl=0,
            discounts_tax_incl=0,
            total_tax_incl=1000,
            explicit_tax_rules_group_id=12,
            resolved_tax_rate_percent=0,
            tax_amounts=[0],
        )

        self.assertEqual(totals["tax"], 0)
        self.assertEqual(totals["products_tax_excl"], 1000)
        self.assertEqual(totals["total_tax_excl"], 1000)
        self.assertEqual(totals["tax_display_mode"], "explicit_zero_rate_rule")

    def test_explicit_zero_rate_checkout_rejects_unknown_or_positive_tax_configuration(self) -> None:
        self.assertTrue(hasattr(checkout_total_math, "reconcile_explicit_zero_rate_checkout"))
        for group_id, rate in ((0, 0), (12, 10)):
            with self.subTest(group_id=group_id, rate=rate):
                with self.assertRaises(AssertionError):
                    checkout_total_math.reconcile_explicit_zero_rate_checkout(
                        products_tax_incl=1000,
                        shipping_tax_incl=0,
                        discounts_tax_incl=0,
                        total_tax_incl=1000,
                        explicit_tax_rules_group_id=group_id,
                        resolved_tax_rate_percent=rate,
                        tax_amounts=[],
                    )

    def test_explicit_zero_rate_checkout_rejects_positive_tax_shipping_and_platform_fees(self) -> None:
        self.assertTrue(hasattr(checkout_total_math, "reconcile_explicit_zero_rate_checkout"))
        common = {
            "products_tax_incl": 1000,
            "shipping_tax_incl": 0,
            "discounts_tax_incl": 0,
            "explicit_tax_rules_group_id": 12,
            "resolved_tax_rate_percent": 0,
        }
        with self.assertRaisesRegex(AssertionError, "positive tax"):
            checkout_total_math.reconcile_explicit_zero_rate_checkout(
                **common, total_tax_incl=1000, tax_amounts=[1]
            )
        with self.assertRaisesRegex(AssertionError, "shipping"):
            checkout_total_math.reconcile_explicit_zero_rate_checkout(
                **{**common, "shipping_tax_incl": 100}, total_tax_incl=1100, tax_amounts=[]
            )
        with self.assertRaisesRegex(AssertionError, "platform fee"):
            checkout_total_math.reconcile_explicit_zero_rate_checkout(
                **common, total_tax_incl=1001, tax_amounts=[]
            )

    def test_confirmation_marks_zero_tax_only_when_explicit_fixture_group_is_supplied(self) -> None:
        self.assertIn(
            "explicit_zero_rate_tax_rules_group_id",
            inspect.signature(checkout_total_math.reconcile_order_confirmation_total_rows).parameters,
        )
        totals = checkout_total_math.reconcile_order_confirmation_total_rows(
            total_rows=[("合計", 1000)],
            tax_amounts=[],
            explicit_zero_rate_tax_rules_group_id=12,
        )

        self.assertEqual(totals["tax"], 0)
        self.assertEqual(totals["total_tax_excl"], 1000)
        self.assertEqual(totals["tax_display_mode"], "explicit_zero_rate_rule")

        with self.assertRaises(AssertionError):
            checkout_total_math.reconcile_order_confirmation_total_rows(
                total_rows=[("合計", 1000)],
                tax_amounts=[1],
                explicit_zero_rate_tax_rules_group_id=12,
            )

    def test_fixture_and_order_verifier_require_a_positive_explicit_japan_zero_rate_rule(self) -> None:
        self.assertTrue(FIXTURE.is_file(), "isolated explicit exemption fixture is missing")
        self.assertTrue(ORDER_VERIFY.is_file(), "isolated explicit exemption native verifier is missing")
        fixture = FIXTURE.read_text(encoding="utf-8")
        verifier = ORDER_VERIFY.read_text(encoding="utf-8")
        for source in (fixture, verifier):
            for marker in (
                "[CI ONLY] explicit exemption test",
                "not a legal",
                "id_country",
                "id_state",
            ):
                with self.subTest(source=source[:30], marker=marker):
                    self.assertTrue(marker in source, f"missing {marker}")
        self.assertIn("$tax->rate = 0.0", fixture)
        tax_name = "[CI ONLY] explicit 0% QA"
        self.assertLessEqual(len(tax_name), 32)
        self.assertIn("$taxName = '[CI ONLY] explicit 0% QA'", fixture)
        self.assertIn("strlen($taxName) > 32", fixture)
        self.assertIn("CI_TEST_EXEMPT_TAX_RULES_GROUP_ID", fixture + WORKFLOW.read_text(encoding="utf-8"))
        self.assertIn("abs((float) $ruleRows[0]['rate']) > 0.000001", verifier)
        self.assertIn("KURANEA_CI_TAX_RULES_GROUP_ID", verifier)
        for marker in (
            "id_tax_rules_group",
            "unit_amount",
            "total_amount",
            "positive native tax",
            "total_paid_tax_incl",
            "total_paid_tax_excl",
            "total_shipping_tax_incl",
            "ps_checkpayment",
        ):
            with self.subTest(marker=marker):
                self.assertTrue(marker in verifier, f"missing {marker}")

    def test_native_exemption_verifier_reconstructs_the_bounded_browser_test_email(self) -> None:
        checkout_helper = CHECKOUT_HELPER.read_text(encoding="utf-8")
        verifier = ORDER_VERIFY.read_text(encoding="utf-8")

        self.assertIn("def checkout_registration_email", checkout_helper)
        self.assertIn("email = checkout_registration_email(label, RUN_ID, RUN_ATTEMPT)", checkout_helper)
        for marker in (
            "$emailRunId = substr($runId, -20)",
            "$emailRunAttempt = substr($runAttempt, -4)",
            "$emailLabel = 'shipping-free-explicit-exemption'",
            "preg_replace('/[^a-z0-9]+/', '-', strtolower($emailLabel))",
            "strlen($emailLocalPart) > 64",
            "substr(hash('sha256', $emailLabel), 0, 8)",
            "$expectedEmail = strtolower($emailLocalPart . '@example.invalid')",
            "$email !== $expectedEmail",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, verifier)
        self.assertNotIn(
            "sprintf('qa-ordenowa-checkout-%s-%s-shipping-free-explicit-exemption'",
            verifier,
        )

    def test_browser_and_admin_reconcile_the_explicit_exemption_order(self) -> None:
        browser = BROWSER.read_text(encoding="utf-8")
        for marker in (
            "def run_japan_explicit_exemption_customer_checkout",
            '"explicit-exemption-customer"',
            "shipping-free-exemption-order.json",
            "explicit_zero_rate_rule",
            "tax_status",
            "not a legal tax rate or tax determination",
            '("exemption", QA_DIR / "shipping-free-exemption-order.json")',
        ):
            with self.subTest(marker=marker):
                self.assertTrue(marker in browser, f"missing {marker}")

    def test_ci_fixture_browser_persistence_and_admin_steps_are_fail_closed_and_artifacted(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for marker in (
            "Prepare isolated explicit exemption product fixture",
            "CI_TEST_EXEMPT_TAX_RULES_GROUP_ID",
            "CI_TEST_EXEMPT_PRODUCT_ID",
            "Verify explicit exemption free-shipping checkout with Chromium",
            "Verify free-shipping orders and totals in the isolated database",
            "shipping-free-exemption-verified.json",
            "steps.shipping_free_exemption_browser_qa.outcome == 'success'",
            "shipping-free-exemption-checkout-desktop.png",
            "shipping-free-exemption-order-confirmation-desktop.png",
            "shipping-free-order-admin-exemption-desktop.png",
            "test_free_shipping_exemption_contract",
        ):
            with self.subTest(marker=marker):
                self.assertTrue(marker in workflow, f"missing {marker}")
        self.assertEqual(workflow.count("tests/smoke/test_free_shipping_exemption_contract.py"), 2)
        self.assertLess(
            workflow.index("tests.smoke.test_free_shipping_exemption_contract"),
            workflow.index("- name: Build the PrestaShop image"),
        )


if __name__ == "__main__":
    unittest.main()
