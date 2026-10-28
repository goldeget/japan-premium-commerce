<?php

declare(strict_types=1);

require_once __DIR__ . '/../../modules/kuraneacatalog/autoload.php';

use Kuranea\Catalog\Fetching\FetchException;
use Kuranea\Catalog\Fetching\FetchRequest;
use Kuranea\Catalog\Fetching\PublicProductFetcher;
use Kuranea\Catalog\Fetching\ResolverInterface;
use Kuranea\Catalog\Fetching\TransportInterface;
use Kuranea\Catalog\Fetching\TransportResponse;

// Standalone, offline regression: challenge pages may retain product metadata.
$challengeBody = file_get_contents(__DIR__ . '/fixtures/amazon-jp-access-challenge.synthetic.html');
if (!is_string($challengeBody)) {
    throw new RuntimeException('Could not read the synthetic access challenge fixture.');
}
$resolver = new class implements ResolverInterface {
    public function resolve(string $host, float $timeoutSeconds): array { return ['8.8.8.8']; }
};
$transport = new class implements TransportInterface {
    public string $body = '';
    public function request(FetchRequest $request): TransportResponse {
        return new TransportResponse(200, $this->body, 'text/html');
    }
};
$fetcher = new PublicProductFetcher($resolver, $transport);
foreach ([$challengeBody, '<html><body>Robot Check</body></html>', '<html><form action="/ap/signin"><input type="password" name="password"></form></html>'] as $body) {
    $transport->body = $body;
    try {
        $fetcher->fetch('https://www.amazon.co.jp/dp/B0KURANEA1');
        throw new RuntimeException('An HTTP 200 access challenge must fail before product metadata can be parsed.');
    } catch (FetchException $exception) {
        if ($exception->failureCategory !== FetchException::FAILURE_ACCESS_BLOCKED) {
            throw new RuntimeException('HTTP 200 access challenges must use the fixed access-blocked category.');
        }
    }
}
$transport->body = '<html><body>[SYNTHETIC FIXTURE] Ordinary product response</body></html>';
if ($fetcher->fetch('https://www.amazon.co.jp/dp/B0KURANEA1')->body !== $transport->body) {
    throw new RuntimeException('Ordinary HTML must still be returned unchanged.');
}
echo "PASS: offline synthetic HTTP 200 access challenge regression\n";
