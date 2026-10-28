<?php

declare(strict_types=1);
require_once __DIR__ . '/points_support.php';

use Ordenowa\Procurement\Infrastructure\Database;
use Ordenowa\Procurement\Infrastructure\Schema;
use Ordenowa\Procurement\Security\Actor;
use Ordenowa\Procurement\Support\SupportService;

// Native ObjectModel seam writes into the very same real MariaDB transaction.
#[AllowDynamicProperties]
class CustomerThread {
    public static Database $db;
    public static string $prefix;
    public int $id = 0;
    public function add(): bool {
        self::$db->execute('INSERT INTO `' . self::$prefix . 'customer_thread` (id_shop,id_customer,id_lang,id_contact,id_product,id_order,email,token,status,date_add,date_upd) VALUES ('
            . $this->id_shop . ',' . $this->id_customer . ',' . $this->id_lang . ',' . $this->id_contact . ',' . $this->id_product . ',0,'
            . self::$db->quote($this->email) . ',' . self::$db->quote($this->token) . ",'open',UTC_TIMESTAMP(),UTC_TIMESTAMP())");
        $this->id = self::$db->insertId(); return true;
    }
}
#[AllowDynamicProperties]
class CustomerMessage {
    public int $id = 0;
    public function add(): bool {
        CustomerThread::$db->execute('INSERT INTO `' . CustomerThread::$prefix . 'customer_message` (id_customer_thread,id_employee,message,private,file_name,date_add,date_upd) VALUES ('
            . $this->id_customer_thread . ',0,' . CustomerThread::$db->quote($this->message) . ',0,\'\',UTC_TIMESTAMP(),UTC_TIMESTAMP())');
        $this->id = CustomerThread::$db->insertId(); return true;
    }
}
$prefix = 'sp_' . bin2hex(random_bytes(4)) . '_';
$db = new Database(pointTestConnection(), $prefix);
$nativeTables = ['customer_message', 'customer_thread', 'contact_shop', 'contact', 'customer'];
CustomerThread::$db = $db; CustomerThread::$prefix = $prefix;
try {
    Schema::install($db);
    $db->execute('CREATE TABLE `' . $prefix . 'customer` (id_customer INT PRIMARY KEY,id_shop INT,id_lang INT,email VARCHAR(255),active TINYINT,deleted TINYINT,is_guest TINYINT) ENGINE=InnoDB');
    $db->execute('CREATE TABLE `' . $prefix . 'contact` (id_contact INT PRIMARY KEY) ENGINE=InnoDB');
    $db->execute('CREATE TABLE `' . $prefix . 'contact_shop` (id_contact INT,id_shop INT) ENGINE=InnoDB');
    $db->execute('CREATE TABLE `' . $prefix . 'customer_thread` (id_customer_thread INT AUTO_INCREMENT PRIMARY KEY,id_shop INT,id_customer INT,id_lang INT,id_contact INT,id_product INT,id_order INT,email VARCHAR(255),token CHAR(12),status VARCHAR(20),date_add DATETIME,date_upd DATETIME) ENGINE=InnoDB');
    $db->execute('CREATE TABLE `' . $prefix . 'customer_message` (id_customer_message INT AUTO_INCREMENT PRIMARY KEY,id_customer_thread INT,id_employee INT,message TEXT,private TINYINT,file_name VARCHAR(32),date_add DATETIME,date_upd DATETIME) ENGINE=InnoDB');
    $db->execute('INSERT INTO `' . $prefix . "customer` VALUES (11,1,1,'owner@example.test',1,0,0),(12,1,1,'other@example.test',1,0,0),(13,2,1,'shop2@example.test',1,0,0)");
    $db->execute('INSERT INTO `' . $prefix . 'contact` VALUES (1)');
    $db->execute('INSERT INTO `' . $prefix . 'contact_shop` VALUES (1,1),(1,2)');
    $request = pointTestRequest($db, 11, 'SUBMITTED');
    $id = (int) $request['id_request'];
    $service = new SupportService($db, $prefix);
    $owner = Actor::customer(1,11);
    pointTestAssert($service->thread($owner,$id)['messages'] === [], 'GET has no thread-creation side effect');
    pointTestReject(fn () => $service->post(Actor::customer(1,12),$id,'wrong',str_repeat('b',64)), 'other customer denied',404);
    pointTestReject(fn () => $service->thread(Actor::customer(2,11),$id), 'other shop denied',404);
    $first = $service->post($owner,$id,'合成のお問い合わせ <safe text>',str_repeat('a',64));
    pointTestAssert(count($first['messages']) === 1 && $first['messages'][0]['body'] === '合成のお問い合わせ <safe text>', 'native message readback plain text');
    $threadId = (int) $db->value('SELECT id_customer_thread FROM ' . $db->table('support_link') . ' WHERE id_request=' . $id);
    pointTestAssert((int)$db->value('SELECT id_customer FROM `' . $prefix . 'customer_thread` WHERE id_customer_thread=' . $threadId) === 11, 'native thread trusted customer');
    pointTestAssert($db->value('SELECT email FROM `' . $prefix . 'customer_thread` WHERE id_customer_thread=' . $threadId) === 'owner@example.test', 'native email comes from persisted identity');
    pointTestAssert($service->post($owner,$id,'合成のお問い合わせ <safe text>',str_repeat('a',64))['duplicate'] === true, 'same-key replay no second message');
    pointTestReject(fn () => $service->post($owner,$id,'changed',str_repeat('a',64)), 'same key different body conflicts',409);
    pointTestReject(fn () => $service->post($owner,$id,' ',str_repeat('d',64)), 'blank message rejected',422);
    pointTestReject(fn () => $service->post($owner,$id,str_repeat('あ',2001),str_repeat('d',64)), 'oversized message rejected',422);
    $db->execute('INSERT INTO `' . $prefix . "customer_message` (id_customer_thread,id_employee,message,private,file_name,date_add,date_upd) VALUES ($threadId,1,'Public reply',0,'',UTC_TIMESTAMP(),UTC_TIMESTAMP()),($threadId,1,'PRIVATE MUST NOT LEAK',1,'',UTC_TIMESTAMP(),UTC_TIMESTAMP())");
    $fresh = (new SupportService(new Database(pointTestConnection(),$prefix),$prefix))->thread($owner,$id);
    pointTestAssert(count($fresh['messages']) === 2 && $fresh['messages'][1]['body'] === 'Public reply', 'fresh connection sees public reply and excludes private notes');
    pointTestAssert($service->adminThreadId(pointTestEmployee(),$id) === $threadId, 'native admin support link validated');
    pointTestReject(fn () => $service->adminThreadId(Actor::employee(1,2,[]),$id), 'admin requires read ACL',403);
    $secondRequest = pointTestRequest($db,11,'SUBMITTED');
    pointTestReject(fn () => $service->post($owner,(int)$secondRequest['id_request'],'other request',str_repeat('a',64)), 'key reuse across requests conflicts',409);
    pointTestAssert(!str_contains(json_encode($fresh,JSON_THROW_ON_ERROR),'token') && !str_contains(json_encode($fresh,JSON_THROW_ON_ERROR),'owner@example.test'), 'customer response omits native token and email');
    $before = (int)$db->value('SELECT COUNT(*) FROM `' . $prefix . 'customer_message`');
    $threadCount = (int)$db->value('SELECT COUNT(*) FROM `' . $prefix . 'customer_thread`');
    $db->execute('CREATE TRIGGER `' . $prefix . 'fail_support_audit` BEFORE INSERT ON ' . $db->table('activity') . " FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='synthetic audit failure'");
    pointTestReject(fn () => $service->post($owner,$id,'rollback message',str_repeat('c',64)), 'audit failure rolls back native message and receipt');
    pointTestAssert((int)$db->value('SELECT COUNT(*) FROM `' . $prefix . 'customer_message`') === $before, 'native message transaction rollback');
    pointTestAssert((int)$db->value('SELECT COUNT(*) FROM ' . $db->table('support_post')) === 1, 'idempotency receipt rollback');
    pointTestReject(fn () => $service->post($owner,(int)$secondRequest['id_request'],'rollback new thread',str_repeat('e',64)), 'initial thread and mapping roll back on audit failure');
    pointTestAssert((int)$db->value('SELECT COUNT(*) FROM `' . $prefix . 'customer_thread`') === $threadCount, 'new native thread rollback');
    pointTestAssert((int)$db->value('SELECT COUNT(*) FROM ' . $db->table('support_link')) === 1, 'request mapping rollback');
    $db->execute('DROP TRIGGER `' . $prefix . 'fail_support_audit`');
    $db->execute('UPDATE `' . $prefix . 'customer_thread` SET id_customer=12 WHERE id_customer_thread=' . $threadId);
    pointTestReject(fn () => $service->thread($owner,$id), 'tampered native thread ownership denied',404);
    echo "PASS request support bridge: real MariaDB native seam, ownership, public/private, replay, trusted email, fresh readback and atomic rollback\n";
} finally {
    foreach (['support_post','support_link'] as $suffix) $db->execute('DROP TABLE IF EXISTS ' . $db->table($suffix));
    pointTestCleanup($db);
    foreach ($nativeTables as $table) $db->execute('DROP TABLE IF EXISTS `' . $prefix . $table . '`');
}
