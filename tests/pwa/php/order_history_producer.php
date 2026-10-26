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
class OrderState extends PushNativeRecordFixture { public static array $rows=[]; public bool $shipped=false; }
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

// Delivery receipts share the authoritative owner checks while using their own toggle and event ID.
$originalHistories=OrderHistory::$rows;$originalOrders=Order::$rows;
$originalCustomers=Customer::$rows;$originalSettings=Configuration::$values;
OrderHistory::$rows[31]=['id'=>31,'id_order'=>101,'id_order_state'=>2];
OrderState::$rows=[2=>['id'=>2,'shipped'=>true],3=>['id'=>3,'shipped'=>false]];
Order::$rows[101]['current_state']=2;Order::$rows[101]['id_lang']=1;
Configuration::$values['7:ORDENOWA_PUSH_EVENT_ORDER']='0';
assertOutbox($producer->recordDelivery(new OrderHistory(31))['status']==='ignored','delivery receipts remain disabled without an explicit shop setting');
Configuration::$values['7:ORDENOWA_PUSH_EVENT_DELIVERY']='1';
Configuration::$values['1:ORDENOWA_PUSH_EVENT_DELIVERY']='1';
$result=$producer->recordDelivery(new OrderHistory(31));
assertOutbox($result['status']==='provider_unavailable','shipped native history records delivery even when order notifications are disabled');
$deliveryReceipt=$outbox->events['7:10:delivery-history:31']??null;
assertOutbox($deliveryReceipt!==null&&$deliveryReceipt['event']==='delivery'&&$deliveryReceipt['locale']==='en'
    &&count($deliveryReceipt['recipients'])===1&&$outbox->history===[],
    'delivery receipt contains generic locale payload and only the consented owner recipient without sending');
assertOutbox($producer->record(new OrderHistory(31))['status']==='ignored','delivery toggle does not enable order receipts');
Configuration::$values['7:ORDENOWA_PUSH_EVENT_ORDER']='1';
assertOutbox($producer->record(new OrderHistory(31))['status']==='provider_unavailable'
    &&isset($outbox->events['7:10:order-history:31']),'order and delivery receipts coexist without event ID collision');
$deliveryEventCount=count($outbox->events);
assertOutbox($producer->recordDelivery(new OrderHistory(31))['status']==='duplicate'
    &&count($outbox->events)===$deliveryEventCount,'shipping history replay is idempotent');
$forgedDelivery=new OrderHistory(31);$forgedDelivery->id_order=999;$forgedDelivery->id_order_state=999;
assertOutbox($producer->recordDelivery($forgedDelivery)['status']==='duplicate','delivery owner and state come from persisted history');
assertOutbox($producer->recordDelivery((object)['id'=>31])['status']==='ignored','delivery rejects a non-native history hint');
assertOutbox($producer->recordDelivery(new OrderHistory(999))['status']==='ignored','delivery rejects an unpersisted history');
Configuration::$values['7:ORDENOWA_PUSH_EVENT_DELIVERY']='0';
assertOutbox($producer->recordDelivery(new OrderHistory(31))['status']==='ignored','delivery uses the order shop toggle even if another shop enables it');
Configuration::$values['7:ORDENOWA_PUSH_EVENT_DELIVERY']='1';
OrderHistory::$rows[32]=['id'=>32,'id_order'=>101,'id_order_state'=>3];Order::$rows[101]['current_state']=3;
assertOutbox($producer->recordDelivery(new OrderHistory(32))['status']==='ignored','unshipped order state produces no delivery receipt');
OrderHistory::$rows[32]['id_order_state']=9;Order::$rows[101]['current_state']=9;
assertOutbox($producer->recordDelivery(new OrderHistory(32))['status']==='ignored','missing native order state is ignored');
Order::$rows[101]['current_state']=2;
Customer::$rows[10]['is_guest']=true;
assertOutbox($producer->recordDelivery(new OrderHistory(31))['status']==='ignored','guest cannot receive a delivery receipt');
Customer::$rows[10]['is_guest']=false;Customer::$rows[10]['active']=false;
assertOutbox($producer->recordDelivery(new OrderHistory(31))['status']==='ignored','inactive customer cannot receive a delivery receipt');
Customer::$rows[10]['active']=true;Customer::$rows[10]['id']=11;
assertOutbox($producer->recordDelivery(new OrderHistory(31))['status']==='ignored','delivery customer identity must match the persisted order');
Customer::$rows[10]['id']=10;Order::$rows[101]['current_state']=3;
assertOutbox($producer->recordDelivery(new OrderHistory(31))['status']==='ignored','stale shipped history does not override the current order state');
assertOutbox(count($outbox->events)===$deliveryEventCount&&$outbox->history===[],'rejected shipping events leave receipts unchanged and perform no send attempts');
OrderHistory::$rows=$originalHistories;Order::$rows=$originalOrders;
Customer::$rows=$originalCustomers;Configuration::$values=$originalSettings;
echo "PASS: native order history push producer, trusted owner, replay dedupe, toggles, locale and no-secret receipt\n";
