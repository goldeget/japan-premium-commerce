<?php

declare(strict_types=1);
namespace Kuranea\Push\Domain;

final class Readiness
{
    public static function isolated(?array $env = null): bool
    {
        $get = static fn(string $name): string => (string) ($env === null ? getenv($name) : ($env[$name] ?? ''));
        $run = $get('GITHUB_RUN_ID');
        $attempt = $get('GITHUB_RUN_ATTEMPT');
        return $get('CI') === 'true' && $get('GITHUB_ACTIONS') === 'true'
            && $get('KURANEA_ISOLATED_CI') === '1' && $get('ORDENOWA_PUSH_TEST_MODE') === '1'
            && preg_match('/\A[1-9][0-9]*\z/D', $run) === 1 && preg_match('/\A[1-9][0-9]*\z/D', $attempt) === 1
            && $get('KURANEA_CI_PROJECT_NAME') === 'kuranea-ci-' . $run . '-' . $attempt;
    }

    public static function canSubscribe(?array $env, string $notice, bool $keyAvailable): bool
    {
        return $keyAvailable && trim($notice) !== '' && self::isolated($env);
    }
}
