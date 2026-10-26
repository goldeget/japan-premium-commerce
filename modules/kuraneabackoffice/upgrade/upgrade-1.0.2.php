<?php

if (!defined('_PS_VERSION_')) {
    exit;
}

function upgrade_module_1_0_2($module): bool
{
    return method_exists($module, 'installSupportAssignments')
        && $module->installSupportAssignments();
}
