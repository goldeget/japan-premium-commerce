<?php

declare(strict_types=1);
require __DIR__ . '/ci_bootstrap.php';
$fixture = ciFixture();
$fixture['languages'] = ['ja' => (int) Language::getIdByIso('ja', true), 'en' => (int) Language::getIdByIso('en', true), 'ko' => (int) Language::getIdByIso('ko', true)];
$module = Module::getInstanceByName('ordenowaprocurement');
ciAssert($module && $module->ensureInfrastructure(), 'Current module infrastructure missing');
$reader = new Employee((int) $fixture['reader']['id']);
$policyTab = (int) Tab::getIdFromClassName('AdminOrdenowaProcurementPolicies');
ciAssert(Validate::isLoadedObject($reader) && $policyTab > 0, 'Native policy reader fixture missing');
ciAssert((new Access())->updateLgcAccess((int) $reader->id_profile, $policyTab, 'view', true, false) === 'ok', 'Native policy READ fixture missing');
Profile::resetCacheAccesses();
$db = Ordenowa\Procurement\Integration\Runtime::database();
ciAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('request') . ' WHERE id_shop=1 AND id_customer=' . (int) $fixture['customers']['a']['id']) === 0, 'Fixture retargeting is forbidden after submission');
$reference = Ordenowa\Procurement\Integration\Runtime::productReference((int) $fixture['product_id'], (int) $fixture['product_attribute_id']);
if (count($reference['image_urls'] ?? []) < 2) {
    // Preserve the first approved snapshot. A second synthetic source identity
    // is reviewed with original CI artwork before its first approval.
    $context->employee = new Employee(1);
    $context->country = new Country((int) Country::getByIso('JP'));
    $context->cart = new Cart();
    require '/tmp/ordenowa-procurement-ci/catalog/prepare_ci_procurement_product.php';
    $product = prepareCiProcurementProduct('gallery');
    $fixture['product_id'] = (int) $product['product_id'];
    $fixture['product_attribute_id'] = (int) $product['product_attribute_id'];
    $reference = Ordenowa\Procurement\Integration\Runtime::productReference($fixture['product_id'], $fixture['product_attribute_id']);
}
ciAssert(count($reference['image_urls'] ?? []) >= 2 && $reference['source_url'] !== '', 'Reviewed native image gallery missing');
$fixture['category_path'] = [];
$expectedNames = [
    ['ja'=>'生活用品','en'=>'Daily necessities','ko'=>'생활용품'],
    ['ja'=>'キッチン用品','en'=>'Kitchenware','ko'=>'주방용품'],
];
$found = [];
foreach ($reference['categories'] ?? [] as $category) {
    foreach ($expectedNames as $level => $names) {
        $actualNames = $category['names'] ?? null;
        if (!is_array($actualNames)) continue;
        $expectedNamesSorted = $names;
        ksort($actualNames, SORT_STRING);
        ksort($expectedNamesSorted, SORT_STRING);
        if ($actualNames === $expectedNamesSorted) $found[$level] = $category;
    }
}
// Fresh acceptance requires a genuinely reviewed parent/leaf path.
// Approved native products are never reclassified for acceptance.
if (count($found) === 2) {
    ciAssert((int)$found[1]['id_parent'] === (int)$found[0]['id_category'], 'Reviewed native category hierarchy mismatch');
    $nativeIds = array_map('intval', Product::getProductCategories((int)$fixture['product_id']));
    ciAssert(in_array((int)$found[1]['id_category'], $nativeIds, true), 'Reviewed native leaf product placement missing');
    $fixture['category_path'] = [$found[0], $found[1]];
} else {
    throw new RuntimeException('Fresh reviewed native category path missing');
}
$native = new Product((int) $fixture['product_id'], false, null, 1);
ciAssert(!(bool) $native->active && !(bool) $native->available_for_order && $native->visibility === 'none', 'Gallery fixture became orderable');
ciAssert(file_put_contents(__DIR__ . '/identity.json', json_encode($fixture, JSON_THROW_ON_ERROR)) !== false, 'Gallery fixture state write failed');
chmod(__DIR__ . '/identity.json', 0600);
echo "PASS parsed private product with reviewed original CI image pair\n";
