<?php

declare(strict_types=1);
require __DIR__ . '/ci_bootstrap.php';
$fixture = ciFixture();
$db = Ordenowa\Procurement\Integration\Runtime::database();
$customer = (int) $fixture['customers']['a']['id'];
$request = $db->one('SELECT id_request FROM ' . $db->table('request') . ' WHERE id_shop=1 AND id_customer=' . $customer);
ciAssert($request !== null, 'Owned request missing');
$link = $db->one('SELECT id_customer_thread FROM ' . $db->table('support_link') . ' WHERE id_shop=1 AND id_customer=' . $customer . ' AND id_request=' . (int) $request['id_request']);
ciAssert($link !== null, 'Native request support mapping missing');
$thread = new CustomerThread((int) $link['id_customer_thread']);
ciAssert(Validate::isLoadedObject($thread) && (int) $thread->id_customer === $customer && (int) $thread->id_shop === 1, 'Native thread ownership changed');
$count = (int) Db::getInstance()->getValue('SELECT COUNT(*) FROM `' . _DB_PREFIX_ . 'customer_message` WHERE id_customer_thread=' . (int) $thread->id);
ciAssert($count === 1, 'Idempotent customer post created duplicate native messages');
foreach ([0 => 'SYNTHETIC_PUBLIC_REPLY', 1 => 'SYNTHETIC_PRIVATE_NOTE'] as $private => $body) {
    $message = new CustomerMessage();
    $message->id_customer_thread = (int) $thread->id;
    $message->id_employee = 1;
    $message->message = $body;
    $message->private = $private;
    $message->file_name = '';
    $message->read = 0;
    $message->user_agent = '';
    $message->ip_address = '0';
    ciAssert($message->add(), 'Native support reply create failed');
}
ciAssert($db->one('SELECT id_customer_thread FROM ' . $db->table('support_link') . ' WHERE id_shop=1 AND id_customer=' . (int) $fixture['customers']['b']['id']) === null, 'Other owner support mapping changed');
echo "PASS native request/thread ownership, idempotent post and synthetic replies\n";
