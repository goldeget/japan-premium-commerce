from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneabackoffice"


class SupportAssignmentContractTests(unittest.TestCase):
    def test_assignment_storage_is_shop_scoped_and_has_append_only_history(self) -> None:
        schema = MODULE / "src" / "Infrastructure" / "SupportAssignmentSchema.php"
        self.assertTrue(schema.is_file(), "missing support assignment schema")
        source = schema.read_text(encoding="utf-8")
        self.assertIn("kuraneabackoffice_support_assignment`", source)
        self.assertIn("PRIMARY KEY (`id_shop`, `id_customer_thread`)", source)
        self.assertIn("kuraneabackoffice_support_assignment_history`", source)
        for field in ("id_shop", "id_customer_thread", "from_employee_id", "to_employee_id", "actor_employee_id", "changed_at_utc"):
            self.assertIn(f"`{field}`", source)
        self.assertIn("AUTO_INCREMENT", source)
        self.assertNotRegex(source, re.compile(r"(?:UPDATE|DELETE\s+FROM)\s+`[^`]*assignment_history`", re.I))

    def test_assignment_repository_validates_thread_and_employee_inside_transaction(self) -> None:
        repository = MODULE / "src" / "Infrastructure" / "SupportAssignmentRepository.php"
        self.assertTrue(repository.is_file(), "missing support assignment repository")
        source = repository.read_text(encoding="utf-8")
        self.assertIn("START TRANSACTION", source)
        self.assertIn("FOR UPDATE", source)
        self.assertIn("customer_thread", source)
        self.assertIn("employee_shop", source)
        self.assertRegex(source, re.compile(r"employee.*?active`\s*=\s*1.*?employee_shop", re.S))
        self.assertIn("INSERT INTO", source)
        self.assertIn("assignment_history", source)
        self.assertIn("ROLLBACK", source)

    def test_locking_selects_bypass_prestashop_query_cache(self) -> None:
        repository = MODULE / "src" / "Infrastructure" / "SupportAssignmentRepository.php"
        self.assertTrue(repository.is_file(), "missing support assignment repository")
        source = repository.read_text(encoding="utf-8")
        self.assertRegex(
            source,
            re.compile(r"private function rows\(string \$sql, string \$failureMessage, bool \$useCache = true\)"),
            "read helper must expose an explicit cache setting",
        )
        self.assertIn("executeS($sql, true, $useCache)", source)
        lock_reads = re.findall(
            r"\$this->rows\((?:(?!\$this->rows\().)*?FOR UPDATE(?:(?!\$this->rows\().)*?\n\s*\)",
            source,
            re.S,
        )
        self.assertEqual(4, len(lock_reads), "all thread, assignment, employee and actor locks are required")
        for call in lock_reads:
            self.assertRegex(call, re.compile(r",\s*false\s*\)$"), "FOR UPDATE query must bypass cached SELECT results")

    def test_create_and_update_permissions_are_checked_under_assignment_lock(self) -> None:
        repository = MODULE / "src" / "Infrastructure" / "SupportAssignmentRepository.php"
        controller = MODULE / "controllers" / "admin" / "AdminKuraneaSupportAssignmentsController.php"
        self.assertTrue(repository.is_file())
        self.assertTrue(controller.is_file())
        repository_source = repository.read_text(encoding="utf-8")
        controller_source = controller.read_text(encoding="utf-8")
        self.assertIn("bool $canCreate", repository_source)
        self.assertIn("bool $canUpdate", repository_source)
        self.assertIn("$fromEmployeeId === null && !$canCreate", repository_source)
        self.assertIn("$fromEmployeeId !== null && !$canUpdate", repository_source)
        self.assertIn("$this->canCreate(),", controller_source)
        self.assertIn("$this->canUpdate()", controller_source)

    def test_controller_requires_view_add_or_edit_and_native_post_token(self) -> None:
        controller = MODULE / "controllers" / "admin" / "AdminKuraneaSupportAssignmentsController.php"
        self.assertTrue(controller.is_file(), "missing support assignment Back Office controller")
        source = controller.read_text(encoding="utf-8")
        self.assertIn("viewAccess()", source)
        self.assertIn("$this->tabAccess['view']", source)
        self.assertIn("$this->access('add')", source)
        self.assertIn("$this->access('edit')", source)
        self.assertIn("$_SERVER['REQUEST_METHOD']", source)
        self.assertIn("hash_equals(", source)
        self.assertIn("Tools::getAdminTokenLite('AdminKuraneaSupportAssignments')", source)
        self.assertIn("Shop::CONTEXT_SHOP", source)
        self.assertIn("preg_match('/\\A[1-9][0-9]{0,9}\\z/D'", source)

    def test_paginated_controller_uses_lookahead_and_preserves_page_in_forms_and_history(self) -> None:
        controller = (MODULE / "controllers" / "admin" / "AdminKuraneaSupportAssignmentsController.php").read_text(encoding="utf-8")
        self.assertIn("$page = $this->requestedPage();", controller)
        self.assertIn("$repository->threadsForShop($shopId, $page)", controller)
        self.assertIn("$hasNextPage = count($threads) > 100;", controller)
        self.assertRegex(controller, re.compile(r"if \(\$hasNextPage\) \{\s*array_pop\(\$threads\);", re.S))
        self.assertIn("$actionUrl .= '&support_page=' . $page;", controller)
        self.assertIn("$this->renderThreadTable($threads, $employees, $actionUrl, $token)", controller)
        self.assertIn("$this->renderPagination($paginationUrl, $page, $hasNextPage)", controller)
        self.assertIn("$actionUrl . '&id_customer_thread=' . $threadId", controller)

    def test_support_status_column_uses_korean_labels_without_raw_status_output(self) -> None:
        controller = (MODULE / "controllers" / "admin" / "AdminKuraneaSupportAssignmentsController.php").read_text(encoding="utf-8")
        self.assertIn("$this->statusLabel((string) ($thread['status'] ?? ''))", controller)
        for native_status, korean_label in (("open", "접수"), ("closed", "종결"), ("pending1", "보류 1"), ("pending2", "보류 2")):
            with self.subTest(status=native_status):
                self.assertIn(f"'{native_status}' => '{korean_label}'", controller)
        self.assertIn("default => '상태 확인 필요'", controller)

    def test_controller_and_repository_do_not_fetch_customer_email_or_address(self) -> None:
        controller = MODULE / "controllers" / "admin" / "AdminKuraneaSupportAssignmentsController.php"
        repository = MODULE / "src" / "Infrastructure" / "SupportAssignmentRepository.php"
        self.assertTrue(controller.is_file())
        self.assertTrue(repository.is_file())
        combined = controller.read_text(encoding="utf-8") + repository.read_text(encoding="utf-8")
        self.assertNotRegex(combined, r"customer_thread.{0,400}(?:email|address)", re.I | re.S)
        self.assertNotRegex(combined, r"customer\.`(?:email|firstname|lastname|address1|address2)`", re.I)

    def test_assignment_upgrade_registers_schema_and_admin_tab_without_dropping_data(self) -> None:
        module = (MODULE / "kuraneabackoffice.php").read_text(encoding="utf-8")
        upgrade = MODULE / "upgrade" / "upgrade-1.0.2.php"
        self.assertTrue(upgrade.is_file(), "missing additive support assignment upgrade")
        upgrade_source = upgrade.read_text(encoding="utf-8")
        self.assertIn("installSupportAssignments", upgrade_source)
        self.assertIn("installSupportAssignments", module)
        self.assertIn("AdminKuraneaSupportAssignments", module)
        self.assertNotRegex(upgrade_source + module, r"DROP\s+TABLE", re.I)

    def test_module_workflow_tracks_imported_support_browser_test_dependencies(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "business-profile.yml").read_text(encoding="utf-8")
        push_paths = workflow.split("  push:", 1)[1].split("  pull_request:", 1)[0]
        pull_request_paths = workflow.split("  pull_request:", 1)[1].split("  workflow_dispatch:", 1)[0]
        for event, paths in (("push", push_paths), ("pull_request", pull_request_paths)):
            for dependency in ("tests/e2e/verify_ci_customer_support_browser.py", "tests/e2e/test_ci_customer_support_browser_contract.py"):
                with self.subTest(event=event, dependency=dependency):
                    self.assertTrue(f"- '{dependency}'" in paths, "support behavior dependencies must trigger module CI")

    def test_php_and_contract_suites_are_wired_to_the_existing_module_workflow(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "business-profile.yml").read_text(encoding="utf-8")
        self.assertIn("php tests/admin_support_assignments/assignment_repository.php", workflow)
        self.assertIn("discover -s tests/admin_support_assignments -p 'test_*.py'", workflow)
        self.assertIn("find modules/kuraneabackoffice -name '*.php'", workflow)


if __name__ == "__main__":
    unittest.main()
