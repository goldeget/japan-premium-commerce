<?php

declare(strict_types=1);

require_once dirname(__DIR__) . '/autoload.php';

use Kuranea\BusinessProfile\Infrastructure\VersionedProfileRepository;

/** Add order-bound payment instruction and receipt-ledger tables without rewriting existing profile data. */
function upgrade_module_1_0_5($module): bool
{
    if (!is_object($module) || !method_exists($module, 'installTransferInstructionsTab')) {
        return false;
    }

    $repository = new VersionedProfileRepository();
    if (!$repository->install()) {
        return false;
    }

    return $module->registerHook(['displayOrderConfirmation', 'displayOrderDetail'])
        && $module->installTransferInstructionsTab();
}
