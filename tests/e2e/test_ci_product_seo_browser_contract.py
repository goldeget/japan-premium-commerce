"""Contracts for the isolated synthetic product SEO browser acceptance."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tests/e2e/verify_ci_product_seo_browser.py"
PRODUCT_FIXTURE = ROOT / "tests/catalog/prepare_ci_free_shipping_product.php"
PRODUCT_TEMPLATE = ROOT / "themes/hummingbird/templates/catalog/product.tpl"
PRODUCT_JSONLD = ROOT / "themes/kuranea/templates/_partials/microdata/product-jsonld.tpl"
PRICE_TEMPLATE = ROOT / "themes/hummingbird/templates/catalog/_partials/product-prices.tpl"
ADD_TO_CART_TEMPLATE = ROOT / "themes/hummingbird/templates/catalog/_partials/product-add-to-cart.tpl"
HEAD_TEMPLATE = ROOT / "themes/kuranea/templates/_partials/head.tpl"


class CiProductSeoBrowserContractTests(unittest.TestCase):
    def test_verifier_compares_rendered_product_offer_to_visible_fixture(self) -> None:
        self.assertTrue(SCRIPT.is_file(), "isolated product SEO browser verifier is missing")
        source = SCRIPT.read_text(encoding="utf-8")
        ast.parse(source)

        for required in (
            "from verify_cart_controls_browser import (",
            "validate_isolated_ci_compose_project",
            "validate_loopback_shop",
            "CI_TEST_PRODUCT_ID",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
            "querySelectorAll",
            "application/ld+json",
            "h1.product__name",
            ".product__price",
            "button[data-ps-ref='add-to-cart']",
            "input#product_page_product_id[name='id_product']",
            "link[rel='canonical']",
            "priceCurrency",
            "availability",
            "application/ld+json",
            '"sku_matches_run_scoped_reference"',
            '"name_matches_visible_heading"',
            '"offer_price_matches_visible_price"',
            '"currency_matches_visible_yen_and_fixture"',
            '"offer_url_matches_canonical"',
            '"availability_matches_purchasable_ui"',
            "all(checks.values())",
            "product-seo-desktop.png",
            "product-seo-result.json",
            'result["substage"]', 'result["response_status"]',
            'result["same_origin"]', 'result["japanese_document"]',
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)

        for forbidden in (
            "requests.",
            "subprocess",
            "controller=order",
            "PaymentModule",
            "add_to_cart",
            "click_at_center",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_existing_fixture_is_active_run_scoped_and_has_known_visible_price_and_stock(self) -> None:
        source = PRODUCT_FIXTURE.read_text(encoding="utf-8")
        for required in (
            "'[CI ONLY] ORDENOWA free shipping product ' . $runId . '-' . $attempt",
            "'price_jpy' => '1100'",
            "'quantity' => '6'",
            "'[CI ONLY] synthetic product tax '",
            "$product->active = 1",
            "$product->visibility = 'both'",
            "$product->available_for_order = 1",
            "$product->show_price = 1",
            "'price_jpy' => 1100",
            "'fixture_scope' => 'run-scoped isolated GitHub Actions disposable checkout database'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)

    def test_assertions_follow_product_theme_markup_and_schema_fields(self) -> None:
        product = PRODUCT_TEMPLATE.read_text(encoding="utf-8")
        product_jsonld = PRODUCT_JSONLD.read_text(encoding="utf-8")
        prices = PRICE_TEMPLATE.read_text(encoding="utf-8")
        add_to_cart = ADD_TO_CART_TEMPLATE.read_text(encoding="utf-8")
        head = HEAD_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="product_page_product_id"', product)
        self.assertIn('<h1 class="product__name', product)
        self.assertIn('"sku":', product_jsonld)
        self.assertIn('"priceCurrency":', product_jsonld)
        self.assertIn('"price":', product_jsonld)
        self.assertIn('"url":', product_jsonld)
        self.assertIn('"availability":', product_jsonld)
        self.assertIn('class="product__price"', prices)
        self.assertIn('data-ps-ref="add-to-cart"', add_to_cart)
        self.assertIn('rel="canonical"', head)

    def test_fresh_install_workflow_runs_and_aggregates_the_product_seo_browser(self) -> None:
        workflow_path = ROOT / ".github/workflows/fresh-install.yml"
        workflow = workflow_path.read_text(encoding="utf-8")
        step = workflow.split("id: storefront_product_seo_browser_qa", 1)
        self.assertEqual(2, len(step), "the rendered Product/Offer browser verifier must run in isolated CI")
        step_block = step[1].split("\n      - name:", 1)[0]
        self.assertIn("continue-on-error: true", step_block)
        self.assertIn("steps.shipping_product_fixture.outcome == 'success'", step_block)
        self.assertIn("steps.chromium_setup.outcome == 'success'", step_block)
        self.assertIn("tests/e2e/verify_ci_product_seo_browser.py", step_block)
        self.assertIn("product-seo-e2e.log", step_block)

        self.assertIn(
            "STOREFRONT_SEO_BROWSER_QA_OUTCOME: ${{ steps.storefront_product_seo_browser_qa.outcome }}",
            workflow,
        )
        self.assertIn("storefront_product_seo=$STOREFRONT_SEO_BROWSER_QA_OUTCOME", workflow)
        self.assertIn("product-seo-result.json", workflow)
        self.assertIn("product-seo-desktop.png", workflow)
        self.assertIn("tests.e2e.test_ci_product_seo_browser_contract", workflow)


if __name__ == "__main__":
    unittest.main()
