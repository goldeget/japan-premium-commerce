<?php

declare(strict_types=1);

/** Register the public XML sitemap routes and safe robots hook without altering profile data. */
function upgrade_module_1_0_6($module): bool
{
    if (!is_object($module) || !method_exists($module, 'refreshRobotsSitemapDirective')) {
        return false;
    }

    if (!$module->registerHook(['moduleRoutes', 'actionAdminMetaAfterWriteRobotsFile'])) {
        return false;
    }

    return (bool) $module->refreshRobotsSitemapDirective();
}
