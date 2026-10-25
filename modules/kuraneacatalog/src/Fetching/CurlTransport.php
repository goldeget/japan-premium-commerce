<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Fetching;

/** HTTPS GET transport. Standard cURL proxy environment/configuration is kept. */
final class CurlTransport implements TransportInterface
{
    /** Safe classification also works in offline tests without ext-curl. */
    public static function assertProxyTunnelAllowed(int $connectStatus): void
    {
        if (in_array($connectStatus, [403, 407], true)) {
            throw new FetchException('Marketplace access was blocked.', FetchException::FAILURE_ACCESS_BLOCKED);
        }
    }

    /** Named options are inspectable offline, including on hosts without ext-curl. */
    public static function securityOptions(FetchRequest $request): array
    {
        $target = ProductUrlPolicy::canonicalize($request->canonicalUrl);
        $addresses = PublicAddressPolicy::validate($request->addresses);
        if ($target['url'] !== $request->canonicalUrl || $request->timeoutSeconds <= 0
            || !is_finite($request->timeoutSeconds) || $request->connectTimeoutSeconds <= 0
            || !is_finite($request->connectTimeoutSeconds) || $request->maxDecodedBytes < 1
            || $request->maxDecodedBytes > PublicProductFetcher::MAX_DECODED_BYTES) {
            throw new FetchException('Invalid product transport request.');
        }
        $address = str_contains($addresses[0], ':') ? '[' . $addresses[0] . ']' : $addresses[0];
        return [
            'CURLOPT_URL' => $request->canonicalUrl,
            'CURLOPT_HTTPGET' => true,
            'CURLOPT_FOLLOWLOCATION' => false,
            'CURLOPT_MAXREDIRS' => 0,
            'CURLOPT_SSL_VERIFYPEER' => true,
            'CURLOPT_SSL_VERIFYHOST' => 2,
            'CURLOPT_PROXY_SSL_VERIFYPEER' => true,
            'CURLOPT_PROXY_SSL_VERIFYHOST' => 2,
            // CONNECT_TO pins the tunnel destination with HTTP/SOCKS proxies;
            // RESOLVE alone would still permit a proxy to resolve the URL host.
            // TLS SNI, hostname verification and Host remain the original host.
            'CURLOPT_CONNECT_TO' => [$target['host'] . ':443:' . $address . ':443'],
            'CURLOPT_HTTPPROXYTUNNEL' => true,
            'CURLOPT_FRESH_CONNECT' => true,
            'CURLOPT_FORBID_REUSE' => true,
            'CURLOPT_TIMEOUT_MS' => max(1, (int) floor($request->timeoutSeconds * 1000)),
            'CURLOPT_CONNECTTIMEOUT_MS' => max(1, (int) floor(min($request->connectTimeoutSeconds, $request->timeoutSeconds) * 1000)),
            'CURLOPT_ENCODING' => '',
            'CURLOPT_USERAGENT' => 'ORDENOWA-Catalog/1.0',
            'CURLOPT_HTTPHEADER' => ['Accept: text/html, application/xhtml+xml'],
        ];
    }

    public function request(FetchRequest $request): TransportResponse
    {
        if (!function_exists('curl_init')) throw new FetchException('Product HTTP transport is unavailable.');
        $handle = curl_init();
        if ($handle === false) throw new FetchException('Product HTTP transport is unavailable.');
        $buffer = new ResponseBuffer($request->maxDecodedBytes);
        try {
            $options = [];
            foreach (self::securityOptions($request) as $name => $value) {
                if (!defined($name)) throw new FetchException('Product HTTP transport is unsupported.');
                $options[constant($name)] = $value;
            }
            $options[CURLOPT_PROTOCOLS] = CURLPROTO_HTTPS;
            $options[CURLOPT_REDIR_PROTOCOLS] = CURLPROTO_HTTPS;
            $options[CURLOPT_WRITEFUNCTION] = static fn ($handle, string $chunk): int => $buffer->appendBody($chunk);
            $options[CURLOPT_HEADERFUNCTION] = static fn ($handle, string $line): int => $buffer->appendHeader($line);
            if (!curl_setopt_array($handle, $options)) throw new FetchException('Product HTTP transport configuration failed.');
            $ok = curl_exec($handle);
            $error = curl_errno($handle);
            $status = (int) curl_getinfo($handle, CURLINFO_RESPONSE_CODE);
            // Failed CONNECT handshakes do not necessarily populate the origin
            // response code. Never inspect/forward curl_error or proxy headers.
            if (defined('CURLINFO_HTTP_CONNECTCODE')) {
                self::assertProxyTunnelAllowed((int) curl_getinfo($handle, constant('CURLINFO_HTTP_CONNECTCODE')));
            }
            if ($buffer->exceeded()) throw new FetchException('Product response exceeded a resource limit.');
            if ($ok === false) {
                if (in_array($error, [CURLE_COULDNT_CONNECT, CURLE_OPERATION_TIMEDOUT, CURLE_SEND_ERROR, CURLE_RECV_ERROR, CURLE_GOT_NOTHING], true)) {
                    throw new TransientTransportException('Transient product transport failure.');
                }
                throw new FetchException('Product HTTP transport failed.');
            }
            return new TransportResponse($status, $buffer->body(), $buffer->contentType(), $buffer->location());
        } finally {
            curl_close($handle);
        }
    }
}
