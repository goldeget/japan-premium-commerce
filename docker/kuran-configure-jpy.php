<?php

declare(strict_types=1);

/**
 * Ensure the Japanese shop starts with JPY as its base currency exactly once.
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

    if ((string) Configuration::get($configuredKey) === '2') {
        $defaultCurrency = new Currency((int) Configuration::get('PS_CURRENCY_DEFAULT'), null, $shopId);
        if (Validate::isLoadedObject($defaultCurrency)) {
            $context->currency = $defaultCurrency;

            return $defaultCurrency;
        }
    }

    $languages = Language::getLanguages(false);
    $japaneseLanguageId = (int) Language::getIdByIso('ja', true);
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
