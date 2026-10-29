<?php
declare(strict_types=1);

namespace Ordenowa\Procurement\Notifications;

/** Technical CLI monitoring defaults; these values are not an approved SLA. */
final class HealthSnapshotThresholds
{
    public function __construct(
        public readonly float $diskWarningRatio = 0.10,
        public readonly float $diskCriticalRatio = 0.05,
        public readonly int $backlogWarning = 100,
        public readonly int $backlogCritical = 500,
        public readonly int $failedWarning = 1,
        public readonly int $failedCritical = 10,
        public readonly int $uncertainWarning = 1,
        public readonly int $uncertainCritical = 5,
        public readonly int $staleAfterSeconds = 900,
    ) {
        if (!is_finite($diskWarningRatio) || !is_finite($diskCriticalRatio)
            || $diskCriticalRatio < 0 || $diskCriticalRatio > 1
            || $diskWarningRatio < 0 || $diskWarningRatio > 1
            || $diskCriticalRatio >= $diskWarningRatio) {
            throw new \InvalidArgumentException('Invalid disk free ratio thresholds.', 422);
        }
        foreach ([
            [$backlogWarning, $backlogCritical],
            [$failedWarning, $failedCritical],
            [$uncertainWarning, $uncertainCritical],
        ] as [$warning, $critical]) {
            if ($warning < 1 || $critical < $warning || $critical > 2_147_483_647) {
                throw new \InvalidArgumentException('Invalid notification count thresholds.', 422);
            }
        }
        if ($staleAfterSeconds < 1 || $staleAfterSeconds > 31_536_000) {
            throw new \InvalidArgumentException('Invalid stale age threshold.', 422);
        }
    }

    public static function defaults(): self
    {
        return new self();
    }

    /** @param array<string,string> $options Raw CLI option values */
    public static function fromOptions(array $options): self
    {
        return new self(
            self::ratio($options, 'disk-warning-ratio', '0.10'),
            self::ratio($options, 'disk-critical-ratio', '0.05'),
            self::count($options, 'backlog-warning', '100'),
            self::count($options, 'backlog-critical', '500'),
            self::count($options, 'failed-warning', '1'),
            self::count($options, 'failed-critical', '10'),
            self::count($options, 'uncertain-warning', '1'),
            self::count($options, 'uncertain-critical', '5'),
            self::count($options, 'stale-after-seconds', '900'),
        );
    }

    /** @param array<string,string> $options */
    private static function ratio(array $options, string $name, string $default): float
    {
        $value = $options[$name] ?? $default;
        if (preg_match('/\A(?:0|1)(?:\.[0-9]{1,6})?\z/D', $value) !== 1) {
            throw new \InvalidArgumentException('Invalid disk free ratio thresholds.', 422);
        }
        $parsed = (float) $value;
        if (!is_finite($parsed) || $parsed < 0 || $parsed > 1) {
            throw new \InvalidArgumentException('Invalid disk free ratio thresholds.', 422);
        }
        return $parsed;
    }

    /** @param array<string,string> $options */
    private static function count(array $options, string $name, string $default): int
    {
        $value = $options[$name] ?? $default;
        if (preg_match('/\A[0-9]+\z/D', $value) !== 1) {
            throw new \InvalidArgumentException('Invalid notification count thresholds.', 422);
        }
        $parsed = filter_var($value, FILTER_VALIDATE_INT, [
            'options' => ['min_range' => 1, 'max_range' => 2_147_483_647],
        ]);
        if ($parsed === false) {
            throw new \InvalidArgumentException('Invalid notification count thresholds.', 422);
        }
        return $parsed;
    }
}
