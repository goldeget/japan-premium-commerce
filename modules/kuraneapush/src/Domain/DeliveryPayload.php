<?php

declare(strict_types=1);
namespace Kuranea\Push\Domain;

/** Wire contract consumed by the service worker; copy and destinations stay in the worker. */
final class DeliveryPayload
{
    public readonly string $event;
    public readonly string $locale;

    public function __construct(string $event, string $locale)
    {
        if (!in_array($event, ['order', 'delivery', 'support'], true)
            || !in_array($locale, ['ja', 'en', 'ko'], true)) {
            throw new \InvalidArgumentException('Invalid delivery payload.');
        }
        $this->event = $event;
        $this->locale = $locale;
    }

    public function toJson(): string
    {
        return json_encode(['event' => $this->event, 'locale' => $this->locale], JSON_THROW_ON_ERROR);
    }
}
