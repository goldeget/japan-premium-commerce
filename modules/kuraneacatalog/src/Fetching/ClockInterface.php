<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Fetching;

interface ClockInterface
{
    /** Monotonic seconds, independent of wall clock adjustments. */
    public function now(): float;
}
