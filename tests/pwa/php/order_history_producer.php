<?php
// Pure synthetic native-model boundary fixture; no PrestaShop bootstrap or network.
declare(strict_types=1);
require_once __DIR__ . '/delivery_outbox.php';
use Kuranea\Push\Domain\PushOutboxService;
use Kuranea\Push\Infrastructure\OrderHistoryPushProducer;

abstract class PushNativeRecordFixture {
    public int $id=0;
    public int $id_order=0;
    public int $id_order_state=0;
    public int $current_state=0;
    public int $id_shop=0;
    public int $id_customer=0;
    public int $id_lang=0;
    public bool $active=true;
    public bool $is_guest=false;
    public function __construct(int $id) {
        foreach(static::$rows[$id]??[] as $name=>$value)$this->$name=$value;
    }
}
class OrderHistory extends PushNativeRecordFixture { public static array $rows=[]; }
class Order extends PushNativeRecordFixture { public static array $rows=[]; }
class Customer extends PushNativeRecordFixture { public static array $rows=[]; }
class Validate { public static function isLoadedObject(object $value):bool { return $value->id>0; } }
class Language { public static function getIsoById(int $id):string { return [1=>'en',2=>'ko',3=>'ja',4=>'fr'][$id]??''; } }
class Configuration {
    public static array $values=[];
    public static function get(string $name,mixed $lang=null,mixed $group=null,mixed $shop=null):mixed {
        return self::$values[(int)$shop.':'.$name]??false;
    }
}
OrderHistory::$rows=[21=>['id'=>21,'id_order'=>101,'id_order_state'=>2]];
Order::$rows=[101=>['id'=>101,'id_shop'=>7,'id_customer'=>10,'current_state'=>2,'id_lang'=>1]];
Customer::$rows=[10=>['id'=>10,'active'=>true,'is_guest'=>false]];
Configuration::$values=['7:ORDENOWA_PUSH_EVENT_ORDER'=>'1','1:ORDENOWA_PUSH_EVENT_ORDER'=>'1'];
$targets=new FixtureTargets();$targets->rows=[$row(7,10,'producer-owner'),$row(1,10,'foreign-shop')];
$outbox=new FixtureOutbox();$service=new PushOutboxService($outbox,$targets);
$producer=new OrderHistoryPushProducer($service);
$result=$producer->record(new OrderHistory(21));
assertOutbox($result['status']==='provider_unavailable','native event is recorded while provider stays disabled');
$receipt=$outbox->events['7:10:order-history:21']??null;
assertOutbox($receipt!==null&&$receipt['event']==='order'&&$receipt['locale']==='en','history ID derives stable receipt and persisted locale');
assertOutbox(count($receipt['recipients'])===1&&$outbox->history===[],'only owner consent snapshot recorded without any send attempt');
assertOutbox($producer->record(new OrderHistory(21))['status']==='duplicate'&&count($outbox->events)===1,'native hook replay is idempotent');
$forged=new OrderHistory(21);$forged->id_order=999;$forged->id_order_state=999;
assertOutbox($producer->record($forged)['status']==='duplicate','owner derives from freshly loaded history rather than mutable hook fields');
assertOutbox($producer->record((object)['id'=>21])['status']==='ignored','non-native hook object rejected');
assertOutbox($producer->record(new OrderHistory(999))['status']==='ignored','unpersisted history rejected');
OrderHistory::$rows[22]=['id'=>22,'id_order'=>101,'id_order_state'=>2];
assertOutbox($producer->record(new OrderHistory(22))['status']==='provider_unavailable'&&count($outbox->events)===2,'different history creates independent receipt');
Configuration::$values['7:ORDENOWA_PUSH_EVENT_ORDER']='0';
assertOutbox($producer->record(new OrderHistory(22))['status']==='ignored','shop toggle suppresses event even if another shop is enabled');
Configuration::$values['7:ORDENOWA_PUSH_EVENT_ORDER']='1';
Customer::$rows[10]['is_guest']=true;assertOutbox($producer->record(new OrderHistory(22))['status']==='ignored','guest receives no receipt');
Customer::$rows[10]['is_guest']=false;Customer::$rows[10]['active']=false;
assertOutbox($producer->record(new OrderHistory(22))['status']==='ignored','disabled customer rejected');Customer::$rows[10]['active']=true;
Order::$rows[101]['current_state']=3;
assertOutbox($producer->record(new OrderHistory(22))['status']==='ignored','nonmatching persisted order state rejected');Order::$rows[101]['current_state']=2;
Customer::$rows[10]['id']=11;
assertOutbox($producer->record(new OrderHistory(22))['status']==='ignored','customer owner must match loaded order');Customer::$rows[10]['id']=10;
OrderHistory::$rows[23]=['id'=>23,'id_order'=>101,'id_order_state'=>2];Order::$rows[101]['id_lang']=2;
assertOutbox($producer->record(new OrderHistory(23))['status']==='provider_unavailable'&&$outbox->events['7:10:order-history:23']['locale']==='ko','locale comes from native order');
// A provider cannot start attempts if a caller has not configured the storage cipher.
$enabledProvider=new FixtureProvider();$withoutCipher=new PushOutboxService($outbox,$targets,null,$enabledProvider);
$result=$withoutCipher->receive(7,10,'no-cipher',new \Kuranea\Push\Domain\DeliveryPayload('order','en'));
assertOutbox($result['status']==='storage_unavailable'&&$enabledProvider->calls===[]&&$outbox->history===[],'missing cipher preserves pending receipt without a send attempt');
echo "PASS: native order history push producer, trusted owner, replay dedupe, toggles, locale and no-secret receipt\n";
