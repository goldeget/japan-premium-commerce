<?php
declare(strict_types=1);

namespace Ordenowa\Procurement\Points;

final class BalanceMismatch extends \RuntimeException
{
    public function __construct(public readonly int $accountId, public readonly int $version)
    {
        parent::__construct('Point reconciliation failed; operator review is required.', 503);
    }
}
