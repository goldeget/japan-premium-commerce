from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneabusinessprofile" / "kuraneabusinessprofile.php"
PROFILE_CONTROLLER = ROOT / "modules" / "kuraneabusinessprofile" / "controllers" / "admin" / "AdminBusinessProfileController.php"
BANKS_CONTROLLER = ROOT / "modules" / "kuraneabusinessprofile" / "controllers" / "admin" / "AdminBusinessProfileBanksController.php"
INSTALLATION_CHECK = ROOT / "tests" / "business_profile" / "verify_installation.php"


class AdminTabNavigationContractTests(unittest.TestCase):
    def test_banks_tab_is_a_sibling_of_profile_settings(self) -> None:
        module = MODULE.read_text(encoding="utf-8")
        install_tabs = module.split("private function installTabs(): bool", 1)[1].split("private function upsertTab", 1)[0]
        self.assertIn("Tab::getIdFromClassName('ShopParameters')", install_tabs)
        self.assertIn("$this->upsertTab('AdminBusinessProfile', '쇼핑몰 운영 설정', $parentId)", install_tabs)
        self.assertIn("$this->upsertTab('AdminBusinessProfileBanks', '은행 계좌', $parentId)", install_tabs)
        self.assertNotIn("$this->upsertTab('AdminBusinessProfileBanks', '은행 계좌', $generalTabId)", install_tabs)

    def test_profile_page_keeps_bank_back_link_and_install_check_asserts_siblings(self) -> None:
        profile_controller = PROFILE_CONTROLLER.read_text(encoding="utf-8")
        installation_check = INSTALLATION_CHECK.read_text(encoding="utf-8")
        self.assertIn("getAdminLink('AdminBusinessProfileBanks')", profile_controller)
        self.assertIn("(int) $tab->id_parent === $shopParametersParentId", installation_check)
        self.assertIn("Tab::getIdFromClassName('ShopParameters')", installation_check)
        self.assertNotIn("AdminParentShopParameters", installation_check)
        self.assertNotIn("AdminParentPreferences", installation_check)
        self.assertIn("(bool) $shopParametersParent->active", installation_check)
        self.assertIn("isset($shopParametersParent->enabled)", installation_check)
        self.assertIn("AdminBusinessProfileBanks'], true)", installation_check)
        self.assertIn("AdminAccessPolicy::canViewBank(", BANKS_CONTROLLER.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
