# ORDENOWA AI Browser QA Handoff

## 최신 수정 코드 검수 상태 (2026-10-25 21:20 UTC)

- QA source commit SHA: `95af3a9104b6e3f7bfc861155bdc73db9a91ab98` (the subsequent branch update is documentation-only); `main` unchanged at `ee02a3657448d563508687614a246e05ac61eecd`.
- Prior full isolated run #40231567083 verified SHA `aed4a3c` successfully. Work-mode GPT opened its browser artifact [ID 12613108935](https://github.com/goldeget/japan-premium-commerce/actions/runs/40231567083/artifacts/12613108935): Japanese details copy, mobile checkout controls, and the Japanese account heading were confirmed fixed.
- That review found policy condition content still English, default/synthetic `Clothes`/`Art` categories, a Korean `My Account` heading, and the long mobile breadcrumb. Code fixes for Korean account chrome and wrapping the final product breadcrumb item are in `95af3a9`.
- Full isolated run [#40233614104](https://github.com/goldeget/japan-premium-commerce/actions/runs/40233614104) verified source SHA `95af3a9104b6e3f7bfc861155bdc73db9a91ab98`: workflow and Step 80 aggregate succeeded. The aggregate recorded `STOREFRONT_BROWSER_QA_OUTCOME=success` and `PWA_BROWSER_QA_OUTCOME=success`; Step 42 product/cart, Step 49 PWA lifecycle/private-cache, Step 73 artifact upload, Step 75 screenshot coverage, and Step 83 isolated cleanup succeeded. New browser artifact: [ID 12613919270](https://github.com/goldeget/japan-premium-commerce/actions/runs/40233614104/artifacts/12613919270), `ordenowa-storefront-browser-40233614104-1`.
- Re-open the new artifact and inspect only the affected screens: `pwa-desktop-ko-account.png`, `mobile-product-detail-breadcrumb.png`, and `mobile-product-detail.png`. Record screenshots as visual evidence only; click/input behavior is assessed by the E2E steps. This Codex turn has not opened the new PNGs, so the updated visual review remains pending.
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

**코드·격리 QA:** 완료. **수정 후 시각 QA:** 위 artifact의 Work-mode GPT 열람/검수 대기. **실기기 QA:** 연결 기기 없음, `미검증—기기 연결 필요`. **운영 출시:** 실제 판매자/상품/세금/배송/결제·환불/법률/호스트 자료 대기.

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
- `bb26f06` 코드와 일치하는 source/build SHA 표시 및 run 종료 뒤에도 정해진 검수 시간 동안 유지되는 환경
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
