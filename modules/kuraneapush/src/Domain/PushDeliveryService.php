<?php

declare(strict_types=1);
namespace Kuranea\Push\Domain;

use Kuranea\Push\Infrastructure\SubscriptionCipher;
use Kuranea\Push\Infrastructure\DisabledPushDeliveryProvider;

final class PushDeliveryService
{
    private PushDeliveryProvider $provider;

    public function __construct(private PushDeliveryStore $store, private SubscriptionCipher $cipher,
        ?PushDeliveryProvider $provider = null)
    {
        $this->provider = $provider ?? new DisabledPushDeliveryProvider();
    }

    public function deliverToOwner(int $shop, int $customer, DeliveryPayload $payload): PushDeliverySummary
    {
        if ($shop < 1 || $customer < 1) {
            throw new \InvalidArgumentException('Invalid delivery owner.');
        }
        try {
            if (!$this->provider->available()) {
                return new PushDeliverySummary('provider_unavailable');
            }
        } catch (\Throwable $error) {
            return new PushDeliverySummary('provider_unavailable');
        }

        try {
            $rows = $this->store->deliveryTargetsForOwner($shop, $customer);
            if (count($rows) > PushDeliveryStore::MAX_DELIVERY_TARGETS) {
                return new PushDeliverySummary('storage_unavailable');
            }
        } catch (\Throwable $error) {
            return new PushDeliverySummary('storage_unavailable');
        }

        $delivered = 0;
        $permanentlyGone = 0;
        $retryableFailure = 0;
        $ineligible = 0;
        foreach ($rows as $row) {
            if (!ConsentedDeliveryTarget::eligible($row, $shop, $customer)) {
                $ineligible++;
                continue;
            }
            try {
                $subscription = $this->cipher->decrypt($row['encrypted_subscription'], $shop, $customer, $row['endpoint_digest']);
            } catch (\Throwable $error) {
                $ineligible++;
                continue;
            }

            try {
                $result = $this->provider->send($subscription, $payload);
            } catch (\Throwable $error) {
                $retryableFailure++;
                continue;
            } finally {
                unset($subscription);
            }
            if (!($result instanceof PushDeliveryResult)) {
                $retryableFailure++;
                continue;
            }
            if ($result->status === PushDeliveryResult::DELIVERED) {
                $delivered++;
                continue;
            }
            if ($result->status === PushDeliveryResult::GONE) {
                try {
                    $this->store->removeDeliveryTargetForOwner($shop, $customer, $row['endpoint_digest']);
                    $permanentlyGone++;
                } catch (\Throwable $error) {
                    $retryableFailure++;
                }
                continue;
            }
            $retryableFailure++;
        }

        return new PushDeliverySummary('completed', $delivered, $permanentlyGone, $retryableFailure, $ineligible);
    }

}
