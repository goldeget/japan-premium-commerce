<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

interface ProfileVersionRepositoryInterface
{
    public function insertVersion(int $shopId, array $profile, int $employeeId, ?int $parentVersionId): ProfileVersion;

    public function setDraftPointer(int $shopId, int $versionId): void;

    public function publishVersion(int $shopId, int $versionId, int $employeeId): void;

    public function loadDraft(int $shopId): ?ProfileVersion;

    public function loadPublished(int $shopId): ?ProfileVersion;

    public function find(int $shopId, int $versionId): ?ProfileVersion;

    /** @return list<ProfileVersion> */
    public function history(int $shopId): array;
}
