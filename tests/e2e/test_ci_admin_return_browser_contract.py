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
            "same_order_detail_url",
            "KURANEA-CI-",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)

    def test_has_no_state_change_email_or_refund_side_effect_path(self) -> None:
        for forbidden in (
            "controller=AdminReturn",
            "AdminReturnController",
            "Mail::Send",
            "OrderSlip",
            "refund",
            "PaymentModule",
            "curl_exec",
            "save_screenshot",
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
        self.assertNotIn("GITHUB_STEP_SUMMARY", self.source)

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


if __name__ == "__main__":
    unittest.main()
