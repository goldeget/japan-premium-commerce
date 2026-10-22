<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Parsing;

use DateTimeImmutable;
use Kuranea\Catalog\Domain\NormalizedProductSnapshot;

interface ProductPageParserInterface
{
    /**
     * Parse an already available HTML snapshot. This method performs no HTTP
     * requests, image downloads, cookies, or browser automation.
     */
    public function parse(
        string $html,
        string $sourceUrl,
        ?DateTimeImmutable $fetchedAt = null
    ): NormalizedProductSnapshot;
}
