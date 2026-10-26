<?php

declare(strict_types=1);

function adminRecoveryFixtureRequire(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

try {
    $runId = (string) getenv('GITHUB_RUN_ID');
    $attempt = (string) getenv('GITHUB_RUN_ATTEMPT');
    $project = (string) getenv('CI_COMPOSE_PROJECT_NAME');
    $adminEmail = trim((string) getenv('ADMIN_MAIL'));
    adminRecoveryFixtureRequire(
        getenv('CI') === 'true'
            && getenv('GITHUB_ACTIONS') === 'true'
            && getenv('KURANEA_ISOLATED_CI') === '1',
        'The employee recovery fixture is restricted to isolated GitHub Actions CI.'
    );
    adminRecoveryFixtureRequire(
        preg_match('/\A[0-9]+\z/D', $runId) === 1
            && preg_match('/\A[0-9]+\z/D', $attempt) === 1
            && $project === sprintf('kuranea-ci-%s-%s', $runId, $attempt),
        'The employee recovery fixture requires its exact run-scoped Compose project.'
    );
    adminRecoveryFixtureRequire(
        filter_var($adminEmail, FILTER_VALIDATE_EMAIL) !== false,
        'The employee recovery fixture requires the isolated primary administrator email.'
    );

    $email = sprintf(
        'ordenowa-admin-recovery-%s-%s-%s@example.invalid',
        $runId,
        $attempt,
        bin2hex(random_bytes(4))
    );
    adminRecoveryFixtureRequire(
        preg_match(
            sprintf('/\Aordenowa-admin-recovery-%s-%s-[a-f0-9]{8}@example\.invalid\z/D', $runId, $attempt),
            $email
        ) === 1,
        'The employee recovery fixture address is not run-scoped.'
    );

    $_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
    $_SERVER['REQUEST_URI'] = '/';
    $_SERVER['SCRIPT_NAME'] = '/index.php';
    require_once '/var/www/html/config/config.inc.php';

    $admin = new Employee();
    adminRecoveryFixtureRequire(
        $admin->getByEmail($adminEmail) !== false && (int) $admin->id === 1,
        'The configured email did not resolve to the primary employee in the isolated shop.'
    );
    adminRecoveryFixtureRequire(
        (int) Tab::getIdFromClassName('AdminDashboard') > 0,
        'The isolated shop does not contain the native Dashboard tab.'
    );

    $koreanLanguageId = (int) Language::getIdByIso('ko', true);
    $koreanLanguage = new Language($koreanLanguageId);
    adminRecoveryFixtureRequire(
        $koreanLanguageId > 0
            && Validate::isLoadedObject($koreanLanguage)
            && (bool) $koreanLanguage->active
            && $koreanLanguage->locale === 'ko-KR',
        'The isolated recovery employee requires the active Korean language.'
    );

    $employee = new Employee();
    $employee->firstname = 'ORDENOWA';
    $employee->lastname = 'CI Password Recovery';
    $employee->email = $email;
    $employee->id_lang = $koreanLanguageId;
    $employee->passwd = (string) $admin->passwd;
    $employee->active = true;
    $employee->id_profile = (int) $admin->id_profile;
    $employee->default_tab = (int) Tab::getIdFromClassName('AdminDashboard');
    $employee->bo_color = (string) ($admin->bo_color ?: '#6f42c1');
    $employee->bo_theme = (string) ($admin->bo_theme ?: 'default');
    $employee->bo_css = (string) ($admin->bo_css ?: 'theme.css');
    $employee->bo_width = max(0, (int) $admin->bo_width);
    $employee->bo_menu = (bool) $admin->bo_menu;
    adminRecoveryFixtureRequire(
        (bool) $employee->add() && (int) $employee->id > 1,
        'The isolated recovery employee could not be created separately from employee id 1.'
    );
    $savedEmployee = new Employee((int) $employee->id);
    adminRecoveryFixtureRequire(
        Validate::isLoadedObject($savedEmployee)
            && (int) $savedEmployee->id_lang === $koreanLanguageId,
        'The isolated recovery employee language did not persist as Korean.'
    );

    $result = json_encode(
        [
            'employee_id' => (int) $employee->id,
            'email' => $email,
        ],
        JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR
    );
    fwrite(STDOUT, 'ORDENOWA_ADMIN_RECOVERY_FIXTURE=' . $result . "\n");
} catch (Throwable $error) {
    $errorType = preg_match('/\A[A-Za-z_][A-Za-z0-9_]*\z/D', $error::class) === 1
        ? $error::class
        : 'Throwable';
    fwrite(STDERR, 'ORDENOWA_ADMIN_RECOVERY_FIXTURE_FAIL=' . $errorType . "\n");
    exit(1);
}
