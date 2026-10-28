<?php

declare(strict_types=1);

// Run with the real PrestaShop Smarty dependency; this never boots an application/DB.
$root = dirname(__DIR__, 2);
$bootstrap = getenv('PROCUREMENT_SMARTY_BOOTSTRAP') ?: '/var/www/html/vendor/smarty/smarty/libs/Smarty.class.php';
if (!is_file($bootstrap)) {
    throw new RuntimeException('Provide PROCUREMENT_SMARTY_BOOTSTRAP pointing to the installed PrestaShop Smarty.class.php.');
}
require $bootstrap;
require $root . '/modules/ordenowaprocurement/autoload.php';

use Ordenowa\Procurement\Presentation\WorkspaceView;

error_reporting(E_ALL & ~E_DEPRECATED);
set_error_handler(static function (int $severity, string $message, string $file, int $line): bool {
    if (error_reporting() & $severity) {
        throw new ErrorException($message, 0, $severity, $file, $line);
    }
    return false;
});

$directory = sys_get_temp_dir() . '/ordenowa-smarty-' . bin2hex(random_bytes(6));
mkdir($directory, 0700, true);
mkdir($directory . '/compiled', 0700);
file_put_contents($directory . '/page.tpl', '<html><head><title>{block name="head_seo_title"}{/block}</title></head><body><h1>{block name="page_title"}{/block}</h1>{block name="page_content"}{/block}</body></html>');
$smarty = new Smarty();
$smarty->setTemplateDir($directory);
$smarty->setCompileDir($directory . '/compiled');
$smarty->registerResource('module', new class($root) extends Smarty_Resource_Custom {
    public function __construct(private string $root) {}

    protected function fetch($name, &$source, &$mtime): void
    {
        if (!str_starts_with($name, 'ordenowaprocurement/views/templates/front/') || str_contains($name, '..')) {
            return;
        }
        $source = file_get_contents($this->root . '/modules/' . $name);
        $mtime = filemtime($this->root . '/modules/' . $name);
    }
});

$checks = 0;
$assert = static function (bool $result, string $label) use (&$checks): void {
    ++$checks;
    if (!$result) {
        throw new RuntimeException('FAIL ' . $label);
    }
};
$hostile = '<script>alert("hostile")</script>';
$url = 'https://ordenowa.example/index.php?fc=module&module=ordenowaprocurement&controller=workspace';
$row = ['id_assignment' => 1, 'id_request' => 2, 'version' => 1, 'status' => 'ACTIVE', 'default_quantity' => 1, 'max_quantity' => 3, 'quantity' => 2, 'instructions' => $hostile, 'submitted_at' => '2026-10-29 00:00:00', 'review_reason' => $hostile, 'product_snapshot' => ['names' => ['ja' => $hostile, 'en' => $hostile, 'ko' => $hostile], 'descriptions' => ['ja' => $hostile, 'en' => $hostile, 'ko' => $hostile], 'reference' => $hostile, 'reference_price' => '1200', 'currency' => 'JPY', 'image_url' => 'javascript:alert(1)', 'image_urls' => ['/img/p/1/1-large_default.jpg', '/img/p/2/2-large_default.jpg'], 'categories' => [['id_category' => 3, 'id_parent' => 2, 'names' => ['en' => $hostile]]]]];

foreach (['ja', 'en', 'ko'] as $locale) {
    $presenter = new WorkspaceView($locale);
    $product = $presenter->assignment($row);
    $product['url'] = $url . '&view=assignment&id_assignment=1';
    $request = $presenter->request(array_replace($row, ['status' => 'APPROVED']), []);
    $request['url'] = $url . '&view=request&id_request=2';
    foreach (['assignments', 'assignment', 'confirm', 'requests', 'request', 'points', 'notifications', 'error'] as $view) {
        $data = [
            'copy' => $presenter->copy(), 'view' => $view, 'token' => 'native-token', 'url' => $url,
            'account_url' => '/account', 'support_url' => '/contact', 'nav' => [], 'error' => '', 'error_status' => 0,
            'items' => $view === 'requests' ? [$request] : [$product], 'item' => $view === 'request' ? $request : $product,
            'categories' => [['id' => 2, 'name' => 'Home', 'url' => $url, 'children' => [['id' => 3, 'name' => $hostile, 'url' => $url, 'children' => []]]]],
            'category' => '', 'q' => $hostile, 'status' => '', 'statuses' => ['ACTIVE'], 'before_id' => 0, 'search_hidden' => ['fc' => 'module', 'module' => 'ordenowaprocurement', 'controller' => 'workspace'],
            'next_url' => $url . '&before_id=1', 'first_url' => $url, 'quantity' => 2, 'idempotency_key' => str_repeat('a', 64), 'edit_url' => $url,
            'balance' => 80, 'ledger' => [['id' => 1, 'request_id' => 2, 'delta' => -20, 'original_entry' => 3, 'original_url' => $url . '#ow-entry-3', 'type' => 'Correction', 'reason' => $hostile, 'created_at' => '2026-10-29 00:00:00', 'request_url' => $url]],
            'notifications' => [['id' => 1, 'label' => $hostile, 'created_at' => '2026-10-29 00:00:00', 'url' => $url]],
        ];
        foreach (['assignments', 'requests', 'points', 'notifications'] as $tab) {
            $data['nav'][$tab] = $url . '&view=' . $tab;
        }
        if ($view === 'error') {
            $data['error'] = $data['copy']['error_404'];
            $data['error_status'] = 404;
        }
        $smarty->assign('ow', $data);
        $html = $smarty->fetch($root . '/modules/ordenowaprocurement/views/templates/front/workspace.tpl');
        $assert(!str_contains($html, '<script>') && !str_contains($html, 'javascript:'), $locale . '/' . $view . ' hostile data cannot become markup');
        $assert(str_contains($html, 'data-testid="workspace"') && str_contains($html, 'data-csrf-token="native-token"'), $locale . '/' . $view . ' workspace CSRF fixture rendered');
        if (in_array($view, ['assignment', 'confirm'], true)) {
            $assert(str_contains($html, '&lt;script&gt;') && str_contains($html, 'method="post"'), $locale . '/' . $view . ' escaped content and native POST');
            $assert(substr_count($html, 'data-testid="product-photo"') === 2 && str_contains($html, 'data-image-count="2"'), $locale . '/' . $view . ' all approved gallery photos rendered');
            $assert(str_contains($html, $data['copy']['photo'] . ' 1') && str_contains($html, $data['copy']['photo'] . ' 2'), $locale . '/' . $view . ' localized numbered photo alternatives');
        }
        if ($view === 'assignments') {
            $assert(substr_count($html, 'ow-category-list') >= 2 && str_contains($html, 'name="controller" value="workspace"'), $locale . ' category submenu and query route fields');
            $assert(!str_contains($html, 'data-testid="product-gallery"') && substr_count($html, '<img ') === 1, $locale . ' assigned product card uses cover only');
        }
    }
}

echo 'PASS ' . $checks . ' actual Smarty checks across 24 customer view/locale renders' . PHP_EOL;
