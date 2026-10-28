<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Fetching;

final class PublicProductFetcher implements ProductPageFetcherInterface
{
    public const MAX_DECODED_BYTES = 2097152;
    public const TOTAL_TIMEOUT_SECONDS = 15.0;
    private readonly ClockInterface $clock;

    public function __construct(
        private readonly ResolverInterface $resolver,
        private readonly TransportInterface $transport,
        ?ClockInterface $clock = null
    ) {
        $this->clock = $clock ?? new class implements ClockInterface {
            public function now(): float { return hrtime(true) / 1e9; }
        };
    }

    public function fetch(string $url): FetchedProduct
    {
        try {
            return $this->fetchWithinDeadline($url);
        } catch (FetchException $exception) {
            // Dependencies can use FetchException too. Trust only its bounded
            // category; never forward their diagnostic text or chained cause.
            $message = match ($exception->failureCategory) {
                FetchException::FAILURE_ACCESS_BLOCKED => 'Marketplace access was blocked.',
                FetchException::FAILURE_SOURCE_UNAVAILABLE => 'Marketplace product page is unavailable.',
                default => 'Public product retrieval failed.',
            };
            throw new FetchException($message, $exception->failureCategory);
        } catch (\Throwable) {
            // No source URL, raw response, exception message, or chained cause.
            throw new FetchException('Public product retrieval failed.', FetchException::FAILURE_FETCH);
        }
    }

    private function fetchWithinDeadline(string $url): FetchedProduct
    {
        $deadline = $this->clock->now() + self::TOTAL_TIMEOUT_SECONDS;
        $target = ProductUrlPolicy::canonicalize($url);
        $provider = $target['provider'];
        $identity = $target['identity'];
        $redirects = 0;
        $retried = false;
        $visited = [$target['url'] => true];
        while (true) {
            $addresses = PublicAddressPolicy::validate($this->resolver->resolve(
                $target['host'], min(3.0, $this->remaining($deadline))
            ));
            $remaining = $this->remaining($deadline);
            try {
                $response = $this->transport->request(new FetchRequest(
                    $target['url'], $addresses, $remaining, min(3.0, $remaining), self::MAX_DECODED_BYTES
                ));
            } catch (TransientTransportException) {
                $this->remaining($deadline);
                if ($retried) throw new FetchException('Product request retry limit exceeded.');
                $retried = true;
                continue;
            }
            $this->remaining($deadline);
            if (strlen($response->body) > self::MAX_DECODED_BYTES) {
                throw new FetchException('Product response exceeded the size limit.');
            }
            if (in_array($response->status, [408, 429, 502, 503, 504], true) && !$retried) {
                $retried = true;
                continue;
            }
            if (in_array($response->status, [401, 403, 407, 429, 451], true)) {
                throw new FetchException('Marketplace access was blocked.', FetchException::FAILURE_ACCESS_BLOCKED);
            }
            if (in_array($response->status, [404, 410], true)) {
                throw new FetchException('Marketplace product page is unavailable.', FetchException::FAILURE_SOURCE_UNAVAILABLE);
            }
            if (in_array($response->status, [301, 302, 303, 307, 308], true)) {
                if ($redirects >= 2 || $response->location === null) {
                    throw new FetchException('Product redirect limit exceeded.');
                }
                $next = ProductUrlPolicy::canonicalize(ProductUrlPolicy::redirectUrl($target['url'], $response->location));
                if ($next['provider'] !== $provider || $next['identity'] !== $identity
                    || isset($visited[$next['url']])) {
                    throw new FetchException('Product redirect is not permitted.');
                }
                $target = $next;
                $visited[$target['url']] = true;
                ++$redirects;
                continue;
            }
            $mediaType = strtolower(trim(explode(';', $response->contentType, 2)[0]));
            if ($response->status !== 200 || !in_array($mediaType, ['text/html', 'application/xhtml+xml'], true) || $response->body === '') {
                throw new FetchException('Product response is not an HTML document.');
            }
            $body = \Kuranea\Catalog\Parsing\HtmlDocumentEncoding::utf8($response->body, $response->contentType);
            if (strlen($body) > self::MAX_DECODED_BYTES) throw new FetchException('Decoded product response exceeded the size limit.');
            // A challenge can retain product metadata, so classify it before parsing.
            if (preg_match(
                '~(?:validateCaptcha|captchaContainer|captcha\.amazon\.com|robot\s+check|画像認証|アクセスを確認してください|不正なアクセスを検知)~iu',
                $body
            ) === 1 || AuthenticationPage::present($body)) {
                throw new FetchException('Marketplace access was blocked.', FetchException::FAILURE_ACCESS_BLOCKED);
            }
            return new FetchedProduct($target['url'], $body, new \DateTimeImmutable('now', new \DateTimeZone('UTC')), $redirects);
        }
    }

    private function remaining(float $deadline): float
    {
        $remaining = $deadline - $this->clock->now();
        if ($remaining <= 0 || !is_finite($remaining)) throw new FetchException('Product retrieval deadline exceeded.');
        return $remaining;
    }
}
