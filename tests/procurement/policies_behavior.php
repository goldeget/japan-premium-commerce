<?php

declare(strict_types=1);
require __DIR__ . '/requests_bootstrap.php';
use Ordenowa\Procurement\Infrastructure\{Database, Schema};
use Ordenowa\Procurement\Integration\PolicyService;
use Ordenowa\Procurement\Security\Actor;

$dsn = getenv('PROCUREMENT_TEST_DSN');
if (!$dsn || !str_contains($dsn, 'dbname=ordenowa_procurement_test')) { fwrite(STDERR, "Isolated procurement test database required.\n"); exit(2); }
$connect = static fn () => new PDO($dsn, getenv('PROCUREMENT_TEST_USER') ?: 'root', getenv('PROCUREMENT_TEST_PASSWORD') ?: '');
$pdo = $connect();
$prefix = 'policy_' . bin2hex(random_bytes(5)) . '_';
$db = new Database($pdo, $prefix);
$tables = ['support_post','support_link','policy','notification_delivery','notification','activity','point_ledger','point_award','point_account','review','request','assignment'];
try {
    Schema::install($db);
    $service = new PolicyService($db);
    $editor = Actor::employee(1, 10, ['policy.read','policy.manage']);
    $reader = Actor::employee(1, 11, ['policy.read']);
    $empty = $service->current(1);
    requestsAssert($empty['version'] === 0 && $empty['payload']['operator_name'] === '' && count($service->missing($empty['payload'])) === 11 && $service->published(1) === null, 'No invented identity, contact or policies may be published');
    requestsReject(fn () => $service->save(Actor::customer(1, 12), 0, []), 403, 'Customer policy write denied');
    requestsReject(fn () => $service->save($reader, 0, []), 403, 'Policy READ does not permit EDIT');
    requestsReject(fn () => $service->history(Actor::customer(1, 12)), 403, 'Policy admin history read denied');
    requestsReject(fn () => $service->save($editor, 0, ['support_email' => 'invalid']), 422, 'Invalid support email');
    requestsReject(fn () => $service->save($editor, 0, ['support_url' => 'javascript:alert(1)']), 422, 'Non HTTPS support URL');
    requestsReject(fn () => $service->save($editor, 0, ['support_url' => 'https://user:password@example.test/']), 422, 'Support URL credentials rejected');
    $first = $service->save($editor, 0, ['operator_name' => 'SYNTHETIC Test Operator']);
    requestsAssert($first['version'] === 1 && $service->published(1) === null, 'Incomplete explicit input remains unpublished');
    $payload = PolicyService::emptyPayload();
    $payload['operator_name'] = 'SYNTHETIC Test Operator';
    $payload['support_email'] = 'synthetic-support@example.test';
    $payload['support_url'] = 'https://support.example.test/';
    foreach (PolicyService::SECTIONS as $section) foreach (PolicyService::LOCALES as $locale) $payload[$section][$locale] = 'SYNTHETIC TEST ONLY ' . $section . ' ' . $locale . ' <script>text remains escaped by template</script>';
    $second = $service->save($editor, 1, $payload);
    requestsAssert($second['version'] === 2 && $service->published(1)['payload'] === $payload, 'All actual supplied fields publish together without logistics or seller requirements');
    requestsAssert($service->published(2) === null && count($service->history($reader)) === 2, 'Policies and history are scoped to shop');
    requestsReject(fn () => $service->save($editor, 1, $payload), 409, 'Stale policy version must not overwrite');
    $fresh = new PolicyService(new Database($connect(), $prefix));
    requestsAssert($fresh->published(1) === $service->published(1), 'New connection reads durable policy revision');
    $audit = $db->all('SELECT action,target_type,target_id,safe_data FROM ' . $db->table('activity') . ' ORDER BY id_activity');
    requestsAssert(count($audit) === 2 && $audit[1]['action'] === 'policy.updated' && (int) $audit[1]['target_id'] === $second['id_policy'] && json_decode($audit[1]['safe_data'],true) === ['version' => 2], 'Audit records the real immutable policy revision without policy body or contact');
    $trigger = '`' . $prefix . 'audit_failure`';
    $pdo->exec('CREATE TRIGGER ' . $trigger . ' BEFORE INSERT ON ' . $db->table('activity') . " FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='synthetic policy audit failure'");
    try { $service->save($editor, 2, $payload); throw new RuntimeException('Audit failure should rollback policy'); }
    catch (Throwable $error) { requestsAssert(!str_contains($error->getMessage(), 'should rollback'), 'Expected injected audit failure'); }
    $pdo->exec('DROP TRIGGER ' . $trigger);
    requestsAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('policy')) === 2 && $fresh->current(1)['version'] === 2, 'Policy and audit rollback atomically');
    echo "policies_behavior: PASS missing readiness, scope, ACL, stale version, append history, durable public read and audit rollback\n";
} finally {
    foreach ($tables as $table) $pdo->exec('DROP TABLE IF EXISTS ' . $db->table($table));
}
