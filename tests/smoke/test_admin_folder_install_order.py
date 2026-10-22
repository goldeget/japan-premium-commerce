"""Guard PrestaShop's installer-required admin path until its assets are ready."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "compose.yaml"
POST_INSTALL = ROOT / "docker" / "kuran-post-install.php"
POST_INSTALL_HOOK = ROOT / "docker" / "init" / "10-kuranea-bootstrap.sh"
MODULE_INSTALL = ROOT / "docker" / "kuran-install-modules.php"
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

    def test_japanese_static_routes_migrate_once_and_preserve_later_seo_edits(self) -> None:
        hook = POST_INSTALL_HOOK.read_text(encoding="utf-8")
        installer = MODULE_INSTALL.read_text(encoding="utf-8")
        smoke = FRESH_INSTALL_SMOKE.read_text(encoding="utf-8")

        module_install_call = hook.find("php /usr/local/bin/kuran-install-modules.php")
        self.assertGreaterEqual(module_install_call, 0)
        self.assertNotIn(".kuranea-bootstrap-v2", hook.split("php /usr/local/bin/kuran-install-modules.php", 1)[0])
        self.assertIn("$routeMigrationKey = 'ORDENOWA_ASCII_ROUTE_MIGRATION_V1'", installer)
        self.assertIn("(string) Configuration::get($routeMigrationKey) !== '1'", installer)
        self.assertIn("Configuration::updateValue($routeMigrationKey, '1')", installer)
        self.assertIn("if ($routeMigrationSucceeded)", installer)
        self.assertIn("reason=retry_next_start", installer)
        self.assertIn("'order' => 'checkout'", installer)
        self.assertIn("'identity' => 'identity'", installer)
        self.assertIn("'password' => 'password-reset'", installer)
        self.assertIn("'history' => 'history'", installer)
        self.assertIn("$optionalMetaPages = ['history']", installer)
        self.assertIn("INNER JOIN `' . _DB_PREFIX_ . 'meta` m ON m.id_meta = ml.id_meta", installer)
        self.assertIn("WHERE m.page = '\" . pSQL($page) . \"' AND ml.id_shop = 1 AND ml.id_lang = ", installer)
        self.assertIn("$db->executeS($routeQuery, true, false)", installer)
        self.assertIn("SELECT COUNT(*) FROM `\" . _DB_PREFIX_ . \"meta` WHERE page = '", installer)
        self.assertIn("if (!$metaExists && in_array($page, $optionalMetaPages, true))", installer)
        self.assertIn("$routeRows as $routeRow", installer)
        self.assertIn("preg_match('/[^\\x00-\\x7F]/', $storedRouteSlug) === 1", installer)
        self.assertIn("$hasNonAsciiRoute", installer)
        self.assertIn("['url_rewrite' => pSQL($routeSlug)]", installer)
        self.assertIn("$db->getValue($routeReadbackQuery, false) !== $routeSlug", installer)
        self.assertIn("PS_REWRITING_SETTINGS", smoke)
        self.assertIn("PS_CANONICAL_REDIRECT", smoke)
        self.assertIn("route_migration_marker", smoke)
        self.assertIn("admin_custom_checkout_route", smoke)
        self.assertIn('test "$checkout_route_after_restart" = "$admin_custom_checkout_route"', smoke)
        self.assertIn('test "$identity_route_after_restart" = "$admin_custom_identity_route"', smoke)
        self.assertIn('test "$password_route_after_restart" = "$admin_custom_password_route"', smoke)
        self.assertIn("canonical_redirect_before_restart", smoke)
        self.assertIn("canonical_redirect_after_restart", smoke)
        self.assertIn("route_migration_marker_after_restart", smoke)
        for route_check in (
            "checkout_route",
            "identity_route",
            "password_route",
            "checkout_route_after_restart",
            "identity_route_after_restart",
            "password_route_after_restart",
            "history_route",
            "history_route_after_restart",
        ):
            self.assertIn(route_check, smoke)


if __name__ == "__main__":
    unittest.main()
