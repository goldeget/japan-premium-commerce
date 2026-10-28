<?php
declare(strict_types=1);

require_once __DIR__ . '/../../modules/ordenowaprocurement/autoload.php';

use Ordenowa\Procurement\Infrastructure\Database;
use Ordenowa\Procurement\Infrastructure\Schema;
use Ordenowa\Procurement\Requests\RequestService;
use Ordenowa\Procurement\Security\Actor;

function pointTestConnection(): PDO
{
    $dsn = getenv('PROCUREMENT_TEST_DSN');
    if (!$dsn || !preg_match('/dbname=([^;]+)/', $dsn, $match) || !str_contains($match[1], 'test')) {
        throw new RuntimeException('PROCUREMENT_TEST_DSN must target an isolated database with test in its name.');
    }
    return new PDO($dsn, getenv('PROCUREMENT_TEST_USER') ?: 'root', getenv('PROCUREMENT_TEST_PASSWORD') ?: '', [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
}

function pointTestDatabase(?string $prefix = null): Database
{
    return new Database(pointTestConnection(), $prefix ?? ('pt_' . bin2hex(random_bytes(4)) . '_'));
}

function pointTestEmployee(int $id = 1): Actor
{
    return Actor::employee(1, $id, ['procurement.manage', 'procurement.review', 'procurement.read', 'points.read', 'points.award', 'points.correct', 'audit.read']);
}

function pointTestRequest(Database $db, int $customer = 11, string $decision = 'APPROVED'): array
{
    $requests = new RequestService($db);
    $assignment = $requests->createAssignment(pointTestEmployee(), $customer, [
        'shop_id' => 1, 'id_product' => 1, 'id_product_attribute' => 0,
        'names' => ['ja' => '合成テスト商品', 'en' => 'Synthetic test item', 'ko' => '합성 테스트 상품'],
        'descriptions' => ['ja' => '', 'en' => '', 'ko' => ''], 'image_url' => '', 'reference' => 'SYNTHETIC', 'source_url' => '',
    ], ['default_quantity' => 1, 'max_quantity' => 3, 'instructions' => 'Synthetic test only', 'deadline' => null]);
    $request = $requests->submit(Actor::customer(1, $customer), (int) $assignment['id_assignment'], (int) $assignment['version'], 1, 'request-' . bin2hex(random_bytes(8)));
    if ($decision === 'SUBMITTED') {
        return $request;
    }
    return $requests->review(pointTestEmployee(), (int) $request['id_request'], (int) $request['version'], $decision, 'Synthetic review');
}

function pointTestAssert(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException('Assertion failed: ' . $message);
    }
}

function pointTestReject(callable $operation, string $message, ?int $code = null): void
{
    try {
        $operation();
    } catch (Throwable $error) {
        pointTestAssert($code === null || $error->getCode() === $code, $message . ' (unexpected code ' . $error->getCode() . ')');
        return;
    }
    throw new RuntimeException('Expected rejection: ' . $message);
}

function pointTestCleanup(Database $db): void
{
    foreach (['policy', 'notification_delivery', 'notification', 'activity', 'point_ledger', 'point_award', 'point_account', 'review', 'request', 'assignment'] as $suffix) {
        $db->execute('DROP TABLE IF EXISTS ' . $db->table($suffix));
    }
}
