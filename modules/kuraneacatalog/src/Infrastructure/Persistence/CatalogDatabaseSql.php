<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Infrastructure\Persistence;

use DateTimeImmutable;
use DateTimeZone;
use JsonException;
use RuntimeException;

final class CatalogDatabaseSql
{
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
