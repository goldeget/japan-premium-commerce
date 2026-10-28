<?php

declare(strict_types=1);
require __DIR__ . '/ci_bootstrap.php';
$labels = ['ORDENOWA', '商品写真', 'Product photo', '상품 사진'];
foreach (['ja', 'en', 'ko'] as $locale) {
    $labels = array_merge($labels, array_values((new Ordenowa\Procurement\Presentation\WorkspaceView($locale))->copy()));
}
echo json_encode(array_values(array_unique($labels)), JSON_THROW_ON_ERROR);
