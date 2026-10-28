<?php
declare(strict_types=1);

namespace Ordenowa\Procurement\Infrastructure;

/** Additive installation only: existing commerce records are never touched. */
final class Schema
{
    public static function install(Database $db): void
    {
        $tables = [
            'assignment' => "id_assignment BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                id_shop INT UNSIGNED NOT NULL,id_customer INT UNSIGNED NOT NULL,
                id_product INT UNSIGNED NOT NULL,id_product_attribute INT UNSIGNED NOT NULL DEFAULT 0,
                product_snapshot LONGTEXT NOT NULL,default_quantity INT UNSIGNED NOT NULL,max_quantity INT UNSIGNED NOT NULL,
                instructions TEXT NOT NULL,deadline DATETIME NULL,status VARCHAR(16) NOT NULL,version BIGINT UNSIGNED NOT NULL DEFAULT 1,
                id_employee INT UNSIGNED NOT NULL,issued_at DATETIME NOT NULL,cancelled_reason TEXT NULL,
                INDEX customer_status(id_shop,id_customer,status,id_assignment),INDEX deadline_status(status,deadline)",
            'request' => "id_request BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                id_assignment BIGINT UNSIGNED NOT NULL,id_shop INT UNSIGNED NOT NULL,id_customer INT UNSIGNED NOT NULL,
                product_snapshot LONGTEXT NOT NULL,instructions TEXT NOT NULL,quantity INT UNSIGNED NOT NULL,
                status VARCHAR(16) NOT NULL,version BIGINT UNSIGNED NOT NULL DEFAULT 1,
                idempotency_key VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                payload_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,submitted_at DATETIME NOT NULL,
                UNIQUE assignment_once(id_assignment),UNIQUE customer_key(id_shop,id_customer,idempotency_key),
                INDEX customer_status(id_shop,id_customer,status,id_request),INDEX shop_status(id_shop,status,id_request)",
            'review' => "id_review BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,id_request BIGINT UNSIGNED NOT NULL,
                id_shop INT UNSIGNED NOT NULL,id_customer INT UNSIGNED NOT NULL,decision VARCHAR(16) NOT NULL,
                reason TEXT NOT NULL,id_employee INT UNSIGNED NOT NULL,reviewed_at DATETIME NOT NULL,
                UNIQUE request_final(id_request),INDEX shop_customer(id_shop,id_customer,id_review)",
            'point_account' => "id_account BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                id_shop INT UNSIGNED NOT NULL,id_customer INT UNSIGNED NOT NULL,balance BIGINT NOT NULL DEFAULT 0,
                version BIGINT UNSIGNED NOT NULL DEFAULT 1,updated_at DATETIME NOT NULL,
                UNIQUE customer_account(id_shop,id_customer)",
            'point_award' => "id_award BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                id_request BIGINT UNSIGNED NOT NULL,id_review BIGINT UNSIGNED NOT NULL,id_account BIGINT UNSIGNED NOT NULL,
                id_shop INT UNSIGNED NOT NULL,id_customer INT UNSIGNED NOT NULL,amount BIGINT NOT NULL,
                id_ledger BIGINT UNSIGNED NULL,id_employee INT UNSIGNED NOT NULL,created_at DATETIME NOT NULL,
                UNIQUE request_once(id_request),INDEX customer_award(id_shop,id_customer,id_award)",
            'point_ledger' => "id_ledger BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                id_account BIGINT UNSIGNED NOT NULL,id_award BIGINT UNSIGNED NOT NULL,id_shop INT UNSIGNED NOT NULL,
                id_customer INT UNSIGNED NOT NULL,entry_type VARCHAR(16) NOT NULL,delta BIGINT NOT NULL,
                original_entry BIGINT UNSIGNED NULL,reason TEXT NOT NULL,id_employee INT UNSIGNED NOT NULL,
                idempotency_key VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                payload_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,created_at DATETIME NOT NULL,
                UNIQUE shop_key(id_shop,idempotency_key),INDEX account_ledger(id_account,id_ledger),
                INDEX award_ledger(id_award,id_ledger),INDEX customer_ledger(id_shop,id_customer,id_ledger)",
            'activity' => "id_activity BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,id_shop INT UNSIGNED NOT NULL,
                actor_type VARCHAR(16) NOT NULL,actor_id INT UNSIGNED NOT NULL,action VARCHAR(64) NOT NULL,
                target_type VARCHAR(32) NOT NULL,target_id BIGINT UNSIGNED NOT NULL,safe_data TEXT NOT NULL,
                created_at DATETIME NOT NULL,INDEX shop_time(id_shop,id_activity),INDEX target(id_shop,target_type,target_id)",
            'notification' => "id_notification BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                id_shop INT UNSIGNED NOT NULL,id_customer INT UNSIGNED NOT NULL,event VARCHAR(64) NOT NULL,
                target_type VARCHAR(32) NOT NULL,target_id BIGINT UNSIGNED NOT NULL,
                event_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,status VARCHAR(16) NOT NULL,
                attempts INT UNSIGNED NOT NULL DEFAULT 0,created_at DATETIME NOT NULL,delivered_at DATETIME NULL,
                UNIQUE event_once(event_key),INDEX customer_notifications(id_shop,id_customer,id_notification),
                INDEX dispatch_status(status,id_notification)",
            'notification_delivery' => "id_delivery BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                id_notification BIGINT UNSIGNED NOT NULL,id_shop INT UNSIGNED NOT NULL,channel VARCHAR(16) NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'PENDING',attempts INT UNSIGNED NOT NULL DEFAULT 0,
                available_at DATETIME NOT NULL,claimed_at DATETIME NULL,sent_at DATETIME NULL,last_error_code VARCHAR(32) NULL,
                UNIQUE notification_channel(id_notification,channel),INDEX shop_dispatch(id_shop,status,available_at)",
            'policy' => "id_policy BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,id_shop INT UNSIGNED NOT NULL,
                version INT UNSIGNED NOT NULL,payload LONGTEXT NOT NULL,id_employee INT UNSIGNED NOT NULL,
                created_at DATETIME NOT NULL,UNIQUE shop_version(id_shop,version),INDEX shop_policy(id_shop,id_policy)",
        ];
        foreach ($tables as $suffix => $columns) {
            $db->execute('CREATE TABLE IF NOT EXISTS ' . $db->table($suffix) . ' (' . $columns
                . ') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci');
        }
    }
}
