<?php
declare(strict_types=1);
$root=dirname(__DIR__,2);
$bootstrap=getenv('PROCUREMENT_SMARTY_BOOTSTRAP')?:'/var/www/html/vendor/smarty/smarty/libs/Smarty.class.php';
if (!is_file($bootstrap)) throw new RuntimeException('Installed Smarty dependency required.');
require $bootstrap;
$directory=sys_get_temp_dir().'/ordenowa-language-selector-'.bin2hex(random_bytes(6));
mkdir($directory,0700,true);
$smarty=new Smarty(); $smarty->setCompileDir($directory);
$locale='en-US'; $localized=false; $catalogs=[]; $checks=0;
$assert=static function(bool $condition)use(&$checks):void{++$checks;if(!$condition)throw new RuntimeException('Native language selector localization contract failed.');};
foreach (['ja-JP'=>'言語を変更','ko-KR'=>'언어 변경'] as $targetLocale=>$expected) {
    $document=new DOMDocument();
    $assert($document->load($root.'/themes/kuranea/translations/'.$targetLocale.'/ShopThemeGlobal.'.$targetLocale.'.xlf'));
    $xpath=new DOMXPath($document);
    $files=$xpath->query('//*[local-name()="file"]');
    $assert($files->length===1&&$files->item(0)->getAttribute('target-language')===$targetLocale&&$files->item(0)->getAttribute('original')==='Shop.Theme.Global');
    $units=$xpath->query('//*[local-name()="trans-unit"]');
    $assert($units->length===1);
    $source=$xpath->query('./*[local-name()="source"]',$units->item(0))->item(0)->textContent;
    $target=$xpath->query('./*[local-name()="target"]',$units->item(0))->item(0)->textContent;
    $assert($source==='Change language'&&$target===$expected);
    $catalogs[$targetLocale][$source]=$target;
}
$smarty->registerPlugin('function','l',static function(array $params)use(&$locale,&$localized,&$catalogs):string{
    if(($params['d']??null)!=='Shop.Theme.Global')throw new RuntimeException('Unexpected native translation domain');
    return htmlspecialchars($localized?($catalogs[$locale][$params['s']]??$params['s']):$params['s'],ENT_QUOTES,'UTF-8');
});
$smarty->registerPlugin('function','url',static function(array $params):string{return '/language/'.(int)$params['id'];});
$template=$root.'/themes/hummingbird/modules/ps_languageselector/ps_languageselector.tpl';
$names=['ja'=>'日本語','en'=>'English','ko'=>'한국어'];
$ids=['ja'=>1,'en'=>2,'ko'=>3];
$languages=[];foreach($ids as$iso=>$id)$languages[]=['id_lang'=>$id,'iso_code'=>$iso,'name_simple'=>$names[$iso]];
foreach (['ja-JP'=>'言語を変更','en-US'=>'Change language','ko-KR'=>'언어 변경']as$locale=>$expected) {
    $selected=$ids[substr($locale,0,2)];
    $smarty->assign(['languages'=>$languages,'current_language'=>['id_lang'=>$selected]]);
    $localized=false;$before=$smarty->fetch($template);$localized=true;$after=$smarty->fetch($template);
    $assert(str_replace('aria-label="'.$expected.'"','aria-label="Change language"',$after)===$before);
    $doc=new DOMDocument();$previous=libxml_use_internal_errors(true);$doc->loadHTML('<?xml encoding="UTF-8">'.$after);libxml_clear_errors();libxml_use_internal_errors($previous);
    $xpath=new DOMXPath($doc);$selects=$xpath->query('//select');$assert($selects->length===1);
    $select=$selects->item(0);$assert($select->getAttribute('aria-label')===$expected);
    $assert($select->getAttribute('class')==='form-select js-language-selector');
    $options=$xpath->query('//select/option');$assert($options->length===3);
    foreach($options as$index=>$option){$iso=array_keys($ids)[$index];$assert($option->textContent===$names[$iso]&&$option->getAttribute('data-iso-code')===$iso&&$option->getAttribute('value')==='/language/'.$ids[$iso]);$assert($option->hasAttribute('selected')===($ids[$iso]===$selected));}
}
echo 'PASS '.$checks.' actual Smarty native language selector checks; JA/EN/KO labels, exact option/selection/layout parity'.PHP_EOL;
