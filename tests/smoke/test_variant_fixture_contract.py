"""Guard the disposable native option-product fixture consumed by cart QA."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class VariantFixtureContractTests(unittest.TestCase):
    def test_variant_fixture_is_run_scoped_guarded_and_separate_from_order_fixture(self) -> None:
        fixture = ROOT / "tests" / "catalog" / "setup_ci_variant_product.php"
        self.assertTrue(fixture.is_file(), "isolated native variant fixture setup is missing")
        source = fixture.read_text(encoding="utf-8")

        for expected in (
            "KURANEA_CI_RUN_ID",
            "KURANEA_CI_RUN_ATTEMPT",
            "KURANEA_CI_PROJECT_NAME",
            "KURANEA_ISOLATED_CI",
            "CI_TEST_TAX_RULES_GROUP_ID",
            "OWA-CI-VARIANT-",
            "[CI ONLY]",
            "PrestaShopNativeProductManager",
            "ProductAdminDraft::fromArray",
            "'options' =>",
            "'options' => 'Color:Blue|Red'",
            "'price_jpy' => '550'",
            "'tax_rules_group_id' => (string) $taxRulesGroupId",
            "'name' => 'Color', 'values' => ['Blue', 'Red']",
            "StockAvailable::getQuantityAvailableByProduct",
            "pa.`default_on`",
            "count($defaultRows) !== 1",
            "value_name') !== ['Blue', 'Red']",
            "quantity !== 8",
            "getQuantityAvailableByProduct($productId, 0, $shopId) !== 0",
            "id_tax_rules_group",
            "addTaxes",
            "10.0",
            "500.0",
            "[CI ONLY]",
            "visibility = 'both'",
            "available_for_order = 1",
            "CI_TEST_VARIANT_PRODUCT_ID=",
            "optionGroups",
            "カートオプション",
            "장바구니 옵션",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)

        self.assertNotIn("KURANEA-CI-", source, "the cart fixture must not be selected as the existing order fixture")
        self.assertNotIn("docker system prune", source)

    def test_cart_controls_script_accepts_setup_output_as_a_product_id(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_cart_controls_browser.py").read_text(encoding="utf-8")
        self.assertIn('os.environ["CI_TEST_PRODUCT_ID"]', browser)
        self.assertIn("product_attribute", browser)


if __name__ == "__main__":
    unittest.main()
