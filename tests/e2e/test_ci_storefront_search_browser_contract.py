"""Static contracts for search QA against the existing isolated variant product."""

from pathlib import Path
import ast
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tests/e2e/verify_ci_storefront_search_browser.py"
WORKFLOW = ROOT / ".github/workflows/fresh-install.yml"


class StorefrontSearchBrowserContractTests(unittest.TestCase):
    def test_browser_checks_exact_partial_missing_and_product_identity(self):
        self.assertTrue(SCRIPT.is_file(), "Japanese storefront search browser verifier is missing")
        source = SCRIPT.read_text(encoding="utf-8")
        ast.parse(source)
        for required in (
            '"exact", "カートオプション"', '"partial", "カートオプ"',
            '"missing", f"該当なし検索検証{run_id}試行{attempt}"',
            'Keys.ENTER', 'parse_qs', 'body#search',
            'assert_japanese_document(driver)', 'expected_name',
            'product_page_failure_reason(', 'expected_product_id=PRODUCT_ID',
            '"desktop", 1440, 960', '"mobile", 390, 844',
            'storefront-search-{label}-{case}.png',
            'storefront-search-{label}-product.png',
            'storefront-search-{label}-result.json', 'payment_provider_called',
            '"diagnostics"', '"search_result_document"', '"query_readback_matches"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)

    def test_post_search_assertions_report_their_own_bounded_substage(self):
        source = SCRIPT.read_text(encoding="utf-8")
        expected = (
            'result["substage"] = "search_result_heading"',
            'result["substage"] = "search_no_results"',
            'result["substage"] = "search_result_title"',
            'result["substage"] = "search_fixture_card"',
            'result["substage"] = "search_product_link"',
        )
        positions = [source.index(stage) for stage in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn('result["current_url"]', source)
        self.assertNotIn('result["query"]', source)

    def test_search_uses_only_existing_variant_and_browser_safety_helpers(self):
        self.assertTrue(SCRIPT.is_file(), "Japanese storefront search browser verifier is missing")
        source = SCRIPT.read_text(encoding="utf-8")
        for required in (
            'from verify_cart_controls_browser import (',
            'validate_isolated_ci_compose_project', 'validate_loopback_shop',
            'click_at_center', 'click_header_search_toggle(driver, toggle)', 'visible', 'CI_TEST_PRODUCT_ID',
            'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT',
            '[CI ONLY] ORDENOWA カートオプション {run_id}-{attempt}',
            'assert_same_origin', 'assert_product_destination',
        ):
            self.assertIn(required, source)
        header_click = source[source.index('def click_header_search_toggle'):source.index('def search(')]
        self.assertIn('document.elementFromPoint(x, y)', header_click)
        self.assertNotIn('y < 70', header_click)
        self.assertIn('element.click()', header_click)
        for forbidden in ('subprocess', 'requests.', 'add_to_cart.click', 'controller=order', 'PaymentModule'):
            self.assertNotIn(forbidden, source)

    def test_selectors_are_grounded_in_child_and_parent_theme_templates(self):
        searchbar = (ROOT / "themes/kuranea/modules/ps_searchbar/ps_searchbar.tpl").read_text()
        for required in ('id="ps_searchbar_input"', 'name="s"', 'role="search"', 'id="searchCanvas"'):
            self.assertIn(required, searchbar)
        miniature = (ROOT / "themes/hummingbird/templates/catalog/_partials/miniatures/product.tpl").read_text()
        for required in ('data-id-product="{$product.id_product}"', '{$componentName}__title', '{$product.url}'):
            self.assertIn(required, miniature)
        search = (ROOT / "themes/kuranea/templates/catalog/listing/search.tpl").read_text()
        for required in ('id="js-product-list-header"', 'の商品は見つかりませんでした', '検索条件に一致する商品が見つかりませんでした。'):
            self.assertIn(required, search)

    def test_existing_variant_fixture_has_expected_japanese_search_term(self):
        fixture = (ROOT / "tests/catalog/setup_ci_variant_product.php").read_text()
        self.assertIn("'[CI ONLY] ORDENOWA カートオプション ' . $runId . '-' . $attempt", fixture)
        self.assertIn("$product->visibility = 'both'", fixture)
        self.assertIn('CI_TEST_VARIANT_PRODUCT_ID=', fixture)
        self.assertIn('Search::indexation(false, $productId)', fixture)

    def test_browser_search_is_run_and_aggregated_from_the_existing_variant_fixture(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        step = workflow.split("- name: Verify Japanese storefront search in Chromium", 1)[1].split("- name:", 1)[0]
        self.assertIn("id: storefront_search_browser_qa", step)
        self.assertIn("steps.variant_fixture.outcome == 'success'", step)
        self.assertIn('CI_TEST_PRODUCT_ID="$CI_TEST_VARIANT_PRODUCT_ID"', step)
        self.assertIn("tests/e2e/verify_ci_storefront_search_browser.py", step)
        self.assertIn("storefront-search-e2e.log", step)
        coverage = workflow.split("- name: Verify browser QA screenshot coverage", 1)[1].split("- name:", 1)[0]
        self.assertIn("STOREFRONT_SEARCH_BROWSER_QA_OUTCOME: ${{ steps.storefront_search_browser_qa.outcome }}", coverage)
        self.assertIn('"$STOREFRONT_SEARCH_BROWSER_QA_OUTCOME" == success', coverage)
        for evidence in (
            "storefront-search-e2e.log",
            "storefront-search-desktop-result.json", "storefront-search-mobile-result.json",
            "storefront-search-desktop-exact.png", "storefront-search-desktop-partial.png",
            "storefront-search-desktop-product.png", "storefront-search-desktop-missing.png",
            "storefront-search-mobile-exact.png", "storefront-search-mobile-partial.png",
            "storefront-search-mobile-product.png", "storefront-search-mobile-missing.png",
        ):
            with self.subTest(evidence=evidence):
                self.assertIn(evidence, coverage)
        self.assertIn('elif [[ "$STOREFRONT_SEARCH_BROWSER_QA_OUTCOME" == failure ]]; then', coverage)
        aggregate = workflow.split("- name: Aggregate browser QA and postal verification failures", 1)[1].split("- name:", 1)[0]
        self.assertIn("STOREFRONT_SEARCH_BROWSER_QA_OUTCOME: ${{ steps.storefront_search_browser_qa.outcome }}", aggregate)
        self.assertIn("steps.storefront_search_browser_qa.outcome", aggregate)
        self.assertIn('"storefront_search=$STOREFRONT_SEARCH_BROWSER_QA_OUTCOME"', aggregate)
        preflight = workflow.split("- name: Verify fresh-install workflow contracts", 1)[1].split("- name:", 1)[0]
        self.assertIn("tests.e2e.test_ci_storefront_search_browser_contract", preflight)


if __name__ == "__main__":
    unittest.main()
