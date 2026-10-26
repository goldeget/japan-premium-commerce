<?php

declare(strict_types=1);
namespace Kuranea\Push\Domain;

final class PushDeliverySummary
{
    public readonly string $status;
    public readonly int $delivered;
    public readonly int $permanentlyGone;
    public readonly int $retryableFailure;
    public readonly int $ineligible;

    public function __construct(string $status, int $delivered = 0, int $permanentlyGone = 0,
        int $retryableFailure = 0, int $ineligible = 0)
    {
        if (!in_array($status, ['completed', 'provider_unavailable', 'storage_unavailable'], true)
            || min($delivered, $permanentlyGone, $retryableFailure, $ineligible) < 0) {
            throw new \InvalidArgumentException('Invalid delivery summary.');
        }
        $this->status = $status;
        $this->delivered = $delivered;
        $this->permanentlyGone = $permanentlyGone;
        $this->retryableFailure = $retryableFailure;
        $this->ineligible = $ineligible;
    }
}
