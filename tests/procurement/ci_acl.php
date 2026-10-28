<?php

declare(strict_types=1);
// Native Link explicitly refuses BO links without this installed admin path.
if (!defined('_PS_ADMIN_DIR_')) define('_PS_ADMIN_DIR_', '/var/www/html/admin-kuranea');
require __DIR__ . '/ci_bootstrap.php';
ciAssert(getenv('GITHUB_ACTIONS') === 'true', 'Native ACL fixture requires matching Actions run');
$mode = $argv[1] ?? '';
ciAssert(in_array($mode,['prepare','grant','revoke'],true), 'Unknown native ACL acceptance phase');
require_once '/var/www/html/modules/kuraneabackoffice/vendor/autoload.php';
require_once '/var/www/html/app/AdminKernel.php';
$kernel = new AdminKernel(_PS_ENV_, _PS_MODE_DEV_);
$kernel->boot();
$native = Db::getInstance();
$backoffice = Module::getInstanceByName('kuraneabackoffice');
ciAssert($backoffice instanceof Module && $backoffice->active
    && $backoffice->isRegisteredInHook('actionAdminUpdateAccessBefore')
    && $backoffice->isRegisteredInHook('actionAdminUpdateModuleAccessBefore'), 'Native ACL official observer hooks are not installed');
$stateFile = __DIR__ . '/acl.json';
$auditTable = '`' . _DB_PREFIX_ . 'kuraneabackoffice_native_acl_audit`';
function aclNativeHash(object $native, int $target): string
{
    $state=[];
    foreach(['access','module_access'] as $table){
        $rows=$native->executeS('SELECT id_profile,id_authorization_role FROM `'._DB_PREFIX_.$table.'` WHERE id_profile<>'.$target.' ORDER BY id_profile,id_authorization_role',true,false);
        ciAssert(is_array($rows),'Native preserved ACL read failed');
        foreach($rows as &$row)foreach($row as &$value)$value=(string)$value;
        unset($row,$value);$state[$table]=$rows;
    }
    $rows=$native->executeS('SELECT id_employee,id_profile FROM `'._DB_PREFIX_.'employee` ORDER BY id_employee',true,false);
    ciAssert(is_array($rows),'Native employee profile read failed');
    foreach($rows as &$row)foreach($row as &$value)$value=(string)$value;
    unset($row,$value);$state['employee_profiles']=$rows;
    return hash('sha256',json_encode($state,JSON_THROW_ON_ERROR));
}
if($mode==='prepare'){
    $fixture=ciFixture();
    $employee=new Employee();$actor=$employee->getByEmail((string)getenv('ADMIN_MAIL'));
    ciAssert($actor instanceof Employee && $actor->active && (int)$actor->id_profile === (int)_PS_ADMIN_PROFILE_, 'Native ACL actor fixture missing');
    $name='SYNTHETIC ACL '.$fixture['run'];
    $profile=null;
    if(is_file($stateFile)){
        $prior=json_decode((string)file_get_contents($stateFile),true,16,JSON_THROW_ON_ERROR);
        ciAssert(($prior['run']??'')===$fixture['run'],'ACL fixture run mismatch');
        $profile=new Profile((int)($prior['profile_id']??0));
    }
    if(!$profile || !Validate::isLoadedObject($profile)){
        $profile=new Profile();$profile->name=[];
        foreach(Language::getLanguages(false)as$language)$profile->name[(int)$language['id_lang']]=$name;
        ciAssert($profile->add(),'Dedicated native ACL profile creation failed');
    }
    foreach ((array)$profile->name as $storedName) ciAssert($storedName===$name,'ACL profile is not the exact run-owned synthetic target');
    $target=(int)$profile->id;
    ciAssert($target>0&&$target!==(int)$actor->id_profile&&$target!==(int)($fixture['reader']['profile_id']??0),'ACL target is not a dedicated profile');
    ciAssert((int)$native->getValue('SELECT COUNT(*) FROM `'._DB_PREFIX_.'employee` WHERE id_profile='.$target,false)===0,'ACL fixture profile has employees');
    ciAssert((int)$native->getValue('SELECT COUNT(*) FROM `'._DB_PREFIX_.'access` WHERE id_profile='.$target,false)===0,'ACL fixture must begin without granted tab roles');
    ciAssert((int)$native->getValue('SELECT COUNT(*) FROM `'._DB_PREFIX_.'module_access` WHERE id_profile='.$target,false)===0,'ACL fixture must begin without granted module roles');
    $tab=(int)Tab::getIdFromClassName('AdminOrdenowaProcurement');
    $slug=Access::sluggifyTab(['class_name'=>'AdminOrdenowaProcurement'],'READ');
    $role=(int)$native->getValue('SELECT id_authorization_role FROM `'._DB_PREFIX_.'authorization_role` WHERE slug=\''.pSQL($slug).'\'',false);
    ciAssert($tab>0&&$role>0,'Known procurement native READ role missing');
    // The official checkbox recursively changes its parent READ checkboxes.
    // Derive that exact role set from persisted native tab ancestry.
    $expectedRoles=[]; $cursor=$tab; $seen=[];
    while($cursor>0){
        ciAssert(!isset($seen[$cursor])&&count($seen)<20,'Native permission ancestry invalid'); $seen[$cursor]=true;
        $row=$native->getRow('SELECT id_parent,class_name FROM `'._DB_PREFIX_.'tab` WHERE id_tab='.$cursor,false);
        ciAssert(is_array($row),'Native permission ancestor missing');
        $ancestorSlug=Access::sluggifyTab(['class_name'=>$row['class_name']],'READ');
        $ancestorRole=(int)$native->getValue('SELECT id_authorization_role FROM `'._DB_PREFIX_.'authorization_role` WHERE slug=\''.pSQL($ancestorSlug).'\'',false);
        ciAssert($ancestorRole>0,'Native ancestor READ role missing');
        $expectedRoles[$ancestorRole]=$ancestorSlug; $cursor=(int)$row['id_parent'];
    }
    $baseline=(int)$native->getValue('SELECT COALESCE(MAX(id_event),0) FROM '.$auditTable,false);
    $state=['run'=>$fixture['run'],'profile_id'=>$target,'tab_id'=>$tab,'role_id'=>$role,'actor_id'=>(int)$actor->id,
        'actor_profile_id'=>(int)$actor->id_profile,'baseline_event'=>$baseline,'preserved_hash'=>aclNativeHash($native,$target),'complete'=>false,
        'access_url'=>Context::getContext()->link->getAdminLink('AdminAccess', false),'expected_roles'=>$expectedRoles];
    ciAssert(file_put_contents($stateFile,json_encode($state,JSON_THROW_ON_ERROR))!==false,'Private ACL fixture state could not be saved');chmod($stateFile,0600);
    echo "PASS native ACL dedicated empty profile prepared; actor/reader profiles preserved\n";exit;
}
$state=json_decode((string)file_get_contents($stateFile),true,16,JSON_THROW_ON_ERROR);
ciAssert(($state['run']??'')===getenv('GITHUB_RUN_ID').'-'.getenv('GITHUB_RUN_ATTEMPT'),'ACL readback run mismatch');
$target=(int)$state['profile_id'];$role=(int)$state['role_id'];
ciAssert((int)$native->getValue('SELECT COUNT(*) FROM `'._DB_PREFIX_.'employee` WHERE id_profile='.$target,false)===0,'Dedicated ACL profile acquired an employee');
ciAssert(hash_equals($state['preserved_hash'],aclNativeHash($native,$target)),'Unrelated native ACL or employee profile changed');
$granted=(int)$native->getValue('SELECT COUNT(*) FROM `'._DB_PREFIX_.'access` WHERE id_profile='.$target.' AND id_authorization_role='.$role,false);
$expected=$mode==='grant'?1:0;
ciAssert($granted===$expected,'Fresh native profile READ permission mismatch');
$rows=$native->executeS('SELECT actor_employee_id,actor_profile_id,target_profile_id,id_shop,context_shop_id,access_kind,role_id,role_slug,old_granted,new_granted,correlation_id FROM '
    .$auditTable.' WHERE id_event>'.(int)$state['baseline_event'].' AND target_profile_id='.$target.' ORDER BY id_event',true,false);
$expectedRoles=$state['expected_roles'];
ciAssert(is_array($expectedRoles)&&isset($expectedRoles[$role]),'Native UI role expectation missing');
ciAssert(is_array($rows)&&count($rows)===count($expectedRoles)*($mode==='grant'?1:2),'Native official hook audit count mismatch');
$transitions=[]; $correlations=[];
foreach($rows as$row){
    ciAssert((int)$row['actor_employee_id']===(int)$state['actor_id']&&(int)$row['actor_profile_id']===(int)$state['actor_profile_id']
        // Native AdminAccess explicitly restricts its controller to CONTEXT_ALL,
        // including when the installed platform has only one shop.
        &&(int)$row['target_profile_id']===$target&&(int)$row['id_shop']===0&&(int)$row['context_shop_id']===0,'Native ACL audit actor/target/global scope mismatch');
    $rowRole=(int)$row['role_id']; $index=count($transitions[$rowRole]??[]);
    ciAssert($row['access_kind']==='TAB'&&isset($expectedRoles[$rowRole])&&$row['role_slug']===$expectedRoles[$rowRole]
        &&(int)$row['old_granted']===($index===0?0:1)&&(int)$row['new_granted']===($index===0?1:0)
        &&preg_match('/\A[a-f0-9]{32}\z/D',$row['correlation_id'])===1,'Native ACL audit before/after values mismatch');
    $transitions[$rowRole][]=(int)$row['new_granted']; $correlations[]=$row['correlation_id'];
}
foreach($expectedRoles as$id=>$unused)ciAssert(($transitions[$id]??[])===($mode==='grant'?[1]:[1,0]),'Native ancestor grant/revoke audit missing');
ciAssert(count(array_unique($correlations))===count($correlations),'Separate native permission AJAX actions must have separate correlations');
if($mode==='revoke'){
    ciAssert((int)$native->getValue('SELECT COUNT(*) FROM `'._DB_PREFIX_.'access` WHERE id_profile='.$target,false)===0,'Native cleanup did not restore empty dedicated profile');
    $state['complete']=true;ciAssert(file_put_contents($stateFile,json_encode($state,JSON_THROW_ON_ERROR))!==false,'ACL completion state write failed');chmod($stateFile,0600);
}
echo 'PASS native official ACL '.$mode." with fresh audit readback and preserved actor/reader permissions\n";
