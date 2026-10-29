<?php

declare(strict_types=1);

namespace ORDENOWA\CatalogProbe;

use DateTimeZone;
use Kuranea\Catalog\Domain\CatalogParseException;
use Kuranea\Catalog\Domain\NormalizedProductSnapshot;
use Kuranea\Catalog\Domain\ProductOptionSnapshot;
use Kuranea\Catalog\Fetching\BoundedSystemResolver;
use Kuranea\Catalog\Fetching\CurlTransport;
use Kuranea\Catalog\Fetching\FetchException;
use Kuranea\Catalog\Fetching\ProductPageFetcherInterface;
use Kuranea\Catalog\Fetching\PublicProductFetcher;
use Kuranea\Catalog\Parsing\AmazonJapanHtmlParser;
use Kuranea\Catalog\Parsing\ProductPageParserInterface;
use Kuranea\Catalog\Parsing\RakutenHtmlParser;

/**
 * Read-only acceptance probe for three fixed public item pages. It never
 * persists data and emits no response HTML or image bytes.
 */
final class CatalogLiveProbe
{
    /** @var list<array{provider: string, url: string}> */
    public const TARGETS = [
        ['provider' => 'amazon_jp', 'url' => 'https://www.amazon.co.jp/dp/B0836L96DZ'],
        ['provider' => 'rakuten_ichiba', 'url' => 'https://item.rakuten.co.jp/tokka-com/4549980616819/'],
        ['provider' => 'rakuten_ichiba', 'url' => 'https://item.rakuten.co.jp/rakuten24/4549980616819/'],
    ];

    private const MAX_TITLE_CHARS = 240;
    private const MAX_OPTION_GROUPS = 12;
    private const MAX_OPTION_VALUES = 20;
    private const MAX_OPTION_TEXT_CHARS = 80;

    /** @param array<string, ProductPageParserInterface> $parsers */
    public function __construct(
        private readonly ProductPageFetcherInterface $fetcher,
        private readonly array $parsers
    ) {
    }

    /** @return array<string, mixed> */
    public function run(): array
    {
        $items = [];
        foreach (self::TARGETS as $target) {
            $items[] = $this->probeOne($target);
        }

        $accepted = count($items) === count(self::TARGETS);
        foreach ($items as $item) {
            $accepted = $accepted && ($item['parser_accepted'] ?? false) === true;
        }

        return [
            'schema_version' => 1,
            'probe' => 'fixed_marketplace_item_html',
            'probe_completed' => count($items) === count(self::TARGETS),
            'acceptance_status' => $accepted ? 'accepted' : 'not_accepted',
            'parser_accepted' => $accepted,
            // Public visibility does not grant photo rights; this probe does not import.
            'image_rights_approved' => false,
            'catalog_imported' => false,
            // Fetcher body is the HTTP entity after content decoding and UTF-8 normalization,
            // not a hash of compressed wire octets.
            'html_capture_layer' => 'decoded_utf8_entity_body',
            'items' => $items,
        ];
    }

    /** @param array<string, mixed> $report */
    public static function exitCode(array $report): int
    {
        $items = $report['items'] ?? null;
        if (($report['probe_completed'] ?? false) !== true
            || ($report['parser_accepted'] ?? false) !== true
            || ($report['acceptance_status'] ?? null) !== 'accepted'
            || !is_array($items)
            || count($items) !== count(self::TARGETS)) {
            return 1;
        }
        foreach ($items as $item) {
            if (!is_array($item) || ($item['parser_accepted'] ?? false) !== true) {
                return 1;
            }
        }
        return 0;
    }

    /** @param array{provider: string, url: string} $target
     *  @return array<string, mixed>
     */
    private function probeOne(array $target): array
    {
        $item = [
            'provider' => $target['provider'],
            'source_url' => $target['url'],
            'fetched_at_utc' => null,
            'fetched_html_sha256' => null,
            'fetched_html_bytes' => null,
            'source_title' => null,
            'parser_accepted' => false,
            'price_jpy' => null,
            'currency' => null,
            'options' => null,
            'options_truncated' => false,
            'category_count' => null,
            'image_count' => null,
            'description_present' => null,
            'failure_stage' => null,
            'failure_code' => null,
        ];

        try {
            $fetched = $this->fetcher->fetch($target['url']);
        } catch (FetchException $exception) {
            $item['failure_stage'] = 'fetch';
            $item['failure_code'] = match ($exception->failureCategory) {
                FetchException::FAILURE_ACCESS_BLOCKED => 'access_blocked',
                FetchException::FAILURE_SOURCE_UNAVAILABLE => 'source_unavailable',
                default => 'fetch_failed',
            };
            return $item;
        } catch (\Throwable) {
            $item['failure_stage'] = 'fetch';
            $item['failure_code'] = 'fetch_failed';
            return $item;
        }

        $item['fetched_at_utc'] = $fetched->fetchedAt
            ->setTimezone(new DateTimeZone('UTC'))
            ->format('Y-m-d\TH:i:s\Z');
        $item['fetched_html_sha256'] = hash('sha256', $fetched->body);
        $item['fetched_html_bytes'] = strlen($fetched->body);
        $item['source_title'] = self::extractSourceTitle($fetched->body);

        try {
            $parser = $this->parsers[$target['provider']] ?? null;
            if (!$parser instanceof ProductPageParserInterface || $fetched->canonicalUrl !== $target['url']) {
                $item['failure_stage'] = 'parse';
                $item['failure_code'] = 'parser_configuration_mismatch';
                return $item;
            }

            $snapshot = $parser->parse($fetched->body, $fetched->canonicalUrl, $fetched->fetchedAt);
            if ($snapshot->source !== $target['provider'] || $snapshot->sourceUrl !== $target['url']) {
                $item['failure_stage'] = 'parse';
                $item['failure_code'] = 'parser_result_mismatch';
                return $item;
            }

            [$options, $optionsTruncated] = self::safeOptions($snapshot->options);
            $item['source_title'] = self::boundedText($snapshot->name, self::MAX_TITLE_CHARS);
            $item['parser_accepted'] = true;
            $item['price_jpy'] = $snapshot->priceJpy;
            $item['currency'] = $snapshot->currency;
            $item['options'] = $options;
            $item['options_truncated'] = $optionsTruncated;
            $item['category_count'] = count($snapshot->categories);
            $item['image_count'] = count($snapshot->images);
            $item['description_present'] = is_string($snapshot->description)
                && trim($snapshot->description) !== '';
            return $item;
        } catch (CatalogParseException $exception) {
            $item['failure_stage'] = 'parse';
            $item['failure_code'] = self::parseFailureCode($exception);
            return $item;
        } catch (\Throwable) {
            $item['failure_stage'] = 'parse';
            $item['failure_code'] = 'parser_failed';
            return $item;
        }
    }

    private static function extractSourceTitle(string $html): ?string
    {
        if (!class_exists(\DOMDocument::class) || !class_exists(\DOMXPath::class)
            || !defined('LIBXML_NONET') || !defined('LIBXML_NOERROR') || !defined('LIBXML_NOWARNING')) {
            return null;
        }

        $previousLibxmlState = libxml_use_internal_errors(true);
        libxml_clear_errors();
        try {
            $document = new \DOMDocument();
            if (!$document->loadHTML($html, LIBXML_NONET | LIBXML_NOERROR | LIBXML_NOWARNING)) {
                return null;
            }
            $xpath = new \DOMXPath($document);
            foreach ([
                '//h1[@id="productTitle"]',
                '//meta[@property="og:title" or @name="twitter:title" or @name="title"]/@content',
                '//h1[1]',
                '//title[1]',
            ] as $query) {
                $nodes = $xpath->query($query);
                if ($nodes === false || $nodes->length < 1) {
                    continue;
                }
                $text = trim((string) ($nodes->item(0)?->nodeValue ?? ''));
                $text = preg_replace('/[\x00-\x1F\x7F]+/u', ' ', $text) ?? '';
                $text = preg_replace('/\s+/u', ' ', trim($text)) ?? '';
                if ($text !== '') {
                    return self::boundedText($text, self::MAX_TITLE_CHARS);
                }
            }
        } catch (\Throwable) {
            return null;
        } finally {
            libxml_clear_errors();
            libxml_use_internal_errors($previousLibxmlState);
        }

        return null;
    }

    /** @param array<int, mixed> $options
     *  @return array{0: list<array{name: string, values: list<string>}>, 1: bool}
     */
    private static function safeOptions(array $options): array
    {
        $safe = [];
        $truncated = false;
        foreach ($options as $option) {
            if (!$option instanceof ProductOptionSnapshot) {
                continue;
            }
            if (count($safe) >= self::MAX_OPTION_GROUPS) {
                $truncated = true;
                break;
            }
            $values = [];
            foreach ($option->values as $value) {
                if (!is_string($value)) {
                    continue;
                }
                if (count($values) >= self::MAX_OPTION_VALUES) {
                    $truncated = true;
                    break;
                }
                $values[] = self::boundedText($value, self::MAX_OPTION_TEXT_CHARS);
            }
            $safe[] = [
                'name' => self::boundedText($option->name, self::MAX_OPTION_TEXT_CHARS),
                'values' => $values,
            ];
        }

        return [$safe, $truncated];
    }

    private static function boundedText(string $text, int $maxCharacters): string
    {
        $text = preg_replace('/[\x00-\x1F\x7F]+/u', ' ', $text) ?? '';
        $text = preg_replace('/\s+/u', ' ', trim($text)) ?? '';
        if ($text === '' || preg_match('//u', $text) !== 1 || $maxCharacters < 1) {
            return '';
        }
        if (preg_match('/\A.{0,' . $maxCharacters . '}/us', $text, $matches) !== 1) {
            return '';
        }
        return $matches[0];
    }

    private static function parseFailureCode(CatalogParseException $exception): string
    {
        return match ($exception->getMessage()) {
            'JPY 가격은 0보다 큰 정수 엔 단위여야 합니다.',
            'JPY 가격이 지원하는 정수 범위를 벗어났습니다.',
            '정확한 정수 엔 가격을 확인할 수 없습니다. 소수 JSON 숫자는 지원하지 않습니다.' => 'exact_jpy_price_unavailable',
            '지원하지 않는 원본 통화입니다. 일본 상품은 JPY 가격만 허용됩니다.' => 'unsupported_currency',
            '집계 가격의 최저·최고 정수 엔 가격을 모두 확인해야 합니다.',
            '집계 가격 범위가 달라 단일 참고 가격을 확정할 수 없습니다.',
            '명시 가격과 집계 가격이 달라 단일 참고 가격을 확정할 수 없습니다.',
            '옵션 또는 판매자별 가격이 달라 단일 참고 가격을 확정할 수 없습니다.' => 'price_not_unambiguous',
            default => 'parser_rejected',
        };
    }

}

/** CLI entry point: no user-supplied URLs, secrets, cookies, or persistence. */
if (PHP_SAPI === 'cli' && realpath($_SERVER['SCRIPT_FILENAME'] ?? '') === __FILE__) {
    ini_set('display_errors', '0');
    ini_set('log_errors', '0');
    $bufferLevel = ob_get_level();
    ob_start();

    $emit = static function (array $payload) use ($bufferLevel): bool {
        while (ob_get_level() > $bufferLevel) {
            ob_end_clean();
        }
        try {
            $line = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
        } catch (\Throwable) {
            $line = '{"schema_version":1,"probe_completed":false,"acceptance_status":"not_accepted","parser_accepted":false,"failure_code":"output_failed","image_rights_approved":false,"catalog_imported":false,"items":[]}' . PHP_EOL;
        }
        return fwrite(STDOUT, $line) === strlen($line);
    };

    if ($argc !== 1) {
        $written = $emit([
            'schema_version' => 1,
            'probe_completed' => false,
            'acceptance_status' => 'not_accepted',
            'parser_accepted' => false,
            'failure_code' => 'invalid_invocation',
            'image_rights_approved' => false,
            'catalog_imported' => false,
            'items' => [],
        ]);
        exit($written ? 64 : 1);
    }

    try {
        require_once dirname(__DIR__, 2) . '/modules/kuraneacatalog/autoload.php';
        $fetcher = new PublicProductFetcher(new BoundedSystemResolver(), new CurlTransport());
        $probe = new CatalogLiveProbe($fetcher, [
            'amazon_jp' => new AmazonJapanHtmlParser(),
            'rakuten_ichiba' => new RakutenHtmlParser(),
        ]);
        $report = $probe->run();
        $exitCode = CatalogLiveProbe::exitCode($report);
        exit($emit($report) ? $exitCode : 1);
    } catch (\Throwable) {
        $emit([
            'schema_version' => 1,
            'probe' => 'fixed_marketplace_item_html',
            'probe_completed' => false,
            'acceptance_status' => 'not_accepted',
            'parser_accepted' => false,
            'image_rights_approved' => false,
            'catalog_imported' => false,
            'html_capture_layer' => 'decoded_utf8_entity_body',
            'failure_stage' => 'probe',
            'failure_code' => 'probe_failed',
            'items' => [],
        ]);
        exit(1);
    }
}
