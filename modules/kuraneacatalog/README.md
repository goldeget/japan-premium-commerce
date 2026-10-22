# ORDENOWA catalog parser foundation

This directory contains dependency-free PHP value objects and offline parsers for Amazon Japan and Rakuten Ichiba product-page snapshots.

## Scope and safeguards

- Parsers accept an HTML string already present in memory. They never fetch product pages, download images, use cookies, launch a browser, or contact marketplace servers.
- Only HTTPS source URLs on the provider's exact configured Japanese marketplace hostnames are accepted.
- `tests/catalog/fixtures/*.synthetic.html` contains invented test data and must not be represented as actual Amazon or Rakuten listings.
- Parsed snapshots retain provider, source URL, provider product ID, fetch time, content fingerprint, image metadata, provider rating/review provenance, JPY price, and options.
- Every snapshot and review-queue entry starts in `pending`. Provider reviews are marked `source_site` and non-publishable; ORDENOWA customer reviews are not populated by these parsers.
- `ProductReviewQueue` is an in-memory domain behavior used to test identity and update semantics. It is not persistent storage and is not an administrator review screen.

## Run offline parser tests

The project does not require Composer or another package for this parser:

```sh
php tests/catalog/run.php
```

Fixtures are artificial contract tests. Their passing result does not establish compatibility with current live Amazon or Rakuten page markup, and no marketplace access is part of this test suite.
