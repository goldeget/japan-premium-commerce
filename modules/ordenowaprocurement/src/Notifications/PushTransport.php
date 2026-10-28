<?php
declare(strict_types=1);
namespace Ordenowa\Procurement\Notifications;

use Kuranea\Push\Domain\DeliveryPayload;

final class PushTransport implements Transport
{
    private readonly \Closure $factory;
    private readonly \Closure $enabled;

    public function __construct(private readonly NativeRecipientResolver $recipients, ?callable $factory = null, ?callable $enabled = null)
    {
        $this->factory = $factory === null ? static fn(int $shop): object => \Kuranea\Push\Infrastructure\LivePushFactory::outbox($shop) : \Closure::fromCallable($factory);
        $this->enabled = $enabled === null ? static fn(int $shop, string $event): bool => (string) \Configuration::get('ORDENOWA_PUSH_EVENT_' . strtoupper($event), null, null, $shop) === '1' : \Closure::fromCallable($enabled);
    }

    public function send(array $event): DeliveryResult
    {
        $recipient = $this->recipients->resolve($event);
        if ($recipient === null) {
            return new DeliveryResult('skipped', 'recipient_ineligible');
        }
        $category = str_starts_with($event['event'], 'points.') ? 'points' : 'procurement';
        $shop = (int) $event['id_shop'];
        $customer = (int) $event['id_customer'];
        if (!(($this->enabled)($shop, $category))) {
            return new DeliveryResult('skipped', 'push_event_disabled');
        }
        $outbox = ($this->factory)($shop);
        $eventId = 'procurement:' . $event['event_key'];
        // Retry the immutable existing receipt before constructing a payload from today's locale.
        $result = $outbox->retry($shop, $customer, $eventId);
        if (($result['status'] ?? '') === 'not_found') {
            $result = $outbox->receive($shop, $customer, $eventId, new DeliveryPayload($category, $recipient['locale']));
            if (($result['status'] ?? '') === 'duplicate') {
                $result = $outbox->retry($shop, $customer, $eventId);
            }
        }
        if (($result['interrupted'] ?? 0) > 0 || ($result['status'] ?? '') === 'storage_unavailable') {
            return new DeliveryResult('uncertain', 'push_delivery_uncertain');
        }
        if (($result['status'] ?? '') !== 'completed' || ($result['retryable_failure'] ?? 0) > 0) {
            return new DeliveryResult('retry', 'push_delivery_unavailable');
        }
        return new DeliveryResult('sent');
    }
}
