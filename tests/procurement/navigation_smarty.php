<?php
declare(strict_types=1);

// Render the real child-theme footer with PrestaShop's actual Smarty engine.
$root = dirname(__DIR__, 2);
$bootstrap = getenv('PROCUREMENT_SMARTY_BOOTSTRAP') ?: '/var/www/html/vendor/smarty/smarty/libs/Smarty.class.php';
if (!is_file($bootstrap)) throw new RuntimeException('Installed PrestaShop Smarty dependency is required.');
require $bootstrap;
set_error_handler(static function (int $level, string $message, string $file, int $line): bool {
    if ($level !== E_DEPRECATED) throw new ErrorException($message, 0, $level, $file, $line);
    return true;
});
$directory = sys_get_temp_dir() . '/ordenowa-navigation-' . bin2hex(random_bytes(6));
mkdir($directory . '/_partials', 0700, true);
mkdir($directory . '/compiled', 0700);
file_put_contents($directory . '/_partials/copyright.tpl', '<small>ORDENOWA</small>');
$smarty = new Smarty();
$smarty->setTemplateDir($directory);
$smarty->setCompileDir($directory . '/compiled');
$calls = [];
$smarty->registerPlugin('function', 'hook', static function (array $params) use (&$calls): string {
    $calls[] = $params;
    return isset($params['mod']) ? '<span>Approved platform footer</span>' : '<a href="/cart">Legacy retail links</a>';
});
$checks = 0;
$assert = static function (bool $value) use (&$checks): void {
    ++$checks;
    if (!$value) throw new RuntimeException('Platform footer navigation contract failed.');
};
foreach (['ja-JP', 'en-US', 'ko-KR'] as $locale) {
    foreach ([false, true] as $enabled) {
        $calls = [];
        $smarty->assign([
            'language' => ['locale' => $locale], 'ordenowaProcurementEnabled' => $enabled,
            'ordenowaWorkspaceUrl' => '/workspace', 'ordenowaWorkspaceRequestsUrl' => '/workspace?view=requests',
            'ordenowaWorkspacePointsUrl' => '/workspace?view=points',
            'urls' => ['pages' => ['index' => '/', 'search' => '/search', 'my_account' => '/account', 'cart' => '/cart']],
        ]);
        $html = $smarty->fetch($root . '/themes/kuranea/templates/_partials/footer.tpl');
        $document = new DOMDocument();
        $previous = libxml_use_internal_errors(true);
        $document->loadHTML('<?xml encoding="UTF-8">' . $html);
        libxml_clear_errors(); libxml_use_internal_errors($previous);
        $xpath = new DOMXPath($document);
        $links = $xpath->query('//nav[contains(@class,"kuranea-mobile-nav")]/a');
        $hrefs = [];
        foreach ($links as $link) $hrefs[] = $link->getAttribute('href');
        $assert(count($hrefs) === 4);
        if ($enabled) {
            $assert($hrefs === ['/workspace', '/workspace?view=requests', '/workspace?view=points', '/account']);
            $assert(!str_contains($html, 'href="/cart"') && !str_contains($html, 'href="/search"'));
            $assert(array_column($calls, 'mod') === ['ps_customeraccountlinks', 'ordenowaprocurement']);
            $assert(!str_contains($html, 'Legacy retail links'));
        } else {
            $assert($hrefs === ['/', '/search', '/account', '/cart']);
            $assert(array_column($calls, 'h') === ['displayFooterBefore', 'displayFooter', 'displayFooterAfter']);
        }
    }
}
echo 'PASS ' . $checks . ' actual Smarty footer checks across JA/EN/KO platform and legacy modes' . PHP_EOL;
