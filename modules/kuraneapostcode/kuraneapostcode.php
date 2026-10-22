<?php

declare(strict_types=1);

if (!defined('_PS_VERSION_')) {
    exit;
}

require_once __DIR__ . '/autoload.php';

use Kuranea\Postcode\Domain\I18n;
use Kuranea\Postcode\Domain\PrefectureCatalog;
use Kuranea\Postcode\Domain\ZipCode;
use Kuranea\Postcode\Infrastructure\DatabasePostalAddressLookup;
use Kuranea\Postcode\Infrastructure\DatabaseSchema;

class Kuraneapostcode extends Module
{
    public function __construct()
    {
        $this->name = 'kuraneapostcode';
        $this->tab = 'front_office_features';
        $this->version = '1.0.0';
        $this->author = 'KURANEA';
        $this->need_instance = 0;
        $this->bootstrap = true;
        $this->ps_versions_compliancy = ['min' => '9.0.0', 'max' => '9.99.99'];
        $this->controllers = ['candidates'];

        parent::__construct();

        $this->displayName = 'KURANEA Japan Postcode Lookup';
        $this->description = 'Offline Japan Post postcode and address candidates for customer address forms.';
    }

    public function install()
    {
        return parent::install()
            && $this->installAddressTable()
            && $this->ensureJapaneseStates()
            && $this->registerHook([
                'additionalCustomerAddressFields',
                'actionFrontControllerSetMedia',
                'actionFrontControllerInitBefore',
                'actionValidateCustomerAddressForm',
                'actionSubmitCustomerAddressForm',
            ]);
    }

    public function uninstall()
    {
        // Postal rows and prefecture states can be referenced by saved orders.
        // Preserve them when the module is disabled or uninstalled.
        return parent::uninstall();
    }

    public function hookAdditionalCustomerAddressFields(array $params)
    {
        $field = new FormField();
        $field->setName('kuraneapostcode_search');
        $field->setType('text');
        $field->setRequired(false);
        $field->setMaxLength(128);
        $field->setLabel(I18n::text('search_label', $this->currentLocale()));
        $field->setAutocompleteAttribute('off');
        $field->setAttr(['data-kuranea-postcode-search' => 'true']);

        return [$field];
    }

    public function hookActionFrontControllerSetMedia(array $params)
    {
        if (!isset($this->context->controller)) {
            return;
        }

        $controller = $this->context->controller;
        $page = (string) ($controller->php_self ?? '');
        if (!in_array($page, ['address', 'order', 'checkout'], true)) {
            return;
        }

        $japanCountryId = (int) Country::getByIso('JP');
        Media::addJsDef([
            'kuraneaPostcodeConfig' => [
                // Follow the shop's configured scheme so local HTTP installations
                // do not get mixed-content-blocked lookup requests.
                'endpoint' => $this->context->link->getModuleLink($this->name, 'candidates'),
                'japanCountryId' => $japanCountryId,
                'strings' => I18n::all($this->currentLocale()),
            ],
        ]);
        $controller->registerJavascript(
            'module-kuraneapostcode-address-lookup',
            'modules/' . $this->name . '/views/js/address-lookup.js',
            ['position' => 'bottom', 'priority' => 150]
        );
    }

    public function hookActionValidateCustomerAddressForm(array $params)
    {
        $form = $params['form'] ?? null;
        if (!is_object($form) || !method_exists($form, 'getFormatter') || !method_exists($form, 'getField')) {
            return true;
        }

        $formatter = $form->getFormatter();
        $country = is_object($formatter) && method_exists($formatter, 'getCountry') ? $formatter->getCountry() : null;
        if (!is_object($country) || strtoupper((string) ($country->iso_code ?? '')) !== 'JP') {
            return true;
        }

        $postcodeField = $form->getField('postcode');
        if (!is_object($postcodeField) || !method_exists($postcodeField, 'getValue')) {
            return true;
        }

        $rawPostcode = $postcodeField->getValue();
        $postcode = is_scalar($rawPostcode) ? ZipCode::normalize((string) $rawPostcode) : null;
        if ($postcode === null) {
            $postcodeField->addError(I18n::text('invalid_postcode', $this->currentLocale()));

            return false;
        }

        $postcodeField->setValue($postcode);

        try {
            $candidates = (new DatabasePostalAddressLookup())->lookupByPostcode($postcode);
        } catch (Throwable $exception) {
            // Keep manual address entry available if the optional postal index
            // is temporarily unavailable.
            return true;
        }

        if ($candidates === []) {
            return true;
        }

        $stateField = $form->getField('id_state');
        $cityField = $form->getField('city');
        $addressField = $form->getField('address1');
        if (!is_object($stateField) || !method_exists($stateField, 'getValue')
            || !is_object($cityField) || !method_exists($cityField, 'getValue')
            || !is_object($addressField) || !method_exists($addressField, 'getValue')) {
            return true;
        }

        $stateId = (int) $stateField->getValue();
        $city = trim((string) $cityField->getValue());
        $address = trim((string) $addressField->getValue());
        $stateIds = [];
        foreach (State::getStatesByIdCountry((int) $country->id, false, 'iso_code', 'asc') as $state) {
            $isoCode = (string) ($state['iso_code'] ?? '');
            if (preg_match('/^JP-([0-9]{2})$/D', $isoCode, $matches) === 1) {
                $stateIds[$matches[1]] = (int) $state['id_state'];
            }
        }

        foreach ($candidates as $candidate) {
            $native = $candidate->toNativeAddressFields($stateIds);
            if ($native === null || $stateId !== $native['id_state'] || $city !== $native['city']) {
                continue;
            }

            // Japan Post uses an empty town for entries where the postal data
            // has no specific town-area subdivision. In those cases the
            // customer can still enter the street/building details manually.
            $townForValidation = str_replace('（次のビルを除く）', '', $native['address1']);
            if ($townForValidation === '' || $native['address1'] === '以下に掲載がない場合'
                || str_starts_with($address, $townForValidation)) {
                return true;
            }
        }

        $postcodeField->addError(I18n::text('address_mismatch', $this->currentLocale()));

        return false;
    }

    public function hookActionFrontControllerInitBefore(array $params)
    {
        if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST' || !isset($_POST['postcode'])) {
            return;
        }

        $rawCountryId = Tools::getValue('id_country');
        $countryId = is_scalar($rawCountryId) ? (int) $rawCountryId : 0;
        if ($countryId < 1 && isset($this->context->country->id)) {
            $countryId = (int) $this->context->country->id;
        }
        if ($countryId < 1 || strtoupper((string) (new Country($countryId))->iso_code) !== 'JP') {
            return;
        }

        $rawPostcode = Tools::getValue('postcode');
        if (!is_scalar($rawPostcode)) {
            return;
        }

        $normalized = ZipCode::normalize((string) $rawPostcode);
        if ($normalized !== null) {
            // Core validates JP's NNN-NNNN country format before the address
            // form validation hook runs. Normalize early so both accepted
            // user formats reach that native validation unchanged semantically.
            $_POST['postcode'] = $normalized;
            $_REQUEST['postcode'] = $normalized;
        }
    }

    public function hookActionSubmitCustomerAddressForm(array $params)
    {
        $address = $params['address'] ?? null;
        if (!$address instanceof Address || (int) $address->id_country !== (int) Country::getByIso('JP')) {
            return;
        }

        $postcode = ZipCode::normalize((string) $address->postcode);
        if ($postcode !== null) {
            $address->postcode = $postcode;
        }
    }

    private function installAddressTable(): bool
    {
        return (bool) Db::getInstance()->execute(DatabaseSchema::createAddressTableSql(_DB_PREFIX_));
    }

    private function ensureJapaneseStates(): bool
    {
        $countryId = (int) Country::getByIso('JP');
        if ($countryId < 1) {
            return false;
        }

        $country = new Country($countryId);
        if (!(bool) $country->contains_states) {
            $country->contains_states = 1;
            if (!$country->update()) {
                return false;
            }
        }

        $states = State::getStatesByIdCountry($countryId, false, 'iso_code', 'asc');
        if (!is_array($states)) {
            return false;
        }
        $existing = [];
        foreach ($states as $stateRow) {
            $existing[(string) $stateRow['iso_code']] = [
                'id_state' => (int) $stateRow['id_state'],
                'active' => (bool) $stateRow['active'],
            ];
        }

        $zoneId = (int) Country::getIdZone($countryId);
        foreach (PrefectureCatalog::all() as $code => $name) {
            $isoCode = PrefectureCatalog::isoCode($code);
            if ($isoCode === null || $zoneId < 1) {
                return false;
            }

            if (isset($existing[$isoCode])) {
                if (!$existing[$isoCode]['active']) {
                    $state = new State($existing[$isoCode]['id_state']);
                    $state->active = 1;
                    if (!$state->update()) {
                        return false;
                    }
                }
                continue;
            }

            $state = new State();
            $state->id_country = $countryId;
            $state->id_zone = $zoneId;
            $state->iso_code = $isoCode;
            $state->name = $name;
            $state->active = 1;
            if (!$state->add()) {
                return false;
            }
        }

        return true;
    }

    private function currentLocale(): string
    {
        return (string) ($this->context->language->iso_code ?? 'ja');
    }
}
