<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

use InvalidArgumentException;

final class ProfileVersionService
{
    public function __construct(
        private readonly ProfileVersionRepositoryInterface $repository,
        private readonly ProfileValidator $validator,
    ) {
    }

    public function saveDraft(int $shopId, array $profile, int $employeeId): int
    {
        if ($shopId < 1 || $employeeId < 1) {
            throw new InvalidArgumentException('Shop and employee identifiers must be positive.');
        }

        $errors = $this->validator->validateDraft($profile);
        if ($errors !== []) {
            throw new InvalidArgumentException(implode(' ', $errors));
        }

        $parentVersionId = $this->repository->loadDraft($shopId)?->id;
        $version = $this->repository->insertVersion($shopId, $profile, $employeeId, $parentVersionId);
        $this->repository->setDraftPointer($shopId, $version->id);

        return $version->id;
    }

    /** @return array{published: bool, errors: list<string>} */
    public function publish(int $shopId, int $versionId, int $employeeId): array
    {
        $version = $this->repository->find($shopId, $versionId);
        if ($version === null) {
            return ['published' => false, 'errors' => ['게시할 설정 버전을 찾을 수 없습니다.']];
        }

        $errors = $this->validator->validateForPublish($version->profile);
        if ($errors !== []) {
            return ['published' => false, 'errors' => $errors];
        }

        $this->repository->publishVersion($shopId, $versionId, $employeeId);

        return ['published' => true, 'errors' => []];
    }

    public function restoreAsDraft(int $shopId, int $versionId, int $employeeId): int
    {
        $version = $this->repository->find($shopId, $versionId);
        if ($version === null) {
            throw new InvalidArgumentException('복원할 설정 버전을 찾을 수 없습니다.');
        }

        $currentDraft = $this->repository->loadDraft($shopId);
        $currentBankAccounts = $currentDraft?->profile['bank_accounts'] ?? [];
        $targetBankAccounts = $version->profile['bank_accounts'] ?? [];

        if ($targetBankAccounts !== $currentBankAccounts) {
            throw new InvalidArgumentException('은행 계좌 관리 권한이 필요한 버전은 일반 설정에서 복원할 수 없습니다.');
        }

        return $this->saveDraft($shopId, $version->profile, $employeeId);
    }

    public function restoreBankAccountsAsDraft(int $shopId, int $versionId, int $employeeId): int
    {
        $version = $this->repository->find($shopId, $versionId);
        $currentDraft = $this->repository->loadDraft($shopId);
        if ($version === null || $currentDraft === null) {
            throw new InvalidArgumentException('복원할 은행 계좌 또는 현재 초안을 찾을 수 없습니다.');
        }

        $profile = $currentDraft->profile;
        $profile['bank_accounts'] = $version->profile['bank_accounts'] ?? [];

        return $this->saveDraft($shopId, $profile, $employeeId);
    }

    /** @return list<ProfileVersion> */
    public function history(int $shopId): array
    {
        return $this->repository->history($shopId);
    }
}
