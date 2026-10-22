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

function assertBusinessProfileThrows(callable $callback, string $message): void
{
    try {
        $callback();
    } catch (InvalidArgumentException) {
        return;
    }

    throw new RuntimeException($message);
}

$autoload = __DIR__ . '/../../modules/kuraneabusinessprofile/autoload.php';
assertBusinessProfileTrue(is_file($autoload), 'The business profile module autoloader must exist.');
require_once $autoload;

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
assertBusinessProfileSame([], $initial['brand']['sources'], 'Original image metadata must remain empty until the official files are uploaded.');

$validator = new \Kuranea\BusinessProfile\Domain\ProfileValidator();
assertBusinessProfileSame([], $validator->validateDraft($initial), 'Incomplete operational details should still be saveable as a draft.');
$pendingPublishErrors = $validator->validateForPublish($initial);
assertBusinessProfileSame([], $pendingPublishErrors, 'A brand profile may publish without seller approval when transactional disclosures and assets remain gated.');
$approvedButIncomplete = $initial;
$approvedButIncomplete['seller']['authorization_status'] = 'approved';
$publishErrors = $validator->validateForPublish($approvedButIncomplete);
assertBusinessProfileTrue($publishErrors !== [], 'An approved seller profile must not publish until required seller disclosures and assets are complete.');
assertBusinessProfileTrue(
    in_array('판매자 정보(ja-JP) 중 필수 항목이 비어 있습니다.', $publishErrors, true),
    'Publish validation must explain in Korean that approved seller disclosures are incomplete.'
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
assertBusinessProfileSame(true, $publishResult['published'], 'Brand settings may publish while seller approval and commerce remain disabled.');
assertBusinessProfileSame($secondVersionId, $versions->loadPublished(1)?->id, 'Publishing must update the public pointer to the selected version.');
assertBusinessProfileSame(3, count($history), 'The history should retain both saved versions and the restore version.');
assertBusinessProfileSame('오데노와 테스트', $history[1]->profile['brand']['name']['ko-KR'], 'The edited historical version should remain unchanged after restore.');
assertBusinessProfileSame('오데노와', $history[2]->profile['brand']['name']['ko-KR'], 'Restore should copy the selected version into a new draft.');
assertBusinessProfileSame($restoredVersionId, $versions->loadDraft(1)?->id, 'Restore should make the new version the current draft.');


$oldBankProfile = $initial;
$oldBankProfile['bank_accounts'] = [[
    'bank_name' => 'TEST BANK',
    'branch_name' => 'TOKYO',
    'account_type' => 'ordinary',
    'account_number' => '11112222',
    'account_holder' => 'TEST HOLDER',
    'active' => true,
]];
$bankRepository = new InMemoryBusinessProfileRepository();
$bankService = new \Kuranea\BusinessProfile\Domain\ProfileVersionService($bankRepository, $validator);
$oldBankVersionId = $bankService->saveDraft(1, $oldBankProfile, 20);
$newBankProfile = $oldBankProfile;
$newBankProfile['bank_accounts'][0]['account_number'] = '99998888';
$currentBankVersionId = $bankService->saveDraft(1, $newBankProfile, 21);
assertBusinessProfileThrows(
    static fn () => $bankService->restoreAsDraft(1, $oldBankVersionId, 22),
    'A general settings restore must not change bank details without bank-management authorization.'
);
assertBusinessProfileSame($currentBankVersionId, $bankRepository->loadDraft(1)?->id, 'A denied bank restore must leave the draft pointer unchanged.');
$currentProfileWithBrandEdit = $bankRepository->loadDraft(1)?->profile ?? [];
$currentProfileWithBrandEdit['brand']['name']['ko-KR'] = '현재 브랜드';
$brandEditedVersionId = $bankService->saveDraft(1, $currentProfileWithBrandEdit, 23);
$authorizedBankRestoreId = $bankService->restoreBankAccountsAsDraft(1, $oldBankVersionId, 24);
assertBusinessProfileSame('11112222', $bankRepository->loadDraft(1)?->profile['bank_accounts'][0]['account_number'], 'A bank-only restore should restore the selected account.');
assertBusinessProfileSame('현재 브랜드', $bankRepository->loadDraft(1)?->profile['brand']['name']['ko-KR'], 'A bank-only restore must preserve unrelated current profile fields.');
assertBusinessProfileTrue($authorizedBankRestoreId !== $oldBankVersionId && $authorizedBankRestoreId !== $brandEditedVersionId, 'An authorized bank restore must create a new immutable version.');

$schema = \Kuranea\BusinessProfile\Infrastructure\DatabaseSchema::createVersionTableSql('ps_');
assertBusinessProfileTrue(str_contains($schema, 'CREATE TABLE IF NOT EXISTS `ps_kuraneabusinessprofile_version`'), 'Profile version storage should install idempotently.');
assertBusinessProfileTrue(!str_contains(strtoupper($schema), 'TRUNCATE'), 'The module schema must not clear existing tables or data.');

echo "PASS: ORDENOWA defaults, publication guard, immutable versions, restore, and safe schema\n";
