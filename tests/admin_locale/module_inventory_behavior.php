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
$start = strpos($source, '$readModule = static function ');
$end = strpos($source, "\n};", $start);
if ($start === false || $end === false) {
    throw new RuntimeException('inventory_closure_missing');
}
eval(substr($source, $start, $end + 3 - $start));
$inventory = $readModule('kuraneabackoffice', true, ['kuraneabackoffice'], ['kuraneabackoffice'], realpath($root . '/modules'));
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
