"""Native public support replies create consent-bound push receipts only."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / 'modules/kuraneapush'


class SupportMessageProducerContract(unittest.TestCase):
    def test_native_hook_registration_and_upgrade(self):
        module = (MODULE / 'kuraneapush.php').read_text()
        self.assertIn("'actionObjectCustomerMessageAddAfter'", module)
        self.assertIn('function hookActionObjectCustomerMessageAddAfter(', module)
        self.assertIn('SupportMessagePushProducer', module)
        self.assertIn('public function ensureSupportMessagePushHook(): bool', module)
        upgrade = MODULE / 'upgrade/upgrade-1.0.4.php'
        self.assertTrue(upgrade.is_file(), 'installed modules need support-message hook registration')
        self.assertIn('actionObjectCustomerMessageAddAfter', upgrade.read_text())

    def test_producer_reloads_public_staff_message_thread_and_customer(self):
        path = MODULE / 'src/Infrastructure/SupportMessagePushProducer.php'
        self.assertTrue(path.is_file(), 'native support-message event producer is missing')
        source = path.read_text()
        for value in (
            'new \\CustomerMessage(', 'new \\CustomerThread(', 'new \\Customer(',
            'id_employee', 'id_customer_thread', 'id_shop', 'private', 'id_order',
            "'ORDENOWA_PUSH_EVENT_SUPPORT'", "'support-message:'",
            "new DeliveryPayload('support'",
        ):
            self.assertIn(value, source)
        self.assertNotIn('getMessage(', source)
        self.assertNotIn('message->message', source)
        self.assertNotIn('file_name', source)
        self.assertNotIn('error_log(', source)
        self.assertNotIn('getenv(', source)

    def test_installer_repairs_the_additive_support_message_hook(self):
        bootstrap = (ROOT / 'docker/kuran-install-modules.php').read_text()
        self.assertIn('$pushModule->ensureSupportMessagePushHook()', bootstrap)

    @unittest.skipUnless(shutil.which('php'), 'native support-message behavior requires Actions PHP runtime')
    def test_php_producer_behavior(self):
        result = subprocess.run(
            ['php', str(ROOT / 'tests/pwa/php/support_message_producer.php')],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('PASS: native support-message push producer', result.stdout)


if __name__ == '__main__':
    unittest.main()
