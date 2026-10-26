# ORDENOWA AI Browser QA Handoff

## Latest isolated browser evidence and pending PWA fix review

- Last completed full-QA source SHA: `acbdc5e78cb8a499a3885fe6dbcdc3ebf539cdcd`; the current `work` update contains a PWA browser fix awaiting Actions runtime; `main` remains unchanged at `ee02a3657448d563508687614a246e05ac61eecd`.
- Full isolated Actions [#40315517530](https://github.com/goldeget/japan-premium-commerce/actions/runs/40315517530) completed **FAILURE**. It passed preflight, image build and fresh installation. The actual aggregate is `pwa_browser_qa=failure pwa_push_qa=skipped`. Desktop JA/EN logout native clicks were intercepted; mobile JA/EN/KO consent waits timed out; desktop KO lifecycle passed. Do not infer push persistence or a full QA pass.
- QA-CI-002 is resolved in code commit `acbdc5e`: the contract now matches workflow's `grep` detail extraction. Step 9 passed in #40315517530. The original browser exit/outcome and sanitized stage/detail extraction remain enforced.
- Browser artifact [12646464536](https://github.com/goldeget/japan-premium-commerce/actions/runs/40315517530/artifacts/12646464536); diagnostics artifact [12647935305](https://github.com/goldeget/japan-premium-commerce/actions/runs/40315517530/artifacts/12647935305). Independently inspect only screenshots relevant to the neutral Korean address helper and PWA failure if present. Capture visual conclusions separately from automation. The archive could not be downloaded in the Codex environment because the configured network policy denies its storage host; the artifact IDs are supplied for approved review.
- Cart/mobile, account/address, catalog, category, carrier, checkout/order, backup and postal outcomes passed at this tested SHA. PWA lifecycle failure remains open; push persistence was skipped. Synthetic provider-free QA is not production delivery, and no real seller data, shipment, payment or device was used.
- Pending patch: `verify_push_account_control` must select the visible `data-ordenowa-push` instance because the hidden mobile sidebar hook precedes the main account-page hook. The desktop signout click now scrolls and uses the existing center-checked native WebDriver click; safe center/occluder metadata and a pre-shutdown failure capture are added. Wait for the new source SHA/run/artifact before judging runtime; screenshot alone does not establish the click or logout state.

## 다음 코드 변경의 독립 브라우저/시각 검수

- Local code source SHA before push: `50d924fdf6923a551c49c0cee65fb5b428765bb1`; remote `origin/work` was still `a890c83f04b81240b07a338f9ed734f0a25caf78` at handoff update. `main` remains `ee02a3657448d563508687614a246e05ac61eecd`. Check the push-triggered Actions run and use its actual source SHA/artifact; no new run or artifact exists yet.
- Run #40310232196 source a890c83 is **FAILURE**, with actual aggregate failures `cart_controls_browser_qa` (mobile `product_add_add_button_wait`) and `shipping_free_admin_configure` (`verify_admin_saved_carrier`). Account/address outcome is success. The account flow succeeded but old edit helper copy was semantically add-only.
- New intended visual screen: `mobile-customer-address-edit-form.png` (390×701), expected neutral Korean helper `계정에 사용할 주소 정보를 입력해 주세요.`; verify its actual fresh artifact and corresponding desktop image before closing LOCALE-003. The old artifact 12644494181 has `계정에 새 주소를 등록할 수 있습니다.` and does not verify the new edit-context copy.
- If a new carrier failure occurs, inspect `shipping-free-carrier-configure-failure.png` and the safe `FAIL: free shipping browser QA at verify_admin_saved_carrier.<allowlisted-stage>` / `carrier_state` line. The diagnostic records redacted booleans/enums only; report the exact stage and actual evidence. Do not infer a save failure from the old screenshot's successful update banner alone.
- Cart button stale-readiness handling is code-tested only until a fresh Chromium result. Inspect `cart-controls-mobile-failure.png` only if uploaded by the new run; screenshots themselves do not prove click/cart persistence.
- PWA-002 introduces these expected evidence names if each step succeeds: `pwa-desktop-ja/en/ko-push-consent.png`, `pwa-mobile-ja/en/ko-push-consent.png`, `pwa-push-owner-1.png`, `pwa-push-owner-2.png`, and `pwa-push-e2e.log`. Screens show the control only; logs establish synthetic API persistence. This QA intentionally never calls a real push provider or emits real notifications. Report the actual artifact's files and outcomes; do not assume an expected file exists.
- No approved live QA hostname or connected/remote iOS/Android device is available. Keep physical device QA and whole-site visual review unverified. The CI browser is an isolated synthetic shop.

## 이전 모바일 주소 화면 검수 (source a890c83, 2026-10-26)

- Tested source/work SHA: `a890c83f04b81240b07a338f9ed734f0a25caf78`; `main` SHA remains `ee02a3657448d563508687614a246e05ac61eecd`.
- Full isolated run [#40310232196](https://github.com/goldeget/japan-premium-commerce/actions/runs/40310232196) is **FAILURE**. Its actual aggregate failures are `cart_controls_browser_qa=failure` and `shipping_free_admin_configure=failure`; customer account outcome, including address edit, is success. The full run is not a global PASS.
- Browser artifact [12644494181](https://github.com/goldeget/japan-premium-commerce/actions/runs/40310232196/artifacts/12644494181) contains `mobile-customer-address-edit-form.png` (390×701), `mobile-customer-address-edited-after-refresh.png` (390×701), and desktop counterparts. Codex opened the mobile edit-form capture and confirmed that the helper below `주소 업데이트` now reads `계정에 새 주소를 등록할 수 있습니다.`. The after-refresh capture corresponds to same-address persistence verified by the browser flow, but the capture itself is not click testing.
- Work-mode follow-up is limited to independent visual review of those two updated mobile captures and the matching desktop captures if needed. Record the exact tested source SHA and artifact. Do not call this a whole-site or physical-device visual PASS.
- In the same run, separately noted failures were mobile `product_add_add_button_wait` (`StaleElementReferenceException`) and `verify_admin_saved_carrier` (`TimeoutException`). Downstream shipping checks were skipped. Do not present skipped outcomes as separate product failures or claim full QA success.

## 모바일 주소 수정 후속 시각 검수 (2026-10-26)

- Source/work SHA: `c045d21313af925072d55629f74ec5272d16dbc1`; focused Actions [#40307437142](https://github.com/goldeget/japan-premium-commerce/actions/runs/40307437142) SUCCESS; browser artifact [12642513725](https://github.com/goldeget/japan-premium-commerce/actions/runs/40307437142/artifacts/12642513725).
- 이 run의 실제 browser outcome은 desktop/mobile account acceptance success다. 합성 고객의 일본 주소 생성→같은 주소 edit form→native save→새 문서 및 refresh 재조회가 통과했다. 가입/중복 가입 거부/login/logout/Mailpit reset도 해당 focus 범위에서 통과했다. 주소의 실제 개인 데이터나 운영 계정은 사용하지 않았다.
- 우선 열어 볼 이름: `mobile-customer-address-saved.png`, `mobile-customer-address-edit-form.png`, `mobile-customer-address-edited-after-refresh.png`. 대응 desktop 캡처는 `desktop-customer-address-saved.png`, `desktop-customer-address-edit-form.png`, `desktop-customer-address-edited-after-refresh.png`다. 화면에서 주소 필드 값은 격리 합성 fixture다. 주소 안내 문구가 한국어로 보이고 화면폭 안에서 저장 버튼과 폼이 읽히는지 확인해 주세요. 캡처만으로 click/save를 판정하지 말고 E2E 로그와 persistence assertion을 별도 근거로 사용하세요.
- 독립 검수에서 `mobile-customer-address-edited-after-refresh.png` 390×701의 edited alias 및 한국어 목록 안내는 PASS였다. 같은 c045 artifact의 `mobile-customer-address-edit-form.png`에는 `Add a new address to your account.`가 영어로 남아 있었다. 이 c045 artifact는 후속 XLIFF/browser assertion 변경보다 앞선 캡처라 당시 시각 근거로 쓰지 않았다. 후속 a890c83 화면에서는 Korean add-only 문구를 확인했으나 edit 맥락에 맞지 않아 교체했다. 최신 neutral wording은 이 handoff 상단의 새 source evidence에서만 판정한다.
- #40300616469의 이전 timeout은 이번 focused run에서 재현되지 않았다. 해당 run에는 card→edit link→form 사이의 정확한 failing predicate가 남지 않아 이전 원인은 미확정이다. 새 단계별 진단은 이후 실패 시 안전한 화면 경로/폼/클릭 상태를 분류한다. 이 handoff는 timeout 원인 확정이나 전체 QA PASS를 뜻하지 않는다.
- #40300616469의 aggregate에서는 catalog same-ID edit/readback/reimport 및 synthetic same-order tracking browser/DB success를 유지한다. 이 검수 대상은 주소 화면 캡처와 한국어 정적 안내뿐이다. 실기기·실출고·운영 쇼핑몰을 대상으로 하지 않는다.
- Codex가 Actions artifact를 현재 환경에서 직접 다운로드할 수 없을 경우 이 handoff의 artifact link와 filename을 써서 독립 시각 QA를 수행한다. 비밀번호/token은 필요하지 않으며 테스트용 credential은 artifact 또는 채팅에 기록하지 않는다.

## 최신 자동 브라우저 증거 (2026-10-26 09:49 UTC)

- Final `work` source/remote SHA `0b68e96f1a38a36feb3732b2d3a26c06afd40c1a`; `main` remains `ee02a3657448d563508687614a246e05ac61eecd`.
- Full isolated run [#40300616469](https://github.com/goldeget/japan-premium-commerce/actions/runs/40300616469) completed **FAILURE**. Step 88's sole aggregate failure is the separate mobile customer `customer_address_edit` timeout (`control_name=none`, `control_type=none`). Do not report overall QA PASS. Catalog import, admin tracking browser, and native tracking persistence outcomes are success; Step 73 ran, establishing actual Step 72 success. Backup/restore, restart, postcode verification, artifact upload and cleanup also passed.
- New screenshot artifact [12641465628](https://github.com/goldeget/japan-premium-commerce/actions/runs/40300616469/artifacts/12641465628) and diagnostics artifact [12639904863](https://github.com/goldeget/japan-premium-commerce/actions/runs/40300616469/artifacts/12639904863) are available/unexpired. For read-only visual review, inspect only relevant current-run captures such as `catalog-import-draft.png`, `catalog-import-manager-edited.png`, `catalog-import-reimport.png`, `shipping-free-order-tracking-admin.png`, `shipping-free-order-tracking-customer.png`, and `shipping-free-order-tracking-customer-table.png`. These are run-scoped synthetic fixture pages; screenshots are not click/input verification. Do not infer production fidelity, actual carrier dispatch, or device QA.
- The prior source SHA `985e1cd3f3c30250b2052d946e0c9e383cb66752` full run [#40298163222](https://github.com/goldeget/japan-premium-commerce/actions/runs/40298163222) was SUCCESS. Independent QA opened artifact [12639887664](https://github.com/goldeget/japan-premium-commerce/actions/runs/40298163222/artifacts/12639887664), verifying the same unpaid order's admin/customer tracking row, Japanese labels, ¥0 shipping and ¥1,100 total. That capture does not establish whether the new stale-element retry path executed; do not claim it did.
- The AdminOrders wait fix catches only `StaleElementReferenceException` from a fresh body's `.text` read and returns false to the existing 35-second wait; success still requires the expected order reference plus the exact same-order admin route. The next tracking row read, cache-disabled fresh GET, customer same-order readback and native persistence assertions remain. No timeout increase, repeated submit, JS-forced click, or success-condition relaxation was added.
- Current scope is complete for catalog baseline ordering and the admin tracking browser path; leave the separate account timeout and the existing ADMIN-KO translation inventory outside this patch. No live QA hostname or physical device is available. Use artifacts only; do not request manual device review as a prerequisite for independent checks.

## 이전 작업 중 code checkpoint (2026-10-26 07:42 UTC)

- Local `work` code commits: `20f3708` (safe native readback predicate diagnostics) and `791f2d3` (JA order-detail labels and tracking-row capture). Validated code SHA: `791f2d31456abd4cfa4dd98447ba1838a41073b0`; `origin/work` still points at f4c75b8 until these commits are pushed. No new Actions run has started for these commits.
- Step 8 preflight command from `fresh-install.yml` passed locally: 538 tests, 7 skipped. Related catalog/locale/integration contracts passed 85/85; Python AST, JA XLIFF parsing, and `git diff --check` passed. Browser runtime is not available in this workspace, so the next push-triggered isolated run is still required.
- Latest complete source run remains f4c75b8 / [#40284146117](https://github.com/goldeget/japan-premium-commerce/actions/runs/40284146117), FAILURE, with actual aggregate's only failure `catalog_import_browser_qa=failure`. It stopped after Amazon approval in `native_readback/native_editor_readback`; prior safe flags show same-origin manager route, matching positive ID, editor visible, HTTP 200, and no token/access denial. New diagnostics record an allowlisted predicate name and match boolean/null immediately around reads, comparisons, same-ID uniqueness, edit preservation, and reimport; they do not print values or raw errors. The failing screenshot only showed the prior inactive notice and did not identify the failed value.
- Independent reviewer opened `catalog-import-unsupported-url.png` from artifact [12633129812](https://github.com/goldeget/japan-premium-commerce/actions/runs/40284146117/artifacts/12633129812): the safe Korean supported-URL guidance is fully visible; this is only that error screen, not catalog import completion.
- The locale patch adds Japanese strings in child-theme `ShopThemeCustomeraccount`, `ShopThemeCatalog`, and `ShopThemeCheckout` catalogs, checks the same customer's Japanese order detail, and saves an additional scrolled tracking-table screenshot. The browser assertions and screenshot are not runtime-verified until the next Actions artifact. They do not verify physical dispatch or carrier link setup.

## 최신 자동 QA: same-order synthetic tracking (2026-10-26 06:58 UTC)

- Source/work SHA: 229dd22f2b90cae8a4425e5a32578bf2141f030b. Full isolated run [#40281533046](https://github.com/goldeget/japan-premium-commerce/actions/runs/40281533046) completed SUCCESS; actual Step 73 `SHIPPING_FREE_TRACKING_PERSISTENCE_OUTCOME=success`, Step 88 aggregate, postal checks and cleanup succeeded. Independent QA opened artifact [12632622676](https://github.com/goldeget/japan-premium-commerce/actions/runs/40281533046/artifacts/12632622676). Its admin/customer screenshots and JSON/DB confirm the same synthetic unpaid order 10, reference `XWMNYZUWG`, OrderCarrier 10 and tracking value; amount ¥1,100, shipping ¥0, order state unchanged and paid amount 0. This is tracking-number assignment/readback only: no carrier destination, dispatch, scan or external link was configured.
- The tracked scenario uses a synthetic unpaid Tokyo order. The admin browser writes a tracking value through the native AdminOrders modal, reloads the same order, then signs in as the customer and reads the same order detail. The read-only PHP verifier compares native Order/OrderCarrier IDs and tracking value; it checks unchanged state/JPY total, paid amount 0, ¥0 shipping, no carrier tracking destination, and no physical dispatch/scan.
- The artifact files are shipping-free-order-tracking-admin.png, shipping-free-order-tracking-customer.png, shipping-free-order-tracking-persistence-verified.json, and shipping-free-order-tracking-persistence.log. The tracking row itself is below the customer capture fold; automation/DB readback confirms it while screenshot review does not.
- No live QA hostname or physical iOS/Android device is available. Actions loopback is run-scoped and removed at cleanup. No physical shipment, carrier scan, external tracking URL or payment occurs.

## 최신 코드 검증: catalog URL 고정 오류 피드백

- The original `invalid_url_notice_visible` fixture mismatch is fixed by f4c75b8; its Step 8 passed in CI. The latest f4 full run failure and artifact limits are recorded above. Do not count Step 46's continue-on-error green display as PASS or claim full QA success.

## 새 일본어 고객 주문 상세 번역 검수

- #40281533046 artifact 12632622676의 `shipping-free-order-tracking-customer.png`에서 `Order Reference … placed on`, `Carrier`, `Payment method`, `Shipment tracking details`가 영어로 보였다. JA 주문 상세 한 화면의 증거이며 EN/KO나 전체 고객 locale 범위로 확대하지 않는다.
- Source: pinned parent `customer/order-detail.tpl` uses `Shop.Theme.Customeraccount` for order reference and `Shop.Theme.Catalog` for payment method plus conditional `Carrier: %carrier_name%`; `_partials/order-shipments.tpl` and `_partials/order-carrier.tpl` use Customeraccount for the tracking heading and Checkout for the Carrier column. Child JA catalogs now include all three exact source domains and preserve interpolation placeholders.
- The same-customer browser flow asserts the `ja` document language, Japanese reference/payment/carrier/tracking labels and captures the tracking table after scrolling. The contract checks both shipment templates and the `Order tracking` XLIFF entry. This code-only evidence awaits Actions runtime and screenshot review. Do not translate dynamic order/carrier values as static labels or claim a real carrier destination.
- The same admin artifact showed untranslated core navigation/payment items (`Carriers`, `Boost sales`, `Méthode de paiement`, Welcome/Care Center); retain these under ADMIN-KO-001 coverage inventory.

## 완료된 합성 상품 관리자 편집 화면

- Source code SHA e085be59a0f9f061769fe7ab3cb79e025042b960; full isolated run [#40277922728](https://github.com/goldeget/japan-premium-commerce/actions/runs/40277922728) SUCCESS; Step 46 manager edit save, fresh readback and edit-preserving reimport and Step 87 aggregate succeeded.
- Artifact [12631716741](https://github.com/goldeget/japan-premium-commerce/actions/runs/40277922728/artifacts/12631716741) was downloaded and opened by independent QA. catalog-import-manager-edited.png at 1440×1057 visibly shows synthetic EN/KO names, JPY 6,780, product ID 29 and inactive notice. Image/options/Korean description are below fold and not visual-PASS.
- JSON/DB readback on the same ID confirms save confirmation, fresh GET, manager edits preserved on same-source reimport, image identity, two combinations, base stock 0 and option stocks 5/5; DB flags remain inactive, hidden and non-orderable. This closes CAT-004 synthetic edit/readback acceptance, not real source compatibility or storefront publication.
- GAP-002 remains unverified: this draft was not activated or checked as customer-visible. Keep the seller/publication gate.
- Do not repeat the closed same-ID edit/reimport flow unless changed code affects it.

## 직전 완료 합성 catalog 관리자 브라우저 증거 (2026-10-26 05:20 UTC)

- 대상 코드 SHA: `e1cd6d0c9d58ee2db64462387fef305c2ab0e757` (`work`); 전체 격리 run [#40272141646](https://github.com/goldeget/japan-premium-commerce/actions/runs/40272141646) SUCCESS. Step 46은 batch, 옵션 거부/반려, Amazon 단일 옵션 승인, 동일 native 상품 관리자 readback 및 reimport/readback을 PASS했고, Step 87 aggregate도 성공했다.
- Artifact: [`ordenowa-storefront-browser-40272141646-1` / ID 12628194683](https://github.com/goldeget/japan-premium-commerce/actions/runs/40272141646/artifacts/12628194683). Codex artifact download가 403으로 실패했으므로 이 세션에서는 PNG를 열지 않았다. 업로드/coverage 성공을 visual review PASS로 보지 않는다.
- 독립 Work-mode GPT가 catalog-import-draft.png와 catalog-import-reimport.png를 실제 열어 합성 JA/EN/KO 텍스트, JPY 표시가격, 비활성 안내와 성공 재수집 화면을 시각 확인했다. 재고 숫자·이미지 세부 영역은 화면 아래여서 시각 확인 범위가 아니며, 관련 자동 DOM/DB readback과 구분한다. 다른 캡처의 upload/coverage 성공은 각 화면을 열어 확인했다는 뜻이 아니다. e1cd6d0 flow에는 manager editor의 별도 저장 버튼 동작이 없었고, 이 공백은 d49fa7d E2E에서 추가했다.
- JSON evidence: `catalog-import-readback.json`은 same-product approval/readback/reimport 비교, `catalog-import-persistence.json`은 그 ID의 native flags/image/combination/reference DB readback이다. 자동 결과는 inactive, invisible, unavailable-for-order, image 1, combinations 2, same reference 1이다. 운영 게시/고객 노출은 하지 않았다.
- 이 run은 exact synthetic Amazon/Rakuten fixtures다. 실제 marketplace page compatibility, live fetch, image rights, real SKU, production merchant state를 입증하지 않는다. 실제 기기 QA도 이 Chromium artifact로 PASS 처리하지 않는다.

## 최신 수정 코드 검수 상태 (2026-10-25 21:20 UTC)

- QA source commit SHA: `95af3a9104b6e3f7bfc861155bdc73db9a91ab98` (the subsequent branch update is documentation-only); `main` unchanged at `ee02a3657448d563508687614a246e05ac61eecd`.
- Prior full isolated run #40231567083 verified SHA `aed4a3c` successfully. Work-mode GPT opened its browser artifact [ID 12613108935](https://github.com/goldeget/japan-premium-commerce/actions/runs/40231567083/artifacts/12613108935): Japanese details copy, mobile checkout controls, and the Japanese account heading were confirmed fixed.
- That review found policy condition content still English, default/synthetic `Clothes`/`Art` categories, a Korean `My Account` heading, and the long mobile breadcrumb. Code fixes for Korean account chrome and wrapping the final product breadcrumb item are in `95af3a9`.
- Full isolated run [#40233614104](https://github.com/goldeget/japan-premium-commerce/actions/runs/40233614104) verified source SHA `95af3a9104b6e3f7bfc861155bdc73db9a91ab98`: workflow and Step 80 aggregate succeeded. The aggregate recorded `STOREFRONT_BROWSER_QA_OUTCOME=success` and `PWA_BROWSER_QA_OUTCOME=success`; Step 42 product/cart, Step 49 PWA lifecycle/private-cache, Step 73 artifact upload, Step 75 screenshot coverage, and Step 83 isolated cleanup succeeded. New browser artifact: [ID 12613919270](https://github.com/goldeget/japan-premium-commerce/actions/runs/40233614104/artifacts/12613919270), `ordenowa-storefront-browser-40233614104-1`.
- Independent QA opened pwa-desktop-ko-account.png and mobile-product-detail-breadcrumb.png from artifact 12613919270 and confirmed the Korean account title and long breadcrumb wrapping for those two captured screens only. This is not whole-page or physical-device verification. Inspect the pending manager-edit screenshot from run #40275686536 separately.
- The checkout policy labels and helper copy are the dynamic `conditions_to_approve` content rendered by Hummingbird `payment.tpl`, not static theme translation strings. Do not invent approved legal Japanese; await seller-provided copy. `Clothes`/`Art` are catalog category data; do not assign taxonomy labels without an approved mapping.
- The local Codex Chromium launcher failed during crashpad initialization, so no new local image was captured or visually passed. The current source has 121 focused Python tests passing; this is separate from the successful Actions/browser evidence above.

## 전체 QA와 시각 검수 (직전 코드 SHA `aed4a3c`, 2026-10-25 20:50 UTC)

- QA 대상 코드/현재 `work`: `aed4a3cc6e143258e9f493603dd226bfa41b34aa`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`이며 변경하지 않았다.
- 전체 격리 Actions [#40231567083](https://github.com/goldeget/japan-premium-commerce/actions/runs/40231567083)은 workflow 성공, Step 80 aggregate `PASS: isolated browser QA and official postcode verification completed.`다. Step 49의 PWA matrix는 desktop/mobile × JA/EN/KO 여섯 경우가 각각 PASS이며 `PWA_BROWSER_QA_OUTCOME=success`다.
- 최신 browser screenshot artifact: [ID 12613108935](https://github.com/goldeget/japan-premium-commerce/actions/runs/40231567083/artifacts/12613108935), `ordenowa-storefront-browser-40231567083-1`. 이 검수 요청은 Work-mode GPT가 artifact를 다운로드해 PNG를 실제 열어 보도록 한다. 이 Codex 세션은 PNG를 직접 열지 않았다.
- Work-mode GPT는 변경 후 화면의 가시성·번역 상태만 확인하고 자동 E2E와 합쳐 클릭/입력 테스트라고 보고하지 않는다. 캡처는 합성 CI 상품/쿠폰/주문 화면이며 실제 판매 catalog나 운영 환경의 fidelity 증거가 아니다.

| 화면/검수 대상 | 자동 확인과 변경 | Work-mode GPT가 확인할 점 |
| --- | --- | --- |
| `shipping-free-checkout-mobile.png` (390×701 및 500px 대응) | #402294의 후속 screenshot에서 390px 화면의 checkout buttons가 bottom nav 위에 완전히 보였다. #402315 checkout browser step도 success다. | 최신 캡처에서 뒤로/계속 버튼, 고정 nav, 하단 여백 및 document-level 가로 넘침을 다시 확인한다. |
| `desktop-korean-login-email.png` | #402294의 screenshot에서 비밀번호가 `비밀번호`로 보였다. | 최신 캡처에서 한국어 label과 input 연결 상태를 확인한다. |
| `checkout-desktop-offline-payment-review.png` | `Show details` 및 accessible cart-details label에 일본어 XLIFF를 추가하고 Step 60에서 검사한다. | `詳細を表示`와 `カートの詳細を表示`가 화면/접근성 이름에 보이는지 확인한다. `Security policy`, `Delivery policy`, `Return policy` 및 helper 문구는 승인된 일본어 판매 정책 없이는 임의로 번역하지 않는다. synthetic coupon 명칭은 테스트 데이터로 표시한다. |
| `pwa-desktop-ja-account.png`, `pwa-mobile-ja-account.png` | JA sidebar title/aria-label과 GDPR link를 번역하고 PWA account 검사에서 보이는 link를 확인한다. Mobile에서 hidden sidebar copy는 대상이 아니다. | Desktop에서 sidebar `マイアカウント` 및 label을, mobile에서 표시되는 GDPR/privacy link를 확인한다. |
| `desktop-home.png`, `brand-desktop-published.png` | `Clothes`/`Art`는 CI의 default/synthetic categories로 남아 있으며 taxonomy mapping을 만들지 않았다. | logo와 브랜드 표현을 확인한다. 합성 category 명칭을 실제 storefront용 확정 번역으로 판정하지 않는다. |
| `mobile-product-detail.png` (390×701) | Hummingbird breadcrumb는 가로 스크롤 UI이며 기존 document overflow 검사가 통과했다. CSS는 변경하지 않았다. | breadcrumb가 잘려 보이면 screenshot만으로 overflow 결론을 내리지 말고 horizontal-scroll indication/interaction evidence가 있는지 분리 기록한다. |
| ja/en/ko desktop/mobile PWA account 및 offline 캡처 | Step 49의 6개 PWA case와 private cache 검증 PASS. | 문자 깨짐, 잘림, button, scroll, error appearance를 화면별로 살핀다. 시각 검수는 테스트 상호작용 증거가 아니다. |

**코드·격리 QA:** e1cd6d0/#40272141646 기준 완료; d49fa7d manager edit flow의 runtime 결과 대기. **시각 QA:** #402336 artifact 12613919270의 한국어 계정 제목과 모바일 breadcrumb 두 화면은 독립 검수자가 실제 열어 확인했고, #402721 artifact 12628194683의 draft/reimport 두 화면도 독립 확인했다. 이번 run의 manager-edit 캡처는 아직 확인 대기다. **실기기 QA:** 연결 기기 없음, 미검증—기기 연결 필요. **운영 출시:** 실제 판매자/상품/세금/배송/결제·환불/법률/호스트 자료 대기.

## 기준 코드와 기존 증거

- 저장소: `goldeget/japan-premium-commerce`
- 브라우저/격리 QA를 통과한 코드 SHA: `bb26f06168e0a10a50607ce4e5171666656611b1`
- 이 handoff를 시작할 당시 `work` HEAD: `b94d1f0ba3418b5724f07735e7186c2adbcb6555`. `bb26f06` 이후 변경은 문서 전용이며 코드 변경이 없으므로 문서 갱신만 이유로 전체 QA를 다시 실행하지 않는다.
- 집중 QA [#40225474420](https://github.com/goldeget/japan-premium-commerce/actions/runs/40225474420)과 전체 격리 QA [#40226037762](https://github.com/goldeget/japan-premium-commerce/actions/runs/40226037762)은 성공했다. 전체 Step 80 aggregate와 workflow conclusion이 success다.
- 전체 실행의 browser artifact: [ordenowa-storefront-browser-40226037762-1](https://github.com/goldeget/japan-premium-commerce/actions/runs/40226037762/artifacts/12611855740), ID `12611855740` (21,326,811 bytes). 메타데이터상 2026-11-24 19:42 UTC까지 보관된다.

## 최초 수정 전 캡처 시각 검수 (#402260 artifact)

Work-mode GPT가 위 artifact를 다운로드해 실제 PNG를 열어 확인했다. 캡처는 QA source SHA `bb26f06168e0a10a50607ce4e5171666656611b1`의 합성 CI 환경 결과다. 이 검수는 코드 변경 전 화면의 시각 증거이며, 이후 수정의 통과 근거로 재사용하지 않는다.

| 캡처 | 실제 관찰 | 분류와 대응 |
| --- | --- | --- |
| `shipping-free-checkout-mobile.png` (390×701) | `Back to 住所` 버튼 아래쪽이 고정 하단 메뉴에 가려졌다. 500×701 대응 캡처에서는 같은 가림이 보이지 않았다. | P2 모바일 checkout 레이아웃 결함. 수정은 checkout 중 고정 메뉴를 숨기고 해당 버튼/일본어 문구를 브라우저 QA에서 확인한다. 새 실행으로 검증 대기. |
| `checkout-mobile-offline-payment-review.png`, `shipping-free-checkout-mobile.png`, `shipping-free-order-confirmation-desktop.png` | JA checkout에 `Pay by Check`, `Place Order`, `Write a comment about this order`, 영어 결제 안내와 영어/일본어가 섞인 이동 버튼이 보였다. 화면에 합성 CI 상품, ¥1,100 및 무료배송 금액이 보였으며 실제 주문 click/input을 증명하는 이미지는 아니다. | P2 일본어 checkout 문구 누락. 일반 checkout 라벨을 JA XLIFF로 보완하고 CI 전용 check-payment 옵션/확인 화면은 JA 번역으로 보완했다. 새 실행으로 검증 대기. |
| `desktop-korean-login-email.png` (1440×817) | 한국어 login 화면의 비밀번호 label이 `Sleutelwoord`로 표시됐다. | P2 한국어 화면 결함. 한국어 `Password` label을 추가하고 브라우저 검사에서 이메일과 별도로 접근 가능한 비밀번호 label을 검증한다. locale fallback의 실제 런타임 원인은 새 QA로 확인 대기. |
| `brand-desktop-published.png`, `pwa-mobile-ja-account.png` | 로고/네이비·블루 시각 체계는 일관되고 JP/EN/KO 글자에 tofu는 보이지 않았다. JA header에는 `Clothes`, `Art`, account에는 `GDPR - Personal data`가 남았다. | GDPR link는 자식 테마의 JA/KO localized copy로 보완하고 PWA account 검사에 locale별 assertion을 둔다. `Clothes`/`Art`는 CI의 기본/합성 category 데이터로 보이며 실제 판매 taxonomy가 없으므로 번역 데이터를 임의로 만들지 않는다. |
| `mobile-product-detail.png` (390×701) | breadcrumb 상품명이 오른쪽에서 잘려 보였으나 이미지로는 DOM overflow나 가로 스크롤 여부가 확인되지 않았다. | 결함 미확정. 새 화면이나 DOM 측정에서 실제 잘림/가로 overflow가 확인되기 전에는 CSS를 바꾸지 않는다. |

모바일 캡처에서는 제품명 대신 `[CI ONLY]` 상품, `No image` 등 합성 fixture 텍스트가 보인다. 모바일 item price와 무료배송은 보였지만 화면 아래의 최종 total은 보이지 않았고, subtotal/discount/shipping/total이 모두 보인 것은 desktop 캡처였다. 이 artifact는 실제 상품, 운영 결제, 실판매 화면의 fidelity 증거가 아니다.

## 역할과 안전 경계

| 담당 | 작업 |
| --- | --- |
| Codex GPT | 코드 수정, 정적/단위 검사, run-scoped 합성 fixture, 격리 GitHub Actions 자동 QA, 결함 재현·최소 수정. 기존 성공 QA를 재사용하며 코드 변경이 있을 때만 영향 범위에 맞는 CI를 실행한다. |
| Work-mode GPT | 승인된 Actions artifact의 PC/모바일 캡처를 열어 시각 검수한다. 승인된 live QA 주소가 제공된 경우에만 추가 브라우저 조작과 캡처를 한다. OS/브라우저/viewport/SHA/fixture 및 화면별 결과를 기록한다. |
| 사용자 | 수동 실기기 QA를 담당하지 않는다. 제품 검수 결과는 AI가 캡처·로그에 근거해 기록한다. |

운영 DB, production, 실결제, 실거래는 검사 대상으로 사용하지 않는다. 비밀번호·토큰은 문서/채팅에 넣지 않고, Work-mode GPT가 접근할 수 있는 승인된 secret binding만 사용한다. 현재 승인된 Work secret 경로는 이 Codex 환경에서 확인되지 않는다.

## 현재 접근 가능한 환경

- Actions run은 ephemeral GitHub runner의 loopback `127.0.0.1:18080`에서만 상점을 실행했다. Step 83이 run-scoped containers와 volumes를 정리해 지금 접속 가능한 QA site나 동일 run DB는 없다.
- 저장소와 Actions에서 안정적인 staging/QA hostname 또는 access window를 찾지 못했다. 이 런타임의 loopback `127.0.0.1:18080`은 HTTP 응답이 없어 재사용 가능한 shop URL이 아니다. staging 주소를 만들어 내거나 workflow localhost를 공개 주소로 취급하지 않는다.
- 현재 Codex 환경에는 headless Chromium `154.0.8037.57`과 Playwright `1.62.0`이 있다. iPhone/iPad/Android viewport profile emulation은 가능하지만 이번 요청에서 실행 가능한 shop target이 없다. 따라서 이 환경에서 ORDENOWA 화면을 실제 캡처하거나 시각 검수하지 않았다. 이 emulation capability를 PASS로 기록하지 않는다.
- 연결된 iPhone/iPad/Android, USB device, iOS/Android simulator, Appium 또는 승인된 remote device farm이 노출되지 않았다. 실제 기기 검증은 **미검증—기기 연결 필요**다. Chromium emulation을 Safari/WebKit 또는 실기기 결과로 간주하지 않는다.
- Codex 환경의 artifact ZIP 다운로드는 HTTP 403/전송 오류로 막혔지만 Work-mode GPT가 위 artifact를 열어 시각 검수를 마쳤다. 새 코드용 screenshot은 새 Actions artifact가 생성된 뒤 Work-mode GPT가 다시 확인해야 한다.

## 이전 artifact의 최초 작업 목록 (최신 artifact는 위 검수 요청 참조)

1. 새 수정 SHA에서 전체 run이 생성되면 그 실행의 artifact `ordenowa-storefront-browser-<run-id>-1`을 열어 아래 변경 화면을 다시 확인한다. 동일 screenshot을 고정된 기존 #402260 artifact에서 재검수하지 않는다.
2. `shipping-free-checkout-mobile.png`와 500px 대응 checkout screenshot에서 현재 배송 단계 뒤로/계속 버튼과 nav의 교차, 화면 아래 여백, 가로 overflow를 확인한다. `checkout-mobile-offline-payment-review.png`에서 check-payment 옵션 label, `shipping-free-order-confirmation-desktop.png`에서 결제 확인 copy의 JA 통일을 확인한다.
3. `desktop-korean-login-email.png`에서 비밀번호 label, `pwa-mobile-ja-account.png`와 en/ko 대응 캡처에서 개인정보 link를 확인한다. 문자열이 실제 화면에서 번역됐는지와 label 관계를 확인하고, 자동 E2E 결과와 screenshot review를 따로 기록한다.
4. 나머지 고객 ja/en/ko, 한국어 관리자 PC/mobile 캡처에서 글자·폰트·버튼·잘림·scroll·입력/error 표시를 확인한다. 상품/옵션/쿠폰/주소/무료배송/주문/로그아웃/PWA cache/RMA 동작은 #402260 자동 증거를 재사용하고 캡처만 시각 평가한다.
5. `Clothes`/`Art`는 미정인 실제 category 명칭을 대신해 로컬라이즈하지 않는다. `mobile-product-detail.png` breadcrumb는 DOM overflow가 확인되기 전까지 시각 관찰로만 기록한다.
6. 발견된 신규 결함은 파일명, locale, viewport, 기대/실제, 영향, 재현 동작을 기록한다. Codex가 최소 수정 후 영향 범위만 재검증한다.

## Live 브라우저 검증에 필요한 환경

실제 interactive QA가 꼭 필요한 미검증 범위만 실행할 수 있도록 다음 환경을 한 번에 제공한다. 이는 현재 존재한다고 확인된 값이 아니다.

- 재사용 시간대가 명시된, Work-mode GPT에서 열 수 있는 승인된 격리 QA HTTPS URL
- 229dd22 코드와 일치하는 source/build SHA 표시 및 run 종료 뒤에도 정해진 검수 시간 동안 유지되는 환경
- 테스트 전용 고객·관리자 계정과 비밀번호 재설정 메일을 받을 test inbox; secret은 승인된 비밀 저장 경로로만 전달
- fixture 이름/식별을 위한 run ID, 고객 locale, synthetic SKU/variant/coupon/order/RMA ID와 초기 상태. 실제 개인정보 대신 `example.invalid` synthetic identities 사용
- 지원이 필요한 경우 승인된 Chromium/Safari/iOS/Android 또는 원격 기기의 모델·OS·브라우저 버전 기록
- QA 종료 후 격리 데이터 및 계정 cleanup 담당/절차

이 조건이 제공되기 전에는 hostname·권한·fixture ID·계정을 추측하지 않는다. 기존 자동 검사로 독립 검증된 기능은 다시 열지 않는다.

## 검증 대상·담당·환경·증거·현재 결과

| 대상 | 담당 | 환경 및 기존 증거 | 현재 결과 / 남은 확인 |
| --- | --- | --- | --- |
| ja/en/ko 고객 화면의 시각 상태 | Work-mode GPT | 기존 artifact의 desktop/mobile 캡처. #402260 Steps 39/49는 account/PWA 언어·viewport 자동 검사를, Step 42는 상품/장바구니를 확인했다. | 자동 기능 검사는 PASS. 각 언어의 제품·checkout 시각 표현 전체는 캡처를 열기 전까지 미검수. |
| 한국어 관리자 화면 | Work-mode GPT | artifact의 Step 35 배송 링크, Step 41 상품 작성/수정, Step 46 권한, Step 70 RMA 화면 캡처. Step 41은 narrow viewport overflow 자동 검사 포함. | 일부 화면/경로 자동 검사는 PASS. 전체 관리자 한국어 coverage나 시각 일관성 PASS는 아님. |
| 옵션/수량/쿠폰/주소/무료배송/금액 | Codex GPT 자동 QA 결과 재사용; Work-mode GPT는 캡처만 시각 확인 | #402260 Steps 42–43, 56–65; Chromium desktop/mobile와 격리 합성 상품/주문. | 자동 동작·금액 대조 PASS. 주소 자동완성과 locale 조합 전체의 시각 review는 artifact에서 확인. 합성 tax fixture는 실상품 세무 근거가 아님. |
| 회원/로그아웃/개인정보 캐시 | Codex GPT 자동 QA 결과 재사용 | #402260 Steps 39/49, desktop/mobile, ja/en/ko cache route cases. | 계정·logout·private route 동작 PASS. 관련 화면의 시각 review는 artifact 미열람 상태. |
| 고객/관리자 RMA | Codex GPT 자동 QA 결과 재사용; Work-mode GPT는 화면만 시각 확인 | #402260 Steps 69–71; same run-scoped synthetic order/RMA; `1→2→1` save/readback. RMA 캡처 2종 이름은 위에 표시. | 저장/복원·lifecycle PASS. 캡처의 시각·레이아웃 review는 artifact 미열람 상태. |
| typography/overflow/scroll/button/validation/error appearance | Work-mode GPT | 기존 screenshots only; artifact viewer needed. | 체계적인 screenshot audit 미완료. 시각 증거를 봐야 severity와 구체 화면을 판정 가능. |
| 실기기 PWA/터치/회전/OS 키보드/back-resume | Work-mode GPT, 승인된 device/farm에서 | 현재 연결 device/farm 없음. Chromium emulation은 실제 iOS/Android가 아님. | 미검증—기기 연결 필요. 사용자 수동 검수 요청은 하지 않음. |
| 운영 판매/거래 준비 | 운영 정보 제공·승인 담당자 | 기존 `미정` 목록은 [개발 현황](DEVELOPMENT_STATUS.md)에 유지. | 자료·환경 대기; 이 handoff로 임의 입력을 채우지 않음. |


`main` `ee02a3657448d563508687614a246e05ac61eecd`는 QA나 문서 작업에서 변경하지 않는다.
