<?php

declare(strict_types=1);

$shopRoot = '/var/www/html';
$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require_once $shopRoot . '/config/config.inc.php';
require_once $shopRoot . '/modules/kuraneapostcode/autoload.php';

use Kuranea\Postcode\Infrastructure\DatabasePostalAddressLookup;
use Kuranea\Postcode\Domain\PrefectureCatalog;

$countryId = (int) Country::getByIso('JP');
if ($countryId < 1) {
    throw new RuntimeException('Japan is not configured in the test shop.');
}

$states = State::getStatesByIdCountry($countryId, true, 'iso_code', 'asc');
$stateIds = [];
foreach (is_array($states) ? $states : [] as $state) {
    $isoCode = (string) $state['iso_code'];
    if (preg_match('/^JP-([0-9]{2})$/D', $isoCode, $matches) === 1) {
        $stateIds[$matches[1]] = (int) $state['id_state'];
    }
}

$candidates = (new DatabasePostalAddressLookup())->lookupByPostcode('1000004', 100);
$tokyoCandidate = null;
foreach ($candidates as $candidate) {
    if ($candidate->prefecture === '東京都'
        && $candidate->municipality === '千代田区'
        && str_contains($candidate->town, '大手町')) {
        $tokyoCandidate = $candidate;
        break;
    }
}
if ($tokyoCandidate === null) {
    throw new RuntimeException('The official 1000004 Tokyo/Otemachi address was not imported.');
}

$native = $tokyoCandidate->toNativeAddressFields($stateIds, 'KURANEA QA Bldg 101');
if ($native === null || empty($native['id_state'])) {
    throw new RuntimeException('The Tokyo prefecture does not map to an active PrestaShop state.');
}

$customer = new Customer();
$customer->firstname = 'KURANEA';
$customer->lastname = '郵便番号QA';
$customer->email = 'kuranea-postcode-' . bin2hex(random_bytes(6)) . '@example.invalid';
$customer->passwd = Tools::hash(bin2hex(random_bytes(24)));
$customer->id_lang = (int) Language::getIdByIso('ja', true);
$customer->id_default_group = (int) Configuration::get('PS_CUSTOMER_GROUP');
$customer->id_shop = 1;
$customer->secure_key = md5(bin2hex(random_bytes(16)));
if (!$customer->add()) {
    throw new RuntimeException('Could not create the isolated postcode QA customer.');
}

$address = new Address();
$address->id_customer = (int) $customer->id;
$address->id_country = $countryId;
$address->id_state = (int) $native['id_state'];
$address->alias = 'Postcode QA';
$address->firstname = $customer->firstname;
$address->lastname = $customer->lastname;
$address->address1 = (string) $native['address1'];
$address->address2 = (string) $native['address2'];
$address->postcode = (string) $native['postcode'];
$address->city = (string) $native['city'];
$address->phone = '0312345678';
$address->id_shop = 1;
if (!$address->add()) {
    throw new RuntimeException('Could not save the native PrestaShop test address.');
}

$saved = new Address((int) $address->id);
if (!Validate::isLoadedObject($saved)
    || $saved->postcode !== '100-0004'
    || (int) $saved->id_state !== (int) $native['id_state']
    || $saved->city !== '千代田区'
    || !str_contains($saved->address1, '大手町')
    || $saved->address2 !== 'KURANEA QA Bldg 101') {
    throw new RuntimeException('The saved native address lost a selected or manually edited field.');
}

printf(
    "PASS: saved native Japan address id=%d postcode=%s prefecture=%s city=%s town=%s building=%s\n",
    (int) $saved->id,
    $saved->postcode,
    PrefectureCatalog::name(substr((string) $tokyoCandidate->jisCode, 0, 2)),
    $saved->city,
    $saved->address1,
    $saved->address2
);
