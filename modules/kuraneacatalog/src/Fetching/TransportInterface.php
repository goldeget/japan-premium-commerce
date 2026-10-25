<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Fetching;

interface TransportInterface
{
    /**
     * One request, no redirects or retries. Pin a supplied address while keeping
     * original-host TLS verification and configured proxy routing. Enforce the
     * time budgets and decoded-byte ceiling while streaming, not after buffering.
     */
    public function request(FetchRequest $request): TransportResponse;
}
