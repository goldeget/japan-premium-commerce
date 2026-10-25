from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "tests" / "postcode" / "verify_ci_native_order_lifecycle.php"
PREPARER = ROOT / "tests" / "postcode" / "prepare_ci_native_order_lifecycle.php"


class CiNativeOrderLifecycleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not VERIFIER.is_file():
            raise AssertionError("the CI-only native order lifecycle verifier is missing")
        cls.source = VERIFIER.read_text(encoding="utf-8")

    def test_verifier_requires_the_exact_isolated_run_and_run_scoped_order_ids(self) -> None:
        for required in (
            "getenv('CI') !== 'true'",
            "getenv('GITHUB_ACTIONS') !== 'true'",
            "getenv('KURANEA_ISOLATED_CI') !== '1'",
            "'kuranea-ci-' . $runId . '-' . $runAttempt",
            "KURANEA_CI_UNPAID_ORDER_ID",
            "KURANEA_CI_PAID_LIKE_ORDER_ID",
            "@example.invalid",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)

    def test_unpaid_cancellation_readback_requires_latest_admin_history_and_zero_paid_amount(self) -> None:
        for required in (
            "Configuration::get('PS_OS_CANCELED')",
            "Back Office unpaid cancellation readback",
            "SELECT `id_order_state`, `id_employee` FROM `",
            "ORDER BY `date_add` DESC, `id_order_history` DESC LIMIT 2",
            "$unpaidHistory[0]['id_order_state']",
            "$unpaidHistory[0]['id_employee']",
            "$unpaidHistory[1]['id_order_state']",
            "$cancelledOrder->hasBeenPaid()",
            "total_paid_real",
            "PS_OS_CANCELED",
            "order_history",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)
        self.assertNotIn("new OrderHistory()", self.source)
        self.assertNotIn("changeIdOrderState(", self.source)
        self.assertNotIn("->addWithemail(", self.source)

    def test_native_return_and_credit_slip_require_enabled_returns_and_a_paid_like_order(self) -> None:
        for required in (
            "Configuration::get('PS_ORDER_RETURN',",
            "->isReturnable()",
            "->hasBeenPaid()",
            "->shipped",
            "new OrderReturn()",
            "addReturnDetail(",
            "OrderReturnState",
            "OrderSlip::create(",
            "unsupported",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)

    def test_verifier_never_calls_a_payment_provider_or_remote_refund(self) -> None:
        forbidden = re.compile(
            r"PaymentModule::|OrderPayment::|Module::getInstanceByName|"
            r"->refund\s*\(|->processRefund\s*\(|curl_exec\s*\(|"
            r"file_get_contents\s*\(\s*['\"]https?://",
            re.IGNORECASE,
        )
        self.assertIsNone(forbidden.search(self.source))

    def test_preparer_uses_only_the_second_run_scoped_offline_browser_order(self) -> None:
        if not PREPARER.is_file():
            self.fail("the CI-only native order lifecycle fixture preparer is missing")
        source = PREPARER.read_text(encoding="utf-8")
        for required in (
            "KURANEA_CI_PAID_LIKE_SOURCE_ORDER_ID",
            "qa-ordenowa-checkout-%s-%s-mobile@example.invalid",
            "'ps_checkpayment'",
            "'KURANEA-CI-'",
            "Configuration::get('PS_OS_DELIVERED')",
            "$deliveredStateId === $paymentStateId",
            "new OrderHistory()",
            "changeIdOrderState(",
            "->add(",
            "KURANEA_CI_PAID_LIKE_ORDER_ID",
            "synthetic CI-only",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        self.assertIn("Configuration::get('PS_OS_PAYMENT')", source)
        self.assertIn("Configuration::get('PS_OS_WS_PAYMENT')", source)
        self.assertNotIn("changeIdOrderState($paymentStateId", source)
        self.assertNotIn("changeIdOrderState($webservicePaymentStateId", source)

    def test_paid_like_fixture_uses_native_order_payment_api_before_paid_state_transition(self) -> None:
        source = PREPARER.read_text(encoding="utf-8")
        required_calls = (
            "$sourceOrder->setInvoice();",
            "$sourceOrder->getInvoicesCollection()",
            "$invoice->getRestPaid()",
            "$sourceOrder->addOrderPayment(",
        )
        missing_calls = [required for required in required_calls if required not in source]
        self.assertFalse(
            missing_calls,
            f"the fixture must use native invoice and payment APIs before paid transition: {missing_calls}",
        )
        if missing_calls:
            return

        invoice_creation = source.index("$sourceOrder->setInvoice();")
        invoice_readback = source.index("$sourceOrder->getInvoicesCollection()", invoice_creation)
        invoice_balance = source.index("$invoice->getRestPaid()", invoice_readback)
        native_payment = source.index("$sourceOrder->addOrderPayment(", invoice_balance)
        paid_state_transition = source.index("$history->changeIdOrderState($deliveredStateId, $sourceOrder);", native_payment)

        self.assertLess(invoice_creation, invoice_readback)
        self.assertLess(invoice_readback, invoice_balance)
        self.assertLess(invoice_balance, native_payment)
        self.assertLess(native_payment, paid_state_transition)
        self.assertIn("$syntheticPaymentMethod", source[native_payment:paid_state_transition])
        self.assertIn("$invoice", source[native_payment:paid_state_transition])
        self.assertIn("$context->employee->id", source[native_payment:paid_state_transition])
        self.assertIn("synthetic CI-only", source)
        self.assertNotRegex(source, r"Db::getInstance\(\)->insert\s*\(")

    def test_native_payment_write_is_read_back_at_both_state_transition_boundaries(self) -> None:
        source = PREPARER.read_text(encoding="utf-8")
        required_reads = (
            "$preTransitionLedger = $readPaymentLedgerBoundary($sourceOrder);",
            "$postTransitionLedger = $readPaymentLedgerBoundary($preparedOrder);",
        )
        missing_reads = [required for required in required_reads if required not in source]
        self.assertFalse(
            missing_reads,
            f"the fixture must read back the native ledger before and after status transition: {missing_reads}",
        )
        if missing_reads:
            return

        payment_write = source.index("$sourceOrder->addOrderPayment(")
        pre_transition_readback = source.index(required_reads[0], payment_write)
        pre_transition_validation = source.index("if (empty($preTransitionLedger['payment_loaded'])", pre_transition_readback)
        state_transition = source.index("$history->changeIdOrderState($deliveredStateId, $sourceOrder);")
        post_transition_readback = source.index(required_reads[1], state_transition)
        final_ledger_validation = source.index("$stage = 'validate native payment ledger row';", post_transition_readback)

        self.assertLess(payment_write, pre_transition_readback)
        self.assertLess(pre_transition_readback, pre_transition_validation)
        self.assertLess(pre_transition_validation, state_transition)
        self.assertLess(state_transition, post_transition_readback)
        self.assertLess(post_transition_readback, final_ledger_validation)
        self.assertIn("$formatPaymentLedgerBoundary('pre_transition', $preTransitionLedger)", source)
        self.assertIn("$formatPaymentLedgerBoundary('post_transition', $postTransitionLedger)", source)
        for field in (
            "invoice_count",
            "invoice_payment_association_count",
            "payment_collection_count",
            "payment_row_found",
            "payment_loaded",
            "order_reference_matches",
            "amount_positive",
        ):
            with self.subTest(field=field):
                self.assertIn("'" + field + "'", source)

    def test_order_product_readbacks_initialize_language_and_currency_before_price_formatting(self) -> None:
        preparer = PREPARER.read_text(encoding="utf-8")
        source_order_readback = preparer.index("$sourceProducts = $sourceOrder->getProducts();")
        for assignment in (
            "$context->language = new Language((int) $sourceOrder->id_lang);",
            "$context->currency = new Currency((int) $sourceOrder->id_currency);",
        ):
            with self.subTest(assignment=assignment):
                self.assertIn(assignment, preparer)
                self.assertLess(preparer.index(assignment), source_order_readback)

        load_test_order = self.source.split("$loadTestOrder = static function", 1)[1].split("return [$order, $customer, $products];", 1)[0]
        product_readback = load_test_order.index("$products = $order->getProducts();")
        for assignment in (
            "$context->language = new Language((int) $order->id_lang);",
            "$context->currency = new Currency((int) $order->id_currency);",
        ):
            with self.subTest(assignment=assignment):
                self.assertIn(assignment, load_test_order)
                self.assertLess(load_test_order.index(assignment), product_readback)

    def test_transition_clears_prestashop_history_cache_before_paid_readback(self) -> None:
        preparer = PREPARER.read_text(encoding="utf-8")
        self.assertIn("Order::cleanHistoryCache();", preparer)
        history_write = preparer.index("if (!$history->add())")
        cache_clear = preparer.index("Order::cleanHistoryCache();", history_write)
        paid_readback = preparer.index("$preparedOrder = new Order", cache_clear)

        self.assertLess(history_write, cache_clear)
        self.assertLess(cache_clear, paid_readback)

    def test_synthetic_payment_failure_stage_identifies_the_exact_native_boundary(self) -> None:
        preparer = PREPARER.read_text(encoding="utf-8")
        for stage in (
            "load native invoice payment association",
            "validate native payment ledger row",
            "label native payment ledger as synthetic",
            "persist native return configuration marker",
        ):
            with self.subTest(stage=stage):
                self.assertIn("$stage = '" + stage + "';", preparer)

    def test_failed_payment_ledger_predicate_emits_bounded_safe_diagnostics(self) -> None:
        preparer = PREPARER.read_text(encoding="utf-8")
        pre_transition_diagnostic = preparer.split(
            "$preTransitionLedger = $readPaymentLedgerBoundary($sourceOrder);", 1
        )[1].split("$stage = 'native synthetic paid-like state transition';", 1)[0]
        post_transition_diagnostic = preparer.split(
            "$postTransitionLedger = $readPaymentLedgerBoundary($preparedOrder);", 1
        )[1].split("$stage = 'validate native payment ledger row';", 1)[0]

        for required in (
            "payment_row_found=",
            "payment_loaded=",
            "order_reference_matches=",
            "amount_positive=",
            "invoice_count=",
            "invoice_payment_association_count=",
            "payment_collection_count=",
            "payment_query_available=",
            "min(9, max(0,",
            "is_numeric($value)",
            "use (&$stage, &$safeDiagnostic)",
        ):
            with self.subTest(required=required):
                self.assertIn(required, preparer)

        self.assertIn("$safeDiagnostic", pre_transition_diagnostic)
        self.assertIn("$safeDiagnostic", post_transition_diagnostic)
        safe_output = preparer.split(
            "$formatPaymentLedgerBoundary = static function", 1
        )[1].split("};", 1)[0]
        for forbidden_value in (
            "$payment->reference",
            "$payment->amount",
            "$preparedOrder->reference",
            "$preparedOrder->id",
        ):
            with self.subTest(forbidden_value=forbidden_value):
                self.assertNotIn(forbidden_value, safe_output)

    def test_returns_configuration_is_run_scoped_and_restored_by_verifier_shutdown(self) -> None:
        if not PREPARER.is_file():
            self.fail("the CI-only native order lifecycle fixture preparer is missing")
        preparer = PREPARER.read_text(encoding="utf-8")
        for required in (
            "PS_ORDER_RETURN",
            "KURANEA_CI_ORDER_RETURN_BACKUP",
            "Configuration::updateValue('PS_ORDER_RETURN', true",
            "'previous_order_return'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, preparer)
        for required in (
            "register_shutdown_function(",
            "KURANEA_CI_ORDER_RETURN_BACKUP",
            "Configuration::updateValue('PS_ORDER_RETURN'",
            "Configuration::deleteByName(",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)

    def test_preparer_does_not_call_payment_or_remote_refund_apis(self) -> None:
        if not PREPARER.is_file():
            self.fail("the CI-only native order lifecycle fixture preparer is missing")
        source = PREPARER.read_text(encoding="utf-8")
        forbidden = re.compile(
            r"PaymentModule::|OrderPayment::|Module::getInstanceByName|"
            r"->refund\s*\(|->processRefund\s*\(|curl_exec\s*\(|"
            r"file_get_contents\s*\(\s*['\"]https?://",
            re.IGNORECASE,
        )
        self.assertIsNone(forbidden.search(source))

    def test_workflow_requires_both_lifecycle_php_steps_and_safe_artifacts(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        fixture_step = workflow.split("- name: Prepare CI-only paid-like order for return verification", 1)[1].split("- name:", 1)[0]
        verify_step = workflow.split("- name: Verify native order cancellation, return, and credit-slip behavior", 1)[1].split("- name:", 1)[0]
        coverage = workflow.split("- name: Verify browser QA screenshot coverage", 1)[1].split("- name:", 1)[0]
        aggregate = workflow.split("- name: Aggregate browser QA and postal verification failures", 1)[1]

        self.assertIn("id: order_lifecycle_fixture", fixture_step)
        self.assertIn("prepare_ci_native_order_lifecycle.php", fixture_step)
        self.assertIn("KURANEA_CI_PAID_LIKE_SOURCE_ORDER_ID", fixture_step)
        self.assertIn("KURANEA_CI_UNPAID_ORDER_ID", fixture_step)
        self.assertIn("id: order_lifecycle", verify_step)
        self.assertIn("verify_ci_native_order_lifecycle.php", verify_step)
        self.assertIn('expected={"status":"passed"', verify_step)
        safe_verification_artifact = verify_step.index(
            '> "$QA_ARTIFACT_DIR/order-lifecycle-verification.json"'
        )
        success_assertion = verify_step.index('expected={"status":"passed"')
        self.assertLess(
            safe_verification_artifact,
            success_assertion,
            "retain the sanitized result before failing on an unexpected outcome",
        )
        for artifact in (
            "order-lifecycle-preparation.json",
            "order-lifecycle-verification.json",
            "order-lifecycle-e2e.log",
        ):
            self.assertIn(artifact, coverage)
        self.assertIn("ORDER_LIFECYCLE_FIXTURE_OUTCOME: ${{ steps.order_lifecycle_fixture.outcome }}", aggregate)
        self.assertIn("ORDER_LIFECYCLE_OUTCOME: ${{ steps.order_lifecycle.outcome }}", aggregate)
        self.assertIn('"order_lifecycle_fixture=$ORDER_LIFECYCLE_FIXTURE_OUTCOME"', aggregate)
        self.assertIn('"order_lifecycle=$ORDER_LIFECYCLE_OUTCOME"', aggregate)


if __name__ == "__main__":
    unittest.main()
