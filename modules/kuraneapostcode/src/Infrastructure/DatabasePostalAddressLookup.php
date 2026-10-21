<?php

declare(strict_types=1);

namespace Kuranea\Postcode\Infrastructure;

use Kuranea\Postcode\Domain\PostalAddress;
use Kuranea\Postcode\Domain\PostalAddressLookup;
use Kuranea\Postcode\Domain\ZipCode;

/** Read-only PrestaShop database adapter for the public postal candidate API. */
final class DatabasePostalAddressLookup implements PostalAddressLookup
{
    /** @var object */
    private $database;

    /** @param object|null $database PrestaShop Db connection; injectable for adapters. */
    public function __construct($database = null)
    {
        $this->database = $database ?? \Db::getInstance(defined('_PS_USE_SQL_SLAVE_') ? _PS_USE_SQL_SLAVE_ : false);
    }

    public function lookupByPostcode(string $postcode, int $limit = 20): array
    {
        $normalized = ZipCode::normalize($postcode);
        if ($normalized === null) {
            return [];
        }

        $escaped = \pSQL($normalized);

        return $this->fetch("`postcode` = '{$escaped}'", $limit);
    }

    public function searchJapaneseAddress(string $query, int $limit = 20): array
    {
        if ($query === '' || preg_match('/[%_\\\\]/u', $query) === 1) {
            return [];
        }

        $escaped = \pSQL($query);

        return $this->fetch("CONCAT(`prefecture`, `municipality`, `town`) LIKE '%{$escaped}%'", $limit);
    }

    /** @return list<PostalAddress> */
    private function fetch(string $where, int $limit): array
    {
        $limit = max(1, min(100, $limit));
        $table = '`' . _DB_PREFIX_ . 'kuraneapostcode_address`';
        $rows = $this->database->executeS(
            'SELECT `postcode`, `jis_code`, `prefecture`, `municipality`, `town` FROM ' . $table
            . ' WHERE ' . $where
            . ' ORDER BY `prefecture`, `municipality`, `town` LIMIT ' . $limit
        );

        if (!is_array($rows)) {
            return [];
        }

        $addresses = [];
        foreach ($rows as $row) {
            $addresses[] = new PostalAddress(
                (string) $row['postcode'],
                (string) $row['jis_code'],
                (string) $row['prefecture'],
                (string) $row['municipality'],
                (string) $row['town']
            );
        }

        return $addresses;
    }
}
