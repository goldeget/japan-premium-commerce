<?php

declare(strict_types=1);
namespace Kuranea\Push\Infrastructure;

use Kuranea\Push\Domain\{DeliveryPayload, PushDeliveryStore, PushOutboxStore};

/** MySQL/InnoDB durable receipts. Advisory locks serialize one owner's event across processes. */
final class PushOutboxRepository implements PushOutboxStore
{
    private object $db;
    private string $events;
    private string $recipients;
    private string $attempts;
    private array $held = [];

    public function __construct(?object $db = null, ?string $prefix = null)
    {
        try { $this->db = $db ?? \Db::getInstance(); }
        catch (\Throwable $error) { throw new \RuntimeException('Storage unavailable.'); }
        $prefix ??= _DB_PREFIX_;
        if (preg_match('/\A[A-Za-z0-9_]*\z/D',$prefix)!==1) { throw new \RuntimeException('Storage unavailable.'); }
        $this->events='`'.$prefix.'kuraneapush_event`';
        $this->recipients='`'.$prefix.'kuraneapush_recipient`';
        $this->attempts='`'.$prefix.'kuraneapush_attempt`';
    }

    public function install(): bool
    {
        $owner='id_shop INT UNSIGNED NOT NULL,id_customer INT UNSIGNED NOT NULL,event_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,';
        $digest='endpoint_digest CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,';
        $tail=' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci';
        try {
            return (bool)$this->db->execute('CREATE TABLE IF NOT EXISTS '.$this->events.' ('.$owner
            .'event_type VARCHAR(16) CHARACTER SET ascii NOT NULL,locale CHAR(2) CHARACTER SET ascii NOT NULL,received_at DATETIME NOT NULL,'
            .'PRIMARY KEY(id_shop,id_customer,event_id))'.$tail)
            && (bool)$this->db->execute('CREATE TABLE IF NOT EXISTS '.$this->recipients.' ('.$owner.$digest
            .'consent_generation CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,'
            .'outcome VARCHAR(32) CHARACTER SET ascii NOT NULL,attempts INT UNSIGNED NOT NULL DEFAULT 0,updated_at DATETIME NOT NULL,'
            .'PRIMARY KEY(id_shop,id_customer,event_id,endpoint_digest))'.$tail)
            && (bool)$this->db->execute('CREATE TABLE IF NOT EXISTS '.$this->attempts.' ('.$owner.$digest
            .'attempt_number INT UNSIGNED NOT NULL,outcome VARCHAR(32) CHARACTER SET ascii NOT NULL,started_at DATETIME NOT NULL,completed_at DATETIME NULL,'
            .'PRIMARY KEY(id_shop,id_customer,event_id,endpoint_digest,attempt_number))'.$tail);
        } catch (\Throwable $error) {
            return false;
        }
    }

    public function acquire(int $shop,int $customer,string $eventId): bool
    {
        $scope=$this->scope($shop,$customer,$eventId);
        $lock=hash('sha256',$this->events."\0".$scope);
        if (isset($this->held[$scope])) { return false; }
        $rows=$this->read("SELECT GET_LOCK('".$lock."',0) AS acquired");
        if ((string)($rows[0]['acquired']??'')!=='1') { return false; }
        $this->held[$scope]=$lock;
        return true;
    }

    public function release(int $shop,int $customer,string $eventId): void
    {
        $scope=$this->scope($shop,$customer,$eventId);
        $this->assertHeld($scope);
        $lock=$this->held[$scope];
        $rows=$this->read("SELECT RELEASE_LOCK('".$lock."') AS released");
        if ((string)($rows[0]['released']??'')!=='1') { throw new \RuntimeException('Event lock unavailable.'); }
        unset($this->held[$scope]);
    }

    public function event(int $shop,int $customer,string $eventId): ?array
    {
        $scope=$this->scope($shop,$customer,$eventId);$this->assertHeld($scope);
        $rows=$this->read('SELECT event_type,locale FROM '.$this->events.$scope.' LIMIT 1');
        if ($rows===[]) { return null; }
        $recipients=$this->read('SELECT endpoint_digest,consent_generation,outcome,attempts FROM '.$this->recipients.$scope
            .' ORDER BY endpoint_digest LIMIT '.(PushDeliveryStore::MAX_DELIVERY_TARGETS+1));
        if (count($recipients)>PushDeliveryStore::MAX_DELIVERY_TARGETS) { throw new \RuntimeException('Recipient limit exceeded.'); }
        return ['event'=>$rows[0]['event_type'],'locale'=>$rows[0]['locale'],'recipients'=>$recipients];
    }

    public function create(int $shop,int $customer,string $eventId,DeliveryPayload $payload,array $recipients): void
    {
        $scope=$this->scope($shop,$customer,$eventId);$this->assertHeld($scope);
        if(count($recipients)>PushDeliveryStore::MAX_DELIVERY_TARGETS) {
            throw new \InvalidArgumentException('Invalid recipients.');
        }
        $seen=[];
        foreach($recipients as $recipient) {
            if(!is_array($recipient)) { throw new \InvalidArgumentException('Invalid recipients.'); }
            $this->digest($recipient['endpoint_digest']??null);
            $this->digest($recipient['consent_generation']??null);
            if(isset($seen[$recipient['endpoint_digest']])) { throw new \InvalidArgumentException('Invalid recipients.'); }
            $seen[$recipient['endpoint_digest']]=true;
        }
        $values=$this->ownerValues($shop,$customer,$eventId);
        $this->transaction(function()use($values,$payload,$recipients):void {
            $this->write('INSERT INTO '.$this->events.' (id_shop,id_customer,event_id,event_type,locale,received_at) VALUES ('
                .$values.",'".pSQL($payload->event)."','".pSQL($payload->locale)."',UTC_TIMESTAMP())");
            foreach($recipients as $recipient) {
                $this->write('INSERT INTO '.$this->recipients.' (id_shop,id_customer,event_id,endpoint_digest,consent_generation,outcome,attempts,updated_at) VALUES ('
                    .$values.",'".pSQL($recipient['endpoint_digest'])."','".pSQL($recipient['consent_generation'])."','pending',0,UTC_TIMESTAMP())");
            }
        });
    }

    public function startAttempt(int $shop,int $customer,string $eventId,string $digest): int
    {
        $scope=$this->scope($shop,$customer,$eventId);$this->assertHeld($scope);$this->digest($digest);
        $where=$scope." AND endpoint_digest='".pSQL($digest)."'";
        $attempt=0;
        $this->transaction(function()use($shop,$customer,$eventId,$digest,$where,&$attempt):void {
            $rows=$this->read('SELECT attempts,outcome FROM '.$this->recipients.$where.' FOR UPDATE');
            $row=$rows[0]??null;
            if (!is_array($row) || !in_array($row['outcome']??null,['pending','retryable_failure'],true)
                || !ctype_digit((string)($row['attempts']??''))) { throw new \RuntimeException('Attempt state unavailable.'); }
            $attempt=(int)$row['attempts']+1;
            $this->write('UPDATE '.$this->recipients." SET outcome='sending',attempts=".$attempt.',updated_at=UTC_TIMESTAMP()'.$where);
            $this->write('INSERT INTO '.$this->attempts.' (id_shop,id_customer,event_id,endpoint_digest,attempt_number,outcome,started_at) VALUES ('
                .$this->ownerValues($shop,$customer,$eventId).",'".pSQL($digest)."',".$attempt.",'sending',UTC_TIMESTAMP())");
        });
        return $attempt;
    }

    public function finishAttempt(int $shop,int $customer,string $eventId,string $digest,int $attempt,string $outcome): void
    {
        $scope=$this->scope($shop,$customer,$eventId);$this->assertHeld($scope);$this->digest($digest);
        if($attempt<1 || !in_array($outcome,['delivered','gone','retryable_failure','skipped','interrupted'],true)) {
            throw new \InvalidArgumentException('Invalid attempt outcome.');
        }
        $where=$scope." AND endpoint_digest='".pSQL($digest)."'";
        $this->transaction(function()use($where,$attempt,$outcome):void {
            $rows=$this->read('SELECT attempts,outcome FROM '.$this->recipients.$where.' FOR UPDATE');
            if ((int)($rows[0]['attempts']??0)!==$attempt || ($rows[0]['outcome']??null)!=='sending') {
                throw new \RuntimeException('Attempt state unavailable.');
            }
            $this->write('UPDATE '.$this->attempts." SET outcome='".pSQL($outcome)."',completed_at=UTC_TIMESTAMP()"
                .$where.' AND attempt_number='.$attempt." AND outcome='sending'");
            $this->write('UPDATE '.$this->recipients." SET outcome='".pSQL($outcome)."',updated_at=UTC_TIMESTAMP()".$where);
        });
    }

    public function deleteCustomer(int $customer, array $shopIds): void
    {
        if ($customer < 1) { throw new \InvalidArgumentException('Invalid owner.'); }
        foreach ($shopIds as $shop) {
            $shop = (int)$shop;
            if ($shop < 1) { throw new \InvalidArgumentException('Invalid owner.'); }
            $where = ' WHERE id_shop='.$shop.' AND id_customer='.$customer;
            $this->transaction(function()use($where):void {
                foreach ([$this->attempts,$this->recipients,$this->events] as $table) {
                    $this->write('DELETE FROM '.$table.$where);
                }
            });
        }
    }

    private function scope(int $shop,int $customer,string $eventId): string
    {
        if($shop<1 || $customer<1 || preg_match('/\A[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\z/D',$eventId)!==1) {
            throw new \InvalidArgumentException('Invalid event owner or identifier.');
        }
        return ' WHERE id_shop='.$shop.' AND id_customer='.$customer." AND event_id='".pSQL($eventId)."'";
    }
    private function ownerValues(int $shop,int $customer,string $eventId): string { return $shop.','.$customer.",'".pSQL($eventId)."'"; }
    private function digest(mixed $digest): void
    {
        if(!is_string($digest)||preg_match('/\A[a-f0-9]{64}\z/D',$digest)!==1) { throw new \InvalidArgumentException('Invalid recipient.'); }
    }
    private function assertHeld(string $scope): void
    {
        if(!isset($this->held[$scope])) { throw new \RuntimeException('Event lock required.'); }
    }
    private function read(string $sql): array
    {
        try { $rows=$this->db->executeS($sql,true,false); }
        catch (\Throwable $error) { throw new \RuntimeException('Storage unavailable.'); }
        if(!is_array($rows)) { throw new \RuntimeException('Storage unavailable.'); }return $rows;
    }
    private function write(string $sql): void
    {
        try { $written=$this->db->execute($sql); }
        catch (\Throwable $error) { throw new \RuntimeException('Storage unavailable.'); }
        if(!$written) { throw new \RuntimeException('Storage unavailable.'); }
    }
    private function transaction(callable $operation): void
    {
        $this->write('START TRANSACTION');
        try { $operation();$this->write('COMMIT'); }
        catch(\Throwable $error) {
            try { $this->db->execute('ROLLBACK'); } catch (\Throwable $rollbackError) {}
            throw $error;
        }
    }
}
