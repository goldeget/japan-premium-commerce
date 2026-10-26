<?php

declare(strict_types=1);

function contactRouteRequire(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

$runId = (string) getenv('GITHUB_RUN_ID');
$attempt = (string) getenv('GITHUB_RUN_ATTEMPT');
$project = (string) getenv('CI_COMPOSE_PROJECT_NAME');
$expectedProject = sprintf('kuranea-ci-%s-%s', $runId, $attempt);
contactRouteRequire(
    getenv('CI') === 'true'
        && getenv('GITHUB_ACTIONS') === 'true'
        && getenv('KURANEA_ISOLATED_CI') === '1'
        && preg_match('/\A[0-9]+\z/D', $runId) === 1
        && preg_match('/\A[0-9]+\z/D', $attempt) === 1
        && $project === $expectedProject
        && getenv('KURANEA_CI_PROJECT_NAME') === $expectedProject,
    'Native contact route readback requires the exact disposable GitHub Actions project.'
);

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require_once '/var/www/html/config/config.inc.php';

$context = Context::getContext();
$shopId = (int) $context->shop->id;
$db = Db::getInstance();
$metaCount = $db->getValue(
    "SELECT COUNT(*) FROM `" . _DB_PREFIX_ . "meta` WHERE page = 'contact'",
    false
);
contactRouteRequire(is_numeric($metaCount), 'Could not read native contact page metadata.');
$metaPresent = (int) $metaCount > 0;
$rewriteRows = $db->executeS(
    'SELECT l.iso_code, ml.url_rewrite'
        . ' FROM `' . _DB_PREFIX_ . 'meta_lang` ml'
        . ' INNER JOIN `' . _DB_PREFIX_ . 'meta` m ON m.id_meta = ml.id_meta'
        . ' INNER JOIN `' . _DB_PREFIX_ . 'lang` l ON l.id_lang = ml.id_lang'
        . " WHERE m.page = 'contact' AND ml.id_shop = " . $shopId
        . " AND l.iso_code IN ('ja', 'en', 'ko')",
    true,
    false
);
contactRouteRequire(is_array($rewriteRows), 'Could not read isolated localized contact routes.');
$localizedRewrites = ['ja' => false, 'en' => false, 'ko' => false];
foreach ($rewriteRows as $row) {
    $iso = (string) ($row['iso_code'] ?? '');
    $rewrite = $row['url_rewrite'] ?? null;
    if (isset($localizedRewrites[$iso])) {
        $localizedRewrites[$iso] = is_string($rewrite) && trim($rewrite) !== '';
    }
}

$urlsByIso = [];
foreach (['ja', 'en', 'ko'] as $iso) {
    $idLang = (int) Language::getIdByIso($iso, true);
    if ($idLang < 1) {
        continue;
    }
    $urlsByIso[$iso] = (string) $context->link->getPageLink('contact', null, $idLang);
}

$payload = [
    'schema' => 1,
    'contact_meta_present' => $metaPresent,
    'rewriting_enabled' => (bool) Configuration::get('PS_REWRITING_SETTINGS'),
    'canonical_redirect_mode' => (int) Configuration::get('PS_CANONICAL_REDIRECT'),
    'contactform_enabled' => Module::isInstalled('contactform') && Module::isEnabled('contactform'),
    'localized_rewrites' => $localizedRewrites,
    'urls_by_iso' => $urlsByIso,
];
fwrite(STDOUT, json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . "\n");
