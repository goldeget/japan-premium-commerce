<?php

declare(strict_types=1);

require_once __DIR__ . '/native_admin_http_login.php';

if (!extension_loaded('curl') || !isset($argv[1])) {
    throw new RuntimeException('native_curl_behavior_prerequisite_missing');
}
$parts = parse_url($argv[1]);
if (!is_array($parts) || ($parts['scheme'] ?? null) !== 'http'
    || strtolower((string) ($parts['host'] ?? '')) !== '127.0.0.1'
    || !isset($parts['port']) || ($parts['path'] ?? null) !== '/probe'
    || isset($parts['user']) || isset($parts['pass']) || isset($parts['query']) || isset($parts['fragment'])) {
    throw new RuntimeException('native_curl_behavior_target_invalid');
}

$perform = static function (string $method, string $body) use ($argv): string {
    $handle = curl_init();
    if ($handle === false) throw new RuntimeException('native_curl_behavior_init_failed');
    try {
        $options = NativeAdminHttpCurlOptions::forRequest($method, $argv[1], $body);
        $options[CURLOPT_RETURNTRANSFER] = true;
        $options[CURLOPT_CONNECTTIMEOUT_MS] = 1000;
        $options[CURLOPT_TIMEOUT_MS] = 3000;
        $options[CURLOPT_PROXY] = '';
        $options[CURLOPT_NOPROXY] = '*';
        if (defined('CURLOPT_PROTOCOLS_STR')) {
            $options[CURLOPT_PROTOCOLS_STR] = 'http';
        } else {
            $options[CURLOPT_PROTOCOLS] = CURLPROTO_HTTP;
        }
        if (!curl_setopt_array($handle, $options)) throw new RuntimeException('native_curl_behavior_options_failed');
        $response = curl_exec($handle);
        if (!is_string($response) || curl_getinfo($handle, CURLINFO_RESPONSE_CODE) !== 200) {
            throw new RuntimeException('native_curl_behavior_response_failed');
        }
        return $response;
    } finally {
        curl_close($handle);
    }
};

if ($perform('GET', '') !== 'GET:') throw new RuntimeException('native_curl_get_method_mismatch');
if ($perform('POST', 'mode=probe') !== 'POST:mode=probe') throw new RuntimeException('native_curl_post_method_mismatch');
echo "native cURL request methods: ok\n";
