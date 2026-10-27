<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

final class SitemapXmlRenderer
{
    /** @param list<string> $urls */
    public static function urlSet(array $urls): ?string
    {
        if (count($urls) > SitemapUrlPolicy::MAX_URLS_PER_SITEMAP) {
            return null;
        }

        $xml = '<?xml version="1.0" encoding="UTF-8"?>' . "\n"
            . '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">';
        foreach ($urls as $url) {
            if (!is_string($url) || strlen($url) > SitemapUrlPolicy::MAX_URL_BYTES) {
                return null;
            }
            $xml .= '<url><loc>' . self::escape($url) . '</loc></url>';
        }
        $xml .= '</urlset>';

        return strlen($xml) <= SitemapUrlPolicy::MAX_XML_BYTES ? $xml : null;
    }

    /** @param list<string> $urls */
    public static function index(array $urls): ?string
    {
        if (count($urls) > SitemapUrlPolicy::MAX_SITEMAPS_PER_INDEX) {
            return null;
        }

        $xml = '<?xml version="1.0" encoding="UTF-8"?>' . "\n"
            . '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">';
        foreach ($urls as $url) {
            if (!is_string($url) || strlen($url) > SitemapUrlPolicy::MAX_URL_BYTES) {
                return null;
            }
            $xml .= '<sitemap><loc>' . self::escape($url) . '</loc></sitemap>';
        }
        $xml .= '</sitemapindex>';

        return strlen($xml) <= SitemapUrlPolicy::MAX_XML_BYTES ? $xml : null;
    }

    private static function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_XML1 | ENT_SUBSTITUTE, 'UTF-8');
    }
}
