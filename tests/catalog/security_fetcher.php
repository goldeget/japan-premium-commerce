<?php

declare(strict_types=1);

require_once __DIR__ . '/../../modules/kuraneacatalog/autoload.php';

use Kuranea\Catalog\Fetching\ClockInterface;
use Kuranea\Catalog\Fetching\BoundedSystemResolver;
use Kuranea\Catalog\Fetching\CurlTransport;
use Kuranea\Catalog\Fetching\FetchException;
use Kuranea\Catalog\Fetching\FetchRequest;
use Kuranea\Catalog\Fetching\PublicProductFetcher;
use Kuranea\Catalog\Fetching\ResolverInterface;
use Kuranea\Catalog\Fetching\ResponseBuffer;
use Kuranea\Catalog\Fetching\TransientTransportException;
use Kuranea\Catalog\Fetching\TransportInterface;
use Kuranea\Catalog\Fetching\TransportResponse;

function fetchAssert(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

fetchAssert(class_exists(PublicProductFetcher::class), 'Secure public marketplace fetch boundary is missing.');

/** All dependencies below are synthetic; this test never initializes cURL or DNS. */
function fetchFixture(array $responses = [], array $addresses = ['8.8.8.8']): array
{
    $clock = new class implements ClockInterface {
        public float $time = 100.0;
        public function now(): float { return $this->time; }
    };
    $resolver = new class($addresses, $clock) implements ResolverInterface {
        public array $calls = [];
        public array $answerSets = [];
        public float $delay = 0;
        public ?Throwable $failure = null;
        public function __construct(public array $addresses, public ClockInterface $clock) {}
        public function resolve(string $host, float $timeoutSeconds): array {
            $this->calls[] = [$host, $timeoutSeconds];
            if ($this->failure !== null) throw $this->failure;
            $this->clock->time += $this->delay;
            return array_shift($this->answerSets) ?? $this->addresses;
        }
    };
    $transport = new class($responses, $clock) implements TransportInterface {
        public array $requests = [];
        public float $delay = 0;
        public function __construct(public array $responses, public ClockInterface $clock) {}
        public function request(FetchRequest $request): TransportResponse {
            $this->requests[] = $request;
            $this->clock->time += $this->delay;
            $response = array_shift($this->responses) ?? new TransportResponse(200, '<html>fixture</html>', 'text/html; charset=UTF-8');
            if ($response instanceof Throwable) throw $response;
            return $response;
        }
    };
    return [new PublicProductFetcher($resolver, $transport, $clock), $resolver, $transport, $clock];
}

function fetchRejects(callable $operation, string $message): void
{
    try {
        $operation();
    } catch (FetchException $error) {
        fetchAssert($error->getPrevious() === null, 'Fetch failures must not retain raw exception causes.');
        fetchAssert(!str_contains($error->getMessage(), 'SECRET'), 'Fetch failures must not expose response/exception details.');
        return;
    }
    throw new RuntimeException($message);
}

$amazon = 'https://www.amazon.co.jp/dp/B012345678';
[$fetcher, $dns, $http] = fetchFixture();
$result = $fetcher->fetch('https://amazon.co.jp/product-title/dp/b012345678/?tag=SECRET#fragment');
fetchAssert($result->canonicalUrl === $amazon, 'Amazon product URLs must canonicalize without tracking or fragment.');
fetchAssert($result->body === '<html>fixture</html>' && $result->redirectCount === 0, 'Result must retain only the fetched body and safe metadata.');
fetchAssert($result->fetchedAt instanceof DateTimeImmutable, 'Result must include the retrieval time.');
fetchAssert(array_keys(get_object_vars($result)) === ['canonicalUrl', 'body', 'fetchedAt', 'redirectCount'], 'No transport headers or other raw response metadata may escape.');
fetchAssert($http->requests[0]->addresses === ['8.8.8.8'], 'Transport must receive vetted pinned addresses.');
fetchAssert($http->requests[0]->maxDecodedBytes === 2097152, 'Decoded HTML ceiling must be 2MiB.');

[$fetcher] = fetchFixture();
fetchAssert($fetcher->fetch('https://item.rakuten.co.jp/shop-name/item_123/?scid=SECRET')->canonicalUrl === 'https://item.rakuten.co.jp/shop-name/item_123/', 'Rakuten must canonicalize only shop/item product paths.');

foreach ([
    'http://www.amazon.co.jp/dp/B012345678',
    'https://www.amazon.co.jp.evil.invalid/dp/B012345678',
    'https://user:SECRET@www.amazon.co.jp/dp/B012345678',
    'https://www.amazon.co.jp:444/dp/B012345678',
    'https://www.amazon.co.jp./dp/B012345678',
    'https://www.amazon.co.jp/s?k=product',
    'https://www.amazon.co.jp/dp/not-an-asin',
    'https://www.amazon.co.jp/%2e%2e/dp/B012345678',
    'https://rakuten.co.jp/shop/item/',
    'https://item.rakuten.co.jp/shop/item/extra/',
    "https://www.amazon.co.jp/dp/B012345678\r\nX-Test: SECRET",
    'https://127.0.0.1/dp/B012345678',
] as $url) {
    [$fetcher, $dns, $http] = fetchFixture();
    fetchRejects(fn () => $fetcher->fetch($url), 'Nonproduct or forbidden URL was accepted.');
    fetchAssert($dns->calls === [] && $http->requests === [], 'Rejected URL must never reach DNS or HTTP.');
}

foreach ([
    '127.0.0.1', '10.0.0.1', '172.16.0.1', '192.168.1.1', '169.254.169.254',
    '100.64.0.1', '0.0.0.0', '192.0.0.1', '192.0.2.1', '198.18.0.1', '224.0.0.1',
    '::1', '::', 'fc00::1', 'fe80::1', 'ff02::1', '2001:db8::1', '2002:a00:1::1', '5f00::1',
    '::ffff:127.0.0.1', '::ffff:8.8.8.8', 'not-an-address',
] as $address) {
    [$fetcher, $dns, $http] = fetchFixture([], ['8.8.8.8', $address]);
    fetchRejects(fn () => $fetcher->fetch($amazon), 'Mixed public/forbidden DNS answer was accepted.');
    fetchAssert($http->requests === [], 'Any forbidden DNS answer must block the request.');
}
[$fetcher, $dns, $http] = fetchFixture([], []);
fetchRejects(fn () => $fetcher->fetch($amazon), 'Empty DNS answers must fail closed.');
[$fetcher] = fetchFixture([], ['2606:4700:4700::1111']);
fetchAssert($fetcher->fetch($amazon)->body !== '', 'Public IPv6 must be supported.');

[$fetcher, $dns, $http] = fetchFixture([
    new TransportResponse(302, '', '', '/gp/product/B012345679?tag=SECRET'),
    new TransportResponse(301, '', '', 'https://amazon.co.jp/dp/B012345670'),
    new TransportResponse(200, '<html>redirected</html>', 'text/html'),
]);
fetchAssert($fetcher->fetch($amazon)->redirectCount === 2 && count($dns->calls) === 3, 'Each allowed redirect must be independently resolved and validated.');
foreach ([
    'https://item.rakuten.co.jp/shop/item/',
    'https://127.0.0.1/private',
    'http://www.amazon.co.jp/dp/B012345679',
    'https://www.amazon.co.jp/signin',
] as $location) {
    [$fetcher, $dns, $http] = fetchFixture([new TransportResponse(302, '', '', $location)]);
    fetchRejects(fn () => $fetcher->fetch($amazon), 'Unsafe redirect was accepted.');
    fetchAssert(count($http->requests) === 1, 'Unsafe redirect must not issue a second request.');
}
[$fetcher, $dns, $http] = fetchFixture([
    new TransportResponse(302, '', '', '/dp/B012345679'),
    new TransportResponse(302, '', '', '/dp/B012345670'),
    new TransportResponse(302, '', '', '/dp/B012345671'),
]);
fetchRejects(fn () => $fetcher->fetch($amazon), 'More than two redirects must fail.');
fetchAssert(count($http->requests) === 3, 'Redirect limit must prevent the fourth HTTP request.');

foreach ([
    new TransportResponse(200, 'SECRET', 'application/json'),
    new TransportResponse(200, str_repeat('x', 2097153), 'text/html'),
    new TransportResponse(404, 'SECRET', 'text/html'),
    new RuntimeException('SECRET transport details'),
] as $response) {
    [$fetcher] = fetchFixture([$response]);
    fetchRejects(fn () => $fetcher->fetch($amazon), 'Invalid or oversized response was accepted.');
}
[$fetcher] = fetchFixture([new TransportResponse(200, str_repeat('x', 2097152), 'text/html')]);
fetchAssert(strlen($fetcher->fetch($amazon)->body) === 2097152, 'Exact size ceiling must be accepted.');
[$fetcher, $dns, $http] = fetchFixture([new TransientTransportException('SECRET'), new TransportResponse(200, '<html>retried</html>', 'text/html')]);
fetchAssert($fetcher->fetch($amazon)->body === '<html>retried</html>' && count($dns->calls) === 2, 'One transient failure may retry with fresh DNS validation.');
[$fetcher, $dns, $http] = fetchFixture([new TransientTransportException('SECRET'), new TransientTransportException('SECRET')]);
fetchRejects(fn () => $fetcher->fetch($amazon), 'Two transient failures must not retry again.');
fetchAssert(count($http->requests) === 2, 'Only one retry is allowed across the whole fetch.');
[$fetcher, $dns, $http, $clock] = fetchFixture([new TransportResponse(503, '', 'text/html')]);
$http->delay = 15;
fetchRejects(fn () => $fetcher->fetch($amazon), 'Deadline must stop retry after a slow response.');
fetchAssert(count($http->requests) === 1, 'No retry may begin after the overall deadline.');
[$fetcher, $dns, $http, $clock] = fetchFixture();
$dns->delay = 16;
fetchRejects(fn () => $fetcher->fetch($amazon), 'DNS must count against the overall deadline.');
fetchAssert($http->requests === [], 'HTTP must not begin after DNS exhausts the deadline.');

[$fetcher, $dns, $http] = fetchFixture([new TransportResponse(302, '', '', '/dp/B012345679')]);
$dns->answerSets = [['8.8.8.8'], ['127.0.0.1']];
fetchRejects(fn () => $fetcher->fetch($amazon), 'A redirect must not reuse an earlier public DNS result.');
fetchAssert(count($http->requests) === 1, 'Rebinding to a forbidden destination must stop before transport.');
[$fetcher, $dns, $http] = fetchFixture([
    new TransportResponse(503, '', 'text/html'),
    new TransportResponse(302, '', '', '/dp/B012345679'),
    new TransportResponse(503, '', 'text/html'),
]);
fetchRejects(fn () => $fetcher->fetch($amazon), 'Redirect must not reset the one-retry allowance.');
fetchAssert(count($http->requests) === 3, 'Retry count must be global across redirects.');

// Decoded streaming chunks are bounded before concatenation, independently of
// Content-Length or Content-Encoding values supplied by the remote server.
fetchAssert(class_exists(ResponseBuffer::class), 'A bounded decoded streaming response buffer is required.');
$buffer = new ResponseBuffer(8);
fetchAssert($buffer->appendBody('12345678') === 8, 'Exact decoded stream limit must fit.');
fetchAssert($buffer->appendBody('9') === 0 && $buffer->exceeded(), 'Streaming overflow must abort transfer.');
fetchAssert($buffer->body() === '12345678', 'Oversized chunks must never be appended to memory.');
$buffer = new ResponseBuffer(8);
$buffer->appendHeader("HTTP/1.1 200 Connection established\r\n");
$buffer->appendHeader("Content-Type: proxy-only\r\n");
$buffer->appendHeader("HTTP/2 200\r\n");
$buffer->appendHeader("Content-Type: text/html\r\n");
fetchAssert($buffer->contentType() === 'text/html', 'Proxy/interim headers must not become final response metadata.');
fetchAssert($buffer->appendHeader('X-Huge: ' . str_repeat('x', 65536)) === 0, 'Header bytes must also be bounded.');


// Inspect transport configuration without cURL initialization or any network calls.
$request = new FetchRequest($amazon, ['2606:4700:4700::1111'], 12.0, 3.0, 2097152);
$options = CurlTransport::securityOptions($request);
fetchAssert($options['CURLOPT_SSL_VERIFYPEER'] === true && $options['CURLOPT_SSL_VERIFYHOST'] === 2, 'TLS peer and hostname verification must remain enabled.');
fetchAssert($options['CURLOPT_FOLLOWLOCATION'] === false && $options['CURLOPT_MAXREDIRS'] === 0, 'cURL must not follow redirects automatically.');
fetchAssert($options['CURLOPT_CONNECT_TO'] === ['www.amazon.co.jp:443:[2606:4700:4700::1111]:443'], 'Connection target must pin the vetted IP even through a proxy tunnel.');
fetchAssert(!isset($options['CURLOPT_PROXY']) && !isset($options['CURLOPT_NOPROXY']), 'Transport must preserve configured proxy routing.');
fetchAssert($options['CURLOPT_ENCODING'] === '', 'Streaming size accounting must apply to decoded response bytes.');
fetchAssert($options['CURLOPT_TIMEOUT_MS'] === 12000, 'Transport timeout must use remaining overall time.');

foreach ([
    FetchException::FAILURE_FETCH => 'Public product retrieval failed.',
    FetchException::FAILURE_ACCESS_BLOCKED => 'Marketplace access was blocked.',
    FetchException::FAILURE_SOURCE_UNAVAILABLE => 'Marketplace product page is unavailable.',
] as $category => $expectedMessage) {
    foreach (['resolver', 'transport'] as $dependency) {
        [$fetcher, $dns] = fetchFixture($dependency === 'transport' ? [new FetchException('SECRET upstream exception', $category)] : []);
        if ($dependency === 'resolver') $dns->failure = new FetchException('SECRET resolver exception', $category);
        try {
            $fetcher->fetch($amazon);
            throw new RuntimeException('Injected fetch exception must fail.');
        } catch (FetchException $error) {
            fetchAssert($error->getMessage() === $expectedMessage, 'Fetch category must select a fixed redacted message.');
            fetchAssert($error->failureCategory === $category, 'Redaction must preserve the safe category.');
            fetchAssert($error->getPrevious() === null, 'Redaction must discard the upstream exception cause.');
        }
    }
}

foreach ([403, 407] as $connectStatus) {
    try {
        CurlTransport::assertProxyTunnelAllowed($connectStatus);
        throw new RuntimeException('Rejected CONNECT tunnel must fail.');
    } catch (FetchException $error) {
        fetchAssert($error->failureCategory === FetchException::FAILURE_ACCESS_BLOCKED, 'Proxy rejection must be access_blocked.');
        fetchAssert($error->getMessage() === 'Marketplace access was blocked.', 'Proxy rejection must use fixed text without proxy diagnostics.');
    }
}
CurlTransport::assertProxyTunnelAllowed(0); // No proxy / unavailable cURL info.
CurlTransport::assertProxyTunnelAllowed(200);

// Substitute only the resolver executable. No real getent/DNS, cURL, or HTTP
// request runs. The fixture shell uses builtins and an exec'd local sleeper.
$resolverFixture = sys_get_temp_dir() . '/ordenowa-fetch-resolver-' . bin2hex(random_bytes(8));
fetchAssert(mkdir($resolverFixture, 0700), 'Could not create private resolver fixture.');
$oldPath = getenv('PATH');
$fixtureExecutable = $resolverFixture . '/getent';
$fixturePid = $resolverFixture . '/pid';
$setResolverScript = static function (string $script) use ($fixtureExecutable): void {
    fetchAssert(file_put_contents($fixtureExecutable, "#!/bin/sh\n" . $script) !== false, 'Could not write resolver fixture.');
    fetchAssert(chmod($fixtureExecutable, 0700), 'Could not make resolver fixture executable.');
};
$assertResolverReaped = static function () use ($fixturePid): void {
    $pid = trim((string) file_get_contents($fixturePid));
    fetchAssert(ctype_digit($pid), 'Resolver fixture must record its PID.');
    if (is_dir('/proc')) {
        fetchAssert(!is_dir('/proc/' . $pid), 'Resolver subprocess must be killed and reaped before returning.');
    }
};
try {
    putenv('PATH=' . $resolverFixture);
    $resolver = new BoundedSystemResolver();
    $setResolverScript("[ \"\$1\" = '--no-addrconfig' ] && [ \"\$2\" = 'ahosts' ] && [ \"\$3\" = 'www.amazon.co.jp' ] || exit 22\nprintf '8.8.8.8 STREAM fixture\\nfc00::1 STREAM fixture\\n'\n");
    $answers = $resolver->resolve('www.amazon.co.jp', 1.0);
    fetchAssert($answers === ['8.8.8.8', 'fc00::1'], 'Resolver must request and retain unfiltered A/AAAA results.');
    fetchRejects(fn () => \Kuranea\Catalog\Fetching\PublicAddressPolicy::validate($answers), 'Mixed-family private answers must be rejected.');

    $pidCommand = 'printf "%s" "$$" > ' . escapeshellarg($fixturePid) . "\n";
    foreach (['stdout', 'stderr'] as $stream) {
        $write = "printf '%s' '" . str_repeat('x', 4096) . "'" . ($stream === 'stderr' ? ' >&2' : '');
        $setResolverScript($pidCommand . "i=0\nwhile [ \"\$i\" -lt 32 ]; do " . $write . "; i=\$((i+1)); done\nexec /bin/sleep 5\n");
        $started = hrtime(true);
        fetchRejects(fn () => $resolver->resolve('www.amazon.co.jp', 1.0), 'Oversized resolver output must fail.');
        fetchAssert((hrtime(true) - $started) / 1e9 < 2.0, 'Output overflow must terminate the resolver without waiting for its sleeper.');
        $assertResolverReaped();
    }
    $setResolverScript($pidCommand . "exec /bin/sleep 5\n");
    $started = hrtime(true);
    fetchRejects(fn () => $resolver->resolve('www.amazon.co.jp', 0.2), 'Resolver deadline must terminate the subprocess.');
    fetchAssert((hrtime(true) - $started) / 1e9 < 2.0, 'Resolver cleanup must not wait for process natural exit.');
    $assertResolverReaped();
} finally {
    $oldPath === false ? putenv('PATH') : putenv('PATH=' . $oldPath);
    if (is_file($fixtureExecutable)) unlink($fixtureExecutable);
    if (is_file($fixturePid)) unlink($fixturePid);
    rmdir($resolverFixture);
}

echo "PASS: secure marketplace fetch boundary synthetic contracts (zero network calls)\n";
