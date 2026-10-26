<?php

declare(strict_types=1);
namespace Kuranea\Push\Domain;
use Kuranea\Push\Infrastructure\SubscriptionCipher;

final class SubscriptionApi
{
    public function __construct(private SubscriptionStore $store, private ?SubscriptionCipher $cipher) {}

    /** Owner IDs, expected token, notice and rendered locale are trusted server inputs. */
    public function handle(string $method, string $action, array $body, bool $authenticated, int $shop, int $customer,
        string $origin, string $baseUrl, string $expectedToken, bool $ready, string $notice, string $expectedLocale): array
    {
        if (!$authenticated || $shop < 1 || $customer < 1) {
            return [401, ['error' => 'unauthorized']];
        }
        if ($action === 'status' && $method === 'GET') {
            try {
                return [200, ['active' => $this->store->active($shop, $customer),
                    'can_subscribe' => $ready && $this->cipher !== null && trim($notice) !== '']];
            } catch (\Throwable $e) {
                return [503, ['error' => 'unavailable']];
            }
        }
        if (!in_array($action, ['subscribe', 'revoke'], true)) {
            return [400, ['error' => 'invalid_request']];
        }
        if ($method !== 'POST') {
            return [405, ['error' => 'method_not_allowed']];
        }
        if (!RequestGuard::allows($method, $origin, $baseUrl, $body['token'] ?? null, $expectedToken)) {
            return [403, ['error' => 'forbidden']];
        }
        try {
            if (isset($body['action']) && $body['action'] !== $action) {
                throw new \InvalidArgumentException('Invalid request.');
            }
            if ($action === 'revoke') {
                SubscriptionValidator::fields($body, ['action', 'token']);
                $this->store->revoke($shop, $customer);
                return [200, ['active' => false]];
            }
            SubscriptionValidator::fields($body, ['action', 'token', 'consent', 'locale', 'notice_version', 'subscription']);
            if (!$ready || $this->cipher === null || trim($notice) === '' || ($body['consent'] ?? null) !== true
                || !in_array($expectedLocale, ['ja', 'en', 'ko'], true)
                || !is_string($body['locale'] ?? null) || $body['locale'] !== $expectedLocale
                || !is_array($body['subscription'] ?? null)) {
                throw new \InvalidArgumentException('Invalid request.');
            }
            $locale = $expectedLocale;
            $expectedNoticeVersion = ConsentNoticeVersion::forNotice($notice, $expectedLocale);
            $noticeVersion = $body['notice_version'] ?? null;
            if (!is_string($noticeVersion) || !ConsentNoticeVersion::isValid($noticeVersion)
                || !hash_equals($expectedNoticeVersion, $noticeVersion)) {
                throw new \InvalidArgumentException('Invalid request.');
            }
            $subscription = SubscriptionValidator::validate($body['subscription']);
            $digest = $this->cipher->digest($subscription['endpoint']);
            $envelope = $this->cipher->encrypt($subscription, $shop, $customer, $digest);
            $this->store->save($shop, $customer, $digest, $envelope, $locale, $noticeVersion);
            return [200, ['active' => true]];
        } catch (\Throwable $e) {
            return [400, ['error' => 'invalid_request']];
        }
    }
}
