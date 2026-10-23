<?php

declare(strict_types=1);

/**
 * Apply PrestaShop's tax-included gross-price mode to all customer groups
 * associated with the storefront shop.
 */
function kuraneaConfigureTaxIncludedGroupPriceDisplay(int $languageId, int $shopId): void
{
    $groups = Group::getGroups($languageId, $shopId);
    if (!is_array($groups) || $groups === []) {
        throw new RuntimeException('Customer groups associated with the Japanese shop are required for price display configuration.');
    }

    $groupIds = [];
    foreach ($groups as $row) {
        $groupId = (int) ($row['id_group'] ?? 0);
        if ($groupId < 1) {
            throw new RuntimeException('A customer group associated with the Japanese shop has an invalid ID.');
        }
        $groupIds[$groupId] = true;
    }

    $requiredGroupIds = array_map(
        static fn (string $configurationKey): int => (int) Configuration::get($configurationKey),
        ['PS_UNIDENTIFIED_GROUP', 'PS_GUEST_GROUP', 'PS_CUSTOMER_GROUP']
    );
    foreach ($requiredGroupIds as $requiredGroupId) {
        if ($requiredGroupId < 1 || !isset($groupIds[$requiredGroupId])) {
            throw new RuntimeException('The Japanese shop must include its configured visitor, guest, and customer groups.');
        }
    }

    foreach (array_keys($groupIds) as $groupId) {
        $group = new Group((int) $groupId, null, $shopId);
        if (!Validate::isLoadedObject($group)) {
            throw new RuntimeException(sprintf('Could not load customer group %d for price display configuration.', $groupId));
        }
        if ((int) $group->price_display_method === Group::PRICE_DISPLAY_METHOD_TAX_INCL) {
            continue;
        }

        $group->price_display_method = Group::PRICE_DISPLAY_METHOD_TAX_INCL;
        if (!$group->update()) {
            throw new RuntimeException(sprintf('Could not set customer group %d to tax-included price display.', $groupId));
        }
    }

    $verifiedGroups = Group::getGroups($languageId, $shopId);
    if (!is_array($verifiedGroups) || count($verifiedGroups) !== count($groupIds)) {
        throw new RuntimeException('Could not re-read all storefront customer groups after price display configuration.');
    }
    foreach ($verifiedGroups as $row) {
        if ((int) ($row['price_display_method'] ?? -1) !== Group::PRICE_DISPLAY_METHOD_TAX_INCL) {
            throw new RuntimeException(sprintf(
                'Customer group %d does not display storefront prices with tax included.',
                (int) ($row['id_group'] ?? 0)
            ));
        }
    }
}

/**
 * Ensure the Japanese shop uses JPY and tax-included storefront display.
 * These settings are repaired on every bootstrap for fresh and legacy shops.
 * Other currencies are disabled until their exchange rates are configured.
 */
function kuraneaConfigureJapaneseCurrency(Context $context): Currency
{
    if (!Validate::isLoadedObject($context->shop)) {
        throw new RuntimeException('The KURANEA shop context is required to configure its currency.');
    }

    $shopId = (int) $context->shop->id;
    Shop::setContext(Shop::CONTEXT_SHOP, $shopId);
    $configuredKey = 'KURANEA_JPY_DEFAULT_CURRENCY_CONFIGURED';
    $japaneseLanguageId = (int) Language::getIdByIso('ja', true);
    if ($japaneseLanguageId < 1) {
        throw new RuntimeException('Japanese language data is required to configure customer group price display.');
    }
    kuraneaConfigureTaxIncludedGroupPriceDisplay($japaneseLanguageId, $shopId);

    if ((string) Configuration::get($configuredKey) === '2') {
        $defaultCurrency = new Currency((int) Configuration::get('PS_CURRENCY_DEFAULT'), null, $shopId);
        if (Validate::isLoadedObject($defaultCurrency)) {
            $context->currency = $defaultCurrency;

            return $defaultCurrency;
        }
    }

    $languages = Language::getLanguages(false);
    if (!$japaneseLanguageId || !$languages) {
        throw new RuntimeException('Japanese language data is required to configure JPY.');
    }

    $names = [];
    $symbols = [];
    $patterns = [];
    foreach ($languages as $language) {
        $languageId = (int) $language['id_lang'];
        $isoCode = strtolower((string) $language['iso_code']);
        $names[$languageId] = match ($isoCode) {
            'ja' => '日本円',
            'ko' => '일본 엔',
            default => 'Japanese yen',
        };
        $symbols[$languageId] = $isoCode === 'ja' ? '￥' : '¥';
        // An empty custom pattern lets PrestaShop format prices with CLDR.
        $patterns[$languageId] = '';
    }

    $currencyId = (int) Currency::getIdByIsoCode('JPY', $shopId, true, true);
    // Leave id_lang unset so ObjectModel::getFieldsLang() persists all
    // installed locales, not only the current Japanese context.
    $currency = new Currency($currencyId ?: null, null, $shopId);
    $currency->iso_code = 'JPY';
    $currency->numeric_iso_code = '392';
    $currency->precision = 0;
    $currency->conversion_rate = 1.0;
    $currency->deleted = false;
    $currency->active = true;
    $currency->unofficial = false;
    $currency->modified = false;
    $currency->setLocalizedNames($names);
    $currency->setLocalizedSymbols($symbols);
    $currency->setLocalizedPatterns($patterns);

    $saved = $currencyId ? $currency->update() : $currency->add();
    if (!$saved) {
        throw new RuntimeException('Could not create or update the JPY currency record.');
    }

    $currencyId = (int) $currency->id;
    if (!$currencyId || !Configuration::updateGlobalValue('PS_CURRENCY_DEFAULT', $currencyId)) {
        throw new RuntimeException('Could not set JPY as the KURANEA base currency.');
    }

    Currency::resetStaticCache();
    foreach (Currency::getCurrencies(true, false) as $otherCurrency) {
        if ($otherCurrency->iso_code === 'JPY' || !(bool) $otherCurrency->active || (bool) $otherCurrency->deleted) {
            continue;
        }

        $otherCurrency->active = false;
        if (!$otherCurrency->update()) {
            throw new RuntimeException(sprintf('Could not disable the unrated %s currency.', $otherCurrency->iso_code));
        }
    }

    if (!Configuration::updateGlobalValue($configuredKey, 2)) {
        throw new RuntimeException('Could not save the JPY bootstrap marker.');
    }

    Currency::resetStaticCache();
    $japaneseCurrency = new Currency($currencyId, null, $shopId);
    if (!Validate::isLoadedObject($japaneseCurrency)) {
        throw new RuntimeException('The newly configured JPY currency could not be reloaded.');
    }
    $context->currency = $japaneseCurrency;

    return $japaneseCurrency;
}
