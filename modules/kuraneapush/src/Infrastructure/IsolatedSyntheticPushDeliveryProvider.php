<?php

declare(strict_types=1);
namespace Kuranea\Push\Infrastructure;

use Kuranea\Push\Domain\DeliveryPayload;
use Kuranea\Push\Domain\PushDeliveryProvider;
use Kuranea\Push\Domain\PushDeliveryResult;
use Kuranea\Push\Domain\Readiness;
use Kuranea\Push\Domain\SubscriptionValidator;

final class IsolatedSyntheticPushDeliveryProvider implements PushDeliveryProvider
{
    private array $outcomes;

    public function __construct(array $outcomes = [])
    {
        if (!Readiness::isolated()) {
            throw new \RuntimeException('Synthetic push delivery is restricted to isolated CI.');
        }
        foreach ($outcomes as $endpointHash => $status) {
            if (!is_string($endpointHash) || preg_match('/\A[a-f0-9]{64}\z/D', $endpointHash) !== 1
                || !in_array($status, [PushDeliveryResult::DELIVERED, PushDeliveryResult::GONE, PushDeliveryResult::RETRYABLE_FAILURE], true)) {
                throw new \InvalidArgumentException('Invalid synthetic delivery scenario.');
            }
        }
        $this->outcomes = $outcomes;
    }

    public function available(): bool
    {
        return Readiness::isolated();
    }

    public function send(array $subscription, DeliveryPayload $payload): PushDeliveryResult
    {
        if (!$this->available()) {
            throw new \RuntimeException('Synthetic push delivery is restricted to isolated CI.');
        }
        $subscription = SubscriptionValidator::validate($subscription);
        // Exercise the same wire serializer a real transport must consume.
        $payload->toJson();
        $key = hash('sha256', $subscription['endpoint']);
        return new PushDeliveryResult($this->outcomes[$key] ?? PushDeliveryResult::DELIVERED);
    }
}
