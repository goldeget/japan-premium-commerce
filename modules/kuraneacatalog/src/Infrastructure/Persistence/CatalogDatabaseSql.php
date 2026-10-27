<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Infrastructure\Persistence;

use DateTimeImmutable;
use DateTimeZone;
use JsonException;
use RuntimeException;

final class CatalogDatabaseSql
{
    /**
     * Read one row under a write lock without Db::getRow()'s trailing LIMIT 1.
     * PrestaShop appends that clause after the supplied SQL, which makes a
     * trailing FOR UPDATE invalid on MariaDB/MySQL.
     *
     * @return array<string, mixed>|null
     */
    public static function selectOneForUpdate(object $database, string $select): ?array
    {
        $query = rtrim($select, " \t\n\r\0\x0B;");
        if (preg_match('/\\A\\s*SELECT\\s/i', $query) !== 1
            || preg_match('/\\b(?:LIMIT|FOR\\s+UPDATE)\\b/i', $query) === 1) {
            throw new RuntimeException('Catalog database lock query is invalid.');
        }
        $rows = $database->executeS($query . ' LIMIT 1 FOR UPDATE', true, false);
        if (!is_array($rows)) {
            throw new RuntimeException('Catalog database row could not be locked.');
        }
        if (!isset($rows[0])) {
            return null;
        }
        if (!is_array($rows[0])) {
            throw new RuntimeException('Catalog database row is invalid.');
        }

        return $rows[0];
    }

    public static function quote(string $value): string
    {
        if (!function_exists('pSQL')) {
            throw new RuntimeException('Catalog database escaping is unavailable.');
        }

        return "'" . pSQL($value, true) . "'";
    }

    /** @param array<string, mixed> $value */
    public static function encode(array $value): string
    {
        try {
            return json_encode($value, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new RuntimeException('Catalog record could not be encoded.', 0, $exception);
        }
    }

    /** @return array<string, mixed> */
    public static function decode(string $value): array
    {
        try {
            $decoded = json_decode($value, true, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new RuntimeException('Catalog database record is invalid.', 0, $exception);
        }
        if (!is_array($decoded)) {
            throw new RuntimeException('Catalog database record is invalid.');
        }

        return $decoded;
    }

    public static function timestamp(DateTimeImmutable $date): string
    {
        return $date->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s');
    }

    public static function date(mixed $value): ?DateTimeImmutable
    {
        if (!is_string($value) || $value === '') {
            return null;
        }
        try {
            return new DateTimeImmutable($value, new DateTimeZone('UTC'));
        } catch (\Throwable $exception) {
            throw new RuntimeException('Catalog database timestamp is invalid.', 0, $exception);
        }
    }
}
