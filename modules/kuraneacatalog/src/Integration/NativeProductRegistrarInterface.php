<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Integration;

interface NativeProductRegistrarInterface
{
    /**
     * Register or return the native product for this stable TEST reference.
     * Implementations must be idempotent because queue persistence can fail
     * after a native product has been created.
     */
    public function register(NativeProductRegistration $registration): int;
}
