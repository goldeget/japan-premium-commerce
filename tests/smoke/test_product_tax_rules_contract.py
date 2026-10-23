"""Guard native tax selection and tax-included JPY price semantics."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneacatalog"


class ProductTaxRulesContractTests(unittest.TestCase):
    def test_product_draft_requires_an_explicit_native_tax_rules_group(self) -> None:
        draft = (MODULE / "src" / "Domain" / "ProductAdminDraft.php").read_text(encoding="utf-8")

        self.assertIn("taxRulesGroupId", draft)
        self.assertIn("tax_rules_group_id", draft)
        self.assertIn("명시적으로 선택", draft)

    def test_korean_editor_lists_native_groups_and_labels_tax_included_price(self) -> None:
        controller = (MODULE / "controllers" / "admin" / "AdminOrdenowaProductManagerController.php").read_text(encoding="utf-8")

        self.assertIn("세금 포함 판매 가격 (JPY)", controller)
        self.assertIn("name=\"tax_rules_group_id\"", controller)
        self.assertIn("세금 규칙 그룹", controller)
        self.assertIn("TaxRulesGroup", controller)
        self.assertIn("tax_rules_group_id", controller)
        self.assertIn("$selectedTaxRulesGroupId = $values['tax_rules_group_id'] ?? ''", controller)
        self.assertIn("'tax_rules_group_id' => ''", controller)
        self.assertIn("#tax_rules_group_id option[value=\"\"][disabled][selected]", (ROOT / "tests" / "e2e" / "verify_product_admin_browser.py").read_text(encoding="utf-8"))
        self.assertIn("세금 규칙 미할당은 계산 규칙이 연결되지 않았다는 뜻이며 과세 여부를 법적으로 결정하지 않습니다", controller)
        self.assertIn("판매자·상품의 세금 설정에 따라 별도로 확인해야 합니다", controller)
        self.assertIn("disabled selected>세금 규칙 그룹을 선택해 주세요", controller)

    def test_manager_converts_tax_included_price_with_selected_native_group(self) -> None:
        manager = (MODULE / "src" / "Integration" / "PrestaShopNativeProductManager.php").read_text(encoding="utf-8")
        save = manager.split("public function save(", 1)[1].split("public function optionGroups(", 1)[0]

        self.assertIn("TaxRulesGroup::getTaxRulesGroupsForOptions()", manager)
        self.assertIn("TaxManagerFactory::getManager", manager)
        self.assertIn("removeTaxes", save)
        self.assertIn("$draft->taxRulesGroupId", save)
        self.assertIn("addTaxes", manager)
        self.assertIn("Group::getGroups", manager)
        self.assertIn("Group::PRICE_DISPLAY_METHOD_TAX_INCL", manager)
        self.assertIn("PS_CUSTOMER_GROUP", manager)
        self.assertNotIn("PS_TAX_DISPLAY", manager)
        self.assertNotIn("$product->id_tax_rules_group = 0;", save)
        self.assertIn("zipcode_from", manager)
        self.assertIn("zipcode_to", manager)
        self.assertIn("도도부현 또는 우편번호", manager)

    def test_isolated_tax_integration_proves_price_conversion_and_saved_order_tax_line(self) -> None:
        integration = ROOT / "tests" / "catalog" / "verify_product_tax_price.php"
        self.assertTrue(integration.is_file(), "isolated synthetic tax conversion and order-line verifier is missing")
        source = integration.read_text(encoding="utf-8")
        for expected in (
            "KURANEA_CI_RUN_ID",
            "KURANEA_CI_RUN_ATTEMPT",
            "KURANEA_CI_PROJECT_NAME",
            "[CI ONLY]",
            "tax-included",
            "Group::getGroups",
            "Group::PRICE_DISPLAY_METHOD_TAX_INCL",
            "Group::PRICE_DISPLAY_METHOD_TAX_EXCL",
            "PRICE_DISPLAY_METHOD_TAX_INCL === 0",
            "PRICE_DISPLAY_METHOD_TAX_EXCL === 1",
            "price_display_method",
            "Cart::ONLY_PRODUCTS",
            "Cart::ONLY_SHIPPING",
            "Cart::BOTH",
            "product_price",
            "total_products_wt",
            "total_shipping_tax_incl",
            "total_paid_tax_excl",
            "total_paid_tax_incl",
            "total_shipping_tax_excl",
            "id_carrier",
            "carrier_zone",
            "1100",
            "1000",
            "OrderDetail",
            "unit_price_tax_excl",
            "unit_price_tax_incl",
            "product_price",
            "id_tax_rules_group",
            "paid",
            "no capture",
            "synthetic",
            "finally",
            "Configuration::deleteByName('PS_MAIL_METHOD')",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)
        self.assertNotIn("PS_TAX_DISPLAY", source)
        self.assertNotIn("Japan legal", source)
        self.assertNotIn("Japan statutory", source)

    def test_tax_order_reconciliation_failure_reports_only_synthetic_money_fields(self) -> None:
        integration = ROOT / "tests" / "catalog" / "verify_product_tax_price.php"
        source = integration.read_text(encoding="utf-8")
        for field in (
            "order_total_paid_real",
            "order_total_paid_tax_excl",
            "order_total_paid_tax_incl",
            "order_total_shipping_tax_excl",
            "order_total_shipping_tax_incl",
            "order_total_products_tax_excl",
            "order_total_products_tax_incl",
            "order_detail_tax_group_id",
            "order_detail_tax_rate",
            "order_detail_unit_tax_excl",
            "order_detail_unit_tax_incl",
            "order_detail_total_tax_excl",
            "order_detail_total_tax_incl",
        ):
            with self.subTest(field=field):
                self.assertIn(field, source)
        self.assertRegex(source, r"json_encode\(\s*\$taxOrderMismatch")
        self.assertIn("JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES", source)


if __name__ == "__main__":
    unittest.main()
