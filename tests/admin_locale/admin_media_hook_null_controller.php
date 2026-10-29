<?php

declare(strict_types=1);

define('_PS_VERSION_', '9.2.0');

#[AllowDynamicProperties]
class Module
{
    public mixed $context = null;
    public string $_path = '/modules/kuraneabackoffice/';

    public function __construct()
    {
    }
}

class AdminDashboardController
{
    /** @var list<string> */
    public array $scripts = [];

    public function addJs(string $path): void
    {
        $this->scripts[] = $path;
    }
}

$root = getenv('ORDENOWA_TEST_REPO_ROOT') ?: dirname(__DIR__, 2);
require $root . '/modules/kuraneabackoffice/kuraneabackoffice.php';
$module = new Kuraneabackoffice();
$module->context = (object) [
    'language' => (object) ['iso_code' => 'ko'],
    'controller' => null,
];

try {
    $module->hookActionAdminControllerSetMedia();
} catch (Throwable) {
    fwrite(STDERR, "hook failed for a native page without legacy controller context\n");
    exit(1);
}

$dashboard = new AdminDashboardController();
$module->context->controller = $dashboard;
$module->hookActionAdminControllerSetMedia();
if ($dashboard->scripts !== ['/modules/kuraneabackoffice/views/js/dashboard-korean.js']) {
    fwrite(STDERR, "dashboard Korean asset registration changed\n");
    exit(1);
}

echo "PASS media hook tolerates absent native controller and preserves dashboard asset\n";
