<?php

declare(strict_types=1);
require __DIR__ . '/ci_bootstrap.php';
$input=json_decode((string)file_get_contents('php://stdin'),true,16,JSON_THROW_ON_ERROR);
ciAssert(is_array($input),'Account fixture command required');
$action=$input['action'] ?? '';
ciAssert(in_array($action,['routes','inspect'],true),'Invalid account fixture command');
$routes=[];
foreach (['ja','en','ko'] as $locale) {
    $lang=(int)Language::getIdByIso($locale,true);
    ciAssert($lang>0,'Account fixture language unavailable');
    foreach (['registration','authentication','my-account','password','identity'] as $route) $routes[$locale][$route]=$context->link->getPageLink($route,null,$lang);
}
ciAssert((string)Configuration::get('PS_MAIL_SERVER')==='mailpit' && (int)Configuration::get('PS_MAIL_SMTP_PORT')===1025,'Existing private Mailpit required');
ciAssert(Configuration::updateValue('PS_MAIL_METHOD',2) && Configuration::updateValue('PS_MAIL_TYPE',3),'Private mail transport unavailable');
if ($action==='routes') {
    echo json_encode(['routes'=>$routes],JSON_THROW_ON_ERROR); exit;
}
$email=$input['email'] ?? '';
$prefix='ordenowa-procurement-account-' . $run . '-' . $attempt . '-';
ciAssert(is_string($email) && preg_match('/\A'.preg_quote($prefix,'/').'(?:ja|en|ko)-[a-f0-9]{8}@example\.invalid\z/D',$email)===1,'Account fixture identity mismatch');
$customer=new Customer();
ciAssert($customer->getByEmail($email) && (int)$customer->id>0 && (int)$customer->id_shop===1 && !$customer->is_guest && $customer->active,'Registered account unavailable');
$count=(int)Db::getInstance()->getValue('SELECT COUNT(*) FROM `'._DB_PREFIX_.'customer` WHERE email=\''.pSQL($email).'\' AND id_shop=1',false);
$addresses=(int)Db::getInstance()->getValue('SELECT COUNT(*) FROM `'._DB_PREFIX_.'address` WHERE id_customer='.(int)$customer->id.' AND deleted=0',false);
// Private process pipe only. Callers must not persist or print this response.
echo json_encode(['count'=>$count,'address_count'=>$addresses,'id_lang'=>(int)$customer->id_lang,'password_hash'=>(string)$customer->passwd,
    'secure_key'=>(string)$customer->secure_key],JSON_THROW_ON_ERROR);
