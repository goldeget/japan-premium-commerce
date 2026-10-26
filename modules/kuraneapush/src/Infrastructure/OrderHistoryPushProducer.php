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
            $shop = (int)$order->id_shop;
            $customer = new \Customer((int)$order->id_customer);
            if (!\Validate::isLoadedObject($customer) || (int)$customer->id !== (int)$order->id_customer
                || (bool)$customer->is_guest || !(bool)$customer->active
                || (string)\Configuration::get('ORDENOWA_PUSH_EVENT_ORDER', null, null, $shop) !== '1') {
                return ['status'=>'ignored'];
            }
            $locale = (string)\Language::getIsoById((int)$order->id_lang);
            $locale = in_array($locale, PushSettings::LOCALES, true) ? $locale : 'ja';
            // Receipt creation needs no storage secret. No provider is bound in the native hook.
            $service = $this->service ?? new PushOutboxService(new PushOutboxRepository(), new SubscriptionRepository());
            return $service->receive($shop, (int)$customer->id, 'order-history:' . (int)$history->id,
                new DeliveryPayload('order', $locale));
        } catch (\Throwable $error) {
            // Optional notification recording must not break native order processing or leak its data.
            return ['status'=>'storage_unavailable'];
        }
    }
}
