"""Keep the unpaid customer order exercise inside isolated GitHub Actions."""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import textwrap
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urljoin, urlparse


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "fresh-install.yml"
COMPOSE = ROOT / "compose.yaml"
CHECKOUT_FLOW = ROOT / "tests" / "e2e" / "verify_ci_checkout_admin_browser.py"
CHECKOUT_ADMIN_ROUTES = ROOT / "tests" / "e2e" / "checkout_admin_routes.py"
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

    def test_checkout_route_diagnostics_are_failure_gated_and_value_encoded(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        diagnostic_step = workflow.split(
            "      - name: Diagnose Japanese order rewrite in the isolated database", 1
        )[1].split("      - name:", 1)[0]

        self.assertIn("steps.checkout_override.outcome == 'success'", diagnostic_step)
        self.assertIn("steps.checkout_customer_browser_qa.outcome == 'failure'", diagnostic_step)
        self.assertIn('MYSQL_PWD="$MARIADB_ROOT_PASSWORD"', diagnostic_step)
        self.assertIn('"$MARIADB_DATABASE"', diagnostic_step)
        self.assertIn("::notice title=ORDENOWA checkout rewrite database::", diagnostic_step)
        self.assertIn('"$route_settings_hex"', diagnostic_step)
        self.assertIn('"$japanese_order_rewrite_hex"', diagnostic_step)
        for expected in (
            "PS_REWRITING_SETTINGS",
            "PS_CANONICAL_REDIRECT",
            "PS_LANG_DEFAULT",
            "PS_DEFAULT_LANGUAGE_URL_PREFIX",
            "HEX(\\`value\\`)",
            "HEX(ml.url_rewrite)",
            "l.iso_code =",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, diagnostic_step)

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

    def test_required_checkout_outcomes_must_succeed_and_use_original_outcome(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        aggregate = workflow.split(
            "      - name: Aggregate browser QA and postal verification failures", 1
        )[1].split("      - name:", 1)[0]
        run_block = aggregate.split("        run: |\n", 1)[1]
        script = textwrap.dedent(run_block)
        outcome_sources = dict(
            re.findall(
                r"^\s*([A-Z_]+_OUTCOME): \$\{\{ steps\.([a-z0-9_]+)\.outcome \}\}$",
                aggregate,
                re.MULTILINE,
            )
        )

        required_checkout = {
            "CHECKOUT_ORDER_PERSISTENCE_OUTCOME": (
                "checkout_order_persistence",
                "checkout_order_persistence",
            ),
            "CHECKOUT_ADMIN_BROWSER_QA_OUTCOME": (
                "checkout_admin_browser_qa",
                "checkout_admin",
            ),
        }
        for variable, (step_id, _) in required_checkout.items():
            with self.subTest(variable=variable):
                self.assertEqual(outcome_sources.get(variable), step_id)

        environment = {variable: "success" for variable in outcome_sources}
        for variable, (_, aggregate_name) in required_checkout.items():
            for outcome in ("skipped", ""):
                with self.subTest(variable=variable, outcome=outcome):
                    case_environment = {**os.environ, **environment, variable: outcome}
                    result = subprocess.run(
                        ["bash", "-c", script],
                        env=case_environment,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(
                        result.returncode,
                        0,
                        f"required step {aggregate_name} with outcome {outcome!r} must fail the aggregate",
                    )
                    self.assertIn(f"{aggregate_name}={outcome}", result.stdout + result.stderr)

    def test_offline_payment_is_selected_before_order_submission(self) -> None:
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        payment_step = flow.split("def choose_delivery_and_offline_payment", 1)[1].split(
            "def place_unpaid_order", 1
        )[0]
        selection_wait = flow.split("def wait_for_offline_payment_selection", 1)[1].split(
            "def choose_delivery_and_offline_payment", 1
        )[0]

        self.assertIn("wait_for_offline_payment_selection(driver)", payment_step)
        diagnostics = flow.split("def emit_checkout_payment_diagnostics", 1)[1].split(
            "def wait_for_offline_payment_selection", 1
        )[0]
        self.assertIn("option.is_selected()", diagnostics)
        self.assertIn("selected_modules", diagnostics)
        self.assertIn("WebDriverWait", selection_wait)
        self.assertIn("TimeoutException", selection_wait)
        self.assertIn("emit_checkout_payment_diagnostics(driver)", selection_wait)

    def test_legacy_admin_order_detail_route_rejects_invoice_and_download_links(self) -> None:
        self.assertTrue(
            CHECKOUT_ADMIN_ROUTES.is_file(),
            "legacy order detail URL matching must be isolated in a testable route helper",
        )
        spec = spec_from_file_location("checkout_admin_routes", CHECKOUT_ADMIN_ROUTES)
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        route_helper = module_from_spec(spec)
        spec.loader.exec_module(route_helper)
        is_detail = route_helper.is_legacy_admin_order_detail_url

        detail = (
            "http://localhost/admin/index.php?controller=AdminOrders&vieworder"
            "&id_order=42&token=ci-token"
        )
        invoice = (
            "http://localhost/admin/index.php?controller=AdminPdf"
            "&submitAction=generateInvoicePDF&id_order=42"
        )
        download = (
            "http://localhost/admin/index.php?controller=AdminOrders"
            "&id_order=42&submitAction=downloadInvoice"
        )
        bare_order_id = (
            "http://localhost/admin/index.php?controller=AdminOrders&id_order=42"
        )
        wrong_order = (
            "http://localhost/admin/index.php?controller=AdminOrders&vieworder"
            "&id_order=420&token=ci-token"
        )

        self.assertTrue(is_detail(detail, 42))
        self.assertFalse(is_detail(invoice, 42))
        self.assertFalse(is_detail(download, 42))
        self.assertFalse(is_detail(bare_order_id, 42))
        self.assertFalse(is_detail(wrong_order, 42))

        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        self.assertIn("is_legacy_admin_order_detail_url(href, order_id)", flow)

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

    def test_checkout_cart_uses_hummingbird_controls_and_safe_state_diagnostics(self) -> None:
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        compose = COMPOSE.read_text(encoding="utf-8")
        customer_step = workflow.split(
            "- name: Verify browser customer search, Japan checkout, and unpaid offline order", 1
        )[1].split("- name:", 1)[0]
        add_to_cart_template = (
            ROOT / "themes" / "hummingbird" / "templates" / "catalog" / "_partials"
            / "product-add-to-cart.tpl"
        ).read_text(encoding="utf-8")
        blockcart_template = (
            ROOT / "themes" / "hummingbird" / "modules" / "ps_shoppingcart" / "modal.tpl"
        ).read_text(encoding="utf-8")
        add_cart = flow.split("def add_product_and_open_checkout", 1)[1].split(
            "def register_checkout_account", 1
        )[0]
        self.assertIn("def emit_checkout_cart_diagnostics", flow)
        self.assertIn("PS_DOMAIN: localhost:${SHOP_PORT:-8080}", compose)
        self.assertIn("SHOP_BASE_URL: http://localhost:18080", customer_step)
        self.assertIn('data-ps-ref="add-to-cart"', add_to_cart_template)
        self.assertIn('data-ps-ref="blockcart-modal"', blockcart_template)
        self.assertIn("Proceed to checkout", blockcart_template)

        diagnostics = flow.split("def emit_checkout_cart_diagnostics", 1)[1].split(
            "def add_product_and_open_checkout", 1
        )[0]
        for required in (
            'button[data-ps-ref="add-to-cart"]',
            '[data-ps-ref="blockcart-modal"]',
            ".blockcart-modal__name",
            '.modal-footer > a.btn-primary',
            'cart_product_ids == [str(PRODUCT_ID)]',
            "emit_checkout_cart_diagnostics(driver, label, operation, verified_pre_navigation_cart)",
            '"cart_product_ids": [',
            '"count": len(verified_cart_product_ids)',
            '"verified": verified_cart_product_ids == [str(PRODUCT_ID)]',
        ):
            self.assertIn(required, add_cart)
        self.assertNotIn(".add-to-cart", add_cart)
        self.assertNotIn("time.sleep", add_cart)
        for state in (
            "destination,",
            "controller,",
            "bodyPage,",
            "titleMarkers,",
            "cartProductIds,",
            "cartProductCount:",
            "emptyCart,",
            "notFound,",
            "authentication,",
            "shopHome,",
            "blockcartModalVisible:",
            "ciOnlyInCart:",
            "currentCheckoutSteps,",
        ):
            with self.subTest(state=state):
                self.assertIn(state, diagnostics)
        self.assertNotIn("document.body.innerText", diagnostics)
        self.assertNotIn("document.body.textContent", diagnostics)

    def test_checkout_cart_failure_emits_operation_and_sanitized_state_as_github_annotation(self) -> None:
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        diagnostics = flow.split("def emit_checkout_cart_diagnostics", 1)[1].split(
            "def browser_options", 1
        )[0]

        self.assertIn('"operation": operation', diagnostics)
        self.assertIn('"state": state', diagnostics)
        self.assertIn('annotation_payload = json.dumps(diagnostic_payload', diagnostics)
        self.assertIn("annotation_payload.replace(\"%\", \"%25\")", diagnostics)
        self.assertIn('"::error title=ORDENOWA checkout cart diagnostics::"', diagnostics)
        self.assertIn("print(annotation, file=sys.stdout)", diagnostics)
        for safe_state in (
            "cartProductIds",
            "pre_navigation_cart",
            "destination,",
            "controller,",
            "bodyPage,",
            "titleMarkers,",
            "emptyCart,",
            "notFound,",
            "authentication,",
            "shopHome,",
            "blockcartModalVisible",
            "ciOnlyInBlockcartModal",
            "addToCartButtons",
            "currentCheckoutSteps",
        ):
            with self.subTest(state=safe_state):
                self.assertIn(safe_state, diagnostics)
        self.assertIn('"pre_navigation_cart": pre_navigation_cart', diagnostics)
        self.assertIn("verified_pre_navigation_cart", flow)
        self.assertIn(
            "emit_checkout_cart_diagnostics(driver, label, operation, verified_pre_navigation_cart)",
            flow,
        )
        self.assertNotIn("window.location.pathname", diagnostics)
        self.assertNotIn("window.location.href", diagnostics)
        self.assertNotIn("get_attribute('href')", diagnostics)
        self.assertNotIn("driver.current_url", diagnostics)
        self.assertNotIn("title: document.title", diagnostics)
        self.assertNotIn("document.body.innerHTML", diagnostics)
        self.assertNotIn("document.body.innerText", diagnostics)
        self.assertNotIn("document.body.textContent", diagnostics)

    def test_checkout_navigation_redirect_capture_strips_queries_and_untrusted_origins(self) -> None:
        flow = CHECKOUT_FLOW.read_text(encoding="utf-8")
        self.assertIn("def checkout_order_navigation_network_diagnostics", flow)
        network_diagnostics = flow.split("def checkout_order_navigation_network_diagnostics", 1)[1].split(
            "def browser_options", 1
        )[0]
        order_navigation = flow.split('operation = "open_order_checkout"', 1)[1].split(
            'operation = "wait_for_initial_checkout_step"', 1
        )[0]

        for expected in (
            'driver.get_log("performance")',
            "Network.requestWillBeSent",
            "redirectResponse",
            "Network.responseReceived",
            '"status":',
            '"target_path":',
            '"target_same_origin":',
            '"requested_order_controller":',
            "urlparse",
            "urljoin",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, network_diagnostics)
        self.assertIn('options.set_capability("goog:loggingPrefs", {"performance": "ALL"})', flow)
        self.assertIn("clear_checkout_network_events(driver)", order_navigation)
        self.assertLess(
            order_navigation.index("clear_checkout_network_events(driver)"),
            order_navigation.index('visit(driver, BASE + "/index.php?controller=order")'),
        )
        self.assertIn('"network": checkout_order_navigation_network_diagnostics(driver)', flow)
        self.assertIn('"verified": verified_cart_product_ids == [str(PRODUCT_ID)]', flow)
        for forbidden in (
            '"headers":',
            '"body":',
            '"location":',
            '"request_url":',
            '"redirect_url":',
            '"query":',
            "driver.current_url",
            "document.body.innerHTML",
            "document.body.textContent",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, network_diagnostics)

    def test_checkout_network_diagnostics_keep_only_same_origin_paths_and_redirect_statuses(self) -> None:
        browser_path = CHECKOUT_FLOW
        tree = ast.parse(browser_path.read_text(encoding="utf-8"))
        helper_names = {
            "_safe_checkout_navigation_path",
            "_safe_checkout_http_status",
            "checkout_order_navigation_network_diagnostics",
        }
        helper_nodes = [
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in helper_names
        ]
        self.assertEqual({node.name for node in helper_nodes}, helper_names)

        namespace = {
            "BASE": "http://localhost:18080",
            "json": json,
            "re": re,
            "urljoin": urljoin,
            "urlparse": urlparse,
            "unquote": unquote,
            "parse_qs": parse_qs,
            "webdriver": SimpleNamespace(Chrome=object),
        }
        helper_module = ast.Module(body=helper_nodes, type_ignores=[])
        exec(compile(helper_module, str(browser_path), "exec"), namespace)

        opaque_path_token = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
        safe_path = namespace["_safe_checkout_navigation_path"](
            f"http://localhost:18080/customer/{opaque_path_token}"
        )
        self.assertEqual(safe_path, "/customer/redacted")
        self.assertNotIn(opaque_path_token, safe_path or "")
        self.assertEqual(
            namespace["_safe_checkout_navigation_path"](
                "http://localhost:18080/%C3%A6%C2%B3%C2%A8%C3%A6%C2%96%C2%87"
            ),
            "/%C3%A6%C2%B3%C2%A8%C3%A6%C2%96%C2%87",
        )

        order_url = "http://localhost:18080/index.php?controller=order&token=checkout-token-sentinel"
        redirected_url = (
            "http://localhost:18080/%C3%A6%C2%B3%C2%A8%C3%A6%C2%96%C2%87"
            "?customer=private-customer-sentinel"
        )
        external_url = "https://attacker.example/redirect-secret-sentinel?token=external-token-sentinel"

        def event(method: str, params: dict[str, object]) -> dict[str, str]:
            return {"message": json.dumps({"message": {"method": method, "params": params}})}

        events = [
            event(
                "Network.requestWillBeSent",
                {
                    "requestId": "navigation-request-sentinel",
                    "type": "Document",
                    "frameId": "checkout-frame-sentinel",
                    "request": {
                        "method": "GET",
                        "url": order_url,
                        "headers": {"Cookie": "session-cookie-sentinel"},
                    },
                },
            ),
            event(
                "Network.requestWillBeSent",
                {
                    "requestId": "navigation-request-sentinel",
                    "type": "Document",
                    "frameId": "checkout-frame-sentinel",
                    "request": {"method": "GET", "url": redirected_url},
                    "redirectResponse": {
                        "status": 302,
                        "headers": {
                            "Location": redirected_url,
                            "Set-Cookie": "session-cookie-sentinel",
                        },
                    },
                },
            ),
            event(
                "Network.requestWillBeSent",
                {
                    "requestId": "navigation-request-sentinel",
                    "type": "Document",
                    "frameId": "checkout-frame-sentinel",
                    "request": {"method": "GET", "url": external_url},
                    "redirectResponse": {
                        "status": 301,
                        "headers": {"Location": external_url},
                    },
                },
            ),
            event(
                "Network.responseReceived",
                {
                    "requestId": "navigation-request-sentinel",
                    "type": "Document",
                    "response": {"status": 404, "url": external_url, "headers": {}},
                },
            ),
            event(
                "Network.requestWillBeSent",
                {
                    "requestId": "iframe-document-request-sentinel",
                    "type": "Document",
                    "frameId": "iframe-frame-sentinel",
                    "request": {
                        "method": "GET",
                        "url": "http://localhost:18080/embedded/frame?token=iframe-token-sentinel",
                    },
                },
            ),
            event(
                "Network.responseReceived",
                {
                    "requestId": "iframe-document-request-sentinel",
                    "type": "Document",
                    "response": {
                        "status": 200,
                        "url": "http://localhost:18080/embedded/frame?token=iframe-token-sentinel",
                    },
                },
            ),
            event(
                "Network.requestWillBeSent",
                {
                    "requestId": "js-navigation-request-sentinel",
                    "type": "Document",
                    "frameId": "checkout-frame-sentinel",
                    "request": {
                        "method": "GET",
                        "url": redirected_url,
                        "headers": {"Cookie": "second-session-cookie-sentinel"},
                    },
                },
            ),
            event(
                "Network.responseReceived",
                {
                    "requestId": "js-navigation-request-sentinel",
                    "type": "Document",
                    "response": {"status": 404, "url": redirected_url, "headers": {}},
                },
            ),
        ]

        class FakeDriver:
            def get_log(self, name: str) -> list[dict[str, str]]:
                self.log_name = name
                return events

        fake_driver = FakeDriver()
        diagnostics = namespace["checkout_order_navigation_network_diagnostics"](fake_driver)
        rendered = json.dumps(diagnostics, sort_keys=True)

        self.assertEqual(fake_driver.log_name, "performance")
        self.assertTrue(diagnostics["available"])
        self.assertEqual(len(diagnostics["redirects"]), 2)
        self.assertEqual(diagnostics["request_path"], "/index.php")
        self.assertTrue(diagnostics["requested_order_controller"])
        self.assertEqual(diagnostics["response_status"], 404)
        self.assertEqual(
            diagnostics["response_path"],
            "/%C3%A6%C2%B3%C2%A8%C3%A6%C2%96%C2%87",
        )
        self.assertEqual(
            diagnostics["documents"],
            [
                {
                    "request_path": "/index.php",
                    "request_same_origin": True,
                    "requested_order_controller": True,
                    "response_status": 404,
                    "response_path": None,
                    "response_same_origin": False,
                },
                {
                    "request_path": "/%C3%A6%C2%B3%C2%A8%C3%A6%C2%96%C2%87",
                    "request_same_origin": True,
                    "requested_order_controller": False,
                    "response_status": 404,
                    "response_path": "/%C3%A6%C2%B3%C2%A8%C3%A6%C2%96%C2%87",
                    "response_same_origin": True,
                },
            ],
        )
        self.assertEqual(diagnostics["redirects"][0]["status"], 302)
        self.assertEqual(
            diagnostics["redirects"][0]["target_path"],
            "/%C3%A6%C2%B3%C2%A8%C3%A6%C2%96%C2%87",
        )
        self.assertTrue(diagnostics["redirects"][0]["target_same_origin"])
        self.assertEqual(diagnostics["redirects"][1]["status"], 301)
        self.assertIsNone(diagnostics["redirects"][1]["target_path"])
        self.assertFalse(diagnostics["redirects"][1]["target_same_origin"])
        for secret_marker in (
            "checkout-token-sentinel",
            "private-customer-sentinel",
            "external-token-sentinel",
            "session-cookie-sentinel",
            "second-session-cookie-sentinel",
            "attacker.example",
            "redirect-secret-sentinel",
            "navigation-request-sentinel",
            "iframe-document-request-sentinel",
            "iframe-frame-sentinel",
            "iframe-token-sentinel",
            "checkout-frame-sentinel",
            "js-navigation-request-sentinel",
        ):
            with self.subTest(secret_marker=secret_marker):
                self.assertNotIn(secret_marker, rendered)

    def test_checkout_document_navigation_capture_is_limited_to_eight_requests(self) -> None:
        browser_path = CHECKOUT_FLOW
        tree = ast.parse(browser_path.read_text(encoding="utf-8"))
        helper_names = {
            "_safe_checkout_navigation_path",
            "_safe_checkout_http_status",
            "checkout_order_navigation_network_diagnostics",
        }
        helper_nodes = [
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in helper_names
        ]
        self.assertEqual({node.name for node in helper_nodes}, helper_names)

        namespace = {
            "BASE": "http://localhost:18080",
            "json": json,
            "re": re,
            "urljoin": urljoin,
            "urlparse": urlparse,
            "unquote": unquote,
            "parse_qs": parse_qs,
            "webdriver": SimpleNamespace(Chrome=object),
        }
        exec(compile(ast.Module(body=helper_nodes, type_ignores=[]), str(browser_path), "exec"), namespace)
        events = []
        for index in range(9):
            request_id = f"document-request-id-sentinel-{index}"
            request_url = f"http://localhost:18080/document/{index}?token=document-token-sentinel-{index}"
            events.extend(
                [
                    {
                        "message": json.dumps(
                            {
                                "message": {
                                    "method": "Network.requestWillBeSent",
                                    "params": {
                                        "requestId": request_id,
                                        "type": "Document",
                                        "frameId": "checkout-frame-sentinel",
                                        "request": {"url": request_url},
                                    },
                                }
                            }
                        )
                    },
                    {
                        "message": json.dumps(
                            {
                                "message": {
                                    "method": "Network.responseReceived",
                                    "params": {
                                        "requestId": request_id,
                                        "type": "Document",
                                        "response": {"status": 200, "url": request_url},
                                    },
                                }
                            }
                        )
                    },
                ]
            )

        class FakeDriver:
            def get_log(self, name: str) -> list[dict[str, str]]:
                self.log_name = name
                return events

        diagnostics = namespace["checkout_order_navigation_network_diagnostics"](FakeDriver())
        rendered = json.dumps(diagnostics, sort_keys=True)

        self.assertEqual(len(diagnostics["documents"]), 8)
        self.assertTrue(diagnostics["truncated"])
        self.assertTrue(all(document["request_same_origin"] for document in diagnostics["documents"]))
        self.assertTrue(all(document["response_same_origin"] for document in diagnostics["documents"]))
        self.assertEqual(diagnostics["documents"][0]["request_path"], "/document/0")
        self.assertEqual(diagnostics["documents"][-1]["request_path"], "/document/7")
        for secret_marker in (
            *(f"document-request-id-sentinel-{index}" for index in range(9)),
            *(f"document-token-sentinel-{index}" for index in range(9)),
        ):
            with self.subTest(secret_marker=secret_marker):
                self.assertNotIn(secret_marker, rendered)

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
        self.assertIn('order["reference"] not in row_text and order["email"] not in row_text', admin_detail)
        self.assertIn("is_legacy_admin_order_detail_url(href, order_id)", admin_detail)
        self.assertNotIn('query.get("id_order") == [order_id]', admin_detail)
        self.assertIn('rf"/sell/orders/orders/{re.escape(order_id)}', admin_detail)
        self.assertIn("raise AssertionError", admin_detail)
        self.assertIn("matching Back Office order-list result", admin_detail)
        self.assertNotIn('return ADMIN_LOGIN + f"/sell/orders/orders/{order[\'order_id\']}/view"', admin_detail)
        self.assertNotIn("controller=AdminOrders&vieworder&id_order=", admin_detail)
        self.assertNotIn('root + "/sell/orders/orders"', admin_detail)


if __name__ == "__main__":
    unittest.main()
