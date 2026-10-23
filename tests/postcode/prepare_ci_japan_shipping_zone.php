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

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SERVER_PORT'] = (string) (parse_url('http://' . $_SERVER['HTTP_HOST'], PHP_URL_PORT) ?: 80);
require_once '/var/www/html/config/config.inc.php';

$japanId = (int) Country::getByIso('JP');
$japan = $japanId > 0 ? new Country($japanId) : false;
if (!$japan instanceof Country || !Validate::isLoadedObject($japan) || !(bool) $japan->active) {
    throw new RuntimeException('The active Japan country is missing from the isolated CI shop.');
}

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

if ((int) $japan->id_zone !== (int) $zone->id) {
    $japan->id_zone = (int) $zone->id;
    if (!$japan->update()) {
        throw new RuntimeException('Could not assign Japan to the run-scoped carrier zone.');
    }
}

if (!Db::getInstance()->execute(
    'UPDATE `' . _DB_PREFIX_ . 'state`'
    . ' SET `id_zone` = ' . (int) $zone->id
    . ' WHERE `id_country` = ' . (int) $japan->id
)) {
    throw new RuntimeException('Could not assign Japanese prefectures to the run-scoped carrier zone.');
}

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
$statesOutsideZone = (int) Db::getInstance()->getValue(
    'SELECT COUNT(*) FROM `' . _DB_PREFIX_ . 'state`'
    . ' WHERE `id_country` = ' . (int) $japan->id
    . ' AND `id_zone` <> ' . (int) $zone->id
);
if ($statesOutsideZone !== 0) {
    throw new RuntimeException('One or more Japanese prefectures are outside the run-scoped carrier zone.');
}

echo json_encode([
    'zone_id' => (int) $zone->id,
    'zone_name' => $zoneName,
    'country_codes' => $countryCodes,
    'fixture_scope' => 'run-scoped isolated GitHub Actions disposable checkout database',
], JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
fwrite(STDERR, sprintf(
    "PASS: prepared active run-scoped Japan-only zone %d containing JP.\n",
    (int) $zone->id
));
