<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Fetching;

/** Only fixed, nonsecret messages leave the public fetching boundary. */
final class FetchException extends \RuntimeException
{
    public const FAILURE_FETCH = 'fetch_failed';
    public const FAILURE_ACCESS_BLOCKED = 'access_blocked';
    public const FAILURE_SOURCE_UNAVAILABLE = 'source_unavailable';

    public function __construct(string $message, public readonly string $failureCategory = self::FAILURE_FETCH)
    {
        if (!in_array($failureCategory, [self::FAILURE_FETCH, self::FAILURE_ACCESS_BLOCKED, self::FAILURE_SOURCE_UNAVAILABLE], true)) {
            throw new \InvalidArgumentException('Unsupported safe product-fetch failure category.');
        }
        parent::__construct($message);
    }
}
