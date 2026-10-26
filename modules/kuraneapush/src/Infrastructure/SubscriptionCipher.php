<?php

declare(strict_types=1);
namespace Kuranea\Push\Infrastructure;
use Kuranea\Push\Domain\SubscriptionValidator;

final class SubscriptionCipher
{
    private string $aeadKey;
    private string $digestKey;

    public function __construct(?string $encodedKey = null)
    {
        $encodedKey ??= (string) getenv('ORDENOWA_PUSH_STORAGE_KEY');
        $master = base64_decode($encodedKey, true);
        if ($master === false || strlen($master) !== 32 || !function_exists('openssl_encrypt')
            || !in_array('aes-256-gcm', openssl_get_cipher_methods(), true)) {
            throw new \RuntimeException('Subscription storage unavailable.');
        }
        $this->aeadKey = hash_hkdf('sha256', $master, 32, 'ordenowa-push:aead:v1');
        $this->digestKey = hash_hkdf('sha256', $master, 32, 'ordenowa-push:hmac:v1');
    }

    public function digest(string $endpoint): string
    {
        return hash_hmac('sha256', $endpoint, $this->digestKey);
    }

    public function encrypt(array $subscription, int $shop, int $customer, string $digest): string
    {
        SubscriptionValidator::validate($subscription);
        if (!hash_equals($this->digest($subscription['endpoint']), $digest)) {
            throw new \RuntimeException('Invalid storage state.');
        }
        $json = json_encode($subscription, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES);
        if (strlen($json) > 4096) {
            throw new \RuntimeException('Invalid storage state.');
        }
        $nonce = random_bytes(12);
        $tag = '';
        $ciphertext = openssl_encrypt($json, 'aes-256-gcm', $this->aeadKey, OPENSSL_RAW_DATA, $nonce, $tag,
            $this->aad($shop, $customer, $digest), 16);
        if ($ciphertext === false || strlen($tag) !== 16) {
            throw new \RuntimeException('Subscription storage unavailable.');
        }
        return json_encode(['v' => 1, 'nonce' => base64_encode($nonce), 'tag' => base64_encode($tag),
            'ciphertext' => base64_encode($ciphertext)], JSON_THROW_ON_ERROR);
    }

    public function decrypt(string $envelope, int $shop, int $customer, string $digest): array
    {
        if (strlen($envelope) > 8192) {
            throw new \RuntimeException('Invalid storage state.');
        }
        $data = json_decode($envelope, true, 8, JSON_THROW_ON_ERROR);
        if (!is_array($data) || ($data['v'] ?? null) !== 1 || count($data) !== 4) {
            throw new \RuntimeException('Invalid storage state.');
        }
        foreach (['nonce', 'tag', 'ciphertext'] as $field) {
            if (!isset($data[$field]) || !is_string($data[$field])) {
                throw new \RuntimeException('Invalid storage state.');
            }
            $data[$field] = base64_decode($data[$field], true);
            if ($data[$field] === false) {
                throw new \RuntimeException('Invalid storage state.');
            }
        }
        if (strlen($data['nonce']) !== 12 || strlen($data['tag']) !== 16 || strlen($data['ciphertext']) > 4096) {
            throw new \RuntimeException('Invalid storage state.');
        }
        $json = openssl_decrypt($data['ciphertext'], 'aes-256-gcm', $this->aeadKey, OPENSSL_RAW_DATA,
            $data['nonce'], $data['tag'], $this->aad($shop, $customer, $digest));
        if ($json === false) {
            throw new \RuntimeException('Invalid storage state.');
        }
        $subscription = json_decode($json, true, 8, JSON_THROW_ON_ERROR);
        if (!is_array($subscription) || !isset($subscription['endpoint']) || !is_string($subscription['endpoint'])
            || !hash_equals($this->digest($subscription['endpoint']), $digest)) {
            throw new \RuntimeException('Invalid storage state.');
        }
        return SubscriptionValidator::validate($subscription);
    }

    private function aad(int $shop, int $customer, string $digest): string
    {
        if ($shop < 1 || $customer < 1 || preg_match('/\A[a-f0-9]{64}\z/D', $digest) !== 1) {
            throw new \RuntimeException('Invalid storage state.');
        }
        return 'ordenowa-push:v1:' . $shop . ':' . $customer . ':' . $digest;
    }
}
