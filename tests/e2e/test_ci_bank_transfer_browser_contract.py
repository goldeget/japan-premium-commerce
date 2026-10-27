from pathlib import Path
import ast
import contextlib
import importlib.util
import io
import re
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
BROWSER = ROOT / "tests" / "e2e" / "verify_ci_bank_transfer_browser.py"
PREPARE = ROOT / "tests" / "business_profile" / "prepare_ci_bank_transfer_fixture.php"
UNPAID_READBACK = ROOT / "tests" / "business_profile" / "verify_ci_bank_transfer_unpaid_order.php"
PAID_READBACK = ROOT / "tests" / "business_profile" / "verify_ci_bank_transfer_persistence.php"
LIMITED_ACCESS = ROOT / "tests" / "business_profile" / "verify_ci_limited_transfer_access.php"
SECURITY_FIXTURE = ROOT / "tests" / "business_profile" / "seed_security_fixtures.php"
TRANSFER_CONTROLLER = ROOT / "modules" / "kuraneabusinessprofile" / "controllers" / "admin" / "AdminBusinessProfileTransfersController.php"


class CiBankTransferBrowserContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.browser = BROWSER.read_text(encoding="utf-8")
        cls.prepare = PREPARE.read_text(encoding="utf-8")
        cls.unpaid_readback = UNPAID_READBACK.read_text(encoding="utf-8") if UNPAID_READBACK.exists() else ""
        cls.paid_readback = PAID_READBACK.read_text(encoding="utf-8")
        cls.limited_access = LIMITED_ACCESS.read_text(encoding="utf-8") if LIMITED_ACCESS.exists() else ""
        cls.security_fixture = SECURITY_FIXTURE.read_text(encoding="utf-8")
        cls.controller = TRANSFER_CONTROLLER.read_text(encoding="utf-8")

    def require(self, needle: str, haystack: str) -> None:
        self.assertTrue(needle in haystack, f"missing contract: {needle}")

    def load_browser_module(self) -> ModuleType:
        spec = importlib.util.spec_from_file_location("ordenowa_bank_transfer_browser", BROWSER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)

        def stub(name: str, **attributes: object) -> ModuleType:
            value = ModuleType(name)
            value.__dict__.update(attributes)
            value.__path__ = []  # type: ignore[attr-defined]
            return value

        webdriver = stub("selenium.webdriver", Chrome=object)
        by = stub(
            "selenium.webdriver.common.by",
            By=SimpleNamespace(ID="id", CSS_SELECTOR="css selector", TAG_NAME="tag name"),
        )
        exceptions = stub(
            "selenium.common.exceptions",
            StaleElementReferenceException=type("StaleElementReferenceException", (Exception,), {}),
        )
        stubs = {
            "selenium": stub("selenium", webdriver=webdriver),
            "selenium.common": stub("selenium.common"),
            "selenium.common.exceptions": exceptions,
            "selenium.webdriver": webdriver,
            "selenium.webdriver.chrome": stub("selenium.webdriver.chrome"),
            "selenium.webdriver.chrome.options": stub("selenium.webdriver.chrome.options", Options=object),
            "selenium.webdriver.common": stub("selenium.webdriver.common"),
            "selenium.webdriver.common.by": by,
            "selenium.webdriver.support": stub("selenium.webdriver.support", expected_conditions=object()),
            "selenium.webdriver.support.ui": stub("selenium.webdriver.support.ui", WebDriverWait=object),
        }
        with patch.dict(sys.modules, stubs):
            spec.loader.exec_module(module)
        return module

    def test_result_schema_accepts_isolated_gate_with_pending_seller_authorization(self) -> None:
        module = self.load_browser_module()

        self.assertNotIn("issue_seller_commerce_gate_enabled", module.SUCCESS_REQUIRED_BOOLEAN_KEYS)
        self.assertIn("issue_effective_commerce_gate_enabled", module.SUCCESS_REQUIRED_BOOLEAN_KEYS)
        result: dict[str, object] = {key: True for key in module.SAFE_RESULT_KEYS}
        result.update({
            "status": "success",
            "stage": "complete",
            "exception_type": None,
            "failure_substage": "none",
            "issue_persistence_diagnostic": "unpaid_instruction_persisted",
            "issue_failure_category": "not_run",
            "wrong_amount_notice_category": "not_run",
            "issue_seller_commerce_gate_enabled": False,
        })
        result["limited_session_route_path_index_php"] = False
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bank-transfer-result.json"
            module.write_result(output, result)
            self.assertTrue(output.is_file())
            result["limited_session_route_path_directory_root"] = False
            with self.assertRaisesRegex(ValueError, "allowlisted schema"):
                module.write_result(output, result)
            result["limited_session_route_path_directory_root"] = True
            result["issue_effective_commerce_gate_enabled"] = False
            with self.assertRaisesRegex(ValueError, "allowlisted schema"):
                module.write_result(output, result)

    def test_limited_access_helper_wrapper_reports_safe_copy_execution_and_json_stages(self) -> None:
        module = self.load_browser_module()

        def completed(returncode, stdout="", stderr="private diagnostic"):
            return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

        scenarios = (
            ([completed(1)], ["limited_access_helper_copy"]),
            ([completed(0), completed(1)], [
                "limited_access_helper_copy", "limited_access_helper_input_validation",
                "limited_access_helper_execution",
            ]),
            ([completed(0), completed(0, "not-json\n")], [
                "limited_access_helper_copy", "limited_access_helper_input_validation",
                "limited_access_helper_execution", "limited_access_helper_json_parse",
            ]),
            ([completed(0), completed(0, "[]\n")], [
                "limited_access_helper_copy", "limited_access_helper_input_validation",
                "limited_access_helper_execution", "limited_access_helper_json_parse",
                "limited_access_helper_json_shape",
            ]),
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "helper.php"
            source.write_text("<?php", encoding="utf-8")
            for responses, expected_stages in scenarios:
                stages: list[str] = []
                output = io.StringIO()
                error_output = io.StringIO()
                with patch.object(module.subprocess, "run", side_effect=responses):
                    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error_output):
                        with self.assertRaises(RuntimeError):
                            module.docker_php_json(
                                {"project": "kuranea-ci-1-1", "run_id": "1", "attempt": "1"},
                                source,
                                "/tmp/helper.php",
                                {},
                                set_substage=stages.append,
                            )
                self.assertEqual(expected_stages, stages)
                self.assertNotIn("private diagnostic", output.getvalue() + error_output.getvalue())

    def test_limited_access_helper_maps_php_failure_stage_to_safe_result_booleans(self) -> None:
        module = self.load_browser_module()
        checks = {key: False for key in module.LIMITED_ACCESS_CHECK_KEYS}
        checks["ci_scope_valid"] = False
        payload = {"status": "failure", "failure_stage": "scope_validation", "checks": checks}
        stages: list[str] = []
        diagnostics: dict[str, object] = {}
        with patch.object(module, "docker_php_json", return_value=payload):
            with self.assertRaises(RuntimeError):
                module.verify_limited_staff_access(
                    {"project": "kuranea-ci-1-1", "view_email": "opaque@example.invalid"},
                    stages.append,
                    diagnostics,
                )
        self.assertEqual("limited_access_scope_validation", stages[-1])
        self.assertFalse(diagnostics["limited_staff_ci_scope_valid"])
        self.assertFalse(diagnostics["limited_staff_employee_found"])
        self.assertNotIn("opaque@example.invalid", str(diagnostics))

    def test_limited_page_and_order_row_diagnostics_are_boolean_only(self) -> None:
        module = self.load_browser_module()
        secret_reference = "PRIVATE-ORDER-REFERENCE"
        secret_token = "PRIVATE-ADMIN-CREDENTIAL"

        class Cell:
            def __init__(self, value: str) -> None:
                self.text = value

        class Row:
            def __init__(self, values: list[str]) -> None:
                self.cells = [Cell(value) for value in values]

            def find_elements(self, by: str, selector: str):
                return self.cells if selector == "td" else []

        class Driver:
            def __init__(self) -> None:
                self.current_url = (
                    "http://localhost:18080/admin-kuranea/?controller="
                    f"AdminBusinessProfileTransfers&token={secret_token}"
                )
                self.rows = [Row([secret_reference, "7001", "1000 JPY"])]
                self.body = Cell("未決済")
                self.body.text = "未決済 엔화 주문"

            def find_elements(self, by: str, selector: str):
                if selector == ".table tbody tr":
                    return self.rows
                if selector == ".table tbody":
                    return [object()]
                return []

            def find_element(self, by: str, selector: str):
                self.assert_body_selector = (by, selector)
                return self.body

        driver = Driver()
        evidence = module.limited_transfer_page_evidence(
            driver, "http://localhost:18080/admin-kuranea", secret_token,
        )
        module.order_row(
            driver,
            {"reference": secret_reference, "order_id": 7001, "amount": "1000"},
            evidence,
        )
        self.assertEqual(
            module.LIMITED_PAGE_DIAGNOSTIC_KEYS - {"limited_mutation_controls_absent"},
            set(evidence),
        )
        self.assertTrue(all(type(value) is bool for value in evidence.values()))
        self.assertNotIn(secret_reference, str(evidence))
        self.assertNotIn(secret_token, str(evidence))
        self.assertTrue(evidence["limited_page_same_admin_origin"])
        self.assertTrue(evidence["limited_page_admin_path_valid"])
        self.assertTrue(evidence["limited_page_controller_valid"])
        self.assertTrue(evidence["limited_page_route_credential_matches"])
        self.assertTrue(evidence["limited_order_exact_row_match"])
        self.assertTrue(evidence["limited_order_amount_matches"])
        self.assertTrue(module.LIMITED_PAGE_REQUIRED_KEYS.issubset(module.SAFE_RESULT_KEYS))
        self.require("all(result[key] is True for key in LIMITED_PAGE_REQUIRED_KEYS)", self.browser)

    def test_limited_session_menu_route_is_exact_and_bounded(self) -> None:
        module = self.load_browser_module()
        admin_root = "http://localhost:18080/admin-kuranea"
        valid_routes = (
            "http://localhost:18080/admin-kuranea/?controller=AdminBusinessProfileTransfers&token=opaque",
            "http://localhost:18080/admin-kuranea/index.php?controller=AdminBusinessProfileTransfers&token=opaque",
        )
        for href in valid_routes:
            diagnostics: dict[str, object] = {}
            route, credential = module.validate_limited_session_route(href, admin_root, diagnostics)
            self.assertEqual(href, route)
            self.assertEqual("opaque", credential)
            self.assertTrue(diagnostics["limited_session_route_same_admin_origin"])
            self.assertTrue(diagnostics["limited_session_route_path_valid"])
            self.assertTrue(diagnostics["limited_session_route_controller_valid"])
            self.assertTrue(diagnostics["limited_session_route_query_shape_valid"])
            self.assertTrue(all(type(value) is bool for value in diagnostics.values()))
            self.assertNotIn("opaque", str(diagnostics))

        invalid_routes = (
            ("http://localhost:18080/admin-kuranea/other/index.php?controller=AdminBusinessProfileTransfers&token=opaque", "limited_session_route_path_valid"),
            ("http://localhost:18080/admin-kuranea/index.php/extra?controller=AdminBusinessProfileTransfers&token=opaque", "limited_session_route_path_valid"),
            ("http://localhost:18080/admin-kuranea/?controller=AdminOrders&token=opaque", "limited_session_route_controller_valid"),
            ("http://localhost:18080/admin-kuranea/?controller=AdminBusinessProfileTransfers&token=", "limited_session_route_credential_present"),
            ("http://localhost:18080/admin-kuranea/?controller=AdminBusinessProfileTransfers&token=opaque&token=extra", "limited_session_route_query_shape_valid"),
            ("http://localhost:18080/admin-kuranea/?controller=AdminBusinessProfileTransfers&token=opaque&extra=1", "limited_session_route_query_shape_valid"),
            ("http://evil.invalid/admin-kuranea/?controller=AdminBusinessProfileTransfers&token=opaque", "limited_session_route_same_admin_origin"),
            ("http://localhost:18080/admin-kuranea/?controller=AdminBusinessProfileTransfers&token=bad%20credential", "limited_session_route_credential_whitespace_free"),
            ("http://localhost:18080/admin-kuranea/?controller=AdminBusinessProfileTransfers&token=" + "x" * 257, "limited_session_route_credential_bounded"),
        )
        for href, failed_check in invalid_routes:
            diagnostics = {}
            with self.assertRaisesRegex(AssertionError, "exact same-admin transfer route"):
                module.validate_limited_session_route(href, admin_root, diagnostics)
            self.assertFalse(diagnostics[failed_check])
            self.assertTrue(all(type(value) is bool for value in diagnostics.values()))
            self.assertNotIn("opaque", str(diagnostics))

    def test_limited_employee_uses_its_authenticated_menu_route_after_acl_readback(self) -> None:
        helper_call = self.browser.index("verify_limited_staff_access(ctx, set_substage, result)")
        menu_call = self.browser.index("find_transfer_menu_link(limited, str(ctx[\"admin\"]), set_substage)", helper_call)
        validator_call = self.browser.index("validate_limited_session_route(", menu_call)
        navigation_call = self.browser.index("visit(limited, limited_url, str(ctx[\"shop\"]))", validator_call)
        self.assertLess(helper_call, menu_call)
        self.assertLess(menu_call, validator_call)
        self.assertLess(validator_call, navigation_call)
        self.assertNotIn("getAdminLink('AdminBusinessProfileTransfers')", self.limited_access)
        self.assertNotIn("payload['route']", self.limited_access)
        self.assertIn("#nav-sidebar #subtab-AdminBusinessProfileTransfers > a[href]", self.browser)

    def test_limited_access_helper_emits_only_boolean_access_evidence(self) -> None:
        module = self.load_browser_module()
        self.require("ordenowaLimitedAccessResult", self.limited_access)
        for stage in (
            "scope_validation", "bootstrap", "employee_lookup", "employee_active",
            "transfer_tab_acl", "orders_read_acl",
        ):
            self.require(f"'{stage}'", self.limited_access)
        for check_key in module.LIMITED_ACCESS_CHECK_KEYS:
            self.require(f"'{check_key}'", self.limited_access)
        for result_key in module.LIMITED_ACCESS_CHECK_KEYS.values():
            self.assertIn(result_key, module.SAFE_RESULT_KEYS)
            self.assertNotRegex(result_key, r"email|token|password|statement_reference|url")
        result_writer = self.limited_access.split("function ordenowaLimitedAccessResult", 1)[1].split("$runId", 1)[0]
        for forbidden in ("$email", "$generated", "$parts", "$query", "getMessage", "getTrace", "route')"):
            self.assertNotIn(forbidden, result_writer)
        self.require("catch (Throwable)", self.limited_access)
        self.assertNotIn("getAdminLink", self.limited_access)
        self.assertNotIn("'route' =>", self.limited_access)
        self.require("limited_access_helper_execution", self.browser)
        self.require("limited_access_helper_json_parse", self.browser)
        self.require("limited_access_helper_json_shape", self.browser)

    def test_fixture_is_bound_to_a_run_scoped_unpaid_native_jpy_order(self) -> None:
        for expected in (
            "GITHUB_ACTIONS",
            "KURANEA_ISOLATED_CI",
            "CI_COMPOSE_PROJECT_NAME",
            "KURANEA_CI_ORDER_ID",
            "KURANEA_CI_VIEWPORT",
            "CommerceGate::isIsolatedCiCheckoutEnabled()",
            "Shop::getTotalShops() === 1",
            "ps_checkpayment",
            "strtoupper((string) $currency->iso_code) === 'JPY'",
            "qa-ordenowa-checkout-%s-%s-bank@example.invalid",
            "$viewport === 'bank'",
            "!(bool) $customer->is_guest",
            "!(bool) $state->paid",
            "(float) $order->total_paid_real === 0.0",
            "ORDENOWA CI synthetic bank",
            "ORDENOWA CI ONLY",
        ):
            self.require(expected, self.prepare)
        self.require('get("currency")', self.browser)
        self.require("total_paid_tax_incl", self.unpaid_readback)
        self.require("order_id", self.unpaid_readback)
        self.require("unpaid", self.unpaid_readback)

    def test_late_bank_browser_uses_a_dedicated_third_order_after_shared_return_lifecycle(self) -> None:
        self.require('order = ctx["bank"]', self.browser)
        self.require('desktop_order = ctx["desktop"]', self.browser)
        self.require("all transfer assertions use the dedicated bank order", self.browser)
        self.require('bank = load_order(artifact_dir, "bank", run_id, attempt)', self.browser)
        self.require('customer_login(foreign, ctx, str(desktop_order["email"]))', self.browser)
        self.require('verify_unpaid_native_order(ctx, order, "unissued")', self.browser)
        self.assertNotIn('verify_unpaid_native_order(ctx, desktop_order, "unissued")', self.browser)
        self.assertNotIn('order = ctx["mobile"]', self.browser)
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        lifecycle = workflow.index("id: order_lifecycle")
        bank_browser = workflow.index("id: bank_transfer_browser_qa")
        checkout_restore = workflow.index("id: checkout_restore")
        bank_override = workflow.index("id: bank_transfer_checkout_override")
        bank_restore = workflow.index("id: bank_transfer_checkout_restore")
        admin_cancel = workflow.index("id: checkout_admin_browser_qa")
        self.assertLess(admin_cancel, lifecycle)
        self.assertLess(lifecycle, bank_browser)
        self.assertLess(checkout_restore, bank_override)
        self.assertLess(bank_override, bank_browser)
        self.assertLess(bank_browser, bank_restore)

    def test_browser_rejects_csrf_and_mismatched_amount_before_real_synthetic_confirmation(self) -> None:
        for expected_stage in (
            '"csrf_rejected"',
            '"issue_csrf_rejected"',
            '"wrong_amount_rejected"',
            '"receipt_confirmation"',
        ):
            self.require(expected_stage, self.browser)
        self.require("관리자 보안 토큰이 현재 관리자 세션과 다릅니다.", self.controller)
        self.require('$token = (string) $this->token;', self.controller)
        self.require("실제 입금액이 주문 금액과 다릅니다.", (ROOT / "modules" / "kuraneabusinessprofile" / "src" / "Infrastructure" / "BankTransferReceiptConfirmer.php").read_text(encoding="utf-8"))
        self.require("submitOrdenowaConfirmBankTransfer", self.browser)
        self.require("verified_transfer", self.browser)

    def test_customer_and_limited_employee_cannot_read_or_mutate_foreign_transfer(self) -> None:
        for expected in (
            "foreign_customer_denial",
            "foreign_customer_denied",
            "VIEW_ONLY_EMAIL",
            "limited_staff_denied",
            "customer_password",
        ):
            self.require(expected, self.browser)
        self.assertIn("section.ordenowa-bank-transfer-instructions", self.browser)
        self.require("주문 입금 확인 권한이 없습니다.", self.controller)
        self.require("주문 입금 안내를 발급할 권한이 없습니다.", self.controller)
        for expected in ("VIEW_ONLY_EMAIL", "Profile::getProfileAccesses", "AdminBusinessProfileTransfers", "view_allowed", "issue_denied", "confirm_denied"):
            self.require(expected, self.limited_access)

    def test_customer_instruction_is_bound_to_the_visible_native_order_product_line(self) -> None:
        self.require("product_id", self.unpaid_readback)
        self.require("product_name", self.unpaid_readback)
        self.require("KURANEA_CI_PRODUCT_ID", self.unpaid_readback)
        self.require("assert_customer_order_product", self.browser)
        self.require('"order_product_line_match"', self.browser)
        self.require("order_product_line_match", self.browser)
        self.require("product_name", self.browser)
        self.require("product_quantity", self.browser)

    def test_native_view_only_transfer_employee_cannot_confirm_with_a_valid_token(self) -> None:
        self.require("AdminBusinessProfileTransfers", self.security_fixture)
        self.require("$transferAccess['view']", self.security_fixture)
        self.require("$transferAccess['edit']", self.security_fixture)
        self.require("$transferAccess['add']", self.security_fixture)
        self.require("view_allowed", self.limited_access)
        self.require("issue_denied", self.limited_access)
        self.require("confirm_denied", self.limited_access)
        self.require("$ordersTabId = (int) Tab::getIdFromClassName('AdminOrders')", self.limited_access)
        self.require("$checks['orders_view_allowed']", self.limited_access)
        self.require("view_only_confirmation_denied", self.browser)
        self.require("view_only_issue_denied", self.browser)
        self.require("view_only_issue_order_unpaid", self.browser)
        self.require("view_only_confirmation_order_unpaid", self.browser)
        self.require("confirmation form", self.browser)
        self.require("주문 입금 확인 권한이 없습니다.", self.browser)
        self.require('verify_unpaid_native_order(ctx, order, "issued")', self.browser)
        self.require("canView($tabAccess)", self.controller)
        self.require("AdminAccessPolicy::canConfirmBankTransferReceipt", self.controller)

    def test_replay_is_idempotent_and_native_order_payment_history_are_unique(self) -> None:
        self.require('"receipt_replay"', self.browser)
        self.require("idempotent_replay", self.browser)
        for expected in (
            "count($instructionRows) === 1",
            "count($receiptRows) === 1",
            "count($payments) === 1",
            "count($paidHistoryRows) === 1",
            "PS_OS_PAYMENT",
            "is_synthetic",
            "order_payment",
            "order_history",
        ):
            self.require(expected, self.paid_readback)

    def test_confirmed_order_is_removed_from_the_admin_unpaid_queue(self) -> None:
        confirm_index = self.controller.index("$this->processConfirm(")
        after_confirmation = self.controller[confirm_index:]
        self.assertIn(
            "$orders = $this->unpaidJpyOrders($shopId);",
            after_confirmation,
            "the admin transfer queue must refresh after receipt confirmation",
        )
        self.require("paid_order_still_listed", self.browser)
        self.require("unpaid transfer queue still listed the paid order", self.browser)

    def test_safe_artifact_contract_omits_credentials_tokens_and_raw_statement_reference(self) -> None:
        for expected in (
            "SAFE_RESULT_KEYS",
            "SAFE_EXCEPTION_TYPES",
            "SAFE_SUBSTAGES",
            '"csrf_form_missing"',
            '"csrf_form_ambiguous"',
            '"csrf_control_validation"',
            '"csrf_invalid_token_submit"',
            '"csrf_rejection_readback"',
            '"csrf_unissued_db_readback"',
            '"csrf_confirmation_page_navigation"',
            '"csrf_confirmation_order_row_readback"',
            '"csrf_confirmation_form_readback"',
            '"csrf_confirmation_control_validation"',
            '"csrf_confirmation_invalid_token_submit"',
            '"csrf_confirmation_submit"',
            '"csrf_confirmation_notice_wait"',
            '"csrf_confirmation_notice_assertion"',
            '"csrf_confirmation_unpaid_db_readback"',
            '"limited_access_fixture_readback"',
            '"limited_access_contract_readback"',
            '"limited_session_route_validation"',
            '"limited_issue_denial_readback"',
            '"limited_issue_unpaid_db_readback"',
            '"limited_confirmation_denial_readback"',
            '"limited_confirmation_unpaid_db_readback"',
            "write_result",
            "bank-transfer-browser-result.json",
            "bank-transfer-customer-instructions-mobile.png",
            "bank-transfer-admin-confirmed-desktop.png",
            "bank-transfer-customer-paid-mobile.png",
        ):
            self.require(expected, self.browser)
        result_keys = re.search(r"SAFE_RESULT_KEYS\s*=\s*\{([^}]+)\}", self.browser, re.DOTALL)
        self.assertIsNotNone(result_keys)
        public_keys = result_keys.group(1)
        for forbidden in ("email", "account_number", "token", "password", "statement_reference", "url"):
            self.assertNotIn(forbidden, public_keys)
        self.require('"failure_substage"', public_keys)
        self.assertNotIn("bank_statement_reference", self.paid_readback)

    def test_invalid_csrf_form_cardinality_is_diagnosed_without_weakening_the_gate(self) -> None:
        helper = self.browser.split("def reject_issue_with_invalid_csrf", 1)[1].split("def confirmation_form", 1)[0]
        self.require('if len(forms) != 1:', helper)
        self.require('set_substage("csrf_form_missing" if not forms else "csrf_form_ambiguous")', helper)
        self.require('raise AssertionError("the unpaid order did not expose one instruction form', helper)
        self.require('tokens = form.find_elements(By.CSS_SELECTOR, \'input[name="token"]\')', helper)
        self.require('buttons = form.find_elements(By.CSS_SELECTOR, \'button[name="submitOrdenowaIssueTransfer"]\')', helper)
        self.require('safe_admin_path(action, admin_root)', helper)

    def test_invalid_csrf_notice_retries_stale_dom_and_keeps_exact_rejection_and_db_readback(self) -> None:
        snapshot = self.browser.split("def read_visible_notice_snapshot", 1)[1].split(
            "def reject_issue_with_invalid_csrf", 1
        )[0]
        self.require("WebDriverWait(driver, 35).until(read_snapshot)", snapshot)
        self.require("[data-ordenowa-transfer-feedback].alert.alert-success", snapshot)
        self.require("[data-ordenowa-transfer-feedback].alert.alert-danger", snapshot)
        self.require("except StaleElementReferenceException:", snapshot)
        self.require("text = notice.text", snapshot)
        self.require('class_name = notice.get_attribute("class") or ""', snapshot)

        helper = self.browser.split("def reject_issue_with_invalid_csrf", 1)[1].split("def confirmation_form", 1)[0]
        self.require(
            'notice_text.strip() != "관리자 보안 토큰이 현재 관리자 세션과 다릅니다. 페이지를 새로고침한 후 다시 시도해 주세요."',
            helper,
        )
        self.require('"alert-danger" not in notice_class.split()', helper)

        csrf_flow = self.browser.split('stage = result["stage"] = "csrf_rejected"', 1)[1].split(
            'stage = result["stage"] = "instruction_issue"', 1
        )[0]
        self.require("reject_issue_with_invalid_csrf(admin, row", csrf_flow)
        self.require('substage = "csrf_unissued_db_readback"', csrf_flow)
        self.require('result["issue_csrf_rejected"] = True', csrf_flow)
        self.require('substage = "none"', csrf_flow)
        no_change_readback = csrf_flow.index('verify_unpaid_native_order(ctx, order, "unissued")')
        self.assertLess(
            csrf_flow.index("reject_issue_with_invalid_csrf(admin, row"),
            no_change_readback,
        )
        self.assertLess(no_change_readback, csrf_flow.index('result["issue_csrf_rejected"] = True'))
        self.assertLess(no_change_readback, csrf_flow.index('substage = "none"'))

    def test_confirmation_form_targets_the_exact_order_in_its_row(self) -> None:
        module = self.load_browser_module()
        admin_root = "http://localhost:18080/admin-kuranea"

        class Control:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get_attribute(self, name: str) -> str | None:
                return self.value if name == "value" else None

        class Form:
            controls = {
                'input[name="received_amount"]': [Control()],
                'input[name="bank_statement_reference"]': [Control()],
                'input[name="verified_transfer"][value="1"]': [Control("1")],
                'input[name="token"]': [Control("opaque")],
                'input[name="id_order"]': [Control("7001")],
                'button[name="submitOrdenowaConfirmBankTransfer"]': [Control("1")],
            }

            def find_elements(self, _by: str, selector: str):
                return self.controls.get(selector, [])

            def get_attribute(self, name: str) -> str | None:
                return "http://localhost:18080/admin-kuranea/?controller=AdminBusinessProfileTransfers" if name == "action" else None

        class Row:
            def __init__(self, form: Form) -> None:
                self.form = form

            def find_elements(self, _by: str, selector: str):
                return [self.form] if selector == "form" else []

        row = Row(Form())
        self.assertEqual(3, len(module.confirmation_form(row, admin_root, 7001)))
        row.form.controls['input[name="id_order"]'] = [Control("7002")]
        with self.assertRaisesRegex(AssertionError, "exact unpaid order"):
            module.confirmation_form(row, admin_root, 7001)

    def test_confirmation_csrf_rejection_has_safe_substage_at_each_browser_boundary(self) -> None:
        limited_flow = self.browser.split('stage = result["stage"] = "limited_staff_denial"', 1)[1]
        csrf_flow = limited_flow.split('stage = result["stage"] = "csrf_rejected"', 1)[1].split(
            'stage = result["stage"] = "wrong_amount_rejected"', 1
        )[0]
        flow_markers = (
            'set_substage("csrf_confirmation_page_navigation")',
            'set_substage("csrf_confirmation_order_row_readback")',
            'tamper_token=True, set_substage=set_substage',
            'set_substage("csrf_confirmation_notice_assertion")',
            'set_substage("csrf_confirmation_unpaid_db_readback")',
            'ctx, order, "issued", set_substage=set_substage',
            'substage_prefix="csrf_confirmation_unpaid"',
            'substage = "none"',
        )
        positions = [csrf_flow.index(marker) for marker in flow_markers]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn('set_substage("none")', csrf_flow)
        self.assertIn('name not in SAFE_SUBSTAGES - {"none"}', self.browser)

        helper = self.browser.split("def fill_and_submit_confirmation", 1)[1].split(
            "def submit_hidden_admin_post", 1
        )[0]
        helper_markers = (
            'set_substage("csrf_confirmation_form_readback")',
            'set_substage("csrf_confirmation_control_validation")',
            'set_substage("csrf_confirmation_invalid_token_submit")',
            'set_substage("csrf_confirmation_submit")',
            'set_substage("csrf_confirmation_notice_wait")',
        )
        helper_positions = [helper.index(marker) for marker in helper_markers]
        self.assertEqual(helper_positions, sorted(helper_positions))
        self.require("notice = read_visible_notice_snapshot(driver)", helper)
        self.assertEqual(1, helper.count('fields["submit"][0].click()'))
        self.assertEqual(1, helper.count("read_visible_notice_snapshot(driver)"))
        self.assertLess(helper.index('fields["submit"][0].click()'), helper.index("read_visible_notice_snapshot(driver)"))
        self.require("notice_text, notice_class = notice_snapshot", csrf_flow)
        self.require('"alert-danger" not in notice_class.split()', csrf_flow)
        self.require(
            '"관리자 보안 토큰이 현재 관리자 세션과 다릅니다." not in notice_text', csrf_flow
        )
        self.require('fields["submit"][0].click()', self.browser)
        self.require('driver.execute_script("arguments[0].value = \'invalid\';", fields["token"][0])', self.browser)
        self.assertNotIn("submit_hidden_admin_post(", csrf_flow)
        for substage in (
            "helper_copy", "input_validation", "execution", "json_parse", "json_shape", "result_contract",
        ):
            self.require(f'"csrf_confirmation_unpaid_{substage}"', self.browser)

        tree = ast.parse(self.browser)
        substage_assignment = next(
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "SAFE_SUBSTAGES" for target in node.targets)
        )
        safe_substages = ast.literal_eval(substage_assignment.value)
        expected = {
            marker.split('"')[1]
            for marker in (*flow_markers, *helper_markers)
            if marker.startswith('set_substage')
        }
        self.assertTrue(expected <= safe_substages)

    def test_wrong_amount_response_is_scoped_classified_and_read_back_before_assertion(self) -> None:
        flow = self.browser.split('stage = result["stage"] = "wrong_amount_rejected"', 1)[1].split(
            'stage = result["stage"] = "receipt_confirmation"', 1
        )[0]
        markers = (
            'substage = "wrong_amount_navigation"',
            'substage = "wrong_amount_row_readback"',
            'substage = "wrong_amount_submit"',
            'wrong_amount_notice, _, _ = fill_and_submit_confirmation(',
            'notice_text, notice_class = wrong_amount_notice',
            'substage = "wrong_amount_notice_readback"',
            'result["wrong_amount_notice_category"] = confirmation_notice_category(notice_text)',
            'substage = "wrong_amount_server_csrf_readback"',
            'result.update(read_confirmation_csrf_server_evidence(admin))',
            'substage = "wrong_amount_unpaid_db_readback"',
            'verify_unpaid_native_order(ctx, order, "issued")',
            'result["wrong_amount_unpaid_readback"] = True',
            'substage = "wrong_amount_notice_assertion"',
            'result["wrong_amount_notice_category"] != "amount_mismatch"',
        )
        positions = [flow.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('"wrong_amount_post_native_csrf_valid"', self.browser)
        self.assertIn('data-ordenowa-transfer-feedback="true"', self.controller)
        self.assertIn('"amount_mismatch"', self.browser)
        self.assertIn('posted_order_id != str(expected_order_id)', self.browser)
        self.assertIn('"wrong_amount_post_order_id_matches_fixture"', self.browser)
        self.assertIn("post-order-id-matches-fixture", self.controller)
        self.assertIn("post-order-exists-in-current-shop", self.controller)

    def test_issue_csrf_failure_distinguishes_wrong_method_from_token_mismatch(self) -> None:
        init_content = self.controller.split("public function initContent()", 1)[1].split(
            "private function processIssue", 1
        )[0]
        self.assertEqual(1, init_content.count("parent::initContent();"))
        self.assertLess(init_content.index("parent::initContent();"), init_content.index("$this->processIssue("))

        issue = self.controller.split("private function processIssue", 1)[1].split(
            "private function processConfirm", 1
        )[0]
        self.assertLess(issue.index("REQUEST_METHOD"), issue.index("hasValidAdminMutationToken"))
        self.require("입금 안내 발급 요청 방식이 올바르지 않습니다.", issue)
        self.require("관리자 보안 토큰이 현재 관리자 세션과 다릅니다.", issue)
        self.require("$this->hasValidAdminMutationToken()", issue)
        self.assertNotIn('hash_equals((string) $this->token, $submittedToken)', issue)
        self.require('요청에 관리자 보안 토큰이 누락되었습니다.', issue)

        confirm = self.controller.split("private function processConfirm", 1)[1].split(
            "private function unpaidJpyOrders", 1
        )[0]
        self.require("$this->hasValidAdminMutationToken()", confirm)
        self.assertNotIn('hash_equals((string) $this->token, $submittedToken)', confirm)

        token_validator = self.controller.split("private function hasValidAdminMutationToken", 1)[1].split(
            "private function isIsolatedCiDiagnosticRun", 1
        )[0]
        for marker in (
            "$_POST['token']", "$_GET['token']", "hash_equals($queryToken, $submittedToken)",
            "SymfonyContainer::getInstance()", "UserTokenManager::class", "isTokenValid() === true",
            "catch (Throwable)", "return false;",
        ):
            self.require(marker, token_validator)
        self.assertNotIn("$this->token", token_validator)

        helper = self.browser.split("def issue_form_token_matches_action", 1)[1].split(
            "def read_visible_notice", 1
        )[0]
        self.require('input[name="token"]', helper)
        self.require('get("token", [])', helper)
        self.require("form_token == action_tokens[0]", helper)
        self.require('result["issue_form_csrf_consistent"] = issue_form_token_matches_action(', self.browser)
        self.require("issue_form_csrf_consistent=", self.browser)

        ci_evidence = self.controller.split("private function renderIsolatedCiCsrfEvidence", 1)[1].split(
            "private function renderIsolatedCiProfileEvidence", 1
        )[0]
        for marker in (
            "isIsolatedCiDiagnosticRun()",
            "hash_equals($controllerToken, $submittedToken)",
            "hash_equals($controllerToken, $queryToken)",
            "hash_equals($queryToken, $submittedToken)",
            "hash_equals($controllerToken, $adminLinkToken)",
            "hasValidAdminMutationToken()",
            "ordenowa-ci-transfer-csrf-evidence",
            "'post-matches-controller'",
        ):
            self.require(marker, ci_evidence)
        self.assertNotIn("CommerceGate::isIsolatedCiCheckoutEnabled()", ci_evidence)
        self.assertNotIn("$submittedToken .", ci_evidence)
        self.assertNotIn("$queryToken .", ci_evidence)
        run_scope = self.controller.split("private function isIsolatedCiDiagnosticRun", 1)[1].split(
            "private function escape", 1
        )[0]
        self.require("getenv('GITHUB_ACTIONS') === 'true'", run_scope)
        self.require("getenv('KURANEA_CI_PROJECT_NAME') === 'kuranea-ci-' . $runId . '-' . $runAttempt", run_scope)

        profile_evidence = self.controller.split("private function renderIsolatedCiProfileEvidence", 1)[1].split(
            "private function hasValidAdminMutationToken", 1
        )[0]
        for marker in (
            "isIsolatedCiDiagnosticRun()", "loadPublished($shopId)",
            "BankTransferPayment::selectedActiveAccount($profile) !== null",
            "CommerceGate::isIsolatedCiCheckoutEnabled()", "CommerceGate::isEnabled(",
            "ordenowa-ci-transfer-profile-evidence", "profile-readback-succeeded",
            "'published-profile-present'", "'selected-active-account-present'",
            "'effective-commerce-gate-enabled'",
        ):
            self.require(marker, profile_evidence)
        self.assertNotIn("account_number", profile_evidence)

        browser_evidence = self.browser.split("def read_issue_csrf_server_evidence", 1)[1].split(
            "def read_visible_notice", 1
        )[0]
        self.require('By.ID, "ordenowa-ci-transfer-csrf-evidence"', browser_evidence)
        self.require('"issue_post_matches_controller", "data-post-matches-controller"', browser_evidence)
        self.require('"issue_post_native_csrf_valid", "data-post-native-csrf-valid"', browser_evidence)
        self.assertNotIn('get_attribute("value")', browser_evidence)
        self.require('result.update(read_issue_csrf_server_evidence(admin))', self.browser)
        self.require('"issue_post_native_csrf_valid"', self.browser)
        profile_browser_evidence = self.browser.split("def read_issue_profile_server_evidence", 1)[1].split(
            "def read_visible_notice", 1
        )[0]
        self.require('By.ID, "ordenowa-ci-transfer-profile-evidence"', profile_browser_evidence)
        self.require('"issue_selected_active_account_present", "data-selected-active-account-present"', profile_browser_evidence)
        self.require('"issue_profile_readback_succeeded", "data-profile-readback-succeeded"', profile_browser_evidence)
        self.require('"issue_effective_commerce_gate_enabled", "data-effective-commerce-gate-enabled"', profile_browser_evidence)
        self.assertNotIn('get_attribute("value")', profile_browser_evidence)
        self.require('result.update(read_issue_profile_server_evidence(admin))', self.browser)
        self.require('"issue_selected_active_account_present"', self.browser)
        self.require('"issue_effective_commerce_gate_enabled"', self.browser)

    def test_synthetic_bank_fixture_reloads_the_published_profile_before_browser_qa(self) -> None:
        fixture = PREPARE.read_text(encoding="utf-8")
        for expected in (
            "$published = $repository->loadPublished($shopId)",
            "BankTransferPayment::selectedActiveAccount($published->profile)",
            "$published->id === $draftVersionId",
            "($publishedAccount['id'] ?? null) === $accountId",
            "($publishedAccount['account_number'] ?? null) === $accountNumber",
            "fresh profile readback",
        ):
            self.require(expected, fixture)

    def test_instruction_issue_notice_uses_fresh_snapshot_before_persistence_readback(self) -> None:
        issue_flow = self.browser.split('stage = result["stage"] = "instruction_issue"', 1)[1].split(
            'stage = result["stage"] = "instruction_readback"', 1
        )[0]
        for marker in (
            'set_substage("instruction_issue_navigation")',
            'set_substage("instruction_issue_order_row_readback")',
            'set_substage("instruction_issue_action_controls")',
            'set_substage("instruction_issue_submit")',
            'set_substage("instruction_issue_notice_readback")',
            'notice_text, notice_class = read_visible_notice_snapshot(admin)',
            '"미결제" not in notice_text',
            '"alert-success" not in notice_class.split()',
            'set_substage("instruction_issue_db_readback")',
            'verify_unpaid_native_order(ctx, order, "issued")',
            'result["instruction_issued"] = True',
        ):
            self.require(marker, issue_flow)
        notice_readback = issue_flow.index("notice_text, notice_class = read_visible_notice_snapshot(admin)")
        persistence_readback = issue_flow.index('verify_unpaid_native_order(ctx, order, "issued")')
        self.assertLess(notice_readback, persistence_readback)

    def test_issue_notice_failure_diagnostics_are_bounded_and_keep_both_assertions(self) -> None:
        helper = self.browser.split("def issue_notice_failure_substage", 1)[1].split(
            "def reject_issue_with_invalid_csrf", 1
        )[0]
        self.require('"unpaid_present" if "미결제" in notice_text else "unpaid_missing"', helper)
        self.require('"alert-success" in classes', helper)
        self.require('"alert-danger" in classes', helper)
        self.require('class_state = "missing"', helper)
        self.require('class_state = "other"', helper)
        self.require('return f"instruction_issue_notice_{unpaid_state}_{class_state}"', helper)
        for forbidden in ("print(notice_text", "print(notice_class", "notice_text}", "notice_class}"):
            self.assertNotIn(forbidden, helper)

        issue_flow = self.browser.split('stage = result["stage"] = "instruction_issue"', 1)[1].split(
            'stage = result["stage"] = "instruction_readback"', 1
        )[0]
        self.require('set_substage(issue_notice_failure_substage(notice_text, notice_class))', issue_flow)
        self.require('"미결제" not in notice_text', issue_flow)
        self.require('"alert-success" not in notice_class.split()', issue_flow)
        self.require('diagnose_unpaid_issue_persistence(ctx, order)', issue_flow)
        self.require('verify_unpaid_native_order(ctx, order, "issued")', issue_flow)

        tree = ast.parse(self.browser)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "issue_notice_failure_substage"
        )
        substage_assignment = next(
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "SAFE_SUBSTAGES" for target in node.targets)
        )
        safe_substages = ast.literal_eval(substage_assignment.value)
        namespace: dict[str, object] = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(BROWSER), "exec"), namespace)
        classify = namespace["issue_notice_failure_substage"]
        observed = {
            classify("주문은 미결제 상태입니다.", "alert alert-success"),
            classify("안내를 유지했습니다.", "alert alert-success"),
            classify("주문은 미결제 상태입니다.", "alert alert-danger"),
            classify("안내를 유지했습니다.", ""),
            classify("안내를 유지했습니다.", "alert alert-info"),
        }
        self.assertEqual(observed, {
            "instruction_issue_notice_unpaid_present_success",
            "instruction_issue_notice_unpaid_missing_success",
            "instruction_issue_notice_unpaid_present_danger",
            "instruction_issue_notice_unpaid_missing_missing",
            "instruction_issue_notice_unpaid_missing_other",
        })
        self.assertTrue(observed <= safe_substages)

        category_helper = self.browser.split("def issue_notice_failure_category", 1)[1].split(
            "def reject_issue_with_invalid_csrf", 1
        )[0]
        self.require('"unclassified_notice"', category_helper)
        self.require('"csrf_field_missing"', category_helper)
        self.require('"csrf_field_mismatch"', category_helper)
        self.require('"invalid_http_method"', category_helper)
        self.require('"instruction_persistence_error"', category_helper)
        self.assertNotIn("print(", category_helper)
        tree = ast.parse(self.browser)
        category_function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "issue_notice_failure_category"
        )
        category_namespace: dict[str, object] = {}
        exec(compile(ast.Module(body=[category_function], type_ignores=[]), str(BROWSER), "exec"), category_namespace)
        classify_category = category_namespace["issue_notice_failure_category"]
        self.assertEqual(
            classify_category("관리자 보안 토큰이 현재 관리자 세션과 다릅니다. 페이지를 새로고침한 후 다시 시도해 주세요."),
            "csrf_field_mismatch",
        )
        self.assertEqual(
            classify_category("요청에 관리자 보안 토큰이 누락되었습니다. 페이지를 새로고침한 후 다시 시도해 주세요."),
            "csrf_field_missing",
        )
        self.assertEqual(
            classify_category("입금 안내 발급 요청 방식이 올바르지 않습니다. 페이지를 새로고침한 후 다시 시도해 주세요."),
            "invalid_http_method",
        )
        self.assertEqual(classify_category("주문 입금 안내를 저장하지 못했습니다."), "instruction_persistence_error")
        self.assertEqual(classify_category("private order error sentinel"), "unclassified_notice")
        self.require('"issue_failure_category"', self.browser)
        self.require('issue_failure_category={result[\'issue_failure_category\']}', self.browser)
        self.require('issue_persistence_diagnostic={result[\'issue_persistence_diagnostic\']}', self.browser)

    def test_failed_issue_notice_reads_only_scoped_unpaid_persistence_flags(self) -> None:
        diagnostic = self.browser.split("def diagnose_unpaid_issue_persistence", 1)[1].split(
            "def verify_limited_staff_access", 1
        )[0]
        for marker in (
            '"KURANEA_CI_TRANSFER_EXPECTATION": "diagnostic"',
            '"db_readback_available", "native_order_unpaid", "instruction_persisted", "instruction_matches_order"',
            '"receipt_absent", "native_payment_absent"',
            'payload["db_readback_available"] is not True',
            '"unpaid_instruction_persisted" if payload["instruction_persisted"] else "unpaid_instruction_absent"',
        ):
            self.require(marker, diagnostic)
        self.assertNotIn("print(", diagnostic)
        self.assertNotIn("write_text(", diagnostic)

        php_branch = self.unpaid_readback.split("if ($expectation === 'diagnostic') {", 1)[1].split(
            "\n\n$instruction = (new BankTransferInstructionRepository())", 1
        )[0]
        for marker in (
            "executeS(", "'db_readback_available' => $readbackAvailable", "'native_order_unpaid' => true",
            "'instruction_persisted' => is_array($instructionRows) && count($instructionRows) > 0",
            "'instruction_matches_order' => $instructionMatchesOrder && $instructionCount <= 1",
            "'receipt_absent' => is_array($receiptRows) && count($receiptRows) === 0",
            "'native_payment_absent' => $readbackAvailable && (int) $paymentRows[0]['payment_count'] === 0",
            "exit;",
        ):
            self.require(marker, php_branch)
        self.assertNotRegex(php_branch, r"\$database->execute\s*\(")
        self.assertNotRegex(php_branch, r"\b(?:INSERT|UPDATE|DELETE)\b")
        for forbidden in ("'order_id' =>", "'order_reference' =>", "'total_paid' =>", "'bank_account_id' =>"):
            self.assertNotIn(forbidden, php_branch)
        self.require("if ($expectation !== 'diagnostic')", self.unpaid_readback)
        self.require('"issue_persistence_diagnostic"', self.browser)
        self.require('SAFE_ISSUE_PERSISTENCE_DIAGNOSTICS', self.browser)

    def test_artifact_coverage_requires_the_dedicated_bank_order_readback(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        self.require('name = f"bank-transfer-{order[\'viewport\']}-unpaid-readback.json"', self.browser)
        bank_coverage = workflow.split('if [[ "$BANK_TRANSFER_BROWSER_QA_OUTCOME" == success ]]; then', 1)[1].split("elif [[", 1)[0]
        self.require("bank-transfer-bank-unpaid-readback.json", bank_coverage)
        self.assertNotIn("bank-transfer-desktop-unpaid-readback.json", bank_coverage)
        self.assertNotIn("bank-transfer-mobile-unpaid-readback.json", bank_coverage)

    def test_browser_uses_real_customer_and_staff_controls_not_database_mutation_or_js_clicks(self) -> None:
        self.require("find_transfer_menu_link", self.browser)
        self.require('#nav-sidebar #subtab-AdminParentOrders > a.link', self.browser)
        self.require('#nav-sidebar #subtab-AdminBusinessProfileTransfers > a[href]', self.browser)
        self.require('query.get("controller") == ["AdminBusinessProfileTransfers"]', self.browser)
        self.require('orders_toggle.get_attribute("aria-expanded") != "true"', self.browser)
        self.require('orders_toggle.click()', self.browser)
        self.require('WebDriverWait(driver, 10).until(lambda _browser: bool(visible_transfer_links()))', self.browser)
        self.require('"the generated transfer menu link left the authenticated Back Office"', self.browser)
        self.assertNotIn('"/transfer" in parsed.path.lower()', self.browser)
        self.require("issue_buttons[0].click()", self.browser)
        self.require("buttons[0].click()", self.browser)
        self.require('fields["submit"][0].click()', self.browser)
        self.assertNotIn("execute_script(\"arguments[0].click()", self.browser)
        self.assertNotIn("UPDATE `orders`", self.browser)
        self.assertNotIn("INSERT INTO `order_payment`", self.browser)
        self.assertNotIn("PaymentModule", self.browser)
        self.require("docker", self.browser)


if __name__ == "__main__":
    unittest.main()
