<?php

declare(strict_types=1);
namespace PrestaShop\PrestaShop\Core\Module\Exception { interface ModuleErrorInterface {} }
namespace {
    require dirname(__DIR__,2) . '/modules/kuraneabackoffice/vendor/autoload.php';
    use Kuranea\Backoffice\Infrastructure\{NativeAclAuditRepository,NativeAclAuditSchema};
    use Kuranea\Backoffice\Admin\{NativeAclAuditObserver,NativeAclAuditUnavailableException};

    class PrestaShopException extends \Exception {}
    class Employee { public int $id=1;public int $id_profile=1;public bool $active=true;public bool $logged=true;public function isLoggedBack():bool{return $this->logged;} }
    class Context { public static object $context;public static function getContext():object{return self::$context;} }
    class Shop { public const CONTEXT_SHOP=1;public static int $scope=1;public static function getContext():int{return self::$scope;} }
    class Tools { public static array $input=[];public static function getValue(string $key):mixed{return self::$input[$key]??false;}public static function isSubmit(string $key):bool{return array_key_exists($key,self::$input);} }
    class AdminAccessControllerCore { public string $controller_name='AdminAccess';public bool $ajax=true;public bool $validToken=true;public int $edit=1;public function checkToken():bool{return $this->validToken;}public function access(string $action):int{return $this->edit;} }
    class Db { public static PDO $pdo;public static function getInstance():PDO{return self::$pdo;} }
    $dsn=getenv('PROCUREMENT_TEST_DSN');
    if(!$dsn || !str_contains($dsn,'dbname=ordenowa_procurement_test')){fwrite(STDERR,"Isolated procurement test DB required for native ACL tests.\n");exit(2);}
    $connect=static fn()=>new PDO($dsn,getenv('PROCUREMENT_TEST_USER')?:'root',getenv('PROCUREMENT_TEST_PASSWORD')?:'',[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
    $worker=str_starts_with((string)($argv[1]??''),'worker');
    $prefix=$worker?($argv[2]??''):'acl_'.bin2hex(random_bytes(4)).'_';
    if(preg_match('/\Aacl_[a-f0-9]{8}_\z/D',$prefix)!==1)exit(2);
    define('_DB_PREFIX_',$prefix);define('_PS_MODE_DEMO_',false);
    Db::$pdo=$connect();
    Context::$context=(object)['employee'=>new Employee(),'shop'=>(object)['id'=>3]];
    $controller=new AdminAccessControllerCore();
    $input=static function(string $kind='TAB'):void{Tools::$input=$kind==='TAB'?['action'=>'updateAccess','submitAddAccess'=>'1','id_profile'=>'2','perm'=>'all','enabled'=>'1','id_tab'=>'-1']:['action'=>'updateModuleAccess','changeModuleAccess'=>'1','id_profile'=>'2','perm'=>'view','enabled'=>'1','id_module'=>'-1'];};
    if($worker){
        Context::$context->employee->id=2;$input('MODULE');
        NativeAclAuditObserver::before(['controller'=>$controller],'MODULE');
        if(($argv[1]??'')!=='worker-noop')Db::$pdo->exec('INSERT INTO `'.$prefix.'module_access` VALUES (2,'.(($argv[1]??'')==='worker-die'?102:103).')');
        if(($argv[1]??'')==='worker-fatal')trigger_error('SYNTHETIC native ACL fatal fixture',E_USER_ERROR);
        // This is the exact termination pattern verified in native PS9 AdminAccess's two AJAX actions.
        die('ok');
    }
    $checks=0;
    $assert=static function(bool $ok,string $message)use(&$checks):void{++$checks;if(!$ok)throw new RuntimeException($message);};
    $pdo=Db::$pdo;
    $table='`'.$prefix.'kuraneabackoffice_native_acl_audit`';
    $tables=['kuraneabackoffice_native_acl_audit','module_access','access','authorization_role','employee_shop','employee','profile'];
    $count=static fn():int=>(int)$pdo->query('SELECT COUNT(*) FROM '.$table)->fetchColumn();
    $granted=static fn(string $kind,int $role):bool=>(bool)$pdo->query('SELECT COUNT(*) FROM `'.$prefix.($kind==='TAB'?'access':'module_access').'` WHERE id_profile=2 AND id_authorization_role='.$role)->fetchColumn();
    $request=static function(string $kind,callable $write,string $response='ok')use($input,$controller):string{
        $input($kind);ob_start();
        try{NativeAclAuditObserver::before(['controller'=>$controller],$kind);$write();echo $response;NativeAclAuditObserver::finish();return (string)ob_get_clean();}
        catch(Throwable $error){NativeAclAuditObserver::finish();while(ob_get_level()>0)ob_end_clean();throw $error;}
    };
    $runWorker=static function(string $mode)use($prefix):array{
        $process=proc_open([PHP_BINARY,__FILE__,$mode,$prefix],[0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes);
        if(!is_resource($process))throw new RuntimeException('Native ACL shutdown worker could not start.');
        fclose($pipes[0]);$out=stream_get_contents($pipes[1]);$err=stream_get_contents($pipes[2]);fclose($pipes[1]);fclose($pipes[2]);return [proc_close($process),$out,$err];
    };
    try{
        $pdo->exec('CREATE TABLE `'.$prefix.'employee`(id_employee INT PRIMARY KEY,id_profile INT,active INT) ENGINE=InnoDB');
        $pdo->exec('CREATE TABLE `'.$prefix.'employee_shop`(id_employee INT,id_shop INT,PRIMARY KEY(id_employee,id_shop)) ENGINE=InnoDB');
        $pdo->exec('CREATE TABLE `'.$prefix.'profile`(id_profile INT PRIMARY KEY) ENGINE=InnoDB');
        $pdo->exec('CREATE TABLE `'.$prefix.'authorization_role`(id_authorization_role INT PRIMARY KEY,slug VARCHAR(255)) ENGINE=InnoDB');
        foreach(['access','module_access']as$name)$pdo->exec('CREATE TABLE `'.$prefix.$name.'`(id_profile INT,id_authorization_role INT,PRIMARY KEY(id_profile,id_authorization_role)) ENGINE=InnoDB');
        $pdo->exec(NativeAclAuditSchema::tableSql($prefix));
        $pdo->exec('INSERT INTO `'.$prefix.'employee` VALUES(1,1,1),(2,1,1)');$pdo->exec('INSERT INTO `'.$prefix.'employee_shop` VALUES(1,3),(2,3)');$pdo->exec('INSERT INTO `'.$prefix.'profile` VALUES(1),(2)');
        $roles=[1=>'ROLE_MOD_TAB_ADMINORDENOWAPROCUREMENT_READ',2=>'ROLE_MOD_TAB_ADMINORDENOWAPROCUREMENT_CREATE',3=>'ROLE_MOD_TAB_ADMINORDENOWAPROCUREMENTPOINTS_UPDATE',4=>'ROLE_MOD_TAB_ADMINOTHER_READ',101=>'ROLE_MOD_MODULE_KURANEAPUSH_UPDATE',102=>'ROLE_MOD_MODULE_KURANEACATALOG_READ',103=>'ROLE_MOD_MODULE_KURANEAPUSH_DELETE'];
        foreach($roles as$id=>$slug)$pdo->exec('INSERT INTO `'.$prefix.'authorization_role` VALUES('.$id.','.$pdo->quote($slug).')');
        $assert($request('TAB',static function():void{})==='ok' && $count()===0,'Unchanged native success must not fabricate an audit change');
        $assert($request('TAB',fn()=>$pdo->exec('INSERT INTO `'.$prefix.'access` VALUES(2,1)'))==='ok','Only committed native success releases ok');
        $row=$pdo->query('SELECT * FROM '.$table)->fetch(PDO::FETCH_ASSOC);
        $assert($count()===1&&(int)$row['id_shop']===0&&(int)$row['context_shop_id']===3&&(int)$row['actor_employee_id']===1&&(int)$row['target_profile_id']===2&&(int)$row['old_granted']===0&&(int)$row['new_granted']===1,'Actual before/after native role grant records trusted actor/profile and global scope');
        $assert(!str_contains(json_encode($row),'token')&&!str_contains(json_encode($row),'enabled'),'No raw request or CSRF material enters audit');
        $request('TAB',fn()=>$pdo->exec('DELETE FROM `'.$prefix.'access` WHERE id_profile=2 AND id_authorization_role=1'));
        $assert($count()===2&&!$granted('TAB',1),'Native revoke records the actual persisted inverse transition');
        $request('TAB',fn()=>$pdo->exec('INSERT INTO `'.$prefix.'access` VALUES(2,2),(2,3)'));
        $assert($count()===4,'Bulk grid action records every actual changed role once');
        $request('MODULE',fn()=>$pdo->exec('INSERT INTO `'.$prefix.'module_access` VALUES(2,101)'));
        $assert($count()===5&&$granted('MODULE',101),'Native module permission grid is observed independently');
        $assert($request('TAB',fn()=>$pdo->exec('INSERT INTO `'.$prefix.'access` VALUES(2,4)'),'error')==='error'&&!$granted('TAB',4)&&$count()===5,'Native failed partial action rolls back with no changed audit');
        $trigger='`'.$prefix.'fail_audit`';
        $pdo->exec('CREATE TRIGGER '.$trigger.' BEFORE INSERT ON '.$table." FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='synthetic audit persistence failure'");
        $assert($request('TAB',fn()=>$pdo->exec('INSERT INTO `'.$prefix.'access` VALUES(2,4)'))==='error','Injected audit failure must suppress native ok');
        $assert(!$granted('TAB',4)&&$count()===5&&!$pdo->inTransaction(),'Injected audit failure rolls back native permission and all audit writes');
        $pdo->exec('DROP TRIGGER '.$trigger);
        foreach(['token','edit','session','active','actor-profile','actor-shop','target','wrong-controller','wrong-action']as$denial){
            $input();$candidate=clone$controller;$employee=Context::$context->employee;
            if($denial==='token')$candidate->validToken=false;if($denial==='edit')$candidate->edit=0;if($denial==='session')$employee->logged=false;if($denial==='active')$employee->active=false;
            if($denial==='actor-profile')$employee->id_profile=99;if($denial==='actor-shop')Context::$context->shop->id=4;if($denial==='target')Tools::$input['id_profile']='999';
            if($denial==='wrong-controller')$candidate->controller_name='AdminOther';if($denial==='wrong-action')Tools::$input['action']='updateOther';
            try { NativeAclAuditObserver::before(['controller'=>$candidate],'TAB'); } catch(NativeAclAuditUnavailableException) {}
            NativeAclAuditObserver::finish();
            $assert($count()===5&&!$pdo->inTransaction(),'Denied native boundary does not start or record a mutation:'.$denial);
            $employee->logged=true;$employee->active=true;$employee->id_profile=1;Context::$context->shop->id=3;
        }
        $pdo->exec('INSERT INTO `'.$prefix.'access` VALUES(999,1)');
        $assert((int)$pdo->query('SELECT COUNT(*) FROM `'.$prefix.'access` WHERE id_profile=999')->fetchColumn()===1,'Native access schema permits orphan profile rows, so observer must fail closed on missing target');
        $pdo->exec('DELETE FROM `'.$prefix.'access` WHERE id_profile=999');
        $input(); Tools::$input['id_profile']='999';
        $blocked=false;
        try { NativeAclAuditObserver::before(['controller'=>$controller],'TAB'); $pdo->exec('INSERT INTO `'.$prefix.'access` VALUES(999,1)'); }
        catch(NativeAclAuditUnavailableException) { $blocked=true; }
        $assert($blocked&&(int)$pdo->query('SELECT COUNT(*) FROM `'.$prefix.'access` WHERE id_profile=999')->fetchColumn()===0&&$count()===5,'Verified official hook blocks unknown target before native write and creates no attempted audit');
        Shop::$scope=2;$request('TAB',fn()=>$pdo->exec('INSERT INTO `'.$prefix.'access` VALUES(2,4)'));Shop::$scope=1;
        $assert((int)$pdo->query('SELECT context_shop_id FROM '.$table.' ORDER BY id_event DESC LIMIT 1')->fetchColumn()===0,'Global native context is recorded explicitly, never inferred from request shop flags');
        [$exit,$body]=$runWorker('worker-die');
        $assert($exit===0&&$body==='ok'&&$granted('MODULE',102)&&$count()===7,'Actual PHP die shutdown commits native write and audited readback before releasing ok');
        [$exit,$body]=$runWorker('worker-noop');$assert($exit===0&&$body==='ok'&&$count()===7,'Native die with no change records nothing');
        $pdo->exec('CREATE TRIGGER '.$trigger.' BEFORE INSERT ON '.$table." FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='synthetic shutdown audit failure'");
        [$exit,$body]=$runWorker('worker-audit-failure');
        $assert($exit===0&&$body==='error'&&!$granted('MODULE',103)&&$count()===7,'Actual die shutdown suppresses ok and rolls back role when audit insert fails');
        $pdo->exec('DROP TRIGGER '.$trigger);
        [$exit,$body]=$runWorker('worker-fatal');
        $assert($exit!==0&&$body==='error'&&!$granted('MODULE',103)&&$count()===7,'Fatal shutdown rolls back uncommitted native role and emits no ok');
        $repository=new NativeAclAuditRepository();$lock=$repository->lock(2);$other=$connect();
        $assert((int)$other->query('SELECT GET_LOCK('.$other->quote($lock).',0)')->fetchColumn()===0,'Profile observation lock serializes competing native grid requests');
        $repository->unlock($lock);$assert((int)$other->query('SELECT GET_LOCK('.$other->quote($lock).',0)')->fetchColumn()===1,'Native profile lock releases after audited completion');$other->query('SELECT RELEASE_LOCK('.$other->quote($lock).')');
        $pdo->exec('RENAME TABLE '.$table.' TO `'.$prefix.'audit_stash`');
        try{$input();NativeAclAuditObserver::before(['controller'=>$controller],'TAB');throw new RuntimeException('Missing audit store must block before native write');}
        catch(NativeAclAuditUnavailableException){$assert(!$pdo->inTransaction(),'Unavailable audit storage prevents an unaudited native mutation');}
        finally{$pdo->exec('RENAME TABLE `'.$prefix.'audit_stash` TO '.$table);}
        $assert(count($repository->pageForShop(5,1)['rows'])===7,'Global profile permission audit is visible to authorized audit reader in every shop');
        NativeAclAuditObserver::finish();$assert($count()===7,'Repeated observer completion never duplicates audit');
        echo 'native_acl_atomic: PASS '.$checks.' real MariaDB checks including grant/revoke/bulk/module, native auth/CSRF, actual die/fatal, and audit-failure rollback' . PHP_EOL;
    }finally{
        NativeAclAuditObserver::finish();if($pdo->inTransaction())$pdo->rollBack();
        foreach($tables as$name)$pdo->exec('DROP TABLE IF EXISTS `'.$prefix.$name.'`');
    }
}
