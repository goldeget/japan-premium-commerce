<?php
declare(strict_types=1);
require_once __DIR__ . '/points_support.php';

use Ordenowa\Procurement\Infrastructure\Schema;
use Ordenowa\Procurement\Points\PointService;
use Ordenowa\Procurement\Security\Actor;

$db = pointTestDatabase();
Schema::install($db);
$points = new PointService($db);
$employee = pointTestEmployee();
$customer = Actor::customer(1, 11);
try {
    pointTestAssert($points->account($customer)['balance'] === 0, 'new account starts at zero');
    pointTestAssert($points->ledger($customer) === [], 'new ledger empty');
    foreach (['SUBMITTED', 'REJECTED', 'CANCELLED'] as $status) {
        $request = pointTestRequest($db, 11, $status);
        pointTestReject(fn() => $points->award($employee, (int) $request['id_request'], 100, 'Manual allowance', 'blocked-' . $status), 'award only after approval');
    }
    $request = pointTestRequest($db);
    $id = (int) $request['id_request'];
    pointTestAssert($points->account($customer)['balance'] === 0, 'approval does not create automatic points');
    foreach ([0, -1] as $amount) {
        pointTestReject(fn() => $points->award($employee, $id, $amount, 'Invalid', 'invalid-' . $amount), 'positive integer award required');
    }
    pointTestReject(fn() => $points->award($employee, $id, 1.5, 'Fraction', 'fraction'), 'fractional award rejected');
    pointTestReject(fn() => $points->award($customer, $id, 100, 'Forbidden', 'customer-award'), 'customer cannot award', 403);
    pointTestReject(fn() => $points->award(Actor::employee(2, 1, ['points.award']), $id, 100, 'Wrong shop', 'shop-award'), 'other shop cannot award', 404);
    pointTestReject(fn() => $points->award($employee, $id, 100, '', 'blank-reason'), 'reason required');
    $award = $points->award($employee, $id, 100, 'Manual allowance', 'base-1');
    pointTestAssert((int) $award['amount'] === 100, 'base amount recorded');
    pointTestAssert($points->account($customer)['balance'] === 100, 'manual award updates balance');
    $retry = $points->award(pointTestEmployee(2), $id, 100, 'Manual allowance', 'base-1');
    pointTestAssert($retry['id_award'] === $award['id_award'], 'same payload retry returns award even by second employee');
    pointTestReject(fn() => $points->award($employee, $id, 100, 'Manual allowance', 'different-key'), 'request cannot receive second base award', 409);
    pointTestReject(fn() => $points->award($employee, $id, 101, 'Manual allowance', 'base-1'), 'key payload conflict', 409);
    $another = pointTestRequest($db);
    pointTestReject(fn() => $points->award($employee, (int) $another['id_request'], 100, 'Manual allowance', 'base-1'), 'key cannot move request', 409);
    pointTestReject(fn() => $points->account(Actor::customer(1, 12), 11), 'customer cannot read other account', 404);
    pointTestReject(fn() => $points->ledger(Actor::customer(1, 12), 11), 'customer cannot read other ledger', 404);
    pointTestAssert($points->account(Actor::customer(1, 12))['balance'] === 0, 'B remains zero after denied read');
    pointTestAssert(count($points->ledger($customer)) === 1, 'no duplicate ledger rows');
    pointTestReject(fn() => $points->correct($customer, (int) $award['id_award'], -1, 'Forbidden', 'customer-correction'), 'customer cannot correct', 403);
    pointTestReject(fn() => $points->correct(Actor::employee(2, 1, ['points.correct']), (int) $award['id_award'], -1, 'Wrong shop', 'shop-correction'), 'other shop cannot correct', 404);
    pointTestReject(fn() => $points->awards($customer), 'customer cannot read award admin list', 403);
    $correction = $points->correct($employee, (int) $award['id_award'], -20, 'Amount correction', 'fix-1');
    pointTestAssert((int) $correction['original_entry'] === (int) $award['id_ledger'], 'correction linked original entry');
    pointTestAssert($points->account($customer)['balance'] === 80, 'correction balance80');
    $retry = $points->correct(pointTestEmployee(2), (int) $award['id_award'], -20, 'Amount correction', 'fix-1');
    pointTestAssert($retry['id_ledger'] === $correction['id_ledger'], 'correction retry idempotent');
    pointTestReject(fn() => $points->correct($employee, (int) $award['id_award'], -21, 'Amount correction', 'fix-1'), 'correction key conflict', 409);
    pointTestReject(fn() => $points->correct($employee, (int) $award['id_award'], -81, 'Too low', 'negative-net'), 'cannot over reverse');
    pointTestReject(fn() => $points->correct($employee, (int) $award['id_award'], 21, 'Too high', 'over-base'), 'cannot exceed base amount');
    pointTestReject(fn() => $points->correct($employee, (int) $award['id_award'], 0, 'Zero', 'zero-correction'), 'zero correction refused');
    $points->correct($employee, (int) $award['id_award'], 20, 'Restore prior correction', 'restore');
    pointTestAssert($points->account($customer)['balance'] === 100, 'positive correction restores cancellation');
    pointTestAssert((int) $db->value('SELECT delta FROM ' . $db->table('point_ledger') . ' WHERE id_ledger=' . (int) $award['id_ledger']) === 100, 'original ledger delta immutable');
    pointTestAssert($points->reconcile($customer)['consistent'] === true, 'ledger and account agree');
    // A fresh connection reads durable state; reads do not depend on session/service caches.
    $fresh = new PointService(pointTestDatabase(str_replace('ordenowa_procurement_point_account', '', trim($db->table('point_account'), '`'))));
    pointTestAssert($fresh->account($customer)['balance'] === 100, 'fresh connection reads balance');
    pointTestAssert(array_sum(array_column($fresh->ledger($customer), 'delta')) === 100, 'fresh ledger sum100');

    $page = $points->ledger($customer, null, ['limit' => 2]);
    pointTestAssert(count($page) === 2, 'ledger first page bounded');
    $next = $points->ledger($customer, null, ['before_id' => $page[1]['id_ledger'], 'limit' => 2]);
    pointTestAssert(count($next) === 1 && $next[0]['entry_type'] === 'BASE', 'ledger cursor gives remaining base entry');
    pointTestReject(fn() => $points->ledger($customer, null, ['limit' => 0]), 'invalid ledger page limit', 422);
    pointTestAssert(count($points->awards($employee, ['limit' => 1])) === 1, 'award admin page bounded');

    // Inject each write-stage failure in the real isolated database and require total rollback.
    foreach (['point_award' => 'INSERT', 'point_ledger' => 'INSERT', 'point_account' => 'UPDATE', 'activity' => 'INSERT', 'notification' => 'INSERT'] as $suffix => $operation) {
        $request = pointTestRequest($db);
        $before = [];
        foreach (['point_award', 'point_ledger', 'activity', 'notification'] as $table) {
            $before[$table] = (int) $db->value('SELECT COUNT(*) FROM ' . $db->table($table));
        }
        $trigger = 'pt_fail_' . bin2hex(random_bytes(4));
        $body = $suffix === 'point_account'
            ? "BEGIN IF NEW.balance <> OLD.balance THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Synthetic rollback injection'; END IF; END"
            : "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Synthetic rollback injection'";
        $db->execute('CREATE TRIGGER `' . $trigger . '` BEFORE ' . $operation . ' ON ' . $db->table($suffix) . ' FOR EACH ROW ' . $body);
        try {
            pointTestReject(fn() => $points->award($employee, (int) $request['id_request'], 7, 'Rollback test', 'rollback-' . $suffix), 'write stage fails');
        } finally {
            $db->execute('DROP TRIGGER `' . $trigger . '`');
        }
        foreach ($before as $table => $count) {
            pointTestAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table($table)) === $count, $suffix . ' rollback preserves ' . $table);
        }
        pointTestAssert($points->account($customer)['balance'] === 100, $suffix . ' rollback preserves balance');
    }
    foreach (['point_ledger' => 'INSERT', 'point_account' => 'UPDATE', 'activity' => 'INSERT', 'notification' => 'INSERT'] as $suffix => $operation) {
        $before = [];
        foreach (['point_ledger', 'activity', 'notification'] as $table) {
            $before[$table] = (int) $db->value('SELECT COUNT(*) FROM ' . $db->table($table));
        }
        $trigger = 'pt_fail_' . bin2hex(random_bytes(4));
        $body = $suffix === 'point_account'
            ? "BEGIN IF NEW.balance <> OLD.balance THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Synthetic rollback injection'; END IF; END"
            : "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Synthetic rollback injection'";
        $db->execute('CREATE TRIGGER `' . $trigger . '` BEFORE ' . $operation . ' ON ' . $db->table($suffix) . ' FOR EACH ROW ' . $body);
        try {
            pointTestReject(fn() => $points->correct($employee, (int) $award['id_award'], -7, 'Rollback correction', 'rollback-fix-' . $suffix), 'correction stage fails');
        } finally {
            $db->execute('DROP TRIGGER `' . $trigger . '`');
        }
        foreach ($before as $table => $count) {
            pointTestAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table($table)) === $count, $suffix . ' correction rollback preserves ' . $table);
        }
        pointTestAssert($points->account($customer)['balance'] === 100, $suffix . ' correction rollback preserves balance');
    }
    // Session variables survive rollback: fail the first two attempts, then permit commit.
    $retryRequest = pointTestRequest($db, 44);
    $trigger = 'pt_retry_' . bin2hex(random_bytes(4));
    $db->execute('SET @point_test_retry_count=0');
    $db->execute('CREATE TRIGGER `' . $trigger . '` BEFORE INSERT ON ' . $db->table('point_ledger')
        . " FOR EACH ROW BEGIN SET @point_test_retry_count=COALESCE(@point_test_retry_count,0)+1; IF @point_test_retry_count<3 THEN SIGNAL SQLSTATE '40001' SET MYSQL_ERRNO=1213,MESSAGE_TEXT='Synthetic deadlock'; END IF; END");
    try {
        $retryAward = $points->award($employee, (int) $retryRequest['id_request'], 5, 'Retry allowance', 'retry-base');
        pointTestAssert((int) $db->value('SELECT @point_test_retry_count') === 3, 'deadlock base retries twice');
        $db->execute('SET @point_test_retry_count=0');
        $points->correct($employee, (int) $retryAward['id_award'], -1, 'Retry correction', 'retry-fix');
        pointTestAssert((int) $db->value('SELECT @point_test_retry_count') === 3, 'deadlock correction retries twice');
        pointTestAssert($points->account(Actor::customer(1, 44))['balance'] === 4, 'retried writes apply once');
        pointTestAssert($points->reconcile(Actor::customer(1, 44))['consistent'] === true, 'retried writes preserve sum');
    } finally {
        $db->execute('DROP TRIGGER `' . $trigger . '`');
    }
    $trigger = 'pt_retry_limit_' . bin2hex(random_bytes(4));
    $db->execute('SET @point_test_retry_count=0');
    $db->execute('CREATE TRIGGER `' . $trigger . '` BEFORE INSERT ON ' . $db->table('point_ledger')
        . " FOR EACH ROW BEGIN SET @point_test_retry_count=COALESCE(@point_test_retry_count,0)+1; SIGNAL SQLSTATE '40001' SET MYSQL_ERRNO=1213,MESSAGE_TEXT='Synthetic persistent deadlock'; END");
    try {
        pointTestReject(fn() => $points->correct($employee, (int) $retryAward['id_award'], -1, 'Bounded retry', 'retry-bounded'), 'persistent deadlock exits');
        pointTestAssert((int) $db->value('SELECT @point_test_retry_count') === 3, 'deadlock retries bounded at three attempts');
        pointTestAssert($points->account(Actor::customer(1, 44))['balance'] === 4, 'exhausted retries preserve balance');
    } finally {
        $db->execute('DROP TRIGGER `' . $trigger . '`');
    }
    // Corrupt only the isolated projection: new award must be blocked by reconciliation.
    $db->execute('UPDATE ' . $db->table('point_account') . ' SET balance=101 WHERE id_shop=1 AND id_customer=11');
    pointTestAssert($points->reconcile($customer)['consistent'] === false, 'mismatch reported');
    $request = pointTestRequest($db);
    pointTestReject(fn() => $points->award($employee, (int) $request['id_request'], 1, 'Blocked mismatch', 'mismatch'), 'mismatch prevents award');
    pointTestReject(fn() => $points->award($employee, (int) $request['id_request'], 1, 'Blocked mismatch', 'mismatch'), 'repeated mismatch remains blocked');
    pointTestAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('activity') . " WHERE action='points.reconciliation_failed'") === 1, 'mismatch operational event bounded per account version');
    $db->execute('UPDATE ' . $db->table('point_account') . ' SET balance=100 WHERE id_shop=1 AND id_customer=11');

    $request = pointTestRequest($db, 33);
    $max = $points->award($employee, (int) $request['id_request'], PHP_INT_MAX, 'Integer maximum', 'max');
    pointTestAssert($points->account(Actor::customer(1, 33))['balance'] === PHP_INT_MAX, 'maximum exact integer retained');
    $request = pointTestRequest($db, 33);
    pointTestReject(fn() => $points->award($employee, (int) $request['id_request'], 1, 'Overflow', 'overflow'), 'balance addition cannot overflow');
    pointTestReject(fn() => $points->correct($employee, (int) $max['id_award'], PHP_INT_MIN, 'Overflow', 'underflow'), 'correction addition cannot underflow');
    pointTestAssert($points->reconcile(Actor::customer(1, 33))['consistent'] === true, 'overflow rejection leaves sum intact');
    print "PASS points behavior: approval, idempotency, ownership, linked corrections, rollback stages, bounded deadlock retries, pagination, durable sums, overflow\n";
} finally {
    pointTestCleanup($db);
}
