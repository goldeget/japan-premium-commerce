<?php

declare(strict_types=1);
if (!defined('_PS_VERSION_')) {
    exit;
}
require_once dirname(__DIR__) . '/autoload.php';

function upgrade_module_1_0_2($module): bool
{
    return is_object($module) && (new \Kuranea\Push\Infrastructure\PushOutboxRepository())->install();
}
