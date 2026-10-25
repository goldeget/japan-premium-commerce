<?php

declare(strict_types=1);

use Kuranea\Catalog\Domain\ProductImageRightsEvidence;

require_once __DIR__ . '/../../modules/kuraneacatalog/autoload.php';

$assertImageRights = static function (bool $condition, string $message): void {
    if (!$condition) {
        throw new RuntimeException($message);
    }
};
$expectSyntheticBasisRejected = static function (string $caseName) use ($assertImageRights): void {
    try {
        ProductImageRightsEvidence::record(
            'synthetic_ci_fixture',
            'CI synthetic file only; no image usage rights are asserted.',
            'employee:1',
            new DateTimeImmutable('2026-10-25T03:00:00+00:00'),
            [91]
        );
    } catch (InvalidArgumentException) {
        return;
    }

    $assertImageRights(false, 'Synthetic image basis must be rejected for ' . $caseName . '.');
};

$requiredEnvironment = [
    'CI' => 'true',
    'GITHUB_ACTIONS' => 'true',
    'KURANEA_ISOLATED_CI' => '1',
    'KURANEA_CATALOG_IMPORT_FIXTURE_MODE' => '1',
    'KURANEA_CI_RUN_ID' => '40240000001',
    'KURANEA_CI_RUN_ATTEMPT' => '2',
    'KURANEA_CI_PROJECT_NAME' => 'kuranea-ci-40240000001-2',
];
$environmentNames = array_keys($requiredEnvironment);
$previousEnvironment = [];
foreach ($environmentNames as $name) {
    $value = getenv($name);
    $previousEnvironment[$name] = $value === false ? null : $value;
}

$setEnvironment = static function (array $values, array $names): void {
    foreach ($names as $name) {
        if (array_key_exists($name, $values)) {
            putenv($name . '=' . $values[$name]);
        } else {
            putenv($name);
        }
    }
};

try {
    $setEnvironment([], $environmentNames);
    foreach (['seller_owned', 'licensed', 'public_domain', 'explicit_permission'] as $basis) {
        $rights = ProductImageRightsEvidence::record(
            $basis,
            'Approved real-image usage document reference.',
            'employee:1',
            new DateTimeImmutable('2026-10-25T03:00:00+00:00'),
            [91]
        );
        $assertImageRights($rights->isUsageRightsClaim(),
            'Existing real usage-right bases must remain valid independently of CI environment variables.');
    }

    $expectSyntheticBasisRejected('a non-CI environment');
    $invalidCases = [
        'CI' => 'false',
        'GITHUB_ACTIONS' => 'false',
        'KURANEA_ISOLATED_CI' => '0',
        'KURANEA_CATALOG_IMPORT_FIXTURE_MODE' => '0',
        'KURANEA_CI_RUN_ID' => 'run-40240000001',
        'KURANEA_CI_RUN_ATTEMPT' => 'attempt-2',
        'KURANEA_CI_PROJECT_NAME' => 'kuranea-ci-40240000001-3',
    ];
    foreach ($invalidCases as $name => $invalidValue) {
        $environment = $requiredEnvironment;
        $environment[$name] = $invalidValue;
        $setEnvironment($environment, $environmentNames);
        $expectSyntheticBasisRejected($name . ' mismatch');
    }

    $setEnvironment($requiredEnvironment, $environmentNames);
    $synthetic = ProductImageRightsEvidence::record(
        'synthetic_ci_fixture',
        'CI synthetic file only; no image usage rights are asserted.',
        'employee:1',
        new DateTimeImmutable('2026-10-25T03:00:00+00:00'),
        [91]
    );
    $assertImageRights(!$synthetic->isUsageRightsClaim(),
        'The synthetic fixture basis must be explicitly distinguishable from usage-right evidence.');
    $restored = ProductImageRightsEvidence::fromArray($synthetic->toArray());
    $assertImageRights($restored->basis === 'synthetic_ci_fixture' && !$restored->isUsageRightsClaim(),
        'Serialized synthetic fixture evidence must remain labeled non-rights evidence.');

    $setEnvironment([], $environmentNames);
    $restoredOutsideFixture = ProductImageRightsEvidence::fromArray($synthetic->toArray());
    $assertImageRights(!$restoredOutsideFixture->isUsageRightsClaim(),
        'Persisted synthetic evidence should remain readable but never become a usage-right claim.');
    echo "PASS: synthetic image markers can only be newly recorded in isolated CI and remain non-rights after reload\n";
} finally {
    $setEnvironment($previousEnvironment, $environmentNames);
}
