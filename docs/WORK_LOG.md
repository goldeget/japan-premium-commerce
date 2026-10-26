# ORDENOWA 작업 기록

## 2026-10-26 — CI 사전 검사 수정 및 격리 전체 QA 결과

- 시작 시 `work` HEAD `eefb19382beaeb08ac6d6f64199da3ae76a17e1f`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`. #40315042151 Step 6이 `kuraneapush`를 포함하지 않는 오래된 설치 순서 계약으로 실패했다. `tests/smoke/test_admin_folder_install_order.py`를 실제 모듈 설치 목록에 맞췄고 commit `19ceed329bdfd2cd47d06979ffca22598a9076d3`을 work에 푸시했다.
- #40315327770 Step 9는 `test_shipping_admin_links_contract.py`가 workflow가 이미 바꾼 `grep` 대신 `rg` 문자열을 기대해 실패했다. 안전한 stage/detail 검사와 원래 browser outcome을 보존하면서 기대 문자열만 고치고 commit `acbdc5e78cb8a499a3885fe6dbcdc3ebf539cdcd`를 푸시했다. 이 두 run은 browser/install UI 검증을 수행하지 않았다.
- 좁은 suite 17개, Step 9 exact suite는 focus false/true 각각 147개, cart/shipping/account/PWA 영향 suite 86개 PASS. 전체/브라우저 검증으로 계산하지 않는다.
- QA-CI-002 수정은 `acbdc5e`에서 계약 assertion 한 줄만 `rg`에서 workflow가 실제 쓰는 `grep`으로 맞췄다. Workflow의 stage/detail 추출, 마지막 진단 줄 선택, 원래 browser exit/outcome 판정은 그대로다. 관련 계약 8개를 로컬에서 실행해 통과했고, #40315517530 Step 9도 성공했다.
- source `acbdc5e` 전체 격리 실행 [#40315517530](https://github.com/goldeget/japan-premium-commerce/actions/runs/40315517530)은 completed **FAILURE**다. Preflight, image build, empty-volume 설치와 이후 account/cart/product/catalog/category/carrier/checkout/order/backup/postcode 검사가 진행됐다. 실제 aggregate 실패는 `pwa_browser_qa=failure pwa_push_qa=skipped`다. PWA desktop JA/EN 로그아웃 클릭은 interception, mobile JA/EN/KO 동의 단계는 timeout, desktop KO lifecycle은 통과했다. continue-on-error의 표시를 실제 outcome으로 간주하지 않는다.
- Browser artifact [12646464536](https://github.com/goldeget/japan-premium-commerce/actions/runs/40315517530/artifacts/12646464536), 진단 artifact [12647935305](https://github.com/goldeget/japan-premium-commerce/actions/runs/40315517530/artifacts/12647935305). 이 실행은 QA-CI-002 preflight 차단을 재현하지 않았으며 전체 QA 성공도 아니다.
- `main`은 수정하지 않았고 사용자 미추적 파일·작업 plan/spec·pycache도 stage하거나 삭제하지 않았다. 카트와 carrier는 이번 source에서 브라우저 저장/재조회를 통과했다. PWA 실패 원인과 push persistence는 아직 열려 있다. LOCALE-003의 neutral helper 자동 assertion은 account flow에서 실행됐지만 새 캡처의 독립 시각 검수는 별도다.

## 2026-10-26 — cart/carrier 검증 보완 및 PWA foundation checkpoint

- 시작 원격 `work` SHA `a890c83f04b81240b07a338f9ed734f0a25caf78`, `main` `ee02a3657448d563508687614a246e05ac61eecd`; 원격 조회에서 진행 중 Actions는 없었다. 로컬 `work`에는 먼저 문서 checkpoint `fa2574e`, 이어 두 변경 commit `ec7ef6b`와 `50d924f`가 있다. 아직 push하지 않았고 사용자 미추적 파일은 stage하지 않았다.
- QA finding: #40310232196 source a890c83의 actual aggregate 실패는 mobile cart add-button readiness `StaleElementReferenceException`과 `shipping_free_admin_configure` saved carrier `TimeoutException` 두 개다. Customer account/address outcome은 success; downstream shipping skips는 독립 실패가 아니다. 기존 주소 timeout은 재현되지 않아 원인 미확정으로 유지한다.
- Cart polling은 매회 버튼을 새로 찾고 visibility/enabled read에서 발생한 stale exception만 다시 대기한다. 20초 wait·native click·상품/옵션/수량 assertions는 그대로다. Carrier readback에는 허용 stage와 redacted same-ID/name/free/zone/readiness facts를 추가했다. 새 run 전에는 실제 timeout predicate를 해결했다고 주장하지 않는다.
- CI failure extraction 3구간은 ripgrep 의존성을 제거했고 PATH에 `rg`가 없는 test subprocess가 원래 exit 7, summary 및 carrier annotation을 보존하는지 확인한다.
- 주소 edit helper는 add/edit 양쪽에 자연스러운 중립 copy `계정에 사용할 주소 정보를 입력해 주세요.`로 바꿨다. 이전 artifact에서 한국어를 보인다는 이유만으로 edit-context QA 완료로 두지 않는다.
- PWA-002 code commit `50d924f`는 별도 `kuraneapush` module, explicit consent/owner-scoped encrypted API, Korean admin config, provider를 호출하지 않는 synthetic API/worker checks를 추가했다. Review는 source 수준 blocker를 찾지 않았지만 production privacy audit에는 consent version/hash, accepted timestamp, retention/erase policy가 빠져 있다. Push sender, VAPID key, approved consent text, support producer는 scope/readiness 대기다.
- 로컬 검증: Step 8 578 OK (7 PHP CLI skips); focus false/true Step 9 각 36 OK; cart/shipping/account contracts 117 OK; PWA/worker/backend contracts 84 OK; Node 12 OK. GitHub Actions가 PHP lint/behavior, PrestaShop/MariaDB install, Chromium/PWA render/runtime과 전체 aggregate를 검증해야 한다. 이 시점에는 Actions run/artifact가 없다.
- 다음 handoff는 푸시 후 새 source SHA/aggregate를 확인하고 `shipping-free-carrier-configure-failure.png`, cart failure/ready evidence, `mobile-customer-address-edit-form.png`, six locale/device PWA push consent screenshots와 two-owner synthetic screenshots를 독립 시각 검수한다. Artifact가 만들어지기 전 파일명은 의도된 evidence coverage이며 존재/검증 주장으로 쓰지 않는다.

## 2026-10-26 — 주소 문구 검증 완료 및 전체 QA 결과

- 최신 source/work `a890c83f04b81240b07a338f9ed734f0a25caf78`, `main` `ee02a3657448d563508687614a246e05ac61eecd` 보존. Full isolated QA #40310232196 completed FAILURE. Account/address browser outcome success; aggregate의 실제 실패는 mobile cart `product_add_add_button_wait` StaleElementReferenceException 및 free carrier admin `verify_admin_saved_carrier` TimeoutException이다. downstream shipping checks는 skipped다.
- artifact 12644494181에서 mobile address edit form 390×701을 직접 열어 새 한국어 helper `계정에 새 주소를 등록할 수 있습니다.`를 확인했다. 같은 run에서 주소 same-ID 저장/fresh GET/refresh acceptance도 통과했다. 이전 address Timeout의 정확한 원인은 재현되지 않아 미확정으로 둔다.
- matrix에는 QA-REG-001로 두 실제 실패를 분리 기록하고 주소/카탈로그/운송장 완료 근거를 유지했다. 기존 #403006 catalog same-ID reimport 및 tracking success를 최신 실패로 덮어쓰지 않는다.
- PWA-002의 설계/계획은 별도 `kuraneapush` 모듈과 격리 synthetic boundary에 한정한다. 이후 `50d924f`에서 코드/CI 구현을 추가했으며 PHP/MariaDB/Chromium runtime은 아직 Actions 검증 대기다. Provider-backed delivery, approved legal/retention copy, support producer, physical devices remain unverified/blocked.

## 2026-10-26 — 모바일 주소 수정 재검증과 workflow focus 경계 보완

- 최신 원격 `work`와 local HEAD는 `c045d21313af925072d55629f74ec5272d16dbc1`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다. 시작 당시 진행 중인 Actions는 없었고, 사용자 미추적 파일은 보존했다.
- #40300616469의 actual aggregate 유일 실패는 mobile account의 `customer_address_edit` TimeoutException이었다. 캡처에는 같은 주소 카드와 수정 링크가 있었지만 failing predicate는 미계측이었다. `open_customer_address_edit()`를 카드 조회/동일 ID/링크/route/scroll·clickability/center hit/native click/form wait/새 ID 검사로 나누고 안전 enum·boolean 진단 및 실패 캡처를 브라우저 종료 전에 저장하도록 했다. 세션/주소 데이터·URL query·원문 예외는 출력하지 않는다. native click, timeout 또는 acceptance 조건을 약화하지 않았다.
- 독립 정적 검토에서 알려지지 않은 가림 요소 class가 있었음에도 `unavailable`로 기록되는 분류 공백과 diagnostics contract가 주소 ID 일치 결과/단계 순서를 충분히 고정하지 않은 점을 찾았다. 미등록 비어 있지 않은 class는 값 자체를 노출하지 않고 `other`로 분류하도록 고쳤고, 회귀 테스트는 edit form ID boolean과 카드→링크→native click→form 순서를 확인한다.
- 한국어 주소 안내를 `ShopThemeCustomeraccount.ko-KR.xlf`에 추가하고 browser assertion을 연결했다. #40300616469가 그대로 반복되는 대신 기존 fixture를 이용한 account focused run #40307437142가 source c045d21에서 SUCCESS했다. desktop/mobile 주소 생성·편집·저장·새 문서/refresh 재조회 및 회원 auth/reset 흐름이 통과했다. 이전 timeout은 재현되지 않아 원인을 확인된 앱/테스트 결함이라고 정하지 않는다. Artifact 12642513725의 캡처 목록은 handoff에 기록했다.
- #40307147507의 선행 preflight failure는 parent focus 환경 상속과 전체 aggregate test fixture의 실행 모드 미지정이 원인이었다. c045d21에는 full fixture=false/focused fixture=true가 명시되어 같은 focused run의 Step 8/aggregate가 통과했다. focused run이 unrelated admin security fixture/browser도 실행한 누락 condition을 발견해 현재 `.github/workflows/fresh-install.yml`과 contract test를 추가 보완했다: full/default 또는 explicit admin-security focus에서만 실행한다.
- 보완 뒤 inherited `ORDENOWA_CUSTOMER_ACCOUNT_FOCUS=true` 환경에서 workflow Step 8 exact command 551 PASS (7 skipped), Step 9 147 PASS, 영향 계약 199 PASS가 확인됐다. YAML parse, diff check도 통과했다. 이 보완 patch와 현재 QA 상태 문서는 아직 최종 regression push/run을 기다린다.
- #40300616469의 catalog native product 29 same-ID edit/fresh GET/reimport, tracking order 10 browser/admin/customer/DB outcomes success를 요구사항 matrix에 보존했다. 이는 synthetic acceptance이며 실상품/실출고·운영 판매를 의미하지 않는다.
- Work-mode GPT는 #40307437142 artifact 12642513725의 mobile after-refresh PNG를 실제 열어 동일 synthetic 주소의 수정값과 한국어 목록 안내를 확인했다. 편집 폼 PNG에서 별도 고정 안내 `Add a new address to your account.`가 영어임을 발견했다. XLIFF target `계정에 새 주소를 등록할 수 있습니다.`와 해당 Korean form의 exact text browser assertion을 추가해 기존 전체 QA 준비 변경과 한 번의 다음 run에 포함한다. c045 캡처는 이 신규 수정 전이므로 수정 후 화면 evidence는 다음 artifact에서 확인해야 한다.
- matrix는 focus QA/기존 성공 evidence를 반영하고 ADDR-002/LOCALE-003을 분리한다. PWA-002 Web Push는 다음 기존 승인 범위 code task로 남기고, 실제 HTTPS/VAPID/운영 동의 문안/모바일 실기기 제약을 별도로 기록한다.

## 2026-10-26 — catalog readback 진단 및 JA 주문 상세 번역 checkpoint

- 시작 시 local/origin `work`는 `f4c75b89f4c89edbe1fb97ba097cbd061dc30259`, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. 사용자 미추적 superpowers 문서와 pycache는 보존했고 stage하지 않았다.
- `20f3708`은 #40284146117에서 미계측된 native manager readback assertion을 predicate 단위로 기록한다. 진단은 enum 이름과 boolean/null만 허용하고 기존 실패 assertion을 유지한다. `791f2d3`은 JA 주문 상세의 고정 UI 라벨을 child-theme XLIFF에 추가하고 같은 주문 상세에서 locale/라벨을 검사하며 운송장 행 스크롤 캡처를 보존한다. parent Hummingbird와 운영 taxonomy/데이터는 수정하지 않았다.
- Exact fresh-install Step 8 명령 538 tests (7 skipped), 관련 catalog/locale/integration tests 85/85, Python AST/XLIFF parsing, `git diff --check`가 통과했다. Codex 작업공간에서는 Docker/browser 실행을 하지 않았다.
- 최신 runtime 근거는 이전 SHA f4c75b8의 전체 run #40284146117 FAILURE (aggregate 유일 실패 `catalog_import_browser_qa=failure`)다. 새 진단과 JA 화면은 Actions 실행을 기다린다. Independent QA는 artifact 12633129812의 고정 한국어 unsupported URL 안내 캡처만 시각 PASS로 확인했다. manager failure field와 JA runtime 화면을 이 PASS로 확대하지 않는다.
- 코드 커밋은 `20f3708`과 `791f2d31456abd4cfa4dd98447ba1838a41073b0`; 현재 문서 변경은 다음 docs-only commit으로 저장하고 code-tested SHA와 remote HEAD를 분리해 기록한다. 변경 묶음 push 후 자동 Actions를 재사용하며 동일 변경으로 수동 중복 실행하지 않는다.

## 2026-10-26 — 관리자 Welcome 번역 및 합성 주문 tracking QA

- 시작 HEAD와 origin/work는 4011819001d941d92d15a971c12d8ef35c446381로 확인했고 main은 ee02a3657448d563508687614a246e05ac61eecd였다. 사용자 미추적 superpowers plan/spec/pycache를 수정·stage하지 않았다.
- b9ad038에서 Welcome back %name%의 한국어 문구를 overlay하고 placeholder 보존을 확인했다. 새 테스트 RED→GREEN 및 admin-locale 31 tests PASS 후 별도 커밋했다.
- 229dd22에서 기존 AdminOrders native shipping modal로 합성 미결제 주문 tracking 번호를 저장하고 같은 Admin order fresh GET과 customer order detail을 연결하는 browser flow를 추가했다. Read-only native Order/OrderCarrier verifier는 같은 order/tracking, state/JPY total, paid=0 및 무료배송을 대조한다. UI/DB 결과에는 raw URL/token을 남기지 않고, 물리 출고나 carrier scan을 수행하지 않는다.
- 자유배송/workflow/artifact/backup 영향 tests 158개, Python syntax, workflow YAML, affected shell/embedded Python, git diff --check PASS 후 work로 push했고 origin/work가 229dd22f2b90cae8a4425e5a32578bf2141f030b와 일치함을 확인했다. main 불변.
- 자동 전체 격리 run [#40281533046](https://github.com/goldeget/japan-premium-commerce/actions/runs/40281533046)은 SHA 229dd22에서 06:58 UTC SUCCESS로 종료했다. 실제 Step 73 tracking outcome, Step 88 aggregate, postal import/verification, run-owned resource cleanup이 성공했다. Independent QA artifact 12632622676의 같은 주문 캡처/JSON 검수도 기록했다. 고객 JA 주문 상세의 영어 고정 라벨은 새 locale 결함으로 분리했다.
- 직전 full run [#40277922728](https://github.com/goldeget/japan-premium-commerce/actions/runs/40277922728), source e085be5 SUCCESS와 independent artifact 12631716741의 manager-edit 시각 검수를 재사용한다. CAT-004 synthetic same-ID edit/save/fresh GET/reimport acceptance 완료; product inactive/hidden/non-orderable다. GAP-002 public storefront path는 미검증이다.
- fe09a56에서 catalog URL empty/unsupported/>10 입력의 exception과 입력 URL 반사를 막고 fixed Korean 안내, safe page classification/screenshot, browser check를 추가했다. Commit f4c75b8는 새 `invalid_url_notice_visible` 필드를 aggregate contract fixture에 더했다. fe09 전체 run은 fixture 누락으로 preflight에서 중단됐고, 정확한 Step 8 535 tests 및 관련 targeted contract 2개는 로컬에서 통과했다. f4 실행 #40284146117은 Step 8을 통과했지만 최종 FAILURE다. Step 88 actual aggregate의 유일 실패는 `catalog_import_browser_qa=failure`; safe diagnostics는 approve 후 `native_readback/native_editor_readback` AssertionError, HTTP200, 정상 manager ID/편집기, 권한거부 없음으로 한정한다. Artifact 12633129812는 shell 다운로드 403으로 이미지 검수가 미완료다. 다른 outcome/backup/restore/postcode/run 전용 정리는 성공했으며 전체 QA PASS로 취급하지 않는다.
- 일본어 주문 상세 번역은 parent Hummingbird를 수정하지 않는다. Customeraccount/Checkout child XLIFF에 order reference/tracking heading/carrier table header를, Catalog XLIFF에 payment/carrier-summary labels를 추가하고 기존 same-order browser flow로 JA page/document locale/labels를 검사할 계획이다. 이 task는 URL QA 완료 후 순차 진행한다. 운영 seller, 상품/권리, carrier contract, 실제 dispatch/payment, production environment와 실기기 결과는 별도 자료·환경 대기다.

## 2026-10-26 — 합성 catalog 승인 후 manager 경로 및 readback 검증

- 시작 시 local `work` HEAD와 원격 `origin/work`가 `40edaa5ae10369b0937108c3b81dd1bc0239dcc9`로 일치했다. main은 `ee02a3657448d563508687614a246e05ac61eecd`다. 사용자 미추적 문서/파일과 pycache는 보존했다.
- #40269983026 aggregate의 유일 실패 `catalog_import_browser_qa=failure`를 확인했다. Safe diagnostics는 Amazon approval click 이후 `stage=native_readback`, `current_substage=approved_product_link`, HTTP 200, 현재 controller가 review controller라고 기록했다. 실행 순서상 manager navigation 전에 링크 검증이 assertion으로 막혔다.
- PrestaShop 9.2 `Link::getAdminLink()`의 legacy 경로 형식과 현재 assertion을 대조했다. 기존 helper는 exact admin root만 허용했다. 실제 manager link의 raw URL, query, token은 출력하지 않고, 관리자 디렉터리·trailing slash·index.php 세 형식만 분류하도록 수정했다. same-origin/controller/단일 양수 ID 조건은 유지했고 임의 path 및 semicolon parameter를 거부한다. 실패 diagnostics schema에는 안전한 link condition flags와 path-class enum을 추가했다.
- 회귀 테스트를 먼저 확장해 현재 코드에서 `/admin/`와 `/admin/index.php`가 거부되는 RED를 확인했다. 수정 후 세 허용 경로와 외부/잘못된 controller/하위 경로/중복 ID/0 ID/semicolon parameter 거부를 검사했다. catalog browser/admin 및 isolated workflow 계약 검사 55개 PASS, Python compile와 diff check PASS.
- Route/schema 독립 검토 agent들은 초기에 `DIAGNOSTIC_FIELDS` 누락과 `urlparse.params` 우회 경계를 각각 발견했다. schema allowlist를 보완하고 params를 거부하는 테스트를 추가했으며, 최종 read-only 검토에서 잔여 이슈가 없다는 결과를 받았다.
- `Accept native PrestaShop manager entry paths` commit `e1cd6d0c9d58ee2db64462387fef305c2ab0e757`를 `work`에 push하고 원격 SHA가 같은지 확인했다. 자동 전체 격리 run [#40272141646](https://github.com/goldeget/japan-premium-commerce/actions/runs/40272141646)은 05:20 UTC에 SUCCESS로 종료했다. Step 46은 synthetic batch→Rakuten 다중 옵션 거부/반려→Amazon 단일 옵션 승인→manager editor field readback→동일 상품 reimport/readback PASS를 기록했고, Step 87 aggregate도 PASS다. 이 flow에서는 editor의 별도 저장 버튼을 누르지 않았다.
- 해당 동일 native product의 read-only DB 증거: active false, visibility none, order false, image count 1, combinations 2, same reference count 1. 운영 상품 활성화나 고객 게시 없이 검증했다.
- browser artifact [12628194683](https://github.com/goldeget/japan-premium-commerce/actions/runs/40272141646/artifacts/12628194683)에는 batch/rejection/option review/draft/reimport 화면과 `catalog-import-readback.json`, `catalog-import-persistence.json`이 포함된다. 이 환경의 다운로드는 403이어서 PNG 시각 검수는 하지 않았다. Work-mode GPT가 화면 artifact를 다시 열 때는 visual review만 자동 E2E와 구분한다.
- 이 검증은 synthetic fixture에 한정한다. 실제 Amazon/Rakuten 상품 호환성 및 허용된 URL/피드 수집, 원격 이미지 다운로드/권리, 다중 옵션 그룹, 운영 판매 및 판매 게시를 PASS로 기록하지 않는다. 운영 자료·환경은 [개발 현황](DEVELOPMENT_STATUS.md)의 미정 목록에 남아 있다.

## 2026-10-25 21:20 UTC — 잔여 시각 QA 반영 및 전체 격리 검증 완료

- Work-mode GPT가 #402315 artifact `12613108935`를 실제로 열어 확인했다. `詳細を表示`, 모바일 checkout buttons, 일본어 account heading은 보이는 상태로 고쳐졌다. 새 잔여 후보는 조건 데이터의 English policy copy, synthetic/default `Clothes`/`Art` category 값, 한국어 `My Account`, mobile long-title breadcrumb였다.
- policy 문구는 Hummingbird checkout의 `conditions_to_approve` dynamic content (`{$condition nofilter}`)이며 저장소 소유 static theme label이 아니다. 판매자 승인 일본어가 없으므로 고치지 않았다. Category labels도 catalog data라 승인 taxonomy 없이 번역하지 않았다.
- `My Account`/sidebar label의 한국어 XLIFF를 추가하고 PWA desktop QA가 KO copy를 검사하도록 확장했다. 모바일 product page에서는 Hummingbird 원본을 수정하지 않고 마지막 breadcrumb만 wrap하는 자식 theme CSS와 긴 synthetic title overflow/title-match assertion을 추가했다. 새 `mobile-product-detail-breadcrumb.png` 캡처도 browser artifact에 포함하도록 했다.
- Local target suite 121개, Python compile, `git diff --check`가 통과했다. system Chromium의 crashpad 초기화 실패로 Codex local capture는 생성하지 못했고 이를 브라우저 검증으로 주장하지 않는다.
- 코드 커밋 `95af3a9104b6e3f7bfc861155bdc73db9a91ab98`은 `work`에 push된 상태이며, 시작 및 수정 후 원격 SHA가 로컬 HEAD와 일치한다. `main`은 `ee02a3657448d563508687614a246e05ac61eecd`다. 전체 isolated run [#40233614104](https://github.com/goldeget/japan-premium-commerce/actions/runs/40233614104)은 workflow success, Step 80 aggregate `PASS: isolated browser QA and official postcode verification completed.`로 끝났다. Step 80이 `STOREFRONT_BROWSER_QA_OUTCOME=success`, `PWA_BROWSER_QA_OUTCOME=success`를 기록했으며 Step 42/49 및 Step 73/75/83도 success다.
- 새 screenshot artifact [ID 12613919270](https://github.com/goldeget/japan-premium-commerce/actions/runs/40233614104/artifacts/12613919270)은 upload와 coverage를 통과했다. Work-mode 시각 재검수 대상은 `pwa-desktop-ko-account.png`, `mobile-product-detail-breadcrumb.png`, `mobile-product-detail.png`로 한정한다. 이 Codex turn은 PNG를 직접 열지 않아 화면 자체의 추가 visual PASS는 기록하지 않는다.
- checkout의 영어 policy/help 문구는 동적 승인 조건 데이터이므로 판매자 승인 일본어 문안 전까지 변경하지 않는다. `Clothes`/`Art`는 catalog/default fixture category 값이라 승인 taxonomy 없이 번역하지 않는다.
- 운영 DB/named volume, 배포, 실결제, 실거래, 새 유료 서비스는 변경하지 않았다. 자동 browser PASS, screenshot 검수, 실기기 및 운영 준비 상태를 서로 구분해 기록한다.

## 2026-10-25 20:50 UTC — PWA 모바일 계정 검사 수정 및 전체 QA 확인

- #402294의 실패를 실제 shop 404로 단정하지 않았다. `customer_account_route` helper가 모바일 account 페이지에서 숨겨진 sidebar의 첫 GDPR anchor만 기다린 것이 원인이었다. `customer/page.tpl`의 sidebar hook과 main account hook이 중복 출력되고, 모바일 sidebar는 숨겨진다. browser helper가 표시되는 링크를 검사하고 sidebar label은 desktop에서만 검증하게 했다.
- JA `Show details`와 accessible cart-detail label, JA `My Account`와 sidebar aria-label을 테마 번역으로 추가했다. 숨겨진/표시 GDPR 링크 순서 및 모바일 숨김 sidebar에 관한 회귀 단위 검사를 작성했다.
- 검증 코드 `aed4a3cc6e143258e9f493603dd226bfa41b34aa`를 `work`에 push했다. 자동 실행된 전체 격리 Actions [#40231567083](https://github.com/goldeget/japan-premium-commerce/actions/runs/40231567083)은 conclusion `success`. Step 49에서 desktop-ja/en/ko 및 mobile-ja/en/ko 각 PASS와 `PWA_BROWSER_QA_OUTCOME=success`; Step 60, 75, 77–80, 83도 success이며 Step 80 실제 aggregate는 `PASS: isolated browser QA and official postcode verification completed.`였다.
- 최신 run은 screenshot artifact `ordenowa-storefront-browser-40231567083-1`, ID `12613108935`를 저장했다. Work-mode GPT가 새 이미지에서 checkout nav, 일본어 details/sidebar labels, 비밀번호, ja/en/ko PC·모바일 화면을 열어 재검수할 수 있도록 handoff를 갱신한다. 이번 Codex 세션에서 PNG를 열지 않았고 시각 PASS 또는 클릭 테스트라고 주장하지 않는다.
- 남은 후보는 승인된 일본어 판매 policy 문안, synthetic coupon/default category fixture, 실제 clipping이 확인되지 않은 horizontal-scroll breadcrumb다. 실기기/운영 환경이나 실제 판매 자료가 필요한 범위는 자료 대기로 둔다. main, 운영 DB/named volume, 배포, 실결제/실거래는 변경하지 않았다.

## 2026-10-25 20:05 UTC — Work-mode GPT 화면 검수 반영 및 targeted UI 수정

- 시작 시 remote `work`와 local HEAD는 `b94d1f0ba3418b5724f07735e7186c2adbcb6555`; remote `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. 최신 Actions 조회에서 #40226037762 전체 run과 #40225474420 집중 run은 완료 SUCCESS였고 진행 중 run은 없었다. 이전 검증 코드 `bb26f06168e0a10a50607ce4e5171666656611b1` 이후 기존 remote 변경은 docs-only다.
- Work-mode GPT가 artifact #40226037762 (ID `12611855740`)의 PNG를 실제로 열어 검수했다. `shipping-free-checkout-mobile.png` 390×701에서 fixed nav가 `Back to 住所` 버튼 하단을 가렸고 500×701 비교 화면은 정상으로 보였다. JA checkout에서 `Place Order`, 주문 comment와 `Back/Continue`가 영어·일본어 혼합이고 synthetic `ps_checkpayment` 확인 화면에 영어 안내가 남았다. `desktop-korean-login-email.png`의 password label은 `Sleutelwoord`; `pwa-mobile-ja-account.png`에는 영문 GDPR label이 남았다.
- 사진에서 ORDENOWA logo/navy-blue 체계는 일관되고 JP/EN/KO glyph tofu는 관찰되지 않았다. `Clothes`/`Art`는 합성/default category data이므로 실제 taxonomy 입력 없이 번역 데이터를 추정하지 않았다. mobile product breadcrumb 잘림은 DOM overflow로 입증되지 않아 수정하지 않았다. 모바일 최종 total은 화면 아래에 있어 해당 캡처만으로 확인되지 않았고 desktop 합계 증거와 혼동하지 않는다.
- 수정은 child theme mobile checkout에서 고정 nav를 숨기고, mobile checkout E2E에 활성 배송 step의 nav/button 교차·JA copy assertion을 추가했다. JA checkout Actions/Checkout와 `Modules.Checkpayment.Admin` option XLIFF, KO Forms label을 채우고, psgdpr/checkpayment confirmation child-theme templates를 project-owned locale domain으로 바꿨다. PWA account browser QA는 아이콘과 분리된 ja/en/ko 개인정보 label을 검사하고, 한국어 login QA는 별도 password label/stage를 검사한다. Hummingbird upstream submodule은 수정하지 않았다.
- 관련 static/contract 검사 172개가 통과했고, 한국어 stage allowlist 변경 후 `test_korean_customer_login_contract` 9개를 다시 통과했다. Python AST/syntax와 `git diff --check`도 통과했다. 실제 새 PrestaShop/Chromium 결과는 아직 없다. 기존 성공 run은 근거로 보존하고 새 source push로 자동 실행될 isolated QA를 기다린 뒤 Work-mode GPT가 새 artifact를 재검수한다.
- [handoff](AI_BROWSER_QA_HANDOFF.md), [개발 현황](DEVELOPMENT_STATUS.md), [테스트 결과](TEST_RESULTS.md)에 이전 screenshot 증거와 신규 검증 상태를 분리 기록했다. 운영 DB·named volume·운영 배포·실결제·실거래·새 유료 기기 서비스는 건드리지 않았다.

## 2026-10-25 — Work-mode GPT 시각 QA handoff 및 기기 접근 점검

- 시작 원격 `work` HEAD `b94d1f0ba3418b5724f07735e7186c2adbcb6555`, QA source SHA `bb26f06168e0a10a50607ce4e5171666656611b1`, `main` `ee02a3657448d563508687614a246e05ac61eecd`를 확인했다. `bb26f06` 이후 `b94d1f0`은 `DEVELOPMENT_STATUS.md`, `TEST_RESULTS.md`, `WORK_LOG.md` 문서 변경만 포함한다. #40225474420 집중 run과 #40226037762 전체 run의 성공 증거를 재사용했고, 문서 갱신 때문에 전체 QA를 다시 실행하지 않았다.
- 전체 #40226037762 artifact metadata: `ordenowa-storefront-browser-40226037762-1` (ID `12611855740`, 21,326,811 bytes, 2026-11-24 19:42 UTC 만료). Step 73 업로드, Step 75 screenshot coverage, Step 80 aggregate는 성공했다. ZIP 다운로드는 이 환경에서 HTTP 403/전송 오류여서 스크린샷을 `view_image`로 열지 못했다.
- 현재 환경에 browser-control tool 또는 연결 기기/farm은 없다. `adb`, `xcrun`, `simctl`, Appium, iOS device utility와 USB bus가 없다. `/usr/bin/chromium` 154.0.8037.57, Playwright 1.62.0과 mobile profiles는 존재하지만 shop target이 없어 product visual emulation은 미실행이다. `127.0.0.1:18080`에는 listening app/HTTP response가 없다.
- workflow의 shop은 run 전용 runner loopback에서만 실행하고 Step 83 cleanup이 project/volumes를 삭제한다. 외부 staging URL/access window, durable synthetic fixture ID, Work GPT용 approved secret path가 없다. 기존 CI credential은 run 전용으로 생성·mask하며 현재 access에 재사용하지 않는다.
- Work-mode GPT가 기존 artifact를 열어 시각 검수하고 캡처별 결과를 기록하도록 `docs/AI_BROWSER_QA_HANDOFF.md`를 만들었다. 그 문서에 Codex/Work 책임, screenshot target, 기존 자동 QA 재사용 범위, access blockers, live interactive QA에 필요한 승인 환경을 한 목록으로 정리했다. 사용자 수동 실기기 검수는 요구하지 않는다.
- 개발 현황에는 자동 QA PASS, visual review pending, mobile emulation target unavailable, physical device `미검증—기기 연결 필요` 및 기존 `미정` 운영 입력을 분리 기록했다. 비밀값·새 host·테스트 계정을 만들지 않았고 유료 기기 서비스를 추가하지 않았다. 사용자 미추적 파일은 스테이징하지 않았다.

## 2026-10-25 — RMA tokenless 경고 확인, 수정, 집중·전체 QA 통과

- 시작 기준 원격 `work`는 `0d9f5d4827010c05a1b4a45647015427f865a6b4`; 시작 시 로컬 변경과 미추적 계획/`__pycache__` 파일을 보존했다. 원격 `main` `ee02a3657448d563508687614a246e05ac61eecd`는 수정하지 않았다.
- tokenless 경로의 정적 검사만으로 원인을 확정하지 않고, PrestaShop 9.2 보안 경고 fixture의 native marker와 exact route 검사를 브라우저 진단에 연결했다. 관리자 로그인 후 생성된 반품 메뉴 anchor를 검사해 same origin, 관리자 path, exact return route 및 단일 세션 token 존재를 확인하고 그 href를 메모리에서만 사용했다. 하드코딩 tokenless path와 정상 tokenized menu 이동을 비교했다.
- 실제 브라우저 결과: tokenless probe는 exact `security/compromised` path + native marker로 분류됐고 marker가 보였다. 앱 생성 메뉴 링크는 검증에 통과했으며 tokenized 복귀 분류는 `none`; comparison은 `tokenless_compromised_tokenized_clear`. 이를 통해 테스트 이동에 session token이 빠져 있었음이 확인됐다. 보안검증이나 권한을 완화하지 않았다.
- 대상 synthetic RMA 동일성 검증 뒤 native form에서 1→2 저장, 새 문서 GET 후 state 2 확인, 2→1 저장 및 새 GET 후 state 1 확인, 원래 상태 복원을 확인했다. 모든 단계에서 native save와 success alert가 확인됐다.
- 회귀 보호: unresolved token comparison은 grid 대기 전에 실패해야 한다는 contract를 추가했다. 로컬 관련 계약 149개, Step 8 142개 false/true 각각, Step 9 43개 false/true 각각 통과했다. workflow YAML, embedded shell, Python compile, `git diff --check`도 통과했다.
- 독립 코드 수정 커밋 `[admin-return-focus] diagnose tokenized return navigation` `bb26f06168e0a10a50607ce4e5171666656611b1`를 `work`에 push했고 `git ls-remote`로 SHA 일치를 확인했다. 자동 집중 Actions [#40225474420](https://github.com/goldeget/japan-premium-commerce/actions/runs/40225474420)는 RMA Step 70 저장/복원과 Step 80 aggregate 성공. 이어 최종 코드에 전체 QA 1회 [#40226037762](https://github.com/goldeget/japan-premium-commerce/actions/runs/40226037762)를 dispatch했고, Step 80 `PASS: isolated browser QA and official postcode verification completed.` 및 workflow success를 확인했다.
- 두 run의 Step 73/75에서 경고 요소와 상태 control screenshot 업로드/coverage가 성공했다. Artifact 다운로드는 403을 반환해 이미지를 로컬에서 시각 열람하지 못했다. GitHub log에서 safe route classifications, screenshot captured=true, transition readback 및 aggregate를 확인했다.
- 상품 제목 `404` 오탐 수정과 폰트 캐시를 그대로 보존했다. 전체 run Step 42 상품 검증, Steps 30–32 font cache/Chromium 준비 통과. run `40214404446` 자체의 실제 문서 HTTP 상태는 미확인 상태로 유지한다.
- 합성 고객/주문, Mailpit 및 isolated DB만 사용했으며 기존 개발 DB/named volume, 운영환경, `main`은 변경하지 않았다. 실결제·배포·실거래를 실행하지 않았다. 판매자·실SKU/권리/세무/배송/결제/환불/법률·운영 인프라 자료는 사용자 제공 기준대로 미정/대기로 유지한다.

## 2026-10-25 — Step63 오탐 수정 확인 및 RMA 집중 실패 단계 확정

- 작업 시작 때 `work` 로컬 `HEAD`와 `origin/work`는 `9c6c05346bad3afcaa1ac539308393061e44d35f`로 일치했다. `main`은 `ee02a3657448d563508687614a246e05ac61eecd`. 기존 미추적 사용자 파일은 변경·삭제·스테이징하지 않았다.
- `6020439ef085be775f2246fe2cb4f8d704902582`는 합성 상품명이 GitHub run ID를 포함해 `404` 숫자열을 가질 수 있는데도 `"404" not in driver.title`로 판정한 오탐을 수정했다. 검사에서 해당 run ID `40214404446`을 포함한 정상 제목을 로컬 재현하고 상품 ID·상세 화면 요소·가능한 최종 문서 응답 상태로 정상 상세와 오류 화면을 구분한다. 과거 #40214404446의 HTTP 상태는 수집되지 않아 unknown이다.
- 로컬 계약 검사 91개가 통과했다. 사전 Step8 테스트 462개 통과/7 skipped, Step9 테스트 137개 통과 결과를 재사용했다. #40221893987의 Steps 8–12 및 14 설치가 성공했다.
- 자동 집중 Actions [#40221893987](https://github.com/goldeget/japan-premium-commerce/actions/runs/40221893987), 코드 SHA `9c6c053`에서 Step67 상품/장바구니 검사는 desktop/mobile 모두 문서 상태 200 및 assertion success를 기록했다. Step68 합성 paid-like fixture와 Step69 고객 반품 제출도 success.
- 관리자 RMA Step70은 실제 process exit 1, aggregate Step80은 `order_return_admin_browser=failure`. 안전 진단은 `last_completed_stage=return_list_navigation`, `failure_stage=return_grid`, `TimeoutException`, requested pathname `/admin-kuranea/sell/customer-service/merchandise-return/`, observed pathname `/admin-kuranea/<redacted>/<redacted>`, same-admin-origin/path true, HTTP 200, `readyState=complete`, `page_class=other_admin`, visible error marker/login form/grid 모두 false다. 따라서 목록 navigation 완료 뒤 예상 그리드가 없는 다른 관리자 경로 형태가 관측됐다. 실제 route text는 마스킹되어 앱 리다이렉트 결함인지 테스트가 기대한 경로 결함인지 확정할 수 없으므로 경로를 추측해 수정하지 않았다.
- 해당 실패로 대상 RMA·주문·편집 화면을 확인하지 못했다. 상태 1→2 POST/성공 알림/fresh GET 재조회 및 2→1 복원/fresh GET는 전혀 실행되지 않았다. RMA 화면 캡처도 생성하지 않았다. RMA 기능 PASS로 기록하지 않는다.
- Step75 screenshot coverage 및 Step83 run 전용 정리는 success. storefront screenshot artifact `12610240802`와 안전 진단 artifact `12609916454`는 Actions에 저장됐다. 다운로드 요청은 403이었으므로 캡처 파일을 시각 열람하지 않았고 Step Summary/annotation에 남은 안전 진단을 사용했다.
- 폰트 archive cache hit로 #402218 Step32 브라우저 환경 준비는 13초였다. 이전 run #402144의 Noto CJK setup 약 23분, #402195 Step32 11분 10초는 fonts-noto-cjk 설치/다운로드 setup이며 앱 검증 시간과 구분한다.
- 집중 aggregate가 실패했으므로 이번 코드로 전체 회귀 QA를 실행하지 않았다. 원인을 확정한 최소 수정과 집중 재검증이 필요하며, 집중 검증 성공 후에만 전체 QA를 1회 실행한다. 운영 DB, named volume, 배포, 실결제·실거래는 사용하지 않았다.

## 2026-10-25 — 관리자 RMA 진단 추가 및 집중 실행 차단 기록

- 시작 상태: `work` 로컬과 `origin/work`는 `066582812796e437e11f471a98777786aec51152`로 일치했고, 진행 중 Actions는 없었다. 미커밋 사용자 파일과 `.superpowers/`/기존 `__pycache__`는 보존했다. `main` SHA `ee02a3657448d563508687614a246e05ac61eecd`는 변경하지 않았다.
- 이전 집중 실행 #40213486739에서 관리자 로그인은 완료됐지만 결합 `return_list` 단계가 `TimeoutException`으로 실패했다. 안전 진단에는 `last_completed_stage=admin_login`, order/RMA/grid match false가 있었으나 실제 라우트·grid 여부는 구분하지 못했다.
- 단계 추적을 `return_list_navigation`과 `return_grid`로 분리했다. 실패 시 동일 시점 `current_url`은 기록하지 않고 same-origin, admin-path, page-class, readyState, grid 존재만 allowlist한다. 모든 일반 예외는 허용된 Selenium/Python 예외명으로만 매핑한다. JSON artifact, Step Summary, annotation은 같은 안전 진단 필드를 사용한다. 캡처는 대상 합성 RMA와 주문을 확인한 편집 화면의 상태 선택 요소로 제한되며 전체 페이지 캡처는 추가하지 않았다. Workflow의 정확한 키·단계·enum 및 bool allowlist를 동기화했다. 테스트 계약은 navigation 완료와 grid 대기를 분리해 고정했다.
- 회귀 보호: `same_admin_origin`은 localhost allowlist뿐 아니라 기대 host와 실제 host의 일치도 요구한다. 포커스 환경변수의 전체·집중 집계 fixture는 기존처럼 각각 명시적 값을 유지한다.
- 로컬 preflight: workflow의 정확한 Step 8 명령은 `ORDENOWA_ADMIN_SECURITY_FOCUS=false`/`true` 각각 133/133 통과, Step 9 명령은 각각 43/43 통과했다. 두 모드 모두 SECURITY/RETURN/QA focus 변수를 명시했다. fresh-install YAML parse, verifier `py_compile`, `git diff --check`도 통과했다.
- 코드 커밋 `[admin-return-focus] separate RMA list navigation and grid diagnostics` (`83d557e5d8c15df098f01d22cf58f4b4fb8e96ad`)를 `work`에 push하고 `git ls-remote`로 동일 SHA를 확인했다.
- 자동 집중 Actions [#40214404446](https://github.com/goldeget/japan-premium-commerce/actions/runs/40214404446)은 이미지 build, 빈 설치, 합성 우편번호, 무료 운송사 setup, checkout browser 및 unpaid order persistence를 통과했다. Checkout restore Step 62도 성공했다. 이후 Step 63 `checkout_gate_after_order`의 실제 outcome은 failure였고 안전한 AssertionError 메시지는 `CI product detail page did not render`였다. `continue-on-error` 때문에 UI step conclusion은 success였으나 aggregate는 이를 failure로 집계했다.
- 이 선행 gate 실패로 Step 64 paid-like fixture, Step 65 customer return, Step 66 admin RMA가 전부 skipped됐다. Step 71 screenshot coverage는 필수 admin RMA 로그 부재로 failure, Step 76 aggregate도 `checkout_gate_after_order=failure order_lifecycle_fixture=skipped order_return_browser=skipped order_return_admin_browser=skipped admin_return_evidence=failure`로 failure였다. Step 79 run-scoped cleanup은 success. 이 실행은 RMA 실패 원인이나 1→2 저장/재조회/2→1 복원을 확인하지 못했다.
- #40214404446의 선행 Step63 failure는 RMA 결함으로 간주하거나 우회하지 않는다. 전체 QA 추가 실행은 진행하지 않았다. RMA 진단 변경은 저장됐지만 기능 버그가 해결된 것으로 판정하지 않는다. 현재 집중 실패의 선행 gate 원인을 근거와 함께 분리한 뒤 기존 focus 환경에서 RMA를 다시 검증해야 한다.
- 운영 DB/named volume, 실결제/실거래, 배포를 사용하지 않았다. 테스트 이후 run 전용 container/volume 정리가 success였다. 문서 업데이트는 이 진단 상태와 Step 63 선행 차단을 정확히 기록한다.

## 2026-10-25 — Return submission 고정 및 전체 QA 결과

- 기존 `work` 브랜치에서 계속 작업하고 `main` SHA `ee02a3657448d563508687614a246e05ac61eecd`는 변경하지 않았다. 최신 QA 대상 코드 SHA는 `c3897dfb1acbc704c1482d32cf2247dbc24ebf55`다.
- #40208183512 (`46b823c`)의 실제 customer return outcome은 `failure`: safe state에서 제출 버튼이 viewport 밖에 있었고 center hit-test는 `no_target`이었다. Hummingbird button은 normal flow였으며 테스트는 checkbox만 명시적으로 scroll했다. `c3897df`는 submit 버튼을 중앙으로 scroll하고 center hit-test wait 후 같은 native Selenium click을 수행하도록 고쳤다. timeout/interception 모두 진단과 screenshot을 저장한 뒤 재발생시킨다. POST/readback 조건은 바꾸지 않았다.
- #40209847999 (`c3897df`)에서 customer return submit은 성공했고 order-follow list의 요청 readback도 통과했다. 그러나 관리자 return browser의 실제 outcome은 failure이며 로그에는 `native admin return form did not preserve the run-scoped return`만 남았다. Admin return step의 결론 `success`는 `continue-on-error` 표시다. 실제 aggregate annotation은 `order_return_admin_browser=failure order_lifecycle=failure`; lifecycle은 admin-return gate에서 멈췄다. 정확한 실패 assertion 및 앱 결함/테스트 결함 구분은 미해결이며 이를 위한 새 전체 QA는 시작하지 않았다.
- #402098의 admin security, account/reset, 관리자 복구, brand/email logo, product, PWA, Tokyo/Osaka free-shipping/tax/order persistence, backup/restore, restart, postal import/verify outcomes는 성공했다. Screenshot upload/coverage와 run 전용 container/volume cleanup, checkout post-step도 성공했다. Browser artifact ID `12605811294`, diagnostics artifact ID `12605901345`가 unexpired로 저장됐다. 파일은 다운로드/시각 검수하지 않았다.
- Privacy fixes: `ab6d3ff`는 customer return checkbox/submit blocker DOM id/class를 exact allowlist로 제한하고 ID를 비운다. `46b823c`는 account blocker도 같은 식으로 처리한다. Step 9 exact workflow command는 `ORDENOWA_ADMIN_SECURITY_FOCUS=false/true` 각각 130 tests 통과. Return focused contract는 7/7, account contract는 50/50 통과. Step 8 이전 preflight는 461 tests, 7 skipped, focus false/true 양쪽 통과했다. 독립 review는 PII 경로나 native click/readback gate 약화를 찾지 않았다.
- 고객 정책 ja/en/ko, JPY, 세금 포함 표시가, 지원 일본 배송지역 고객 요금 ¥0, 결제 시 별도 세금/배송비와 플랫폼 수수료 ¥0은 확정이다. 실상품·세무·배송/운송·결제/환불 운영 값은 미정이다. 실제 seller/LOGISTEED 관계·seller authority·customer center, SKU/권리/세금, 승인 결제와 약관, production host/domain/DNS/TLS/SMTP/registry/secrets, 운영 admin access owner, 운영 backup/restore 목표/담당자, iOS/Android 실기기 모두 미정이다. LOGISTEED 공개정보는 `company_reference` 전용이다.
- run [#40209847999](https://github.com/goldeget/japan-premium-commerce/actions/runs/40209847999)은 **FAIL**이므로 출시 QA PASS로 기록하지 않는다. Browser artifact [ID 12605811294](https://github.com/goldeget/japan-premium-commerce/actions/runs/40209847999/artifacts/12605811294)와 diagnostics artifact `12605901345`는 Actions에 저장되어 있으며 캡처는 현 workspace에서 열어보지 않았다. 운영 DB/named volume, Docker Cloud build, 실배포, 실결제, 실거래, 유료구매를 사용하지 않았다.

## 2026-10-25 — 고정 범위 Dashboard 경로 수정 및 1회 최종 QA

- 시작 원격 `work`/로컬 코드 기준은 `e356a8a01f9215f2a3dd32ab623a806bda5e398a`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. 이전 전체 격리 QA [#40187411910](https://github.com/goldeget/japan-premium-commerce/actions/runs/40187411910)은 Step69에서 `admin_security_browser_qa=failure` 하나로 실패했고 Step72 cleanup은 통과했다. 그 실행에서 brand Step32/33은 성공했으므로 `admin_login_after_publish` 오류는 재처리하지 않았다.
- Step39에서 관찰한 실제 상태는 로그인 폼 없음, Dashboard 링크 1개, 분류 결과 `current_controller=other`였다. 안전한 기존 로그가 token을 포함한 전체 URL을 기록하지 않았기 때문에 실제 경로 형태는 확인 불가였다.
- TDD RED로 `/admin-kuranea/index.php/sell/dashboard?controller=AdminDashboard`가 이전 분류기에서 `other`가 되는 것을 재현했다. 같은 origin, controller 및 exact path 제한을 유지하며 이 index.php 접두 Symfony Dashboard 경로를 추가했다. 추가 하위 경로와 외부 origin 거부는 그대로 테스트했다. 보안 계약 36/36과 `git diff --check`가 통과했다.
- 코드 커밋 `74e64b966d5943a3d06cadd04fe6fc7b17669bfe`를 `work`에 푸시했고 원격 SHA를 확인했다. 푸시 자동 실행인 전체 QA [#40188721058](https://github.com/goldeget/japan-premium-commerce/actions/runs/40188721058)이 이번 범위의 유일한 추가 실행이다.
- 최종 실행은 FAIL: Step39 실제 outcome이 다시 `view_only_employee_dashboard_route`였고 `current_controller=other`; Step69 유일 실패는 `admin_security_browser_qa=failure`. 경로를 포함하지 않는 현재 증거로 추가 변경을 추측하지 않았다. 명시된 실행 한도에 따라 추가 전체 QA는 하지 않는다.
- 같은 run에서 brand Step32/33, PWA Step41, 회원·상품·장바구니 Steps34–37, 주문 및 무료배송/금액 Steps48/50–57, lifecycle Steps51/61, 격리 backup/restore Step62, 캡처 coverage Step64, restart Step66, Japan Post Steps67–68은 실제 outcome success이며 Step72 run 전용 cleanup도 success다. PC·모바일 캡처 artifact는 ID `12597164472`에 보존했다. artifact는 다운로드하지 않았다.
- 수정·문서는 운영 DB/named volume, 실결제, 운영 배포를 사용하지 않았다. 최종 코드 SHA와 실패 상태를 출시 현황·테스트 결과·이 작업 로그에 기록한다.

## 2026-10-25 — AdminOrders Korean locale 원인 수정 및 출시 범위 재점검

- 시작 시 원격 `work`는 `b5c20a2299984cded956ffbf3d86560b1f4e0f1f`, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. `/tmp/ordenowa-release-closure` 격리 checkout에서 작업했고 원래 `/workspace`의 untracked 자료는 건드리지 않았다.
- #40171264031의 Step39 실패를 route/auth와 UI translation으로 분리했다. `/sell/orders`는 HTTP200, `AdminOrders` route, login/permission error 없음이었다. 진단의 `main` selectors가 PS 9.2의 `#main-div`, toolbar `h1.title`, `.js-grid-panel`, `.grid-table` 구조와 맞지 않아 blank-shell 결과는 잘못된 진단이었다.
- 실제 번역 공백은 source 도메인에서 확인했다. Orders grid/menu title은 `Admin.Navigation.Menu`; empty-state title/description은 `Admin.Orderscustomers.Feature`. 해당 Korean XLIFF 2개를 module subscriber에 등록했다. Browser assertion은 정확한 Korean page/grid title 및 empty-state copy를 확인하고 English `order(s)` 표기를 허용하지 않는다. Empty 및 populated branch 모두 local contract가 있다.
- TDD focused contracts는 변경 전 overlay 누락 4건 RED, 수정 뒤 GREEN을 확인했다. 전체 focused batch는 124/124, Python AST/XLIFF XML 및 `git diff --check` PASS. PHP CLI는 로컬에 없어 PHP lint는 Actions에 위임했다.
- Code review는 Critical/Important 없음, selector/domain/source strings를 적합하다고 판정했다. populated Orders page branch 추가 검토 후 코드 변경 없이 contract coverage gap을 닫았다.
- `70c034255218f8b2cb9c388b143dc82bfe3cd5db`와 `c392db70400a4468b57da279eb024a12d8ab0d24`를 `work`에 push했고 `git ls-remote`로 최종 SHA를 확인했다. `main`은 변경되지 않았다. full isolated run [#40173333689](https://github.com/goldeget/japan-premium-commerce/actions/runs/40173333689)은 기록 시점에 진행 중이며 최종 결과를 아래 QA record에 추가해야 한다.
- 기존 UI/flow 및 release blockers는 출시 상태표와 release audit에 근거해 분리한다. 합성 상품/세율·Mailpit·무결제 주문은 실제 운영 준비로 취급하지 않는다. 실제 운영 배포·실결제·실거래는 하지 않았다.

## 2026-10-24 — PWA 빈 체크아웃 실패 진단 및 출시 준비 점검

- 작업 시작 시 `work`와 `origin/work`는 `44a88a07e0693ecf463764a357262f5d19455529`였고, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. 미커밋 진단 변경을 보존한 채 진행했고 `main`에는 쓰지 않았다.
- 이전 PWA 수정 커밋 `44a88a0`는 PrestaShop에서 실제 확인한 JA `マイアカウント`, KO `내 계정` 경로를 반영했다. 같은 SHA의 full run [#40131335079](https://github.com/goldeget/japan-premium-commerce/actions/runs/40131335079)와 [#40131324863](https://github.com/goldeget/japan-premium-commerce/actions/runs/40131324863)은 모두 Step 65 aggregate에서 `pwa_browser_qa=failure`다. 완료 시각이 더 늦은 #40131324863은 21:02:10 UTC 완료다. annotation은 desktop-en/mobile-en 모두 `guest_empty_checkout_route; AssertionError; path=/<other>`로만 한정된다. 해당 당시 E2E substep telemetry가 없었고 logs/artifact ZIP은 프록시 egress 403이라 원인을 더 세분화하지 못했다. HTTP 404나 앱 결함으로 추정하지 않는다. Step 68의 run-specific cleanup은 PASS, Step 49는 conditional skip.
- `16f3f3a`에서 empty-checkout validator의 하위 검증 조건을 고정 substage로 기록하고 민감한 URL/query를 제외한 trace 진단을 추가했다. 그 SHA의 full run [#40132927859](https://github.com/goldeget/japan-premium-commerce/actions/runs/40132927859)은 Step 65 aggregate FAIL이었다. desktop-en/mobile-en annotation은 `guest_empty_checkout_initial_route`였다. 진단 trace의 initial target은 `/en/cart`, redirect/final은 cart 200/private no-store/network로 나왔다.
- Trace 원인을 코드에서 확인했다. `navigate_private_document()`가 cache policy 확인용 `driver.current_url`(최종 `/en/cart`)을 넘긴 뒤, 같은 URL을 `safe_document_navigation_trace()`의 최초 요청 인자로 재사용했다. trace는 주문 요청이 아니라 마지막 cart request부터 추적돼 validator의 expected `order`와 충돌했다. 이는 테스트 harness 결함이며 HTTP 404나 PrestaShop logout 결함이 아니었다. Steps 34 account/logout은 통과했고 Step 41은 빈 checkout 검사까지 진행했다.
- `test_final_cart_cache_check_keeps_order_url_as_navigation_trace_origin`를 먼저 작성해 실제 `navigate_private_document()` 경계에서 수정 전 `expected order / got cart` RED를 확인했다. `b99b615`는 최초 navigation URL을 `navigation_trace_url`로 별도 보존하며 cache header target은 최종 문서 URL로 유지한다. 수정 후 회귀 GREEN, PWA/cache focused 101/101, offline smoke 526 PASS/7 skipped, Python/JS syntax, `git diff --check`를 확인했다.
- `fix(test): trace empty checkout from the requested order URL` 커밋 `b99b61559978dd8b4c25819623669e0d92deb768`를 `work`에 push했고 `git ls-remote`와 로컬 HEAD가 일치한다. push가 시작한 full isolated Actions [#40134196682](https://github.com/goldeget/japan-premium-commerce/actions/runs/40134196682)는 기록 당시 Chromium 검사를 수행 중이었으며, 최종 결과는 다음 bullet에 기록했다.
- Run #40134196682는 2026-10-24 21:37:51 UTC SHA `b99b615`에서 `success`로 완료됐다. Step 65 aggregate, Step 68 run-specific cleanup 및 Steps 34, 41, 52–57, 60–64가 통과했다. failure/cancelled step이나 failure/cancelled annotation은 없었다. Step 49 conditional skip, Step 66 failure diagnostics skip은 조건을 충족하지 않아 건너뛴 결과다.
- 해당 check-run의 한국어 logout notice 10개에서 account-page/menu의 same-origin `/ko/?mylogout` signout 링크와 첫 document request가 일치했다. 응답 sequence는 `302 → 302 → 200`; 두 redirect Location 모두 다음 요청과 맞고 마지막 응답은 expected login route HTTP 200이었다. 페이지가 우회 전 service-worker-controlled였고 network-only 비교에서는 bypass가 enabled, 30개 event 전부 `from_service_worker=false`였다. 이 후속 통과 실행에서 HTTP 404는 재현되지 않았으며 이전 #40036387808의 exact event trace는 복원하지 못했다.
- PC·모바일 브라우저 캡처는 [run #40134196682 artifact](https://github.com/goldeget/japan-premium-commerce/actions/runs/40134196682/artifacts/12576851933)의 `ordenowa-storefront-browser-40134196682-1` (ID `12576851933`, 15,618,931 bytes)에 보관된다. Step 60 upload와 Step 61 coverage는 PASS, metadata상 미만료다. 파일 본문은 실행환경 프록시에서 403으로 막혀 직접 다운로드하지 못했다.
- CLI GitHub 인증, `work` 원격 조회/push, Actions run metadata와 check annotation은 작동한다. 이 환경의 프록시는 GitHub Actions log/artifact signed storage host 연결을 403으로 거부해 로그 및 ZIP 본문을 가져오지 못했다. GitHub 앱 커넥터는 현재 도구에 노출되지 않는다. 이번 진단 결과를 저장소 문서에 signed URL이나 인증정보와 함께 기록하지 않았다.
- 출시 필수 입력과 근거 한계(실제 SKU/가격·세금·carrier, 승인된 payment provider/계좌, seller identity/authorization, 운영 domain/TLS/mail, 환불 운영, 재해복구, 완전한 관리자 한국어, iOS/Android 실기기 설치)는 [최신 개발 현황](DEVELOPMENT_STATUS.md)의 준비 상태 표에 정리했다. 실제 상품/판매자/결제 설정이 승인되고 운영 검증을 마치기 전 판매 가능 상태로 판단하지 않는다.
- 운영 DB·named volume을 초기화/삭제하지 않았고, 운영 배포·실결제·실거래를 하지 않았다. Codex Cloud에서 Docker 빌드를 시도하지 않았으며 runtime QA는 격리 GitHub Actions에 뒀다.

## 2026-10-23 — 출시 가격 정책 최종 격리 QA (23:06 UTC)

- `work`와 `origin/work`는 `c60a851e114ff00f6e4d8c8c708ad3016bc980bd`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다. CI 테스트 계정 이메일 로컬 파트 길이 수정 후 focused checkout/free-shipping 계약 77개, pricing/tax suite 83개, Python 구문 및 diff 검사가 통과했다.
- 최신 isolated fresh-install run [#40036387808](https://github.com/goldeget/japan-premium-commerce/actions/runs/40036387808)은 완료됐으며 Step 65 aggregate는 `Failed steps: pwa_browser_qa=failure`다. 안전한 주석은 desktop logout 후 로그인 폼을 기다리다 final document HTTP 404로 끝났다고 보고한다. 이는 가격과 무관한 PWA logout/redirect blocker다.
- 가격 Steps 52–57은 전부 PASS다. Tokyo PC 수량 2+쿠폰 및 같은 장바구니 모바일 뷰포트 대조, Osaka 모바일 수량 1, 합성 과세 상품, 명시적 0% QA 상품에서 배송비 ¥0을 확인했다. 상품 상세·장바구니·체크아웃·주문 확인·주문내역 totals를 대조했다. Step 56 네이티브 미결제 주문의 상품·세금·배송·할인·총액 저장 검증과 Step 57 별도 관리자 세션의 네 주문 금액 검증도 통과했다.
- Free Japan carrier는 격리 Back Office에서 설정 후 재조회했다. 체크아웃 fail-closed 상태 복구·재확인, PC/모바일 캡처 coverage, shop restart persistence, Japan Post import/count, run 전용 cleanup도 통과했다. checkout 주문은 `ps_checkpayment` 미결제 fixture이며 실제 결제는 실행하지 않았다.
- 배송 구역 fixture는 47개 지원 도도부현을 포함하지만 browser 주문은 Tokyo/Osaka 표본뿐이다. 10% 과세와 명시적 0%는 CI 전용 합성 규칙이며 일본 법정 세율이나 실제 판매자·상품 세무 판단의 증거가 아니다. 운영 DB·named volume·운영 배송 설정을 변경하거나 운영 배포를 하지 않았다.


## 2026-10-23 — 가격 정책 격리 QA 결과 (20:44 UTC)

- 원격 `work` 및 로컬 HEAD는 `92818b73bc849e69a8ac9f9241524c4236ac4f94`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 변경하지 않았다.
- 최신 전체 fresh-install run [#40019954429](https://github.com/goldeget/japan-premium-commerce/actions/runs/40019954429)은 완료됐으며 Step 63 aggregate 결과는 FAIL이다. Steps 51–55는 Tokyo desktop 수량 2+쿠폰, Osaka mobile 수량 1+쿠폰 없음, 합성 과세 checkout, 저장 주문 재조정, 별도 관리자 금액 확인에서 각각 성공했다. Step 49–50은 건너뛰었다.
- Aggregate 진단: `admin_security_browser_qa=failure`, `pwa_browser_qa=failure`, `account=failure`, `checkout_customer=failure`, `checkout_order_persistence=skipped`, `checkout_admin=skipped`. 안전한 주석에는 고객 PC·모바일 상품 검색 timeout, 모바일 계정 수정 후 `/identity`에 남으며 현재 비밀번호와 `customer_privacy`·`psgdpr` 필수값이 invalid인 상태, 관리자 누락 토큰 응답을 식별하지 못한 상태(HTTP 200), PWA 주문 경로 assertion 실패가 기록됐다. 따라서 전체 QA를 PASS로 표시하지 않는다.
- Steps 41–45의 격리 무료 운송사 설정·재조회, 51–55의 pricing-only 검사, 56–57의 fail-closed 복구, 58–62의 캡처·재시작·Japan Post 가져오기/주소 검증은 성공했다. 개별 성공 step을 aggregate 결론과 구분해 보존한다.
- 세금 fixture는 CI 전용 합성 10% 규칙으로 계산을 검증한다. 일본 세법·판매자 세무 상태·상품별 면세 판단 근거가 아니며 면세 상품 시나리오도 미검증이다. Carrier zone은 47개 지원 도도부현을 포함하지만 브라우저 주문은 Tokyo와 Osaka 표본이다.
- 이 QA는 격리 Actions 환경에서 수행했다. 운영 DB/named volume/carrier 설정을 변경하거나 실결제·운영 배포를 하지 않았다.

## 2026-10-23 — 출시 가격 정책 QA 상태 갱신 (13:00 UTC)

- 현재 기준 `work` SHA `6a371a912d436c354b0ab91f67c458a3d9131439`; `main` SHA `ee02a3657448d563508687614a246e05ac61eecd`는 변경하지 않았다.
- 사용자가 확정한 가격 정책은 일본 지원 지역 배송비 ¥0, 상품 표시 세금 포함 판매가격과 결제 상품 금액의 일치, 결제 단계 추가 배송비·세금·플랫폼 이용료 미청구다. 과세 대상은 실제로 지정된 판매자·상품 세금 규칙을 유지하고, 규칙 미할당을 면세 또는 0%로 허위 기록하지 않는 범위로 QA한다.
- 로컬에서 storefront 네트워크 검사 파일을 제외한 smoke 361개와 무료배송·세금 집중 계약 23개가 통과했다. 이 결과는 계약/정적 테스트이며 실제 브라우저, PrestaShop 주문 저장, 관리자 금액 검증이 아니다. Codex Cloud에서 Docker 빌드를 하지 않는다.
- 최종 코드 SHA `6a371a9`의 격리 fresh-install Actions [#39957544456](https://github.com/goldeget/japan-premium-commerce/actions/runs/39957544456)는 진행 중이다. 이전 코드 SHA `0aafdd8`의 [#39957326795](https://github.com/goldeget/japan-premium-commerce/actions/runs/39957326795)도 상태 행 재사용을 검증하기 위해 실행 중이다. 실제 설치·가격 QA 결과는 관련 단계 완료 전 미확정이다.
- 이전 full run [#39956044032](https://github.com/goldeget/japan-premium-commerce/actions/runs/39956044032)은 일본 지원 도도부현 행이 중복이라고 판정되어 무료배송 fixture에서 실패했다. checkout 가격 브라우저 단계는 실행되지 않았다.
- 최신 배송 fixture는 PrestaShop State API로 47개 카탈로그 행을 재사용한다. 상태 조회가 실패하거나 중복 ISO 코드가 존재하면 쓰기 전에 중단하고, 비지원 활성 상태가 country zone fallback으로 무료배송을 받는 것도 거부한다. 브라우저 표본은 Tokyo desktop qty 2+coupon와 같은 장바구니 mobile viewport 대조, Osaka mobile qty 1/no coupon, 별도 synthetic-tax Tokyo 주문이며 모든 지역·조건 조합을 의미하지 않는다.
- 한국어 배송 패널은 현재 PrestaShop AdminCarriers/AdminShipping 설정을 링크한다. 이번 QA는 그 native 화면에서 무료 운송사를 run-scoped 일본 zone에 저장하고 재조회하는 동작을 CI 격리 DB에서만 수행하며, 운영 배송 설정을 변경하지 않는다.
- 합성 10% 세금은 산술·저장 검증용 CI fixture이며 일본의 적법한 세율이나 판매자의 실제 세무 판단이 아니다. 실제 과세/면세 구분은 판매자·상품 세금 규칙으로 확인해야 한다.
- 현 시점에는 무료배송 가격, 브라우저 주문, 저장 주문, 주문내역, 관리자 주문액의 runtime PASS가 없다. Actions 각 단계가 완료되고 성공한 뒤에만 결과를 갱신한다. 운영 DB/named volume/carrier 설정은 변경하지 않았고, 실결제와 운영 배포를 실행하지 않았다.

## 2026-10-23 — ORDENOWA 출시 가격 정책 격리 QA (이전 checkpoint)

- 시작 기준 local `HEAD`, live remote `work`는 `8808791057349c46dd37f4bab055c84a9fd04319`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. Codex Cloud에서 Docker 이미지 빌드나 production DB 접근을 하지 않았다.
- 세금 포함 상품 가격 구현은 고객 표시 가격을 기준으로 PrestaShop 저장가격을 환산하고, 선택 세금 규칙·주문 세액을 검증한다. 일본 규칙을 알 수 없을 때 실제 세금을 0으로 기록하지 않고 저장을 거부한다. 합성 10%는 CI 전용이며 법정 세율 근거가 아니다.
- 배송 QA는 격리된 run별 일본 전용 존·무료 운송사를 생성하고 Back Office 저장 후 PrestaShop을 재시작해 다시 읽는다. 일반 주문 QA보다 이 설정을 먼저 수행한다. 도쿄 PC 수량 2+쿠폰, 오사카 모바일 수량 1+쿠폰 없음, 과세 상품 주문, native 저장 데이터와 관리자 금액을 대조한다. 도쿄 검증 실패가 오사카 모바일 검증을 건너뛰지 않도록 했다.
- 리뷰에서 발견한 CI 결함 두 가지를 회귀 테스트로 먼저 재현했다. 일본 국가/상품의 MariaDB 조회는 SQL에 역슬래시가 포함된 따옴표를 넘겼고, Osaka QA는 Tokyo 단계 성공을 선행 조건으로 요구했다. 쿼리 인자 검증과 지역 단계 의존 조건을 수정했다. PWA 고객 생성 경로도 exact run/project/port 검사를 Chromium 시작 전에 요구한다.
- 로컬 정적 검증: 통합 QA 계약 182개, checkout·상품·브랜드 계약 75개, Japan Post updater 7개 통과. Python 구문, workflow YAML, 63개 step, 셸 60개, 고유 workflow step ID 40개, `git diff --check` 통과. PHP·DB·Chromium은 GitHub Actions에만 둔다.
- 독립 push 체크포인트: `561cba7487610c00b05e87dd71ce033f268c1394` (`feat(catalog): preserve tax-inclusive JPY sale prices`), `081e0b87b98773a6b2409e92c280babf3dc7580b` (`test(storefront): cover account and brand workflows`), `29766718481a2c594ab7aa7896bb563de784c856` (`test(checkout): verify taxable prices and free Japan shipping`). 각 push 후 `git ls-remote` SHA와 `origin/work` tracking ref를 대조하고 원격 파일을 다시 읽었다. `main`은 변경하지 않았다.
- Actions `39940265549`는 통합 workflow보다 먼저 실행되어 preflight 계약에서 실패했다. 통합 SHA `2976671`의 최신 run `39940305885`는 사전 계약과 이미지 빌드를 통과했지만 synthetic postcode fixture와 tax fixture가 각각 실패했다. 이후 상품·장바구니·계정·배송 브라우저 단계는 건너뛰었다. 로그 접근은 403 Forbidden이므로 다음 run에는 합성 주문 금액의 기대/관측 필드만 출력하도록 진단을 보강했다. Osaka `State.name`을 PrestaShop 9.2 scalar 모델에 맞게 수정했고, postcode 오류가 독립 browser QA를 중단하지 않게 aggregate 조건을 추가했다. 주문 확인 화면에서 상품 합계·배송·세금·최종 합계를 주문내역 이동 전에 대조한다. 새 격리 runtime QA와 artifact가 통과하기 전까지 브라우저·주문 결과를 PASS로 기록하지 않는다.
- Production DB/volume, 운영 배송 설정, 실제 결제는 변경하지 않았다. Actions QA의 두 일본 주소는 격리 테스트이며 일본 전 지역에 대한 운영 carrier 설정의 증거로 확장하지 않는다.

## 2026-10-22 — Actions 분리 기준 및 SEO escape 보안 체크포인트

- 시작 전 `work`와 `origin/work`는 `f8de2015d14cfefb5f25982bd56d781007d91ff3`, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. 미커밋 변경은 없었다. Codex Cloud에서 Docker `vfs`/32 GB 이미지 빌드를 재시도하지 않고 Docker·MariaDB·브라우저 실행을 GitHub Actions에 둔다.
- Draft PR #3 (`095d19baec40400e3b7c286e98af7886532290b2`)의 SEO diff를 검토했다. title/description/robots/canonical/hreflang/Open Graph 속성 값의 HTML escaping과 JSON-LD `JSON_HEX_TAG`를 적용하고, PR 검사에서 빠졌던 PWA `data-service-worker`·`data-scope`의 `$urls.base_url`도 escape하도록 보완했다. 기존 KURANEA 원본 자산은 변경하지 않았다.
- TDD: 새 SEO source contract를 먼저 실행해 현재 head template에서 2개 테스트 실패를 확인했다. 수정 적용 후 SEO contract 2/2, 기존 theme contract 15/15, `git diff --check`가 통과했다.
- `security(seo): escape dynamic metadata and JSON-LD` 커밋 `000b0661937c9d4f48e4408d7fb88598cd426e45`를 `work`에 push했다. 원격 SHA와 새 파일 내용을 확인했고, GitHub Actions SEO contract run `39786618881`이 성공했다. 해당 workflow는 source contract만 실행했으며 실제 PrestaShop/Smarty 렌더링은 검증하지 않았다.
- `main`은 변경하지 않았다. `work` checkpoint를 별도 `/tmp` clone으로 복제해 SHA와 세 변경 파일을 검증했다. ORDENOWA 공식 원본 ZIP은 아직 저장소나 작업공간에서 찾지 못해 이미지 배포는 대기 중이다.

## 2026-10-22 — P0 Docker 설치 후처리 실패 진단 및 로컬 수정

- 시작 기준: 원격 `work`는 `c2e3d9f11dc0cfeb3c116fde8d0c03274d7e88a3`, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. checkpoint clone에 있던 미커밋 카탈로그 파서·workflow·문서 변경을 보존했고 main이나 기존 개발 DB/named volume을 수정하지 않았다.
- 사용자가 전달한 run `39728912492` 로그에서 설치 CLI가 성공해 `/install`을 제거한 뒤, 공식 Docker 스크립트가 같은 경로를 다시 삭제하다 실패한 것을 확인했다. 스크립트는 `set -e`라 post-install hook과 뒤쪽 설치 완료 단계까지 진행하지 않는다. Compose `restart: unless-stopped`는 parameters 파일을 보고 `PrestaShop Core already installed` 분기로 재시작했고, first-install 전용 후처리를 건너뛰었다. 이후 HTTP 진입점에서 `var/cache/prod/appParameters.php` 누락 fatal이 발생했다.
- 검증 출처: 고정 이미지의 `/tmp/docker_run.sh` 원본 SHA-256 `422f08ac00c69614936f0eb2d9e5ea8316de6dd6e4b2fa5904720b1f901b9f2f`; PrestaShop 9.2.0 공식 `Install::postInstall()`은 `install.lock`, `Install::finalize()`는 install 디렉터리를 제거한다. 설정 캐시 파일은 실제 PrestaShop config bootstrap으로 생성되어야 하며 테스트나 초기화에서 가짜 파일은 만들지 않는다.
- 수정 후보: 두 중복 삭제를 대상 존재 시에만 수행하도록 고정 upstream 구문을 fail-closed patcher로 바꾼다. KURANEA bootstrap과 module setup을 first-install post hook에서 모든 시작 시 호출되는 init hook으로 이동해 최초 부팅·재시작에서 실행되게 한다. `/var/www/html/var/cache/prod`만 `www-data` 소유로 맞추고 신규 smoke에 `parameters.php`, 실 cache 파일, marker, 초기화 로그 및 재시작 실행 로그를 확인하도록 추가했다. PrestaShop PHP 코어는 변경하지 않았다.
- 검증: P0 회귀 계약 3/3, 관리자 경로 계약 4/4, 주소 갱신 계약 6/6, shell 구문 및 upstream 스크립트 복사본의 patch/idempotence 통과. 전체 storefront/smoke 계약의 기존 로컬 사이트 카테고리 3건은 빈 카테고리 URL에서 HTTP 500으로 실패했고 이는 이미 기록된 별도 결함이다. 로컬 Docker 설치/DB 접근은 공간 및 실행환경 문제 때문에 시도하지 않았다.
- 이 커밋은 원격 저장 및 신규 설치 Actions 실행 전이다. 코드 리뷰 후 `work`에 저장해 격리된 fresh-install workflow를 단 한 번 실행한다. 그때 신규 설치 성공이 확인되기 전까지 주문/address E2E는 PASS로 기록하지 않는다.

## 2026-10-22 — 관리자 폴더 설치 경로 후속 수정

- 원격 최신 SHA는 `175d75dac132ddb0a8f54777519795208df8ae4d`였다. 첫 수정 커밋의 Actions run `39727310686`은 이미지 빌드/정적 검사를 통과했지만 빈 DB 설치 단계에서 실패했다. 이 실행의 상세 로그는 현재 환경에서 404/접근 오류여서 실패 세부를 추정하지 않았다.
- 후속 후보는 `PS_FOLDER_ADMIN=admin-dev`로 공식 Docker entrypoint가 실제 관리자 파일을 `/admin-dev`에 놓게 한다. 공식 CLI 자산 설치가 반환된 뒤 post-install helper가 실행되고, PHP bootstrap의 official post-install 처리 이후 실제 감지한 관리 디렉터리를 `admin-kuranea`로 옮겨 최종 assets를 확인한다. 빈 관리자 디렉터리나 `chmod 777`을 사용하지 않는다.
- 테스트: 관리자 설치 순서 계약 4/4, 주소 갱신 계약 6/6, 관리자 번역 계약 8/8 통과. 전체 storefront smoke는 38건 중 35건 통과, 3개 언어의 빈 카테고리 URL에서 HTTP 500이 발생했다. 로컬 category 응답에는 `Category.php`와 `CategoryController.php`의 `foreach(false)` 경고가 있으나 원인 분석은 미완료다. `docker compose exec` PHP lint는 runc runtime 오류로 재시도 불가했다.
- 안전: overlay 여유 0 bytes·inode 100%, MariaDB unhealthy를 관찰했다. 실행 중인 컨테이너와 모든 named volume을 보존하고 재시작, DB 변경, prune, 재빌드는 하지 않았다. 동일한 이유로 신규 설치/실주문 검증은 하지 않았다.
- 현재 후속 코드는 로컬 수정이며 다음 원격 checkpoint SHA는 아직 없다. 코드와 이 기록을 `work`에 push/원격 SHA 확인한 뒤 fresh-install Actions를 확인하고, 성공 전에 주문 E2E를 실행하지 않는다.

## 2026-10-22 — PrestaShop 신규 설치 admin-dev 경로 오류

- 시작 기준: 로컬 `work`와 원격 `work`가 `4c6d38d7cf94506e2427c2fc904074055a070312`였고 원격 `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. 미추적 QA 캡처/JSON/pycache, 실행 중인 PrestaShop·MariaDB, 기존 named volume과 미연결 volume을 보존했다.
- 신규 원인: 최신 Actions 로그의 `assets:install admin-dev --symlink=1` 오류를 PrestaShop 9.2.0 `Install::finalize()`와 Docker 시작 순서에 대조했다. Docker가 설치 전에 `/admin`을 `admin-kuranea`로 이동해 CLI 설치기가 존재하지 않는 `admin-dev`를 target으로 선택했다. 과거 `errno 28`은 이전 실패 기록이며 이번 직접 원인으로 취급하지 않는다. 공식 이슈는 PrestaShop #40348 및 Docker #465다.
- 변경: Compose 신규 설치에는 `PS_FOLDER_ADMIN=admin`, 최종 이름은 별도 `KURANEA_ADMIN_FOLDER=admin-kuranea`로 분리했다. post-install helper가 설치기가 감지한 관리자 경로를 확인하고, 대상 충돌을 거부한 뒤 최종 경로로 이동하고 공식 `AssetsInstaller`를 다시 호출한다. 최종 폴더와 관리자 CSS/로그인 URL 검증을 smoke에 추가하고 CI에서 경로 순서 계약을 확인한다. 코어, 기존 DB, named volume은 수정하지 않았다.
- 테스트: 회귀 계약은 구현 전 3건 실패를 재현한 뒤 3/3 통과, 기존 fresh-install workflow 계약과 합계 10/10 통과했다. PHP lint, shell syntax, `docker compose config --quiet`, `git diff --check`도 통과했다. 실제 신규 설치는 작업공간 85 MB 여유로 로컬 실행하지 않았다.
- 보존: 커밋 `175d75dac132ddb0a8f54777519795208df8ae4d`를 즉시 원격 `work`에 push했다. `git ls-remote`, `origin/work`, 로컬 HEAD가 일치하고 원격 파일을 재조회했다. 새 shallow clone `/tmp/kuran-recovery-175d75d`의 HEAD와 helper/회귀 테스트 복구를 확인했다. `main`은 그대로다. Actions run `39727310686`은 이미지 빌드·사전 계약 검사를 통과했고 격리 설치 결과는 아직 진행 중이다.
- 다음: 동일 CI 실행에서 빈 설치, ja/en/ko, KURANEA theme, 최종 `admin-kuranea` assets/login, 재시작 보존을 확인한다. 실패하면 로그에서 새 직접 원인을 확인하고 필요한 수정만 별도 체크포인트로 저장한다. 이후 실제 storefront checkout/browser order를 격리 runner에서 검증한다.

## 2026-10-22 — 주소 데이터 안전성·갱신과 환경 상태 점검

- 시작 기준: 로컬 `HEAD`, `origin/work`, GitHub `work` 원격 SHA가 `1690a073bc25f38d3c02cc7616dd7b8f9f5a3cc7`로 일치했다. `main`은 `ee02a3657448d563508687614a246e05ac61eecd`다. 기존 미추적 브라우저 캡처와 테스트 캐시는 변경하거나 삭제하지 않았다.
- 주소 코드 체크포인트: `06617f6`에서 Japan Post의 설명용 `（次のビルを除く）`를 고객 주소에서 제거하고 `以下に掲載がない場合`를 상세 주소 빈값으로 처리했다. `a444238`은 공식 `1000004` 주소 검증이 `大手町`를 정확히 기대하게 했다. `1690a07`은 공식 KEN_ALL ZIP을 검증한 뒤 기존 트랜잭션 importer를 실행하는 수동 갱신 CLI를 추가했다. 세 체크포인트 모두 `work`에 푸시 후 원격 SHA와 파일 재조회를 확인했다.
- 검증: Python smoke/CI 계약 34/34, 관리자 번역 계약 8/8, 주소 갱신 CLI 계약 6/6, workflow 계약 7/7 통과. PHP 도메인/후보 응답 테스트 및 기존 DB read-only 통합 주소 검증, PHP lint, JavaScript·shell 문법, `docker compose config --quiet`도 통과했다. 이 turn에는 주소 데이터를 다시 적재하거나 고객·주소·주문 행을 만들지 않았다.
- CI 상태: run `39703327857`, `39704824787`은 이미지 빌드와 격리 캐시 권한 검사 뒤 `Start the empty-volume shop`에서 실패했다. 공개 실행 목록에서 후속 `39705702536`, `39706052890`, `39706126218`도 Failure로 확인했다. 마지막 run은 `1690a07`에서 2분 39초 후 실패하고 3.37 KB artifact(SHA-256 `5ba78e90152543f775930472455c8434fae47018303373b8a93711506dcb2500`)를 생성했다. GitHub 페이지는 로그 열람에 로그인하라고 표시하며 API `403`, artifact 익명 다운로드 `404`다. 최신 실패 단계와 `errno 28` 여부는 확인할 수 없어 추측하지 않는다.
- 상품 수집 접근: Amazon Japan 및 Rakuten 공개 홈페이지에 보낸 읽기 전용 HTTPS 요청은 개발환경 egress proxy CONNECT `403`으로 차단됐다. 허용되지 않은 도메인을 통한 우회는 하지 않았고 실제 상품을 scrape/등록하지 않았다. 현재 사용자 제공 개별 상품 URL과 HTML fixture도 저장소에 없다.
- 환경: cloud status의 활성/관측 revision은 2다. 저장 draft revision 4는 checkout `2db98927a9ede2b2423456873f0994ddd19ffe4e`를 가리켜 현재 `work`와 일치하지 않는다. 유효 egress 목록에는 `api.github.com`이 없다. 사용자가 언급한 revision 3의 적용 증거는 없으며 설정을 수정·게시하지 않았다.
- 보존: 작업공간 여유는 약 86 MB, inode 사용률 95%다. Compose의 healthy PrestaShop/MariaDB와 모든 기존 named volume을 보존했다. Docker prune·재빌드·DB 초기화는 수행하지 않았다. 사용자가 첨부한 공식 브랜드 ZIP의 세 이미지 SHA-256은 `assets/brand/source/` 원본과 모두 일치했다.
- 다음: 먼저 새 빈 볼륨 CI의 상세 stderr를 접근 가능한 환경에서 확보하고 설치를 통과시킨다. 그 다음 실제 checkout/주문 저장, 상품 파서와 상품 등록, 관리자 한국어 범위, PWA를 독립적으로 검증한다. 실제 상품 URL/fixture가 없고 상품 파서 구현도 아직 없어 외부 사이트 상품을 수집하거나 실제 상품처럼 등록하지 않았다.

## 2026-10-22 — Japan Post 배송지의 격리 주문 저장 QA 추가

- 시작 기준: 원격 `work`와 로컬 `HEAD`가 `9a187efbb465c622b1e13afe18ed3f5d34aaf119`로 일치했고, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. 기존 미추적 파일과 두 활성 named volume을 보존했다.
- 변경: `tests/postcode/verify_native_order_persistence.php`는 `CI=true`, `GITHUB_ACTIONS=true`, 실행 ID·시도·고유 Compose 프로젝트 이름이 맞을 때만 작동한다. 고유 CI DB에서 공식 오프라인 `ps_checkpayment`, CI 전용 무료 배송사와 상품, 일본우편 `1000004` 배송지·수정 건물명, 실제 `PaymentModule::validateOrder()` 주문 저장, `id_address_delivery`, Back Office `GetOrderForViewing` 주소 projection을 확인하도록 추가했다. workflow가 실행 ID 환경을 전달한다.
- 추가 발견: CI 설치 계약 테스트 4개가 기존 합쳐진 step 이름을 찾고 있어 분리된 새 workflow를 대상으로 실패했다. 테스트를 개별 이미지 빌드·캐시 권한 probe·Compose 시작·공통 실패 진단 구조에 맞게 업데이트했다.
- 검증: smoke 및 CI 계약 34/34, 관리자 번역 계약 8/8, 주문 스크립트 PHP lint, postcode 도메인 및 read-only live address 검증, Compose 설정, 실제 storefront HTTP 200을 확인했다. 로컬 DB의 주문 0건·상품 0건을 읽기 전용 조회로 재확인했다. 관리자 주문 목록은 한국어 PC 1440×1000·모바일 390×844에서 HTTP 200, 브라우저 오류 0건이며 캡처를 저장했다. 빈 목록이라 주문별 주소 표시는 확인하지 못했다.
- 빈 설치 CI: run `39703327857`과 주문 스크립트를 포함한 `39704824787` 모두 이미지 빌드·캐시 권한 probe PASS 후 `Start the empty-volume shop`에서 실패했다. 진단 단계/artifact 업로드는 완료됐지만 이 환경의 GitHub API·익명 artifact 접근 제한으로 본문 로그를 읽지 못해 root cause 및 `errno 28` 여부를 확정하지 않았다. 두 run 모두 설치 완료 전 주문 검증은 건너뛰었다.
- 환경·데이터 보존: cloud spec revision은 실제 status에서 2로 확인되어 요청된 3이 미적용이다. 로컬 workspace는 91 MB 여유, inode 95%여서 로컬 이미지 재빌드를 하지 않았다. 기존 `kuranea_mariadb_data`, `kuranea_prestashop_html`, 알 수 없는 미연결 볼륨을 초기화하거나 삭제하지 않았다.
- 원격 checkpoint: `1f5f552316a7e9b860ff551b8998e14313f8bac0`을 `work`에 푸시하고 `git rev-parse`, `git ls-remote`, `git show origin/work:<file>`로 SHA와 주문 테스트·workflow 파일을 재조회했다. `main`은 변경하지 않았다.
- 미완료: 새 빈 설치와 주소 적재, CI 네이티브 주문 및 관리자 주소 projection은 미검증이다. Back Office 전체 한국어 100%, PWA 실제 설치, 실제 checkout 브라우저 주문도 미완료다.

## 2026-10-22 — 빈 카탈로그 메인 화면 보완

- 시작 기준: `work` 로컬·원격 SHA `15a3d82de3df746994eac88c194bdf3caf4e1779`, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`; 기존 미추적 파일과 named volume을 보존했다.
- 원인: Hummingbird `ps_featuredproducts::getWidgetVariables()`는 상품이 없으면 `false`를 반환해 테마 모듈 템플릿을 호출하지 않는다. 실행 중인 PrestaShop은 수정 전 Smarty 컴파일본과 CSS 합본 캐시도 사용하고 있었다.
- 변경: 자식 테마 메인 템플릿에 ja/en/ko 안내와 검색 링크를 넣고, 실제 featured product list가 있을 때만 안내를 숨긴다. 모듈 템플릿은 Hummingbird의 네이티브 상품 카드 출력을 유지한다. CSS는 작은 화면에서 문구와 링크를 세로로 배치한다.
- 검증: 상품 상태 계약 테스트를 먼저 실행해 실패를 확인한 뒤 구현했다. Smarty 홈 컴파일 캐시와 CSS 합본 한 파일만 `/tmp`에 백업 후 무효화해 재생성했다. 실제 페이지 HTTP 200, ja/en/ko 홈 문구, Chromium 데스크톱 1440×1000 및 모바일 390×844, 수평 넘침 0, 브라우저 오류 0을 확인했다. Python smoke/계약 27/27, 관리자 계약 6/6, postcode PHP lint 및 도메인/API 단위 테스트 통과, `docker compose config --quiet`, healthy 컨테이너 및 `git diff --check` 확인.
- 캡처: `artifacts/qa/phase1a/home-empty-state-desktop-v2.png` 및 `home-empty-state-mobile-v2.png`.
- 범위: 실제 상품이 아직 0개이므로 상품 카드의 숨김 조건은 계약 검사로 확인했고, 실상품 카드 UI는 아직 브라우저에서 검증하지 않았다. DB와 기존 주문은 변경하지 않았다.
- GitHub 보존: 기능 커밋 `1af5fda05285b423baad2c7751bb7898c3257caa`를 `work`에 푸시하고 `git ls-remote`·`origin/work`와 비교했다. 별도 shallow clone `/tmp/kuranea-checkpoint-1af5fda`에서 같은 HEAD, 템플릿, 두 캡처 파일의 SHA-256을 재확인했다. `main`은 변경하지 않았다.

## 2026-10-21 — 검색 다국어와 모바일 내비게이션 대비 개선

- 시작 기준: `work` 원격 SHA `d1b2166d6380348e855989b6dbe79650cc9ecedc`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다.
- 원인: Hummingbird의 검색 템플릿은 `Search products...`를 일본어·한국어에도 출력했고, 모바일 하단 메뉴는 `#fffefa` 배경 위에서 푸터 링크 색상 `#e9e5dc`를 상속해 대비가 약 1.25:1이었다.
- 변경: Hummingbird 원본은 유지하고 KURANEA 자식 테마의 `ps_searchbar` 템플릿 오버라이드를 추가해 일본어·영어·한국어 검색창과 검색 관련 접근성 문구를 현지화했다. 모바일 메뉴에 `#footer` 고특이도 선택자를 적용해 브랜드 잉크색으로 표시한다.
- 검증: locale별 검색 문구 smoke를 포함한 smoke 19/19 PASS. 실제 Chromium에서 데스크톱 1440×1000·모바일 390×844를 열어 HTTP 200, 올바른 `ja-JP` 및 검색 문구, 모바일 메뉴색 `rgb(23, 38, 56)`, 가로 넘침 없음, 페이지 오류 0건을 확인했다. 캡처: `artifacts/qa/phase1a/home-desktop-locale-contrast.png`, `home-mobile-locale-contrast.png`.
- 미완료: 푸터의 일부 링크 문구가 영어이며, 기본 통화는 아직 EUR이고 상품 카탈로그는 비어 있다. 해당 사항은 후속 작업으로 남긴다. 기존 상품/주문 데이터와 named volume은 변경하지 않았다.

## 2026-10-21 — 신규 설치 CI의 공식 우편 CSV 경로 복구

- 시작 기준: `work` 로컬·원격 SHA `ec2059c519121e0a73640b75e6f62be95a1f1797`, `main` SHA `ee02a3657448d563508687614a246e05ac61eecd`; 기존 미추적 QA 캡처와 테스트 캐시는 그대로 보존했다.
- 실패 증거: GitHub Actions 실행 #9 `39692749750` 및 #8 `39691897612`는 `Build and install into unique empty volumes` 단계에서 실패했다. 공개 실행 페이지에서는 상세 로그가 차단되어 원래 stderr는 확인되지 않았다.
- 원인 확인: Actions의 기존 Japan Post KEN_ALL 주소는 HTTP 404였다. 공식 다운로드 페이지에서 확인한 `/service/search/zipcode/download/kogaki/zip/ken_all.zip`은 HTTP 200 및 ZIP 응답을 반환했다.
- 변경: 신규 설치 Actions에서 Compose 기동 실패 시 해당 격리 실행의 파일시스템·Docker 사용량, 컨테이너 상태와 제한된 서비스 로그를 즉시 출력하도록 했다. Japan Post 공식 CSV 경로를 수정하고, 두 동작을 고정하는 회귀 계약 테스트를 추가했다.
- 검증: 회귀 계약 2/2, 전체 smoke 16/16 PASS; 공식 URL HEAD 200, Compose YAML parse 및 `docker compose config --quiet` PASS. 격리된 GitHub Actions 신규 설치 결과는 새 실행이 끝나기 전까지 미검증이다.
- 데이터 보존: 로컬 overlay에는 약 197 MB 여유와 95% inode 사용률이 남아 있어 Docker 빌드·prune을 실행하지 않았다. 기존 `kuranea_mariadb_data` 및 `kuranea_prestashop_html` 볼륨과 실행 중인 컨테이너를 유지했고, DB에는 주소 CSV를 가져오지 않았다.

## 2026-10-21 — PrestaShop 9 주소 조회 응답 및 신규 설치 요청 보강

- 시작 기준: `work` 로컬 HEAD 및 원격 SHA `6044653535c7e37d88c2b6c2c23bd22d7eb3f3f0`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다.
- 원인: PrestaShop 9.2에서 이전 응답 API `Tools::jsonEncode()`와 `ajaxDie()`는 사용할 수 없어 postcode 후보 라우트가 503을 반환했다. 테스트 더블도 존재하지 않는 `ajaxDie()`를 제공해 실제 코어 동작을 잘못 모사하고 있었다.
- 변경: 컨트롤러는 표준 `json_encode()`와 PS9 `ajaxRender()`로 상태 코드가 포함된 JSON을 출력하고 종료한다. 주소 테스트는 격리된 PHP 자식 프로세스에서 `ajaxRender()` 응답을 받아 검증한다. 빈 설치 CI의 주소 조회 `curl`에는 canonical-host 리다이렉트 추적을 추가했다.
- 검증: 기존 실행 중인 쇼핑몰에서 주소 lookup 경로 HTTP 200, JSON 응답, `manual_entry_available=true`를 확인했다. 응답 후보는 0개이며 공식 Japan Post CSV가 아직 적재되지 않았으므로 실제 `100-0004` 주소 매핑은 PASS로 기록하지 않는다. 스모크 13/13, 관리자 계약 테스트 6/6, postcode PHP 도메인·컨트롤러 테스트, PHP lint 통과.
- 보존: 실행 중인 PrestaShop/MariaDB와 named volume은 초기화하거나 삭제하지 않았다. GitHub Actions API는 이 환경에서 `403 Forbidden`을 반환해 신규 빈 DB 설치 결과를 직접 확인할 수 없었다.

## 2026-10-21 — 관리자 로그인 한국어·공식 로고 및 모듈 파일 권한

- 시작 기준: 주소 기능 체크포인트 `6531d64f419e24867f5aff6832ef240c7fa7762c`가 원격 `work`와 일치했다.
- 원인: 기존 Back Office의 `AdminGlobal` 한국어 XLIFF에는 Dutch 대상 문자열이 남아 있었고, PrestaShop 번역기는 XLIFF 뒤에 DB 번역 리소스를 붙여 단순 `addResource()` 오버레이보다 DB 문자열이 우선했다. 컨테이너에 수동 복사한 로컬 파일도 호스트 `0600` 모드가 전파되어 `www-data`가 읽지 못했다.
- 변경: Back Office 모듈이 한국어 XLIFF를 완성된 번역 카탈로그 뒤에 병합해 DB 값보다 우선하도록 했다. 로그인 화면은 제공된 공식 로고를 이미지로 표시하고 PrestaShop 상단·푸터 브랜딩을 감춘다. `docker/kuranea-entrypoint.sh`는 두 KURANEA 모듈 트리만 `www-data` 소유·디렉터리 0755·파일 0644로 동기화하고, fresh-install QA가 해당 파일을 실제 `www-data`로 읽을 수 있는지 확인한다.
- 브라우저 검증: 실제 관리자 로그인 데스크톱 1440×1000과 모바일 390×844에서 HTTP 200, `lang=ko`, 비밀번호 라벨 한국어, 공식 로고 표시, stock header/footer 숨김, 가로 넘침 없음, 페이지 오류 0건을 확인했다. 캡처는 `artifacts/qa/phase1a/admin-login-desktop-brand-fix.png`, `admin-login-mobile-brand-fix.png`에 저장했다.
- 제한: 로그인 외 관리자 전체 메뉴·대시보드의 한국어 100%는 아직 검증되지 않았다. 새 빈 DB Actions 실행과 공식 Japan Post CSV 실데이터 lookup도 아직 미확인이다.

## 2026-10-21 — Phase 1A 일본어 홈 UI 및 반응형 QA

- 시작 SHA: 로컬 `work`와 GitHub 원격 `work`가 모두 `34b97b6982e42361018f1746eb0214efe5fe366b`였다. 기존 컨테이너와 named volume은 유지했다.
- 변경: 홈 편집 문구와 하단 모바일 메뉴를 일본어·영어·한국어로 적용하고, Hummingbird 데모 배너를 홈에서 숨겼다. 뉴스레터 입력 대비와 공식 워드마크 크기를 조정했다.
- 검증: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/smoke -v` 12개 통과. 실제 브라우저에서 데스크톱 1440px과 모바일 390px을 열어 HTTP 200, `ja-JP`, 가로 넘침 없음, 브라우저 오류 0건을 확인했다. 현재 캡처는 `artifacts/qa/phase1a/home-desktop-current.png`, `home-mobile-current.png`, `admin-login-current.png`, 결과는 `browser-results-current.json`에 보존했다.
- 제한: 기존 카탈로그에 상품이 없어 유효한 카테고리·상품 상세 경로와 주문 흐름은 검증하지 않았다. 관리자 로그인은 접근 가능하지만 한국어/공식 관리자 로고 적용 전 상태로 촬영했다. 이번 UI 소스는 로컬 검토용으로 기존 webroot에 복사했으며, Compose 이미지는 빌드·배포하지 않았다.

## 2026-10-21 — 일본 우편번호 모듈 및 관리자 한국어 기반

- 변경: `kuraneapostcode` 모듈이 7자리/하이픈/전각 우편번호, 일본어 주소 검색, 복수 후보, 수동 입력, 공식 KEN_ALL CSV 가져오기, 일본어·영어·한국어 문구와 네이티브 주소 매핑을 제공한다. `kuraneabackoffice`는 익명 로그인 한국어 context, 제공된 공식 로고 hook, 누락 번역 overlay의 시작 범위를 제공한다.
- 런타임 경로: Compose 이미지가 두 모듈을 포함하고 기존 설치에서도 멱등 설치 helper를 실행하도록 연결했다. 신규 빈 설치 CI는 별도 GitHub-hosted project/volume을 사용해 공식 Japan Post CSV 다운로드·가져오기, 실제 `1000004` lookup, 수동 건물명이 있는 네이티브 Address 저장, 관리자 로그인 브랜드/한국어, 재시작 후 테이블 유지를 검증하도록 구성했다.
- 로컬 검증: smoke 12/12, 관리자 overlay 5/5, 우편번호 도메인 테스트 통과, 모듈 PHP lint 및 helper PHP lint 통과, JS 구문 검사, 셸 구문 검사, XLIFF XML 파싱, `docker compose config --quiet`, `git diff --check` 통과.
- 미검증: 공식 CSV 네트워크 다운로드와 실제 `1000004` 통합 테스트는 GitHub Actions 실행이 완료되어야 PASS로 기록한다. 브라우저 주소 입력/주문 생성/관리자 주문 화면도 아직 미검증이다. 기존 DB/named volume은 변경하지 않았다. 한국어 관리자 전체 화면 100%는 미완료이며 로그인 및 소수 번역 보완 코드만 검토했다.

## 2026-10-21 — 빈 설치 캐시 권한 P0 수정

- 시작 상태: `work`의 로컬 및 GitHub 원격 SHA가 `6ddf52b0b3dc63a873bb39019fd93060a9d4b645`로 일치했고, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다.
- 원인 근거: 공식 컨테이너의 `/tmp/docker_run.sh`는 `/tmp/data-ps/prestashop`에서 webroot로 파일을 복사한 뒤 `/tmp/pre-install-scripts/`를 실행하고, 설치 CLI를 `www-data` 사용자로 시작한다. 설치 전후 캐시 소유권을 보정하는 프로젝트 hook은 없었다.
- 변경: `var/cache/prod`만 대상으로 하는 pre-install hook을 추가해 설치 CLI보다 먼저 `www-data:www-data` 소유권을 설정한다. 전체 권한을 열거나 기존 DB·named volume을 초기화하지 않는다.
- 검증: 스모크·테마 계약 테스트 11개 PASS, pre-install 셸 구문 검사 PASS, `docker compose config --quiet` PASS, `git diff --check` PASS.
- 제한: 이번 실행환경의 빈 named volume 신규 설치는 아직 재검증하지 않았다. 실제 PASS는 격리된 GitHub Actions runner의 성공 결과를 확인한 뒤 기록한다.

### P0 원인 범위 축소 — CI assertion 추가

- 소스 검토로 확인: KURANEA entrypoint가 CA 파일을 위해 `var/cache/prod`를 root로 먼저 만들고, 공식 PrestaShop 파일 복사 원본에는 이 하위 디렉터리가 없다. 따라서 installer가 `www-data`로 실행될 때 디렉터리 쓰기 권한이 없을 수 있다. 실패한 Actions 상세 로그는 현재 GitHub API에서 403으로 접근되지 않아 이 원인은 소스 기반 진단이다.
- 후속 수정: pre-install hook은 `var/cache/prod` 디렉터리의 소유자만 `www-data`로 설정한다. CI 설치 스크립트에는 디렉터리와 `class_index.php` 소유자, `www-data` 쓰기 가능 여부 검사를 추가했다.
- 신규 빈 볼륨 결과는 GitHub Actions 완료 후 별도로 기록한다.

## 2026-10-21 — PWA manifest 경로 및 storefront smoke 보강

- 변경: PrestaShop의 제한된 테마 디렉터리 접근 정책을 피하도록 manifest를 webroot `/manifest.webmanifest`에서 제공하고, HTML의 manifest 링크를 그 경로로 갱신했다. smoke 테스트는 manifest의 `ja-JP`와 아이콘 크기를 확인한다.
- 검증: 기존 실행 사이트에서 manifest HTTP 200 및 JSON을 확인했다. 10개 뷰포트에서 일본어 문서 언어, HTTP 200, 가로 넘침 없음, 브라우저 페이지 오류 0건을 기록했다. service worker 범위는 루트이고 Cache API 목록은 비어 있으며, 네트워크 실패 시 503 오프라인 안내를 확인했다.
- 범위 제한: 카테고리 캡처 URL은 현재 홈페이지로 리다이렉트되어 카테고리 화면 검증으로 인정하지 않는다. 현재 카탈로그가 비어 있어 상품 상세·주문과 실제 기기 설치도 검증하지 않았다.

## 2026-10-21 — JPY 기본 통화 및 재시작 smoke 검증

- 시작 기준: `work` 로컬 및 원격 SHA `69a99c4ef6f14882d7151ea109e86a47d2c4d2a8`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다. 로컬 변경과 미추적 QA 산출물을 먼저 점검하고 기존 파일을 삭제하거나 초기화하지 않았다.
- 변경: 신규 설치와 기존 설치 helper가 같은 멱등 JPY 부트스트랩을 사용하도록 했다. 기본 통화는 JPY, 정밀도는 0, ja/en/ko 표시명을 설정한다. 확인된 환율이 없는 EUR/USD는 비활성화한다. 신규 설치 smoke는 재시작 후 JPY 기본값과 3개 언어 번역을 다시 검사한다.
- 테스트: smoke 23/23, 관리자 계약 테스트 6/6, 우편번호 도메인·후보 API 테스트, PHP lint, shell/JS 문법, Compose 설정, `git diff --check` 통과. 기존 DB 읽기 전용 조회에서 JPY 활성/기본값 및 ja/en/ko 이름을 확인했고 상품/주문은 각각 0건이었다.
- 제한: 새 빈 볼륨 Actions run `39693892012`는 `Build and install into unique empty volumes`에서 실패했다. 익명 로그 및 무효한 현재 `GH_TOKEN`으로 상세 로그를 열지 못했으므로 설치 성공은 PASS로 기록하지 않는다. 공식 CSV 적재, 저장주소/주문/관리자 주문 화면, 관리자 전체 한국어, PWA 실기기 설치는 미완료다.
- 환경/보존: 관측된 cloud environment revision은 2로, 요청된 3이 적용되지 않았다. workspace 여유는 약 194 MB이고 inode 사용률은 95%다. 실행 중인 컨테이너, DB 데이터 및 named volume을 보존했고 prune/재빌드/초기화를 실행하지 않았다.

### 검증 추가 — 공식 우편 CSV 및 기존 볼륨 재시작

- Japan Post 공식 `ken_all.zip`을 내려받아 SHA-256 `c976cb0ff691a1aa7480b47b7e1f61bea08c2eadb3278f0366e474cd82dbf4b8`를 기록했다. 최신 CSV 124,840행을 기존 모듈 importer로 메모리 파싱했으며 저장 DB를 건드리지 않았다.
- PASS: `1000004`/`100-0004`가 각각 같은 실제 후보 1개를 찾고, `千代田区大手町` 부분검색 결과에 해당 주소가 포함됐다. 공식 CSV의 중복 우편번호 `004-0000`에서 서로 다른 후보 2개를 선택했고, `1000004` 후보가 `id_state`/도시/町域과 고객 입력 건물명을 네이티브 주소 필드로 보존했다.
- 기존 MariaDB/PrestaShop 컨테이너만 재시작했다. 두 컨테이너 healthy 및 쇼핑몰 HTTP 200을 확인하고 JPY 기본값·3개 언어 행·상품 0건·주문 0건을 읽기 전용 조회했다. 기존 named volume은 유지했다.
- 범위 제한: 위 공식 데이터 검증은 parser와 in-memory lookup까지다. 데이터베이스/API/checkout 주문 저장/Back Office 주문 화면 통합은 새 빈 볼륨 Actions 실패를 해결한 뒤 실행한다.
- 체크포인트: 구현 커밋 `ec7af91b66bdb31a36ea073957fdd8c7d428d334`를 `work` 원격과 대조했다. `git show`로 원격 PHP helper와 개발 현황 문서를 다시 읽고 데스크톱·모바일 증거 PNG 존재를 확인했다. 원격 `main`은 그대로다.

## 2026-10-21 — 신규 설치 실패 진단 가시성

- 확인: GitHub Actions run `39694912661`도 `Build and install into unique empty volumes` 단계에서 실패했다. 익명 Actions 화면은 상세 stderr/stdout을 숨기며 현재 `GH_TOKEN`은 유효하지 않고 Git credential helper에도 Actions 읽기 자격 증명이 없었다. 기존 로그의 원인을 추측해 설치 성공으로 보고하지 않았다.
- 변경: 실패 시 Docker 사용량, 디스크/inode, 격리 Compose 상태, 서비스 최근 160줄을 수집해 비밀번호/토큰 형태를 제거하고 `$GITHUB_STEP_SUMMARY`와 job log에 출력하도록 워크플로우를 보완했다.
- 검증: 전체 smoke 24/24, CI 워크플로우 계약 3/3 PASS. GitHub Actions `run:` bash 블록을 추출해 `bash -n` 및 모의 Docker 실패 실행을 했고, summary에 실패 진단이 포함되며 `MARIADB_ROOT_PASSWORD` 예시 값은 `[REDACTED]`로 변환됨을 확인했다. 새 Actions 실행 결과는 푸시 뒤 확인한다.
- 안전: 로컬 컨테이너/named volume을 조작하지 않았고 Docker prune/build를 실행하지 않았다.
- 원격 보존: `62690b81bcee67a6589981a6004956131e974943`를 `git ls-remote` 및 `origin/work`과 대조했다. 원격 workflow와 계약 테스트를 `git show`로 다시 읽었다. `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다.

## 2026-10-21 — 신규 설치 CI 진단 마스킹 및 artifact 보존

- 시작 기준: 로컬과 원격 `work` SHA `1238c7cc0a7e1590b4eb372b2dbb80d68dd8580c`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다. 기존 미추적 QA 캡처·테스트 캐시는 그대로 뒀다.
- CI 증거: run `39695319325` (`62690b81bcee67a6589981a6004956131e974943`)는 2분 15초 뒤 `Build and install into unique empty volumes` 단계에서 실패했다. 공개 job 화면은 exit code만 보였고 GitHub API 호출은 403을 반환해 원인을 검증할 상세 요약/로그에 접근하지 못했다.
- 변경: 시작 단계와 이후 실패 단계가 공통 수집기를 사용한다. Docker 상태와 최대 160줄의 서비스 로그를 마스킹한 뒤에만 stdout·step summary·2일 보존 artifact에 쓴다. 시작 실패 후 후속 단계에서 원시 서비스 로그를 다시 출력하던 경로를 제거했다.
- 검증: 테스트 우선으로 수집기 부재 시 회귀 테스트 실패를 확인한 뒤 구현했다. 전체 smoke 26/26, admin locale 계약 6/6, bash 구문, workflow YAML 파싱, `docker compose config --quiet`, `git diff --check` 통과. 현재 실행 중인 컨테이너와 named volume은 유지했고 Docker 빌드/prune을 하지 않았다.
- 원격 보존: `f636d40738c217f9c1f587b50c70742789583d99`를 `work`로 푸시한 뒤 로컬 HEAD·`git ls-remote`·`origin/work`이 일치하는 것을 확인하고 원격 workflow/수집기/회귀 테스트를 다시 읽었다. 이 커밋은 run `39695971760`을 시작했으며 마지막 확인 시 실행 중이었다.
- 후속 검증: run `39695971760`은 2분 32초 뒤 같은 시작 단계에서 실패했다. 공개 run 페이지에서 `fresh-install-diagnostics-39695971760-1` artifact ID `12391041696`, 크기 3.71 KB, digest `sha256:d2dbb7b5a52cf41d8fd4663c4823cf0b8bd1d8af6c4ed35a5a2642184bcfabd0`를 확인했다. artifact 본문과 상세 job 로그는 이 환경에서 다운로드/API 403/404로 접근할 수 없어 근본 원인을 추측하거나 PASS로 기록하지 않았다.

## 2026-10-22 — 공식 주소 데이터 로컬 통합 및 staging 공간 회수

- 시작 보호 확인: 현재 `work` 로컬/원격 SHA `e84fb2a238ef6f999d8d508e422c87f0b68e7dff`가 일치했고 `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지됐다. 기존 미추적 QA 캡처와 pycache는 삭제·초기화하지 않았다. MariaDB와 PrestaShop 컨테이너 및 named volume은 계속 실행 상태로 보존했다.
- 공식 주소 데이터: Japan Post 공식 `ken_all.zip`의 SHA-256 `c976cb0ff691a1aa7480b47b7e1f61bea08c2eadb3278f0366e474cd82dbf4b8`을 기록하고 CSV 124,840행을 파싱했다. 기존 DB의 모듈 주소 테이블에 고유 후보 124,839건을 적재했다. `1000004`와 `100-0004` 모두 도쿄도·지요다구·오테마치를 반환했고, `千代田区大手町` 검색과 복수 주소 `004-0000`의 후보 2개를 HTTP API에서 확인했다.
- 디스크 안전: import 뒤 active와 staging 테이블이 같은 데이터 124,839건을 보유하는 것을 양방향 전체 비교로 확인했다. 기존 주소 테이블을 유지하면서 staging 테이블만 비웠다. 주소 행은 124,839건 유지되고 staging은 0건이며 workspace 가용 공간은 42 MB에서 118 MB로 늘었다. 운영 중인 named volume, 기존 고객·주문 데이터는 초기화하지 않았다.
- 코드: importer가 새 주소 데이터의 `COMMIT` 성공 뒤에만 staging 복사본을 비우도록 수정하고, 빈 설치 smoke가 staging 행 0개를 확인하게 했다. 실패한 가져오기는 기존 active 데이터를 교체하지 않는다.
- 브라우저: 실제 사이트 origin의 모듈 JS와 DB-backed API를 주소 폼 계약 fixture에 연결했다. PC 1440×900 및 모바일 390×844에서 `1000004` 후보 선택, 도도부현/도시/町域 매핑, 일본어 문자열 검색, `004-0000`의 복수 선택, 건물명 수동 편집 보존을 확인했다. 브라우저 JS 오류는 0건이다. 증거 PNG는 `artifacts/qa/phase1a/postcode-widget-desktop.png`, `postcode-widget-mobile.png`다. 실제 checkout 페이지·주문 저장 화면은 아니므로 해당 검증은 미완료다.
- 테스트: smoke/계약 28/28, 관리자 번역 계약 6/6, PHP importer lint, 주소 도메인 및 후보 API 테스트, `bash -n`, `docker compose config --quiet`, `git diff --check` 통과. 관리자 한국어 100%와 실제 checkout 주소/주문 및 관리자 주문 표시 검증은 미완료다.
- 신규 설치/환경: 새 빈 설치 run `39697612835`가 `Build and install into unique empty volumes`에서 2분 38초 후 실패했다. 이 실행환경에서는 상세 로그와 artifact를 읽을 수 없어 errno 28 재현 여부를 확정하지 못했다. 로컬 workspace는 117 MB 여유, inode 사용률 95%여서 Docker 재빌드를 하지 않았다. 관측된 클라우드 environment revision은 2이며 사용자 지정 revision 3은 적용 증거가 없다.
- 커밋 범위는 importer·관련 테스트/CI 체크와 해당 브라우저 증거만 명시적으로 stage했다. 미추적 QA 캡처와 pycache는 그대로 보존했다.

## 2026-10-22 — 다국어 storefront 상태 및 QA 캡처

- 시작 시 로컬 `HEAD`, `origin/work`, 원격 `work`가 `b437e2dc6af0f7548f840103d537c9b03e74e708`에서 일치했고 `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다.
- 자식 테마에 일본어·영어·한국어 검색 및 빈 카테고리 상태, footer 링크/accessibility 문구를 추가했다. PC 1440px, 모바일 390px 캡처와 ja/en/ko 페이지 검증을 저장했다. smoke/contract 33/33 통과.
- 커밋 `2636d67cb1d155d5f9993a2476292d6fe11970e8`를 `work`에 push하고 `git ls-remote`, `origin/work`, remote file re-read로 확인했다. CI run #18 `39701030162`는 실패했다.

## 2026-10-22 — 주소 저장 전 우편번호 일치 검증

- Japan Post 후보가 존재하면 PrestaShop 주소 저장 전에 state/city/town 영역을 같은 우편번호 후보와 비교한다. 여러 town 후보는 각각 허용하고 건물·호수 입력은 유지한다. 인덱스에 후보가 없거나 조회가 실패하면 수동 입력을 허용한다. 메시지는 일본어·영어·한국어다.
- PHP synthetic harness와 PHP lint를 기존 PrestaShop 컨테이너의 임시 경로에서 실행했다. 기존 dev DB를 읽는 통합 검증에서 공식 `1000004` Tokyo/千代田区/大手町의 정상 저장 검증, 1000004/100-0004, 불일치 시구정촌 거부, 건물명 허용 및 수동 fallback을 확인했다. 이 테스트는 DB 데이터를 생성하지 않는다.
- 커밋 `bb40026956f98e51ff0158c1c095dab8c7f72d8a`를 push하고 원격 SHA·원격 테스트 파일을 다시 확인했다. CI run #19 `39701310507`는 실패; public job 화면에서 실패 단계는 확인했으나 상세 원인은 얻지 못했다.

## 2026-10-22 — 관리자 대시보드 날짜 필드 한국어

- 실제 관리자 대시보드에서 영어 `From`, `Start`, `End`를 확인했다. PrestaShop core는 수정하지 않고 KURANEA 관리자 모듈의 XLIFF 도메인을 PrestaShop 명명 규칙에 맞췄으며, dashboard 전용 module JS가 날짜 입력 label/placeholder와 요약을 한국어로 표시하도록 했다.
- 관리자 브라우저 로그인 후 PC 1440×1000에서 `lang=ko`, 한국어 날짜 labels/placeholders/요약, 한국어 메뉴, page error 0건을 검증하고 `artifacts/qa/phase1a/admin-dashboard-korean-after-date-overlay.png`를 저장했다. 관리자 locale 계약 8/8, JS syntax,
## 2026-10-22 — Fresh install 주소 저장 실패 진단 분리

- 시작 기준: `work` 원격·로컬 SHA `1cfc24c9585ebe4169250dcc38321ad6c5825c68`, `main` SHA `ee02a3657448d563508687614a246e05ac61eecd`. 기존 카탈로그 파서 등 미커밋 파일과 저장소 밖 개발 DB/named volume을 보존했다.
- 직전 수정 후 격리 Actions run `39732730236`은 이미지 빌드, 캐시 권한 probe, 빈 볼륨 Compose 기동, 공식 Japan Post CSV import 단계까지 성공했다. `Verify real Tokyo postcode lookup and saved native address` 결합 단계는 종료 코드 255로 실패했고 이후 native order 및 restart smoke는 실행되지 않았다. run artifact는 공개 실행 페이지에서 본문을 읽을 수 없으므로 예외의 실제 발생 위치를 추측하지 않는다.
- 진단 보강: CI를 도쿄 API 조회와 PrestaShop 네이티브 주소 저장으로 분리했다. PHP 저장 검증은 bootstrap, Japan/state 조회, CSV 후보, 고객 생성, 주소 저장, reload 단계를 기록하고 예외 클래스·메시지를 GitHub error annotation으로 제한 출력한다. 회귀 계약 테스트가 두 workflow step 분리와 진단 단계를 고정한다. 프로덕션 모듈/코어는 수정하지 않았다.
- 로컬 검증: fresh-install workflow contract 및 주소 데이터 갱신 계약 테스트 14개 통과, Docker Compose 정적 config와 `git diff --check` 통과. 호스트에 PHP CLI가 없고 활성 로컬 Docker/DB 상태를 보존하기 위해 실행 DB에 테스트 데이터를 넣지 않았다.
- 다음 검증은 새 원격 커밋에 의해 실행되는 격리 Actions 1회다. 주소 API, 네이티브 Address, 무결제 Order, 관리자 배송지 표시, 일본어/다국어·JPY·테마·관리자 로그인, 재시작 후 지속성은 실제 각 단계가 성공하기 전까지 미검증이다.
## 2026-10-22 — Native Address 저장 CI 오류 수정

- 격리 Actions run `39734469874`에서 workflow contract, 이미지 build, cache ownership probe, 빈 볼륨 shop 기동, 공식 Japan Post CSV import와 `1000004` postcode API lookup이 모두 통과했다. 실패 단계 annotation은 `KURANEA_NATIVE_ADDRESS_STAGE=native address save; exception=Error; message=Cannot access protected property Address::$id_shop`였다. 이후 native order와 restart smoke는 실행되지 않았다.
- PrestaShop 9.2.0 공식 `AddressCore`를 확인해 `id_shop`가 Address public property나 ObjectModel field가 아닌 것을 대조했다. 테스트 harness의 불필요한 `$address->id_shop = 1`만 제거했고 코어/운영 모듈을 수정하지 않았다.
- TDD: 먼저 Address의 미지원 shop 속성 대입을 금지하는 workflow contract를 추가하고 실패를 확인한 다음 잘못된 대입을 지웠다. postcode workflow 및 Japan Post refresh contract 15/15 통과, Compose 정적 설정과 `git diff --check` 통과.
- 새 격리 CI에서 native address save, unpaid Order 생성, 관리자 배송지 조회, restart/data persistence는 다시 확인해야 하므로 아직 PASS가 아니다. 기존 개발 DB, named volume 및 미커밋 catalog parser 변경은 보존했다.
## 2026-10-22 — Native order verifier의 미지원 Address 속성 제거

- run `39735099736`은 주소 저장 verifier의 첫 수정 커밋으로 진행 중이었다. 이 실행에서 다음 단계로 넘어가기 전에 `tests/postcode/verify_native_order_persistence.php`도 같은 `$address->id_shop` 대입을 하고 있음을 확인했다. 이전 CI annotation으로 확인된 PrestaShop 9.2.0 `AddressCore` 계약과 같은 원인이므로 주소·주문 검증기를 함께 고친다.
- 회귀 검사를 먼저 확장해 두 스크립트에서 해당 대입을 거부하는 검사가 기존 코드에서 실패함을 확인했다. native order verifier의 한 줄 대입을 삭제했으며, 주소/주문 로직과 코어는 변경하지 않았다.
- fresh-install workflow contract 및 Japan Post refresh 테스트 15/15 통과, Compose 설정·diff 검사 통과. 이 수정은 다음 격리 CI에서 검증하며 `39735099736`은 수정 전 snapshot이므로 별도로 결과를 기록한다.
## 2026-10-22 — Native order E2E 실패 경계 계측

- run `39735099736`은 empty-volume install, 공식 CSV import, `1000004` postcode lookup 및 native Address 저장까지 통과했다. Order step 실패 후 확인하니 그 run의 checkout SHA `dad3066`에서 주문 verifier에 Address의 미지원 `id_shop` 대입이 남아 있었다. 같은 속성을 거부하는 회귀 계약을 확장하고 해당 대입을 제거해 `994a3f6`에 저장했다.
- 새 수정 run `39735277398`에서 empty-volume startup, Japan Post CSV import, Tokyo/Otemachi API lookup 및 native Address save가 통과했지만 native unpaid-order/Back Office projection step은 exit 255로 실패했다. 당시 order verifier의 uncaught exception은 public job page에서 상세 로그로 읽을 수 없어 실패 경계를 추정하지 않는다. restart step은 skipped.
- 개선: native order verifier에 bootstrap, Back Office kernel, JP context, payment module, address, product, cart/quantity, delivery, order 및 Back Office projection stage를 추가한다. Uncaught Throwable은 제한된 메시지와 stage를 GitHub annotation으로 출력한다. 다음 CI의 오류 증거로 실제 root cause를 판정한다.
- TDD/로컬 검사: stage contract를 먼저 추가해 fail을 확인한 뒤 handler와 stage marker를 넣었다. fresh-install contract 및 Japan Post refresh 테스트 15/15, Compose YAML 검증, `git diff --check` 통과. 실제 PHP/MySQL 동작은 다음 격리 CI에서 확인한다.
## 2026-10-22 — Back Office order projection query bus 수정

- run `39736010830`에서 workflow/image/cache probe, 빈 볼륨 설치, official CSV import, `1000004` Tokyo/Otemachi API lookup 및 native Address 저장이 통과했다. annotation의 실패 단계는 `Back Office shipping address projection`; 예외는 Symfony `ServiceNotFoundException`으로 `CommandBusInterface`가 컴파일된 컨테이너에서 removed/inlined 됐다는 내용이었다. restart step은 실행하지 않았다.
- PrestaShop 9.2.0 공식 `FrameworkBundleAdminController::getQueryBus()`가 `prestashop.core.query_bus` 서비스를 사용하고 공식 OrderController가 `GetOrderForViewing($orderId, QuerySorting::DESC)`를 dispatch하는 것을 확인했다. 검증기는 같은 query bus service id 및 정렬값을 사용하도록 바꿨으며 PHP 코어/쇼핑몰 모듈은 변경하지 않았다.
- 회귀 contract를 먼저 추가해 기존 direct `CommandBusInterface::class` 호출에서 실패를 확인하고, 공식 query bus alias 적용 후 green을 확인했다. fresh-install contract 및 Japan Post refresh 15/15, Compose config, `git diff --check` 통과.
- 실제 관리자 order projection, unpaid Order의 저장/주소 표시 및 restart/data persistence는 다음 격리 GitHub Actions 실행 전까지 미완료다.
## 2026-10-22 — 빈 DB 설치·일본 주소 주문 native E2E 통과

- query bus 수정 코드 `6b05ae8`로 실행한 GitHub Actions run `39736745903`은 job 및 workflow `Success`였다. 이미지 build, isolated cache ownership probe, 빈 MariaDB named volume의 신규 설치, Japan Post 공식 KEN_ALL 다운로드/import, postcode `1000004` 도쿄/오테마치 HTTP lookup, native Address 생성 및 재조회, unpaid Order와 Back Office projection, fresh-shop restart smoke 순서로 통과했다.
- Order fixture는 `[CI ONLY]` product, 전용 Customer, `1-2-3` 집주소와 CI 전용 건물/호수, native Cart 및 free CI-only carrier를 격리 DB에 만들고 `ps_checkpayment`의 unpaid/non-logable state로 `validateOrder()`를 실행한다. `total_paid_real=0`, delivery address 연결, postcode/도도부현/시구정촌/町域/번지/건물 필드를 확인했다. 실제 결제·은행 입금은 없었다. official `GetOrderForViewing` query로 Back Office 배송지 문자열도 검증했다.
- Restart smoke는 storefront HTTP 200, 관리자 `admin-kuranea` 로그인 화면/공식 로고, ja 기본 및 en/ko 활성, JPY, KURANEA theme/CSS, 캐시/bootstrap marker와 DB 테이블 수/구성을 재확인했다. 이는 격리된 GitHub runner의 신규 DB만 대상으로 했고 기존 개발 named volume은 건드리지 않았다.
- 한계: 이 검증은 PrestaShop native model/service를 통한 주소·장바구니·주문 저장이며 실제 고객 브라우저에서 상품 카드→장바구니→checkout UI를 완료한 browser E2E는 아니다. Restart 후 방금 만든 특정 주문/배송지 row를 다시 조회하는 개별 assertion도 없다. 이 두 항목을 후속 격리 browser/persistence QA로 남긴다.

## 2026-10-22 — ORDENOWA 유지보수 이어가기

- 시작 원격 `work` SHA는 `d8896c346215f73ec36f806b17d277ef3a899ec9`, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. 기존 변경·named volume은 건드리지 않았다.
- `Offline catalog parser` run `39751104912`는 PHP 8.3 lint, synthetic Amazon Japan/Rakuten parser 테스트, fresh-install 계약 테스트를 통과했다. 실제 외부 페이지 접속·상품 등록은 이 실행으로 검증되지 않는다.
- fresh-install run `39749482357`는 상점 Compose 시작 뒤 공식 Japan Post KEN_ALL 다운로드 단계에서 curl exit 22로 실패했다. 공개 로그는 상세 HTTP 응답을 숨기고 artifact는 인증 없이 다운로드되지 않아 상태 코드와 응답 본문은 미확정이다. 시작 때 지적된 `admin-dev` 오류는 이 run에서 나타나지 않았다.
- CI는 모듈의 기존 HTTPS·최종 호스트·ZIP/CSV 검증 및 트랜잭션 importer를 직접 실행하도록 변경했다. 다운로드 실패 시 exit/status와 URL query를 제외한 호스트만 기록하고, 실패 후 importer 미호출을 회귀 테스트로 고정했다. 관련 검사 16/16 통과 후 `ba5de866d2ca771e2cdad5f36d5d40a6ce7573fa`를 `work`에 push했다. `git ls-remote`, 별도 shallow clone 및 원격 파일 재조회로 SHA와 변경 내용을 확인했으며 `main`은 유지됐다. 이 수정 커밋의 fresh-install run `39751809078`은 확인 시점에 진행 중이었다.
- ORDENOWA 공식 이미지는 사용자 메시지에서 미리보기로 보였지만, 실제 ZIP/PNG 바이트는 이번 실행환경에서 접근할 수 없었다. 이 환경의 attachments에는 기존 KURANEA 원본만 확인됐다. 따라서 신규 ORDENOWA 로고·favicon·PWA/OG 아이콘을 저장하거나 적용했다고 기록하지 않으며 기존 원본/이력을 유지한다.
- cloud environment의 현재 `spec_revision`과 `observed_spec_revision`은 2다. 일본 우편 호스트는 현재 restricted egress 정책에 없다. revision 3 적용은 확인되지 않았고 환경 draft 변경·게시도 하지 않았다.
- 신규 설치/주소 자동완성·저장 주문·관리자 배송지 화면, 실제 브라우저 E2E, 전체 관리자 한국어, PWA 실기기 설치, 영업 승인·실거래는 완료로 표시하지 않는다.

## 2026-10-22 — ORDENOWA 카탈로그 parser 체크포인트

- Amazon Japan/Rakuten을 위한 합성 HTML fixture 파서와 독립 Actions workflow를 `d8896c346215f73ec36f806b17d277ef3a899ec9`에 저장했다. run `39751104912`가 성공했다. 페이지 네트워크는 제한을 우회하지 않았고 실제 상품 수집은 0건이다.
- parser의 검수 큐는 메모리 기반이며 관리자 지속형 검수/승인, PrestaShop 네이티브 상품 생성, TEST/DEMO 상품 10개 등록은 후속 작업이다.

## 2026-10-22 — ORDENOWA 관리자 설정·검증 이어가기

- 시작 시 원격 `work` SHA `6f6ff5e5a99210f916b7064dacd00c73932ded6c`, `main` SHA `ee02a3657448d563508687614a246e05ac61eecd`를 확인했다. `/workspace/japan-premium-commerce`의 기존 미커밋 파일·스크린샷·테스트 폴더 및 named volume은 수정·삭제·초기화하지 않았다. 실제 변경은 별도 `/tmp/kuran-p0-checkpoint` work clone에서 진행했다.
- `ba508b4`는 관리자 운영 설정의 특정상거래법 필드 라벨을 한국어로 바꿨다. CI `39756576373`가 새 assertion의 다국어 접미어 `· 일본어` 누락을 확인했고, `3ec583c`에서 기대값을 실제 필드 라벨과 일치시켰다.
- `3404116`은 법률 페이지 PHP 테스트의 실패 메시지를 Workflow summary와 step output에 노출하도록 보완했다. 정확한 예외는 `PublishedLegalPageBuilder::build()`가 locale `title`을 본문 `<h1>`에 렌더링하지 않는 것이었다. `7cf8c41`에 localized `<h1>` 및 회귀 테스트를 추가했다. 같은 커밋에 은행 계좌이체 결제 활성화/계좌 연결을 추가했고, 게시된 법률 페이지·푸터·HTML/텍스트 주문 이메일은 선택된 완전한 활성 계좌 하나만 표시한다. `39757526475`에서 business-profile Actions 전체가 성공했다.
- `cc448a6`은 `kuraneabackoffice`, `kuraneapostcode` Module Manager 이름과 설명을 한국어로 바꾸고 회귀 테스트를 추가했다. 이번 로컬 실행: business-profile Python 10/10, admin locale 13/13, fresh-install workflow contract 10/10, `git diff --check` 통과.
- fresh-install run `39756769346`은 빈 볼륨 Compose `--wait` 기동까지 성공했다. 이어 공식 Japan Post KEN_ALL을 받는 단계가 `curl_exit=22 http_status=503 effective_host=www.post.japanpost.jp`로 실패하여 주소 조회, 네이티브 주소·주문 저장, 관리자 주문 조회, 재시작 보존은 실행되지 않았다. 같은 네트워크 실패를 근거 없이 성공 처리하거나 무작정 재시도하지 않는다. 최신 `39757526456`은 당시 실행 중이었다.
- business-profile run `39756769193`의 실제 예외는 영어 법률 페이지 제목 누락이었다. 이 문제는 `7cf8c41`에서 수정되었고 `39757526475`가 통과했다. 따라서 해당 기능의 PHP 코드 계약은 Actions에서 확인됐으나, 관리자/고객 브라우저 E2E는 별도 미완료다.
- 첨부 ORDENOWA 세 이미지 미리보기는 대화에서 확인되지만 `download_file`은 `cannot create attachment directory: Not a directory`로 실패했다. `/workspace`와 `/tmp`를 검색해도 ORDENOWA 원본 바이너리가 없었다. 기존 KURANEA `assets/brand/source/` 및 과거 이미지는 보존했고, 공식 ORDENOWA 로고·favicon·PWA·OG 산출물을 만들거나 교체하지 않았다.
- 현재 cloud environment는 `spec_revision=2`, `observed_spec_revision=2`로 revision 3 적용이 확인되지 않았다. 이전 SHA를 가리키는 draft를 수정하거나 게시하지 않았다. `/workspace` 여유 공간은 0 bytes이고 현재 기존 PrestaShop/MariaDB 컨테이너 모두 unhealthy다. Docker 상태만 읽었으며 기존 named volume을 건드리거나 새 컨테이너를 만들지 않았다.
- 검증 한계: 이 셸에는 PHP CLI가 없다. PHP 변경은 remote Actions에서 검사했다. 현재 로컬에서 새 browser screenshot, 실제 상품 수집·등록·주문, 기기 PWA 설치 검증은 하지 않았다. 실제 외부 상품 수집 0건, 실제 신규 주문 0건으로 보고한다.

## 2026-10-22 — Catalog CI false-positive 수정 및 원격 확인

- 시작 시 격리 clone `/tmp/kuran-p0-checkpoint`의 원격 `work` SHA는 `940d8a0d5ab5fcf3832983e44a1ad88bd7597ef3`, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. 원래 `/workspace/japan-premium-commerce`의 미커밋 코드·스크린샷은 읽기만 했으며 기존 named volume, DB와 `main`은 변경하지 않았다.
- cloud environment status는 revision 2가 활성 관측 상태이며 revision 3 적용 증거가 없다. 읽은 설정 draft는 revision 4이나 저장소 ref가 이전 SHA `2db98927a9ede2b2423456873f0994ddd19ffe4e`를 가리킨다. active network policy state는 `unknown`; draft/활성 설정은 수정하거나 게시하지 않았다.
- run `39759208949`는 `940d8a0`에서 synthetic parser 테스트가 exit 255로 실패했다. controller 화면의 이미지 메타데이터만 검사하려던 테스트가 전체 페이지에서 `amazon_jp` slug가 없어야 한다고 단언했지만, 화면에는 provider slug가 포함된 deduplication key도 정상 표시된다. 이 테스트 조건이 확인된 false-positive였다.
- `tests/catalog/admin_review_controller.php`는 deduplication key를 별도 확인하고 `이미지 메타데이터` 블록에서만 한국어 출처명을 검증하도록 수정했다. parser/controller production behavior는 바꾸지 않았다. CI 실패는 기존에 전체 로그를 그대로 출력하고 annotation 특수문자를 escape하지 않아 실제 원인을 보여주지 못했다. 실패 시 summary에는 최근 80줄, annotation에는 500자 이하 마지막 줄을 출력하고 `%`, CR, LF를 escape하며 PHP exit code를 보존하도록 보완했다. 회귀 계약은 먼저 실행해 `%25` 이스케이프가 없어 실패하는 RED를 확인한 뒤 수정 후 GREEN을 확인했다.
- `fix(ci): scope parser assertion and bound failure logs` 커밋 `5b2a1cb8d2193458a088174eb04228f252cd9e0e`를 `work`에 push했다. `git ls-remote`, fresh shallow clone `/tmp/ordenowa-remote-check`, 원격 파일 재조회 결과가 동일 SHA였다. 원격 `main`은 변하지 않았다.
- 새 parser run [39760154509](https://github.com/goldeget/japan-premium-commerce/actions/runs/39760154509)은 성공했다. 이는 PHP lint 및 synthetic Amazon Japan/Rakuten parser 검증이다. 실제 외부 상품 수집과 PrestaShop 네이티브 상품 등록은 0건/미검증이다.
- fresh-install run [39759208769](https://github.com/goldeget/japan-premium-commerce/actions/runs/39759208769)은 image build, isolated cache probe, 빈 볼륨 상점 시작, catalog 모듈 설치 및 PrestaShop 재시작 후 별도 queue 보존까지 통과했다. 공식 Japan Post archive download가 `curl_exit=22 http_status=503 effective_host=www.post.japanpost.jp`로 실패해 lookup/address/order/admin/restart 후속 검사는 건너뛰었다. 후속 run [39760154414](https://github.com/goldeget/japan-premium-commerce/actions/runs/39760154414)도 같은 HTTP 503으로 실패했으며 updater의 기존 `curl --retry 3 --retry-delay 2` 이후에도 지속됐다. 주소/주문 E2E는 여전히 검증되지 않았다.
- 최신 로컬 확인: business-profile Python 계약 10/10, admin-locale 13/13, fresh-install workflow 계약 12/12, `git diff --check`, `bash -n docker/kuranea-entrypoint.sh`, Compose 및 두 workflow YAML parse 통과. 호스트 PHP CLI가 없어 로컬 PHP 직접 실행은 하지 않았다. 로컬 운영 DB/컨테이너 변경과 브라우저 캡처는 없고 기존 KURANEA/ORDENOWA 자산 상태를 바꾸지 않았다.


## 2026-10-26 — imported draft manager edit/save/readback coverage

- Starting point: work HEAD and origin/work were confirmed at d49fa7d2e5b7714fee8f31bdd1558f54bdb2a6d7; main remains ee02a3657448d563508687614a246e05ac61eecd. Existing user files were preserved.
- Added an isolated browser flow for the exact approved imported product: edit EN/KO text, sale price and both option stocks; native save click; exact success notice; fresh GET via the previously validated same-origin manager link; compare saved values and retained image/category/tax/option identities; reimport the same source and assert the same product ID, unchanged product set and preserved manager edits.
- The product remains behind the existing inactive/hidden/non-orderable gate; the price-hidden manager guard is preserved. No storefront publication, production DB, deployment or real transaction was performed. This does not close GAP-002.
- Focused catalog/admin/workflow contract tests, Python syntax, workflow YAML and diff checks had passed before commit; independent read-only review found no blocking identity or gate issue. Local PHP CLI is unavailable, so PrestaShop runtime assertions await Actions.
- Commit d49fa7d2e5b7714fee8f31bdd1558f54bdb2a6d7 was pushed; git ls-remote confirmed origin/work at the same SHA and main unchanged. Full isolated run #40275686536 was last observed at 05:55 UTC on Step 66 (admin order browser QA); do not record its browser or aggregate result until completed. Separate Offline catalog parser run #40275686540 on the same code SHA succeeded: PHP lint, synthetic Amazon Japan/Rakuten parser checks and 65 workflow contracts.

## 2026-10-26 — imported draft save confirmation stale-element correction

- Rechecked the current state before changing code: work and origin/work were `422f73120aeeb33327c342a1b6994897036dbd6f`, `main` remained `ee02a3657448d563508687614a246e05ac61eecd`, and no workflow was running at that check. The d49 full run #40275686536 later completed with the sole aggregate failure `catalog_import_browser_qa=failure` at `manager_edit_save_confirmation` (`StaleElementReferenceException`). Its safe JSON showed that the save click returned, HTTP was 200, the correct manager editor and hidden product ID remained; it did not prove save outcome.
- Independent review of artifact 12630308572 opened a 640×180 failure crop showing only the protected inactive-product notice. It did not contain the edited values, success message or failing element, so the screenshot does not further localize the exception.
- The native controller’s exact normal save success message matches the browser expectation. The harness retained alert WebElements while issuing separate visibility/text commands; a DOM replacement between calls could stale the reference and abort WebDriverWait. Replaced that read with one synchronous DOM snapshot, preserving visible-alert and exact-message matching, native form click, fresh GET, persisted-field assertions and reimport checks. Safe diagnostics add only a boolean for the exact expected success notice.
- The new contract test failed before the helper existed and passed after implementation. Focused catalog-import/workflow contracts: 38/38. Python `py_compile` and `git diff --check` passed. Read-only review found no blockers and confirmed the stale WebElement path was removed without weakening save/readback assertions.
- Commit `e085be59a0f9f061769fe7ab3cb79e025042b960` was pushed to work; remote SHA matched. Full isolated run #40277922728 began automatically and was last observed at Step 14 `Start the empty-volume shop`. Same-product save/readback/reimport runtime and aggregate are still pending; no PASS is claimed.

## 2026-10-26 — catalog baseline and AdminOrders document-wait recovery

- Reconfirmed `work`/`origin/work` before continuing; `main` remained `ee02a3657448d563508687614a246e05ac61eecd`. Preserved all untracked user files and did not touch local DBs or named volumes.
- Catalog evidence from #40292752486 and independent review showed the approved product existed exactly once in the manager list, but `before_ids` was read only after `reject_unsupported_product_url()` navigated away from the manager page. Commit `0da85d391956ff52418672973f275c88af4ac1ab` captures that baseline on the manager page before navigation and adds the order contract. #40294965246 then passed catalog create/edit/fresh readback/reimport in the actual aggregate; its only failure was shipping admin browser QA.
- #402949 safe diagnostics localized shipping to `admin_post_save_document_wait` / `StaleElementReferenceException`; the native submit returned and the screenshot showed a success banner, but there was no tracking-row readback, so save success was not inferred. Commit `985e1cd3f3c30250b2052d946e0c9e383cb66752` catches only a transient stale `<body>.text` read inside the document polling predicate, requires the same order reference and exact modern/legacy admin order route, retains the 35-second wait and downstream same-row/fresh-GET/customer/DB assertions, and emits only bounded safe predicate state. Commit `0b68e96f1a38a36feb3732b2d3a26c06afd40c1a` rejects missing or non-string expected references.
- TDD/verification: the browser wait contract first failed because the helper did not exist; afterward stale-once-then-valid passed, repeated stale never passed, and wrong route, wrong reference and missing reference were rejected. Diagnostic tests confirm only allowlisted body state/route/count/boolean values are annotated, with exception/raw order reference excluded. The exact Step 8 contract command passed 546 tests (7 skipped); free-shipping contracts 47/47; Python compile and `git diff --check` passed.
- Baseline Actions [#40298163222](https://github.com/goldeget/japan-premium-commerce/actions/runs/40298163222) on `985e1cd` completed SUCCESS; Step 88 aggregate and actual catalog, shipping admin and tracking-persistence outcomes were all success. Independent QA opened browser artifact [12639887664](https://github.com/goldeget/japan-premium-commerce/actions/runs/40298163222/artifacts/12639887664) and verified same-order Japanese tracking detail/admin/customer display. This does not prove the stale catch branch fired in that run.
- Final SHA Actions [#40300616469](https://github.com/goldeget/japan-premium-commerce/actions/runs/40300616469) completed FAILURE. Step 88's sole aggregate failure was `account=failure`, annotated at mobile `customer_address_edit` with `TimeoutException` and no named control. The catalog, shipping-admin and native tracking persistence aggregate outcomes were success; Step 73 ran, confirming actual admin Step 72 outcome. Backup/restore, restart, Japan Post verification and run-scoped cleanup succeeded. This unrelated account failure was not investigated or rewritten as PASS.
- Latest artifacts: browser screenshots [12641465628](https://github.com/goldeget/japan-premium-commerce/actions/runs/40300616469/artifacts/12641465628) and diagnostics [12639904863](https://github.com/goldeget/japan-premium-commerce/actions/runs/40300616469/artifacts/12639904863). Both are unexpired. No visual review of the new final-run PNGs is claimed here.
- `work` remote and local HEAD are `0b68e96f1a38a36feb3732b2d3a26c06afd40c1a`; `main` unchanged. No production deployment/payment/trade/dispatch or operational data changes. Actual seller/SKU/tax/shipping/payment/legal/production/backup inputs and iOS/Android device access remain release blockers; full Korean admin coverage remains incomplete.
