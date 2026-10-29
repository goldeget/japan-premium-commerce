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
$root = getenv('ORDENOWA_TEST_REPO_ROOT') ?: dirname(__DIR__, 2);
$root = realpath($root) ?: throw new RuntimeException('native_test_repo_root_missing');
require $root . '/modules/kuraneabackoffice/kuraneabackoffice.php';
require_once __DIR__ . '/native_admin_http_login.php';
require_once __DIR__ . '/native_admin_mbo_route.php';
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
$routeHelper = file_get_contents(__DIR__ . '/native_admin_mbo_route.php');
if (!is_string($routeHelper) || !str_contains($source, 'NativeAdminMboRoute::canonicalizeGeneratedUri($catalogPath, $nativeSessionToken)')) {
    throw new RuntimeException('native_mbo_route_helper_not_used');
}
$nativeToken = 'a.' . str_repeat('b', 43) . '.' . str_repeat('c', 58);
$expectedNativeUri = '/admin-kuranea/index.php/modules/mbo/themes/catalog/?_token=' . $nativeToken;
if (NativeAdminMboRoute::nativeTargetUri($nativeToken) !== $expectedNativeUri) {
    throw new RuntimeException('native_mbo_module_route_target_changed');
}
foreach ([
    '/modules/mbo/themes/catalog/?_token=',
    '/admin-kuranea/index.php/modules/mbo/themes/catalog/?_token=' . $nativeToken,
    '/modules/mbo/themes/catalog/?_token=z.' . str_repeat('y', 43) . '.' . str_repeat('x', 58),
] as $generatedRoute) {
    if (NativeAdminMboRoute::canonicalizeGeneratedUri($generatedRoute, $nativeToken) !== $expectedNativeUri) {
        throw new RuntimeException('native_mbo_module_route_canonicalization_changed');
    }
}
foreach ([
    '', '/mbo/themes/catalog/?_token=' . $nativeToken,
    '/modules/mbo/themes/catalog?_token=' . $nativeToken,
    '/modules/mbo/themes/catalog/?_token=' . $nativeToken . '&_token=' . $nativeToken,
    '/modules/mbo/themes/catalog/?_token=' . $nativeToken . '&unexpected=1',
    'https://example.invalid/modules/mbo/themes/catalog/?_token=' . $nativeToken,
    '/modules/mbo/themes/catalog/?_token=invalid',
] as $invalidRoute) {
    try {
        NativeAdminMboRoute::canonicalizeGeneratedUri($invalidRoute, $nativeToken);
    } catch (RuntimeException $error) {
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
