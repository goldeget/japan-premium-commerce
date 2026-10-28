<?php

declare(strict_types=1);
require __DIR__ . '/ci_bootstrap.php';

use Ordenowa\Procurement\Infrastructure\Database;
use Ordenowa\Procurement\Points\PointService;
use Ordenowa\Procurement\Requests\RequestService;
use Ordenowa\Procurement\Security\Actor;

ciAssert(getenv('PROCUREMENT_RESTORE_HOST') === 'procurement-restore', 'Restore target guard failed');
$pdo = new PDO('mysql:host=procurement-restore;dbname=prestashop;charset=utf8mb4', 'root', (string) getenv('MARIADB_ROOT_PASSWORD'), [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$db = new Database($pdo, _DB_PREFIX_);
$fixture = ciFixture();
$a = Actor::customer(1, (int) $fixture['customers']['a']['id']);
$b = Actor::customer(1, (int) $fixture['customers']['b']['id']);
$manifest = json_decode((string) file_get_contents(__DIR__ . '/domain-manifest.json'), true, 32, JSON_THROW_ON_ERROR);
foreach ($manifest as $suffix => $hash) {
    ciAssert(ciDomainHash($db, $suffix) === $hash, 'Restored domain mismatch');
}
$points = new PointService($db);
$requests = new RequestService($db);
ciAssert((int) $points->account($a)['balance'] === 80, 'Restored balance mismatch');
ciAssert(array_sum(array_column($points->ledger($a), 'delta')) === 80, 'Restored ledger mismatch');
ciAssert(count($requests->customerRequests($a)) === 1 && $requests->customerRequests($b) === [], 'Restored ownership mismatch');
$product = $pdo->query('SELECT active,available_for_order,visibility FROM `' . _DB_PREFIX_ . 'product` WHERE id_product=' . (int) $fixture['product_id'])->fetch(PDO::FETCH_ASSOC);
ciAssert(is_array($product) && (int) $product['active'] === 0 && (int) $product['available_for_order'] === 0 && $product['visibility'] === 'none', 'Restored native reference mismatch');
echo "PASS restored ledger, ownership and private native product\n";
