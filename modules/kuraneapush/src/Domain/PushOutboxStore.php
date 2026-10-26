<?php

declare(strict_types=1);
namespace Kuranea\Push\Domain;

/** All operations require the exact trusted owner/event scope and an acquired event lock. */
interface PushOutboxStore
{
    public function acquire(int $shop, int $customer, string $eventId): bool;
    public function release(int $shop, int $customer, string $eventId): void;
    /** Returns event/locale and bounded recipient digest/outcome/attempts records, never endpoint secrets. */
    public function event(int $shop, int $customer, string $eventId): ?array;
    /** Atomically creates receipt and digest/consent_generation snapshot. Never upserts. */
    public function create(int $shop, int $customer, string $eventId, DeliveryPayload $payload, array $recipients): void;
    /** Durably records sending before outbound I/O; returns this recipient's attempt number. */
    public function startAttempt(int $shop, int $customer, string $eventId, string $digest): int;
    /** Atomically saves recipient outcome and completion of its attempt record. */
    public function finishAttempt(int $shop, int $customer, string $eventId, string $digest, int $attempt, string $outcome): void;
}
