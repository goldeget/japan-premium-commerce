<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

final class SitemapEndpoint
{
    /** @param array{status: int, body: string} $response */
    public static function send(array $response): never
    {
        http_response_code(max(200, min(599, (int) ($response['status'] ?? 503))));
        header('Content-Type: application/xml; charset=utf-8');
        header('X-Content-Type-Options: nosniff');
        header('X-Robots-Tag: noindex');
        header('Cache-Control: private, no-store, max-age=0');
        echo (string) ($response['body'] ?? '');
        exit;
    }
}
