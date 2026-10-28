<?php

declare(strict_types=1);
require __DIR__ . '/ci_bootstrap.php';
$fixture = ciFixture();
$db = Ordenowa\Procurement\Integration\Runtime::database();
$customer = new Customer((int) $fixture['customers']['a']['id']);
ciAssert(Validate::isLoadedObject($customer), 'Synthetic event recipient missing');
if (($argv[1] ?? '') === 'locale') {
    $locale = $argv[2] ?? '';
    ciAssert(in_array($locale, ['ja', 'en', 'ko'], true), 'Invalid synthetic test locale');
    foreach (['PS_MAIL_METHOD' => 2, 'PS_MAIL_SERVER' => 'mailpit', 'PS_MAIL_SMTP_PORT' => 1025,
        'PS_MAIL_SMTP_ENCRYPTION' => '', 'PS_MAIL_USER' => '', 'PS_MAIL_PASSWD' => '', 'PS_MAIL_TYPE' => 3] as $name => $value) {
        ciAssert(Configuration::updateValue($name, $value), 'Isolated SMTP configuration failed');
    }
    $customer->id_lang = (int) Language::getIdByIso($locale, true);
    ciAssert($customer->id_lang > 0 && $customer->update(), 'Synthetic locale update failed');
} elseif (($argv[1] ?? '') === 'verify') {
    $events = (int) $db->value('SELECT COUNT(*) FROM ' . $db->table('notification'));
    ciAssert($events === 5, 'Actual domain event count changed');
    ciAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('notification_delivery') . " WHERE channel='mail' AND status='SENT'") === $events, 'Native mail deliveries incomplete');
    ciAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('notification_delivery') . " WHERE channel='mail' AND (status<>'SENT' OR attempts<>1)") === 0, 'Native mail replay changed deliveries');
    ciAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('notification') . ' WHERE id_customer<>' . (int) $customer->id) === 0, 'Event recipient changed');
    ciAssert((int) Ordenowa\Procurement\Integration\Runtime::points()->account(Ordenowa\Procurement\Security\Actor::customer(1, (int) $customer->id))['balance'] === 80, 'Dispatch changed points');
    ciAssert((string) Language::getIsoById((int) $customer->id_lang) === 'ja', 'Synthetic recipient locale not restored');
} else {
    throw new InvalidArgumentException('Choose a fixed notification acceptance command');
}
echo "PASS native notification configuration or delivery state\n";
