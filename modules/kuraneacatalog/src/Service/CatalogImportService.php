<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Service;

use DateTimeImmutable;
use DateTimeZone;
use Kuranea\Catalog\Domain\CatalogImportBatch;
use Kuranea\Catalog\Domain\CatalogImportBatchItem;
use Kuranea\Catalog\Domain\CatalogImportBatchRepositoryInterface;
use Kuranea\Catalog\Domain\CatalogParseException;
use Kuranea\Catalog\Domain\ProductReviewQueueRepositoryInterface;
use Kuranea\Catalog\Fetching\FetchException;
use Kuranea\Catalog\Fetching\ProductPageFetcherInterface;
use Kuranea\Catalog\Parsing\AmazonJapanHtmlParser;
use Kuranea\Catalog\Parsing\RakutenHtmlParser;
use Throwable;

/** Processes at most one bounded public product URL per administrator request. */
final class CatalogImportService
{
    public function __construct(
        private readonly CatalogImportBatchRepositoryInterface $batches,
        private readonly ProductReviewQueueRepositoryInterface $reviews,
        private readonly ProductPageFetcherInterface $fetcher
    ) {
    }

    /** @param list<string> $urls */
    public function createBatch(array $urls, ?DateTimeImmutable $createdAt = null): CatalogImportBatch
    {
        return $this->batches->create($urls, $createdAt);
    }

    public function findBatch(string $batchId): ?CatalogImportBatch
    {
        if (preg_match('/\A[a-f0-9]{32}\z/', $batchId) !== 1) {
            return null;
        }

        return $this->batches->find($batchId);
    }

    /** Fetch and parse one queued URL, recording only fixed safe outcomes. */
    public function processNext(string $batchId): CatalogImportBatch
    {
        $batch = $this->findBatch($batchId);
        if ($batch === null) {
            throw new \InvalidArgumentException('Catalog import batch was not found.');
        }

        // A worker may have stopped after claiming an item. Recover only leases
        // that have actually expired before choosing the next queued item.
        $batch = $this->batches->recoverStaleProcessing($batchId);

        $item = null;
        foreach ($batch->items as $candidate) {
            if ($candidate->status === CatalogImportBatchItem::STATUS_QUEUED) {
                $item = $candidate;
                break;
            }
        }
        if ($item === null) {
            return $batch;
        }

        $claimedBatch = $this->batches->markProcessing($batchId, $item->id);
        $claimedItem = $claimedBatch->item($item->id);
        $expectedAttempt = $claimedItem->attempts;
        try {
            $fetched = $this->fetcher->fetch($item->canonicalUrl);
            $parser = match ($item->provider) {
                'amazon_jp' => new AmazonJapanHtmlParser(),
                'rakuten_ichiba' => new RakutenHtmlParser(),
                default => throw new \LogicException('Unsupported product provider.'),
            };
            try {
                // Use the persisted claim time, not response completion time,
                // to order source observations across concurrent batches. A
                // slower old request must not overwrite a later started fetch.
                $snapshot = $parser->parse(
                    $fetched->body,
                    $fetched->canonicalUrl,
                    $claimedItem->processingStartedAt ?? $fetched->fetchedAt
                );
            } catch (CatalogParseException $exception) {
                $category = $this->isAccessChallenge($fetched->body)
                    ? CatalogImportBatchItem::FAILURE_ACCESS_BLOCKED
                    : (str_contains($exception->getMessage(), '지원하지 않는 원본 통화')
                        ? CatalogImportBatchItem::FAILURE_UNSUPPORTED_CURRENCY
                        : CatalogImportBatchItem::FAILURE_PARSE_FAILED);
                return $this->failClaimedAttempt($batchId, $item->id, $expectedAttempt, $category);
            }

            if ($snapshot->source !== $item->provider
                || $snapshot->sourceProductId !== $item->sourceProductId
                || $snapshot->deduplicationKey !== $item->productKey) {
                return $this->failClaimedAttempt(
                    $batchId,
                    $item->id,
                    $expectedAttempt,
                    CatalogImportBatchItem::FAILURE_SOURCE_UNAVAILABLE
                );
            }

            return $this->batches->completeWithReviewSnapshot(
                $batchId,
                $item->id,
                $expectedAttempt,
                $snapshot,
                fn () => $this->reviews->enqueue($snapshot, new DateTimeImmutable('now', new DateTimeZone('UTC')))
            );
        } catch (FetchException $exception) {
            $category = match ($exception->failureCategory) {
                FetchException::FAILURE_ACCESS_BLOCKED => CatalogImportBatchItem::FAILURE_ACCESS_BLOCKED,
                FetchException::FAILURE_SOURCE_UNAVAILABLE => CatalogImportBatchItem::FAILURE_SOURCE_UNAVAILABLE,
                default => CatalogImportBatchItem::FAILURE_FETCH_FAILED,
            };
            return $this->failClaimedAttempt($batchId, $item->id, $expectedAttempt, $category);
        } catch (Throwable) {
            return $this->failClaimedAttempt(
                $batchId,
                $item->id,
                $expectedAttempt,
                CatalogImportBatchItem::FAILURE_PROCESSING_FAILED
            );
        }
    }

    private function failClaimedAttempt(
        string $batchId,
        string $itemId,
        int $expectedAttempt,
        string $failureCategory
    ): CatalogImportBatch {
        try {
            return $this->batches->markFailed($batchId, $itemId, $expectedAttempt, $failureCategory);
        } catch (\LogicException $exception) {
            $current = $this->findBatch($batchId);
            if ($current !== null) {
                try {
                    $item = $current->item($itemId);
                    if ($item->attempts !== $expectedAttempt || $item->status !== CatalogImportBatchItem::STATUS_PROCESSING) {
                        return $current;
                    }
                } catch (\OutOfBoundsException) {
                    return $current;
                }
            }

            throw $exception;
        }
    }

    public function retryFailedItems(string $batchId): CatalogImportBatch
    {
        $batch = $this->findBatch($batchId);
        if ($batch === null) {
            throw new \InvalidArgumentException('Catalog import batch was not found.');
        }

        return $this->batches->retryFailedItems($batchId);
    }

    private function isAccessChallenge(string $html): bool
    {
        return preg_match(
            '~(?:validateCaptcha|captchaContainer|captcha\.amazon\.com|robot\s+check|画像認証|アクセスを確認してください|不正なアクセスを検知)~iu',
            $html
        ) === 1;
    }
}
