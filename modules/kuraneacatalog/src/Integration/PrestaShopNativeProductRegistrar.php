<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Integration;

use RuntimeException;

/**
 * Explicit adapter to PrestaShop's native Product model. It creates inactive,
 * non-orderable TEST/DEMO records only; no adapter action runs at module load.
 */
final class PrestaShopNativeProductRegistrar implements NativeProductRegistrarInterface
{
    public function register(NativeProductRegistration $registration): int
    {
        if (!str_starts_with($registration->name, '[TEST/DEMO] ')
            || preg_match('/\ATEST-[A-Z0-9-]+\z/', $registration->reference) !== 1
            || $registration->active
            || $registration->visibility !== 'none'
            || $registration->availableForOrder
            || $registration->currency !== 'JPY'
            || $registration->priceJpy < 1
            || trim($registration->approvedBy) === ''
            || !str_contains($registration->provenance, 'KURANEA TEST/DEMO catalog import; not for sale.')
            || !str_contains($registration->provenance, 'Approved by: ' . $registration->approvedBy)
            || !str_contains($registration->provenance, 'Approved at: ' . $registration->approvedAt->format(DATE_ATOM))) {
            throw new RuntimeException('Catalog registration must be inactive, hidden, non-orderable JPY TEST/DEMO data.');
        }

        foreach (['Product', 'Context', 'Configuration', 'Currency', 'Language', 'Db'] as $class) {
            if (!class_exists($class)) {
                throw new RuntimeException('PrestaShop is not bootstrapped; refusing native catalog registration.');
            }
        }
        if (!method_exists('Product', 'getIdByReference')) {
            throw new RuntimeException('This PrestaShop Product model does not support idempotent reference lookup.');
        }

        $defaultCurrencyId = (int) \Configuration::get('PS_CURRENCY_DEFAULT');
        $defaultCurrency = new \Currency($defaultCurrencyId);
        if ((string) $defaultCurrency->iso_code !== 'JPY') {
            throw new RuntimeException('TEST/DEMO catalog registration requires the shop default currency to be JPY.');
        }

        $context = \Context::getContext();
        $languageId = (int) ($context->language->id ?? 0);
        $shopId = (int) ($context->shop->id ?? 0);
        $homeCategoryId = (int) \Configuration::get('PS_HOME_CATEGORY');
        if ($languageId < 1 || $shopId < 1 || $homeCategoryId < 1) {
            throw new RuntimeException('PrestaShop language, shop, and home category context are required.');
        }

        if (!method_exists('Db', 'getInstance')) {
            throw new RuntimeException('PrestaShop database connection does not support reference-level advisory locks.');
        }
        $database = \Db::getInstance();
        if (!is_object($database) || !method_exists($database, 'getValue')) {
            throw new RuntimeException('PrestaShop database connection does not support reference-level advisory locks.');
        }
        $lockName = $this->lockName($registration->reference);
        if ((int) $database->getValue("SELECT GET_LOCK('" . $lockName . "', 10)", false) !== 1) {
            throw new RuntimeException('Could not acquire the catalog TEST product reference lock.');
        }

        try {
            return $this->registerWhileLocked($registration, $languageId, $shopId, $homeCategoryId);
        } finally {
            if ((int) $database->getValue("SELECT RELEASE_LOCK('" . $lockName . "')", false) !== 1) {
                throw new RuntimeException('Could not release the catalog TEST product reference lock.');
            }
        }
    }

    private function registerWhileLocked(
        NativeProductRegistration $registration,
        int $languageId,
        int $shopId,
        int $homeCategoryId
    ): int {
        $existingProductId = (int) \Product::getIdByReference($registration->reference);
        if ($existingProductId > 0) {
            $existingProduct = new \Product($existingProductId);
            $localizedName = is_array($existingProduct->name ?? null)
                ? (string) ($existingProduct->name[$languageId] ?? '')
                : (string) ($existingProduct->name ?? '');
            if ((int) ($existingProduct->id ?? 0) !== $existingProductId
                || (string) ($existingProduct->reference ?? '') !== $registration->reference
                || !str_starts_with($localizedName, '[TEST/DEMO] ')
                || (bool) ($existingProduct->active ?? true)
                || (string) ($existingProduct->visibility ?? '') !== 'none'
                || (bool) ($existingProduct->available_for_order ?? true)) {
                throw new RuntimeException('A product already uses the TEST reference but is not a safe TEST/DEMO record.');
            }
            if (!$existingProduct->addToCategories([$homeCategoryId])) {
                throw new RuntimeException('PrestaShop could not complete the existing TEST/DEMO product category link.');
            }

            return $existingProductId;
        }

        $product = new \Product();
        $escapedName = htmlspecialchars($registration->name, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
        $escapedProvenance = htmlspecialchars($registration->provenance, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
        $slug = 'kuranea-' . strtolower(str_replace('-', '', $registration->reference));
        $product->name = [];
        $product->link_rewrite = [];
        $product->description_short = [];
        $product->description = [];
        foreach (\Language::getLanguages(false) as $language) {
            $productLanguageId = (int) ($language['id_lang'] ?? 0);
            if ($productLanguageId < 1) {
                continue;
            }
            $product->name[$productLanguageId] = $registration->name;
            $product->link_rewrite[$productLanguageId] = $slug;
            $product->description_short[$productLanguageId] = '<p><strong>' . $escapedName . '</strong></p><p>Internal TEST/DEMO review record. Not for sale.</p>';
            $product->description[$productLanguageId] = '<pre>' . $escapedProvenance . '</pre>';
        }
        if ($product->name === [] || !isset($product->name[$languageId])) {
            throw new RuntimeException('PrestaShop has no active language for catalog product registration.');
        }
        $product->reference = $registration->reference;
        $product->price = (float) $registration->priceJpy;
        $product->id_shop_default = $shopId;
        $product->id_category_default = $homeCategoryId;
        $product->id_tax_rules_group = 0;
        $product->minimal_quantity = 1;
        $product->active = 0;
        $product->visibility = 'none';
        $product->available_for_order = 0;
        $product->show_price = 0;

        if (!$product->add()) {
            throw new RuntimeException('PrestaShop could not create the inactive TEST/DEMO catalog product.');
        }

        $productId = (int) $product->id;
        if ($productId < 1 || !$product->addToCategories([$homeCategoryId])) {
            throw new RuntimeException('PrestaShop created an incomplete TEST/DEMO product record.');
        }

        return $productId;
    }

    private function lockName(string $reference): string
    {
        return 'kuranea_catalog_' . substr(hash('sha256', $reference), 0, 48);
    }
}
