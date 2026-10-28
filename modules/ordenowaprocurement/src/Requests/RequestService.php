<?php
declare(strict_types=1);

namespace Ordenowa\Procurement\Requests;

use Ordenowa\Procurement\Infrastructure\Database;
use Ordenowa\Procurement\Infrastructure\Recorder;
use Ordenowa\Procurement\Security\Actor;

final class RequestService
{
    private Recorder $recorder;

    public function __construct(private readonly Database $db)
    {
        $this->recorder = new Recorder($db);
    }

    public function createAssignment(Actor $actor, int $customerId, array $trustedProduct, array $input): array
    {
        $actor->require('procurement.manage');
        if ($customerId < 1) { $this->invalid('A verified customer is required.'); }
        $product = $this->productSnapshot($actor, $trustedProduct);
        $default = $this->quantityInput($input['default_quantity'] ?? 1);
        $max = $this->quantityInput($input['max_quantity'] ?? 1);
        if ($default > $max) { $this->invalid('Default quantity exceeds the allowed quantity.'); }
        $instructions = $this->text($input['instructions'] ?? '', 10000, false);
        $deadline = $input['deadline'] ?? null;
        if ($deadline === '') { $deadline = null; }
        if ($deadline !== null) {
            if (!is_string($deadline)) { $this->invalid('Invalid deadline.'); }
            $date = \DateTimeImmutable::createFromFormat('!Y-m-d H:i:s', $deadline, new \DateTimeZone('UTC'));
            if (!$date || $date->format('Y-m-d H:i:s') !== $deadline) { $this->invalid('Invalid UTC deadline.'); }
        }
        return $this->db->transaction(function () use ($actor, $customerId, $product, $default, $max, $instructions, $deadline): array {
            $this->db->execute('INSERT INTO ' . $this->db->table('assignment')
                . ' (id_shop,id_customer,id_product,id_product_attribute,product_snapshot,default_quantity,max_quantity,instructions,deadline,status,version,id_employee,issued_at) VALUES ('
                . $actor->shopId . ',' . $customerId . ',' . $product['id_product'] . ',' . $product['id_product_attribute'] . ','
                . $this->db->quote(json_encode($product, JSON_THROW_ON_ERROR)) . ',' . $default . ',' . $max . ',' . $this->db->quote($instructions) . ','
                . ($deadline === null ? 'NULL' : $this->db->quote($deadline)) . ",'ACTIVE',1," . $actor->id . ',UTC_TIMESTAMP())');
            $id = $this->db->insertId();
            $this->recorder->audit($actor, 'assignment.created', 'assignment', $id, ['version'=>1]);
            $this->recorder->notify($actor->shopId, $customerId, 'assignment.created', 'assignment', $id);
            return $this->hydrate($this->assignmentRow($actor, $id));
        });
    }

    public function revokeAssignment(Actor $actor, int $id, int $version, string $reason): array
    {
        $actor->require('procurement.manage');
        $reason = $this->text($reason, 2000, true);
        return $this->db->transaction(function () use ($actor, $id, $version, $reason): array {
            $row = $this->assignmentRow($actor, $id, true);
            $this->pendingAssignment($row, $version);
            $this->db->execute('UPDATE ' . $this->db->table('assignment') . " SET status='CANCELLED',version=version+1,cancelled_reason="
                . $this->db->quote($reason) . ' WHERE id_assignment=' . $id . ' AND id_shop=' . $actor->shopId);
            $this->recorder->audit($actor, 'assignment.revoked', 'assignment', $id, ['version'=>$version+1]);
            $this->recorder->notify($actor->shopId, (int)$row['id_customer'], 'assignment.revoked', 'assignment', $id);
            return $this->hydrate($this->assignmentRow($actor, $id));
        });
    }

    public function customerAssignments(Actor $actor, array $filters = []): array
    {
        $this->customer($actor);
        return array_map([$this, 'hydrate'], $this->db->all('SELECT * FROM ' . $this->db->table('assignment')
            . ' WHERE id_shop=' . $actor->shopId . ' AND id_customer=' . $actor->id . $this->filters($filters, 'id_assignment')
            . ' ORDER BY id_assignment DESC LIMIT ' . $this->limit($filters)));
    }

    public function adminAssignments(Actor $actor, array $filters = []): array
    {
        $actor->require('procurement.read');
        return array_map([$this, 'hydrate'], $this->db->all('SELECT * FROM ' . $this->db->table('assignment')
            . ' WHERE id_shop=' . $actor->shopId . $this->filters($filters, 'id_assignment')
            . ' ORDER BY id_assignment DESC LIMIT ' . $this->limit($filters)));
    }

    public function customerCategories(Actor $actor): array
    {
        $this->customer($actor);
        $categories = [];
        // Enumerate categories independently of list pagination and client filters.
        foreach ($this->db->all("SELECT JSON_EXTRACT(product_snapshot,'$.categories') AS categories FROM " . $this->db->table('assignment') . ' WHERE id_shop='
            . $actor->shopId . ' AND id_customer=' . $actor->id) as $row) {
            $items = $row['categories'] === null ? [] : json_decode($row['categories'], true, 32, JSON_THROW_ON_ERROR);
            foreach ($items ?? [] as $category) { $categories[(int)$category['id_category']] = $category; }
        }
        ksort($categories);
        return array_values($categories);
    }

    public function assignment(Actor $actor, int $id): array
    {
        $this->readPermission($actor);
        return $this->hydrate($this->assignmentRow($actor, $id));
    }

    public function submit(Actor $actor, int $id, int $version, int $quantity, string $key): array
    {
        $this->customer($actor);
        $this->key($key);
        return $this->db->transaction(function () use ($actor, $id, $version, $quantity, $key): array {
            // Submission and revocation serialize on the same immutable assignment owner.
            $assignment = $this->assignmentRow($actor, $id, true);
            $hash = hash('sha256', json_encode([$actor->shopId,$actor->id,$id,$version,$quantity], JSON_THROW_ON_ERROR));
            $existing = $this->db->one('SELECT * FROM ' . $this->db->table('request') . ' WHERE id_shop=' . $actor->shopId
                . ' AND id_customer=' . $actor->id . ' AND (id_assignment=' . $id . ' OR idempotency_key=' . $this->db->quote($key) . ') ORDER BY id_request LIMIT 1');
            if ($existing !== null) {
                if ((int)$existing['id_assignment'] === $id && hash_equals($existing['idempotency_key'], $key) && hash_equals($existing['payload_hash'], $hash)) {
                    return $this->request($actor, (int)$existing['id_request']);
                }
                $this->conflict('This assignment or submission key has already been used.');
            }
            $this->pendingAssignment($assignment, $version);
            if ($quantity < 1 || $quantity > (int)$assignment['max_quantity']) { $this->invalid('Quantity is outside the assigned range.'); }
            $this->db->execute('INSERT INTO ' . $this->db->table('request')
                . ' (id_assignment,id_shop,id_customer,product_snapshot,instructions,quantity,status,version,idempotency_key,payload_hash,submitted_at) VALUES ('
                . $id . ',' . $actor->shopId . ',' . $actor->id . ',' . $this->db->quote($assignment['product_snapshot']) . ','
                . $this->db->quote($assignment['instructions']) . ',' . $quantity . ",'SUBMITTED',1," . $this->db->quote($key) . ',' . $this->db->quote($hash) . ',UTC_TIMESTAMP())');
            $requestId = $this->db->insertId();
            $this->db->execute('UPDATE ' . $this->db->table('assignment') . " SET status='REQUESTED',version=version+1 WHERE id_assignment=" . $id . ' AND id_shop=' . $actor->shopId);
            $this->recorder->audit($actor, 'request.submitted', 'request', $requestId, ['id_assignment'=>$id,'version'=>1]);
            $this->recorder->notify($actor->shopId, $actor->id, 'request.submitted', 'request', $requestId);
            return $this->request($actor, $requestId);
        });
    }

    public function customerRequests(Actor $actor, array $filters = []): array
    {
        $this->customer($actor);
        return $this->requestList($actor, true, $filters);
    }

    public function adminRequests(Actor $actor, array $filters = []): array
    {
        $actor->require('procurement.read');
        return $this->requestList($actor, false, $filters);
    }

    public function request(Actor $actor, int $id): array
    {
        $this->readPermission($actor);
        return $this->hydrate($this->requestRow($actor, $id));
    }

    public function review(Actor $actor, int $id, int $version, string $decision, string $reason): array
    {
        if ($decision === 'CANCELLED') {
            try { $actor->require('procurement.review'); } catch (\RuntimeException $denied) { $actor->require('procurement.manage'); }
        } else {
            $actor->require('procurement.review');
        }
        if (!in_array($decision, ['APPROVED','REJECTED','CANCELLED'], true)) { $this->invalid('Invalid final decision.'); }
        $reason = $this->text($reason, 2000, true);
        return $this->db->transaction(function () use ($actor, $id, $version, $decision, $reason): array {
            $row = $this->requestRow($actor, $id, true);
            if ($row['status'] !== 'SUBMITTED' || (int)$row['version'] !== $version) { $this->conflict('The request is stale or already final.'); }
            $this->db->execute('INSERT INTO ' . $this->db->table('review')
                . ' (id_request,id_shop,id_customer,decision,reason,id_employee,reviewed_at) VALUES (' . $id . ',' . $actor->shopId . ','
                . (int)$row['id_customer'] . ',' . $this->db->quote($decision) . ',' . $this->db->quote($reason) . ',' . $actor->id . ',UTC_TIMESTAMP())');
            $reviewId = $this->db->insertId();
            $this->db->execute('UPDATE ' . $this->db->table('request') . ' SET status=' . $this->db->quote($decision)
                . ',version=version+1 WHERE id_request=' . $id . ' AND id_shop=' . $actor->shopId);
            $this->recorder->audit($actor, 'request.reviewed', 'request', $id, ['id_review'=>$reviewId,'decision'=>$decision,'version'=>$version+1]);
            $this->recorder->notify($actor->shopId, (int)$row['id_customer'], 'request.reviewed', 'request', $id);
            return $this->hydrate($this->requestRow($actor, $id));
        });
    }

    private function assignmentRow(Actor $actor, int $id, bool $lock = false): array
    {
        $row = $this->db->one('SELECT * FROM ' . $this->db->table('assignment') . ' WHERE id_assignment=' . $id
            . ' AND id_shop=' . $actor->shopId . ($actor->type === 'customer' ? ' AND id_customer=' . $actor->id : '')
            . ' LIMIT 1' . ($lock ? ' FOR UPDATE' : ''));
        if ($row === null) { throw new \RuntimeException('Assignment not found.', 404); }
        return $row;
    }

    private function requestRow(Actor $actor, int $id, bool $lock = false): array
    {
        // A locking read touches the request only; nullable joins are read after the lock.
        $row = $this->db->one('SELECT r.* FROM ' . $this->db->table('request') . ' r WHERE r.id_request=' . $id
            . ' AND r.id_shop=' . $actor->shopId . ($actor->type === 'customer' ? ' AND r.id_customer=' . $actor->id : '')
            . ' LIMIT 1' . ($lock ? ' FOR UPDATE' : ''));
        if ($row === null) { throw new \RuntimeException('Request not found.', 404); }
        $review = $this->db->one('SELECT id_review,reason,reviewed_at FROM ' . $this->db->table('review') . ' WHERE id_request=' . $id
            . ' AND id_shop=' . $actor->shopId . ' LIMIT 1');
        $row['id_review'] = $review === null ? null : (int)$review['id_review'];
        $row['review_reason'] = $review['reason'] ?? null;
        $row['reviewed_at'] = $review['reviewed_at'] ?? null;
        return $row;
    }

    private function requestList(Actor $actor, bool $customer, array $filters): array
    {
        $unawarded = $filters['unawarded'] ?? false;
        if (!is_bool($unawarded) || ($customer && $unawarded)) { $this->invalid('Invalid pending award filter.'); }
        $rows = $this->db->all('SELECT r.*,v.id_review,v.reason AS review_reason,v.reviewed_at FROM ' . $this->db->table('request') . ' r LEFT JOIN '
            . $this->db->table('review') . ' v ON v.id_request=r.id_request AND v.id_shop=r.id_shop WHERE r.id_shop=' . $actor->shopId
            . ($customer ? ' AND r.id_customer=' . $actor->id : '') . $this->filters($filters, 'id_request', 'r.')
            . ($unawarded ? ' AND NOT EXISTS (SELECT 1 FROM ' . $this->db->table('point_award') . ' pa WHERE pa.id_request=r.id_request AND pa.id_shop=r.id_shop AND pa.id_customer=r.id_customer)' : '')
            . ' ORDER BY r.id_request DESC LIMIT ' . $this->limit($filters));
        return array_map([$this, 'hydrate'], $rows);
    }

    private function hydrate(array $row): array
    {
        $row['product_snapshot'] = json_decode($row['product_snapshot'], true, 32, JSON_THROW_ON_ERROR);
        $row['product'] = $row['product_snapshot'];
        foreach (['id_assignment','id_request','id_customer','id_shop','id_product','id_product_attribute','default_quantity','max_quantity','quantity','version','id_review'] as $field) {
            if (isset($row[$field])) { $row[$field] = (int)$row[$field]; }
        }
        if (isset($row['deadline']) && $row['status'] === 'ACTIVE' && $row['deadline'] <= gmdate('Y-m-d H:i:s')) { $row['status'] = 'EXPIRED'; }
        // Network keys and hashes are server implementation details, never customer display fields.
        unset($row['idempotency_key'], $row['payload_hash']);
        return $row;
    }

    private function pendingAssignment(array $row, int $version): void
    {
        if ($row['status'] !== 'ACTIVE' || (int)$row['version'] !== $version || ($row['deadline'] !== null && $row['deadline'] <= gmdate('Y-m-d H:i:s'))) {
            $this->conflict('The assignment is stale, recalled or expired.');
        }
    }

    private function productSnapshot(Actor $actor, array $product): array
    {
        if (($product['shop_id'] ?? null) !== $actor->shopId || !is_int($product['id_product'] ?? null) || $product['id_product'] < 1
            || !is_int($product['id_product_attribute'] ?? null) || $product['id_product_attribute'] < 0) {
            $this->invalid('A trusted product and variant in the current shop are required.');
        }
        $result = ['shop_id'=>$actor->shopId,'id_product'=>$product['id_product'],'id_product_attribute'=>$product['id_product_attribute']];
        foreach (['names'=>500,'descriptions'=>50000] as $field => $limit) {
            if (!is_array($product[$field] ?? null)) { $this->invalid('Product localization is required.'); }
            $result[$field] = [];
            foreach (['ja','en','ko'] as $locale) { $result[$field][$locale] = $this->text($product[$field][$locale] ?? '', $limit, false); }
        }
        if (implode('', $result['names']) === '') { $this->invalid('A product name is required.'); }
        foreach (['image_url'=>2048,'reference'=>255,'source_url'=>2048] as $field => $limit) {
            $result[$field] = $this->text($product[$field] ?? '', $limit, false);
        }
        foreach (['image_url','source_url'] as $field) {
            if ($result[$field] !== '' && (!filter_var($result[$field], FILTER_VALIDATE_URL) || !in_array(strtolower((string)parse_url($result[$field], PHP_URL_SCHEME)), ['https','http'], true))) {
                $this->invalid('Product URLs must be approved HTTP references.');
            }
        }
        // Optional reviewed source price is descriptive only; it never creates a payment or award amount.
        $price = $product['reference_price'] ?? '';
        $currency = $product['currency'] ?? '';
        if (!is_string($price) || !is_string($currency)
            || ($price !== '' && (!preg_match('/^[0-9]{1,12}(?:\.[0-9]{1,4})?$/D', $price) || $currency === ''))
            || ($currency !== '' && !preg_match('/^[A-Z]{3}$/D', $currency))) { $this->invalid('Invalid source reference price.'); }
        $result['reference_price'] = $price;
        $result['currency'] = $currency;
        if (isset($product['image_rights'])) {
            $rights = $product['image_rights'];
            if (!is_array($rights) || ($rights['kind'] ?? null) !== 'operator-attestation'
                || ($rights['id_employee'] ?? null) !== $actor->id || !is_array($rights['image_ids'] ?? null)
                || count($rights['image_ids']) < 1 || count($rights['image_ids']) > 20) { $this->invalid('Invalid native image rights attestation.'); }
            $attestation = $this->text($rights['attestation'] ?? '', 2000, true);
            foreach ($rights['image_ids'] as $image) {
                if (!is_int($image) || $image < 1) { $this->invalid('Invalid approved native image.'); }
            }
            $result['image_rights'] = ['kind'=>'operator-attestation','attestation'=>$attestation,
                'id_employee'=>$actor->id,'image_ids'=>array_values(array_unique($rights['image_ids']))];
        }
        $result['categories'] = [];
        if (isset($product['categories']) && (!is_array($product['categories']) || count($product['categories']) > 200)) { $this->invalid('Invalid product categories.'); }
        foreach ($product['categories'] ?? [] as $category) {
            if (!is_array($category) || !is_int($category['id_category'] ?? null) || $category['id_category'] < 1
                || !is_int($category['id_parent'] ?? null) || $category['id_parent'] < 0 || !is_array($category['names'] ?? null)) { $this->invalid('Invalid product category.'); }
            $names = [];
            foreach (['ja','en','ko'] as $locale) { $names[$locale] = $this->text($category['names'][$locale] ?? '', 500, false); }
            $result['categories'][] = ['id_category'=>$category['id_category'],'id_parent'=>$category['id_parent'],'names'=>$names];
        }
        return $result;
    }

    private function limit(array $filters): int
    {
        $limit = $filters['limit'] ?? 50;
        if (!is_int($limit) || $limit < 1 || $limit > 200) { $this->invalid('Invalid page size.'); }
        return $limit;
    }

    private function filters(array $filters, string $idField, string $alias = ''): string
    {
        $where = '';
        $before = $filters['before_id'] ?? 0;
        if (!is_int($before) || $before < 0) { $this->invalid('Invalid page cursor.'); }
        if ($before > 0) { $where .= ' AND ' . $alias . $idField . '<' . $before; }
        $status = $filters['status'] ?? null;
        $assignment = $idField === 'id_assignment';
        $statuses = $assignment ? ['ACTIVE','REQUESTED','CANCELLED','EXPIRED'] : ['SUBMITTED','APPROVED','REJECTED','CANCELLED'];
        if ($status !== null && $status !== '') {
            if (!in_array($status, $statuses, true)) { $this->invalid('Invalid status filter.'); }
            $column = $alias . 'status';
            if ($assignment) { $column = '(CASE WHEN status=\'ACTIVE\' AND deadline IS NOT NULL AND deadline<=UTC_TIMESTAMP() THEN \'EXPIRED\' ELSE status END)'; }
            $where .= ' AND ' . $column . '=' . $this->db->quote($status);
        }
        $query = $this->text($filters['q'] ?? '', 400, false);
        if (!preg_match('/\A.{0,100}\z/usD', $query)) { $this->invalid('Search is limited to 100 characters.'); }
        if ($query !== '') {
            $pattern = $this->db->quote('%' . str_replace(['=','%','_'], ['==','=%','=_'], $query) . '%');
            $matches = [];
            foreach (['names.ja','names.en','names.ko','reference'] as $path) {
                $matches[] = 'JSON_UNQUOTE(JSON_EXTRACT(' . $alias . 'product_snapshot,\'$.' . $path . '\')) LIKE ' . $pattern . " ESCAPE '='";
            }
            $where .= ' AND (' . implode(' OR ', $matches) . ')';
        }
        $category = $filters['category_id'] ?? 0;
        if (!is_int($category) || $category < 0) { $this->invalid('Invalid category filter.'); }
        if ($category > 0) {
            $where .= ' AND JSON_CONTAINS(' . $alias . "product_snapshot,JSON_OBJECT('id_category'," . $category . "),'$.categories')=1";
        }
        return $where;
    }

    private function customer(Actor $actor): void
    {
        if ($actor->type !== 'customer') { throw new \RuntimeException('Customer access required.', 403); }
    }

    private function readPermission(Actor $actor): void
    {
        if ($actor->type === 'employee') { $actor->require('procurement.read'); }
    }

    private function quantityInput(mixed $quantity): int
    {
        if (!is_int($quantity) || $quantity < 1 || $quantity > 1000000) { $this->invalid('Quantity must be an integer from 1 to 1000000.'); }
        return $quantity;
    }

    private function text(mixed $value, int $max, bool $required): string
    {
        if (!is_string($value) || strlen($value) > $max || str_contains($value, "\0") || ($required && trim($value) === '')) { $this->invalid('Invalid text field.'); }
        return $value;
    }

    private function key(string $key): void
    {
        if (!preg_match('/^[A-Za-z0-9_.:-]{1,128}$/D', $key)) { $this->invalid('A valid submission key is required.'); }
    }

    private function invalid(string $message): never { throw new \InvalidArgumentException($message, 422); }
    private function conflict(string $message): never { throw new \RuntimeException($message, 409); }
}
