<?php

declare(strict_types=1);
require __DIR__ . '/ci_bootstrap.php';
$mode = $argv[1] ?? '';
ciAssert(in_array($mode, ['snapshot', 'compare'], true), 'Unknown retail boundary fixture command');
$state = [];
foreach (['orders', 'order_detail', 'order_payment', 'cart', 'cart_product'] as $suffix) {
    $rows = Db::getInstance()->executeS('SELECT * FROM `' . _DB_PREFIX_ . $suffix . '`', true, false);
    ciAssert(is_array($rows), 'Native commerce boundary state unavailable');
    foreach ($rows as &$row) {
        ksort($row);
        foreach ($row as &$value) $value = $value === null ? null : (string)$value;
        unset($value);
    }
    unset($row);
    $canonical = array_map(static fn(array $row): string => json_encode($row, JSON_THROW_ON_ERROR), $rows);
    sort($canonical, SORT_STRING);
    $state[$suffix] = hash('sha256', json_encode($canonical, JSON_THROW_ON_ERROR));
}
$path = __DIR__ . '/retail-boundary.json';
if ($mode === 'snapshot') {
    ciAssert(file_put_contents($path, json_encode($state, JSON_THROW_ON_ERROR)) !== false, 'Native commerce boundary snapshot unavailable');
    chmod($path, 0600);
} else {
    $before = json_decode((string)file_get_contents($path), true, 16, JSON_THROW_ON_ERROR);
    ciAssert($before === $state, 'Denied retail navigation changed commerce state');
}
echo "PASS native commerce boundary state snapshot or unchanged readback\n";
