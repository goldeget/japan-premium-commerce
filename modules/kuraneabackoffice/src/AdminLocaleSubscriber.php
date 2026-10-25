<?php

declare(strict_types=1);

namespace Kuranea\Backoffice;

use PrestaShop\PrestaShop\Core\Context\LanguageContextBuilder;
use PrestaShop\PrestaShop\Core\Language\LanguageRepositoryInterface;
use PrestaShopBundle\Translation\TranslatorLanguageLoader;
use Symfony\Component\EventDispatcher\EventSubscriberInterface;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpKernel\Event\RequestEvent;
use Symfony\Component\HttpKernel\Event\ResponseEvent;
use Symfony\Component\HttpKernel\KernelEvents;
use Symfony\Component\Translation\Loader\XliffFileLoader;
use Symfony\Contracts\Translation\TranslatorInterface;

final class AdminLocaleSubscriber implements EventSubscriberInterface
{
    private const MODULE_NAME = 'kuraneabackoffice';
    private const KOREAN_LOCALE = 'ko-KR';
    public const PRIORITY = 14;

    /** @param string[] $activeModules */
    public function __construct(
        private readonly LanguageRepositoryInterface $languageRepository,
        private readonly LanguageContextBuilder $languageContextBuilder,
        private readonly TranslatorInterface $translator,
        private readonly TranslatorLanguageLoader $translatorLanguageLoader,
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
        if (!$event->isMainRequest() || !in_array(self::MODULE_NAME, $this->activeModules, true)) {
            return;
        }

        $request = $event->getRequest();
        $route = (string) $request->attributes->get('_route', '');
        if (!str_starts_with($route, 'admin_') || !$this->applyKoreanAdminLocale($request)) {
            return;
        }

        $this->loadKoreanCatalogue(self::KOREAN_LOCALE);
    }

    public function onKernelResponse(ResponseEvent $event): void
    {
        $request = $event->getRequest();
        $response = $event->getResponse();
        $route = (string) $request->attributes->get('_route', '');
        $isMainRequest = $event->isMainRequest();
        $moduleActive = in_array(self::MODULE_NAME, $this->activeModules, true);
        $adminRoute = str_starts_with($route, 'admin_');
        $diagnosticEnabled = self::isIsolatedCiDiagnosticRequest($request)
            && $request->headers->get('X-ORDENOWA-ADMIN-LOCALE-DIAGNOSTIC') === '1'
            && $request->query->get('controller') === 'AdminBusinessProfile';
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
        ];
        $writeDiagnostic = static function (string $stage) use (
            $response,
            $diagnosticEnabled,
            &$diagnosticFields
        ): void {
            if (!$diagnosticEnabled) {
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

        $koreanLanguageAttribute = 'lang="' . self::KOREAN_LOCALE . '"';
        $htmlTagCount = 0;
        if ($diagnosticEnabled) {
            preg_match_all('/<html\b[^>]*>/i', $content, $originalHtmlTags);
            $diagnosticFields['html_tags'] = (string) min(9999, count($originalHtmlTags[0] ?? []));
            $diagnosticFields['lang_before'] = self::diagnosticLanguageCategory(
                $originalHtmlTags[0][0] ?? null
            );
            $diagnosticFields['lang_after'] = $diagnosticFields['lang_before'];
        }
        $localizedContent = preg_replace_callback(
            '/<html\b[^>]*>/i',
            static function (array $matches) use ($koreanLanguageAttribute): string {
                $htmlTag = $matches[0];
                $languageAttributeCount = 0;
                $localizedTag = preg_replace(
                    '/\s+lang\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)/i',
                    ' ' . $koreanLanguageAttribute,
                    $htmlTag,
                    1,
                    $languageAttributeCount
                );
                if (!is_string($localizedTag)) {
                    return $htmlTag;
                }

                if ($languageAttributeCount > 0) {
                    return $localizedTag;
                }

                $closingBracket = strrpos($htmlTag, '>');
                if ($closingBracket === false) {
                    return $htmlTag;
                }

                return substr($htmlTag, 0, $closingBracket)
                    . ' ' . $koreanLanguageAttribute
                    . substr($htmlTag, $closingBracket);
            },
            $content,
            1,
            $htmlTagCount
        );
        if ($diagnosticEnabled) {
            $diagnosticFields['html_replacements'] = (string) $htmlTagCount;
        }

        if ($htmlTagCount !== 1 || !is_string($localizedContent) || $localizedContent === $content) {
            $writeDiagnostic($localizedContent === $content ? 'content_unchanged' : 'html_tag_count');
            return;
        }

        if ($diagnosticEnabled) {
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
        $htmlTag = null;
        if (preg_match('/<html\b[^>]*>/i', $content, $matches) === 1) {
            $htmlTag = $matches[0];
        }

        return self::diagnosticLanguageCategory($htmlTag);
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
        $runId = (string) $request->server->get('GITHUB_RUN_ID', '');
        $runAttempt = (string) $request->server->get('GITHUB_RUN_ATTEMPT', '');
        if (preg_match('/\A[0-9]+\z/D', $runId) !== 1 || preg_match('/\A[0-9]+\z/D', $runAttempt) !== 1) {
            return false;
        }

        $expectedProjectName = 'kuranea-ci-' . $runId . '-' . $runAttempt;

        return $request->server->get('CI') === 'true'
            && $request->server->get('GITHUB_ACTIONS') === 'true'
            && $request->server->get('KURANEA_ADMIN_LOCALE_DIAGNOSTICS') === '1'
            && $request->server->get('KURANEA_CI_PROJECT_NAME') === $expectedProjectName;
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
        foreach ([
            'Admin.Actions' => 'AdminActions.ko-KR.xlf',
            'Admin.Global' => 'AdminGlobal.ko-KR.xlf',
            'Admin.Navigation.Header' => 'AdminNavigationHeader.ko-KR.xlf',
            'messages' => 'messages.ko-KR.xlf',
        ] as $domain => $filename) {
            $translationFile = $this->modulePath . '/translations/' . $locale . '/' . $filename;
            if (is_file($translationFile)) {
                $this->translator->addResource('xlf', $translationFile, $locale, $domain);
                $overlayFiles[$domain] = $translationFile;
            }
        }

        // PrestaShop's translator adds a database resource after each XLIFF resource. Merge
        // module-owned overrides after the catalogue is built so stale admin DB translations
        // cannot replace the Korean strings.
        if (method_exists($this->translator, 'getCatalogue') && $overlayFiles !== []) {
            $catalogue = $this->translator->getCatalogue($locale);
            $loader = new XliffFileLoader();
            foreach ($overlayFiles as $domain => $translationFile) {
                $catalogue->addCatalogue($loader->load($translationFile, $locale, $domain));
            }
        }
    }
}
