<?php

declare(strict_types=1);
$root=dirname(__DIR__,2);
$bootstrap=getenv('PROCUREMENT_SMARTY_BOOTSTRAP') ?: '/var/www/html/vendor/smarty/smarty/libs/Smarty.class.php';
if (!is_file($bootstrap)) throw new RuntimeException('Installed PrestaShop Smarty dependency required.');
require_once $bootstrap;
require_once $root . '/modules/ordenowaprocurement/autoload.php';
use Ordenowa\Procurement\Support\SupportView;
error_reporting(E_ALL & ~E_DEPRECATED);
set_error_handler(static function(int $level,string $message,string $file,int $line): bool {
    if (error_reporting() & $level) throw new ErrorException($message,0,$level,$file,$line);
    return false;
});
$dir=sys_get_temp_dir() . '/ordenowa-support-smarty-' . bin2hex(random_bytes(6));
mkdir($dir,0700); mkdir($dir.'/compiled',0700);
file_put_contents($dir.'/page.tpl','<html><body><h1>{block name="page_title"}{/block}</h1>{block name="page_content"}{/block}</body></html>');
$smarty=new Smarty(); $smarty->setTemplateDir($dir); $smarty->setCompileDir($dir.'/compiled');
$checks=0;
foreach (['ja','en','ko'] as $locale) {
    foreach ([true,false] as $allowed) {
        $data=['copy'=>SupportView::copy($locale),'messages'=>[['sender'=>'operator','body'=>'<script>alert("fixture")</script>','date'=>'2026-10-29 00:00:00']],
            'allowed'=>$allowed,'error'=>$allowed?'':SupportView::copy($locale)['error'],'url'=>'/index.php?module=ordenowaprocurement&controller=support&id_request=7',
            'back_url'=>'/workspace?view=request&id_request=7','id_request'=>7,'token'=>'native-token','idempotency_key'=>str_repeat('a',64)];
        $smarty->assign('ordenowa_support',$data);
        $html=$smarty->fetch($root.'/modules/ordenowaprocurement/views/templates/front/support.tpl');
        if (str_contains($html,'<script>')) throw new RuntimeException('Support message became executable markup.'); ++$checks;
        if ($allowed && (!str_contains($html,'&lt;script&gt;') || !str_contains($html,'name="token" value="native-token"') || !str_contains($html,'data-testid="support-send"'))) throw new RuntimeException('Authorized support form/escaping missing.'); ++$checks;
        if (!$allowed && (str_contains($html,'<form') || str_contains($html,'fixture') || !str_contains($html,'data-testid="support-error"'))) throw new RuntimeException('Denied support response leaked conversation/form.'); ++$checks;
    }
}
echo 'PASS '.$checks." actual Smarty support checks across JA/EN/KO allowed and denied views\n";
