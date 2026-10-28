<?php

declare(strict_types=1);
require_once __DIR__ . '/../../modules/kuraneacatalog/autoload.php';
require_once __DIR__ . '/../../modules/ordenowaprocurement/autoload.php';

use Kuranea\Catalog\Infrastructure\Persistence\CatalogDatabaseRowMapper;
use Kuranea\Catalog\Domain\ProductReviewQueueEntry;
use Kuranea\Catalog\Domain\ProductImageRightsEvidence;
use Kuranea\Catalog\Parsing\AmazonJapanHtmlParser;
use Ordenowa\Procurement\Catalog\ReviewedProductEvidence;
use Ordenowa\Procurement\Infrastructure\Database;

function evidenceSame(mixed $expected, mixed $actual): void {
    if ($expected !== $actual) throw new RuntimeException('Evidence differs: ' . var_export($actual, true));
}
$native = new class {
    public array $rows = [];
    public bool $installed = true;
    public function escape(string $s, bool $unused = true): string { return addslashes($s); }
    public function executeS(string $sql, bool $array = true, bool $cache = true): array {
        if ($cache) throw new RuntimeException('Evidence read must not use cached results.');
        if (str_contains($sql, 'information_schema')) return $this->installed ? [['present' => 1]] : [];
        if (!str_contains($sql, 'id_shop = 3') || !str_contains($sql, 'native_product_id = 17')) throw new RuntimeException('Missing native product/shop isolation.');
        return $this->rows;
    }
};
$adapter = new ReviewedProductEvidence(new Database($native, 'ps_'), 'ps_');
evidenceSame(false, $adapter->forProduct(3, 17)['reviewed']);
$snapshot = (new AmazonJapanHtmlParser())->parse(file_get_contents(__DIR__ . '/fixtures/amazon-jp-review-single-option.synthetic.html'), 'https://www.amazon.co.jp/dp/B0KURANEA1');
$entry = new ProductReviewQueueEntry($snapshot->deduplicationKey, 'pending', $snapshot, new DateTimeImmutable());
$rights = ProductImageRightsEvidence::record('licensed', 'offline license reference', 'employee:2', new DateTimeImmutable('2026-10-29T00:00:00Z'), [42]);
$entry = $entry->approve(17, 'employee:2', new DateTimeImmutable('2026-10-29T00:00:00Z'), $rights);
$row = CatalogDatabaseRowMapper::review($entry);
$native->rows = [['status' => $row['status'], 'native_product_id' => 17, 'content_hash' => $row['content_hash'], 'payload_sha256' => $row['hash'], 'payload' => $row['payload']]];
$approved = $adapter->forProduct(3, 17);
evidenceSame(true, $approved['reviewed']);
evidenceSame($snapshot->sourceUrl, $approved['source_url']);
evidenceSame([42], $approved['approved_image_ids']);
evidenceSame((string) $snapshot->priceJpy, $approved['reference_price']);
evidenceSame($snapshot->categories, $approved['source_categories']);
$native->rows[0]['payload_sha256'] = str_repeat('0', 64);
try { $adapter->forProduct(3, 17); throw new LogicException('Corrupt evidence accepted.'); } catch (UnexpectedValueException) {}
$native->rows = [['status' => $row['status'], 'native_product_id' => 17, 'content_hash' => $row['content_hash'], 'payload_sha256' => $row['hash'], 'payload' => $row['payload']]];
$badPayload = json_decode($row['payload'], true, 64, JSON_THROW_ON_ERROR);
$badPayload['nativeProductId'] = 18;
$native->rows[0]['payload'] = json_encode($badPayload, JSON_THROW_ON_ERROR);
$native->rows[0]['payload_sha256'] = hash('sha256', $native->rows[0]['payload']);
try { $adapter->forProduct(3, 17); throw new LogicException('Mismatched native product accepted.'); } catch (UnexpectedValueException) {}
$pending = new ProductReviewQueueEntry($snapshot->deduplicationKey, 'pending', $snapshot, new DateTimeImmutable());
$pending = $pending->linkDraft(17);
$pendingRow = CatalogDatabaseRowMapper::review($pending);
$native->rows = [['status' => 'pending', 'native_product_id' => null, 'content_hash' => $pendingRow['content_hash'], 'payload_sha256' => $pendingRow['hash'], 'payload' => $pendingRow['payload']]];
evidenceSame(false, $adapter->forProduct(3, 17)['reviewed']);
$syntheticRights = ProductImageRightsEvidence::fromArray(array_replace($rights->toArray(), ['basis' => 'synthetic_ci_fixture']));
$syntheticEntry = (new ProductReviewQueueEntry($snapshot->deduplicationKey, 'pending', $snapshot, new DateTimeImmutable()))->approve(17, 'employee:2', new DateTimeImmutable('2026-10-29T00:00:00Z'), $syntheticRights);
$syntheticRow = CatalogDatabaseRowMapper::review($syntheticEntry);
$native->rows = [['status' => 'approved', 'native_product_id' => 17, 'content_hash' => $syntheticRow['content_hash'], 'payload_sha256' => $syntheticRow['hash'], 'payload' => $syntheticRow['payload']]];
evidenceSame([], $adapter->forProduct(3, 17)['approved_image_ids']);
$native->rows[] = $native->rows[0];
try { $adapter->forProduct(3, 17); throw new LogicException('Ambiguous native review links accepted.'); } catch (UnexpectedValueException) {}
$native->installed = false;
evidenceSame(false, $adapter->forProduct(3, 17)['reviewed']);
echo "PASS: approved catalog evidence scopes product/shop, verifies payload, and exposes licensed local image IDs only\n";
