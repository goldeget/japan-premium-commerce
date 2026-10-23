"""Lock in the standalone Chromium cart controls QA without Docker."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode, urlparse


ROOT = Path(__file__).resolve().parents[2]
CART_CONTROLS_E2E = ROOT / "tests" / "e2e" / "verify_cart_controls_browser.py"


class CartControlsBrowserContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not CART_CONTROLS_E2E.is_file():
            raise AssertionError("standalone Chromium cart controls QA is missing")
        cls.source = CART_CONTROLS_E2E.read_text(encoding="utf-8")

    def test_uses_the_existing_isolated_product_and_real_cart_controls(self) -> None:
        for expected in (
            'os.environ["SHOP_BASE_URL"]',
            'os.environ["CI_TEST_PRODUCT_ID"]',
            'os.environ["QA_ARTIFACT_DIR"]',
            "webdriver.Chrome(",
            '".js-cart-line-product-quantity"',
            "js-increment-button",
            "button.click()",
            'button[data-bs-dismiss="modal"]',
            'data-link-action="delete-from-cart"',
            "remove_link.click()",
            "cart-controls-{label}-initial.png",
            "cart-controls-{label}-quantity-updated.png",
            "cart-controls-{label}-empty.png",
            "cart-controls-{label}-readded.png",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.source)

    def test_variant_qa_requires_the_fixture_color_choices_and_real_combination_change(self) -> None:
        for expected in (
            '"fieldset.product-variant"',
            'legend != "Color"',
            'available != {"Blue", "Red"}',
            'select[name^="group["]',
            'input[type="radio"][name^="group["]',
            '"the CI Color fixture must have a selectable non-default value"',
            "before_attribute_id",
            'variant["variant_status"] != "selected"',
            '"variant_status"',
            '".product-line__item-value"',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.source)

    def test_variant_detail_and_cart_show_the_tax_included_gross_price(self) -> None:
        for expected in (
            "EXPECTED_GROSS_PRICE_JPY = 550",
            '".product__price"',
            '".product-line__item-price"',
            '".product-line__price"',
            "expected_quantity",
            "EXPECTED_GROSS_PRICE_JPY * int(expected_quantity)",
            "tax-inclusive",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.source)

    def test_cart_controls_flow_does_not_open_checkout_or_payment(self) -> None:
        self.assertNotIn('controller=order', self.source)
        self.assertNotIn("ps_checkpayment", self.source)

    def test_product_url_is_relative_and_visit_prefixes_shop_base_once(self) -> None:
        tree = ast.parse(self.source, filename=str(CART_CONTROLS_E2E))
        function_nodes = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in {"product_url", "visit"}
        ]
        self.assertEqual({node.name for node in function_nodes}, {"product_url", "visit"})

        class FakeDriver:
            url = ""

            def get(self, url: str) -> None:
                self.url = url

            def execute_script(self, _script: str) -> str:
                return "complete"

        class ImmediateWait:
            def __init__(self, driver: FakeDriver, _timeout: int) -> None:
                self.driver = driver

            def until(self, predicate):
                return predicate(self.driver)

        namespace = {
            "BASE": "http://localhost:18080",
            "PRODUCT_ID": 123,
            "urlencode": urlencode,
            "webdriver": SimpleNamespace(Chrome=FakeDriver),
            "WebDriverWait": ImmediateWait,
        }
        module = ast.Module(body=function_nodes, type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), str(CART_CONTROLS_E2E), "exec"), namespace)

        path = namespace["product_url"]()
        self.assertTrue(path.startswith("/index.php?"))
        self.assertEqual(urlparse(path).scheme, "")

        driver = FakeDriver()
        namespace["visit"](driver, path)
        self.assertEqual(driver.url, "http://localhost:18080" + path)
        self.assertEqual(driver.url.count("http://"), 1)

    def test_product_add_reports_privacy_safe_wait_substages(self) -> None:
        expected_substages = (
            "detail_navigation",
            "fixture_marker_wait",
            "variant_group_discovery",
            "variant_selection",
            "variant_selection_update_wait",
            "detail_price_wait",
            "add_button_wait",
            "add_button_click",
            "blockcart_confirmation_wait",
            "continue_shopping_click",
            "blockcart_close_wait",
            "cart_navigation",
            "cart_line_wait",
        )
        for substage in expected_substages:
            with self.subTest(substage=substage):
                self.assertTrue(
                    f'mark_substage("{substage}")' in self.source,
                    f"missing fixed product-add diagnostic substage: {substage}",
                )
        variant_start = self.source.index("def select_variant_when_available(")
        variant_end = self.source.index("\ndef visible_product_line(", variant_start)
        variant_source = self.source[variant_start:variant_end]
        variant_substages = expected_substages[2:5]
        variant_positions = [
            variant_source.index(f'mark_substage("{substage}")')
            for substage in variant_substages
        ]
        self.assertEqual(variant_positions, sorted(variant_positions))

        add_start = self.source.index("def add_product_from_detail(")
        add_end = self.source.index("\ndef wait_for_empty_cart(", add_start)
        add_source = self.source[add_start:add_end]
        runtime_order = (
            'mark_substage("detail_navigation")',
            'mark_substage("fixture_marker_wait")',
            "select_variant_when_available(driver, mark_substage)",
            'mark_substage("detail_price_wait")',
            'mark_substage("add_button_wait")',
            'mark_substage("add_button_click")',
            'mark_substage("blockcart_confirmation_wait")',
            'mark_substage("continue_shopping_click")',
            'mark_substage("blockcart_close_wait")',
            'mark_substage("cart_navigation")',
            'mark_substage("cart_line_wait")',
        )
        add_positions = [add_source.index(statement) for statement in runtime_order]
        self.assertEqual(add_positions, sorted(add_positions))

        self.assertTrue("current_add_substage" in self.source)
        self.assertTrue('f"{stage}_{current_add_substage[0]}"' in self.source)
        self.assertFalse("driver.current_url" in self.source)
        self.assertTrue("failed at {safe_stage} ({exception_type})" in self.source)

    def test_variant_selection_supports_hummingbird_form_without_hidden_combination_id(self) -> None:
        self.assertTrue("tuple[list[tuple[str, str]], int | None] | bool" in self.source)
        self.assertTrue("any(value == requested_label for _, value in selected)" in self.source)
        self.assertTrue("before_attribute_id is not None" in self.source)
        self.assertTrue("visible_product_line(browser, None)" in self.source)
        self.assertTrue('variant_result["product_attribute_id"] = cart_attribute_id' in self.source)
        self.assertTrue('data-id-product-attribute' in self.source)


if __name__ == "__main__":
    unittest.main()
