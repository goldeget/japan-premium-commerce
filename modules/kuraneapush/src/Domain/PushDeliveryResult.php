<?php

declare(strict_types=1);
namespace Kuranea\Push\Domain;

final class PushDeliveryResult
{
    public const DELIVERED = 'delivered';
    public const GONE = 'gone';
    public const RETRYABLE_FAILURE = 'retryable_failure';

    public readonly string $status;

    public function __construct(string $status)
    {
        if (!in_array($status, [self::DELIVERED, self::GONE, self::RETRYABLE_FAILURE], true)) {
            throw new \InvalidArgumentException('Invalid delivery result.');
        }
        $this->status = $status;
    }
}
