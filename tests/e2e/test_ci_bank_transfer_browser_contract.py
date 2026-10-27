from pathlib import Path
import ast
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
BROWSER = ROOT / "tests" / "e2e" / "verify_ci_bank_transfer_browser.py"
PREPARE = ROOT / "tests" / "business_profile" / "prepare_ci_bank_transfer_fixture.php"
UNPAID_READBACK = ROOT / "tests" / "business_profile" / "verify_ci_bank_transfer_unpaid_order.php"
PAID_READBACK = ROOT / "tests" / "business_profile" / "verify_ci_bank_transfer_persistence.php"
LIMITED_ROUTE = ROOT / "tests" / "business_profile" / "resolve_ci_limited_transfer_route.php"
SECURITY_FIXTURE = ROOT / "tests" / "business_profile" / "seed_security_fixtures.php"
TRANSFER_CONTROLLER = ROOT / "modules" / "kuraneabusinessprofile" / "controllers" / "admin" / "AdminBusinessProfileTransfersController.php"


class CiBankTransferBrowserContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.browser = BROWSER.read_text(encoding="utf-8")
        cls.prepare = PREPARE.read_text(encoding="utf-8")
        cls.unpaid_readback = UNPAID_READBACK.read_text(encoding="utf-8") if UNPAID_READBACK.exists() else ""
        cls.paid_readback = PAID_READBACK.read_text(encoding="utf-8")
        cls.limited_route = LIMITED_ROUTE.read_text(encoding="utf-8") if LIMITED_ROUTE.exists() else ""
        cls.security_fixture = SECURITY_FIXTURE.read_text(encoding="utf-8")
        cls.controller = TRANSFER_CONTROLLER.read_text(encoding="utf-8")

    def require(self, needle: str, haystack: str) -> None:
        self.assertTrue(needle in haystack, f"missing contract: {needle}")

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
        admin_cancel = workflow.index("id: checkout_admin_browser_qa")
        self.assertLess(admin_cancel, lifecycle)
        self.assertLess(lifecycle, bank_browser)

    def test_browser_rejects_csrf_and_mismatched_amount_before_real_synthetic_confirmation(self) -> None:
        for expected_stage in (
            '"csrf_rejected"',
            '"issue_csrf_rejected"',
            '"wrong_amount_rejected"',
            '"receipt_confirmation"',
        ):
            self.require(expected_stage, self.browser)
        self.require("관리자 보안 토큰이 올바르지 않습니다.", self.controller)
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
            self.require(expected, self.limited_route)

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
        self.require("view_allowed", self.limited_route)
        self.require("issue_denied", self.limited_route)
        self.require("confirm_denied", self.limited_route)
        self.require("view_only_confirmation_denied", self.browser)
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
        self.require("browser.find_elements(By.CSS_SELECTOR, \".alert.alert-success, .alert.alert-danger\")", snapshot)
        self.require("except StaleElementReferenceException:", snapshot)
        self.require("text = notice.text", snapshot)
        self.require('class_name = notice.get_attribute("class") or ""', snapshot)

        helper = self.browser.split("def reject_issue_with_invalid_csrf", 1)[1].split("def confirmation_form", 1)[0]
        self.require(
            'notice_text.strip() != "관리자 보안 토큰이 올바르지 않습니다. 페이지를 새로고침한 후 다시 시도해 주세요."',
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
        self.require('"csrf_rejected"', category_helper)
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
            classify_category("관리자 보안 토큰이 올바르지 않습니다. 페이지를 새로고침한 후 다시 시도해 주세요."),
            "csrf_rejected",
        )
        self.assertEqual(classify_category("주문 입금 안내를 저장하지 못했습니다."), "instruction_persistence_error")
        self.assertEqual(classify_category("private order error sentinel"), "unclassified_notice")
        self.require('"issue_failure_category"', self.browser)
        self.require('issue_failure_category={result[\'issue_failure_category\']}', self.browser)
        self.require('issue_persistence_diagnostic={result[\'issue_persistence_diagnostic\']}', self.browser)

    def test_failed_issue_notice_reads_only_scoped_unpaid_persistence_flags(self) -> None:
        diagnostic = self.browser.split("def diagnose_unpaid_issue_persistence", 1)[1].split(
            "def limited_transfer_route", 1
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
