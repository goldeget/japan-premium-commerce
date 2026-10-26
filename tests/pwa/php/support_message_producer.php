<?php
// Synthetic native-model boundary fixture; no PrestaShop bootstrap, provider, or network.
declare(strict_types=1);

require_once __DIR__ . '/order_history_producer.php';

use Kuranea\Push\Domain\PushOutboxService;
use Kuranea\Push\Infrastructure\SupportMessagePushProducer;

class CustomerThread extends PushNativeRecordFixture
{
    public static array $rows = [];
}

class CustomerMessage extends PushNativeRecordFixture
{
    public static array $rows = [];
    public int $id_customer_thread = 0;
    public int $id_employee = 0;
    public bool $private = false;
    public string $message = '';
    public string $file_name = '';
}

CustomerThread::$rows = [
    501 => ['id' => 501, 'id_customer' => 10, 'id_shop' => 7, 'id_lang' => 3, 'id_order' => 101],
    502 => ['id' => 502, 'id_customer' => 10, 'id_shop' => 7, 'id_lang' => 2, 'id_order' => 0],
    503 => ['id' => 503, 'id_customer' => 11, 'id_shop' => 7, 'id_lang' => 1, 'id_order' => 101],
    504 => ['id' => 504, 'id_customer' => 10, 'id_shop' => 7, 'id_lang' => 1, 'id_order' => 102],
    505 => ['id' => 505, 'id_customer' => 10, 'id_shop' => 8, 'id_lang' => 1, 'id_order' => 0],
];
CustomerMessage::$rows = [
    301 => [
        'id' => 301, 'id_customer_thread' => 501, 'id_employee' => 9, 'private' => false,
        'message' => 'SUPPORT BODY MUST NOT LEAK', 'file_name' => 'private-attachment.png',
    ],
    302 => ['id' => 302, 'id_customer_thread' => 501, 'id_employee' => 9, 'private' => true, 'message' => 'SECRET INTERNAL NOTE'],
    303 => ['id' => 303, 'id_customer_thread' => 501, 'id_employee' => 0, 'private' => false, 'message' => 'CUSTOMER SUBMISSION'],
    304 => ['id' => 304, 'id_customer_thread' => 503, 'id_employee' => 9, 'private' => false, 'message' => 'FOREIGN ORDER THREAD'],
    305 => ['id' => 305, 'id_customer_thread' => 502, 'id_employee' => 9, 'private' => false, 'message' => 'ORDERLESS STAFF REPLY'],
    306 => ['id' => 306, 'id_customer_thread' => 504, 'id_employee' => 9, 'private' => false, 'message' => 'CROSS SHOP ORDER THREAD'],
    307 => ['id' => 307, 'id_customer_thread' => 501, 'id_employee' => 9, 'private' => false, 'message' => 'DISABLED TOGGLE'],
    308 => ['id' => 308, 'id_customer_thread' => 501, 'id_employee' => 9, 'private' => false, 'message' => 'INACTIVE CUSTOMER'],
    309 => ['id' => 309, 'id_customer_thread' => 501, 'id_employee' => 9, 'private' => false, 'message' => 'GUEST CUSTOMER'],
    310 => ['id' => 310, 'id_customer_thread' => 505, 'id_employee' => 9, 'private' => false, 'message' => 'WRONG SHOP TOGGLE'],
];
Order::$rows[102] = ['id' => 102, 'id_shop' => 8, 'id_customer' => 10, 'current_state' => 2, 'id_lang' => 1];
Configuration::$values['7:ORDENOWA_PUSH_EVENT_SUPPORT'] = '1';
Configuration::$values['8:ORDENOWA_PUSH_EVENT_SUPPORT'] = '0';

$supportTargets = new FixtureTargets();
$supportTargets->rows = [
    $row(7, 10, 'support-owner'),
    $row(7, 11, 'support-other-customer'),
    $row(8, 10, 'support-other-shop'),
];
$supportOutbox = new FixtureOutbox();
$supportService = new PushOutboxService($supportOutbox, $supportTargets);
$supportProducer = new SupportMessagePushProducer($supportService);

$result = $supportProducer->record(new CustomerMessage(301));
assertOutbox($result['status'] === 'provider_unavailable', 'public employee reply records receipt with delivery disabled');
$receipt = $supportOutbox->events['7:10:support-message:301'] ?? null;
assertOutbox(
    $receipt !== null
        && $receipt['event'] === 'support'
        && $receipt['locale'] === 'ja'
        && count($receipt['recipients']) === 1
        && $supportOutbox->history === [],
    'receipt is scoped to the customer, shop, thread locale and current consent without a send attempt'
);
assertOutbox(
    $supportProducer->record(new CustomerMessage(301))['status'] === 'duplicate'
        && count($supportOutbox->events) === 1,
    'hook replay does not create a duplicate receipt'
);

foreach ([302, 303, 304, 306, 307, 308, 309, 310, 999] as $messageId) {
    if ($messageId === 307) {
        Configuration::$values['7:ORDENOWA_PUSH_EVENT_SUPPORT'] = '0';
    } elseif ($messageId === 308) {
        Configuration::$values['7:ORDENOWA_PUSH_EVENT_SUPPORT'] = '1';
        Customer::$rows[10]['active'] = false;
    } elseif ($messageId === 309) {
        Customer::$rows[10]['active'] = true;
        Customer::$rows[10]['is_guest'] = true;
    } elseif ($messageId === 310) {
        Customer::$rows[10]['is_guest'] = false;
    }
    assertOutbox($supportProducer->record(new CustomerMessage($messageId))['status'] === 'ignored', 'non-recipient support event is ignored');
}
assertOutbox($supportProducer->record((object) ['id' => 301])['status'] === 'ignored', 'non-native event object is ignored');
assertOutbox(count($supportOutbox->events) === 1, 'private, customer-authored, foreign, disabled, guest, and inactive events create no receipt');

$orderlessResult = $supportProducer->record(new CustomerMessage(305));
assertOutbox($orderlessResult['status'] === 'provider_unavailable', 'owner-bound orderless public inquiry may receive a generic support receipt');
assertOutbox(
    ($supportOutbox->events['7:10:support-message:305']['locale'] ?? null) === 'ko',
    'orderless support receipt uses the thread language'
);
$serialized = json_encode($supportOutbox->events, JSON_THROW_ON_ERROR);
foreach (['SUPPORT BODY MUST NOT LEAK', 'SECRET INTERNAL NOTE', 'private-attachment.png', 'CUSTOMER SUBMISSION'] as $privateValue) {
    assertOutbox(!str_contains($serialized, $privateValue), 'receipt contains no support content or attachment metadata');
}

echo "PASS: native support-message push producer records public staff replies only, with owner isolation and no content\n";
