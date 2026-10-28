<?php

declare(strict_types=1);
namespace Kuranea\Catalog\Fetching;

/** A login link in a normal product header is harmless; credential forms are blocked. */
final class AuthenticationPage
{
    public static function present(string $html): bool
    {
        if (!preg_match('/<(?:form|input)\b/i', $html)) return false;
        $document = new \DOMDocument();
        $previous = libxml_use_internal_errors(true);
        try {
            if (!$document->loadHTML($html, LIBXML_NONET | LIBXML_NOWARNING | LIBXML_NOERROR | LIBXML_COMPACT)) return false;
            $xpath = new \DOMXPath($document);
            return ($xpath->query('//form[.//input[translate(@type,"PASSWORD","password")="password"]]')?->length ?? 0) > 0;
        } finally {
            libxml_clear_errors();
            libxml_use_internal_errors($previous);
        }
    }
}
