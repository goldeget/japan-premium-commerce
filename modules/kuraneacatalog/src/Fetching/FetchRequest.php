<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Fetching;

final class FetchRequest
{
    /** @param non-empty-list<string> $addresses */
    public function __construct(
        public readonly string $canonicalUrl,
        public readonly array $addresses,
        public readonly float $timeoutSeconds,
        public readonly float $connectTimeoutSeconds,
        public readonly int $maxDecodedBytes
    ) {
    }
}
