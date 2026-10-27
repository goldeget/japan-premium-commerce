<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

final class RobotsSitemapDirective
{
    private const OWNER_MARKER = '# ORDENOWA XML sitemap';

    public static function rewriteContent(string $content, ?string $sitemapUrl): string
    {
        $newline = str_contains($content, "\r\n") ? "\r\n" : "\n";
        $lines = preg_split('/\r\n|\n|\r/', $content);
        if (!is_array($lines)) {
            return $content;
        }

        $filtered = [];
        for ($index = 0, $count = count($lines); $index < $count; ++$index) {
            if (trim((string) $lines[$index]) !== self::OWNER_MARKER) {
                $filtered[] = $lines[$index];
                continue;
            }

            if (isset($lines[$index + 1]) && preg_match('/^[ \t]*Sitemap[ \t]*:/i', (string) $lines[$index + 1]) === 1) {
                ++$index;
            }
        }

        $content = implode($newline, $filtered);
        if ($sitemapUrl === null || !SitemapUrlPolicy::isSafeAbsoluteSitemapUrl($sitemapUrl)) {
            return $content;
        }

        $content = rtrim($content, "\r\n");
        if ($content !== '') {
            $content .= $newline . $newline;
        }

        return $content . self::OWNER_MARKER . $newline . 'Sitemap: ' . $sitemapUrl . $newline;
    }

    /** Rewrite PrestaShop's already-written file without changing its Allow/Disallow rules. */
    public static function rewriteStream(mixed $writeStream, string $robotsPath, ?string $sitemapUrl): bool
    {
        if (!is_resource($writeStream) || !fflush($writeStream)) {
            return false;
        }

        $content = @file_get_contents($robotsPath);
        if (!is_string($content)) {
            return false;
        }

        return self::writeStream($writeStream, self::rewriteContent($content, $sitemapUrl));
    }

    public static function rewriteExistingFile(string $robotsPath, ?string $sitemapUrl): bool
    {
        if (!is_file($robotsPath)) {
            return true;
        }

        $content = @file_get_contents($robotsPath);
        if (!is_string($content)) {
            return false;
        }

        $updated = self::rewriteContent($content, $sitemapUrl);
        return @file_put_contents($robotsPath, $updated, LOCK_EX) === strlen($updated);
    }

    private static function writeStream(mixed $writeStream, string $contents): bool
    {
        if (fseek($writeStream, 0) !== 0 || !ftruncate($writeStream, 0)) {
            return false;
        }

        $written = 0;
        $length = strlen($contents);
        while ($written < $length) {
            $chunk = fwrite($writeStream, substr($contents, $written));
            if (!is_int($chunk) || $chunk < 1) {
                return false;
            }
            $written += $chunk;
        }

        return fflush($writeStream);
    }
}
