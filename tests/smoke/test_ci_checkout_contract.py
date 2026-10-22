"""Keep the unpaid customer order exercise inside isolated GitHub Actions."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "fresh-install.yml"
COMPOSE = ROOT / "compose.yaml"
CHECKOUT_FLOW = ROOT / "tests" / "e2e" / "verify_ci_checkout_admin_browser.py"
STOREFRONT_FLOW = ROOT / "tests" / "e2e" / "verify_storefront_browser.py"
GATE = ROOT / "modules" / "kuraneabusinessprofile" / "src" / "Customer" / "CommerceGate.php"
SHOP_MODULE = ROOT / "modules" / "kuraneabusinessprofile" / "kuraneabusinessprofile.php"


class IsolatedCheckoutContractTests(unittest.TestCase):
    def test_checkout_bypass_is_limited_to_the_matching_disposable_github_project(self) -> None:
        gate = GATE.read_text(encoding="utf-8")
        module = SHOP_MODULE.read_text(encoding="utf-8")
        self.assertIn("function isIsolatedCiCheckoutEnabled()", gate)
        for condition in (
            "getenv('CI') === 'true'",
            "getenv('GITHUB_ACTIONS') === 'true'",
            "getenv('KURANEA_ISOLATED_CI') === '1'",
            "getenv('GITHUB_RUN_ID')",
            "getenv('GITHUB_RUN_ATTEMPT')",
            "'kuranea-ci-' . $runId . '-' . $runAttempt",
        ):
            self.assertIn(condition, gate)
        hook = module.split("public function hookActionFrontControllerInitBefore", 1)[1].split("public function ", 1)[0]
        self.assertIn("CommerceGate::isIsolatedCiCheckoutEnabled()", hook)
        self.assertIn("CommerceGate::isEnabled($profile, $this->externalAuthorizationConfirmed())", hook)

    def test_workflow_passes_only_run_scoped_ci_checkout_environment(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        compose = COMPOSE.read_text(encoding="utf-8")
        overlay = (ROOT / "tests" / "fixtures" / "ci-checkout.compose.yaml").read_text(encoding="utf-8")
        self.assertIn('CI: "false"', compose)
        self.assertIn('GITHUB_ACTIONS: "false"', compose)
        self.assertIn('KURANEA_ISOLATED_CI: "0"', compose)
        self.assertIn('CI: "true"', overlay)
        self.assertIn('GITHUB_ACTIONS: "true"', overlay)
        self.assertIn("GITHUB_RUN_ID:", overlay)
        self.assertIn("GITHUB_RUN_ATTEMPT:", overlay)
        self.assertIn("KURANEA_CI_PROJECT_NAME:", overlay)
        self.assertIn("Enable run-scoped checkout only for the isolated order browser QA", workflow)
        self.assertIn("tests/e2e/verify_ci_checkout_admin_browser.py customer", workflow)
        self.assertIn("tests/e2e/verify_ci_checkout_admin_browser.py admin", workflow)
        self.assertIn("tests.business_profile.test_admin_tab_navigation_contract", workflow)
        self.assertIn("tests.business_profile.test_admin_access_source_contract", workflow)
        self.assertIn("tests/postcode/verify_ci_browser_checkout_order.php", workflow)
        self.assertIn("ci-checkout-admin-e2e.log", workflow)
        self.assertIn("verify_storefront_browser.py", workflow, "the production checkout gate smoke test must remain active")
        self.assertNotIn("ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED=1", workflow)
        self.assertLess(
            workflow.index("Verify real product detail and cart in Chromium"),
            workflow.index("Enable run-scoped checkout only for the isolated order browser QA"),
        )
        self.assertLess(
            workflow.index("Restore the fail-closed base checkout environment"),
            workflow.index("Recheck storefront checkout stays gated after unpaid CI order QA"),
        )
        self.assertLess(
            workflow.index("Verify ORDENOWA business profile installation and admin access"),
            workflow.index("Prepare Chromium browser smoke environment"),
        )

    def test_browser_flow_uses_unpaid_native_payment_and_separate_admin_session(self) -> None:
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        order_verifier = (ROOT / "tests" / "postcode" / "verify_ci_browser_checkout_order.php").read_text(encoding="utf-8")
        for required in (
            "ps_checkpayment",
            "payment-option",
            "100-0004",
            "kuraneapostcode_search",
            "confirm-addresses",
            "order-history__cell--reference",
            "total_paid_real",
            "ADMIN_LOGIN_URL",
            "checkout-admin-order-{order['viewport']}-detail.png",
            "checkout-{label}.png",
        ):
            self.assertIn(required, flow + order_verifier)
        self.assertGreaterEqual(flow.count("webdriver.Chrome("), 2)
        self.assertIn("def run_admin_order_view()", flow)
        self.assertIn("GITHUB_RUN_ID", flow)
        self.assertIn("@example.invalid", flow)
        self.assertIn("live payment", flow.lower())

    def test_browser_checkout_explicitly_creates_a_registered_customer(self) -> None:
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        field_setup = flow.split("def prepare_required_customer_fields", 1)[1].split(
            "def search_for_product", 1
        )[0]
        account_checkbox = field_setup.split(
            'create_account = form.find_elements(By.CSS_SELECTOR, "#password-form__check")', 1
        )[1].split("password_fields =", 1)[0]

        self.assertIn("if not create_account:", account_checkbox)
        self.assertIn("raise AssertionError", account_checkbox)
        self.assertIn("account_checkbox = create_account[0]", account_checkbox)
        self.assertIn("account_checkbox.is_selected()", account_checkbox)
        self.assertIn(
            'account_label = form.find_elements(By.CSS_SELECTOR, \'label[for="password-form__check"]\')',
            account_checkbox,
        )
        self.assertIn("if not account_label:", account_checkbox)
        self.assertIn("click_at_center(driver, account_label[0])", account_checkbox)
        self.assertLess(
            account_checkbox.index("click_at_center(driver, account_label[0])"),
            account_checkbox.index("WebDriverWait(driver, 5"),
        )
        self.assertNotIn("click_at_center(driver, account_checkbox)", account_checkbox)
        self.assertIn("WebDriverWait(driver, 5", account_checkbox)

    def test_required_checkout_checkboxes_use_their_visible_label_and_assert_selection(self) -> None:
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        checkbox_helper = flow.split("def click_required_checkbox_label", 1)[1].split(
            "def prepare_required_customer_fields", 1
        )[0]
        field_setup = flow.split("def prepare_required_customer_fields", 1)[1].split(
            "def search_for_product", 1
        )[0]
        checkbox_branch = field_setup.split(
            'if field_type == "checkbox"', 1
        )[1].split('elif field_type == "radio"', 1)[0]

        self.assertIn('form.find_elements(By.CSS_SELECTOR, "label[for]")', checkbox_helper)
        self.assertIn('candidate.get_attribute("for") == checkbox_id', checkbox_helper)
        self.assertIn("candidate.is_displayed()", checkbox_helper)
        self.assertIn("click_at_center(driver, label)", checkbox_helper)
        self.assertIn("lambda _browser: checkbox.is_selected()", checkbox_helper)
        self.assertIn("click_required_checkbox_label(driver, form, field)", checkbox_branch)
        self.assertNotIn("click_at_center(driver, field)", checkbox_branch)

    def test_mobile_search_toggle_uses_a_native_webdriver_click(self) -> None:
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        search_flow = flow.split("def search_for_product", 1)[1].split(
            "def add_product_and_open_checkout", 1
        )[0]

        self.assertIn("search_toggle.click()", search_flow)
        self.assertNotIn("click_at_center(driver, search_toggle)", search_flow)

    def test_product_search_selects_the_exact_hummingbird_autocomplete_result(self) -> None:
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        fixture = (ROOT / "tests" / "postcode" / "verify_native_order_persistence.php").read_text(
            encoding="utf-8"
        )
        search_helper = flow.split("def enter_product_search_query", 1)[1].split(
            "def prepare_required_customer_fields", 1
        )[0]
        search_flow = flow.split("def search_for_product", 1)[1].split(
            "def add_product_and_open_checkout", 1
        )[0]
        self.assertIn('search.send_keys("postcode")', search_helper)
        self.assertNotIn("Keys.ENTER", search_helper)
        self.assertIn("$productName = '[CI ONLY] KURANEA postcode order ' . $suffix;", fixture)
        self.assertIn("Search::indexation(false, (int) $product->id);", fixture)
        self.assertIn("enter_product_search_query(driver)", search_flow)
        self.assertIn("ignored_exceptions=(StaleElementReferenceException,)", search_flow)
        self.assertIn('f"result_product_option_{PRODUCT_ID}"', search_flow)
        self.assertIn('product_link.get_attribute("aria-label")', search_flow)
        self.assertIn('if "[CI ONLY]" not in product_name', search_flow)
        self.assertIn('"[CI ONLY]" not in product_link.text', search_flow)
        self.assertIn("click_at_center(driver, product_link)", search_flow)
        self.assertNotIn(".product-miniature[data-id-product]", search_flow)
        self.assertNotIn("except Exception", search_helper)
        self.assertNotIn("except TimeoutException", search_helper)

    def test_product_search_navigation_matches_the_selected_suggestion_url(self) -> None:
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        search_flow = flow.split("def search_for_product", 1)[1].split(
            "def add_product_and_open_checkout", 1
        )[0]
        navigation_wait = search_flow.split("WebDriverWait(driver, 30).until(", 1)[1].split(
            'if "[CI ONLY]" not in driver.find_element', 1
        )[0]

        self.assertIn('f"result_product_option_{PRODUCT_ID}"', search_flow)
        self.assertIn('product_url = urlparse(product_link.get_attribute("href"))', search_flow)
        self.assertLess(
            search_flow.index("click_at_center(driver, product_link)"),
            search_flow.index("WebDriverWait(driver, 30).until("),
        )
        for component in ("netloc", "path", "query"):
            with self.subTest(component=component):
                self.assertIn(
                    f"urlparse(browser.current_url).{component} == product_url.{component}",
                    navigation_wait,
                )
        self.assertNotIn("driver.find_element(By.TAG_NAME, \"body\")", navigation_wait)

    def test_customer_runner_attempts_both_viewports_before_reporting_failure(self) -> None:
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        customer_runner = flow.split("def run_customer_checkouts", 1)[1].split(
            "def admin_login", 1
        )[0]

        viewport_loop = customer_runner.index(
            'for width, height, label in ((1440, 960, "desktop"), (390, 844, "mobile")):'
        )
        failure_catch = customer_runner.index("except SystemExit:")
        aggregate_failure = customer_runner.index(
            'raise SystemExit(f"isolated customer checkout failed for: {failed_viewports}")'
        )
        self.assertLess(viewport_loop, failure_catch)
        self.assertIn("failures.append(label)", customer_runner)
        self.assertGreater(aggregate_failure, failure_catch)
        self.assertIn('", ".join(failures)', customer_runner)

    def test_persisted_browser_order_requires_a_non_guest_customer(self) -> None:
        verifier = (ROOT / "tests" / "postcode" / "verify_ci_browser_checkout_order.php").read_text(encoding="utf-8")
        customer_check = verifier.split("$customer = new Customer", 1)[1].split(
            "$stage = 'unpaid ps_checkpayment order'", 1
        )[0]
        rejecting_condition = customer_check.split("if (", 1)[1].split(") {", 1)[0]

        self.assertIn("$customer->is_guest", customer_check)
        self.assertIn("|| (bool) $customer->is_guest", rejecting_condition)

    def test_browser_order_asserts_autocomplete_values_before_manual_address_edits(self) -> None:
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        address_flow = flow.split("def select_japan_address", 1)[1].split(
            "def choose_delivery_and_offline_payment", 1
        )[0]
        autocomplete_helper = flow.partition("def wait_for_autocomplete_fields")[2].partition(
            "def search_for_product"
        )[0]
        autocomplete_call = address_flow.find("wait_for_autocomplete_fields(driver, form)")
        candidate_click = address_flow.index("click_at_center(driver, candidate)")
        manual_edits = address_flow.index("for name, value in (")
        self.assertGreaterEqual(autocomplete_call, 0, "the browser must assert autocomplete fields")
        self.assertLess(candidate_click, autocomplete_call)
        self.assertLess(autocomplete_call, manual_edits)
        for field, expected in (
            ('"postcode"', '"100-0004"'),
            ('"city"', '"千代田区"'),
            ('"address1"', '"大手町"'),
        ):
            with self.subTest(field=field):
                self.assertIn(field, autocomplete_helper)
                self.assertIn(expected, autocomplete_helper)
        self.assertIn('select[name="id_state"]', autocomplete_helper)
        self.assertIn("first_selected_option.get_attribute(\"value\")", autocomplete_helper)

    def test_browser_order_persists_expected_product_quantity_and_tokyo_state(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        verifier = (ROOT / "tests" / "postcode" / "verify_ci_browser_checkout_order.php").read_text(encoding="utf-8")
        order_step = workflow.split(
            "- name: Verify saved browser orders are unpaid and retain Japan addresses", 1
        )[1].split("- name:", 1)[0]

        self.assertIn('"product_id": PRODUCT_ID', flow)
        self.assertIn('KURANEA_CI_PRODUCT_ID="$product_id"', order_step)
        for expected in (
            "getenv('KURANEA_CI_PRODUCT_ID')",
            "order_detail",
            "(int) $orderDetails[0]['product_id'] !== $productId",
            "(int) $orderDetails[0]['product_quantity'] !== 1",
            "JP-13",
            "(int) $address->id_state !== $tokyoStateId",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, verifier)

    def test_public_checkout_gate_rejects_order_path_and_controller_query(self) -> None:
        flow = STOREFRONT_FLOW.read_text(encoding="utf-8")
        gate_check = flow.split('visit(driver, "/index.php?controller=order")', 1)[1].split(
            'driver.save_screenshot', 1
        )[0]
        self.assertIn(
            'not re.search(r"(order|checkout)", urlparse(driver.current_url).path.lower())',
            gate_check,
        )
        self.assertIn(
            'and "controller=order" not in urlparse(driver.current_url).query.lower()',
            gate_check,
        )
        self.assertNotIn(
            'or "controller=order" not in urlparse(driver.current_url).query.lower()',
            gate_check,
        )

    def test_storefront_cart_contains_the_exact_ci_product_id(self) -> None:
        flow = STOREFRONT_FLOW.read_text(encoding="utf-8")
        cart_check = flow.split(
            'visit(driver, "/index.php?controller=cart&action=show")', 1
        )[1].split('driver.save_screenshot', 1)[0]

        self.assertIn(
            '[data-link-action="delete-from-cart"][data-id-product]',
            cart_check,
        )
        self.assertIn('get_attribute("data-id-product")', cart_check)
        self.assertIn('cart_product_ids == [str(PRODUCT_ID)]', cart_check)
        self.assertIn('[CI ONLY]', cart_check)

    def test_checkout_registration_and_admin_routes_follow_rendered_prestashop_flow(self) -> None:
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        registration = flow.split("def register_checkout_account", 1)[1].split("def select_japan_address", 1)[0]
        admin_detail = flow.split("def find_admin_detail_url", 1)[1].split("def run_admin_order_view", 1)[0]
        self.assertIn("#checkout-continue-form button", registration)
        self.assertNotIn("identity_main_link", registration)
        self.assertIn('ADMIN_LOGIN + "/sell/orders/orders"', admin_detail)
        self.assertIn('ADMIN_LOGIN + f"/sell/orders/orders/{order[\'order_id\']}/view"', admin_detail)
        self.assertNotIn('root + "/sell/orders/orders"', admin_detail)


if __name__ == "__main__":
    unittest.main()
