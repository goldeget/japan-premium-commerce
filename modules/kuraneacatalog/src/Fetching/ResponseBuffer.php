<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Fetching;

/** Bounded decoded stream buffer; no raw response headers are retained. */
final class ResponseBuffer
{
    private string $body = '';
    private int $headerBytes = 0;
    private string $contentType = '';
    private ?string $location = null;
    private bool $exceeded = false;

    public function __construct(private readonly int $maxDecodedBytes)
    {
        if ($maxDecodedBytes < 1 || $maxDecodedBytes > PublicProductFetcher::MAX_DECODED_BYTES) {
            throw new FetchException('Invalid product response limit.');
        }
    }

    /** cURL passes decoded chunks when CURLOPT_ENCODING is enabled. */
    public function appendBody(string $chunk): int
    {
        if ($this->exceeded || strlen($chunk) > $this->maxDecodedBytes - strlen($this->body)) {
            $this->exceeded = true;
            return 0;
        }
        $this->body .= $chunk;
        return strlen($chunk);
    }

    public function appendHeader(string $line): int
    {
        $this->headerBytes += strlen($line);
        if ($this->exceeded || $this->headerBytes > 65536) {
            $this->exceeded = true;
            return 0;
        }
        if (preg_match('~^HTTP/\S+\s+\d{3}~i', $line)) {
            $this->contentType = '';
            $this->location = null;
        } elseif (stripos($line, 'Content-Type:') === 0) {
            if ($this->contentType !== '') { $this->exceeded = true; return 0; }
            $this->contentType = trim(substr($line, 13));
        } elseif (stripos($line, 'Location:') === 0) {
            if ($this->location !== null || strlen($line) > 4096) { $this->exceeded = true; return 0; }
            $this->location = trim(substr($line, 9));
        }
        return strlen($line);
    }

    public function body(): string { return $this->body; }
    public function contentType(): string { return $this->contentType; }
    public function location(): ?string { return $this->location; }
    public function exceeded(): bool { return $this->exceeded; }
}
