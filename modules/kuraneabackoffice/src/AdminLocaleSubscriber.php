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
        if (!$event->isMainRequest() || !in_array(self::MODULE_NAME, $this->activeModules, true)) {
            return;
        }

        $request = $event->getRequest();
        $route = (string) $request->attributes->get('_route', '');
        if (!str_starts_with($route, 'admin_')) {
            return;
        }

        $response = $event->getResponse();
        if ($response->isRedirection()) {
            return;
        }

        $contentType = (string) $response->headers->get('Content-Type', '');
        $mediaType = strtolower(trim(explode(';', $contentType, 2)[0]));
        if ($mediaType !== 'text/html') {
            return;
        }

        $content = $response->getContent();
        if (!is_string($content) || $content === '') {
            return;
        }

        $koreanLanguageAttribute = 'lang="' . self::KOREAN_LOCALE . '"';
        $htmlTagCount = 0;
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

        if ($htmlTagCount !== 1 || !is_string($localizedContent) || $localizedContent === $content) {
            return;
        }

        $response->setContent($localizedContent);
        $response->headers->remove('Content-Length');
        $response->headers->remove('ETag');
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
