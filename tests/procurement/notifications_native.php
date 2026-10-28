<?php
declare(strict_types=1);
require_once __DIR__ . '/points_support.php';
require_once __DIR__ . '/../../modules/kuraneapush/autoload.php';

use Ordenowa\Procurement\Infrastructure\Schema;
use Ordenowa\Procurement\Notifications\NativeRecipientResolver;
use Ordenowa\Procurement\Notifications\MailTransport;
use Ordenowa\Procurement\Notifications\PushTransport;

$db = pointTestDatabase();
Schema::install($db);
$prefix = 'nn_' . bin2hex(random_bytes(4)) . '_';
try {
    $db->execute('CREATE TABLE `' . $prefix . 'customer` (id_customer INT PRIMARY KEY,id_shop INT,id_lang INT,email VARCHAR(255),active INT,deleted INT,is_guest INT) ENGINE=InnoDB');
    $db->execute('CREATE TABLE `' . $prefix . 'lang` (id_lang INT PRIMARY KEY,iso_code VARCHAR(4),active INT) ENGINE=InnoDB');
    $db->execute('CREATE TABLE `' . $prefix . 'lang_shop` (id_lang INT,id_shop INT) ENGINE=InnoDB');
    foreach ([1 => 'ja', 2 => 'en', 3 => 'ko'] as $language => $locale) {
        $customer = 10 + $language;
        $db->execute('INSERT INTO `' . $prefix . 'customer` VALUES (' . $customer . ',1,' . $language . ',' . $db->quote('synthetic-' . $locale . '@example.invalid') . ',1,0,0)');
        $db->execute('INSERT INTO `' . $prefix . 'lang` VALUES (' . $language . ',' . $db->quote($locale) . ',1)');
        $db->execute('INSERT INTO `' . $prefix . 'lang_shop` VALUES (' . $language . ',1)');
    }
    $resolver = new NativeRecipientResolver($db, $prefix);
    $sent = [];
    $transport = new MailTransport($resolver, function (array $message) use (&$sent): bool { $sent[] = $message; return true; },
        static fn(int $shop, int $language, string $view): string => 'https://workspace.example.invalid/index.php?fc=module&module=ordenowaprocurement&controller=workspace&shop=' . $shop . '&lang=' . $language . '&view=' . $view);
    foreach ([1 => 'ja', 2 => 'en', 3 => 'ko'] as $language => $locale) {
        $request = pointTestRequest($db, 10 + $language);
        $event = $db->one('SELECT * FROM ' . $db->table('notification') . " WHERE event='request.reviewed' AND target_id=" . (int) $request['id_request']);
        pointTestAssert($transport->send($event)->status === 'sent', 'native recipient eligible');
        $message = end($sent);
        pointTestAssert($message['id_lang'] === $language && $message['email'] === 'synthetic-' . $locale . '@example.invalid', 'current own customer locale/email selected');
        pointTestAssert(str_contains($message['variables']['{workspace_url_text}'], 'shop=1&lang=' . $language), 'generated link uses recipient shop and language');
        pointTestAssert(str_ends_with($message['variables']['{workspace_url_text}'], '&view=requests'), 'review link targets request workspace');
        pointTestAssert(!str_contains(json_encode($message['variables']), '@example.invalid') && !str_contains(json_encode($message['variables']), 'balance'), 'mail content excludes recipient address and point data');
    }
    $count = count($sent);
    $wrongOwner = $event;
    $wrongOwner['id_customer'] = 11;
    pointTestAssert($transport->send($wrongOwner)->status === 'skipped', 'target owner mismatch skips');
    $wrongShop = $event;
    $wrongShop['id_shop'] = 2;
    pointTestAssert($transport->send($wrongShop)->status === 'skipped', 'native shop mismatch skips');
    $db->execute('UPDATE `' . $prefix . 'customer` SET active=0 WHERE id_customer=13');
    pointTestAssert($transport->send($event)->status === 'skipped' && count($sent) === $count, 'inactive native customer not sent');
    $db->execute('UPDATE `' . $prefix . 'customer` SET active=1 WHERE id_customer=13');
    $failed = new MailTransport($resolver, static fn(array $message): bool => false, static fn(int $shop, int $language): string => 'https://workspace.example.invalid/');
    pointTestAssert($failed->send($event)->status === 'retry', 'native mail false is definite retryable failure');

    $fakePush = new class {
        public array $payloads = [];
        public int $retries = 0;
        public array $receipts = [];
        public function receive(int $shop, int $customer, string $id, object $payload): array
        {
            $incoming = json_decode($payload->toJson(), true);
            if (isset($this->receipts[$id]) && $this->receipts[$id] !== $incoming) { throw new InvalidArgumentException('Immutable receipt payload conflict'); }
            if (isset($this->receipts[$id])) { return ['status' => 'duplicate']; }
            $this->receipts[$id] = $incoming;
            $this->payloads[] = [$shop, $customer, $id, $incoming];
            return ['status' => 'completed'];
        }
        public function retry(int $shop, int $customer, string $id): array { if (!isset($this->receipts[$id])) { return ['status' => 'not_found']; } ++$this->retries; return ['status' => 'completed']; }
    };
    $push = new PushTransport($resolver, static fn(int $shop): object => $fakePush, static fn(int $shop, string $category): bool => true);
    pointTestAssert($push->send($event)->status === 'sent', 'procurement push delivered');
    pointTestAssert($fakePush->payloads[0][3] === ['event' => 'procurement', 'locale' => 'ko'], 'push exact generic enum and customer locale only');
    pointTestAssert($fakePush->payloads[0][0] === 1 && $fakePush->payloads[0][1] === 13, 'push owner exact');
    pointTestAssert($push->send($event)->status === 'sent' && $fakePush->retries === 1, 'existing push receipt retries through push outbox');
    $db->execute('UPDATE `' . $prefix . 'customer` SET id_lang=2 WHERE id_customer=13');
    pointTestAssert($push->send($event)->status === 'sent' && $fakePush->retries === 2, 'locale change retries immutable receipt without payload conflict');
    $db->execute('UPDATE `' . $prefix . 'customer` SET id_lang=3 WHERE id_customer=13');
    $award = (new \Ordenowa\Procurement\Points\PointService($db))->award(pointTestEmployee(), (int) $request['id_request'], 100, 'Synthetic allowance', 'notice-base');
    $pointEvent = $db->one('SELECT * FROM ' . $db->table('notification') . " WHERE event='points.awarded' AND target_id=" . (int) $award['id_ledger']);
    pointTestAssert($push->send($pointEvent)->status === 'sent', 'points notice delivered');
    pointTestAssert(end($fakePush->payloads)[3] === ['event' => 'points', 'locale' => 'ko'], 'points push contains no balance or amount');
    pointTestAssert($transport->send($pointEvent)->status === 'sent' && str_ends_with(end($sent)['variables']['{workspace_url_text}'], '&view=points'), 'points mail targets points workspace');
    pointTestAssert((new \Ordenowa\Procurement\Points\PointService($db))->account(\Ordenowa\Procurement\Security\Actor::customer(1, 13))['balance'] === 100, 'sending point notice preserves original balance');
    $disabled = new PushTransport($resolver, static fn(int $shop): object => $fakePush, static fn(int $shop, string $category): bool => false);
    pointTestAssert($disabled->send($event)->status === 'skipped', 'shop event setting respected');
    print "PASS notifications native adapters: JA/EN/KO owner locale/email, shop/target eligibility, generic payload/link, mail failure and push receipt retry\n";
} finally {
    foreach (['customer', 'lang', 'lang_shop'] as $table) { $db->execute('DROP TABLE IF EXISTS `' . $prefix . $table . '`'); }
    pointTestCleanup($db);
}
