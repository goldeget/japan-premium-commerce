"""Local source contracts; PHP behavioral coverage lives in run.php (CI)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / 'modules/kuraneapush'

class BackendContract(unittest.TestCase):
    def source(self, path):
        file = MODULE / path
        self.assertTrue(file.is_file(), f'missing backend contract: {path}')
        return file.read_text()

    def test_crypto_has_authenticated_owner_binding(self):
        source = self.source('src/Infrastructure/SubscriptionCipher.php')
        for value in ['aes-256-gcm', 'random_bytes(12)', 'hash_hkdf', 'hash_hmac', 'ORDENOWA_PUSH_STORAGE_KEY', 'hash_equals']:
            self.assertIn(value, source)

    def test_front_boundary_uses_purpose_token_and_private_json(self):
        source = self.source('controllers/front/subscription.php')
        for value in ["Tools::getToken('kuraneapush', $this->context)", 'private, no-store', '8193', 'HTTP_ORIGIN', 'getBaseLink', 'isLogged', 'is_guest']:
            self.assertIn(value, source)
        self.assertNotIn('getMessage(', source)
        self.assertIn('getBaseLink($shop)', source)
        self.assertNotIn('getBaseLink($shop, true)', source)
        self.assertNotIn('HTTP_HOST', source)
        self.assertNotIn('HTTP_X_FORWARDED', source)

    def test_repository_prevents_owner_transfer(self):
        source = self.source('src/Infrastructure/SubscriptionRepository.php')
        self.assertIn('id_shop', source)
        self.assertIn('id_customer', source)
        self.assertIn('endpoint_digest', source)
        self.assertNotIn('ON DUPLICATE KEY UPDATE', source)
        self.assertNotIn('REPLACE INTO', source)

    def test_admin_access_and_lifecycle(self):
        source = self.source('controllers/admin/AdminKuraneaPushController.php')
        for value in ['viewAccess()', "access('edit')", 'hash_equals', '발송', '일본어', '영어', '한국어']:
            self.assertIn(value, source)
        module = self.source('kuraneapush.php')
        for value in ['hookDisplayCustomerAccount', 'hookActionObjectCustomerDeleteAfter', 'account_push.tpl', 'account-push.js', 'account-push.css']:
            self.assertIn(value, module)
        self.assertNotIn('DROP TABLE', module)

if __name__ == '__main__':
    unittest.main()
