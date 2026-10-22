<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

final class OrderConfirmationMailContent
{
    /**
     * Add a published profile block to PrestaShop's fully rendered order confirmation templates.
     *
     * @param array<string, mixed> $profile
     */
    public static function append(
        string $template,
        string &$templateHtml,
        string &$templateTxt,
        array $profile,
        bool $commerceEnabled
    ): bool {
        if ($template !== 'order_conf') {
            return false;
        }

        $bodyClosePosition = strripos(strtolower($templateHtml), '</body>');
        if ($bodyClosePosition === false) {
            return false;
        }

        $htmlBlock = PublicFooterBuilder::build($profile, $commerceEnabled);
        $textBlock = self::toPlainText($htmlBlock);
        if (trim($htmlBlock) === '' || $textBlock === '') {
            return false;
        }

        $templateHtml = substr_replace($templateHtml, $htmlBlock, $bodyClosePosition, 0);
        $templateTxt .= "\n\n" . $textBlock;

        return true;
    }

    private static function toPlainText(string $html): string
    {
        $withLineBreaks = preg_replace('~<br\s*/?>~i', "\n", $html) ?? $html;
        $withLineBreaks = preg_replace('~</(?:p|section|h[1-6]|div|dt|dd|li|ul|dl)>~i', "\n", $withLineBreaks) ?? $withLineBreaks;
        $text = html_entity_decode(strip_tags($withLineBreaks), ENT_QUOTES | ENT_HTML5, 'UTF-8');
        $text = str_replace("\xc2\xa0", ' ', $text);
        $text = preg_replace('/[ \t]+\n/', "\n", $text) ?? $text;
        $text = preg_replace('/\n{3,}/', "\n\n", $text) ?? $text;

        return trim($text);
    }
}
