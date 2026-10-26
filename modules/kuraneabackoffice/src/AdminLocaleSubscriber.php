<?php

declare(strict_types=1);

namespace Kuranea\Backoffice;

use Kuranea\Backoffice\AdminDocumentLanguage;
use PrestaShop\PrestaShop\Core\Context\LanguageContextBuilder;
use PrestaShop\PrestaShop\Core\Language\LanguageRepositoryInterface;
use PrestaShop\PrestaShop\Core\Translation\Storage\Normalizer\DomainNormalizer;
use PrestaShopBundle\EventListener\Admin\Context\LanguageContextSubscriber;
use PrestaShopBundle\Translation\TranslatorLanguageLoader;
use Symfony\Component\EventDispatcher\EventSubscriberInterface;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\RequestStack;
use Symfony\Component\HttpKernel\Event\RequestEvent;
use Symfony\Component\HttpKernel\Event\ResponseEvent;
use Symfony\Component\HttpKernel\KernelEvents;
use Symfony\Component\Translation\Loader\XliffFileLoader;
use Symfony\Contracts\Translation\TranslatorInterface;

final class AdminLocaleSubscriber implements EventSubscriberInterface
{
    private const MODULE_NAME = 'kuraneabackoffice';
    private const KOREAN_LOCALE = 'ko-KR';
    // Override the employee language before the legacy context is built at priority 0.
    public const PRIORITY = LanguageContextSubscriber::KERNEL_REQUEST_PRIORITY - 1;

    /** @param string[] $activeModules */
    public function __construct(
        private readonly LanguageRepositoryInterface $languageRepository,
        private readonly LanguageContextBuilder $languageContextBuilder,
        private readonly TranslatorInterface $translator,
        private readonly TranslatorLanguageLoader $translatorLanguageLoader,
        private readonly RequestStack $requestStack,
        private readonly string $modulePath,
        private readonly array $activeModules,
    ) {
    }

    public static function getSubscribedEvents(): array
    {
        return [
            KernelEvents::REQUEST => ['onKernelRequest', self::PRIORITY],
            // Run after Symfony's ResponseListener prepares default response headers.
            KernelEvents::RESPONSE => ['onKernelResponse', -1],
        ];
    }

    public function onKernelRequest(RequestEvent $event): void
    {
        if (!in_array(self::MODULE_NAME, $this->activeModules, true)) {
            return;
        }

        $request = $event->getRequest();
        if (!$event->isMainRequest()) {
            $this->applyKoreanAdminSubrequestLocale($request);

            return;
        }

        $route = (string) $request->attributes->get('_route', '');
        if (!str_starts_with($route, 'admin_') || !$this->applyKoreanAdminLocale($request)) {
            return;
        }

        $this->loadKoreanCatalogue(self::KOREAN_LOCALE);
    }

    private function applyKoreanAdminSubrequestLocale(Request $request): void
    {
        $parentRequest = $this->requestStack->getMainRequest();
        if (
            $parentRequest === null
            || !str_starts_with((string) $parentRequest->attributes->get('_route', ''), 'admin_')
            || $parentRequest->getLocale() !== self::KOREAN_LOCALE
        ) {
            return;
        }

        // PrestaShop resets subrequests to the employee locale before this listener runs.
        $request->setLocale(self::KOREAN_LOCALE);
        if (method_exists($this->translator, 'setLocale')) {
            $this->translator->setLocale(self::KOREAN_LOCALE);
        }
    }

    public function onKernelResponse(ResponseEvent $event): void
    {
        $request = $event->getRequest();
        $response = $event->getResponse();
        $route = (string) $request->attributes->get('_route', '');
        $isMainRequest = $event->isMainRequest();
        $moduleActive = in_array(self::MODULE_NAME, $this->activeModules, true);
        $adminRoute = str_starts_with($route, 'admin_');
        $gateFields = self::diagnosticGateFields($request);
        $isolatedCiDiagnosticEnabled = self::isIsolatedCiDiagnosticRequest($request)
            && $gateFields['probe_header'] === '1'
            && $gateFields['probe_controller'] === '1';
        $diagnosticProbeEnabled = $isolatedCiDiagnosticEnabled;
        $diagnosticFields = [
            'main_request' => $isMainRequest ? '1' : '0',
            'module_active' => $moduleActive ? '1' : '0',
            'admin_route' => $adminRoute ? '1' : '0',
            'is_redirect' => $response->isRedirection() ? '1' : '0',
            'http_status' => (string) $response->getStatusCode(),
            'is_html' => 'not_checked',
            'body_present' => 'not_checked',
            'html_tags' => 'not_checked',
            'html_replacements' => 'not_checked',
            'lang_before' => 'not_checked',
            'lang_after' => 'not_checked',
            'rewritten' => '0',
            'response_listener' => '1',
            'isolated_ci_gate' => $isolatedCiDiagnosticEnabled ? '1' : '0',
            'probe_header' => $gateFields['probe_header'],
            'probe_controller' => $gateFields['probe_controller'],
            'server_ci' => $gateFields['server_ci'],
            'server_actions' => $gateFields['server_actions'],
            'server_run_id_valid' => $gateFields['server_run_id_valid'],
            'server_run_attempt_valid' => $gateFields['server_run_attempt_valid'],
            'server_diagnostics' => $gateFields['server_diagnostics'],
            'server_project_match' => $gateFields['server_project_match'],
            'env_ci' => $gateFields['env_ci'],
            'env_actions' => $gateFields['env_actions'],
            'env_run_id_valid' => $gateFields['env_run_id_valid'],
            'env_run_attempt_valid' => $gateFields['env_run_attempt_valid'],
            'env_diagnostics' => $gateFields['env_diagnostics'],
            'env_project_match' => $gateFields['env_project_match'],
        ];
        $writeDiagnostic = static function (string $stage) use (
            $response,
            $diagnosticProbeEnabled,
            &$diagnosticFields
        ): void {
            if (!$diagnosticProbeEnabled) {
                return;
            }

            $fields = ['stage=' . $stage];
            foreach ($diagnosticFields as $name => $value) {
                $fields[] = $name . '=' . $value;
            }
            $response->headers->set('X-ORDENOWA-ADMIN-LOCALE-DIAGNOSTIC', implode(';', $fields));
        };

        if (!$isMainRequest || !$moduleActive) {
            $writeDiagnostic('request_scope');
            return;
        }

        if ($response->isRedirection()) {
            $writeDiagnostic('redirect');
            return;
        }

        if (!$adminRoute) {
            $writeDiagnostic('not_admin_route');
            return;
        }

        $contentType = (string) $response->headers->get('Content-Type', '');
        $mediaType = strtolower(trim(explode(';', $contentType, 2)[0]));
        $diagnosticFields['is_html'] = $mediaType === 'text/html' ? '1' : '0';
        if ($mediaType !== 'text/html') {
            $writeDiagnostic('not_html');
            return;
        }

        $content = $response->getContent();
        if (!is_string($content) || $content === '') {
            $diagnosticFields['body_present'] = '0';
            $writeDiagnostic('empty_body');
            return;
        }
        $diagnosticFields['body_present'] = '1';

        $htmlTagCount = 0;
        $rootTagBefore = null;
        if ($diagnosticProbeEnabled) {
            preg_match_all('/<html\b[^>]*>/i', $content, $originalHtmlTags);
            $diagnosticFields['html_tags'] = (string) min(9999, count($originalHtmlTags[0] ?? []));
            $rootTagBefore = AdminDocumentLanguage::rootTag($content);
            $diagnosticFields['lang_before'] = self::diagnosticLanguageCategory(
                $rootTagBefore
            );
            $diagnosticFields['lang_after'] = $diagnosticFields['lang_before'];
        }
        $localizedContent = AdminDocumentLanguage::setRootLocale($content, self::KOREAN_LOCALE);
        $htmlTagCount = $localizedContent === null ? 0 : 1;
        if ($diagnosticProbeEnabled) {
            $diagnosticFields['html_replacements'] = (string) $htmlTagCount;
        }

        if ($localizedContent === null) {
            $localizedContent = $content;
        }

        if ($htmlTagCount !== 1 || !is_string($localizedContent) || $localizedContent === $content) {
            $writeDiagnostic($localizedContent === $content ? 'content_unchanged' : 'html_tag_count');
            return;
        }

        if ($diagnosticProbeEnabled) {
            $diagnosticFields['lang_after'] = self::diagnosticLanguageCategoryFromContent($localizedContent);
            $diagnosticFields['rewritten'] = '1';
        }
        $response->setContent($localizedContent);
        $response->headers->remove('Content-Length');
        $response->headers->remove('ETag');
        $writeDiagnostic('rewritten');
    }

    private static function diagnosticLanguageCategoryFromContent(string $content): string
    {
        return self::diagnosticLanguageCategory(AdminDocumentLanguage::rootTag($content));
    }

    private static function diagnosticLanguageCategory(?string $htmlTag): string
    {
        if ($htmlTag === null
            || preg_match(
                '/\s+lang\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))/i',
                $htmlTag,
                $matches,
                PREG_UNMATCHED_AS_NULL
            ) !== 1
        ) {
            return 'none';
        }

        $language = strtolower(trim((string) ($matches[1] ?? $matches[2] ?? $matches[3] ?? '')));

        return in_array($language, ['ko', 'ko-kr'], true) ? 'korean' : 'other';
    }

    private static function isIsolatedCiDiagnosticRequest(Request $request): bool
    {
        $fields = self::diagnosticGateFields($request);
        $serverGate = $fields['server_ci'] === '1'
            && $fields['server_actions'] === '1'
            && $fields['server_run_id_valid'] === '1'
            && $fields['server_run_attempt_valid'] === '1'
            && $fields['server_diagnostics'] === '1'
            && $fields['server_project_match'] === '1';
        $environmentGate = $fields['env_ci'] === '1'
            && $fields['env_actions'] === '1'
            && $fields['env_run_id_valid'] === '1'
            && $fields['env_run_attempt_valid'] === '1'
            && $fields['env_diagnostics'] === '1'
            && $fields['env_project_match'] === '1';

        return $serverGate || $environmentGate;
    }

    /** @return array<string, string> */
    private static function diagnosticGateFields(Request $request): array
    {
        $serverRunId = (string) $request->server->get('GITHUB_RUN_ID', '');
        $serverRunAttempt = (string) $request->server->get('GITHUB_RUN_ATTEMPT', '');
        $environmentRunId = getenv('GITHUB_RUN_ID');
        $environmentRunId = is_string($environmentRunId) ? $environmentRunId : '';
        $environmentRunAttempt = getenv('GITHUB_RUN_ATTEMPT');
        $environmentRunAttempt = is_string($environmentRunAttempt) ? $environmentRunAttempt : '';
        $serverRunIdValid = preg_match('/\A[0-9]+\z/D', $serverRunId) === 1;
        $serverRunAttemptValid = preg_match('/\A[0-9]+\z/D', $serverRunAttempt) === 1;
        $environmentRunIdValid = preg_match('/\A[0-9]+\z/D', $environmentRunId) === 1;
        $environmentRunAttemptValid = preg_match('/\A[0-9]+\z/D', $environmentRunAttempt) === 1;
        $serverProjectMatches = $serverRunIdValid
            && $serverRunAttemptValid
            && $request->server->get('KURANEA_CI_PROJECT_NAME')
                === 'kuranea-ci-' . $serverRunId . '-' . $serverRunAttempt;
        $environmentProjectName = getenv('KURANEA_CI_PROJECT_NAME');
        $environmentProjectName = is_string($environmentProjectName) ? $environmentProjectName : '';
        $environmentProjectMatches = $environmentRunIdValid
            && $environmentRunAttemptValid
            && $environmentProjectName === 'kuranea-ci-' . $environmentRunId . '-' . $environmentRunAttempt;
        $controllerQueryValue = $request->query->all()['controller'] ?? null;

        return [
            'probe_header' => $request->headers->get('X-ORDENOWA-ADMIN-LOCALE-DIAGNOSTIC') === '1' ? '1' : '0',
            'probe_controller' => $controllerQueryValue === 'AdminBusinessProfile' ? '1' : '0',
            'server_ci' => $request->server->get('CI') === 'true' ? '1' : '0',
            'server_actions' => $request->server->get('GITHUB_ACTIONS') === 'true' ? '1' : '0',
            'server_run_id_valid' => $serverRunIdValid ? '1' : '0',
            'server_run_attempt_valid' => $serverRunAttemptValid ? '1' : '0',
            'server_diagnostics' => $request->server->get('KURANEA_ADMIN_LOCALE_DIAGNOSTICS') === '1' ? '1' : '0',
            'server_project_match' => $serverProjectMatches ? '1' : '0',
            'env_ci' => getenv('CI') === 'true' ? '1' : '0',
            'env_actions' => getenv('GITHUB_ACTIONS') === 'true' ? '1' : '0',
            'env_run_id_valid' => $environmentRunIdValid ? '1' : '0',
            'env_run_attempt_valid' => $environmentRunAttemptValid ? '1' : '0',
            'env_diagnostics' => getenv('KURANEA_ADMIN_LOCALE_DIAGNOSTICS') === '1' ? '1' : '0',
            'env_project_match' => $environmentProjectMatches ? '1' : '0',
        ];
    }

    private function applyKoreanAdminLocale(Request $request): bool
    {
        $koreanLanguage = $this->languageRepository->getOneByLocaleOrIsoCode(self::KOREAN_LOCALE);
        if (
            $koreanLanguage === null
            || (method_exists($koreanLanguage, 'getActive') && !$koreanLanguage->getActive())
            || $koreanLanguage->getLocale() !== self::KOREAN_LOCALE
        ) {
            return false;
        }

        $request->setDefaultLocale(self::KOREAN_LOCALE);
        $request->setLocale(self::KOREAN_LOCALE);
        $this->languageContextBuilder->setLanguageId($koreanLanguage->getId());

        return true;
    }

    private function loadKoreanCatalogue(string $locale): void
    {
        if (!method_exists($this->translator, 'addResource')) {
            return;
        }

        if (method_exists($this->translator, 'setLocale')) {
            $this->translator->setLocale($locale);
        }

        if (
            !method_exists($this->translator, 'isLanguageLoaded')
            || !$this->translator->isLanguageLoaded($locale)
        ) {
            $this->translatorLanguageLoader
                ->setIsAdminContext(true)
                ->loadLanguage($this->translator, $locale, true);
        }

        $overlayFiles = [];
        $domainNormalizer = new DomainNormalizer();
        foreach ([
            'Admin.Actions' => 'AdminActions.ko-KR.xlf',
            'Admin.Global' => 'AdminGlobal.ko-KR.xlf',
            'Admin.Dashboard.Feature' => 'AdminDashboardFeature.ko-KR.xlf',
            'Admin.Navigation.Header' => 'AdminNavigationHeader.ko-KR.xlf',
            'Admin.Navigation.Menu' => 'AdminNavigationMenu.ko-KR.xlf',
            'Admin.Orderscustomers.Feature' => 'AdminOrderscustomersFeature.ko-KR.xlf',
            'messages' => 'messages.ko-KR.xlf',
        ] as $domain => $filename) {
            $translationFile = $this->modulePath . '/translations/' . $locale . '/' . $filename;
            if (is_file($translationFile)) {
                $catalogueDomain = $domainNormalizer->normalize($domain);
                $this->translator->addResource('xlf', $translationFile, $locale, $catalogueDomain);
                $overlayFiles[$catalogueDomain] = $translationFile;
            }
        }

        // PrestaShop's translator adds a database resource after each XLIFF resource. Merge
        // module-owned overrides after the catalogue is built so stale admin DB translations
        // cannot replace the Korean strings.
        if (method_exists($this->translator, 'getCatalogue') && $overlayFiles !== []) {
            $catalogue = $this->translator->getCatalogue($locale);
            $loader = new XliffFileLoader();
            foreach ($overlayFiles as $catalogueDomain => $translationFile) {
                $catalogue->addCatalogue($loader->load($translationFile, $locale, $catalogueDomain));
            }
        }
    }
}
