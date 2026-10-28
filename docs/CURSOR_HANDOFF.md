# Cursor AI 인계: ORDENOWA 기존 개발 이어가기

### 최종 검증 후보 — 91c6098 / 전체 격리 QA SUCCESS

검증 코드 **`91c6098c6b551946cc8291b31c868656d50c9b34`**를 원격 work에 저장하고 변경 파일 재조회·새 원격 복제본으로 일치 확인했다. main **`ee02a3657448d563508687614a246e05ac61eecd`**와 원래 사용자 체크아웃/운영 DB·volume은 보존했다. 이후 문서 저장 HEAD와 검증 코드 SHA는 구분한다.

전체 [#40763074207](https://github.com/goldeget/japan-premium-commerce/actions/runs/40763074207)는 최종 **SUCCESS**, 실제 **38/38 phase PASS / aggregate passed=true / cleanup success**다. native browser16단계·3언어 회원/reset·공식 ACL·메일/Push mock·재시작/독립 복원까지 통과했다. 초기/재시작 앱1140·Pushvendor1426 파일이 정확한91코드와 일치했다. [artifact12850640042](https://github.com/goldeget/japan-premium-commerce/actions/runs/40763074207/artifacts/12850640042), ZIP SHA256 **`5c01e0d4b070875e3bac1e75b4586ee20113748a298039dc1a2f5589c4c69802`**를 직접 확인했고 [원본12JSON·24PNG·무결성 명세](evidence/2026-10-29-procurement-local/fresh-91c6098-complete/)를 보존했다.

직전 실패는 실제200ms 링크 font/padding 전환이 끝나기 전에 캡처한 QA 순서 문제였다. 기존30초와 full rect/center hit/privacy geometry/enabled/stable scroll·권한 조건을 유지한 수정으로13unit·실제D20target·저장 재조회가 통과했다. 별도 GPT는 **새 hosted24PNG를 모두 실제 열었고 핵심20target(3언어9메뉴·9요청확인·2사진)을 인수**했다. JA/KO 글리프·부모/하위 분류·최종 버튼/사진쌍이 보인다. 전체 텍스트를 치환한 나머지4포인트 PNG는 의미/geometry 인수 근거로 쓰지 않는다. [독립 실제 검수](evidence/2026-10-29-procurement-local/fresh-91c6098-complete/ordenowa-independent-final-hosted-40763074207-review.md).

최신 품질은 JA7경로/10폭+일부dark의7privacy·84layout·84axe·14실제클릭·14Lighthouse PASS다.14건 성능/접근성100, 공개정책SEO100, 모바일LCP최대1747.3ms/CLS0.0001이다. axe위반0이지만84셀 incomplete와 기존 제한된13패턴 수동 검토를 유지한다. 전체WCAG·실사용INP·실기기 성공으로 확대하지 않는다.

로컬D의 요청/원장/포인트계정0·ACTIVE1과 원래A/B/C/80P·업무12/ACL감사8/메뉴2/상품·사진 보존을 확인했다. 새D의 native언어 전환 `id_lang/date_upd`와 접속/session telemetry만 별도 기록했다. [로컬 집중·정확한 보존 범위](evidence/2026-10-29-procurement-local/real-two-level-category-focus/). **핵심 구현과 명시한 합성 격리 검증은 완료했으며, 실제 상품·운영 정책/환경·기기 인수는 남아 있다. 운영 출시 완료는 아니다.**


## 역할과 보존

Cloud Codex가 코드·커밋·CI를 담당한다. Work Mode는 제공된 SHA/artifact/변경 화면의 독립 시각·사용성 검수를 담당한다. 활성 작업은 `/workspace/ordenowa-release-audit`의 검증 후보이며 기존 `/workspace/japan-premium-commerce`와 main은 보존했다. 정확한 코드/증거를 기준으로 검수하고 발견 결함은 재현 조건과 함께 기록한다. 외부 Work Mode에 실제 전달하거나 인수받은 이력은 없다.


## 구현과 검증 범위

운영자 상품 배정 → 고객 상품·수량 확인/발주 요청 → 운영자 수동 검토 → 별도 수동 포인트 지급 → 고객 잔액·내역 조회를 구현했다. 판매결제·배송·반품·상품환불·포인트 사용/출금은 확정 범위 제외다. 일반 업무 결과·증거 제출 플랫폼으로 확장하지 않는다.

전용12테이블의 저장/rollback·동시성·멱등, owner/shop/역할/CSRF, 원본 연결 정정과 원장 대조, 요청별 공개 문의/내부 메모, 정책 버전·감사·outbox를 검증했다. 실제 native A의 수량2 요청·승인0P→명시적100P→새 로그인100P→정정80P, B GET/POST 거부·본인 인증 유지·A원본 보존, 유효 native 토큰을 사용한 제한 직원 변경403을 확인했다.

3언어 회원/reset·Mailpit5건/재전달0·실제 ACL6변경/감사6행·재시작/독립 복원 집중 결과를 보존한다. 관리자69메뉴노드(60목적지) 중66건200KO,69번역·13Tab CAS·범위가 고정된 언어복사 라벨 수정 후19건 재조회와 native폼62/DB33/locale61검사를 통과했다. 외부2페이지와 미진입 오류 분기는 전체 한국어 인수 미완료다.

이전 품질3은 JA7경로/10폭·84layout/axe·14클릭·14Lighthouse PASS(성능99–100/접근성100/공개SEO100)다. 자동 incomplete84셀과 제한된 수동 검토를 구분하며 전체WCAG·실기기·field INP 인증은 주장하지 않는다. 로컬 overlay 검사와 최신 immutable fresh 결과도 구분한다.

## 남은 출시 조건

1. Amazon Japan/Rakuten 실제 가격·상세·사진·원문 분류 호환: 현재 관리망 CONNECT403으로 차단. 합성 결과로 대체하지 않는다.
2. 관리자 외부2페이지와 미진입 오류 분기의 전체 한국어 인수. 접근성 incomplete84셀과 제한된 수동13패턴도 보존한다.
3. 실제 운영자/지원·상품/참여 고객·검토/수당 기준과9개 JA/EN/KO 정책 초안 승인.
4. 승인 운영 환경의 HTTPS/SMTP·secret 참조·불변 이미지 digest·scheduler·감시·복원/롤백 연결과 인수. 단순 값 입력만 남은 상태가 아니다.
5. 실제 iOS/Android PWA·Push 설치/업데이트/수신/철회 인수.

[요구사항표](RELEASE_REQUIREMENTS_MATRIX.md)·[정확한 QA 이력](TEST_RESULTS.md)·[증거 목록](evidence/2026-10-29-procurement-local/README.md)·[단일 운영 입력표](PRODUCTION_DEPLOYMENT.md#현재-서비스의-운영-입력-체크리스트)를 따른다. 운영 배포·실결제·실거래·유료 서비스는 실행하지 않았다.

---

> **최종 제품 기준 — 2026-10-29:** 운영자가 고객에게 특정 상품 발주를 안내하고, 고객이 쇼핑몰 주문하듯 해당 상품·수량을 확인해 발주 요청하면 운영자가 수동 검토 후 포인트 잔액을 지급 반영한다. 고객은 잔액·내역만 표시받고 별도 처리는 운영자가 맡는다. 일반 작업결과/증거 제출 시스템으로 확장하지 않는다. 배송·반품·상품환불·판매결제/출금은 제외하고 수동수당포인트는 필수다. [최종 아키텍처](superpowers/specs/2026-10-29-ordenowa-procurement-points-platform-design.md)와 [새 요구사항표](RELEASE_REQUIREMENTS_MATRIX.md)가 우선한다. 아래 쇼핑몰 기록은 과거 해당범위 증거이며 새출시 PASS/FAIL이 아니다. 현재 구현 및 검증 상태는 이 문서 맨 위와 새 요구사항표를 따른다. 아래 기록의 미구현·최신 실패 표기는 당시 범위에 한정한다.

기록일: 2026-10-28 (한국시간). 이 문서는 기존 프로젝트의 담당자를 Cursor로 전환하기 위한 문서다. 코드 변경, QA 실행 또는 배포 완료를 뜻하지 않는다. 시작 시 실제 원격과 실행 상태를 다시 확인한다.

## 1. 저장소와 보존 기준

- 저장소: https://github.com/goldeget/japan-premium-commerce
- 개발 브랜치: `work`. `main`은 `ee02a3657448d563508687614a246e05ac61eecd`를 보존한다.
- 인계 직전 확인한 원격 work: `364ba341009c83ba9dbabd93aa95bfffa6171455`.
- 이 문서를 추가한 커밋은 문서 전용이며 위 코드의 검증 결과를 바꾸지 않는다. 새 HEAD를 위 코드 SHA와 혼동하지 않는다.
- `AGENTS.md`를 먼저 따른다. 기존 로컬 수정·미추적 파일·커밋을 삭제하거나 덮어쓰지 않는다. force push, reset --hard, clean -fdx를 하지 않는다.
- 원격 변경이 있으면 먼저 비교하고 보존하여 통합한다. 문서의 SHA를 맞추려고 작업 트리를 강제 초기화하지 않는다.
- 각 독립 작업은 작은 커밋으로 work에 보존하고 원격 SHA와 변경 파일을 확인한다. 비밀값과 개인정보는 커밋·로그에 남기지 않는다.

## 2. 사용자 환경과 역할

- 사용자는 Windows 저사양 PC(약 8 GB RAM, 저장공간 부족)를 사용한다.
- Cursor 로컬 Agent는 소스 읽기·수정·가벼운 검사와 Git 작업을 담당한다.
- Docker, PrestaShop/MariaDB 전체 스택, 대규모 브라우저·성능·규모 QA는 기존 격리 GitHub Actions에서 실행한다. PC에 전체 Docker/DB 스택을 설치·기동하지 않는다.
- 로컬 검사에 Python/PHP/Bash가 필요한지 먼저 확인한다. Windows에 없는 Linux 도구 때문에 실패한 검사를 앱 결함으로 오인하지 않는다. 지원되지 않는 검사는 적합한 Actions 환경에서 수행하고 실제 실행 위치를 기록한다.
- 코드를 쓰는 주담당은 Cursor 하나로 전환한다. 이전 클라우드 담당자와 동시에 같은 work에 코드를 쓰지 않는다.
- 워크모드는 완료된 SHA와 artifact를 기준으로 독립 시각·사용성 검수를 담당한다. 이미지 저장/업로드 성공과 실제 이미지 열람은 구분한다.
- 유료 서비스 구매, 유료 러너, 운영 배포, 실결제·실거래, 운영 DB·named volume 변경은 허용되지 않았다.

## 3. 이전 클라우드 환경의 미회수 수정

이전 작업자 보고에 따르면 다음 수정은 원격 work에 없다.

- 이전 사용자 checkout `/workspace/japan-premium-commerce`: 기준 `9d13b1d232da2f8276262895815ffae8bb437658`와 기존 tracked 수정 6개를 보존했다고 보고했다.
- 후속 작업 디렉터리 `/tmp/ordenowa-integration`: 감사 대상 참조/브라우저 재조회, 주소 검증기, 여러 실패 후보 수정 등이 미커밋 상태라고 보고했다.
- 환경은 running으로 보였으나 연결 offline/셸 미제공으로 마지막 검토·검사·커밋을 완료하지 못했다.

이 경로들은 이전 클라우드 머신의 경로다. Cursor의 Windows PC에서 자동 접근할 수 있다고 가정하지 않는다. 해당 디렉터리가 현재 PC에 없다는 사실을 원본 소실 증거로 삼지 않는다.

이전 환경이 복구되면 기준 SHA, tracked diff, 신규 파일을 포함한 복구 자료를 검토하여 가져온다. 비밀값을 제외하고 기존 work와 비교한 뒤 적용한다. 복구되지 않았으면 미회수로 명시하고, 원격에 있는 코드와 실제 QA 증거를 기준으로 원인을 다시 확인하여 필요한 수정을 구현한다. 기억이나 완료 보고만으로 패치 적용·검증을 주장하지 않는다. 미회수 자료 대기와 독립적인 진단 작업을 구분한다.

## 4. 확정된 제품 기준

- 브랜드: ORDENOWA / オーデノワ / 오데노와. KURANEA는 과거 브랜드와 기술 경로로 보존한다.
- PrestaShop 9.2.0, Hummingbird 2.1.2, MariaDB 10.11. 코어와 부모 테마를 직접 수정하지 않고 자식 테마와 독립 모듈을 사용한다.
- `.gitmodules`의 `themes/hummingbird`는 기존에 고정된 gitlink를 사용한다. 임의 최신 버전으로 올리지 않는다.
- 고객 기본 언어 JA, EN/KO 지원. 관리자 한국어 전체 적용은 기존 요구사항이나 현재 전체 완료 근거는 없다.
- JPY 세금 포함 판매가격, 지원되는 일본 지역의 고객 배송비 ¥0 정책을 유지한다. CI의 10%/0%는 합성 규칙이며 실제 상품의 과세 판단이 아니다.
- 상품 수집은 허용된 Amazon Japan/Rakuten 원문 또는 승인된 feed/export, 출처/권리 검수, 비공개 초안과 검수 흐름을 유지한다. 실제 원문 호환과 합성 fixture 성공을 구분한다.
- LOGISTEED는 company_reference이며 실제 판매자·소속·공식 판매 승인을 대신하지 않는다.
- 범위는 실제 상품 판매·주문·상담·배송·반품 운영이다. 현금성 지갑·작업 수익·출금은 기존의 명시적 범위 제외를 유지한다.
- 계정·장바구니·결제·주문·고객정보는 PWA에 캐시하지 않는다.
- 실제 운영 판매자/상품/세금/정책/도메인/메일/VAPID/백업 담당자 자료는 승인 없이 생성하지 않는다.

## 5. 검증 기준: 성공과 현재 실패를 모두 보존

### 과거 전체 성공

- 전체 격리 QA: https://github.com/goldeget/japan-premium-commerce/actions/runs/40508152705
- 코드: `f5b1cca`.
- 검색, 상품 SEO, 회원/주소, 상품 검수, 관리자 보안, PWA/합성 Push, 재설정 메일, 상담, 계좌이체, 무료배송/운송장, 반품, 백업/복원 등의 당시 acceptance가 통과했다.
- 합성 주문별 계좌 안내, 금액/권한/CSRF 거부, receipt/payment/history readback의 성공은 실제 운영 입금이나 송금을 뜻하지 않는다.
- 새 코드의 PASS를 이 과거 실행으로 대신하지 않는다.

### 최신 전체 실패

- 실행: https://github.com/goldeget/japan-premium-commerce/actions/runs/40559740938
- 코드: `364ba341009c83ba9dbabd93aa95bfffa6171455`.
- 실제 job aggregate: FAILURE. step UI의 success와 continue-on-error 이전 실제 outcome을 구분한다.
- 실제 failure:
  - `perf_accessibility_qa`
  - `storefront_search`
  - `account`
  - `catalog_import_browser_qa`
  - `checkout_email_locale`
  - `checkout_gate_after_order`
  - `seo_sitemap_http`
- 실행되지 않은 범위에는 catalog scale acceptance, bank-transfer browser, order lifecycle/returns 관련 의존 단계 등이 있다. skipped를 앱 결함 또는 PASS로 바꾸지 않는다. 관리자 감사 브라우저도 완료 근거가 없다.
- PWA, 합성 Push, reset 관련 검사, product SEO, backup/restore 등의 성공과 전체 aggregate 실패는 함께 기록한다.
- 브라우저 artifact: https://github.com/goldeget/japan-premium-commerce/actions/runs/40559740938/artifacts/12761377082
- 비식별 진단: https://github.com/goldeget/japan-premium-commerce/actions/runs/40559740938/artifacts/12761073334

### 로그에서 직접 확인한 실패 지점

- 계정: PC/모바일 모두 `customer_address_cross_owner_foreign_address_create`, substage `foreign_address_create`에서 TimeoutException. B 주소 저장 단계라 교차 고객 POST 거부와 A 최종 재조회까지 도달하지 못했다.
- 기존 GET 증거: 동일 쇼핑몰의 네트워크 요청, 302→404, A 편집 폼/주소 내용 없음. 요청 후 B 인증과 최종 A 저장 상태를 포함한 전체 POST acceptance는 아직 닫히지 않았다. 이후 200 응답 거부/별칭 제한 등의 후보 수정은 미회수 상태이므로 적용·브라우저 통과를 가정하지 않는다.
- 상품 검수: unsupported URL 거부 알림 기대 문구에서 중단됐다. 검증기는 `Amazon Japan 또는 Rakuten`, controller는 `아마존 일본 또는 라쿠텐`으로 소스가 불일치하며 안전 진단의 문서 상태는 200이다. 이후 batch/검수/게시 통과는 입증되지 않았고, 과거 HTTP 500과 동일 원인으로 단정하지 않는다.
- 검색: 모바일 partial/search_submit. document_changed=false, input_readback_matches=false, query_readback_matches=false, response_status=unavailable.
- 메일: JA `order_confirmation_raw_mime` RuntimeError. 기존 reset 메일 성공과 새 주문 메일 MIME 검증을 구분한다.
- 성능/접근성, sitemap HTTP, 주문 후 checkout gate는 해당 로그/산출물과 테스트 소스를 추가 확인하여 원인을 확정한다.

후속 로컬 집중 계약 검사 통과 보고는 있으나 원격에 없는 수정의 검증 증거로 확대하지 않는다. 진단의 false/미완료는 개인정보 유출의 확정 증거가 아니다.

## 6. 처음 읽을 자료

1. `AGENTS.md`
2. `docs/PROJECT_ARCHITECTURE.md`
3. `docs/superpowers/specs/2026-10-22-business-profile-admin-control-design.md`
4. `docs/RELEASE_REQUIREMENTS_MATRIX.md`
5. `docs/DEVELOPMENT_STATUS.md`, `docs/TEST_RESULTS.md`
6. `docs/AI_BROWSER_QA_HANDOFF.md`, `docs/WORK_LOG.md`
7. 원본 요구 범위가 필요하면 `docs/KURANEA_MASTER_DEVELOPMENT_DIRECTIVE.md`, `docs/ADMIN_KOREAN_REQUIREMENTS.md`.

원본의 구 브랜드·법인·운영 기준은 최신 승인 기준과 AGENTS에 따라 해석한다. 상태 문서에는 과거 SHA가 현재라고 쓰이거나 완료된 run이 실행 중이라고 남아 있다. 현재 사실은 GitHub 원격·해당 SHA의 코드·실제 run 결과로 대조하여 수정한다.

## 7. 작업 순서와 반복 제한

1. 실제 원격/로컬 SHA, 기존 수정, 사용 가능한 도구, 진행 중인 Actions를 확인한다. 다른 저장소나 사용자 변경을 건드리지 않는다.
2. 최신 실패를 원인별로 분류하고 한 번에 작은 독립 단위로 해결한다. 주소는 저장 전제부터 GET/POST 거부, 실제 A/B 인증, A 최종 fresh readback까지 같은 대상의 근거를 유지한다.
3. 각 수정은 관련 계약과 필요한 실제 브라우저 의존 단계를 포함한 집중 QA로 확인한다. 기존 focus 모드가 있다면 올바른 aggregate와 함께 사용한다.
4. 안정된 후보의 전체 QA를 실행한다. 작은 수정마다 전체 설치를 반복하거나, 새 변경/증거 없이 동일 실패를 재실행하지 않는다.
5. assertion, CSRF/ACL/소유권, 실제 native click/save/readback, no-store, 실제 HTTP 응답 확인을 약화하여 통과시키지 않는다. timeout 연장만으로 문제를 닫지 않는다.
6. 새 실패 또는 수정으로 영향이 생긴 경우에만 필요한 검사를 다시 실행한다. 문서만 바뀌었다고 전체 QA를 재실행하지 않는다.
7. 기존 요구사항의 남은 구현·검증을 한 목록으로 고정하고 순차 완료한다. 선택 개선/새 기능은 별도 기록한다. 통과한 합성 acceptance는 실제 상품·실기기·운영 검증으로 확대하지 않는다.
8. 진행 중 약 30분마다 새 증거·완료 항목·차단 사유·다음 완료 조건을 짧게 보고한다. 장시간 무출력 대기와 계획 재작성만 반복하지 않는다.

## 8. 완료 판정과 운영 대기

최종 보고에는 코드/문서 변경, 실제 검사와 한계, 코드 SHA와 원격 SHA, run/artifact, 남은 개발 결함, 외부 입력 대기를 분리한다.

- 실제 판매자 승인과 법률/고객센터 문안
- 허가된 실제 상품 원문/feed, 이미지 권리, SKU별 판매/세금/재고/배송 값
- 운영 도메인/DNS/TLS·메일·VAPID와 비밀값 관리
- 운영 백업 저장소·암호화·보존·RPO/RTO·복구 책임자
- 승인된 HTTPS 대상과 iOS/Android 실제 또는 승인된 원격 기기

위 자료가 없으면 정확한 입력/사용 위치를 한 목록으로 정리하고 독립 개발은 진행한다. 사용자가 제공한 값을 다시 일괄 요청하지 않는다. AI 검사, Chromium 모바일 에뮬레이션, 실제 기기 검증을 구분한다. 점수/성능 목표는 측정한 환경과 수치만 보고한다.

개발 완료와 운영 전환 준비를 구분한다. 원래 필수 요구사항이 남았으면 전체 완료라고 보고하지 않는다. 완료 후 선택 개선을 계속 추가해 작업을 무기한 늘리지 않는다. 운영 배포·실결제·실거래는 별도 명시적 지시 전까지 수행하지 않는다.
