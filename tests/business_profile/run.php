<?php

declare(strict_types=1);

function assertBusinessProfileSame(mixed $expected, mixed $actual, string $message): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($message . '; expected ' . var_export($expected, true) . ', got ' . var_export($actual, true));
    }
}

function assertBusinessProfileTrue(bool $actual, string $message): void
{
    if (!$actual) {
        throw new RuntimeException($message);
    }
}

$autoload = __DIR__ . '/../../modules/kuraneabusinessprofile/autoload.php';
assertBusinessProfileTrue(is_file($autoload), 'The business profile module autoloader must exist.');
require_once $autoload;

$initial = \Kuranea\BusinessProfile\Domain\ProfileDefaults::initial();
assertBusinessProfileSame('ORDENOWA', $initial['brand']['name']['en-US'], 'The confirmed English brand name should seed the editable profile.');
assertBusinessProfileSame('オーデノワ', $initial['brand']['name']['ja-JP'], 'The confirmed Japanese brand name should seed the editable profile.');
assertBusinessProfileSame('오데노와', $initial['brand']['name']['ko-KR'], 'The confirmed Korean brand name should seed the editable profile.');
assertBusinessProfileSame('法人向け商品調達・受発注サービス', $initial['brand']['description']['ja-JP'], 'The confirmed Japanese service description should seed the editable profile.');
assertBusinessProfileSame('企業と商品をつなぐ、次世代のB2B調達プラットフォーム', $initial['brand']['slogan']['ja-JP'], 'The confirmed slogan should seed the editable profile.');
assertBusinessProfileSame('4010001226242', $initial['company_reference']['corporate_number'], 'The company reference must retain the provided corporate number.');
assertBusinessProfileSame('LOGISTEED, Ltd.', $initial['company_reference']['name']['en-US'], 'The company reference must identify LOGISTEED, Ltd.');
assertBusinessProfileSame('pending', $initial['seller']['authorization_status'], 'Seller authorization must remain pending by default.');
assertBusinessProfileSame('', $initial['seller']['support']['phone'], 'The corporate phone must not be copied to shop support.');
assertBusinessProfileSame([], $initial['bank_accounts'], 'Real bank details must not be seeded.');
assertBusinessProfileSame([], $initial['brand']['assets'], 'Official brand assets must remain empty until the uploaded originals are available.');

$validator = new \Kuranea\BusinessProfile\Domain\ProfileValidator();
assertBusinessProfileSame([], $validator->validateDraft($initial), 'Incomplete operational details should still be saveable as a draft.');
$publishErrors = $validator->validateForPublish($initial);
assertBusinessProfileTrue($publishErrors !== [], 'An unapproved and incomplete seller profile must not be publishable.');
assertBusinessProfileTrue(
    in_array('판매사업 운영 승인이 확인되지 않았습니다.', $publishErrors, true),
    'Publish validation must explain in Korean that seller authorization is pending.'
);

$versions = new InMemoryBusinessProfileRepository();
$service = new \Kuranea\BusinessProfile\Domain\ProfileVersionService($versions, $validator);
$firstVersionId = $service->saveDraft(1, $initial, 10);
$versions->seedPublished(1, $firstVersionId);
$edited = $initial;
$edited['brand']['name']['ko-KR'] = '오데노와 테스트';
$secondVersionId = $service->saveDraft(1, $edited, 11);
$publishResult = $service->publish(1, $secondVersionId, 13);
$restoredVersionId = $service->restoreAsDraft(1, $firstVersionId, 12);
$history = $service->history(1);

assertBusinessProfileTrue($firstVersionId !== $secondVersionId, 'Saving edits should create a new immutable version.');
assertBusinessProfileTrue($restoredVersionId !== $firstVersionId, 'Restore should create a new version instead of overwriting the old one.');
assertBusinessProfileSame(false, $publishResult['published'], 'An unapproved profile must not publish.');
assertBusinessProfileSame($firstVersionId, $versions->loadPublished(1)?->id, 'Failed validation must leave the existing published pointer unchanged.');
assertBusinessProfileSame(3, count($history), 'The history should retain both saved versions and the restore version.');
assertBusinessProfileSame('오데노와 테스트', $history[1]->profile['brand']['name']['ko-KR'], 'The edited historical version should remain unchanged after restore.');
assertBusinessProfileSame('오데노와', $history[2]->profile['brand']['name']['ko-KR'], 'Restore should copy the selected version into a new draft.');
assertBusinessProfileSame($restoredVersionId, $versions->loadDraft(1)?->id, 'Restore should make the new version the current draft.');

$schema = \Kuranea\BusinessProfile\Infrastructure\DatabaseSchema::createVersionTableSql('ps_');
assertBusinessProfileTrue(str_contains($schema, 'CREATE TABLE IF NOT EXISTS `ps_kuraneabusinessprofile_version`'), 'Profile version storage should install idempotently.');
assertBusinessProfileTrue(!str_contains(strtoupper($schema), 'TRUNCATE'), 'The module schema must not clear existing tables or data.');

echo "PASS: ORDENOWA profile defaults, publication guard, immutable version history, and safe schema\n";

final class InMemoryBusinessProfileRepository implements \Kuranea\BusinessProfile\Domain\ProfileVersionRepositoryInterface
{
    /** @var array<int, list<\Kuranea\BusinessProfile\Domain\ProfileVersion>> */
    private array $versions = [];

    /** @var array<int, int> */
    private array $draftIds = [];

    /** @var array<int, int> */
    private array $publishedIds = [];

    private int $nextId = 1;

    public function insertVersion(int $shopId, array $profile, int $employeeId, ?int $parentVersionId): \Kuranea\BusinessProfile\Domain\ProfileVersion
    {
        $version = new \Kuranea\BusinessProfile\Domain\ProfileVersion(
            $this->nextId++,
            $shopId,
            $profile,
            $employeeId,
            $parentVersionId,
            '2026-10-22 00:00:00'
        );
        $this->versions[$shopId][] = $version;

        return $version;
    }

    public function setDraftPointer(int $shopId, int $versionId): void
    {
        $this->draftIds[$shopId] = $versionId;
    }

    public function seedPublished(int $shopId, int $versionId): void
    {
        $this->publishedIds[$shopId] = $versionId;
    }

    public function publishVersion(int $shopId, int $versionId, int $employeeId): void
    {
        $this->publishedIds[$shopId] = $versionId;
    }

    public function loadPublished(int $shopId): ?\Kuranea\BusinessProfile\Domain\ProfileVersion
    {
        return isset($this->publishedIds[$shopId]) ? $this->find($shopId, $this->publishedIds[$shopId]) : null;
    }

    public function loadDraft(int $shopId): ?\Kuranea\BusinessProfile\Domain\ProfileVersion
    {
        return isset($this->draftIds[$shopId]) ? $this->find($shopId, $this->draftIds[$shopId]) : null;
    }

    public function find(int $shopId, int $versionId): ?\Kuranea\BusinessProfile\Domain\ProfileVersion
    {
        foreach ($this->versions[$shopId] ?? [] as $version) {
            if ($version->id === $versionId) {
                return $version;
            }
        }

        return null;
    }

    /** @return list<\Kuranea\BusinessProfile\Domain\ProfileVersion> */
    public function history(int $shopId): array
    {
        return $this->versions[$shopId] ?? [];
    }
}
