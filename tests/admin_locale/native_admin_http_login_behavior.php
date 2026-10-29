<?php

declare(strict_types=1);

namespace Symfony\Component\BrowserKit {
    class Cookie
    {
        public array $arguments;

        public function __construct(...$arguments)
        {
            $this->arguments = $arguments;
        }
    }
}

namespace {
    foreach ([
        'CURLOPT_URL' => 10001,
        'CURLOPT_POSTFIELDS' => 10002,
        'CURLOPT_POST' => 10003,
        'CURLOPT_HTTPGET' => 10004,
    ] as $name => $value) {
        if (!defined($name)) define($name, $value);
    }
    require_once __DIR__ . '/native_admin_http_login.php';

    $assert = static function (bool $condition, string $message): void {
        if (!$condition) {
            throw new RuntimeException($message);
        }
    };

    $localAdminUri = static function (string $candidate, string $baseUri): string {
        $parts = parse_url($candidate);
        if (!is_array($parts) || isset($parts['user']) || isset($parts['pass']) || isset($parts['fragment'])) {
            throw new RuntimeException('mock_unsafe_uri');
        }
        if (isset($parts['scheme']) || isset($parts['host'])) {
            if (($parts['scheme'] ?? '') !== 'http' || strtolower((string) ($parts['host'] ?? '')) !== 'localhost'
                || (int) ($parts['port'] ?? 80) !== 18081) {
                throw new RuntimeException('mock_nonlocal_uri');
            }
        }
        $path = (string) ($parts['path'] ?? '');
        if ($path === '') {
            $base = parse_url($baseUri);
            $path = is_array($base) ? (string) ($base['path'] ?? '') : '';
        } elseif (!str_starts_with($path, '/')) {
            $base = parse_url($baseUri);
            $basePath = is_array($base) ? (string) ($base['path'] ?? '/') : '/';
            $baseDirectory = str_ends_with($basePath, '/') ? rtrim($basePath, '/') : dirname($basePath);
            $path = rtrim($baseDirectory, '/') . '/' . $path;
        }
        if (!preg_match('~\A/admin-kuranea(?:/|\z)~D', $path) || str_contains($path, '\\')) {
            throw new RuntimeException('mock_admin_path_out_of_scope');
        }
        return $path . (isset($parts['query']) ? '?' . $parts['query'] : '');
    };

    $requests = [];
    $request = static function (string $method, string $uri, ?array $fields) use (&$requests): array {
        $requests[] = [$method, $uri, $fields];
        if ($method === 'GET' && $uri === '/admin-kuranea/') {
            return ['status' => 200, 'body' => 'LOGIN_FORM'];
        }
        if ($method === 'POST' && $uri === '/admin-kuranea/login') {
            return ['status' => 303, 'location' => 'http://localhost:18081/admin-kuranea/index.php?controller=AdminDashboard', 'body' => ''];
        }
        if ($method === 'GET' && $uri === '/admin-kuranea/index.php?controller=AdminDashboard') {
            return ['status' => 200, 'body' => 'AUTHENTICATED_DASHBOARD'];
        }
        throw new RuntimeException('mock_request_out_of_contract');
    };
    $cookieReader = static fn (): array => [[
        'name' => 'AdminSession', 'value' => 'raw%2Bsession', 'domain' => 'localhost',
        'path' => '/admin-kuranea', 'expires' => null, 'secure' => false, 'http_only' => true,
    ], [
        'name' => 'LiteralPlus', 'value' => 'left+right', 'domain' => 'localhost',
        'path' => '/admin-kuranea', 'expires' => null, 'secure' => false, 'http_only' => false,
    ]];
    $parseLoginForm = static function (string $body): ?array {
        return $body === 'LOGIN_FORM'
            ? ['action' => 'login', 'fields' => ['token' => 'native-csrf'], 'email_name' => 'email', 'password_name' => 'passwd']
            : null;
    };
    $hasLoginForm = static fn (string $body): bool => $body === 'LOGIN_FORM';

    $login = NativeAdminHttpLogin::authenticate(
        '/admin-kuranea/', 'ci-admin@example.invalid', 'synthetic-password',
        $request, $cookieReader, $parseLoginForm, $hasLoginForm, $localAdminUri
    );
    $assert($login['login_form_posted'] === true, 'native form POST proof');
    $assert($login['final_uri'] === '/admin-kuranea/index.php?controller=AdminDashboard', 'same-admin final redirect');
    $assert($login['redirects'] === 1, 'redirect count');
    $assert(count($requests) === 3, 'one GET, one form POST, one validated redirect GET');
    $assert($requests[1][0] === 'POST' && $requests[1][2] === [
        'token' => 'native-csrf', 'email' => 'ci-admin@example.invalid', 'passwd' => 'synthetic-password',
    ], 'hidden CSRF/form fields preserved with real login credentials');

    $getMethodOptions = NativeAdminHttpCurlOptions::forRequest('GET', 'http://127.0.0.1:18080/probe');
    $assert(array_keys($getMethodOptions) === [CURLOPT_URL, CURLOPT_POSTFIELDS, CURLOPT_POST, CURLOPT_HTTPGET]
        && $getMethodOptions[CURLOPT_POSTFIELDS] === null
        && $getMethodOptions[CURLOPT_POST] === false
        && $getMethodOptions[CURLOPT_HTTPGET] === true,
        'GET explicitly clears POST state and makes HTTPGET the final method option');
    $postMethodOptions = NativeAdminHttpCurlOptions::forRequest('POST', 'http://127.0.0.1:18080/probe', 'mode=probe');
    $assert(array_keys($postMethodOptions) === [CURLOPT_URL, CURLOPT_HTTPGET, CURLOPT_POST, CURLOPT_POSTFIELDS]
        && $postMethodOptions[CURLOPT_HTTPGET] === false
        && $postMethodOptions[CURLOPT_POST] === true
        && $postMethodOptions[CURLOPT_POSTFIELDS] === 'mode=probe',
        'POST sets body only after selecting POST method');
    try {
        NativeAdminHttpCurlOptions::forRequest('GET', 'https://example.com/probe');
        throw new RuntimeException('nonlocal cURL URL was accepted');
    } catch (RuntimeException $error) {
        $assert($error->getMessage() === 'native_loopback_method_url_invalid', 'nonlocal cURL URL rejected');
    }

    $globals = NativeAdminHttpLogin::globalsForUri($login['cookies'], '/admin-kuranea/index.php/mbo/themes/catalog');
    $assert($globals === ['AdminSession' => 'raw+session', 'LiteralPlus' => 'left+right'],
        'cookie values use PHP raw URL decoding semantics and path scope');
    $scopedCookies = $login['cookies'];
    $scopedCookies[] = [
        'name' => 'NotForAdmin', 'value' => 'ignored', 'domain' => 'localhost',
        'path' => '/admin-kuranea/other', 'expires' => null, 'secure' => false, 'http_only' => false,
    ];
    $cookieJar = new class {
        public array $values = [];
        public function set(object $cookie): void { $this->values[] = $cookie; }
    };
    NativeAdminHttpLogin::installInBrowserKit($cookieJar, $scopedCookies);
    $assert(count($cookieJar->values) === 3, 'scoped cookie records installed in BrowserKit');
    $assert($cookieJar->values[0] instanceof \Symfony\Component\BrowserKit\Cookie, 'BrowserKit Cookie created');
    $assert($cookieJar->values[0]->arguments[1] === 'raw%2Bsession' && $cookieJar->values[0]->arguments[7] === true,
        'raw cookie value preserved as already encoded');
    $assert($cookieJar->values[1]->arguments[1] === 'left+right' && $cookieJar->values[1]->arguments[7] === true,
        'literal plus is preserved in the Cookie header representation');

    try {
        NativeAdminHttpLogin::validateCookies([[
            'name' => 'Session', 'value' => 'secret', 'domain' => 'evil.example', 'path' => '/',
            'expires' => null, 'secure' => false, 'http_only' => true,
        ]]);
        throw new RuntimeException('nonlocal cookie was accepted');
    } catch (RuntimeException $error) {
        $assert($error->getMessage() === 'native_http_cookie_scope_invalid', 'nonlocal cookie rejected');
    }

    $redirectRequests = 0;
    $redirectLoop = static function (string $method, string $uri, ?array $fields) use (&$redirectRequests): array {
        ++$redirectRequests;
        return ['status' => 302, 'location' => '/admin-kuranea/loop', 'body' => ''];
    };
    try {
        NativeAdminHttpLogin::authenticate(
            '/admin-kuranea/', 'unused', 'unused', $redirectLoop, $cookieReader,
            $parseLoginForm, $hasLoginForm, $localAdminUri
        );
        throw new RuntimeException('redirect loop was accepted');
    } catch (RuntimeException $error) {
        $assert($error->getMessage() === 'native_http_login_redirect_limit', 'redirect loop bounded');
    }
    $assert($redirectRequests === 7, 'redirect limit sends no eighth request');

    $externalRequests = 0;
    $externalRedirect = static function (string $method, string $uri, ?array $fields) use (&$externalRequests): array {
        ++$externalRequests;
        return ['status' => 302, 'location' => 'https://evil.example/admin-kuranea/login', 'body' => ''];
    };
    try {
        NativeAdminHttpLogin::authenticate(
            '/admin-kuranea/', 'unused', 'unused', $externalRedirect, $cookieReader,
            $parseLoginForm, $hasLoginForm, $localAdminUri
        );
        throw new RuntimeException('external redirect was accepted');
    } catch (RuntimeException $error) {
        $assert($error->getMessage() === 'mock_nonlocal_uri', 'external redirect rejected before request');
    }
    $assert($externalRequests === 1, 'external redirect produced no outbound request');

    echo "native HTTP admin login flow: ok\n";
}
