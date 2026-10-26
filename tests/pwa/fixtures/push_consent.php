<?php
/** Run-scoped synthetic consent only; no sender or subscription delivery. */
declare(strict_types=1);

$run = (string) getenv('GITHUB_RUN_ID');
$attempt = (string) getenv('GITHUB_RUN_ATTEMPT');
$project = 'kuranea-ci-' . $run . '-' . $attempt;
if (PHP_SAPI !== 'cli'
    || getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || getenv('ORDENOWA_PUSH_TEST_MODE') !== '1'
    || !preg_match('/^[0-9]+$/D', $run)
    || !preg_match('/^[0-9]+$/D', $attempt)
    || getenv('KURANEA_CI_PROJECT_NAME') !== $project) {
    throw new RuntimeException('Synthetic push fixtures require the exact isolated Actions project.');
}
$action = $argv[1] ?? '';
if (!in_array($action, ['seed', 'restore'], true)) {
    throw new RuntimeException('Unknown synthetic push fixture operation.');
}
$storageKey = base64_decode((string) getenv('ORDENOWA_PUSH_STORAGE_KEY'), true);
if (!is_string($storageKey) || strlen($storageKey) !== 32) {
    throw new RuntimeException('Synthetic push fixture requires a throwaway storage key.');
}
unset($storageKey);
$_SERVER['HTTP_HOST'] = (string) getenv('PS_DOMAIN') ?: 'localhost:18080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require_once '/var/www/html/config/config.inc.php';
Shop::setContext(Shop::CONTEXT_SHOP, 1);
Context::getContext()->shop = new Shop(1);
$keys = [
    'ORDENOWA_PUSH_CONSENT_NOTICE_JA',
    'ORDENOWA_PUSH_CONSENT_NOTICE_EN',
    'ORDENOWA_PUSH_CONSENT_NOTICE_KO',
    'ORDENOWA_PUSH_EVENT_ORDER',
    'ORDENOWA_PUSH_EVENT_DELIVERY',
    'ORDENOWA_PUSH_EVENT_SUPPORT',
];
$snapshotPath = '/tmp/ordenowa-push-consent-' . $run . '-' . $attempt . '.json';
if (is_link($snapshotPath)) {
    throw new RuntimeException('Unsafe synthetic push fixture snapshot.');
}
if ($action === 'seed') {
    $snapshot = [];
    foreach ($keys as $key) {
        $snapshot[$key] = Configuration::get($key, null, null, 1);
    }
    foreach (array_slice($keys, 0, 3) as $key) {
        if (trim((string) $snapshot[$key]) !== '') {
            throw new RuntimeException('Synthetic fixture requires initially blank consent notices.');
        }
    }
    $handle = fopen($snapshotPath, 'x');
    if ($handle === false || !chmod($snapshotPath, 0600)) {
        throw new RuntimeException('Could not create isolated push configuration snapshot.');
    }
    $encoded = json_encode(['project' => $project, 'values' => $snapshot], JSON_THROW_ON_ERROR);
    if (fwrite($handle, $encoded) !== strlen($encoded) || !fclose($handle)) {
        throw new RuntimeException('Could not persist isolated push configuration snapshot.');
    }
    foreach ($keys as $key) {
        $value = str_contains($key, '_CONSENT_NOTICE_')
            ? '[CI SYNTHETIC ONLY] Disposable notification consent test. No messages are sent.' : '1';
        if (!Configuration::updateValue($key, $value, false, null, 1)) {
            throw new RuntimeException('Could not seed synthetic push configuration.');
        }
    }
    echo "PASS: run-scoped synthetic push consent seeded; no sender configured.\n";
} else {
    if (!is_file($snapshotPath)) {
        // A startup failure may occur before the fixture has changed anything.
        echo "PASS: no synthetic push snapshot to restore.\n";
        exit(0);
    }
    $handle = fopen($snapshotPath, 'r');
    if ($handle === false) {
        throw new RuntimeException('Could not read isolated push configuration snapshot.');
    }
    $snapshot = json_decode(stream_get_contents($handle), true, 8, JSON_THROW_ON_ERROR);
    fclose($handle);
    if (($snapshot['project'] ?? '') !== $project
        || array_keys($snapshot['values'] ?? []) !== $keys) {
        throw new RuntimeException('Synthetic push snapshot identity did not match this run.');
    }
    foreach ($keys as $key) {
        $original = $snapshot['values'][$key];
        $ok = $original === false ? Configuration::deleteByName($key)
            : Configuration::updateValue($key, $original, false, null, 1);
        if (!$ok || Configuration::get($key, null, null, 1) !== $original) {
            throw new RuntimeException('Could not restore/read back original push configuration.');
        }
    }
    if (!unlink($snapshotPath)) {
        throw new RuntimeException('Could not remove restored synthetic push snapshot.');
    }
    echo "PASS: original push consent/event configuration restored and read back.\n";
}
