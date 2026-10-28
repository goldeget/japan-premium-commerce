<?php

declare(strict_types=1);

require_once dirname(__FILE__, 3) . '/autoload.php';

use Ordenowa\Procurement\Integration\Runtime;
use Ordenowa\Procurement\Presentation\WorkspaceView;

class OrdenowaprocurementWorkspaceModuleFrontController extends ModuleFrontController
{
    public $auth = true;
    public $guestAllowed = false;
    public $ssl = true;

    public function init(): void
    {
        $this->privateHeaders();
        parent::init();
        $this->privateHeaders();
    }

    private function privateHeaders(): void
    {
        header('Cache-Control: private, no-store, no-cache, max-age=0, must-revalidate');
        header('Pragma: no-cache');
        header('Expires: 0');
        header('X-Robots-Tag: noindex, nofollow, noarchive');
        header('X-Content-Type-Options: nosniff');
        header('Referrer-Policy: same-origin');
    }

    public function setMedia(): void
    {
        parent::setMedia();
        $this->registerStylesheet('ordenowa-workspace', 'modules/ordenowaprocurement/views/css/workspace.css', ['media' => 'all', 'priority' => 200]);
    }

    public function initContent(): void
    {
        parent::initContent();
        $presenter = new WorkspaceView((string) ($this->context->language->iso_code ?? 'ja'));
        $copy = $presenter->copy();
        $data = [
            'copy' => $copy, 'view' => 'assignments', 'items' => [], 'item' => [], 'ledger' => [],
            'notifications' => [], 'balance' => 0, 'error' => '', 'error_status' => 0,
            'token' => (string) Tools::getToken(false), 'url' => $this->workspaceLink(),
            'account_url' => $this->context->link->getPageLink('my-account', true),
            'support_url' => $this->context->link->getPageLink('contact', true),
            'nav' => [], 'categories' => [], 'category' => '', 'q' => '', 'status' => '', 'statuses' => [],
            'next_url' => '', 'first_url' => '', 'before_id' => 0, 'search_hidden' => [],
        ];
        foreach (['assignments', 'requests', 'points', 'notifications'] as $tab) {
            $data['nav'][$tab] = $this->workspaceLink(['view' => $tab]);
        }
        try {
            if (!Runtime::procurementEnabled()) {
                throw new RuntimeException('Workspace unavailable.', 503);
            }
            // Never derive an actor, beneficiary or scope from request parameters.
            $actor = Runtime::customerActor();
            foreach (['id_customer', 'customer_id', 'recipient_id', 'id_shop'] as $forbidden) {
                if (Tools::getValue($forbidden) !== false) {
                    throw new RuntimeException('Not found.', 404);
                }
            }
            $service = Runtime::requests();
            $view = (string) Tools::getValue('view', 'assignments');
            if (!in_array($view, ['assignments', 'assignment', 'requests', 'request', 'points', 'notifications'], true)) {
                throw new RuntimeException('Not found.', 404);
            }
            $data['view'] = $view;
            $filters = [];
            if ($view === 'assignments' || $view === 'requests') {
                $query = Tools::getValue('q', '');
                $status = Tools::getValue('status', '');
                $category = Tools::getValue('category', '');
                if (!is_string($query) || !preg_match('/\A.{0,100}\z/usD', $query) || !is_string($status) || !is_string($category)) {
                    throw new InvalidArgumentException('Invalid filters.', 422);
                }
                $statuses = $view === 'assignments' ? ['ACTIVE', 'REQUESTED', 'CANCELLED', 'EXPIRED'] : ['SUBMITTED', 'APPROVED', 'REJECTED', 'CANCELLED'];
                if (($status !== '' && !in_array($status, $statuses, true)) || ($category !== '' && !preg_match('/\A[1-9][0-9]{0,9}\z/D', $category))) {
                    throw new InvalidArgumentException('Invalid filter.', 422);
                }
                $beforeId = Tools::getValue('before_id', '') === '' ? 0 : $this->positiveInt('before_id');
                $data['q'] = trim($query);
                $data['status'] = $status;
                $data['category'] = $category;
                $data['statuses'] = $statuses;
                $data['before_id'] = $beforeId;
                $filters = ['before_id' => $beforeId, 'limit' => 51, 'q' => $data['q']];
                if ($status !== '') {
                    $filters['status'] = $status;
                }
                if ($category !== '') {
                    $filters['category_id'] = (int) $category;
                }
                $params = ['view' => $view, 'q' => $data['q'], 'status' => $status, 'category' => $category];
                $data['first_url'] = $this->workspaceLink($params);
                $parts = parse_url($data['url']);
                if (isset($parts['query'])) {
                    parse_str($parts['query'], $data['search_hidden']);
                }
            }
            $method = strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? 'GET'));
            if ($method !== 'GET' && $method !== 'POST') {
                throw new RuntimeException('Invalid request.', 422);
            }
            if ($method === 'POST') {
                $provided = Tools::getValue('token');
                if (!is_string($provided) || !hash_equals((string) Tools::getToken(false), $provided)) {
                    throw new RuntimeException('Invalid token.', 403);
                }
                $id = $this->positiveInt('id_assignment');
                $version = $this->positiveInt('version');
                $quantity = $this->positiveInt('quantity');
                $action = Tools::getValue('action');
                if ($action === 'submit') {
                    $key = Tools::getValue('idempotency_key');
                    if (!is_string($key) || !preg_match('/\A[a-f0-9]{64}\z/D', $key)) {
                        throw new InvalidArgumentException('Invalid request key.', 422);
                    }
                    $request = $service->submit($actor, $id, $version, $quantity, $key);
                    Tools::redirect($this->workspaceLink(['view' => 'request', 'id_request' => (int) $request['id_request']]));
                    return;
                }
                if ($action !== 'confirm') {
                    throw new InvalidArgumentException('Invalid action.', 422);
                }
                $row = $service->assignment($actor, $id);
                $item = $presenter->assignment($row);
                if (!$item['available'] || $item['version'] !== $version) {
                    throw new RuntimeException('Assignment changed.', 409);
                }
                if ($quantity > $item['max_quantity']) {
                    throw new InvalidArgumentException('Invalid quantity.', 422);
                }
                $data['view'] = 'confirm';
                $data['item'] = $item;
                $data['quantity'] = $quantity;
                $data['idempotency_key'] = bin2hex(random_bytes(32));
                $data['edit_url'] = $this->workspaceLink(['view' => 'assignment', 'id_assignment' => $id]);
            } elseif (Tools::getValue('action') !== false) {
                throw new InvalidArgumentException('Actions require POST.', 422);
            } elseif ($view === 'assignments') {
                $rows = $service->customerAssignments($actor, $filters);
                $hasNext = count($rows) > 50;
                foreach (array_slice($rows, 0, 50) as $row) {
                    $item = $presenter->assignment($row);
                    $item['url'] = $this->workspaceLink(['view' => 'assignment', 'id_assignment' => $item['id']]);
                    $data['items'][] = $item;
                }
                if ($hasNext) {
                    $data['next_url'] = $this->workspaceLink($params + ['before_id' => (int) end($data['items'])['id']]);
                }
                // Build category navigation solely from this customer's authorized snapshots.
                $categories = $presenter->categories($service->customerCategories($actor));
                $selected = $data['category'];
                if ($selected !== '' && !isset($categories[(int) $selected])) {
                    throw new RuntimeException('Not found.', 404);
                }
                foreach ($categories as &$category) {
                    $category['child'] = isset($categories[$category['parent']]);
                    $category['url'] = $this->workspaceLink(['view' => 'assignments', 'category' => $category['id'], 'q' => $data['q'], 'status' => $data['status']]);
                }
                unset($category);
                $data['categories'] = $presenter->categoryTree($categories);
                $data['category'] = $selected;
            } elseif ($view === 'assignment') {
                $data['item'] = $presenter->assignment($service->assignment($actor, $this->positiveInt('id_assignment')));
            } elseif ($view === 'requests' || $view === 'request') {
                $paid = [];
                foreach (Runtime::points()->ledger($actor) as $entry) {
                    if (($entry['entry_type'] ?? '') === 'BASE') {
                        $paid[(int) $entry['id_request']] = true;
                    }
                }
                if ($view === 'requests') {
                    $rows = $service->customerRequests($actor, $filters);
                    $hasNext = count($rows) > 50;
                    foreach (array_slice($rows, 0, 50) as $row) {
                        $item = $presenter->request($row, $paid);
                        $item['url'] = $this->workspaceLink(['view' => 'request', 'id_request' => $item['id']]);
                        $data['items'][] = $item;
                    }
                    if ($hasNext) {
                        $data['next_url'] = $this->workspaceLink($params + ['before_id' => (int) end($data['items'])['id']]);
                    }
                } else {
                    $data['item'] = $presenter->request($service->request($actor, $this->positiveInt('id_request')), $paid);
                    $data['support_url'] = $this->context->link->getModuleLink('ordenowaprocurement', 'support', ['id_request' => $data['item']['id']], true);
                }
            } elseif ($view === 'points') {
                $beforeId = Tools::getValue('before_id', '') === '' ? 0 : $this->positiveInt('before_id');
                $data['before_id'] = $beforeId;
                $ledgerFilters = ['limit' => 51];
                if ($beforeId > 0) {
                    $ledgerFilters['before_id'] = $beforeId;
                }
                $data['balance'] = (int) Runtime::points()->account($actor)['balance'];
                $rows = Runtime::points()->ledger($actor, null, $ledgerFilters);
                $hasNext = count($rows) > 50;
                foreach (array_slice($rows, 0, 50) as $row) {
                    $data['ledger'][] = [
                        'id' => (int) $row['id_ledger'], 'request_id' => (int) $row['id_request'],
                        'type' => $row['entry_type'] === 'BASE' ? $copy['point_award'] : $copy['point_correction'],
                        'delta' => (int) $row['delta'], 'original_entry' => (int) ($row['original_entry'] ?? 0),
                        'reason' => (string) $row['reason'], 'created_at' => (string) $row['created_at'],
                        'request_url' => $this->workspaceLink(['view' => 'request', 'id_request' => (int) $row['id_request']]),
                        'original_url' => !empty($row['original_entry']) ? $this->workspaceLink(['view' => 'points', 'before_id' => (int) $row['original_entry'] + 1]) . '#ow-entry-' . (int) $row['original_entry'] : '',
                    ];
                }
                $data['first_url'] = $this->workspaceLink(['view' => 'points']);
                if ($hasNext) {
                    $data['next_url'] = $this->workspaceLink(['view' => 'points', 'before_id' => (int) end($data['ledger'])['id']]);
                }
            } elseif ($view === 'notifications') {
                $beforeId = Tools::getValue('before_id', '') === '' ? 0 : $this->positiveInt('before_id');
                $data['before_id'] = $beforeId;
                $db = Runtime::database();
                $rows = $db->all('SELECT id_notification,event,target_type,target_id,created_at FROM ' . $db->table('notification')
                    . ' WHERE id_shop=' . (int) $actor->shopId . ' AND id_customer=' . (int) $actor->id
                    . ($beforeId > 0 ? ' AND id_notification<' . $beforeId : '') . ' ORDER BY id_notification DESC LIMIT 51');
                $hasNext = count($rows) > 50;
                foreach (array_slice($rows, 0, 50) as $row) {
                    $target = (string) $row['target_type'];
                    $label = $target === 'assignment' ? 'notification_assignment' : ($target === 'request' ? 'notification_request' : 'notification_points');
                    if ((string) $row['event'] === 'assignment.revoked') {
                        $label = 'notification_revoked';
                    } elseif (stripos((string) $row['event'], 'review') !== false) {
                        $label = 'notification_review';
                    }
                    $params = ['view' => 'points'];
                    if ($target === 'assignment') {
                        $params = ['view' => 'assignment', 'id_assignment' => (int) $row['target_id']];
                    } elseif ($target === 'request') {
                        $params = ['view' => 'request', 'id_request' => (int) $row['target_id']];
                    }
                    $data['notifications'][] = ['id' => (int) $row['id_notification'], 'label' => $copy[$label], 'created_at' => (string) $row['created_at'], 'url' => $this->workspaceLink($params)];
                }
                $data['first_url'] = $this->workspaceLink(['view' => 'notifications']);
                if ($hasNext) {
                    $data['next_url'] = $this->workspaceLink(['view' => 'notifications', 'before_id' => (int) end($data['notifications'])['id']]);
                }
            }
        } catch (Throwable $error) {
            $status = (int) $error->getCode();
            if ($error instanceof InvalidArgumentException) {
                $status = 422;
            }
            if (!in_array($status, [403, 404, 409, 422, 503], true)) {
                $status = 503;
            }
            http_response_code($status);
            $data['error_status'] = $status;
            $data['error'] = $copy['error_' . $status];
            $data['items'] = $data['item'] = $data['ledger'] = $data['notifications'] = [];
        }
        $page = $this->context->smarty->getTemplateVars('page');
        if (is_array($page)) {
            $page['meta']['robots'] = 'noindex, nofollow, noarchive';
            $page['canonical'] = '';
            $this->context->smarty->assign('page', $page);
        }
        $this->context->smarty->assign('ow', $data);
        $this->setTemplate('module:ordenowaprocurement/views/templates/front/workspace.tpl');
    }

    private function positiveInt(string $name): int
    {
        $value = Tools::getValue($name);
        if (!is_string($value) || !preg_match('/\A[1-9][0-9]{0,9}\z/D', $value) || (int) $value > 2147483647) {
            throw new InvalidArgumentException('Invalid integer.', 422);
        }
        return (int) $value;
    }

    private function workspaceLink(array $params = []): string
    {
        return $this->context->link->getModuleLink('ordenowaprocurement', 'workspace', $params, true);
    }
}
