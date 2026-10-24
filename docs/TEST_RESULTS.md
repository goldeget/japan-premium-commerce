# ORDENOWA 테스트 결과

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
