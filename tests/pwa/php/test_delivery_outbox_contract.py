"""Outbox source boundaries locally; behavioral PHP contracts run where PHP is available."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / 'modules/kuraneapush'


class DeliveryOutboxContract(unittest.TestCase):
    def test_outbox_stores_receipts_recipients_and_attempts(self):
        path = MODULE / 'src/Infrastructure/PushOutboxRepository.php'
        self.assertTrue(path.is_file(), 'durable outbox storage is missing')
        repository = path.read_text()
        for name in ('kuraneapush_event', 'kuraneapush_recipient', 'kuraneapush_attempt'):
            self.assertIn(name, repository)
        self.assertIn('GET_LOCK', repository)
        self.assertIn('RELEASE_LOCK', repository)
        self.assertIn('UTC_TIMESTAMP()', repository)
        self.assertNotIn('encrypted_subscription', repository)
        self.assertIn('consent_generation', repository)

    def test_explicit_retry_preserves_the_disabled_provider(self):
        path = MODULE / 'src/Domain/PushOutboxService.php'
        self.assertTrue(path.is_file(), 'explicit event receipt/retry API is missing')
        service = path.read_text()
        self.assertIn('function receive(', service)
        self.assertIn('function retry(', service)
        self.assertIn('new DisabledPushDeliveryProvider()', service)
        self.assertIn('deliveryTargetsForOwner', service)
        self.assertNotIn('sleep(', service)
        self.assertNotIn('curl_', service)
        self.assertIn('consent_generation', service)
        self.assertIn('hash_equals', service)

    @unittest.skipUnless(shutil.which('php'), 'PHP outbox behavior requires Actions PHP runtime')
    def test_php_outbox_behavior(self):
        result = subprocess.run(['php', str(ROOT / 'tests/pwa/php/delivery_outbox.php')],
                                text=True, capture_output=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('PASS: push outbox', result.stdout)


if __name__ == '__main__':
    unittest.main()
