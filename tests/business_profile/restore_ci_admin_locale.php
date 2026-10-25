<?php

declare(strict_types=1);

$runId = trim((string) getenv('GITHUB_RUN_ID'));
$runAttempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
$projectName = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$adminEmail = trim((string) getenv('ADMIN_MAIL'));
$expectedProjectName = 'kuranea-ci-' . $runId . '-' . $runAttempt;

if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $runAttempt) !== 1
    || $projectName !== $expectedProjectName
    || filter_var($adminEmail, FILTER_VALIDATE_EMAIL) === false
) {
    fwrite(STDERR, "BLOCKED: administrator locale restoration requires the matching disposable GitHub Actions shop.\n");
    exit(77);
}

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require_once '/var/www/html/config/config.inc.php';

$employee = new Employee();
if (!$employee->getByEmail($adminEmail)
    || !Validate::isLoadedObject($employee)
    || (int) $employee->id !== 1
) {
    fwrite(STDERR, "FAIL: the isolated primary Back Office employee could not be loaded for locale restoration.\n");
    exit(1);
}

$koreanLanguageId = (int) Language::getIdByIso('ko', true);
if ($koreanLanguageId < 1) {
    fwrite(STDERR, "FAIL: the isolated shop has no active Korean language for locale restoration.\n");
    exit(1);
}

$employee->id_lang = $koreanLanguageId;
if (!$employee->update()) {
    fwrite(STDERR, "FAIL: the isolated primary Back Office employee language could not be restored.\n");
    exit(1);
}

$savedEmployee = new Employee((int) $employee->id);
if (!Validate::isLoadedObject($savedEmployee) || (int) $savedEmployee->id_lang !== $koreanLanguageId) {
    fwrite(STDERR, "FAIL: the primary Back Office employee language did not persist as Korean.\n");
    exit(1);
}

fwrite(STDOUT, "PASS: restored the run-scoped primary Back Office employee language to Korean after locale QA.\n");
