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
    /** @var array{template: ?string, shop_id: ?int, lang_id: ?int, native_reset_url: ?string, reset_url_candidate_present: bool, reset_url_credentials_complete: bool, reset_url_native_route: bool}|null */
    private static ?array $pendingMailSendContext = null;

    private ?int $activeMailShopId = null;
    private ?int $activeMailLangId = null;
    private ?string $activeMailTemplate = null;
    private ?string $activeNativeResetUrl = null;

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
            'actionMailAlterMessageBeforeSend',
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

            $sendContext = self::$pendingMailSendContext;
            if (($params['template'] ?? '') === 'password_query'
                && ($sendContext['template'] ?? $this->activeMailTemplate) === 'password_query') {
                $mailLangId = (int) ($params['id_lang'] ?? 0);
                if ($mailLangId < 1) {
                    $mailLangId = (int) ($sendContext['lang_id'] ?? $this->activeMailLangId ?? 0);
                }
                $mailShopId = $sendContext['shop_id'] ?? $mailContextShopId;
                $nativeResetUrl = $sendContext['native_reset_url'] ?? $this->activeNativeResetUrl;
                if ($mailLangId > 0 && is_string($nativeResetUrl)) {
                    $validatedResetUrl = $this->validatedNativeResetUrl(
                        $nativeResetUrl,
                        $mailLangId,
                        is_int($mailShopId) && $mailShopId > 0 ? $mailShopId : null
                    );
                    if ($validatedResetUrl !== null) {
                        // Mail::send() merges extra_template_vars over templateVars
                        // immediately before strtr() builds both HTML and Text.
                        $params['extra_template_vars']['{url}'] = $validatedResetUrl;
                        $sendContext['final_reset_url_template_var_pinned'] = true;
                        self::$pendingMailSendContext = $sendContext;
                    }
                }
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

        if (($params['template'] ?? '') === 'password_query'
            && isset($params['template_txt'])
            && is_string($params['template_txt'])) {
            $sendContext = self::$pendingMailSendContext;
            $mailTemplate = $sendContext['template'] ?? $this->activeMailTemplate;
            $mailLangId = (int) ($params['id_lang'] ?? 0);
            if ($mailLangId < 1) {
                $mailLangId = (int) ($sendContext['lang_id'] ?? $this->activeMailLangId ?? 0);
            }
            $mailShopId = $sendContext['shop_id'] ?? $mailContextShopId;
            $nativeResetUrl = $sendContext['native_reset_url'] ?? $this->activeNativeResetUrl;
            if ($mailTemplate !== 'password_query' || $mailLangId < 1 || !is_string($nativeResetUrl)) {
                return;
            }

            $validatedResetUrl = $this->validatedNativeResetUrl(
                $nativeResetUrl,
                $mailLangId,
                is_int($mailShopId) && $mailShopId > 0 ? $mailShopId : null
            );
            if ($validatedResetUrl === null) {
                return;
            }

            $templateTxt = $params['template_txt'];
            if (!$this->hasExactValidatedNativeResetUrl(
                $templateTxt,
                $validatedResetUrl,
                $mailLangId,
                is_int($mailShopId) && $mailShopId > 0 ? $mailShopId : null
            )) {
                // Mail::send() substitutes template variables after this hook. Replace
                // the placeholder here with the already validated same-send URL so a
                // later template-variable hook cannot remove or alter the Text link.
                if (str_contains($templateTxt, '{url}')) {
                    $templateTxt = str_replace('{url}', $validatedResetUrl, $templateTxt);
                } else {
                    $templateTxt = ($templateTxt === '' ? '' : rtrim($templateTxt) . "\n\n")
                        . $validatedResetUrl;
                }
                $params['template_txt'] = $templateTxt;
            }

            return;
        }

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
        $langId = (int) ($params['idLang'] ?? 0);
        $this->activeMailLangId = $langId > 0 ? $langId : null;
        $this->activeMailTemplate = is_string($params['template'] ?? null) ? $params['template'] : null;
        $this->activeNativeResetUrl = null;

        if ($this->activeMailTemplate !== 'password_query'
            || !isset($params['templateVars']) || !is_array($params['templateVars'])) {
            self::$pendingMailSendContext = null;
            return;
        }

        $templateUrlEvidence = [];
        $this->activeNativeResetUrl = $this->validatedNativeResetUrl(
            $params['templateVars']['{url}'] ?? null,
            $this->activeMailLangId ?? 0,
            $this->activeMailShopId,
            $templateUrlEvidence
        );
        // The mail-alter hook can run on another instance of this module. Keep the
        // request-scoped native template context available until that message is sent.
        self::$pendingMailSendContext = [
            'template' => $this->activeMailTemplate,
            'shop_id' => $this->activeMailShopId,
            'lang_id' => $this->activeMailLangId,
            'native_reset_url' => $this->activeNativeResetUrl,
            'reset_url_candidate_present' => $templateUrlEvidence['candidate_present'] ?? false,
            'reset_url_credentials_complete' => $templateUrlEvidence['credentials_complete'] ?? false,
            'reset_url_native_route' => $templateUrlEvidence['native_route'] ?? false,
            'final_reset_url_template_var_pinned' => false,
        ];
    }

    /** @param array<string, mixed> $params */
    public function hookActionMailAlterMessageBeforeSend(array $params): void
    {
        $message = $params['message'] ?? null;
        $sendContext = self::$pendingMailSendContext;
        try {
            if (!is_object($message)
                || !method_exists($message, 'getHtmlBody')
                || !method_exists($message, 'getTextBody')) {
                return;
            }

            $htmlBody = (string) ($message->getHtmlBody() ?? '');
            $mailLangId = (int) ($params['id_lang'] ?? 0);
            if ($mailLangId < 1) {
                $mailLangId = $sendContext['lang_id'] ?? $this->activeMailLangId
                    ?? (int) ($this->context->language->id ?? 0);
            }
            $mailShopId = (int) ($params['id_shop'] ?? $params['idShop'] ?? 0);
            if ($mailShopId < 1) {
                $mailShopId = $sendContext['shop_id'] ?? $this->activeMailShopId;
            }
            if (($mailShopId ?? 0) < 1) {
                $contextShopId = (int) ($this->context->shop->id ?? 0);
                $mailShopId = $contextShopId > 0 ? $contextShopId : null;
            }
            // Prefer a credential-complete link visible in the rendered HTML body.
            // The mailer may expose a different HTML snapshot here than the one it
            // eventually serializes, so a validated same-send template URL remains
            // the safe text fallback when this snapshot omits the link.
            $mailTemplate = $sendContext['template'] ?? $this->activeMailTemplate;
            $nativeResetUrl = $sendContext['native_reset_url'] ?? $this->activeNativeResetUrl;
            $htmlUrlEvidence = [];
            $resetUrl = $mailTemplate === 'password_query'
                ? $this->extractNativeResetUrl($htmlBody, $mailLangId, $mailShopId, $htmlUrlEvidence)
                : null;
            if ($resetUrl === null && $mailTemplate === 'password_query' && is_string($nativeResetUrl)) {
                // Revalidate against this message's mail language and shop. This
                // preserves the canonical route and all three credential checks;
                // the raw-MIME integration check independently verifies that the
                // serialized HTML and Text parts carry the same reset credentials.
                $templateUrlEvidence = [];
                $resetUrl = $this->validatedNativeResetUrl(
                    $nativeResetUrl,
                    $mailLangId,
                    $mailShopId,
                    $templateUrlEvidence
                );
            }
            $textSetterAvailable = method_exists($message, 'text');
            $textSetterInvoked = false;
            $messageIsSymfonyEmail = $message instanceof \Symfony\Component\Mime\Email;
            $textSetterReturnedSameMessage = false;
            $textGetterReturnedString = false;
            $textGetterHasLink = false;
            $textReplacementContainsExpectedUrl = false;
            $textGetterContainsExpectedUrl = false;
            $textMimeContainsExpectedUrl = false;
            $textMimeHasLink = false;
            $textGetterMatchReason = 'not_checked';
            $textMimeMatchReason = 'not_checked';
            $textGetterEvidence = [];
            $textMimeEvidence = [];
            $textMimeBodyReadSucceeded = false;
            $textMimeBodyIdentitySameAfterSetter = false;
            $textMimeBodyChangedAfterReset = false;
            $textMimeBodyResetRetryAttempted = false;
            $textPlainTextPartPresent = false;
            $textMimeBodyBeforeSetter = null;
            if ($messageIsSymfonyEmail && $resetUrl !== null && $textSetterAvailable) {
                try {
                    $textMimeBodyBeforeSetter = $message->getBody();
                } catch (\Throwable) {
                    // The same boolean diagnostics below record a failed body read.
                }
            }
            if ($resetUrl !== null && $textSetterAvailable) {
                $textBody = (string) ($message->getTextBody() ?? '');
                $textBodyEvidence = [];
                $textGetterHasLink = $this->hasExactValidatedNativeResetUrl(
                    $textBody,
                    $resetUrl,
                    $mailLangId,
                    $mailShopId,
                    $textBodyEvidence
                );
                $textGetterMatchReason = $textBodyEvidence['match_reason'] ?? 'unavailable';
                $replacement = $textGetterHasLink
                    ? $textBody
                    : ($textBody === '' ? '' : rtrim($textBody) . "\n\n") . $resetUrl;
                $textReplacementContainsExpectedUrl = str_contains($replacement, $resetUrl);
                try {
                    if (!$textGetterHasLink) {
                        $setterResult = $message->text($replacement, 'utf-8');
                        $textSetterInvoked = true;
                        $textSetterReturnedSameMessage = $setterResult === $message;
                    }

                    // Symfony Email::text() is the supported setter. Verify both its
                    // public getter and the MIME tree that Mailer will serialize.
                    $textReadback = $message->getTextBody();
                    $textGetterReturnedString = is_string($textReadback);
                    $textGetterContainsExpectedUrl = is_string($textReadback)
                        && str_contains($textReadback, $resetUrl);
                    $textGetterEvidence = [];
                    $textGetterHasLink = $this->hasExactValidatedNativeResetUrl(
                        (string) ($textReadback ?? ''),
                        $resetUrl,
                        $mailLangId,
                        $mailShopId,
                        $textGetterEvidence
                    );
                    $textGetterMatchReason = $textGetterEvidence['match_reason'] ?? 'unavailable';
                    if ($messageIsSymfonyEmail) {
                        $textMimeBody = $message->getBody();
                        $textMimeBodyReadSucceeded = true;
                        $textMimeBodyIdentitySameAfterSetter = $textMimeBodyBeforeSetter === $textMimeBody;
                        $textPlainTextPartPresent = $this->hasPlainTextMimePart($textMimeBody);
                        $textMimeContainsExpectedUrl = $this->plainTextMimeContainsExpectedUrl(
                            $textMimeBody,
                            $resetUrl
                        );
                        $textMimeEvidence = [];
                        $textMimeHasLink = $this->hasExactNativeResetUrlInMimeBody(
                            $textMimeBody,
                            $resetUrl,
                            $mailLangId,
                            $mailShopId,
                            $textMimeEvidence
                        );
                        $textMimeMatchReason = $textMimeEvidence['match_reason'] ?? 'unavailable';
                        if (!$textGetterHasLink || !$textMimeHasLink) {
                            // Symfony Email can retain an explicit base Message body,
                            // which takes precedence over its lazily generated parts.
                            // Clear only that explicit body, then rebuild from Email's
                            // HTML/Text/attachment fields using its public APIs.
                            $textMimeBodyResetRetryAttempted = true;
                            $message->setBody(null);
                            $setterResult = $message->text($replacement, 'utf-8');
                            $textSetterInvoked = true;
                            $textSetterReturnedSameMessage = $textSetterReturnedSameMessage
                                || $setterResult === $message;
                            $textReadback = $message->getTextBody();
                            $textGetterReturnedString = is_string($textReadback);
                            $textGetterContainsExpectedUrl = is_string($textReadback)
                                && str_contains($textReadback, $resetUrl);
                            $textGetterEvidence = [];
                            $textGetterHasLink = $this->hasExactValidatedNativeResetUrl(
                                (string) ($textReadback ?? ''),
                                $resetUrl,
                                $mailLangId,
                                $mailShopId,
                                $textGetterEvidence
                            );
                            $textGetterMatchReason = $textGetterEvidence['match_reason'] ?? 'unavailable';
                            $rebuiltMimeBody = $message->getBody();
                            $textMimeBodyReadSucceeded = true;
                            $textMimeBodyChangedAfterReset = $textMimeBody !== $rebuiltMimeBody;
                            $textPlainTextPartPresent = $this->hasPlainTextMimePart($rebuiltMimeBody);
                            $textMimeContainsExpectedUrl = $this->plainTextMimeContainsExpectedUrl(
                                $rebuiltMimeBody,
                                $resetUrl
                            );
                            $textMimeEvidence = [];
                            $textMimeHasLink = $this->hasExactNativeResetUrlInMimeBody(
                                $rebuiltMimeBody,
                                $resetUrl,
                                $mailLangId,
                                $mailShopId,
                                $textMimeEvidence
                            );
                            $textMimeMatchReason = $textMimeEvidence['match_reason'] ?? 'unavailable';
                        }
                    }
                } catch (\Throwable) {
                    // Keep mail delivery available if a compatible mailer cannot replace its text body.
                }
            }

            if (!$this->isIsolatedResetFixtureMessage($message)
                || !method_exists($message, 'getHeaders')) {
                return;
            }

            $headers = $message->getHeaders();
            if (!is_object($headers) || !method_exists($headers, 'addTextHeader')) {
                return;
            }
            $htmlHasLink = $resetUrl !== null
                && $this->hasNativeResetLink($htmlBody, $resetUrl);
            $headers->addTextHeader('X-ORDENOWA-CI-Pre-SMTP-HTML-Native-Reset-Link', $htmlHasLink ? 'true' : 'false');
            $headers->addTextHeader(
                'X-ORDENOWA-CI-Pre-SMTP-Text-Native-Reset-Link',
                $textGetterHasLink ? 'true' : 'false'
            );
            $headers->addTextHeader(
                'X-ORDENOWA-CI-Pre-SMTP-Text-Mime-Native-Reset-Link',
                $textMimeHasLink ? 'true' : 'false'
            );
            $headers->addTextHeader('X-ORDENOWA-CI-Reset-Text-Getter-Match-Reason', $textGetterMatchReason);
            $headers->addTextHeader('X-ORDENOWA-CI-Reset-Text-Mime-Match-Reason', $textMimeMatchReason);
            foreach ([
                'message_is_symfony_email' => 'Symfony-Email-Object',
                'text_setter_returned_same_message' => 'Text-Setter-Returned-Same-Message',
                'text_getter_returned_string' => 'Text-Getter-Returned-String',
                'text_replacement_contains_expected_url' => 'Text-Replacement-Contains-Expected-URL',
                'text_getter_contains_expected_url' => 'Text-Getter-Contains-Expected-URL',
                'text_mime_contains_expected_url' => 'Text-Mime-Contains-Expected-URL',
                'text_getter_expected_url_literal_present' => 'Text-Getter-Expected-URL-Literal-Present',
                'text_getter_expected_url_candidate_present' => 'Text-Getter-Expected-URL-Candidate-Present',
                'text_getter_expected_url_candidate_exact' => 'Text-Getter-Expected-URL-Candidate-Exact',
                'text_getter_expected_url_candidate_credentials_complete' => 'Text-Getter-Expected-URL-Candidate-Credentials-Complete',
                'text_mime_expected_url_literal_present' => 'Text-Mime-Expected-URL-Literal-Present',
                'text_mime_expected_url_candidate_present' => 'Text-Mime-Expected-URL-Candidate-Present',
                'text_mime_expected_url_candidate_exact' => 'Text-Mime-Expected-URL-Candidate-Exact',
                'text_mime_expected_url_candidate_credentials_complete' => 'Text-Mime-Expected-URL-Candidate-Credentials-Complete',
                'text_mime_body_read_succeeded' => 'Text-Mime-Body-Read-Succeeded',
                'text_mime_body_identity_same_after_setter' => 'Text-Mime-Body-Identity-Same-After-Setter',
                'text_mime_body_reset_retry_attempted' => 'Text-Mime-Body-Reset-Retry-Attempted',
                'text_mime_body_changed_after_reset' => 'Text-Mime-Body-Changed-After-Reset',
                'text_plain_text_part_present' => 'Text-Plain-Part-Present',
            ] as $key => $suffix) {
                $evidence = match ($key) {
                    'message_is_symfony_email' => $messageIsSymfonyEmail,
                    'text_setter_returned_same_message' => $textSetterReturnedSameMessage,
                    'text_getter_returned_string' => $textGetterReturnedString,
                    'text_replacement_contains_expected_url' => $textReplacementContainsExpectedUrl,
                    'text_getter_contains_expected_url' => $textGetterContainsExpectedUrl,
                    'text_mime_contains_expected_url' => $textMimeContainsExpectedUrl,
                    'text_getter_expected_url_literal_present' => $textGetterEvidence['expected_url_literal_present'] ?? false,
                    'text_getter_expected_url_candidate_present' => $textGetterEvidence['expected_url_candidate_present'] ?? false,
                    'text_getter_expected_url_candidate_exact' => $textGetterEvidence['expected_url_candidate_exact'] ?? false,
                    'text_getter_expected_url_candidate_credentials_complete' => $textGetterEvidence['expected_url_candidate_credentials_complete'] ?? false,
                    'text_mime_expected_url_literal_present' => $textMimeEvidence['expected_url_literal_present'] ?? false,
                    'text_mime_expected_url_candidate_present' => $textMimeEvidence['expected_url_candidate_present'] ?? false,
                    'text_mime_expected_url_candidate_exact' => $textMimeEvidence['expected_url_candidate_exact'] ?? false,
                    'text_mime_expected_url_candidate_credentials_complete' => $textMimeEvidence['expected_url_candidate_credentials_complete'] ?? false,
                    'text_mime_body_read_succeeded' => $textMimeBodyReadSucceeded,
                    'text_mime_body_identity_same_after_setter' => $textMimeBodyIdentitySameAfterSetter,
                    'text_mime_body_reset_retry_attempted' => $textMimeBodyResetRetryAttempted,
                    'text_mime_body_changed_after_reset' => $textMimeBodyChangedAfterReset,
                    'text_plain_text_part_present' => $textPlainTextPartPresent,
                };
                $headers->addTextHeader(
                    'X-ORDENOWA-CI-Reset-' . $suffix,
                    $evidence ? 'true' : 'false'
                );
            }
            $headers->addTextHeader('X-ORDENOWA-CI-Reset-URL-Candidate-Found', $resetUrl !== null ? 'true' : 'false');
            $headers->addTextHeader(
                'X-ORDENOWA-CI-Reset-Template-Context-Recognized',
                $mailTemplate === 'password_query' ? 'true' : 'false'
            );
            $headers->addTextHeader(
                'X-ORDENOWA-CI-Reset-Template-URL-Candidate-Present',
                ($sendContext['reset_url_candidate_present'] ?? false) ? 'true' : 'false'
            );
            $headers->addTextHeader(
                'X-ORDENOWA-CI-Reset-Template-URL-Credentials-Complete',
                ($sendContext['reset_url_credentials_complete'] ?? false) ? 'true' : 'false'
            );
            $headers->addTextHeader(
                'X-ORDENOWA-CI-Reset-Template-URL-Native-Route',
                ($sendContext['reset_url_native_route'] ?? false) ? 'true' : 'false'
            );
            $headers->addTextHeader(
                'X-ORDENOWA-CI-Reset-Final-Template-URL-Pinned',
                ($sendContext['final_reset_url_template_var_pinned'] ?? false) ? 'true' : 'false'
            );
            foreach ([
                'candidate_present' => 'HTML-URL-Candidate-Present',
                'token_present' => 'HTML-Token-Present',
                'reset_token_present' => 'HTML-Reset-Token-Present',
                'id_customer_present' => 'HTML-Customer-ID-Present',
                'scheme_host_port_match' => 'HTML-Scheme-Host-Port-Match',
                'path_match' => 'HTML-Path-Match',
                'credentials_complete' => 'HTML-Credentials-Complete',
                'candidate_selected' => 'HTML-Candidate-Selected',
            ] as $key => $suffix) {
                $headers->addTextHeader(
                    'X-ORDENOWA-CI-Reset-' . $suffix,
                    ($htmlUrlEvidence[$key] ?? false) ? 'true' : 'false'
                );
            }
            $headers->addTextHeader('X-ORDENOWA-CI-Text-Setter-Available', $textSetterAvailable ? 'true' : 'false');
            $headers->addTextHeader('X-ORDENOWA-CI-Text-Setter-Invoked', $textSetterInvoked ? 'true' : 'false');
        } finally {
            $this->activeMailTemplate = null;
            $this->activeNativeResetUrl = null;
            $this->activeMailShopId = null;
            $this->activeMailLangId = null;
            self::$pendingMailSendContext = null;
        }
    }

    private function isIsolatedResetFixtureMessage(mixed $message): bool
    {
        $runId = (string) getenv('GITHUB_RUN_ID');
        $attempt = (string) getenv('GITHUB_RUN_ATTEMPT');
        $project = 'kuranea-ci-' . $runId . '-' . $attempt;
        if (getenv('CI') !== 'true'
            || getenv('GITHUB_ACTIONS') !== 'true'
            || getenv('KURANEA_CI_PROJECT_NAME') !== $project
            || preg_match('/\\A[0-9]+\\z/D', $runId) !== 1
            || preg_match('/\\A[0-9]+\\z/D', $attempt) !== 1
            || !is_object($message)
            || !method_exists($message, 'getTo')) {
            return false;
        }

        $recipients = $message->getTo();
        if (!is_array($recipients)) {
            return false;
        }
        $pattern = '/\\Aordenowa-reset-locale-' . preg_quote($runId, '/') . '-'
            . preg_quote($attempt, '/') . '-(?:ja|en|ko)-[a-f0-9]{8}@example\\.invalid\\z/D';
        foreach ($recipients as $recipient) {
            if (!is_object($recipient) || !method_exists($recipient, 'getAddress')) {
                continue;
            }
            if (preg_match($pattern, strtolower((string) $recipient->getAddress())) === 1) {
                return true;
            }
        }
        return false;
    }

    private function validatedNativeResetUrl(
        mixed $candidate,
        int $idLang,
        ?int $shopId,
        ?array &$evidence = null
    ): ?string
    {
        $evidence = [
            'candidate_present' => is_string($candidate) && trim($candidate) !== '',
            'token_present' => false,
            'reset_token_present' => false,
            'id_customer_present' => false,
            'credentials_complete' => false,
            'scheme_host_port_match' => false,
            'path_match' => false,
            'native_route' => false,
        ];
        if (!is_string($candidate) || trim($candidate) === ''
            || !is_object($this->context->link) || !method_exists($this->context->link, 'getPageLink')) {
            return null;
        }
        $nativeUrl = (string) $this->context->link->getPageLink(
            'password', null, $idLang > 0 ? $idLang : null, null, false, ($shopId ?? 0) > 0 ? $shopId : null
        );
        $native = parse_url($nativeUrl);
        $parts = parse_url(trim($candidate));
        $routeEvidence = $this->resetRouteEvidence($parts, $native);
        $evidence['scheme_host_port_match'] = $routeEvidence['scheme_host_port_match'];
        $evidence['path_match'] = $routeEvidence['path_match'];
        $evidence['native_route'] = $routeEvidence['native_route'];
        $credentialEvidence = $this->resetCredentialEvidence($parts);
        foreach (['token_present', 'reset_token_present', 'id_customer_present', 'credentials_complete'] as $key) {
            $evidence[$key] = $credentialEvidence[$key];
        }
        if (!$evidence['native_route'] || !$evidence['credentials_complete']) {
            return null;
        }

        return trim($candidate);
    }

    private function extractNativeResetUrl(
        string $body,
        int $idLang,
        ?int $shopId,
        ?array &$evidence = null,
        ?string $expectedUrl = null
    ): ?string
    {
        $evidence = [
            'candidate_present' => false,
            'token_present' => false,
            'reset_token_present' => false,
            'id_customer_present' => false,
            'credentials_complete' => false,
            'scheme_host_port_match' => false,
            'path_match' => false,
            'candidate_selected' => false,
            'expected_url_literal_present' => false,
            'expected_url_candidate_present' => false,
            'expected_url_candidate_exact' => false,
            'expected_url_candidate_credentials_complete' => false,
        ];
        if ($body === '' || !is_object($this->context->link) || !method_exists($this->context->link, 'getPageLink')) {
            return null;
        }
        $nativeUrl = (string) $this->context->link->getPageLink(
            'password', null, $idLang > 0 ? $idLang : null, null, false, ($shopId ?? 0) > 0 ? $shopId : null
        );
        $native = parse_url($nativeUrl);
        if (!is_array($native)) {
            return null;
        }

        $decoded = html_entity_decode($body, ENT_QUOTES | ENT_HTML5, 'UTF-8');
        $evidence['expected_url_literal_present'] = $expectedUrl !== null
            && str_contains($decoded, $expectedUrl);
        if (preg_match_all('~https?://[^\s<>]+~i', $decoded, $matches) < 1) {
            return null;
        }
        foreach ($matches[0] as $candidate) {
            $candidate = rtrim($candidate, '.,;)]>' . chr(34) . chr(39));
            $parts = parse_url($candidate);
            $evidence['candidate_present'] = true;
            $credentialEvidence = $this->resetCredentialEvidence($parts);
            $routeEvidence = $this->resetRouteEvidence($parts, $native);
            if ($expectedUrl !== null && str_contains($candidate, $expectedUrl)) {
                $evidence['expected_url_candidate_present'] = true;
                $evidence['expected_url_candidate_exact'] = $evidence['expected_url_candidate_exact']
                    || hash_equals($expectedUrl, $candidate);
                $evidence['expected_url_candidate_credentials_complete'] =
                    $evidence['expected_url_candidate_credentials_complete']
                    || $credentialEvidence['credentials_complete'];
            }
            foreach (['token_present', 'reset_token_present', 'id_customer_present'] as $key) {
                $evidence[$key] = $evidence[$key] || $credentialEvidence[$key];
            }
            $evidence['credentials_complete'] = $evidence['credentials_complete']
                || $credentialEvidence['credentials_complete'];
            $evidence['scheme_host_port_match'] = $evidence['scheme_host_port_match']
                || $routeEvidence['scheme_host_port_match'];
            $evidence['path_match'] = $evidence['path_match'] || $routeEvidence['path_match'];
            if (!$routeEvidence['native_route'] || !$credentialEvidence['credentials_complete']) {
                continue;
            }

            $evidence['candidate_selected'] = true;
            if ($expectedUrl !== null && !hash_equals($expectedUrl, $candidate)) {
                continue;
            }

            return $candidate;
        }

        return null;
    }

    /** @return array{token_present: bool, reset_token_present: bool, id_customer_present: bool, credentials_complete: bool} */
    private function resetCredentialEvidence(mixed $parts): array
    {
        $result = [
            'token_present' => false,
            'reset_token_present' => false,
            'id_customer_present' => false,
            'credentials_complete' => false,
        ];
        if (!is_array($parts)) {
            return $result;
        }

        $queryString = (string) ($parts['query'] ?? '');
        parse_str($queryString, $query);
        $separators = (string) ini_get('arg_separator.input');
        if ($separators === '') {
            $separators = '&';
        }
        $pairs = preg_split('/[' . preg_quote($separators, '/') . ']/', $queryString) ?: [];
        $credentialCounts = array_fill_keys(['token', 'reset_token', 'id_customer'], 0);
        foreach ($pairs as $pair) {
            if ($pair === '') {
                continue;
            }
            $encodedKey = explode('=', $pair, 2)[0];
            $key = urldecode($encodedKey);
            if (array_key_exists($key, $credentialCounts)) {
                ++$credentialCounts[$key];
            }
        }
        foreach ([
            'token' => 'token_present',
            'reset_token' => 'reset_token_present',
            'id_customer' => 'id_customer_present',
        ] as $key => $resultKey) {
            $result[$resultKey] = $credentialCounts[$key] === 1
                && is_string($query[$key] ?? null)
                && trim($query[$key]) !== '';
        }
        $result['credentials_complete'] = $result['token_present']
            && $result['reset_token_present']
            && $result['id_customer_present'];

        return $result;
    }

    /** @return array{scheme_host_port_match: bool, path_match: bool, native_route: bool} */
    private function resetRouteEvidence(mixed $candidate, mixed $expected): array
    {
        $result = ['scheme_host_port_match' => false, 'path_match' => false, 'native_route' => false];
        if (!is_array($candidate) || !is_array($expected)
            || !isset($candidate['scheme'], $candidate['host'], $candidate['path'])
            || !isset($expected['scheme'], $expected['host'], $expected['path'])
            || isset($candidate['user']) || isset($candidate['pass']) || isset($candidate['fragment'])) {
            return $result;
        }
        $candidateScheme = strtolower((string) $candidate['scheme']);
        $expectedScheme = strtolower((string) $expected['scheme']);
        if (!in_array($candidateScheme, ['http', 'https'], true)) {
            return $result;
        }
        $defaultPort = $candidateScheme === 'https' ? 443 : 80;
        $result['scheme_host_port_match'] = $candidateScheme === $expectedScheme
            && strtolower((string) $candidate['host']) === strtolower((string) $expected['host'])
            && (int) ($candidate['port'] ?? $defaultPort) === (int) ($expected['port'] ?? $defaultPort);
        $result['path_match'] = rtrim(rawurldecode((string) $candidate['path']), '/')
            === rtrim(rawurldecode((string) $expected['path']), '/');
        $result['native_route'] = $result['scheme_host_port_match'] && $result['path_match'];

        return $result;
    }

    private function hasNativeResetLink(string $body, string $expectedUrl): bool
    {
        if ($body === '') {
            return false;
        }

        $decoded = html_entity_decode($body, ENT_QUOTES | ENT_HTML5, 'UTF-8');
        if (preg_match_all('~https?://[^\s<>]+~i', $decoded, $matches) < 1) {
            return false;
        }
        $expected = parse_url($expectedUrl);
        if (!is_array($expected)) {
            return false;
        }
        $expectedCredentialEvidence = $this->resetCredentialEvidence($expected);
        if (!$expectedCredentialEvidence['credentials_complete']) {
            return false;
        }
        parse_str((string) ($expected['query'] ?? ''), $expectedQuery);
        foreach ($matches[0] as $candidate) {
            $candidate = rtrim($candidate, '.,;)]>' . chr(34) . chr(39));
            $parts = parse_url($candidate);
            if (!$this->sameNativeResetRoute($parts, $expected)) {
                continue;
            }
            $credentialEvidence = $this->resetCredentialEvidence($parts);
            if (!$credentialEvidence['credentials_complete']) {
                continue;
            }
            parse_str((string) ($parts['query'] ?? ''), $query);
            $sameReset = true;
            foreach (['token', 'reset_token', 'id_customer'] as $key) {
                if (!is_string($query[$key] ?? null)
                    || !is_string($expectedQuery[$key] ?? null)
                    || $query[$key] !== $expectedQuery[$key]) {
                    $sameReset = false;
                    break;
                }
            }
            if ($sameReset) {
                return true;
            }
        }

        return false;
    }

    /**
     * Require the body candidate itself to pass native route and credential checks,
     * then require its complete URL to equal this message's validated template URL.
     * This avoids comparing parsed query arrays that may normalize equivalent
     * query encodings differently while preserving all reset-link guards.
     *
     * @param array<string, mixed>|null $evidence
     */
    private function hasExactValidatedNativeResetUrl(
        string $body,
        string $expectedUrl,
        int $idLang,
        ?int $shopId,
        ?array &$evidence = null
    ): bool {
        $evidence = [
            'candidate_present' => false,
            'token_present' => false,
            'reset_token_present' => false,
            'id_customer_present' => false,
            'credentials_complete' => false,
            'scheme_host_port_match' => false,
            'path_match' => false,
            'candidate_selected' => false,
            'expected_url_match' => false,
            'expected_url_literal_present' => false,
            'expected_url_candidate_present' => false,
            'expected_url_candidate_exact' => false,
            'expected_url_candidate_credentials_complete' => false,
            'match_reason' => 'candidate_absent',
        ];
        if ($body === '') {
            return false;
        }

        $expectedEvidence = [];
        $validatedExpectedUrl = $this->validatedNativeResetUrl(
            $expectedUrl,
            $idLang,
            $shopId,
            $expectedEvidence
        );
        if ($validatedExpectedUrl === null) {
            $evidence['match_reason'] = 'expected_url_invalid';

            return false;
        }

        $candidateEvidence = [];
        $candidateUrl = $this->extractNativeResetUrl(
            $body,
            $idLang,
            $shopId,
            $candidateEvidence,
            $validatedExpectedUrl
        );
        foreach ([
            'candidate_present', 'token_present', 'reset_token_present', 'id_customer_present',
            'credentials_complete', 'scheme_host_port_match', 'path_match', 'candidate_selected',
            'expected_url_literal_present', 'expected_url_candidate_present',
            'expected_url_candidate_exact', 'expected_url_candidate_credentials_complete',
        ] as $key) {
            $evidence[$key] = $candidateEvidence[$key] ?? false;
        }
        $evidence['expected_url_match'] = is_string($candidateUrl)
            && ($candidateEvidence['credentials_complete'] ?? false)
            && ($candidateEvidence['candidate_selected'] ?? false)
            && ($candidateEvidence['scheme_host_port_match'] ?? false)
            && ($candidateEvidence['path_match'] ?? false)
            && hash_equals($validatedExpectedUrl, $candidateUrl);
        if ($evidence['expected_url_match']) {
            $evidence['match_reason'] = 'matched';

            return true;
        }
        if (!($evidence['candidate_present'] ?? false)) {
            $evidence['match_reason'] = 'candidate_absent';
        } elseif (!($evidence['credentials_complete'] ?? false)) {
            $evidence['match_reason'] = 'credentials_incomplete';
        } elseif (!($evidence['scheme_host_port_match'] ?? false)) {
            $evidence['match_reason'] = 'origin_mismatch';
        } elseif (!($evidence['path_match'] ?? false)) {
            $evidence['match_reason'] = 'path_mismatch';
        } elseif (!($evidence['candidate_selected'] ?? false)) {
            $evidence['match_reason'] = 'native_candidate_missing';
        } else {
            $evidence['match_reason'] = 'expected_url_mismatch';
        }

        return false;
    }

    /** @param array<string, mixed>|false|null $candidate @param array<string, mixed>|false|null $expected */
    private function sameNativeResetRoute(mixed $candidate, mixed $expected): bool
    {
        return $this->resetRouteEvidence($candidate, $expected)['native_route'];
    }

    private function hasPlainTextMimePart(mixed $part): bool
    {
        return $this->selectedPlainTextMimePart($part) !== null;
    }

    private function selectedPlainTextMimePart(mixed $part): ?\Symfony\Component\Mime\Part\TextPart
    {
        if ($part instanceof \Symfony\Component\Mime\Part\DataPart) {
            return null;
        }
        if ($part instanceof \Symfony\Component\Mime\Part\TextPart) {
            return $part->getMediaSubtype() === 'plain' ? $part : null;
        }
        if ($part instanceof \Symfony\Component\Mime\Part\AbstractMultipartPart) {
            foreach ($part->getParts() as $child) {
                $plainPart = $this->selectedPlainTextMimePart($child);
                if ($plainPart !== null) {
                    return $plainPart;
                }
            }
        }

        return null;
    }

    private function plainTextMimeContainsExpectedUrl(mixed $part, string $expectedUrl): bool
    {
        $plainPart = $this->selectedPlainTextMimePart($part);

        return $plainPart !== null && str_contains($plainPart->getBody(), $expectedUrl);
    }

    private function hasExactNativeResetUrlInMimeBody(
        mixed $part,
        string $expectedUrl,
        int $idLang,
        ?int $shopId,
        ?array &$evidence = null
    ): bool
    {
        $plainPart = $this->selectedPlainTextMimePart($part);
        if ($plainPart === null) {
            $evidence = ['match_reason' => 'plain_text_part_missing'];

            return false;
        }

        return $this->hasExactValidatedNativeResetUrl(
            $plainPart->getBody(),
            $expectedUrl,
            $idLang,
            $shopId,
            $evidence
        );
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

    /** Reapply the non-destructive payment schema and hooks after a core installer pre-registers this module. */
    public function ensureBankTransferInfrastructure(): bool
    {
        return (new VersionedProfileRepository())->install()
            && $this->registerHook(['displayOrderConfirmation', 'displayOrderDetail'])
            && $this->installTransferInstructionsTab();
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
            || (string) ($order->module ?? '') !== 'ps_checkpayment'
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
