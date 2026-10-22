from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "modules/kuraneabusinessprofile/kuraneabusinessprofile.php"
APPENDER_PATH = ROOT / "modules/kuraneabusinessprofile/src/Customer/OrderConfirmationMailContent.php"
PHP_TEST_PATH = ROOT / "tests/business_profile/order_confirmation_mail.php"
UPGRADE_PATH = ROOT / "modules/kuraneabusinessprofile/upgrade/upgrade-1.0.1.php"


class OrderConfirmationMailContractTest(unittest.TestCase):
    def test_only_order_confirmation_registers_and_uses_the_mail_hook(self):
        module = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("'actionEmailAddAfterContent'", module)
        self.assertIn("function hookActionEmailAddAfterContent(array $params)", module)
        self.assertIn("($params['template'] ?? '') !== 'order_conf'", module)
        self.assertRegex(module, r"OrderConfirmationMailContent::append\(\s*'order_conf'")

    def test_mail_profile_resolution_uses_mail_language_and_shop(self):
        module = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("new Language((int) ($params['id_lang'] ?? 0))", module)
        self.assertIn("$params['id_shop'] ?? $this->context->shop->id", module)
        self.assertIn("->forShop($shopId, $isoCode)", module)

    def test_existing_install_upgrade_registers_the_new_hook(self):
        module = MODULE_PATH.read_text(encoding="utf-8")
        upgrade = UPGRADE_PATH.read_text(encoding="utf-8")
        self.assertIn("$this->version = '1.0.1'", module)
        self.assertIn("function upgrade_module_1_0_1", upgrade)
        self.assertIn("registerHook('actionEmailAddAfterContent')", upgrade)

    def test_appender_preserves_both_templates_and_uses_escaped_public_profile_output(self):
        appender = APPENDER_PATH.read_text(encoding="utf-8")
        self.assertIn("$template !== 'order_conf'", appender)
        self.assertIn("PublicFooterBuilder::build($profile, $commerceEnabled)", appender)
        self.assertIn("strip_tags", appender)
        self.assertIn("html_entity_decode", appender)
        self.assertIn("</body>", appender)
        self.assertIn("substr_replace", appender)

    def test_php_synthetic_regression_covers_core_sentinels_and_fail_closed_cases(self):
        php_test = PHP_TEST_PATH.read_text(encoding="utf-8")
        for expected in (
            "{order_name}",
            "{products}",
            "{total_paid}",
            "{products_txt}",
            "결제 안내",
            "</body>",
            "'new_order'",
            "bodylessHtml",
        ):
            self.assertIn(expected, php_test)


if __name__ == "__main__":
    unittest.main()
