<?php

declare(strict_types=1);

namespace Kuranea\Postcode\Domain;

use Generator;
use RuntimeException;

/** Parser for Japan Post's headerless 15-column KEN_ALL CSV layout. */
final class KenAllCsvParser
{
    /** @return Generator<int, array<int, string>> */
    public function readRows(string $file): Generator
    {
        $handle = @fopen($file, 'rb');
        if ($handle === false) {
            throw new RuntimeException(sprintf('Cannot open KEN_ALL CSV file: %s', $file));
        }

        try {
            while (($row = fgetcsv($handle, 0, ',', '"', '')) !== false) {
                if ($row === [null] || $row === []) {
                    continue;
                }

                $row[0] = preg_replace('/^\xEF\xBB\xBF/', '', (string) $row[0]) ?? (string) $row[0];
                yield $this->decodeRow($row);
            }
        } finally {
            fclose($handle);
        }
    }

    /** @param array<int, string|null> $row */
    public function parseRow(array $row): ?PostalAddress
    {
        if (count($row) < 9) {
            return null;
        }

        $jisCode = trim((string) $row[0]);
        $postcode = ZipCode::normalize((string) $row[2]);
        $prefecture = trim((string) $row[6]);
        $municipality = trim((string) $row[7]);
        $town = trim((string) $row[8]);

        if (!preg_match('/^[0-9]{5}$/D', $jisCode)
            || $postcode === null
            || $prefecture === ''
            || $municipality === '') {
            return null;
        }

        return new PostalAddress($postcode, $jisCode, $prefecture, $municipality, $town);
    }

    /** @param array<int, string|null> $row
     *  @return array<int, string>
     */
    private function decodeRow(array $row): array
    {
        $decoded = [];
        foreach ($row as $field) {
            $field = (string) $field;
            if (preg_match('//u', $field) === 1) {
                $decoded[] = $field;
                continue;
            }

            $utf8 = iconv('CP932', 'UTF-8', $field);
            if ($utf8 === false) {
                throw new RuntimeException('KEN_ALL CSV contains data that is neither UTF-8 nor valid CP932.');
            }
            $decoded[] = $utf8;
        }

        return $decoded;
    }
}
