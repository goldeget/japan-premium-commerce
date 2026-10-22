<?php

declare(strict_types=1);

namespace Kuranea\Backoffice;

use PrestaShop\PrestaShop\Core\Context\LanguageContextBuilder;
use PrestaShop\PrestaShop\Core\Language\LanguageRepositoryInterface;
use PrestaShopBundle\Translation\TranslatorLanguageLoader;
use Symfony\Component\EventDispatcher\EventSubscriberInterface;
use Symfony\Component\HttpKernel\Event\RequestEvent;
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
        ];
    }

    public function onKernelRequest(RequestEvent $event): void
    {
        if (!$event->isMainRequest() || !in_array(self::MODULE_NAME, $this->activeModules, true)) {
            return;
        }

        $request = $event->getRequest();
        $route = (string) $request->attributes->get('_route', '');
        $locale = $request->getLocale();

        if ($route === 'admin_login') {
            $koreanLanguage = $this->languageRepository->getOneByLocaleOrIsoCode(self::KOREAN_LOCALE);
            if (
                $koreanLanguage === null
                || (method_exists($koreanLanguage, 'getActive') && !$koreanLanguage->getActive())
                || $koreanLanguage->getLocale() !== self::KOREAN_LOCALE
            ) {
                return;
            }

            $locale = $koreanLanguage->getLocale();
            $request->setDefaultLocale($locale);
            $request->setLocale($locale);
            $this->languageContextBuilder->setLanguageId($koreanLanguage->getId());
        }

        if (!str_starts_with($route, 'admin_') || $locale !== self::KOREAN_LOCALE) {
            return;
        }

        $this->loadKoreanCatalogue($locale);
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
