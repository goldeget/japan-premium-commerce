<?php

declare(strict_types=1);

use Symfony\Bundle\FrameworkBundle\KernelBrowser;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Runs the actual native AdminKernel with the same legacy-request handoff as
 * admin-dev/index.php. BrowserKit's in-process transport builds a Request and
 * calls HttpKernel directly; it does not populate PHP's superglobals or call
 * Dispatcher::setRequest() like the production front controller does.
 *
 * This adapter only synchronizes the real BrowserKit request for the duration
 * of the native kernel dispatch. It does not assign employee, shop, or auth
 * context and restores the caller's globals even when dispatch throws.
 */
class NativeAdminKernelBrowser extends KernelBrowser
{
    public int $nativeRequestCount = 0;

    protected function doRequest(object $request): Response
    {
        if (!$request instanceof Request) {
            throw new UnexpectedValueException('native_http_foundation_request_required');
        }
        ++$this->nativeRequestCount;

        $previousGet = $_GET;
        $previousPost = $_POST;
        $previousServer = $_SERVER;
        $previousCookie = $_COOKIE;
        $previousRequest = $_REQUEST;
        $previousFiles = $_FILES;

        try {
            $request->overrideGlobals();
            Dispatcher::setRequest($request);

            return parent::doRequest($request);
        } finally {
            $_GET = $previousGet;
            $_POST = $previousPost;
            $_SERVER = $previousServer;
            $_COOKIE = $previousCookie;
            $_REQUEST = $previousRequest;
            $_FILES = $previousFiles;
        }
    }
}
