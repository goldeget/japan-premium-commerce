<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

use Kuranea\Catalog\Fetching\FetchException;
use Kuranea\Catalog\Fetching\ProductUrlPolicy;

/** One bounded marketplace URL and its safe, one-step processing state. */
final class CatalogImportBatchItem
{
    public const STATUS_QUEUED = 'queued';
    public const STATUS_PROCESSING = 'processing';
    public const STATUS_SUCCEEDED = 'succeeded';
    public const STATUS_FAILED = 'failed';

    public const MAX_ATTEMPTS = 3;
    public const PROCESSING_LEASE_SECONDS = 300;

    public const FAILURE_FETCH_FAILED = 'fetch_failed';
    public const FAILURE_PARSE_FAILED = 'parse_failed';
    public const FAILURE_UNSUPPORTED_CURRENCY = 'unsupported_currency';
    public const FAILURE_SOURCE_UNAVAILABLE = 'source_unavailable';
    public const FAILURE_ACCESS_BLOCKED = 'access_blocked';
    public const FAILURE_DUPLICATE_PRODUCT = 'duplicate_product';
    public const FAILURE_PROCESSING_FAILED = 'processing_failed';

    /** @var array<string, string> */
    private const FAILURE_MESSAGES = [
        self::FAILURE_FETCH_FAILED => '상품 페이지를 가져오지 못했습니다.',
        self::FAILURE_PARSE_FAILED => '상품 정보를 읽지 못했습니다.',
        self::FAILURE_UNSUPPORTED_CURRENCY => '지원하지 않는 통화의 상품입니다.',
        self::FAILURE_SOURCE_UNAVAILABLE => '상품 페이지를 확인할 수 없습니다.',
        self::FAILURE_ACCESS_BLOCKED => '판매처에서 상품 정보 접근을 제한했습니다.',
        self::FAILURE_DUPLICATE_PRODUCT => '중복 상품으로 확인되었습니다.',
        self::FAILURE_PROCESSING_FAILED => '상품 처리 중 오류가 발생했습니다.',
    ];

    private function __construct(
        public readonly string $id,
        public readonly string $provider,
        public readonly string $sourceProductId,
        public readonly string $productKey,
        public readonly string $canonicalUrl,
        public readonly string $status,
        public readonly int $attempts,
        public readonly ?string $failureCategory,
        public readonly ?NormalizedProductSnapshot $snapshot,
        public readonly ?\DateTimeImmutable $processingStartedAt = null
    ) {
        if (!in_array($this->provider, ['amazon_jp', 'rakuten_ichiba'], true)
            || trim($this->sourceProductId) === ''
            || $this->productKey !== $this->provider . ':' . $this->sourceProductId
            || $this->id !== hash('sha256', $this->productKey)
            || $this->attempts < 0) {
            throw new \InvalidArgumentException('Catalog import item identity is invalid.');
        }

        $canonical = self::canonicalProviderUrl($this->canonicalUrl);
        if ($canonical['provider'] !== $this->provider
            || $canonical['productId'] !== $this->sourceProductId
            || $canonical['productKey'] !== $this->productKey
            || $canonical['url'] !== $this->canonicalUrl) {
            throw new \InvalidArgumentException('Catalog import item URL must already be canonical and query-free.');
        }

        if (!in_array($this->status, [
            self::STATUS_QUEUED,
            self::STATUS_PROCESSING,
            self::STATUS_SUCCEEDED,
            self::STATUS_FAILED,
        ], true)) {
            throw new \InvalidArgumentException('Catalog import item status is unsupported.');
        }

        if ($this->status === self::STATUS_QUEUED) {
            if ($this->failureCategory !== null || $this->snapshot !== null || $this->processingStartedAt !== null) {
                throw new \InvalidArgumentException('Queued catalog import items cannot contain a failure or snapshot.');
            }
        } elseif ($this->attempts < 1) {
            throw new \InvalidArgumentException('Processed catalog import items require at least one attempt.');
        }

        if ($this->status === self::STATUS_PROCESSING
            && ($this->failureCategory !== null || $this->snapshot !== null)) {
            throw new \InvalidArgumentException('Processing catalog import items cannot contain a failure or snapshot.');
        }
        if ($this->status !== self::STATUS_PROCESSING && $this->processingStartedAt !== null) {
            throw new \InvalidArgumentException('Only processing catalog import items can contain a lease start time.');
        }
        if ($this->status === self::STATUS_FAILED
            && (!is_string($this->failureCategory) || !isset(self::FAILURE_MESSAGES[$this->failureCategory]) || $this->snapshot !== null)) {
            throw new \InvalidArgumentException('Failed catalog import items require a fixed failure category only.');
        }
        if ($this->status === self::STATUS_SUCCEEDED
            && ($this->failureCategory !== null || !$this->snapshot instanceof NormalizedProductSnapshot)) {
            throw new \InvalidArgumentException('Successful catalog import items require one normalized snapshot.');
        }
        if ($this->status !== self::STATUS_FAILED && $this->failureCategory !== null) {
            throw new \InvalidArgumentException('Only failed catalog import items may contain a failure category.');
        }
        if ($this->status !== self::STATUS_SUCCEEDED && $this->snapshot !== null) {
            throw new \InvalidArgumentException('Only successful catalog import items may contain a product snapshot.');
        }
        if ($this->snapshot instanceof NormalizedProductSnapshot) {
            $this->assertSafeSnapshotIdentity($this->snapshot);
        }
    }

    public static function fromUrl(string $url): self
    {
        $canonical = self::canonicalProviderUrl($url);
        $productKey = $canonical['productKey'];

        return new self(
            hash('sha256', $productKey),
            $canonical['provider'],
            $canonical['productId'],
            $productKey,
            $canonical['url'],
            self::STATUS_QUEUED,
            0,
            null,
            null
        );
    }

    public function markProcessing(?\DateTimeImmutable $startedAt = null): self
    {
        if ($this->status !== self::STATUS_QUEUED) {
            throw new \LogicException('Only queued catalog import items can begin processing.');
        }
        if ($this->attempts >= self::MAX_ATTEMPTS) {
            throw new \LogicException('The catalog import item has exhausted its processing attempts.');
        }

        $startedAt ??= new \DateTimeImmutable('now', new \DateTimeZone('UTC'));

        return $this->withState(
            self::STATUS_PROCESSING,
            $this->attempts + 1,
            null,
            null,
            $startedAt->setTimezone(new \DateTimeZone('UTC'))
        );
    }

    public function markSucceeded(NormalizedProductSnapshot $snapshot, int $expectedAttempt): self
    {
        $normalizedSnapshot = $this->normalizeSnapshot($snapshot);
        if ($this->status !== self::STATUS_PROCESSING || $this->attempts !== $expectedAttempt) {
            throw new \LogicException('Only processing catalog import items can succeed.');
        }

        return $this->withState(self::STATUS_SUCCEEDED, $this->attempts, null, $normalizedSnapshot, null);
    }

    public function markFailed(string $failureCategory, int $expectedAttempt): self
    {
        if (!isset(self::FAILURE_MESSAGES[$failureCategory])) {
            throw new \InvalidArgumentException('Catalog import failure category is unsupported.');
        }
        if ($this->status !== self::STATUS_PROCESSING || $this->attempts !== $expectedAttempt) {
            throw new \LogicException('Only processing catalog import items can fail.');
        }

        return $this->withState(self::STATUS_FAILED, $this->attempts, $failureCategory, null, null);
    }

    public function retry(): self
    {
        if ($this->status !== self::STATUS_FAILED || $this->attempts >= self::MAX_ATTEMPTS) {
            throw new \LogicException('Only failed catalog import items can be retried.');
        }

        return $this->withState(self::STATUS_QUEUED, $this->attempts, null, null, null);
    }

    public function hasExpiredProcessingLease(\DateTimeImmutable $now): bool
    {
        if ($this->status !== self::STATUS_PROCESSING) {
            return false;
        }
        if ($this->processingStartedAt === null) {
            // Schema v1 records created before lease timestamps are recoverable.
            return true;
        }

        $leaseExpiresAt = $this->processingStartedAt->modify('+' . self::PROCESSING_LEASE_SECONDS . ' seconds');
        return $leaseExpiresAt <= $now->setTimezone(new \DateTimeZone('UTC'));
    }

    public function recoverStaleProcessing(\DateTimeImmutable $now): self
    {
        if (!$this->hasExpiredProcessingLease($now)) {
            throw new \LogicException('Only catalog import items with an expired processing lease can be recovered.');
        }

        if ($this->attempts >= self::MAX_ATTEMPTS) {
            return $this->withState(
                self::STATUS_FAILED,
                $this->attempts,
                self::FAILURE_PROCESSING_FAILED,
                null,
                null
            );
        }

        return $this->withState(self::STATUS_QUEUED, $this->attempts, null, null, null);
    }

    public function failExhaustedQueuedItem(): self
    {
        if ($this->status !== self::STATUS_QUEUED || $this->attempts < self::MAX_ATTEMPTS) {
            throw new \LogicException('Only a queued catalog import item at its attempt limit can be closed.');
        }

        return $this->withState(
            self::STATUS_FAILED,
            $this->attempts,
            self::FAILURE_PROCESSING_FAILED,
            null,
            null
        );
    }

    public function failureMessage(): ?string
    {
        return $this->failureCategory === null ? null : self::FAILURE_MESSAGES[$this->failureCategory];
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'provider' => $this->provider,
            'sourceProductId' => $this->sourceProductId,
            'productKey' => $this->productKey,
            'canonicalUrl' => $this->canonicalUrl,
            'status' => $this->status,
            'attempts' => $this->attempts,
            'failureCategory' => $this->failureCategory,
            'snapshot' => $this->snapshot?->toArray(),
            'processingStartedAt' => $this->processingStartedAt?->format('Y-m-d\\TH:i:s.uP'),
        ];
    }

    /** @param array<string, mixed> $data */
    public static function fromArray(array $data): self
    {
        $requiredKeys = [
            'id', 'provider', 'sourceProductId', 'productKey', 'canonicalUrl', 'status',
            'attempts', 'failureCategory', 'snapshot',
        ];
        $allowedKeys = [...$requiredKeys, 'processingStartedAt'];
        if (array_diff(array_keys($data), $allowedKeys) !== []
            || array_diff($requiredKeys, array_keys($data)) !== []) {
            throw new \UnexpectedValueException('Persisted catalog import item schema is invalid.');
        }

        foreach (['id', 'provider', 'sourceProductId', 'productKey', 'canonicalUrl', 'status'] as $key) {
            if (!is_string($data[$key])) {
                throw new \UnexpectedValueException('Persisted catalog import item text is invalid.');
            }
        }
        if (!is_int($data['attempts'])
            || ($data['failureCategory'] !== null && !is_string($data['failureCategory']))
            || ($data['snapshot'] !== null && !is_array($data['snapshot']))
            || (array_key_exists('processingStartedAt', $data)
                && $data['processingStartedAt'] !== null
                && !is_string($data['processingStartedAt']))) {
            throw new \UnexpectedValueException('Persisted catalog import item state is invalid.');
        }

        try {
            $snapshot = $data['snapshot'] === null
                ? null
                : NormalizedProductSnapshot::fromArray($data['snapshot']);
            $processingStartedAt = !isset($data['processingStartedAt'])
                ? null
                : new \DateTimeImmutable($data['processingStartedAt']);
        } catch (\Throwable $exception) {
            throw new \UnexpectedValueException('Persisted catalog import snapshot is invalid.', 0, $exception);
        }

        return new self(
            $data['id'],
            $data['provider'],
            $data['sourceProductId'],
            $data['productKey'],
            $data['canonicalUrl'],
            $data['status'],
            $data['attempts'],
            $data['failureCategory'],
            $snapshot,
            $processingStartedAt
        );
    }

    /** @return array{provider:string, productId:string, productKey:string, url:string} */
    private static function canonicalProviderUrl(string $url): array
    {
        if ($url === '' || strlen($url) > 2048 || preg_match('/[\x00-\x20\x7f]/', $url) === 1) {
            throw new \InvalidArgumentException('Catalog import URL is empty, too long, or contains control characters.');
        }

        try {
            $canonical = ProductUrlPolicy::canonicalize($url);
        } catch (FetchException $exception) {
            throw new \InvalidArgumentException('Catalog import URL is not a supported marketplace product URL.', 0, $exception);
        }

        $canonicalUrl = $canonical['url'];
        if ($canonical['provider'] === 'amazon_jp'
            && preg_match('~\Ahttps://www\.amazon\.co\.jp/dp/([A-Z0-9]{10})\z~D', $canonicalUrl, $matches) === 1) {
            $productId = $matches[1];
        } elseif ($canonical['provider'] === 'rakuten_ichiba'
            && preg_match('~\Ahttps://item\.rakuten\.co\.jp/([A-Za-z0-9][A-Za-z0-9_-]{0,127})/([A-Za-z0-9][A-Za-z0-9_-]{0,127})/\z~D', $canonicalUrl, $matches) === 1) {
            $productId = $matches[1] . ':' . $matches[2];
        } else {
            throw new \InvalidArgumentException('Catalog import URL could not be assigned a supported marketplace product identity.');
        }
        $provider = $canonical['provider'];

        return [
            'provider' => $provider,
            'productId' => $productId,
            'productKey' => $provider . ':' . $productId,
            'url' => $canonicalUrl,
        ];
    }

    private function assertSafeSnapshotIdentity(NormalizedProductSnapshot $snapshot): void
    {
        if ($snapshot->source !== $this->provider
            || $snapshot->sourceProductId !== $this->sourceProductId
            || $snapshot->deduplicationKey !== $this->productKey
            || $snapshot->sourceUrl !== $this->canonicalUrl
            || $snapshot->currency !== 'JPY'
            || $snapshot->priceJpy < 1) {
            throw new \InvalidArgumentException('Catalog import snapshot does not match its canonical JPY product item.');
        }
        foreach ($snapshot->images as $image) {
            if (!$image instanceof ProductImageSnapshot
                || self::safeImageUrl($image->url) !== $image->url) {
                throw new \InvalidArgumentException('Persisted catalog import image metadata must contain a query-free safe URL.');
            }
        }
    }

    private function normalizeSnapshot(NormalizedProductSnapshot $snapshot): NormalizedProductSnapshot
    {
        if ($snapshot->source !== $this->provider
            || $snapshot->sourceProductId !== $this->sourceProductId
            || $snapshot->deduplicationKey !== $this->productKey
            || $snapshot->currency !== 'JPY'
            || $snapshot->priceJpy < 1) {
            throw new \InvalidArgumentException('Catalog import snapshot does not match its canonical JPY product item.');
        }

        $snapshotData = $snapshot->toArray();
        $sourceIdentity = self::canonicalProviderUrl($snapshot->sourceUrl);
        if ($sourceIdentity['productKey'] !== $this->productKey) {
            throw new \InvalidArgumentException('Catalog import snapshot URL does not identify the queued product.');
        }
        $snapshotData['sourceUrl'] = $this->canonicalUrl;
        foreach ($snapshotData['images'] as &$image) {
            $image['url'] = self::safeImageUrl((string) $image['url']);
        }
        unset($image);
        $snapshotData['contentHash'] = self::snapshotContentHash($snapshotData);

        return NormalizedProductSnapshot::fromArray($snapshotData);
    }

    /** @param array<string, mixed> $snapshotData */
    private static function snapshotContentHash(array $snapshotData): string
    {
        $content = [];
        foreach ([
            'source', 'sourceProductId', 'sourceUrl', 'name', 'brand', 'description', 'categories',
            'priceJpy', 'currency', 'images', 'options', 'reviews', 'sourceRating', 'sourceReviewCount', 'availability',
        ] as $key) {
            $content[$key] = $snapshotData[$key] ?? null;
        }

        try {
            $serialized = json_encode($content, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
        } catch (\JsonException $exception) {
            throw new \InvalidArgumentException('Catalog import snapshot cannot be normalized safely.', 0, $exception);
        }

        return hash('sha256', $serialized);
    }

    private static function safeImageUrl(string $url): string
    {
        if ($url === '' || strlen($url) > 4096 || preg_match('/[\x00-\x20\x7f]/', $url) === 1) {
            throw new \InvalidArgumentException('Catalog image URL is malformed.');
        }
        $parts = parse_url($url);
        if (!is_array($parts)) {
            throw new \InvalidArgumentException('Catalog image URL is malformed.');
        }
        $scheme = strtolower((string) ($parts['scheme'] ?? ''));
        $host = strtolower(rtrim((string) ($parts['host'] ?? ''), '.'));
        if (!in_array($scheme, ['http', 'https'], true)
            || $host === ''
            || isset($parts['user'])
            || isset($parts['pass'])) {
            throw new \InvalidArgumentException('Catalog image metadata must use an absolute credential-free HTTP URL.');
        }

        $port = isset($parts['port']) ? (int) $parts['port'] : null;
        $portSuffix = $port !== null && !(($scheme === 'http' && $port === 80) || ($scheme === 'https' && $port === 443))
            ? ':' . $port
            : '';
        $path = (string) ($parts['path'] ?? '');

        return $scheme . '://' . $host . $portSuffix . $path;
    }

    private function withState(
        string $status,
        int $attempts,
        ?string $failureCategory,
        ?NormalizedProductSnapshot $snapshot,
        ?\DateTimeImmutable $processingStartedAt
    ): self {
        return new self(
            $this->id,
            $this->provider,
            $this->sourceProductId,
            $this->productKey,
            $this->canonicalUrl,
            $status,
            $attempts,
            $failureCategory,
            $snapshot,
            $processingStartedAt
        );
    }
}
