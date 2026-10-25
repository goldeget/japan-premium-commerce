# ORDENOWA 테스트 결과

## 2026-10-25 — 시각 QA 잔여 항목 수정 및 전체 격리 검증 완료

현재 코드 SHA `95af3a9104b6e3f7bfc861155bdc73db9a91ab98`가 remote `work`다. 최신 전체 격리 Actions [#40233614104](https://github.com/goldeget/japan-premium-commerce/actions/runs/40233614104)은 workflow 성공, Step 80 aggregate `PASS: isolated browser QA and official postcode verification completed.`로 종료했다. Aggregate에 기록된 `STOREFRONT_BROWSER_QA_OUTCOME=success`, `PWA_BROWSER_QA_OUTCOME=success`; Step 42 product/cart, Step 49 PWA, Step 73/75 screenshots, Step 83 run-only cleanup 모두 성공했다. 직전 성공 run #40231567083은 SHA `aed4a3cc6e143258e9f493603dd226bfa41b34aa`의 별도 기준점으로 보존한다.

Work-mode GPT가 #402315 browser artifact [ID 12613108935](https://github.com/goldeget/japan-premium-commerce/actions/runs/40231567083/artifacts/12613108935)를 열어 다음을 확인했다: `詳細を表示`, 모바일 checkout button visibility, 일본어 `マイアカウント`는 수정됐다. 남은 영어 정책 문구, catalog category data, KO account heading, long-title breadcrumb를 별도로 분류했다. screenshot inspection은 클릭/입력 상호작용 검사가 아니다.

| 항목 | 현재 결과 | 근거 |
| --- | --- | --- |
| checkout policy labels/helper copy | 자료 대기, 변경하지 않음 | Hummingbird checkout은 `conditions_to_approve` 값을 `{$condition nofilter}`로 출력한다. `Security policy`, `Delivery policy`, `Return policy`와 보조문구는 이 동적 승인 조건 콘텐츠이며 저장소의 정적 theme string이 아니다. 실제 판매자 승인 일본어 정책 문안 없이 법률성 문구를 만들지 않는다. English CI coupon label은 fixture 데이터다. |
| `Clothes`/`Art` category names | 자료 대기, 변경하지 않음 | storefront catalog data이며 theme translation entry가 아니다. 승인된 taxonomy label이 없으므로 이름을 추정해 번역하지 않는다. |
| Korean PWA account heading | 자동 브라우저 검증 PASS; 시각 재검수 대기 | `ShopThemeCustomeraccount.ko-KR.xlf`에 `내 계정`/`내 계정 메뉴`를 추가하고 desktop PWA assertion을 JA/KO로 확장했다. #402336 Step 49 outcome은 aggregate에서 success다. |
| mobile long product breadcrumb | 자동 브라우저 검증 PASS; 시각 재검수 대기 | Hummingbird 모바일 기본은 `nowrap`, `overflow-x:scroll`, 숨긴 scrollbar다. 자식 테마에서 product page의 마지막 crumb에만 wrap을 추가했다. Step 42 E2E는 synthetic long title이 product heading과 일치하고 horizontal overflow가 없는지 검사하며 `mobile-product-detail-breadcrumb.png`를 캡처했다. |
| local focused regression suite | PASS | `test_theme_contract`, `test_storefront_visual_residuals`, `test_pwa_service_worker`, `test_ci_checkout_contract`: 121개 통과. 수정 Python 파일 구문 검사와 `git diff --check` 통과. |
| 최신 Actions | PASS | #40233614104, source SHA `95af3a9104b6e3f7bfc861155bdc73db9a91ab98`; Step 80 실제 aggregate PASS. |
| 현재 환경에서 시각 capture | 미실행; 새 Actions artifact 보유 | Codex system Chromium이 crashpad 초기화에 실패하여 local capture를 생성하지 않았다. 새 격리 browser artifact [ID 12613919270](https://github.com/goldeget/japan-premium-commerce/actions/runs/40233614104/artifacts/12613919270)은 업로드/coverage PASS이며 Work-mode 시각 검수가 남아 있다. |

121개 local target tests도 fresh run에서 통과했다. 자동 브라우저 테스트와 screenshot 생성은 run-scoped 합성 fixture 및 격리 DB에서 이뤄졌다. 운영 DB, named volume, 실배포, 실결제, 실거래, 유료 서비스를 변경하지 않았다. 시각 검수와 실기기 검증은 자동 CI outcome과 구분한다.

## 2026-10-25 — PWA 모바일 계정 검사 수정 및 전체 격리 QA (직전 코드 SHA)

검증 코드 SHA `aed4a3cc6e143258e9f493603dd226bfa41b34aa`; remote `work`도 같은 SHA이며 `main`은 `ee02a3657448d563508687614a246e05ac61eecd`다. 전체 Actions [#40231567083](https://github.com/goldeget/japan-premium-commerce/actions/runs/40231567083)은 workflow `success`, Step 80 실제 aggregate `PASS: isolated browser QA and official postcode verification completed.`로 종료했다.

| 검사 | 결과 | 근거 |
| --- | --- | --- |
| #402294 PWA timeout 원인 | 확인된 테스트 결함 | 모바일 account template에는 숨겨진 sidebar GDPR 링크와 표시되는 main account GDPR 링크가 둘 다 렌더링된다. Selenium의 첫-match visibility wait가 숨겨진 첫 요소만 기다려 `customer_account_route`에서 timeout하고, 진단 경로는 `/<other>`였다. 데스크톱 sidebar는 표시되므로 이전 성공 run의 desktop 및 mobile 결과와 차이가 났다. |
| PWA 검사 수정 | PASS | helper가 GDPR anchor의 표시된 일치 요소들을 검사하고 JA 문구를 확인한다. 숨겨진 sidebar 제목/접근성 label은 desktop에서만 검사한다. 중복 숨김/표시 링크와 mobile skip을 재현하는 unit tests가 포함됐다. |
| PWA 실제 격리 브라우저 | PASS | #402315 Step 49 로그에 `desktop-ja/en/ko`, `mobile-ja/en/ko`가 각각 PASS. 각 경우 secure-context installability, manifest icons, service-worker lifecycle, localized offline navigation, private cache 상태를 확인했다. `PWA_BROWSER_QA_OUTCOME=success`; private Cache-Control 검사와 Step 80 aggregate도 성공했다. |
| 일본어 cart details / account sidebar | PASS (격리 자동 QA) | JA XLIFF에 `Show details`, `Show cart details`, `My Account`, `My account navigation sidebar`를 추가했고 browser/theme assertions를 둔다. #402315 Step 60 checkout 및 Step 49 PWA 성공. 새 캡처의 시각 검수는 아직 대기 중이다. |
| 모바일 checkout/한국어 password 수정 | 자동 QA PASS; 최신 artifact 시각 확인 대기 | 이전 시각 후속 #402294 artifact에서 Work-mode GPT는 390×701의 checkout buttons가 nav 위로 완전히 보이며 KO password label이 `비밀번호`라고 확인했다. #402315에서는 재검수할 캡처를 생성했다. |
| 로컬 영향 테스트 | PASS | `tests.smoke.test_theme_contract`, `test_free_shipping_e2e_contract`, `test_pwa_service_worker`, `test_pwa_logout_diagnostics_contract`, `test_private_customer_cache_routes_contract`: 159개 통과. |
| 전체 격리 QA와 정리 | PASS | #402315 Step 75 screenshot coverage, Step 77 재시작/보존, Steps 78–79 공식 Japan Post 데이터, Step 80 aggregate, Step 83 run 전용 리소스 정리 모두 성공. |
| 최신 캡처 artifact | 저장됨; 시각 검수 대기 | [browser artifact ID 12613108935](https://github.com/goldeget/japan-premium-commerce/actions/runs/40231567083/artifacts/12613108935), 이름 `ordenowa-storefront-browser-40231567083-1`. 이 Codex 세션에서는 ZIP/PNG를 열지 않았다. Work-mode GPT의 후속 시각 검수와 자동 동작 검증을 서로 구분한다. |
| 미해결 화면 후보 | 부분 자료 대기 / 미확정 | `Security/Delivery/Return policy` 문구는 승인된 판매 정책 일본어가 없어 임의로 채우지 않는다. CI 쿠폰명과 `Clothes`/`Art`는 합성/default fixture 값이다. breadcrumb는 CSS 수평 스크롤 요소이며 기존 문서 overflow 검사는 통과해 실제 결함으로 확정하지 않았다. |

모든 자동 검사는 run-scoped 합성 fixture와 격리 DB에서 실행됐다. 운영 DB, named volume, 실결제, 실거래, 실배포는 사용하지 않았다. 이 run은 기술/격리 QA 성공 근거이며 실판매 자료, iOS/Android 실기기, 운영 서버/도메인/메일 또는 법률·세무 승인 완료를 뜻하지 않는다.

## 2026-10-25 — 기존 전체 QA 및 후속 AI 화면 검수 (이전 기준점; #402315 이전)

remote `work`는 `b94d1f0ba3418b5724f07735e7186c2adbcb6555`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`다. 마지막 browser/isolated QA 코드는 `bb26f06168e0a10a50607ce4e5171666656611b1` (`[admin-return-focus] diagnose tokenized return navigation`). 집중 run [#40225474420](https://github.com/goldeget/japan-premium-commerce/actions/runs/40225474420)과 전체 run [#40226037762](https://github.com/goldeget/japan-premium-commerce/actions/runs/40226037762)은 모두 성공했고 Step 80 aggregate는 `PASS: isolated browser QA and official postcode verification completed.`를 기록했다. Work-mode GPT는 전체 artifact [ID 12611855740](https://github.com/goldeget/japan-premium-commerce/actions/runs/40226037762/artifacts/12611855740)를 실제 열어 시각 검수했다. 그 검수에서 확인된 화면 문제에 대한 현재 local source changes는 아직 Actions에서 실행되지 않았다.

| 검사 | 결과 | 근거 |
| --- | --- | --- |
| 로컬 RMA/workflow 계약 | PASS | 관련 계약 149개; Step 8 정확한 사전 검사 142개씩 (security focus false/true); Step 9 43개씩 (false/true). Python compile, workflow YAML parse, embedded shell `bash -n`, `git diff --check` 통과. |
| 실제 경고 화면 | 확인 | tokenless 직접 경로의 classifier 결과 `prestashop_security_compromised`; 정확한 same-origin `/security/compromised` 경로와 `#security-compromised-page` marker가 확인됐고 marker visible=true. tokenless probe 화면 캡처 true. 응답 상태 코드는 성공 요약에 기록되지 않아 별도 주장하지 않는다. |
| 실제 메뉴 이동 | PASS | 앱 생성 메뉴 링크가 same-origin/admin/return path 검사와 세션 `token`/`_token` 검사 통과. tokenized menu route classification `none`; 비교값 `tokenless_compromised_tokenized_clear`. 로그인·라우팅 문제는 앱이 아니라 tokenless 테스트 이동 방식이었다. |
| RMA 대상 및 상태 전환 | PASS | #402254와 #402260 Step 70. 동일 run-scoped 주문/RMA 일치, `1_to_2` 네이티브 저장·새 문서 재조회·success alert 후 state 2, `2_to_1` 저장·재조회 후 state 1, original state restored=true. |
| 전체 regression 범위 | PASS | #402260의 account, product, storefront/cart, PWA/private cache, free-shipping/tax/order, RMA/lifecycle, backup/restore, restart, Japan Post, screenshot coverage 관련 steps가 성공; Step 80 aggregate 성공. Step 74는 비집중 dashboard screenshot 단계라 skipped이며 aggregate 요구사항은 아니다. |
| 기존 title/fon트 변경 | 보존 및 PASS | 상품 화면 Step 42 통과. Chromium font cache Steps 30–32 통과; full run은 archive cache를 복원했다. #40214404446의 실제 HTTP 상태는 여전히 미확인으로 남긴다. |
| 캡처 산출물 | Actions에 저장 | `admin-return-security-compromised.png`, `admin-return-state-control.png`는 Step 73/75 coverage로 검증됐다. Artifact 다운로드 요청이 403을 반환해 파일을 로컬에서 열어보지는 못했다. |
| Work-mode GPT의 기존 artifact 시각 검수 | 완료 (기존 코드 SHA) | 390×701 checkout 뒤로 버튼이 fixed nav에 가려짐, JA checkout 영어 혼합, KO password label의 `Sleutelwoord`, JA `GDPR - Personal data`를 확인. `Clothes`/`Art`는 기본 synthetic category 값, product breadcrumb의 DOM overflow는 미확정이다. 상세와 screenshot 이름은 [AI Browser QA handoff](AI_BROWSER_QA_HANDOFF.md)에 기록했다. |
| targeted 수정 후 browser QA | 실행 대기 | 로컬 CSS/locale/template/E2E assertions를 추가하고 172개 영향 계약 검사와 마지막 9개 Korean login contracts가 통과했다. 현재 수정 SHA로 실행한 Actions 결과는 아직 없다. 변경 push 후 automatic isolated QA artifact로 layout, JA/KO labels, GDPR link를 검증하고 Work-mode GPT가 캡처를 재검수해야 한다. |

운영 DB·named volume·운영 배포·실결제·실거래는 변경하지 않았다. 전체 QA는 격리 run 데이터와 합성 fixtures만 사용했다. 위 PASS는 기술/격리 QA 기준이며 실제 판매자, 실상품, 세무 분류, 운송사 계약, 결제/환불 절차나 운영 호스트의 준비 완료를 의미하지 않는다.

## 이전 실행 — Step 63 제목 오탐 수정 및 RMA 집중 진단 (superseded by the result above)

코드 검증 SHA `9c6c05346bad3afcaa1ac539308393061e44d35f` (`main`은 `ee02a3657448d563508687614a246e05ac61eecd`). 전체 Actions [#40221893987](https://github.com/goldeget/japan-premium-commerce/actions/runs/40221893987)은 **FAIL**이며 Step 80 실제 aggregate의 유일한 실패는 `order_return_admin_browser=failure`다. Step 70의 화면상 초록 conclusion은 `continue-on-error`를 반영하므로 통과로 보지 않았다.

| 검사 | 결과 | 근거 |
| --- | --- | --- |
| Step63 상품 제목 오탐 회귀 | PASS | `6020439`에서 상품 제목의 `404` 부분 문자열 판정을 제거했다. run ID `40214404446`이 들어간 합성 상품명을 로컬에서 재현하고, 대상 상품 식별·상품 화면 요소와 가능한 Document 상태를 확인해 정상 상세 화면과 실제 오류 화면을 분리한다. 이전 run #40214404446의 실제 HTTP 상태는 미기록이므로 unknown이다. |
| 집중 실행 PC·모바일 상품/장바구니 | PASS | #402218 Step67은 데스크톱과 모바일 각각 `Storefront product document response status: 200` 및 home/product/cart/sale-gate/responsive assertions PASS를 기록했다. |
| RMA 선행 및 집중 검사 | 일부 PASS, aggregate FAIL | #402218 Steps 56/58 checkout·주문 저장, 67 storefront gate, 68 CI-only fixture, 69 고객 반품은 success. Step70 실제 process는 exit 1; Step80 `order_return_admin_browser=failure`. |
| RMA 실패 단계 및 안전 증거 | **FAIL at `return_grid`** | Step70의 `last_completed_stage=return_list_navigation`, `failure_stage=return_grid`, `TimeoutException`; 요청 `/admin-kuranea/sell/customer-service/merchandise-return/`, 최종 안전 경로 `/admin-kuranea/<redacted>/<redacted>`, same-origin admin path=true, document status=200, readyState=complete, page class=`other_admin`, visible error=false, login form=false, grid=false. 따라서 예상 목록으로부터 다른 관리자 경로 형태로 이동했으나 실제 route text는 마스킹되어 앱 라우팅과 테스트 경로 중 원인은 확정되지 않았다. |
| RMA 1→2 저장/재조회 및 2→1 복원 | **미실행** | Grid와 대상 RMA가 확인되지 않아 상태 선택·POST·fresh GET·원상복원 단계에 도달하지 않았다. |
| 사전 검사 및 정리 | PASS | 로컬 targeted contracts 91개 통과; 이전에 확인한 Step8 462개 통과/7 skipped, Step9 137개 통과. Actions Steps 8–12 및 Step14 설치 성공, Step75 캡처 범위 검사와 Step83 run-only cleanup도 성공했다. |
| 브라우저 준비 시간 | PASS (cache hit) | #402218 Step32 Chromium 환경 준비 13초. 앞선 cache miss #402144의 Noto CJK setup 약 23분, #402195 Step32 11분 10초는 폰트 다운로드/setup 시간이었으며 앱/RMA 진단 시간과 구분한다. |
| 캡처·진단 산출물 | 보존됨, 시각 열람 미확인 | #402218 storefront browser artifact ID `12610240802`, safe diagnostics artifact ID `12609916454`; 두 아티팩트는 Actions에 저장됐고 이 환경의 artifact 다운로드는 403이었다. RMA 상태 폼 캡처는 RMA 편집 화면에 도달하지 않아 생성되지 않았다. 실패 핵심은 Step Summary 및 annotation에 남았다. |
| 전체 회귀 QA | 실행 안 함 | 집중 aggregate가 실패했으므로 사용자 조건에 따라 전체 QA를 시작하지 않았다. 이전 full run #40209847999는 별도 과거 결과(FAIL)다. |

판정: 제목 오탐은 수정·PC/모바일 브라우저에서 통과했다. 관리자 RMA는 목록 경로 이동 뒤 예상 그리드가 없는 same-origin 200 문서에 도달한 것이 확인됐지만, 경로 마스킹 때문에 원인을 확정할 증거가 부족하다. 근거 없는 route 수정이나 상태 변경 테스트 통과 주장은 없다. 동일 RMA 상태 저장·재조회·복원과 전체 QA는 미검증이며 전체 QA PASS가 아니다.

## 2026-10-25 — RMA 단계 진단 및 제한 집중 QA 결과

Latest diagnostic code SHA is `83d557e5d8c15df098f01d22cf58f4b4fb8e96ad`; `main` remains `ee02a3657448d563508687614a246e05ac61eecd`. This commit splits the admin return list navigation and grid waits, records only safe route classes/origin/path/ready-state booleans, validates the exact allowlisted diagnostic schema, and requires exact host equality for same-origin checks. It does not change application RMA state behavior.

| 검사 | 결과 | 근거 |
| --- | --- | --- |
| Step 8 workflow preflight | PASS | Exact Step 8 command: 133 tests passed with `ORDENOWA_ADMIN_SECURITY_FOCUS=false` and `true`; `ORDENOWA_ADMIN_RETURN_FOCUS` and `ORDENOWA_ADMIN_QA_FOCUS` were also explicitly pinned for each mode. |
| Step 9 workflow preflight | PASS | Exact Step 9 command: 43 tests passed with focus variables explicitly set to false and true. |
| Workflow YAML / Python / diff | PASS | Fresh-install workflow YAML parsed; RMA verifier compiled; `git diff --check` passed. |
| Focused Actions after diagnostics | **FAIL before RMA** | [#40214404446](https://github.com/goldeget/japan-premium-commerce/actions/runs/40214404446), head `83d557e`. Step 52 checkout and Step 54 unpaid-order persistence succeeded; Step 62 checkout restore succeeded. Step 63 actual outcome was `failure` although its continue-on-error step conclusion was `success`; the safe exception text was `CI product detail page did not render` (`AssertionError`). Aggregate annotation: `checkout_gate_after_order=failure order_lifecycle_fixture=skipped order_return_browser=skipped order_return_admin_browser=skipped admin_return_evidence=failure`. Steps 64–66 did not run. Step 71 screenshot coverage and Step 76 aggregate failed; Step 79 run-only cleanup succeeded. |
| Prior focused Actions | **FAIL at admin return list** | [#40213486739](https://github.com/goldeget/japan-premium-commerce/actions/runs/40213486739), head `0665828`. Safe diagnostics: `failure_stage=return_list`, `last_completed_stage=admin_login`, `exception_class=TimeoutException`; target order/RMA and grid evidence were unavailable because navigation/grid shared one stage. |
| Latest full isolated Actions | **FAIL** | [#40209847999](https://github.com/goldeget/japan-premium-commerce/actions/runs/40209847999), head `c3897df`; customer return succeeded, admin return browser and lifecycle gate failed. This predates the diagnostic commit. No full QA was launched after #40214404446 because focused verification did not pass. |
| Artifact / cleanup | Partial | #40214404446 completed run-owned cleanup. The admin RMA verifier was skipped, so no RMA screenshot/diagnostics were produced by that run. Step Summary/annotation contain the safe prerequisite failure and aggregate. |

The RMA application/test cause remains unconfirmed: #402134 could not distinguish route navigation from grid wait, and #402144 did not run the RMA steps. No state transition or restore was verified in this task. The currently observed Step 63 failure is a separate CI prerequisite failure; it was not treated as an RMA defect or silently bypassed. Do not claim focused or full QA PASS.

## 2026-10-25 — 대시보드 경로 수정 후 제한된 최종 전체 QA

코드 검증 SHA `74e64b966d5943a3d06cadd04fe6fc7b17669bfe`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다. 전체 격리 Actions [#40188721058](https://github.com/goldeget/japan-premium-commerce/actions/runs/40188721058)은 **FAIL**이다. 사용자가 제한한 추가 전체 QA 1회를 사용했으며 추가 재실행하지 않는다.

| 검사 | 결과 | 근거 |
| --- | --- | --- |
| 집중 재현 (TDD RED) | 재현 | 새 계약 테스트는 `/admin-kuranea/index.php/sell/dashboard?controller=AdminDashboard`를 이전 분류기가 `other`로 반환하는 것을 확인했다. |
| 대시보드 분류기 수정 | 로컬 집중 검사 PASS, 브라우저 미해결 | 커밋 `74e64b9`는 정확한 `index.php/sell/dashboard` 경로를 추가로 허용하고, 추가 하위 경로 및 다른 origin 거부를 유지했다. `tests.smoke.test_security_runtime_e2e_contract` 36/36 통과. |
| 최종 Dashboard 브라우저 outcome | FAIL | Step39 초록 `conclusion`은 `continue-on-error` 결과다. 실제 로그에는 `login_form_visible=false`, `dashboard_link_count=1`, `current_controller=other`, `stage=view_only_employee_dashboard_route`가 있고, Step69가 `admin_security_browser_qa=failure`로 aggregate했다. 전체 현재 URL 경로는 안전 로그에 기록되지 않아 추가 수정 근거가 부족하다. |
| 브랜드 게시 후 로그인 및 이메일 로고 | PASS | Step32 실제 `BRAND_BROWSER_QA_OUTCOME=success`, Step33 통과. Step69에서도 `brand`와 `reset_email_brand` outcome이 success다. 과거 `admin_login_after_publish` TimeoutException은 재현되지 않았다. |
| 회원·상품·PWA·주문·가격/무료배송 | PASS (격리 QA) | Step34–37, Step41, Steps52–57의 outcome은 성공. 합성 세금/상품, Mailpit, run 전용 미결제 주문만 사용했다. |
| 취소·반품·credit slip | PASS (격리 합성 주문) | Steps51, 60–61을 포함한 `ORDER_LIFECYCLE_OUTCOME=success`. 취소는 미결제 주문이고 반품/credit slip은 합성 paid-like 레코드로 확인했으며 현금 환불은 하지 않았다. |
| CI 복원·캡처·재시작·우편 데이터·cleanup | PASS | Steps62–68 및 Step72의 실제 outcome이 success. DB·PrestaShop 파일·catalog queue 격리 복원, 재시작, PC/모바일 캡처 coverage와 run 전용 정리를 확인했다. |
| Step69 aggregate | FAIL (단일 항목) | 로그의 유일한 실패는 `admin_security_browser_qa=failure`. Step72 cleanup은 성공했다. 따라서 전체 QA는 PASS가 아니다. |
| 브라우저 캡처 artifact | 보존됨 | `ordenowa-storefront-browser-40188721058-1`, ID `12597164472` (15,970,997 bytes); Step64 coverage 통과. [Actions artifacts](https://github.com/goldeget/japan-premium-commerce/actions/runs/40188721058/artifacts/12597164472). 직접 다운로드/시각 점검은 하지 않았다. 진단 artifact `fresh-install-diagnostics-40188721058-1`, ID `12597274231`. |
| 운영 DB·실결제·실배포 | 실행하지 않음 | run-scoped CI database/volumes, 합성 fixtures, Mailpit 및 미결제 주문만 사용했다. |

앞선 전체 QA [#40187411910](https://github.com/goldeget/japan-premium-commerce/actions/runs/40187411910)도 aggregate의 유일한 실패가 `admin_security_browser_qa=failure`였다. 그 실행과 이번 실행 모두 brand 게시·로그인 단계와 Step72 cleanup은 성공했다. 이전 기준 성공 [#40134196682](https://github.com/goldeget/japan-premium-commerce/actions/runs/40134196682)은 보존하되 이번 SHA의 실패를 대체하는 증거로 사용하지 않는다. 이번 작업 범위는 미완료 대시보드 경로 검사에서 종료한다.

## Historical snapshot (2026-10-25 08:21 UTC; superseded)

QA 대상 `work` SHA `b368a6b0a4c39985a13dcb0720683b0a0b5929f4`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다. 독립 수정 커밋은 backup/restore `0392573e0e37008c524872d9f0d73679413aec71`, PWA `77e337e96b0bcd00e72dc0266b291e38dffdbda9`, AdminOrders locale `b368a6b0a4c39985a13dcb0720683b0a0b5929f4`다. 전체 격리 Actions [#40176160072](https://github.com/goldeget/japan-premium-commerce/actions/runs/40176160072)은 이 SHA에서 실행 중이다.

| 검사 | 결과 | 근거 |
| --- | --- | --- |
| 기준 성공 전체 QA #40134196682 | PASS (기준점) | SHA `b99b615`; aggregate와 cleanup 성공. 이를 이후 수정 QA의 대체 근거로 사용하지 않는다. |
| 이전 전체 격리 QA #40173333689 | FAIL (aggregate) | `admin_security_browser_qa=failure backup_restore_drill=failure`; Step39 화면은 HTTP 200/정상 grid인데 영어 Orders heading이었고 Step62 최초 MariaDB restore 생성 실패. Step72 cleanup은 success. |
| 최신 선행 전체 격리 QA #40174672771 | FAIL (aggregate) | SHA `b8eccca`; Step69는 `admin_security_browser_qa=failure pwa_browser_qa=failure backup_restore_drill=failure`. Step72 cleanup은 success. Step conclusion만으로 내부 outcome PASS를 주장하지 않는다. |
| Orders 번역 실패 원인 | 확인됨 | `Admin.Navigation.Menu` 도메인 정규화는 필요했고 b8eccca에서 보완됐다. 그러나 module REQUEST priority 14는 core EmployeeContext priority 7 및 LanguageContext priority 6보다 먼저였다. 영어 view-only 직원의 language가 builder/translator를 이후 다시 덮었다. Response `html lang=ko`는 translator 상태를 증명하지 않았다. |
| Orders locale 수정 | 로컬 격리 회귀 PASS, 브라우저 재검증 대기 | module listener를 `LanguageContextSubscriber::KERNEL_REQUEST_PRIORITY - 1` (5)로 옮겨 core 언어 설정 뒤, LegacyContext priority 0 전에 실행한다. 실제 Symfony dispatcher와 PrestaShop context/translator를 이용한 5개 시나리오가 pass했고 영어 직원 선호도는 유지됐다. `#401761` Step39가 HTTP/browser 결과를 확인한다. |
| PWA controller 실패 원인 | 재현된 harness race, 전체 CI 재검증 대기 | 첫 `/` document ready 직후 locale navigation이 시작됐고 worker registration은 `window.load`에 시작된다. Controlled delay Chromium reproducer에서 navigation 중 activation 이후 document가 uncontrolled로 남으며 기존 검사에서 `controller_timeout`을 냈다. 수정은 locale 이동 전 root controller를 기다리고 이후 locale page의 기존 scope/origin/path 검사도 유지한다. 이전 run에 request-level trace가 없어 historical interleaving을 직접 증명하지는 못했다. |
| Backup/restore 실패 원인 | Compose source로 확인, 격리 restore 재검증 대기 | Compose v2.38.2 `create`는 `--no-deps`를 지원하지 않는다. #401733/#401746 raw stderr는 보존되지 않아 당시 stderr는 알 수 없으나 명령 자체의 unsupported flag가 확인됐다. flag만 제거하고 실제 command contract를 추가했다. |
| 로컬 집중 회귀 검사 | PASS | admin locale Python 37, PWA/logout 106, backup+fresh-install contracts 68, security browser/workflow contract 36. PHP lifecycle regression 5 scenarios와 두 PHP 파일 lint도 통과했다. |
| 수정 후 전체 isolated Actions #40176160072 | 진행 중 | SHA `b368a6b`; image build를 지나 fresh cache probe가 시작됐다. 실제 Step39/41/62 결과, Step69 aggregate, Step72 cleanup은 아직 미완료. |
| SEO Draft PR #3 | 변경 미적용 | PR #3은 2026-10-23 closed/unmerged draft, base는 work의 오래된 SHA이며 conflict 상태. 모든 유효 escaping은 current work에 이미 반영·확장됐고 unique useful changes 없음. SEO source contract 15/15 PASS; rendered hostile-input/browser scope는 이 source test만으로 증명하지 않음. |
| Business-profile module workflow #40174672745 | PASS | SHA `b8eccca`; `module-tests` 성공, failure annotation 없음 (Node/Ubuntu migration notices만 informational). |
| GitHub Actions 전체 격리 QA #40174672771 | 진행 중 | SHA `b8eccca`; install/image build, empty-volume bootstrap, product fixtures and Steps 31–39 have executed; Step41 PWA currently active. Step39/62 actual outcomes, Step69 aggregate and Step72 cleanup are not final yet. |
| #401733 CI backup/restore failure detail | 원인 미확정 | Step62 visible conclusion was green because it is `continue-on-error`; its actual outcome is failure. Sanitized result: MariaDB `compose create --no-deps` exit 1, stdout had no diagnostic, stderr was unclassified, restore resources/services were absent. Raw stderr was intentionally not preserved, so no code change is justified by this evidence alone. |
| #401733 browser artifacts | 보존됨 | `ordenowa-storefront-browser-40173333689-1` ID `12591571549` (16,660,764 bytes) and `fresh-install-diagnostics-40173333689-1` ID `12590948714` (5,111 bytes), metadata not expired; Step64 screenshot coverage passed. |
| #401746 browser evidence | 보존됨 | `ordenowa-storefront-browser-40174672771-1` ID `12592037915` (16,532,674 bytes), `fresh-install-diagnostics-40174672771-1` ID `12591359845` (5,086 bytes); metadata was unexpired at inspection. PC/mobile artifact ZIP was not downloaded/visually inspected. |
| 운영 데이터·배포·결제 | 실행하지 않음 | run 전용 CI DB/volume, synthetic fixture, Mailpit, 미결제 `ps_checkpayment`만 사용한다. |

Step39의 최종 결과는 `.outcome`과 화면 진단을 확인하고, Step69 actual aggregate 및 Step72 정리 결과와 함께 판단한다. Actions 개별 step conclusion은 `continue-on-error` 단계의 내부 QA 결과를 대신하지 않는다.

## 2026-10-24 — PWA trace 원인 수정 및 전체 회귀 재실행

코드 기준 `work`와 `origin/work` SHA **b99b61559978dd8b4c25819623669e0d92deb768**. `main`은 수정하지 않았다.

| 검사 | 결과 | 근거 |
| --- | --- | --- |
| PWA trace 회귀 재현 | RED→GREEN | `test_final_cart_cache_check_keeps_order_url_as_navigation_trace_origin`은 수정 전 초기 trace controller `cart`를 반환해 `order` 기대값에서 실패했고, 최초 order URL을 별도 보존한 뒤 통과했다. redirect 2개, 최종 cart 200/private no-store, 캐시 provenance assertions는 유지했다. |
| PWA 집중/cache route suite | PASS | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.smoke.test_pwa_service_worker tests.smoke.test_pwa_logout_diagnostics_contract tests.smoke.test_private_customer_cache_routes_contract -v`: 101/101. |
| 오프라인 smoke 회귀 | PASS | `tests/smoke/test_storefront.py` 제외 526 PASS, 7 skipped, 실패/오류 0. Docker/PrestaShop/Chromium 런타임 판정은 Actions가 담당한다. |
| 구문 및 diff 검사 | PASS | `python3 -m py_compile tests/e2e/verify_pwa_browser.py tests/smoke/test_pwa_logout_diagnostics_contract.py`, `node --check themes/kuranea/assets/sw.js`, `git diff --check`. |
| 직전 full isolated Actions [#40132927859](https://github.com/goldeget/japan-premium-commerce/actions/runs/40132927859) | FAIL (수정 전 SHA `16f3f3a`) | Step 65 aggregate `pwa_browser_qa=failure`; EN desktop/mobile 모두 `guest_empty_checkout_initial_route; PwaDiagnosticAssertionError`. safe trace에는 `/en/cart` HTTP 200, private/no-store, network source, SW/disk/prefetch cache 미사용이 기록됐다. 원인은 최종 cart cache URL을 trace 최초 URL로 재사용한 E2E harness 결함이었다. Steps 60–64 및 68 cleanup PASS, Step 49 조건부 skip. |
| PC·모바일 캡처 | artifact 보관 | [run #40134196682 artifact](https://github.com/goldeget/japan-premium-commerce/actions/runs/40134196682/artifacts/12576851933)의 `ordenowa-storefront-browser-40134196682-1` (15,618,931 bytes), Step 61 coverage PASS, metadata상 미만료. ZIP 본문은 실행환경 프록시가 파일 저장소 연결을 403으로 거부해 직접 확인하지 못했다. |
| 수정 SHA 전체 isolated Actions [#40134196682](https://github.com/goldeget/japan-premium-commerce/actions/runs/40134196682) | PASS | SHA `b99b61559978dd8b4c25819623669e0d92deb768`; run conclusion `success`, Step 65 aggregate PASS, failed/cancelled step 없음. 회원/로그아웃 Step 34, PWA lifecycle/privacy-cache Step 41, Tokyo/Osaka 무료배송·과세/면세·DB/관리자 금액 대조 Steps 52–57, 재시작·일본우편 데이터 Steps 62–64가 통과했다. Step 49 조건부 skip, Step 66 진단은 실패가 없어 skip, Step 68 run 전용 자원 정리 PASS. |

회원 QA의 check-run에는 한국어 로그아웃 trace 10개가 있다. Account-page/menu에서 선택한 same-origin `/ko/?mylogout` 링크가 실제 문서 요청과 일치했다. 응답은 두 번의 HTTP 302 후 로그인 페이지 HTTP 200이었고 두 redirect의 `Location`은 이어진 요청과 일치했다. Worker가 우회 전 브라우저를 제어했으며 네트워크 전용 비교 중 bypass가 켜졌고 30개 요청/redirect 응답이 모두 `from_service_worker=false`였다. 이 후속 증거에서는 404가 재현되지 않았다.

직전 full run에서 고객 계정 가입/로그인/로그아웃 Step 34는 통과했고 재현된 PWA 실패는 로그아웃 404가 아니라 빈 체크아웃 trace 생성 단계에서 발생했다. `b99b615`는 cache policy 확인에 사용할 최종 URL과 navigation trace에 사용할 최초 URL을 분리했다. 후속 full run은 성공했고 Step 34와 Step 41을 통과했으며 원래 HTTP 404는 재현되지 않았다. 다만 #40036387808의 원 요청/리다이렉트 및 service worker 경로는 artifact 본문에 접근하지 못해 확정하지 못했다. 실기기 PWA 설치 및 실제 운영 자료 검증은 별도다.

이전 CI의 배송·세금·주문 성공 범위와 그 합성 데이터 한계는 아래 2026-10-23 표 및 `DEVELOPMENT_STATUS.md`의 최신 출시 준비 표를 함께 참조한다. 실제 상품, seller tax mapping, carrier 운영 설정 및 실결제 결과로 확대 해석하지 않는다.

## 이전 출시 가격 정책 격리 QA 스냅샷 (2026-10-23 23:06 UTC)

기준 `work` 및 `origin/work` SHA `c60a851e114ff00f6e4d8c8c708ad3016bc980bd`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지한다.

| 검사 | 결과 | 근거 |
| --- | --- | --- |
| Focused checkout/free-shipping 계약 | PASS (로컬 정적 QA) | 최신 CI 이메일 길이 회귀 수정 후 77개 계약 통과. |
| Pricing/tax focused suite | PASS (로컬 정적 QA) | 무료배송·세금 집중 83개 테스트 통과. Python 구문 및 `git diff --check` 통과. |
| 격리 fresh-install Actions [#40036387808](https://github.com/goldeget/japan-premium-commerce/actions/runs/40036387808) | FAIL (aggregate) | SHA `c60a851`. Step 65가 보고한 유일한 실패는 `pwa_browser_qa=failure`이며 desktop logout 후 로그인 폼 대신 HTTP 404 경로에 도달했다. 가격 검증 Steps 52–57은 모두 통과했다. |
| 브라우저 가격 및 무료배송 QA | PASS (격리 Chromium) | Tokyo PC 수량 2+쿠폰, Osaka 모바일 수량 1, 합성 과세 상품, 명시적 0% QA 상품에서 배송비 ¥0 확인. 상품 상세·장바구니·체크아웃·주문 확인·주문내역 금액 일치. |
| 저장 주문 및 관리자 합계 | PASS (격리 DB/별도 관리자 브라우저) | Step 56에서 네이티브 미결제 주문의 JPY 상품·세금·배송·할인·총액을 확인했고, Step 57에서 별도 관리자 세션의 주문 금액을 확인했다. 저장 배송비 ¥0, 설명되지 않는 플랫폼 수수료 없음. |
| CI 복구·캡처·재시작·주소 데이터 | PASS | 체크아웃 fail-closed 복구와 재확인(Steps 58–59), PC·모바일 screenshot coverage(Steps 60–61), 재시작 지속성(Step 62), Japan Post import/verify(Steps 63–64), 격리 리소스 정리(Step 68). |
| 운영 DB·실결제·운영 배포 | 실행하지 않음 | run 전용 Compose 프로젝트·DB·volume과 `ps_checkpayment` 미결제 주문만 사용했다. |

배송 fixture는 47개 지원 도도부현을 무료배송 구역에 구성했지만 실제 브라우저 주문은 Tokyo와 Osaka 표본만 포함한다. 모든 지역·수량·쿠폰 조합의 주문 QA는 아니다. 과세 fixture의 10%와 명시적 0% 규칙은 격리 테스트 데이터다. 일본 법정 세율, 판매자 세무 상태 또는 실제 상품의 과세·면세 적법성을 검증하지 않으며, 운영 상품의 세금은 판매자·상품별 적법한 규칙으로 별도 확인해야 한다.

전체 workflow aggregate는 PWA logout 후 로그인 리다이렉트가 HTTP 404가 된 문제로 실패했다. 이 결과는 전체 QA PASS를 뜻하지 않지만 가격·배송·주문 저장·관리자 금액 단계는 모두 통과했다. 운영 배송 설정과 named volume은 변경하지 않았고 실결제 및 운영 배포도 하지 않았다.

## 이전 검증 현황 (2026-10-23 02:26 UTC; 당시 결과)

최신 기능 및 full Chromium 검증 `work` SHA: `dfa30a1127a50d2eb4926d7c1fb6d75030a64121`. `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다.

| 검사 | 결과 | 근거 |
| --- | --- | --- |
| 계정 재설정 로그인 회귀 | PASS (로컬 계약·Chromium) | #39888370630은 이전 비밀번호 거부 뒤 남은 오류 알림 때문에 새 비밀번호 로그인도 거부된 것으로 오판했다. `dfa30a1`은 검증된 로그인 URL을 다시 열고 이메일 입력과 오류 알림 부재를 확인한 뒤 제출한다. 집중 계약 RED→GREEN, 계정 계약 22개 통과, #39889443441 Step 30 및 aggregate PASS. |
| 전체 오프라인 테스트 | PASS (서비스 의존 제외) | `PYTHONDONTWRITEBYTECODE=1 python3 -c ...`로 `tests/smoke/test_storefront.py`만 제외하고 304 tests 통과. HTTP 서버에 의존하는 해당 storefront 테스트는 Cloud에서 실행하지 않았다. |
| Python 구문·diff | PASS | `python3 -m py_compile tests/e2e/verify_customer_account_browser.py`, `git diff --check` 통과. |
| 공식 브랜드 ZIP | PASS (무결성/소스 계약) | ZIP 22개 항목 CRC, 원본 3종·파생 17종의 SHA-256/저장 경로, KURANEA 백업 보존 계약을 확인했다. |
| Browser: 브랜드·메일 로고 | PASS (격리 CI 단계) | #39888149608 Steps 28–29 및 #39889264268/#39889443441 Steps 28–29 성공. #398892와 #398894 Step 28에는 EN storefront SEO/PWA/이미지 검사가 포함된다. 두 run의 Step 41 필수 screenshot artifact gate도 통과했다. |
| Browser: 회원 계정 | PASS (격리 CI 단계) | #39888149608, #39889264268, #39889443441 Step 30 및 전체 aggregate 성공. #39888370630에서 old-password rejection 알림이 새 로그인 결과로 오인됐고, `dfa30a1` clean-login reload 수정은 #39889443441에서 검증됐다. |
| Browser: 관리자 상품·상점 주문 | PASS (격리 CI 단계) | #39888149608, #39889264268, #39889443441 Steps 31–39에서 관리자 상품 create/edit, synthetic 상품 검색·장바구니, PC·모바일 일본 주소 무결제 주문, 관리자 조회 및 checkout fail-closed 복구 성공. Steps 42–44도 #39889443441에서 통과했다. |
| Actions #39889443441 (`dfa30a1`) | PASS | 전체 isolated fresh-install 성공. Steps 28–30 브랜드·메일·계정, 31–39 상품·장바구니·무결제 주문, 40–41 캡처/coverage, 42 재시작, 43–44 Japan Post, 45 aggregate 성공. Step 35는 조건부 skip. |
| Actions #39889264268 (`021214d`) | PASS | 전체 isolated fresh-install 성공. 영문 브랜드와 필수 캡처 gate 포함. 계정·상품·무결제 주문·관리자 조회·재시작·주소 및 aggregate 성공. Step 35는 조건부 skip. |
| Actions #39889264241 (`021214d`) | PASS (범위 제한) | Offline parser workflow; full install/browser QA를 대체하지 않는다. |
| Actions #39888370630 (`49bad87`) | FAIL | Raw aggregate `Failed steps: account=failure`. Annotation은 desktop reset-login submit에서 `AssertionError`, 이후 상태는 `/ko/` authenticated/user menu visible이며 login form/danger alert 없음으로 기록했다. Brand, product, unpaid order, restart 및 Japan Post 단계는 성공했다. Step 41은 진단 fallback만 실행해 전체 screenshot coverage를 인증하지 않았다. |
| Actions #39888149608 (`60a82f3`) | PASS | 전체 isolated fresh-install workflow 성공. Brand/email, account reset, product create/edit, unpaid order/admin view, full screenshot coverage, restart, Japan Post import/count 모두 통과; Step 35는 조건부 skip. |
| Actions #39881329928 (`f6dd110`) | FAIL (이력) | 이전 진단 run은 완료 실패했으며 현재 최신 판정이 아니다. |
| Actions #39881329855 (`f6dd110`) | PASS (범위 제한, 이력) | Offline parser workflow; full install/browser QA를 대체하지 않는다. |
| Actions #39879191400 (`9525b37`) | FAIL | Raw aggregate `Failed steps: account=failure`; PC·모바일 모두 `/identity`에서 visible invalid checkbox `name=psgdpr`. Browser product/order/postal groups had no failure annotation. |
| Actions #39879191441 (`9525b37`) | PASS (범위 제한) | Offline catalog parser workflow; full install/browser QA를 대체하지 않는다. |
| 운영 배포·실결제 | 실행하지 않음 | 한국어 관리자 등록 상품 fixture는 비활성이고 checkout은 별도의 활성 synthetic CI 상품과 `ps_checkpayment` 무결제 경로를 사용했다. Production과 실거래는 활성화하지 않았다. |

## 이전 이어가기 결과 (`work` SHA `5b2a1cb8d2193458a088174eb04228f252cd9e0e`)

| 검사 | 결과 | 근거 |
| --- | --- | --- |
| 관리자 운영 설정 모듈 Actions | PASS | run `39757526475` 성공. PHP 8.3 lint, profile lifecycle, Korean admin form, brand-derivative contracts, published customer/PWA output, localized legal page, seller gate, email hooks, PrestaShop module wiring을 검사했다. 이는 실제 관리자 브라우저 E2E는 아니다. |
| 로컬 Python business-profile 계약 | PASS | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/business_profile -p 'test_*.py' -v`: 10/10. |
| 로컬 관리자 언어 계약 | PASS | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/admin_locale -p 'test_*.py' -v`: 13/13. |
| 신규 설치 workflow 계약 | PASS | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.smoke.test_fresh_install_workflow_contract -v`: 12/12. |
| 셸·YAML·공백 정적 검사 | PASS | `bash -n docker/kuranea-entrypoint.sh`, Compose/두 workflow YAML 파싱, `git diff --check` 통과. |
| 카탈로그 parser Actions | PASS (synthetic fixtures) | run [39760154509](https://github.com/goldeget/japan-premium-commerce/actions/runs/39760154509) on SHA `5b2a1cb` completed successfully, including PHP 8.3 lint and synthetic Amazon Japan/Rakuten tests. It does not prove external collection or PrestaShop native product registration. |
| 카탈로그 CI 실패 원인·수정 | 수정 후 PASS | 이전 run `39759208949` failed because its admin assertion forbade `amazon_jp` across the entire HTML even though the deduplication key intentionally includes it. The assertion now checks the image-metadata block separately; the production parser was unchanged. Failure output is bounded and annotation-escaped. |
| 격리 신규 설치 | FAIL / Japan Post HTTP 503 | run [39760154414](https://github.com/goldeget/japan-premium-commerce/actions/runs/39760154414) on SHA `5b2a1cb` failed at official KEN_ALL download with `curl_exit=22 http_status=503 effective_host=www.post.japanpost.jp`, even though the updater already uses `curl --retry 3 --retry-delay 2`. Image build/cache probe and prior startup/catalog steps passed; address lookup, native address/order persistence, admin order view and final restart smoke were skipped. The preceding completed run `39759208769` reported the same external failure. |
| 실제 상품·주문 E2E | 미검증 | 이 작업에서 TEST/DEMO 상품을 네이티브 PrestaShop DB에 등록하거나 고객 주문을 만들지 않았다. Japan Post 실패로 최신 설치 run의 후속 주소·주문 단계도 실행되지 않았다. |
| ORDENOWA 공식 이미지 | BLOCKED | 대화 미리보기 외 원본 바이트를 가져올 수 없었다. `download_file`은 첨부 staging 오류로 실패했고 로컬에는 KURANEA 원본만 확인됐다. 새 로고나 아이콘을 만들거나 적용하지 않았다. |
| 실제 DB/브라우저/PWA 설치 | 미검증 | 이 turn에서는 운영 DB/컨테이너를 실행하거나 수정하지 않았고 새 상품·주문·고객 row 및 스크린샷을 만들지 않았다. `/workspace` 작업트리, 기존 볼륨, `main`을 보존했다. |
| 코드 체크포인트·복구 확인 | PASS | parser/CI 코드 체크포인트 `5b2a1cb8d2193458a088174eb04228f252cd9e0e`를 `work` 원격에서 확인했고 별도 shallow clone에서 같은 SHA 및 수정 파일을 재조회했다. 문서 후속 체크포인트는 별도 commit이다. `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지됐다. |
| cloud environment 적용 상태 | 확인됨, revision 3 미적용 | 현재 관측 revision 2이며 저장 draft revision 4는 이전 repository SHA `2db98927a9ede2b2423456873f0994ddd19ffe4e`를 참조한다. draft/활성 설정을 변경하거나 게시하지 않았다. |

아래 표는 선행 Phase 1A 작업의 증거·제약을 보존한 기록이며, 위 현재 결과로 덮어쓰지 않는다.

## 선행 로컬 실행 기록

| 검사 | 결과 | 근거 |
| --- | --- | --- |
| PrestaShop 관리자 경로 설치 순서 회귀 계약 | PASS (정적/계약) | `tests/smoke/test_admin_folder_install_order.py` 구현 전 3건 실패를 재현하고 수정 후 3/3 통과했다. Compose가 공식 `/admin`을 첫 설치 동안 유지하고 post-install이 감지된 관리자 폴더를 이동한 뒤 최종 경로 자산을 설치하는지 검사한다. 실제 빈 DB 설치는 별도 CI 결과가 필요하다. |
| 관리자 경로 후속 후보 계약 | PASS (정적/계약) | 수정된 후보의 `PS_FOLDER_ADMIN=admin-dev`, CLI 이후 PHP bootstrap 순서, 최종 `admin-kuranea`/`admin-dev` 부재 검사를 4/4 통과했다. 이 검사는 실제 신규 설치를 대체하지 않는다. |
| 관련 workflow 계약·설정·문법 | PASS | 관리자 경로 회귀 및 기존 fresh-install workflow 계약 합계 10/10, PHP lint, shell syntax, `docker compose config --quiet`, `git diff --check` 통과. |
| Python smoke 및 CI 계약 테스트 | 부분 실패 | 2026-10-22 최근 실행은 38건 중 35건 통과, 3건 오류다. 세 오류는 빈 카테고리 ja/en/ko 경로가 리다이렉트 후 HTTP 500을 반환한 기존 로컬 storefront 동작이다 (`Category.php`/`CategoryController.php`에서 DB 조회 결과 `false`에 대한 foreach 경고). 나머지 smoke 검사는 통과했다. 이 환경의 DB를 변경하지 않았으며 원인은 별도 조사 대상이다. |
| 관리자 번역 계약 테스트 | PASS | 2026-10-22 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/admin_locale -p 'test_*.py' -v`: 8/8. 전체 Back Office 번역 커버리지 검증은 아니다. |
| Japan Post 데이터 갱신 CLI 계약 테스트 | PASS | 2026-10-22 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/postcode -p 'test_*.py' -v`: 6/6. 공식 URL, TLS 리다이렉트 제한, ZIP/CSV 검증, 실패 시 importer 미호출, 임시 파일 제거를 stubs로 확인했다. 실제 다운로드/import는 실행하지 않았다. |
| 우편번호 도메인·주소 검증 테스트 | PASS | 호스트에 PHP CLI가 없어 기존 PrestaShop 컨테이너의 임시 `/tmp` 경로에 테스트 소스만 복사해 실행했다. 정규화, 후보 검색, 복수 후보, 주소 일치/불일치, 건물 입력 및 수동 fallback 통과. 영구 프로젝트 파일/DB 변경 없음. |
| 우편번호 후보 API 단위 테스트 | PASS | 격리 테스트 더블에서 JSON 후보 및 `manual_entry_available` 응답 확인 |
| 공식 Japan Post KEN_ALL 데이터 및 DB API | PASS (기존 dev DB) | 공식 ZIP SHA-256 `c976cb0ff691a1aa7480b47b7e1f61bea08c2eadb3278f0366e474cd82dbf4b8`; CSV 124,840행 파싱, 고유 후보 124,839건 DB에 적재. HTTP에서 `1000004`/`100-0004`, 일본어 검색, `004-0000` 후보 2개 확인. 활성 주소 124,839행, staging 0행. |
| 주소 자동완성 브라우저 동작 | PASS (주소 폼 fixture) | 실제 사이트 origin의 모듈 JS와 DB API를 사용해 1440px·390px에서 우편번호 후보 적용, 일본어 검색, 중복 후보 선택, 건물명 편집 보존을 확인했다. JS page error 0건. 캡처 `artifacts/qa/phase1a/postcode-widget-desktop.png`, `postcode-widget-mobile.png`. 실제 checkout 경로가 아니므로 checkout 검증 PASS가 아니다. |
| 실제 Japan Post API 및 서버 주소 검증 | PASS (읽기 전용) | 기존 dev DB의 공식 `1000004` 행을 새 모듈 소스로 검증했다. 입력 주소 `address1=大手町`, 1000004/100-0004, 저장 전 시구정촌 불일치 거부, 선택 주소/건물 입력 허용, 후보 미존재 시 수동 입력을 확인했다. 테스트 고객/주소/주문은 생성하지 않았다. |
| Japan Post 후보 응답 town 정규화 | PASS | PHP controller fixture의 원본 town `テスト町（次のビルを除く）`가 API 응답 `テスト町`으로 직렬화되는 것을 확인했다. GitHub Actions에서도 실제 `1000004` 응답 town을 `大手町`와 정확히 비교하도록 했다. |
| 실제 Japan Post HTTP 후보 API | PASS (기존 dev DB, 읽기 전용; 기존 런타임 소스) | 기존 API에서 `1000004`와 `100-0004`, `千代田区大手町`, 중복 `004-0000` 2건, 미일치 검색 0건 및 `manual_entry_available=true`를 확인했다. 이 API 캡처는 수정 전 런타임이므로 접미어 제거 검증은 새 PHP 소스의 controller fixture와 read-only 통합 검사로 별도 확인했다. |
| 공식 Japan Post 갱신 CLI | 구현·계약 테스트 PASS, 실제 download/import 미실행 | `modules/kuraneapostcode/bin/update-ken-all.sh`는 Japan Post 공식 HTTPS ZIP을 검증한 다음 기존 트랜잭션 importer를 호출한다. 신규 6개 테스트는 fake curl/unzip/php만 사용했다. 기존 dev 주소 DB를 다시 쓰지 않았다. |
| 우편번호 주문 검증 스크립트 | PASS (문법·가드만) | `tests/postcode/verify_native_order_persistence.php`를 기존 컨테이너에 임시 복사해 `php -l` 통과. 주문 검증은 실행하지 않았고 활성 DB 주문 수는 0건 그대로다. |
| 관리자 대시보드 및 주문 목록 브라우저 | 부분 PASS | 한국어 관리자 로그인 뒤 주문 목록 메뉴 링크에서 PC 1440×1000·모바일 390×844 HTTP 200, 제목/메뉴/본문 한국어, JavaScript 오류 0건을 확인했다. 실제 주문이 0건이라 배송지 주문 행은 미검증이다. 캡처 `artifacts/qa/phase1a/admin-orders-list-korean-desktop-qa.png`, `admin-orders-list-korean-mobile-qa.png`. 전체 관리자 100%는 아니다. |
| 우편번호 모듈 PHP 문법 검사 | PASS | 모듈 및 우편번호 테스트 PHP 파일 전체 lint |
| 셸/JavaScript/Compose 문법 | PASS | `bash -n`, `node --check`, `docker compose config --quiet` |
| 변경사항 공백 검사 | PASS | `git diff --check` |
| CI 진단 마스킹·워크플로우 계약 | PASS | smoke 34/34. 분리된 설치 단계, 실패 진단, 민감값 마스킹, 공식 주소 importer, 격리 주문 검증 가드를 포함한다. |
| 컨테이너 상태 | 부분 실패 | 마지막 관찰에서 PrestaShop은 healthy였으나 MariaDB healthcheck는 unhealthy였다. 기존 서비스 재시작이나 DB 조작은 하지 않았다. |
| JPY DB 설정 | PASS | DB 읽기 전용 조회에서 JPY 활성·0자리·기본값, ja/en/ko 통화명 확인; EUR/USD 비활성 |
| 기존 DB 재시작 보존 | PASS | 기존 MariaDB/PrestaShop 컨테이너를 재시작한 뒤 HTTP 200, 양쪽 healthy, JPY 기본값과 3개 언어 행을 읽기 전용 확인 |
| 로컬 DB 상품/주문 현황 | PASS | 읽기 전용 조회 결과 상품 0건, 주문 0건 |
| 빈 카탈로그·검색·푸터 다국어 화면 | PASS | 홈/카테고리/검색/푸터를 실제 PrestaShop+Chromium에서 ja/en/ko로 확인했다. 검색/카테고리 HTTP 200, 홈에서 320–1920px 10개 폭 가로 넘침 없음, PC·모바일 캡처를 `artifacts/qa/phase1a/`에 저장했다. 현재 상품이 없어 카드·상세 상태의 실제 상품 렌더링은 검증할 수 없다. |

## 선행 제한 또는 실패 기록

| 검사 | 결과 | 상세 |
| --- | --- | --- |
| P0 신규 설치 부팅 오류 | 부팅 경로 복구, 전체 QA FAIL | run `39732730236`에서 이미지 빌드, 캐시 권한 probe, 빈 볼륨 Compose 기동 및 공식 CSV 가져오기가 성공해 이전 `/install` 중복 삭제로 인한 시작 중단은 재현되지 않았다. API 조회와 네이티브 주소 저장을 묶은 검증 단계는 exit 255로 실패했고 이후 주문·관리자·재시작 검증은 건너뛰었다. 해당 실행의 PHP 예외 상세는 현 공개 실행 페이지에서 읽을 수 없어 세부 실패 원인은 아직 미확정이다. 다음 실행에서 API 조회와 주소 저장을 분리하고 PHP 검증기가 단계별 오류 annotation을 출력하도록 보강했다. 따라서 전체 신규 설치/주소 주문 QA는 아직 PASS가 아니다. |
| 과거 신규 빈 볼륨 설치 | FAIL (이전 코드) | runs `39703327857`, `39704824787`, `39705702536`, `39706052890`, `39706126218`은 이전 코드에서 실패했다. 최신 사용자가 제공한 상세 로그에서 `assets:install admin-dev`가 부재한 `/var/www/html/admin-dev`를 대상으로 한 직접 원인을 확인했다. 이번 원인은 errno 28로 기록하지 않는다. |
| 오프라인 Amazon Japan·Rakuten parser | 선행 기록 기준 대기 | 이 선행 결과 표 작성 당시에는 synthetic fixture 기반 PHP 파서 Actions 실행을 기다렸다. 이후 구현·검수 모듈 결과는 위 최신 실행 표의 run `39760154509` 및 현황 문서를 참조한다. 실제 외부 수집과 PrestaShop 네이티브 상품 등록은 여전히 검증되지 않았다. |
| Amazon Japan·Rakuten 원본 페이지 접근 | BLOCKED | 2026-10-22 읽기 전용 HTTPS 요청 모두 egress proxy CONNECT `403`을 반환했다. 접근통제를 우회하지 않았고 페이지를 수집·파싱하지 않았다. |
| 신규 설치 DB 적재 및 API lookup | import PASS, lookup/address save 판정 대기 | run `39732730236`은 공식 Japan Post CSV import 단계까지 성공했다. 이어진 lookup+native address 단계가 exit 255로 실패해 해당 단계의 조회 결과를 분리해 판정할 수 없었다. 다음 실행은 두 작업을 독립 step으로 나눈다. |
| checkout 주문 연결 및 관리자 배송지 | 미실행 | 무결제 네이티브 Order 생성, `id_address_delivery` 연결, PrestaShop 관리자 조회 주소 formatter를 검사하는 CI 전용 스크립트를 추가·원격 저장했고 PHP 문법 및 격리 가드만 확인했다. 실제 검증은 새 빈 설치 CI가 먼저 통과해야 한다. 브라우저 checkout 경로는 아직 주소 폼 fixture만 검증했다. |
| PC/모바일 browser regression | 부분 PASS | 홈 빈 카탈로그 안내는 PC 1440px·모바일 390px에서 실제 렌더링했다. 화면별 증거는 위 캡처를 참조한다. 전체 반응형 폭 테스트와 상품 상세·주문 화면은 별도 미완료다. |
| 관리자 한국어 100% | 미완료 | 로그인과 대시보드에서 한국어 메뉴·날짜 범위를 실제 브라우저로 확인했다. 모듈 계약 테스트는 8/8이지만 전체 메뉴, 모든 설정·주문관리·모듈 화면은 아직 범위별 audit을 하지 않았다. |
| PWA 기기 설치 | 미실행 | manifest/service worker 정적 검증은 있지만 iOS/Android 홈 화면 설치 테스트는 없다. |
| Docker 신규 설치/재빌드 | 차단 | `/workspace` overlay 여유 블록 0 bytes, inode 사용률 100%(약 7천 개 여유). Docker 이미지/캐시/volume 사용량은 조사했다. 신규 컨테이너 생성과 컨테이너 exec가 공간/runtime 오류로 실패해 로컬 설치는 실행하지 않았다. 기존 데이터와 모든 볼륨을 보존하고 prune·재빌드·재시작은 하지 않았다. |
| Cloud config revision 3 | 미적용·draft 갱신 대기 | 활성 status는 revision 2/observed 2, 저장 draft revision 4는 이전 SHA `2db9892`다. 코드 체크포인트를 최신화한 뒤 저장 draft를 현재 `work` SHA로 갱신하고 Actions API 및 필요한 공식 주소 호스트를 추가해 사용자 검토용으로 저장할 계획이다. 저장·게시 후 적용은 별도로 확인해야 한다. |

새 기능의 최종 PASS는 반드시 실제 격리 환경 및 해당 기능의 end-to-end 검증으로 기록한다.
