<?php

declare(strict_types=1);
namespace Kuranea\Push\Infrastructure;

use Kuranea\Push\Domain\DeliveryPayload;
use Kuranea\Push\Domain\PushOutboxService;

/** Receives persisted native history events; the default outbox records without a live sender. */
final class OrderHistoryPushProducer
{
    public function __construct(private ?PushOutboxService $service = null) {}

    public function record(mixed $event): array
    {
        return $this->recordEvent($event, 'order');
    }

    public function recordDelivery(mixed $event): array
    {
        return $this->recordEvent($event, 'delivery');
    }

    private function recordEvent(mixed $event, string $type): array
    {
        try {
            if (!($event instanceof \OrderHistory) || (int)$event->id < 1) {
                return ['status'=>'ignored'];
            }
            // Derive identity from stored models, never mutable hook owner fields or admin context.
            $history = new \OrderHistory((int)$event->id);
            if (!\Validate::isLoadedObject($history) || (int)$history->id !== (int)$event->id
                || (int)$history->id_order < 1 || (int)$history->id_order_state < 1) {
                return ['status'=>'ignored'];
            }
            $order = new \Order((int)$history->id_order);
            if (!\Validate::isLoadedObject($order) || (int)$order->id !== (int)$history->id_order
                || (int)$order->current_state !== (int)$history->id_order_state
                || (int)$order->id_shop < 1 || (int)$order->id_customer < 1) {
                return ['status'=>'ignored'];
            }
            if ($type === 'delivery') {
                $state = new \OrderState((int)$history->id_order_state);
                if (!\Validate::isLoadedObject($state) || (int)$state->id !== (int)$history->id_order_state
                    || !(bool)$state->shipped) {
                    return ['status'=>'ignored'];
                }
            }
            $shop = (int)$order->id_shop;
            $setting = $type === 'delivery' ? 'ORDENOWA_PUSH_EVENT_DELIVERY' : 'ORDENOWA_PUSH_EVENT_ORDER';
            $customer = new \Customer((int)$order->id_customer);
            if (!\Validate::isLoadedObject($customer) || (int)$customer->id !== (int)$order->id_customer
                || (bool)$customer->is_guest || !(bool)$customer->active
                || (string)\Configuration::get($setting, null, null, $shop) !== '1') {
                return ['status'=>'ignored'];
            }
            $locale = (string)\Language::getIsoById((int)$order->id_lang);
            $locale = in_array($locale, PushSettings::LOCALES, true) ? $locale : 'ja';
            // Receipt creation needs no storage secret. No provider is bound in the native hook.
            $service = $this->service ?? new PushOutboxService(new PushOutboxRepository(), new SubscriptionRepository());
            $eventPrefix = $type === 'delivery' ? 'delivery-history:' : 'order-history:';
            return $service->receive($shop, (int)$customer->id, $eventPrefix . (int)$history->id,
                new DeliveryPayload($type, $locale));
        } catch (\Throwable $error) {
            // Optional notification recording must not break native order processing or leak its data.
            return ['status'=>'storage_unavailable'];
        }
    }
}
