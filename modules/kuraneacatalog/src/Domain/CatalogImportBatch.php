<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

use DateTimeImmutable;

/** Immutable bounded batch of canonical provider product URLs. */
final class CatalogImportBatch
{
    public const MAX_ITEMS = 10;

    /** @param list<CatalogImportBatchItem> $items */
    private function __construct(
        public readonly string $id,
        public readonly DateTimeImmutable $createdAt,
        public readonly array $items
    ) {
        if (preg_match('/\A[a-f0-9]{32}\z/', $this->id) !== 1
            || $this->items === []
            || count($this->items) > self::MAX_ITEMS) {
            throw new \InvalidArgumentException('Catalog import batch identity or size is invalid.');
        }

        $itemIds = [];
        $productKeys = [];
        foreach ($this->items as $item) {
            if (!$item instanceof CatalogImportBatchItem
                || isset($itemIds[$item->id])
                || isset($productKeys[$item->productKey])) {
                throw new \InvalidArgumentException('Catalog import batch items must be valid and unique by product.');
            }
            $itemIds[$item->id] = true;
            $productKeys[$item->productKey] = true;
        }
    }

    /** @param list<string> $urls */
    public static function fromUrls(array $urls, ?DateTimeImmutable $createdAt = null): self
    {
        if (!array_is_list($urls) || $urls === [] || count($urls) > self::MAX_ITEMS) {
            throw new \InvalidArgumentException('A catalog import batch must contain between one and ten URLs.');
        }

        $items = [];
        $seenProducts = [];
        foreach ($urls as $url) {
            if (!is_string($url)) {
                throw new \InvalidArgumentException('Catalog import batch URLs must be strings.');
            }
            $item = CatalogImportBatchItem::fromUrl($url);
            if (isset($seenProducts[$item->productKey])) {
                continue;
            }
            $seenProducts[$item->productKey] = true;
            $items[] = $item;
        }

        return new self(bin2hex(random_bytes(16)), $createdAt ?? new DateTimeImmutable('now'), $items);
    }

    /** @param array<string, mixed> $data */
    public static function fromArray(array $data): self
    {
        $allowedKeys = ['id', 'createdAt', 'items'];
        if (array_diff(array_keys($data), $allowedKeys) !== []
            || array_diff($allowedKeys, array_keys($data)) !== []
            || !is_string($data['id'])
            || !is_string($data['createdAt'])
            || !is_array($data['items'])
            || !array_is_list($data['items'])) {
            throw new \UnexpectedValueException('Persisted catalog import batch schema is invalid.');
        }

        try {
            $createdAt = new DateTimeImmutable($data['createdAt']);
        } catch (\Throwable $exception) {
            throw new \UnexpectedValueException('Persisted catalog import batch timestamp is invalid.', 0, $exception);
        }

        $items = [];
        foreach ($data['items'] as $itemData) {
            if (!is_array($itemData)) {
                throw new \UnexpectedValueException('Persisted catalog import batch item is invalid.');
            }
            try {
                $items[] = CatalogImportBatchItem::fromArray($itemData);
            } catch (\Throwable $exception) {
                throw new \UnexpectedValueException('Persisted catalog import batch item is invalid.', 0, $exception);
            }
        }

        return new self($data['id'], $createdAt, $items);
    }

    public function item(string $itemId): CatalogImportBatchItem
    {
        foreach ($this->items as $item) {
            if ($item->id === $itemId) {
                return $item;
            }
        }

        throw new \OutOfBoundsException('Catalog import batch item was not found.');
    }

    /** @return array{queued:int, processing:int, succeeded:int, failed:int} */
    public function counts(): array
    {
        $counts = [
            CatalogImportBatchItem::STATUS_QUEUED => 0,
            CatalogImportBatchItem::STATUS_PROCESSING => 0,
            CatalogImportBatchItem::STATUS_SUCCEEDED => 0,
            CatalogImportBatchItem::STATUS_FAILED => 0,
        ];
        foreach ($this->items as $item) {
            $counts[$item->status]++;
        }

        return $counts;
    }

    public function markProcessing(string $itemId, ?DateTimeImmutable $startedAt = null): self
    {
        return $this->replaceItem($this->item($itemId)->markProcessing($startedAt));
    }

    public function markSucceeded(string $itemId, int $expectedAttempt, NormalizedProductSnapshot $snapshot): self
    {
        return $this->replaceItem($this->item($itemId)->markSucceeded($snapshot, $expectedAttempt));
    }

    public function markFailed(string $itemId, int $expectedAttempt, string $failureCategory): self
    {
        return $this->replaceItem($this->item($itemId)->markFailed($failureCategory, $expectedAttempt));
    }

    public function recoverStaleProcessing(DateTimeImmutable $now): self
    {
        $items = [];
        $changed = false;
        foreach ($this->items as $item) {
            if ($item->status === CatalogImportBatchItem::STATUS_PROCESSING
                && $item->hasExpiredProcessingLease($now)) {
                $items[] = $item->recoverStaleProcessing($now);
                $changed = true;
            } elseif ($item->status === CatalogImportBatchItem::STATUS_QUEUED
                && $item->attempts >= CatalogImportBatchItem::MAX_ATTEMPTS) {
                // Preserve old schema-v1 queued entries that were retryable before the cap existed.
                $items[] = $item->failExhaustedQueuedItem();
                $changed = true;
            } else {
                $items[] = $item;
            }
        }

        return $changed ? new self($this->id, $this->createdAt, $items) : $this;
    }

    public function retryFailedItems(): self
    {
        $items = [];
        $changed = false;
        foreach ($this->items as $item) {
            if ($item->status === CatalogImportBatchItem::STATUS_FAILED
                && $item->attempts < CatalogImportBatchItem::MAX_ATTEMPTS) {
                $items[] = $item->retry();
                $changed = true;
            } else {
                $items[] = $item;
            }
        }

        return $changed ? new self($this->id, $this->createdAt, $items) : $this;
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'createdAt' => $this->createdAt->format(DATE_ATOM),
            'items' => array_map(static fn (CatalogImportBatchItem $item): array => $item->toArray(), $this->items),
        ];
    }

    private function replaceItem(CatalogImportBatchItem $replacement): self
    {
        $items = [];
        $found = false;
        foreach ($this->items as $item) {
            if ($item->id !== $replacement->id) {
                $items[] = $item;
                continue;
            }

            if ($item->productKey !== $replacement->productKey
                || $item->canonicalUrl !== $replacement->canonicalUrl
                || $item->provider !== $replacement->provider
                || $item->sourceProductId !== $replacement->sourceProductId
                || !self::isOneStepTransition($item, $replacement)) {
                throw new \LogicException('Catalog import batch item update must preserve identity and advance one state.');
            }
            $items[] = $replacement;
            $found = true;
        }
        if (!$found) {
            throw new \OutOfBoundsException('Catalog import batch item was not found.');
        }

        return new self($this->id, $this->createdAt, $items);
    }

    private static function isOneStepTransition(CatalogImportBatchItem $before, CatalogImportBatchItem $after): bool
    {
        $expected = match ($before->status) {
            CatalogImportBatchItem::STATUS_QUEUED => [
                CatalogImportBatchItem::STATUS_PROCESSING,
                CatalogImportBatchItem::STATUS_FAILED,
            ],
            CatalogImportBatchItem::STATUS_PROCESSING => [
                CatalogImportBatchItem::STATUS_QUEUED,
                CatalogImportBatchItem::STATUS_SUCCEEDED,
                CatalogImportBatchItem::STATUS_FAILED,
            ],
            CatalogImportBatchItem::STATUS_FAILED => CatalogImportBatchItem::STATUS_QUEUED,
            default => null,
        };
        $allowed = is_array($expected) ? $expected : [$expected];
        if (!in_array($after->status, $allowed, true)) {
            return false;
        }

        return match ($before->status) {
            CatalogImportBatchItem::STATUS_QUEUED => $after->status === CatalogImportBatchItem::STATUS_PROCESSING
                ? $after->attempts === $before->attempts + 1
                : ($after->attempts === $before->attempts
                    && $before->attempts >= CatalogImportBatchItem::MAX_ATTEMPTS
                    && $after->failureCategory === CatalogImportBatchItem::FAILURE_PROCESSING_FAILED),
            CatalogImportBatchItem::STATUS_PROCESSING,
            CatalogImportBatchItem::STATUS_FAILED => $after->attempts === $before->attempts,
            default => false,
        };
    }
}
