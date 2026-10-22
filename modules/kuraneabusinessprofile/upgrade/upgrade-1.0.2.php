<?php

function upgrade_module_1_0_2($module)
{
    return $module->registerHook('actionEmailSendBefore');
}
