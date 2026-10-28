<?php

declare(strict_types=1);
namespace Ordenowa\Procurement\Catalog;

use Kuranea\Catalog\Domain\ProductReviewQueueEntry;
use Kuranea\Catalog\Fetching\ProductUrlPolicy;
use Ordenowa\Procurement\Infrastructure\Database;

/** Read-only bridge from the reviewed source revision to a hidden native product. */
final class ReviewedProductEvidence
{
    private string $prefix;

    public function __construct(private Database $database, ?string $nativePrefix = null)
    {
        $nativePrefix ??= defined('_DB_PREFIX_') ? (string) constant('_DB_PREFIX_') : '';
        if (!preg_match('/\A[A-Za-z0-9_]*\z/D', $nativePrefix)) throw new \InvalidArgumentException('Invalid native catalog prefix.');
        $this->prefix = $nativePrefix;
    }

    /** No source image is downloaded or promoted to public usage by this adapter. */
    public function forProduct(int $shopId, int $productId): array
    {
        if ($shopId < 1 || $productId < 1) throw new \InvalidArgumentException('Invalid catalog product context.');
        $empty = ['reviewed' => false, 'source_url' => '', 'approved_image_ids' => [], 'source_categories' => [], 'reviewed_category_ids' => [], 'reference_price' => '', 'currency' => ''];
        $table = $this->prefix . 'kuraneacatalog_review';
        if ($this->database->one('SELECT 1 AS present FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ' . $this->database->quote($table) . ' LIMIT 1') === null) return $empty;
        $rows = $this->database->all('SELECT status, native_product_id, content_hash, payload_sha256, payload FROM `' . $table . '` WHERE id_shop = ' . $shopId
            . ' AND (native_product_id = ' . $productId . ' OR linked_product_id = ' . $productId . ') LIMIT 2');
        if ($rows === []) return $empty;
        if (count($rows) !== 1) throw new \UnexpectedValueException('Catalog product has ambiguous review evidence.');
        $row = $rows[0];
        if (!is_string($row['payload'] ?? null) || !is_string($row['payload_sha256'] ?? null)
            || !hash_equals($row['payload_sha256'], hash('sha256', $row['payload']))) throw new \UnexpectedValueException('Catalog review evidence is corrupt.');
        $autoload = dirname(__DIR__, 3) . '/kuraneacatalog/autoload.php';
        if (!class_exists(ProductReviewQueueEntry::class) && is_file($autoload)) require_once $autoload;
        if (!class_exists(ProductReviewQueueEntry::class)) throw new \UnexpectedValueException('Catalog review evidence cannot be verified.');
        try {
            $entry = ProductReviewQueueEntry::fromArray(json_decode($row['payload'], true, 64, JSON_THROW_ON_ERROR));
            if (($row['status'] ?? null) !== $entry->status || ($row['content_hash'] ?? null) !== $entry->snapshot->contentHash) throw new \UnexpectedValueException();
            if ($entry->status !== ProductReviewQueueEntry::STATUS_APPROVED) return $empty;
            if ($entry->nativeProductId !== $productId || (int) ($row['native_product_id'] ?? 0) !== $productId) throw new \UnexpectedValueException();
            $target = ProductUrlPolicy::canonicalize($entry->snapshot->sourceUrl);
            if ($target['provider'] !== $entry->snapshot->source || $entry->snapshot->currency !== 'JPY' || $entry->snapshot->priceJpy < 1) throw new \UnexpectedValueException();
            $identity = $entry->snapshot->source === 'rakuten_ichiba'
                ? str_replace('/', ':', substr($target['identity'], strlen('rakuten_ichiba:')))
                : substr($target['identity'], strlen('amazon_jp:'));
            if ($identity !== $entry->snapshot->sourceProductId) throw new \UnexpectedValueException();
        } catch (\Throwable $error) {
            throw new \UnexpectedValueException('Catalog review evidence does not match the native product.', 0, $error);
        }
        $rights = $entry->imageRightsEvidence;
        return ['reviewed' => true, 'source_url' => $target['url'],
            'approved_image_ids' => $rights !== null && $rights->isUsageRightsClaim() ? $rights->imageIds : [],
            'source_categories' => $entry->snapshot->categories,
            'reviewed_category_ids' => $entry->importReviewEvidence?->categoryIds ?? [],
            'reference_price' => (string) $entry->snapshot->priceJpy, 'currency' => 'JPY'];
    }
}
