<?php

declare(strict_types=1);
namespace Kuranea\Push\Infrastructure;
use Kuranea\Push\Domain\SubscriptionStore;

final class SubscriptionRepository implements SubscriptionStore
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
            PRIMARY KEY (id_subscription),
            UNIQUE KEY shop_endpoint (id_shop, endpoint_digest),
            KEY owner (id_shop, id_customer)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci');
    }

    public function active(int $shop, int $customer): bool
    {
        $rows = $this->db->executeS('SELECT id_subscription FROM ' . $this->table . $this->owner($shop, $customer) . ' LIMIT 1');
        if (!is_array($rows)) {
            throw new \RuntimeException('Storage unavailable.');
        }
        return $rows !== [];
    }

    public function save(int $shop, int $customer, string $digest, string $envelope): void
    {
        if (preg_match('/\A[a-f0-9]{64}\z/D', $digest) !== 1 || strlen($envelope) > 8192) {
            throw new \RuntimeException('Invalid storage state.');
        }
        $where = $this->owner($shop, $customer) . " AND endpoint_digest='" . pSQL($digest) . "'";
        $existing = $this->db->executeS('SELECT id_subscription FROM ' . $this->table . $where . ' LIMIT 1');
        if (!is_array($existing)) {
            throw new \RuntimeException('Storage unavailable.');
        }
        if ($existing !== []) {
            return;
        }
        // Never upsert: the shop-wide unique key rejects ownership transfer, including races.
        $saved = $this->db->execute('INSERT INTO ' . $this->table
            . ' (id_shop,id_customer,endpoint_digest,encrypted_subscription,created_at) VALUES ('
            . (int) $shop . ',' . (int) $customer . ",'" . pSQL($digest) . "','" . pSQL($envelope) . "',UTC_TIMESTAMP())");
        if (!$saved) {
            $owned = $this->db->executeS('SELECT id_subscription FROM ' . $this->table . $where . ' LIMIT 1');
            if (!is_array($owned) || $owned === []) {
                throw new \RuntimeException('Subscription unavailable.');
            }
        }
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
}
