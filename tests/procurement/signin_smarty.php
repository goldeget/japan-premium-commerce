<?php
declare(strict_types=1);

// Render the real child-theme module override using the installed Smarty engine.
$root = dirname(__DIR__, 2);
$bootstrap = getenv('PROCUREMENT_SMARTY_BOOTSTRAP') ?: '/var/www/html/vendor/smarty/smarty/libs/Smarty.class.php';
if (!is_file($bootstrap)) throw new RuntimeException('Installed Smarty dependency is required.');
require $bootstrap;
set_error_handler(static function (int $level, string $message, string $file, int $line): bool {
    if ($level !== E_DEPRECATED) throw new ErrorException($message, 0, $level, $file, $line);
    return true;
});
$directory = sys_get_temp_dir() . '/ordenowa-signin-' . bin2hex(random_bytes(6));
mkdir($directory, 0700, true);
$smarty = new Smarty();
$smarty->setCompileDir($directory);
$smarty->registerPlugin('modifier', 'strpos', 'strpos');
$smarty->registerPlugin('modifier', 'urlencode', 'urlencode');
$locale = 'en-US';
$smarty->registerPlugin('function', 'l', static function (array $params) use (&$locale): string {
    $label = (string) $params['s'];
    $labels = ['ja-JP' => ['Your account' => 'アカウント'], 'ko-KR' => ['Your account' => '내 계정']];
    return htmlspecialchars($labels[$locale][$label] ?? $label, ENT_QUOTES, 'UTF-8');
});
$checks = 0;
$assert = static function (bool $value) use (&$checks): void {
    ++$checks;
    if (!$value) throw new RuntimeException('Child sign-in scope/accessibility contract failed.');
};
foreach (['ja-JP', 'en-US', 'ko-KR'] as $locale) {
    foreach ([false, true] as $enabled) {
        foreach ([false, true] as $loggedIn) {
            $pages = [];
            foreach (['my_account', 'identity', 'contact', 'addresses', 'address', 'history', 'order_slip', 'discount', 'order_follow', 'authentication'] as $page) $pages[$page] = '/' . $page;
            $smarty->assign([
                'customer' => ['is_logged' => $loggedIn, 'firstname' => 'Synthetic', 'lastname' => 'Fixture', 'addresses' => []],
                'customerName' => 'Synthetic Fixture', 'ordenowaProcurementEnabled' => $enabled,
                'ordenowaWorkspaceUrl' => '/workspace', 'ordenowaWorkspaceLabel' => 'Workspace',
                'urls' => ['pages' => $pages, 'current_url' => '/workspace'], 'logout_url' => '/logout',
                'configuration' => ['is_catalog' => false, 'voucher_enabled' => true, 'return_enabled' => true],
            ]);
            $html = $smarty->fetch($root . '/themes/kuranea/modules/ps_customersignin/ps_customersignin.tpl');
            $document = new DOMDocument();
            $previous = libxml_use_internal_errors(true);
            $document->loadHTML('<?xml encoding="UTF-8">' . $html);
            libxml_clear_errors(); libxml_use_internal_errors($previous);
            $xpath = new DOMXPath($document);
            $assert($xpath->query('//*[@id="_desktop_ps_customersignin"]')->length === 1);
            $assert($xpath->query('//*[@id="userMenuButton"]')->length === (int) $loggedIn);
            if (!$loggedIn) {
                $assert($xpath->query('//a[starts-with(@href,"/authentication")]')->length === 1);
                continue;
            }
            $button = $xpath->query('//*[@id="userMenuButton"]')->item(0);
            if ($enabled) {
                $assert(trim($button->textContent) === $button->getAttribute('aria-label') || str_ends_with(trim($button->textContent), $button->getAttribute('aria-label')));
                $assert(!str_contains($button->textContent, 'Synthetic'));
                $hrefs = [];
                foreach ($xpath->query('//div[contains(@class,"dropdown-menu")]//a') as $link) $hrefs[] = $link->getAttribute('href');
                $assert($hrefs === ['/my_account', '/identity', '/workspace', '/contact', '/logout']);
                foreach (['/address', '/addresses', '/history', '/order_slip', '/discount', '/order_follow'] as $retail) $assert(!in_array($retail, $hrefs, true));
            } else {
                $assert(str_contains($html, 'href="/address"') && str_contains($html, 'href="/history"'));
                $assert(!str_contains($html, 'href="/workspace" class="dropdown-item'));
            }
        }
    }
}
$calls = [];
$smarty->registerPlugin('function', 'hook', static function (array $params) use (&$calls): string {
    $calls[] = $params;
    return '<span>Hook</span>';
});
foreach (['ja-JP', 'en-US', 'ko-KR'] as $locale) {
    foreach ([false, true] as $enabled) {
        $calls = [];
        $smarty->assign([
            'ordenowaProcurementEnabled' => $enabled, 'ordenowaBrandName' => 'ORDENOWA',
            'ordenowaLogoDesktop' => '', 'ordenowaLogoMobile' => '', 'shop' => ['name' => 'ORDENOWA'],
            'ordenowaWorkspaceUrl' => '/workspace', 'ordenowaWorkspaceLabel' => 'Workspace',
            'urls' => ['pages' => ['index' => '/', 'my_account' => '/account', 'cart' => '/cart']],
            'configuration' => ['is_catalog' => false], 'cart' => ['products_count' => 0],
        ]);
        $html = $smarty->fetch($root . '/themes/kuranea/templates/_partials/header.tpl');
        if ($enabled) {
            $assert(array_column($calls, 'h') === ['displayBanner', 'displayNav2', 'displayNav2']);
            $assert(array_column($calls, 'mod') === ['ps_languageselector', 'ps_customersignin']);
            $assert(!str_contains($html, 'id="_mobile_ps_shoppingcart"'));
            $assert(str_contains($html, 'col d-none d-md-flex align-items-center justify-content-end ordenowa-header-platform-nav'));
        } else {
            $assert(array_column($calls, 'h') === ['displayBanner', 'displayNav1', 'displayNav2', 'displayTop', 'displayNavFullWidth']);
            $assert(str_contains($html, 'id="_mobile_ps_shoppingcart"'));
        }
    }
}
echo 'PASS ' . $checks . ' real Smarty sign-in/header checks across JA/EN/KO authenticated/anonymous and platform/legacy modes' . PHP_EOL;
