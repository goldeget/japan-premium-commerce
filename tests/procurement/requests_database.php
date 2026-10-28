<?php
declare(strict_types=1);
require __DIR__ . '/requests_bootstrap.php';

use Ordenowa\Procurement\Infrastructure\Database;
use Ordenowa\Procurement\Security\Actor;

// The native PrestaShop Db cannot be booted without the application install. This
// boundary spy specifically catches accidental cached reads or getRow LIMITs.
$native = new class {
    public array $reads = [];
    public array $writes = [];
    public function executeS(string $sql, bool $array = true, bool $cache = true): array
    {
        $this->reads[] = [$sql, $array, $cache];
        return [['value'=>'7']];
    }
    public function execute(string $sql, bool $cache = true): bool
    {
        $this->writes[] = [$sql, $cache];
        return true;
    }
    public function escape(string $value, bool $html = false): string { return addslashes($value); }
    public function Insert_ID(): int { return 12; }
};
$db = new Database($native, 'ps_');
requestsAssert($db->table('request') === '`ps_ordenowa_procurement_request`', 'Dedicated domain namespace');
$sql = 'SELECT id_request FROM requests LIMIT 1 FOR UPDATE';
requestsAssert($db->value($sql) === '7' && $native->reads[0] === [$sql,true,false], 'Native locking reads bypass cache and preserve caller SQL');
$db->transaction(static function (Database $db): void {
    $db->transaction(static function (Database $db): void { $db->execute('SELECT 1'); });
});
requestsAssert(array_column($native->writes, 0) === ['START TRANSACTION','SAVEPOINT ordenowa_1','SELECT 1','RELEASE SAVEPOINT ordenowa_1','COMMIT'], 'Nested native transaction boundaries');
requestsAssert(count(array_filter(array_column($native->writes, 1))) === 0, 'Native writes bypass cache');
requestsAssert($db->insertId() === 12, 'Native insert id');
requestsReject(fn () => $db->table('request;DROP'), 422, 'Table identifier guard');
requestsReject(fn () => (new Database($native, str_repeat('x', 64)))->table('request'), 422, 'MariaDB identifier length guard');
requestsReject(fn () => Actor::customer(1, 2)->require('points.award'), 403, 'Customer employee permission denied');
requestsReject(fn () => Actor::employee(1, 2, ['points.read'])->require('points.award'), 403, 'Exact permission required');
fwrite(STDOUT, "PASS requests native database adapter and Actor boundary tests\n");
