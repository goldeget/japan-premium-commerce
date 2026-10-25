"""Offline source contracts for the public product fetch security boundary.

These checks protect configuration and control-flow invariants; the PHP security
suite provides behavioral coverage. No marketplace request or PHP is executed.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
FETCHING = ROOT / 'modules/kuraneacatalog/src/Fetching'


class CatalogFetcherContract(unittest.TestCase):
    def source(self, name):
        return (FETCHING / (name + '.php')).read_text(encoding='utf-8')

    def require(self, source, *markers):
        for marker in markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_only_exact_https_marketplace_product_paths_are_canonicalized(self):
        source = self.source('ProductUrlPolicy')
        self.require(source,
                     "strtolower((string) ($parts['scheme'] ?? '')) !== 'https'",
                     "isset($parts['user']) || isset($parts['pass'])",
                     "isset($parts['port']) && $parts['port'] !== 443",
                     "['amazon.co.jp', 'www.amazon.co.jp']",
                     "$host === 'item.rakuten.co.jp'",
                     '(?:dp|gp/product)/([A-Za-z0-9]{10})/?$~D',
                     '([A-Za-z0-9][A-Za-z0-9_-]{0,127})/([A-Za-z0-9][A-Za-z0-9_-]{0,127})/?$~D',
                     "strlen($url) > 4096", "preg_match('/[\\x00-\\x20\\x7f",
                     "throw new FetchException('Unsupported product URL.')")
        self.assertNotIn('str_ends_with($host', source)
        # Exact equality/allowlist checks must remain the only provider branches.
        providers = re.findall(r"'provider'\s*=>\s*'([^']+)'", source)
        self.assertEqual(providers, ['amazon_jp', 'rakuten_ichiba'])

    def test_redirects_are_manual_bounded_and_revalidate_destinations(self):
        transport = self.source('CurlTransport')
        self.require(transport, "'CURLOPT_FOLLOWLOCATION' => false", "'CURLOPT_MAXREDIRS' => 0",
                     '$options[CURLOPT_PROTOCOLS] = CURLPROTO_HTTPS',
                     '$options[CURLOPT_REDIR_PROTOCOLS] = CURLPROTO_HTTPS')
        fetcher = self.source('PublicProductFetcher')
        self.require(fetcher, '$redirects >= 2',
                     "ProductUrlPolicy::canonicalize(ProductUrlPolicy::redirectUrl($target['url'], $response->location))",
                     "$next['provider'] !== $provider || isset($visited[$next['url']])",
                     'PublicAddressPolicy::validate($this->resolver->resolve(')
        loop = fetcher.split('while (true)', 1)[1]
        self.assertLess(loop.index('PublicAddressPolicy::validate'), loop.index('$this->transport->request'))
        self.assertLess(loop.index('$target = $next;'), loop.index('++$redirects;'))

    def test_tls_and_proxy_tunnel_keep_original_host_and_pin_validated_ip(self):
        source = self.source('CurlTransport')
        self.require(source,
                     '$target = ProductUrlPolicy::canonicalize($request->canonicalUrl)',
                     '$addresses = PublicAddressPolicy::validate($request->addresses)',
                     "$target['url'] !== $request->canonicalUrl",
                     "'CURLOPT_SSL_VERIFYPEER' => true", "'CURLOPT_SSL_VERIFYHOST' => 2",
                     "'CURLOPT_PROXY_SSL_VERIFYPEER' => true", "'CURLOPT_PROXY_SSL_VERIFYHOST' => 2",
                     "'CURLOPT_URL' => $request->canonicalUrl",
                     "'CURLOPT_CONNECT_TO' => [$target['host'] . ':443:' . $address . ':443']",
                     "'CURLOPT_HTTPPROXYTUNNEL' => true", "'CURLOPT_FRESH_CONNECT' => true",
                     "'CURLOPT_FORBID_REUSE' => true")
        for option in ('CURLOPT_PROXY', 'CURLOPT_NOPROXY', 'CURLOPT_RESOLVE'):
            self.assertNotRegex(source, rf"['\"]{option}['\"]\s*=>")
        self.assertNotIn('CURLOPT_SSL_VERIFYPEER] = false', source)

    def test_every_dns_answer_is_checked_and_special_ip_ranges_are_denied(self):
        policy = self.source('PublicAddressPolicy')
        self.require(policy, '$addresses === [] || count($addresses) > 64',
                     'foreach ($addresses as $address)', '!is_string($address) || !self::isPublic($address)',
                     'FILTER_VALIDATE_IP, FILTER_FLAG_IPV4', 'FILTER_VALIDATE_IP, FILTER_FLAG_IPV6')
        for network in ('0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8',
                        '169.254.0.0/16', '172.16.0.0/12', '192.168.0.0/16', '198.18.0.0/15',
                        '192.0.2.0/24', '198.51.100.0/24', '203.0.113.0/24', '224.0.0.0/4', '240.0.0.0/4'):
            self.assertIn("'" + network + "'", policy)
        self.require(policy, "self::inRange($address, '2000::/3')",
                     "!self::inRange($address, '2001::/23')", "!self::inRange($address, '2001:db8::/32')",
                     "!self::inRange($address, '2002::/16')", "!self::inRange($address, '5f00::/16')",
                     "!self::inRange($address, '3fff::/20')")
        resolver = self.source('BoundedSystemResolver')
        self.require(resolver, '!in_array($host, self::HOSTS, true)',
                     "['getent', '--no-addrconfig', 'ahosts', $host]", 'FILTER_VALIDATE_IP',
                     "'www.amazon.co.jp'", "'amazon.co.jp'", "'item.rakuten.co.jp'",
                     'hrtime(true) / 1e9 >= $deadline', '65536 - $outputBytes',
                     'proc_terminate($process, 9)', 'proc_close($process)')

    def test_total_deadline_retries_and_streamed_decoded_response_are_bounded(self):
        fetcher = self.source('PublicProductFetcher')
        self.require(fetcher, 'MAX_DECODED_BYTES = 2097152', 'TOTAL_TIMEOUT_SECONDS = 15.0',
                     '$deadline = $this->clock->now() + self::TOTAL_TIMEOUT_SECONDS',
                     "min(3.0, $this->remaining($deadline))", '$retried = false',
                     'if ($retried) throw new FetchException', '$retried = true',
                     '$this->remaining($deadline)', 'strlen($response->body) > self::MAX_DECODED_BYTES',
                     '$remaining <= 0 || !is_finite($remaining)', "['text/html', 'application/xhtml+xml']")
        self.require(self.source('CurlTransport'), "'CURLOPT_TIMEOUT_MS' =>", "'CURLOPT_CONNECTTIMEOUT_MS' =>",
                     "'CURLOPT_ENCODING' => ''", 'CURLOPT_WRITEFUNCTION', '$buffer->appendBody($chunk)',
                     'CURLOPT_HEADERFUNCTION', '$buffer->appendHeader($line)', '$buffer->exceeded()')
        buffer = self.source('ResponseBuffer')
        self.require(buffer, 'strlen($chunk) > $this->maxDecodedBytes - strlen($this->body)',
                     '$this->headerBytes > 65536', 'strlen($line) > 4096', 'return 0;')
        self.assertLess(buffer.index('strlen($chunk) >'), buffer.index('$this->body .= $chunk'))

    def test_dependency_failures_expose_fixed_categories_without_secret_diagnostics(self):
        fetcher = self.source('PublicProductFetcher')
        boundary = fetcher.split('public function fetch(string $url): FetchedProduct', 1)[1].split(
            'private function fetchWithinDeadline', 1)[0]
        self.require(boundary, 'catch (FetchException $exception)', 'catch (\\Throwable)',
                     "FetchException::FAILURE_ACCESS_BLOCKED => 'Marketplace access was blocked.'",
                     "FetchException::FAILURE_SOURCE_UNAVAILABLE => 'Marketplace product page is unavailable.'",
                     "default => 'Public product retrieval failed.'",
                     'throw new FetchException($message, $exception->failureCategory)')
        for forbidden in ('getMessage(', 'getPrevious(', '$exception->get', '$response->body', '$url .'):
            self.assertNotIn(forbidden, boundary)
        transport = self.source('CurlTransport')
        self.require(transport, 'assertProxyTunnelAllowed', '[403, 407]', 'CURLINFO_HTTP_CONNECTCODE')
        # Comments may explain the redaction rule; actual diagnostic calls must be absent.
        self.assertNotRegex(transport, r'\bcurl_error\s*\(')
        self.assertNotRegex(transport, r'\b(?:echo|print|error_log|var_dump)\s*\(?\s*\$')

    def test_ci_runs_contract_and_triggers_for_changes_exactly_once(self):
        workflow = (ROOT / '.github/workflows/fresh-install.yml').read_text()
        self.assertEqual(workflow.count("      - 'tests/smoke/test_catalog_fetcher_contract.py'"), 2)
        self.assertEqual(workflow.count('tests.smoke.test_catalog_fetcher_contract'), 1)
        self.assertLess(workflow.index('tests.smoke.test_catalog_fetcher_contract'), workflow.index('id: image_build'))


if __name__ == '__main__':
    unittest.main()
