"""Keep isolated browser checkout QA aligned with the approved free-shipping policy."""
from __future__ import annotations

import unittest
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/fresh-install.yml"
BROWSER = ROOT / "tests/e2e/verify_ci_free_shipping_browser.py"
ORDER_VERIFY = ROOT / "tests/postcode/verify_ci_free_shipping_order.php"
COUPON_FIXTURE = ROOT / "tests/postcode/seed_ci_shipping_coupon.php"
JAPAN_ZONE_FIXTURE = ROOT / "tests/postcode/prepare_ci_japan_shipping_zone.php"
SHIPPING_PRODUCT_FIXTURE = ROOT / "tests/catalog/prepare_ci_free_shipping_product.php"


class FreeShippingE2eContractTest(unittest.TestCase):
    def test_active_no_rule_product_fixture_is_independent_of_postcode_order_qa(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertTrue(SHIPPING_PRODUCT_FIXTURE.is_file(), "free-shipping QA needs its own active CI product fixture")
        product_step = workflow.split(
            "- name: Prepare isolated active product for storefront and free-shipping QA", 1
        )[1].split("- name:", 1)[0]
        postcode_step = workflow.split(
            "- name: Import synthetic Tokyo postcode fixture for isolated checkout QA", 1
        )[1].split("- name:", 1)[0]
        self.assertIn("id: shipping_product_fixture", product_step)
        self.assertIn("prepare_ci_free_shipping_product.php", product_step)
        self.assertNotIn("postcode_fixture.outcome", product_step)
        self.assertLess(workflow.index("id: shipping_product_fixture"), workflow.index("id: postcode_fixture"))
        self.assertIn("'tax_rules_group_id' => '0'", SHIPPING_PRODUCT_FIXTURE.read_text(encoding="utf-8"))
        self.assertIn("not a legal tax determination", SHIPPING_PRODUCT_FIXTURE.read_text(encoding="utf-8"))
        self.assertIn("CI_TEST_PRODUCT_ID=", product_step)
        self.assertNotIn("KURANEA-CI-%", product_step)
        free_shipping_step = workflow.split(
            "- name: Prepare isolated free-shipping order and coupon fixtures", 1
        )[1].split("- name:", 1)[0]
        self.assertIn("CI_TEST_PRODUCT_ID", free_shipping_step)
        self.assertNotIn("steps.postcode_fixture.outcome", free_shipping_step)

    def test_free_shipping_price_checks_do_not_depend_on_postcode_lookup(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for step_name in (
            "Enable run-scoped checkout only for the isolated order browser QA",
            "Verify zero shipping in Tokyo coupon and quantity checkout with Chromium",
            "Verify zero shipping in Osaka mobile checkout with Chromium",
            "Verify tax-included taxable Japan checkout with the free carrier",
            "Verify free-shipping orders and totals in the isolated database",
            "Verify free-shipping orders in a separate admin browser session",
        ):
            with self.subTest(step=step_name):
                step = workflow.split(f"- name: {step_name}", 1)[1].split("- name:", 1)[0]
                self.assertNotIn("steps.postcode_lookup.outcome", step)
        self.assertIn("steps.postcode_lookup.outcome == 'success'", workflow.split(
            "- name: Verify browser customer search, Japan checkout, and unpaid offline order", 1
        )[1].split("- name:", 1)[0], "the independent postal-address checkout test must retain its lookup prerequisite")

    def test_free_shipping_fixture_failure_exposes_safe_stage_diagnostics(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        fixture_step = workflow.split(
            "- name: Prepare isolated free-shipping order and coupon fixtures", 1
        )[1].split("- name:", 1)[0]
        for phase in ("japan_zone", "stock", "coupon"):
            with self.subTest(phase=phase):
                self.assertIn(phase, fixture_step)
        self.assertIn("::error title=ORDENOWA free-shipping fixture::", fixture_step)
        self.assertIn("shipping-free-fixture", fixture_step)
        self.assertIn("CI_TEST_PRODUCT_ID", fixture_step)

        zone_source = JAPAN_ZONE_FIXTURE.read_text(encoding="utf-8")
        self.assertIn("ORDENOWA_CI_JAPAN_ZONE_STAGE=", zone_source)
        self.assertIn("set_exception_handler", zone_source)
        coupon_source = COUPON_FIXTURE.read_text(encoding="utf-8")
        self.assertIn("fwrite(STDERR, '::error title=ORDENOWA CI coupon fixture::'", coupon_source)
        self.assertNotIn("fwrite(STDOUT, '::error title=ORDENOWA CI coupon fixture::'", coupon_source)

    def test_database_writing_fixtures_guard_the_connected_disposable_database(self) -> None:
        for path in (
            SHIPPING_PRODUCT_FIXTURE,
            JAPAN_ZONE_FIXTURE,
            COUPON_FIXTURE,
        ):
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertIn("KURANEA_CI_PROJECT_NAME", source)
                self.assertIn("_DB_SERVER_", source)
                self.assertIn("_DB_NAME_", source)
                self.assertIn("SELECT DATABASE()", source)
                self.assertIn("'mariadb'", source)
                self.assertIn("'prestashop'", source)
                self.assertIn("server_match=%s", source)
                self.assertIn("configured_name_match=%s", source)
                self.assertIn("active_connection_match=%s", source)

    def test_japan_zone_fixture_requires_and_reports_configured_prefectures(self) -> None:
        source = JAPAN_ZONE_FIXTURE.read_text(encoding="utf-8")
        self.assertIn("$stateCount", source)
        self.assertIn("$stateCount !== 47", source)
        self.assertIn("'state_count' => $stateCount", source)
        workflow = WORKFLOW.read_text(encoding="utf-8")
        zone_validation = workflow.split(
            "shipping_fixture_stage=\"japan_zone_validate\"", 1
        )[1].split("shipping_fixture_stage=", 1)[0]
        self.assertIn("state_count", zone_validation)
        self.assertIn("== 47", zone_validation)

    def test_japan_zone_fixture_compares_the_exact_supported_prefecture_code_set(self) -> None:
        source = JAPAN_ZONE_FIXTURE.read_text(encoding="utf-8")
        self.assertIn("/var/www/html/modules/kuraneapostcode/autoload.php", source)
        self.assertIn("PrefectureCatalog::all()", source)
        self.assertIn("PrefectureCatalog::isoCode($prefectureCode)", source)
        self.assertIn("$stateCodes !== $expectedStateCodes", source)
        self.assertIn("'state_iso_codes' => $stateCodes", source)

        workflow = WORKFLOW.read_text(encoding="utf-8")
        zone_validation = workflow.split(
            'python3 - "$zone_fixture" <<\'PY\' 2>&1 | tee "$shipping_fixture_log"', 1
        )[1].split("          PY", 1)[0]
        self.assertIn('[f"JP-{code:02d}" for code in range(1, 48)]', zone_validation)
        self.assertIn('fixture["state_iso_codes"] == expected_state_codes', zone_validation)

    def test_workflow_saves_and_reloads_free_carrier_before_checkout_and_order_checks(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        steps = (
            "Prepare isolated free-shipping order and coupon fixtures",
            "Configure the free Japan carrier through Chromium AdminCarriers",
            "Restart PrestaShop with the CI database volume intact",
            "Read back the free Japan carrier after a fresh admin login",
            "Verify zero shipping in Tokyo coupon and quantity checkout with Chromium",
            "Verify zero shipping in Osaka mobile checkout with Chromium",
            "Verify free-shipping orders and totals in the isolated database",
            "Verify free-shipping orders in a separate admin browser session",
        )
        positions = [workflow.index(f"- name: {step}") for step in steps]
        self.assertEqual(positions, sorted(positions))

        for step_id in (
            "shipping_free_fixture",
            "shipping_free_admin_configure",
            "shipping_free_restart",
            "shipping_free_admin_readback",
            "shipping_free_customer_browser_qa",
            "shipping_free_osaka_mobile_browser_qa",
            "shipping_free_order_persistence",
            "shipping_free_admin_browser_qa",
        ):
            self.assertIn(f"id: {step_id}", workflow)

        restart_step = workflow.split("- name: Restart PrestaShop with the CI database volume intact", 1)[1].split("- name:", 1)[0]
        self.assertIn('docker compose -p "$CI_COMPOSE_PROJECT_NAME" restart prestashop', restart_step)
        self.assertNotIn("tests/fixtures/ci-checkout.compose.yaml", restart_step)
        for mode in ("configure", "readback", "customer", "osaka-mobile", "admin"):
            self.assertIn(f"verify_ci_free_shipping_browser.py {mode}", workflow)
        self.assertIn("verify_ci_free_shipping_order.php", workflow)
        self.assertIn("seed_ci_shipping_coupon.php", workflow)
        self.assertIn("CI_JAPAN_ZONE_ID", workflow)
        self.assertIn("CI_TEST_PRODUCT_TAX_GROUP", workflow)
        self.assertIn("prepare_ci_japan_shipping_zone.php", workflow)
        self.assertIn("5300001", workflow)
        self.assertIn('[ "$product_tax_group_id" != "0" ]', workflow)
        self.assertIn('[ "$product_id" != "$expected_product_id" ]', workflow)
        self.assertIn('[ "$product_tax_group_id" != "$expected_tax_group_id" ]', workflow)
        self.assertNotIn('|| "$product_tax_group_id" !=', workflow)
        self.assertNotIn('|| "$product_id" !=', workflow)

    def test_browser_only_sets_free_japan_shipping_and_reconciles_customer_views(self) -> None:
        self.assertTrue(BROWSER.is_file(), "free-shipping browser QA must be implemented")
        browser = BROWSER.read_text(encoding="utf-8")
        for marker in (
            "def configure_free_carrier",
            "def readback_free_carrier",
            "def run_japan_customer_checkout",
            "def run_japan_mobile_osaka_checkout",
            "def run_free_carrier_admin_order_view",
            "carrier[shipping_settings][is_free]",
            "carrier_shipping_settings_zones",
            "def _assert_free_carrier_form",
            "#quantity_wanted",
            "cart-subtotal-shipping",
            "order-history__cell--total",
            "CI_COUPON_CODE",
            "5300001",
            "total_tax_incl",
            "coupon_condition",
            "save_screenshot",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, browser)

        self.assertNotIn("ShippingMethod.BY_PRICE", browser)
        self.assertNotIn("ShippingMethod.BY_WEIGHT", browser)
        self.assertNotIn("js-add-carrier-ranges-btn", browser)
        self.assertNotIn("_set_tax_rule_to_no_tax", browser)
        self.assertNotIn("EXPECTED_QUANTITY", browser)
        self.assertIn("BLOCKED: no run-scoped disposable coupon fixture was supplied", browser)
        self.assertIn("selected zones were", browser)

    def test_checkout_tax_classifier_does_not_count_tax_inclusive_grand_total_as_tax(self) -> None:
        source = ast.parse(BROWSER.read_text(encoding="utf-8"))
        classifier = next(
            node for node in source.body
            if isinstance(node, ast.FunctionDef) and node.name == "_is_tax_summary_label"
        )
        isolated = ast.Module(body=[classifier], type_ignores=[])
        namespace: dict[str, object] = {}
        exec(compile(ast.fix_missing_locations(isolated), str(BROWSER), "exec"), namespace)
        is_tax_summary_label = namespace["_is_tax_summary_label"]

        for label in ("Total (tax incl.)", "Total tax included", "合計 (税込)", "総計 税込"):
            with self.subTest(label=label):
                self.assertFalse(is_tax_summary_label(label), label)
        for label in ("Taxes", "Tax", "税", "消費税"):
            with self.subTest(label=label):
                self.assertTrue(is_tax_summary_label(label), label)

    def test_admin_order_view_reconciles_tokyo_osaka_and_taxable_orders(self) -> None:
        browser = BROWSER.read_text(encoding="utf-8")
        admin_view = browser.split("def run_free_carrier_admin_order_view", 1)[1].split(
            "def _emit_failure", 1
        )[0]
        for marker in (
            "shipping-free-mobile-order.json",
            "shipping-free-taxable-order.json",
            "for order_kind, order_path in order_paths",
            "#orderProductsTotal",
            "#orderShippingTotal",
            "#orderTaxesTotal",
            "#orderTotal",
            "#shipping-grid-table .carrier-price",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, admin_view)

    def test_order_confirmation_totals_are_checked_before_history_navigation(self) -> None:
        browser = BROWSER.read_text(encoding="utf-8")
        self.assertIn("def _order_confirmation_totals", browser)
        self.assertIn("def _place_unpaid_order_and_verify_confirmation", browser)
        for marker in (
            ".order-confirmation__product-total",
            ".order-confirmation__subtotals .order-confirmation__line",
            ".order-confirmation__totals .order-confirmation__line",
            "products_tax_incl",
            "shipping_tax_incl",
            "total_tax_incl",
            "browser_totals[\"tax\"]",
            "if observed != expected:",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, browser)

        confirmation_reader = browser.split("def _order_confirmation_totals", 1)[1].split(
            "def _place_unpaid_order_and_verify_confirmation", 1
        )[0]
        for expression in (
            "sum(product_totals)",
            "_parse_yen(shipping_lines[0])",
            "sum(tax_amounts)",
            "total_amounts[-1]",
        ):
            with self.subTest(expression=expression):
                self.assertIn(expression, confirmation_reader)

        source = ast.parse(browser)
        shipping_classifier = next(
            node for node in source.body
            if isinstance(node, ast.FunctionDef) and node.name == "_is_shipping_summary_label"
        )
        namespace: dict[str, object] = {}
        exec(compile(ast.Module(body=[shipping_classifier], type_ignores=[]), str(BROWSER), "exec"), namespace)
        is_shipping_summary_label = namespace["_is_shipping_summary_label"]
        for label in ("Shipping", "Delivery", "送料", "配送", "発送", "배송"):
            with self.subTest(shipping_label=label):
                self.assertTrue(is_shipping_summary_label(label))
        for label in ("Products", "商品", "Tax"):
            with self.subTest(non_shipping_label=label):
                self.assertFalse(is_shipping_summary_label(label))

        placer = browser.split("def _place_unpaid_order_and_verify_confirmation", 1)[1].split(
            "def _order_history_total", 1
        )[0]
        self.assertLess(
            placer.index("_order_confirmation_totals(driver)"),
            placer.index('BASE + "/index.php?controller=history"'),
            "the real confirmation totals must be captured before the browser leaves that page",
        )
        for flow in (
            "def run_japan_customer_checkout",
            "def run_japan_mobile_osaka_checkout",
            "def run_japan_taxable_customer_checkout",
        ):
            body = browser.split(flow, 1)[1].split("\ndef ", 1)[0]
            with self.subTest(flow=flow):
                self.assertIn("_place_unpaid_order_and_verify_confirmation(", body)
                self.assertIn("browser_totals", body)

    def test_order_verifier_reconciles_browser_and_native_amounts_without_changing_tax(self) -> None:
        self.assertTrue(ORDER_VERIFY.is_file(), "free-shipping order verifier must be implemented")
        verifier = ORDER_VERIFY.read_text(encoding="utf-8")
        for marker in (
            "KURANEA_ISOLATED_CI",
            "KURANEA_CI_ORDER_ID",
            "KURANEA_CI_CARRIER_ID",
            "total_products_tax_excl",
            "total_products_tax_incl",
            "total_shipping_tax_excl",
            "total_shipping_tax_incl",
            "total_paid_tax_excl",
            "total_paid_tax_incl",
            "total_paid_real",
            "product_shop",
            "id_tax_rules_group",
            "order_detail",
            "browser_checkout",
            "product_quantity",
            "platform fee",
            "tax_fixture_scope",
            "expectedStateIso",
            "carrier_zone_country_codes",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, verifier)
        self.assertNotIn("id_tax_rules_group = 0", verifier)
        self.assertIn("$order->total_products", verifier)
        self.assertIn("$order->total_products_wt", verifier)
        self.assertNotIn("$order->total_products_tax_excl", verifier)
        self.assertNotIn("$order->total_products_tax_incl", verifier)
        self.assertNotIn("Configuration::updateValue", verifier)

    def test_free_shipping_outcomes_are_aggregated_and_required_artifacts_are_gated(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        artifact_gate = workflow.split("- name: Verify browser QA screenshot coverage", 1)[1].split(
            "- name:", 1
        )[0]
        aggregate = workflow.split("- name: Aggregate browser QA and postal verification failures", 1)[1].split(
            "- name:", 1
        )[0]

        shipping_ids = (
            "shipping_free_fixture",
            "shipping_free_admin_configure",
            "shipping_free_restart",
            "shipping_free_admin_readback",
            "shipping_free_customer_browser_qa",
            "shipping_free_osaka_mobile_browser_qa",
            "shipping_free_order_persistence",
            "shipping_free_admin_browser_qa",
        )
        for step_id in shipping_ids:
            variable = step_id.upper() + "_OUTCOME"
            with self.subTest(step_id=step_id):
                self.assertIn(f"steps.{step_id}.outcome", artifact_gate)
                self.assertIn(variable, artifact_gate)
                self.assertIn(f"steps.{step_id}.outcome", aggregate)
                self.assertIn(f'"{step_id}=${variable}"', aggregate)

        for artifact in (
            "shipping-free-tokyo-coupon-checkout-e2e.log",
            "shipping-free-osaka-mobile-checkout-e2e.log",
            "shipping-free-order-admin-tokyo-desktop.png",
            "shipping-free-order-admin-osaka-desktop.png",
            "shipping-free-order-admin-taxable-desktop.png",
            "shipping-free-order-admin-mobile.png",
        ):
            self.assertIn(artifact, artifact_gate)

    def test_japan_zone_fixture_is_disposable_and_contains_japan_only(self) -> None:
        self.assertTrue(JAPAN_ZONE_FIXTURE.is_file(), "Japan-only shipping zone fixture must be implemented")
        fixture = JAPAN_ZONE_FIXTURE.read_text(encoding="utf-8")
        for marker in (
            "KURANEA_ISOLATED_CI",
            "kuranea-ci-",
            "ORDENOWA CI Japan",
            "WHERE `name` = \"' . pSQL($zoneName)",
            "countryCodes !== ['JP']",
            " . _DB_PREFIX_ . 'state`",
            "`id_country` = ",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, fixture)

    def test_coupon_fixture_is_run_scoped_and_does_not_enable_free_shipping(self) -> None:
        self.assertTrue(COUPON_FIXTURE.is_file(), "isolated CI coupon fixture must be implemented")
        coupon = COUPON_FIXTURE.read_text(encoding="utf-8")
        for marker in (
            "KURANEA_ISOLATED_CI",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
            "ORDENOWACI",
            "quantity_per_user",
            "reduction_percent",
            "free_shipping = 0",
            "Disposable isolated CI checkout fixture",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, coupon)


if __name__ == "__main__":
    unittest.main()
