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
            "click_at_center(driver, button)",
            'button[data-bs-dismiss="modal"]',
            'data-link-action="delete-from-cart"',
            "click_at_center(driver, remove_link)",
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

    def test_cart_totals_are_allowed_to_catch_up_after_quantity_input_changes(self) -> None:
        """Hummingbird updates the input first, then refreshes prices after its AJAX response."""
        tree = ast.parse(self.source, filename=str(CART_CONTROLS_E2E))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"assert_cart_has_only_test_product", "visible_product_line"}
        }
        self.assertEqual(set(functions), {"assert_cart_has_only_test_product", "visible_product_line"})

        class Text:
            def __init__(self, browser, stale: str, updated: str) -> None:
                self.browser = browser
                self.stale = stale
                self.updated = updated

            @property
            def text(self) -> str:
                return self.updated if self.browser.poll >= 2 else self.stale

        class Field:
            def get_attribute(self, name: str) -> str | None:
                return "2" if name == "value" else None

        class Row:
            def __init__(self, browser) -> None:
                self.browser = browser

            def find_elements(self, _by, selector):
                if selector == ".js-cart-line-product-quantity":
                    return [Field()]
                if selector == ".product-line__item-value":
                    return []
                if selector == ".product-line__item-price":
                    return [Text(self.browser, "¥550", "¥550")]
                if selector == ".product-line__price":
                    return [Text(self.browser, "¥550", "¥1,100")]
                return []

        class Browser:
            poll = 0

            def __init__(self) -> None:
                self.row = Row(self)

            def find_elements(self, _by, selector):
                if selector == ".cart__item":
                    return [self.row]
                if selector == "#cart-subtotal-products .cart-summary__value":
                    return [Text(self, "¥550", "¥1,100")]
                return []

        class PollingWait:
            def __init__(self, browser, _timeout, **_kwargs) -> None:
                self.browser = browser

            def until(self, predicate, message=""):
                for self.browser.poll in (1, 2, 3):
                    result = predicate(self.browser)
                    if result:
                        return result
                raise AssertionError(message or "cart line and subtotal did not catch up with quantity two")

        browser = Browser()
        namespace = {
            "By": SimpleNamespace(CSS_SELECTOR="css selector"),
            "EXPECTED_GROSS_PRICE_JPY": 550,
            "StaleElementReferenceException": RuntimeError,
            "WebDriverWait": PollingWait,
            "visible_product_line": lambda _browser, _attribute_id: browser.row,
            "parse_yen": lambda raw: int(raw.replace("¥", "").replace(",", "")),
        }
        module = ast.Module(
            body=[functions["assert_cart_has_only_test_product"]],
            type_ignores=[],
        )
        exec(compile(ast.fix_missing_locations(module), str(CART_CONTROLS_E2E), "exec"), namespace)

        namespace["assert_cart_has_only_test_product"](browser, "2", 27, [])
        self.assertEqual(browser.poll, 2)

    def test_product_add_click_waits_for_an_unobstructed_center(self) -> None:
        tree = ast.parse(self.source, filename=str(CART_CONTROLS_E2E))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"add_product_from_detail", "click_at_center"}
        }
        self.assertIn("click_at_center", functions)
        self.assertIn("add_product_from_detail", functions)
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "click_at_center"
                and len(node.args) == 2
                for node in ast.walk(functions["add_product_from_detail"])
            ),
            "product add must use the guarded center click instead of Selenium auto-scrolling",
        )

        class Element:
            clicked = False

            def click(self) -> None:
                if not driver.unobstructed:
                    raise AssertionError("the click target is still covered by the fixed mobile UI")
                self.clicked = True

        class Driver:
            unobstructed = False
            checks = 0

            def execute_script(self, script, _element):
                if "scrollIntoView" in script:
                    self.scrolled = True
                    return None
                if "elementFromPoint" in script:
                    self.checks += 1
                    return self.unobstructed
                raise AssertionError("click helper ran an unexpected browser script")

        driver = Driver()
        element = Element()

        class UnobstructedWait:
            def __init__(self, _driver, _timeout, **_kwargs) -> None:
                pass

            def until(self, predicate, message=""):
                if predicate(driver):
                    return True
                driver.unobstructed = True
                if predicate(driver):
                    return True
                raise AssertionError(message or "the target center never became unobstructed")

        module = ast.Module(body=[functions["click_at_center"]], type_ignores=[])
        namespace = {"WebDriverWait": UnobstructedWait}
        exec(compile(ast.fix_missing_locations(module), str(CART_CONTROLS_E2E), "exec"), namespace)
        namespace["click_at_center"](driver, element)
        self.assertTrue(driver.scrolled)
        self.assertEqual(driver.checks, 2)
        self.assertTrue(element.clicked)

    def run_add_button_wait(self, batches):
        """Execute the real readiness block with deterministic DOM replacements."""
        tree = ast.parse(self.source)
        add = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == "add_product_from_detail")
        start = next(i for i, node in enumerate(add.body)
                     if ast.unparse(node) == "mark_substage('add_button_wait')")
        end = next(i for i, node in enumerate(add.body)
                   if ast.unparse(node) == "mark_substage('add_button_click')")
        test = self

        class Browser:
            def find_elements(self, by, selector):
                test.assertEqual((by, selector), (
                    "css selector", 'button[data-ps-ref="add-to-cart"]',
                ))
                return next(batches)

        class PollingWait:
            def __init__(self, browser, timeout):
                test.assertEqual(timeout, 20)
                self.browser = browser

            def until(self, predicate, message=""):
                for _ in range(3):
                    result = predicate(self.browser)
                    if result:
                        return result
                raise TimeoutError(message)

        namespace = {
            "driver": Browser(),
            "By": SimpleNamespace(CSS_SELECTOR="css selector"),
            "WebDriverWait": PollingWait,
            "StaleElementReferenceException": StaleButtonError,
            "mark_substage": lambda _name: None,
        }
        module = ast.Module(body=add.body[start:end], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), str(CART_CONTROLS_E2E), "exec"), namespace)
        return namespace["button"]

    def test_product_add_reacquires_button_after_stale_readiness_probe(self) -> None:
        for stale_probe in ("is_displayed", "is_enabled"):
            with self.subTest(stale_probe=stale_probe):
                class ReplacedButton:
                    def is_displayed(self):
                        if stale_probe == "is_displayed":
                            raise StaleButtonError("product refreshed")
                        return True

                    def is_enabled(self):
                        raise StaleButtonError("product refreshed")

                fresh = SimpleNamespace(is_displayed=lambda: True, is_enabled=lambda: True)
                self.assertIs(
                    self.run_add_button_wait(iter([[ReplacedButton()], [fresh]])), fresh,
                )

    def test_product_add_still_times_out_when_button_never_becomes_ready(self) -> None:
        hidden = SimpleNamespace(is_displayed=lambda: False, is_enabled=lambda: True)
        disabled = SimpleNamespace(is_displayed=lambda: True, is_enabled=lambda: False)
        with self.assertRaisesRegex(TimeoutError, "no active add-to-cart button"):
            self.run_add_button_wait(iter([[], [hidden], [disabled]]))

    def test_continue_shopping_waits_until_modal_show_transition_finishes(self) -> None:
        """Bootstrap ignores dismiss clicks between visible and shown.bs.modal."""
        tree = ast.parse(self.source)
        add = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == "add_product_from_detail")
        start = next(i for i, node in enumerate(add.body)
                     if ast.unparse(node) == "mark_substage('add_button_click')")
        end = next(i for i, node in enumerate(add.body)
                   if ast.unparse(node) == "mark_substage('cart_navigation')")
        stages = []

        class Modal:
            text = "[CI ONLY]"
            displayed = True
            shown = False
            observed_shown = False

            def is_displayed(self):
                return self.displayed

            def get_attribute(self, name):
                return "true" if name == "data-cart-controls-shown" and self.observed_shown else None

            def find_element(self, *_args):
                return self

            def click(self):
                if self.shown:
                    self.displayed = False

        modal = Modal()

        class Driver:
            observing_shown = False

            def execute_script(self, script):
                self.observing_shown = "shown.bs.modal" in script

            def find_elements(self, *_args):
                return [modal]

        driver = Driver()

        class TransitionWait:
            def __init__(self, _driver, _timeout):
                pass

            def until(self, predicate, message=""):
                for poll in range(3):
                    # First poll sees the fade before Bootstrap accepts dismiss.
                    if poll:
                        modal.shown = True
                        modal.observed_shown = driver.observing_shown
                    result = predicate(driver)
                    if result:
                        return result
                raise AssertionError(message)

        namespace = {
            "driver": driver,
            "button": SimpleNamespace(click=lambda: None),
            "WebDriverWait": TransitionWait,
            "By": SimpleNamespace(CSS_SELECTOR="css selector"),
            "mark_substage": stages.append,
            "click_at_center": lambda _driver, element: element.click(),
        }
        module = ast.Module(body=add.body[start:end], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), str(CART_CONTROLS_E2E), "exec"), namespace)
        self.assertFalse(modal.displayed, "continue shopping must close the confirmed modal")
        self.assertIn("blockcart_close_wait", stages)


class StaleButtonError(Exception):
    """Stand-in for Selenium's detached element error without a browser install."""


if __name__ == "__main__":
    unittest.main()
