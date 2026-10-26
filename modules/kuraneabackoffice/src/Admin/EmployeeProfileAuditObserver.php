<?php

declare(strict_types=1);

namespace Kuranea\Backoffice\Admin;

use Kuranea\Backoffice\Infrastructure\EmployeeProfileAuditRepository;
use Throwable;

/** Captures Employee ObjectModel profile changes without observing the ACL permission grid. */
final class EmployeeProfileAuditObserver
{
    /** @var array<int, array{shopId:int,actorEmployeeId:?int,targetEmployeeId:int,oldProfileId:int}> */
    private static array $pendingByObject = [];

    /** @param array<string, mixed> $params */
    public static function beforeUpdate(array $params): void
    {
        $employee = $params['object'] ?? null;
        if (!$employee instanceof \Employee) {
            return;
        }

        $objectId = spl_object_id($employee);
        unset(self::$pendingByObject[$objectId]);
        $targetEmployeeId = (int) ($employee->id ?? 0);
        $proposedProfileId = (int) ($employee->id_profile ?? 0);
        if ($targetEmployeeId < 1 || $proposedProfileId < 1) {
            return;
        }

        try {
            $repository = new EmployeeProfileAuditRepository();
            $oldProfileId = $repository->profileIdForEmployee($targetEmployeeId);
            if ($oldProfileId === null || $oldProfileId === $proposedProfileId) {
                return;
            }

            $context = \Context::getContext();
            $shopId = \Shop::getContext() === \Shop::CONTEXT_SHOP
                ? (int) ($context->shop->id ?? 0)
                : 0;
            $actorId = (int) ($context->employee->id ?? 0);

            self::$pendingByObject[$objectId] = [
                'shopId' => max(0, $shopId),
                'actorEmployeeId' => $actorId > 0 ? $actorId : null,
                'targetEmployeeId' => $targetEmployeeId,
                'oldProfileId' => $oldProfileId,
            ];
        } catch (Throwable) {
            self::reportFailure();
        }
    }

    /** @param array<string, mixed> $params */
    public static function afterUpdate(array $params): void
    {
        $employee = $params['object'] ?? null;
        if (!$employee instanceof \Employee) {
            return;
        }

        $objectId = spl_object_id($employee);
        $pending = self::$pendingByObject[$objectId] ?? null;
        unset(self::$pendingByObject[$objectId]);
        if (!is_array($pending)) {
            return;
        }

        try {
            $repository = new EmployeeProfileAuditRepository();
            $persistedProfileId = $repository->profileIdForEmployee($pending['targetEmployeeId']);
            if ($persistedProfileId === null || $persistedProfileId === $pending['oldProfileId']) {
                return;
            }

            $repository->appendProfileChange(
                $pending['shopId'],
                $pending['actorEmployeeId'],
                $pending['targetEmployeeId'],
                $pending['oldProfileId'],
                $persistedProfileId
            );
        } catch (Throwable) {
            self::reportFailure();
        }
    }

    private static function reportFailure(): void
    {
        error_log('ORDENOWA employee profile audit could not record a profile update.');
    }
}
