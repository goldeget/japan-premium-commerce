<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

use DateTimeImmutable;

/** Staff-recorded image review evidence; the CI fixture marker is not a rights claim. */
final class ProductImageRightsEvidence
{
    public const BASIS_SYNTHETIC_CI_FIXTURE = 'synthetic_ci_fixture';
    public const MAX_IMAGE_IDS = 5;
    public const MAX_REFERENCE_LENGTH = 512;

    /** @param list<int> $imageIds */
    private function __construct(
        public readonly string $basis,
        public readonly string $reference,
        public readonly string $reviewedBy,
        public readonly DateTimeImmutable $reviewedAt,
        public readonly array $imageIds
    ) {
        $rightsBases = ['seller_owned', 'licensed', 'public_domain', 'explicit_permission'];
        if ($basis !== self::BASIS_SYNTHETIC_CI_FIXTURE && !in_array($basis, $rightsBases, true)) {
            throw new \InvalidArgumentException('이미지 사용권 검수 기록이 올바르지 않습니다.');
        }

        if (trim($reference) === ''
            || strlen($reference) > self::MAX_REFERENCE_LENGTH
            || preg_match('/[\x00-\x1f\x7f]/', $reference) === 1
            || trim($reviewedBy) === ''
            || $reviewedAt->getOffset() !== 0
            || !array_is_list($imageIds)
            || $imageIds === []
            || count($imageIds) > self::MAX_IMAGE_IDS) {
            throw new \InvalidArgumentException('이미지 사용권 검수 기록이 올바르지 않습니다.');
        }
        foreach ($imageIds as $imageId) {
            if (!is_int($imageId) || $imageId < 1) {
                throw new \InvalidArgumentException('이미지 사용권 기록에는 저장된 이미지 ID가 필요합니다.');
            }
        }
        if (count(array_unique($imageIds)) !== count($imageIds)) {
            throw new \InvalidArgumentException('이미지 사용권 기록에 중복 이미지 ID가 있습니다.');
        }
    }

    /** Record operator-supplied evidence; synthetic markers are run-scoped only. */
    public static function record(
        string $basis,
        string $reference,
        string $reviewedBy,
        DateTimeImmutable $reviewedAt,
        array $imageIds
    ): self {
        if ($basis === self::BASIS_SYNTHETIC_CI_FIXTURE && !self::isExactIsolatedFixtureEnvironment()) {
            throw new \InvalidArgumentException(
                '합성 fixture 이미지는 사용권 근거가 아니며 격리된 GitHub Actions fixture 환경에서만 기록할 수 있습니다.'
            );
        }

        return new self($basis, $reference, $reviewedBy, $reviewedAt, $imageIds);
    }

    /** Synthetic CI markers are deliberately not treated as usage-right claims. */
    public function isUsageRightsClaim(): bool
    {
        return $this->basis !== self::BASIS_SYNTHETIC_CI_FIXTURE;
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        return [
            'basis' => $this->basis,
            'reference' => $this->reference,
            'reviewedBy' => $this->reviewedBy,
            'reviewedAt' => $this->reviewedAt->format(DATE_ATOM),
            'imageIds' => $this->imageIds,
        ];
    }

    /** @param array<string, mixed> $data */
    public static function fromArray(array $data): self
    {
        $basis = $data['basis'] ?? null;
        $reference = $data['reference'] ?? null;
        $reviewedBy = $data['reviewedBy'] ?? null;
        $reviewedAt = $data['reviewedAt'] ?? null;
        $imageIds = $data['imageIds'] ?? null;
        if (!is_string($basis) || !is_string($reference) || !is_string($reviewedBy)
            || !is_string($reviewedAt) || !is_array($imageIds) || !array_is_list($imageIds)) {
            throw new \UnexpectedValueException('Persisted image rights evidence is invalid.');
        }
        try {
            $date = new DateTimeImmutable($reviewedAt);
        } catch (\Throwable $exception) {
            throw new \UnexpectedValueException('Persisted image rights timestamp is invalid.', 0, $exception);
        }

        return new self($basis, $reference, $reviewedBy, $date, $imageIds);
    }

    private static function isExactIsolatedFixtureEnvironment(): bool
    {
        $runId = getenv('KURANEA_CI_RUN_ID');
        $attempt = getenv('KURANEA_CI_RUN_ATTEMPT');
        if (getenv('CI') !== 'true'
            || getenv('GITHUB_ACTIONS') !== 'true'
            || getenv('KURANEA_ISOLATED_CI') !== '1'
            || getenv('KURANEA_CATALOG_IMPORT_FIXTURE_MODE') !== '1'
            || !is_string($runId)
            || preg_match('/\A[0-9]+\z/D', $runId) !== 1
            || !is_string($attempt)
            || preg_match('/\A[0-9]+\z/D', $attempt) !== 1) {
            return false;
        }

        return getenv('KURANEA_CI_PROJECT_NAME') === 'kuranea-ci-' . $runId . '-' . $attempt;
    }
}
