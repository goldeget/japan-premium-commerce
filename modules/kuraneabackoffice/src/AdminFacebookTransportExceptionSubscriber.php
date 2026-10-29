<?php

declare(strict_types=1);

namespace Kuranea\Backoffice;

use RuntimeException;
use Symfony\Bundle\SecurityBundle\Security;
use Symfony\Component\EventDispatcher\EventSubscriberInterface;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpKernel\Event\ExceptionEvent;
use Symfony\Component\HttpKernel\KernelEvents;
use Twig\Environment;

/**
 * Convert only ps_facebook's native cURL transport RuntimeException on its
 * authenticated legacy admin page into a fixed Korean service-unavailable page.
 *
 * It deliberately does not inspect arbitrary exception messages or traces for
 * display. The cURL message is used only as a narrow branch predicate and is
 * never returned, logged, or passed to Twig.
 */
final class AdminFacebookTransportExceptionSubscriber implements EventSubscriberInterface
{
    private const FACEBOOK_CONTROLLER = 'AdminPsfacebookModuleController';
    private const FACEBOOK_CONTROLLER_NAME = 'AdminPsfacebookModule';
    private const FACEBOOK_ROUTE = 'admin_legacy_controller_route';
    private const FACEBOOK_ACTION = 'read';
    private const FACEBOOK_HTTP_CLIENT = 'PrestaShop\\Module\\PrestashopFacebook\\Http\\HttpClient';
    private const TEMPLATE = '@Modules/kuraneabackoffice/views/templates/admin/facebook_transport_error.html.twig';

    /** @param string[] $activeModules */
    public function __construct(
        private readonly Security $security,
        private readonly Environment $twig,
        private readonly string $modulesPath,
        private readonly array $activeModules,
    ) {
    }

    public static function getSubscribedEvents(): array
    {
        // Handle this narrow case before Symfony's generic exception renderer.
        return [KernelEvents::EXCEPTION => ['onKernelException', 64]];
    }

    public function onKernelException(ExceptionEvent $event): void
    {
        if (!$event->isMainRequest() || !$this->isExactAuthenticatedFacebookRead($event)) {
            return;
        }

        $failure = $event->getThrowable();
        if (!$failure instanceof RuntimeException || get_class($failure) !== RuntimeException::class
            || !$this->isFacebookCurlTransportFailure($failure)) {
            return;
        }

        try {
            $html = $this->twig->render(self::TEMPLATE, [
                'layoutTitle' => 'Facebook 계정 연결 오류',
                'meta_title' => 'Facebook 계정 연결 오류',
            ]);
        } catch (\Throwable) {
            // Preserve the original exception if the project-owned view cannot render.
            return;
        }

        $response = new Response($html, Response::HTTP_SERVICE_UNAVAILABLE, [
            'Content-Type' => 'text/html; charset=UTF-8',
            'Cache-Control' => 'private, no-store, max-age=0',
            'X-Robots-Tag' => 'noindex',
        ]);
        $event->setResponse($response);
    }

    /**
     * Read-only bridge used by the isolated-CI pre-action fixture. It returns
     * the same full-authentication, native READ, route and module predicate as
     * the exception handler; it does not grant or create a security token.
     */
    public function isAuthenticatedFacebookReadForIsolatedTest(Request $request): bool
    {
        return $this->isExactAuthenticatedFacebookRequest($request);
    }

    private function isExactAuthenticatedFacebookRead(ExceptionEvent $event): bool
    {
        return $this->isExactAuthenticatedFacebookRequest($event->getRequest());
    }

    private function isExactAuthenticatedFacebookRequest(Request $request): bool
    {
        if ($request->getMethod() !== 'GET'
            || $request->attributes->get('_route') !== self::FACEBOOK_ROUTE
            || $request->attributes->get('_controller')
                !== 'PrestaShopBundle\\Controller\\Admin\\LegacyController::legacyPageAction'
            || $request->attributes->get('_legacy_controller_class') !== self::FACEBOOK_CONTROLLER
            || $request->attributes->get('_legacy_controller_name') !== self::FACEBOOK_CONTROLLER_NAME
            || $request->attributes->get('_legacy_controller_action') !== self::FACEBOOK_ACTION
            || $request->attributes->get('_legacy_controller_is_module') !== true
            || $request->attributes->get('_anonymous_controller') !== false
            || !in_array('ps_facebook', $this->activeModules, true)) {
            return false;
        }

        $legacyController = $request->attributes->get('_legacy_controller_instance');
        if (!is_object($legacyController) || get_class($legacyController) !== self::FACEBOOK_CONTROLLER) {
            return false;
        }

        try {
            return $this->security->isGranted('IS_AUTHENTICATED_FULLY')
                && $this->security->isGranted(self::FACEBOOK_ACTION, self::FACEBOOK_CONTROLLER_NAME);
        } catch (\Throwable) {
            return false;
        }
    }

    private function isFacebookCurlTransportFailure(RuntimeException $failure): bool
    {
        // Current ps_facebook HttpClient throws this exact format from curl_exec failure.
        // Do not include the raw message in response or diagnostics.
        if (preg_match('/\AcURL error \([1-9][0-9]{0,2}\):\s+\S[^\r\n]*\z/D', $failure->getMessage()) !== 1) {
            return false;
        }

        $modulesRoot = realpath($this->modulesPath);
        $facebookRoot = realpath($this->modulesPath . DIRECTORY_SEPARATOR . 'ps_facebook');
        $httpClientFile = $facebookRoot === false
            ? false
            : realpath($facebookRoot . DIRECTORY_SEPARATOR . 'classes' . DIRECTORY_SEPARATOR . 'Http' . DIRECTORY_SEPARATOR . 'HttpClient.php');
        $thrownFrom = realpath($failure->getFile());
        if ($modulesRoot === false || $facebookRoot === false || dirname($facebookRoot) !== $modulesRoot
            || basename($facebookRoot) !== 'ps_facebook' || $httpClientFile === false
            || $thrownFrom === false || $thrownFrom !== $httpClientFile) {
            return false;
        }

        $expectedPrefix = 'PrestaShop\\Module\\PrestashopFacebook\\Http\\';
        if (!class_exists(self::FACEBOOK_HTTP_CLIENT)) {
            return false;
        }
        $reflection = new \ReflectionClass(self::FACEBOOK_HTTP_CLIENT);
        if ($reflection->getName() !== self::FACEBOOK_HTTP_CLIENT
            || realpath((string) $reflection->getFileName()) !== $httpClientFile
            || !str_starts_with(self::FACEBOOK_HTTP_CLIENT, $expectedPrefix)) {
            return false;
        }

        foreach ($failure->getTrace() as $frame) {
            if (($frame['class'] ?? null) === self::FACEBOOK_HTTP_CLIENT
                && ($frame['type'] ?? null) === '->'
                && in_array(($frame['function'] ?? null), ['get', 'request'], true)
                && isset($frame['file']) && realpath((string) $frame['file']) === $httpClientFile) {
                return true;
            }
        }

        return false;
    }
}
