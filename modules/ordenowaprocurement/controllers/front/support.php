<?php

declare(strict_types=1);
require_once dirname(__FILE__,3) . '/autoload.php';

use Ordenowa\Procurement\Integration\Runtime;
use Ordenowa\Procurement\Support\{SupportService,SupportView};

class OrdenowaprocurementSupportModuleFrontController extends ModuleFrontController
{
    public $auth = true;
    public $guestAllowed = false;
    public $ssl = true;

    public function init(): void
    {
        $this->privateHeaders();
        parent::init();
        $this->privateHeaders();
    }
    private function privateHeaders(): void
    {
        header('Cache-Control: private, no-store, no-cache, max-age=0, must-revalidate');
        header('Pragma: no-cache');
        header('Expires: 0');
        header('X-Robots-Tag: noindex, nofollow, noarchive');
        header('Referrer-Policy: same-origin');
        header('X-Content-Type-Options: nosniff');
    }
    public function initContent(): void
    {
        parent::initContent();
        $copy = SupportView::copy((string)($this->context->language->iso_code ?? 'ja'));
        $data = ['copy'=>$copy,'messages'=>[],'error'=>'','allowed'=>false,'url'=>'','back_url'=>'',
            'id_request'=>0,'token'=>(string)Tools::getToken(false),'idempotency_key'=>bin2hex(random_bytes(32))];
        try {
            if (!Runtime::procurementEnabled()) throw new RuntimeException('Support unavailable.',503);
            $actor = Runtime::customerActor();
            foreach (['id_customer','customer_id','id_shop','id_employee','id_customer_thread','thread_id','thread_token','email','private','role'] as $field) {
                if (Tools::getValue($field) !== false) throw new RuntimeException('Not found.',404);
            }
            $id = Tools::getValue('id_request');
            if (!is_string($id) || !preg_match('/\A[1-9][0-9]{0,9}\z/D',$id)) throw new RuntimeException('Not found.',404);
            $requestId = (int)$id;
            $service = new SupportService(Runtime::database());
            $method = strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? 'GET'));
            if ($method === 'POST') {
                $token = Tools::getValue('token');
                if (!is_string($token) || !hash_equals((string)Tools::getToken(false),$token)) throw new RuntimeException('Invalid request.',403);
                if ($_FILES !== [] || Tools::getValue('action') !== 'message') throw new RuntimeException('Invalid request.',422);
                $body = Tools::getValue('message');
                $key = Tools::getValue('idempotency_key');
                if (!is_string($body) || !is_string($key)) throw new RuntimeException('Invalid request.',422);
                $service->post($actor,$requestId,$body,$key);
                Tools::redirect($this->context->link->getModuleLink('ordenowaprocurement','support',['id_request'=>$requestId]));
                return;
            }
            if ($method !== 'GET' || Tools::getValue('action') !== false) throw new RuntimeException('Invalid request.',422);
            $thread = $service->thread($actor,$requestId);
            $data['messages'] = $thread['messages'];
            $data['id_request'] = $thread['id_request'];
            $data['allowed'] = true;
            $data['url'] = $this->context->link->getModuleLink('ordenowaprocurement','support',['id_request'=>$thread['id_request']]);
            $data['back_url'] = $this->context->link->getModuleLink('ordenowaprocurement','workspace',['view'=>'request','id_request'=>$thread['id_request']]);
        } catch (Throwable $error) {
            $status = (int)$error->getCode();
            http_response_code(in_array($status,[403,404,409,422,503],true) ? $status : 500);
            $data['error'] = $copy['error'];
        }
        $this->context->smarty->assign(['ordenowa_support'=>$data]);
        $this->setTemplate('module:ordenowaprocurement/views/templates/front/support.tpl');
    }
}
