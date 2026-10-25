<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Fetching;

interface ResolverInterface
{
    /**
     * Return every A/AAAA destination for this host; no network connections.
     * Implementations MUST bound resolution by timeoutSeconds, including CNAME
     * traversal. dns_get_record alone cannot provide that deadline guarantee.
     * Never return a prefiltered subset that conceals nonpublic answers.
     *
     * @return list<string>
     */
    public function resolve(string $host, float $timeoutSeconds): array;
}
