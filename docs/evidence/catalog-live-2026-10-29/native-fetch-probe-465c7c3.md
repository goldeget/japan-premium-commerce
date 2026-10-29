# Native catalog fetch/parser probe — 2026-10-29

This evidence records the fixed live-source probe from candidate commit `465c7c3cd0c67ca15577b41d3a300acdd8b7a894`.

| Run evidence | Value |
| --- | --- |
| GitHub Actions run | `40827877833` |
| Safe-output artifact ID | `12877576413` |
| Artifact ZIP SHA-256 | `a584ee55a70669bd7868eb6af8695094d876a2a2e18af5672104d2e956b4fb34` |
| Copied safe JSON SHA-256 | `2E998F3BACC9905C10A3DB6C632524554EBC8729357BD8E34E61463564BC2D5C` |
| Result | Probe completed; parser acceptance failed; no SKU accepted |

The artifact contains only fixed URLs, bounded titles/metadata, response-body hashes and byte counts, and fixed failure enums. It contains no response body, raw response headers, exception text, or image bytes. `fetched_html_sha256` and `fetched_html_bytes` describe `PublicProductFetcher`'s content-decoded, UTF-8-normalized entity body, not compressed wire octets.

## Per-source result

| Fixed item URL | Observation time (UTC) | Normalized body bytes | SHA-256 | Parser result |
| --- | --- | ---: | --- | --- |
| <https://www.amazon.co.jp/dp/B0836L96DZ> | Not returned | Not returned | Not returned | `fetch/access_blocked`; the artifact does not retain an HTTP status or distinguish the blocking cause |
| <https://item.rakuten.co.jp/tokka-com/4549980616819/> | `2026-10-29T06:13:25Z` | 42 | `0eb8d306e8083ec6aa706e7940b86328732bb468c3194d4619f47870ee7c6bd3` | `parse/parser_rejected`; title was not extracted |
| <https://item.rakuten.co.jp/rakuten24/4549980616819/> | `2026-10-29T06:13:35Z` | 42 | `138c155ec300694f62b86697467ee4d082d5c8e66ccf7ebf757e0a45be46cf92` | `parse/parser_rejected`; title was not extracted |

For the Rakuten records, the fetcher returned a `FetchedProduct`. Its contract returns a product body only after accepting a nonempty HTTP 200 `text/html` or `application/xhtml+xml` response, validating encoding, enforcing the size limit, and checking its known authentication/challenge markers. The artifact does not preserve response status, headers, final transport endpoint, or body. These records therefore establish only that the fetch boundary accepted a small HTML entity body; they do not establish that it was the marketplace product page or identify a denial, challenge, maintenance response, or other cause. The two distinct hashes show the two 42-byte bodies were not byte-identical after normalization.

Code review found no truncation path that returns a partial body as successful: [`ResponseBuffer`](../../../modules/kuraneacatalog/src/Fetching/ResponseBuffer.php) appends complete cURL chunks and aborts on overflow, [`CurlTransport`](../../../modules/kuraneacatalog/src/Fetching/CurlTransport.php) refuses an exceeded buffer, and [`HtmlDocumentEncoding`](../../../modules/kuraneacatalog/src/Parsing/HtmlDocumentEncoding.php) either returns/converts the whole body or fails. The [`fixed probe`](../../../tools/catalog/catalog_live_probe.php) intentionally emits only the normalized entity-body hash and size. The 42-byte size is an observed small payload; its exact content and origin cannot be inferred from the hash. `parser_rejected` is deliberately generic, so null price/options/category/image counts are not evidence that those fields were absent from a product page.

## Acceptance and rights status

- No source produced an accepted parser snapshot. No title, exact JPY price, options, category, or image metadata was accepted as a product record.
- No native catalog import or launch-SKU approval occurred. The artifact reports `catalog_imported: false` and `image_rights_approved: false`.
- No image content was downloaded or reused. Public visibility does not establish image-use permission.
- Amazon's `access_blocked` result is retained as the fetcher's safe classification only; there is no evidence here to call it HTTP 403, CAPTCHA, or any more specific cause.
- The probe used the existing normal public fetcher and parser path. It did not log in, use cookies, purchase, access checkout, retry through a browser, or bypass an access control.

The earlier Rakuten field observations are separate public rendered-DOM captures, not raw HTTP response HTML and not parser acceptance. See [the prior source-observation record](prelaunch-source-evidence.md); those frontend observations cannot replace a successful native fetch/parser result.

## Safe machine-readable record

The exact safe JSON copied from artifact `12877576413` is [catalog-live-probe.json](catalog-live-probe.json). Its body hashes are for normalized entity bodies only; the original HTML was not retained.
