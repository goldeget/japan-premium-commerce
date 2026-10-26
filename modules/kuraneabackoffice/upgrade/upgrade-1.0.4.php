<?php

if (!defined('_PS_VERSION_')) {
    exit;
}

function upgrade_module_1_0_4($module): bool
{
    return is_object($module)
        && method_exists($module, 'installSupportContactPrivacy')
        && $module->installSupportContactPrivacy();
}
