<?php
/** Optional real MariaDB fixture. Exact disposable Actions environment only; never run locally. */
declare(strict_types=1);
$module='/var/www/html/modules/kuraneapush/autoload.php';
require $module;
use Kuranea\Push\Domain\{DeliveryPayload, Readiness};
use Kuranea\Push\Infrastructure\PushOutboxRepository;
if(PHP_SAPI!=='cli'||!Readiness::isolated()) { throw new RuntimeException('Requires exact isolated Actions push environment.'); }
$_SERVER['HTTP_HOST']=(string)getenv('PS_DOMAIN')?:'localhost:18080';
$_SERVER['REQUEST_URI']='/';$_SERVER['SCRIPT_NAME']='/index.php';
require '/var/www/html/config/config.inc.php';
function checkOutboxDb(bool $ok,string $label):void { if(!$ok)throw new RuntimeException($label); }
$db=Db::getInstance();
// This fixture owns only these random-prefixed tables, never module/customer/shop data.
$prefix='pushqa_'.bin2hex(random_bytes(8)).'_';
$tables=[$prefix.'kuraneapush_attempt',$prefix.'kuraneapush_recipient',$prefix.'kuraneapush_event'];
try {
    $first=new PushOutboxRepository($db,$prefix);checkOutboxDb($first->install(),'temporary outbox tables install');
    checkOutboxDb($first->acquire(1,10,'synthetic-receipt'),'first receipt lock');
    $digest=str_repeat('a',64);$first->create(1,10,'synthetic-receipt',new DeliveryPayload('order','en'),[['endpoint_digest'=>$digest,'consent_generation'=>str_repeat('b',64)]]);
    $attempt=$first->startAttempt(1,10,'synthetic-receipt',$digest);
    $first->finishAttempt(1,10,'synthetic-receipt',$digest,$attempt,'retryable_failure');
    $first->release(1,10,'synthetic-receipt');unset($first);
    $fresh=new PushOutboxRepository($db,$prefix);checkOutboxDb($fresh->acquire(1,10,'synthetic-receipt'),'fresh repository lock');
    $receipt=$fresh->event(1,10,'synthetic-receipt');
    checkOutboxDb($receipt['event']==='order'&&$receipt['recipients'][0]['outcome']==='retryable_failure','receipt survives repository recreation');
    checkOutboxDb((int)$receipt['recipients'][0]['attempts']===1,'attempt count is durable');
    $attempt=$fresh->startAttempt(1,10,'synthetic-receipt',$digest);
    checkOutboxDb($attempt===2,'explicit retry increments persisted attempt number');
    $fresh->finishAttempt(1,10,'synthetic-receipt',$digest,$attempt,'delivered');
    try {$fresh->startAttempt(1,10,'synthetic-receipt',$digest);throw new LogicException('delivered recipient retried');}
    catch(RuntimeException $expected) {}
    $fresh->release(1,10,'synthetic-receipt');
    checkOutboxDb($fresh->acquire(2,10,'synthetic-receipt'),'other shop lock');
    checkOutboxDb($fresh->event(2,10,'synthetic-receipt')===null,'cross shop receipt hidden');
    $fresh->release(2,10,'synthetic-receipt');
    $attempts=$db->executeS('SELECT attempt_number,outcome,started_at,completed_at FROM `'.$prefix.'kuraneapush_attempt` ORDER BY attempt_number',true,false);
    checkOutboxDb(count($attempts)===2&&$attempts[0]['outcome']==='retryable_failure'&&$attempts[1]['outcome']==='delivered','history persists both attempts');
    foreach($attempts as $row)checkOutboxDb(!empty($row['started_at'])&&!empty($row['completed_at']),'attempt timestamps are persisted');
    $fresh->deleteCustomer(10,[1]);
    $remaining=$db->executeS('SELECT event_id FROM `'.$prefix.'kuraneapush_event`',true,false);
    checkOutboxDb($remaining===[],'customer erasure removes durable receipts');
    echo "PASS: isolated MariaDB outbox receipt, attempt history, retry, successful-recipient guard and owner isolation\n";
} finally {
    foreach($tables as $table) {
        if(!$db->execute('DROP TABLE IF EXISTS `'.$table.'`'))throw new RuntimeException('Could not clean up fixture-owned outbox table.');
    }
}
