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
        $images = $this->amazonImageUrls($xpath);
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
        $categoryLabels = [];
        foreach ($xpath->query('//*[@id="wayfinding-breadcrumbs_feature_div"]//li/a') ?: [] as $breadcrumb) {
            if (!$breadcrumb instanceof DOMElement) continue;
            $label = $this->cleanText($breadcrumb->textContent);
            if ($label !== '' && $label !== $name && !in_array($label, $categoryLabels, true)) $categoryLabels[] = $label;
        }
        $categories = $categoryLabels === [] ? [] : [implode(' > ', $categoryLabels)];
        return ['name' => $name, 'category' => $categories, 'description' => $description, 'image' => $images,
            'offers' => ['price' => $price, 'priceCurrency' => $currency], 'additionalProperty' => $properties];
    }

    /** @return list<string> */
    private function amazonImageUrls(DOMXPath $xpath): array
    {
        $galleryItems = $xpath->query('//*[@id="altImages"]//li[@data-csa-c-media-type="IMAGE"]');
        if ($galleryItems !== false && $galleryItems->length > 0) {
            $images = [];
            foreach ($galleryItems as $item) {
                if (!$item instanceof DOMElement) continue;
                $url = $this->preferredAmazonGalleryUrl($xpath, $item);
                if ($url !== '') $images[] = $url;
            }
            return $images;
        }

        // Older rendered pages have no per-photo gallery list; preserve their existing metadata behavior.
        $images = [];
        foreach ($xpath->query('//img[@id="landingImage" or @id="imgBlkFront"]') ?: [] as $image) {
            if (!$image instanceof DOMElement) continue;
            $dynamic = json_decode($image->getAttribute('data-a-dynamic-image'), true);
            if (is_array($dynamic)) foreach (array_keys($dynamic) as $url) if (is_string($url)) $images[] = $url;
            $imageUrl = $image->getAttribute('data-old-hires') ?: $image->getAttribute('src');
            if ($imageUrl !== '') $images[] = $imageUrl;
        }
        return $images;
    }

    private function preferredAmazonGalleryUrl(DOMXPath $xpath, DOMElement $item): string
    {
        $direct = trim($item->getAttribute('data-old-hires'));
        if ($direct !== '') return $direct;

        foreach ($xpath->query('.//*[@data-old-hires]', $item) ?: [] as $node) {
            if (!$node instanceof DOMElement) continue;
            $direct = trim($node->getAttribute('data-old-hires'));
            if ($direct !== '') return $direct;
        }

        $dynamicNodes = [];
        if ($item->hasAttribute('data-a-dynamic-image')) $dynamicNodes[] = $item;
        foreach ($xpath->query('.//*[@data-a-dynamic-image]', $item) ?: [] as $node) {
            if ($node instanceof DOMElement) $dynamicNodes[] = $node;
        }
        foreach ($dynamicNodes as $node) {
            $url = $this->largestAmazonDynamicImageUrl($node->getAttribute('data-a-dynamic-image'));
            if ($url !== '') return $url;
        }

        foreach ($xpath->query('.//img[@data-src or @src]', $item) ?: [] as $node) {
            if (!$node instanceof DOMElement) continue;
            $url = trim($node->getAttribute('data-src') ?: $node->getAttribute('src'));
            if ($url !== '') return $url;
        }
        return '';
    }

    private function largestAmazonDynamicImageUrl(string $encodedImages): string
    {
        $images = json_decode($encodedImages, true);
        if (!is_array($images)) return '';

        $bestUrl = '';
        $bestArea = 0;
        foreach ($images as $url => $dimensions) {
            if (!is_string($url) || !is_array($dimensions)) continue;
            $width = $dimensions[0] ?? null;
            $height = $dimensions[1] ?? null;
            if ((!is_int($width) && !is_float($width)) || (!is_int($height) && !is_float($height))
                || $width <= 0 || $height <= 0 || $width > 10000 || $height > 10000) continue;
            $area = $width * $height;
            if ($area > $bestArea) {
                $bestArea = $area;
                $bestUrl = $url;
            }
        }
        return $bestUrl;
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
