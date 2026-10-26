"""Local source contracts; PHP behavioral coverage lives in run.php (CI)."""
from pathlib import Path
import unittest

from tests.pwa.php.test_delivery_outbox_contract import DeliveryOutboxContract

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

    def test_subscription_binds_server_consent_to_the_displayed_notice(self):
        api = self.source('src/Domain/SubscriptionApi.php')
        version = self.source('src/Domain/ConsentNoticeVersion.php')
        controller = self.source('controllers/front/subscription.php')
        template = self.source('views/templates/hook/account_push.tpl')
        javascript = self.source('views/js/account-push.js')
        for value in ["'notice_version'", 'ConsentNoticeVersion::forNotice', '$locale']:
            self.assertIn(value, api)
        self.assertIn("hash('sha256'", version)
        self.assertIn('expectedLocale', api)
        self.assertIn("$body['locale'] !== $expectedLocale", api)
        self.assertIn("$this->context->language->iso_code", controller)
        self.assertIn('ordenowa_push_consent_notice_version', self.source('kuraneapush.php'))
        self.assertIn('data-push-notice-version', template)
        self.assertIn('notice_version: noticeVersion', javascript)
        self.assertIn("/^[a-f0-9]{64}$/", javascript)

    def test_consent_storage_is_nullable_owner_scoped_and_migrates_without_backfill(self):
        repository = self.source('src/Infrastructure/SubscriptionRepository.php')
        store = self.source('src/Domain/SubscriptionStore.php')
        self.assertIn('consent_notice_version CHAR(64)', repository)
        self.assertIn('consent_locale CHAR(2)', repository)
        self.assertIn('consent_accepted_at DATETIME NULL', repository)
        self.assertIn('SHOW COLUMNS FROM', repository)
        self.assertIn('UTC_TIMESTAMP()', repository)
        self.assertIn('consent_notice_version IS NOT NULL', repository)
        self.assertIn('consent_accepted_at IS NOT NULL', repository)
        self.assertIn('public function stored(int $shop, int $customer): bool', repository)
        self.assertIn('public function stored(int $shop, int $customer): bool', store)
        self.assertIn('data-revocable=', self.source('views/templates/hook/account_push.tpl'))
        self.assertIn("root.dataset.revocable === '1'", self.source('views/js/account-push.js'))
        self.assertIn('legacy stored subscription stays revocable', self.source('views/tests/account-push.test.cjs'))
        self.assertIn('consentNoticeVersion', store)
        install = repository.split('public function install(): bool', 1)[1].split('public function active(', 1)[0]
        self.assertNotIn('UPDATE', install)
        upgrade = (MODULE / 'upgrade/upgrade-1.0.1.php').read_text()
        self.assertIn('SubscriptionRepository())->install()', upgrade)

    def test_same_owner_resubscribe_refreshes_encrypted_material(self):
        repository = self.source('src/Infrastructure/SubscriptionRepository.php')
        self.assertIn("SET encrypted_subscription='", repository)
        self.assertIn("hash_equals($envelope, $row['encrypted_subscription'])", repository)

    def test_delivery_is_owner_scoped_consent_gated_and_live_disabled(self):
        provider = self.source('src/Domain/PushDeliveryProvider.php')
        store = self.source('src/Domain/PushDeliveryStore.php')
        service = self.source('src/Domain/PushDeliveryService.php')
        eligibility = self.source('src/Domain/ConsentedDeliveryTarget.php')
        fake = self.source('src/Infrastructure/IsolatedSyntheticPushDeliveryProvider.php')
        disabled = self.source('src/Infrastructure/DisabledPushDeliveryProvider.php')
        repository = self.source('src/Infrastructure/SubscriptionRepository.php')
        self.assertIn('Readiness::isolated()', fake)
        self.assertIn('available(): bool', provider)
        self.assertIn('deliveryTargetsForOwner', store)
        self.assertIn('removeDeliveryTargetForOwner', store)
        self.assertIn('deliveryTargetsForOwner($shop, $customer)', service)
        self.assertIn('ConsentedDeliveryTarget::eligible', service)
        self.assertIn("'consent_notice_version'", eligibility)
        self.assertIn("'consent_locale'", eligibility)
        self.assertIn("'consent_accepted_at'", eligibility)
        self.assertIn('consent_notice_version IS NOT NULL', repository)
        self.assertIn('consent_accepted_at IS NOT NULL', repository)
        self.assertIn('PushDeliveryStore::MAX_DELIVERY_TARGETS', repository)
        self.assertIn('MAX_DELIVERY_TARGETS = 100', store)
        self.assertIn('available(): bool', disabled)
        self.assertIn('new DisabledPushDeliveryProvider()', service)
        self.assertNotIn('curl_init(', fake + disabled)
        for source in (service, fake, disabled):
            self.assertNotIn('error_log(', source)
            self.assertNotIn('getMessage(', source)
            self.assertNotIn('var_dump(', source)

    def test_delivery_payload_serializes_only_the_worker_event_contract(self):
        payload = self.source('src/Domain/DeliveryPayload.php')
        synthetic = self.source('src/Infrastructure/IsolatedSyntheticPushDeliveryProvider.php')
        self.assertIn('function toJson(): string', payload)
        self.assertIn("['event' => $this->event, 'locale' => $this->locale]", payload)
        self.assertIn("['order', 'delivery', 'support']", payload)
        self.assertIn("['ja', 'en', 'ko']", payload)
        self.assertIn('$payload->toJson()', synthetic)
        self.assertNotIn('public readonly string $body', payload)

if __name__ == '__main__':
    unittest.main()
