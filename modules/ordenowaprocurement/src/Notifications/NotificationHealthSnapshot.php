<?php
declare(strict_types=1);

namespace Ordenowa\Procurement\Notifications;

use Ordenowa\Procurement\Infrastructure\Database;

/** Read-only, per-shop operational metrics. Never loads notification contents. */
final class NotificationHealthSnapshot
{
    /** @var \Closure(string):array{0:int|float|false,1:int|float|false} */
    private readonly \Closure $diskStats;

    /**
     * The optional disk probe exists for deterministic tests. Production uses
     * PHP's read-only filesystem statistics for the PrestaShop root volume.
     */
    public function __construct(
        private readonly Database $db,
        private readonly string $diskPath,
        ?callable $diskStats = null,
    ) {
        $this->diskStats = $diskStats !== null
            ? \Closure::fromCallable($diskStats)
            : static fn (string $path): array => [@disk_free_space($path), @disk_total_space($path)];
    }

    /** @return array{status:string,shop_id:int,database_select_1:bool,disk_free_ratio:float,notification_counts:array{backlog:int,future_retry:int,undelivered_events:int,failed:int,uncertain:int,oldest_stale_age_seconds:int}} */
    public function collect(int $shop, HealthSnapshotThresholds $thresholds): array
    {
        if ($shop < 1 || $shop > 2_147_483_647) {
            throw new \InvalidArgumentException('Invalid shop ID.', 422);
        }

        $databaseProbe = $this->db->value('SELECT 1');
        if ($databaseProbe !== 1 && $databaseProbe !== '1') {
            throw new \RuntimeException('Health source unavailable.');
        }

        $space = ($this->diskStats)($this->diskPath);
        if (!is_array($space) || count($space) !== 2) {
            throw new \RuntimeException('Health source unavailable.');
        }
        [$free, $total] = $space;
        if ((!is_int($free) && !is_float($free)) || (!is_int($total) && !is_float($total))
            || !is_finite((float) $free) || !is_finite((float) $total)
            || $free < 0 || $total <= 0 || $free > $total) {
            throw new \RuntimeException('Health source unavailable.');
        }
        $diskRatio = round((float) $free / (float) $total, 6);

        $deliveryCounts = $this->db->one(
            'SELECT COUNT(CASE WHEN status IN (\'PENDING\',\'RETRY\') AND available_at<=UTC_TIMESTAMP() THEN 1'
            . ' WHEN status=\'SENDING\' THEN 1 END) AS due_backlog_count,'
            . 'COUNT(CASE WHEN status=\'RETRY\' AND available_at>UTC_TIMESTAMP() THEN 1 END) AS future_retry_count,'
            . 'COUNT(CASE WHEN status=\'FAILED\' THEN 1 END) AS failed_count,'
            . 'COUNT(CASE WHEN status=\'UNCERTAIN\' THEN 1 END) AS uncertain_count,'
            . 'COALESCE(MAX(CASE WHEN status IN (\'PENDING\',\'RETRY\') AND available_at<=UTC_TIMESTAMP()'
            . ' THEN GREATEST(0,TIMESTAMPDIFF(SECOND,available_at,UTC_TIMESTAMP())) END),0) AS oldest_due_age_seconds,'
            . 'COALESCE(MAX(CASE WHEN status=\'SENDING\' AND claimed_at IS NOT NULL'
            . ' THEN GREATEST(0,TIMESTAMPDIFF(SECOND,claimed_at,UTC_TIMESTAMP())) END),0) AS oldest_sending_age_seconds FROM '
            . $this->db->table('notification_delivery') . ' WHERE id_shop=' . $shop
            . " AND status IN ('PENDING','RETRY','SENDING','FAILED','UNCERTAIN')"
        );
        $undelivered = $this->db->one(
            'SELECT COUNT(*) AS undelivered_count,'
            . 'COALESCE(MAX(GREATEST(0,TIMESTAMPDIFF(SECOND,n.created_at,UTC_TIMESTAMP()))),0) AS oldest_undelivered_age_seconds FROM '
            . $this->db->table('notification') . ' n WHERE n.id_shop=' . $shop
            . ' AND NOT EXISTS (SELECT 1 FROM ' . $this->db->table('notification_delivery')
            . ' d WHERE d.id_notification=n.id_notification AND d.id_shop=n.id_shop)'
        );
        if ($deliveryCounts === null || $undelivered === null) {
            throw new \RuntimeException('Health source unavailable.');
        }
        $dueBacklog = self::count($deliveryCounts['due_backlog_count'] ?? null);
        $undeliveredEvents = self::count($undelivered['undelivered_count'] ?? null);
        $oldestStaleAge = max(
            self::count($deliveryCounts['oldest_due_age_seconds'] ?? null),
            self::count($deliveryCounts['oldest_sending_age_seconds'] ?? null),
            self::count($undelivered['oldest_undelivered_age_seconds'] ?? null),
        );
        $safeCounts = [
            'backlog' => self::sumCounts($dueBacklog, $undeliveredEvents),
            'future_retry' => self::count($deliveryCounts['future_retry_count'] ?? null),
            'undelivered_events' => $undeliveredEvents,
            'failed' => self::count($deliveryCounts['failed_count'] ?? null),
            'uncertain' => self::count($deliveryCounts['uncertain_count'] ?? null),
            'oldest_stale_age_seconds' => $oldestStaleAge,
        ];

        $status = self::highestStatus([
            self::diskStatus($diskRatio, $thresholds),
            self::countStatus($safeCounts['backlog'], $thresholds->backlogWarning, $thresholds->backlogCritical),
            self::countStatus($safeCounts['failed'], $thresholds->failedWarning, $thresholds->failedCritical),
            self::countStatus($safeCounts['uncertain'], $thresholds->uncertainWarning, $thresholds->uncertainCritical),
            $oldestStaleAge >= $thresholds->staleAfterSeconds ? 'warning' : 'ok',
        ]);

        return [
            'status' => $status,
            'shop_id' => $shop,
            'database_select_1' => true,
            'disk_free_ratio' => $diskRatio,
            'notification_counts' => $safeCounts,
        ];
    }

    private static function count(mixed $value): int
    {
        if (!is_int($value) && !is_string($value)) {
            throw new \RuntimeException('Health source unavailable.');
        }
        $parsed = filter_var((string) $value, FILTER_VALIDATE_INT, [
            'options' => ['min_range' => 0, 'max_range' => 2_147_483_647],
        ]);
        if ($parsed === false) {
            throw new \RuntimeException('Health source unavailable.');
        }
        return $parsed;
    }

    private static function sumCounts(int $left, int $right): int
    {
        if ($left > 2_147_483_647 - $right) {
            throw new \RuntimeException('Health source unavailable.');
        }
        return $left + $right;
    }

    private static function diskStatus(float $freeRatio, HealthSnapshotThresholds $thresholds): string
    {
        if ($freeRatio <= $thresholds->diskCriticalRatio) {
            return 'critical';
        }
        if ($freeRatio <= $thresholds->diskWarningRatio) {
            return 'warning';
        }
        return 'ok';
    }

    private static function countStatus(int $count, int $warning, int $critical): string
    {
        if ($count >= $critical) {
            return 'critical';
        }
        if ($count >= $warning) {
            return 'warning';
        }
        return 'ok';
    }

    /** @param list<string> $statuses */
    private static function highestStatus(array $statuses): string
    {
        if (in_array('critical', $statuses, true)) {
            return 'critical';
        }
        if (in_array('warning', $statuses, true)) {
            return 'warning';
        }
        return 'ok';
    }
}
