<?php

declare(strict_types=1);

namespace Kuranea\Postcode\Domain;

final class KenAllCsvImporter
{
    public function __construct(private readonly KenAllCsvParser $parser)
    {
    }

    /**
     * Parse a local official-data file and send each valid row to a caller-owned
     * persistence adapter. This method never fetches data or touches a database.
     *
     * @param callable(PostalAddress): void $persist
     */
    public function import(string $file, callable $persist): ImportSummary
    {
        $imported = 0;
        $skipped = 0;

        foreach ($this->parser->readRows($file) as $row) {
            $address = $this->parser->parseRow($row);
            if ($address === null) {
                ++$skipped;
                continue;
            }

            $persist($address);
            ++$imported;
        }

        return new ImportSummary($imported, $skipped);
    }
}
