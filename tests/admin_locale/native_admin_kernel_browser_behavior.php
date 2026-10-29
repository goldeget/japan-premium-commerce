<?php

declare(strict_types=1);

namespace Symfony\Component\HttpFoundation {
    class Request
    {
        public function __construct(
            private array $get,
            private array $post,
            private array $server,
            private array $cookie,
            private array $request
        ) {
        }

        public function overrideGlobals(): void
        {
            $_GET = $this->get;
            $_POST = $this->post;
            $_SERVER = $this->server;
            $_COOKIE = $this->cookie;
            $_REQUEST = $this->request;
            $_FILES = ['request_override' => 'must be restored'];
            $GLOBALS['native_browser_test_events'][] = 'override_globals';
        }
    }

    class Response
    {
    }
}

namespace Symfony\Bundle\FrameworkBundle {
    class KernelBrowser
    {
        public static int $parentDispatches = 0;
        public static bool $throwDuringDispatch = false;

        protected function doRequest(object $request): \Symfony\Component\HttpFoundation\Response
        {
            ++self::$parentDispatches;
            $GLOBALS['native_browser_test_events'][] = 'parent_dispatch';
            if (\Dispatcher::$request !== $request) {
                throw new \RuntimeException('legacy_request_not_synchronized');
            }
            if (self::$throwDuringDispatch) throw new \RuntimeException('synthetic_parent_failure');

            return new \Symfony\Component\HttpFoundation\Response();
        }
    }
}

namespace {
    class Dispatcher
    {
        public static ?object $request = null;

        public static function setRequest(object $request): void
        {
            self::$request = $request;
            $GLOBALS['native_browser_test_events'][] = 'set_dispatcher_request';
        }
    }

    require_once __DIR__ . '/native_admin_kernel_browser.php';

    $assert = static function (bool $condition, string $message): void {
        if (!$condition) {
            throw new RuntimeException($message);
        }
    };

    $browser = new class extends NativeAdminKernelBrowser {
        public function dispatch(object $request): \Symfony\Component\HttpFoundation\Response
        {
            return $this->doRequest($request);
        }
    };

    $_GET = ['before' => 'get'];
    $_POST = ['before' => 'post'];
    $_SERVER = ['before' => 'server'];
    $_COOKIE = ['before' => 'cookie'];
    $_REQUEST = ['before' => 'request'];
    $_FILES = ['before' => 'files'];
    $originalGlobals = [$_GET, $_POST, $_SERVER, $_COOKIE, $_REQUEST, $_FILES];
    $GLOBALS['native_browser_test_events'] = [];

    $getRequest = new \Symfony\Component\HttpFoundation\Request(
        ['method' => 'GET'], [], ['REQUEST_METHOD' => 'GET'], [], ['method' => 'GET']
    );
    $getResponse = $browser->dispatch($getRequest);
    $assert($getResponse instanceof \Symfony\Component\HttpFoundation\Response, 'GET dispatch response type');
    $assert(Dispatcher::$request === $getRequest, 'actual GET request passed to legacy Dispatcher');
    $assert(\Symfony\Bundle\FrameworkBundle\KernelBrowser::$parentDispatches === 1, 'GET reached parent kernel browser');
    $assert($GLOBALS['native_browser_test_events'] === ['override_globals', 'set_dispatcher_request', 'parent_dispatch'], 'GET bootstrap order');
    $assert([$_GET, $_POST, $_SERVER, $_COOKIE, $_REQUEST, $_FILES] === $originalGlobals, 'GET globals restored');

    $GLOBALS['native_browser_test_events'] = [];
    $postRequest = new \Symfony\Component\HttpFoundation\Request(
        [], ['csrf' => 'native-form-value'], ['REQUEST_METHOD' => 'POST'], ['session' => 'browser-cookie'], ['csrf' => 'native-form-value']
    );
    $postResponse = $browser->dispatch($postRequest);
    $assert($postResponse instanceof \Symfony\Component\HttpFoundation\Response, 'POST dispatch response type');
    $assert(Dispatcher::$request === $postRequest, 'actual POST request replaces previous Dispatcher request');
    $assert(\Symfony\Bundle\FrameworkBundle\KernelBrowser::$parentDispatches === 2, 'POST reached parent kernel browser');
    $assert($GLOBALS['native_browser_test_events'] === ['override_globals', 'set_dispatcher_request', 'parent_dispatch'], 'POST bootstrap order');
    $assert([$_GET, $_POST, $_SERVER, $_COOKIE, $_REQUEST, $_FILES] === $originalGlobals, 'POST globals restored');

    $GLOBALS['native_browser_test_events'] = [];
    try {
        $browser->dispatch(new \stdClass());
        throw new RuntimeException('wrong request was accepted');
    } catch (\UnexpectedValueException $error) {
        $assert($error->getMessage() === 'native_http_foundation_request_required', 'wrong request fail-closed code');
    }
    $assert(\Symfony\Bundle\FrameworkBundle\KernelBrowser::$parentDispatches === 2, 'wrong request failed before native parent dispatch');
    $assert($GLOBALS['native_browser_test_events'] === [], 'wrong request failed before global or Dispatcher mutation');
    $assert([$_GET, $_POST, $_SERVER, $_COOKIE, $_REQUEST, $_FILES] === $originalGlobals, 'wrong request preserves globals');

    \Symfony\Bundle\FrameworkBundle\KernelBrowser::$throwDuringDispatch = true;
    try {
        $browser->dispatch($postRequest);
        throw new RuntimeException('parent_failure_not_preserved');
    } catch (RuntimeException $error) {
        $assert($error->getMessage() === 'synthetic_parent_failure', 'parent failure preserved');
    }
    $assert([$_GET, $_POST, $_SERVER, $_COOKIE, $_REQUEST, $_FILES] === $originalGlobals, 'throwing parent restores all globals');
    echo "native admin BrowserKit handoff: ok\n";
}
