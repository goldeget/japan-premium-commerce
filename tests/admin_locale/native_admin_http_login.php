<?php

declare(strict_types=1);

/**
 * Authenticates through the real local Admin HTTP entry point before an
 * in-process AdminKernel request is made. Every raw cookie stays in memory.
 */
final class NativeAdminHttpLogin
{
    private const MAX_REDIRECTS = 6;
    public const MAX_COOKIES = 20;
    private const MAX_COOKIE_VALUE_BYTES = 4096;
    private static ?array $safeAuthLandingFacts = null;
    private static ?array $privateLastHttpResponse = null;

    /** Safe, fixed-schema diagnosis of the latest login POST landing. */
    public static function safeAuthLandingFacts(): ?array
    {
        return self::$safeAuthLandingFacts;
    }

    /** Raw response is available only in process for guarded encrypted CI capture. */
    public static function privateLastHttpResponse(): ?array
    {
        return self::$privateLastHttpResponse;
    }

    /**
     * @return array{login_form_posted: bool, final_uri: string, native_body_token: string, redirects: int, cookies: array<int, array{name: string, value: string, domain: string, path: string, expires: ?int, secure: bool, http_only: bool}>}
     */
    public static function authenticate(
        string $loginUri,
        string $email,
        string $password,
        callable $request,
        callable $cookieReader,
        callable $parseLoginForm,
        callable $hasLoginForm,
        callable $localAdminUri,
        ?callable $stageObserver = null
    ): array {
        self::$safeAuthLandingFacts = null;
        self::$privateLastHttpResponse = null;
        if ($stageObserver !== null) $stageObserver('native_login_get');
        $uri = $localAdminUri($loginUri, $loginUri);
        $response = $request('GET', $uri, null);
        self::rememberPrivateResponse($uri, $response);
        if ($stageObserver !== null) $stageObserver('native_login_get_redirects');
        $page = self::followRedirects($response, $uri, $request, $localAdminUri);
        if ($page['response']['status'] !== 200 || !is_string($page['response']['body'])) {
            throw new RuntimeException('native_http_login_page_unavailable');
        }

        $form = $parseLoginForm($page['response']['body']);
        if (!is_array($form) || !isset($form['action'], $form['fields'], $form['email_name'], $form['password_name'])
            || !is_array($form['fields']) || !is_string($form['email_name']) || !is_string($form['password_name'])) {
            throw new RuntimeException('native_http_login_form_contract_mismatch');
        }

        $postUri = $localAdminUri((string) $form['action'], $page['uri']);
        $fields = $form['fields'];
        $fields[$form['email_name']] = $email;
        $fields[$form['password_name']] = $password;
        if ($stageObserver !== null) $stageObserver('native_login_post');
        $postResponse = $request('POST', $postUri, $fields);
        if ($stageObserver !== null) $stageObserver('native_login_post_redirects');
        self::rememberPrivateResponse($postUri, $postResponse);
        if (!isset($postResponse['status'], $postResponse['body'])
            || !is_int($postResponse['status']) || $postResponse['status'] < 100 || $postResponse['status'] > 599
            || !is_string($postResponse['body'])) {
            throw new RuntimeException('native_http_response_contract_invalid');
        }
        $postLoginPage = (bool) $hasLoginForm($postResponse['body']);
        self::recordSafeAuthLandingFacts(
            $postResponse['status'], $postResponse['status'], $postUri, 0, $postResponse['body'], $postLoginPage
        );
        // PrestaShop's native authentication success handler answers the
        // credential POST with an HTTP 302. Do not treat a rendered 200 page as
        // proof of a successful login or use its session token.
        if ($postResponse['status'] !== 302) {
            throw new RuntimeException('native_http_login_post_status_not_302');
        }
        $authenticated = self::followRedirects($postResponse, $postUri, $request, $localAdminUri);
        $authenticatedLoginPage = (bool) $hasLoginForm($authenticated['response']['body']);
        self::recordSafeAuthLandingFacts(
            $postResponse['status'], $authenticated['response']['status'], $authenticated['uri'], $authenticated['redirects'],
            $authenticated['response']['body'], $authenticatedLoginPage
        );
        if ($authenticated['response']['status'] !== 200 || !is_string($authenticated['response']['body'])
            || $authenticatedLoginPage) {
            throw new RuntimeException('native_http_admin_authentication_not_established');
        }

        // Keep the token only in this in-memory result. The native Admin page
        // exposes the authenticated user's Symfony CSRF token on its body;
        // this avoids generating an empty token before BrowserKit has dispatched
        // a request and initialized the native session/security context.
        $nativeBodyToken = self::extractNativeBodyToken($authenticated['response']['body']);

        $cookies = self::validateCookies($cookieReader());
        if ($cookies === []) {
            throw new RuntimeException('native_http_login_session_cookie_missing');
        }

        return [
            'login_form_posted' => true,
            'final_uri' => $authenticated['uri'],
            'native_body_token' => $nativeBodyToken,
            'redirects' => $page['redirects'] + $authenticated['redirects'],
            'cookies' => $cookies,
        ];
    }

    /**
     * Extract the unique native body token from the authenticated Admin page.
     * The token format matches Symfony 6.4's masked URI-safe CSRF token. Raw
     * response HTML and the token are deliberately never written by this helper.
     */
    public static function extractNativeBodyToken(string $html): string
    {
        if (!class_exists(DOMDocument::class) || !class_exists(DOMXPath::class)
            || !defined('LIBXML_NONET') || !defined('LIBXML_NOERROR') || !defined('LIBXML_NOWARNING')
            || !defined('LIBXML_HTML_NOIMPLIED')) {
            throw new RuntimeException('native_http_dom_unavailable');
        }

        $previousLibxmlState = libxml_use_internal_errors(true);
        libxml_clear_errors();
        try {
            $document = new DOMDocument();
            if (!$document->loadHTML($html, LIBXML_NONET | LIBXML_NOERROR | LIBXML_NOWARNING | LIBXML_HTML_NOIMPLIED)) {
                throw new RuntimeException('native_http_authenticated_document_invalid');
            }
            $bodies = (new DOMXPath($document))->query('/html/body');
            if ($bodies === false || $bodies->length !== 1 || !$bodies->item(0) instanceof DOMElement) {
                throw new RuntimeException('native_http_authenticated_body_ambiguous');
            }

            $token = $bodies->item(0)->getAttribute('data-token');
            $tokenKind = self::classifyToken($token);
            if ($tokenKind === 'missing') {
                throw new RuntimeException('native_http_authenticated_body_token_missing');
            }
            if (!self::isSymfonyUriSafeToken($token)) {
                throw new RuntimeException('native_http_authenticated_body_token_invalid');
            }

            return $token;
        } finally {
            libxml_clear_errors();
            libxml_use_internal_errors($previousLibxmlState);
        }
    }

    /** Symfony 6.4 randomizes a URI-safe token into bounded, dot-separated pieces. */
    public static function isSymfonyUriSafeToken(string $token): bool
    {
        return preg_match('/\A[A-Za-z0-9_-]{1,32}\.[A-Za-z0-9_-]{43}\.[A-Za-z0-9_-]{43,256}\z/D', $token) === 1;
    }

    /** @return array<string, int|string> */
    private static function safeAuthLandingFactDefaults(
        int $postStatus,
        int $finalStatus,
        string $uri,
        int $redirectCount,
        string $body,
        bool $loginPage
    ): array
    {
        $controller = self::safeControllerKind($uri);
        $bodyPage = self::safeBodyPageKind($body, $loginPage);
        $path = self::safePathKind($uri, $bodyPage);
        return [
            'post_status' => $postStatus,
            'redirect_count' => $redirectCount,
            'final_status' => $finalStatus,
            'final_path_kind' => $path,
            'final_controller_kind' => $controller,
            'redirect_token_kind' => self::safeUriTokenKind($uri),
            'body_token_kind' => self::safeBodyTokenKind($body),
            'body_page_kind' => $bodyPage,
        ];
    }

    private static function recordSafeAuthLandingFacts(
        int $postStatus,
        int $finalStatus,
        string $uri,
        int $redirectCount,
        string $body,
        bool $loginPage
    ): void {
        self::$safeAuthLandingFacts = self::safeAuthLandingFactDefaults(
            $postStatus, $finalStatus, $uri, $redirectCount, $body, $loginPage
        );
    }

    private static function rememberPrivateResponse(string $uri, mixed $response): void
    {
        self::$privateLastHttpResponse = null;
        if (!is_array($response) || !isset($response['status'], $response['body'])
            || !is_int($response['status']) || $response['status'] < 100 || $response['status'] > 599
            || !is_string($response['body']) || strlen($response['body']) > 8 * 1024 * 1024
            || strlen($uri) > 8192 || !str_starts_with($uri, '/admin-kuranea')) {
            return;
        }
        self::$privateLastHttpResponse = [
            'status' => $response['status'],
            'request_uri' => $uri,
            'body' => $response['body'],
        ];
    }

    private static function safeControllerKind(string $uri): string
    {
        $query = parse_url($uri, PHP_URL_QUERY);
        if (!is_string($query)) return 'none';
        parse_str($query, $parameters);
        $controller = $parameters['controller'] ?? null;
        if (!is_string($controller) || $controller === '') return 'none';
        if ($controller === 'AdminLogin') return 'login';
        if ($controller === 'AdminDashboard') return 'dashboard';
        return 'other';
    }

    private static function safePathKind(string $uri, string $bodyPage): string
    {
        if ($bodyPage === 'login' || self::safeControllerKind($uri) === 'login') return 'login';
        $path = parse_url($uri, PHP_URL_PATH);
        if (is_string($path) && preg_match('~\A/admin-kuranea(?:/index\.php)?/?\z~D', $path)) return 'index';
        return 'other_admin';
    }

    private static function safeUriTokenKind(string $uri): string
    {
        $query = parse_url($uri, PHP_URL_QUERY);
        if (!is_string($query)) return 'missing';
        $tokens = [];
        foreach (explode('&', $query) as $field) {
            [$key, $value] = array_pad(explode('=', $field, 2), 2, '');
            $decodedKey = rawurldecode(str_replace('+', ' ', $key));
            if (in_array($decodedKey, ['_token', 'token'], true)) {
                $tokens[] = rawurldecode(str_replace('+', ' ', $value));
            }
        }
        if ($tokens === []) return 'missing';
        if (count($tokens) !== 1) return 'other';
        return self::classifyToken($tokens[0]);
    }

    private static function safeBodyPageKind(string $html, bool $loginForm): string
    {
        if ($loginForm) return 'login';
        if (!class_exists(DOMDocument::class) || !class_exists(DOMXPath::class)) return 'other';
        $previousLibxmlState = libxml_use_internal_errors(true);
        libxml_clear_errors();
        try {
            $document = new DOMDocument();
            if (!$document->loadHTML($html, LIBXML_NONET | LIBXML_NOERROR | LIBXML_NOWARNING | LIBXML_HTML_NOIMPLIED)) return 'other';
            $securityWarning = (new DOMXPath($document))->query('//*[@id="security-compromised-page"]');
            if ($securityWarning !== false && $securityWarning->length === 1) return 'security_warning';
            $bodies = (new DOMXPath($document))->query('/html/body');
            if ($bodies === false || $bodies->length !== 1 || !$bodies->item(0) instanceof DOMElement) return 'other';
            $classes = preg_split('/\s+/', strtolower(trim($bodies->item(0)->getAttribute('class'))), -1, PREG_SPLIT_NO_EMPTY);
            if (!is_array($classes)) return 'other';
            $isLogin = (bool) array_intersect($classes, [
                'login', 'adminlogin', 'page-login', 'admin-login', 'admin_login', 'page-admin-login',
                'page-adminlogin', 'controller-admin-login', 'controller-adminlogin',
            ]);
            $isDashboard = (bool) array_intersect($classes, [
                'dashboard', 'admindashboard', 'page-dashboard', 'admin-dashboard', 'admin_dashboard',
                'page-admin-dashboard', 'page-admindashboard', 'controller-admin-dashboard',
                'controller-admindashboard',
            ]);
            if ($isLogin === $isDashboard) return 'other';
            return $isLogin ? 'login' : 'dashboard';
        } catch (Throwable) {
            return 'other';
        } finally {
            libxml_clear_errors();
            libxml_use_internal_errors($previousLibxmlState);
        }
    }

    private static function safeBodyTokenKind(string $html): string
    {
        if (!class_exists(DOMDocument::class) || !class_exists(DOMXPath::class)) return 'other';
        $previousLibxmlState = libxml_use_internal_errors(true);
        libxml_clear_errors();
        try {
            $document = new DOMDocument();
            if (!$document->loadHTML($html, LIBXML_NONET | LIBXML_NOERROR | LIBXML_NOWARNING | LIBXML_HTML_NOIMPLIED)) return 'other';
            $bodies = (new DOMXPath($document))->query('/html/body');
            if ($bodies === false || $bodies->length !== 1 || !$bodies->item(0) instanceof DOMElement) return 'other';
            $body = $bodies->item(0);
            if (!$body->hasAttribute('data-token')) return 'missing';
            return self::classifyToken($body->getAttribute('data-token'));
        } catch (Throwable) {
            return 'other';
        } finally {
            libxml_clear_errors();
            libxml_use_internal_errors($previousLibxmlState);
        }
    }

    private static function classifyToken(string $token): string
    {
        if ($token === '') return 'missing';
        if (self::isSymfonyUriSafeToken($token)) return 'masked';
        if (preg_match('/\A[a-f0-9]{32}\z/iD', $token)) return 'plain_hex32';
        if (preg_match('/\A[A-Za-z0-9_-]{20,128}\z/D', $token)) return 'plain_uri_safe';
        return 'other';
    }

    /**
     * Validate cookie records before placing them into PHP globals or a
     * BrowserKit CookieJar. This method intentionally accepts localhost only.
     *
     * @return array<int, array{name: string, value: string, domain: string, path: string, expires: ?int, secure: bool, http_only: bool}>
     */
    public static function validateCookies(mixed $cookies): array
    {
        if (!is_array($cookies) || count($cookies) < 1 || count($cookies) > self::MAX_COOKIES) {
            throw new RuntimeException('native_http_cookie_inventory_invalid');
        }

        $validated = [];
        foreach ($cookies as $cookie) {
            if (!is_array($cookie)
                || !isset($cookie['name'], $cookie['value'], $cookie['domain'], $cookie['path'])
                || !is_string($cookie['name']) || !is_string($cookie['value'])
                || !is_string($cookie['domain']) || !is_string($cookie['path'])
                || !preg_match('/\A[!#$%&\'*+.^_`|~0-9A-Za-z-]{1,128}\z/D', $cookie['name'])
                || $cookie['value'] === '' || strlen($cookie['value']) > self::MAX_COOKIE_VALUE_BYTES
                || preg_match('/[\r\n;]/', $cookie['value'])
                || !in_array(strtolower(ltrim($cookie['domain'], '.')), ['localhost'], true)
                || ($cookie['path'] !== '/' && !preg_match('~\A/admin-kuranea(?:/|\z)~D', $cookie['path']))
                || str_contains($cookie['path'], '\\') || preg_match('~(?:\A|/)\.\.?(/|\z)|%2e|%2f|%5c~i', $cookie['path'])
                || (isset($cookie['expires']) && $cookie['expires'] !== null && (!is_int($cookie['expires']) || $cookie['expires'] < 0))
                || (isset($cookie['secure']) && !is_bool($cookie['secure']))
                || (isset($cookie['http_only']) && !is_bool($cookie['http_only']))) {
                throw new RuntimeException('native_http_cookie_scope_invalid');
            }

            $domain = strtolower(ltrim($cookie['domain'], '.'));
            $validated[] = [
                'name' => $cookie['name'],
                'value' => $cookie['value'],
                'domain' => $domain,
                'path' => $cookie['path'],
                'expires' => $cookie['expires'] ?? null,
                'secure' => $cookie['secure'] ?? false,
                'http_only' => $cookie['http_only'] ?? false,
            ];
        }

        return $validated;
    }

    /**
     * Select cookies applicable to a canonical local admin URI for $_COOKIE.
     * BrowserKit still receives the full scoped cookies through its CookieJar.
     *
     * @param array<int, array{name: string, value: string, domain: string, path: string, expires: ?int, secure: bool, http_only: bool}> $cookies
     * @return array<string, string>
     */
    public static function globalsForUri(array $cookies, string $uri): array
    {
        $path = parse_url($uri, PHP_URL_PATH);
        if (!is_string($path) || !preg_match('~\A/admin-kuranea(?:/|\z)~D', $path)) {
            throw new RuntimeException('native_http_cookie_target_invalid');
        }

        $applicable = [];
        foreach (self::validateCookies($cookies) as $cookie) {
            if ($cookie['secure'] || ($cookie['expires'] !== null && $cookie['expires'] > 0 && $cookie['expires'] <= time())) {
                continue;
            }
            $cookiePath = $cookie['path'];
            if ($cookiePath !== '/' && $path !== $cookiePath
                && !str_starts_with($path, rtrim($cookiePath, '/') . '/')) {
                continue;
            }
            if (!array_key_exists($cookie['name'], $applicable) || strlen($cookiePath) > $applicable[$cookie['name']]['path_length']) {
                $applicable[$cookie['name']] = [
                    // PHP cookie parsing uses raw URL decoding, so a literal plus
                    // remains a plus while %2B becomes the plus character.
                    'value' => rawurldecode($cookie['value']),
                    'path_length' => strlen($cookiePath),
                ];
            }
        }

        $values = [];
        foreach ($applicable as $name => $cookie) {
            $values[$name] = $cookie['value'];
        }
        return $values;
    }

    /**
     * Install raw cookie records in a Symfony BrowserKit CookieJar while
     * preserving the original encoded value and path/domain scope.
     *
     * @param array<int, array{name: string, value: string, domain: string, path: string, expires: ?int, secure: bool, http_only: bool}> $cookies
     */
    public static function installInBrowserKit(object $cookieJar, array $cookies): void
    {
        if (!method_exists($cookieJar, 'set') || !class_exists(\Symfony\Component\BrowserKit\Cookie::class)) {
            throw new RuntimeException('native_http_cookie_jar_unavailable');
        }
        foreach (self::validateCookies($cookies) as $cookie) {
            $cookieJar->set(new \Symfony\Component\BrowserKit\Cookie(
                $cookie['name'],
                $cookie['value'],
                $cookie['expires'],
                $cookie['path'],
                $cookie['domain'],
                $cookie['secure'],
                $cookie['http_only'],
                true
            ));
        }
    }

    /**
     * @param array{status: int, location?: string|null, body: string} $response
     * @return array{response: array{status: int, location?: string|null, body: string}, uri: string, redirects: int}
     */
    private static function followRedirects(array $response, string $uri, callable $request, callable $localAdminUri): array
    {
        $redirects = 0;
        while (in_array($response['status'] ?? null, [301, 302, 303], true)) {
            if ($redirects >= self::MAX_REDIRECTS) {
                throw new RuntimeException('native_http_login_redirect_limit');
            }
            $location = $response['location'] ?? null;
            if (!is_string($location) || $location === '') {
                throw new RuntimeException('native_http_login_redirect_location_missing');
            }
            $uri = $localAdminUri($location, $uri);
            $response = $request('GET', $uri, null);
            self::rememberPrivateResponse($uri, $response);
            ++$redirects;
        }

        if (!isset($response['status'], $response['body']) || !is_int($response['status']) || !is_string($response['body'])) {
            throw new RuntimeException('native_http_response_contract_invalid');
        }

        return ['response' => $response, 'uri' => $uri, 'redirects' => $redirects];
    }
}

/** Ordered cURL method options: libcurl's last method/body option wins. */
final class NativeAdminHttpCurlOptions
{
    /** @return array<int, mixed> */
    public static function forRequest(string $method, string $url, string $formBody = ''): array
    {
        $parts = parse_url($url);
        if (!is_array($parts) || ($parts['scheme'] ?? null) !== 'http'
            || !in_array(strtolower((string) ($parts['host'] ?? '')), ['localhost', '127.0.0.1'], true)
            || !isset($parts['port']) || $parts['port'] < 1 || $parts['port'] > 65535
            || isset($parts['user']) || isset($parts['pass']) || isset($parts['fragment'])) {
            throw new RuntimeException('native_loopback_method_url_invalid');
        }
        $options = [CURLOPT_URL => $url];
        if ($method === 'GET') {
            // Clear any prior POST body first, then make HTTPGET the final
            // method-setting option so cURL cannot silently retain POST.
            $options[CURLOPT_POSTFIELDS] = null;
            $options[CURLOPT_POST] = false;
            $options[CURLOPT_HTTPGET] = true;
            return $options;
        }
        if ($method === 'POST') {
            $options[CURLOPT_HTTPGET] = false;
            $options[CURLOPT_POST] = true;
            $options[CURLOPT_POSTFIELDS] = $formBody;
            return $options;
        }
        throw new RuntimeException('native_loopback_method_invalid');
    }
}

/**
 * Small fixed-destination cURL client for the disposable local Admin HTTP
 * server. It never follows redirects, logs bodies, or writes a cookie jar.
 */
final class NativeAdminHttpCurlTransport
{
    private const MAX_RESPONSE_BYTES = 2_097_152;
    private const MAX_FORM_BYTES = 65_536;

    /** @var resource|object */
    private $handle;
    private string $responseBody = '';
    private ?string $responseLocation = null;
    private int $locationCount = 0;
    private int $requestCount = 0;

    public function __construct()
    {
        if (!extension_loaded('curl') || !defined('CURLOPT_CONNECT_TO') || !defined('CURLINFO_COOKIELIST')) {
            throw new RuntimeException('native_loopback_curl_unavailable');
        }
        $handle = curl_init();
        if ($handle === false) {
            throw new RuntimeException('native_loopback_curl_init_failed');
        }
        $this->handle = $handle;
        $optionsSet = curl_setopt_array($this->handle, [
            CURLOPT_CONNECT_TO => ['localhost:18081:127.0.0.1:80'],
            CURLOPT_COOKIEFILE => '',
            CURLOPT_FOLLOWLOCATION => false,
            CURLOPT_CONNECTTIMEOUT_MS => 2000,
            CURLOPT_TIMEOUT_MS => 20000,
            CURLOPT_MAXREDIRS => 0,
            CURLOPT_PROXY => '',
            CURLOPT_NOPROXY => 'localhost,127.0.0.1',
            CURLOPT_HTTPHEADER => [
                'Host: localhost:18081',
                'Accept: text/html,application/xhtml+xml',
                'User-Agent: ORDENOWA-isolated-ci-native-admin-login',
            ],
            CURLOPT_HEADERFUNCTION => function ($handle, string $line): int {
                $length = strlen($line);
                $normalized = trim($line, "\r\n");
                if (preg_match('~\AHTTP/[0-9.]+ [0-9]{3}(?:\s|\z)~i', $normalized)) {
                    $this->responseLocation = null;
                    $this->locationCount = 0;
                    return $length;
                }
                $separator = strpos($normalized, ':');
                if ($separator !== false && strtolower(trim(substr($normalized, 0, $separator))) === 'location') {
                    ++$this->locationCount;
                    $this->responseLocation = trim(substr($normalized, $separator + 1));
                }
                return $length;
            },
            CURLOPT_WRITEFUNCTION => function ($handle, string $chunk): int {
                $length = strlen($chunk);
                if (strlen($this->responseBody) + $length > self::MAX_RESPONSE_BYTES) {
                    return 0;
                }
                $this->responseBody .= $chunk;
                return $length;
            },
        ]);
        if (!$optionsSet) {
            curl_close($this->handle);
            throw new RuntimeException('native_loopback_curl_options_failed');
        }
        if (defined('CURLOPT_PROTOCOLS_STR')) {
            if (!curl_setopt($this->handle, CURLOPT_PROTOCOLS_STR, 'http')) {
                $this->close();
                throw new RuntimeException('native_loopback_curl_protocol_guard_failed');
            }
        } elseif (defined('CURLOPT_PROTOCOLS')) {
            if (!curl_setopt($this->handle, CURLOPT_PROTOCOLS, CURLPROTO_HTTP)) {
                $this->close();
                throw new RuntimeException('native_loopback_curl_protocol_guard_failed');
            }
        }
    }

    /** @return array{status: int, location?: string|null, body: string} */
    public function request(string $method, string $uri, ?array $formFields = null): array
    {
        if (!in_array($method, ['GET', 'POST'], true) || !self::isLocalAdminUri($uri)) {
            throw new RuntimeException('native_loopback_request_out_of_scope');
        }
        $formBody = '';
        if ($method === 'POST') {
            if (!is_array($formFields) || count($formFields) > 100) {
                throw new RuntimeException('native_loopback_form_invalid');
            }
            foreach ($formFields as $key => $value) {
                if (!is_string($key) || (!is_string($value) && !is_int($value) && !is_float($value))) {
                    throw new RuntimeException('native_loopback_form_invalid');
                }
            }
            $formBody = http_build_query($formFields, '', '&', PHP_QUERY_RFC3986);
            if (strlen($formBody) > self::MAX_FORM_BYTES) {
                throw new RuntimeException('native_loopback_form_too_large');
            }
        } elseif ($formFields !== null) {
            throw new RuntimeException('native_loopback_get_form_invalid');
        }

        $this->responseBody = '';
        $this->responseLocation = null;
        $this->locationCount = 0;
        ++$this->requestCount;
        $optionsSet = curl_setopt_array(
            $this->handle,
            NativeAdminHttpCurlOptions::forRequest($method, 'http://localhost:18081' . $uri, $formBody)
        );
        if (!$optionsSet) {
            throw new RuntimeException('native_loopback_request_options_failed');
        }
        $result = curl_exec($this->handle);
        if ($result === false || $this->locationCount > 1) {
            throw new RuntimeException('native_loopback_request_failed');
        }
        $status = (int) curl_getinfo($this->handle, CURLINFO_RESPONSE_CODE);
        if ($status < 100 || $status > 599) {
            throw new RuntimeException('native_loopback_response_status_invalid');
        }

        return [
            'status' => $status,
            'location' => $this->responseLocation,
            'body' => $this->responseBody,
        ];
    }

    /** @return array<int, array{name: string, value: string, domain: string, path: string, expires: ?int, secure: bool, http_only: bool}> */
    public function cookies(): array
    {
        $lines = curl_getinfo($this->handle, CURLINFO_COOKIELIST);
        if (!is_array($lines) || count($lines) > NativeAdminHttpLogin::MAX_COOKIES) {
            throw new RuntimeException('native_loopback_cookie_jar_unavailable');
        }
        $cookies = [];
        foreach ($lines as $line) {
            if (!is_string($line)) {
                throw new RuntimeException('native_loopback_cookie_record_invalid');
            }
            $httpOnly = false;
            if (str_starts_with($line, '#HttpOnly_')) {
                $httpOnly = true;
                $line = substr($line, strlen('#HttpOnly_'));
            } elseif ($line === '' || $line[0] === '#') {
                continue;
            }
            $parts = explode("\t", $line);
            if (count($parts) !== 7) {
                throw new RuntimeException('native_loopback_cookie_record_invalid');
            }
            [$domain, $includeSubdomains, $path, $secure, $expires, $name, $value] = $parts;
            if (!in_array($includeSubdomains, ['TRUE', 'FALSE'], true)
                || !in_array($secure, ['TRUE', 'FALSE'], true)
                || !preg_match('/\A[0-9]{1,12}\z/D', $expires)) {
                throw new RuntimeException('native_loopback_cookie_record_invalid');
            }
            $cookies[] = [
                'domain' => $domain,
                'path' => $path,
                'expires' => (int) $expires > 0 ? (int) $expires : null,
                'name' => $name,
                'value' => $value,
                'secure' => $secure === 'TRUE',
                'http_only' => $httpOnly,
            ];
        }
        return NativeAdminHttpLogin::validateCookies($cookies);
    }

    public function close(): void
    {
        if (is_object($this->handle) || is_resource($this->handle)) {
            curl_close($this->handle);
        }
    }

    public function requestCount(): int
    {
        return $this->requestCount;
    }

    private static function isLocalAdminUri(string $uri): bool
    {
        $parts = parse_url($uri);
        if (!is_array($parts) || isset($parts['scheme']) || isset($parts['host']) || isset($parts['user']) || isset($parts['pass'])
            || isset($parts['fragment']) || !isset($parts['path'])) {
            return false;
        }
        $path = (string) $parts['path'];
        return !str_contains($path, '\\')
            && !preg_match('~(?:\A|/)\.\.?(/|\z)|%2e|%2f|%5c~i', $path)
            && preg_match('~\A/admin-kuranea(?:/|\z)~D', $path) === 1;
    }
}
