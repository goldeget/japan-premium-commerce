<?php
declare(strict_types=1);

namespace Ordenowa\Procurement\Points;

use Ordenowa\Procurement\Infrastructure\Database;
use Ordenowa\Procurement\Infrastructure\Recorder;
use Ordenowa\Procurement\Security\Actor;

/** Explicit employee awards and append-only linked corrections in integer points. */
final class PointService
{
    private readonly Recorder $recorder;

    public function __construct(private readonly Database $db)
    {
        $this->recorder = new Recorder($db);
    }

    public function award(Actor $actor, int $requestId, int $amount, string $reason, string $key): array
    {
        $actor->require('points.award');
        if ($amount < 1) {
            throw new \InvalidArgumentException('Award must be a positive integer.', 422);
        }
        [$reason, $key] = $this->input($reason, $key);
        $hash = $this->hash(['BASE', $requestId, $amount, $reason]);
        return $this->mutate($actor, function () use ($actor, $requestId, $amount, $reason, $key, $hash): array {
            $request = $this->requestLock($actor, $requestId);
            $account = $this->accountLock($actor, (int) $request['id_customer']);
            $existing = $this->keyEntry($actor, $key);
            if ($existing !== null) {
                $this->samePayload($existing, $hash);
                return $this->awardRow($actor, (int) $existing['id_award']);
            }
            if ($request['status'] !== 'APPROVED') {
                throw new \RuntimeException('Request must be approved before a manual award.', 409);
            }
            $review = $this->db->one('SELECT * FROM ' . $this->db->table('review') . ' WHERE id_request=' . $requestId
                . ' AND id_shop=' . $actor->shopId . ' AND id_customer=' . (int) $request['id_customer'] . " AND decision='APPROVED'");
            if ($review === null) {
                throw new \RuntimeException('An approved review is required.', 409);
            }
            if ($this->db->one('SELECT id_award FROM ' . $this->db->table('point_award') . ' WHERE id_request=' . $requestId) !== null) {
                throw new \RuntimeException('This request has already received its base award.', 409);
            }
            $this->assertConsistent($account);
            $balance = $this->add((int) $account['balance'], $amount);
            $this->db->execute('INSERT INTO ' . $this->db->table('point_award')
                . ' (id_request,id_review,id_account,id_shop,id_customer,amount,id_ledger,id_employee,created_at) VALUES ('
                . $requestId . ',' . (int) $review['id_review'] . ',' . (int) $account['id_account'] . ',' . $actor->shopId
                . ',' . (int) $request['id_customer'] . ',' . $amount . ',NULL,' . $actor->id . ',UTC_TIMESTAMP())');
            $awardId = $this->db->insertId();
            $ledgerId = $this->insertLedger($actor, $account, $awardId, 'BASE', $amount, null, $reason, $key, $hash);
            $this->db->execute('UPDATE ' . $this->db->table('point_award') . ' SET id_ledger=' . $ledgerId . ' WHERE id_award=' . $awardId);
            $this->updateBalance($account, $balance);
            $this->recorder->audit($actor, 'points.awarded', 'point_ledger', $ledgerId, ['id_request' => $requestId, 'id_award' => $awardId, 'id_account' => (int) $account['id_account']]);
            $this->recorder->notify($actor->shopId, (int) $request['id_customer'], 'points.awarded', 'point_ledger', $ledgerId);
            return $this->awardRow($actor, $awardId);
        });
    }

    public function correct(Actor $actor, int $awardId, int $delta, string $reason, string $key): array
    {
        $actor->require('points.correct');
        if ($delta === 0) {
            throw new \InvalidArgumentException('Correction must be a nonzero integer.', 422);
        }
        [$reason, $key] = $this->input($reason, $key);
        $hash = $this->hash(['CORRECTION', $awardId, $delta, $reason]);
        return $this->mutate($actor, function () use ($actor, $awardId, $delta, $reason, $key, $hash): array {
            // Read the immutable anchor, then take exactly the same request -> account locks as award().
            $award = $this->awardRow($actor, $awardId);
            $request = $this->requestLock($actor, (int) $award['id_request']);
            $account = $this->accountLock($actor, (int) $request['id_customer']);
            if ((int) $award['id_account'] !== (int) $account['id_account'] || (int) $award['id_customer'] !== (int) $request['id_customer']) {
                throw new \RuntimeException('Award ownership does not match its request.', 503);
            }
            $existing = $this->keyEntry($actor, $key);
            if ($existing !== null) {
                $this->samePayload($existing, $hash);
                return $this->ledgerRow($actor, (int) $existing['id_ledger']);
            }
            $this->assertConsistent($account);
            $base = $this->db->one('SELECT * FROM ' . $this->db->table('point_ledger') . ' WHERE id_ledger=' . (int) $award['id_ledger']
                . ' AND id_award=' . $awardId . ' AND id_account=' . (int) $account['id_account'] . " AND entry_type='BASE'");
            if ($base === null || (int) $base['delta'] !== (int) $award['amount']) {
                throw new \RuntimeException('Original award entry is unavailable.', 503);
            }
            $net = $this->integer($this->db->value('SELECT COALESCE(SUM(delta),0) FROM ' . $this->db->table('point_ledger') . ' WHERE id_award=' . $awardId . ' FOR UPDATE'));
            $nextNet = $this->add($net, $delta);
            if ($nextNet < 0 || $nextNet > (int) $award['amount']) {
                throw new \InvalidArgumentException('Correction must keep the award total within its original amount.', 422);
            }
            $balance = $this->add((int) $account['balance'], $delta);
            if ($balance < 0) {
                throw new \InvalidArgumentException('Correction would create a negative balance.', 422);
            }
            $ledgerId = $this->insertLedger($actor, $account, $awardId, 'CORRECTION', $delta, (int) $award['id_ledger'], $reason, $key, $hash);
            $this->updateBalance($account, $balance);
            $this->recorder->audit($actor, 'points.corrected', 'point_ledger', $ledgerId, ['id_request' => (int) $award['id_request'], 'id_award' => $awardId, 'id_account' => (int) $account['id_account']]);
            $this->recorder->notify($actor->shopId, (int) $account['id_customer'], 'points.corrected', 'point_ledger', $ledgerId);
            return $this->ledgerRow($actor, $ledgerId);
        });
    }

    public function account(Actor $actor, ?int $customerId = null): array
    {
        $customerId = $this->customer($actor, $customerId);
        $row = $this->db->one('SELECT * FROM ' . $this->db->table('point_account') . ' WHERE id_shop=' . $actor->shopId . ' AND id_customer=' . $customerId);
        return $row === null ? ['id_account' => null, 'id_shop' => $actor->shopId, 'id_customer' => $customerId, 'balance' => 0, 'version' => 0] : $this->numbers($row);
    }

    public function ledger(Actor $actor, ?int $customerId = null, array $filters = []): array
    {
        $customerId = $this->customer($actor, $customerId);
        [$cursor, $limit] = $this->page($filters, 'l.id_ledger');
        return array_map($this->numbers(...), $this->db->all('SELECT l.*,a.id_request FROM ' . $this->db->table('point_ledger') . ' l INNER JOIN '
            . $this->db->table('point_award') . ' a ON a.id_award=l.id_award AND a.id_shop=l.id_shop AND a.id_customer=l.id_customer'
            . ' WHERE l.id_shop=' . $actor->shopId . ' AND l.id_customer=' . $customerId . $cursor . ' ORDER BY l.id_ledger DESC' . $limit));
    }

    public function awards(Actor $actor, array $filters = []): array
    {
        $actor->require('points.read');
        [$cursor, $limit] = $this->page($filters, 'id_award');
        return array_map($this->numbers(...), $this->db->all('SELECT * FROM ' . $this->db->table('point_award') . ' WHERE id_shop=' . $actor->shopId . $cursor . ' ORDER BY id_award DESC' . $limit));
    }

    public function reconcile(Actor $actor, ?int $customerId = null): array
    {
        // A single SQL snapshot avoids reporting a mismatch across two concurrent commits.
        $customerId = $this->customer($actor, $customerId);
        $scope = 'id_shop=' . $actor->shopId . ' AND id_customer=' . $customerId;
        $row = $this->db->one('SELECT a.id_account,COALESCE(a.balance,0) AS balance,t.ledger_sum,t.ledger_count FROM '
            . '(SELECT COALESCE(SUM(delta),0) AS ledger_sum,COUNT(*) AS ledger_count FROM ' . $this->db->table('point_ledger') . ' WHERE ' . $scope . ') t'
            . ' LEFT JOIN ' . $this->db->table('point_account') . ' a ON a.id_shop=' . $actor->shopId . ' AND a.id_customer=' . $customerId);
        $balance = $this->integer($row['balance']);
        $sum = $this->integer($row['ledger_sum']);
        return ['id_account' => $row['id_account'] === null ? null : (int) $row['id_account'], 'balance' => $balance, 'ledger_sum' => $sum, 'consistent' => $balance === $sum && ($row['id_account'] !== null || (int) $row['ledger_count'] === 0)];
    }

    private function page(array $filters, string $column): array
    {
        foreach (['before_id', 'limit'] as $field) {
            if (isset($filters[$field]) && (!is_int($filters[$field]) || $filters[$field] < 1 || ($field === 'limit' && $filters[$field] > 101))) {
                throw new \InvalidArgumentException('Invalid point history pagination.', 422);
            }
        }
        return [isset($filters['before_id']) ? ' AND ' . $column . '<' . $filters['before_id'] : '', isset($filters['limit']) ? ' LIMIT ' . $filters['limit'] : ''];
    }

    private function customer(Actor $actor, ?int $customerId): int
    {
        if ($actor->type === 'customer') {
            if ($customerId !== null && $customerId !== $actor->id) {
                throw new \RuntimeException('Point account not found.', 404);
            }
            return $actor->id;
        }
        $actor->require('points.read');
        if ($customerId === null || $customerId < 1) {
            throw new \InvalidArgumentException('Choose a customer account.', 422);
        }
        return $customerId;
    }

    private function requestLock(Actor $actor, int $id): array
    {
        $request = $this->db->one('SELECT * FROM ' . $this->db->table('request') . ' WHERE id_request=' . $id . ' AND id_shop=' . $actor->shopId . ' FOR UPDATE');
        if ($request === null) {
            throw new \RuntimeException('Request not found.', 404);
        }
        return $request;
    }

    private function accountLock(Actor $actor, int $customer): array
    {
        $this->db->execute('INSERT INTO ' . $this->db->table('point_account') . ' (id_shop,id_customer,balance,version,updated_at) VALUES ('
            . $actor->shopId . ',' . $customer . ',0,1,UTC_TIMESTAMP()) ON DUPLICATE KEY UPDATE id_account=id_account');
        $account = $this->db->one('SELECT * FROM ' . $this->db->table('point_account') . ' WHERE id_shop=' . $actor->shopId . ' AND id_customer=' . $customer . ' FOR UPDATE');
        if ($account === null) {
            throw new \RuntimeException('Point account unavailable.', 503);
        }
        return $this->numbers($account);
    }

    private function assertConsistent(array $account): void
    {
        $sum = $this->integer($this->db->value('SELECT COALESCE(SUM(delta),0) FROM ' . $this->db->table('point_ledger') . ' WHERE id_shop=' . (int) $account['id_shop'] . ' AND id_customer=' . (int) $account['id_customer'] . ' FOR UPDATE'));
        if ($sum !== (int) $account['balance'] || $sum < 0) {
            throw new BalanceMismatch((int) $account['id_account'], (int) $account['version']);
        }
    }

    private function mutate(Actor $actor, callable $operation): array
    {
        try {
            for ($attempt = 0; ; ++$attempt) {
                try {
                    return $this->db->transaction($operation);
                } catch (\Throwable $error) {
                    if ($attempt >= 2 || !$this->retryable($error)) {
                        throw $error;
                    }
                }
            }
        } catch (BalanceMismatch $error) {
            // The blocked operation is rolled back first. Leave an operator-visible audit signal without balance data.
            $this->db->transaction(function () use ($actor, $error): void {
                $this->db->one('SELECT id_account FROM ' . $this->db->table('point_account') . ' WHERE id_account=' . $error->accountId . ' AND id_shop=' . $actor->shopId . ' FOR UPDATE');
                $safe = $this->db->quote(json_encode(['version' => $error->version], JSON_THROW_ON_ERROR));
                $exists = $this->db->one('SELECT id_activity FROM ' . $this->db->table('activity') . ' WHERE id_shop=' . $actor->shopId
                    . " AND action='points.reconciliation_failed' AND target_type='point_account' AND target_id=" . $error->accountId . ' AND safe_data=' . $safe . ' LIMIT 1');
                if ($exists === null) {
                    $this->recorder->audit($actor, 'points.reconciliation_failed', 'point_account', $error->accountId, ['version' => $error->version]);
                }
            });
            throw $error;
        }
    }

    private function retryable(\Throwable $error): bool
    {
        // Every callback effect belongs to the rolled-back database transaction.
        do {
            if (in_array((string) $error->getCode(), ['1213', '1205', '40001'], true)) {
                return true;
            }
            if ($error instanceof \PDOException && in_array((int) ($error->errorInfo[1] ?? 0), [1213, 1205], true)) {
                return true;
            }
            $error = $error->getPrevious();
        } while ($error !== null);
        return false;
    }

    private function keyEntry(Actor $actor, string $key): ?array
    {
        return $this->db->one('SELECT * FROM ' . $this->db->table('point_ledger') . ' WHERE id_shop=' . $actor->shopId . ' AND idempotency_key=' . $this->db->quote($key) . ' FOR UPDATE');
    }

    private function samePayload(array $existing, string $hash): void
    {
        if (!hash_equals((string) $existing['payload_hash'], $hash)) {
            throw new \RuntimeException('Idempotency key payload conflict.', 409);
        }
    }

    private function awardRow(Actor $actor, int $id): array
    {
        $row = $this->db->one('SELECT * FROM ' . $this->db->table('point_award') . ' WHERE id_award=' . $id . ' AND id_shop=' . $actor->shopId);
        if ($row === null) {
            throw new \RuntimeException('Award not found.', 404);
        }
        return $this->numbers($row);
    }

    private function ledgerRow(Actor $actor, int $id): array
    {
        $row = $this->db->one('SELECT l.*,a.id_request FROM ' . $this->db->table('point_ledger') . ' l INNER JOIN ' . $this->db->table('point_award')
            . ' a ON a.id_award=l.id_award WHERE l.id_ledger=' . $id . ' AND l.id_shop=' . $actor->shopId);
        if ($row === null) {
            throw new \RuntimeException('Ledger entry not found.', 404);
        }
        return $this->numbers($row);
    }

    private function insertLedger(Actor $actor, array $account, int $awardId, string $type, int $delta, ?int $original, string $reason, string $key, string $hash): int
    {
        $this->db->execute('INSERT INTO ' . $this->db->table('point_ledger')
            . ' (id_account,id_award,id_shop,id_customer,entry_type,delta,original_entry,reason,id_employee,idempotency_key,payload_hash,created_at) VALUES ('
            . (int) $account['id_account'] . ',' . $awardId . ',' . $actor->shopId . ',' . (int) $account['id_customer'] . ',' . $this->db->quote($type)
            . ',' . $delta . ',' . ($original ?? 'NULL') . ',' . $this->db->quote($reason) . ',' . $actor->id . ',' . $this->db->quote($key)
            . ',' . $this->db->quote($hash) . ',UTC_TIMESTAMP())');
        return $this->db->insertId();
    }

    private function updateBalance(array $account, int $balance): void
    {
        $this->db->execute('UPDATE ' . $this->db->table('point_account') . ' SET balance=' . $balance . ',version=version+1,updated_at=UTC_TIMESTAMP() WHERE id_account=' . (int) $account['id_account']);
    }

    private function input(string $reason, string $key): array
    {
        $reason = trim($reason);
        if ($reason === '' || strlen($reason) > 4000 || preg_match('//u', $reason) !== 1) {
            throw new \InvalidArgumentException('A valid correction or award reason is required.', 422);
        }
        if (preg_match('/^[A-Za-z0-9._:-]{1,128}$/D', $key) !== 1) {
            throw new \InvalidArgumentException('A valid idempotency key is required.', 422);
        }
        return [$reason, $key];
    }

    private function hash(array $payload): string
    {
        return hash('sha256', json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));
    }

    private function add(int $a, int $b): int
    {
        if (($b > 0 && $a > PHP_INT_MAX - $b) || ($b < 0 && $a < PHP_INT_MIN - $b)) {
            throw new \InvalidArgumentException('Integer point limit exceeded.', 422);
        }
        return $a + $b;
    }

    private function integer(mixed $value): int
    {
        $text = (string) $value;
        $number = filter_var($text, FILTER_VALIDATE_INT);
        if ($number === false) {
            throw new \RuntimeException('Stored point integer is outside supported limits.', 503);
        }
        return $number;
    }

    private function numbers(array $row): array
    {
        foreach (['id_account', 'id_award', 'id_request', 'id_review', 'id_shop', 'id_customer', 'id_ledger', 'id_employee', 'original_entry', 'amount', 'balance', 'delta', 'version'] as $field) {
            if (isset($row[$field])) {
                $row[$field] = $this->integer($row[$field]);
            }
        }
        return $row;
    }
}
