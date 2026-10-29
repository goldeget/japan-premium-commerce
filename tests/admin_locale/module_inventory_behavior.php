<?php
declare(strict_types=1);

// Exercise the probe's real inventory closure against the project's actual
// module class, whose valid PrestaShop metadata does not include config.xml.
define('_PS_VERSION_', '9.2.0');
#[AllowDynamicProperties]
class Module
{
    public function __construct() {}
    public static function getInstanceByName(string $name): self
    {
        return new Kuraneabackoffice();
    }
}
$root = dirname(__DIR__, 2);
require $root . '/modules/kuraneabackoffice/kuraneabackoffice.php';
$source = file_get_contents(__DIR__ . '/native_mbo_error_authenticated.php');
$headerEnd = strpos($source, "ini_set(");
if ($headerEnd === false) throw new RuntimeException('native_probe_header_missing');
$header = str_replace('<?php', '', substr($source, 0, $headerEnd));
$browserAlias = eval($header . "\nreturn KernelBrowser::class;");
if ($browserAlias !== 'Symfony\\Bundle\\FrameworkBundle\\KernelBrowser') {
    throw new RuntimeException('native_kernel_browser_alias_must_resolve_to_framework_class');
}
$start = strpos($source, '$readModule = static function ');
$end = strpos($source, "\n};", $start);
if ($start === false || $end === false) {
    throw new RuntimeException('inventory_closure_missing');
}
eval(substr($source, $start, $end + 3 - $start));
$inventory = $readModule('kuraneabackoffice', true, ['kuraneabackoffice'], ['kuraneabackoffice'], realpath($root . '/modules'));
// The native router includes RequestContext::baseUrl after a real admin login.
$routeStart = strpos($source, '$canonicalMboUri = static function ');
$routeEnd = $routeStart === false ? false : strpos($source, "\n};", $routeStart);
if ($routeStart === false || $routeEnd === false) throw new RuntimeException('canonical_mbo_uri_closure_missing');
eval(substr($source, $routeStart, $routeEnd + 3 - $routeStart));
foreach (['/mbo/themes/catalog', '/admin-kuranea/index.php/mbo/themes/catalog'] as $path) {
    if ($canonicalMboUri($path) !== '/admin-kuranea/index.php/mbo/themes/catalog') {
        throw new RuntimeException('canonical_mbo_target_changed');
    }
}
foreach (['', '/admin-kuranea/mbo/themes/catalog', '/mbo/themes/catalog?x=1',
    'http://localhost:18081/admin-kuranea/index.php/mbo/themes/catalog',
    '/admin-kuranea/index.php/admin-kuranea/index.php/mbo/themes/catalog',
    '//example.org/mbo/themes/catalog', '/mbo/themes/catalog/'] as $path) {
    try { $canonicalMboUri($path); }
    catch (RuntimeException $error) {
        if ($error->getMessage() === 'native_mbo_route_contract_mismatch') continue;
        throw $error;
    }
    throw new RuntimeException('noncanonical_mbo_target_accepted');
}
if ($inventory !== ['installed' => true, 'active' => true, 'version' => (new Kuraneabackoffice())->version]) {
    throw new RuntimeException('native_project_metadata_not_used');
}
foreach ([[[], ['kuraneabackoffice']], [['kuraneabackoffice'], []]] as [$installed, $active]) {
    try {
        $readModule('kuraneabackoffice', true, $installed, $active, realpath($root . '/modules'));
    } catch (RuntimeException $error) {
        if (in_array($error->getMessage(), ['module_not_installed', 'module_not_active'], true)) {
            continue;
        }
        throw $error;
    }
    throw new RuntimeException('invalid_inventory_accepted');
}
echo "PASS actual project module inventory without optional config.xml\n";
