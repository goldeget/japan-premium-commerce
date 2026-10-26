<?php

declare(strict_types=1);

function supportFixtureRequire(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

$runId = (string) getenv('GITHUB_RUN_ID');
$attempt = (string) getenv('GITHUB_RUN_ATTEMPT');
$project = (string) getenv('CI_COMPOSE_PROJECT_NAME');
$expectedProject = sprintf('kuranea-ci-%s-%s', $runId, $attempt);
supportFixtureRequire(
    getenv('CI') === 'true'
        && getenv('GITHUB_ACTIONS') === 'true'
        && getenv('KURANEA_ISOLATED_CI') === '1'
        && preg_match('/\A[0-9]+\z/D', $runId) === 1
        && preg_match('/\A[0-9]+\z/D', $attempt) === 1
        && $project === $expectedProject
        && getenv('KURANEA_CI_PROJECT_NAME') === $expectedProject,
    'Customer support fixture requires the exact disposable GitHub Actions project.'
);

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require_once '/var/www/html/config/config.inc.php';

supportFixtureRequire(Module::isInstalled('contactform') && Module::isEnabled('contactform'), 'Native contact form is unavailable.');
supportFixtureRequire(
    Configuration::updateValue('PS_CUSTOMER_SERVICE_FILE_UPLOAD', 1),
    'Could not enable file upload for this disposable support test.'
);
supportFixtureRequire(
    Configuration::updateValue('CONTACTFORM_SEND_CONFIRMATION_EMAIL', 1),
    'Could not enable the native thread token confirmation for this disposable support test.'
);
supportFixtureRequire(
    Configuration::updateValue('CONTACTFORM_SEND_NOTIFICATION_EMAIL', 0),
    'Could not disable unrelated contact inbox notifications for this disposable support test.'
);
supportFixtureRequire(
    (int) Configuration::get('PS_CUSTOMER_SERVICE_FILE_UPLOAD') === 1
        && (int) Configuration::get('CONTACTFORM_SEND_CONFIRMATION_EMAIL') === 1
        && (int) Configuration::get('CONTACTFORM_SEND_NOTIFICATION_EMAIL') === 0,
    'Native contact form settings did not persist.'
);

supportFixtureRequire(
    Tools::getMaxUploadSize() >= 4096,
    'Disposable support acceptance needs at least 4096 bytes of effective PHP upload capacity.'
);

fwrite(STDOUT, "PASS: disposable native support upload and confirmation fixtures are ready.\n");
