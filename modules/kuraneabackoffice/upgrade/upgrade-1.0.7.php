<?php

declare(strict_types=1);
if (!defined('_PS_VERSION_')) exit;
function upgrade_module_1_0_7($module): bool
{
    return is_object($module) && method_exists($module, 'installKoreanAdminTabLabels') && $module->installKoreanAdminTabLabels();
}
