from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneabackoffice"


class EmployeeProfileAuditContractTests(unittest.TestCase):
    def test_module_admin_controller_fixture_matches_prestashop_92_init_header_signature(self) -> None:
        fixture = (ROOT / "tests" / "admin_audit" / "employee_profile_audit.php").read_text(encoding="utf-8")
        parent = fixture.split("class ModuleAdminController\n{", 1)[1].split("\n}\n\nfinal class Hook", 1)[0]

        # In pinned PrestaShop 9.2.0, ModuleAdminControllerCore inherits
        # AdminControllerCore::initHeader(), which has no declared return type.
        self.assertRegex(parent, re.compile(r"public function initHeader\(\)\s*\{"))
        self.assertNotRegex(parent, re.compile(r"public function initHeader\(\)\s*:\s*void"))

    def test_schema_is_shop_scoped_and_contains_only_profile_transition_identifiers(self) -> None:
        schema_path = MODULE / "src" / "Infrastructure" / "EmployeeProfileAuditSchema.php"
        self.assertTrue(schema_path.is_file(), "missing employee profile audit schema")
        schema = schema_path.read_text(encoding="utf-8")
        for field in (
            "id_event", "id_shop", "actor_employee_id", "target_employee_id",
            "old_profile_id", "new_profile_id", "changed_at_utc",
        ):
            self.assertIn(f"`{field}`", schema)
        self.assertIn("AUTO_INCREMENT", schema)
        self.assertIn("DATETIME", schema)
        self.assertNotRegex(schema, re.compile(r"`(?:email|firstname|lastname|password|token|address)[^`]*`", re.I))
        self.assertNotRegex(schema, re.compile(r"UPDATE\s+`[^`]*employee_profile_audit|DELETE\s+FROM\s+`[^`]*employee_profile_audit", re.I))

    def test_repository_compares_persisted_profiles_and_exposes_bounded_shop_pages(self) -> None:
        repository_path = MODULE / "src" / "Infrastructure" / "EmployeeProfileAuditRepository.php"
        self.assertTrue(repository_path.is_file(), "missing employee profile audit repository")
        repository = repository_path.read_text(encoding="utf-8")
        self.assertIn("profileIdForEmployee", repository)
        self.assertIn("appendProfileChange", repository)
        self.assertIn("pageForShop", repository)
        self.assertIn("changed_at_utc", repository)
        self.assertIn("gmdate('Y-m-d H:i:s')", repository)
        self.assertRegex(repository, re.compile(r"LIMIT\s*['\"]?51", re.I))
        self.assertIn("WHERE (`id_shop` = ' . $shopId . ' OR `id_shop` = 0)", repository)
        self.assertNotRegex(repository, re.compile(r"function\s+(?:update|delete|remove)\w*\s*\(", re.I))
        self.assertNotRegex(repository, re.compile(r"UPDATE\s+`[^`]*employee_profile_audit|DELETE\s+FROM\s+`[^`]*employee_profile_audit", re.I))
        self.assertNotRegex(repository, re.compile(r"\b(?:email|firstname|lastname|passwd|password|token|address1|address2)\b", re.I))

    def test_observer_captures_old_state_before_and_appends_only_persisted_change_after(self) -> None:
        observer_path = MODULE / "src" / "Admin" / "EmployeeProfileAuditObserver.php"
        self.assertTrue(observer_path.is_file(), "missing Employee ObjectModel audit observer")
        observer = observer_path.read_text(encoding="utf-8")
        self.assertRegex(observer, re.compile(r"beforeUpdate\([^)]*\).*?profileIdForEmployee", re.S))
        self.assertRegex(observer, re.compile(r"afterUpdate\([^)]*\).*?profileIdForEmployee", re.S))
        self.assertIn("appendProfileChange", observer)
        self.assertIn("'actorEmployeeId' => $actorId > 0 ? $actorId : null", observer)
        self.assertIn("spl_object_id", observer)

        module = (MODULE / "kuraneabackoffice.php").read_text(encoding="utf-8")
        self.assertIn("actionObjectEmployeeUpdateBefore", module)
        self.assertIn("actionObjectEmployeeUpdateAfter", module)
        self.assertIn("EmployeeProfileAuditObserver::beforeUpdate", module)
        self.assertIn("EmployeeProfileAuditObserver::afterUpdate", module)

    def test_audit_tab_requires_native_view_permission_and_reads_only_one_shop(self) -> None:
        controller_path = MODULE / "controllers" / "admin" / "AdminKuraneaEmployeeProfileAuditController.php"
        self.assertTrue(controller_path.is_file(), "missing read-only employee profile audit page")
        controller = controller_path.read_text(encoding="utf-8")
        self.assertIn("$this->viewAccess()", controller)
        self.assertIn("$this->tabAccess['view']", controller)
        self.assertIn("Shop::CONTEXT_SHOP", controller)
        self.assertIn("AdminAuditEventRepository", controller)
        self.assertIn("pageForShop($shopId, $page, $authorizedSources)", controller)
        self.assertIn("canViewSourceTab('ADMINKURANEASUPPORTASSIGNMENTS')", controller)
        self.assertIn("canViewSourceTab('ADMINBUSINESSPROFILETRANSFERS')", controller)
        self.assertNotRegex(controller, re.compile(r"<form|<input|method=[\"']post|submit[A-Za-z]", re.I))
        for field in ("actor_employee_id", "event_at", "source", "action", "target_id"):
            self.assertIn(field, controller)
        self.assertNotRegex(controller, re.compile(r"\b(?:email|firstname|lastname|password|token|address1|address2)\b", re.I))
        self.assertNotIn("AdminAccessController", controller)

    def test_order_status_audit_reads_native_history_read_only_and_shop_scoped(self) -> None:
        repository_path = MODULE / "src" / "Infrastructure" / "OrderHistoryAuditRepository.php"
        self.assertTrue(repository_path.is_file(), "missing native order history audit read model")
        repository = repository_path.read_text(encoding="utf-8")
        for field in ("id_order_history", "id_order", "reference", "id_order_state", "id_employee", "date_add"):
            self.assertIn(field, repository)
        self.assertIn("INNER JOIN `", repository)
        self.assertIn("$this->prefix . 'orders`", repository)
        self.assertIn("' WHERE o.`id_shop` = ' . $shopId", repository)
        self.assertIn("$this->prefix . 'order_state_lang`", repository)
        self.assertIn("LIMIT 51 OFFSET", repository)
        self.assertNotRegex(repository, re.compile(r"\b(?:INSERT|UPDATE|DELETE|REPLACE)\b", re.I))
        self.assertNotRegex(repository, re.compile(r"\b(?:email|firstname|lastname|passwd|password|token|address1|address2)\b", re.I))

        controller = (MODULE / "controllers" / "admin" / "AdminKuraneaEmployeeProfileAuditController.php").read_text(encoding="utf-8")
        self.assertIn("canViewOrderHistory()", controller)
        self.assertIn("return $this->canViewSourceTab('ADMINORDERS');", controller)
        self.assertIn("Permission::PREFIX_TAB . strtoupper($tabClass) . '_READ'", controller)
        self.assertIn("$authorizedSources[] = 'order_history'", controller)
        self.assertIn("use PrestaShop\\PrestaShop\\Core\\Security\\Permission;", controller)
        self.assertIn("renderEvents", controller)
        self.assertIn("주문 상태 변경", controller)
        self.assertNotRegex(controller, re.compile(r"<form|<input|method=[\"']post", re.I))

    def test_activity_repository_is_bounded_scoped_read_only_and_allowlists_safe_fields(self) -> None:
        repository_path = MODULE / "src" / "Infrastructure" / "AdminAuditEventRepository.php"
        self.assertTrue(repository_path.is_file(), "missing unified read-only audit feed repository")
        repository = repository_path.read_text(encoding="utf-8")
        self.assertIn("PAGE_SIZE = 50", repository)
        self.assertIn("ORDER BY `event_at` DESC, `event_source` ASC, `event_id` DESC", repository)
        self.assertIn("LIMIT ' . (self::PAGE_SIZE + 1) . ' OFFSET ' . $offset", repository)
        for source in (
            "employee_profile", "order_history", "support_assignment",
            "bank_transfer_instruction", "bank_transfer_receipt",
        ):
            self.assertIn(f"'{source}'", repository)
        self.assertIn("WHERE (`id_shop` = ' . $shopId . ' OR `id_shop` = 0)", repository)
        self.assertIn("WHERE o.`id_shop` = ' . $shopId", repository)
        self.assertIn("WHERE `id_shop` = ' . $shopId", repository)
        self.assertIn("// Copy only allowlisted audit fields", repository)
        self.assertIn("'source' => $source", repository)
        self.assertIn("'target_id' => $targetId", repository)
        self.assertNotRegex(repository, re.compile(r"\b(?:email|message|profile_json|bank_account_id|receipt_reference_sha256|order_reference|received_amount)\b", re.I))
        self.assertNotRegex(repository, re.compile(r"\b(?:INSERT|UPDATE|DELETE|REPLACE)\b", re.I))

    def test_activity_fixture_covers_global_ordering_acl_escape_and_sensitive_exclusion(self) -> None:
        fixture = (ROOT / "tests" / "admin_audit" / "employee_profile_audit.php").read_text(encoding="utf-8")
        for expected in (
            "The combined activity feed should cap rows at fifty.",
            "The combined feed should order timestamp ties deterministically across sources.",
            "ADMINKURANEASUPPORTASSIGNMENTS_READ:2",
            "ADMINBUSINESSPROFILETRANSFERS_READ:2",
            "PRIVATE-CONTACT",
            "PRIVATE-REFERENCE-DIGEST",
            "&lt;script&gt;alert(1)&lt;/script&gt;",
            "A reader without native view permission must not query audit rows.",
            "The page should reject all-shop context before querying audit events.",
        ):
            self.assertIn(expected, fixture)
        self.assertIn("'source', 'event_id', 'event_at', 'time_basis', 'actor_employee_id', 'action', 'target_type', 'target_id'", fixture)

    def test_order_history_php_fixture_parses_the_production_shop_alias_format(self) -> None:
        fixture = (ROOT / "tests" / "admin_audit" / "employee_profile_audit.php").read_text(encoding="utf-8")
        self.assertIn("preg_match('/o\\.`id_shop`\\s*=\\s*(\\d+)/', $sql, $shopMatch);", fixture)
        self.assertIn("WHERE o.`id_shop` = 7", fixture)

    def test_order_history_fixture_grants_the_native_permission_slug_used_by_the_controller(self) -> None:
        fixture = (ROOT / "tests" / "admin_audit" / "employee_profile_audit.php").read_text(encoding="utf-8")
        self.assertIn("Access::$grants[Permission::PREFIX_TAB . 'ADMINORDERS_READ:2'] = true;", fixture)
        self.assertIn("Access::isGranted($ordersReadRole, $profileId)", fixture)
        self.assertIn("$ordersReadRole = Permission::PREFIX_TAB . 'ADMINORDERS_READ';", fixture)
        self.assertIn("Context::$instance->employee = (object) ['id' => 90, 'id_profile' => 2];", fixture)

    def test_module_installs_additive_audit_schema_tab_and_employee_hooks(self) -> None:
        module = (MODULE / "kuraneabackoffice.php").read_text(encoding="utf-8")
        self.assertIn("$this->version = '1.0.6';", module)
        self.assertIn("installEmployeeProfileAudit", module)
        self.assertIn("installEmployeeProfileAuditTab", module)
        self.assertIn("AdminKuraneaEmployeeProfileAudit", module)
        self.assertIn("관리자 감사 기록", module)
        self.assertIn("EmployeeProfileAuditSchema::tableSql", module)
        self.assertIn("actionObjectEmployeeUpdateBefore", module)
        self.assertIn("actionObjectEmployeeUpdateAfter", module)
        installer = module.split("public function installEmployeeProfileAudit(): bool", 1)[1].split(
            "public function installEmployeeProfileAuditTab(): bool", 1
        )[0]
        self.assertIn("$this->registerHook([", installer)
        self.assertNotIn("AdminAccessController", installer)
        self.assertNotIn("Access::", installer)
        self.assertNotRegex(module, re.compile(r"DROP\s+TABLE", re.I))

        upgrade_path = MODULE / "upgrade" / "upgrade-1.0.3.php"
        self.assertTrue(upgrade_path.is_file(), "missing additive employee audit upgrade")
        upgrade = upgrade_path.read_text(encoding="utf-8")
        self.assertIn("installEmployeeProfileAudit", upgrade)
        self.assertNotRegex(upgrade, re.compile(r"DROP\s+TABLE", re.I))
        audit_upgrade = (MODULE / "upgrade" / "upgrade-1.0.5.php").read_text(encoding="utf-8")
        self.assertIn("upgrade_module_1_0_5", audit_upgrade)
        self.assertIn("installEmployeeProfileAuditTab", audit_upgrade)
        self.assertNotRegex(audit_upgrade, re.compile(r"DROP\s+TABLE", re.I))

    def test_native_acl_upgrade_registers_official_hooks_without_core_mutations(self) -> None:
        module = (MODULE / "kuraneabackoffice.php").read_text(encoding="utf-8")
        for hook in ("actionAdminUpdateAccessBefore", "actionAdminUpdateModuleAccessBefore"):
            self.assertIn(hook, module)
        self.assertIn("NativeAclAuditSchema::tableSql", module)
        self.assertIn("installNativeAclAudit", (MODULE / "upgrade/upgrade-1.0.6.php").read_text(encoding="utf-8"))
        observer = (MODULE / "src/Admin/NativeAclAuditObserver.php").read_text(encoding="utf-8")
        self.assertIn("$controller->checkToken()", observer)
        self.assertIn("$controller->access('edit')", observer)
        self.assertIn("register_shutdown_function", observer)
        self.assertIn("$repository->commit()", observer)
        self.assertIn("$repository->rollback()", observer)
        self.assertIn("$body !== 'ok'", observer)
        self.assertIn("ob_start", observer)
        self.assertNotIn("updateLgcAccess(", observer)
        self.assertNotIn("updateLgcModuleAccess(", observer)
        fixture = (ROOT / "tests/admin_audit/native_acl_atomic.php").read_text(encoding="utf-8")
        self.assertIn("synthetic audit persistence failure", fixture)
        self.assertIn("worker-fatal", fixture)
        self.assertIn("worker-die", fixture)

    def test_php_fixture_and_source_contract_run_in_existing_business_profile_workflow(self) -> None:
        fixture = (ROOT / "tests" / "admin_audit" / "employee_profile_audit.php").read_text(encoding="utf-8")
        self.assertIn("$module->install()", fixture)
        self.assertIn("upgrade_module_1_0_3($module)", fixture)
        self.assertIn("upgrade_module_1_0_5($module)", fixture)
        self.assertIn("in_array($hookName, self::$module->registeredHooks, true)", fixture)
        workflow = (ROOT / ".github" / "workflows" / "business-profile.yml").read_text(encoding="utf-8")
        self.assertIn("php tests/admin_audit/employee_profile_audit.php", workflow)
        self.assertIn("discover -s tests/admin_audit -p 'test_*.py'", workflow)
        self.assertIn("tests/admin_audit/**", workflow)


if __name__ == "__main__":
    unittest.main()
