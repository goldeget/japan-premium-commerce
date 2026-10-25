<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Fetching;

/** Restricted transport data, never returned directly to an importer/UI. */
final class TransportResponse
{
    public function __construct(
        public readonly int $status,
        public readonly string $body,
        public readonly string $contentType,
        public readonly ?string $location = null
    ) {
    }
}
