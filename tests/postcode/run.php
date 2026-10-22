<?php

declare(strict_types=1);

require_once __DIR__ . '/../../modules/kuraneapostcode/autoload.php';

function assertSameValue(mixed $expected, mixed $actual, string $message): void
{
    if ($expected !== $actual) {
        throw new RuntimeException(sprintf(
            "%s\nExpected: %s\nActual:   %s",
            $message,
            var_export($expected, true),
            var_export($actual, true)
        ));
    }
}

function assertTrueValue(bool $actual, string $message): void
{
    assertSameValue(true, $actual, $message);
}

assertTrueValue(
    class_exists(\Kuranea\Postcode\Domain\ZipCode::class),
    'The postcode module must expose its ZipCode domain service.'
);

assertSameValue(
    '100-0004',
    \Kuranea\Postcode\Domain\ZipCode::normalize('1000004'),
    'Seven digits should normalize to Japan Post NNN-NNNN format.'
);
assertSameValue(
    '100-0004',
    \Kuranea\Postcode\Domain\ZipCode::normalize('100-0004'),
    'The hyphenated postal format should remain valid.'
);
assertSameValue(
    '100-0004',
    \Kuranea\Postcode\Domain\ZipCode::normalize('１００－０００４'),
    'Full-width digits and a full-width hyphen should normalize.'
);
assertSameValue(
    '100-0004',
    \Kuranea\Postcode\Domain\ZipCode::normalize("\u{3000}１００‐０００４\u{3000}"),
    'Japanese full-width surrounding spaces and a Unicode hyphen should normalize.'
);
assertSameValue(null, \Kuranea\Postcode\Domain\ZipCode::normalize('100-004'), 'Incomplete postcodes should be rejected.');
assertSameValue(null, \Kuranea\Postcode\Domain\ZipCode::normalize('100-0004x'), 'Non-digit postcode characters should be rejected.');
assertSameValue(null, \Kuranea\Postcode\Domain\ZipCode::normalize('1-00-0004'), 'Multiple or misplaced separators should be rejected.');
assertSameValue('1000004', \Kuranea\Postcode\Domain\ZipCode::digits('100-0004'), 'The canonical postcode digits should be available for lookups.');

assertTrueValue(
    class_exists(\Kuranea\Postcode\Domain\KenAllCsvParser::class),
    'The module must parse local Japan Post KEN_ALL CSV rows.'
);
assertTrueValue(
    class_exists(\Kuranea\Postcode\Domain\PostalAddressIndex::class),
    'The module must provide local postcode and Japanese address matching.'
);
assertTrueValue(
    class_exists(\Kuranea\Postcode\Domain\CandidateSearchService::class),
    'The public candidate endpoint should use a validated search service.'
);
assertTrueValue(
    class_exists(\Kuranea\Postcode\Domain\I18n::class),
    'The address search widget should provide Japanese, English, and Korean strings.'
);
assertTrueValue(
    class_exists(\Kuranea\Postcode\Infrastructure\DatabaseSchema::class),
    'The module should expose an idempotent module-owned table schema.'
);
assertSameValue(47, count(\Kuranea\Postcode\Domain\PrefectureCatalog::all()), 'The module should define all 47 Japanese prefectures.');
assertSameValue('東京都', \Kuranea\Postcode\Domain\PrefectureCatalog::name('13'), 'JIS prefecture code 13 should resolve to Tokyo.');
assertSameValue('JP-47', \Kuranea\Postcode\Domain\PrefectureCatalog::isoCode('47'), 'The prefecture catalog should provide stable PrestaShop state ISO codes.');

if (!defined('_DB_PREFIX_')) {
    define('_DB_PREFIX_', 'ps_');
}
if (!function_exists('pSQL')) {
    function pSQL(string $value): string
    {
        return str_replace("'", "\\'", $value);
    }
}

final class FakePostalDatabase
{
    /** @var list<string> */
    public array $queries = [];

    public function executeS(string $query): array
    {
        $this->queries[] = $query;

        return [[
            'postcode' => '999-9999',
            'jis_code' => '13101',
            'prefecture' => '東京都',
            'municipality' => '千代田区',
            'town' => 'テスト町',
        ]];
    }
}

$fakeDatabase = new FakePostalDatabase();
$databaseLookup = new \Kuranea\Postcode\Infrastructure\DatabasePostalAddressLookup($fakeDatabase);
assertSameValue(1, count($databaseLookup->lookupByPostcode('９９９９９９９')), 'The DB lookup adapter should return normalized candidates.');
assertTrueValue(str_starts_with($fakeDatabase->queries[0], 'SELECT '), 'The public candidate lookup should issue a read-only SELECT.');
assertTrueValue(str_contains($fakeDatabase->queries[0], '`ps_kuraneapostcode_address`'), 'The query should use the module-owned postal table.');
assertTrueValue(str_contains($fakeDatabase->queries[0], "`postcode` = '999-9999'"), 'The query should filter by canonical postcode.');
$databaseLookup->searchJapaneseAddress('千代田区', 7);
assertTrueValue(str_starts_with($fakeDatabase->queries[1], 'SELECT '), 'Japanese partial-address matching should remain read-only.');
assertTrueValue(str_contains($fakeDatabase->queries[1], 'LIMIT 7'), 'The DB lookup adapter should enforce the caller result limit.');

$fixture = __DIR__ . '/fixtures/ken_all_synthetic.csv';
$parser = new \Kuranea\Postcode\Domain\KenAllCsvParser();
$importer = new \Kuranea\Postcode\Domain\KenAllCsvImporter($parser);
$imported = [];
$summary = $importer->import($fixture, static function (\Kuranea\Postcode\Domain\PostalAddress $address) use (&$imported): void {
    $imported[] = $address;
});

assertSameValue(2, $summary->imported, 'The synthetic KEN_ALL fixture should import both duplicate-postcode rows.');
assertSameValue(1, $summary->skipped, 'Malformed synthetic rows should be counted and skipped.');
$index = new \Kuranea\Postcode\Domain\PostalAddressIndex($imported);
$searchService = new \Kuranea\Postcode\Domain\CandidateSearchService($index);
$deduplicatedIndex = new \Kuranea\Postcode\Domain\PostalAddressIndex([$imported[0], $imported[0], $imported[1]]);
assertSameValue(2, count($deduplicatedIndex->lookupByPostcode('999-9999')), 'Exact repeated CSV rows should not produce duplicate choices.');
$postcodeCandidates = $index->lookupByPostcode('９９９－９９９９');
assertSameValue(2, count($postcodeCandidates), 'Duplicate postcodes should return every selectable address candidate.');
assertSameValue(2, count($searchService->search('９９９９９９９')), 'The candidate API service should normalize full-width postcodes.');
assertSameValue(1, count($searchService->search('ベータ町')), 'The candidate API service should support Japanese address text.');
assertSameValue([], $searchService->search('都'), 'One-character address queries should not scan a large postal table.');
assertSameValue([], $searchService->search(str_repeat('東京都', 50)), 'Overlong public API queries should be rejected.');
assertSameValue(1, count($searchService->search('千代田区', 1)), 'Candidate API result limits should be enforced.');
assertSameValue('東京都', $postcodeCandidates[0]->prefecture, 'KEN_ALL prefectures should be parsed as Japanese text.');
assertSameValue('千代田区', $postcodeCandidates[0]->municipality, 'KEN_ALL municipalities should map to city.');
assertSameValue('テスト町', $postcodeCandidates[0]->town, 'KEN_ALL town areas should be parsed.');

$partialCandidates = $index->search('千代田区ベータ', 10);
assertSameValue(1, count($partialCandidates), 'Japanese partial address queries should find matching towns.');
assertSameValue('ベータ町', $partialCandidates[0]->town, 'Partial address results should retain the selected town.');
assertSameValue(
    $postcodeCandidates[1]->candidateId,
    $index->select($postcodeCandidates[1]->candidateId)?->candidateId,
    'A candidate ID should select one address from a duplicate-postcode group.'
);
assertSameValue(null, $index->select('unknown-candidate'), 'Unknown candidate IDs should not resolve to an address.');
assertSameValue([], $index->lookupByPostcode('000-000'), 'Invalid postcode lookup should return no candidates.');
assertSameValue([], $index->search('千代田区', 0), 'A zero result limit should return no candidates.');

$nativeFields = $postcodeCandidates[0]->toNativeAddressFields(['13' => 43], 'サンプルビル 101');
assertSameValue('999-9999', $nativeFields['postcode'], 'Native address fields should use the canonical postcode.');
assertSameValue(43, $nativeFields['id_state'], 'The prefecture should map to the installed PrestaShop state ID.');
assertSameValue('千代田区', $nativeFields['city'], 'PrestaShop city should contain the municipality.');
assertSameValue('テスト町', $nativeFields['address1'], 'PrestaShop address1 should contain the town area.');
assertSameValue('サンプルビル 101', $nativeFields['address2'], 'The customer-entered building should remain editable and preserved.');
assertSameValue(null, $postcodeCandidates[0]->toNativeAddressFields([], '手入力建物'), 'Missing prefecture state mapping should keep manual entry available.');

assertSameValue('郵便番号・住所検索', \Kuranea\Postcode\Domain\I18n::text('search_label', 'ja-JP'), 'The widget should have Japanese text.');
assertSameValue('Postcode or address search', \Kuranea\Postcode\Domain\I18n::text('search_label', 'en'), 'The widget should have English text.');
assertSameValue('우편번호·주소 검색', \Kuranea\Postcode\Domain\I18n::text('search_label', 'ko-KR'), 'The widget should have Korean text.');
assertTrueValue(\Kuranea\Postcode\Domain\I18n::text('invalid_postcode', 'ko') !== 'invalid_postcode', 'Postcode validation errors should be translated.');
$schemaSql = \Kuranea\Postcode\Infrastructure\DatabaseSchema::createAddressTableSql('ps_');
assertTrueValue(str_contains($schemaSql, 'CREATE TABLE IF NOT EXISTS `ps_kuraneapostcode_address`'), 'The module address table should install idempotently.');
assertTrueValue(str_contains($schemaSql, '`candidate_id` CHAR(64) NOT NULL'), 'The table should use deterministic address candidate IDs.');
assertTrueValue(!str_contains(strtoupper($schemaSql), 'TRUNCATE'), 'The install schema must never initialize or clear existing data.');

$cp932Imported = [];
$cp932Summary = $importer->import(__DIR__ . '/fixtures/ken_all_synthetic_cp932.csv', static function (\Kuranea\Postcode\Domain\PostalAddress $address) use (&$cp932Imported): void {
    $cp932Imported[] = $address;
});
assertSameValue(2, $cp932Summary->imported, 'The local importer should decode synthetic CP932 KEN_ALL rows.');
assertSameValue('東京都', $cp932Imported[0]->prefecture, 'CP932 prefecture names should decode into UTF-8.');

if (!class_exists('Module')) {
    class Module
    {
        public $context;
        public array $registeredHooks = [];

        public function __construct()
        {
            $this->context = (object) ['language' => (object) ['iso_code' => 'ja'], 'country' => (object) ['id' => 392]];
        }

        public function install()
        {
            return true;
        }

        public function uninstall()
        {
            return true;
        }

        public function registerHook($hooks): bool
        {
            $this->registeredHooks = array_merge($this->registeredHooks, (array) $hooks);
            return true;
        }
    }
}
if (!class_exists('FormField')) {
    class FormField
    {
        public string $name = '';
        public string $type = '';
        public bool $required = false;
        public int $maxLength = 0;
        public string $label = '';
        public string $autocomplete = '';
        public array $attr = [];
        public $value = null;
        public array $errors = [];

        public function setName(string $value): self { $this->name = $value; return $this; }
        public function setType(string $value): self { $this->type = $value; return $this; }
        public function setRequired(bool $value): self { $this->required = $value; return $this; }
        public function setMaxLength(int $value): self { $this->maxLength = $value; return $this; }
        public function setLabel(string $value): self { $this->label = $value; return $this; }
        public function setAutocompleteAttribute(string $value): self { $this->autocomplete = $value; return $this; }
        public function setAttr(array $value): self { $this->attr = $value; return $this; }
        public function getValue() { return $this->value; }
        public function setValue($value): self { $this->value = $value; return $this; }
        public function addError(string $value): void { $this->errors[] = $value; }
    }
}
if (!class_exists('Address')) {
    class Address
    {
        public int $id_country = 392;
        public string $postcode = '';
    }
}
if (!class_exists('Country')) {
    class Country
    {
        public static bool $japanContainsStates = false;
        public string $iso_code;
        public int $id;
        public int $contains_states = 0;

        public function __construct(int $id)
        {
            $this->id = $id;
            $this->iso_code = $id === 392 ? 'JP' : 'US';
            $this->contains_states = $id === 392 && self::$japanContainsStates ? 1 : 0;
        }

        public static function getByIso(string $isoCode): int|false
        {
            return strtoupper($isoCode) === 'JP' ? 392 : false;
        }

        public static function getIdZone(int $idCountry): int
        {
            return $idCountry === 392 ? 5 : 0;
        }

        public function update(): bool
        {
            self::$japanContainsStates = (bool) $this->contains_states;
            return true;
        }
    }
}
if (!class_exists('State')) {
    class State
    {
        public static array $rows = [];
        private static int $nextId = 1;
        public int $id_state = 0;
        public int $id_country = 0;
        public int $id_zone = 0;
        public string $iso_code = '';
        public string $name = '';
        public int $active = 0;

        public function __construct(int $id = 0)
        {
            if ($id > 0) {
                foreach (self::$rows as $row) {
                    if ($row['id_state'] === $id) {
                        $this->id_state = $id;
                        $this->id_country = $row['id_country'];
                        $this->id_zone = $row['id_zone'];
                        $this->iso_code = $row['iso_code'];
                        $this->name = $row['name'];
                        $this->active = $row['active'];
                    }
                }
            }
        }

        public static function getStatesByIdCountry(int $countryId, bool $active = false, ?string $orderBy = null, string $sort = 'ASC'): array
        {
            return array_values(array_filter(self::$rows, static fn (array $row): bool =>
                $row['id_country'] === $countryId && (!$active || $row['active'] === 1)
            ));
        }

        public function add(): bool
        {
            $this->id_state = self::$nextId++;
            self::$rows[] = $this->toRow();
            return true;
        }

        public function update(): bool
        {
            foreach (self::$rows as &$row) {
                if ($row['id_state'] === $this->id_state) {
                    $row = $this->toRow();
                    return true;
                }
            }
            unset($row);
            return false;
        }

        private function toRow(): array
        {
            return [
                'id_state' => $this->id_state,
                'id_country' => $this->id_country,
                'id_zone' => $this->id_zone,
                'iso_code' => $this->iso_code,
                'name' => $this->name,
                'active' => $this->active,
            ];
        }
    }
}
if (!class_exists('Db')) {
    class Db
    {
        public static array $queries = [];
        public static array $resultRows = [[
            'postcode' => '999-9999',
            'jis_code' => '13101',
            'prefecture' => '東京都',
            'municipality' => '千代田区',
            'town' => 'テスト町',
        ]];
        private static ?self $instance = null;

        public static function getInstance($slave = false): self
        {
            return self::$instance ??= new self();
        }

        public function execute(string $query): bool
        {
            self::$queries[] = $query;
            return true;
        }

        public function executeS(string $query): array
        {
            self::$queries[] = $query;
            return self::$resultRows;
        }
    }
}
if (!class_exists('Tools')) {
    class Tools
    {
        public static function getValue(string $key, $default = false)
        {
            return $_POST[$key] ?? $_GET[$key] ?? $default;
        }
    }
}

if (!defined('_PS_VERSION_')) {
    define('_PS_VERSION_', '9.2.0');
}
require_once __DIR__ . '/../../modules/kuraneapostcode/kuraneapostcode.php';
$module = new Kuraneapostcode();
$installModule = new Kuraneapostcode();
assertSameValue(true, $installModule->install(), 'Module installation should create its own table and register hooks.');
assertSameValue(47, count(State::$rows), 'Installation should seed all 47 Japan prefecture states.');
assertSameValue(true, Country::$japanContainsStates, 'Installation should enable the native Japan state selector.');
assertTrueValue(in_array('actionFrontControllerInitBefore', $installModule->registeredHooks, true), 'Installation should register early postcode normalization.');
assertTrueValue(str_contains(Db::$queries[0], 'CREATE TABLE IF NOT EXISTS `ps_kuraneapostcode_address`'), 'Installation should create the idempotent module table.');
assertSameValue(true, $installModule->install(), 'Repeated installation should be idempotent.');
assertSameValue(47, count(State::$rows), 'Repeated installation should not duplicate prefecture states.');
$module->context->language->iso_code = 'ko-KR';
$widgetFields = $module->hookAdditionalCustomerAddressFields([]);
assertSameValue(1, count($widgetFields), 'The customer address hook should add exactly one optional search field.');
assertSameValue('kuraneapostcode_search', $widgetFields[0]->name, 'The search field name should be module-scoped.');
assertSameValue(false, $widgetFields[0]->required, 'Address lookup must stay optional for manual entry.');
assertSameValue('우편번호·주소 검색', $widgetFields[0]->label, 'The customer address hook should select the Korean label.');

$_SERVER['REQUEST_METHOD'] = 'POST';
$_POST = ['id_country' => 392, 'postcode' => '１０００００４'];
$_REQUEST = $_POST;
$module->hookActionFrontControllerInitBefore([]);
assertSameValue('100-0004', $_POST['postcode'], 'The early front hook should normalize both accepted formats before native validation.');

$testCountry = new Country(392);
$testAddressFormatter = new class($testCountry) {
    public function __construct(private object $country) {}
    public function getCountry(): object { return $this->country; }
};
$testPostcodeField = new FormField();
$testPostcodeField->setValue('１０００００４');
Db::$resultRows = [];
$testAddressFields = [
    'postcode' => $testPostcodeField,
    'id_state' => (new FormField())->setValue(0),
    'city' => (new FormField())->setValue(''),
    'address1' => (new FormField())->setValue(''),
    'address2' => (new FormField())->setValue(''),
];
$testAddressForm = new class($testAddressFormatter, $testAddressFields) {
    public function __construct(private object $formatter, private array $fields) {}
    public function getFormatter(): object { return $this->formatter; }
    public function getField(string $name): ?object { return $this->fields[$name] ?? null; }
};
assertSameValue(true, $module->hookActionValidateCustomerAddressForm(['form' => $testAddressForm]), 'Japan postcode hook validation should accept and normalize full-width input.');
assertSameValue('100-0004', $testPostcodeField->value, 'Address validation should canonicalize postcode before persistence.');
$testPostcodeField->setValue('100-0004x');
assertSameValue(false, $module->hookActionValidateCustomerAddressForm(['form' => $testAddressForm]), 'Invalid Japan postcode should be rejected by the module validation hook.');
assertTrueValue(count($testPostcodeField->errors) === 1, 'Invalid postcode should produce a localized field error.');

$tokyoStateId = 0;
foreach (State::$rows as $stateRow) {
    if ($stateRow['iso_code'] === 'JP-13') {
        $tokyoStateId = $stateRow['id_state'];
        break;
    }
}
assertTrueValue($tokyoStateId > 0, 'The address validation fixture should resolve Tokyo to a native state ID.');
Db::$resultRows = [
    [
        'postcode' => '100-0004',
        'jis_code' => '13101',
        'prefecture' => '東京都',
        'municipality' => '千代田区',
        'town' => '大手町（次のビルを除く）',
    ],
    [
        'postcode' => '100-0004',
        'jis_code' => '13101',
        'prefecture' => '東京都',
        'municipality' => '千代田区',
        'town' => '丸の内',
    ],
];
$makeJapanAddressForm = static function (int $stateId, string $city, string $town, string $building = '') use ($testAddressFormatter): object {
    $fields = [
        'postcode' => (new FormField())->setValue('100-0004'),
        'id_state' => (new FormField())->setValue($stateId),
        'city' => (new FormField())->setValue($city),
        'address1' => (new FormField())->setValue($town),
        'address2' => (new FormField())->setValue($building),
    ];

    return new class($testAddressFormatter, $fields) {
        public function __construct(private object $formatter, private array $fields) {}
        public function getFormatter(): object { return $this->formatter; }
        public function getField(string $name): ?object { return $this->fields[$name] ?? null; }
    };
};
assertSameValue(
    true,
    $module->hookActionValidateCustomerAddressForm(['form' => $makeJapanAddressForm($tokyoStateId, '千代田区', '大手町1-2', '大手町タワー101号')]),
    'An official postcode candidate with the Japan Post building qualifier removed from town text and editable building should pass.'
);
assertSameValue(
    true,
    $module->hookActionValidateCustomerAddressForm(['form' => $makeJapanAddressForm($tokyoStateId, '千代田区', '丸の内1-2')]),
    'A second town-area candidate for the same postcode should pass when selected.'
);
$mismatchedPrefecture = $makeJapanAddressForm($tokyoStateId + 1, '千代田区', '大手町1-2');
assertSameValue(false, $module->hookActionValidateCustomerAddressForm(['form' => $mismatchedPrefecture]), 'A mismatched prefecture should be rejected when official postcode candidates exist.');
assertSameValue('우편번호에 해당하는 도도부현·시구정촌·정역을 확인해 주세요.', $mismatchedPrefecture->getField('postcode')->errors[0], 'Address mismatch errors should be localized in the active store language.');
assertSameValue(false, $module->hookActionValidateCustomerAddressForm(['form' => $makeJapanAddressForm($tokyoStateId, '中央区', '大手町1-2')]), 'A mismatched municipality should be rejected.');
assertSameValue(false, $module->hookActionValidateCustomerAddressForm(['form' => $makeJapanAddressForm($tokyoStateId, '千代田区', '神田1-2')]), 'A mismatched town area should be rejected.');
Db::$resultRows = [];
assertSameValue(
    true,
    $module->hookActionValidateCustomerAddressForm(['form' => $makeJapanAddressForm($tokyoStateId, '手入力の市区町村', '手入力の町域')]),
    'Manual entry should remain available when the official postcode index has no candidate rows.'
);

$savedAddress = new Address();
$savedAddress->postcode = '1000004';
$module->hookActionSubmitCustomerAddressForm(['address' => $savedAddress]);
assertSameValue('100-0004', $savedAddress->postcode, 'The native customer address hook should persist canonical postcode formatting.');

$controllerPipes = [];
$controllerProcess = proc_open(
    [PHP_BINARY, __DIR__ . '/run_candidates_endpoint.php'],
    [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']],
    $controllerPipes
);
if (!is_resource($controllerProcess)) {
    throw new RuntimeException('Could not start the isolated candidate endpoint test process.');
}
fclose($controllerPipes[0]);
$controllerOutput = stream_get_contents($controllerPipes[1]);
$controllerError = stream_get_contents($controllerPipes[2]);
fclose($controllerPipes[1]);
fclose($controllerPipes[2]);
$controllerExitCode = proc_close($controllerProcess);
assertSameValue(0, $controllerExitCode, 'The candidate endpoint test process should complete successfully: ' . $controllerError);
$apiResponse = json_decode(trim($controllerOutput), true, 512, JSON_THROW_ON_ERROR);
assertSameValue(true, $apiResponse['manual_entry_available'], 'The public candidate endpoint should always preserve manual entry.');
assertSameValue(1, count($apiResponse['candidates']), 'The public candidate endpoint should return matching candidates.');
assertSameValue('東京都', $apiResponse['candidates'][0]['prefecture'], 'The public API should return the prefecture candidate.');
assertTrueValue(is_int($apiResponse['candidates'][0]['state_id']), 'The public API should resolve the candidate to the native state ID.');

echo "PASS: postcode normalization, KEN_ALL import, candidate endpoint lookup, address form validation/persistence hooks, localization, and native field mapping\n";
