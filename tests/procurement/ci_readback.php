<?php

declare(strict_types=1);
require __DIR__ . '/ci_bootstrap.php';

use Ordenowa\Procurement\Infrastructure\Database;
use Ordenowa\Procurement\Integration\Runtime;
use Ordenowa\Procurement\Security\Actor;

$fixture = ciFixture();
$a = Actor::customer(1, (int) $fixture['customers']['a']['id']);
$b = Actor::customer(1, (int) $fixture['customers']['b']['id']);
$requests = Runtime::requests()->customerRequests($a);
ciAssert(count($requests) === 1, 'Browser request count incorrect');
$request = $requests[0];
ciAssert($request['status'] === 'APPROVED' && (int) $request['quantity'] === 2, 'Browser request readback incorrect');
$account = Runtime::points()->account($a);
$ledger = Runtime::points()->ledger($a);
ciAssert((int) $account['balance'] === 80 && count($ledger) === 2, 'Point readback incorrect');
ciAssert(array_sum(array_column($ledger, 'delta')) === 80, 'Ledger sum mismatch');
ciAssert(Runtime::requests()->customerRequests($b) === [] && Runtime::points()->ledger($b) === [], 'Owner isolation changed');
ciAssert((int) Runtime::points()->account($b)['balance'] === 0, 'Other owner balance changed');
try {
    Runtime::requests()->request($b, (int) $request['id_request']);
    throw new LogicException('Expected ownership denial');
} catch (RuntimeException $error) {
    ciAssert($error->getCode() === 404, 'Ownership must return not found');
}
$db = Runtime::database();
$tables = ['assignment', 'request', 'review', 'point_account', 'point_award', 'point_ledger', 'activity', 'notification', 'notification_delivery', 'policy', 'support_link', 'support_post'];
$manifest = [];
foreach ($tables as $suffix) {
    // Hashes stay in private temp storage, never in uploaded artifacts.
    $manifest[$suffix] = ciDomainHash($db, $suffix);
}
if (($argv[1] ?? '') === 'manifest') {
    file_put_contents(__DIR__ . '/domain-manifest.json', json_encode($manifest, JSON_THROW_ON_ERROR));
    chmod(__DIR__ . '/domain-manifest.json', 0600);
} elseif (($argv[1] ?? '') === 'compare') {
    $expected = json_decode((string) file_get_contents(__DIR__ . '/domain-manifest.json'), true, 32, JSON_THROW_ON_ERROR);
    ciAssert($manifest === $expected, 'Domain restore hashes changed');
}
echo "PASS durable request, point ledger, owner isolation and domain readback\n";
