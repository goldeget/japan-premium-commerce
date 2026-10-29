<?php
declare(strict_types=1);

require_once __DIR__ . '/requests_bootstrap.php';

use Ordenowa\Procurement\Infrastructure\Database;
use Ordenowa\Procurement\Integration\PolicyService;
use Ordenowa\Procurement\Security\Actor;

// This fixture can read an existing row, but every attempted write fails.
// Placeholder rejection must happen before transaction/audit database access.
$connection = new class {
    public int $reads = 0;
    public int $writes = 0;
    public array $rows = [];
    public function executeS(string $sql, bool $array, bool $cache): array { ++$this->reads; return $this->rows; }
    public function execute(string $sql, bool $cache): bool { ++$this->writes; throw new RuntimeException('Unexpected database write'); }
};
$service = new PolicyService(new Database($connection, 'placeholder_test_'));
$editor = Actor::employee(1, 10, ['policy.read', 'policy.manage']);
$complete = PolicyService::emptyPayload();
$complete['operator_name'] = 'SYNTHETIC test operator';
$complete['support_email'] = 'synthetic-support@example.test';
foreach (PolicyService::SECTIONS as $section) {
    foreach (PolicyService::LOCALES as $locale) {
        $complete[$section][$locale] = 'SYNTHETIC test policy ' . $section . ' ' . $locale . ' {ordinary single braces}';
    }
}
requestsAssert($service->missing($complete) === [], 'Resolved policies and ordinary braces remain ready');
foreach (PolicyService::SECTIONS as $section) {
    foreach (PolicyService::LOCALES as $locale) {
        foreach (['{{operator_name}}', '{{ support_email }}', '{{retention_rules}}', '{{processors_and_countries}}', '{{dispute_procedure}}', '{{future_pending_clause}}', '{{unfinished', 'unfinished}}'] as $marker) {
            $draft = $complete;
            $draft[$section][$locale] .= ' ' . $marker;
            requestsAssert($service->missing($draft) === [$section . '.' . $locale], 'Unresolved policy text must remain unpublished');
            requestsReject(fn () => $service->save($editor, 7, $draft), 422, 'Unresolved draft cannot create policy/audit writes');
        }
    }
}
foreach (['operator_name', 'support_phone'] as $field) {
    $draft = $complete;
    $draft[$field] = '{{' . $field . '}}';
    requestsAssert($service->missing($draft) === [$field], 'Unresolved operator/contact remains unpublished');
    requestsReject(fn () => $service->save($editor, 7, $draft), 422, 'Unresolved operator/contact cannot be saved');
}
requestsAssert($connection->reads === 0 && $connection->writes === 0, 'Reject incomplete template text before any database access');

// Existing draft rows stay readable for an authorized administrator to fix,
// but are never exposed by the public policy reader.
$legacy = $complete;
$legacy['privacy']['ko'] .= ' {{retention_rules}}';
$connection->rows = [['id_policy' => '12', 'version' => '3', 'payload' => json_encode($legacy, JSON_THROW_ON_ERROR), 'created_at' => '2026-01-01 00:00:00']];
requestsAssert($service->current(1)['payload'] === $legacy, 'Existing unresolved row remains editable rather than unreadable');
requestsAssert($service->published(1) === null, 'Existing unresolved row is not a public policy');
requestsAssert($connection->writes === 0, 'Public readiness does not rewrite legacy policy history');
echo "policies_readiness: PASS unresolved drafts, zero database writes, legacy readback and ordinary braces\n";
