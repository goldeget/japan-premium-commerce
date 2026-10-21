"""Contract checks for KURANEA's Japanese base-currency bootstrap."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class CurrencyBootstrapContractTests(unittest.TestCase):
    def test_first_install_and_existing_shop_call_the_shared_currency_bootstrap(self) -> None:
        dockerfile = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
        for script in ("kuran-post-install.php", "kuran-install-modules.php"):
            contents = (ROOT / "docker" / script).read_text(encoding="utf-8")
            self.assertIn("kuran-configure-jpy.php", dockerfile)
            self.assertIn("kuraneaConfigureJapaneseCurrency($context)", contents)

    def test_jpy_is_localized_for_each_active_store_language(self) -> None:
        helper = (ROOT / "docker" / "kuran-configure-jpy.php").read_text(encoding="utf-8")
        self.assertIn("'ja' => '日本円'", helper)
        self.assertIn("'ko' => '일본 엔'", helper)
        self.assertIn("default => 'Japanese yen'", helper)
        self.assertIn("new Currency($currencyId ?: null, null, $shopId)", helper)
        self.assertIn("KURANEA_JPY_DEFAULT_CURRENCY_CONFIGURED", helper)

    def test_installer_verifies_jpy_default_and_no_unrated_alternatives(self) -> None:
        script = (ROOT / "tests" / "smoke" / "fresh_install.sh").read_text(encoding="utf-8")
        self.assertIn("default_currency", script)
        self.assertIn("= JPY", script)
        self.assertIn("active_non_jpy", script)

    def test_installer_rechecks_jpy_currency_after_database_restart(self) -> None:
        script = (ROOT / "tests" / "smoke" / "fresh_install.sh").read_text(encoding="utf-8")
        restart_checks = script.split("compose restart mariadb prestashop", 1)[1]
        self.assertIn("default_currency_after_restart", restart_checks)
        self.assertIn("jpy_translations_after_restart", restart_checks)


if __name__ == "__main__":
    unittest.main()
