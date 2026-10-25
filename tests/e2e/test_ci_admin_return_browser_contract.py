from __future__ import annotations

import ast
import importlib.util
import math
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADMIN_RETURN_BROWSER = ROOT / "tests" / "e2e" / "verify_ci_admin_return_browser.py"
WORKFLOW = ROOT / ".github" / "workflows" / "fresh-install.yml"


class CiAdminReturnBrowserContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ADMIN_RETURN_BROWSER.is_file():
            raise AssertionError("the isolated native admin return browser flow is missing")
        cls.source = ADMIN_RETURN_BROWSER.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_requires_the_matching_isolated_run_and_paid_like_order(self) -> None:
        for required in (
            'os.environ.get("CI")',
            'os.environ.get("GITHUB_ACTIONS")',
            'os.environ.get("KURANEA_ISOLATED_CI")',
            'os.environ.get("KURANEA_CI_PROJECT_NAME")',
            'run_id = os.environ.get("GITHUB_RUN_ID", "")',
            'run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")',
            'positive_int(os.environ.get("PAID_LIKE_ORDER_ID"))',
            'expected_project_name = f"kuranea-ci-{run_id}-{run_attempt}"',
            '"KURANEA-CI-"',
            '"[CI ONLY]"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)

    def test_uses_the_pinned_modern_merchandise_return_grid_and_order_edit_form(self) -> None:
        for required in (
            '"/sell/customer-service/merchandise-return/"',
            '"merchandise_return_grid_table"',
            '"td.column-id_order_return"',
            '"td.column-id_order"',
            '"td.column-actions a[href]"',
            '"[name$=\'[order_return_state]\']"',
            '"submitAddorder_returnAndStay"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)

    def test_saves_the_current_return_state_and_checks_the_same_rma_and_order(self) -> None:
        for required in (
            "WAITING_FOR_CONFIRMATION_STATE_ID = \"1\"",
            "selected_state_before",
            "updated_state",
            "readback_state",
            "expected_order_id",
            "return_id",
            "same_order_detail_link_matches",
            "KURANEA-CI-",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)

    def test_native_admin_form_transitions_pending_return_to_package_and_restores_pending(self) -> None:
        required_calls = (
            'WAITING_FOR_PACKAGE_STATE_ID = "2"',
            "RMA_STATE_TRANSITION_PATH = (",
            "(WAITING_FOR_CONFIRMATION_STATE_ID, WAITING_FOR_PACKAGE_STATE_ID)",
            "(WAITING_FOR_PACKAGE_STATE_ID, WAITING_FOR_CONFIRMATION_STATE_ID)",
            "for previous_state_id, next_state_id in RMA_STATE_TRANSITION_PATH:",
            "save_and_verify_return_state_transition(",
            "Select(status_select).select_by_value(next_state_id)",
            "updated_state != next_state_id",
            "current_return_form(browser, admin_root, return_id, order_id, stage)",
        )
        missing_calls = [required for required in required_calls if required not in self.source]
        self.assertFalse(
            missing_calls,
            f"native return transition contract is missing expected form/readback behavior: {missing_calls}",
        )

        transition_flow = self.source.split(
            "def verify_existing_synthetic_return(", 1
        )[1].split("def run_admin_return_browser(", 1)[0]
        initial_state_check = 'initial_state = Select(status_select).first_selected_option.get_attribute("value")'
        transition_loop = "for previous_state_id, next_state_id in RMA_STATE_TRANSITION_PATH:"
        self.assertIn(initial_state_check, transition_flow)
        self.assertIn(transition_loop, transition_flow)
        if initial_state_check in transition_flow and transition_loop in transition_flow:
            self.assertLess(transition_flow.index(initial_state_check), transition_flow.index(transition_loop))
        self.assertIn('table[data-role="order-return-products"]', transition_flow)
        self.assertIn("KURANEA-CI-", transition_flow)
        self.assertIn("same_order_detail_link_matches", transition_flow)
        transition_function = self.source.split(
            "def save_and_verify_return_state_transition(", 1
        )[1].split("def verify_existing_synthetic_return(", 1)[0]
        for stage_call in (
            'stage.begin(f"{stage_name}_select")',
            'stage.begin(f"{stage_name}_save")',
            'stage.begin(f"{stage_name}_readback")',
        ):
            self.assertIn(stage_call, transition_function)

    def test_return_list_failure_separates_navigation_from_grid_wait(self) -> None:
        for required in (
            '"return_list_navigation"',
            '"return_grid"',
            '"requested_pathname"',
            '"observed_pathname"',
            '"document_response_status"',
            '"visible_error_marker"',
            'stage.begin("return_list_navigation")',
            'stage.begin("return_grid")',
            '"same_admin_origin"',
            '"admin_path_matches"',
            '"safe_page_class"',
            '"document_ready_state"',
            '"return_grid_present"',
            "def collect_safe_page_diagnostics(",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)

        list_flow = self.source.split("def find_existing_return(", 1)[1].split(
            "def same_order_detail_link_matches(", 1
        )[0]
        self.assertIn('stage.begin("return_menu_link")', list_flow)
        self.assertIn('stage.begin("return_list_navigation")', list_flow)
        self.assertIn("generated_return_menu_link(driver, admin_root, stage)", list_flow)
        self.assertIn("menu_link.click()", list_flow)
        self.assertIn('stage.begin("return_tokenless_probe")', list_flow)
        self.assertIn('stage.begin("return_tokenized_restore")', list_flow)
        self.assertIn("visit(driver, menu_url)", list_flow)
        self.assertNotIn("driver.back()", list_flow)
        self.assertIn("security_page_failure_reason(stage.tokenless_probe_classification)", list_flow)
        self.assertLess(
            list_flow.index('stage.begin("return_tokenless_probe")'),
            list_flow.index('stage.begin("return_tokenized_restore")'),
        )
        self.assertLess(
            list_flow.index('stage.begin("return_tokenized_restore")'),
            list_flow.index('stage.begin("return_grid")'),
        )
        self.assertLess(
            list_flow.index('stage.begin("return_grid")'),
            list_flow.index("EC.presence_of_element_located"),
        )
        self.assertIn("collect_safe_page_diagnostics(stage, driver, admin_root)", list_flow)
        self.assertIn("reject_security_page_signal(stage.compromised_page_classification)", list_flow)
        self.assertIn("stage.safe_page_class != \"admin_return_list\"", list_flow)
        self.assertIn(
            "token_comparison_classification(\n        stage.tokenless_probe_classification,\n        stage.tokenized_restore_classification,",
            list_flow,
        )
        self.assertIn('if stage.token_comparison == "inconclusive":', list_flow)
        self.assertLess(
            list_flow.index('if stage.token_comparison == "inconclusive":'),
            list_flow.index('stage.begin("return_grid")'),
            "an unresolved token comparison must fail before waiting for the return grid",
        )
        self.assertLess(
            list_flow.index('if stage.token_comparison == "inconclusive":'),
            list_flow.index("EC.presence_of_element_located"),
        )

        origin_guard = self.source.split("def same_admin_origin(", 1)[1].split(
            "def is_admin_path(", 1
        )[0]
        self.assertIn("candidate_hostname == expected_hostname", origin_guard)
        self.assertIn("candidate_port == expected_port", origin_guard)

    def test_safe_navigation_diagnostics_preserve_routes_and_redact_dynamic_values(self) -> None:
        helper_path = ROOT / "tests" / "e2e" / "safe_admin_browser_diagnostics.py"
        self.assertTrue(helper_path.is_file(), "safe route diagnostic helpers are missing")
        spec = importlib.util.spec_from_file_location("safe_admin_browser_diagnostics", helper_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)

        safe_path = helper.safe_admin_pathname(
            "http://localhost:18080/admin-kuranea/index.php/sell/customer-service/"
            "merchandise-return/98765/edit/?token=private-query-value",
            "http://localhost:18080/admin-kuranea",
        )
        self.assertEqual(
            safe_path,
            "/admin-kuranea/index.php/sell/customer-service/merchandise-return/<id>/edit/",
        )
        self.assertNotIn("private-query-value", safe_path)
        self.assertEqual(
            helper.safe_admin_pathname(
                "http://localhost:18080/admin-kuranea/security/compromised?token=private-token-sentinel",
                "http://localhost:18080/admin-kuranea",
            ),
            "/admin-kuranea/security/compromised",
        )
        self.assertEqual(
            helper.safe_admin_pathname(
                "http://localhost:18080/admin-kuranea/" + "a" * 32 + "/index.php/",
                "http://localhost:18080/admin-kuranea",
            ),
            "/admin-kuranea/<redacted>/index.php/",
        )
        self.assertEqual(
            helper.safe_admin_pathname(
                "http://localhost:18080/admin-kuranea/customer-name/orders/",
                "http://localhost:18080/admin-kuranea",
            ),
            "/admin-kuranea/<redacted>/orders/",
        )
        self.assertEqual(
            helper.safe_admin_pathname(
                "http://localhost:18080/customer-name/profile/",
                "http://localhost:18080/admin-kuranea",
            ),
            "same_origin_non_admin",
        )
        self.assertEqual(
            helper.safe_admin_pathname(
                "https://example.invalid/private/customer/name",
                "http://localhost:18080/admin-kuranea",
            ),
            "outside_admin",
        )

        self.assertEqual(helper.safe_document_response_status(200), "200")
        self.assertEqual(helper.safe_document_response_status(404), "404")
        for unavailable in (None, 0, "200", True, 99, 600, math.nan, math.inf):
            with self.subTest(unavailable=unavailable):
                self.assertEqual(helper.safe_document_response_status(unavailable), "unknown")

    def test_compromised_route_and_native_fixture_marker_are_classified_without_page_data(self) -> None:
        helper_path = ROOT / "tests" / "e2e" / "admin_return_navigation.py"
        self.assertTrue(helper_path.is_file(), "safe tokenized return-navigation helpers are missing")
        spec = importlib.util.spec_from_file_location("admin_return_navigation", helper_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)

        class MarkerParser(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.found = False

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                self.found = self.found or dict(attrs).get("id") == "security-compromised-page"

        fixture = (ROOT / "tests" / "fixtures" / "prestashop-9.2-security-compromised.html").read_text(
            encoding="utf-8"
        )
        parser = MarkerParser()
        parser.feed(fixture)
        self.assertTrue(parser.found, "the pinned PrestaShop fixture should contain the native marker")

        diagnostic = helper.compromised_page_facts(
            "http://localhost:18080/admin-kuranea/security/compromised?token=private-token-sentinel",
            "http://localhost:18080/admin-kuranea",
            parser.found,
        )
        self.assertEqual(
            diagnostic,
            {
                "static_path_matches": True,
                "page_marker_present": True,
                "classification": "prestashop_security_compromised",
            },
        )
        self.assertNotIn("private-token-sentinel", repr(diagnostic))
        self.assertEqual(
            helper.compromised_page_facts(
                "http://localhost:18080/admin-kuranea/sell/customer-service/merchandise-return/",
                "http://localhost:18080/admin-kuranea",
                parser.found,
            )["classification"],
            "security_marker_off_path",
        )
        self.assertEqual(
            helper.compromised_page_facts(
                "http://localhost:18080/admin-kuranea/security/compromised/",
                "http://localhost:18080/admin-kuranea",
                False,
            )["classification"],
            "security_path_without_marker",
        )
        self.assertFalse(
            helper.compromised_page_facts(
                "http://localhost:18080/admin-kuranea/security/compromised//",
                "http://localhost:18080/admin-kuranea",
                parser.found,
            )["static_path_matches"]
        )

    def test_generated_return_menu_link_requires_exact_origin_route_and_one_session_token(self) -> None:
        helper_path = ROOT / "tests" / "e2e" / "admin_return_navigation.py"
        self.assertTrue(helper_path.is_file(), "safe tokenized return-navigation helpers are missing")
        spec = importlib.util.spec_from_file_location("admin_return_navigation", helper_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        admin_root = "http://localhost:18080/admin-kuranea"
        secret = "generated-session-token-sentinel"
        for pathname, expected in (
            ("/admin-kuranea/sell/customer-service/merchandise-return", True),
            ("/admin-kuranea/sell/customer-service/merchandise-return/", True),
            ("/admin-kuranea/sell/customer-service/merchandise-return///", False),
            ("/admin-kuranea/sell/customer-service/merchandise-return/extra", False),
            ("/admin-kuranea/index.php/sell/customer-service/merchandise-return/", False),
        ):
            with self.subTest(pathname=pathname):
                self.assertEqual(helper.return_list_path_matches(pathname, admin_root), expected)

        for token_parameter in ("token", "_token"):
            with self.subTest(token_parameter=token_parameter):
                href = (
                    "http://localhost:18080/admin-kuranea/sell/customer-service/"
                    f"merchandise-return/?{token_parameter}={secret}"
                )
                facts = helper.return_menu_link_facts(href, admin_root)
                self.assertEqual(
                    facts,
                    {
                        "same_origin": True,
                        "admin_path": True,
                        "return_path": True,
                        "session_token_present": True,
                        "valid": True,
                    },
                )
                self.assertNotIn(secret, repr(facts))

        invalid_links = (
            "http://localhost:18080/admin-kuranea/sell/customer-service/merchandise-return/",
            "http://localhost:18080/admin-kuranea/sell/customer-service/merchandise-return/?token=",
            "http://localhost:18080/admin-kuranea/sell/customer-service/merchandise-return/?token=a&token=b",
            "http://localhost:18080/admin-kuranea/sell/customer-service/merchandise-return/?token=a&_token=b",
            "http://localhost:18080/admin-kuranea/sell/customer-service/merchandise-return///?token=a",
            "http://outside.example/admin-kuranea/sell/customer-service/merchandise-return/?token=a",
            "http://localhost:18080/admin-kuranea/sell/customer-service/merchandise-return/extra?token=a",
            "http://localhost:18080/admin-kuranea/sell/orders/?token=a",
            "http://user@localhost:18080/admin-kuranea/sell/customer-service/merchandise-return/?token=a",
        )
        for href in invalid_links:
            with self.subTest(href_without_query=href.split("?", 1)[0]):
                self.assertFalse(helper.return_menu_link_facts(href, admin_root)["valid"])

    def test_token_route_comparison_accepts_clear_pages_and_compares_restored_menu_result(self) -> None:
        helper_path = ROOT / "tests" / "e2e" / "admin_return_navigation.py"
        spec = importlib.util.spec_from_file_location("admin_return_navigation", helper_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)

        cases = (
            (
                "prestashop_security_compromised",
                "none",
                "prestashop_security_compromised",
                "admin_return_list",
                "tokenless_compromised_tokenized_clear",
            ),
            ("none", "none", "admin_return_list", "admin_return_list", "tokenless_clear_tokenized_clear"),
            (
                "prestashop_security_compromised",
                "prestashop_security_compromised",
                "prestashop_security_compromised",
                "prestashop_security_compromised",
                "tokenless_compromised_tokenized_compromised",
            ),
            (
                "none",
                "prestashop_security_compromised",
                "admin_return_list",
                "prestashop_security_compromised",
                "tokenless_clear_tokenized_compromised",
            ),
            (
                "security_path_without_marker",
                "none",
                "security_path_without_marker",
                "admin_return_list",
                "inconclusive",
            ),
            ("none", "none", "admin_login", "admin_return_list", "tokenless_login_tokenized_clear"),
            ("none", "none", "other_admin", "admin_return_list", "tokenless_other_admin_tokenized_clear"),
            ("none", "none", "unknown", "admin_return_list", "inconclusive"),
        )
        for tokenless, tokenized, tokenless_page, tokenized_page, expected in cases:
            with self.subTest(tokenless=tokenless, tokenized=tokenized):
                self.assertEqual(
                    helper.token_comparison_classification(
                        tokenless,
                        tokenized,
                        tokenless_page,
                        tokenized_page,
                    ),
                    expected,
                )

        list_flow = self.source.split("def find_existing_return(", 1)[1].split(
            "def same_order_detail_link_matches(", 1
        )[0]
        self.assertIn("stage.tokenized_restore_classification,", list_flow)

    def test_only_exact_native_compromised_route_uses_native_warning_failure(self) -> None:
        helper_path = ROOT / "tests" / "e2e" / "admin_return_navigation.py"
        spec = importlib.util.spec_from_file_location("admin_return_navigation", helper_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)

        self.assertEqual(helper.security_page_failure_reason("none"), "clear")
        self.assertEqual(
            helper.security_page_failure_reason("prestashop_security_compromised"),
            "native_compromised_page",
        )
        for classification in ("security_path_without_marker", "security_marker_off_path"):
            with self.subTest(classification=classification):
                self.assertEqual(
                    helper.security_page_failure_reason(classification),
                    "security_signal_mismatch",
                )

        rejection = self.source.split("def reject_security_page_signal(", 1)[1].split(
            "def collect_safe_page_diagnostics(", 1
        )[0]
        self.assertIn('failure_reason == "native_compromised_page"', rejection)
        self.assertIn("raise PrestaShopSecurityCompromisedPageError", rejection)
        self.assertIn('failure_reason == "security_signal_mismatch"', rejection)
        self.assertIn("raise CompromisedPageSignalMismatchError", rejection)

    def test_state_readback_requires_post_document_and_a_fresh_get(self) -> None:
        transition_function = self.source.split(
            "def save_and_verify_return_state_transition(", 1
        )[1].split("def verify_existing_synthetic_return(", 1)[0]
        for required in (
            'pre_save_document_time_origin = driver.execute_script("return performance.timeOrigin")',
            'browser.execute_script("return performance.timeOrigin") != pre_save_document_time_origin',
            'if (form.get_attribute("method") or "").upper() != "POST":',
            'if not is_admin_origin(action_url, admin_root):',
            "EC.staleness_of(form)",
            "new_post_save_document_observed",
            "save_success_visible",
            "visit(driver, edit_url)",
            "fresh_get_completed",
            "readback_state",
            "target_rma_matches",
            "target_order_matches",
            "order_detail_link_matches",
        ):
            with self.subTest(required=required):
                self.assertIn(required, transition_function)
        self.assertIn("original_state_restored", self.source)
        self.assertIn("stage.initial_state = stage.selected_state", self.source)
        self.assertIn("stage.requested_pathname = safe_admin_pathname(edit_url, admin_root)", self.source)
        self.assertIn("stage.requested_pathname = safe_admin_pathname(action_url, admin_root)", self.source)
        self.assertIn('".page-not-found, [data-error-page]"', self.source)

    def test_status_change_emails_are_confined_to_the_run_owned_mailpit(self) -> None:
        mailpit_setup = self.workflow.split("id: mailpit_setup", 1)[1].split("- name:", 1)[0]
        admin_step = self.workflow.split(
            "- name: Verify native admin return state form in Chromium", 1
        )[1].split("- name:", 1)[0]

        self.assertIn("axllent/mailpit:v1.31.6", mailpit_setup)
        self.assertIn('mailpit_name="${CI_COMPOSE_PROJECT_NAME}-mailpit"', mailpit_setup)
        self.assertIn('--name "$mailpit_name"', mailpit_setup)
        self.assertIn('--network "${CI_COMPOSE_PROJECT_NAME}_default"', mailpit_setup)
        self.assertIn('--publish 127.0.0.1:8025:8025', mailpit_setup)
        self.assertIn('"PS_MAIL_SERVER" => "mailpit"', mailpit_setup)
        self.assertIn('"PS_MAIL_SMTP_PORT" => 1025', mailpit_setup)
        self.assertIn("Configuration::get($key)", mailpit_setup)
        self.assertIn("GITHUB_RUN_ID: ${{ github.run_id }}", admin_step)
        self.assertIn("GITHUB_RUN_ATTEMPT: ${{ github.run_attempt }}", admin_step)
        self.assertIn("PAID_LIKE_ORDER_ID: ${{ steps.order_lifecycle_fixture.outputs.paid_like_order_id }}", admin_step)
        self.assertLess(
            self.workflow.index("id: mailpit_setup"),
            self.workflow.index("- name: Verify native admin return state form in Chromium"),
        )
        self.assertNotIn("PaymentModule", self.source)
        self.assertNotIn("OrderSlip", self.source)
        self.assertNotIn("refund", self.source.lower())

    def test_has_no_state_change_email_or_refund_side_effect_path(self) -> None:
        for forbidden in (
            "controller=AdminReturn",
            "AdminReturnController",
            "Mail::Send",
            "OrderSlip",
            "refund",
            "PaymentModule",
            "curl_exec",
            "driver.save_screenshot",
            "driver.get_screenshot_as_file",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.source)

    def test_console_output_is_static_and_contains_no_runtime_identifiers(self) -> None:
        output_calls = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ]
        self.assertTrue(output_calls, "the browser flow should report a static result")
        for call in output_calls:
            with self.subTest(call=ast.unparse(call)):
                self.assertTrue(call.args)
                self.assertTrue(
                    all(isinstance(argument, ast.Constant) and isinstance(argument.value, str)
                        for argument in call.args),
                    "browser diagnostics must not interpolate credentials, emails, IDs, or URLs",
                )
    def test_failure_diagnostics_are_allowlisted_and_reach_summary_and_annotation(self) -> None:
        for required in (
            "SAFE_DIAGNOSTIC_STAGES = (",
            '"admin_login"',
            '"return_list_navigation"',
            '"return_grid"',
            '"target_rma"',
            '"edit_screen"',
            "EXCEPTION_CLASS_ALLOWLIST = (",
            'SAFE_FALLBACK_EXCEPTION_CLASS_NAME = "UnexpectedError"',
            '"last_completed_stage"',
            '"failure_stage"',
            '"exception_class"',
            '"target_order_matches"',
            '"order_detail_link_matches"',
            '"target_rma_matches"',
            '"same_admin_origin"',
            '"admin_path_matches"',
            '"safe_page_class"',
            '"document_ready_state"',
            '"requested_pathname"',
            '"observed_pathname"',
            '"document_response_status"',
            '"visible_error_marker"',
            '"compromised_static_path_matches"',
            '"compromised_page_marker_present"',
            '"compromised_page_marker_visible"',
            '"compromised_page_classification"',
            '"compromised_page_screenshot_captured"',
            '"compromised_page_screenshot_stage"',
            '"compromised_page_screenshot_captured"',
            '"compromised_page_screenshot_stage"',
            '"return_grid_present"',
            '"return_menu_link_session_token_present"',
            '"tokenless_probe_classification"',
            '"tokenless_probe_page_marker_visible"',
            '"tokenless_probe_page_class"',
            '"tokenized_menu_classification"',
            '"tokenized_restore_classification"',
            '"token_comparison"',
            '"login_form_visible"',
            '"selected_state"',
            '"save_success_visible"',
            '"original_state_restored"',
            '"transition_results"',
            "def safe_exception_class_name(",
            "def build_safe_diagnostics(",
            "def report_failure_diagnostics(",
            'os.environ.get("GITHUB_STEP_SUMMARY")',
            '"::error title=ORDENOWA admin RMA browser::"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)

        payload = self.source.split("def build_safe_diagnostics(", 1)[1].split(
            "def capture_safe_status_screenshot(", 1
        )[0]
        for forbidden in (
            "current_url",
            "page_source",
            "ADMIN_MAIL",
            "ADMIN_PASSWD",
            "exception_text",
            "traceback",
            "email",
            "address",
            "customer_name",
            "return_id",
            "order_id",
            "token_value",
            '"href"',
            '"query"',
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, payload)

        runner = self.source.split("def run_admin_return_browser(", 1)[1].split(
            "def main(", 1
        )[0]
        self.assertLess(runner.index("capture_safe_status_screenshot("), runner.index("driver.quit()"))
        self.assertLess(runner.index("report_failure_diagnostics(diagnostics)"), runner.index("driver.quit()"))
        self.assertIn("report_success_diagnostics(stage)", runner)
        coverage = self.workflow.split(
            "- name: Verify browser QA screenshot coverage", 1
        )[1].split("- name:", 1)[0]
        for required in (
            "requested_pathname", "observed_pathname", "document_response_status",
            "transition_results", "safe_path_pattern", "new_post_save_document_observed",
        ):
            with self.subTest(required=required):
                self.assertIn(required, coverage)

    def test_failure_screenshots_are_limited_to_verified_status_or_native_warning_elements(self) -> None:
        screenshot = self.source.split(
            "def capture_safe_status_screenshot(", 1
        )[1].split("def report_failure_diagnostics(", 1)[0]
        self.assertIn("current_return_form(", screenshot)
        self.assertIn("same_order_detail_link_matches(", screenshot)
        self.assertIn("status_select.screenshot(", screenshot)
        self.assertNotIn("driver.save_screenshot", screenshot)
        self.assertNotIn("get_screenshot_as_file", screenshot)
        self.assertNotIn("page_source", screenshot)

        compromised = self.source.split(
            "def capture_safe_compromised_page_screenshot(", 1
        )[1].split("def transition_evidence_lines(", 1)[0]
        for required in (
            "stage.compromised_static_path_matches",
            "stage.compromised_page_marker_present",
            'stage.compromised_page_classification != "prestashop_security_compromised"',
            "driver.find_elements(By.ID, SECURITY_COMPROMISED_PAGE_ID)",
            "visible_page_elements[0]",
            "page_element.screenshot(str(screenshot_path))",
            "stage.compromised_page_marker_visible",
        ):
            with self.subTest(required=required):
                self.assertIn(required, compromised)
        self.assertNotIn("driver.save_screenshot", compromised)
        self.assertNotIn("page_source", compromised)
        self.assertNotIn("stage.target_rma_matches = False", screenshot)
        self.assertIn("screenshot_observation = StageTracker()", screenshot)

    def test_fresh_install_runs_native_admin_return_before_lifecycle_readback(self) -> None:
        self.assertIn("- name: Verify native admin return state form in Chromium", self.workflow)
        admin_step = self.workflow.split(
            "- name: Verify native admin return state form in Chromium", 1
        )[1].split("- name:", 1)[0]
        lifecycle_step = self.workflow.split(
            "- name: Verify native order cancellation, return, and credit-slip behavior", 1
        )[1].split("- name:", 1)[0]
        aggregate = self.workflow.split(
            "- name: Aggregate browser QA and postal verification failures", 1
        )[1]
        self.assertIn("id: order_return_admin_browser", admin_step)
        self.assertIn("verify_ci_admin_return_browser.py", admin_step)
        self.assertIn("steps.order_return_browser.outcome == 'success'", admin_step)
        self.assertIn("continue-on-error: true", admin_step)
        self.assertLess(
            self.workflow.index("- name: Submit customer return request in Chromium"),
            self.workflow.index("- name: Verify native admin return state form in Chromium"),
        )
        self.assertLess(
            self.workflow.index("- name: Verify native admin return state form in Chromium"),
            self.workflow.index("- name: Verify native order cancellation, return, and credit-slip behavior"),
        )
        self.assertIn(
            "KURANEA_CI_ADMIN_RETURN_BROWSER_OUTCOME: ${{ steps.order_return_admin_browser.outcome }}",
            lifecycle_step,
        )
        self.assertIn("order_return_admin_browser=$ORDER_RETURN_ADMIN_BROWSER_OUTCOME", aggregate)
        self.assertIn("ORDER_RETURN_ADMIN_BROWSER_OUTCOME: ${{ steps.order_return_admin_browser.outcome }}", aggregate)
        self.assertIn("tests.e2e.test_ci_admin_return_browser_contract", self.workflow)
        coverage = self.workflow.split(
            "- name: Verify browser QA screenshot coverage", 1
        )[1].split("- name:", 1)[0]
        self.assertIn('if [[ "$ORDENOWA_ADMIN_RETURN_FOCUS" == true ]]; then', coverage)
        self.assertIn("admin-return-e2e.log", coverage)
        self.assertIn("admin-return-diagnostics.json", coverage)
        self.assertIn("admin-return-state-control.png", coverage)
        self.assertIn("admin-return-security-compromised.png", coverage)
        self.assertIn("compromised_page_screenshot_captured", coverage)

    def test_return_navigation_uses_generated_session_link_and_classifies_tokenless_probe_before_grid(self) -> None:
        for required in (
            "return_menu_link_facts",
            '"#nav-sidebar a[href]"',
            "stage.begin(\"return_menu_link\")",
            "stage.begin(\"return_list_navigation\")",
            "menu_link.click()",
            "visit(driver, menu_url)",
            '"generated_href"',
            "stage.begin(\"return_tokenless_probe\")",
            "tokenless_url = admin_root + RETURN_LIST_SUFFIX",
            "copy_tokenless_probe_diagnostics(stage)",
            "stage.begin(\"return_tokenized_restore\")",
            "visit(driver, menu_url)",
            "tokenless_probe_page_class",
            "token_comparison_classification",
            'stage.begin("return_grid")',
            "PrestaShopSecurityCompromisedPageError",
            "CompromisedPageSignalMismatchError",
            "TokenRouteComparisonInconclusiveError",
            'By.ID, SECURITY_COMPROMISED_PAGE_ID',
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)

        navigation = self.source.split("def find_existing_return(", 1)[1].split(
            "def same_order_detail_link_matches(", 1
        )[0]
        tokenless_probe = navigation.index('stage.begin("return_tokenless_probe")')
        restore = navigation.index('stage.begin("return_tokenized_restore")')
        grid_wait = navigation.index('stage.begin("return_grid")')
        self.assertLess(tokenless_probe, restore)
        self.assertLess(restore, grid_wait)
        self.assertIn("reject_security_page_signal(stage.compromised_page_classification)", navigation)
        self.assertIn("token_comparison_classification(", navigation)
        self.assertIn("stage.safe_page_class != \"admin_return_list\"", navigation)

        workflow = self.workflow.split(
            "- name: Verify browser QA screenshot coverage", 1
        )[1].split("- name:", 1)[0]
        self.assertIn("compromised_static_path_matches", workflow)
        self.assertIn("return_menu_link_session_token_present", workflow)
        self.assertIn("tokenless_probe_classification", workflow)
        self.assertIn("tokenless_probe_page_class", workflow)
        self.assertIn("tokenized_menu_classification", workflow)
        self.assertIn("token_comparison", workflow)
        self.assertIn("tokenless_login_tokenized_clear", workflow)
        self.assertIn("TokenRouteComparisonInconclusiveError", workflow)
        self.assertIn("native_compromised_page_visible", workflow)
        self.assertIn("tokenless_marker_visible=True", workflow)


if __name__ == "__main__":
    unittest.main()
