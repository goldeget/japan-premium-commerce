from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneabusinessprofile"


class AdminProfileHistoryContractTests(unittest.TestCase):
    def test_admin_history_uses_parent_version_diff_and_escapes_values(self) -> None:
        form = (MODULE / "src" / "Admin" / "AdminProfileForm.php").read_text(encoding="utf-8")
        change_set_path = MODULE / "src" / "Admin" / "ProfileChangeSet.php"
        browser = (ROOT / "tests" / "e2e" / "verify_brand_admin_browser.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")

        self.assertTrue(change_set_path.is_file(), "field-level profile change projection is missing")
        change_set = change_set_path.read_text(encoding="utf-8")
        self.assertIn("ProfileChangeSet::between", form)
        self.assertIn("parentVersionId", form)
        self.assertIn("self::renderHistoryValue($change['previous'])", form)
        self.assertIn("self::renderHistoryValue($change['current'])", form)
        self.assertIn("return self::escape($value)", form)
        self.assertIn("bank_accounts", change_set)
        self.assertIn("은행 계좌 정보 변경 전", change_set)
        self.assertIn("은행 계좌 정보 변경 후", change_set)
        self.assertIn("ja-JP", change_set)
        self.assertIn("ko-KR", change_set)
        self.assertIn("localization.default_locale", change_set)
        self.assertIn("'unverified' => '미확인'", change_set)
        self.assertIn("verify_profile_change_row", browser)
        self.assertIn("ORDENOWA CI BRAND KO", browser)
        self.assertIn("brand-admin-history-change-diff.png", workflow)


if __name__ == "__main__":
    unittest.main()
