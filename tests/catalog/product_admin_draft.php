<?php

declare(strict_types=1);

use Kuranea\Catalog\Domain\ProductAdminDraft;

function assertProductDraftSame(mixed $expected, mixed $actual, string $message): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($message . '; expected ' . var_export($expected, true) . ', got ' . var_export($actual, true));
    }
}

$draft = ProductAdminDraft::fromArray([
    'name_ja' => 'CI 合成商品',
    'name_ko' => 'CI 합성 상품',
    'price_jpy' => '1280',
    'tax_rules_group_id' => '0',
    'quantity' => '6',
    'category_ids' => ['2', '4'],
    'description_ja' => "日本語の商品説明\n2行目",
    'description_ko' => "한국어 상품 설명\n둘째 줄",
    'options' => "色:青|赤\nサイズ:S|M",
]);

assertProductDraftSame('CI 合成商品', $draft->nameJa, 'Product drafts should retain the Japanese product name.');
assertProductDraftSame('CI 합성 상품', $draft->nameKo, 'Product drafts should retain the Korean product name.');
assertProductDraftSame(1280, $draft->priceJpy, 'Product drafts should use integer JPY prices.');
assertProductDraftSame(0, $draft->taxRulesGroupId, 'Product drafts should retain an explicit no-tax group selection.');
assertProductDraftSame(6, $draft->quantity, 'Product drafts should retain stock quantity.');
assertProductDraftSame([2, 4], $draft->categoryIds, 'Product drafts should normalize category identifiers.');
assertProductDraftSame([
    ['name' => '色', 'values' => ['青', '赤']],
    ['name' => 'サイズ', 'values' => ['S', 'M']],
], $draft->optionGroups, 'Product drafts should parse native option groups and values.');
assertProductDraftSame([], $draft->combinationQuantities, 'Product drafts without a posted variant map should retain the legacy shared quantity behavior.');

$variantDraft = ProductAdminDraft::fromArray([
    'name_ja' => 'CI 合成商品',
    'name_ko' => 'CI 합성 상품',
    'price_jpy' => '1280',
    'tax_rules_group_id' => 0,
    'quantity' => '6',
    'category_ids' => ['2'],
    'description_ja' => '',
    'description_ko' => '',
    'options' => "色:青|赤\nサイズ:S|M",
    'combination_quantities' => [
        '101' => '0',
        '102' => '4',
        '103' => 7,
    ],
]);
assertProductDraftSame(
    [101 => 0, 102 => 4, 103 => 7],
    $variantDraft->combinationQuantities,
    'Product drafts should normalize nonnegative native combination stock values by combination ID.'
);

$boundaryDraft = ProductAdminDraft::fromArray([
    'name_ja' => str_repeat('日', 128),
    'name_ko' => str_repeat('한', 128),
    'price_jpy' => '1280',
    'tax_rules_group_id' => '0',
    'quantity' => '0',
    'category_ids' => ['2'],
    'description_ja' => '',
    'description_ko' => '',
    'options' => str_repeat('옵', 64) . ':' . str_repeat('値', 128),
]);
assertProductDraftSame(128, mb_strlen($boundaryDraft->nameJa, 'UTF-8'), 'Japanese product names should allow the native 128-character limit.');
assertProductDraftSame(128, mb_strlen($boundaryDraft->nameKo, 'UTF-8'), 'Korean product names should allow the native 128-character limit.');
assertProductDraftSame(64, mb_strlen($boundaryDraft->optionGroups[0]['name'], 'UTF-8'), 'Korean option group names should use character limits.');
assertProductDraftSame(128, mb_strlen($boundaryDraft->optionGroups[0]['values'][0], 'UTF-8'), 'Japanese option values should use character limits.');

foreach ([
    ['price_jpy' => '0'],
    ['price_jpy' => '-1'],
    ['price_jpy' => '1.5'],
    ['quantity' => '-1'],
    ['tax_rules_group_id' => ''],
    ['tax_rules_group_id' => null],
    ['tax_rules_group_id' => '-1'],
    ['tax_rules_group_id' => '1.5'],
    ['category_ids' => []],
    ['options' => "色:青|青"],
    ['options' => "壊れた書式"],
    ['options' => "色:青|赤\nサイズ:S|M\n素材:綿|絹\n形:小|大"],
    ['name_ja' => str_repeat('日', 129)],
    ['name_ko' => str_repeat('한', 129)],
    ['options' => str_repeat('옵', 65) . ':値'],
    ['options' => '色:' . str_repeat('赤', 129)],
    ['combination_quantities' => '101=2'],
    ['combination_quantities' => ['not-a-combination' => '2']],
    ['combination_quantities' => ['101' => '-1']],
    ['combination_quantities' => ['101' => '1.5']],
    ['combination_quantities' => ['101' => '10000000']],
] as $invalid) {
    $values = [
        'name_ja' => '合成商品',
        'name_ko' => '합성 상품',
        'price_jpy' => '1280',
        'tax_rules_group_id' => '0',
        'quantity' => '6',
        'category_ids' => ['2'],
        'description_ja' => '',
        'description_ko' => '',
        'options' => '',
        'combination_quantities' => [],
    ];
    foreach ($invalid as $key => $value) {
        $values[$key] = $value;
    }

    try {
        ProductAdminDraft::fromArray($values);
    } catch (InvalidArgumentException) {
        continue;
    }

    throw new RuntimeException('Invalid product draft values must be rejected before native persistence.');
}
