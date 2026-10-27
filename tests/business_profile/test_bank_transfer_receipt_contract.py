from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneabusinessprofile"


class BankTransferReceiptContractTests(unittest.TestCase):
    def test_confirmation_uses_a_separate_edit_permission_and_csrf_post(self) -> None:
        policy = (MODULE / "src/Admin/AdminAccessPolicy.php").read_text(encoding="utf-8")
        controller = (MODULE / "controllers/admin/AdminBusinessProfileTransfersController.php").read_text(encoding="utf-8")
        self.assertIn("canConfirmBankTransferReceipt", policy)
        self.assertIn("self::granted($tabAccess, 'edit')", policy)
        self.assertIn("submitOrdenowaConfirmBankTransfer", controller)
        self.assertIn("AdminAccessPolicy::canConfirmBankTransferReceipt", controller)
        self.assertIn("$_SERVER['REQUEST_METHOD']", controller)
        self.assertIn("hash_equals", controller)
        self.assertIn("$_POST['verified_transfer']", controller)
        installation = (ROOT / "tests/business_profile/verify_installation.php").read_text(encoding="utf-8")
        self.assertIn("ADMINBUSINESSPROFILETRANSFERS_UPDATE", installation)

    def test_confirmation_uses_native_payment_and_history_in_a_transaction(self) -> None:
        confirmer = (MODULE / "src/Infrastructure/BankTransferReceiptConfirmer.php").read_text(encoding="utf-8")
        for required in (
            "START TRANSACTION",
            "FOR UPDATE",
            "addOrderPayment(",
            "changeIdOrderState(",
            "->add()",
            "COMMIT",
            "ROLLBACK",
            "id_order_payment",
            "id_order_history",
            "total_paid_real",
            "current_state",
        ):
            self.assertIn(required, confirmer)
        lock_query = confirmer.split("$lockedOrders = $this->database->executeS(", 1)[1].split(");", 1)[0]
        self.assertIn("LIMIT 1 FOR UPDATE", lock_query)
        self.assertIn("true,\n                false", lock_query)
        self.assertNotIn("$lockedOrderId = (int) $this->database->getValue(", confirmer)
        self.assertNotIn("addWithemail", confirmer)
        self.assertNotIn("Mail::Send", confirmer)

    def test_receipt_ledger_stores_only_a_reference_digest_and_native_ids(self) -> None:
        schema = (MODULE / "src/Infrastructure/DatabaseSchema.php").read_text(encoding="utf-8")
        repository = (MODULE / "src/Infrastructure/BankTransferReceiptRepository.php").read_text(encoding="utf-8")
        confirmer = (MODULE / "src/Infrastructure/BankTransferReceiptConfirmer.php").read_text(encoding="utf-8")
        self.assertIn("receipt_reference_sha256", schema)
        self.assertIn("id_order_payment", schema)
        self.assertIn("id_order_history", schema)
        self.assertIn("bank_account_id", schema)
        receipt_table = schema.split("function createBankTransferReceiptLedgerTableSql", 1)[1].split("private function assertPrefix", 1)[0]
        self.assertNotIn("bank_statement_reference", receipt_table)
        self.assertIn("hash('sha256'", confirmer)
        self.assertNotIn("bank_statement_reference", repository)
        self.assertIn("UNIQUE KEY `one_confirmation_per_order`", receipt_table)
        self.assertIn("UNIQUE KEY `one_use_per_bank_reference`", receipt_table)
        self.assertIn("findByStatementReference", repository)

    def test_receipt_confirmation_is_exact_and_synthetic_only_in_the_isolated_ci_gate(self) -> None:
        confirmer = (MODULE / "src/Infrastructure/BankTransferReceiptConfirmer.php").read_text(encoding="utf-8")
        self.assertIn("CommerceGate::isIsolatedCiCheckoutEnabled()", confirmer)
        self.assertIn("BankTransferInstructionRepositoryInterface", confirmer)
        self.assertIn("currencyIso", confirmer)
        self.assertIn("orderReference", confirmer)
        self.assertIn("receivedAmount", confirmer)
        self.assertIn("verifiedTransfer", confirmer)
        self.assertIn("referenceDigest", confirmer)
        self.assertIn("total_paid_real", confirmer)
        self.assertIn("assertSameNativeOrder", confirmer)
        self.assertIn("idempot", confirmer.lower())
        self.assertIn("JpyAmount::normalizePositive", confirmer)
        self.assertIn("다른 주문", confirmer)

    def test_receipt_confirmation_rejects_orders_created_with_another_payment_method(self) -> None:
        confirmer = (MODULE / "src/Infrastructure/BankTransferReceiptConfirmer.php").read_text(encoding="utf-8")
        native_order_guard = confirmer.split("private function assertSameNativeOrder", 1)[1].split(
            "private function assertUnpaidOrder", 1
        )[0]
        self.assertIn("(string) ($order->module ?? '') !== 'ps_checkpayment'", native_order_guard)
        fixture = (ROOT / "tests/business_profile/bank_transfer_receipt_confirmation.php").read_text(encoding="utf-8")
        self.assertIn("$wrongPaymentMethodOrder['module'] = 'ps_wirepayment'", fixture)
        self.assertIn("A JPY order placed through a different payment module must not be confirmed as a bank transfer.", fixture)

    def test_retries_reuse_the_existing_payment_and_history_without_mutation(self) -> None:
        confirmer = (MODULE / "src/Infrastructure/BankTransferReceiptConfirmer.php").read_text(encoding="utf-8")
        self.assertIn("findForOrder", confirmer)
        self.assertIn("sameReceipt", confirmer)
        self.assertIn("return new BankTransferReceiptConfirmation", confirmer)
        self.assertIn("assertNativeReadback", confirmer)
        self.assertIn("!$this->isZeroAmount((string) $order->total_paid_real)", confirmer)

    def test_controller_does_not_confirm_until_manual_attestation_and_matching_reference(self) -> None:
        controller = (MODULE / "controllers/admin/AdminBusinessProfileTransfersController.php").read_text(encoding="utf-8")
        self.assertIn("received_amount", controller)
        self.assertIn("bank_statement_reference", controller)
        self.assertIn("verified_transfer", controller)
        self.assertIn("전액 입금을 직접 확인했습니다", controller)
        self.assertIn("CommerceGate::isIsolatedCiCheckoutEnabled()", controller)
        self.assertIn("CommerceGate::isEnabled(", controller)
        confirm = controller.split("private function processConfirm", 1)[1].split("private function unpaidJpyOrders", 1)[0]
        self.assertLess(confirm.index("hasValidAdminMutationToken"), confirm.index("->confirm("))
        self.assertLess(confirm.index("canConfirmBankTransferReceipt"), confirm.index("->confirm("))
        self.assertLess(confirm.index("!$verifiedTransfer"), confirm.index("->confirm("))
        self.assertIn("입금 사실을 확인해야 합니다", confirm)

    def test_admin_transfer_errors_do_not_expose_untranslated_exception_text(self) -> None:
        controller = (MODULE / "controllers/admin/AdminBusinessProfileTransfersController.php").read_text(encoding="utf-8")
        presenter = (MODULE / "src/Admin/AdminErrorMessage.php").read_text(encoding="utf-8")
        issue = controller.split("private function processIssue", 1)[1].split(
            "private function processConfirm", 1
        )[0]
        confirm = controller.split("private function processConfirm", 1)[1].split(
            "private function unpaidJpyOrders", 1
        )[0]
        self.assertIn("AdminErrorMessage::fromException(", issue)
        self.assertIn("AdminErrorMessage::fromException(", confirm)
        self.assertIn("주문 입금 안내를 발급하지 못했습니다.", issue)
        self.assertIn("주문 입금을 확인하지 못했습니다.", confirm)
        self.assertIn("preg_match('/[가-힣]/u', $message) === 1", presenter)
        self.assertIn("$exception instanceof \\InvalidArgumentException", presenter)
        self.assertIn("SAFE_TRANSFER_RUNTIME_MESSAGES", presenter)
        self.assertIn("in_array($message, self::SAFE_TRANSFER_RUNTIME_MESSAGES, true)", presenter)
        self.assertIn("return $fallback;", presenter)

    def test_issue_and_customer_rendering_reject_fractional_yen(self) -> None:
        instruction = (MODULE / "src/Domain/BankTransferInstruction.php").read_text(encoding="utf-8")
        controller = (MODULE / "controllers/admin/AdminBusinessProfileTransfersController.php").read_text(encoding="utf-8")
        self.assertIn("JpyAmount::normalizePositive($totalPaid)", instruction)
        self.assertIn("JpyAmount::normalizePositive($amount) !== null", controller)
        self.assertIn("$this->hasRecordedPayment($order)", (MODULE / "kuraneabusinessprofile.php").read_text(encoding="utf-8"))

    def test_synthetic_php_fixture_covers_success_retry_denials_and_rollback(self) -> None:
        fixture = (ROOT / "tests/business_profile/bank_transfer_receipt_confirmation.php").read_text(encoding="utf-8")
        for expected in (
            "setReceiptIsolatedCi(false)",
            "setReceiptIsolatedCi(true)",
            "Without a positive staff attestation",
            "A partial payment",
            "An overpayment",
            "partial paid amount",
            "pre-existing payment row",
            "An identical retry",
            "conflicting reference retry",
            "same bank statement reference must never confirm a second order",
            "History failure must roll back",
            "Ledger failure must roll back",
            "concurrent receipt with the same account-scoped digest",
            "different shop order",
            "non-JPY native order",
        ):
            self.assertIn(expected, fixture)

    def test_synthetic_fixture_guard_uses_the_prestashop_bootstrap_marker(self) -> None:
        fixture = (ROOT / "tests/business_profile/bank_transfer_receipt_confirmation.php").read_text(encoding="utf-8")
        guard = fixture.split("if (defined('_PS_VERSION_'))", 1)
        self.assertEqual(len(guard), 2, "The receipt fixture must refuse to run inside a bootstrapped PrestaShop process.")
        self.assertLess(guard[1].index("throw new RuntimeException"), guard[1].index("final class FakeTransferReceiptDb"))
        self.assertNotIn("class_exists('Db', false)", fixture, "A fake Db class declared later in this fixture must not trip its own guard.")

    def test_in_memory_instruction_repository_implements_immutable_insert_contract(self) -> None:
        fixture = (ROOT / "tests/business_profile/bank_transfer_receipt_confirmation.php").read_text(encoding="utf-8")
        repository = fixture.split("final class InMemoryReceiptInstructionRepository", 1)[1].split(
            "final class InMemoryReceiptLedger", 1
        )[0]
        self.assertIn("insertIfAbsent(BankTransferInstruction $instruction): bool", repository)
        self.assertIn("$instruction->shopId . ':' . $instruction->orderId", repository)
        self.assertIn("isset($this->instructions[$key])", repository)
        self.assertIn("$this->instructions[$key] = $instruction", repository)

    def test_standalone_fixture_provides_only_the_sql_escaping_primitive_it_uses(self) -> None:
        fixture = (ROOT / "tests/business_profile/bank_transfer_receipt_confirmation.php").read_text(encoding="utf-8")
        self.assertIn("if (!function_exists('pSQL'))", fixture)
        self.assertIn("function pSQL(string $value", fixture)
        self.assertIn("return addslashes($value)", fixture)

    def test_installation_table_readback_does_not_duplicate_native_get_value_limit(self) -> None:
        verifier = (ROOT / "tests/business_profile/verify_installation.php").read_text(encoding="utf-8")
        query = verifier.split("$database->getValue(", 1)[1].split(") === $requiredTable", 1)[0]
        self.assertIn("information_schema.TABLES", query)
        self.assertIn("TABLE_NAME = '", query)
        self.assertNotIn("LIMIT 1", query.upper())
        self.assertIn(",\n            false", query)


if __name__ == "__main__":
    unittest.main()
