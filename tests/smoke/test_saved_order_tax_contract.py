"""Guard saved native tax evidence and deterministic taxable-fixture shipping."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class SavedOrderTaxContractTests(unittest.TestCase):
    def test_browser_order_verifier_compares_the_saved_detail_tax_group(self) -> None:
        source = (ROOT / "tests/postcode/verify_ci_free_shipping_order.php").read_text()
        query = source.split("$orderDetails =", 1)[1].split("$productTaxGroupId =", 1)[0]
        self.assertIn("`id_order_detail`", query)
        self.assertIn("`id_tax_rules_group`", query)
        self.assertIn("(int) $orderDetails[0]['id_tax_rules_group'] !== $browserProductTaxGroupId", source)

    def test_positive_tax_uses_persisted_tax_rows_identity_rate_and_amounts(self) -> None:
        source = (ROOT / "tests/postcode/verify_ci_free_shipping_order.php").read_text()
        for marker in (
            "order_detail_tax", "odt.`id_tax`", "odt.`unit_amount`", "odt.`total_amount`",
            "t.`rate`", "tr.`id_tax_rules_group`", "$savedDetailTaxGroupId > 0",
            "$storedTaxTotal - $nativeTaxes", "$discountedProductTaxBase",
            "$discountedProductTaxBase * $storedTaxRate / 100",
            "$storedTaxUnit * $expectedQuantity", "$storedTaxRate - 10.0",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_unassigned_group_does_not_report_a_legal_zero_tax_rate(self) -> None:
        source = (ROOT / "tests/postcode/verify_ci_free_shipping_order.php").read_text()
        self.assertIn("No assigned calculation rule; not a legal tax determination", source)
        self.assertIn('"tax_display_mode": "no_assigned_tax_rule"', (ROOT / "tests/e2e/checkout_total_math.py").read_text())
        self.assertIn("must not report a legal zero tax or net amount", source)
        self.assertIn("$browserTotals['tax'] !== null", source)
        self.assertIn("'saved_order_detail_tax_group_id' => $savedDetailTaxGroupId", source)
        self.assertIn("'saved_order_detail_taxes' => $storedTaxRows", source)

    def test_saved_order_rejects_shipping_and_wrapping_fees(self) -> None:
        source = (ROOT / "tests/postcode/verify_ci_free_shipping_order.php").read_text()
        self.assertIn("abs($wrappingTaxExcl) > 0.0001", source)
        self.assertIn("abs($wrappingTaxIncl) > 0.0001", source)
        self.assertIn("'total_wrapping_tax_excl' => $wrappingTaxExcl", source)
        self.assertIn("'total_wrapping_tax_incl' => $wrappingTaxIncl", source)

    def test_native_verifier_stdout_remains_parseable_json(self) -> None:
        source = (ROOT / "tests/postcode/verify_ci_free_shipping_order.php").read_text()
        self.assertNotIn("fwrite(STDOUT, sprintf(", source)
        self.assertIn("fwrite(STDERR, sprintf(", source)

    def test_tax_fixture_selects_its_own_carrier_and_rejects_missing_option(self) -> None:
        source = (ROOT / "tests/catalog/verify_product_tax_price.php").read_text()
        selection = source.split("$deliveryOptions =", 1)[1].split("if (!$cart->update()", 1)[0]
        self.assertNotIn("array_key_first", selection)
        self.assertIn("$option['carrier_list']", selection)
        self.assertIn("(int) $carrier->id", selection)
        self.assertIn("$ciCarrierOptionKey === null", selection)
        self.assertIn("$cart->setDeliveryOption([(int) $address->id => $ciCarrierOptionKey])", selection)


if __name__ == "__main__":
    unittest.main()
