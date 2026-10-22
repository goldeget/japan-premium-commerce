<?php

declare(strict_types=1);

$shopRoot = '/var/www/html';
$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require_once $shopRoot . '/config/config.inc.php';
require_once $shopRoot . '/modules/kuraneapostcode/kuraneapostcode.php';

use Kuranea\Postcode\Infrastructure\DatabasePostalAddressLookup;

final class KuraneaQaAddressField
{
    public array $errors = [];

    public function __construct(private $value) {}

    public function getValue() { return $this->value; }

    public function setValue($value): void { $this->value = $value; }

    public function addError(string $error): void { $this->errors[] = $error; }
}

$countryId = (int) Country::getByIso('JP');
$states = State::getStatesByIdCountry($countryId, true, 'iso_code', 'asc');
$stateIds = [];
foreach (is_array($states) ? $states : [] as $state) {
    if (preg_match('/^JP-([0-9]{2})$/D', (string) $state['iso_code'], $matches) === 1) {
        $stateIds[$matches[1]] = (int) $state['id_state'];
    }
}

$candidates = (new DatabasePostalAddressLookup())->lookupByPostcode('1000004', 100);
$candidate = null;
foreach ($candidates as $item) {
    if ($item->prefecture === '東京都' && $item->municipality === '千代田区' && str_contains($item->town, '大手町')) {
        $candidate = $item;
        break;
    }
}
if ($candidate === null) {
    throw new RuntimeException('The official Japan Post candidate 1000004 / Tokyo / Otemachi is unavailable.');
}
$native = $candidate->toNativeAddressFields($stateIds);
if ($native === null) {
    throw new RuntimeException('Tokyo does not map to a native PrestaShop state.');
}

$country = new Country($countryId);
$formatter = new class($country) {
    public function __construct(private object $country) {}
    public function getCountry(): object { return $this->country; }
};
$makeForm = static function (string $postcode, int $stateId, string $city, string $town, string $building = '') use ($formatter): object {
    $fields = [
        'postcode' => new KuraneaQaAddressField($postcode),
        'id_state' => new KuraneaQaAddressField($stateId),
        'city' => new KuraneaQaAddressField($city),
        'address1' => new KuraneaQaAddressField($town),
        'address2' => new KuraneaQaAddressField($building),
    ];

    return new class($formatter, $fields) {
        public function __construct(private object $formatter, private array $fields) {}
        public function getFormatter(): object { return $this->formatter; }
        public function getField(string $name): ?object { return $this->fields[$name] ?? null; }
    };
};

$module = new Kuraneapostcode();
Context::getContext()->language->iso_code = 'ja';
$editableTown = str_replace('（次のビルを除く）', '', $native['address1']);
$validForm = $makeForm('1000004', $native['id_state'], $native['city'], $editableTown . '1-2', 'KURANEA QA Bldg 101');
if ($module->hookActionValidateCustomerAddressForm(['form' => $validForm]) !== true) {
    throw new RuntimeException('A valid 1000004 address with a manually entered building was rejected.');
}

$mismatchedForm = $makeForm('100-0004', $native['id_state'], '中央区', '大手町1-2');
if ($module->hookActionValidateCustomerAddressForm(['form' => $mismatchedForm]) !== false) {
    throw new RuntimeException('A municipality that does not match official postcode data was accepted.');
}

$manualForm = $makeForm('9999999', $native['id_state'], '手入力の市区町村', '手入力の町域');
if ($module->hookActionValidateCustomerAddressForm(['form' => $manualForm]) !== true) {
    throw new RuntimeException('Manual entry failed when the official postcode lookup returned no rows.');
}

printf(
    "PASS: readonly live validation for 1000004, 100-0004 normalization, %s / %s, editable building, mismatch rejection, and no-result manual entry\n",
    $native['city'],
    $candidate->town
);
