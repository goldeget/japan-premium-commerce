<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Infrastructure\Persistence;

use Kuranea\Catalog\Domain\ProductReviewQueueEntry;

final class CatalogDatabaseRowMapper
{
    /** @return array<string, mixed> */
    public static function review(ProductReviewQueueEntry $entry): array
    {
        $payload = CatalogDatabaseSql::encode($entry->toArray());
        $decision = $entry->approvedAt ?? $entry->rejectedAt;

        return [
            'key' => $entry->idempotencyKey,
            'source_identity_hash' => hash('sha256', $entry->snapshot->source . "\0" . $entry->snapshot->sourceProductId),
            'provider' => strtolower(substr($entry->snapshot->source, 0, 32)),
            'status' => $entry->status,
            'content_hash' => $entry->snapshot->contentHash,
            'queued_at' => CatalogDatabaseSql::timestamp($entry->queuedAt),
            'decision_at' => $decision === null ? null : CatalogDatabaseSql::timestamp($decision),
            'native_product_id' => $entry->nativeProductId,
            'linked_product_id' => $entry->linkedProductId,
            'hash' => hash('sha256', $payload),
            'payload' => $payload,
        ];
    }
}
