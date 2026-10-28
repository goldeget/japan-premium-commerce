<?php

declare(strict_types=1);
namespace Kuranea\Backoffice\Infrastructure;

final class NativeAclAuditSchema
{
    public static function tableSql(string $prefix): string
    {
        if (preg_match('/\A[A-Za-z0-9_]*\z/D', $prefix) !== 1 || strlen($prefix . 'kuraneabackoffice_native_acl_audit') > 64) throw new \InvalidArgumentException('Invalid ACL audit table prefix.');
        return 'CREATE TABLE IF NOT EXISTS `' . $prefix . 'kuraneabackoffice_native_acl_audit` ('
            . 'id_event BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,id_shop INT UNSIGNED NOT NULL DEFAULT 0,'
            . 'context_shop_id INT UNSIGNED NOT NULL,actor_employee_id INT UNSIGNED NOT NULL,actor_profile_id INT UNSIGNED NOT NULL,'
            . 'target_profile_id INT UNSIGNED NOT NULL,access_kind VARCHAR(8) NOT NULL,role_id INT UNSIGNED NOT NULL,role_slug VARCHAR(255) NOT NULL,'
            . 'old_granted TINYINT UNSIGNED NOT NULL,new_granted TINYINT UNSIGNED NOT NULL,correlation_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,'
            . 'changed_at_utc DATETIME NOT NULL,UNIQUE observed_role(correlation_id,target_profile_id,access_kind,role_id),'
            . 'INDEX shop_event(id_shop,id_event),INDEX profile_event(target_profile_id,id_event)'
            . ') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci';
    }
}
