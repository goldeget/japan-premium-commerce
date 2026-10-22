<?php

declare(strict_types=1);

use PrestaShop\PrestaShop\Core\CommandBus\CommandBusInterface;
use PrestaShop\PrestaShop\Core\Domain\Order\Query\GetOrderForViewing;
use Kuranea\Postcode\Infrastructure\DatabasePostalAddressLookup;

$runId = trim((string) getenv('KURANEA_CI_RUN_ID'));
$runAttempt = trim((string) getenv('KURANEA_CI_RUN_ATTEMPT'));
$projectName = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$expectedProjectName = 'kuranea-ci-' . $runId . '-' . $runAttempt;

if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $runAttempt) !== 1
    || $projectName !== $expectedProjectName) {
    fwrite(STDERR, "BLOCKED: this native order test only runs in its matching isolated GitHub Actions Compose project.\n");
    exit(77);
}

$stage = 'PrestaShop bootstrap';
set_exception_handler(static function (Throwable $exception) use (&$stage): void {
    $message = preg_replace('/[\r\n]+/', ' ', $exception->getMessage()) ?? 'Unknown error';
    $diagnostic = sprintf(
        'KURANEA_NATIVE_ORDER_STAGE=%s; exception=%s; message=%s',
        $stage,
        get_class($exception),
        substr($message, 0, 1000)
    );
    fwrite(STDERR, $diagnostic . PHP_EOL);

    if (getenv('GITHUB_ACTIONS') === 'true') {
        $annotation = str_replace(['%', "\r", "\n"], ['%25', '%0D', '%0A'], $diagnostic);
        fwrite(STDOUT, '::error title=KURANEA native order::' . $annotation . PHP_EOL);
    }

    exit(1);
});

$shopRoot = '/var/www/html';
if (!is_file($shopRoot . '/config/config.inc.php')
    || !is_file($shopRoot . '/modules/kuraneapostcode/autoload.php')
    || !is_file($shopRoot . '/app/AdminKernel.php')) {
    throw new RuntimeException('The installed PrestaShop files required by the isolated order test are missing.');
}

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SERVER_PORT'] = (string) (parse_url('http://' . $_SERVER['HTTP_HOST'], PHP_URL_PORT) ?: 80);

$stage = 'PrestaShop bootstrap';
require_once $shopRoot . '/config/config.inc.php';
require_once $shopRoot . '/modules/kuraneapostcode/autoload.php';
require_once $shopRoot . '/app/AdminKernel.php';

global $kernel;
$stage = 'Back Office kernel boot';
$kernel = new AdminKernel(_PS_ENV_, _PS_MODE_DEV_);
$kernel->boot();

$stage = 'Japanese shop context';
$shopId = 1;
$shop = new Shop($shopId);
$japaneseLanguageId = (int) Language::getIdByIso('ja', true);
$japanCountryId = (int) Country::getByIso('JP');
$jpyCurrencyId = (int) Currency::getIdByIsoCode('JPY', $shopId);
$homeCategoryId = (int) Configuration::get('PS_HOME_CATEGORY');

if (!Validate::isLoadedObject($shop)
    || $japaneseLanguageId < 1
    || $japanCountryId < 1
    || $jpyCurrencyId < 1
    || $homeCategoryId < 1) {
    throw new RuntimeException('The isolated shop is missing its Japanese language, Japan, JPY currency, or home category.');
}

$context = Context::getContext();
$context->shop = $shop;
Shop::setContext(Shop::CONTEXT_SHOP, $shopId);
$context->language = new Language($japaneseLanguageId);
$context->country = new Country($japanCountryId, $japaneseLanguageId);
$context->currency = new Currency($jpyCurrencyId, null, $shopId);
$context->employee = new Employee(1);
$context->cart = new Cart();
$kernel->getContainer()
    ->get(PrestaShop\PrestaShop\Core\Context\ContextBuilderPreparer::class)
    ->prepareFromLegacyContext($context);

$stage = 'offline payment module';
$paymentModuleName = 'ps_checkpayment';
$paymentModule = Module::getInstanceByName($paymentModuleName);
if (!$paymentModule) {
    throw new RuntimeException('BLOCKED: the official ps_checkpayment source is not present in this PrestaShop image.');
}
if (!Module::isInstalled($paymentModuleName) && !$paymentModule->install()) {
    throw new RuntimeException('Could not install the official offline ps_checkpayment module in the isolated CI database.');
}
if (!(bool) $paymentModule->active && !$paymentModule->enable()) {
    throw new RuntimeException('Could not enable the official offline ps_checkpayment module in the isolated CI database.');
}
$paymentModule = Module::getInstanceByName($paymentModuleName);
$pendingStateId = (int) Configuration::get('PS_OS_CHEQUE');
$pendingState = $pendingStateId > 0 ? new OrderState($pendingStateId, $japaneseLanguageId) : false;

if (!($paymentModule instanceof PaymentModule) || !(bool) $paymentModule->active) {
    throw new RuntimeException('The isolated official offline ps_checkpayment module is not active.');
}
if (!($pendingState instanceof OrderState)
    || !Validate::isLoadedObject($pendingState)
    || (bool) $pendingState->paid
    || (bool) $pendingState->logable) {
    throw new RuntimeException('The official cheque order state is not a valid unpaid, non-logable state.');
}

$japan = new Country($japanCountryId, $japaneseLanguageId);

$homeCategory = new Category($homeCategoryId, $japaneseLanguageId);
if (!Validate::isLoadedObject($homeCategory) || !(bool) $homeCategory->active) {
    throw new RuntimeException('The configured home category is not available for a disposable QA product.');
}

$stage = 'official postcode candidate';
$stateIds = [];
$states = State::getStatesByIdCountry($japanCountryId, true, 'iso_code', 'asc');
foreach (is_array($states) ? $states : [] as $state) {
    $isoCode = (string) $state['iso_code'];
    if (preg_match('/\AJP-([0-9]{2})\z/D', $isoCode, $matches) === 1) {
        $stateIds[$matches[1]] = (int) $state['id_state'];
    }
}

$officialCandidates = (new DatabasePostalAddressLookup())->lookupByPostcode('1000004', 100);
$officialCandidate = null;
foreach ($officialCandidates as $candidate) {
    if ($candidate->prefecture === '東京都'
        && $candidate->municipality === '千代田区'
        && str_contains($candidate->town, '大手町')) {
        $officialCandidate = $candidate;
        break;
    }
}

if ($officialCandidate === null) {
    throw new RuntimeException('The official Japan Post 1000004 Tokyo/Chiyoda/Otemachi candidate was not imported.');
}

$nativeAddress = $officialCandidate->toNativeAddressFields($stateIds);
if ($nativeAddress === null || (int) $nativeAddress['id_state'] < 1) {
    throw new RuntimeException('The official Tokyo candidate cannot be mapped to an active native PrestaShop prefecture.');
}

$oldMailMethod = Configuration::get('PS_MAIL_METHOD');
if (!Configuration::updateValue('PS_MAIL_METHOD', Mail::METHOD_DISABLE)) {
    throw new RuntimeException('Could not disable PrestaShop mail delivery in the isolated test shop.');
}

$stage = 'customer and address persistence';
try {
    $customer = new Customer();
    $customer->firstname = 'KURANEA';
    $customer->lastname = 'CI専用';
    $customer->email = 'kuranea-order-postcode-' . bin2hex(random_bytes(6)) . '@example.invalid';
    $customer->passwd = Tools::hash(bin2hex(random_bytes(24)));
    $customer->id_lang = $japaneseLanguageId;
    $customer->id_default_group = (int) Configuration::get('PS_CUSTOMER_GROUP');
    $customer->id_shop = $shopId;
    $customer->secure_key = md5(bin2hex(random_bytes(16)));
    if (!$customer->add()) {
        throw new RuntimeException('Could not create the CI-only native PrestaShop customer.');
    }

    $houseNumber = '1-2-3';
    $building = 'KURANEA CI専用テストビル 101';
    $address = new Address();
    $address->id_customer = (int) $customer->id;
    $address->id_country = $japanCountryId;
    $address->id_state = (int) $nativeAddress['id_state'];
    $address->alias = 'CI専用 日本郵便住所 QA';
    $address->firstname = $customer->firstname;
    $address->lastname = $customer->lastname;
    $address->address1 = trim((string) $nativeAddress['address1']) . ' ' . $houseNumber;
    $address->address2 = $building;
    $address->postcode = (string) $nativeAddress['postcode'];
    $address->city = (string) $nativeAddress['city'];
    $address->phone = '0312345678';
    if (!$address->add()) {
        throw new RuntimeException('Could not save the CI-only native Japan Post address.');
    }

    $savedAddress = new Address((int) $address->id);
    if (!Validate::isLoadedObject($savedAddress)
        || $savedAddress->postcode !== '100-0004'
        || (int) $savedAddress->id_state !== (int) $nativeAddress['id_state']
        || $savedAddress->city !== '千代田区'
        || !str_contains((string) $savedAddress->address1, '大手町')
        || !str_contains((string) $savedAddress->address1, $houseNumber)
        || $savedAddress->address2 !== $building) {
        throw new RuntimeException('The selected or manually edited Japanese address fields did not persist in the native Address record.');
    }

    $stage = 'CI-only product creation';
    $suffix = strtoupper(bin2hex(random_bytes(4)));
    $productName = '[CI ONLY] KURANEA postcode order ' . $suffix;
    $product = new Product();
    $product->id_shop_default = $shopId;
    $product->id_category_default = $homeCategoryId;
    $product->id_tax_rules_group = 0;
    $product->reference = 'KURANEA-CI-' . $suffix;
    $product->price = 1.0;
    $product->weight = 0.1;
    $product->minimal_quantity = 1;
    $product->active = 1;
    $product->available_for_order = 1;
    $product->show_price = 1;
    $product->visibility = 'both';
    $product->condition = 'new';
    $product->name = [];
    $product->link_rewrite = [];
    $product->description_short = [];
    foreach (Language::getLanguages(false) as $language) {
        $languageId = (int) $language['id_lang'];
        $product->name[$languageId] = $productName;
        $product->link_rewrite[$languageId] = 'kuranea-ci-postcode-order-' . strtolower($suffix);
        $product->description_short[$languageId] = 'CI only. No real payment or capture.';
    }
    if (!$product->add()) {
        throw new RuntimeException('Could not create the clearly marked CI-only order product.');
    }
    if (!$product->addToCategories([$homeCategoryId])) {
        throw new RuntimeException('Could not associate the CI-only product with the native home category.');
    }
    StockAvailable::setQuantity((int) $product->id, 0, 10, $shopId);
    if ((int) StockAvailable::getQuantityAvailableByProduct((int) $product->id, 0, $shopId) < 1) {
        throw new RuntimeException('Could not add stock to the CI-only product.');
    }

    $stage = 'CI-only carrier setup';
    $carrier = new Carrier();
    $carrier->name = 'KURANEA CI ONLY - Japan free test carrier';
    $carrier->active = 1;
    $carrier->is_free = 1;
    $carrier->shipping_handling = 0;
    $carrier->shipping_external = 0;
    $carrier->range_behavior = 0;
    $carrier->shipping_method = Carrier::SHIPPING_METHOD_FREE;
    $carrier->max_weight = 1000;
    $carrier->need_range = 0;
    $carrier->is_module = 0;
    $carrier->delay = [];
    foreach (Language::getLanguages(false) as $language) {
        $carrier->delay[(int) $language['id_lang']] = 'CI only; no physical dispatch';
    }
    if (!$carrier->add() || !$carrier->addZone((int) $japan->id_zone)) {
        throw new RuntimeException('Could not create a free CI-only carrier for the Japan zone.');
    }
    $customerGroups = array_map('intval', $customer->getGroups());
    if (!in_array((int) $customer->id_default_group, $customerGroups, true)) {
        $customerGroups[] = (int) $customer->id_default_group;
    }
    if ($customerGroups === [] || !$carrier->setGroups($customerGroups)) {
        throw new RuntimeException('Could not associate the CI-only Japan carrier with the test customer groups.');
    }

    $stage = 'native cart and quantity';
    $cart = new Cart();
    $cart->id_customer = (int) $customer->id;
    $cart->id_address_delivery = (int) $address->id;
    $cart->id_address_invoice = (int) $address->id;
    $cart->id_currency = $jpyCurrencyId;
    $cart->id_lang = $japaneseLanguageId;
    $cart->id_shop = $shopId;
    $cart->id_shop_group = (int) $shop->id_shop_group;
    $cart->secure_key = (string) $customer->secure_key;
    if (!$cart->add()) {
        throw new RuntimeException('Could not create the native CI-only PrestaShop cart.');
    }

    $context->cart = $cart;
    $context->customer = $customer;
    $quantityAdded = $cart->updateQty(1, (int) $product->id, 0, false, 'up', (int) $address->id, $shop);
    if (!$quantityAdded) {
        throw new RuntimeException('Could not add the CI-only product to the native cart.');
    }

    $stage = 'delivery option';
    $deliveryOptions = $cart->getDeliveryOptionList($japan, true);
    $addressOptions = $deliveryOptions[(int) $address->id] ?? [];
    if (!is_array($addressOptions) || $addressOptions === []) {
        throw new RuntimeException('No existing delivery option is available for the saved Japanese address.');
    }
    $selectedDeliveryOption = (string) array_key_first($addressOptions);
    $cart->setDeliveryOption([(int) $address->id => $selectedDeliveryOption]);
    if (!$cart->update() || (int) $cart->id_carrier < 1) {
        throw new RuntimeException('The native Japanese delivery option did not persist on the test cart.');
    }

    $orderTotal = (float) $cart->getOrderTotal(true, Cart::BOTH);
    if ($orderTotal <= 0) {
        throw new RuntimeException('The CI-only cart total is invalid.');
    }

    $stage = 'unpaid native order';
    $paymentModule->validateOrder(
        (int) $cart->id,
        $pendingStateId,
        $orderTotal,
        'KURANEA CI ONLY - offline check payment, no capture',
        'CI ONLY: native order persistence check for Japan Post postcode 1000004.',
        [],
        $jpyCurrencyId,
        false,
        (string) $customer->secure_key,
        $shop
    );

    $orderId = (int) $paymentModule->currentOrder;
    $order = $orderId > 0 ? new Order($orderId) : false;
    if (!($order instanceof Order)
        || !Validate::isLoadedObject($order)
        || (int) $order->id_cart !== (int) $cart->id
        || (int) $order->id_address_delivery !== (int) $address->id
        || (int) $order->id_customer !== (int) $customer->id
        || (float) $order->total_paid_real !== 0.0) {
        throw new RuntimeException('The native order did not persist the delivery address or remained unexpectedly paid.');
    }

    $savedOrderAddress = new Address((int) $order->id_address_delivery);
    if (!Validate::isLoadedObject($savedOrderAddress)
        || $savedOrderAddress->postcode !== '100-0004'
        || $savedOrderAddress->address2 !== $building
        || !str_contains((string) $savedOrderAddress->address1, $houseNumber)) {
        throw new RuntimeException('The order delivery address no longer resolves to the selected and edited native address.');
    }

    $savedOrderState = new OrderState((int) $order->current_state, $japaneseLanguageId);
    if (!Validate::isLoadedObject($savedOrderState) || (bool) $savedOrderState->paid) {
        throw new RuntimeException('The CI-only order did not remain in an unpaid state.');
    }

    $stage = 'Back Office shipping address projection';
    $orderForViewing = $kernel->getContainer()
        ->get(CommandBusInterface::class)
        ->handle(new GetOrderForViewing($orderId));
    if (!is_object($orderForViewing) || !method_exists($orderForViewing, 'getShippingAddressFormatted')) {
        throw new RuntimeException('PrestaShop could not load the native Back Office order-view address projection.');
    }

    $adminShippingAddress = html_entity_decode(
        strip_tags((string) $orderForViewing->getShippingAddressFormatted()),
        ENT_QUOTES | ENT_HTML5,
        'UTF-8'
    );
    $state = new State((int) $savedOrderAddress->id_state, $japaneseLanguageId);
    $stateNames = $state->name;
    $stateName = is_array($stateNames)
        ? (string) ($stateNames[$japaneseLanguageId] ?? current($stateNames))
        : (string) $stateNames;
    $formattedFields = [
        'postcode' => '100-0004',
        'prefecture' => $stateName !== '' ? $stateName : '東京都',
        'municipality' => '千代田区',
        'official town' => '大手町',
        'edited house number' => $houseNumber,
        'edited building' => $building,
    ];
    foreach ($formattedFields as $fieldName => $fieldValue) {
        if ($fieldValue === '' || !str_contains($adminShippingAddress, $fieldValue)) {
            throw new RuntimeException(sprintf(
                'The Back Office shipping-address formatter omitted %s (%s). Formatted value: %s',
                $fieldName,
                $fieldValue,
                $adminShippingAddress
            ));
        }
    }

    printf(
        "PASS: official Japan Post 1000004 address persisted into unpaid CI-only order id=%d reference=%s delivery_address_id=%d\n",
        $orderId,
        (string) $order->reference,
        (int) $order->id_address_delivery
    );
    printf("PASS: native Back Office shipping-address projection contains postcode, prefecture, municipality, town, house number, and building.\n");
    printf("ADMIN SHIPPING ADDRESS:\n%s\n", $adminShippingAddress);
} finally {
    if (!Configuration::updateValue('PS_MAIL_METHOD', $oldMailMethod)) {
        fwrite(STDERR, "WARNING: mail configuration could not be restored in the disposable CI database.\n");
    }
}
