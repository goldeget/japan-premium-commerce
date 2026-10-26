<?php

declare(strict_types=1);

if (!defined('_PS_VERSION_')) {
    exit;
}

function upgrade_module_1_0_4($module): bool
{
    return is_object($module) && $module->registerHook('actionObjectCustomerMessageAddAfter');
}
