"""Contracts for a disposable native PrestaShop employee recovery fixture."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "business_profile" / "seed_admin_recovery_fixture.php"


class AdminRecoveryFixtureContractTests(unittest.TestCase):
    def test_fixture_creates_a_distinct_run_scoped_employee_and_does_not_mutate_the_primary(self):
        self.assertTrue(FIXTURE.is_file(), "the isolated Back Office recovery employee fixture is missing")
        source = FIXTURE.read_text(encoding="utf-8")

        for marker in (
            "getenv('CI') === 'true'",
            "getenv('GITHUB_ACTIONS') === 'true'",
            "getenv('KURANEA_ISOLATED_CI') === '1'",
            "kuranea-ci-%s-%s",
            "ordenowa-admin-recovery-%s-%s-%s@example.invalid",
            "$admin->getByEmail($adminEmail)",
            "(int) $admin->id === 1",
            "$employee = new Employee()",
            "$employee->add()",
            "'employee_id' => (int) $employee->id",
            "'email' => $email",
            "ORDENOWA_ADMIN_RECOVERY_FIXTURE=",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

        self.assertNotIn("$admin->update()", source)
        self.assertNotIn("'password' =>", source)
        self.assertNotIn("'token' =>", source)


if __name__ == "__main__":
    unittest.main()
