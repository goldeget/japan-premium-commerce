<?php

declare(strict_types=1);

function upgrade_module_1_0_4($module): bool
{
    return is_object($module) && $module->registerHook('actionFrontControllerSetVariables');
}
