# Procurement source parsing support and evidence

Evidence date: 2026-10-28. Fixtures are synthetic and offline. They are not copies of licensed source pages or proof that a current live listing works.

## Supported observations

| Source shape | Parsed fields | Explicit boundary |
| --- | --- | --- |
| Amazon Japan / Rakuten JSON-LD Product, lists and @graph | name, brand, description, category, JPY offer, images, additionalProperty option groups, attributed nonpublishable reviews | A unique source product must be identifiable. Unbound multiple Products, conflicting direct JPY offers and mismatched product URLs fail. @id references resolve within this bounded document only. |
| Open Graph product metadata | title, description, explicit JPY amount/currency, image/alt | No invented option, review, stock or translation data. |
| Amazon rendered public HTML | productTitle, core-price/priceblock explicit yen price, productDescription or feature bullets, landing-image dynamic URLs, labeled select options | Fixture coverage of these selectors only; no script execution, hidden API, seller offer scraping or generated combinations. |
| Rakuten explicit schema.org Product microdata | name, description, category, explicit JPY price/currency, images | Exactly one Product scope. Arbitrary merchant template markup is not covered. |
| JSON-LD BreadcrumbList | source path labels ordered by explicit positions; current product excluded | Source taxonomy remains provenance. No guessing a native category from a similar label. |
| UTF-8 and explicitly declared Shift-JIS/Windows-31J/EUC-JP | Japanese text normalized to UTF-8 | Invalid or unsupported encodings fail; no replacement characters or guessed charset. |

Prices use decimal text validation rather than floats. Positive integer yen and zero-only textual decimal fractions are accepted. Fractional yen, scientific notation, malformed grouping, overflow and JSON float prices fail. AggregateOffer.lowPrice remains a source minimum reference, not a variant price or an editable operating price. Source option groups do not establish price/stock per variant; existing review blocks multi-group native imports and requires staff confirmation for a single group.

## Review, category placement and customer reference

The Korean catalog review shows source categories and requires explicit shop-native category IDs. `PrestaShopNativeProductManager` validates the selected categories against the native shop, adds their product associations, and preserves the operator's native categories when a changed source observation is reviewed. Source breadcrumbs never create categories or override those decisions. The operator supplies localized names/descriptions, reviews options and separately records local uploaded image rights. Native imported products remain inactive, hidden, unavailable for order and with retail price display off.

`Ordenowa\Procurement\Catalog\ReviewedProductEvidence` reads one same-shop catalog review row for the native product, verifies the payload hash, decision, source revision and source identity, and exposes source URL, reference price, source category provenance and reviewed category IDs. An `OWA-IMPORT-` product without current approved evidence is refused by the native procurement adapter. The customer receives a trusted assignment snapshot of native data, not client source metadata. Reference prices are labeled separately and do not open retail checkout.

Source image URLs are observations, not usage permission. Script/data/credential/private-literal/localhost image URLs are rejected; remaining remote URLs are not downloaded or made customer-facing. Only approved local image IDs with an actual usage-rights claim can be selected by the native same-shop product adapter. Synthetic CI image markers never count as a rights claim.

## Network and access limits

The existing fetch boundary retains HTTPS product allowlists, canonical source identity, public DNS validation, pinned cURL destinations, redirect identity/loop/count checks, total/connect deadlines, retry bounds, decompressed and normalized body limits, and safe fixed failure text. HTTP authorization failures and CAPTCHA/credential forms fail as access blocked; no bypass exists.

Independent public access investigation by the release coordinator reached managed-network CONNECT 403 for Amazon Japan and Rakuten. This is an environment allowlist denial, not evidence of a marketplace CAPTCHA or parser compatibility. No approved actual product page was retrieved in this session. An allowed, rights-reviewed real sample is still needed to establish current marketplace compatibility. No paid retrieval service or proxy bypass was used.

## Executable evidence

- `php tests/catalog/run.php`: existing fetch/persistence/review suite plus parser quality behaviors.
- `php tests/catalog/parser_quality.php`: synthetic source identity, graph, exact price, hostile/missing/blocked/encoding/HTML/breadcrumb behavior.
- `php tests/catalog/fetch_access_challenge.php`: HTTP 200 challenge and credential-form classification.
- `php tests/catalog/reviewed_procurement_evidence.php`: offline trusted evidence bridge with product/shop filters and corrupt payload rejection.
- `tests/catalog/prepare_ci_procurement_product.php`: exact isolated procurement Actions guard, synthetic parser -> SQL review -> modern inactive native draft -> approved evidence -> real native M/L attribute IDs. Runtime results belong to the procurement acceptance run; syntax or offline results alone do not claim this path passed.

Observed existing warnings in the combined catalog suite: `http_response_code()` after earlier test output, and ineffective global `use Closure` in the old catalog service test. These do not fail the assertions and are not described as warning-free output.
