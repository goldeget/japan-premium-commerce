<?php

declare(strict_types=1);
namespace Kuranea\Push\Infrastructure;
use Kuranea\Push\Domain\SubscriptionStore;
use Kuranea\Push\Domain\PushDeliveryStore;

final class SubscriptionRepository implements SubscriptionStore, PushDeliveryStore
{
    private object $db;
    private string $table;
    public function __construct(?object $db = null, ?string $prefix = null)
    {
        $this->db = $db ?? \Db::getInstance();
        $prefix ??= _DB_PREFIX_;
        if (preg_match('/\A[A-Za-z0-9_]*\z/D', $prefix) !== 1) {
            throw new \RuntimeException('Storage unavailable.');
        }
        $this->table = '`' . $prefix . 'kuraneapush_subscription`';
    }

    public function install(): bool
    {
        return (bool) $this->db->execute('CREATE TABLE IF NOT EXISTS ' . $this->table . ' (
            id_subscription BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            id_shop INT UNSIGNED NOT NULL,
            id_customer INT UNSIGNED NOT NULL,
            endpoint_digest CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
            encrypted_subscription TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            consent_notice_version CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
            consent_locale CHAR(2) CHARACTER SET ascii COLLATE ascii_bin NULL,
            consent_accepted_at DATETIME NULL,
            PRIMARY KEY (id_subscription),
            UNIQUE KEY shop_endpoint (id_shop, endpoint_digest),
            KEY owner (id_shop, id_customer)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci')
            && $this->ensureColumn('consent_notice_version', 'CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL')
            && $this->ensureColumn('consent_locale', 'CHAR(2) CHARACTER SET ascii COLLATE ascii_bin NULL')
            && $this->ensureColumn('consent_accepted_at', 'DATETIME NULL');
    }

    public function active(int $shop, int $customer): bool
    {
        $rows = $this->db->executeS('SELECT id_subscription FROM ' . $this->table . $this->owner($shop, $customer)
            . ' AND consent_notice_version IS NOT NULL AND consent_locale IS NOT NULL AND consent_accepted_at IS NOT NULL LIMIT 1');
        if (!is_array($rows)) {
            throw new \RuntimeException('Storage unavailable.');
        }
        return $rows !== [];
    }

    public function stored(int $shop, int $customer): bool
    {
        $rows = $this->db->executeS('SELECT id_subscription FROM ' . $this->table . $this->owner($shop, $customer) . ' LIMIT 1');
        if (!is_array($rows)) {
            throw new \RuntimeException('Storage unavailable.');
        }
        return $rows !== [];
    }

    public function deliveryTargetsForOwner(int $shop, int $customer): array
    {
        $rows = $this->db->executeS('SELECT id_subscription,id_shop,id_customer,endpoint_digest,encrypted_subscription,consent_notice_version,consent_locale,consent_accepted_at FROM '
            . $this->table . $this->owner($shop, $customer)
            . ' AND consent_notice_version IS NOT NULL AND consent_locale IS NOT NULL AND consent_accepted_at IS NOT NULL'
            . ' ORDER BY id_subscription ASC LIMIT ' . PushDeliveryStore::MAX_DELIVERY_TARGETS);
        if (!is_array($rows)) {
            throw new \RuntimeException('Storage unavailable.');
        }
        return $rows;
    }

    public function removeDeliveryTargetForOwner(int $shop, int $customer, string $digest): void
    {
        if (preg_match('/\A[a-f0-9]{64}\z/D', $digest) !== 1) {
            throw new \RuntimeException('Invalid storage state.');
        }
        if (!$this->db->execute('DELETE FROM ' . $this->table . $this->owner($shop, $customer)
            . " AND endpoint_digest='" . pSQL($digest) . "'")) {
            throw new \RuntimeException('Storage unavailable.');
        }
    }

    public function save(int $shop, int $customer, string $digest, string $envelope, string $locale, string $consentNoticeVersion): void
    {
        if (preg_match('/\A[a-f0-9]{64}\z/D', $digest) !== 1 || strlen($envelope) > 8192
            || !in_array($locale, ['ja', 'en', 'ko'], true) || preg_match('/\A[a-f0-9]{64}\z/D', $consentNoticeVersion) !== 1) {
            throw new \RuntimeException('Invalid storage state.');
        }
        $where = $this->owner($shop, $customer) . " AND endpoint_digest='" . pSQL($digest) . "'";
        $existing = $this->db->executeS('SELECT id_subscription FROM ' . $this->table . $where . ' LIMIT 1');
        if (!is_array($existing)) {
            throw new \RuntimeException('Storage unavailable.');
        }
        if ($existing !== []) {
            $this->updateConsent($where, $locale, $consentNoticeVersion, $envelope);
            return;
        }
        // Never upsert: the shop-wide unique key rejects ownership transfer, including races.
        $saved = $this->db->execute('INSERT INTO ' . $this->table
            . ' (id_shop,id_customer,endpoint_digest,encrypted_subscription,created_at,consent_notice_version,consent_locale,consent_accepted_at) VALUES ('
            . (int) $shop . ',' . (int) $customer . ",'" . pSQL($digest) . "','" . pSQL($envelope) . "',UTC_TIMESTAMP(),'"
            . pSQL($consentNoticeVersion) . "','" . pSQL($locale) . "',UTC_TIMESTAMP())");
        if (!$saved) {
            $owned = $this->db->executeS('SELECT id_subscription FROM ' . $this->table . $where . ' LIMIT 1');
            if (!is_array($owned) || $owned === []) {
                throw new \RuntimeException('Subscription unavailable.');
            }
            $this->updateConsent($where, $locale, $consentNoticeVersion, $envelope);
            return;
        }
        $this->assertConsentSaved($where, $locale, $consentNoticeVersion, $envelope);
    }

    public function revoke(int $shop, int $customer): void
    {
        if (!$this->db->execute('DELETE FROM ' . $this->table . $this->owner($shop, $customer))) {
            throw new \RuntimeException('Storage unavailable.');
        }
    }

    /** Customer erasure deliberately enumerates shops rather than using an unscoped delete. */
    public function deleteCustomer(int $customer, array $shopIds): void
    {
        foreach ($shopIds as $shop) {
            $this->revoke((int) $shop, $customer);
        }
    }

    private function owner(int $shop, int $customer): string
    {
        if ($shop < 1 || $customer < 1) {
            throw new \RuntimeException('Invalid owner.');
        }
        return ' WHERE id_shop=' . (int) $shop . ' AND id_customer=' . (int) $customer;
    }

    private function ensureColumn(string $column, string $definition): bool
    {
        if (!in_array($column, ['consent_notice_version', 'consent_locale', 'consent_accepted_at'], true)) {
            return false;
        }
        $rows = $this->db->executeS('SHOW COLUMNS FROM ' . $this->table . " LIKE '" . pSQL($column) . "'");
        if (!is_array($rows)) {
            return false;
        }
        if ($rows !== []) {
            return true;
        }
        return (bool) $this->db->execute('ALTER TABLE ' . $this->table . ' ADD ' . $column . ' ' . $definition);
    }

    private function updateConsent(string $where, string $locale, string $consentNoticeVersion, string $envelope): void
    {
        $updated = $this->db->execute('UPDATE ' . $this->table . " SET encrypted_subscription='" . pSQL($envelope)
            . "', consent_notice_version='" . pSQL($consentNoticeVersion) . "', consent_locale='" . pSQL($locale)
            . "', consent_accepted_at=UTC_TIMESTAMP()" . $where);
        if (!$updated) {
            throw new \RuntimeException('Consent storage unavailable.');
        }
        $this->assertConsentSaved($where, $locale, $consentNoticeVersion, $envelope);
    }

    private function assertConsentSaved(string $where, string $locale, string $consentNoticeVersion, string $envelope): void
    {
        $rows = $this->db->executeS('SELECT encrypted_subscription,consent_notice_version,consent_locale,consent_accepted_at FROM '
            . $this->table . $where . ' LIMIT 1');
        $row = is_array($rows) ? ($rows[0] ?? null) : null;
        if (!is_array($row) || !isset($row['encrypted_subscription'], $row['consent_notice_version'], $row['consent_locale'], $row['consent_accepted_at'])
            || !is_string($row['encrypted_subscription']) || !hash_equals($envelope, $row['encrypted_subscription'])
            || !is_string($row['consent_notice_version']) || !hash_equals($consentNoticeVersion, $row['consent_notice_version'])
            || !is_string($row['consent_locale']) || $row['consent_locale'] !== $locale
            || !is_string($row['consent_accepted_at']) || trim($row['consent_accepted_at']) === '') {
            throw new \RuntimeException('Consent storage unavailable.');
        }
    }
}
