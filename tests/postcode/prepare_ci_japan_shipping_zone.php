<?php

declare(strict_types=1);

$runId = trim((string) getenv('GITHUB_RUN_ID'));
$runAttempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
$projectName = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$expectedProjectName = 'kuranea-ci-' . $runId . '-' . $runAttempt;

if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $runAttempt) !== 1
    || $projectName !== $expectedProjectName
) {
    fwrite(STDERR, "BLOCKED: Japan carrier-zone preparation requires its matching disposable GitHub Actions checkout.\n");
    exit(77);
}

$stage = 'PrestaShop bootstrap';
set_exception_handler(static function (Throwable $exception) use (&$stage): void {
    $message = preg_replace('/[\r\n]+/', ' ', $exception->getMessage()) ?? 'Unknown error';
    fwrite(STDERR, sprintf(
        'ORDENOWA_CI_JAPAN_ZONE_STAGE=%s; exception=%s; message=%s%s',
        $stage,
        get_class($exception),
        substr($message, 0, 800),
        PHP_EOL
    ));
    exit(1);
});

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SERVER_PORT'] = (string) (parse_url('http://' . $_SERVER['HTTP_HOST'], PHP_URL_PORT) ?: 80);
require_once '/var/www/html/config/config.inc.php';
require_once '/var/www/html/modules/kuraneapostcode/autoload.php';

$dbServer = defined('_DB_SERVER_') ? (string) _DB_SERVER_ : '';
$dbServerMatches = in_array($dbServer, ['mariadb', 'mariadb:3306'], true)
    && getenv('DB_SERVER') === 'mariadb'
    && getenv('DB_PORT') === '3306';
$dbNameMatches = defined('_DB_NAME_') && (string) _DB_NAME_ === 'prestashop';
$activeDatabaseMatches = $dbNameMatches
    && (string) Db::getInstance()->getValue('SELECT DATABASE()') === (string) _DB_NAME_;
if (!$dbServerMatches || !$dbNameMatches || !$activeDatabaseMatches) {
    throw new RuntimeException(sprintf(
        'The connected shop database failed its isolation guard: server_match=%s; configured_name_match=%s; active_connection_match=%s.',
        $dbServerMatches ? 'yes' : 'no',
        $dbNameMatches ? 'yes' : 'no',
        $activeDatabaseMatches ? 'yes' : 'no'
    ));
}

$stage = 'load active Japan country';
$japanId = (int) Country::getByIso('JP');
$japan = $japanId > 0 ? new Country($japanId) : false;
if (!$japan instanceof Country || !Validate::isLoadedObject($japan) || !(bool) $japan->active) {
    throw new RuntimeException('The active Japan country is missing from the isolated CI shop.');
}

$stage = 'create run-scoped Japan shipping zone';
$zoneName = sprintf('ORDENOWA CI Japan %s-%s', $runId, $runAttempt);
$zoneId = (int) Db::getInstance()->getValue(
    'SELECT `id_zone` FROM `' . _DB_PREFIX_ . 'zone` WHERE `name` = "' . pSQL($zoneName) . '" LIMIT 1'
);
$zone = $zoneId > 0 ? new Zone($zoneId) : new Zone();
$zone->name = $zoneName;
$zone->active = 1;
$saved = $zoneId > 0 ? $zone->update() : $zone->add();
if (!$saved || (int) $zone->id < 1) {
    throw new RuntimeException('Could not create the run-scoped Japan-only carrier zone.');
}

$stage = 'assign Japan to the run-scoped zone';
if ((int) $japan->id_zone !== (int) $zone->id) {
    $japan->id_zone = (int) $zone->id;
    if (!$japan->update()) {
        throw new RuntimeException('Could not assign Japan to the run-scoped carrier zone.');
    }
}

$stage = 'prepare all Japanese prefectures in the isolated shop';
$expectedStateCodes = [];
foreach (array_keys(\Kuranea\Postcode\Domain\PrefectureCatalog::all()) as $prefectureCode) {
    $stateIsoCode = \Kuranea\Postcode\Domain\PrefectureCatalog::isoCode($prefectureCode);
    if ($stateIsoCode === null) {
        throw new RuntimeException('The postcode module returned an invalid prefecture ISO code.');
    }
    $expectedStateCodes[] = $stateIsoCode;
}
sort($expectedStateCodes, SORT_STRING);
$expectedStateCodeSet = array_fill_keys($expectedStateCodes, true);
$existingStateRows = State::getStatesByIdCountry((int) $japan->id, false, 'iso_code', 'asc');
if (!is_array($existingStateRows)) {
    throw new RuntimeException('Could not read existing Japanese prefecture rows from the isolated shop.');
}
$existingStateIdsByIso = [];
$existingDuplicateStateCodes = [];
foreach ($existingStateRows as $existingStateRow) {
    $existingIsoCode = (string) ($existingStateRow['iso_code'] ?? '');
    if (!isset($expectedStateCodeSet[$existingIsoCode])) {
        continue;
    }
    if (isset($existingStateIdsByIso[$existingIsoCode])) {
        $existingDuplicateStateCodes[] = $existingIsoCode;
        continue;
    }
    $existingStateIdsByIso[$existingIsoCode] = (int) $existingStateRow['id_state'];
}
if ($existingDuplicateStateCodes !== []) {
    $existingDuplicateStateCodes = array_values(array_unique($existingDuplicateStateCodes));
    sort($existingDuplicateStateCodes, SORT_STRING);
    throw new RuntimeException(
        'The isolated shop already has duplicate supported prefecture rows: '
        . implode(',', $existingDuplicateStateCodes)
    );
}

foreach (\Kuranea\Postcode\Domain\PrefectureCatalog::all() as $prefectureCode => $prefectureName) {
    $stateIsoCode = \Kuranea\Postcode\Domain\PrefectureCatalog::isoCode($prefectureCode);
    if ($stateIsoCode === null) {
        throw new RuntimeException('The postcode module returned an invalid prefecture ISO code.');
    }

    $stateId = (int) ($existingStateIdsByIso[$stateIsoCode] ?? 0);
    $state = $stateId > 0 ? new State($stateId) : new State();
    $state->id_country = (int) $japan->id;
    $state->id_zone = (int) $zone->id;
    $state->iso_code = $stateIsoCode;
    $state->active = 1;
    $state->name = (string) $prefectureName;
    $saved = $stateId > 0 ? $state->update() : $state->add();
    if (!$saved) {
        throw new RuntimeException('Could not prepare every Japanese prefecture in the isolated carrier zone.');
    }
    if ($stateId < 1) {
        $existingStateIdsByIso[$stateIsoCode] = (int) $state->id;
    }
}

$stage = 'verify Japan-only zone membership';
$countryCodes = Db::getInstance()->executeS(
    'SELECT `iso_code` FROM `' . _DB_PREFIX_ . 'country`'
    . ' WHERE `id_zone` = ' . (int) $zone->id
    . ' ORDER BY `iso_code`'
);
$countryCodes = array_values(array_map(
    static fn (array $row): string => (string) $row['iso_code'],
    is_array($countryCodes) ? $countryCodes : []
));
if ($countryCodes !== ['JP']) {
    throw new RuntimeException(
        'The free-carrier zone must serve Japan alone; found: ' . implode(',', $countryCodes)
    );
}
$stage = 'verify all Japanese prefectures use the run-scoped zone';
$stateRows = Db::getInstance()->executeS(
    'SELECT `iso_code`, `id_zone`, `active` FROM `' . _DB_PREFIX_ . 'state`'
    . ' WHERE `id_country` = ' . (int) $japan->id
    . ' ORDER BY `iso_code`'
);
$allStateRows = is_array($stateRows) ? $stateRows : [];
$supportedStateRows = array_values(array_filter(
    $allStateRows,
    static fn (array $row): bool => isset($expectedStateCodeSet[(string) $row['iso_code']])
));
$stateCodes = array_values(array_map(
    static fn (array $row): string => (string) $row['iso_code'],
    $supportedStateRows
));
$stateCodeCounts = array_count_values($stateCodes);
$duplicateStateCodes = array_keys(array_filter(
    $stateCodeCounts,
    static fn (int $count): bool => $count > 1
));
$missingStateCodes = array_values(array_diff($expectedStateCodes, array_keys($stateCodeCounts)));
$statesOutsideZone = count(array_filter(
    $supportedStateRows,
    static fn (array $row): bool => (int) $row['id_zone'] !== (int) $zone->id
));
$unsupportedStatesUsingFreeShippingZone = count(array_filter(
    $allStateRows,
    static fn (array $row): bool => !isset($expectedStateCodeSet[(string) $row['iso_code']])
        && ((int) $row['id_zone'] === (int) $zone->id
            || ((int) $row['active'] === 1 && (int) $row['id_zone'] === 0))
));
$activeStateCount = count(array_filter(
    $supportedStateRows,
    static fn (array $row): bool => (int) $row['active'] === 1
));
$stateCount = count($supportedStateRows);
if ($missingStateCodes !== [] || $duplicateStateCodes !== []) {
    throw new RuntimeException(
        'Supported Japan prefecture rows are missing or duplicated: missing '
        . implode(',', $missingStateCodes) . '; duplicated ' . implode(',', $duplicateStateCodes)
    );
}
if ($statesOutsideZone !== 0) {
    throw new RuntimeException('One or more Japanese prefectures are outside the run-scoped carrier zone.');
}
if ($unsupportedStatesUsingFreeShippingZone !== 0) {
    throw new RuntimeException(
        'A non-catalog Japanese state can use the run-scoped free-shipping zone directly or through the country fallback.'
    );
}
if ($stateCount !== 47) {
    throw new RuntimeException('The isolated shop must have all 47 Japanese prefectures configured before free-shipping QA.');
}
if ($stateCodes !== $expectedStateCodes) {
    throw new RuntimeException(
        'Configured Japanese state ISO codes do not match the supported postcode catalog: expected '
        . implode(',', $expectedStateCodes) . '; found ' . implode(',', $stateCodes)
    );
}
if ($activeStateCount !== 47) {
    throw new RuntimeException('All 47 Japanese prefectures must be active before free-shipping QA.');
}

echo json_encode([
    'zone_id' => (int) $zone->id,
    'zone_name' => $zoneName,
    'country_codes' => $countryCodes,
    'state_count' => $stateCount,
    'active_state_count' => $activeStateCount,
    'state_iso_codes' => $stateCodes,
    'fixture_scope' => 'run-scoped isolated GitHub Actions disposable checkout database',
], JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
fwrite(STDERR, sprintf(
    "PASS: prepared active run-scoped Japan-only zone %d containing JP.\n",
    (int) $zone->id
));
