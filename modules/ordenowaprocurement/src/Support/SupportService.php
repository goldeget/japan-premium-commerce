<?php

declare(strict_types=1);
namespace Ordenowa\Procurement\Support;

use Ordenowa\Procurement\Infrastructure\{Database,Recorder};
use Ordenowa\Procurement\Security\Actor;

/** A request links to native support; native support keeps public/private replies and assignments. */
final class SupportService
{
    private string $prefix;
    public function __construct(private Database $db, ?string $nativePrefix = null)
    {
        $this->prefix = $nativePrefix ?? (defined('_DB_PREFIX_') ? (string)_DB_PREFIX_ : '');
        if (!preg_match('/\A[A-Za-z0-9_]*\z/D',$this->prefix)) throw new \InvalidArgumentException('Invalid native prefix.',422);
    }

    public function thread(Actor $actor, int $requestId): array
    {
        $this->customer($actor);
        $this->request($actor,$requestId);
        return $this->read($actor,$requestId);
    }

    public function post(Actor $actor, int $requestId, string $body, string $key): array
    {
        $this->customer($actor);
        $body = trim(str_replace(["\r\n","\r"],"\n",$body));
        if ($body === '' || !mb_check_encoding($body,'UTF-8') || mb_strlen($body,'UTF-8') > 2000
            || preg_match('/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/',$body)) throw new \InvalidArgumentException('Invalid support message.',422);
        if (!preg_match('/\A[a-f0-9]{64}\z/D',$key)) throw new \InvalidArgumentException('Invalid message key.',422);
        return $this->db->transaction(function () use ($actor,$requestId,$body,$key): array {
            // One customer's posts serialize before request locking, including key reuse across requests.
            $identity = $this->db->one('SELECT email,id_lang FROM ' . $this->native('customer') . ' WHERE id_customer=' . $actor->id
                . ' AND id_shop=' . $actor->shopId . ' AND active=1 AND deleted=0 AND is_guest=0 FOR UPDATE');
            if (!$identity || !filter_var($identity['email'],FILTER_VALIDATE_EMAIL) || (int)$identity['id_lang'] < 1) $this->missing();
            $request = $this->request($actor,$requestId,true);
            $keyHash = hash('sha256',$key);
            $payloadHash = hash('sha256',json_encode([$actor->shopId,$actor->id,$requestId,$body],JSON_THROW_ON_ERROR));
            $receipt = $this->db->one('SELECT * FROM ' . $this->db->table('support_post') . ' WHERE id_shop=' . $actor->shopId
                . ' AND id_customer=' . $actor->id . ' AND key_hash=' . $this->db->quote($keyHash) . ' LIMIT 1');
            if ($receipt) {
                if ((int)$receipt['id_request'] !== $requestId || !hash_equals($receipt['payload_hash'],$payloadHash)) throw new \RuntimeException('Message key already used.',409);
                return $this->read($actor,$requestId) + ['duplicate'=>true];
            }
            $link = $this->link($actor,$requestId,true);
            if ($link === null) {
                $contact = (int)$this->db->value('SELECT c.id_contact FROM ' . $this->native('contact') . ' c INNER JOIN '
                    . $this->native('contact_shop') . ' cs ON cs.id_contact=c.id_contact AND cs.id_shop=' . $actor->shopId . ' ORDER BY c.id_contact LIMIT 1');
                if ($contact < 1) throw new \RuntimeException('Support contact unavailable.',503);
                $snapshot = json_decode($request['product_snapshot'],true,64,JSON_THROW_ON_ERROR);
                $threadId = (new NativeSupportWriter())->thread(['id_shop'=>$actor->shopId,'id_customer'=>$actor->id,
                    'id_lang'=>(int)$identity['id_lang'],'id_contact'=>$contact,'id_product'=>(int)($snapshot['id_product'] ?? 0),'email'=>$identity['email']]);
                $this->db->execute('INSERT INTO ' . $this->db->table('support_link')
                    . ' (id_shop,id_customer,id_request,id_customer_thread) VALUES (' . $actor->shopId . ',' . $actor->id . ',' . $requestId . ',' . $threadId . ')');
                $link = $this->link($actor,$requestId,true);
            }
            $threadId = $this->verifiedThread($actor,$link,true);
            $messageId = (new NativeSupportWriter())->message($threadId,$body);
            $this->db->execute('UPDATE ' . $this->native('customer_thread') . " SET status='open',date_upd=UTC_TIMESTAMP() WHERE id_customer_thread=" . $threadId);
            $this->db->execute('INSERT INTO ' . $this->db->table('support_post')
                . ' (id_shop,id_customer,id_request,id_customer_thread,id_customer_message,key_hash,payload_hash,created_at) VALUES ('
                . $actor->shopId . ',' . $actor->id . ',' . $requestId . ',' . $threadId . ',' . $messageId . ',' . $this->db->quote($keyHash) . ',' . $this->db->quote($payloadHash) . ',UTC_TIMESTAMP())');
            (new Recorder($this->db))->audit($actor,'support.message_created','request',$requestId,['id_request'=>$requestId]);
            return $this->read($actor,$requestId) + ['duplicate'=>false];
        });
    }

    public function adminThreadId(Actor $actor, int $requestId): ?int
    {
        $actor->require('procurement.read');
        $request = $this->request($actor,$requestId);
        $owner = Actor::customer($actor->shopId,(int)$request['id_customer']);
        $link = $this->link($owner,$requestId);
        return $link === null ? null : $this->verifiedThread($owner,$link);
    }

    private function read(Actor $actor,int $request): array
    {
        $link = $this->link($actor,$request);
        if ($link === null) return ['id_request'=>$request,'thread_exists'=>false,'messages'=>[]];
        $thread = $this->verifiedThread($actor,$link);
        $rows = $this->db->all('SELECT cm.id_customer_message,cm.id_employee,cm.message,cm.date_add FROM ' . $this->native('customer_message') . ' cm'
            . ' INNER JOIN ' . $this->native('customer_thread') . ' ct ON ct.id_customer_thread=cm.id_customer_thread'
            . ' WHERE cm.id_customer_thread=' . $thread . ' AND ct.id_shop=' . $actor->shopId . ' AND ct.id_customer=' . $actor->id
            . ' AND cm.private=0 ORDER BY cm.id_customer_message DESC LIMIT 100');
        $messages = [];
        foreach (array_reverse($rows) as $row) {
            $text = preg_replace('~</?(?:p|div|br|li)\b[^>]*>~i',' ',(string)$row['message']);
            $messages[] = ['body'=>html_entity_decode(strip_tags($text ?? ''),ENT_QUOTES | ENT_HTML5,'UTF-8'),
                'sender'=>(int)$row['id_employee'] > 0 ? 'operator' : 'you','date'=>(string)$row['date_add']];
        }
        return ['id_request'=>$request,'thread_exists'=>true,'messages'=>$messages];
    }

    private function link(Actor $actor,int $request,bool $lock=false): ?array
    {
        $row = $this->db->one('SELECT * FROM ' . $this->db->table('support_link') . ' WHERE id_shop=' . $actor->shopId
            . ' AND id_request=' . $request . ' LIMIT 1' . ($lock ? ' FOR UPDATE' : ''));
        if ($row && (int)$row['id_customer'] !== $actor->id) $this->missing();
        return $row;
    }

    private function verifiedThread(Actor $actor,?array $link,bool $lock=false): int
    {
        if (!$link) $this->missing();
        $thread = (int)$link['id_customer_thread'];
        if (!$this->db->one('SELECT id_customer_thread FROM ' . $this->native('customer_thread') . ' WHERE id_customer_thread=' . $thread
            . ' AND id_shop=' . $actor->shopId . ' AND id_customer=' . $actor->id . ' LIMIT 1' . ($lock ? ' FOR UPDATE' : ''))) $this->missing();
        return $thread;
    }

    private function request(Actor $actor,int $id,bool $lock=false): array
    {
        if ($id < 1) $this->missing();
        $row = $this->db->one('SELECT * FROM ' . $this->db->table('request') . ' WHERE id_request=' . $id . ' AND id_shop=' . $actor->shopId
            . ($actor->type === 'customer' ? ' AND id_customer=' . $actor->id : '') . ' LIMIT 1' . ($lock ? ' FOR UPDATE' : ''));
        if (!$row) $this->missing();
        return $row;
    }
    private function customer(Actor $actor): void { if ($actor->type !== 'customer') throw new \RuntimeException('Customer required.',403); }
    private function missing(): never { throw new \RuntimeException('Not found.',404); }
    private function native(string $table): string { return '`' . $this->prefix . $table . '`'; }
}
