# KURANEA catalog review module

This directory contains dependency-free PHP value objects and offline parsers for Amazon Japan and Rakuten Ichiba product-page snapshots.

## Scope and safeguards

- Parsers accept an HTML string already present in memory. They never fetch product pages, download images, use cookies, launch a browser, or contact marketplace servers.
- Only HTTPS source URLs on the provider's exact configured Japanese marketplace hostnames are accepted.
- `tests/catalog/fixtures/*.synthetic.html` contains invented test data and must not be represented as actual Amazon or Rakuten listings.
- Parsed snapshots retain provider, source URL, provider product ID, fetch time, content fingerprint, image metadata, provider rating/review provenance, JPY price, and options.
- Every snapshot and review-queue entry starts in `pending`. Provider reviews are marked `source_site` and non-publishable; ORDENOWA customer reviews are not populated by these parsers.
- `ProductReviewQueue` is an in-memory domain behavior used to test identity and update semantics. It is not persistent storage and is not an administrator review screen.

## Persistent review and explicit TEST/DEMO registration

- Compose mounts `catalog_review_data` at `/var/lib/kuranea/catalog-review`, outside `/var/www/html`. The entrypoint only sets ownership and permissions on the mounted directory; it does not clear existing queue data. `KURANEA_CATALOG_QUEUE_DIR` injects this location into `CatalogQueueRepositoryFactory`.
- `JsonFileProductReviewQueueRepository` stores complete normalized snapshots in a schema-versioned JSON file. It uses an adjacent process lock and atomic replacement. The module preserves the queue volume when uninstalled.
- Changed source content returns to `pending` review. An approved item retains the staff identity, timestamp, and native product ID. Re-importing identical content is idempotent.
- The Korean Back Office tab checks view/edit access and gets the approver identity from the authenticated employee context. Approval requires a POST, PrestaShop admin token, an explicit confirmation checkbox, and `KURANEA_CATALOG_TEST_DEMO_APPROVAL=1`.
- Only `ProductApprovalService::approve(..., confirmed: true)` calls the native registration interface. The explicit confirmation and staff identity are required for a pending item.
- `PrestaShopNativeProductRegistrar` refuses to run unless PrestaShop is bootstrapped and the shop default currency is JPY. It registers a hidden, inactive, non-orderable product with a `[TEST/DEMO]` name, `TEST-` reference, and escaped source provenance. It does not import source reviews or images.
- The review screen displays queued snapshots, but there is no marketplace fetcher, background importer, or native product registration test in this repository. Only explicitly enqueued snapshots appear in the queue. The fresh-install CI verifies module/tab installation and queue persistence, not `Product::add()` behavior.

## Run offline parser tests

The project does not require Composer or another package for this parser:

```sh
php tests/catalog/run.php
```

Fixtures are artificial contract tests. Their passing result does not establish compatibility with current live Amazon or Rakuten page markup, and no marketplace access is part of this test suite.
