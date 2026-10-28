<?php

declare(strict_types=1);
define('_DB_PREFIX_','fixture_');
require_once __DIR__.'/../../modules/kuraneacatalog/autoload.php';
require_once __DIR__.'/prepare_ci_procurement_product.php';
function categoryAssert(bool $ok,string $label): void { if (!$ok) throw new RuntimeException($label); }
class Configuration { public static function get(string $key): int { return 2; } }
class Product { public static function getProductCategories(int $id): array { categoryAssert($id===17,'Only approved native product is read'); return [91]; } }
class Group { public static function getGroups(int $lang,int $shop): array { return [['id_group'=>1],['id_group'=>2],['id_group'=>3]]; } }
class Context { public static function getContext(): object { return (object)['language'=>(object)['id'=>1]]; } }
class Language { public static function getLanguages(bool $active): array { return [['id_lang'=>1,'iso_code'=>'ja'],['id_lang'=>2,'iso_code'=>'en'],['id_lang'=>3,'iso_code'=>'ko']]; } }
class Db { public static function getInstance(): object { return new class { public function getValue(string $sql,bool $cache): int { return 0; } }; } }
#[AllowDynamicProperties]
class Category {
    public static array $created=[];
    public int $id=0;
    public function add(): bool { $this->id=100+count(self::$created); self::$created[]=$this; return true; }
    public function associateTo(array $shops): bool { categoryAssert($shops===[1],'Category limited to current shop'); return true; }
}
function pSQL(string $value): string { return addslashes($value); }
$entry=(object)['status'=>'pending','nativeProductId'=>null,'snapshot'=>(object)['categories'=>['生活用品 > キッチン用品']]];
categoryAssert(prepareCiProcurementReviewedCategoryIds('primary',$entry,1,'123','4')===[2] && Category::$created===[],'Default primary remains Home without creating taxonomy');
$approved=(object)['status'=>'approved','nativeProductId'=>17,'snapshot'=>$entry->snapshot];
categoryAssert(prepareCiProcurementReviewedCategoryIds('gallery',$approved,1,'123','4')===[91] && Category::$created===[],'Approved gallery preserves actual native categories without retrofitting');
$ids=prepareCiProcurementReviewedCategoryIds('gallery',$entry,1,'123','4');
categoryAssert($ids===[101] && count(Category::$created)===2,'Fresh pending gallery selects reviewed leaf');
categoryAssert(Category::$created[0]->id_parent===2 && Category::$created[1]->id_parent===100,'Native parent-child relation follows reviewed source path');
categoryAssert(Category::$created[0]->name===[1=>'生活用品',2=>'Daily necessities',3=>'생활용품'] && Category::$created[1]->name===[1=>'キッチン用品',2=>'Kitchenware',3=>'주방용품'],'Category names have explicit JA EN KO review');
categoryAssert(Category::$created[0]->active===1 && Category::$created[1]->groupBox===[1,2,3],'Native categories active with explicit current groups');
$entry->snapshot->categories=['Unreviewed > Different'];
try { prepareCiProcurementReviewedCategoryIds('gallery',$entry,1,'123','4'); throw new LogicException('Unreviewed source was classified'); }
catch (RuntimeException $error) { categoryAssert(!$error instanceof LogicException,'Wrong source rejected'); }
categoryAssert(count(Category::$created)===2,'Unreviewed path creates no category');
$entry->status='rejected';
try { prepareCiProcurementReviewedCategoryIds('gallery',$entry,1,'123','4'); throw new LogicException('Rejected source was classified'); }
catch (RuntimeException $error) { categoryAssert(!$error instanceof LogicException,'Rejected source cannot create taxonomy'); }
categoryAssert(count(Category::$created)===2,'Rejected source creates no category');
echo "PASS synthetic category placement guards: primary unchanged, approved preserved, pending source path mapped to native JA EN KO leaf only\n";
