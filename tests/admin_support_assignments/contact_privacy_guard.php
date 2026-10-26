<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/modules/kuraneabackoffice/vendor/autoload.php';

use Kuranea\Backoffice\Support\SupportContactAccessGuard;

// Only native object reads are replaced; the production policy and request parsing run unchanged.
class CustomerThread
{
    public static array $records = [];
    public int $id = 0;
    public int $id_shop = 0;
    public int $id_customer = 0;
    public string $token = '';
    public function __construct(int $id) { foreach (self::$records[$id] ?? [] as $key => $value) { $this->$key = $value; } }
}
class Order
{
    public static array $records = [];
    public int $id = 0;
    public int $id_shop = 0;
    public int $id_customer = 0;
    public function __construct(int $id) { foreach (self::$records[$id] ?? [] as $key => $value) { $this->$key = $value; } }
}
class Customer
{
    public static function customerExists(string $email, bool $returnId, bool $ignoreGuest): int
    {
        return strtolower($email) === 'owner@example.invalid' ? 7 : 0;
    }
}

function supportPrivacyContext(int $id, string $email, bool $logged): object
{
    $customer = new class($id, $email, $logged) {
        public function __construct(public int $id, public string $email, private bool $logged) {}
        public function isLogged(): bool { return $this->logged; }
    };
    return (object) ['shop' => (object) ['id' => 1], 'customer' => $customer];
}
function supportPrivacyExpected(bool $expected, object $context, array $query, array $post, bool $submission, string $label): void
{
    if (SupportContactAccessGuard::allows($context, $query, $post, $submission) !== $expected) {
        throw new RuntimeException($label);
    }
}
CustomerThread::$records = [
    11 => ['id' => 11, 'id_shop' => 1, 'id_customer' => 7, 'token' => 'Synthetic123'],
    12 => ['id' => 12, 'id_shop' => 2, 'id_customer' => 7, 'token' => 'Synthetic123'],
    13 => ['id' => 13, 'id_shop' => 1, 'id_customer' => 0, 'token' => 'Synthetic123'],
];
Order::$records = [21 => ['id' => 21, 'id_shop' => 1, 'id_customer' => 7]];
$privacyOwner = supportPrivacyContext(7, 'owner@example.invalid', true);
$privacyForeign = supportPrivacyContext(8, 'other@example.invalid', true);
$privacyGuest = supportPrivacyContext(0, '', false);
$privacyLink = ['id_customer_thread' => '11', 'token' => 'Synthetic123'];
supportPrivacyExpected(true, $privacyOwner, $privacyLink, [], false, 'Owner link must remain available.');
supportPrivacyExpected(false, $privacyForeign, $privacyLink, [], false, 'Valid token must not reveal another account thread.');
supportPrivacyExpected(false, $privacyGuest, $privacyLink, [], false, 'Account thread links require their owner login.');
supportPrivacyExpected(false, $privacyOwner, ['id_customer_thread' => '12'], [], false, 'Foreign shop thread must be denied.');
supportPrivacyExpected(false, $privacyOwner, ['id_customer_thread' => ['11']], [], false, 'Malformed thread IDs must be denied.');
supportPrivacyExpected(true, $privacyGuest, ['id_customer_thread' => '13', 'token' => 'Synthetic123'], [], false, 'Valid unregistered guest link remains available.');
supportPrivacyExpected(false, $privacyGuest, ['id_customer_thread' => '13', 'token' => 'wrong'], [], false, 'Guest token remains mandatory.');
supportPrivacyExpected(true, $privacyOwner, [], ['from' => 'OWNER@example.invalid', 'id_order' => '21', 'token' => 'unchanged'], true, 'Owner order reply must retain native CSRF validation.');
supportPrivacyExpected(false, $privacyForeign, [], ['from' => 'owner@example.invalid', 'id_order' => '0'], true, 'Orderless account impersonation must be denied.');
supportPrivacyExpected(false, $privacyForeign, [], ['from' => 'other@example.invalid', 'id_order' => '21'], true, 'Foreign order IDs must be rejected before normalization.');
supportPrivacyExpected(false, $privacyGuest, [], ['from' => 'owner@example.invalid'], true, 'Guest cannot impersonate an existing registered account.');
supportPrivacyExpected(false, $privacyGuest, [], ['from' => 'new@example.invalid', 'id_order' => '21'], true, 'Guest cannot attach an account order.');
supportPrivacyExpected(true, $privacyGuest, [], ['from' => 'new@example.invalid'], true, 'New guest orderless inquiry remains available.');
supportPrivacyExpected(false, $privacyForeign, ['from' => 'owner@example.invalid'], [], true, 'GET-style native submission must be guarded too.');
fwrite(STDOUT, "PASS: account-owned contact links, sender binding, order ownership, and guest privacy.\n");
