"""Guard PrestaShop's installer-required admin path until its assets are ready."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "compose.yaml"
POST_INSTALL = ROOT / "docker" / "kuran-post-install.php"
POST_INSTALL_HOOK = ROOT / "docker" / "post-install" / "10-kuranea-bootstrap.sh"
FRESH_INSTALL_SMOKE = ROOT / "tests" / "smoke" / "fresh_install.sh"


class AdminFolderInstallOrderTests(unittest.TestCase):
    def test_official_installer_keeps_its_default_admin_directory_until_post_install(self) -> None:
        compose = COMPOSE.read_text(encoding="utf-8")
        self.assertRegex(compose, r"(?m)^\s*PS_FOLDER_ADMIN:\s*admin-dev\s*$")
        self.assertRegex(compose, r"(?m)^\s*KURANEA_ADMIN_FOLDER:\s*admin-kuranea\s*$")

    def test_post_install_defers_admin_rename_to_php_bootstrap(self) -> None:
        hook = POST_INSTALL_HOOK.read_text(encoding="utf-8")
        php_bootstrap = hook.find('php /usr/local/bin/kuran-post-install.php')
        final_check = hook.find('if [ ! -d "$admin_dir" ]; then')

        self.assertGreaterEqual(php_bootstrap, 0)
        self.assertGreater(final_check, php_bootstrap, "verify the final path after PHP detected and renamed it")
        self.assertNotIn('mv -- "$admin_source" "$admin_dir"', hook)
        self.assertNotRegex(hook, r"mkdir\s+[^\n]*admin-dev")

    def test_php_bootstrap_reruns_assets_at_final_path_and_rejects_legacy_admin_dev(self) -> None:
        source = POST_INSTALL.read_text(encoding="utf-8")
        post_install = source.find("$install->postInstall()")
        admin_rename = source.find("$filesystem->rename(")
        final_assets = source.find("->installAssets($adminFolder . '/')")

        self.assertGreaterEqual(post_install, 0, "keep the official PrestaShop post-install phase")
        self.assertGreater(admin_rename, post_install, "rename only after PrestaShop installation is complete")
        self.assertGreater(final_assets, admin_rename, "install assets in the final admin directory")
        self.assertIn("prestashop.admin_dir", source)
        self.assertIn("KURANEA_ADMIN_FOLDER", source)
        self.assertNotRegex(source, r"mkdir\s*\([^;]*admin-dev")

    def test_fresh_install_smoke_requires_final_admin_assets_and_no_public_admin_dev(self) -> None:
        smoke = FRESH_INSTALL_SMOKE.read_text(encoding="utf-8")
        self.assertIn("/var/www/html/admin-kuranea", smoke)
        self.assertIn("/var/www/html/admin-dev", smoke)
        self.assertIn("themes/new-theme/public/theme.css", smoke)


if __name__ == "__main__":
    unittest.main()
