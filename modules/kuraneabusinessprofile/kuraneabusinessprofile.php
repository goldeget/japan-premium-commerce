<?php

declare(strict_types=1);

if (!defined('_PS_VERSION_')) {
    exit;
}

require_once __DIR__ . '/autoload.php';

use Kuranea\BusinessProfile\Domain\ProfileDefaults;
use Kuranea\BusinessProfile\Customer\PublishedProfileProvider;
use Kuranea\BusinessProfile\Customer\PublicFooterBuilder;
use Kuranea\BusinessProfile\Customer\StructuredDataBrandEnricher;
use Kuranea\BusinessProfile\Customer\CommerceGate;
use Kuranea\BusinessProfile\Customer\PublishedLegalPageBuilder;
use Kuranea\BusinessProfile\Customer\OrderConfirmationMailContent;
use Kuranea\BusinessProfile\Customer\BankTransferInstructionPresenter;
use Kuranea\BusinessProfile\Infrastructure\VersionedProfileRepository;
use Kuranea\BusinessProfile\Infrastructure\BankTransferInstructionRepository;

class Kuraneabusinessprofile extends Module
{
    private ?int $activeMailShopId = null;

    public function __construct()
    {
        $this->name = 'kuraneabusinessprofile';
        $this->tab = 'administration';
        $this->version = '1.0.5';
        $this->author = 'ORDENOWA';
        $this->need_instance = 0;
        $this->bootstrap = true;
        $this->ps_versions_compliancy = ['min' => '9.2.0', 'max' => '9.99.99'];

        parent::__construct();

        $this->displayName = '쇼핑몰 운영 설정';
        $this->description = 'ORDENOWA 브랜드, 회사 참고정보 및 판매사업 운영 설정을 관리합니다.';
    }

    public function install(): bool
    {
        if (!parent::install()) {
            return false;
        }

        $repository = new VersionedProfileRepository();
        if (!$repository->install() || !$this->ensureInitialDraft($repository) || !$this->installTabs()) {
            return false;
        }
        if (!$this->configureOfficialMailLogo(ProfileDefaults::initial(), $this->shopId())) {
            return false;
        }

        return $this->registerHook([
            'actionAdminControllerSetMedia',
            'displayHeader',
            'displayFooter',
            'actionFrontControllerInitBefore',
            'actionFrontControllerSetVariables',
            'actionGetExtraMailTemplateVars',
            'actionEmailSendBefore',
            'actionEmailAddAfterContent',
            'displayOrderConfirmation',
            'displayOrderDetail',
        ]);
    }

    public function uninstall(): bool
    {
        $this->removeTab('AdminBusinessProfileBanks');
        $this->removeTab('AdminBusinessProfile');
        $this->removeTab('AdminBusinessProfileTransfers');

        // Keep profile versions and account data when disabling or uninstalling the module.
        return parent::uninstall();
    }

    public function getContent(): string
    {
        $adminUrl = $this->context->link->getAdminLink('AdminBusinessProfile');

        return '<div class="panel"><h3>쇼핑몰 운영 설정</h3><p>브랜드·사업자·운영 정보를 한국어로 관리합니다.</p>'
            . '<a class="btn btn-primary" href="' . htmlspecialchars((string) $adminUrl, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8') . '">설정 열기</a></div>';
    }

    public function hookActionAdminControllerSetMedia(): void
    {
        $controller = $this->context->controller ?? null;
        if (is_object($controller) && method_exists($controller, 'addCSS')) {
            $controller->addCSS($this->_path . 'views/css/admin.css');
        }
    }

    public function hookDisplayHeader(): string
    {
        $profile = $this->publicProfile();
        $published = $profile !== null;
        if ($profile === null) {
            $profile = ProfileDefaults::initial();
            $profile['_resolved_locale'] = PublishedProfileProvider::localeForIso(
                (string) ($this->context->language->iso_code ?? 'ja')
            );
        }

        $locale = (string) $profile['_resolved_locale'];
        $assets = (array) ($profile['brand']['assets'] ?? []);
        $baseUrl = (string) $this->context->link->getBaseLink();
        $this->context->smarty->assign([
            'ordenowaBrandName' => (string) ($profile['brand']['name'][$locale] ?? $profile['brand']['name']['ja-JP'] ?? 'ORDENOWA'),
            'ordenowaBrandDescription' => (string) ($profile['brand']['description'][$locale] ?? ''),
            'ordenowaBrandSlogan' => (string) ($profile['brand']['slogan'][$locale] ?? ''),
            'ordenowaLogoDesktop' => $this->assetUrl($assets['header_desktop'] ?? null, $baseUrl),
            'ordenowaLogoMobile' => $this->assetUrl($assets['header_mobile'] ?? null, $baseUrl),
            'ordenowaSeoTitle' => (string) ($profile['seo']['title'][$locale] ?? $profile['brand']['name'][$locale] ?? 'ORDENOWA'),
            'ordenowaSeoDescription' => (string) ($profile['seo']['description'][$locale] ?? $profile['brand']['description'][$locale] ?? ''),
            'ordenowaBrandPublished' => $published,
            'ordenowaAppleTouchIcon' => $this->assetUrl($assets['apple_touch'] ?? null, $baseUrl),
        ]);

        $manifestUrl = (string) $this->context->link->getModuleLink($this->name, 'manifest');
        $themeColor = preg_match('/\\A#[0-9A-Fa-f]{6}\\z/D', (string) ($profile['pwa']['theme_color'] ?? ''))
            ? (string) $profile['pwa']['theme_color']
            : '#10243a';

        $icons = '';
        foreach ([
            ['favicon', 'image/x-icon', ''],
            ['favicon_16', 'image/png', '16x16'],
            ['favicon_32', 'image/png', '32x32'],
            ['apple_touch', 'image/png', '180x180'],
        ] as [$assetName, $mime, $sizes]) {
            $url = $this->assetUrl($assets[$assetName] ?? null, $baseUrl);
            if ($url !== '') {
                $icons .= '<link rel="icon" type="' . $mime . '"'
                    . ($sizes === '' ? '' : ' sizes="' . $sizes . '"')
                    . ' href="' . $this->escape($url) . '">';
            }
        }

        $ogImage = $this->assetUrl($assets['og_image'] ?? null, $baseUrl);
        $controller = $this->context->controller ?? null;
        $isProductPage = is_object($controller) && ($controller->php_self ?? '') === 'product';
        $openGraph = '';
        if ($ogImage !== '' && !$isProductPage) {
            $openGraph = '<meta property="og:image" content="' . $this->escape($ogImage) . '">';
        }
        $appleTouch = $this->assetUrl($assets['apple_touch'] ?? null, $baseUrl);
        if ($appleTouch !== '') {
            $icons .= '<link rel="apple-touch-icon" sizes="180x180" href="' . $this->escape($appleTouch) . '">';
        }

        return $icons . '<link rel="manifest" href="' . $this->escape($manifestUrl) . '">'
            . '<meta name="application-name" content="' . $this->escape((string) ($profile['pwa']['name'][$locale] ?? 'ORDENOWA')) . '">'
            . '<meta name="theme-color" content="' . $this->escape($themeColor) . '">'
            . $openGraph;
    }

    public function hookDisplayFooter(): string
    {
        $profile = $this->publicProfile();
        if ($profile === null) {
            return '';
        }

        return PublicFooterBuilder::build(
            $profile,
            CommerceGate::isEnabled($profile, $this->externalAuthorizationConfirmed())
        ) . PublishedLegalPageBuilder::footerLink(
            $profile,
            (string) $this->context->link->getModuleLink($this->name, 'legal')
        );
    }

    /** Show instructions only for the owning customer's confirmed, order-bound record. */
    public function hookDisplayOrderConfirmation(array $params): string
    {
        return $this->renderIssuedTransferInstructions($params);
    }

    /** Show the same issue-time instruction binding in the owning customer's order history. */
    public function hookDisplayOrderDetail(array $params): string
    {
        return $this->renderIssuedTransferInstructions($params);
    }

    /** @param array<string, mixed> $params
     *  @return array<string, never>
     */
    public function hookActionFrontControllerSetVariables(array $params): array
    {
        if (!isset($params['templateVars']) || !is_array($params['templateVars'])) {
            return [];
        }

        $structuredData = $params['templateVars']['structured_data'] ?? null;
        if (!is_array($structuredData)) {
            return [];
        }

        $profile = $this->publicProfile();
        if ($profile === null) {
            $profile = ProfileDefaults::initial();
            $profile['_resolved_locale'] = PublishedProfileProvider::localeForIso(
                (string) ($this->context->language->iso_code ?? 'ja')
            );
        }

        $locale = (string) ($profile['_resolved_locale'] ?? 'ja-JP');
        $brandName = (string) ($profile['brand']['name'][$locale] ?? $profile['brand']['name']['ja-JP'] ?? 'ORDENOWA');
        $brandLogoUrl = $this->assetUrl(
            $profile['brand']['assets']['header_desktop'] ?? null,
            (string) $this->context->link->getBaseLink()
        );
        $params['templateVars']['structured_data'] = StructuredDataBrandEnricher::apply($structuredData, $brandName, $brandLogoUrl);

        return [];
    }

    public function hookActionFrontControllerInitBefore(array $params = []): void
    {
        $controller = $params['controller'] ?? $this->context->controller;
        $controllerName = (string) ($controller->php_self ?? '');
        if (
            $controllerName === ''
            && is_object($controller)
            && is_a($controller, 'GetFileControllerCore')
        ) {
            $controllerName = 'getfile';
        }

        $isLogoutAction = $controllerName === 'index' && array_key_exists('mylogout', $_GET);
        if (in_array($controllerName, [
            'address',
            'addresses',
            'authentication',
            'cart',
            'contact',
            'discount',
            'getfile',
            'guest-tracking',
            'history',
            'identity',
            'my-account',
            'order',
            'order-confirmation',
            'order-detail',
            'order-follow',
            'order-opc',
            'order-return',
            'order-slip',
            'password',
            'pdf-invoice',
            'pdf-order-return',
            'pdf-order-slip',
            'registration',
        ], true) || $isLogoutAction) {
            // Apply this before controller authorization redirects as well as successful responses.
            header('Cache-Control: private, no-store, max-age=0', true);
            header('Pragma: no-cache', true);
            header('Expires: 0', true);
        }

        $isCustomerRegistrationRequest = $controllerName === 'registration'
            || ($controllerName === 'authentication' && \Tools::isSubmit('submitCreate'));
        if ($isCustomerRegistrationRequest && !CommerceGate::isRegistrationEnabled(
            $this->publicProfile(),
            $this->externalAuthorizationConfirmed()
        )) {
            \Tools::redirect($this->context->link->getPageLink('index'));
        }

        if (!in_array($controllerName, ['order', 'order-opc'], true)) {
            return;
        }

        $profile = $this->publicProfile();
        if (CommerceGate::isEnabled($profile, $this->externalAuthorizationConfirmed())
            || CommerceGate::isIsolatedCiCheckoutEnabled()
        ) {
            return;
        }

        \Tools::redirect($this->context->link->getPageLink('index'));
    }

    /** @param array<string, mixed> $params */
    public function hookActionGetExtraMailTemplateVars(array $params): void
    {
        $mailContextShopId = $this->activeMailShopId;

        try {
            if (!isset($params['extra_template_vars']) || !is_array($params['extra_template_vars'])) {
                return;
            }

            // Generic templates must never inherit account details from another hook or environment.
            $params['extra_template_vars']['{ordenowa_bank_accounts}'] = '';

            [$shopId, $isoCode] = $this->mailShopAndIsoCode($params, $mailContextShopId);
            $profile = (new PublishedProfileProvider(new VersionedProfileRepository()))->forShop($shopId, $isoCode);
            $safeDefaults = $profile ?? ProfileDefaults::initial();
            $locale = $profile['_resolved_locale'] ?? PublishedProfileProvider::localeForIso($isoCode);
            $brandName = (string) ($safeDefaults['brand']['name'][$locale] ?? $safeDefaults['brand']['name']['ja-JP'] ?? 'ORDENOWA');

            $emailLogo = $safeDefaults['brand']['assets']['email_logo'] ?? '';
            $emailLogoRelative = is_string($emailLogo)
                && preg_match('~\\Aimg/ordenowa/versions/[A-Fa-f0-9]{64}/(?:email-logo|official-email-logo)\\.png\\z~D', $emailLogo) === 1
                ? substr($emailLogo, 4)
                : '';
            $emailLogoIsCurrent = $emailLogoRelative !== ''
                && (string) \Configuration::get('PS_LOGO_MAIL', null, null, $shopId) === $emailLogoRelative
                && is_file(_PS_IMG_DIR_ . $emailLogoRelative);

            // Suppress any pre-existing KURANEA or PrestaShop default mail logo until an ORDENOWA asset is published.
            $params['extra_template_vars']['{shop_logo}'] = $emailLogoIsCurrent ? 'cid:shop_logo' : '';
            $params['extra_template_vars']['{shop_name}'] = $brandName;
            $params['extra_template_vars']['{ordenowa_brand_name}'] = $brandName;
            if (!CommerceGate::isEnabled($profile, $this->externalAuthorizationConfirmed())) {
                return;
            }

            $params['extra_template_vars']['{ordenowa_customer_support}'] = trim(implode(' · ', array_filter([
                (string) ($profile['customer_support']['phone'] ?? ''),
                (string) ($profile['customer_support']['email'] ?? ''),
            ])));
            $params['extra_template_vars']['{ordenowa_payment_policy}'] = (string) ($profile['payment'][$locale] ?? '');
            $params['extra_template_vars']['{ordenowa_shipping_policy}'] = (string) ($profile['shipping'][$locale] ?? '');
            $params['extra_template_vars']['{ordenowa_refund_policy}'] = (string) ($profile['refund'][$locale] ?? '');
            $params['extra_template_vars']['{ordenowa_seller_name}'] = (string) ($profile['seller']['legal_name'][$locale] ?? '');
            $params['extra_template_vars']['{ordenowa_seller_corporate_number}'] = (string) ($profile['seller']['corporate_number'] ?? '');
            $params['extra_template_vars']['{ordenowa_seller_address}'] = (string) ($profile['seller']['address'][$locale] ?? '');
            $params['extra_template_vars']['{ordenowa_seller_representative}'] = (string) ($profile['seller']['representative'][$locale] ?? '');
            $params['extra_template_vars']['{ordenowa_seller_responsible_person}'] = (string) ($profile['seller']['responsible_person'][$locale] ?? '');
        } finally {
            $this->activeMailShopId = null;
        }
    }

    /** @param array<string, mixed> $params */
    public function hookActionEmailAddAfterContent(array $params): void
    {
        $mailContextShopId = $this->activeMailShopId;

        if (($params['template'] ?? '') !== 'order_conf'
            || !isset($params['template_html'], $params['template_txt'])
            || !is_string($params['template_html'])
            || !is_string($params['template_txt'])) {
            return;
        }

        [$shopId, $isoCode] = $this->mailShopAndIsoCode($params, $mailContextShopId);
        $profile = (new PublishedProfileProvider(new VersionedProfileRepository()))->forShop($shopId, $isoCode);
        if ($profile === null) {
            return;
        }

        $templateHtml = $params['template_html'];
        $templateTxt = $params['template_txt'];
        OrderConfirmationMailContent::append(
            'order_conf',
            $templateHtml,
            $templateTxt,
            $profile,
            CommerceGate::isEnabled($profile, $this->externalAuthorizationConfirmed())
        );

        $params['template_html'] = $templateHtml;
        $params['template_txt'] = $templateTxt;
    }

    /** @param array<string, mixed> $params */
    public function hookActionEmailSendBefore(array $params): void
    {
        $shopId = (int) ($params['idShop'] ?? 0);
        $this->activeMailShopId = $shopId > 0 ? $shopId : null;
    }

    /** @return array<string, mixed>|null */
    public function publicProfile(): ?array
    {
        $shopId = (int) ($this->context->shop->id ?? 0);
        $isoCode = (string) ($this->context->language->iso_code ?? 'ja');

        return (new PublishedProfileProvider(new VersionedProfileRepository()))->forShop($shopId, $isoCode);
    }

    /** @param array<string, mixed> $params
     *  @return array{0: int, 1: string}
     */
    private function mailShopAndIsoCode(array $params, ?int $mailShopId = null): array
    {
        $language = new Language((int) ($params['id_lang'] ?? 0));
        $isoCode = (string) ($language->iso_code ?? $this->context->language->iso_code ?? 'ja');
        $shopId = (int) ($params['id_shop'] ?? 0);
        if ($shopId < 1) {
            $shopId = (int) ($mailShopId ?? $this->activeMailShopId ?? $this->context->shop->id ?? 0);
        }

        return [$shopId, $isoCode];
    }

    /** @param mixed $path */
    private function assetUrl(mixed $path, string $baseUrl): string
    {
        if (!is_string($path) || preg_match('~\\Aimg/ordenowa/versions/[A-Fa-f0-9]{64}/[A-Za-z0-9._-]+\\z~D', $path) !== 1) {
            return '';
        }

        return rtrim($baseUrl, '/') . '/' . $path;
    }

    private function publicText(string $label, mixed $content): string
    {
        if (!is_string($content) || trim($content) === '') {
            return '';
        }

        return '<section><h3>' . $this->escape($label) . '</h3><p>'
            . nl2br($this->escape($content), false) . '</p></section>';
    }

    private function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }

    private function externalAuthorizationConfirmed(): bool
    {
        return getenv('ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED') === '1';
    }

    private function ensureInitialDraft(VersionedProfileRepository $repository): bool
    {
        $shopId = $this->shopId();
        if ($repository->loadDraft($shopId) !== null) {
            return true;
        }

        $employeeId = (int) ($this->context->employee->id ?? 0);
        $version = $repository->insertVersion($shopId, ProfileDefaults::initial(), $employeeId, null);
        $repository->setDraftPointer($shopId, $version->id);

        return $version->id > 0;
    }

    /** Set the approved email logo on a new install; an admin publish keeps it synchronized later. */
    public function configureOfficialMailLogo(array $profile, int $shopId): bool
    {
        $emailLogo = $profile['brand']['assets']['email_logo'] ?? '';
        if (!is_string($emailLogo)
            || preg_match('~\Aimg/ordenowa/versions/[A-Fa-f0-9]{64}/(?:email-logo|official-email-logo)\.png\z~D', $emailLogo) !== 1
            || !is_file(_PS_ROOT_DIR_ . '/' . $emailLogo)
        ) {
            return false;
        }

        return (bool) \Configuration::updateValue('PS_LOGO_MAIL', substr($emailLogo, 4), false, null, max(1, $shopId));
    }

    private function installTabs(): bool
    {
        $parentId = (int) Tab::getIdFromClassName('ShopParameters');
        if ($parentId < 1) {
            $parentId = (int) Tab::getIdFromClassName('AdminParentShopParameters');
        }
        if ($parentId < 1) {
            $parentId = (int) Tab::getIdFromClassName('AdminParentPreferences');
        }
        if ($parentId < 1) {
            return false;
        }

        $generalTabId = $this->upsertTab('AdminBusinessProfile', '쇼핑몰 운영 설정', $parentId);
        if ($generalTabId < 1) {
            return false;
        }

        if ($this->upsertTab('AdminBusinessProfileBanks', '은행 계좌', $parentId) < 1) {
            return false;
        }

        return $this->installTransferInstructionsTab();
    }

    /** The issue screen lives under Orders and receives a separate add permission. */
    public function installTransferInstructionsTab(): bool
    {
        $ordersParentId = (int) Tab::getIdFromClassName('AdminParentOrders');
        if ($ordersParentId < 1) {
            return false;
        }

        return $this->upsertTab('AdminBusinessProfileTransfers', '주문 입금 안내', $ordersParentId) > 0;
    }

    private function upsertTab(string $className, string $label, int $parentId): int
    {
        $tabId = (int) Tab::getIdFromClassName($className);
        $tab = $tabId > 0 ? new Tab($tabId) : new Tab();
        $tab->active = 1;
        $tab->class_name = $className;
        $tab->module = $this->name;
        $tab->id_parent = $parentId;
        $tab->name = [];

        foreach (Language::getLanguages(false) as $language) {
            $tab->name[(int) $language['id_lang']] = $label;
        }

        $saved = $tabId > 0 ? $tab->update() : $tab->add();

        return $saved ? (int) $tab->id : 0;
    }

    private function removeTab(string $className): void
    {
        $tabId = (int) Tab::getIdFromClassName($className);
        if ($tabId > 0) {
            (new Tab($tabId))->delete();
        }
    }

    /** @param array<string, mixed> $params */
    private function renderIssuedTransferInstructions(array $params): string
    {
        $order = $params['order'] ?? null;
        if (!($order instanceof Order)) {
            $orderId = is_array($order)
                ? (int) ($order['id_order'] ?? $order['id'] ?? 0)
                : (int) (is_object($order) ? ($order->id_order ?? $order->id ?? 0) : 0);
            $order = $orderId > 0 ? new Order($orderId) : null;
        }
        if (!is_object($order)
            || !Validate::isLoadedObject($order)
            || (int) ($order->id_customer ?? 0) < 1
        ) {
            return '';
        }

        $customer = $this->context->customer ?? null;
        $shopId = (int) ($this->context->shop->id ?? 0);
        if (!is_object($customer)
            || (int) ($customer->id ?? 0) !== (int) $order->id_customer
            || (int) ($order->id_shop ?? 0) !== $shopId
        ) {
            return '';
        }

        try {
            $orderState = new OrderState((int) $order->current_state);
            if (!Validate::isLoadedObject($orderState)
                || (bool) $orderState->paid
                || (int) $order->current_state === (int) Configuration::get('PS_OS_CANCELED')
                || $this->hasRecordedPayment($order)
            ) {
                return '';
            }

            $instruction = (new BankTransferInstructionRepository())->findForOrder($shopId, (int) $order->id);
            $currency = new Currency((int) $order->id_currency);
            if ($instruction === null
                || !Validate::isLoadedObject($currency)
                || $instruction->orderReference !== (string) $order->reference
                || $instruction->totalPaid !== (string) $order->total_paid_tax_incl
                || $instruction->currencyIso !== strtoupper((string) $currency->iso_code)
            ) {
                return '';
            }

            $profileVersion = (new VersionedProfileRepository())->find($shopId, $instruction->profileVersionId);
            if ($profileVersion === null) {
                return '';
            }

            $requestedLocale = PublishedProfileProvider::localeForIso((string) ($this->context->language->iso_code ?? 'ja'));
            $defaultLocale = $profileVersion->profile['localization']['default_locale'] ?? 'ja-JP';
            if (!in_array($defaultLocale, ProfileDefaults::LOCALES, true)) {
                $defaultLocale = 'ja-JP';
            }
            $enabledLocales = $profileVersion->profile['localization']['enabled_locales'] ?? ProfileDefaults::LOCALES;
            $locale = is_array($enabledLocales) && in_array($requestedLocale, $enabledLocales, true)
                ? $requestedLocale
                : $defaultLocale;
            $formattedAmount = $this->context->getCurrentLocale()->formatPrice(
                (float) $instruction->totalPaid,
                (string) $currency->iso_code
            );

            return BankTransferInstructionPresenter::render(
                $instruction,
                $profileVersion->profile,
                $locale,
                (string) $formattedAmount
            );
        } catch (Throwable) {
            // Do not fall back to the current profile: an unavailable immutable snapshot must not leak a different account.
            return '';
        }
    }

    /** Fail closed when any positive native payment amount has been recorded. */
    private function hasRecordedPayment(Order $order): bool
    {
        $amount = (string) $order->total_paid_real;
        if (preg_match('/\A(?:0|[1-9][0-9]{0,17})(?:\.([0-9]{1,6}))?\z/D', $amount, $parts) !== 1) {
            return true;
        }

        return $amount[0] !== '0' || trim((string) ($parts[1] ?? ''), '0') !== '';
    }

    private function shopId(): int
    {
        $shopId = (int) ($this->context->shop->id ?? 0);
        if ($shopId < 1 && class_exists('Shop')) {
            $shopId = (int) Shop::getContextShopID();
        }

        return max(1, $shopId);
    }
}
