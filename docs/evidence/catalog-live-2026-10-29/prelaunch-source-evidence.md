# Prelaunch catalog source evidence — 2026-10-29

This note records bounded public-source observations. The saved captures are TinyFish `fetch_content` rendered-DOM extractions, not raw origin HTTP response bytes. No native catalog import was performed, neither listing is approved as a launch SKU, seller authorization was not established, and public image visibility does not establish image-use rights. No image was reused.

## Tokka-COM / Rakuten — Panasonic N-W1A, one unit

Captured 2026-10-29 03:17:26 UTC (12:17:26 JST), with public Rakuten item and shop-filtered search pages retrieved using `ttl=0`.

- Item detail: <https://item.rakuten.co.jp/tokka-com/4549980616819/>
- Shop-filtered Rakuten listing: <https://search.rakuten.co.jp/search/mall/4549980616819/?sid=313470>
- Exact item link displayed on the listing: <https://item.rakuten.co.jp/tokka-com/4549980616819/?variantId=4549980616819>
- Seller classification: Rakuten Ichiba, 特価COM (Tokka-COM), shop ID `313470`; Panasonic-authorized status was not verified.
- Title: `パナソニック(Panasonic) N-W1A 洗濯槽クリーナー 塩素系 縦型全自動式用`.
- Product ID `4549980616819`; listing item ID `313470/10765360`; fixed specification `1回分 (1500ml)`; no product option selector appeared in the item-detail extraction.
- Original category: `家電 > 洗濯機・衣類乾燥機 > 洗濯機関連アクセサリー`.
- The listing card displayed item price ¥2,106 plus shipping ¥550 (¥2,656 combined). The item-detail extraction itself did not contain a price.
- The item detail displayed `【在庫あり】`, but also advised customers to click its stock-status banner to confirm exact availability. That banner was not clicked; this is only the label shown at capture time, not a guaranteed inventory statement.
- Delivery estimate shown: order by 15:00 for earliest delivery 10/30; the marketplace describes delivery dates as estimates.
- Saved extraction checksums: item capture, 9,079 bytes, SHA-256 `5D3140A546B1A1E44D2FC92229CFC4DC3015C758F42F470E46F1BB52E995A17A`; listing card, 8,349 bytes, SHA-256 `81F75B1F74C1C73B50EA82B69E7EB29CFBEE6B86A51ABE6A4F8275A4143F7BF1`.
- Detail: [rakuten-tokka-com-4549980616819-evidence.md](rakuten-tokka-com-4549980616819-evidence.md).

## Rakuten24 — Panasonic N-W1A, one unit

Captured 2026-10-29 03:14:53 UTC (12:14:53 JST), from public Rakuten item and shop-filtered search pages using `ttl=0`.

- Item detail: <https://item.rakuten.co.jp/rakuten24/4549980616819/>
- Shop-filtered Rakuten listing: <https://search.rakuten.co.jp/search/mall/4549980616819/?sid=261122>
- Exact one-unit item link: <https://item.rakuten.co.jp/rakuten24/4549980616819/?variantId=4549980616819>
- Seller classification: 楽天24 (Rakuten24), shop ID `261122`; Panasonic-authorized status was not verified.
- Title: `洗濯槽クリーナー(縦型全自動式用) N-W1A(1個入)`; product ID `4549980616819`; listing item ID `261122/10992507`; one unit, 1500 ml.
- Original category: `日用品 > 洗濯用品 > 洗濯機用品 > 洗濯槽クリーナー`.
- The listing card displayed item price ¥2,246 plus shipping ¥770 (¥3,016 combined). The detail extraction itself did not contain a price. Search results also included separate multipacks; evidence above is for the exact one-unit item link.
- Delivery estimate shown: order by 10/30 12:00 for earliest delivery 10/31. Neither item detail nor listing card displayed a literal stock label; availability is unknown.
- Saved extraction checksums: item capture, 5,485 bytes, SHA-256 `3667E2643E37BAA6FFF90715856E0F83FCFFC2C4D357EFE2D38A146FED807FC9`; listing card, 8,249 bytes, SHA-256 `5F74E524B74F1F9A350F933F02539A4E17EDC3EE8926DC0707045137CED8E5BA`.
- Detail: [rakuten24-4549980616819-evidence.md](rakuten24-4549980616819-evidence.md).

## Acceptance boundary and retrieval limits

These paired sources verify listing fields across an item page and a separate seller-filtered, first-party marketplace listing. They do **not** prove that the current item-page-only parser can extract price, nor do they satisfy a single-page price/availability acceptance gate. Keep missing item-page price fail-closed; no SKU was imported or approved.

Direct PowerShell retrieval of Rakuten search pages failed with a DNS host-resolution error. Native Chrome window capture timed out after the documented fresh-window retry. TinyFish public rendered-DOM extraction worked; its returned content must not be described as raw wire HTML. No login, cart, purchase, checkout, CAPTCHA, or access-control bypass was used.

Amazon Japan candidates were also not accepted: observed direct pages either had no featured offer/current price, were unavailable, or remained in a United States delivery/USD context even when the ordinary public URL included Japanese language and JPY display parameters. Those observations do not establish Japan-local availability or a Japanese offer. See [live-source-observations-2026-10-29.md](live-source-observations-2026-10-29.md).

Evidence storage: referenced rendered-DOM capture files remain in the task private work/catalog-round2 folder; their bytes are not included in this Git source record. No native browser screenshot was obtained.
