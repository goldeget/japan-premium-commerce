"""Keep official brand asset upgrades additive and commerce gated."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class BrandAssetUpgradeContractTests(unittest.TestCase):
    def test_module_upgrade_adds_assets_as_new_versions_and_syncs_email_logo(self) -> None:
        module = (ROOT / "modules/kuraneabusinessprofile/kuraneabusinessprofile.php").read_text(encoding="utf-8")
        upgrade = (ROOT / "modules/kuraneabusinessprofile/upgrade/upgrade-1.0.3.php").read_text(encoding="utf-8")
        self.assertIn("$this->version = '1.0.6'", module)
        self.assertIn("upgrade_module_1_0_3", upgrade)
        self.assertIn("ordenowa_add_verified_brand_defaults", upgrade)
        self.assertIn("insertVersion($shopId, $profile, 0, $draft->id)", upgrade)
        self.assertIn("setDraftPointer($shopId, $version->id)", upgrade)
        self.assertIn("publishVersion($shopId, $version->id, 0)", upgrade)
        self.assertIn("configureOfficialMailLogo", upgrade)
        self.assertIn("is_file(_PS_ROOT_DIR_ . '/' . $candidate)", upgrade)
        self.assertNotIn("DELETE FROM", upgrade)

    def test_upgrade_does_not_change_seller_approval_or_payment_state(self) -> None:
        upgrade = (ROOT / "modules/kuraneabusinessprofile/upgrade/upgrade-1.0.3.php").read_text(encoding="utf-8")
        self.assertNotIn("authorization_status'", upgrade)
        self.assertNotIn("bank_accounts'", upgrade)
        self.assertNotIn("payment_methods'", upgrade)

    def test_existing_installations_register_core_structured_data_hook_on_upgrade(self) -> None:
        module = (ROOT / "modules/kuraneabusinessprofile/kuraneabusinessprofile.php").read_text(encoding="utf-8")
        upgrade_path = ROOT / "modules/kuraneabusinessprofile/upgrade/upgrade-1.0.4.php"

        self.assertTrue(upgrade_path.is_file(), "existing module installs need the new front controller hook")
        upgrade = upgrade_path.read_text(encoding="utf-8")
        self.assertIn("$this->version = '1.0.6'", module)
        self.assertIn("function upgrade_module_1_0_4($module)", upgrade)
        self.assertIn("registerHook('actionFrontControllerSetVariables')", upgrade)
        self.assertIn("'actionFrontControllerSetVariables'", module)
        self.assertNotIn("DELETE FROM", upgrade)

    def test_official_assets_feed_storefront_admin_pwa_and_email_before_first_publish(self) -> None:
        business_profile = (ROOT / "modules/kuraneabusinessprofile/kuraneabusinessprofile.php").read_text(encoding="utf-8")
        backoffice = (ROOT / "modules/kuraneabackoffice/kuraneabackoffice.php").read_text(encoding="utf-8")
        manifest = (ROOT / "themes/kuranea/assets/manifest.webmanifest").read_text(encoding="utf-8")
        self.assertIn("$assets = (array) ($profile['brand']['assets'] ?? [])", business_profile)
        self.assertIn("ProfileDefaults::initial()", backoffice)
        self.assertIn("configureOfficialMailLogo(ProfileDefaults::initial()", business_profile)
        self.assertIn("PS_LOGO_MAIL", business_profile)
        self.assertIn("pwa-maskable-512.png", manifest)
        self.assertIn('"icons": [', manifest)


if __name__ == "__main__":
    unittest.main()
