<?php
declare(strict_types=1);
namespace Ordenowa\Procurement\Integration {
    final class Runtime {
        public static int $customer = 10;
        public static object $service;
        public static array $pointActors=[];
        public static string $notificationQuery='';
        public static function procurementEnabled(): bool { return true; }
        public static function customerActor(): object { if (!self::$customer) throw new \RuntimeException('denied',403); return (object)['id'=>self::$customer,'shopId'=>1]; }
        public static function requests(): object { return self::$service; }
        public static function points(): object { return new class { public function ledger(object $actor,?int $customer=null,array $filters=[]):array{Runtime::$pointActors[]=$actor->id;return [];} public function account(object $actor):array{Runtime::$pointActors[]=$actor->id;return ['balance'=>0];} }; }
        public static function database():object{return new class {public function table(string $suffix):string{return 'ps_ordenowa_'.$suffix;}public function all(string $sql):array{Runtime::$notificationQuery=$sql;return [];}};}
    }
}
namespace {
    use Ordenowa\Procurement\Integration\Runtime;
    use Ordenowa\Procurement\Presentation\WorkspaceView;
    class ModuleFrontController {
        public object $context;
        public function __construct() {
            $this->context=(object)['language'=>(object)['iso_code'=>'en'],'link'=>new class {
                public function getModuleLink(string $module,string $controller,array $params=[],bool $ssl=true):string {return 'https://ordenowa.example/index.php?'.http_build_query(['fc'=>'module','module'=>$module,'controller'=>$controller]+$params);}
                public function getPageLink(string $page,bool $ssl=true):string{return 'https://ordenowa.example/'.$page;}
            },'smarty'=>new class {
                public array $vars=['page'=>['meta'=>['robots'=>'index'],'canonical'=>'secret']];
                public function assign($key,$value=null):void {$this->vars[$key]=$value;}
                public function getTemplateVars(string $key){return $this->vars[$key]??null;}
            }];
        }
        public function initContent():void {}
        public function setTemplate(string $template):void {}
    }
    class Tools {
        public static array $input=[];
        public static string $redirect='';
        public static function getValue(string $name,$default=false){return self::$input[$name]??$default;}
        public static function getToken(bool $ignored):string {return 'native-csrf-'.Runtime::$customer;}
        public static function redirect(string $url):void {self::$redirect=$url;}
    }
    require dirname(__DIR__, 2) . '/modules/ordenowaprocurement/controllers/front/workspace.php';
    $checks=0;
    function check(bool $condition,string $name):void {global $checks; ++$checks; if(!$condition)throw new \RuntimeException('FAIL '.$name);}
    $service = new class {
        public int $submits=0;
        public int $listCount=1;
        public array $last=[];
        public array $filters=[];
        public array $imageUrls=[];
        public function assignment(object $actor,int $id):array {
            if($actor->id!==10||$id!==1)throw new \RuntimeException('not found',404);
            return ['id_assignment'=>1,'version'=>2,'status'=>'ACTIVE','default_quantity'=>1,'max_quantity'=>3,'instructions'=>'<script>instructions</script>','product_snapshot'=>['names'=>['ja'=>'日本語','en'=>'<script>alert(1)</script>'],'descriptions'=>['en'=>'<img onerror="bad">'],'image_url'=>'javascript:alert(1)','image_urls'=>$this->imageUrls,'reference'=>'REF','categories'=>[['id_category'=>3,'id_parent'=>2,'names'=>['en'=>'Kitchen']]],'reference_price'=>'123.00','currency'=>'JPY'],'internal_note'=>'secret'];
        }
        public function submit(object $actor,int $id,int $version,int $quantity,string $key):array {
            $this->assignment($actor,$id);
            if($version!==2)throw new \RuntimeException('stale',409);
            if($quantity>3)throw new \InvalidArgumentException('range',422);
            ++$this->submits;$this->last=[$actor->id,$id,$version,$quantity,$key];return ['id_request'=>9];
        }
        public function request(object $actor,int $id):array {
            if($id!==9)throw new \RuntimeException('not found',404);
            return $this->assignment($actor,1)+['id_request'=>9,'quantity'=>2,'submitted_at'=>'2026-10-29 00:00:00'];
        }
        public function customerRequests(object $actor,array $filters=[]):array{return $actor->id===10?[$this->request($actor,9)]:[];}
        public function customerAssignments(object $actor,array $filters=[]):array {
            $this->filters=$filters;
            if($actor->id!==10)return [];
            $rows=[];
            for($i=$this->listCount;$i>0;--$i){if(isset($filters['before_id'])&&$filters['before_id']>0&&$i>=$filters['before_id'])continue;$row=$this->assignment($actor,1);$row['id_assignment']=$i;$rows[]=$row;}
            return array_slice($rows,0,$filters['limit']??50);
        }
        public function customerCategories(object $actor):array{return $actor->id===10?[['id_category'=>3,'id_parent'=>2,'names'=>['en'=>'Kitchen']]]:[];}
    };
    Runtime::$service=$service;
    function page(array $input=[],string $method='GET'):array {Tools::$input=$input;Tools::$redirect='';$_SERVER['REQUEST_METHOD']=$method;$c=new OrdenowaprocurementWorkspaceModuleFrontController();$c->initContent();return [$c->context->smarty->vars['ow']??[],$c->context->smarty->vars['page']];}
    [$a,$meta]=page(['view'=>'assignment','id_assignment'=>'1']);
    check($a['error']===''&&$a['item']['id']===1,'owner detail');check($a['item']['image']==='','unsafe image omitted');check(!isset($a['item']['internal_note']),'internal note absent');check($meta['meta']['robots']==='noindex, nofollow, noarchive'&&$meta['canonical']==='','private metadata');
    $base=['id_assignment'=>'1','version'=>'2','quantity'=>'2','token'=>'native-csrf-10'];
    [$confirmation]=page($base+['action'=>'confirm'],'POST');check($confirmation['view']==='confirm'&&$confirmation['quantity']===2&&strlen($confirmation['idempotency_key'])===64,'explicit confirmation with unique key');check($service->submits===0,'confirmation has no mutation');
    [$badcsrf]=page(array_replace($base,['token'=>'forged','action'=>'submit','idempotency_key'=>str_repeat('a',64)]),'POST');check($badcsrf['error_status']===403&&$service->submits===0,'CSRF denied before mutation');
    [$stale]=page(array_replace($base,['version'=>'1','action'=>'confirm']),'POST');check($stale['error_status']===409,'stale confirmation denied');
    [$badqty]=page(array_replace($base,['quantity'=>'0','action'=>'confirm']),'POST');check($badqty['error_status']===422,'zero quantity denied');
    [$largeqty]=page(array_replace($base,['quantity'=>'4','action'=>'confirm']),'POST');check($largeqty['error_status']===422,'overlimit quantity denied');
    [$getaction]=page(['action'=>'submit','id_assignment'=>'1']);check($getaction['error_status']===422,'GET action denied');
    [$clientid]=page(['view'=>'points','id_customer'=>'20']);check($clientid['error_status']===404,'client beneficiary forbidden');
    Runtime::$customer=20;
    [$b]=page(['view'=>'assignment','id_assignment'=>'1']);check($b['error_status']===404&&$b['item']===[]&&Runtime::$customer===20,'B detail denied and session preserved');
    [$bpost]=page(array_replace($base,['token'=>'native-csrf-20','action'=>'submit','idempotency_key'=>str_repeat('b',64)]),'POST');check($bpost['error_status']===404&&$service->submits===0&&Runtime::$customer===20,'B valid CSRF owner POST denied');
    [$brequest]=page(['view'=>'request','id_request'=>'9']);check($brequest['error_status']===404&&$brequest['item']===[]&&Runtime::$customer===20,'B request detail denied and session preserved');
    [$brequests]=page(['view'=>'requests']);check($brequests['error']===''&&$brequests['items']===[],'B request list empty');
    Runtime::$pointActors=[];[$bpoints]=page(['view'=>'points']);check($bpoints['balance']===0&&$bpoints['ledger']===[]&&Runtime::$pointActors===[20,20],'B point reads use session actor only');
    [$bnotifications]=page(['view'=>'notifications']);check($bnotifications['notifications']===[]&&str_contains(Runtime::$notificationQuery,'WHERE id_shop=1 AND id_customer=20'),'notification SQL scopes shop and customer from actor');
    Runtime::$customer=10;
    [$submit]=page($base+['action'=>'submit','idempotency_key'=>$confirmation['idempotency_key'],'product_snapshot'=>'forged','amount'=>'1000000'],'POST');check($service->submits===1&&$service->last[0]===10&&$service->last[3]===2&&str_contains(Tools::$redirect,'id_request=9'),'native actor submit then redirect');
    [$requestView]=page(['view'=>'request','id_request'=>'9']);check(str_contains($requestView['support_url'],'controller=support')&&str_contains($requestView['support_url'],'id_request=9'),'support URL derives from authorized request readback');
    foreach(['ja','en','ko','fr']as$locale){$p=new WorkspaceView($locale);check(count($p->copy())===count((new WorkspaceView('ja'))->copy()),'complete translation '.$locale);}
    foreach(['javascript:alert(1)','data:image/svg+xml,bad','https://127.0.0.1/a','https://user:pass@public.co.jp/a','http://public.co.jp/a','https://public.co.jp:8443/a','https://foo.internal/a']as$url){check(WorkspaceView::publicImage($url)==='','unsafe image '.$url);}
    check(WorkspaceView::publicImage('https://images.public.co.jp/photo.jpg')==='https://images.public.co.jp/photo.jpg','public https image');
    foreach(['/img/p/../1.jpg','/img/p/1/1.jpg?customer=20','/img/p/1/1.jpg#private','/img/p/1/%31.jpg','/img/p/1/1.svg','//public.co.jp/img.jpg','/module/private/photo/1']as$url){check(WorkspaceView::publicImage($url)==='','noncanonical native image denied '.$url);}
    $photoRow=$service->assignment((object)['id'=>10],1);
    $photoRow['product_snapshot']['image_url']='/img/p/1/1-large_default.jpg';
    $photoRow['product_snapshot']['image_urls']=['/img/p/1/1-large_default.jpg','/img/p/2/2-large_default.jpg','/img/p/2/2-large_default.jpg','javascript:alert(1)','https://127.0.0.1/private.jpg'];
    $gallery=(new WorkspaceView('en'))->assignment($photoRow);
    check($gallery['image']==='/img/p/1/1-large_default.jpg'&&$gallery['images']===['/img/p/1/1-large_default.jpg','/img/p/2/2-large_default.jpg']&&$gallery['image_count']===2,'gallery preserves safe cover and all approved distinct photos');
    $photoRow['product_snapshot']['image_url']='';$gallery=(new WorkspaceView('en'))->assignment($photoRow);
    check($gallery['image']==='/img/p/1/1-large_default.jpg','first approved photo supplies missing cover');
    $photoRow['product_snapshot']['image_urls']=array_map(static fn(int $n):string=>'/img/p/'.$n.'/'.$n.'-large_default.jpg',range(1,25));
    check((new WorkspaceView('en'))->assignment($photoRow)['image_count']===20,'gallery display bounded to twenty trusted photos');
    $service->imageUrls=['/img/p/1/1-large_default.jpg','/img/p/2/2-large_default.jpg'];[$ownedGallery]=page(['view'=>'assignment','id_assignment'=>'1']);check($ownedGallery['item']['image_count']===2,'controller forwards only authorized snapshot gallery');
    Runtime::$customer=20;[$deniedGallery]=page(['view'=>'assignment','id_assignment'=>'1']);check($deniedGallery['error_status']===404&&$deniedGallery['item']===[]&&Runtime::$customer===20,'B denied gallery detail without changing session');Runtime::$customer=10;
    $p=new WorkspaceView('en');$tree=$p->categoryTree([2=>['id'=>2,'parent'=>1,'name'=>'Home'],3=>['id'=>3,'parent'=>2,'name'=>'Kitchen'],4=>['id'=>4,'parent'=>5,'name'=>'Cycle A'],5=>['id'=>5,'parent'=>4,'name'=>'Cycle B']]);check($tree[0]['children'][0]['id']===3&&count($tree)===2,'owned category hierarchy and bounded cycles');
    $service->listCount=52;
    [$paged]=page(['q'=>'商品','status'=>'ACTIVE','category'=>'3']);
    check(count($paged['items'])===50&&$paged['items'][0]['id']===52&&$paged['items'][49]['id']===3,'first page has fifty real service rows');
    parse_str((string)parse_url($paged['next_url'],PHP_URL_QUERY),$next);
    check($next['before_id']==='3'&&$next['q']==='商品'&&$next['status']==='ACTIVE'&&$next['category']==='3','cursor preserves search status category');
    check($service->filters['category_id']===3&&$service->filters['limit']===51&&$service->filters['q']==='商品','filters reach owner-scoped service');
    [$lastpage]=page(['before_id'=>'3']);check(count($lastpage['items'])===2&&$lastpage['next_url']===''&&count($lastpage['categories'])===1,'final page and all-own category menu');
    [$unknownCategory]=page(['category'=>'4']);check($unknownCategory['error_status']===404&&$unknownCategory['items']===[],'unknown category reveals no products');
    [$badstatus]=page(['status'=>'APPROVED']);check($badstatus['error_status']===422,'list rejects invalid status');
    Runtime::$customer=0;[$unauthenticated]=page();check($unauthenticated['error_status']===403,'unauthenticated actor denied');
    echo "PASS $checks customer controller/presentation checks (native boundaries stubbed; real domain covered separately)\n";
}
