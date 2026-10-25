<?php

declare(strict_types=1);

// Localize only the two exact sample categories in this disposable CI shop.
$runId = trim((string) getenv('KURANEA_CI_RUN_ID'));
$attempt = trim((string) getenv('KURANEA_CI_RUN_ATTEMPT'));
$project = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $attempt) !== 1
    || $project !== 'kuranea-ci-' . $runId . '-' . $attempt) {
    fwrite(STDERR, "BLOCKED: category locale fixture requires the matching isolated GitHub Actions shop.\n");
    exit(77);
}

$shopRoot = '/var/www/html';
if (!is_file($shopRoot . '/config/config.inc.php')) {
    fwrite(STDERR, "The isolated PrestaShop installation is missing.\n");
    exit(1);
}
$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SERVER_PORT'] = (string) (parse_url('http://' . $_SERVER['HTTP_HOST'], PHP_URL_PORT) ?: 80);
require_once $shopRoot . '/config/config.inc.php';

$dbServerMatches = defined('_DB_SERVER_')
    && in_array((string) _DB_SERVER_, ['mariadb', 'mariadb:3306'], true)
    && getenv('DB_SERVER') === 'mariadb'
    && getenv('DB_PORT') === '3306';
$activeDatabaseMatches = defined('_DB_NAME_')
    && (string) _DB_NAME_ === 'prestashop'
    && (string) Db::getInstance()->getValue('SELECT DATABASE()') === (string) _DB_NAME_;
if (!$dbServerMatches || !$activeDatabaseMatches) {
    fwrite(STDERR, "BLOCKED: connected database did not match the isolated PrestaShop fixture.\n");
    exit(77);
}

$shopId = 1;
$englishId = (int) Language::getIdByIso('en', true);
$japaneseId = (int) Language::getIdByIso('ja', true);
$koreanId = (int) Language::getIdByIso('ko', true);
$shop = new Shop($shopId);
if (!Validate::isLoadedObject($shop) || min($englishId, $japaneseId, $koreanId) < 1) {
    fwrite(STDERR, "The isolated shop is missing a required storefront language.\n");
    exit(1);
}

$labels = [
    'Clothes' => ['ja' => '衣料品', 'en' => 'Clothes', 'ko' => '의류'],
    'Art' => ['ja' => 'アート', 'en' => 'Art', 'ko' => '아트'],
];
$languageIds = ['ja' => $japaneseId, 'en' => $englishId, 'ko' => $koreanId];
$resolved = [];
foreach ($labels as $englishName => $localizedNames) {
    $targets = Db::getInstance()->executeS(
        'SELECT c.`id_category`'
        . ' FROM `' . _DB_PREFIX_ . 'category` c'
        . ' INNER JOIN `' . _DB_PREFIX_ . 'category_shop` cs'
        . ' ON cs.`id_category` = c.`id_category` AND cs.`id_shop` = ' . $shopId
        . ' INNER JOIN `' . _DB_PREFIX_ . 'category_lang` cl'
        . ' ON cl.`id_category` = c.`id_category` AND cl.`id_shop` = ' . $shopId
        . ' AND cl.`id_lang` = ' . $englishId
        . " WHERE cl.`name` = '" . pSQL($englishName) . "'"
        . ' ORDER BY c.`id_category`'
    );
    if (!is_array($targets) || count($targets) !== 1) {
        throw new RuntimeException('The isolated sample category name was missing or ambiguous.');
    }
    $categoryId = (int) ($targets[0]['id_category'] ?? 0);
    if ($categoryId < 2) {
        throw new RuntimeException('The isolated sample category ID is invalid.');
    }

    $before = Db::getInstance()->executeS(
        'SELECT `id_lang`, `name`, `link_rewrite`'
        . ' FROM `' . _DB_PREFIX_ . 'category_lang`'
        . ' WHERE `id_category` = ' . $categoryId . ' AND `id_shop` = ' . $shopId
        . ' ORDER BY `id_lang`'
    );
    if (!is_array($before)) {
        throw new RuntimeException('Could not read the isolated sample category language rows.');
    }
    $beforeByLanguage = [];
    foreach ($before as $row) {
        $beforeByLanguage[(int) ($row['id_lang'] ?? 0)] = [
            'name' => (string) ($row['name'] ?? ''),
            'link_rewrite' => (string) ($row['link_rewrite'] ?? ''),
        ];
    }
    if (($beforeByLanguage[$englishId]['name'] ?? null) !== $englishName) {
        throw new RuntimeException('The isolated English sample category changed during fixture resolution.');
    }

    foreach (['ja', 'ko'] as $isoCode) {
        $idLanguage = $languageIds[$isoCode];
        if (!isset($beforeByLanguage[$idLanguage])) {
            throw new RuntimeException('A required isolated category language row is missing.');
        }
        if (!Db::getInstance()->update(
            'category_lang',
            ['name' => pSQL($localizedNames[$isoCode])],
            '`id_category` = ' . $categoryId . ' AND `id_lang` = ' . $idLanguage . ' AND `id_shop` = ' . $shopId
        )) {
            throw new RuntimeException('Could not update an isolated sample category display label.');
        }
    }

    $after = Db::getInstance()->executeS(
        'SELECT `id_lang`, `name`, `link_rewrite`'
        . ' FROM `' . _DB_PREFIX_ . 'category_lang`'
        . ' WHERE `id_category` = ' . $categoryId . ' AND `id_shop` = ' . $shopId
        . ' ORDER BY `id_lang`'
    );
    if (!is_array($after)) {
        throw new RuntimeException('Could not re-read the isolated sample category language rows.');
    }
    $afterByLanguage = [];
    foreach ($after as $row) {
        $afterByLanguage[(int) ($row['id_lang'] ?? 0)] = [
            'name' => (string) ($row['name'] ?? ''),
            'link_rewrite' => (string) ($row['link_rewrite'] ?? ''),
        ];
    }
    foreach ($beforeByLanguage as $idLanguage => $oldValues) {
        $expectedName = match ($idLanguage) {
            $japaneseId => $localizedNames['ja'],
            $koreanId => $localizedNames['ko'],
            default => $oldValues['name'],
        };
        if (($afterByLanguage[$idLanguage]['name'] ?? null) !== $expectedName
            || ($afterByLanguage[$idLanguage]['link_rewrite'] ?? null) !== $oldValues['link_rewrite']) {
            throw new RuntimeException('The isolated category fixture changed an unrelated language row or URL slug.');
        }
    }
    $resolved[$englishName] = [
        'id' => $categoryId,
        'names' => $localizedNames,
        'link_rewrite_preserved' => true,
        'other_languages_preserved' => true,
    ];
}

$report = [
    'database_isolated' => true,
    'created_categories' => 0,
    'updated_fields' => ['category_lang.name for ja and ko only'],
    'categories' => $resolved,
    'language_ids' => $languageIds,
];
echo json_encode($report, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT) . PHP_EOL;
