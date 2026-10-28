<?php
declare(strict_types=1);
require_once __DIR__ . '/points_support.php';

use Ordenowa\Procurement\Infrastructure\{Database,Schema};
use Ordenowa\Procurement\Security\Actor;
use Ordenowa\Procurement\Support\SupportService;

// The actual native ObjectModel boundary writes through this same real isolated
// connection. The application runtime separately exercises the native classes.
#[AllowDynamicProperties]
class CustomerThread {
    public static Database $db;
    public static string $prefix;
    public int $id=0;
    public function add(): bool {
        self::$db->execute('INSERT INTO `' . self::$prefix . 'customer_thread` (id_shop,id_customer,id_lang,id_contact,id_product,id_order,email,token,status,date_add,date_upd) VALUES ('
            . $this->id_shop . ',' . $this->id_customer . ',' . $this->id_lang . ',' . $this->id_contact . ',' . $this->id_product . ',0,'
            . self::$db->quote($this->email) . ',' . self::$db->quote($this->token) . ",'open',UTC_TIMESTAMP(),UTC_TIMESTAMP())");
        $this->id=self::$db->insertId();return true;
    }
}
#[AllowDynamicProperties]
class CustomerMessage {
    public int $id=0;
    public function add(): bool {
        CustomerThread::$db->execute('INSERT INTO `' . CustomerThread::$prefix . 'customer_message` (id_customer_thread,id_employee,message,private,file_name,date_add,date_upd) VALUES ('
            . $this->id_customer_thread . ',0,' . CustomerThread::$db->quote($this->message) . ",0,'',UTC_TIMESTAMP(),UTC_TIMESTAMP())");
        $this->id=CustomerThread::$db->insertId();return true;
    }
}

if (($argv[1] ?? '') === 'worker') {
    [,,$prefix,$requestId,$key,$gate,$worker]=$argv;
    if (!preg_match('/\Asr_[a-f0-9]{10}_\z/D',$prefix) || !ctype_digit($requestId)
        || !str_starts_with($gate,sys_get_temp_dir().'/ordenowa-support-review-')) exit(2);
    $db=new Database(pointTestConnection(),$prefix);
    CustomerThread::$db=$db;CustomerThread::$prefix=$prefix;
    $service=new SupportService($db,$prefix);
    touch($gate.'.ready.'.$worker);
    $deadline=microtime(true)+10;
    while (!is_file($gate)) {
        if (microtime(true)>$deadline) exit(2);
        usleep(1000);
    }
    try {
        $result=$service->post(Actor::customer(1,11),(int)$requestId,'Synthetic concurrent support',$key);
        fwrite(STDOUT,json_encode(['duplicate'=>$result['duplicate']],JSON_THROW_ON_ERROR));exit(0);
    } catch (Throwable $error) {
        if ($error->getCode()===409) { fwrite(STDOUT,'{"conflict":true}');exit(9); }
        fwrite(STDERR,get_class($error).':'.$error->getMessage());exit(2);
    }
}

$prefix='sr_'.bin2hex(random_bytes(5)).'_';
$db=new Database(pointTestConnection(),$prefix);
CustomerThread::$db=$db;CustomerThread::$prefix=$prefix;
$native=['customer_message','customer_thread','contact_shop','contact','customer'];
$gates=[];
try {
    Schema::install($db);
    $db->execute('CREATE TABLE `'.$prefix.'customer` (id_customer INT PRIMARY KEY,id_shop INT,id_lang INT,email VARCHAR(255),active INT,deleted INT,is_guest INT) ENGINE=InnoDB');
    $db->execute('CREATE TABLE `'.$prefix.'contact` (id_contact INT PRIMARY KEY) ENGINE=InnoDB');
    $db->execute('CREATE TABLE `'.$prefix.'contact_shop` (id_contact INT,id_shop INT) ENGINE=InnoDB');
    $db->execute('CREATE TABLE `'.$prefix.'customer_thread` (id_customer_thread INT AUTO_INCREMENT PRIMARY KEY,id_shop INT,id_customer INT,id_lang INT,id_contact INT,id_product INT,id_order INT,email VARCHAR(255),token CHAR(12),status VARCHAR(16),date_add DATETIME,date_upd DATETIME) ENGINE=InnoDB');
    $db->execute('CREATE TABLE `'.$prefix.'customer_message` (id_customer_message INT AUTO_INCREMENT PRIMARY KEY,id_customer_thread INT,id_employee INT,message TEXT,private INT,file_name VARCHAR(32),date_add DATETIME,date_upd DATETIME) ENGINE=InnoDB');
    $db->execute('INSERT INTO `'.$prefix."customer` VALUES (11,1,1,'synthetic@example.invalid',1,0,0)");
    $db->execute('INSERT INTO `'.$prefix.'contact` VALUES (1)');
    $db->execute('INSERT INTO `'.$prefix.'contact_shop` VALUES (1,1)');
    foreach (['same-request','cross-request'] as $mode) {
        for ($round=0;$round<3;++$round) {
            $first=pointTestRequest($db,11,'SUBMITTED');
            $second=$mode==='same-request'?$first:pointTestRequest($db,11,'SUBMITTED');
            $before=(int)$db->value('SELECT COUNT(*) FROM `'.$prefix.'customer_message`');
            $gate=sys_get_temp_dir().'/ordenowa-support-review-'.bin2hex(random_bytes(8));$gates[]=$gate;
            $key=hash('sha256',$mode.':'.$round);$processes=[];
            foreach ([0,1] as $worker) {
                $request=$worker===0?$first:$second;
                $process=proc_open([PHP_BINARY,__FILE__,'worker',$prefix,(string)$request['id_request'],$key,$gate,(string)$worker],
                    [0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes);
                pointTestAssert(is_resource($process),'support worker starts');fclose($pipes[0]);$processes[]=[$process,$pipes];
            }
            $deadline=microtime(true)+10;
            while (!is_file($gate.'.ready.0') || !is_file($gate.'.ready.1')) {
                pointTestAssert(microtime(true)<$deadline,'support workers reach barrier');usleep(1000);
            }
            touch($gate);$results=[];
            foreach ($processes as [$process,$pipes]) {
                $output=stream_get_contents($pipes[1]);$error=stream_get_contents($pipes[2]);fclose($pipes[1]);fclose($pipes[2]);
                $exit=proc_close($process);pointTestAssert(in_array($exit,[0,9],true),'support race completes: '.$error);
                $results[]=['exit'=>$exit,'data'=>json_decode($output,true,16,JSON_THROW_ON_ERROR)];
            }
            $exits=array_column($results,'exit');sort($exits);
            pointTestAssert($exits===($mode==='same-request'?[0,0]:[0,9]),'same customer key conflict resolves after identity lock');
            if ($mode==='same-request') {
                $duplicates=array_column(array_column($results,'data'),'duplicate');sort($duplicates);
                pointTestAssert($duplicates===[false,true],'same payload returns exactly one duplicate');
            }
            pointTestAssert((int)$db->value('SELECT COUNT(*) FROM `'.$prefix.'customer_message`')===$before+1,'only one native message committed');
            $scope='id_request IN ('.(int)$first['id_request'].','.(int)$second['id_request'].')';
            foreach (['support_link','support_post'] as $suffix) {
                pointTestAssert((int)$db->value('SELECT COUNT(*) FROM '.$db->table($suffix).' WHERE '.$scope)===1,'one owned thread link/receipt per key race');
            }
        }
    }
    echo "PASS support concurrency: six same-customer replay/cross-request key races, native message/link/receipt atomicity\n";
} finally {
    foreach ($gates as $gate) foreach ([$gate,$gate.'.ready.0',$gate.'.ready.1'] as $file) if (is_file($file)) unlink($file);
    pointTestCleanup($db);
    foreach ($native as $table) $db->execute('DROP TABLE IF EXISTS `'.$prefix.$table.'`');
}
