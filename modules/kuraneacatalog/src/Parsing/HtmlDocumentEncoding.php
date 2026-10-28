<?php

declare(strict_types=1);
namespace Kuranea\Catalog\Parsing;

/** Preserve explicitly declared Japanese encodings; never guess or replace invalid bytes. */
final class HtmlDocumentEncoding
{
    public static function utf8(string $html, string $contentType = ''): string
    {
        $encoding = null;
        if (preg_match('/charset\s*=\s*["\']?([A-Za-z0-9_-]+)/i', $contentType, $match)) $encoding = $match[1];
        if ($encoding === null && preg_match('/<meta\b[^>]*charset\s*=\s*["\']?([A-Za-z0-9_-]+)/i', substr($html, 0, 8192), $match)) $encoding = $match[1];
        $encoding = match (strtolower((string) $encoding)) {
            '', 'utf-8', 'utf8' => 'UTF-8',
            'shift_jis', 'shift-jis', 'sjis', 'windows-31j', 'cp932' => 'SJIS-win',
            'euc-jp', 'euc_jp' => 'EUC-JP',
            default => throw new \UnexpectedValueException('Unsupported source HTML character encoding.'),
        };
        if (!mb_check_encoding($html, $encoding)) throw new \UnexpectedValueException('Invalid source HTML character encoding.');
        if ($encoding === 'UTF-8') return $html;
        $html = mb_convert_encoding($html, 'UTF-8', $encoding);
        return preg_replace('/(<meta\b[^>]*charset\s*=\s*["\']?)[A-Za-z0-9_-]+/i', '${1}UTF-8', $html) ?? $html;
    }
}
