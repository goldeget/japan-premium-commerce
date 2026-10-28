<?php
declare(strict_types=1);

// Private scheduler entry point. Never expose dispatch through an HTTP controller.
if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}
$options = getopt('', ['shop:', 'limit:', 'channels:', 'retry-uncertain:', 'ack-possible-duplicate']);
$shop = filter_var($options['shop'] ?? null, FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]);
$limit = filter_var($options['limit'] ?? 25, FILTER_VALIDATE_INT, ['options' => ['min_range' => 1, 'max_range' => 100]]);
$channels = explode(',', (string) ($options['channels'] ?? ''));
if ($shop === false || $limit === false || $channels === [] || count(array_unique($channels)) !== count($channels)
    || array_diff($channels, ['mail', 'push']) !== []) {
    fwrite(STDERR, "Usage: php modules/ordenowaprocurement/bin/dispatch-notifications.php --shop=ID --channels=mail,push [--limit=25]\n");
    exit(2);
}
try {
    // Native bootstrap resolves a shop before Context can be configured in CLI.
    $_GET['id_shop'] = $shop;
    $_SERVER['HTTP_HOST'] ??= 'localhost';
    $_SERVER['SERVER_NAME'] ??= 'localhost';
    $_SERVER['REQUEST_URI'] ??= '/index.php';
    $_SERVER['SCRIPT_NAME'] = '/index.php';
    require dirname(__DIR__, 3) . '/config/config.inc.php';
    require_once dirname(__DIR__) . '/autoload.php';
    if (!\Ordenowa\Procurement\Integration\Runtime::procurementEnabled()) {
        throw new RuntimeException('Worker unavailable.');
    }
    $nativeShop = new Shop($shop);
    if (!Validate::isLoadedObject($nativeShop) || !$nativeShop->active) {
        throw new RuntimeException('Worker unavailable.');
    }
    Shop::setContext(Shop::CONTEXT_SHOP, $shop);
    Context::getContext()->shop = $nativeShop;
    Context::getContext()->link = new Link();
    $db = \Ordenowa\Procurement\Integration\Runtime::database();
    $recipients = new \Ordenowa\Procurement\Notifications\NativeRecipientResolver($db, _DB_PREFIX_);
    $transports = [];
    foreach ($channels as $channel) {
        if ($channel === 'push') {
            require_once _PS_MODULE_DIR_ . 'kuraneapush/autoload.php';
            $transports[$channel] = new \Ordenowa\Procurement\Notifications\PushTransport($recipients);
        } else {
            $transports[$channel] = new \Ordenowa\Procurement\Notifications\MailTransport($recipients);
        }
    }
    $dispatcher = new \Ordenowa\Procurement\Notifications\Dispatcher($db, $transports);
    if (isset($options['retry-uncertain'])) {
        $delivery = filter_var($options['retry-uncertain'], FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]);
        if ($delivery === false) {
            throw new InvalidArgumentException('Invalid delivery identifier.');
        }
        $dispatcher->retryUncertain($shop, $delivery, array_key_exists('ack-possible-duplicate', $options));
    }
    fwrite(STDOUT, json_encode($dispatcher->dispatch($shop, $limit), JSON_THROW_ON_ERROR) . "\n");
} catch (Throwable) {
    // Never emit recipient addresses, point data, provider errors or server configuration.
    fwrite(STDERR, "Notification worker failed; inspect channel state through authorized administration.\n");
    exit(1);
}
