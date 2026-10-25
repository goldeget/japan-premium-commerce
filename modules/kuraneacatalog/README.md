# ORDENOWA catalog collection and review

`kuraneacatalog` retains the original Amazon Japan and Rakuten Ichiba HTML parsers and connects them to a bounded URL fetcher, persistent review queue, and PrestaShop's native product manager.

## Collection and review flow

The Korean Back Office screen accepts one or more supported product URLs, stores a run-independent import batch outside the public web root, and processes at most one URL per request. Each batch accepts at most 10 URLs; duplicate provider/product identities in one batch collapse to one item. Item state and attempt count are persisted so staff can see queued, processing, succeeded, and failed results and retry eligible failures. Retry attempts are capped. Expired processing leases can be recovered without treating an old worker's result as current.

The fetcher accepts only canonical Amazon Japan and Rakuten product-page paths over HTTPS. It resolves and validates public addresses, pins the connection destination, disables automatic redirects, revalidates each redirect, caps the request at 15 seconds and decoded response at 2 MiB, and uses the configured proxy. It does not send cookies, authenticate, bypass CAPTCHA, or follow arbitrary hosts. CAPTCHA/access blocking and unsupported pages are recorded as fixed Korean failure categories; raw response and transport exception details are not persisted.

Parsers preserve source provider, product ID, canonical URL, fetch time, JPY source price, categories, available image metadata, options, source availability, and source-review provenance where present. Missing fields remain missing. A parsed source price is a reference value, not the ORDENOWA sale price or own stock. Source-site reviews are not registered as ORDENOWA customer reviews.

The persistent review queue deduplicates by provider/product identity, retains the previous snapshot for changed-source comparison, records approval/rejection metadata, and preserves a linked native draft. Its current JSON backend has hard limits of 5,000 source identities and 32 MiB; over-limit operations fail without pruning existing records. This is not capacity evidence for the 10,000/100,000-item targets in the older master directive. A source refresh never silently overwrites the existing draft, manager edits, sale price, or own stock. Staff must review source changes again.

## Native drafts, images, and variants

Approval creates or reuses one deterministic native product reference per source identity. Imported products are `active=0`, `visibility=none`, `available_for_order=0`, and `show_price=0` at product and shop level. Customer publication is not part of this import flow; separate seller and operating approval gates remain in effect.

Staff enter reviewed Japanese, English, and Korean text, a JPY sale price, an own-stock quantity, category, tax treatment and evidence. English and Korean review must be confirmed. Taxable products require a real PrestaShop tax group; explicit exemption requires a separate review reference. The source price is shown as context and is never silently used as the sale price. If staff choose the same number, they confirm that choice explicitly.

Source image URLs are metadata only. The importer does not download remote images. Only local files uploaded by staff are connected as native product images, with a recorded rights-review basis and reference. A synthetic CI image marker explicitly makes no usage-rights claim and is restricted to its exact disposable Actions fixture.

Options are reviewed before approval and become native Cartesian combinations with one uniform base price. The current adapter does not represent sparse option combinations or per-combination price differences; those source products must not be treated as faithfully imported until such support is implemented.

## Verification boundaries

`tests/catalog/fixtures/*.synthetic.html` and the exact-run browser adapter are invented data. They verify parser, queue, admin review, native draft persistence, image upload, options, duplicate prevention, and safe failure flow in an isolated environment. They do not establish compatibility with current live Amazon/Rakuten markup or real marketplace access.

No production SKU URL list was present in the supplied project material, and the managed cloud egress policy does not allow the marketplace hosts. No CAPTCHA or access restriction is bypassed. Live source compatibility remains unverified until a permitted item URL or authorized feed/export and allowed network route are available.

Run the PHP domain/parser/persistence checks in the existing isolated GitHub Actions workflow:

```sh
php tests/catalog/run.php
```

The isolated fresh-install workflow also runs the exact-run synthetic admin browser check and reads the created native draft back from PrestaShop. A green result proves only that tested code SHA and fixture workflow; it is not a live-import, production catalog, seller, tax, rights, publication, or customer-visible-product acceptance.
