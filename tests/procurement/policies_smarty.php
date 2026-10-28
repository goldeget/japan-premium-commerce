<?php

declare(strict_types=1);
$bootstrap = getenv('PROCUREMENT_SMARTY_BOOTSTRAP') ?: '/var/www/html/vendor/smarty/smarty/libs/Smarty.class.php';
if (!is_file($bootstrap)) throw new RuntimeException('Installed native Smarty dependency is required.');
require $bootstrap;
error_reporting(E_ALL & ~E_DEPRECATED);
set_error_handler(static function (int $severity, string $message, string $file, int $line): bool { if (error_reporting() & $severity) throw new ErrorException($message,0,$severity,$file,$line); return false; });
$directory = sys_get_temp_dir() . '/ordenowa-policy-smarty-' . bin2hex(random_bytes(6));
mkdir($directory,0700); mkdir($directory.'/compiled',0700);
file_put_contents($directory.'/page.tpl','<html><head><title>{block name="head_seo_title"}{/block}</title></head><body><h1>{block name="page_title"}{/block}</h1>{block name="page_content"}{/block}</body></html>');
$smarty = new Smarty(); $smarty->setTemplateDir($directory);$smarty->setCompileDir($directory.'/compiled');
$template=dirname(__DIR__,2).'/modules/ordenowaprocurement/views/templates/front/policy.tpl';
$checks=0;
$assert=static function(bool $ok,string $label)use(&$checks):void{++$checks;if(!$ok)throw new RuntimeException('Policy render failed:'.$label);};
$hostile='<script>alert("test")</script>';
try {
    foreach (['ja'=>'利用規約','en'=>'Terms','ko'=>'이용약관'] as $locale=>$title) {
        foreach ([false,true] as $ready) foreach (['operator','terms','privacy','points'] as $section) {
            $smarty->assign(['ordenowa_policy_ready'=>$ready,'ordenowa_policy_title'=>$title,'ordenowa_policy_unavailable'=>'SYNTHETIC preparing',
                'ordenowa_policy_operator'=>$section==='operator'?['operator_name'=>$hostile,'support_email'=>'synthetic-support@example.test','support_phone'=>$hostile,'support_url'=>'https://support.example.test/']:[],
                'ordenowa_policy_text'=>$hostile,"ordenowa_policy_version"=>1]);
            $html=$smarty->fetch($template);
            $assert(!str_contains($html,'<script>'),'untrusted policy/operator content must remain plain text');
            $assert(str_contains($html,'<title>')&&str_contains($html,'| ORDENOWA</title>'),'translated document title');
            $assert(str_contains($html,'data-testid="procurement-public-policy"'),'public policy marker');
            if (!$ready) $assert(str_contains($html,'SYNTHETIC preparing')&&!str_contains($html,'synthetic-support@example.test'),'incomplete fields never leak as published policy');
            else $assert(str_contains($html,'&lt;script&gt;'),'supplied operator and policy text is escaped');
        }
    }
    echo 'policies_smarty: PASS '.$checks.' actual Smarty checks across24 locale/section/readiness renders' . PHP_EOL;
} finally {
    $iterator=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($directory,FilesystemIterator::SKIP_DOTS),RecursiveIteratorIterator::CHILD_FIRST);
    foreach($iterator as$file){if($file->isDir())rmdir($file->getPathname());else unlink($file->getPathname());} rmdir($directory);
}
