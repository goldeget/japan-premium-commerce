from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneabackoffice"


class EmployeeProfileAuditContractTests(unittest.TestCase):
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
        self.assertIn("pageForShop($shopId, $page)", controller)
        self.assertIn("PAGE_SIZE = 50", controller)
        self.assertNotRegex(controller, re.compile(r"<form|<input|method=[\"']post|submit[A-Za-z]", re.I))
        for field in ("actor_employee_id", "target_employee_id", "old_profile_id", "new_profile_id", "changed_at_utc"):
            self.assertIn(field, controller)
        self.assertNotRegex(controller, re.compile(r"\b(?:email|firstname|lastname|password|token|address1|address2)\b", re.I))
        self.assertNotIn("AdminAccessController", controller)
        self.assertNotIn("Access::", controller)

    def test_module_installs_additive_audit_schema_tab_and_employee_hooks(self) -> None:
        module = (MODULE / "kuraneabackoffice.php").read_text(encoding="utf-8")
        self.assertIn("$this->version = '1.0.3';", module)
        self.assertIn("installEmployeeProfileAudit", module)
        self.assertIn("installEmployeeProfileAuditTab", module)
        self.assertIn("AdminKuraneaEmployeeProfileAudit", module)
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

    def test_php_fixture_and_source_contract_run_in_existing_business_profile_workflow(self) -> None:
        fixture = (ROOT / "tests" / "admin_audit" / "employee_profile_audit.php").read_text(encoding="utf-8")
        self.assertIn("$module->install()", fixture)
        self.assertIn("upgrade_module_1_0_3($module)", fixture)
        self.assertIn("in_array($hookName, self::$module->registeredHooks, true)", fixture)
        workflow = (ROOT / ".github" / "workflows" / "business-profile.yml").read_text(encoding="utf-8")
        self.assertIn("php tests/admin_audit/employee_profile_audit.php", workflow)
        self.assertIn("discover -s tests/admin_audit -p 'test_*.py'", workflow)
        self.assertIn("tests/admin_audit/**", workflow)


if __name__ == "__main__":
    unittest.main()
