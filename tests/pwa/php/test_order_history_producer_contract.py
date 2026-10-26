"""Native order producer boundaries; PHP behavior remains runtime coverage."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / 'modules/kuraneapush'


class OrderHistoryProducerContract(unittest.TestCase):
    def test_native_hook_registration_and_upgrade(self):
        module = (MODULE / 'kuraneapush.php').read_text()
        self.assertIn("'actionOrderHistoryAddAfter'", module)
        self.assertIn('function hookActionOrderHistoryAddAfter(', module)
        self.assertIn('OrderHistoryPushProducer', module)
        upgrade = MODULE / 'upgrade/upgrade-1.0.3.php'
        self.assertTrue(upgrade.is_file(), 'installed modules need order hook registration')
        self.assertIn('actionOrderHistoryAddAfter', upgrade.read_text())

    def test_producer_reloads_native_owner_and_uses_history_identity(self):
        path = MODULE / 'src/Infrastructure/OrderHistoryPushProducer.php'
        self.assertTrue(path.is_file(), 'native order event producer is missing')
        source = path.read_text()
        for value in ('new \\OrderHistory(', 'new \\Order(', 'new \\Customer(',
                      "'ORDENOWA_PUSH_EVENT_ORDER'", "'order-history:'", "recordEvent($event, 'order')", 'current_state'):
            self.assertIn(value, source)
        self.assertNotIn('getMessage(', source)
        self.assertNotIn('getenv(', source)
        self.assertNotIn('error_log(', source)
        self.assertNotIn('Context::getContext', source)

    def test_receipt_accepts_no_cipher_without_enabling_delivery(self):
        source = (MODULE / 'src/Domain/PushOutboxService.php').read_text()
        self.assertIn('?SubscriptionCipher $cipher = null', source)
        self.assertIn('$this->cipher === null', source)

    def test_shipped_history_records_an_independent_delivery_receipt(self):
        source = (MODULE / 'src/Infrastructure/OrderHistoryPushProducer.php').read_text()
        module = (MODULE / 'kuraneapush.php').read_text()
        for value in ('function recordDelivery(', 'new \\OrderState(', '->shipped',
                      "'ORDENOWA_PUSH_EVENT_DELIVERY'", "'delivery-history:'"):
            self.assertIn(value, source)
        hook = module.split('public function hookActionOrderHistoryAddAfter(', 1)[1].split(
            'public function hookActionObjectCustomerMessageAddAfter(', 1
        )[0]
        self.assertIn('->recordDelivery(', hook)

    @unittest.skipUnless(shutil.which('php'), 'native producer PHP behavior requires Actions PHP runtime')
    def test_php_producer_behavior(self):
        result = subprocess.run(['php', str(ROOT / 'tests/pwa/php/order_history_producer.php')],
                                capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('PASS: native order history push producer', result.stdout)


if __name__ == '__main__':
    unittest.main()
