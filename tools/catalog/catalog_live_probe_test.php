<?php
declare(strict_types=1);

$moduleAutoload = getenv('ORDENOWA_CATALOG_MODULE_AUTOLOAD');
if (!is_string($moduleAutoload) || $moduleAutoload === '') {
    $moduleAutoload = dirname(__DIR__, 2) . '/modules/kuraneacatalog/autoload.php';
}
require_once $moduleAutoload;
require_once __DIR__ . '/catalog_live_probe.php';

use Kuranea\Catalog\Domain\CatalogParseException;
use Kuranea\Catalog\Domain\NormalizedProductSnapshot;
use Kuranea\Catalog\Domain\ProductImageSnapshot;
use Kuranea\Catalog\Domain\ProductOptionSnapshot;
use Kuranea\Catalog\Fetching\FetchException;
use Kuranea\Catalog\Fetching\FetchedProduct;
use Kuranea\Catalog\Fetching\ProductPageFetcherInterface;
use Kuranea\Catalog\Parsing\ProductPageParserInterface;
use ORDENOWA\CatalogProbe\CatalogLiveProbe;

function liveProbeAssert(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

final class LiveProbeFixtureFetcher implements ProductPageFetcherInterface
{
    public array $requested = [];

    public function __construct(private readonly ?string $failureCategory = null)
    {
    }

    public function fetch(string $url): FetchedProduct
    {
        $this->requested[] = $url;
        if ($this->failureCategory !== null) {
            throw new FetchException('never expose this transport message', $this->failureCategory);
        }
        return new FetchedProduct(
            $url,
            '<html><head><meta property="og:title" content="Fetched title"></head><body>FIXTURE PRIVATE BODY</body></html>',
            new DateTimeImmutable('2026-10-29T03:30:00+00:00'),
            0
        );
    }
}

final class LiveProbeFixtureParser implements ProductPageParserInterface
{
    public array $parsedUrls = [];

    public function __construct(
        private readonly string $provider,
        private readonly bool $reject = false,
        private readonly string $rejectionMessage = 'never expose this parser message'
    )
    {
    }

    public function parse(string $html, string $sourceUrl, ?DateTimeImmutable $fetchedAt = null): NormalizedProductSnapshot
    {
        $this->parsedUrls[] = $sourceUrl;
        if ($this->reject) {
            throw new CatalogParseException($this->rejectionMessage);
        }
        $fetchedAt ??= new DateTimeImmutable('2026-10-29T03:30:00+00:00');
        $id = $this->provider === 'amazon_jp' ? 'B0836L96DZ' : 'rakuten-shop:item';
        return new NormalizedProductSnapshot(
            $this->provider,
            $id,
            $this->provider . ':' . $id,
            $sourceUrl,
            str_repeat('あ', 250),
            null,
            'description exists but is not emitted',
            ['Kitchen', 'Supplies'],
            2480,
            'JPY',
            [new ProductImageSnapshot('https://images.example.test/private-photo.jpg', 'private alt', 0, $this->provider)],
            [new ProductOptionSnapshot('Size', ['1 item', '2 item'])],
            [],
            null,
            null,
            'https://schema.org/InStock',
            'pending',
            $fetchedAt,
            str_repeat('0', 64)
        );
    }
}

$urls = [
    'https://www.amazon.co.jp/dp/B0836L96DZ',
    'https://item.rakuten.co.jp/tokka-com/4549980616819/',
    'https://item.rakuten.co.jp/rakuten24/4549980616819/',
];
$fetcher = new LiveProbeFixtureFetcher();
$amazon = new LiveProbeFixtureParser('amazon_jp');
$rakuten = new LiveProbeFixtureParser('rakuten_ichiba');
$probe = new CatalogLiveProbe($fetcher, [
    'amazon_jp' => $amazon,
    'rakuten_ichiba' => $rakuten,
]);
$report = $probe->run();
$json = json_encode($report, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);

liveProbeAssert($fetcher->requested === $urls, 'Only the three fixed marketplace item URLs may be requested, in order.');
liveProbeAssert($amazon->parsedUrls === [$urls[0]], 'The Amazon URL must use the Amazon parser only.');
liveProbeAssert($rakuten->parsedUrls === [$urls[1], $urls[2]], 'Both Rakuten URLs must use the Rakuten parser.');
liveProbeAssert($report['probe_completed'] === true && $report['parser_accepted'] === true, 'All successful parser results must yield accepted completion.');
liveProbeAssert($report['image_rights_approved'] === false && $report['catalog_imported'] === false, 'Probe must not claim image permission or import.');
liveProbeAssert(count($report['items']) === 3 && $report['items'][0]['price_jpy'] === 2480, 'Exact JPY price must be reported from the parser snapshot.');
liveProbeAssert(count(preg_split('//u', $report['items'][0]['source_title'], -1, PREG_SPLIT_NO_EMPTY)) === 240, 'Source titles must be capped at 240 Unicode characters.');
liveProbeAssert($report['items'][0]['fetched_at_utc'] === '2026-10-29T03:30:00Z', 'Fetched timestamp must be emitted in UTC.');
liveProbeAssert($report['items'][0]['fetched_html_bytes'] === strlen('<html><head><meta property="og:title" content="Fetched title"></head><body>FIXTURE PRIVATE BODY</body></html>'), 'Fetched HTML byte count must match the parser input body.');
liveProbeAssert($report['items'][0]['fetched_html_sha256'] === hash('sha256', '<html><head><meta property="og:title" content="Fetched title"></head><body>FIXTURE PRIVATE BODY</body></html>'), 'Fetched HTML digest must match the parser input body.');
liveProbeAssert($report['items'][0]['category_count'] === 2 && $report['items'][0]['image_count'] === 1, 'Only category and image counts are emitted.');
liveProbeAssert($report['items'][0]['options'] === [['name' => 'Size', 'values' => ['1 item', '2 item']]], 'Bounded parsed option labels and values must be emitted.');
liveProbeAssert($report['items'][0]['description_present'] === true, 'Description output is a presence flag only.');
liveProbeAssert(!str_contains($json, 'FIXTURE PRIVATE BODY') && !str_contains($json, 'private-photo.jpg') && !str_contains($json, 'private alt'), 'Raw HTML and image URLs/alt text must never appear in the safe report.');
liveProbeAssert(CatalogLiveProbe::exitCode($report) === 0, 'Only full parser acceptance may return success.');

$rejecting = new CatalogLiveProbe(new LiveProbeFixtureFetcher(), [
    'amazon_jp' => new LiveProbeFixtureParser('amazon_jp', true),
    'rakuten_ichiba' => new LiveProbeFixtureParser('rakuten_ichiba'),
]);
$rejectedReport = $rejecting->run();
$rejectedJson = json_encode($rejectedReport, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
liveProbeAssert($rejectedReport['probe_completed'] === true && $rejectedReport['parser_accepted'] === false, 'A completed probe with one rejected parser must not be called accepted.');
liveProbeAssert($rejectedReport['items'][0]['failure_stage'] === 'parse' && $rejectedReport['items'][0]['failure_code'] === 'parser_rejected', 'Generic parser failures must use a fixed safe stage and enum.');
liveProbeAssert($rejectedReport['items'][0]['source_title'] === 'Fetched title', 'A parser rejection may still report a bounded page title from fetched HTML.');
liveProbeAssert(!str_contains($rejectedJson, 'never expose this parser message'), 'Parser exception text must never be emitted.');
liveProbeAssert(CatalogLiveProbe::exitCode($rejectedReport) === 1, 'Any parser rejection must fail the command.');
$falseAcceptedReport = $rejectedReport;
$falseAcceptedReport['parser_accepted'] = true;
$falseAcceptedReport['acceptance_status'] = 'accepted';
liveProbeAssert(CatalogLiveProbe::exitCode($falseAcceptedReport) === 1, 'The command must reject a top-level acceptance flag when any item was not parsed.');

$blocked = new CatalogLiveProbe(new LiveProbeFixtureFetcher(FetchException::FAILURE_ACCESS_BLOCKED), [
    'amazon_jp' => new LiveProbeFixtureParser('amazon_jp'),
    'rakuten_ichiba' => new LiveProbeFixtureParser('rakuten_ichiba'),
]);
$blockedReport = $blocked->run();
$blockedJson = json_encode($blockedReport, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
liveProbeAssert($blockedReport['items'][0]['failure_stage'] === 'fetch' && $blockedReport['items'][0]['failure_code'] === 'access_blocked', 'Access blocks must remain fixed safe fetch outcomes.');
liveProbeAssert(!str_contains($blockedJson, 'never expose this transport message'), 'Transport exception text must never be emitted.');
liveProbeAssert(CatalogLiveProbe::exitCode($blockedReport) === 1, 'A blocked source must fail acceptance.');

$missingPrice = new CatalogLiveProbe(new LiveProbeFixtureFetcher(), [
    'amazon_jp' => new LiveProbeFixtureParser('amazon_jp', true, 'JPY価格は0より大きい整数円単位である必要があります。'),
    'rakuten_ichiba' => new LiveProbeFixtureParser('rakuten_ichiba'),
]);
$missingPriceReport = $missingPrice->run();
$missingPriceJson = json_encode($missingPriceReport, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
liveProbeAssert($missingPriceReport['items'][0]['failure_code'] === 'parser_rejected', 'Unknown parser messages must remain a generic safe enum.');
liveProbeAssert(!str_contains($missingPriceJson, 'JPY価格は0より大きい整数円単位である必要があります。'), 'Unknown parser text must not be copied into output.');

$exactMissingPrice = new CatalogLiveProbe(new LiveProbeFixtureFetcher(), [
    'amazon_jp' => new LiveProbeFixtureParser('amazon_jp', true, 'JPY 가격은 0보다 큰 정수 엔 단위여야 합니다.'),
    'rakuten_ichiba' => new LiveProbeFixtureParser('rakuten_ichiba'),
]);
$exactMissingPriceReport = $exactMissingPrice->run();
$exactMissingPriceJson = json_encode($exactMissingPriceReport, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
liveProbeAssert($exactMissingPriceReport['items'][0]['failure_code'] === 'exact_jpy_price_unavailable', 'Known fixed parser price failures must report a safe exact-price enum.');
liveProbeAssert(!str_contains($exactMissingPriceJson, 'JPY 가격은 0보다 큰 정수 엔 단위여야 합니다.'), 'Known parser messages must be mapped, never emitted verbatim.');
liveProbeAssert(CatalogLiveProbe::exitCode($exactMissingPriceReport) === 1, 'An unavailable exact JPY price must never be an accepted probe.');

echo "PASS: fixed live catalog probe shape, redaction, and acceptance gate\n";
