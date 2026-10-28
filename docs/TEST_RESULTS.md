# ORDENOWA 테스트 결과

## 2026-10-29 Amazon parser regression and latest acceptance

Code under test is [`d107cf9042c1a041c7c32b820c10e0b3874056e9`](https://github.com/goldeget/japan-premium-commerce/commit/d107cf9042c1a041c7c32b820c10e0b3874056e9) on remote `work`. It adds source breadcrumb paths and one canonical image URL per visible Amazon image gallery entry. It keeps `#productTitle` as the selected HTML title, keeps exact JPY parsing fail-closed, leaves option inference unchanged, and treats image URLs as source metadata rather than reuse permission.

- Test-only commit [`a62e902`](https://github.com/goldeget/japan-premium-commerce/commit/a62e902eae5082c655e16fa04914757696c0b1c1) added a synthetic Amazon gallery/breadcrumb fixture. Its focused pre-fix run [#40772668598](https://github.com/goldeget/japan-premium-commerce/actions/runs/40772668598) failed after PHP lint, confirming the regression gate was red before the parser patch. The workflow redacts assertion details; it reported `UNKNOWN/source unavailable`.
- Post-fix focused run [#40774173388](https://github.com/goldeget/japan-premium-commerce/actions/runs/40774173388) passed PHP lint, **41 parser quality behaviors**, synthetic marketplace access-challenge rejection, and workflow contract tests.
- Post-fix full isolated platform run [#40774173140](https://github.com/goldeget/japan-premium-commerce/actions/runs/40774173140) passed **38/38 unique phases**, aggregate `passed=true`, and run-owned cleanup. Artifact [#12855260313](https://github.com/goldeget/japan-premium-commerce/actions/runs/40774173140/artifacts/12855260313) has SHA-256 digest `sha256:1b5aa21a03492ed6ad631ea0710f04ae968af45914b81e969cad196cea0bae4a`.

Live-source limitation remains: Amazon [B0H4V3GT4J](https://www.amazon.co.jp/dp/B0H4V3GT4J) showed no exact current price; parser rejection is expected. Page metadata timestamp was 2026-10-20. Rakuten candidate timed out; no live price/options/image rights were verified. No source product was imported. The patch changes only the parser; no public UI changed. Main SHA remains `ee02a3657448d563508687614a246e05ac61eecd`.

## 2026-10-29 현재 발주 플랫폼 검증

### 이전 통합 검증 기준점 — 91c6098 / 전체 격리 QA SUCCESS

검증 코드 **`91c6098c6b551946cc8291b31c868656d50c9b34`**를 원격 work에 저장하고 변경 파일 재조회·새 원격 복제본으로 일치 확인했다. main **`ee02a3657448d563508687614a246e05ac61eecd`**와 원래 사용자 체크아웃/운영 DB·volume은 보존했다. 이후 문서 저장 HEAD와 검증 코드 SHA는 구분한다.

전체 [#40763074207](https://github.com/goldeget/japan-premium-commerce/actions/runs/40763074207)는 최종 **SUCCESS**, 실제 **38/38 phase PASS / aggregate passed=true / cleanup success**다. native browser16단계·3언어 회원/reset·공식 ACL·메일/Push mock·재시작/독립 복원까지 통과했다. 초기/재시작 앱1140·Pushvendor1426 파일이 정확한91코드와 일치했다. [artifact12850640042](https://github.com/goldeget/japan-premium-commerce/actions/runs/40763074207/artifacts/12850640042), ZIP SHA256 **`5c01e0d4b070875e3bac1e75b4586ee20113748a298039dc1a2f5589c4c69802`**를 직접 확인했고 [원본12JSON·24PNG·무결성 명세](evidence/2026-10-29-procurement-local/fresh-91c6098-complete/)를 보존했다.

직전 실패는 실제200ms 링크 font/padding 전환이 끝나기 전에 캡처한 QA 순서 문제였다. 기존30초와 full rect/center hit/privacy geometry/enabled/stable scroll·권한 조건을 유지한 수정으로13unit·실제D20target·저장 재조회가 통과했다. 별도 GPT는 **새 hosted24PNG를 모두 실제 열었고 핵심20target(3언어9메뉴·9요청확인·2사진)을 인수**했다. JA/KO 글리프·부모/하위 분류·최종 버튼/사진쌍이 보인다. 전체 텍스트를 치환한 나머지4포인트 PNG는 의미/geometry 인수 근거로 쓰지 않는다. [독립 실제 검수](evidence/2026-10-29-procurement-local/fresh-91c6098-complete/ordenowa-independent-final-hosted-40763074207-review.md).

최신 품질은 JA7경로/10폭+일부dark의7privacy·84layout·84axe·14실제클릭·14Lighthouse PASS다.14건 성능/접근성100, 공개정책SEO100, 모바일LCP최대1747.3ms/CLS0.0001이다. axe위반0이지만84셀 incomplete와 기존 제한된13패턴 수동 검토를 유지한다. 전체WCAG·실사용INP·실기기 성공으로 확대하지 않는다.

로컬D의 요청/원장/포인트계정0·ACTIVE1과 원래A/B/C/80P·업무12/ACL감사8/메뉴2/상품·사진 보존을 확인했다. 새D의 native언어 전환 `id_lang/date_upd`와 접속/session telemetry만 별도 기록했다. [로컬 집중·정확한 보존 범위](evidence/2026-10-29-procurement-local/real-two-level-category-focus/). **핵심 구현과 명시한 합성 격리 검증은 완료했으며, 실제 상품·운영 정책/환경·기기 인수는 남아 있다. 운영 출시 완료는 아니다.**


### 직전 재확인 — 587bdf4 / 전체 QA 실패 원인 집중 조사

당시 로컬·원격 work는 `587bdf484d5e3b27084b99870ccdbedc914bdb7a`이며 main은 `ee02a3657448d563508687614a246e05ac61eecd`를 유지한다. 앱 소스는 d4e470a와 같고587 변경은 CI의 native 관리자 대상 토큰·화면 캡처·CJK 폰트 환경이다.

전체 [#40759815264](https://github.com/goldeget/japan-premium-commerce/actions/runs/40759815264)는 **28phase PASS / native_browser FAIL / 후속9 not_run / cleanup success**다. 폰트 JA17/KO12 glyph 및 오프라인11+61은 통과했다. 첫 실패는 실제2단계 카테고리의 새 target capture(main394), 첫PNG 전이다. 실제 D 재현에서 모든 target rect/center hit와 즉시 privacy geometry는 통과하고 screenshot 후 scroll 안정성만 실패했다. native 링크의200ms font-size/padding CSS 전환이 캡처 전후 running(99.9→166.6ms)이어서 문서 높이/scroll이 바뀌는 검증기 순서 문제를 확정했다. 기존30초 내 실제 CSS 전환 완료를 관찰하는 수정과 집중 재검증을 진행한다. artifact **12847477729**, ZIP SHA256 `57f41209767259df3d2517f94de8f204fabc7cf56f5b9d72619e69168532fecb`. [안전한 결과](evidence/2026-10-29-procurement-local/fresh-587bdf4-partial/).

이전 d4e470a/#40757330613도 완료 **FAIL**이며 native 조회전용 관리자의 대상 controller 토큰을 잘못 복사한 QA 문제를 실제 native form action200과 대조해 수정했다. 현재 helper의 정상 READ GET3건200·각 대상의 유효 body token을 사용한 변경 POST4건403·보호 데이터 무변경을 집중 확인했다. [집중 증거](evidence/2026-10-29-procurement-local/native-reader-token-focus/).

해당 d4e artifact12847660925의20PNG는 실제 독립 검수에서 JA/KO 글리프 누락 및 target이 캡처 밖인 문제가 확인되어 시각 PASS가 아니다. 로컬 새 target15PNG는 범위 내 PASS지만 Home-only 메뉴로 실제2단계 메뉴 인수를 대신할 수 없다. 동일 소유 격리 환경의 별도 D 합성 상품·고객으로 실제2단계 메뉴/필터와 캡처를 집중 재현 중이며 최종 제출·지급은 하지 않는다. 원래 고객·요청·원장은 보존하고, native 분류 생성의 기존 nleft/nright 재번호만 허용한다. 새 자료 없이 같은 QA를 반복하지 않는다.

당시 검증 코드: **`d4e470ae005a27568b260653107dfe62074fbc6a`** (원격 work 저장·변경 파일 일치). 최종 단일 SHA 전체38phase [#40757330613](https://github.com/goldeget/japan-premium-commerce/actions/runs/40757330613)는 완료 FAIL이며 최신 집중 조사는 위587bdf4 절을 따른다.

| 검증 | 실제 결과와 범위 |
|---|---|
| 도메인·저장 | PHP8.3/MariaDB 요청 snapshot·권한·rollback·12개 동시 경합, 수동 지급/연결 정정·원장 대조·동시 지급, 채널별 outbox·UNCERTAIN 중단 복구 PASS |
| 정책·문의·보안 | 정책 저장/새 연결/감사 rollback·6경합, native 문의 연결/본인·shop·공개/내부·멱등·6경합 PASS. 실제 잘못된 POST body token403/무변경, 정상 정책 저장/새 관리자11필드 재조회 PASS |
| 실제 브라우저 핵심 | 운영 배정→수량2 요청, 고객B GET/POST 거부·본인 인증 유지·A원본 보존, 제한 직원 검토/지급/정정403, 승인0P→별도100P→재로그인100P→정정80P, 문의 공개/내부 분리 PASS |
| 메일·계정 | 실제 native Mailpit5건(EN1/KO1/JA3)·재전달0·raw MIME 링크/제목/비노출 PASS. JA/EN/KO 가입·중복 거부·주소 없음·login/logout/reset·이전 비밀번호 거부/새 로그인 PASS. 운영 SMTP 미검증 |
| 관리자·감사 | 공식 native ACL 실제 브라우저 grant/revoke·정확6감사·다른 권한 보존 PASS, 실제 DB 원자성31검사 PASS. 한국어17경로 재조회·정적 누락7종 수정·실제5Tab CAS/멱등·DB12검사 PASS |
| 파싱·Push | 합성 parser38행동·기존 catalog suite·명시적 fixture smoke77 PASS. AggregateOffer 모호 가격 거부. 실제 locked minishlink9.0.4 VAPID/AES128GCM+mock201/410/503/native autoload PASS. 실제 상품 원문·기기 수신 미검증 |
| 렌더·PWA | 실제 Smarty 고객72/정책169/문의18/메뉴24/signin81/언어선택41 PASS. 새 PWA Node2·기존 SW73 PASS. 최종3언어 computed name/키보드·카탈로그 병합 보존 PASS |
| 품질3 | 실제 native JA7경로·10폭+dark 일부: layout84/axe84/실제 클릭14/Lighthouse14 PASS. 성능99–100·접근성100·공개정책SEO100·최대LCP2131.1ms·CLS0.0001. field INP 미측정 |
| 독립 시각 | 별도 GPT가 안전한 고객21+54PNG, 정적 구성요소42PNG, 언어선택3PNG를 실제 열어 검수. 추가 native 관리자12PNG의 top viewport도 독립 검수. 관측13패턴에 확정 결함 없음. 자동 incomplete84셀 유지, 전체WCAG·보조기술·실기기 PASS 아님 |
| 소스·복원 | 최신 app1140/vendor1426 정렬, native 기준 파일/CCC 분류·unknown0; 재시작과 별도 복원 DB12테이블+native 상담/ACL hash 일치 PASS. 기본512M 실제 cache:clear WITH warmup PASS |
| CI 수정 | 6f9c301 portable build/sanitized evidence5검사 PASS. root 최초 unittest module경로 호출은 import 오류였고 표준 discover 경로에서5PASS; 제품 실패가 아니다 |

[안전한 결과·캡처·독립 검수](evidence/2026-10-29-procurement-local/README.md)를 보존한다. 로컬 집중 검증은 bd1ced8 이미지+후속 정렬/부분 수정 결과이며 최신 immutable fresh aggregate와 동일시하지 않는다. 초기 품질1 실제 label mismatch·품질2 이전 소스 결과 및 중간 continuation FAIL은 기록을 유지하고 최신 품질3/집중 후속 결과와 구분한다.

### 실제 원격 결과

- business-profile [#40746034641](https://github.com/goldeget/japan-premium-commerce/actions/runs/40746034641), cc99bbb: SUCCESS.
- parser [#40737085749](https://github.com/goldeget/japan-premium-commerce/actions/runs/40737085749), 3035be7: SUCCESS.
- 첫 fresh #40746215184(4f8c18e): FAIL/cleanup success; artifact12840743415.
- 두 번째 #40747596953(77b2ceb): image_build FAIL/나머지37 not_run/cleanup success; artifact12841243413.
- 세 번째 #40748071562(4faa400): image_build FAIL/나머지37 not_run/cleanup success; artifact12841443567, ZIP SHA256 `a6f591c558a19097bed40e68a5187d0750bc3410357a7d110637386918cee930`. 보존된 안전 tail에서 host network/외부CA 파일 Bake 권한 요구 확인. 앱 실행 전 실패이며 개인정보 유출·앱 결함으로 단정하지 않는다. 6f9c301에서 원인 수정 후 위 최신 run 검증 중.
- 과거 쇼핑몰 전체 [#40508152705](https://github.com/goldeget/japan-premium-commerce/actions/runs/40508152705), f5b1cca: 당시 범위 SUCCESS 유지. 아래 ‘최신’ 표기는 각 기록 시점에 한정한다.

### 최신 로그인 진입 원인 수정과 재검증

실제 fresh #40749362584(6f9c301)는 **28phase PASS / native_browser FAIL / 후행9 not_run / cleanup success**다. 빌드·설치·1128app/1426vendor·한국어 bootstrap·검수 상품의2단계 카테고리·기본512M warmup은 통과했다. 최초 브라우저 실패는 category UI 전 `login_customer`의 이메일 입력란 대기였다. raw authentication+id_lang의 실제404/폼0과 native 생성 링크200/폼1을 대조했고, **수정한 helper로 A/B 각각 새 브라우저의 정책9경로→로그인→정확 본인 확인이 PASS**했다. 12domain/8ACL·감사/3critical hash 불변이다. 1aca9e9은 네이티브 생성 auth/identity URL과 same-origin guard를 사용하며 원래 로그인·신원·타임아웃 조건을 유지한다. 오프라인8계약 PASS 및 CI 사전 실행을 추가했다. 후속 #40750834639는 정책 저장 새 세션 version 재조회에서 FAIL했고 아래 원인 수정과 구분한다. 이전 실행은 FAIL로 보존한다. [안전한 집중 증거](evidence/2026-10-29-procurement-local/login-route-focus/modified-helper-outcome.json), artifact12843502379/ZIP SHA256 `13978d20868ce9629743cafd1c8c283167d1ca49a360e63b0b470cdf58feaef0`.

### ad51cff 최종 수정 묶음과 집중 결과

- #40750834639/1aca9e9:28phase PASS/native_browser FAIL/후행9 not_run/cleanup success. artifact12844705387 SHA256 `2ea6f0f498b26eefc800b4b23c6adfbcf85d78d8276caad84e7db089f9b8c795`. 실제 클릭27.52ms 뒤 정책POST33.33ms 시작·302161.79ms·최종200문서4313.06ms를 확인했다. 단1회 저장/정확1policy+1audit/새 세션13값/다른 데이터 보존 PASS. 수정은 이전 form stale와 새 문서 complete를 같은30초에 기다리며 모든 저장값/버전 검사를 유지한다.
- native 관리자69노드 GET:66건200·KO·인증 본문,3실패는2외부 목적지(별칭 포함), 정규화60목적지다. 최초17개 화면만으로 전체 관리자 완료를 선언하지 않고 범위를 확장했다. 원문/도메인 확인된69번역, 정확13Tab CAS, KO CopyLanguageType raw From/To만 수정했다. 기존 글로벌 날짜From/To·다른 언어·custom labels·선택값·CSRF는 보존한다.
- 영향19건 집중 GET(6+7+6) 모두200·KO·인증 본문. 원문/도메인에 맞는 한국어와 Email 메뉴를 긍정 검증했고 비기술 영문 잔존0이다. 언어 복사 라벨의 direct text는 정확히 원본 언어/대상 언어, 추가 node는 native 필수표시 `*`뿐이다. 초기 whole-label strict false와 원인을 보존하며 느슨한 contains로 대체하지 않았다. 두 select의 visible/enabled/4options와 전후12domain/ACL·감사/Tab·TabLang/critical hash가 일치한다.
- native FormFactory62 / CAS 실제 MariaDB33 / locale Python61 / audit계약13 / CI계약9 / fresh 현재소스 경량 workflow24명령군 PASS. host/opt/live 앱1140·locked Push vendor1426 일치·unknown0, 기본512M/nooverride/www-data cache:clear WITHwarmup5.9초 PASS. 새62폼 검사는 기존38phase native_boundary에 포함했다.
- 테마 마켓플레이스503은 native external-content circuit fallback(하위 transport상세 미확정), Facebook모듈500은 기존 로그의 cURL56 CONNECT403 외부 통신 실패다. 발주/포인트 controller 결함으로 단정하지 않고 외부 페이지의 가용/시각 인수는 남긴다. 재시도·유료 서비스·우회 호출은 실행하지 않았다.

[최종 관리자 결과와 원본 실패](evidence/2026-10-29-procurement-local/admin-expanded/), [정책 저장 단1회 증거](evidence/2026-10-29-procurement-local/policy-submit-focus/). 위 로컬1140파일은 bd1ced8 이미지+명시적 ad51cff 소스 overlay이며, 현재 실행 중인 immutable fresh aggregate와 구분한다.

### 8663e96 시점의 fresh 초기값 불일치 기록

ad51cff의 전체 #40755121454는 **3phase PASS/module_seed FAIL/후속34not_run/cleanup success**다. 새13메뉴의 엄격한 한국어 초기값 assertion에서 실패했고 당시 로그에는 대상 클래스가 없어, 올바른 기존 한국어 표현 보존과의 기대값 충돌인지 실제 초기화 결함인지 아직 확정하지 않는다. artifact12845373313 SHA256 `115a8c0c4d9e4c4a112b3814aaead0feed688a4e02c54134753cc12620786cca`.

8663e96은 앱을 바꾸지 않고, 원래 엄격한13개 assertion 전에 고정 클래스의 존재/owner/일치/기본영문/Hangul/중복 여부만 안전하게 보존한다. 이름 원문·ID·토큰은 넣지 않고 실패 후에도 JSON을 복사한다.5개 진단 fixture/기존9계약·lint 통과 후 위 실행에서 새 증거를 수집 중이다. 실패를 성공으로 바꾸거나 확인되지 않은 원인을 수정했다고 기록하지 않는다. 앱1140파일은 ad51cff와 동일하다.

### 이전 d4e470a 후보 — 시작 메뉴 문구 일치

8663e96/#40756263392는 원본3phase PASS/module_seed FAIL/34not_run/cleanup success이며, 안전한13클래스 vector에서 **HOME만 expected owner·한 행·Hangul13bytes·기대값 불일치**, 나머지12개는 정확 일치했다. artifact12847195330 SHA256 `cb52ad758ffa7fae7cedfb83dbd6ad5fc23a0a0116eeb2f3bced93a31f7e1a25`.

실제 native ClassicEdition TabsInstaller+번역기를 메모리 경계에서 실행해 이전 XLF가 `시작 안내`13bytes, 수정 XLF가 기존 CAS/엄격 seed와 같은 `시작하기`12bytes를 생성함을 재현했다. 원격 이름 원문 자체는 미보존이라 정확 동일성을 추정해 기록하지 않는다. source의 세 경로 불일치는 확정되어 XLF 한 값만 고쳤고, 원래13개 assertion·사용자 지정 한국어 보존은 그대로다. 세 경로 일치 회귀검사 포함 locale61 PASS. 실제 관리자 한 페이지에서200KO·`시작하기`/`지원 센터`를 확인했고 기존12domain/ACL·감사/Tab·TabLang/critical hash가 같았다. 최종1140app/1426vendor 정렬·기본512M warmup5.68초 PASS.

현재 전체38phase [#40757330613](https://github.com/goldeget/japan-premium-commerce/actions/runs/40757330613),d4e470a는 완료 FAIL이고 경량 #40757330533은 SUCCESS다. 같은 QA를 중복 실행하지 않으며 실제 aggregate·cleanup·artifact가 확정되기 전 전체 PASS로 표시하지 않는다.

---

> **최종 제품 기준 — 2026-10-29:** 운영자가 고객에게 특정 상품 발주를 안내하고, 고객이 쇼핑몰 주문하듯 해당 상품·수량을 확인해 발주 요청하면 운영자가 수동 검토 후 포인트 잔액을 지급 반영한다. 고객은 잔액·내역만 표시받고 별도 처리는 운영자가 맡는다. 일반 작업결과/증거 제출 시스템으로 확장하지 않는다. 배송·반품·상품환불·판매결제/출금은 제외하고 수동수당포인트는 필수다. [최종 아키텍처](superpowers/specs/2026-10-29-ordenowa-procurement-points-platform-design.md)와 [새 요구사항표](RELEASE_REQUIREMENTS_MATRIX.md)가 우선한다. 아래 쇼핑몰 기록은 과거 해당범위 증거이며 새출시 PASS/FAIL이 아니다. 현재 구현 및 검증 상태는 이 문서 맨 위와 새 요구사항표를 따른다. 아래 기록의 미구현·최신 실패 표기는 당시 범위에 한정한다.

> **2026-10-29 출시 전수조사 갱신:** 조사 기준 work `e357b8b`(실행 코드 `364ba34`)의 최신 전체 QA #40559740938은 실제 aggregate **FAILURE**다. 현재 구현·39개 추적 항목·실패/skip·운영 대기는 [출시 잔여 작업 전수조사](RELEASE_READINESS_AUDIT_2026-10-29.md)를 최신 판정으로 사용한다. 아래 과거 candidate/실행 중/완료 표기는 해당 기록 당시 범위이며 최신 통합 PASS가 아니다. Indexed DB catalog/규모검사 소스는 이미 구현됐고, 검증기 실패와 운영 미구현은 구분한다. 이번 조사에서 새 CI나 운영 배포는 실행하지 않았다.

## 현재 통합 결과와 focused security follow-up (2026-10-27 UTC)

- Full isolated Actions [#40508152705](https://github.com/goldeget/japan-premium-commerce/actions/runs/40508152705), source `f5b1cca49805b130b57f86746f025713580f0e39`, completed with Step 101 aggregate **SUCCESS**; cleanup Step 104 passed. Business-profile [#40508152784](https://github.com/goldeget/japan-premium-commerce/actions/runs/40508152784) also succeeded, including PHP lint and synthetic receipt contracts.
- The only prior full aggregate failure was `bank_transfer` readback at #40503353045. PrestaShop 9.2 `Db::getRow()` appended `LIMIT 1` to the verifier query that already had one. f5b1cca removed only the duplicate and added a regression contract. Step 90 now passed order issue, wrong-amount/ACL denials, confirmation and idempotent replay; exact-one receipt/native payment/paid history checks; and a fresh customer read showing paid state and hidden unpaid instructions. Checkout restoration Step 91 passed.
- This run also passed catalog review/native draft (18–21, 45–48), admin token/view-only (57), JA/EN/KO reset email (40), customer account (42), PWA/contact (61), push consent/outbox (62), support lifecycle (73), JA search (53), Product/Offer SEO (54), free shipping (76–81), tracking (82), returns (86–88), backup/restore (93), restart (98), Japan Post (99–100), and cleanup (104). The earlier isolated PWA 404, support timeout, JA mail, search, SEO, catalog HTTP 500 and admin-review assertion did not recur. PWA and support were different checks and are not treated as one cause.
- The local focused commands on candidate `9bc31eb` passed **268 tests** with **1 skipped** across account/address, checkout/MIME, workflow, catalog, audit and business-profile contracts. Python AST validation of eight changed Python files and `git diff --check` passed. Local PHP CLI and Docker are unavailable.
- The earlier #40516685529 result on `1fc99c10556aec3a1a8d1a5e19592d59246c0713` timed out during A owner re-login after B was authenticated and A's edit form/content were absent. A reauthentication and final address readback were not reached. The newer #40526816393 on `9bc31eb2b678d7ed6a22688f14d49179a49d560a` also failed aggregate Step 101 (`account=failure`); cleanup Step 104 passed. Actual desktop/mobile logs timed out at `owner_account_page_identity_link`: login returned an authenticated header on localized `/ko/` home, then the harness asserted an account-only link without navigating to the saved My Page route. The foreign target request was intercepted by the service worker; safe traces record a 302→404 redirect chain served by the service worker. The browser recorded no owner form or address content and did read B's account route after the request, but this is not a backend ACL or owner reauthentication/readback result. `owner_session_authenticated=false` and `owner_fresh_readback_unchanged=false` mean those checks did not execute; no disclosure or mutation is established. Artifacts: browser [12743953276](https://github.com/goldeget/japan-premium-commerce/actions/runs/40526816393/artifacts/12743953276), redacted diagnostics [12743748456](https://github.com/goldeget/japan-premium-commerce/actions/runs/40526816393/artifacts/12743748456).
- Candidate `32ab27ecb6a1fe559a6111510031a7d210050722` is confirmed on `origin/work`; remote `main` remains `ee02a3657448d563508687614a246e05ac61eecd`. Business-profile Actions [#40526816398](https://github.com/goldeget/japan-premium-commerce/actions/runs/40526816398) completed SUCCESS with PHP 8.3 lint, updated audit PHP fixture, and profile/error tests. Synthetic parser Actions [#40526816700](https://github.com/goldeget/japan-premium-commerce/actions/runs/40526816700) completed SUCCESS. Address-focused fresh-install [#40530519482](https://github.com/goldeget/japan-premium-commerce/actions/runs/40530519482) completed SUCCESS: Steps 8/9/12/14/42–44, aggregate Step 101 and cleanup Step 104 passed. Artifact [12745089136](https://github.com/goldeget/japan-premium-commerce/actions/runs/40530519482/artifacts/12745089136) is available. On both desktop and mobile, all 14 sanitized isolation outcomes are true: exact same-origin foreign edit request matched the captured target and used the network; B remained authenticated on fresh network account reads before and after; no owner edit form/address content appeared; A reauthenticated to the native account route; and a fresh network read showed A's saved address unchanged. The direct trace was 302→404 with Service Worker, disk-cache and prefetch flags false. Status alone is not used as denial proof. No address, email or token values were logged or included in the safe result. This is GET confidentiality evidence; cross-owner write POST was not exercised.
- Candidate includes the partial permission-gated five-source admin activity feed, selected Korean admin label/error updates, and full-run-only JA/EN/KO registration and unpaid order-confirmation raw-MIME verifier with native persistence readback. Audit page roles/coverage and new mail acceptance remain pending the full candidate run. Address/account and result-schema contracts pass 77/77; exact Step 8 preflight passes 797 tests with 11 skipped. No application ACL, wait, assertion, CSRF or customer-isolation condition was relaxed.
- Catalog admin-access readback in #405081 Step 47 is unresolved. GitHub exposes green post-`continue-on-error` step and aggregate conclusions, while reported no-readback JSON could not be matched to an accessible run artifact. The workflow now keeps only a sanitized result artifact and requires a separate explicit ready output in the aggregate; the upcoming full candidate run must establish this outcome.
- Browser artifact [12736384730](https://github.com/goldeget/japan-premium-commerce/actions/runs/40508152705/artifacts/12736384730) includes `bank-transfer-customer-instructions-mobile.png`, `bank-transfer-limited-denied-desktop.png`, `bank-transfer-admin-confirmed-desktop.png` and `bank-transfer-customer-paid-mobile.png`; Step 96 verified the required capture set. Screenshots were not visually opened. f5b1cca changes only verifier/test code; no customer screen changed.
- No production DB, deployment, real payment, bank transaction, shipment or external trade was performed. User checkout changes and `main` are preserved.

## 2026-10-26 — 카트/배송 진단과 PWA foundation의 로컬 검사 (Actions 대기)

- 로컬 `work` code SHA `50d924fdf6923a551c49c0cee65fb5b428765bb1`; 원격 `origin/work`는 push 전 `a890c83f04b81240b07a338f9ed734f0a25caf78`. `main`은 변경하지 않았다. 변경은 `ec7ef6b` 카트/배송/한국어 주소 문구 보완과 `50d924f` PWA synthetic foundation 두 commit으로 분리됐다. 아직 새 Docker/DB/Chromium Actions runtime은 없다.
- Workflow Step 8의 현재 명령은 **578 tests OK (7 skipped)**. Skip 7개는 PHP CLI 부재로 실행할 수 없는 PHP-only account-address source contracts다. Step 9의 `test_ci_checkout_contract`는 parent `ORDENOWA_ADMIN_SECURITY_FOCUS=false` 및 `true` 각각 **36 tests OK**다.
- 영향 계약: cart/shipping/account/residual **117 tests OK**; PWA worker/module/backend workflow contracts **84 tests OK**. Node account client **12 tests OK**. PWA Python source contract **4 tests OK**. Worker negative Cache-Control checks intentionally print their rejected-case messages while the suite result remains OK. `git diff --check`, Python/YAML/embedded JS/Bash syntax checks pass.
- Cart fix retries only a stale element in the existing ready-button probe; carrier checks retain the original waits and assertions and add safe substage diagnostics. No browser runtime has confirmed the stale recovery or carrier save/readback on this SHA. The previous `shipping_free_admin_configure` timeout remains unclassified until new Actions evidence.
- Korean address edit helper now uses `계정에 사용할 주소 정보를 입력해 주세요.`. Older artifact 12644494181 shows the previous Korean but edit-inappropriate copy; the new text needs a fresh source capture before visual completion.
- PWA-002 code is synthetic/no-provider only. PHP behavior and MariaDB repository tests are wired to Actions; PHP is unavailable locally. Source review found consent notice version/hash and acceptance timestamp/audit are not stored; keep this as a production privacy/readiness gap. Never record the local checks as full CI or browser PASS.

## 2026-10-26 — 주소 번역 런타임 확인 및 전체 QA 결과

## 2026-10-26 — 주소 번역 런타임 확인 및 전체 QA 결과

- 대상 `work` SHA `a890c83f04b81240b07a338f9ed734f0a25caf78`; `main`은 변경하지 않았다. 전체 isolated Actions [#40310232196](https://github.com/goldeget/japan-premium-commerce/actions/runs/40310232196)은 completed **FAILURE**이며 실제 aggregate 실패는 `cart_controls_browser_qa=failure`와 `shipping_free_admin_configure=failure`다. 주소 browser outcome은 `ACCOUNT_BROWSER_QA_OUTCOME=success`; 전체 실행은 PASS가 아니다.
- Cart 실패는 mobile `product_add_add_button_wait` / `StaleElementReferenceException`이다. Free carrier 설정 실패는 `verify_admin_saved_carrier` / `TimeoutException`이며 실패 당시 controller path class는 admin carrier edit다. 의존 후속 shipping checks는 skipped라 추가 독립 결함으로 세지 않는다.
- Account outcome은 desktop/mobile 회원가입·중복 방지·로그인/로그아웃·메일 reset 및 주소 생성/동일 주소 편집·저장·fresh readback/refresh 확인을 통과했다. 과거 #40300616469의 address Timeout은 이번 run에서 재현되지 않아 기존 원인을 확정하지 않는다.
- Browser artifact [12644494181](https://github.com/goldeget/japan-premium-commerce/actions/runs/40310232196/artifacts/12644494181)에서 `mobile-customer-address-edit-form.png` (390×701)를 열어 정적 안내 `계정에 새 주소를 등록할 수 있습니다.`의 한국어 표시를 확인했다. 계정 흐름의 캡처/자동 assertion 근거이며 실기기 또는 전체 고객 화면의 시각 PASS가 아니다. `mobile-customer-address-edited-after-refresh.png`도 artifact에 포함된다.
- Focus run #40307437142 / artifact 12642513725의 account success와 목록 안내 검수는 이전 코드 범위로 유지한다. 최신 form 문구 검증은 #40310232196 source SHA에서 확인했다.
- 이후 전체 QA는 PWA 변경 후 필요한 코드 검증과 새 수정이 있을 때 사용한다. 같은 a890c83을 근거 없이 재실행하지 않는다.

## 2026-10-26 — 모바일 주소 편집 focused QA 통과 및 회귀 준비

- 시작 기준 work/origin은 `c045d21313af925072d55629f74ec5272d16dbc1`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`다. 중간에 추가된 workflow 조건 수정은 아직 commit되지 않았으며 기존 변경·미추적 파일은 보존한다.
- 전체 #40300616469의 실제 유일 실패는 `account=failure`, mobile `customer_address_edit=TimeoutException`이었다. 그 run에는 카드/동일 주소 확인 이후 edit-link click, form wait 중 어느 predicate에서 timeout됐는지 기록되지 않았다. 새 focused QA가 통과했어도 이전 실패 원인은 미확정이며 timeout 증가나 성공 조건 완화는 하지 않았다.
- #40307147507은 account focus preflight Step 8에서 실패해 브라우저까지 도달하지 않았다. commit prefix가 `ORDENOWA_CUSTOMER_ACCOUNT_FOCUS=true`를 설정한 상태에서 full-mode aggregate fixture가 상속한 것이 원인이었다. c045d21은 full fixtures에 명시적 false, focus fixture에 명시적 true를 넣었다. 이 수정 후 자동 account-focused run [#40307437142](https://github.com/goldeget/japan-premium-commerce/actions/runs/40307437142)는 actual aggregate SUCCESS였으며, desktop/mobile 회원가입·중복 거부·profile/address create/edit/save/fresh GET·login/logout·Mailpit reset이 통과했다.
- Browser artifact [12642513725](https://github.com/goldeget/japan-premium-commerce/actions/runs/40307437142/artifacts/12642513725)는 저장/수정 폼/새로고침 후 주소 화면 캡처를 포함한다: `desktop-customer-address-saved.png`, `mobile-customer-address-saved.png`, `desktop-customer-address-edit-form.png`, `mobile-customer-address-edit-form.png`, `desktop-customer-address-edited-after-refresh.png`, `mobile-customer-address-edited-after-refresh.png`. 새 캡처는 자동 E2E/화면 내용 근거이며 Codex에서 PNG를 실제 열지 않았다. Work-mode GPT가 화면을 열어 정적 한국어 주소 안내와 레이아웃을 확인하도록 `AI_BROWSER_QA_HANDOFF.md`에 범위를 적었다.
- 브라우저 주소 단계 계측은 민감값을 제외해 safe route class, form/card/link boolean, same-address identity boolean, native click attempt/return, 문서 이동 및 allowlisted error/occluder를 기록한다. 새 Korean locale assertion은 Step 41에서 PASS했다. 기존 주소 수정 실제 동작을 바꾸지 않았다.
- 이후 보완한 workflow condition은 account focus에서 unrelated admin security fixture/browser를 건너뛰고, default/full 및 admin-security focus에서는 실행되게 한다. inherited focus variables를 둔 exact Step 8은 551 tests PASS (7 skipped), Step 9는 147 PASS, 영향 contract suite는 199 PASS다. YAML parse와 `git diff --check`도 통과했다. 이 workflow 변경을 포함한 push가 시작할 최종 전체 격리 run은 아직 없다.
- #40300616469의 합성 catalog native same-ID edit/readback/reimport 및 shipping tracking browser/DB outcomes는 success로 보존한다. 현재 회귀 QA가 끝나기 전에는 전체 QA PASS로 보고하지 않는다.
- 독립 Work QA는 c045 artifact 12642513725의 `mobile-customer-address-edited-after-refresh.png` (390×701)를 실제 열어 edited synthetic address와 한국어 목록 안내를 확인했다. 같은 artifact의 `mobile-customer-address-edit-form.png`에는 영문 정적 안내 `Add a new address to your account.`가 남았다. 이에 XLIFF target `계정에 새 주소를 등록할 수 있습니다.`와 한국어 edit-form browser assertion을 추가했다. c045 artifact는 이 변경 전 캡처라 수정 후 시각 PASS로 재사용하지 않는다.
- XLIFF와 form assertion을 구현한 최신 local source의 targeted customer/account/locale/workflow contract suite는 199 tests PASS했다. 최신 Step 8 exact command 551 PASS (7 skipped), Step 9 147 PASS, YAML/Python/XLIFF validation 및 `git diff --check`도 통과했다. 수정된 edit copy의 실제 PrestaShop 렌더링은 다음 Actions에서 재검증해야 한다.

## 2026-10-26 — catalog baseline 및 운송장 문서 대기 회귀 검증

- Final `work` SHA `0b68e96f1a38a36feb3732b2d3a26c06afd40c1a`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 보존했다.
- #40294965246의 catalog 실패는 unsupported-URL 검사 함수가 브라우저를 review 화면으로 이동한 다음, 검증기가 그 화면에서 manager ID baseline을 읽어 생긴 harness 순서 오류였다. `0da85d3`는 manager 화면에서 baseline을 읽은 뒤 unsupported URL 이동을 수행한다. #402949 aggregate의 유일한 실패였던 shipping 단계는 별도로 `admin_post_save_document_wait`의 stale body-text read로 확인됐다.
- `985e1cd`는 동일 주문 참조와 정확한 관리자 주문 경로를 요구하는 기존 predicate에서 stale body text 예외만 해당 polling predicate 안에서 false로 처리한다. 제출 재시도나 JS 강제 클릭은 하지 않으며 같은 35초 대기, 저장 후 운송장 행, cache-disabled fresh GET, 고객 같은 주문, unpaid/free-shipping 보존 및 DB readback 검사는 그대로다. `0b68e96`는 누락/비문자열 주문 참조를 거부하도록 fail-closed 보강했다.
- 최종 SHA `0b68e96`의 전체 Actions [#40300616469](https://github.com/goldeget/japan-premium-commerce/actions/runs/40300616469)는 Step 88 aggregate **FAILURE**다. 실제 유일 실패 `account=failure`; annotation: mobile `customer_address_edit`, `TimeoutException`, control name/type 없음. 이 새 account failure는 이번 변경 범위에 포함하지 않았으며 원인을 추정하지 않는다.
- 같은 aggregate에서 `catalog_import_browser_qa=success`, `shipping_free_admin_browser_qa=success`, `shipping_free_tracking_persistence=success`가 확인됐다. Step 73이 실제 수행돼 Step 72 관리자 outcome도 success다. Step 80 isolated backup/restore, Step 85 restart persistence, Steps 86–87 Japan Post import/verification, Steps 89–91 diagnostics/upload/cleanup도 성공했다. Overall workflow는 account 실패 때문에 success가 아니다.
- 전체 성공 직전 baseline은 SHA `985e1cd` / [#40298163222](https://github.com/goldeget/japan-premium-commerce/actions/runs/40298163222)로, actual Step 88 aggregate PASS 및 catalog/shipping/tracking outcomes success다. 독립 검수는 artifact [12639887664](https://github.com/goldeget/japan-premium-commerce/actions/runs/40298163222/artifacts/12639887664)의 일본어 주문 상세와 관리자·고객 운송장 화면을 확인했다. 그 성공 JSON은 stale retry가 실제 실행됐다는 사실까지 증명하지 않는다.
- 최종 SHA artifact: browser screenshots [12641465628](https://github.com/goldeget/japan-premium-commerce/actions/runs/40300616469/artifacts/12641465628), diagnostics [12639904863](https://github.com/goldeget/japan-premium-commerce/actions/runs/40300616469/artifacts/12639904863). Codex에서는 이 이미지들의 새 시각 검수를 완료했다고 주장하지 않는다.
- 최종 코드의 local Step 8 exact command: 546 tests PASS, 7 skipped; free-shipping E2E contract suite 47/47 PASS; `py_compile`와 `git diff --check` PASS. 이것은 final SHA의 전체 Actions aggregate FAILURE를 바꾸지 않는다.

## 2026-10-26 — native readback predicate 진단과 일본어 주문 추적 라벨

- Validated local work code SHA `791f2d31456abd4cfa4dd98447ba1838a41073b0` adds `20f3708` diagnostic instrumentation and `791f2d3` Japanese order-detail translations; origin/work remains f4c75b8 until push. `main` is unchanged.
- For QA-IMP-009, `native_readback_check` is a fixed allowlist and `native_readback_check_match` is boolean/null. The browser records a check immediately before each manager route/form/ID/category/JA-EN-KO name and description/quantity/tax/price/option/combination/image/inactive-gate/unique-ID comparison. Manager edit preservation and reimport identity checks also use the same safe fields. A false comparison still raises; an exception during a read leaves that predicate with a null match. No values, raw exception, URL or token are emitted.
- LOCALE-002 adds child-theme JA XLIFF entries for order reference/date, carrier/payment labels, shipment heading/table aria label, and the Carrier table header, preserving placeholders. The existing same-order customer flow asserts JA labels and captures the tracking table after scrolling. This is not runtime or visual PASS until its CI artifact is checked.
- Verification: exact Step 8 command from `.github/workflows/fresh-install.yml` passed 538 tests (7 skipped); related catalog/locale/integration contracts passed 85/85; Python AST, JA XLIFF XML parsing and `git diff --check` passed. No Docker/browser runtime was run locally.
- Previous code SHA f4c75b8 full QA [#40284146117](https://github.com/goldeget/japan-premium-commerce/actions/runs/40284146117) remains FAILURE; actual aggregate sole failure was `catalog_import_browser_qa=failure` at the unnamed `native_editor_readback` assertion. Independent QA confirms only the unsupported-URL screenshot in artifact [12633129812](https://github.com/goldeget/japan-premium-commerce/actions/runs/40284146117/artifacts/12633129812) was visually inspected; the failure crop did not show the failed field. The new diagnosis/runtime and JA screenshots await the next push-triggered Actions run.

## 과거 checkpoint — 동일 주문 추적 QA 및 관리자 URL 오류 검증 상태 (2026-10-26)

- 현재 branch SHA: f4c75b89f4c89edbe1fb97ba097cbd061dc30259; `main`: ee02a3657448d563508687614a246e05ac61eecd. Current app change is fe09a56; f4c75b8 updates its diagnostic contract fixture.
- commit b9ad038은 관리자 Welcome back %name%를 한국어 %name%님, 환영합니다로 overlay하며 placeholder를 보존한다. 회귀 검사는 변경 전 실패했고 변경 후 admin locale 31 tests가 통과했다.
- commit 229dd22는 격리 무결제 Tokyo 주문 하나에 네이티브 관리자 tracking 저장→fresh Admin GET→같은 고객 주문 상세 readback을 추가했다. 별도 PHP 검증은 native Order/OrderCarrier의 같은 order/carrier/tracking ID, 미결제/paid=0, 상태·JPY 합계 보존, ¥0 배송, dispatch/scan 없음을 읽는다. 임의 외부 tracking URL을 만들지 않는다.
- 변경 영향 검증: focused free-shipping/workflow/artifact/backup tests 158개 PASS, Python compile, workflow YAML, 변경된 shell/embedded Python parse와 git diff --check PASS. Codex host에는 PHP CLI/격리 shop이 없어 native browser/runtime 검증은 Actions에 맡겼다.
- 자동 전체 격리 QA [#40281533046](https://github.com/goldeget/japan-premium-commerce/actions/runs/40281533046), source SHA 229dd22, 06:58 UTC `completed SUCCESS`; actual Step 73 tracking outcome, Step 88 aggregate, postal verification and cleanup succeeded. Same SHA parser [#40281533000](https://github.com/goldeget/japan-premium-commerce/actions/runs/40281533000) and business-profile [#40281532995](https://github.com/goldeget/japan-premium-commerce/actions/runs/40281532995) also succeeded.
- Artifact [12632622676](https://github.com/goldeget/japan-premium-commerce/actions/runs/40281533046/artifacts/12632622676) was opened by independent QA. Readback confirmed synthetic order 10/reference XWMNYZUWG, OrderCarrier 10, tracking value, amount ¥1,100, shipping ¥0, unpaid state unchanged, and no carrier destination. Captures show the admin/customer pages, but the customer tracking row itself is below fold. Japanese system labels remain in English and are now LOCALE-002; the capture is not click or all-locale visual QA.
- 이전 full QA [#40277922728](https://github.com/goldeget/japan-premium-commerce/actions/runs/40277922728), source e085be5, SUCCESS를 보존한다. Step 46/87의 CAT-004 synthetic edit/save/fresh readback/reimport 성공 및 independent visual review artifact 12631716741은 완료 근거다. Importer는 inactive/hidden/non-orderable 상태를 보존했다; GAP-002 storefront 공개는 미검증이다.
- 운영 DB/deploy/payment/trade/dispatch 및 기존 named volumes를 변경하지 않았다. 실기기·실제 판매자료·운영환경 결과는 CI synthetic PASS에 포함하지 않는다.
- Commit fe09a56 replaces raw `InvalidArgumentException` feedback with a fixed Korean 1–10 supported-URL message and adds browser/controller coverage for unsupported, empty, and >10 URL input; no URL or raw exception is reflected, and no progress batch is accepted. Local 120 focused tests passed; PHP CLI is unavailable.
- Run [#40283927023](https://github.com/goldeget/japan-premium-commerce/actions/runs/40283927023) at fe09a56 failed before install/browser at preflight because the isolated aggregate contract fixture omitted the new `invalid_url_notice_visible` boolean. This is a test harness/schema mismatch, not a browser result; catalog parser run [#40283926974](https://github.com/goldeget/japan-premium-commerce/actions/runs/40283926974) succeeded. Commit f4c75b8 adds the missing field. The exact Step 8 command then passed 535 tests locally.
- Full isolated run [#40284146117](https://github.com/goldeget/japan-premium-commerce/actions/runs/40284146117), SHA f4c75b8, completed FAILURE. Step 8 preflight and the two focused local contracts passed. Step 88 actual aggregate reports only `catalog_import_browser_qa=failure`; its Step 46 is green only after `continue-on-error`. Safe diagnostics locate an `AssertionError` at `native_readback/native_editor_readback`, with HTTP 200, valid manager route/ID/editor, and no access/token denial. The exact field predicate is not logged. Artifact [12633129812](https://github.com/goldeget/japan-premium-commerce/actions/runs/40284146117/artifacts/12633129812) could not be downloaded here (403), so no screenshot visual review is claimed. Step 80 backup/isolated restore, Step 83 screenshot coverage, Step 85 restart, Steps 86–87 postal import/verification, Steps 89–91 diagnostics and cleanup passed.

## 2026-10-26 — imported draft 저장 확인의 DOM stale 경쟁 수정

- 시작 원격은 `422f73120aeeb33327c342a1b6994897036dbd6f`였고 work만 수정했다. `d49fa7d2e5b7714fee8f31bdd1558f54bdb2a6d7`의 전체 QA [#40275686536](https://github.com/goldeget/japan-premium-commerce/actions/runs/40275686536)은 `catalog_import_browser_qa=failure` 하나로 종료됐다. 안전 진단은 `manager_edit_save_confirmation`, `StaleElementReferenceException`, save click 반환, HTTP 200, 동일 hidden product ID를 보였다. 저장 성공/실패 및 fresh readback은 입증되지 않았다.
- 독립 검수 artifact [12630308572](https://github.com/goldeget/japan-premium-commerce/actions/runs/40275686536/artifacts/12630308572)의 failure crop은 보호 안내만 보였다. 편집값, 저장 알림, 실패 element가 없어 화면으로는 원인을 더 좁힐 수 없었다. 앱 저장 결함으로 단정하지 않는다.
- 관리자 컨트롤러가 no-image edit에 내는 정확한 success notice와 브라우저 기대 문자열은 일치한다. 테스트가 `.alert-success`를 여러 Selenium WebElement 호출로 읽어 DOM 갱신 경합 시 stale 참조가 전파될 수 있었다. `tests/e2e/verify_catalog_import_browser.py`는 이제 표시 중인 alert와 exact full notice를 한 번의 synchronous DOM snapshot에서 비교하고 bool만 돌려준다. 동일한 기대 문구, native click, fresh GET 및 edited value/image/option assertions는 유지한다. 안전 진단에는 success notice의 존재만 boolean으로 추가했다.
- TDD regression contract는 수정 전 함수 부재로 실패했고 수정 후 정확 텍스트/한 번의 DOM snapshot 조건을 검사한다. 관련 browser/workflow contract 38/38, `py_compile`, `git diff --check` 통과. 독립 정적 리뷰에서 blocker는 없었다.
- 수정 commit `e085be59a0f9f061769fe7ab3cb79e025042b960`를 work에 push했고 `git ls-remote`로 동일 원격 SHA를 확인했다. 전체 격리 QA [#40277922728](https://github.com/goldeget/japan-premium-commerce/actions/runs/40277922728)은 e085be5에서 실행 중이며 마지막 관측은 Step 14 `Start the empty-volume shop`다. 저장→fresh GET→same-source reimport 및 aggregate outcome은 대기 중이며 성공으로 보고하지 않는다.


## 2026-10-26 — catalog 승인 후 manager 경로 수정 및 전체 격리 QA

- 수정 코드 `e1cd6d0c9d58ee2db64462387fef305c2ab0e757`를 `work`에 push했고 remote SHA를 재확인했다. `main`은 변경하지 않았다.
- 실패 원인은 앱의 상품 저장으로 단정하지 않았다. #40269983026에서 승인 click은 반환됐지만 browser가 manager GET 전에 `approved_product_link` 경로 assertion에서 멈췄다. 검증기가 `/admin-kuranea` 하나만 허용했고, PrestaShop 9.2 legacy admin link 형식 `/admin-kuranea/` 및 `/admin-kuranea/index.php`를 거부할 수 있었다.
- 최소 수정은 native admin entrypoint 세 경로만 허용하고 same-origin, exact `AdminOrdenowaProductManager`, 단일 양수 `id_product` 검사를 유지하는 것이다. 임의 하위 경로, 외부 origin, 다른 controller, 중복/0 ID 및 URL `;params`는 거부한다. 안전 진단은 URL/query/token/상품 ID를 출력하지 않고 origin·경로 분류·controller·ID 유효성 boolean만 보존한다.
- 회귀 검사는 기존 bare admin 경로 외에 slash/index.php 형식을 허용하고 잘못된 경로를 거부하는 것을 확인한다. 이 회귀 검사는 구현 전에 trailing slash 및 `index.php` 사례에서 실패했고 수정 후 통과했다.
- 영향 검사: `test_catalog_import_browser_workflow_contract`, `test_catalog_import_admin_contract`, `test_isolated_ci_integration_workflow_contract` 합계 55개 PASS. 수정 Python 파일 `py_compile` 및 `git diff --check`도 통과했다. 독립 read-only 리뷰는 경로 경계와 진단 schema에서 추가 문제를 찾지 못했다.
- 전체 격리 Actions [#40272141646](https://github.com/goldeget/japan-premium-commerce/actions/runs/40272141646), source SHA `e1cd6d0c9d58ee2db64462387fef305c2ab0e757`: workflow conclusion SUCCESS. Step 46 browser flow가 `PASS: synthetic batch, rejection, reviewed draft, local image and same-product reimport readback.`를 출력했고, Step 87 aggregate는 완료했으며 기록된 `CATALOG_IMPORT_BROWSER_QA_OUTCOME=success`로 전체 aggregate PASS를 확인했다.
- 같은 브라우저가 manager editor 화면에서 승인된 native product ID의 언어·가격·카테고리·이미지·옵션/조합 재고 필드를 읽어 확인하고, 같은 상품 ID로 reimport 후 같은 값을 다시 비교했다. 해당 e1cd6d0 flow에는 manager editor의 별도 저장 버튼 동작이 없었다. workflow의 read-only DB 결과는 비활성/비노출/주문불가, 이미지 1, 조합 2, 동일 reference 1을 확인했다. 독립 QA는 artifact 12628194683의 draft/reimport PNG를 실제 열어 표시 이름·가격·비활성 상태·성공 화면만 확인했으며, 재고 숫자 화면 검수는 하지 않았다. catalog-import-readback.json과 catalog-import-persistence.json은 이 artifact에 있다.
- 이 세션은 해당 artifact ZIP 다운로드에서 403을 받아 이미지를 직접 열지 않았다. artifact 생성 및 coverage PASS는 시각 검수를 뜻하지 않는다. 실제 상품 페이지 수집, 실제 상품/이미지 사용권, 판매 게시, 외부 거래는 확인되지 않았다.

## 2026-10-25 — 시각 QA 잔여 항목 수정 및 전체 격리 검증 완료

QA source code SHA는 `95af3a9104b6e3f7bfc861155bdc73db9a91ab98`다. 검증 후 `work`에 문서 전용 업데이트가 올라갔으며 앱과 QA 코드는 변경되지 않았다. 최신 전체 격리 Actions [#40233614104](https://github.com/goldeget/japan-premium-commerce/actions/runs/40233614104)은 workflow 성공, Step 80 aggregate `PASS: isolated browser QA and official postcode verification completed.`로 종료했다. Aggregate에 기록된 `STOREFRONT_BROWSER_QA_OUTCOME=success`, `PWA_BROWSER_QA_OUTCOME=success`; Step 42 product/cart, Step 49 PWA, Step 73/75 screenshots, Step 83 run-only cleanup 모두 성공했다. 직전 성공 run #40231567083은 SHA `aed4a3cc6e143258e9f493603dd226bfa41b34aa`의 별도 기준점으로 보존한다.

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
