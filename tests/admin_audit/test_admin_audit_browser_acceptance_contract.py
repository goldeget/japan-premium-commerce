from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "fresh-install.yml"
FIXTURE = ROOT / "tests" / "admin_audit" / "prepare_browser_acceptance.php"
BROWSER = ROOT / "tests" / "e2e" / "verify_admin_audit_browser.py"


class AdminAuditBrowserAcceptanceContractTests(unittest.TestCase):
    def test_fixture_invokes_guard_as_a_declared_php_function(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        self.assertRegex(fixture, re.compile(r"\bfunction\s+adminAuditFixtureRequire\s*\("))
        self.assertGreaterEqual(
            len(re.findall(r"(?m)^adminAuditFixtureRequire\s*\(", fixture)),
            10,
        )
        self.assertNotRegex(fixture, re.compile(r"\$adminAuditFixtureRequire\s*\("))

    def test_fixture_is_limited_to_the_disposable_single_shop_ci_run(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        for marker in (
            "getenv('CI') === 'true'",
            "getenv('GITHUB_ACTIONS') === 'true'",
            "getenv('KURANEA_ISOLATED_CI') === '1'",
            "$project === $expectedProject",
            "Shop::getTotalShops() === 1",
            "Shop::getContext() === Shop::CONTEXT_SHOP",
            "$order->id_shop === $shopId",
            "qa-ordenowa-checkout-%s-%s-bank@example.invalid",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, fixture)
        self.assertNotIn("KURANEA_CATALOG_QUEUE_DIR", fixture)
        self.assertNotIn("CatalogQueueRepositoryFactory", fixture)
        self.assertNotRegex(fixture, re.compile(r"\b(?:DROP\s+TABLE|TRUNCATE\s+TABLE)\b", re.I))

    def test_fixture_uses_native_reader_roles_and_persisted_source_rows(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        for marker in (
            "AdminKuraneaEmployeeProfileAudit",
            "AdminOrders",
            "AdminKuraneaSupportAssignments",
            "AdminBusinessProfileTransfers",
            "updateLgcAccess((int) $readerProfile->id, $tabId, 'view', true, false)",
            "updateLgcAccess((int) $limitedProfile->id, $tabIds['audit'], 'view', true, false)",
            "'ADMINORDERS_READ' => (int) $readerProfile->id",
            "Access::isGranted($permission, $profileId)",
            "!Access::isGranted($permission, (int) $limitedProfile->id)",
            "$reader->update()",
            "kuraneabackoffice_employee_profile_audit",
            "kuraneabackoffice_support_assignment_history",
            "kuraneabusinessprofile_bank_transfer_instruction",
            "kuraneabusinessprofile_bank_transfer_receipt",
            "order_history",
            "INSERT INTO",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, fixture)
        self.assertRegex(fixture, re.compile(r"old_profile_id.*new_profile_id", re.S))
        self.assertIn("The completed CI bank flow did not leave same-shop instruction, receipt, and native order-history rows.", fixture)

    def test_browser_checks_all_five_sources_both_roles_and_fresh_page_reads(self) -> None:
        browser = BROWSER.read_text(encoding="utf-8")
        for marker in (
            '"관리자 프로필"',
            '"주문 상태"',
            '"상담 배정"',
            '"입금 안내"',
            '"입금 확인"',
            '"관리자 프로필 변경"',
            '"주문 상태 변경"',
            '"담당자 지정"',
            '"입금 안내 발급"',
            '"입금 확인 기록"',
            "driver.refresh()",
            "verify_full_reader(values)",
            "verify_source_limited_reader(values)",
            "row[1] != \"관리자 프로필\"",
            "tokenized audit route",
            "--headless=new",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, browser)
        self.assertNotIn("sleep(", browser)

    def test_fresh_install_workflow_runs_and_aggregates_the_isolated_browser_acceptance(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("      - 'tests/admin_audit/**'"), 2)
        self.assertIn("tests.admin_audit.test_admin_audit_browser_acceptance_contract", workflow)

        bank = workflow.split("      - name: Verify order-bound bank transfer issue, rejection, and receipt confirmation in Chromium\n", 1)[1].split("      - name:", 1)[0]
        fixture = workflow.split("      - name: Seed isolated five-source admin audit browser fixtures\n", 1)[1].split("      - name:", 1)[0]
        browser = workflow.split("      - name: Verify native five-source admin audit access and fresh readback in Chromium\n", 1)[1].split("      - name:", 1)[0]
        restore = workflow.split("      - name: Restore fail-closed checkout after the isolated bank transfer browser QA\n", 1)[1].split("      - name:", 1)[0]
        positions = [workflow.index("      - name: " + title) for title in (
            "Verify order-bound bank transfer issue, rejection, and receipt confirmation in Chromium",
            "Seed isolated five-source admin audit browser fixtures",
            "Verify native five-source admin audit access and fresh readback in Chromium",
            "Restore fail-closed checkout after the isolated bank transfer browser QA",
        )]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("steps.bank_transfer_browser_qa.outcome == 'success'", fixture)
        self.assertIn("steps.admin_audit_fixture.outcome == 'success'", browser)
        self.assertIn("KURANEA_ISOLATED_CI=1", fixture)
        self.assertIn("CI_COMPOSE_PROJECT_NAME", fixture)
        self.assertIn("steps.admin_audit_fixture.outputs.reader_email", browser)
        self.assertIn("steps.admin_audit_fixture.outputs.limited_reader_email", browser)
        self.assertIn("ADMIN_AUDIT_FIXTURE_OUTCOME", workflow)
        self.assertIn('"admin_audit_fixture=$ADMIN_AUDIT_FIXTURE_OUTCOME"', workflow)
        self.assertIn('"admin_audit_browser_qa=$ADMIN_AUDIT_BROWSER_QA_OUTCOME"', workflow)
        self.assertIn("admin-audit-authorized.png", workflow)
        self.assertIn("admin-audit-source-limited.png", workflow)
        self.assertIn("admin-audit-e2e.log", workflow)
        self.assertIn("admin-audit-fixture.log", workflow)
        self.assertIn("continue-on-error: true", bank)
        self.assertIn("continue-on-error: true", fixture)
        self.assertIn("continue-on-error: true", browser)


if __name__ == "__main__":
    unittest.main()
