# Rakuten Tokka-COM live listing evidence — 2026-10-29

Capture time: 2026-10-29 03:17:26 UTC (2026-10-29T12:17:26.000Z, JST)
Capture route: TinyFish public `fetch_content` with cache freshness `ttl=0`; item detail captured as HTML extraction and search listing captured as HTML extraction scoped to the observed `#root` element. The saved files are the exact rendered-DOM extraction strings returned by that tool, not raw HTTP wire-response bytes.

## Source pages

- Item detail: https://item.rakuten.co.jp/tokka-com/4549980616819/
- First-party Rakuten shop-filtered search listing: https://search.rakuten.co.jp/search/mall/4549980616819/?sid=313470
- Exact listing item link: https://item.rakuten.co.jp/tokka-com/4549980616819/?variantId=4549980616819

## Live source fields

- Marketplace and seller: Rakuten Ichiba listing, seller 特価COM (Tokka-COM), shop ID 313470. This does not establish Panasonic-authorized status.
- Listing item ID: 313470/10765360; product identifier: 4549980616819.
- Item title: パナソニック(Panasonic) N-W1A 洗濯槽クリーナー 塩素系 縦型全自動式用.
- Fixed specification: 1回分 (1500ml); no product option selector appears in the detail extraction.
- Original Rakuten category path: 家電 > 洗濯機・衣類乾燥機 > 洗濯機関連アクセサリー.
- Exact current listing: ¥2,106 item price + ¥550 shipping = ¥2,656 price-plus-shipping total.
- Availability label on item detail: 「【在庫あり】」.
- Availability caveat also printed on the same detail page: 「正確な在庫状況は上記バナー『在庫状況を確認する』をクリックして頂き、必ずご確認ください。」 The stock banner was not clicked. Report the label as displayed at capture time, with the seller's caveat; do not call it a guaranteed inventory state.
- Fulfillment text on the listing: 「15:00までの注文で最短10/30(翌日)お届け」. Rakuten labels this as an estimate; exact delivery is confirmed at checkout.
- Image URL in item metadata: https://shop.r10s.jp/tokka-com/cabinet/441/4549980616819.jpg. Public visibility does not establish image-use permission; no image was reused.

## Parser implication

The direct item-detail extraction contains title, identifier, category, fixed specification and the seller's explicit in-stock label, but no price. The shop-filtered first-party Rakuten search card contains the exact price, shipping, total, exact item href and delivery estimate. This is useful live field-level evidence, but it does not show that the current item-page-only parser can extract the price. Keep missing-price behavior fail-closed; no parser change is proposed from this evidence.

## Retrieval limits

PowerShell `Invoke-WebRequest` to Rakuten's search host failed DNS resolution at 2026-10-29 03:11:26 UTC, so no raw HTTP response was collected. Native Chrome window capture timed out twice after the documented fresh-window retry, so no native screenshot was obtained. No login, cart, purchase, checkout, CAPTCHA or access-control bypass was used.

## Saved extraction checksums

These SHA-256 values are for the saved TinyFish rendered-DOM extraction files, not raw origin HTTP response bytes:

- `rakuten-tokka-com-4549980616819-item-capture.html` — 9079 bytes; `5D3140A546B1A1E44D2FC92229CFC4DC3015C758F42F470E46F1BB52E995A17A`.
- `rakuten-tokka-com-4549980616819-offer-card.html` — 8349 bytes; `81F75B1F74C1C73B50EA82B69E7EB29CFBEE6B86A51ABE6A4F8275A4143F7BF1`.

Evidence storage: referenced rendered-DOM capture files remain in the task private work/catalog-round2 folder; their bytes are not included in this Git source record. No native browser screenshot was obtained.
