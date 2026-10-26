# ORDENOWA 개발 현황

## 최신 주소 편집 집중 QA 및 전체 회귀 준비 (2026-10-26)

현재 `work`와 실제 원격은 `c045d21313af925072d55629f74ec5272d16dbc1`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다. 이번 checkout focus QA [#40307437142](https://github.com/goldeget/japan-premium-commerce/actions/runs/40307437142)는 SUCCESS이며 account/browser evidence artifact [12642513725](https://github.com/goldeget/japan-premium-commerce/actions/runs/40307437142/artifacts/12642513725)를 저장했다.

- #40300616469의 유일한 aggregate 실패는 `account=failure`, mobile `customer_address_edit` timeout이었다. 당시 캡처에서 주소 카드는 남아 있고 수정 링크가 보였으나 그 run은 edit 단계 내부 세부 원인을 기록하지 않았다. 이번 focused run은 desktop/mobile 모두 합성 일본 주소 생성·동일 주소 수정·저장·새 문서 및 refresh 후 재조회, 가입·중복 가입 거부·로그인/로그아웃·Mailpit reset까지 통과했다. 과거 timeout은 재현되지 않아 원인을 클릭 실패/폼 진입/저장 문제 중 하나로 단정하지 않는다.
- `tests/e2e/verify_customer_account_browser.py`는 주소 카드·ID 일치·edit link·same-origin route·scroll/clickability/center hit/native click·edit form visibility/ID 검사로 단계를 나눴다. 실패 진단은 허용된 stage/error/path/occluder 분류와 boolean/null만 출력하고 query, 주소/이름/email, token, DOM 원문을 배제한다. 수정 성공/refresh 뒤 캡처도 추가했다. native 클릭, 원래 wait 제한, 동일 주소 ID/저장/새 조회 조건은 유지했다.
- 고객 한국어 주소 목록 안내는 child-theme XLIFF로 번역했고 #40307437142 Step 41 자동 assertion이 통과했다. 독립 검수는 artifact 12642513725의 `mobile-customer-address-edited-after-refresh.png` 390×701을 열어 편집값과 목록 안내를 시각 확인했다. Codex에서 PNG를 직접 연 것은 아니다.
- 독립 재검수는 artifact 12642513725의 `mobile-customer-address-edited-after-refresh.png` (390×701)에서 같은 합성 주소 ID의 수정값과 한국어 목록 안내가 보임을 확인했다. `mobile-customer-address-edit-form.png`에는 정적 `Add a new address to your account.`가 영어로 남아 있음을 추가 발견했다. 현재 XLIFF에 한국어 문구를 추가하고 edit form에서 정확히 검사하는 browser assertion을 작성했으나, 이 새 코드 변경은 아직 Actions에서 실행되지 않았다.
- 이전 b83ab55 실행 #40307147507은 브라우저가 시작되기 전 preflight Step 8 실패였다. 실제 이유는 commit prefix로 focus=true가 된 환경을 전체 집계 fixture가 물려받은 것이며 제품의 주소 결함이 아니다. c045d21은 full-mode fixtures가 false를 명시하게 하고 account-focus aggregate fixture만 true를 설정했다. 같은 SHA의 account focus #40307437142는 aggregate success다.
- 그 focused run은 workflow condition 누락으로 관련 없는 admin security fixture/browser도 실행했다. 현재 local follow-up은 이를 full/admin-security focus에서만 실행하게 제한하고 회귀 계약을 추가했다. 독립 검수에서 확인된 edit-form 한국어 문구 누락도 same-source XLIFF 및 browser assertion으로 함께 보완했다. 최신 local validation: Step 8 exact command 551 tests PASS (7 skipped), Step 9 exact command 147 PASS, 영향 계약 묶음 199 PASS; workflow YAML, browser Python AST, Korean XLIFF parsing과 `git diff --check`도 PASS다. 새 edit-form 문구의 PrestaShop runtime은 다음 Actions에서 확인해야 한다. 이 변경 묶음 push 이후 자동 전체 격리 QA가 아직 필요하며 그 전까지 전체 QA는 대기 상태다.
- #40300616469에서 통과한 catalog same-ID edit/readback/reimport와 synthetic tracking browser/DB outcome을 보존한다. #40298163222의 일본어 tracking/customer 화면 확인도 그대로 유지한다. 합성 결과를 live marketplace 수집, 실출고, 운영 판매, 전체 UI 시각 확인으로 넓히지 않는다.
- 다음 코드 구현 후보는 승인 요구사항의 PWA-002 consent-based Web Push다. 기존 service worker는 install/activate/fetch만 제공한다. 이를 business-profile manifest 기능과 분리하고 isolated fake sender에서 구독/해지·소유권·payload/path 검증을 구현할 계획이다. 생산 HTTPS, 승인된 consent/privacy 보존 문안, VAPID key custody/발송자, iOS·Android 실기기는 별도 자료·환경 대기다.

## 최신 코드 및 격리 QA 상태 (2026-10-26 09:49 UTC)

`work`와 `origin/work`는 `0b68e96f1a38a36feb3732b2d3a26c06afd40c1a`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다.

- `0da85d3`는 manager 상품 ID baseline을 unsupported URL 검사 전에 읽도록 순서를 바로잡았다. 해당 검사 함수는 review 화면으로 이동하므로 이전 순서에서는 manager ID 집합을 review 페이지에서 읽었다. 합성 상품 조회 실패나 중복 생성의 증거가 아니었다.
- `985e1cd`는 운송장 저장 직후 문서 대기에서 `<body>.text`를 읽는 중 생기는 `StaleElementReferenceException`만 일시적인 대기 결과로 처리한다. 정확한 주문 참조와 허용된 동일 관리자 주문 경로가 모두 맞아야 통과하며 35초 제한, 운송장 행 재조회, cache-disabled 새 GET, 고객의 같은 주문 조회와 네이티브 DB 검증은 유지한다.
- `0b68e96`는 주문 참조가 비어 있거나 문자열이 아닌 경우 대기 predicate가 통과하지 않도록 한다. 주문 ID나 주문 참조를 출력하지 않는다.
- 최종 코드 SHA의 전체 격리 QA [#40300616469](https://github.com/goldeget/japan-premium-commerce/actions/runs/40300616469)는 **FAILURE**다. Step 88 실제 aggregate의 유일한 실패는 `account=failure`; 안전 주석은 모바일 `customer_address_edit`의 `TimeoutException`, `control_name=none`, `control_type=none`이다. 이 단계는 이번 catalog/shipping 수정 범위 밖이며 원인은 확정하지 않았다. 따라서 전체 QA PASS나 출시 가능으로 기록하지 않는다.
- 같은 aggregate에서 `CATALOG_IMPORT_BROWSER_QA_OUTCOME=success`, `SHIPPING_FREE_ADMIN_BROWSER_QA_OUTCOME=success`, `SHIPPING_FREE_TRACKING_PERSISTENCE_OUTCOME=success`였다. Step 73이 실행되어 관리자 브라우저 outcome도 실제 success였다. 합성 catalog 승인·manager readback, 운송장 저장·새 GET·같은 고객 주문 조회 결과를 이 범위에서 유지한다. 운송장 실제 출고·carrier scan·외부 tracking URL은 검증하지 않았다.
- 독립 QA는 이전 전체 성공 SHA `985e1cd` / [#40298163222](https://github.com/goldeget/japan-premium-commerce/actions/runs/40298163222) artifact [12639887664](https://github.com/goldeget/japan-premium-commerce/actions/runs/40298163222/artifacts/12639887664)를 열어 관리자·고객 운송장 행과 일본어 주문 라벨을 확인했다. 이 캡처는 합성 주문이며 stale retry 분기가 실제로 실행됐다는 증거는 아니다. 최종 SHA run의 browser artifact [12641465628](https://github.com/goldeget/japan-premium-commerce/actions/runs/40300616469/artifacts/12641465628)와 diagnostics [12639904863](https://github.com/goldeget/japan-premium-commerce/actions/runs/40300616469/artifacts/12639904863)는 보존돼 있으나 이 환경에서 새 이미지를 직접 열어 확인했다고 주장하지 않는다.
- 검증: final-code `fresh-install.yml` Step 8은 CI에서 통과했다. 최종 코드의 정확한 Step 8 로컬 명령은 546 tests PASS (7 skipped), free-shipping contract file은 47/47 PASS; Python compile 및 `git diff --check`도 통과했다. 해당 로컬 결과는 Actions runtime/전체 aggregate를 대체하지 않는다.
- 별도 release blockers는 유지한다: 실제 판매자·상품/SKU 및 이미지 사용권·SKU 세금 분류, 운송사/출고·반품 운영, 결제·환불 및 승인 문안, production domain/TLS/SMTP/secrets, 운영 backup 정책·저장소·담당자, iOS/Android 실기기 접근이 자료·환경 대기다. 관리자 전체 한국어 inventory도 미완료다. 실기기·실판매·운영환경 PASS로 추정하지 않는다.

## 이전 최신 상태 (2026-10-26 07:42 UTC)

현재 `work`의 코드 checkpoint는 `791f2d31456abd4cfa4dd98447ba1838a41073b0`; 원격 `origin/work`는 push 전 `f4c75b89f4c89edbe1fb97ba097cbd061dc30259`다. `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 보존했다. `20f3708`은 catalog native readback의 실패 predicate를 enum과 boolean만으로 기록하고, `791f2d3`은 일본어 주문 상세 JA label을 child theme에서 번역한다.

마지막 완료 전체 QA는 SHA 229dd22 / [#40281533046](https://github.com/goldeget/japan-premium-commerce/actions/runs/40281533046) SUCCESS다. 실제 Step 73 tracking outcome, Step 88 aggregate, official postcode import/verification 및 cleanup이 성공했다. 독립 QA artifact [12632622676](https://github.com/goldeget/japan-premium-commerce/actions/runs/40281533046/artifacts/12632622676)의 same-order evidence는 기존 항목 아래에서 유지한다.

fe09a56 전체 실행 [#40283927023](https://github.com/goldeget/japan-premium-commerce/actions/runs/40283927023)은 preflight `Verify fresh-install workflow contracts`에서 종료됐다. 새 `invalid_url_notice_visible` schema field가 `test_isolated_ci_integration_workflow_contract.py`의 합성 진단 fixture에 빠져 validator가 `catalog import failure diagnostic is invalid`로 거부한 것이 확인 원인이다. 앱 설치/브라우저 검사는 실행되지 않았고, skipped screenshot/aggregate 단계는 별도 제품 결함으로 해석하지 않는다. 별도 parser run [#40283926974](https://github.com/goldeget/japan-premium-commerce/actions/runs/40283926974)는 SUCCESS다.

f4c75b8 당시 `fresh-install.yml` Step 8의 535개 계약 테스트가 통과했다. 현재 두 code commit에 대한 동일 Step 8 명령은 538 tests PASS (7 skipped)이며, 관련 catalog/locale/aggregate contracts는 85/85 PASS, Python AST/XLIFF parse와 `git diff --check`도 통과했다. 자동 전체 격리 Actions [#40284146117](https://github.com/goldeget/japan-premium-commerce/actions/runs/40284146117)은 f4c75b8 SHA에서 완료됐으나 **FAILURE**다. Step 88 실제 aggregate의 유일한 실패는 `catalog_import_browser_qa=failure`; run 전용 정리/백업/postcode 검증은 성공했다. Step 46의 green conclusion은 `continue-on-error` 표시라 성공 근거로 쓰지 않는다. 기존 안전 진단은 승인 후 `native_editor_readback`에서 `AssertionError`, HTTP 200, 같은 manager 경로·상품 ID·편집기 표시, 권한/토큰 오류 없음을 기록했으나 정확한 필드는 계측되지 않았다. 독립 검수가 artifact [12633129812](https://github.com/goldeget/japan-premium-commerce/actions/runs/40284146117/artifacts/12633129812)의 `catalog-import-unsupported-url.png`를 열어 고정 한국어 URL 안내 화면을 확인했다. 실패 crop은 기존 비활성 안내만 보여 field 판정에는 도움이 되지 않았다. 새 predicate 진단은 로컬 검증됐지만 Actions runtime은 다음 run에서 확인해야 한다. 전체 QA PASS로 기록하지 않는다.

앞선 CAT-004 완료 run은 e085be59a0f9f061769fe7ab3cb79e025042b960의 [#40277922728](https://github.com/goldeget/japan-premium-commerce/actions/runs/40277922728) SUCCESS다. Independent QA가 artifact [12631716741](https://github.com/goldeget/japan-premium-commerce/actions/runs/40277922728/artifacts/12631716741)을 열어 catalog-import-manager-edited.png에서 EN/KO 이름, ¥6,780, native ID 29와 비활성 안내를 확인했다. JSON/DB는 같은 ID의 fresh GET/reimport, base stock 0, 조합 재고 5/5, 이미지/옵션 identity 보존과 inactive/hidden/non-orderable gate를 확인했다. 캡처에서 이미지·옵션·한국어 상세설명은 fold 아래이므로 시각 검수 PASS에 포함하지 않는다. 이 synthetic acceptance는 CAT-004를 닫지만 실제 source 수집·권리·실상품 fidelity 및 GAP-002 고객 공개 검증과는 별개다.

이번 주문 추적 변경은 위 격리 주문의 관리자 저장→같은 관리자 주문 새 조회→같은 고객 주문 상세 조회를 통과했다. 독립 시각 검수에서 JA 고객 주문 상세의 `Order Reference`, `Carrier`, `Payment method`, `Shipment tracking details` 영어 라벨을 확인했다(LOCALE-002). child theme의 JA Customeraccount/Catalog/Checkout XLIFF를 추가하고 같은 주문의 JA locale/labels 및 tracking-row screenshot을 확인하도록 브라우저 검사를 보강했다. 해당 화면의 runtime 결과는 새 Actions artifact를 기다린다. Catalog importer의 동일상품 readback은 새 세부 진단을 추가했으나 실제 predicate 및 이후 manager edit/reimport acceptance는 여전히 검증 대기다.

개발/격리 QA 결과는 출시 준비를 의미하지 않는다. 실제 seller/authority, SKU와 이미지 사용권, SKU 세금, 배송지역/운송·출고/반품 운영, 승인 결제·환불 정책, 법률 문안, production host/domain/TLS/SMTP/secrets, 운영 backup destination/key/retention/RPO/RTO/owners는 자료·환경 대기다. 코드 측에서는 관리자 전체 한국어 inventory, PWA Web Push, 공통 관리자 감사 ledger 등 matrix의 부분/미구현 항목이 남아 있다. Web Push와 shared admin ledger는 사용자 승인 요구사항에 남아 있는 미구현 기능이다. 실기기 PWA는 연결 가능한 기기가 없어 미검증이다. 기존 회사 reference, ORDENOWA 브랜드, 무료배송/가격 승인정책은 보존한다.

## 직전 완료 격리 QA 및 catalog import 기준점 (2026-10-26 05:20 UTC)

검증 대상 `work` commit `e1cd6d0c9d58ee2db64462387fef305c2ab0e757`는 원격과 일치한다. `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다. 전체 격리 Actions [#40272141646](https://github.com/goldeget/japan-premium-commerce/actions/runs/40272141646)은 성공했고 Step 87 aggregate는 `PASS: isolated browser QA and official postcode verification completed.`로 끝났다.

이전 [#40269983026](https://github.com/goldeget/japan-premium-commerce/actions/runs/40269983026)의 유일한 실패는 catalog browser의 `approved_product_link` 검사였다. 브라우저는 승인 화면에 남아 있었고 native manager로 이동하기 전에 URL 검사에서 중단됐다. PrestaShop 9.2 legacy `getAdminLink()`는 관리자 디렉터리의 `/` 또는 `/index.php` 진입 경로를 만들 수 있는데 검사는 관리자 경로의 정확한 bare 값만 허용했다. 검증기를 같은 origin, 정확한 manager controller, 단일 양수 상품 ID를 유지하면서 `/admin-kuranea`, `/admin-kuranea/`, `/admin-kuranea/index.php`만 허용하도록 수정했다. 임의 하위 경로·외부 origin·중복/무효 ID·`;params`는 계속 거부한다. 실패 시 링크 자체나 query/token은 기록하지 않고 경로 유형 및 조건별 boolean만 남긴다.

새 Step 46 로그는 합성 Amazon/Rakuten batch, 옵션 가드 반려, 단일 옵션 검수 승인, native product manager 화면의 같은 상품 값 재조회 및 동일 상품 재수집 후 readback PASS를 기록했다. 이 catalog flow에서는 manager 편집 폼의 저장 버튼을 누르지 않았다. 같은 ID의 native product DB 확인은 active=false, visibility=none, available_for_order=false, 이미지 1개, 조합 2개, 동일 reference 상품 1개다. 고객 노출·판매 활성화는 수행하지 않았다. 독립 QA가 artifact 12628194683의 draft/reimport PNG를 실제 열어 합성 JA/EN/KO 이름, JPY 표시가격, 비활성 안내, 재수집 성공 화면을 시각 확인했다. 이 Codex 환경은 artifact 다운로드 403으로 이미지를 열지 못했으나 별도 검수자의 확인은 완료됐다. 재고 숫자는 DOM/DB 자동 확인과 구분해 화면상 PASS로 주장하지 않는다. 새 manager-edit 캡처는 #40275686536 artifact에서 확인 대기다.

이 결과는 격리 synthetic fixture로 현재 승인·비활성 draft·재수집 경로를 확인한 것이다. Amazon Japan/Rakuten 실제 상품 페이지 호환, 허용된 실상품 URL/피드 수집, 원격 이미지 취득 및 사용권, 다중 옵션 조합 지원은 완료로 확대하지 않는다. 운영 판매자·상품·세금·배송·결제·법률 문안 및 production 환경 자료는 기존 미정 항목으로 남는다.

## 이전 QA 및 출시 체크리스트 (2026-10-25 21:20 UTC; 2026-10-26 최신 run으로 superseded)

검증 대상 코드 commit SHA는 `95af3a9104b6e3f7bfc861155bdc73db9a91ab98`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd` 그대로다. 이 검증 뒤 `work`에는 문서 전용 업데이트가 올라갔고 앱/테스트 코드는 바뀌지 않았다. 전체 격리 Actions [#40233614104](https://github.com/goldeget/japan-premium-commerce/actions/runs/40233614104)은 workflow 성공이며 Step 80 실제 aggregate는 `PASS: isolated browser QA and official postcode verification completed.`다. Aggregate의 storefront/PWA browser outcomes도 각각 success이며 Step 42, 49, 73, 75, 83이 성공했다. 새 artifact [ID 12613919270](https://github.com/goldeget/japan-premium-commerce/actions/runs/40233614104/artifacts/12613919270)의 수정 화면 시각 재검수는 아직 대기 중이다. 검증 대상 코드의 로컬 영향 테스트 121개도 통과했다.

| 영역 | 상태 | 근거 / 다음 담당 |
| --- | --- | --- |
| 모바일 PWA 계정 경로 검사 | 완료 (격리 자동 QA) | #402294 timeout은 모바일에서 숨겨진 sidebar의 중복 GDPR 링크를 첫 요소로 고른 테스트 결함이었다. 표시되는 일치 요소를 검사하도록 수정했고 #402315 Step 49의 JA/EN/KO desktop/mobile 6개가 각각 PASS했다. |
| 일본어 checkout details 및 계정 sidebar | 완료 (격리 자동/화면 QA) | Work-mode GPT가 #402315에서 `詳細を表示`, 모바일 checkout 버튼, 일본어 `マイアカウント`를 확인했다. Step 60/49도 통과했다. |
| 한국어 계정 sidebar 제목 | 자동 브라우저 검증 완료; 시각 재검수 대기 | #402315 캡처의 English `My Account`를 `내 계정`/`내 계정 메뉴` XLIFF로 수정했다. #402336 Step 49와 Step 80 aggregate에서 KO PWA browser outcome이 success다. 새 artifact의 시각 확인은 대기 중이다. |
| 모바일 긴 상품 breadcrumb | 자동 브라우저 검증 완료; 시각 재검수 대기 | Hummingbird 기본 mobile rule은 한 줄 수평 스크롤과 숨긴 scrollbar다. 자식 테마에서 상품 페이지의 현재 crumb만 줄바꿈하게 하고 긴 합성 제목의 DOM overflow/title equality assertion 및 `mobile-product-detail-breadcrumb.png` 캡처를 추가했다. #402336 Step 42 및 aggregate에서 storefront outcome success다. 새 캡처의 시각 확인은 대기 중이다. |
| checkout 정책 제목/보조문구 | 자료·정책 문안 대기 | checkout template은 조건 문구를 동적 `{$condition nofilter}` 데이터로 렌더한다. 승인된 일본어 판매 정책이 없으므로 값을 임의 번역하지 않는다. synthetic coupon 이름은 테스트 데이터다. |
| `Clothes`/`Art` 카테고리 명 | 실제 카탈로그 분류 자료 대기 | 이 값은 테마 UI string이 아니라 PrestaShop default/synthetic category 데이터다. 승인된 일본어/한국어 분류명이 없어 mapping을 만들지 않는다. |
| 최신 Work-mode 시각 QA | 새 artifact 검수 대기 | #402336 artifact `12613919270`의 한국어 계정 제목과 긴 breadcrumb 캡처를 확인한다. Codex의 system Chromium은 local capture 시 crashpad 초기화에 실패했으므로 이 환경에서 새 PNG를 열지 않았다. |
| 계정/상품/배송/주문/RMA/PWA/복원/우편번호 | 완료 (현재 격리 코드 SHA 범위) | #402336 Step 80 aggregate 성공. CI browser screenshots는 합성 fixture에 한정된다. |
| 실기기 PWA/브라우저 | 미검증—기기 연결 필요 | 연결된 iOS/Android 기기나 승인된 remote device farm이 없다. Chromium CI emulation을 실기기 PASS로 취급하지 않는다. |
| 운영 출시 | 자료·환경 대기 | 실제 판매자·SKU/이미지 권리·세무·배송 계약·결제/환불·법률 문안·운영 host/domain/mail/backup과 책임자 자료는 기존 `미정` 상태다. 기존 회사 참고정보, 공식 브랜드, JPY·세금 포함 가격·무료배송 정책은 유지한다. |

이전 전체 성공 실행은 그대로 보존한다. 자동 browser/aggregate PASS와 새 artifact에 대한 시각 검수는 별도 상태로 기록한다.

## 이전 화면 검수 전 기준점 (2026-10-25 20:05 UTC; 후속 run #40231567083으로 superseded)

현재 remote `work`는 `b94d1f0ba3418b5724f07735e7186c2adbcb6555`, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`다. 마지막 성공 코드 SHA `bb26f06168e0a10a50607ce4e5171666656611b1`의 집중 QA [#40225474420](https://github.com/goldeget/japan-premium-commerce/actions/runs/40225474420)과 전체 격리 QA [#40226037762](https://github.com/goldeget/japan-premium-commerce/actions/runs/40226037762)은 성공했다. Work-mode GPT가 전체 run artifact를 열어 화면을 검수했고, 이 근거에서 확인된 모바일 checkout 가림과 locale 누락을 수정 중이다. 현재 작업 트리에 변경이 있으나 새 코드 SHA의 Actions 실행은 아직 없다. 영향받은 정적/계약 검사 172개가 통과했고, 마지막 한국어 로그인 stage allowlist 변경 후 해당 9개도 다시 통과했다.

| 영역 | 상태 | 근거 / 다음 담당 |
| --- | --- | --- |
| 상품 제목 `404` 오탐 | 완료 | #402260 Step 42 통과. #40214404446의 실제 HTTP 응답 상태는 미기록이라 계속 미확인으로 둔다. |
| RMA 세션 토큰 이동과 상태 | 완료 (격리 QA) | tokenless 경로에서 exact native `security/compromised` 화면 marker 확인; session token이 있는 앱 생성 메뉴 링크는 정상 목록으로 복귀. 같은 run-scoped RMA의 1→2 저장/재조회, 2→1 복원/재조회 성공. |
| Chromium 폰트 캐시 | 완료 | #402254/#402260 Steps 30–32 캐시 복원과 브라우저 준비 성공. |
| 계정/상품/배송/주문/PWA/복원 | 완료 (격리 자동 QA 범위) | #402260 관련 브라우저 steps와 Step 80 aggregate 성공. 세부 범위/한계는 [테스트 결과](TEST_RESULTS.md)에 기록했다. |
| Work-mode AI 시각 QA | 기존 artifact 검수 완료; 수정 화면 재검증 대기 | #402260 artifact에서 mobile checkout nav가 390×701에서 뒤로 버튼을 가리는 것, JA checkout의 영어 혼합, KO login의 Dutch password label, JA GDPR link 영문 잔류를 확인했다. 현재 CSS/XLIFF/child-theme/E2E 수정은 정적 검사만 통과했고 browser 확인은 새 run 대기다. |
| 레이아웃·언어 수정 | 코드 수정 완료, 격리 브라우저 검증 대기 | checkout에서는 fixed nav를 숨기고 현재 배송 step 버튼, JA CTA/comment, check-payment 옵션·확인 화면을 검증하도록 했다. JA/KO 비밀번호·개인정보 label도 locale화하고 브라우저 assertion을 추가했다. 새 source SHA의 Actions 결과 전까지 PASS로 처리하지 않는다. |
| 남은 시각 후보 | 부분 관찰 / 결함 미확정 | `Clothes`/`Art`는 synthetic/default category data로 보여 실제 catalog 없이 임의 번역하지 않는다. 상품 breadcrumb의 잘림은 screenshot만으로 DOM overflow를 확인하지 못했다. |
| 신규 코드 화면 검증 | 실행 대기 | 로컬 shop/staging 주소가 없고 Codex artifact direct download는 403이다. source 변경 push가 만든 격리 QA artifact로 Work-mode GPT가 변경 화면을 다시 검수한다. |
| Codex 모바일 emulation | target 부재로 화면 QA 미실행 | Chromium 154/Playwright 1.62 및 mobile viewport profiles는 사용 가능하지만 shop URL이 없어 현재 source의 emulation capture는 만들지 않았다. |
| 실기기 PWA/브라우저 | 미검증—기기 연결 필요 | 연결된 iOS/Android나 승인된 remote device farm이 현재 Codex 환경에 노출되지 않았다. 사용자의 수동 검수를 요구하지 않는다. |
| 운영 출시 | 자료·환경 대기 | 실제 판매자·상품/권리·세무·배송·결제·환불·법률 문안·운영 호스트/메일/백업·담당자 값은 기존 자료의 `미정` 상태를 유지한다. 회사 참고정보와 ORDENOWA 브랜드, JPY/세금 포함 가격/무료배송 정책은 재요청하거나 바꾸지 않는다. |

새 수정 코드의 전체 Actions run이 생성되면 Work-mode GPT가 그 run artifact에서 변경된 화면을 다시 검사하도록 [handoff](AI_BROWSER_QA_HANDOFF.md)를 갱신한다. live browser가 필요한 미검증 항목은 [handoff 환경 조건](AI_BROWSER_QA_HANDOFF.md#live-브라우저-검증에-필요한-환경)에 필요한 승인 격리 환경만 명시했으며 hostname이나 계정을 만들어내지 않았다. 정식 운영 출시는 운영 자료·환경이 준비되기 전까지 완료로 표시하지 않는다.

## 과거 고정 범위 결과 (2026-10-25 11:39 UTC; 위 현재 상태로 대체됨)

최종 회귀 대상 코드 `work` SHA는 **74e64b966d5943a3d06cadd04fe6fc7b17669bfe**다. 격리 Actions [#40188721058](https://github.com/goldeget/japan-premium-commerce/actions/runs/40188721058)은 **FAIL**로 종료했고 Step69의 유일한 실제 실패는 `admin_security_browser_qa=failure`; Step72의 run 전용 리소스 정리는 성공했다. 이전 SHA `e356a8a01f9215f2a3dd32ab623a806bda5e398a` 실행 [#40187411910](https://github.com/goldeget/japan-premium-commerce/actions/runs/40187411910)도 같은 실패였다. `main` **ee02a3657448d563508687614a246e05ac61eecd**는 변경하지 않았다. 기준 성공 실행 [#40134196682](https://github.com/goldeget/japan-premium-commerce/actions/runs/40134196682)는 기존 기준점으로 보존한다.

| 항목 | 완료 조건 | 현재 상태 | 남은 작업 | 필요한 외부 자료 |
| --- | --- | --- | --- | --- |
| 보기 전용 직원 대시보드 경로 | 로그인 뒤 허용된 같은 origin의 Dashboard 화면과 한국어 날짜 UI를 브라우저에서 확인 | **코드 수정 필요** — Step39 실제 outcome이 두 연속 실행에서 실패. 로그는 `login_form_visible=false`, `dashboard_link_count=1`, `current_controller=other`를 기록한다. 커밋 `74e64b9`에서 `/admin-kuranea/index.php/sell/dashboard`를 정확히 허용하고 외부 origin·추가 하위 경로 거부를 유지했지만, 최종 실행에서도 실패했다. 실제 주소 경로는 안전 로그에 저장하지 않아 원인을 확정하지 못했다. | 현재 실패의 안전한 실제 경로 형태를 확보하고 분류기를 그 근거에 맞게 수정한 뒤 브라우저 검증. 이번 고정 범위의 추가 전체 QA 한도는 소진됨 | 없음 |
| 브랜드 게시 후 재로그인 | 게시/복원 후 PC·모바일 로고 및 관리자 로그인 표시 확인 | **완료** — #401887 Step32 실제 brand outcome 및 Step33 이메일 로고 검사 통과; Step69에서 brand outcome success 확인 | 없음 | 공식 승인 브랜드 원본은 저장소에 보존됨 |
| 회원·상품·PWA·배송·가격·주문 | 핵심 PC·모바일 브라우저 흐름, 저장된 주문/금액, 개인정보 캐시와 무료배송 확인 | **완료 (격리 QA)** — #401887 aggregate에서 대시보드 외 실패 없음. Step41, Steps52–57 통과 | 새 변경이 없으면 재검사하지 않음 | 실기기 PWA 설치만 iOS/Android 기기·운영 HTTPS 필요 |
| 관리자 취소·반품 레코드 | 기본 관리자 화면에서 미결제 주문 취소 및 native 반품/credit slip 저장 상태 확인 | **완료 (격리 합성 주문)** — #401887 Steps51, 61 및 aggregate 통과. 반품/credit slip은 합성 paid-like CI fixture이며 현금 이동 없음 | 반품 승인/처리 UI와 실제 결제 환불은 미검증 | 판매자 취소·반품·환불 정책, 결제 제공자 계약/접근 |
| 전체 한국어 관리자 범위 | 승인 요구 문서의 모든 코어/커스텀 화면·오류·보고서·메일 한국어 검증 | **검증 필요** — 일부 브랜드·상품·배송·주문·권한 화면만 확인. 전체 화면 inventory와 메시지 coverage는 미완료 | 기존 `docs/ADMIN_KOREAN_REQUIREMENTS.md` 범위의 미검증 화면 QA | 실제 법률·고객 안내 문안은 판매자 승인 자료 |
| CI 백업·복원 | 격리 DB·파일·catalog queue 복원, 재시작 및 정리 | **완료 (격리 drill)** — #401887 Step62와 Step72 통과; 운영 복구로 확대 해석하지 않음 | 운영 복원은 실제 운영 target에서 별도로 검증해야 함 | 운영 백업 저장소·암호화·접근·보존기간·승인 RPO/RTO·복원 담당자/대상 |
| 정식 출시 환경 | 실제 상품과 판매자 정보, 세금·배송·결제·법률 문구와 운영 접속 검증 | **자료·환경 대기** — 합성 상품·세율·Mailpit·미결제 CI 주문만 사용 | 입력 승인 후 환경별 deployment/rollback 및 외부 전송 인수 검사 | 판매자/법률 정보와 고객센터, 실제 SKU·가격·재고·이미지 권리, 세금·배송 계약/지역, 결제·환불 정책, 도메인/DNS/TLS/서버·비밀 및 담당자, SMTP, 운영 백업·복원, iOS/Android 기기 |

아래의 이전 감사 표와 세부 화면 목록은 당시의 과거 스냅샷이다. 위 표가 현재 상태이며 과거 검증 근거는 보존한다.

## 이전 종합 감사 스냅샷 (2026-10-25 08:21 UTC)

현재 격리 전체 QA 대상 코드 SHA는 **b368a6b0a4c39985a13dcb0720683b0a0b5929f4**이며 `work`에 push했다. 최종 변경 목록은 backup/restore command fix `0392573e0e37008c524872d9f0d73679413aec71`, PWA bootstrap race fix `77e337e96b0bcd00e72dc0266b291e38dffdbda9`, AdminOrders Korean locale fix `b368a6b0a4c39985a13dcb0720683b0a0b5929f4`의 세 독립 커밋이다. `main` **ee02a3657448d563508687614a246e05ac61eecd**는 수정하지 않았다. 성공 기준점 `b99b61559978dd8b4c25819623669e0d92deb768`의 전체 QA [#40134196682](https://github.com/goldeget/japan-premium-commerce/actions/runs/40134196682)는 보존한다. #40173333689 (`c392db7`)은 `admin_security_browser_qa=failure backup_restore_drill=failure`로, #40174672771 (`b8eccca`)은 `admin_security_browser_qa=failure pwa_browser_qa=failure backup_restore_drill=failure`로 끝났으며 두 실행 모두 run 전용 정리는 통과했다. 현재 전체 격리 QA [#40176160072](https://github.com/goldeget/japan-premium-commerce/actions/runs/40176160072)은 `b368a6b`에서 실행 중이다. 최종 aggregate가 나오기 전까지 전체 QA를 통과로 기록하지 않는다.

### 이번 수정 및 검증 범위

- `SELL → AdminParentOrders → AdminOrders` 뷰 권한 경로는 #401712에서 수정되어 해당 Orders 목록 링크 탐색이 가능해졌다. #401712 Step 39에서 목록 URL은 HTTP 200, 로그인 폼·권한 거부는 없었다.
- #401746의 실제 Orders 진단은 HTTP 200, 정상 `AdminOrders` route와 grid, `document_locale=korean`인데 toolbar/grid heading은 영어였다. 한국어 overlay 도메인 정규화는 필요했으나 충분하지 않았다. module listener priority 14가 core employee/context 초기화보다 먼저 실행되어 employee `en-US`가 이후 builder와 shared translator를 다시 덮었다. #401761에서는 module override를 core `LanguageContextSubscriber::KERNEL_REQUEST_PRIORITY - 1` (priority 5)에 두고 legacy context 생성(priority 0) 전에 적용하며, 실제 Symfony dispatcher·PrestaShop context builder/legacy context/translator를 이용한 5개 회귀 시나리오를 실행한다. 화면 결과는 Step39와 aggregate로 확인 대기다.
- #401746 PWA failure는 `mobile-ja`에서 registration active/activated, expected scope, controller 없음과 `controller_timeout`이었다. Origin/path 진단은 controller가 있을 때만 계산되므로 그 실행의 `false` 기본값은 URL mismatch 증거가 아니다. Harness는 첫 `/` 문서가 완전히 로드된 직후 locale navigation을 시작해 `window.load`에서 시작하는 worker registration/activation과 경합할 수 있었다. 제어된 지연을 둔 최소 Chromium 재현에서 기존 순서는 같은 timeout을 내고, 초기 controller 대기 후에는 controller 및 expected URL 검사가 통과했다. 저장된 #401746 로그는 당시 요청별 interleaving을 담지 않아 이 재현은 확인된 메커니즘이지 과거 요청 순서의 직접 trace는 아니다. #401761은 initial control barrier와 기존 locale-page assertion을 함께 검증한다.
- Backup/restore의 첫 MariaDB 생성 명령은 `docker compose -p … create --no-deps …`였다. 공식 Compose v2.38.2의 `create` 하위명령에는 `--no-deps`가 없으며 이 옵션은 다른 하위명령에 존재한다. #401733/#401746의 원문 stderr는 보존되지 않았지만 unsupported argument는 소스에서 확인했다. `--no-deps`만 제거하고 shell contract를 추가해 #401761 Step62에서 실제 격리 restore를 확인한다.
- #401746 Step39, Step41, Step62의 실제 outcome은 모두 failure이며 Step69 집계는 `admin_security_browser_qa=failure pwa_browser_qa=failure backup_restore_drill=failure`였다. Step72 cleanup은 success였다. `#401761` 전 로컬 집중 검사 결과: admin-locale 37, PWA 106, backup/fresh-install contracts 68, security contract 36 Python tests pass; PHP lifecycle regression 5 scenarios, 두 PHP 파일 lint, shell syntax와 수정 파일 `git diff --check` pass. (과거 #401746의 화면 검사는 성공으로 기록하지 않는다.)
- #401746 artifact 메타데이터는 browser `ordenowa-storefront-browser-40174672771-1` (ID `12592037915`, 16,532,674 bytes)와 diagnostics `fresh-install-diagnostics-40174672771-1` (ID `12591359845`, 5,086 bytes)다. #401761 결과와 PC/mobile 캡처 경로는 해당 run 종료 뒤 기록한다. Workflow는 실패 시에도 `if: always()` 업로드를 실행한다.

### 기존 요구사항과 출시 상태

| 항목 | 완료 조건 | 현재 상태 | 남은 작업 | 필요한 외부 자료 |
| --- | --- | --- | --- | --- |
| 관리자 상품 등록·수정 | 상품명·설명·이미지·옵션·재고를 네이티브 PrestaShop에 저장하고 고객 화면에서 확인 | **완료 (합성 기능 QA)** — #401712 Steps 17–19, 35; 화면 한국어 전체 인수는 별도 미완료 | full Korean UI/오류·알림 audit | 실제 SKU, 가격, 재고, 설명, 이미지 사용권 및 판매 승인 |
| 관리자 계정 복구 | 한국어 관리자 로그인에서 비밀번호 복구를 요청하고 Mailpit 재설정 메일/링크로 복구 | **검증 필요** — customer account reset E2E는 있음; 그것만으로 Back Office employee recovery를 증명하지 않음 | core admin recovery form, Korean errors, token, Mailpit delivery를 격리 브라우저로 확인 | 운영 메일 전달성은 SMTP/발신도메인 승인 후 |
| ORDENOWA 공식 이미지·게시 | 승인 원본 3종과 파생본 무결성; PC·모바일 헤더, 관리자 로그인, favicon, Apple Touch/PWA 아이콘, OG/SEO, 일반·재설정 이메일 로고의 업로드·미리보기·게시·복원 | **검증 필요** — #401746 Steps 11, 32, 33 개별 conclusion success였지만 전체 aggregate는 다른 세 실패로 fail. #401761 결과 대기 | 현재 run의 outcome, PC/mobile/email 캡처와 게시 후 readback 확인 | 출시 상품·회사 정보를 게시하려면 seller approval |
| 한국어 관리자 운영 설정 | 회사 참고정보와 실제 판매사업자 정보 분리; 고객센터·은행 계좌 권한·배송/환불·약관/개인정보/특상법·SEO/PWA 값을 한국어 관리자에서 저장·재조회하고 고객 화면에 반영; brand draft→preview→publish→history→restore 흐름 확인 | **검증 필요** — #401746 Step32는 브랜드 upload/preview/publish/history/restore, Step25는 business profile 설치/접근을 확인했다. Step39에서는 read-only settings display까지 갔지만 Orders assertion 뒤 write-denial test는 실행되지 않았으며 bank permission browser coverage는 미검증. PHP module checks cover legal/payment linkage; SEO escaping은 source contract만 확인 | bank-account permission, customer support/refund/legal forms와 locale별 readback, SEO/PWA 관리자 제어의 browser inventory; #401761 outcome 대기 | 회사 참고정보와 별도인 실제 판매자 법적 정보·고객센터·은행 계좌 권한, 배송/환불/약관 문구와 최종 domain/SEO 공개값 승인 필요 |
| 회원 계정·주문 내역 | 중복 가입/잘못된 비밀번호 거부, 이메일 로그인·로그아웃, 재설정 token 만료·재사용 거부, my page, 주소 생성/수정, 주문 내역 확인 | **검증 필요** — 별도 사용자 ID 찾기가 아니라 PrestaShop 이메일 로그인이다. #401746 Step34 회원 흐름과 Step40 reset-token replay/expiry는 각각 성공했지만 전체 aggregate는 다른 영역에서 fail; #401761 결과 대기 | aggregate 기준 가입·로그인·재설정·계정/주소/주문 동선 확인. 별도 사용자 ID 찾기 기능은 구현 요구로 두지 않음 | 운영 메일 발신은 승인된 SMTP/도메인 필요; 격리 reset은 Mailpit |
| 주문 조회·상태·취소·반품 | 별도 관리자에서 주문 상태 변경·이력, 취소·반품·credit slip readback | **격리 기능 QA 완료 확인 대기** — #401746 Step61 개별 success였으며 취소·반품 fixture는 synthetic paid-like 상태; #401761 Step61 확인 예정 | 전체 aggregate와 Step61 결과 확인. 실제 결제 환불/송금은 CI에서 실행하지 않음 | 실제 fulfillment·취소·반품·환불 정책 및 결제 계약 |
| Orders 화면 한국어 | 영어 설정의 읽기 전용 직원으로 실제 AdminOrders 목록·toolbar·grid 제목을 한국어로 렌더링 | **코드 수정 완료, 격리 확인 대기** — #401746은 HTTP 200/정상 grid인데 영어 headings. listener order를 고쳤고 actual context lifecycle test가 5/5 통과; #401761 Step39 결과 대기 | aggregate·screenshot 확인 | 자료 불필요 |
| 관리자 전체 한국어 100% | 기존 PrestaShop 코어 전 화면과 승인된 관리자 흐름의 메뉴·필드·도움말·오류·메일·알림을 실제 화면에서 확인 | **검증 필요** — 16개 주요 동선과 선택된 overlay는 있지만 전체 core inventory, Korean pack source/version pinning, 모든 employee의 기본 언어 증거는 없음 | 로그인/복구, 모든 메뉴, 상품/분류/재고, 주문/고객/배송, 결제/세금/통화, 직원/권한, 모듈/테마, 회사/시스템, 백업/유지보수 문구 inventory와 browser evidence; 발견된 결함만 수정 | synthetic screen audit은 가능; 실제 업무 문구는 seller approval 필요 |
| 회원·로그아웃·PWA 기본 동선 | 가입·로그인·재설정·로그아웃 후 인증 종료, 계정/주문 접근 보호와 private cache 부재를 PC·모바일 Chromium에서 확인 | **검증 필요** — #401746 Step34 성공, PWA Step41 실패 on mobile-JA; #401761에는 초기 worker control barrier를 넣었고 기존 logout/cache assertions 유지. 최종 결과 대기 | aggregate·Step41 확인; iOS/Android 설치·실기기 동작은 별도 | iOS/Android 실기기 접근 |
| 고객 Web Push 알림 | 고객 동의·구독, 서버 발송, 주문/배송 알림, 한국어 관리자 제어를 검증 | **코드 수정 필요** — 현재 코드는 manifest/설치/offline/service worker만 제공; `PushManager`, 구독 endpoint, 발송기, `push` handler, 관리자 발송 UI 및 테스트가 없음 | 별도 승인된 구현 단위와 격리 전송 QA 필요; service worker/private-cache PASS를 push PASS로 보지 않음 | 운영 HTTPS 도메인 및 판매자 승인 알림 정책; 운영용 VAPID 발송 키/보유 책임 |
| 한국어 운영 설명서·보고서·관리자 알림 | 기존 관리자 기능 설명, report 및 관리자 email/notification을 한국어로 확인 | **검증 필요** — `ORDENOWA_ADMIN_GUIDE_KO.md`는 기본 사용법을 담지만 완전한 업무 매뉴얼은 아님; report/관리자 mail/notification 범위 inventory와 QA 증거 없음 | 기존 화면과 템플릿을 목록화하고 격리 Mailpit/브라우저에서 한국어 문구 확인; 사용 설명서 보완 | 판매자별 운영 절차/수신자 정보는 승인 후 |
| 관리자 감사 기록 | 권한이 필요한 주요 변경이 사용자·시각·변경내역과 함께 보존되고 한국어로 조회 | **검증 필요** — 사업자 설정의 버전 이력과 상품 검수 승인 메타데이터는 있음; 이것만으로 전체 관리자 action log 또는 거래원장은 증명하지 않음 | native PrestaShop log 및 커스텀 action/history 화면, 접근제어·보존·Korean UI를 확인 | 운영 로그 보존/접근 정책은 판매자 승인 후; synthetic 검증에는 자료 불필요 |
| SEO·입력 보안 | 관리자가 ja/en/ko SEO 값을 저장하고 canonical/hreflang/OG/JSON-LD와 CSRF·세션·upload control을 실제 화면에서 검증 | **검증 필요** — output escaping은 `work`에 있고 SEO source contract 15/15 PASS; Draft PR #3의 유효 escaping은 이미 반영·확장됨. 이는 관리자 SEO 편집 흐름이나 rendered hostile-input 전체 증거는 아님 | SEO 관리 화면과 rendered metadata를 locale별 확인하고 발견된 결함만 수정; PR #3에서 가져올 고유 변경 없음 | 실제 domain/canonical 공개값은 운영 도메인 승인 후 |
| 주문·가격·세금·무료배송 | 검색·장바구니·일본 주소·미결제 주문, 상품/주문/관리자 금액 일치, 지원 배송의 ¥0 비용 | **검증 필요** — #401746 Steps 48, 50, 52–57 개별 success였으나 전체 workflow fail; 합성 SKU·세율과 `ps_checkpayment` 무결제 주문. #401761 결과 대기. 이후 무료배송 정책이 유료 요율 검증을 대체함 | aggregate 확인. 미지원 지역/no-carrier/잘못된 요율 예외는 별도 미검증 | 실제 SKU별 적법한 세금 분류, carrier 계약과 지원 지역 |
| CI backup/restore | run 전용 DB·webroot·catalog queue 복원, 데이터 비교·재시작·cleanup | **코드 수정 완료, 격리 검증 대기** — #401746 Step62 실패. Compose v2.38.2 `create`가 `--no-deps`를 지원하지 않는 점을 확인하고 flag 제거·회귀 contract 추가 | #401761 Step62 실제 `.outcome`, Step69 aggregate, Step72 cleanup 확인. CI drill은 운영 백업을 증명하지 않음 | 운영 백업 저장소/정책은 별도 자료 |
| 운영 배포·복원 runbook | 승인된 운영값·호스트용 배포, HTTPS/mail acceptance, immutable rollback, durable backup/restore 안내 | **자료·환경 대기** — [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md)는 정확한 준비 템플릿이나 실행 가능한 운영 runbook/복원 검증은 아님 | 승인 이미지/registry로 deploy/rollback, 파일·DB·queue 일치 restore, HTTPS/mail acceptance 절차를 실제 입력에 맞춰 구체화 | 호스트/project, domain/DNS, TLS/proxy/firewall, secrets/SMTP, immutable image registry와 release owner, backup 대상/접근/암호화/보존/RPO/RTO/restore owner |
| 실제 판매 운영 | 승인된 판매자·상품·세금·배송·결제·환불 및 고객지원 정보를 운영에 구성 | **자료·환경 대기** — CI는 합성 데이터·Mailpit·무결제 주문만 사용 | 운영 승인된 실제 자료로 설정하고 고객/관리자 화면 검증 | 판매자 법적 정보·권한·주소·고객센터, SKU/가격/이미지 권리, 상품별 세무, 배송 계약/범위, 결제 계정·실거래 승인, 이용약관·개인정보·배송/환불 정책 |

`docs/ADMIN_KOREAN_REQUIREMENTS.md`는 기본 Back Office 화면 전체, 커스텀 기능, 한국어 설명서/보고서/알림과 16개 QA 흐름을 요구한다. 아래 16개 QA 흐름은 core 화면 전체 inventory를 대신하지 않는다. 현재 full run의 결과는 별도다.

| # | 관리자 업무 흐름 | 구현·검증 근거 | 상태와 남은 일 | 필요한 입력 |
| --- | --- | --- | --- | --- |
| 1 | 관리자 로그인·계정 복구 | 신규 설치는 storefront 기본 언어를 일본어로, 초기 employee 언어를 한국어로 설정·검사한다 (`kuran-post-install.php`, `fresh_install.sh`). Back Office locale lifecycle 회귀 검사는 비로그인 관리자 로그인 화면도 포함한다. | 부분 검증 — 초기 직원 1명의 한국어와 비로그인 관리자 한국어 문맥은 확인; 모든 직원의 기본 언어 및 직원 비밀번호 복구는 미검증. 공식 한국어 언어팩 source/version과 전체 catalog coverage도 고정·감사되지 않음. | 격리 재설정은 Mailpit 사용 가능; 운영 발신성은 승인된 SMTP/도메인 필요 |
| 2 | 대시보드 | PrestaShop core 및 한국어 날짜 UI가 있음. | #401746의 Orders 한국어 assertion이 먼저 실패해 대시보드 검증/캡처는 실행되지 않았다. #401761 재검사 대기. | 없음 |
| 3 | 상품 등록 | native product manager, ja/en/ko text, image/options/stock/category create. | 합성 create QA 통과 — 전체 UI 문구·도움말·오류의 Korean 인수는 미검증. | SKU/가격/재고/설명/image rights |
| 4 | 상품 편집 | 같은 native manager에서 기존 제품/이미지/옵션/재고 수정. | 합성 edit/readback QA 통과 — 전체 Korean 인수는 미검증. | 출시 상품 자료 |
| 5 | 상품 수집 | Amazon JP/Rakuten parser, review queue 및 승인 controller. | 부분 구현 — fixture parser/queue/승인 기능은 있음. URL 일괄 제출, parsing 진행률, 반려 상태/동선은 구현·검증 근거를 찾지 못함. 실제 외부 fetch는 final directive상 필수 안정화 범위에서 제외. | 실판매 SKU·허가 source fetch는 이번 안정화 범위에서 실행하지 않음 |
| 6 | 주문 조회 | native AdminOrders, 별도 관리자 상세/금액 확인; 한국어 메뉴/제목/grid overlay. | #401746 Step51 별도 관리자 주문 조회는 성공했으나 Step39는 문서 locale만 한국어이고 heading은 영어여서 실제 실패했다. #401761 재검사 대기. | 없음 |
| 7 | 입금 상태 변경 | 은행 계좌/이체 설정 초안은 있으나 실제 수동 입금 확인/입금 ledger route 없음. Core order-state와 입금 확인은 다름. | 미구현 — `ps_checkpayment` 미결제 CI 주문은 입금 확인 검증이 아님. | 판매자 결제/입금 확인 정책 및 provider/계좌 |
| 8 | 고객 상담/상담원 배정 | PrestaShop core customer functions는 있으나 custom 상담원 배정 화면/route와 Korean E2E 없음. | 미검증 / 커스텀 기능 미구현. | 운영 상담 프로세스/담당자 정책 |
| 9 | 지갑 지급·차감 | module route/model/test 없음. | 미구현·이번 단계 개발 제외 — 신규 B2B/금전 시스템으로 확장하지 않음. | 별도 범위 결정 필요 |
| 10 | 수익 정산 | module route/model/test 없음. | 미구현·이번 단계 개발 제외. | 별도 범위 결정 필요 |
| 11 | 출금 신청 검토 | withdrawal/payout route와 transfer-state test 없음. | 미구현·이번 단계 개발 제외. | 별도 범위 결정 필요 |
| 12 | 배송 처리 | native carrier setup/readback, checkout ¥0 및 order amount 대조. | 부분 완료 — 지원 carrier와 무료배송 확인은 있으나 주문별 운송장·출고·배송완료의 한국어 E2E 증거는 없다. | 실제 carrier 계약/운영 범위 |
| 13 | 직원 권한 관리 | PrestaShop profiles 및 module ACL, run-scoped view-only employee fixture. | #401746 Step39는 한국어 Orders label 검사에서 실패했다. 다른 route 접근 거부도 aggregate 결과 확인이 필요하다. 전체 native 직원/역할 편집 UI 한국어 범위는 없다. | 실제 운영 역할/권한 정책 |
| 14 | 회사정보 설정 | 한국어 business-profile form 및 brand draft→preview→publish→history→restore, email-logo output. | #401746 Step25 profile install/access, Steps32–33 brand/email flow는 개별 성공이지만 전체 aggregate는 다른 영역에서 실패했다. Value는 synthetic이며 승인된 회사정보가 아니다. #401761 재검사 대기. | 승인된 판매자·고객센터·정책 정보 |
| 15 | 시스템 설정 | PrestaShop core + 선택된 브랜드/SEO/PWA/payment/shipping 설정 화면. | 일부 custom form/browser만 검증; native settings 화면 audit 없음. 전체 범위에는 system/parameters/modules/design/backup/maintenance가 포함됨. | 실제 domain/email/policy 값은 승인 자료 |
| 16 | 오류·알림 메시지 | custom product/profile/catalog의 일부 한국어 validation/ACL/save messages. | 전체 core toast/error/email/report/push/notification Korean E2E 없음. | synthetic template audit 가능; 운영 수신자·정책은 판매자 승인 필요 |

사용자가 신규 B2B 고도화 기능 개발을 제외했으므로 wallet/settlement/withdrawal은 계속 미구현·이번 범위 제외다. 기존 요건 문서에는 남은 요구사항으로 표시한다. CI 주문취소/credit slip은 실결제나 현금 환불 증거가 아니다.

**정식 출시는 준비되지 않았다.** 실제 판매 자료와 운영 인프라·복구 절차가 없고, 전체 Back Office 한국어 인수 조건도 확인되지 않았다. #401761 전체 격리 QA가 실행 중이며, 미결 항목을 PASS로 기록하지 않는다.

## PWA 성공 기준점 및 당시 출시 검토 스냅샷 (2026-10-24)

이 절은 `b99b615`에서 성공한 기존 PWA 기준과 2026-10-24 당시 출시 검토를 보존한다. 현재 요구사항 상태는 이 문서 맨 위 표를 기준으로 한다.

PWA trace correction commit: **b99b61559978dd8b4c25819623669e0d92deb768** (`work`)

`main`: **ee02a3657448d563508687614a246e05ac61eecd** (변경하지 않음)

- 같은 SHA `44a88a07e0693ecf463764a357262f5d19455529`의 full isolated Actions [#40131335079](https://github.com/goldeget/japan-premium-commerce/actions/runs/40131335079)와 [#40131324863](https://github.com/goldeget/japan-premium-commerce/actions/runs/40131324863)은 모두 **FAIL**이다. 해당 SHA 기준 완료 시각이 더 늦은 #40131324863 (21:02:10 UTC)이 최신 완료 run이다. Step 65 aggregate는 두 run 모두 `pwa_browser_qa=failure`; annotation은 desktop-en과 mobile-en 각각 `stage=guest_empty_checkout_route; exception=AssertionError`만 보여 준다. 내부 assertion은 식별되지 않았고, 이 run에서 HTTP 404가 발생했다고 확인된 것은 아니다. Step 41의 초록 표시는 `continue-on-error` 결과이므로 aggregate를 덮지 않는다. Step 49는 조건부 skip, Step 68 run 전용 리소스 정리는 PASS다.
- 이전의 로그아웃 후 404 증상 뒤 JA/KO 계정 경로를 CI DB에서 확인해 일본어 `マイアカウント`, 한국어 `내 계정` 경로를 테스트·서비스워커 보호 목록에 반영했다. 후속 run에서 가입·로그아웃 Step 34와 PWA Step 41은 통과했고 404는 재현되지 않았다. 다만 당시 #40036387808의 원 요청 URL·리다이렉트 체인·서비스워커 관여는 Actions 로그/ZIP 본문에 접근하지 못해 독립 확인하지 못했다. 이 실행환경은 GitHub API 메타데이터는 읽지만 로그 및 ZIP 본문을 제공하는 파일 저장소 연결에서 프록시 403을 받는다.
- 진단 커밋 `16f3f3a`는 빈 체크아웃 validator의 안전한 하위 단계와 민감정보 없는 trace를 추가했다. 그 코드의 full run [#40132927859](https://github.com/goldeget/japan-premium-commerce/actions/runs/40132927859)은 **FAIL**이었다. EN PC·모바일 둘 다 `guest_empty_checkout_initial_route`에서 실패했고, safe trace는 `/en/cart` HTTP 200, `private, no-store`, service-worker/cache 미사용을 표시했다. 원인은 `navigate_private_document()`가 cache policy 확인에 쓴 최종 카트 URL을 trace의 최초 요청 URL로도 넘긴 테스트 harness 오류였다. 따라서 trace가 카트만 기록하면서 order controller 시작을 요구해 실패했다. 애플리케이션의 HTTP 404가 아니며 조건을 완화하지 않았다.
- `b99b615`는 cache-header 확인용 최종 문서 URL과 redirect trace용 최초 요청 URL을 분리하고, 실제 `navigate_private_document()` 경계를 재현하는 회귀 테스트를 추가했다. 테스트는 수정 전 `expected order / got cart`로 실패하고 수정 후 통과했다. 로컬 PWA/cache suite는 **101/101**, 오프라인 smoke는 **526 PASS, 7 skipped**, Python/JS syntax와 `git diff --check`도 통과했다.
- 수정 SHA `b99b615`의 격리 full run [#40134196682](https://github.com/goldeget/japan-premium-commerce/actions/runs/40134196682)은 2026-10-24 21:37:51 UTC **SUCCESS**로 완료됐다. Step 65 aggregate와 Step 68 run 전용 리소스 정리가 성공했고 failed/cancelled step은 없다. Step 49 및 실패 진단 Step 66은 조건부 skip이다. 회원 가입·로그아웃 Step 34, PWA·비공개 경로 캐시 Step 41, 무료배송·세금·주문 금액 대조 Steps 52–57, 재시작 및 일본우편 데이터 Steps 62–64가 통과했다.
- 같은 run의 check annotation에는 한국어 로그아웃 trace 10개가 남았다. 선택된 계정 페이지/메뉴 로그아웃 링크는 same-origin `/ko/`의 `mylogout` 요청과 모두 일치했고 redirect 상태는 `302 → 302 → 200`, 각 `Location`은 다음 요청과 일치했으며 최종 응답은 테스트가 기대한 로그인 경로의 HTTP 200이었다. 서비스워커가 우회 전 문서를 제어했지만 logout probe는 우회를 켰고 기록된 30개 응답 모두 `from_service_worker=false`였다. 이는 수정 후 실행 증거이며 과거 #40036387808의 실패 순간을 재구성한 기록은 아니다.
- PC·모바일 브라우저 캡처는 완료 run의 [browser QA artifacts](https://github.com/goldeget/japan-premium-commerce/actions/runs/40134196682/artifacts)에 보관되어 있다. artifact `ordenowa-storefront-browser-40134196682-1` (ID `12576851933`, 15,618,931 bytes)은 metadata상 만료되지 않았고 Step 61 screenshot coverage가 통과했다. 화면은 Actions에 기록됐으나 파일 본문은 이 실행환경에서 직접 다운로드해 재확인하지 못했다.

### 출시 준비 항목

아래 표는 성공 기준점 실행 당시 기록이며, 2026-10-25의 최신 상태를 대신하지 않는다.

| 항목 | 상태 | 근거 및 필요한 입력 |
| --- | --- | --- |
| 실제 판매 상품 등록 및 고객 화면 | BLOCKED | CI는 합성 상품으로 검색·장바구니를 확인했고 관리자는 별도 비활성 상품을 생성·수정했다. 출시할 SKU, 이미지 사용권, 상품 설명, 재고와 판매 승인 자료가 없다. |
| 실제 가격·세금·배송 | BLOCKED | 출시 정책상 지원 지역 배송비 ¥0이다. CI의 합성 10%·명시적 0% 세금과 Tokyo/Osaka 주문은 실제 판매자 세무 판단, 상품별 세율, carrier 계약·계정·전 지역 운영 가능성을 입증하지 않는다. 판매자/세무 담당자의 상품 매핑과 배송 운영 설정이 필요하다. |
| 주문 상태·취소·환불·반품 | INCOMPLETE | 브라우저 주문은 미결제 `ps_checkpayment`를 쓰고 저장 및 별도 관리자 조회를 확인했다. 실제 결제와 운영 fulfillment, 취소·환불·반품 절차는 검증하지 않았다. |
| 운영 결제 설정 | BLOCKED | 기본 프로필은 `bank_accounts=[]`, 은행 이체 disabled, 결제 안내문 blank다. seller/provider 승인 및 실거래는 진행하지 않았으며, 출시 전에 승인된 결제 제공자 또는 검증된 계좌·안내문을 구성해야 한다. |
| 한국어 관리자 전체 번역 | INCOMPLETE | 프로젝트 모듈과 선택된 상품/운영 흐름의 일부를 확인했다. 기록된 화면 문자열 결함은 이미 overlay로 보완됐으나, 공식 Korean language pack 버전과 전체 PrestaShop core/메뉴/주문/고객/설정 화면의 100% coverage는 확인하지 않았다. 확인되지 않은 번역 결함을 추측해 완료로 기록하지 않는다. |
| 운영 도메인·HTTPS·메일 발송 | BLOCKED | Compose와 CI는 localhost 및 disposable Mailpit을 사용한다. 운영 DNS/TLS와 발신자 설정, 외부 메일 전달성 증거가 없다. |
| 백업·복원 절차 | CI 검증 중 / 운영 BLOCKED | CI 전용 DB·파일·queue backup/restore drill은 현재 SHA의 fresh-install run에서 확인 중이다. 운영 백업 위치·보존·암호화·접근·RPO/RTO·책임자와 운영 restore drill은 별도로 준비되지 않았다. |
| iOS·Android PWA 설치 | INCOMPLETE | Chromium에서 manifest, service worker, PC·모바일 뷰를 확인했지만 iOS/Android 실기기 홈 화면 설치·업데이트·실행은 확인하지 않았다. |
| PC·모바일 Chromium PWA 전체 흐름 | 이전 checkpoint PASS | #40132927859의 EN desktop/mobile 빈 체크아웃 trace 실패는 최초 주문 URL 대신 최종 카트 URL을 trace 시작점으로 넘긴 테스트 harness 오류였다. `b99b615`의 #40134196682에서 회원 로그아웃 Step 34와 PWA lifecycle/privacy-cache Step 41이 통과했다. 원래 증상인 HTTP 404는 후속 실행에서 재현되지 않았다. 최신 SHA의 PWA 상태는 맨 위 범위 표를 본다. |
| 판매자·고객센터·배송·환불·법률 정보 | BLOCKED | `ProfileDefaults.php`에서 LOGISTEED는 참고정보로 분리되어 있고 seller authorization은 `pending`; 판매자 법적 신원, 주소, 대표/연락처 및 운영 정책 입력이 비어 있다. 승인 정보 없이는 게시·운영을 진행할 수 없다. |

**당시 출시 불가 판단.** 현재 출시 판단은 맨 위 최신 범위 표를 본다. 실제 판매자/상품/세금/배송/결제/지원 정보와 운영 인프라, 재해복구 및 실기기 검증은 운영 출시 전 요구사항이다.

## 출시 가격 정책 QA 상태 (2026-10-23 23:06 UTC; 당시 실행 스냅샷)

현재 `work` 및 `origin/work` 기준 커밋: **c60a851e114ff00f6e4d8c8c708ad3016bc980bd**
`main`: **ee02a3657448d563508687614a246e05ac61eecd** (변경하지 않음)

- 출시 정책은 일본 지원 지역 배송비 ¥0, 상품에 표시된 적법한 세금 포함 가격을 최종 상품 가격으로 취급, 결제 단계 추가 배송비·세금·플랫폼 수수료 없음이다. 실제 세금은 판매자와 상품에 명시적으로 연결된 세금 규칙을 따른다. 규칙 미할당을 면세나 0%로 기록하지 않는다.
- 최신 격리 fresh-install 실행 [#40036387808](https://github.com/goldeget/japan-premium-commerce/actions/runs/40036387808), SHA `c60a851`, 전체 workflow 결과는 **FAIL**이며 Step 65 aggregate가 보고한 유일한 실패는 `pwa_browser_qa=failure`다. PC logout 후 로그인 폼을 기다리는 동안 최종 문서가 HTTP 404가 된 PWA 경로 문제이며, 가격 단계 실패는 보고되지 않았다.
- 가격 runtime QA Steps 52–57은 모두 PASS다. Step 52 Tokyo PC 수량 2+쿠폰 및 같은 장바구니 PC·모바일 합계 대조, Step 53 Osaka 모바일 수량 1, Step 54 합성 과세 상품, Step 55 명시적 0% QA 상품을 브라우저에서 확인했다. 상품 상세·장바구니·체크아웃·주문 확인·주문내역이 일치했고, Step 56은 미결제 네이티브 주문의 가격·세금·배송·쿠폰·총액을 격리 DB와 대조했으며, Step 57은 별도 관리자 세션에서 네 주문 금액을 확인했다.
- 무료 운송사는 PrestaShop 관리자 화면에서 설정·재조회(Steps 44–46)했다. QA 결제는 미결제 `ps_checkpayment`만 사용했다. 체크아웃 설정을 fail-closed 기본 상태로 복구하고 다시 확인(Steps 58–59), PC·모바일 캡처와 coverage(Steps 60–61), shop 재시작 지속성(Step 62), Japan Post 데이터 가져오기·검증(Steps 63–64), run 전용 리소스 정리(Step 68)도 통과했다.
- 격리 DB의 과세 fixture는 테스트 전용 합성 10% 규칙(¥1,100 세금 포함 = ¥1,000 세전 + ¥100 세액)이며 명시적 0% fixture와 구분한다. 이는 일본 법정 세율, 판매자의 세무 상태, 실제 상품의 과세·면세 적법성을 입증하지 않는다. 47개 지원 도도부현은 무료배송 zone fixture로 확인했지만 실제 브라우저 주문 표본은 Tokyo와 Osaka뿐이며 전 지역·모든 조건 조합의 주문 QA는 아니다.
- 이메일 로컬 파트 길이를 RFC 한도에 맞춘 CI 전용 수정 `c60a851` 이후 면세 체크아웃, 주문 저장 및 관리자 조회가 통과했다. 이 수정의 focused checkout/free-shipping 계약 77개와 별도 pricing/tax focused suite 83개가 통과했다. Python 구문 및 `git diff --check`도 통과했다.
- 전체 workflow는 PWA logout/redirect 문제 하나로 빨간 상태이므로 전체 QA PASS로 표시하지 않는다. 운영 DB·named volume·운영 carrier 설정 변경, 실결제, 운영 배포는 하지 않았다. Docker/DB/Chromium QA는 격리된 GitHub Actions에서 실행했다.

## 이전 이어가기 기준 (2026-10-23 02:33 UTC; 과거 검증 이력)

작업 브랜치: **work**
최신 기능 코드 및 full Chromium 검증 SHA: **dfa30a1127a50d2eb4926d7c1fb6d75030a64121**
`main`: **ee02a3657448d563508687614a246e05ac61eecd** (수정하지 않음)

### 현재 검증 현황

| 영역 | 상태 | 근거와 한계 |
| --- | --- | --- |
| ORDENOWA 브랜드 자산 | 브라우저 PASS | ZIP 22개 항목 CRC, 원본 3종·파생 17종 SHA-256 및 KURANEA 백업을 검증했다. #39888149608 Steps 28–29와 #39889443441 Steps 28–29에서 업로드·초안·미리보기·게시·교체복원, PC·모바일·관리자 로그인·favicon·Apple·PWA·OG·SEO 이미지 출력 및 Mailpit 재설정 이메일 로고가 통과했다. #39889264268과 #39889443441의 Step 28에서 영문 공개 페이지 브랜드/SEO/PWA 검사가, Step 41에서 필수 캡처 gate가 통과했다. |
| 회원 계정 | Chromium PASS | #39888149608, #39889264268, #39889443441 Step 30 및 각 전체 aggregate에서 가입·이메일 로그인·로그아웃·비밀번호 재설정·마이페이지가 통과했다. #39888370630의 `account=failure`는 reset 이후 이전 로그인 오류 상태 오판이었다. `dfa30a1`은 검증된 로그인 URL을 다시 열고 오류 알림 부재를 확인하도록 수정했고 #39889443441에서 통과했다. |
| 한국어 관리자 상품 | Chromium PASS | #39888149608, #39889264268, #39889443441 Step 31에서 실제 관리자 상품 생성·수정과 옵션별 재고 확인이 성공했다. 등록 fixture는 비활성이고 checkout 검증은 별도의 활성 synthetic CI 상품을 사용했다. |
| 상품·장바구니·무결제 주문 | Chromium PASS | #39888149608, #39889264268, #39889443441 Steps 32–39에서 검색·상품 상세·장바구니, PC·모바일 일본 주소 주문, 오프라인 `ps_checkpayment` 저장, 별도 관리자 주문 조회와 checkout fail-closed 복구가 통과했다. 실결제는 실행하지 않았다. |
| 스크린샷·재시작·주소 데이터 | 전체 coverage PASS | #39888149608, #39889264268, #39889443441 screenshot coverage, 빈 설치 재시작, Japan Post import 및 전국 주소 수 검사가 통과했다. #39888370630은 계정 실패 뒤 진단 fallback만 실행해 전체 screenshot coverage를 인증하지 않았다. |
| 한국어 운영·SEO·PWA 설정 | 브라우저 설정 흐름 PASS, 운영 일부 미검증 | c078 브랜드 관리자 화면은 회사·고객지원·배송/환불 문구·SEO·PWA 필드를 저장·재조회·미리보기·게시하고 공개 출력을 확인했다. 배송 정책 편집과 관리자 배송 화면 연결을 확인했지만 배송 요율 변경, 환불 거래, iOS/Android 홈 화면 설치는 테스트하지 않았다. |
| Codex Cloud 실행 범위 | Docker 빌드 미실행 | 이미지·DB·Mailpit·Chromium 검증은 GitHub Actions에서 수행한다. Codex Cloud의 `vfs`/32 GB 제한을 넘기는 빌드, 운영 배포, 실결제는 실행하지 않았다. |

### 최신 GitHub Actions

- [dfa30a1 — Isolated fresh install #39889443441](https://github.com/goldeget/japan-premium-commerce/actions/runs/39889443441): 전체 PASS. Steps 28–30 브랜드·메일·계정, 31–39 상품·장바구니·일본 무결제 주문·관리자 조회·checkout 복구, 40–41 캡처/coverage, 42 재시작, 43–44 Japan Post, 45 aggregate가 성공했다. Step 35 진단은 조건부 건너뜀이다.
- [021214d — Isolated fresh install #39889264268](https://github.com/goldeget/japan-premium-commerce/actions/runs/39889264268): 전체 PASS. 영문 브랜드 검사와 필수 screenshot gate를 포함한 브라우저, 계정, 상품, 주문, 재시작 및 주소 데이터 단계가 성공했다. Step 35 진단은 조건부 건너뜀이다.
- [021214d — Offline catalog parser #39889264241](https://github.com/goldeget/japan-premium-commerce/actions/runs/39889264241): PASS (범위 제한). PHP lint/parser와 fresh-install 계약 검사; 통합 설치/브라우저 QA 판정은 아니다.
- [49bad87 — Isolated fresh install #39888370630](https://github.com/goldeget/japan-premium-commerce/actions/runs/39888370630): FAIL; aggregate는 `account=failure`. 계정 진단은 `/ko/`에서 `authenticated`와 사용자 메뉴 표시를 확인했고 이전 로그인 오류 알림과 인증 후 결과의 오판 경계가 드러났다. 브랜드·상품·무결제 주문·스크린샷·재시작·주소 단계는 통과했다.
- [60a82f3 — Isolated fresh install #39888149608](https://github.com/goldeget/japan-premium-commerce/actions/runs/39888149608): 전체 PASS. 브랜드·메일·계정·상품·무결제 주문·관리자 조회·전체 screenshot gate·재시작·Japan Post 단계가 통과했다. Step 35 진단은 조건부 건너뜀이다.
- [8423011 — Isolated fresh install #39879610940](https://github.com/goldeget/japan-premium-commerce/actions/runs/39879610940): completed FAIL, raw aggregate `account=failure`만 남았다. 브랜드·상품·장바구니·무결제 주문/관리자 조회·전체 screenshot coverage·재시작·Japan Post 검사는 통과했다. 회원은 동의 선택 뒤 `email_login`의 구체 하위 대기에서 timeout됐으며 비밀번호 재설정은 수행되지 않았다.
- [9525b37 — Isolated fresh install #39879191400](https://github.com/goldeget/japan-premium-commerce/actions/runs/39879191400): completed FAIL, raw aggregate `account=failure`만 남았다. PC·모바일 `/identity`에서 실제 필수 입력 `psgdpr`가 비어 있었고, 초록 Step 30은 이 실패를 덮지 않았다. 이 커밋은 잘못된 selector를 사용했다.
- [9525b37 — Offline catalog parser #39879191441](https://github.com/goldeget/japan-premium-commerce/actions/runs/39879191441): PASS (범위 제한). 통합 설치/브라우저 QA 판정은 아니다.
- [c078b38 — Isolated fresh install #39878462667](https://github.com/goldeget/japan-premium-commerce/actions/runs/39878462667): raw aggregate FAIL, `account=failure`만 남았다. 실제 invalid control은 `name=psgdpr`; 초록색 browser step은 이 annotation을 덮지 않는다. Brand/email, product, cart/order/admin, fail-closed, screenshot, restart 및 KEN_ALL 단계에는 실패 annotation이 없다.
- [c078b38 — Offline catalog parser #39878462635](https://github.com/goldeget/japan-premium-commerce/actions/runs/39878462635): PASS (범위 제한).

### 최근 기능 커밋

| 커밋 | 변경 | 검증 |
| --- | --- | --- |
| `dfa30a1` | 이전 비밀번호 거부 화면을 닫고 검증된 한국어 로그인 URL에서 새 비밀번호를 제출하도록 계정 QA 수정 | 회귀 계약 RED→GREEN, 계정 계약 22개, 오프라인 전체 304개, Python 구문 통과. #39889443441 full Chromium QA PASS. |
| `021214d` | 영문 고객 페이지 SEO·OG·JSON-LD·manifest·브랜드 이미지 검사와 필수 캡처 추가 | 브랜드/SEO 계약 및 오프라인 전체 303개 통과. #39889264268 full Chromium QA PASS; Offline parser PASS. |
| `49bad87` | 재설정 뒤 로그인 실패 지점을 안전한 하위 상태로 진단 | #39888370630에서 이전 로그인 오류 알림과 인증 결과 충돌 확인; diagnostic-only CI 실패. |
| `60a82f3` | 한국어 가입 경로 언어 보존 검사 | #39888149608 full fresh-install Chromium QA PASS. |
| `cf3c413` | 로그인·로그아웃의 브라우저 결과를 검증 | #39887294434에서 계정 실패가 재현되어 후속 진단 수행. |
| `f6dd110` | email login/logout/authentication 대기 결과를 분리하고 개인정보 없는 CI 상태 진단 추가 | 계약·오프라인 검사 및 범위 제한 parser workflow 통과. |
| `8423011` | 계정 QA가 실제 필수 `/identity` 입력 `psgdpr`를 선택하도록 수정 | 회귀 계약을 먼저 RED로 확인한 뒤 수정. 동의 선택 오류는 사라졌으나 #39879610940에서 계정 login 단계 timeout으로 aggregate 실패. |
| `9525b37` | 프로필 동의 체크박스 직접 클릭 및 상태 확인 | Fresh-install #39879191400 raw aggregate `account=failure`; PC·모바일에서 `psgdpr`가 계속 선택되지 않았다. 잘못된 selector였다. |
| `c078b38` | PrestaShop 현지화된 재설정 경로를 메일·브라우저 검증과 일치 | 브랜드와 주문 흐름 단계 성공; aggregate의 유일 실패는 계정 `psgdpr` 입력 선택. |
| `143d984` | 인증 전 관리자 로그인 로고 URL 캡처 | 후속 c078 run의 brand/login 검증에는 실패 annotation이 없었다. |

## 이전 완료 기준 결과

- `b58a2eb`의 #656은 `account=failure` raw aggregate였고 brand upload/publish와 product/cart/order 경로 단계가 성공했다.
- `fc00804`의 #662은 `account=failure`; 한국어 login form/email-label assertions 뒤 reset-link polling 중 controller 404 → 일본어 경로 302가 관측됐다. 원인은 미확정이며 Mailpit logo assertion은 실행되지 않았다.
- `f8719ee`의 #670은 `shipping_admin=failure account=failure`; 배송 요율을 바꾸지 않았다.
- `761cc62`의 #835는 `brand=failure shipping_admin=failure account=failure`; brand replacement timeout이 보고됐다.
- Scope-limited SEO, business-profile, parser workflows는 각각의 계약 범위에서 PASS이며 전체 fresh-install/browser QA를 대체하지 않는다.

## 실행 기반

- PrestaShop 9.2.0, Hummingbird 2.1.2, MariaDB 10.11, Docker Compose를 사용한다. 개발 포트는 `127.0.0.1:8080`에 바인딩된다.
- Codex Cloud는 코드 분석·수정·Python 계약 테스트에 사용한다. 이 런타임은 Docker `vfs` storage driver와 32 GB 파일시스템을 사용하며 PrestaShop 이미지 빌드가 공간 부족으로 실패했다. 호스트 기본 PHP CLI는 없지만, 서명된 배포판 패키지를 격리 경로 `/tmp/brand-php-runtime`에서 검증한 PHP 8.4/GD 런타임으로 사업자 프로필 PHP 계약을 실행했다. 시스템 패키지는 설치하지 않았다. 여기서 Docker 빌드·Compose 구동을 반복하지 않고, 이미지·DB·Chromium 검증은 격리된 GitHub Actions에서 수행한다.
- 현재 작업트리는 `/workspace/japan-premium-commerce`의 `work`다. 미추적 `tests/admin_locale/__pycache__/`, `tests/business_profile/__pycache__/`, `tests/e2e/__pycache__/`, `tests/postcode/__pycache__/`, `tests/smoke/__pycache__/`는 삭제하지 않았다. `main` SHA `ee02a3657448d563508687614a246e05ac61eecd`는 보존한다. 이 설정 작업에서 컨테이너나 named volume을 만들거나 초기화하지 않았다.

## 구현 상태 기록 (2026-10-22 과거 스냅샷; 현재는 위 최신 표가 우선)

| 영역 | 상태 | 확인 내용 |
| --- | --- | --- |
| ORDENOWA 공식 이미지 | BLOCKED | 세 이미지 미리보기는 대화에 표시되지만 첨부 다운로드가 `cannot create attachment directory: Not a directory`로 실패했고 로컬 원본 바이트를 찾지 못했다. 저장소에는 KURANEA 원본만 있어 이를 보존했다. ORDENOWA 로고·파비콘·PWA 아이콘은 생성·교체하지 않았다. |
| 쇼핑몰 운영 설정 모듈 | 코드·CI PASS, 실제 운영 화면 QA 미완료 | 한국어 설정 폼, 다국어 브랜드·회사 참조/판매자 분리, 이미지 업로드 파생물, 초안·게시·이력·복원, 공개 법률 페이지·푸터·SEO·manifest·메일 연결이 있다. bank transfer는 사용 여부와 계좌 연결을 별도로 선택하고 선택된 활성 계좌 하나만 공개한다. CI run `39757526475`에서 PHP lint와 모듈·법률·메일 계약이 통과했다. 실제 관리자 브라우저 저장·미리보기·게시 및 세 언어 확인은 미실행이다. |
| SEO 메타데이터 보안 | 소스 계약 CI PASS, 실제 Smarty 렌더링 QA 미실행 | Draft PR #3의 동적 title/description/robots/canonical/hreflang/Open Graph 이스케이프와 JSON-LD `JSON_HEX_TAG` 수정을 검토해 `000b066`에 반영했다. PWA script URL 속성도 HTML 이스케이프한다. 전용 Actions run `39786618881`의 2개 Python 계약 테스트와 기존 테마 계약 15개가 통과했다. |
| LOGISTEED 운영 법인 참조 | 초깃값 구성·미확인 | ロジスティード株式会社, LOGISTEED, Ltd., 법인번호·주소·대표전화·대표자를 참고정보로 분리했다. 실제 판매사업 정보는 별도 빈 설정이고 승인 상태는 pending이므로 공식 판매처 표기와 거래는 fail-closed다. |
| Storefront 및 반응형 | 기존 화면 일부 확인, ORDENOWA 최종 QA 미실행 | 일본어/영어/한국어 빈 카탈로그 화면과 반응형 자식 테마의 과거 캡처가 남아 있다. 현재 상품은 0개다. 이 작업에서 새로운 ORDENOWA 실제 브라우저 스크린샷, 상품 카드·상세·주문 여정은 확보하지 않았다. |
| JPY 기본 통화 | 설정 코드·이전 읽기 확인 | JPY 기본 통화와 ja/en/ko 표시명·0자리 정밀도 설정 코드가 있다. 최근 신규 설치 CI는 우편 CSV 단계에서 중단되어 이번 실행에서 JPY·테마·관리자 로그인 설정을 검증하지 못했다. |
| 일본 주소 자동완성 | 기존 DB/API 확인, 빈 설치·주문 E2E 미검증 | 7자리·하이픈·전각 숫자, 일본어 검색, 후보 선택, 수동 주소 입력, ja/en/ko를 지원한다. 이전 dev DB에 공식 KEN_ALL 고유 후보 124,839건이 있었고 읽기 전용 조회는 통과했다. 새 빈 설치 CI는 Japan Post가 HTTP 503을 반환해 import 이후 lookup·주소·주문 검사가 건너뛰어졌다. |
| 관리자 한국어 | 부분 적용, 100% 미완료 | 로그인·대시보드·주문 목록의 과거 PC/모바일 점검과 프로젝트 소유 Module Manager 표시명 수정이 있다. CI에서 운영 설정 폼 한국어 계약이 통과했다. 전체 PrestaShop core·모든 메뉴·상품/고객/주문/설정 화면의 100% 한국어와 현재 브라우저 검증은 미완료다. |
| PWA | manifest·service worker 기반, 공식 아이콘·기기 QA 미완료 | 동적 manifest 및 정적 자산 전용 offline page가 있으나 ORDENOWA 원본 이미지가 없어 아이콘 목록이 비어 있다. iOS·Android 실기기 설치도 미실행이다. |
| 카탈로그 파서·검수 | fixture parser CI PASS, 실제 상품 등록 미검증 | Amazon Japan/Rakuten HTML fixture 파서, 영속 JSON queue, TEST/DEMO 승인 서비스, 비활성 native product adapter 및 한국어 검수 탭이 있다. run `39760154509`에서 PHP 8.3 lint와 parser/관리자 계약이 성공했다. 빈 설치 CI의 카탈로그 모듈·queue 재시작 보존도 run `39759208769`에서 Japan Post 다운로드 단계 전까지 통과했다. 실제 PrestaShop 상품 생성·브라우저 검수는 아직 미검증이고 외부 수집 0건이다. |
| 실제 상품·주문 | 0건 / E2E 미실행 | 로컬 DB에서 상품·주문 0건으로 이전 확인됐다. 신규 설치 503 때문에 주소가 들어간 무결제 주문 저장·한국어 관리자 조회·재시작 보존은 이번 작업에서 확인되지 않았다. |
| 신규 설치 CI | FAIL / Japan Post HTTP 503 | run `39760154414`도 기존 `--retry 3`을 거친 뒤 공식 KEN_ALL 다운로드에서 `curl_exit=22 http_status=503 effective_host=www.post.japanpost.jp`로 실패했다. 앞선 이미지 build/cache/startup/catalog queue 검사가 통과했고, 주소 조회·주소/주문 저장·관리자 조회·최종 재시작 검사는 건너뛰었다. 반복 실행을 성공으로 취급하지 않으며 외부 주소 데이터 단계의 제한을 별도로 기록한다. |

## 이전 작업 기록

- `6f6ff5e`에서 synthetic Amazon Japan/Rakuten 파서를 파일 기반 검수 큐, 원자적 승인 서비스 및 숨김 상태 PrestaShop Product 등록 어댑터에 연결했다. 전용 Actions run `39756075106`은 PHP lint와 fixture 테스트에서 성공했지만 실제 PrestaShop DB 등록·관리자 화면은 검증되지 않았다.
- `ba508b4`에서 관리자 특정상거래법 라벨을 한국어로 바꿨다. 후속 run `39756576373`에서 다국어 필드에 붙는 `· 일본어`를 테스트 기대값이 빠뜨린 것이 확인되어 `3ec583c`에서 assertion을 수정했다. 그 뒤 CI는 법률 페이지에서 `<h1>` 제목이 렌더링되지 않는 실제 결함을 드러냈다.
- `3404116`은 PHP 예외를 Actions 요약에 노출하도록 진단을 보강했다. `7cf8c41`에서 localized `<h1>`와 bank-transfer 계좌 링크를 구현했고 business-profile Actions run `39757526475`는 PHP lint, 설정·법률·공개 프로필·메일 검사 모두 통과했다.
- `cc448a6`에서 두 프로젝트 모듈의 Module Manager 이름/설명을 한국어로 바꿨다. admin locale Python 검사 13/13, business-profile Python 계약 검사 10/10, fresh-install workflow 계약 10/10이 통과했다. 이 계약 테스트들은 실제 관리자 브라우저 UI 검증을 대신하지 않는다.
- `940d8a0`에서 카탈로그 파서 검수 모듈·한국어 Back Office 탭과 별도 named volume 영속 queue를 연결했다. fresh-install run `39759208769`에서 해당 모듈 설치와 PrestaShop 재시작 후 queue 유지가 확인됐지만 Japan Post HTTP 503 뒤 주소·주문 단계는 실행되지 않았다.
- run `39759208949`는 `amazon_jp`가 의도된 중복 키에도 나타나는데 페이지 전체에서 금지하던 과도한 assertion 때문에 실패했다. `5b2a1cb`에서 중복 키와 이미지 메타데이터의 출처 표기를 분리해 검사하고 실패 로그를 80줄/500자로 제한 및 GitHub annotation escape 처리했다. parser run `39760154509`가 성공했다. 이 수정은 실제 파서 로직을 바꾸지 않았다.
- fresh-install run `39760154414`도 공식 Japan Post host HTTP 503으로 종료됐다. `update-ken-all.sh`에 이미 `curl --retry 3 --retry-delay 2`가 있어 같은 동작의 재실행만으로는 해결되지 않는다. 이 run은 빈 설치의 전체 주문 E2E를 PASS로 만들지 못했다.
- fresh-install run `39756769346`은 빈 볼륨 Compose 기동까지 통과했으나 `www.post.japanpost.jp`가 HTTP 503을 반환해 KEN_ALL import 이후 주소·주문·재시작 단계를 수행하지 못했다. 해당 실패를 새 설치 PASS로 기록하지 않는다.
- ORDENOWA 이미지 3장은 대화 미리보기로 보이나 Sediment 파일 다운로드가 staging 오류로 실패했다. 저장소 `assets/brand/source/`의 KURANEA 원본은 보존했고, 이를 새 공식 로고로 가장하지 않았다.
- JPY 설정을 신규 설치 및 기존 설치 부트스트랩에 연결했다. DB에서 JPY 활성·기본값, ja/en/ko 통화명을 확인했고 상품/주문 수는 각각 0건임을 읽기 전용 조회로 확인했다.
- 우편번호 테스트는 `1000004` 샘플뿐 아니라 CP932 파싱, 전각 입력, 복수 후보, 후보 선택, 네이티브 주소 필드 및 수동 건물명 매핑을 포함한다.
- 관리자 계약 테스트는 특정 로그인·번역 오버레이만 확인한다. 전체 관리자 한국어 수용 기준을 충족한다고 표시하지 않는다.
- CI 실패 진단 스크립트는 로그를 stdout·요약·artifact에 쓰기 전에 자격 증명 형태를 가리고, 이후 설치 단계의 실패에도 같은 수집기를 사용한다. 테스트용 민감 문자열을 실제 로그와 요약에서 제거하는 회귀 검사를 추가했다.
- 2026-10-22: Hummingbird featured-products 모듈은 대상 상품이 없을 때 템플릿 렌더링 자체를 건너뛴다. 자식 테마 홈 템플릿에 일본어·영어·한국어 빈 카탈로그 안내를 배치했고, 실제 상품 목록이 렌더링되면 안내를 감추도록 했다. 최신 PC·모바일 캡처는 `artifacts/qa/phase1a/home-empty-state-desktop-v2.png`와 `home-empty-state-mobile-v2.png`다.
- 2026-10-22: 공식 KEN_ALL archive를 기존 모듈 importer로 개발 DB에 적재하고 API를 확인했다. 활성 데이터 124,839건, staging 0건이다. importer는 성공적으로 교체한 뒤에만 staging 복사본을 비우며 신규 설치 smoke도 이를 검사한다. 주소 위젯 캡처는 주소 폼 계약 fixture를 사용했으므로 실제 checkout 화면 증거는 아니다.
- 2026-10-22: 체크포인트 `2636d67`에서 일본어·영어·한국어 검색 및 빈 카테고리 상태, 푸터 접근성 문구를 보강했다. PC·모바일 화면을 실제 Chromium에서 확인하고 해당 캡처를 `artifacts/qa/phase1a/`에 저장했다.
- 2026-10-22: 체크포인트 `bb40026`에서 Japan Post 후보가 있는 경우 주소 저장 전에 도도부현·시구정촌·町域이 일치하는지 서버 검증한다. 테스트용 synthetic rows와 기존 dev DB의 실제 `1000004` 후보로 조회·오류·수동 fallback을 검증했다. live 검증은 DB를 변경하지 않았다.
- 2026-10-22: 체크포인트 `46fc912`에서 관리자 한국어 XLIFF overlay 도메인을 PrestaShop 표기와 맞추고, 대시보드의 영어 날짜 필드/요약을 KURANEA 모듈 JS로 번역했다. 실제 관리자 브라우저에서 PC 1440px, `lang=ko`, 날짜 입력/요약 한국어, JS 오류 0건을 확인했다. 전체 관리자 100% 한국어는 아직 아니다.
- 2026-10-22: `1f5f552`에서 격리 GitHub Actions에만 실행되는 일본 우편 주소 주문 저장 검증을 추가했다. 실행 ID와 Compose 프로젝트명이 일치하는 CI 가드, 오프라인 무결제 모듈, CI 전용 무료 배송사, 공식 `1000004` 주소, 수정 가능한 번지·건물명, 네이티브 Order와 관리자 주문 조회 주소 projection 검사를 포함한다. 로컬 PHP 컨테이너에서 문법만 검사했고, 스크립트는 운영 중인 dev DB에서 실행하지 않았다.
- 2026-10-22: 관리자 주문 목록을 인증된 메뉴 링크로 열어 데스크톱 1440×1000 및 모바일 390×844, HTTP 200, JS 오류 0건을 확인했다. 주문 0건이라 실제 배송지 행은 없으며 캡처는 `artifacts/qa/phase1a/admin-orders-list-korean-desktop-qa.png`, `admin-orders-list-korean-mobile-qa.png`다. 화면 전체 번역 상태와 빈 상태 삽화의 영어 샘플 문구는 후속 점검이 필요하다.
- 2026-10-22: 첨부 ZIP에 든 KURANEA 공식 로고·파비콘·PWA 원본 SHA-256을 저장소 `assets/brand/source/`와 비교해 세 파일 모두 일치함을 확인했다.
- 2026-10-22: 체크포인트 `06617f6`에서 Japan Post town 설명 접미어를 고객용 주소·API 후보에서 제거하고 `以下に掲載がない場合`를 빈 주소란으로 처리했다. 원본 공식 CSV 값은 변경하지 않는다. `a444238`은 실데이터 검사에서 `大手町` 정규화를 단언하고, `1690a07`은 안전한 공식 데이터 갱신 CLI와 6개 계약 테스트를 CI 앞단에 추가했다. 도메인·응답 fixture 테스트, 실제 dev DB 읽기 전용 주소 검증에서 통과했으며 고객/주소/주문 행은 생성하지 않았다.
- 2026-10-22: 시작 후 cloud status를 다시 읽었다. 활성 revision 2, 저장 draft revision 4이며 draft의 repository SHA는 이전 기준 `2db9892`다. revision 3 적용 증거는 없고 draft를 수정하거나 게시하지 않았다. active network status에서 `api.github.com`을 확인할 수 없어 실패 실행의 상세 로그는 계속 접근 불가다.
- 2026-10-22: 최신 Actions 진단에서 이전 `errno 28` 가정과 다른 직접 원인을 확인했다. PrestaShop `Install::finalize()`는 `/admin/`이 없으면 기본 target `admin-dev`를 사용하지만 Docker entrypoint가 설치 전에 관리자 폴더를 옮겼다. 첫 수정안 `175d75d`는 CI run `39727310686`에서 이미지 빌드와 사전 검사를 통과했으나 빈 설치 단계는 실패했다. 현재 환경에서 상세 로그가 제공되지 않아 이 시도의 실패 세부를 확정하지 않는다.
- 2026-10-22: 후속 수정안 `fcf78ad`는 `PS_FOLDER_ADMIN=admin-dev`를 사용해 Docker entrypoint가 실제 관리자 파일을 기본 설치 경로에 유지하고, 공식 post-install 이후 PHP 부트스트랩이 `admin-kuranea`로 이동해 assets를 설치한다. 정적 경로 계약 4/4 통과, 원격 CI run `39728912492`는 Compose의 빈 상점 시작에서 실패했다. 실패 artifact는 존재하지만 현재 환경에서 읽을 수 없어 새 직접 원인은 미확정이다.

## 이전 우선순위 기록

1. 코드 리뷰 후 수정 후보를 `work`에 원격 보존하고 신규 설치 Actions를 한 번 실행한다. 실제 결과로 빈 DB 설치 및 주문 E2E를 판정한다.
