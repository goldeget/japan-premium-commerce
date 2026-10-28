<?php

declare(strict_types=1);
require __DIR__ . '/ci_bootstrap.php';

// Assert the fresh native bootstrap repaired only its known Korean fallbacks.
// Do not repair here: a missing install/upgrade path must fail acceptance.
$koreanLanguage = (int) Language::getIdByIso('ko', true);
ciAssert($koreanLanguage > 0, 'Fresh native Korean language missing');
foreach ([
    'AdminPsdistributionapiclientCommunity' => '커뮤니티',
    'AdminPsdistributionapiclient' => '명예의 전당',
    'AdminSecurity' => '보안',
    'AdminParentSecurity' => '보안',
    'AdminExtraPropertyDefinitions' => '추가 속성',
] as $tabClass => $expectedName) {
    $actualName = Db::getInstance()->getValue('SELECT tl.name FROM `' . _DB_PREFIX_ . 'tab` t'
        . ' INNER JOIN `' . _DB_PREFIX_ . 'tab_lang` tl ON tl.id_tab=t.id_tab'
        . ' WHERE t.class_name=\'' . pSQL($tabClass) . '\' AND tl.id_lang=' . $koreanLanguage, false);
    ciAssert($actualName === $expectedName, 'Fresh native Korean tab metadata bootstrap incomplete');
}

$module = Module::getInstanceByName('ordenowaprocurement');
ciAssert($module instanceof Module, 'Module missing');
if (!Module::isInstalled('ordenowaprocurement')) {
    ciAssert($module->install(), 'Module install failed');
}
ciAssert(Module::isEnabled('ordenowaprocurement'), 'Module disabled');
ciAssert($module->ensureInfrastructure(), 'Module infrastructure unavailable');
$context->employee = new Employee(1);
$context->country = new Country((int) Country::getByIso('JP'));
$context->cart = new Cart();
ciAssert(Validate::isLoadedObject($context->employee), 'Native employee missing');
ciAssert((int) Db::getInstance()->getValue('SELECT COUNT(*) FROM `' . _DB_PREFIX_ . 'group` WHERE price_display_method<>0') === 0, 'Fixture requires tax inclusive groups');
$runLabel = $run . '-' . $attempt;
$password = bin2hex(random_bytes(24));
$customers = [];
foreach (['a', 'b'] as $side) {
    $email = 'procurement-' . $runLabel . '-' . $side . '@example.invalid';
    ciAssert(!Customer::customerExists($email), 'Fixture identity must be fresh');
    $customer = new Customer();
    $customer->id_shop = 1;
    $customer->id_shop_group = 1;
    $customer->id_default_group = (int) Configuration::get('PS_CUSTOMER_GROUP');
    $customer->id_lang = (int) Language::getIdByIso('ja', true);
    $customer->firstname = 'Synthetic';
    $customer->lastname = strtoupper($side);
    $customer->email = $email;
    $customer->passwd = (new PrestaShop\PrestaShop\Core\Crypto\Hashing())->hash($password);
    $customer->active = true;
    $customer->is_guest = false;
    $customer->secure_key = md5(random_bytes(32));
    ciAssert($customer->add(), 'Native customer create failed');
    $customer->updateGroup([(int) Configuration::get('PS_CUSTOMER_GROUP')]);
    $customers[$side] = ['id' => (int) $customer->id, 'email' => $email];
}
// This helper must actually parse, review, and register the synthetic source.
// It returns only IDs; imported products remain inactive and non-orderable.
require_once '/var/www/html/modules/kuraneacatalog/autoload.php';
$helper = '/tmp/ordenowa-procurement-ci/catalog/prepare_ci_procurement_product.php';
ciAssert(is_file($helper), 'Reviewed parser/native helper missing');
require $helper;
$parsed = prepareCiProcurementProduct();
$productId = $parsed['product_id'] ?? 0;
ciAssert(is_int($productId) && $productId > 0, 'Reviewed parsed product missing');
$attributeId = (int) ($parsed['product_attribute_id'] ?? 0);
$reference = Ordenowa\Procurement\Integration\Runtime::productReference($productId, $attributeId);
ciAssert((int) ($reference['id_product'] ?? 0) === $productId && (int) ($reference['id_product_attribute'] ?? 0) === $attributeId, 'Native reference mismatch');
ciAssert((string) ($reference['source_url'] ?? '') !== '', 'Reviewed source provenance missing');
$product = new Product($productId, false, null, 1);
ciAssert(!(bool) $product->active && !(bool) $product->available_for_order && $product->visibility === 'none', 'Product sale flags changed');
// A native READ-only employee proves ACL enforcement with a valid own-session
// CSRF token; superadmin-only browser coverage would miss role-name errors.
$profile = new Profile();
$profile->name = [];
foreach (Language::getLanguages(false) as $language) {
    $profile->name[(int) $language['id_lang']] = '합성 CI 조회 전용';
}
ciAssert($profile->add(), 'Native read profile create failed');
foreach (['AdminOrdenowaProcurement', 'AdminOrdenowaProcurementReviews', 'AdminOrdenowaProcurementPoints', 'AdminOrdenowaProcurementAudit', 'AdminOrdenowaProcurementPolicies'] as $tabName) {
    $tab = (int) Tab::getIdFromClassName($tabName);
    ciAssert($tab > 0, 'Native procurement tab missing');
    foreach (['view' => true, 'add' => false, 'edit' => false, 'delete' => false] as $action => $allow) {
        ciAssert((new Access())->updateLgcAccess((int) $profile->id, $tab, $action, $allow, false) === 'ok', 'Native profile permission write failed');
    }
}
Profile::resetCacheAccesses();
$reader = new Employee();
$reader->firstname = 'Synthetic';
$reader->lastname = 'Reader';
$reader->email = 'procurement-reader-' . $runLabel . '@example.invalid';
$reader->passwd = (new PrestaShop\PrestaShop\Core\Crypto\Hashing())->hash($password);
$reader->id_lang = (int) Language::getIdByIso('ko', true);
$reader->active = true;
$reader->id_profile = (int) $profile->id;
$reader->default_tab = (int) Tab::getIdFromClassName('AdminOrdenowaProcurementReviews');
$reader->bo_color = (string) ($context->employee->bo_color ?: '#6f42c1');
$reader->bo_theme = (string) ($context->employee->bo_theme ?: 'default');
$reader->bo_css = (string) ($context->employee->bo_css ?: 'theme.css');
$reader->bo_width = max(0, (int) $context->employee->bo_width);
$reader->bo_menu = (bool) $context->employee->bo_menu;
ciAssert($reader->add(), 'Native read employee create failed');
$identity = ['languages' => ['ja' => (int) Language::getIdByIso('ja', true), 'en' => (int) Language::getIdByIso('en', true), 'ko' => (int) Language::getIdByIso('ko', true)], 'run' => $runLabel, 'customers' => $customers, 'password' => $password,
    'reader' => ['id' => (int) $reader->id, 'email' => $reader->email],
    'product_id' => $productId, 'product_attribute_id' => $attributeId, 'employee_id' => 1];
$identity['mail_subject_prefix'] = '[' . strip_tags((string) Configuration::get('PS_SHOP_NAME')) . '] ';
$identity['routes'] = [];
foreach ($identity['languages'] as $locale => $languageId) {
    foreach (['workspace', 'policy', 'support'] as $controller) {
        $identity['routes'][$locale][$controller] = $context->link->getModuleLink('ordenowaprocurement', $controller, [], null, $languageId, 1);
    }
}
$path = __DIR__ . '/identity.json';
ciAssert(file_put_contents($path, json_encode($identity, JSON_THROW_ON_ERROR)) !== false, 'Private identity write failed');
chmod($path, 0600);
echo "PASS native module install, fresh synthetic identities, parsed private product reference\n";
