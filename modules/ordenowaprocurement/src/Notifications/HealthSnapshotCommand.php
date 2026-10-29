<?php
declare(strict_types=1);

namespace Ordenowa\Procurement\Notifications;

/** CLI argument and redacted output boundary shared by the private entry point and tests. */
final class HealthSnapshotCommand
{
    public const EXIT_OK = 0;
    public const EXIT_WARNING = 1;
    public const EXIT_CRITICAL = 2;
    public const EXIT_UNAVAILABLE = 3;
    public const EXIT_USAGE = 64;

    private const OPTION_NAMES = [
        'shop',
        'disk-warning-ratio', 'disk-critical-ratio',
        'backlog-warning', 'backlog-critical',
        'failed-warning', 'failed-critical',
        'uncertain-warning', 'uncertain-critical',
        'stale-after-seconds',
    ];

    /**
     * @param list<string> $arguments Args excluding the script filename
     * @param callable(int,HealthSnapshotThresholds):array $collect
     * @param resource $stdout
     * @param resource $stderr
     */
    public static function run(array $arguments, callable $collect, $stdout, $stderr): int
    {
        try {
            [$shop, $thresholds] = self::parseArguments($arguments);
        } catch (\Throwable) {
            fwrite($stderr, self::usage() . "\n");
            return self::EXIT_USAGE;
        }

        try {
            $result = self::safeResult($collect($shop, $thresholds));
            fwrite($stdout, json_encode($result, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . "\n");
            return match ($result['status']) {
                'ok' => self::EXIT_OK,
                'warning' => self::EXIT_WARNING,
                'critical' => self::EXIT_CRITICAL,
            };
        } catch (\Throwable) {
            fwrite($stderr, "Health snapshot unavailable.\n");
            return self::EXIT_UNAVAILABLE;
        }
    }

    private static function safeResult(mixed $result): array
    {
        $topLevelKeys = ['status', 'shop_id', 'database_select_1', 'disk_free_ratio', 'notification_counts'];
        $countKeys = ['backlog', 'future_retry', 'undelivered_events', 'failed', 'uncertain', 'oldest_stale_age_seconds'];
        if (!is_array($result) || !self::hasExactKeys($result, $topLevelKeys)
            || !in_array($result['status'] ?? null, ['ok', 'warning', 'critical'], true)
            || !is_int($result['shop_id'] ?? null) || $result['shop_id'] < 1
            || ($result['database_select_1'] ?? null) !== true
            || (!is_int($result['disk_free_ratio'] ?? null) && !is_float($result['disk_free_ratio'] ?? null))
            || !is_finite((float) $result['disk_free_ratio']) || $result['disk_free_ratio'] < 0 || $result['disk_free_ratio'] > 1
            || !is_array($result['notification_counts'] ?? null)
            || !self::hasExactKeys($result['notification_counts'], $countKeys)) {
            throw new \RuntimeException('Invalid health snapshot result.');
        }
        foreach ($countKeys as $key) {
            if (!is_int($result['notification_counts'][$key]) || $result['notification_counts'][$key] < 0) {
                throw new \RuntimeException('Invalid health snapshot result.');
            }
        }

        return [
            'status' => $result['status'],
            'shop_id' => $result['shop_id'],
            'database_select_1' => true,
            'disk_free_ratio' => (float) $result['disk_free_ratio'],
            'notification_counts' => [
                'backlog' => $result['notification_counts']['backlog'],
                'future_retry' => $result['notification_counts']['future_retry'],
                'undelivered_events' => $result['notification_counts']['undelivered_events'],
                'failed' => $result['notification_counts']['failed'],
                'uncertain' => $result['notification_counts']['uncertain'],
                'oldest_stale_age_seconds' => $result['notification_counts']['oldest_stale_age_seconds'],
            ],
        ];
    }

    /** @param array<mixed> $value @param list<string> $expected */
    private static function hasExactKeys(array $value, array $expected): bool
    {
        $actual = array_keys($value);
        sort($actual);
        sort($expected);
        return $actual === $expected;
    }

    /** @param list<string> $arguments @return array{0:int,1:HealthSnapshotThresholds} */
    private static function parseArguments(array $arguments): array
    {
        $raw = [];
        foreach ($arguments as $argument) {
            if (!is_string($argument) || preg_match('/\A--([a-z][a-z0-9-]*)=(.+)\z/D', $argument, $match) !== 1) {
                throw new \InvalidArgumentException('Invalid arguments.', 422);
            }
            $name = $match[1];
            if (!in_array($name, self::OPTION_NAMES, true) || array_key_exists($name, $raw)) {
                throw new \InvalidArgumentException('Invalid arguments.', 422);
            }
            $raw[$name] = $match[2];
        }
        if (!isset($raw['shop']) || preg_match('/\A[0-9]+\z/D', $raw['shop']) !== 1) {
            throw new \InvalidArgumentException('Invalid arguments.', 422);
        }
        $shop = filter_var($raw['shop'], FILTER_VALIDATE_INT, [
            'options' => ['min_range' => 1, 'max_range' => 2_147_483_647],
        ]);
        if ($shop === false) {
            throw new \InvalidArgumentException('Invalid arguments.', 422);
        }
        unset($raw['shop']);
        return [$shop, HealthSnapshotThresholds::fromOptions($raw)];
    }

    private static function usage(): string
    {
        return 'Usage: php health-snapshot.php --shop=ID [--disk-warning-ratio=0.10 --disk-critical-ratio=0.05 '
            . '--backlog-warning=100 --backlog-critical=500 --failed-warning=1 --failed-critical=10 '
            . '--uncertain-warning=1 --uncertain-critical=5 --stale-after-seconds=900]';
    }
}
