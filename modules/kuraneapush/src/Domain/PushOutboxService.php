<?php

declare(strict_types=1);
namespace Kuranea\Push\Domain;

use Kuranea\Push\Infrastructure\DisabledPushDeliveryProvider;
use Kuranea\Push\Infrastructure\SubscriptionCipher;

/** Explicit single-pass delivery. No scheduler, automatic retry or live provider binding. */
final class PushOutboxService
{
    private PushDeliveryProvider $provider;
    public function __construct(private PushOutboxStore $outbox, private PushDeliveryStore $targets,
        private ?SubscriptionCipher $cipher = null, ?PushDeliveryProvider $provider = null)
    {
        $this->provider = $provider ?? new DisabledPushDeliveryProvider();
    }

    public function receive(int $shop, int $customer, string $eventId, DeliveryPayload $payload): array
    {
        return $this->process($shop, $customer, $eventId, $payload);
    }

    public function retry(int $shop, int $customer, string $eventId): array
    {
        return $this->process($shop, $customer, $eventId, null);
    }

    private function process(int $shop, int $customer, string $eventId, ?DeliveryPayload $incoming): array
    {
        if ($shop < 1 || $customer < 1 || preg_match('/\A[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\z/D', $eventId) !== 1) {
            throw new \InvalidArgumentException('Invalid event owner or identifier.');
        }
        $result = ['status'=>'completed','delivered'=>0,'gone'=>0,'retryable_failure'=>0,'skipped'=>0,'interrupted'=>0];
        try { $locked = $this->outbox->acquire($shop, $customer, $eventId); }
        catch (\Throwable $error) { return array_replace($result, ['status'=>'storage_unavailable']); }
        if (!$locked) { return array_replace($result, ['status'=>'busy']); }
        try {
            $receipt = $this->outbox->event($shop, $customer, $eventId);
            if ($receipt !== null && $incoming !== null) {
                if ($receipt['event'] !== $incoming->event || $receipt['locale'] !== $incoming->locale) {
                    throw new \InvalidArgumentException('Event identifier already has a different payload.');
                }
                return array_replace($result, ['status'=>'duplicate']);
            }
            if ($receipt === null && $incoming === null) {
                return array_replace($result, ['status'=>'not_found']);
            }
            $rows = $this->currentTargets($shop, $customer);
            if ($receipt === null) {
                $snapshot = array_map(static fn(array $row): array => [
                    'endpoint_digest'=>$row['endpoint_digest'],
                    'consent_generation'=>ConsentedDeliveryTarget::generation($row),
                ], array_values($rows));
                $this->outbox->create($shop, $customer, $eventId, $incoming, $snapshot);
                $receipt = $this->outbox->event($shop, $customer, $eventId);
                if ($receipt === null) { throw new \RuntimeException('Receipt storage unavailable.'); }
            }
            $payload = new DeliveryPayload($receipt['event'], $receipt['locale']);
            if (!is_array($receipt['recipients']) || count($receipt['recipients']) > PushDeliveryStore::MAX_DELIVERY_TARGETS) {
                throw new \RuntimeException('Recipient storage unavailable.');
            }
            try { $available = $this->provider->available(); }
            catch (\Throwable $error) { $available = false; }
            if (!$available) { return array_replace($result, ['status'=>'provider_unavailable']); }
            if ($this->cipher === null) { return array_replace($result, ['status'=>'storage_unavailable']); }
            foreach ($receipt['recipients'] as $recipient) {
                $digest = $recipient['endpoint_digest'] ?? null;
                if (!is_string($digest) || preg_match('/\A[a-f0-9]{64}\z/D', $digest) !== 1) {
                    throw new \RuntimeException('Recipient storage unavailable.');
                }
                $state = $recipient['outcome'] ?? null;
                if ($state === 'sending') {
                    // A previous process may have transmitted before losing its acknowledgement.
                    // Preserve uncertainty; provider idempotency is needed for safe recovery.
                    $this->outbox->finishAttempt($shop,$customer,$eventId,$digest,(int)$recipient['attempts'],'interrupted');
                    $result['interrupted']++;
                    continue;
                }
                if (!in_array($state, ['pending','retryable_failure'], true)) { continue; }
                // A failed consent preflight has not sent anything and must remain retryable.
                $current = $this->currentTargets($shop,$customer);
                $generation = $recipient['consent_generation'] ?? null;
                $eligible = isset($current[$digest]) && is_string($generation)
                    && hash_equals($generation, ConsentedDeliveryTarget::generation($current[$digest]));
                $attempt = $this->outbox->startAttempt($shop,$customer,$eventId,$digest);
                $outcome = $eligible
                    ? $this->sendTarget($current[$digest],$shop,$customer,$digest,$payload)
                    : 'skipped';
                $this->outbox->finishAttempt($shop,$customer,$eventId,$digest,$attempt,$outcome);
                $result[$outcome]++;
            }
        } catch (\InvalidArgumentException $error) {
            throw $error;
        } catch (\Throwable $error) {
            $result['status'] = 'storage_unavailable';
        } finally {
            try { $this->outbox->release($shop,$customer,$eventId); }
            catch (\Throwable $error) { /* A connection loss releases MySQL advisory locks. */ }
        }
        return $result;
    }

    private function currentTargets(int $shop, int $customer): array
    {
        $rows = $this->targets->deliveryTargetsForOwner($shop,$customer);
        if (count($rows) > PushDeliveryStore::MAX_DELIVERY_TARGETS) {
            throw new \RuntimeException('Recipient storage unavailable.');
        }
        $eligible = [];
        foreach ($rows as $row) {
            if (ConsentedDeliveryTarget::eligible($row,$shop,$customer)) {
                $eligible[$row['endpoint_digest']] = $row;
            }
        }
        return $eligible;
    }

    private function sendTarget(array $row, int $shop, int $customer, string $digest, DeliveryPayload $payload): string
    {
        try { $subscription = $this->cipher->decrypt($row['encrypted_subscription'],$shop,$customer,$digest); }
        catch (\Throwable $error) { return 'skipped'; }
        try { $sent = $this->provider->send($subscription,$payload); }
        catch (\Throwable $error) { return 'retryable_failure'; }
        finally { unset($subscription); }
        if ($sent->status === PushDeliveryResult::GONE) {
            try { $this->targets->removeDeliveryTargetForOwner($shop,$customer,$digest); }
            catch (\Throwable $error) { return 'retryable_failure'; }
            return 'gone';
        }
        return $sent->status === PushDeliveryResult::DELIVERED ? 'delivered' : 'retryable_failure';
    }
}
