<?php

declare(strict_types=1);

namespace Kuranea\Push\Infrastructure;

use Kuranea\Push\Domain\DeliveryPayload;
use Kuranea\Push\Domain\PushOutboxService;

/** Records a generic owner-scoped receipt for a public staff reply. */
final class SupportMessagePushProducer
{
    public function __construct(private ?PushOutboxService $service = null)
    {
    }

    /** @return array<string, int|string> */
    public function record(mixed $event): array
    {
        try {
            if (!($event instanceof \CustomerMessage) || (int) $event->id < 1) {
                return ['status' => 'ignored'];
            }

            // The hook payload is only an identity hint. Re-read the persisted row before using it.
            $message = new \CustomerMessage((int) $event->id);
            if (!\Validate::isLoadedObject($message)
                || (int) $message->id !== (int) $event->id
                || (int) $message->id_employee < 1
                || (bool) $message->private
                || (int) $message->id_customer_thread < 1) {
                return ['status' => 'ignored'];
            }

            $thread = new \CustomerThread((int) $message->id_customer_thread);
            if (!\Validate::isLoadedObject($thread)
                || (int) $thread->id !== (int) $message->id_customer_thread
                || (int) $thread->id_customer < 1
                || (int) $thread->id_shop < 1
                || (int) $thread->id_lang < 1
                || (int) $thread->id_order < 0) {
                return ['status' => 'ignored'];
            }

            // An order-linked thread must still identify the same customer and shop as its order.
            if ((int) $thread->id_order > 0) {
                $order = new \Order((int) $thread->id_order);
                if (!\Validate::isLoadedObject($order)
                    || (int) $order->id !== (int) $thread->id_order
                    || (int) $order->id_customer !== (int) $thread->id_customer
                    || (int) $order->id_shop !== (int) $thread->id_shop) {
                    return ['status' => 'ignored'];
                }
            }

            $customer = new \Customer((int) $thread->id_customer);
            $shopId = (int) $thread->id_shop;
            if (!\Validate::isLoadedObject($customer)
                || (int) $customer->id !== (int) $thread->id_customer
                || (bool) $customer->is_guest
                || !(bool) $customer->active
                || (string) \Configuration::get('ORDENOWA_PUSH_EVENT_SUPPORT', null, null, $shopId) !== '1') {
                return ['status' => 'ignored'];
            }

            $locale = (string) \Language::getIsoById((int) $thread->id_lang);
            $locale = in_array($locale, PushSettings::LOCALES, true) ? $locale : 'ja';
            // Only the event enum and locale enter the outbox; message text and attachment stay private.
            $service = $this->service ?? new PushOutboxService(
                new PushOutboxRepository(),
                new SubscriptionRepository()
            );

            return $service->receive(
                $shopId,
                (int) $customer->id,
                'support-message:' . (int) $message->id,
                new DeliveryPayload('support', $locale)
            );
        } catch (\Throwable) {
            // Optional receipt recording must never break native support messaging or expose its contents.
            return ['status' => 'storage_unavailable'];
        }
    }
}
