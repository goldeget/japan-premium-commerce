<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Parsing;

use DOMElement;
use DOMXPath;

final class AmazonJapanHtmlParser extends AbstractProductPageParser
{
    protected const PROVIDER = 'amazon_jp';
    protected const ALLOWED_HOSTS = ['amazon.co.jp', 'www.amazon.co.jp'];

    protected function htmlProduct(DOMXPath $xpath): array
    {
        $microdata = parent::htmlProduct($xpath);
        if ($microdata !== []) return $microdata;
        $name = $this->nodeValue($xpath, '//*[@id="productTitle"]');
        if ($name === '') return [];
        $price = $this->nodeValue($xpath, '//*[@id="corePrice_feature_div" or @id="corePriceDisplay_desktop_feature_div"]//*[contains(concat(" ", normalize-space(@class), " "), " a-offscreen ")]');
        if ($price === '') $price = $this->nodeValue($xpath, '//*[@id="priceblock_ourprice" or @id="priceblock_dealprice"]');
        $currency = preg_match('/\A[¥￥]/u', $price) === 1 ? 'JPY' : '';
        $description = $this->nodeValue($xpath, '//*[@id="productDescription"]');
        if ($description === '') {
            $parts = [];
            foreach ($xpath->query('//*[@id="feature-bullets"]//li') ?: [] as $bullet) {
                $text = $this->cleanText($bullet->textContent);
                if ($text !== '') $parts[] = $text;
            }
            $description = implode(' ', $parts);
        }
        $images = [];
        foreach ($xpath->query('//img[@id="landingImage" or @id="imgBlkFront"]') ?: [] as $image) {
            if (!$image instanceof DOMElement) continue;
            $dynamic = json_decode($image->getAttribute('data-a-dynamic-image'), true);
            if (is_array($dynamic)) foreach (array_keys($dynamic) as $url) if (is_string($url)) $images[] = $url;
            $imageUrl = $image->getAttribute('data-old-hires') ?: $image->getAttribute('src');
            if ($imageUrl !== '') $images[] = $imageUrl;
        }
        $properties = [];
        foreach ($xpath->query('//*[starts-with(@id,"variation_")][.//select]') ?: [] as $group) {
            $label = rtrim($this->nodeValue($xpath, './/label', $group), ':： ');
            if ($label === '') continue;
            $values = [];
            foreach ($xpath->query('.//select/option', $group) ?: [] as $option) {
                if (!$option instanceof DOMElement || $option->hasAttribute('disabled') || in_array($option->getAttribute('value'), ['', '-1'], true)) continue;
                $value = $this->cleanText($option->textContent);
                if ($value !== '') $values[] = $value;
            }
            if ($values !== []) $properties[] = ['name' => $label, 'value' => $values];
        }
        return ['name' => $name, 'description' => $description, 'image' => $images,
            'offers' => ['price' => $price, 'priceCurrency' => $currency], 'additionalProperty' => $properties];
    }

    protected function extractProductId(array $product, string $sourceUrl): string
    {
        $path = (string) (parse_url($sourceUrl, PHP_URL_PATH) ?: '');
        if (preg_match('~/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)~i', $path, $matches) === 1) {
            return strtoupper($matches[1]);
        }

        foreach (['asin', 'productID', 'sku', 'mpn'] as $key) {
            $value = trim((string) ($product[$key] ?? ''));
            if ($value !== '') {
                return strtoupper($value);
            }
        }

        return '';
    }
}
