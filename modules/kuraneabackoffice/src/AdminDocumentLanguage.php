<?php

declare(strict_types=1);

namespace Kuranea\Backoffice;

final class AdminDocumentLanguage
{
    public static function rootTag(string $content): ?string
    {
        $bounds = self::rootTagBounds($content);
        if ($bounds === null) {
            return null;
        }

        return substr($content, $bounds['start'], $bounds['end'] - $bounds['start']);
    }

    public static function setRootLocale(string $content, string $locale): ?string
    {
        $bounds = self::rootTagBounds($content);
        if ($bounds === null) {
            return null;
        }

        $escapedLocale = htmlspecialchars($locale, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
        $rootTag = substr($content, $bounds['start'], $bounds['end'] - $bounds['start']);
        $languageAttributeCount = 0;
        $localizedTag = preg_replace_callback(
            '/(\s+lang\s*=\s*)(?:"[^"]*"|\'[^\']*\'|[^\s"\'=<>`]+)/i',
            static fn (array $matches): string => $matches[1] . '"' . $escapedLocale . '"',
            $rootTag,
            1,
            $languageAttributeCount
        );

        if (!is_string($localizedTag)) {
            return null;
        }

        if ($languageAttributeCount === 0) {
            $suffix = str_ends_with(substr($rootTag, 0, -1), '/') ? '/>' : '>';
            $openingTag = substr($rootTag, 0, strlen($rootTag) - strlen($suffix));
            $localizedTag = $openingTag . ' lang="' . $escapedLocale . '"' . $suffix;
        }

        return substr($content, 0, $bounds['start'])
            . $localizedTag
            . substr($content, $bounds['end']);
    }

    /** @return array{start: int, end: int}|null */
    private static function rootTagBounds(string $content): ?array
    {
        $length = strlen($content);
        $offset = str_starts_with($content, "\xEF\xBB\xBF") ? 3 : 0;

        while ($offset < $length) {
            while ($offset < $length && str_contains("\x09\x0A\x0C\x0D\x20", $content[$offset])) {
                ++$offset;
            }

            if (substr($content, $offset, 4) === '<!--') {
                $commentEnd = strpos($content, '-->', $offset + 4);
                if ($commentEnd === false) {
                    return null;
                }
                $offset = $commentEnd + 3;
                continue;
            }

            if (substr($content, $offset, 2) === '<?') {
                $instructionEnd = strpos($content, '?>', $offset + 2);
                if ($instructionEnd === false) {
                    return null;
                }
                $offset = $instructionEnd + 2;
                continue;
            }

            if (substr($content, $offset, 2) === '<!') {
                $declarationEnd = self::declarationEnd($content, $offset);
                if ($declarationEnd === null) {
                    return null;
                }
                $offset = $declarationEnd;
                continue;
            }

            break;
        }

        if (preg_match('/\G<html(?=[\x09\x0A\x0C\x0D\x20\/>])/i', $content, $matches, 0, $offset) !== 1) {
            return null;
        }

        $tagEnd = self::tagEnd($content, $offset + strlen($matches[0]));
        if ($tagEnd === null) {
            return null;
        }

        return ['start' => $offset, 'end' => $tagEnd];
    }

    private static function declarationEnd(string $content, int $start): ?int
    {
        $length = strlen($content);
        $quote = null;
        $subsetDepth = 0;

        for ($offset = $start + 2; $offset < $length; ++$offset) {
            $character = $content[$offset];
            if ($quote !== null) {
                if ($character === $quote) {
                    $quote = null;
                }
                continue;
            }

            if ($character === '"' || $character === "'") {
                $quote = $character;
            } elseif ($character === '[') {
                ++$subsetDepth;
            } elseif ($character === ']' && $subsetDepth > 0) {
                --$subsetDepth;
            } elseif ($character === '>' && $subsetDepth === 0) {
                return $offset + 1;
            }
        }

        return null;
    }

    private static function tagEnd(string $content, int $offset): ?int
    {
        $length = strlen($content);
        $quote = null;

        for (; $offset < $length; ++$offset) {
            $character = $content[$offset];
            if ($quote !== null) {
                if ($character === $quote) {
                    $quote = null;
                }
                continue;
            }

            if ($character === '"' || $character === "'") {
                $quote = $character;
            } elseif ($character === '>') {
                return $offset + 1;
            }
        }

        return null;
    }
}
