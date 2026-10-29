# ORDENOWA 발주·수동 수당 포인트 플랫폼 출시 준비 — 2026-10-29

## 2026-10-29 자동 실행·검증 업데이트

검증 코드 [ae370bbb3a8aab98e3da7f33419b843618c5e508](https://github.com/goldeget/japan-premium-commerce/commit/ae370bbb3a8aab98e3da7f33419b843618c5e508)의 [전체 격리 검사 #40800924097](https://github.com/goldeget/japan-premium-commerce/actions/runs/40800924097)는 **39/39 고유 단계 PASS, aggregate passed=true, cleanup success**다. 새 알림 상태 점검, 설치된 MBO 컨트롤러/한국어 오류 Twig 렌더링, 실제 age 암호화·변조/잘못된 키 거부·독립 DB 복원을 포함한다. [artifact12866995280](https://github.com/goldeget/japan-premium-commerce/actions/runs/40800924097/artifacts/12866995280)를 다운로드해 SHA-256 `17c3c254e636dcf0d2762eb7122de38cf2a07fbce6461e1b8b026da607d9d533`와 안전한 결과 JSON을 직접 대조했다.

별도 [배포 묶음 #40798367714](https://github.com/goldeget/japan-premium-commerce/actions/runs/40798367714)는 7de7538에서 실제 Docker build/save/load와 manifest 검증을 통과했다. 두 SHA 사이 변경은 관리자 QA 파일 하나뿐이지만 동일한 승격 artifact로 합쳐 주장하지 않는다. [정기 실행 설정 #40798061866](https://github.com/goldeget/japan-premium-commerce/actions/runs/40798061866)은 Linux 13검사와 systemd 분석을 통과했다. 서버 서비스 설치/활성화, registry 게시나 운영 전환은 수행하지 않았다.

실제 MBO 오류 템플릿과 native light parent에서 한국어 문구 2회·영문 부재·503/헤더를 확인했다. 이는 시험용 실패 provider와 메모리 세션을 사용하는 직접 컨트롤러 검사이며, 인증 HTTP·전체 관리자 chrome/시각·외부 Addons/Facebook 정상 가용성 인수는 아니다. 상태 점검의 정상 결과와 암호화 복원은 격리 환경 결과다.

GPT가 상품 URL 선정·원문 조사·설정 준비·구현·검사를 맡는다. 기존 표의 설정명은 사용자에게 전부 작성해 달라는 요청이 아니다. 승인된 브랜드·자산·일본어 설명·JPY 세금포함·지원 지역 무료배송을 재사용한다. 실제 상품의 현행 가격/옵션·사진 사용 근거, 실운영 계정/정책 승인·HTTPS/SMTP/Push 및 물리 기기 인수는 사실 확인이 남으며 완료로 만들지 않는다. 운영 배포·운영 DB 변경·실거래·실결제는 실행하지 않았고 main은 ee02a3657448d563508687614a246e05ac61eecd로 보존했다.

[실행별 증거·실패 수정·환경 조사·정확한 한계](evidence/2026-10-29-release-automation.md)를 기준으로 한다. 아래의 이전 “최신/최종” 표기는 해당 시점 기록이며 이 절이 우선한다.


**핵심 기능 구현·합성 집중 검증을 완료했고, 고정 후보 전체 격리 인수를 완료했다. 실제 상품·운영 환경·실기기 인수가 남아 있어 운영 출시 완료는 아니다.**

### 최종 검증 후보 — 91c6098 / 전체 격리 QA SUCCESS

검증 코드 **`91c6098c6b551946cc8291b31c868656d50c9b34`**를 원격 work에 저장하고 변경 파일 재조회·새 원격 복제본으로 일치 확인했다. main **`ee02a3657448d563508687614a246e05ac61eecd`**와 원래 사용자 체크아웃/운영 DB·volume은 보존했다. 이후 문서 저장 HEAD와 검증 코드 SHA는 구분한다.

전체 [#40763074207](https://github.com/goldeget/japan-premium-commerce/actions/runs/40763074207)는 최종 **SUCCESS**, 실제 **38/38 phase PASS / aggregate passed=true / cleanup success**다. native browser16단계·3언어 회원/reset·공식 ACL·메일/Push mock·재시작/독립 복원까지 통과했다. 초기/재시작 앱1140·Pushvendor1426 파일이 정확한91코드와 일치했다. [artifact12850640042](https://github.com/goldeget/japan-premium-commerce/actions/runs/40763074207/artifacts/12850640042), ZIP SHA256 **`5c01e0d4b070875e3bac1e75b4586ee20113748a298039dc1a2f5589c4c69802`**를 직접 확인했고 [원본12JSON·24PNG·무결성 명세](evidence/2026-10-29-procurement-local/fresh-91c6098-complete/)를 보존했다.

직전 실패는 실제200ms 링크 font/padding 전환이 끝나기 전에 캡처한 QA 순서 문제였다. 기존30초와 full rect/center hit/privacy geometry/enabled/stable scroll·권한 조건을 유지한 수정으로13unit·실제D20target·저장 재조회가 통과했다. 별도 GPT는 **새 hosted24PNG를 모두 실제 열었고 핵심20target(3언어9메뉴·9요청확인·2사진)을 인수**했다. JA/KO 글리프·부모/하위 분류·최종 버튼/사진쌍이 보인다. 전체 텍스트를 치환한 나머지4포인트 PNG는 의미/geometry 인수 근거로 쓰지 않는다. [독립 실제 검수](evidence/2026-10-29-procurement-local/fresh-91c6098-complete/ordenowa-independent-final-hosted-40763074207-review.md).

최신 품질은 JA7경로/10폭+일부dark의7privacy·84layout·84axe·14실제클릭·14Lighthouse PASS다.14건 성능/접근성100, 공개정책SEO100, 모바일LCP최대1747.3ms/CLS0.0001이다. axe위반0이지만84셀 incomplete와 기존 제한된13패턴 수동 검토를 유지한다. 전체WCAG·실사용INP·실기기 성공으로 확대하지 않는다.

로컬D의 요청/원장/포인트계정0·ACTIVE1과 원래A/B/C/80P·업무12/ACL감사8/메뉴2/상품·사진 보존을 확인했다. 새D의 native언어 전환 `id_lang/date_upd`와 접속/session telemetry만 별도 기록했다. [로컬 집중·정확한 보존 범위](evidence/2026-10-29-procurement-local/real-two-level-category-focus/). **핵심 구현과 명시한 합성 격리 검증은 완료했으며, 실제 상품·운영 정책/환경·기기 인수는 남아 있다. 운영 출시 완료는 아니다.**


## 확정 범위와 완료 근거

상품 안내/배정 → 고객 상품·수량 확인과 발주 요청 → 수동 검토 → 별도 수동 포인트 지급·연결 정정 → 본인 잔액·내역 표시가 제품이다. 배송·반품·상품환불·판매결제·포인트 사용/양도/현금환산/출금은 명시적 범위 제외다. 기존 데이터와 당시 소매 QA 성공은 보존한다.

| 범위 | 실제 완료 근거와 한계 |
| --- | --- |
| 요청·검토·포인트·문의·정책·감사 | 저장/rollback·멱등·실제 경합·본인/shop/역할/CSRF, A수량2→승인0P→명시100P→새로그인100P→정정80P, B GET/POST 거부·B인증/A원본 보존, 유효 토큰의 제한 직원403, 문의 public/private 분리·정책 새 조회 확인 |
| 계정·알림·복원 | JA/EN/KO signup/login/reset, Mailpit5건/중복0·언어별 MIME, 실제 native ACL6변경/감사6행, 재시작/독립 DB 복원 집중 PASS. 운영 SMTP/실제 Push 인수는 별도 |
| 파싱·상품·분류 | 합성 parser38행동·모호 가격 거부·private inactive 상품/옵션/로컬 원본사진2장과 실제 D2단계 저장/배치/3언어 메뉴·filter·20target 검증. 실제 쇼핑몰 호환은 미완료 |
| 관리자 한국어 |69메뉴노드/60목적지 중66건200KO.69번역/13Tab CAS/scoped raw label 수정 후19건 재조회와 native폼62/DB33/locale61 PASS. 외부2페이지와 미진입 분기의100% 인증은 미완료 |
| 품질·PWA | 기존 품질3의84layout/axe·14클릭/14Lighthouse PASS(성능99–100/접근성100/공개SEO100), 자동 incomplete84셀과 수동13유형 분리. 정적cache/private제외·업데이트 및 scoped 화면 검수 PASS. 전체WCAG·fieldINP·물리 기기 검증 아님 |

## 실제 원격 QA 이력

| 실행/코드 | 실제 결과 |
| --- | --- |
| [#40763074207](https://github.com/goldeget/japan-premium-commerce/actions/runs/40763074207),91c6098 | 최신 전체38/38PASS·aggregate true·cleanup success·workflowSUCCESS. 독립 GPT가24장을 실제 열어20target 인수,4broad포인트 제외 |
| [#40759815264](https://github.com/goldeget/japan-premium-commerce/actions/runs/40759815264),587bdf4 |28PASS/native_browser FAIL/9not_run/cleanup success. 실제200ms native CSS 전환 중 screenshot scroll 안정성 실패를 재현해 수정. artifact12847477729 |
| [#40757330613](https://github.com/goldeget/japan-premium-commerce/actions/runs/40757330613),d4e470a |28PASS/native_browser FAIL/9not_run/cleanup success. readonly 대상 token QA 문제를 native form action200/유효 bodytoken403으로 대조·수정. artifact12847660925의20PNG는 글리프/target위치 결함으로 시각 FAIL. 경량40757330533 SUCCESS |
| #40756263392,8663e96 / #40755121454,ad51cff |각3PASS/module_seed FAIL/34not_run/cleanup success. 엄격13메뉴 중 HOME XLF/CAS/seed 문구 불일치만 고쳤고 원래 assertions 보존 |
| #40750834639,1aca9e9 / #40749362584,6f9c301 |각28PASS/browser FAIL/9not_run/cleanup success. 실제 POST 시작 전 종료/이전 문서 대기 문제 및 raw 언어auth404를 수정해 집중 재검증 |
| 이전 build 3회 / 과거 소매#40508152705,f5b1cca |build 준비 실패 원본·알려진 Bake 권한 원인 수정 보존. f5b1cca의 당시 전체 SUCCESS도 해당 범위로 보존 |

모든 원본 outcome·artifact digest·집중 결과는 [TEST_RESULTS](TEST_RESULTS.md)와 [증거 목록](evidence/2026-10-29-procurement-local/README.md)에 보존한다. 새 자료 없이 QA를 반복하지 않고 실제 outcome/aggregate/cleanup으로 판정한다.

## 출시를 막는 잔여 — 다섯 범주

| 범주 | 현재 차단과 종료 조건 |
| --- | --- |
| 1. 관리자 검증 범위 |외부2페이지와 미진입 오류 분기의 전체 한국어 인수는 남는다. 합성38단계·핵심20target 인수와 구분 |
| 2. 실제 상품 |Amazon Japan/Rakuten 관리망 CONNECT403. 승인 원문/피드/내보내기 접근과 이미지 사용 근거에서 실제 가격/상세/사진/옵션/분류·검수 snapshot 대조 필요. 같은 URL 전체 반복 요청·차단 우회·합성 대체 없음 |
| 3. 운영자·참여자·정책 |실제 운영자/지원·상품/수량/고객·검토/수당 기준과9개 정책 초안 승인. LOGISTEED company_reference를 운영자 신원으로 추정하지 않음 |
| 4. 운영 환경·전환 |HTTPS/SMTP/secret참조/불변 app·DB digest/registry/scheduler/감시/backup RPO-RTO 담당 및 승인 staging의 승격·복원·rollback 인수 필요. compose의 mutable local app tag는 운영 승격 완료가 아님 |
| 5. 실기기 |실제 iOS/Android PWA 설치/업데이트·Push 수신/철회 인수. field INP는 실사용 전 미측정으로 유지 |

관리자 외부 ThemesCatalog503은 native external-content circuit fallback(하위 transport 상세 미확정), Facebook500은 cURL56 CONNECT403 외부 통신 실패로 분리한다. 발주/포인트 controller 결함으로 단정하지 않으며 정상 가용/시각 인수는 남는다.

필요 값·사용 위치·막힌 작업은 [단일 운영 입력표](PRODUCTION_DEPLOYMENT.md#현재-서비스의-운영-입력-체크리스트), 정책 문안은 [9개 JA/EN/KO 미승인 초안](POLICY_DRAFTS_JA_EN_KO.md), 전체 항목은 [요구사항표](RELEASE_REQUIREMENTS_MATRIX.md)를 따른다. 운영 자료 대기와 코드/검증 결함을 구분한다.

Cloud Codex의 실제 Chromium 검사와 내부 GPT의 실제 PNG 독립 검수는 수행했다. 외부 Work Mode 직접 전달/인수는 수행하지 않았다. Codex 패널 queued는 GUI 접근 성공이 아니다. 원본 main/사용자 파일/운영 DB·volume을 보존하며 운영 배포·실결제·실거래·유료 서비스는 실행하지 않았다.

## 보관자료 — 이전 소매 39항목 조사와 당시 QA

아래 전체 기록은 이전 `e357b8b`/실행 코드 `364ba34` 시점의 소매 조사다. 아래의 “현재”, “최신”, “NO-GO”, “미구현”, 39행 집계·7개 실패와 외부 입력은 **그 과거 범위/시점에 한정**한다. 위 현 플랫폼 판정과 최신 승인 설계가 우선하며, 아래 배송·반품·세금·판매자 승인·출금 자료를 현 출시 입력으로 재적용하지 않는다. 기존 증거와 당시 요구의 추적을 위해 삭제하지 않고 보존한다.

### ORDENOWA 출시 잔여 작업 전수조사 — 2026-10-29 한국시간

> **최종 제품 기준 — 2026-10-29:** 운영자가 고객에게 특정 상품 발주를 안내하고, 고객이 쇼핑몰 주문하듯 해당 상품·수량을 확인해 발주 요청하면 운영자가 수동 검토 후 포인트 잔액을 지급 반영한다. 고객은 잔액·내역만 표시받고 별도 처리는 운영자가 맡는다. 일반 작업결과/증거 제출 시스템으로 확장하지 않는다. 배송·반품·상품환불·판매결제/출금은 제외하고 수동수당포인트는 필수다. [최종 아키텍처](superpowers/specs/2026-10-29-ordenowa-procurement-points-platform-design.md)와 [새 요구사항표](RELEASE_REQUIREMENTS_MATRIX.md)가 우선한다. 아래 쇼핑몰 기록은 과거 해당범위 증거이며 새출시 PASS/FAIL이 아니다. 신규 발주요청·포인트핵심 구현/검증은 아직 미완료다.

#### 판정과 조사 범위

**현재 공개 판매 출시: NO-GO. 오늘 완료를 보증할 근거가 없다.** 최신 전체 QA의 7개 범위가 실패했고, 필수 Push 발송·일부 PWA·감사 범위·운영 배포 구성이 미완료다. 실제 판매자 승인과 출시 상품·운영 환경도 확인되지 않았다. 기존 필수 요구사항을 줄이거나 합성 검증을 실거래 인수로 대체해서 출시 가능으로 판정하지 않는다.

이번 작업은 6개 GPT 서브에이전트의 독립 영역 조사와 주담당의 원격 SHA·Actions 로그·artifact 목록 대조로 수행했다. 읽은 기준은 AGENTS.md, Master 원본, 관리자 한국어 원본, 일본 주소 요구사항, 최신 Architecture, business-profile/PWA spec, RELEASE_REQUIREMENTS_MATRIX, 현황·테스트·handoff·운영 문서 및 실제 모듈/테마/검증 소스다. 이 보고서는 코드 수정이나 신규 QA 통과 보고가 아니다. 새 전체 QA·배포·운영 DB 변경·실거래·유료 서비스는 실행하지 않았다.

##### 확인한 기준

- 원격 work HEAD: `e357b8b30f62949d96b0e5339c4925d3fffddc86`. 마지막 변경은 Cursor 인계 문서뿐이다. 실제 실행 코드 기준은 부모 `364ba341009c83ba9dbabd93aa95bfffa6171455`다.
- 원격 main: `ee02a3657448d563508687614a246e05ac61eecd`. 이번 조사는 원본 checkout을 이동시키지 않고 별도 `/workspace/ordenowa-release-audit`에서 했다.
- 이전 `/tmp/ordenowa-integration` 미커밋 패치는 현재 머신에서 확인되지 않았고 원격에도 없다. 이전 focused test 통과 보고를 현재 소스에 적용된 수정의 근거로 사용하지 않았다. 이 사실만으로 이전 머신의 원본 소실을 확정하지 않는다.
- 현재 셸·Git·GitHub 조회는 연결됐다. 이전 offline 환경 장애는 현재 실행을 막는 사유가 아니다. 조회한 최신 Actions 15개는 모두 종료됐고 동일 목적 실행 중 QA는 없었다.
- 현재 담당 전환 문서 `CURSOR_HANDOFF.md:25-28`은 코드 주담당 Cursor를 명시한다. 이번 위임은 전수조사이며 같은 브랜치에 병렬 코드 수정/CI를 하지 않았다.
- 원본 지갑·수익·출금 요구는 이후 확정된 범위 제외를 유지한다. 카드 PG·자동 은행 API·조건부 실시간 채팅을 새 필수 결함으로 만들어 넣지 않는다.

#### 실제 QA 결과와 산출물

| 증거 | 실제 판정 | 사용할 수 있는 범위 |
| --- | --- | --- |
| [전체 #40508152705](https://github.com/goldeget/japan-premium-commerce/actions/runs/40508152705), `f5b1cca` | SUCCESS, aggregate/cleanup 성공 | 당시 회원·주소·검색·상품 SEO·상품 검수·보안·PWA·합성 Push·reset·상담·계좌이체·배송·반품·복원 합성 acceptance. 최신 코드 전체 PASS로 확대 불가 |
| [주소 집중 #40530519482](https://github.com/goldeget/japan-premium-commerce/actions/runs/40530519482), `32ab27e` | SUCCESS, PC/mobile 14/14 boolean | B 인증 전후·네트워크 GET·A 폼/주소 부재·A 재인증/주소 보존. 교차 고객 POST는 검사하지 않음 |
| [최신 전체 #40559740938](https://github.com/goldeget/japan-premium-commerce/actions/runs/40559740938), `364ba34` | **FAILURE**, 실제 aggregate 실패 | PWA·합성 Push·reset·상품 Product/Offer SEO·상담·주문/배송 일부·백업/복원·우편번호 등 실제 성공은 유지. 아래 실패·skip 별도 |
| [business-profile #40559740899](https://github.com/goldeget/japan-premium-commerce/actions/runs/40559740899) / [parser #40559741067](https://github.com/goldeget/japan-premium-commerce/actions/runs/40559741067) | SUCCESS | 같은 SHA의 해당 모듈/합성 parser 검사. 전체 브라우저·운영 판매 인수 대체 불가 |

최신 전체 aggregate의 failure는 `perf_accessibility_qa`, `storefront_search`, `account`, `catalog_import_browser_qa`, `checkout_email_locale`, `checkout_gate_after_order`, `seo_sitemap_http`의 **7개**다. `catalog_import_scale_acceptance`, `bank_transfer`, order lifecycle/returns 및 admin audit browser 등은 선행 의존 단계 때문에 실행되지 않았다. skip을 별도 앱 결함이나 PASS로 세지 않는다. continue-on-error 이후 녹색 conclusion과 실제 outcome을 구분했다.

- [브라우저 artifact 12761377082](https://github.com/goldeget/japan-premium-commerce/actions/runs/40559740938/artifacts/12761377082): 25,024,558 bytes, GitHub상 만료 아님. 만료 예정 2026-11-27 03:45:20 한국시간.
- [비식별 진단 artifact 12761073334](https://github.com/goldeget/japan-premium-commerce/actions/runs/40559740938/artifacts/12761073334): 3,889 bytes, 조회 시 만료 아님. 만료 예정 **2026-10-30 03:46:40 한국시간**.
- artifact 목록과 job 원문 로그를 재조회했다. 이번 조사에서 전체 캡처를 열어 독립 시각 PASS로 판정하거나 개별 Lighthouse JSON 점수를 추출하지 않았다. 보고서 생성 수를 점수 통과 수로 해석하지 않는다.

#### 7개 실패: 최초 지점·분류·닫히는 조건

| 순서 | 확인한 최초 실패와 근거 | 현재 분류 | 필요한 수정/확인과 통과 조건 |
| --- | --- | --- | --- |
| 1 주소 | PC/mobile `customer_address_cross_owner_foreign_address_create` Timeout. B의 대조 주소를 만드는 중 중단. `verify_customer_account_browser.py:2796` 별칭은 35/34자로 native 32자 한도를 초과 | fixture 불일치 확정, timeout의 단독 원인인지는 저장 응답 부족으로 미확정 | 유효 길이 별칭·전체 입력값 readback. GET native 거부(현재 :4473은 200도 허용), 폼/주소 부재, 요청 후 B 실제 인증을 별도 기록. B own POST 저장 대조 → 정확한 A 대상 POST → 거부/내용 부재 → B 상태/주소 재조회 → A 재로그인·원래 주소 fresh readback. 권한/CSRF 유지 |
| 2 상품 검수 | HTTP200, unsupported URL 알림 대기에서 문구 불일치. verifier:43,1097 `Amazon Japan 또는 Rakuten`, controller:116 `아마존 일본 또는 라쿠텐` | 검증기 locale drift 확정. 이전 HTTP500과 동일 원인 아님 | 한국어 기대값 일치 후 URL 거부·권한·CSRF 유지. batch 저장/재조회·검수 수정/승인/반려·native draft·same-ID 게시/고객 cart까지 실제 도달/통과 |
| 3 검색 | mobile partial/search_submit, document_changed=false, native GET form/submit visible, HTTP 응답 미관측. verifier:135 Enter 사용 | 브라우저 입력/제출 경로 의심. 서버 검색 결함 확정 아님 | native submit 버튼으로 실제 제출·query/input readback 유지. PC/mobile exact/partial/missing·결과/상품 이동 재검증. timeout만 늘리지 않음 |
| 4 메일 | JA `order_confirmation_raw_mime` RuntimeError. verifier:332-346은 stage/예외종류만 기록 | 전달/메시지 식별/수신자/MIME/본문 중 최초 원인 미확정 | 비식별 고정 failure code로 분류. JA/EN/KO 등록·주문 raw MIME, 정확 수신자·새 메시지·본문 locale·주문 참조, DB 언어/state readback. reset mail 성공과 구분 |
| 5 성능·접근성 | `contact_ja:request_error`, interaction_control_unavailable/result_invalid. home/product는200 | route 인코딩/반응형 selector 가정 의심; 실제 수치별 예산 판정도 미완료 | raw Unicode HTTP path 처리·desktop/mobile 실제 보이는 control 확인. 세 경로×두 viewport 보고서와 예산별 점수/수치·axe rule별 결과 확보. 기존 목표 유지 |
| 6 사이트맵 | `verify_ci_sitemap_routes.py:96-121` robots HTTP readback에서 AssertionError | 실패 predicate 미확정. 현재 정보로 robots 앱 결함/테스트 가정 구분 불가 | URL/본문 없이 고정 오류코드·HTTP 상태로 최초 조건 특정. robots→index/locale HTTP 검사. 현재 검사는 pending seller의 빈 sitemap만 대상으로 하므로 approved seller의 실제 URL 검증 별도 |
| 7 주문 후 gate | 상품→cart assertion에서 중단; gate 검증 미도달. workflow:2889는 최신 active `KURANEA-CI-%`를 선택 | 정확한 상품/재고 fixture 선택 문제 가능. checkout 개방 증거 아님 | exact run `CI_TEST_PRODUCT_ID`/reference·disposable stock 전제 확인 후 cart→차단 gate 검증. 성공 뒤 실제 의존 bank-transfer·returns·audit 범위 실행 |

주소 GET의 실제 trace는 네트워크 302→404이고 A 편집 폼·주소 내용 부재를 확인했다. 그 후 B canonical account의 identity/network assert를 통과해야 대조 주소 생성 단계로 간다. 다만 현 결과 스키마에는 명시 after-request flag가 없고, 후속 POST/A 재조회 false는 미도달이다. **현재 증거는 개인정보 유출/변조 확정이 아니다.** `psgdpr`라는 마지막 control 이름만으로 이 timeout의 원인을 동의 체크박스라고 확정하지 않는다.

성능 로그 `lighthouse=4/6 axe=4/6 interaction_lab_proxy=0/2`는 `run_quality_audit.py:503-505`의 **생성된 측정 항목 수**다. 4개가 통과했다는 뜻이 아니다. 현 보고서 범위는 home/product/contact × 390/1440px이며 실제 INP field measurement는 없다(:413). 클릭→paint proxy는 INP 달성 근거가 아니다. 원본 목표는 mobile90/desktop95, A11Y/SEO95, LCP≤2.5s, CLS≤0.1, INP≤200ms이며 목표/측정 가능 범위를 명시한다. 실제 사용자 field INP는 출시 전 합성 검사로 생성할 수 없으므로 측정 없음과 운영 계측을 구분한다.

#### 기존 요구사항표 39개 추적 항목 전수 대조

상태는 사용자 지정 5개 값이다. 한 행의 상태는 전체 해당 요구를 기준으로 하고, 이미 통과한 하위 범위는 증거/잔여 열에 보존한다. 새로운 독립 결함 없이 기존 성공 기능을 재개발 대상으로 돌리지 않는다. 집계는 해당 범위 검증 완료14, 검증 미완료15, 구현 미완료4, 외부 대기5, 제외1이다. 추적 항목별 크기와 하위 범위가 달라 이 숫자로 플랫폼 완료율을 계산하지 않는다.

| ID | 현재 상태 | 검증된 범위와 정확한 잔여 |
| --- | --- | --- |
| PLAT-001 | 구현과 해당 범위 검증 완료 | 격리 CI 설치/cleanup. 운영 인프라·배포는 OPS-ENV-001 |
| QA-REG-001 | 구현과 해당 범위 검증 완료 | native cart/무료 carrier 저장·fresh readback의 기존 합성 성공. 최신 주문후 gate 검사는 별도 실패 |
| BRAND-001 | 구현과 해당 범위 검증 완료 | 원본3/파생17·hash/manifest·게시/upload/reset-logo 연결. 전체 배경 시각/판매자 승인 별도 |
| PROFILE-001 | 구현됐으나 검증 미완료 | draft/preview/publish/history/새 초안 restore 구현. 전 locale/field·별도 role·저장→fresh read→고객출력→restore 인수 보완 |
| CAT-001 | 외부 자료·운영 환경 대기 | 허용 fetch/parser·합성 fixture 존재. 실제 승인 marketplace 원문/feed 및 권리 호환 미검증 |
| CAT-002 | 구현됐으나 검증 미완료 | 기본 **indexed shop DB** batch/review 저장 구현. JSON 기본이라는 matrix 표현은 오래됨. 최신 browser 실패 |
| CAT-003 | 구현됐으나 검증 미완료 | 검수 승인/반려/담당·시각·중복방지 구현. 최신 실제 검수/권한/재조회 인수 미완료 |
| CAT-004 | 구현과 해당 범위 검증 완료 | 기존 합성 inactive native draft·판매값/원문 분리·편집·동일ID 재수집. 실상품/게시 범위 별도 |
| CAT-SCALE-001 | 구현됐으나 검증 미완료 | DB transaction/index와1k/10k/100k 검사 구현; 최신 skipped. lookup p95≤250ms, page/count≤1s 실제 보고 필요. storefront100k 검색부하 증명과는 별개 |
| DOC-001 | 구현과 해당 범위 검증 완료 | catalog README의 제한·DB/JSON 구분 존재. 상태문서의 오래된 최신/미구현 표기 교정 별도 |
| GAP-002 | 구현됐으나 검증 미완료 | 명시 native publish→fresh flags→같은ID 고객화면/cart 검증 소스 존재(:1899-2020). 최신 최초 실패로 통과 미입증 |
| ACCT-001 | 구현됐으나 검증 미완료 | 기존 회원/중복/login/logout/profile/reset 성공 보존. 최신 POST 포함 account 전체 실패 |
| LOCALE-001 | 구현됐으나 검증 미완료 | 3언어 selector/category/PWA 등 부분 성공. 구매·계정·문의·정책·메일의 전체 화면/오류 inventory와 실제 상품 번역 미완료 |
| LOCALE-002 | 구현과 해당 범위 검증 완료 | 합성 JA 동일 주문 상세/운송장 label. 실제 출고/모든 언어/실기기 아님 |
| LOCALE-003 | 구현과 해당 범위 검증 완료 | KO 주소 목록/편집 helper 자동검사. 최신 독립 시각은 VIS-001 |
| DISC-001 | 구현과 해당 범위 검증 완료 | 합성 JPY 세금포함/쿠폰·수량·10%/명시 면세/무료배송. 실제 SKU 세금 판단 필요 |
| ADDR-001 | 구현과 해당 범위 검증 완료 | 공식 KEN_ALL import/우편번호·선택·수정·native 주문 저장/관리자 readback. 운영 refresh/지역 조건 별도 |
| ADDR-002 | 구현됐으나 검증 미완료 | 본인 주소 create/edit·기존 GET 격리 성공 유지. 새 POST/요청후 인증/최종 원소유자 보존 acceptance 미완료 |
| ORD-001 | 구현과 해당 범위 검증 완료 | 합성 주문별 안내·권한/CSRF/금액거부·one-use 확인/replay·receipt/payment/history·고객 paid 반영. 운영 계좌/정책 대기 |
| OPS-RET-001 | 구현과 해당 범위 검증 완료 | native 합성 취소/RMA/credit-slip. 최신 dependency skip은 새 반품 결함 아님. 실제 현금환불/정책 별도 |
| OPS-SHIP-001 | 구현과 해당 범위 검증 완료 | 합성 carrier/tracking native 저장/고객 표시. 계약/실제 출고/scan/추적URL 미입증 |
| CS-001 | 구현과 해당 범위 검증 완료 | 문의·주문/첨부·공개답변·내부메모 비노출·상태·배정 이력·고객격리/고객반영 합성 성공. 실시간 채팅 완료 아님 |
| WAL-001 | 기존에 명시적으로 확정된 범위 제외 | 현금성 지갑·작업수익·출금 제외 유지. 대체 포인트 기능을 새 필수로 추가하지 않음 |
| ADMIN-KO-001 | 구현됐으나 검증 미완료 | native KO import/partial9XLF·선택 화면 검사. 전체 core/menu/필드/help/error/toast/report/mail·직원/시스템 화면 인수 없음 |
| ADMIN-REC-001 | 구현과 해당 범위 검증 완료 | admin recovery/reset/replay·기존 보안 범위 성공. 운영 전달/모든 직원 기본 locale 별도 |
| PWA-001 | 구현 미완료 | manifest/SW control/update/offline503/private-cache 합성 성공. 원본 static-resource cache·설치 안내는 구현 근거 없음. 이후 foundation spec의 ‘이번 변경 non-goal’은 영구 제외 아님 |
| PWA-DEVICE-001 | 외부 자료·운영 환경 대기 | native 설치 prompt/standalone 실행·복귀·업데이트 iOS/iPadOS/Android 인수 없음. HTTPS·기기 필요 |
| PWA-002 | 구현 미완료 | consent/refresh/revoke/owner isolation·outbox 합성 성공. 실제 provider adapter·실행 worker/schedule·발송/수신 미구현 |
| MAIL-001 | 구현됐으나 검증 미완료 | reset/admin recovery 성공. 등록/주문 raw MIME JA 실패로3언어 인수 미완료; SMTP 외부 대기 |
| SEO-001 | 구현됐으나 검증 미완료 | JA 합성 Product/Offer 성공. robots HTTP 실패, category/locale·실상품·approved gate sitemap/운영 canonical 검증 필요 |
| SEARCH-001 | 구현됐으나 검증 미완료 | 과거 JA PC/mobile 성공 유지. 최신 mobile partial 제출 실패. EN/KO·실상품 관련도/부하 별도 |
| PERF-A11Y-001 | 구현됐으나 검증 미완료 | 측정 tool/budgets 구현. 최신 outcome 실패;10width·키보드/스크린리더·axe incomplete 수동 판정·실제 수치 필요 |
| SECURITY-001 | 구현됐으나 검증 미완료 | token/role/shop/owner/upload/escaping/no-store 통제와 일부 성공 존재. 주소 POST·변경경로 회귀·운영 secrets/TLS/role 검증 미완료. 전체 취약점 부재를 주장하지 않음 |
| AUDIT-001 | 구현 미완료 | 5-source READ별/shop별/읽기전용50행 feed 구현. native UI acceptance skipped, catalog decision/개별 권한변경 전체 event coverage·target 연결·보존 미완료 |
| BACKUP-001 | 외부 자료·운영 환경 대기 | 최신 isolated DB/files/queue restore/restart 성공 유지. 실제 durable storage/암호화/보존/RPO/RTO/owner·운영 restore drill 없음 |
| SELLER-001 | 외부 자료·운영 환경 대기 | published approved seller와 외부 승인 없으면 fail-closed. LOGISTEED reference는 승인 증거 아님 |
| CAT-ENV-001 | 외부 자료·운영 환경 대기 | 실제 허용 URL/feed/export·이미지/후기 권리·지원 SKU 옵션 확인 필요. CAPTCHA 우회 없음 |
| VIS-001 | 구현됐으나 검증 미완료 | 기존 캡처 존재. 최신 안정 SHA 전체 주요화면·3언어·PC/mobile·밝고 어두운 배경 독립 검수/실제 전달 근거 없음 |
| OPS-ENV-001 | 구현 미완료 | local/CI Compose·운영 runbook만 존재. 운영 artifact/promotion·승인신호 주입·TLS/SMTP/backup/rollback/monitoring 구성/실증 없음. host/owners 외부 대기 |

#### 관리자와 감사의 남은 구체적 범위

원본 ADMIN_KOREAN_REQUIREMENTS:233-254의16동선 중 지갑/수익/출금9-11은 제외다. 나머지는 로그인/복구, 대시보드, 상품등록/편집/수집, 주문, 입금, 상담, 배송, 직원/권한, 회사정보, 시스템설정, 오류/알림이다. 선택된 화면 성공을 유지하면서 다음 공백을 닫아야 한다.

- `verify_admin_security_browser.py:1885-1905,1922-2005`는 custom4/Orders/dashboard/설정 일부만 검사. Employees/Profiles/Permissions/Preferences 추가 검사는 현재 원격에 없다. 전체 Parameters/Modules/Design/Maintenance 및 error/toast/mail/report inventory와 별도 role 저장/로그인 재조회가 필요하다.
- KO pack runtime import(`docker/kuran-post-install.php:37-52`)와 Employee1 locale 설정(:149-154), request locale 강제는 전체 직원 기본값/모든 문자열 완료 증거가 아니다. pack version/source 기록과 누락/업데이트 회귀 필요.
- `AdminAuditEventRepository.php:48-54,129-154`는 employee profile/order status/support assignment/transfer instruction/receipt의 **5 sources**. source별 READ·selected shop·비밀 제외·50행 lookahead는 재사용한다.
- catalog 승인/반려의 실제 검수 대상과 연결한 append event, 권한표 개별 변경 등 high-impact mutation coverage는 없다. `AdminKuraneaEmployeeProfileAuditController.php:67`도 누락 범위를 명시한다. transaction·중복방지·append 실패 rollback·대상 참조·role/shop·fresh UI readback 인수가 필요하다. 이전 opaque-reference 로컬 패치는 적용 증거가 없다.
- 보존기간/독자역할/DB 운영자 변경통제·대량이력 조회/복구 정책은 운영 책임과 개발 양쪽이 필요하다. 모든 DB를 무조건 변경 불가능하게 만들거나 새 유료 ledger를 도입해야 한다는 뜻은 아니다.
- ProfileVersionService:54-93,236-279와 VersionedProfileRepository:40-112의 draft/publish/history/새 draft restore·은행 전용권한 분리는 이미 구현됐다. 재제작 대신 locale/role/고객반영 인수를 보완한다.

#### 요구사항표 밖으로 빠뜨리면 안 되는 작업

1. **안전한 public static cache·설치 안내:** Master:777-791 요구. SW:167-191은 network fetch와503 fallback이며 CacheStorage가 없다. private cache 금지 유지하면서 원본 요구를 처리해야 한다.
2. **실제 Push:** PushOutboxService:9-16 default는 DisabledPushDeliveryProvider이고 native producer도 provider 없이 enqueue만 한다. provider/worker/retry 실행·승인 consent/VAPID/HTTPS·기기 수신이 남는다.
3. **운영 승인 신호 전달:** CommerceGate:28-37은 published approved seller + 외부 승인 + publish validation을 요구한다. 모듈:1444-1446이 읽는 `ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED`의 운영 전달/절차가 base Compose·env example·배포 runbook에 없다. 승인 전 차단을 유지하며 운영 정의와 staging 인수를 구현해야 한다.
4. **불변 app artifact와 승격/롤백:** DB와 PrestaShop base는 digest 고정돼 있다. 그러나 app은 local mutable build tag(`compose.yaml:22-25`). SHA/gitlink/app digest/migration set·registry·같은 artifact 승격·이전 digest+schema 호환 복귀 증거가 없다.
5. **운영 감시/대응:** Master Phase7:1115-1126 필수. Compose healthcheck는 있으나 HTTP/error/DB/disk/backup 실패 alert destination·운영 비식별 로그 정책·on-call/rollback 담당·시험 증거 없음.
6. **10개 폭과 수동 접근성:**320/360/375/390/430/768/1024/1280/1440/1920px 주요화면·locale 길이·menu/filter/cart/checkout/상담 버튼 실제 검수. axe incomplete는 수동검수 필요 표시이며 전체 WCAG PASS가 아니다.
7. **조건부 실시간 채팅:** Master:631의 “가능하면 자체 상담 기능” 아래 실시간 채팅이 있다. 구현은 비동기 thread 상담이다. 확정 필수 blocker나 확정 범위 제외로 임의 변경하지 않고 조건부 미구현 요구로 남긴다.
8. **실제 옵션 한계:** catalog README:25는 Cartesian/균일가격 형태만 지원. sparse/조합별 차등가격 출시 SKU가 필요하면 adapter 구현이 추가로 필요하다. SKU 자료 없이 전체 실상품 호환을 완료 처리하지 않는다.

#### 외부 입력 — 이미 승인된 자료를 재요청하지 않는 단일 목록

재사용 가능한 승인 자료는 ORDENOWA 표기/JA 설명·슬로건, 공식 원본3종/파생17종, JPY 세금포함 표시, 지원 일본지역 무료배송 정책이다. 다음은 저장소에서 실제 운영값/연결 증거를 확인하지 못한 항목이다. 외부 시스템에 전혀 없다는 단정은 아니다. 비밀값은 채팅/Git가 아닌 승인 secret-store reference로 연결한다.

| 필요한 값·승인 | 사용 위치 | 없어서 막히는 일 |
| --- | --- | --- |
| 실제 seller 법적 신원/책임자·판매권한·ORDENOWA 관계 | seller published profile, 법정표시, commerce gate | 실제 판매자 공개·거래 활성화 |
| 고객센터 전용 연락처/시간·직원 role/배정 정책·JA/EN/KO 약관/개인정보/특정상거래법/배송·반품·환불 문안 | 고객지원/법률/메일·배정 | 실제 고객 지원/법정표시/운영 권한 |
| 허가 source/feed/export, 출시 SKU·3언어 텍스트·taxonomy·판매가/재고/옵션/세금·이미지/후기 권리 | parser/review/native publication/search/SEO | 실제 상품 호환·게시·주문·실상품 번역/세금 검수 |
| 계약 carrier/service·지원지역/도서·출고/추적조건·무료배송 부담자·반품주소/비용/기한·현금환불 담당 | carrier/checkout/운영 반품 | 실제 출고/배송/반품/환불 인수 |
| 판매자 승인 계좌·입금 대조 정책/담당자 | 안내/receipt·수동 입금 확인 | 실제 은행 안내·입금/환불 운영. 카드PG는 초기 필수 아님 |
| 승인 push notice/version/locales/retention/수신자정책·VAPID reference | consent/provider/worker | 실제 Push 발송/수신과 보존 책임 |
| host/owner·domain/DNS/TLS/proxy/firewall·resource·SMTP sender/test inbox·secret store·registry·deploy/admin/rollback owner | 운영 정의·release artifact·승인신호·메일 | HTTPS 운영 설치/승격·실메일·안전한 활성화/복귀 |
| durable backup target·암호화/키 보관·권한/보존·RPO/RTO·별도복구 대상/책임자 | backup/restore/rollback | 운영 백업·복구 drill |
| high-impact event 범위·감사 독자role·보존/예외정책·감사책임자·장애알림 수신자 | audit/monitoring | 이력 인수·감시/대응 운영 |
| 승인 HTTPS target·iOS/iPadOS/Android 실기기 또는 승인 원격기기 | native PWA install/standalone/update/resume | 실기기 인수. Chromium mobile emulation으로 대체 불가 |

#### 완료 순서와 오늘 출시를 위한 판정문

동시에 진행할 수 있는 것은 (A) 코드/집중검증, (B) 승인 자료/운영 준비, (C) 독립 화면·실기기 검수다. A가 통과해도 B/C의 증거를 대신하지 않는다. 원본 요구를 축소하는 범위 결정이 없으므로 선택사항으로 몰래 이관하지 않는다.

1. 원격 `e357b8b`에 없는 미회수 패치를 확인하고, 복구 불가면 현재 원인에 근거해 필요한 부분만 구현한다. 주소 별칭/거부응답/인증 결과, catalog 한국어 문구, search native 제출, exact checkout fixture를 우선 처리한다. mail/robots/perf는 안전한 실패코드로 최초 원인을 특정한다.
2. 주소 **POST 포함** 집중 QA를 실제 의존 install/mail/account 단계와 함께 닫는다. 나머지는 관련 집중검사→원인수정→저장/새 요청 재조회로 묶어서 처리한다. assertion/권한/CSRF/no-store/소유권/예산/시간제한을 낮춰 통과시키지 않는다.
3. 자료 없이 가능한 Push provider/worker, PWA cache/안내, 관리자 한국어·감사 coverage, 운영 정의/승격·rollback·monitoring을 구현/인수한다. 비밀값/운영 대상에 의존하는 단계는 위 단일 목록에 묶는다.
4. catalog browser 성공 뒤 scale1k/10k/100k·same-ID publication과 의존 bank-transfer/returns/audit 범위를 실행한다. **안정된 같은 코드 SHA**에서 전체 격리 QA aggregate/cleanup 통과, artifact·실제 수치 확보. 현재코드 unchanged 재실행은 하지 않는다.
5. 같은 SHA의 출시 SKU/seller/legal/role·메일·HTTPS·백업복구·10width/3locale/수동접근성·native PWA·독립 시각 인수를 완료하고 결함을 닫는다. handoff에는 SHA/image digest/artifact/변경 화면/기대값·잔여 한계를 기록하고 실제 전달 여부를 따로 표시한다.
6. 담당자가 승인된 seller/profile/상품/운영 자료와 검증된 app digest·migration/backup/rollback·운영자/감시 수신자를 갖춘 뒤 기존 운영 전환 승인 절차를 수행한다. 이번 조사는 배포 권한 변경이나 실거래 실행이 아니다.

**오늘 출시 가능 조건:** 위 개발·검증·운영 입력이 오늘 실제로 모두 닫히고 동일 artifact의 전환 인수가 통과한 경우에만 가능 판정한다. 현재는 미구현·실패 원인 미확정·자료 대기가 함께 있어 일정 확약이나 임의 시간 추정은 하지 않는다. 즉시 서버에 local Compose를 올리는 것만으로 기존 필수 요구를 충족한 출시가 되지는 않는다. 외부 자료가 전부 준비돼도 남은 코드/검증 공백은 독립적으로 해결해야 한다.

#### 기록 교정·이번 조사 한계

- 기존 matrix의 JSON 기본/scale 구현 미완료는 현재 indexed DB 및 scale acceptance 소스와 불일치한다. 반대로 최신 검색 완료·새 메일 미실행·과거 candidate32ab를 최신으로 쓰는 상태도 실제 최신 결과와 불일치한다. 이 보고서의39행 대조와 실제 run 결과를 최신 판정으로 사용한다.
- CURSOR_HANDOFF의 catalog 최초 실패가 batch 이후라는 서술은 unsupported URL 알림 locale drift 증거로 교정해 읽어야 한다.
- 상거래·브랜드·reset·PWA private-cache·백업의 통과 범위를 보존한다. 미실행/false/timeout에서 유출·거래 개방·운영 손실을 추정하지 않는다.
- 이번 조사에서는 새 테스트/설치/전체 QA를 실행하지 않았다. artifact 전체 화면·개별 Lighthouse JSON·실제 외부 운영 시스템/기기는 검수하지 않았다. 운영값은 repository 기록 및 연결 증거 기준이며 조직 전체에 자료가 없음을 단정하지 않는다.
