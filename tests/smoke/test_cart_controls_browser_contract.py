"""Lock in the standalone Chromium cart controls QA without Docker."""
from __future__ import annotations

import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
