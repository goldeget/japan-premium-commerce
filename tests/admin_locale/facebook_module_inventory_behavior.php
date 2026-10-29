<?php

declare(strict_types=1);

define('_PS_VERSION_', '9.2.0');

#[AllowDynamicProperties]
class Module
{
    public function __construct()
    {
    }

    public static function getInstanceByName(string $name): self
    {
        if ($name !== 'kuraneabackoffice') {
            throw new RuntimeException('unexpected_module_name');
        }

        return new Kuraneabackoffice();
    }
}

$root = dirname(__DIR__, 2);
if (!is_file($root . '/modules/kuraneabackoffice/kuraneabackoffice.php')) {
    // Local sidecar runs may point at the separate current project checkout;
    // the integrated CI run resolves directly from its repository root.
    $sourceRoot = getenv('KURANEA_MODULE_INVENTORY_SOURCE_ROOT') ?: '';
    $sourceRoot = $sourceRoot !== '' ? realpath($sourceRoot) : false;
    if ($sourceRoot === false || !is_file($sourceRoot . '/modules/kuraneabackoffice/kuraneabackoffice.php')) {
        throw new RuntimeException('project_module_source_root_missing');
    }
    $root = $sourceRoot;
}
require $root . '/modules/kuraneabackoffice/kuraneabackoffice.php';

$source = file_get_contents(__DIR__ . '/native_facebook_transport_fallback.php');
$start = is_string($source) ? strpos($source, '$readModule = static function (') : false;
$end = is_string($source) && $start !== false ? strpos($source, "\n};", $start) : false;
if (!is_string($source) || $start === false || $end === false) {
    throw new RuntimeException('native_module_inventory_closure_missing');
}
eval(substr($source, $start, $end + 3 - $start));

$modulesRoot = realpath($root . '/modules');
$modulePath = realpath($root . '/modules/kuraneabackoffice');
if ($modulesRoot === false || $modulePath === false || is_file($modulePath . '/config.xml')) {
    throw new RuntimeException('project_module_metadata_fixture_unexpected');
}
$inventory = $readModule(
    'kuraneabackoffice',
    ['kuraneabackoffice'],
    ['kuraneabackoffice'],
    $modulesRoot,
    true
);
$expectedModuleFile = realpath($modulePath . '/kuraneabackoffice.php');
$expectedVersion = (new Kuraneabackoffice())->version;
if ($inventory !== [
    'installed' => true,
    'active' => true,
    'version' => $expectedVersion,
    'module_path' => $modulePath,
] || $expectedModuleFile === false || realpath((new ReflectionClass(Module::getInstanceByName('kuraneabackoffice')))->getFileName()) !== $expectedModuleFile) {
    throw new RuntimeException('native_project_module_metadata_not_used');
}

echo "PASS native project module metadata without config.xml\n";
