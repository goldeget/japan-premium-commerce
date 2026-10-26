from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneabusinessprofile"


class BankTransferInstructionsContractTests(unittest.TestCase):
    def test_issuance_requires_a_dedicated_create_permission(self) -> None:
        policy = (MODULE / "src/Admin/AdminAccessPolicy.php").read_text(encoding="utf-8")
        controller = (MODULE / "controllers/admin/AdminBusinessProfileTransfersController.php").read_text(encoding="utf-8")
        self.assertIn("canIssueBankTransferInstructions", policy)
        self.assertIn("'add'", policy)
        self.assertIn("AdminAccessPolicy::canIssueBankTransferInstructions", controller)
        self.assertIn("Tools::getAdminTokenLite('AdminBusinessProfileTransfers')", controller)
        self.assertIn("hash_equals", controller)

    def test_issue_action_requires_the_live_seller_gate_or_exact_isolated_ci_gate(self) -> None:
        controller = (MODULE / "controllers/admin/AdminBusinessProfileTransfersController.php").read_text(encoding="utf-8")
        self.assertIn("$_SERVER['REQUEST_METHOD']", controller)
        self.assertIn("$_POST['token']", controller)
        self.assertIn("$this->context->employee->id", controller)
        self.assertIn("CommerceGate::isEnabled(", controller)
        self.assertIn("getenv('ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED') === '1'", controller)
        self.assertIn("CommerceGate::isIsolatedCiCheckoutEnabled()", controller)
        self.assertNotIn("PaymentModule", controller)
        self.assertNotIn("OrderHistory", controller)

    def test_generic_customer_and_email_surfaces_do_not_publish_bank_accounts(self) -> None:
        module = (MODULE / "kuraneabusinessprofile.php").read_text(encoding="utf-8")
        footer = (MODULE / "src/Customer/PublicFooterBuilder.php").read_text(encoding="utf-8")
        legal = (MODULE / "src/Customer/PublishedLegalPageBuilder.php").read_text(encoding="utf-8")
        method_start = module.index("public function hookActionGetExtraMailTemplateVars")
        method_open = module.index("{", method_start)
        depth = 0
        for index in range(method_open, len(module)):
            if module[index] == "{":
                depth += 1
            elif module[index] == "}":
                depth -= 1
                if depth == 0:
                    mail_method = module[method_open:index + 1]
                    break
        else:
            self.fail("Could not parse the extra mail variables hook body")
        blank_bank_var = mail_method.index("['{ordenowa_bank_accounts}'] = ''")
        commerce_gate = mail_method.index("if (!CommerceGate::isEnabled(")
        self.assertLess(blank_bank_var, commerce_gate, "The generic mail account variable must be blank even when the live commerce gate is closed.")
        self.assertNotIn("BankTransferPayment", footer)
        self.assertNotIn("account_number", footer)
        self.assertNotIn("BankTransferPayment", legal)
        self.assertNotIn("account_number", legal)

    def test_issuance_uses_only_existing_unpaid_jpy_orders_in_current_shop(self) -> None:
        controller = (MODULE / "controllers/admin/AdminBusinessProfileTransfersController.php").read_text(encoding="utf-8")
        self.assertIn("new Order($orderId)", controller)
        self.assertIn("OrderState", controller)
        self.assertIn("total_paid_real", controller)
        self.assertIn("'JPY'", controller)
        self.assertIn("order->id_shop", controller)
        issue = controller.split("private function processIssue", 1)[1].split("private function processConfirm", 1)[0]
        self.assertIn("$order->module !== 'ps_checkpayment'", issue)
        self.assertIn("입금 안내는 미결제 계좌이체 주문에만 발급할 수 있습니다.", issue)
        self.assertLess(
            issue.index("$order->module !== 'ps_checkpayment'"),
            issue.index("new BankTransferInstructionIssuer"),
            "a direct POST for another payment module must be rejected before issuing",
        )
        order_listing = controller.split("private function unpaidJpyOrders", 1)[1].split("private function renderOrders", 1)[0]
        self.assertIn("o.`module`", order_listing)
        self.assertIn("ps_checkpayment", order_listing)
        self.assertIn("o.`total_paid_tax_incl` > 0", order_listing)
        self.assertNotIn("PS_OS_PAYMENT", controller)

    def test_instruction_binding_is_immutable_order_keyed_and_separate_from_receipts(self) -> None:
        schema = (MODULE / "src/Infrastructure/DatabaseSchema.php").read_text(encoding="utf-8")
        repo = (MODULE / "src/Infrastructure/BankTransferInstructionRepository.php").read_text(encoding="utf-8")
        issuer = (MODULE / "src/Domain/BankTransferInstructionIssuer.php").read_text(encoding="utf-8")
        self.assertIn("PRIMARY KEY (`id_order`)", schema)
        self.assertIn("`profile_version_id` INT UNSIGNED", schema)
        self.assertIn("`bank_account_id` CHAR(32)", schema)
        self.assertIn("`issued_by_employee_id` INT UNSIGNED", schema)
        self.assertIn("`issued_at_utc` DATETIME", schema)
        self.assertIn("UNIQUE KEY `one_confirmation_per_order` (`id_order`)", schema)
        self.assertIn("receipt_reference_sha256", schema)
        self.assertIn("INSERT IGNORE", repo)
        self.assertNotIn("UPDATE `", repo)
        self.assertIn("findForOrder", issuer)
        self.assertIn("assertSameNativeOrder", issuer)
        self.assertIn("BankTransferPayment::selectedActiveAccount", issuer)

    def test_order_customer_output_reads_snapshot_and_original_profile_version(self) -> None:
        module = (MODULE / "kuraneabusinessprofile.php").read_text(encoding="utf-8")
        presenter = (MODULE / "src/Customer/BankTransferInstructionPresenter.php").read_text(encoding="utf-8")
        self.assertIn("displayOrderConfirmation", module)
        self.assertIn("displayOrderDetail", module)
        self.assertIn("BankTransferInstructionRepository", module)
        self.assertIn("->find($shopId, $instruction->profileVersionId)", module)
        self.assertNotIn("loadPublished($shopId)", module.split("private function renderIssuedTransferInstructions", 1)[1])
        self.assertIn("BankTransferInstructionPresenter::render", module)
        self.assertIn("(string) ($order->module ?? '') !== 'ps_checkpayment'", module.split("private function renderIssuedTransferInstructions", 1)[1])
        self.assertIn("htmlspecialchars", presenter)
        self.assertIn("accountId", presenter)
        self.assertIn("$customer->id ?? 0) !== (int) $order->id_customer", module)
        self.assertIn("(int) ($order->id_shop ?? 0) !== $shopId", module)

    def test_instruction_hooks_match_hummingbird_templates_and_preinstalled_registration(self) -> None:
        module = (MODULE / "kuraneabusinessprofile.php").read_text(encoding="utf-8")
        upgrade = (MODULE / "upgrade/upgrade-1.0.5.php").read_text(encoding="utf-8")
        confirmation_template = (ROOT / "themes/hummingbird/templates/checkout/order-confirmation.tpl").read_text(encoding="utf-8")
        detail_template = (ROOT / "themes/hummingbird/templates/customer/order-detail.tpl").read_text(encoding="utf-8")

        # PrestaShop 9.2 OrderConfirmationController passes ['order' => $order] to
        # displayOrderConfirmation and assigns its result to HOOK_ORDER_CONFIRMATION.
        # OrderDetailController does the same for displayOrderDetail/HOOK_DISPLAYORDERDETAIL.
        # These are the hook names and template variables emitted by the pinned Hummingbird theme.
        self.assertIn("$HOOK_ORDER_CONFIRMATION", confirmation_template)
        self.assertIn("$HOOK_DISPLAYORDERDETAIL", detail_template)
        self.assertIn("public function hookDisplayOrderConfirmation(array $params)", module)
        self.assertIn("public function hookDisplayOrderDetail(array $params)", module)
        self.assertIn("$params['order'] ?? null", module.split("private function renderIssuedTransferInstructions", 1)[1])
        self.assertIn("'displayOrderConfirmation'", module)
        self.assertIn("'displayOrderDetail'", module)
        self.assertIn("registerHook(['displayOrderConfirmation', 'displayOrderDetail'])", upgrade)

    def test_customer_instructions_hide_after_any_native_payment_is_recorded(self) -> None:
        module = (MODULE / "kuraneabusinessprofile.php").read_text(encoding="utf-8")
        render = module.split("private function renderIssuedTransferInstructions", 1)[1].split("private function shopId", 1)[0]
        self.assertIn("$this->hasRecordedPayment($order)", render)
        self.assertIn("total_paid_real", module)

    def test_schema_upgrade_preserves_existing_profile_tables_and_instructions(self) -> None:
        upgrade = (MODULE / "upgrade/upgrade-1.0.5.php").read_text(encoding="utf-8")
        self.assertIn("$repository->install()", upgrade)
        self.assertIn("registerHook(['displayOrderConfirmation', 'displayOrderDetail'])", upgrade)
        self.assertIn("$module->installTransferInstructionsTab()", upgrade)
        self.assertNotIn("DROP TABLE", upgrade.upper())

    def test_isolated_module_bootstrap_repairs_payment_schema_for_an_already_installed_module(self) -> None:
        bootstrap = (ROOT / "docker/kuran-install-modules.php").read_text(encoding="utf-8")
        module = (MODULE / "kuraneabusinessprofile.php").read_text(encoding="utf-8")
        self.assertIn("$businessProfileModule->ensureBankTransferInfrastructure()", bootstrap)
        self.assertLess(bootstrap.index("foreach (['kuraneapostcode'"), bootstrap.index("ensureBankTransferInfrastructure"))
        self.assertIn("public function ensureBankTransferInfrastructure(): bool", module)
        ensure = module.split("public function ensureBankTransferInfrastructure(): bool", 1)[1].split("public function uninstall()", 1)[0]
        self.assertIn("(new VersionedProfileRepository())->install()", ensure)
        self.assertIn("registerHook(['displayOrderConfirmation', 'displayOrderDetail'])", ensure)
        self.assertIn("installTransferInstructionsTab()", ensure)
        self.assertNotIn("DROP TABLE", ensure.upper())


if __name__ == "__main__":
    unittest.main()
