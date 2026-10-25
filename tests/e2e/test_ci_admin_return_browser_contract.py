from __future__ import annotations

import ast
import unittest
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
            "selected_state_after",
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
            "selected_state_after == next_state_id",
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
            'stage.begin(f"{transition}_select")',
            'stage.begin(f"{transition}_save")',
            'stage.begin(f"{transition}_readback")',
        ):
            self.assertIn(stage_call, transition_function)

    def test_return_list_failure_separates_navigation_from_grid_wait(self) -> None:
        for required in (
            '"return_list_navigation"',
            '"return_grid"',
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
        self.assertLess(
            list_flow.index('stage.begin("return_list_navigation")'),
            list_flow.index("visit(driver, admin_root + RETURN_LIST_SUFFIX)"),
        )
        self.assertLess(
            list_flow.index("stage.complete()"),
            list_flow.index('stage.begin("return_grid")'),
        )
        self.assertLess(
            list_flow.index('stage.begin("return_grid")'),
            list_flow.index("EC.presence_of_element_located"),
        )

        origin_guard = self.source.split("def same_admin_origin(", 1)[1].split(
            "def is_admin_path(", 1
        )[0]
        self.assertIn("candidate_hostname == expected_hostname", origin_guard)
        self.assertIn("candidate_port == expected_port", origin_guard)

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
            '"return_grid_present"',
            '"login_form_visible"',
            '"selected_state"',
            '"save_success_visible"',
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
            "token",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, payload)

        runner = self.source.split("def run_admin_return_browser(", 1)[1].split(
            "def main(", 1
        )[0]
        self.assertLess(runner.index("capture_safe_status_screenshot("), runner.index("driver.quit()"))
        self.assertLess(runner.index("report_failure_diagnostics(diagnostics)"), runner.index("driver.quit()"))

    def test_failure_screenshot_is_only_the_verified_status_control(self) -> None:
        screenshot = self.source.split(
            "def capture_safe_status_screenshot(", 1
        )[1].split("def report_failure_diagnostics(", 1)[0]
        self.assertIn("current_return_form(", screenshot)
        self.assertIn("same_order_detail_link_matches(", screenshot)
        self.assertIn("status_select.screenshot(", screenshot)
        self.assertNotIn("driver.save_screenshot", screenshot)
        self.assertNotIn("get_screenshot_as_file", screenshot)
        self.assertNotIn("page_source", screenshot)

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


if __name__ == "__main__":
    unittest.main()
