<?php

declare(strict_types=1);
namespace Kuranea\Backoffice\Infrastructure;

/** Dedicated append-only observations of persisted native global profile permissions. */
final class NativeAclAuditRepository
{
    private object $database;
    private string $prefix;

    public function __construct(?object $database = null, ?string $prefix = null)
    {
        $this->database = $database ?? \Db::getInstance();
        $this->prefix = $prefix ?? (string) _DB_PREFIX_;
        NativeAclAuditSchema::tableSql($this->prefix);
    }

    public function actorMatches(int $employee, int $profile, int $shop): bool
    {
        if ($employee < 1 || $profile < 1 || $shop < 0) return false;
        return $this->rows('SELECT e.id_employee FROM `' . $this->prefix . 'employee` e'
            . ($shop > 0 ? ' INNER JOIN `' . $this->prefix . 'employee_shop` es ON es.id_employee=e.id_employee AND es.id_shop=' . $shop : '')
            . ' WHERE e.id_employee=' . $employee . ' AND e.id_profile=' . $profile . ' AND e.active=1 LIMIT 1') !== [];
    }

    public function profileExists(int $profile): bool
    {
        return $profile > 0 && $this->rows('SELECT id_profile FROM `' . $this->prefix . 'profile` WHERE id_profile=' . $profile . ' LIMIT 1') !== [];
    }

    public function begin(string $kind): void
    {
        if (!in_array($kind,['TAB','MODULE'],true)) throw new \InvalidArgumentException('Invalid ACL transaction kind.');
        $nativeTable = $this->prefix . ($kind === 'TAB' ? 'access' : 'module_access');
        $auditTable = $this->prefix . 'kuraneabackoffice_native_acl_audit';
        $engines = $this->rows('SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (' . $this->quote($nativeTable) . ',' . $this->quote($auditTable) . ')');
        if (count($engines) !== 2) throw new \RuntimeException('Native ACL transaction tables unavailable.');
        foreach ($engines as $engine) if (strtolower((string)$engine['ENGINE']) !== 'innodb') throw new \RuntimeException('Native ACL audit requires transactional tables.');
        $state = $this->rows('SELECT @@in_transaction AS active');
        if ((int)($state[0]['active'] ?? 0) !== 0) throw new \RuntimeException('ACL audit requires its own native transaction.');
        // Existence/readability is checked before any native permission write; no DDL occurs here.
        $this->rows('SELECT id_event FROM `' . $this->prefix . 'kuraneabackoffice_native_acl_audit` LIMIT 0');
        if ($this->database instanceof \PDO) $this->database->beginTransaction();
        else $this->write('START TRANSACTION');
    }

    public function commit(): void
    {
        if ($this->database instanceof \PDO) { if (!$this->database->commit()) throw new \RuntimeException('ACL audit commit failed.'); }
        else $this->write('COMMIT');
    }

    public function rollback(): void
    {
        if ($this->database instanceof \PDO) { if ($this->database->inTransaction()) $this->database->rollBack(); }
        else $this->write('ROLLBACK');
    }

    public function lock(int $profile): string
    {
        $name = 'ordenowa_acl_' . substr(hash('sha256', $this->prefix . ':' . $profile), 0, 40);
        $row = $this->rows('SELECT GET_LOCK(' . $this->quote($name) . ',5) AS acquired');
        if ((int) ($row[0]['acquired'] ?? 0) !== 1) throw new \RuntimeException('ACL observation lock unavailable.');
        return $name;
    }

    public function unlock(string $name): void
    {
        $this->rows('SELECT RELEASE_LOCK(' . $this->quote($name) . ') AS released');
    }

    /** Keyed native authorization roles, read without PrestaShop's permission cache. */
    public function snapshot(int $profile, string $kind, ?array $knownRoles = null): array
    {
        if ($profile < 1 || !in_array($kind, ['TAB','MODULE'], true)) throw new \InvalidArgumentException('Invalid ACL observation scope.');
        if ($knownRoles === []) return [];
        $table = $kind === 'TAB' ? 'access' : 'module_access';
        if ($knownRoles === null) {
            // Lock the native profile range, including missing role gaps, before taking the baseline.
            $this->rows('SELECT id_authorization_role FROM `' . $this->prefix . $table . '` WHERE id_profile=' . $profile . ' FOR UPDATE');
        }
        $ids = $knownRoles === null ? [] : array_map('intval', array_keys($knownRoles));
        $rows = $this->rows('SELECT r.id_authorization_role,r.slug,CASE WHEN a.id_profile IS NULL THEN 0 ELSE 1 END AS granted'
            . ' FROM `' . $this->prefix . 'authorization_role` r LEFT JOIN `' . $this->prefix . $table . '` a'
            . ' ON a.id_authorization_role=r.id_authorization_role AND a.id_profile=' . $profile
            . ' WHERE r.slug LIKE ' . $this->quote('ROLE_MOD_' . $kind . '_%')
            . ($knownRoles === null ? '' : ' AND r.id_authorization_role IN (' . implode(',', $ids) . ')')
            . ' ORDER BY r.id_authorization_role LIMIT 20001');
        if (count($rows) > 20000) throw new \RuntimeException('ACL observation exceeds supported role bound.');
        $result = [];
        foreach ($rows as $row) {
            $id = (int) $row['id_authorization_role'];
            $slug = (string) $row['slug'];
            if ($id > 0 && preg_match('/\AROLE_MOD_' . $kind . '_[A-Z0-9_]+_(?:CREATE|READ|UPDATE|DELETE)\z/D', $slug) === 1) $result[$id] = ['slug'=>$slug,'granted'=>(string)$row['granted'] === '1'];
        }
        return $result;
    }

    public function appendChanges(int $contextShop, int $actor, int $actorProfile, int $targetProfile, string $kind, array $before, array $after, string $correlation): int
    {
        if ($contextShop < 0 || min($actor,$actorProfile,$targetProfile) < 1 || !in_array($kind,['TAB','MODULE'],true)
            || preg_match('/\A[a-f0-9]{32}\z/D',$correlation) !== 1) throw new \InvalidArgumentException('Invalid ACL audit identity.');
        $values = [];
        $time = $this->quote(gmdate('Y-m-d H:i:s'));
        foreach ($before as $id => $old) {
            $new = $after[$id] ?? null;
            if (!is_array($new) || $old['slug'] !== $new['slug'] || $old['granted'] === $new['granted']) continue;
            // Native profile permissions apply globally, even when the actor selected one shop.
            $values[] = '(0,' . $contextShop . ',' . $actor . ',' . $actorProfile . ',' . $targetProfile . ',' . $this->quote($kind) . ',' . (int)$id . ','
                . $this->quote($old['slug']) . ',' . (int)$old['granted'] . ',' . (int)$new['granted'] . ',' . $this->quote($correlation) . ',' . $time . ')';
        }
        if ($values === []) return 0;
        $this->write('INSERT INTO `' . $this->prefix . 'kuraneabackoffice_native_acl_audit`'
            . ' (id_shop,context_shop_id,actor_employee_id,actor_profile_id,target_profile_id,access_kind,role_id,role_slug,old_granted,new_granted,correlation_id,changed_at_utc) VALUES ' . implode(',',$values));
        return count($values);
    }

    public function pageForShop(int $shop, int $page): array
    {
        if ($shop < 1 || $page < 1 || $page > 1000000) throw new \InvalidArgumentException('Invalid audit page.');
        $rows = $this->rows('SELECT id_event,context_shop_id,actor_employee_id,target_profile_id,access_kind,role_id,role_slug,old_granted,new_granted,changed_at_utc FROM `'
            . $this->prefix . 'kuraneabackoffice_native_acl_audit` WHERE (id_shop=0 OR id_shop=' . $shop . ') ORDER BY id_event DESC LIMIT 51 OFFSET ' . (($page-1)*50));
        return ['rows'=>array_slice($rows,0,50),'has_next'=>count($rows)>50];
    }

    private function rows(string $sql): array
    {
        $rows = $this->database instanceof \PDO ? $this->database->query($sql)->fetchAll(\PDO::FETCH_ASSOC) : $this->database->executeS($sql,true,false);
        if (!is_array($rows)) throw new \RuntimeException('ACL observation read unavailable.');
        return $rows;
    }

    private function write(string $sql): void
    {
        $result = $this->database instanceof \PDO ? $this->database->exec($sql) : $this->database->execute($sql,false);
        if ($result === false) throw new \RuntimeException('ACL audit write unavailable.');
    }

    private function quote(string $value): string
    {
        return $this->database instanceof \PDO ? $this->database->quote($value) : "'" . $this->database->escape($value,true) . "'";
    }
}
