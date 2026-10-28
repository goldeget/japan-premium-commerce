<?php
declare(strict_types=1);
require __DIR__ . '/requests_bootstrap.php';

use Ordenowa\Procurement\Infrastructure\Database;
use Ordenowa\Procurement\Infrastructure\Schema;
use Ordenowa\Procurement\Requests\RequestService;
use Ordenowa\Procurement\Security\Actor;

$dsn = getenv('PROCUREMENT_TEST_DSN');
if (!$dsn || !str_contains($dsn, 'dbname=ordenowa_procurement_test')) {
    fwrite(STDERR, "Refusing database tests without isolated ordenowa_procurement_test database.\n");
    exit(2);
}
$pdo = new PDO($dsn, getenv('PROCUREMENT_TEST_USER') ?: 'root', getenv('PROCUREMENT_TEST_PASSWORD') ?: '');
$prefix = 'requests_' . bin2hex(random_bytes(5)) . '_';
$db = new Database($pdo, $prefix);
$tables = ['support_post','support_link','policy','notification_delivery','notification','activity','point_ledger','point_award','point_account','review','request','assignment'];
try {
    Schema::install($db);
    $service = new RequestService($db);
    $manager = Actor::employee(1, 10, ['procurement.read','procurement.manage','procurement.review']);
    $a = Actor::customer(1, 101);
    $b = Actor::customer(1, 102);
    $otherShop = Actor::customer(2, 101);
    $product = ['shop_id'=>1,'id_product'=>7,'id_product_attribute'=>8,'names'=>['ja'=>'商品','en'=>'Product','ko'=>'상품'],
        'descriptions'=>['ja'=>'説明','en'=>'Description','ko'=>'설명'],'image_url'=>'','reference'=>'SYNTHETIC','source_url'=>'',
        'reference_price'=>'1234','currency'=>'JPY'];
    $make = static fn (array $input = []) => $service->createAssignment($manager, 101, $product,
        $input + ['default_quantity'=>1,'max_quantity'=>5,'instructions'=>'Synthetic procurement instruction']);
    $assignment = $make();
    $id = $assignment['id_assignment'];
    requestsAssert(count($service->customerAssignments($a)) === 1 && $service->customerAssignments($b) === [], 'Assignment lists enforce ownership');
    foreach ([$b, $otherShop] as $outsider) {
        requestsReject(fn () => $service->assignment($outsider, $id), 404, 'Assignment owner guard');
        requestsReject(fn () => $service->submit($outsider, $id, 1, 1, 'outsider'), 404, 'Submit owner guard');
    }
    requestsReject(fn () => $service->createAssignment($a, 101, $product, []), 403, 'Customer cannot create');
    requestsReject(fn () => $service->createAssignment($manager, 101, array_replace($product, ['shop_id'=>2]), []), 422, 'Cross shop product rejected');
    requestsReject(fn () => $service->createAssignment($manager, 101, array_replace($product, ['reference_price'=>'NaN']), []), 422, 'Invalid source price rejected');
    $missingPrice = $service->createAssignment($manager, 101, array_replace($product, ['reference_price'=>'']), []);
    requestsAssert($missingPrice['product_snapshot']['reference_price'] === '', 'Missing optional source price remains absent');
    $rightsProduct = $product;
    $rightsProduct['image_rights'] = ['kind'=>'operator-attestation','attestation'=>'Synthetic locally approved image permission',
        'id_employee'=>10,'image_ids'=>[9]];
    $rightsAssignment = $service->createAssignment($manager, 101, $rightsProduct, []);
    requestsAssert(($rightsAssignment['product_snapshot']['image_rights'] ?? null) === $rightsProduct['image_rights'], 'Native image rights attestation preserved in immutable snapshot');
    $rightsRequest = $service->submit($a, $rightsAssignment['id_assignment'], 1, 1, 'rights-snapshot');
    requestsAssert($rightsRequest['product_snapshot']['image_rights'] === $rightsProduct['image_rights'], 'Submitted image rights snapshot preserved');
    $rightsProduct['image_rights']['id_employee'] = 11;
    requestsReject(fn () => $service->createAssignment($manager, 101, $rightsProduct, []), 422, 'Image attestation must identify verified issuing employee');
    $galleryProduct = $product;
    $galleryProduct['image_url'] = '/img/p/1/2/12-home_default.jpg';
    $galleryProduct['image_urls'] = ['/img/p/1/2/12-home_default.jpg','/img/p/1/3/13-home_default.webp'];
    $gallery = $service->createAssignment($manager, 101, $galleryProduct, []);
    requestsAssert($gallery['product_snapshot']['image_urls'] === $galleryProduct['image_urls'], 'Approved canonical native gallery paths preserved');
    foreach (['/img/p/../private.jpg','/img/p/12-home_default.jpg?token=private','data:image/png;base64,AAAA','/account/customer.jpg'] as $unsafeImage) {
        requestsReject(fn () => $service->createAssignment($manager, 101, array_replace($galleryProduct, ['image_urls'=>[$unsafeImage]]), []), 422, 'Private or noncanonical gallery image denied');
    }
    requestsReject(fn () => $service->submit($a, $id, 2, 1, 'stale'), 409, 'Stale assignment');
    foreach ([0, 6] as $quantity) { requestsReject(fn () => $service->submit($a, $id, 1, $quantity, 'badqty'), 422, 'Quantity bounds'); }
    $request = $service->submit($a, $id, 1, 3, 'submit-one');
    requestsAssert($request['quantity'] === 3 && $request['status'] === 'SUBMITTED', 'Submission persists');
    requestsAssert($service->submit($a, $id, 1, 3, 'submit-one')['id_request'] === $request['id_request'], 'Idempotent same payload returns request');
    requestsReject(fn () => $service->submit($a, $id, 1, 2, 'submit-one'), 409, 'Same key different payload');
    requestsReject(fn () => $service->submit($a, $id, 1, 3, 'other-key'), 409, 'Different key duplicate assignment');
    requestsReject(fn () => $service->request($b, $request['id_request']), 404, 'Request owner guard');
    $db->execute('UPDATE ' . $db->table('assignment') . " SET product_snapshot='{}',instructions='changed' WHERE id_assignment=" . $id);
    $saved = (new RequestService(new Database(new PDO($dsn, getenv('PROCUREMENT_TEST_USER') ?: 'root', getenv('PROCUREMENT_TEST_PASSWORD') ?: ''), $prefix)))->request($a, $request['id_request']);
    requestsAssert($saved['product_snapshot']['names']['en'] === 'Product' && $saved['instructions'] === 'Synthetic procurement instruction', 'New connection reads immutable product/instruction snapshot');
    requestsAssert($saved['product_snapshot']['reference_price'] === '1234' && $saved['product_snapshot']['currency'] === 'JPY', 'Reviewed source reference price preserved without numeric coercion');
    requestsReject(fn () => $service->review(Actor::employee(1, 11, ['procurement.read']), $request['id_request'], 1, 'APPROVED', 'ok'), 403, 'Review ACL');
    requestsReject(fn () => $service->review($a, $request['id_request'], 1, 'INVALID', 'ok'), 403, 'Review authorization precedes decision validation');
    requestsReject(fn () => $service->review($manager, $request['id_request'], 2, 'APPROVED', 'ok'), 409, 'Review version');
    $approved = $service->review($manager, $request['id_request'], 1, 'APPROVED', 'Confirmed synthetic request');
    requestsAssert($approved['status'] === 'APPROVED' && $approved['review_reason'] === 'Confirmed synthetic request', 'Final review readback');
    requestsReject(fn () => $service->review($manager, $request['id_request'], 2, 'REJECTED', 'change'), 409, 'Final review immutable');
    requestsAssert((int)$db->value('SELECT COUNT(*) FROM ' . $db->table('point_ledger')) === 0, 'Approval never awards points');
    requestsAssert(count($service->adminRequests($manager, ['status'=>'APPROVED','unawarded'=>true])) === 1, 'Pending award filter includes approved unpaid request');
    (new \Ordenowa\Procurement\Points\PointService($db))->award(Actor::employee(1, 10, ['points.award']), $request['id_request'], 100, 'Synthetic pending award filter', 'pending-filter');
    requestsAssert($service->adminRequests($manager, ['status'=>'APPROVED','unawarded'=>true]) === [], 'Pending award filter excludes historical award');
    $revoked = $make();
    $service->revokeAssignment($manager, $revoked['id_assignment'], 1, 'Recalled');
    requestsReject(fn () => $service->submit($a, $revoked['id_assignment'], 1, 1, 'revoked'), 409, 'Revoked rejects old page');
    $expired = $make(['deadline'=>'2000-01-01 00:00:00']);
    requestsReject(fn () => $service->submit($a, $expired['id_assignment'], 1, 1, 'expired'), 409, 'Expired assignment');
    foreach (['REJECTED','CANCELLED'] as $decision) {
        $fresh = $make();
        $pending = $service->submit($a, $fresh['id_assignment'], 1, 1, 'final-' . $decision);
        requestsAssert($service->review($manager, $pending['id_request'], 1, $decision, 'Synthetic decision')['status'] === $decision, 'Final decision ' . $decision);
    }
    // SQL triggers inject actual database failures after earlier transactional writes.
    foreach (['activity','notification'] as $failTable) {
        $fresh = $make();
        $before = [];
        foreach (['request','activity','notification'] as $table) { $before[$table] = (int)$db->value('SELECT COUNT(*) FROM '.$db->table($table)); }
        $trigger = '`' . $prefix . 'fail_' . $failTable . '`';
        $db->execute('CREATE TRIGGER ' . $trigger . ' BEFORE INSERT ON ' . $db->table($failTable) . " FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Synthetic rollback fault'");
        requestsReject(fn () => $service->submit($a, $fresh['id_assignment'], 1, 1, 'rollback-' . $failTable), 0, 'Injected transactional failure');
        $db->execute('DROP TRIGGER ' . $trigger);
        foreach ($before as $table => $count) { requestsAssert((int)$db->value('SELECT COUNT(*) FROM '.$db->table($table)) === $count, 'No partial ' . $table); }
        requestsAssert($service->assignment($a, $fresh['id_assignment'])['status'] === 'ACTIVE', 'Assignment rollback');
        requestsAssert($service->submit($a, $fresh['id_assignment'], 1, 1, 'rollback-' . $failTable)['status'] === 'SUBMITTED', 'Retry after rollback');
    }
    // An outbox failure must also roll back issuance, revocation and final review.
    foreach (['create','revoke','review'] as $operation) {
        $fresh = $make();
        $pending = $operation === 'review' ? $service->submit($a, $fresh['id_assignment'], 1, 1, 'rollback-review') : null;
        $before = [];
        foreach (['assignment','review','activity','notification'] as $table) { $before[$table] = (int)$db->value('SELECT COUNT(*) FROM '.$db->table($table)); }
        $trigger = '`' . $prefix . 'fail_operation`';
        $db->execute('CREATE TRIGGER ' . $trigger . ' BEFORE INSERT ON ' . $db->table('notification') . " FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Synthetic rollback fault'");
        $mutate = match ($operation) {
            'create' => fn () => $make(),
            'revoke' => fn () => $service->revokeAssignment($manager, $fresh['id_assignment'], 1, 'Synthetic revoke'),
            'review' => fn () => $service->review($manager, $pending['id_request'], 1, 'APPROVED', 'Synthetic review'),
        };
        requestsReject($mutate, 0, 'Outbox rollback for ' . $operation);
        $db->execute('DROP TRIGGER ' . $trigger);
        foreach ($before as $table => $count) { requestsAssert((int)$db->value('SELECT COUNT(*) FROM '.$db->table($table)) === $count, 'No partial ' . $operation . ' ' . $table); }
        if ($operation === 'review') { requestsAssert($service->request($a, $pending['id_request'])['status'] === 'SUBMITTED', 'Review status rolled back'); }
        else { requestsAssert($service->assignment($a, $fresh['id_assignment'])['status'] === 'ACTIVE', 'Assignment remains active'); }
    }
    // Nested transactions preserve the outer unit while rolling back a failed inner savepoint.
    $count = (int)$db->value('SELECT COUNT(*) FROM ' . $db->table('activity'));
    $db->transaction(function () use ($db, $manager): void {
        (new \Ordenowa\Procurement\Infrastructure\Recorder($db))->audit($manager, 'test.outer', 'assignment', 1);
        try {
            $db->transaction(function () use ($db, $manager): void {
                (new \Ordenowa\Procurement\Infrastructure\Recorder($db))->audit($manager, 'test.inner', 'assignment', 1);
                throw new RuntimeException('Synthetic inner failure');
            });
        } catch (RuntimeException $expected) {}
    });
    requestsAssert((int)$db->value('SELECT COUNT(*) FROM ' . $db->table('activity')) === $count + 1, 'Nested savepoint rollback');
    // More than the previous hard cap: every record remains reachable by cursor,
    // and category navigation uses all owned snapshots rather than page one.
    for ($index = 0; $index < 205; ++$index) {
        $pagedProduct = $product;
        $pagedProduct['names']['en'] = 'Paging Fixture ' . $index;
        $pagedProduct['categories'] = [['id_category'=>$index === 0 ? 41 : 42,'id_parent'=>0,
            'names'=>['ja'=>'分類','en'=>$index === 0 ? 'Earliest category' : 'Current category','ko'=>'분류']]];
        $paged = $service->createAssignment($manager, 101, $pagedProduct, ['default_quantity'=>1,'max_quantity'=>1]);
        if ($index < 55) { $service->submit($a, $paged['id_assignment'], 1, 1, 'paging-' . $index); }
    }
    $seen = [];
    $cursor = 0;
    do {
        $page = $service->customerAssignments($a, ['before_id'=>$cursor,'limit'=>50,'q'=>'Paging Fixture']);
        foreach ($page as $item) { $seen[] = $item['id_assignment']; }
        $cursor = $page === [] ? 0 : $page[count($page)-1]['id_assignment'];
    } while (count($page) === 50);
    requestsAssert(count($seen) === 205 && count(array_unique($seen)) === 205, 'All assignments reachable without duplicated cursor rows');
    $categoryIds = array_column($service->customerCategories($a), 'id_category');
    requestsAssert(in_array(41, $categoryIds, true) && in_array(42, $categoryIds, true), 'Category enumeration includes oldest snapshot');
    requestsAssert(count($service->customerAssignments($a, ['category_id'=>41])) === 1, 'Category filtered independently of page one');
    requestsAssert($service->customerAssignments($b, ['category_id'=>41]) === [], 'Category filter retains owner guard');
    requestsAssert($service->customerAssignments($a, ['q'=>'%']) === [], 'Search wildcards treated literally');
    $unicodeProduct = $product;
    $unicodeProduct['names']['ja'] = str_repeat('商', 40);
    $service->createAssignment($manager, 101, $unicodeProduct, []);
    requestsAssert(count($service->customerAssignments($a, ['q'=>str_repeat('商', 40)])) === 1, 'Japanese search limit counts characters rather than UTF-8 bytes');
    requestsAssert(count($service->customerAssignments($a, ['q'=>'Paging Fixture','status'=>'REQUESTED','limit'=>200])) === 55, 'Assignment status filter');
    $page = $service->customerRequests($a, ['q'=>'Paging Fixture','limit'=>50]);
    $second = $service->customerRequests($a, ['q'=>'Paging Fixture','limit'=>50,'before_id'=>$page[49]['id_request']]);
    requestsAssert(count($page) === 50 && count($second) === 5, 'Request cursor pagination');
    requestsAssert(count($service->adminAssignments($manager, ['q'=>'Paging Fixture','limit'=>200])) === 200, 'Admin filters and bounded pages');
    requestsReject(fn () => $service->customerAssignments($a, ['limit'=>201]), 422, 'Page size bounded');
    requestsReject(fn () => $service->customerRequests($a, ['before_id'=>-1]), 422, 'Cursor validation');
    fwrite(STDOUT, "PASS requests behavioral ownership/version/idempotency/snapshot/final review/transaction tests\n");
} finally {
    foreach ($tables as $table) { $db->execute('DROP TABLE IF EXISTS ' . $db->table($table)); }
}
