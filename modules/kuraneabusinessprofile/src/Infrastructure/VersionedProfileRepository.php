<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Infrastructure;

use DomainException;
use JsonException;
use Kuranea\BusinessProfile\Domain\ProfileVersion;
use Kuranea\BusinessProfile\Domain\ProfileVersionRepositoryInterface;
use RuntimeException;

final class VersionedProfileRepository implements ProfileVersionRepositoryInterface
{
    private object $database;
    private string $prefix;

    public function __construct(?object $database = null, ?string $prefix = null)
    {
        if ($database === null) {
            if (!class_exists('Db')) {
                throw new RuntimeException('PrestaShop database service is not available.');
            }
            $database = \Db::getInstance();
        }

        $this->database = $database;
        $this->prefix = $prefix ?? (defined('_DB_PREFIX_') ? (string) _DB_PREFIX_ : '');
        DatabaseSchema::createVersionTableSql($this->prefix);
    }

    public function install(): bool
    {
        return $this->database->execute(DatabaseSchema::createVersionTableSql($this->prefix))
            && $this->database->execute(DatabaseSchema::createStateTableSql($this->prefix));
    }

    public function insertVersion(int $shopId, array $profile, int $employeeId, ?int $parentVersionId): ProfileVersion
    {
        $json = json_encode($profile, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        $inserted = $this->database->insert('kuraneabusinessprofile_version', [
            'id_shop' => $shopId,
            'parent_version_id' => $parentVersionId,
            'profile_json' => pSQL($json, true),
            'id_employee' => $employeeId,
            'created_at' => date('Y-m-d H:i:s'),
        ]);

        if (!$inserted) {
            throw new RuntimeException('Could not save the business profile version.');
        }

        $versionId = (int) $this->database->Insert_ID();
        return new ProfileVersion($versionId, $shopId, $profile, $employeeId, $parentVersionId, date('Y-m-d H:i:s'));
    }

    public function setDraftPointer(int $shopId, int $versionId): void
    {
        $this->ensureState($shopId);
        $ok = $this->database->execute('UPDATE `' . $this->prefix . 'kuraneabusinessprofile_state`'
            . ' SET `draft_version_id` = ' . (int) $versionId . ', `updated_at` = NOW()'
            . ' WHERE `id_shop` = ' . (int) $shopId);

        if (!$ok) {
            throw new RuntimeException('Could not update the draft profile pointer.');
        }
    }

    public function publishVersion(int $shopId, int $versionId, int $employeeId): void
    {
        if ($this->find($shopId, $versionId) === null) {
            throw new DomainException('Profile version does not belong to this shop.');
        }

        $this->ensureState($shopId);
        $ok = $this->database->execute('UPDATE `' . $this->prefix . 'kuraneabusinessprofile_state`'
            . ' SET `published_version_id` = ' . (int) $versionId
            . ', `published_by` = ' . (int) $employeeId
            . ', `published_at` = NOW(), `updated_at` = NOW()'
            . ' WHERE `id_shop` = ' . (int) $shopId);

        if (!$ok) {
            throw new RuntimeException('Could not publish the business profile.');
        }
    }

    public function loadDraft(int $shopId): ?ProfileVersion
    {
        return $this->loadPointer($shopId, 'draft_version_id');
    }

    public function loadPublished(int $shopId): ?ProfileVersion
    {
        return $this->loadPointer($shopId, 'published_version_id');
    }

    public function find(int $shopId, int $versionId): ?ProfileVersion
    {
        $rows = $this->database->executeS('SELECT `id_version`, `id_shop`, `parent_version_id`, `profile_json`, `id_employee`, `created_at`'
            . ' FROM `' . $this->prefix . 'kuraneabusinessprofile_version`'
            . ' WHERE `id_shop` = ' . (int) $shopId . ' AND `id_version` = ' . (int) $versionId . ' LIMIT 1');

        return is_array($rows) && isset($rows[0]) ? $this->fromRow($rows[0]) : null;
    }

    public function history(int $shopId): array
    {
        $rows = $this->database->executeS('SELECT `id_version`, `id_shop`, `parent_version_id`, `profile_json`, `id_employee`, `created_at`'
            . ' FROM `' . $this->prefix . 'kuraneabusinessprofile_version`'
            . ' WHERE `id_shop` = ' . (int) $shopId . ' ORDER BY `id_version` ASC');

        if (!is_array($rows)) {
            throw new RuntimeException('Could not load business profile history.');
        }

        return array_map(fn (array $row): ProfileVersion => $this->fromRow($row), $rows);
    }

    private function loadPointer(int $shopId, string $column): ?ProfileVersion
    {
        if (!in_array($column, ['draft_version_id', 'published_version_id'], true)) {
            throw new DomainException('Invalid profile pointer.');
        }

        $rows = $this->database->executeS('SELECT `' . $column . '` AS `id_version` FROM `'
            . $this->prefix . 'kuraneabusinessprofile_state` WHERE `id_shop` = ' . (int) $shopId . ' LIMIT 1');
        $versionId = is_array($rows) && isset($rows[0]['id_version']) ? (int) $rows[0]['id_version'] : 0;

        return $versionId > 0 ? $this->find($shopId, $versionId) : null;
    }

    private function ensureState(int $shopId): void
    {
        $ok = $this->database->execute('INSERT IGNORE INTO `' . $this->prefix . 'kuraneabusinessprofile_state`'
            . ' (`id_shop`, `updated_at`) VALUES (' . (int) $shopId . ', NOW())');

        if (!$ok) {
            throw new RuntimeException('Could not initialize profile state for the shop.');
        }
    }

    /** @param array<string, mixed> $row */
    private function fromRow(array $row): ProfileVersion
    {
        try {
            $profile = json_decode((string) $row['profile_json'], true, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new RuntimeException('Stored profile JSON is invalid.', 0, $exception);
        }

        if (!is_array($profile)) {
            throw new RuntimeException('Stored profile must be a JSON object.');
        }

        $parentId = isset($row['parent_version_id']) && (int) $row['parent_version_id'] > 0
            ? (int) $row['parent_version_id']
            : null;

        return new ProfileVersion(
            (int) $row['id_version'],
            (int) $row['id_shop'],
            $profile,
            (int) $row['id_employee'],
            $parentId,
            (string) $row['created_at']
        );
    }
}
