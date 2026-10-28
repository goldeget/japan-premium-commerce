# ORDENOWA 발주·수동 수당 포인트 플랫폼 출시 준비 — 2026-10-29

## 현재 판정과 코드 기준

**새 플랫폼의 출시 인수는 아직 완료되지 않았다. 현재 차단점은 동일 후보의 fresh 통합 QA와 실제 상품·운영 환경·기기 인수다.** 현재까지 관측한 앱 결함은 원인별로 수정하고 아래 범위의 실제 결과를 남겼다. 로컬 집중 성공을 최종 새 이미지의 전체 성공으로 확대하지 않는다.

제품은 **운영자 상품 안내·배정 → 고객 상품/수량 확인·발주 요청 → 운영자 수동 검토 → 별도 명시적 포인트 지급·정정 → 고객 잔액/내역 표시**다. 판매 checkout·배송·반품/상품환불·포인트 사용/현금 환산/송금/출금은 확정된 범위 제외다. 기존 코드와 과거 QA 성공은 보존한다.

- 이번 재확인 기준 로컬/원격 `work`: **`6f9c301d6cb4070c2fb440400a0c2a86e2a5ff8b`**. 원격 `main`: **`ee02a3657448d563508687614a246e05ac61eecd`**, 보존 확인.
- 실제 로컬 소스 정렬 체크포인트는 `cc99bbb42031a03493dc2df3969d8c6caf00abd2`다. `cc99bbb..6f9c301`의 차이는 workflow와 CI 실패 진단/실행기 파일이며 앱 모듈·테마는 바뀌지 않았다. CI 실행기 변경은 fresh 검증으로 확인해야 한다.
- [승인 설계](superpowers/specs/2026-10-29-ordenowa-procurement-points-platform-design.md), [현 요구사항표](RELEASE_REQUIREMENTS_MATRIX.md), [보존된 로컬 증거](evidence/2026-10-29-procurement-local/README.md)를 대조했다. 아래 보관자료의 소매39행과 당시7개 실패는 현 범위의 새 미구현 목록이 아니다.

## 최신 hosted QA — 성공으로 바꾸지 않은 결과

Actions의 실제 status/conclusion과 실행 SHA, artifact 목록을 재조회했다. 세 fresh 실행은 모두 build/up 준비 중 실패했으며 **새 native 기능 전체 PASS는 없다**.

| 실행·검증 SHA | 실제 결과 | 사용할 수 있는 근거 |
| --- | --- | --- |
| [#40746215184](https://github.com/goldeget/japan-premium-commerce/actions/runs/40746215184) · `4f8c18e` | FAILURE | `fresh_install` 이전 준비 실패, 후속36단계 not_run, cleanup 성공. 당시 private build 로그가 보존되지 않아 첫 직접 원인은 확정하지 않는다. [artifact12840743415](https://github.com/goldeget/japan-premium-commerce/actions/runs/40746215184/artifacts/12840743415), [보존 outcome](evidence/2026-10-29-procurement-local/remote-first-fresh-outcome.json). |
| [#40747596953](https://github.com/goldeget/japan-premium-commerce/actions/runs/40747596953) · `77b2ceb` | FAILURE | 후속 hosted build/up 준비 실패. native 기능 인수에 도달한 증거가 아니다. [artifact12841243413](https://github.com/goldeget/japan-premium-commerce/actions/runs/40747596953/artifacts/12841243413). |
| [#40748071562](https://github.com/goldeget/japan-premium-commerce/actions/runs/40748071562) · `4faa400` | FAILURE | 불필요한 Compose Bake host-network 및 외부 CA 파일 관련 entitlement가 확인된 준비 실패. 6f9c301에서 managed 전용 설정을 분리하고 hosted 표준 network/이미지 CA로 수정했다(집중5검사 PASS). 앱 기능 실패나 전체 통과로 판정하지 않는다. [artifact12841443567](https://github.com/goldeget/japan-premium-commerce/actions/runs/40748071562/artifacts/12841443567). |
| [#40746034641](https://github.com/goldeget/japan-premium-commerce/actions/runs/40746034641) · `cc99bbb` | SUCCESS | 해당 저비용 집중/사전 검사 범위. fresh 이미지·브라우저·전체 native aggregate를 대신하지 않는다. |
| 과거 전체 [#40508152705](https://github.com/goldeget/japan-premium-commerce/actions/runs/40508152705) · `f5b1cca` | SUCCESS 보존 | 당시 소매 범위의 회원·주소·검색·SEO·검수·보안·PWA·합성 Push·메일·상담·계좌이체·배송·반품·복원 성공. 현재 발주/포인트 후보 전체 성공을 뜻하지 않는다. |

**최종 CI 결과: [#40749362584](https://github.com/goldeget/japan-premium-commerce/actions/runs/40749362584),6f9c301 검증 중.** CI 수정 후 안정된 work 후보의 새 실행 SHA·run·실제 phase outcome/aggregate·cleanup·artifact를 주담당이 이 자리에 연결한다. 실행 시작이나 녹색 개별 step만으로 완료 처리하지 않는다. 새 증거 없이 같은 실패 검사를 반복하거나 권한·CSRF·고객 격리·assertion을 약화하지 않는다.

## 다섯 상태와 현재 기능별 판정

| 상태 | 뜻 |
| --- | --- |
| 구현과 해당 범위 검증 완료 | 명시된 실제 집중 검증 범위의 완료. 전체 출시 완료와 구분한다. |
| 구현됐으나 검증 미완료 | 동작 코드와 부분 근거가 있으나 필요한 통합·실물·현장 근거가 남는다. |
| 구현 미완료 | 현재 필수 동작에서 확인한 코드 공백. 추정이나 파일 부재만으로 지정하지 않는다. |
| 외부 자료·운영 환경 대기 | 실제 원문 접근·승인 자료·실기기·운영값/접근에 의존한다. |
| 기존에 명시적으로 확정된 범위 제외 | 최신 사용자 정의의 제외 범위. 출시 개발 잔여에 합산하지 않는다. |

| 현재 범위 | 상태 | 실제 완료 근거와 한계 |
| --- | --- | --- |
| 상품 안내·수량/기한/version·요청 snapshot·owner/shop/role·멱등 | 구현과 해당 범위 검증 완료 | PHP8.3/MariaDB 행동·실패 rollback·12개 동시 경합 통과. 실제 native A 요청, 고객 B GET/POST 거부와 요청 후 본인 인증·원본 보존, READ 전용 직원 쓰기403을 확인했다. 최종 fresh 후보의 반복 인수는 아래 통합 gate다. |
| 승인·명시적 수동 지급·연결 정정·잔액/원장 대조 | 구현과 해당 범위 검증 완료 | 실제 native 승인만으로0P → 명시100P → 새 고객 로그인100P → -20P 정정80P. 기본 지급1회·멱등/충돌·실제 경합·정수 한계·각 쓰기 rollback·새 연결 합계 대조 통과. approval과 지급을 같은 동작으로 바꾸지 않았다. |
| 정책·요청별 문의·공개 답변/내부메모 분리 | 구현과 해당 범위 검증 완료 | 정상 masked body token 저장0→1·새 로그인11필드 유지, 잘못된 body token은 유효한 URL token 유무와 관계없이403/무변경. 실제 문의 저장·replay·고객 B 거부·공개 답변 반영·내부메모 비노출과 정책/문의 각6개 경합 통과. 실제 운영 문안 승인은 별도다. |
| 알림/outbox·native 메일·유지보수 중단 복구 | 구현과 해당 범위 검증 완료 | 독립 채널·최대5회 backoff·중복 방지·killed sender UNCERTAIN·명시적 재시도 통과. 실제 native outbox5건·재실행 추가0·Mailpit EN1/KO1/JA3 MIME, locale 변경 후 Push receipt 재시도 회귀 통과. 운영 SMTP·실기기 전달은 별도다. |
| 상품 parser→검수→native 참조·분류/이미지·고객 안내 | 구현됐으나 검증 미완료 | 합성 parser·검수 evidence·same-shop 상품/옵션 경계·native 로컬 이미지2장·고객 안내 연결을 확인했다. 독립 코드 검수에서 AggregateOffer 가격 범위 모호성을 고쳐 불일치/누락 범위는 명시적으로 거부한다. 원문 breadcrumb는 provenance이며 native 분류는 운영자 검토다. fresh 부모/leaf 생성·하위 메뉴/filter/배치 및 실제 Amazon/Rakuten 원문·이미지 호환은 아직 인수되지 않았다. |
| native 설치·retail 차단·회원/reset·재시작·독립 복원 | 구현됐으나 검증 미완료 | 로컬 실제 boundary, JA/EN 회원 및 KO 수정 집중 검사, 재시작/별도 DB 복원 범위 성공을 보존했다. [기능별 로컬 outcome](evidence/2026-10-29-procurement-local/README.md)은 기존 DB와 당시 수정 runtime의 근거다. 최종 SHA의 clean 설치·전 단계 aggregate·cleanup은 hosted 준비 실패로 미완료다. |
| 10폭·성능/접근성·키보드·독립 시각 | 구현과 해당 범위 검증 완료 | 소스 일치한 bd1ced8 frontend의 quality3:7경로×원본10폭/밝음·어둠의 layout84·axe84·trusted lab click14·Lighthouse14 통과, 성능99–100·접근성100·공개 SEO100·LCP최대2131.1ms·CLS최대0.0001. 실제54PNG를 별도 GPT가 검수했고 수동27대표 셀/42정적 crop의13개 incomplete 패턴을 판정했다. 자동 incomplete는 지우지 않았다. cc99bbb 언어 선택기 접근성 이름 현지화와 native 옵션/키보드·기존8개 Global key 보존도 집중 확인했다. 전체 WCAG·모든 상태·field INP·실기기 인증은 아니다. |
| 관리자 한국어·권한 변경 감사 | 구현과 해당 범위 검증 완료 | 실제17관리자 페이지+로그인, 확인한7개 정적 미번역 종료. known native5Tab의 한국어 fallback만 CAS 수정하고 다른 언어/사용자 지정 값/Tab metadata/ACL/직원 profile/12domain 불변과 멱등을 확인했다. locale43·실제 DB12·XLIFF15 parse 통과. 공식 native permission grid의 부모 재귀 READ grant3/revoke3·감사6행·새 조회·원래 ACL/직원 보존 통과. 전체 숨은 오류/메일/보고서의100% 한국어 또는 최종 fresh hook 설치 성공으로 확대하지 않는다. |
| 안전한 PWA cache·설치 안내·Push provider 구현 | 구현과 해당 범위 검증 완료 | 새 Node2·기존 SW73검사, 실제 native autoload/locked vendor 공존·VAPID ES256·AES128GCM·mock201/410/503·TLS/timeout·Configuration/원장/outbox 무변경 통과. 공개 static cache와 private bypass, 실제 HTTPS/live gate를 유지한다. 실제 기기 설치/수신·철회·업데이트 인수는 외부 대기다. |
| 실제 상품·운영 정책·운영 환경·기기 | 외부 자료·운영 환경 대기 | 관리망의 Amazon/Rakuten CONNECT403, 실제 사용 근거/상품 샘플·운영 신원/문안·SMTP/HTTPS/keys·배포/감시/복원/기기 근거가 남는다. 자료 목록은 아래 단일 운영 입력표를 재사용한다. |
| 판매 결제·배송·반품/상품환불·포인트 사용/환전·현금 지갑·출금 | 기존에 명시적으로 확정된 범위 제외 | 발주 요청·수동 수당 원장과 구분한다. 기존 소매 기능을 중복 제작하거나 현 출시 요구로 되돌리지 않는다. |

범위별 행은 크기와 포함 관계가 달라 완료율로 환산하지 않는다. 현재 확인하지 못한 코드 공백을 임의로 만들지 않으며, 부분 검증이 곧 전체 필수 요구 완료라는 주장도 하지 않는다.

## 소스·화면·검증 증거의 경계

이전 hotcopy runtime은 재시작 때 옛 이미지의 entrypoint가 덮어쓴 사례가 있었다. **quality2와 초기 캡처는 당시 상태의 역사적 근거이며 최신 후보 성공이 아니다.** 이후 bd1ced8 이미지 재빌드로 기존 DB/volume을 보존하고 host→image bundle→webroot 일치 및 재시작 전후 데이터를 확인했다. 후속 관리자/캐시/언어 선택기 수정은 명시된 overlay로 반영했다.

최종 local 정렬 근거는 [cc99bbb source alignment](evidence/2026-10-29-procurement-local/cc99bbb-source-alignment-outcome.json)의 앱1128개/vendor1426개다. 기존 설치 보존과 overlay 조합이므로 immutable fresh 설치 성공을 뜻하지 않는다. hosted fresh run은 같은 후보에서 새로 build·설치·저장/재조회·복원·재시작 지속성을 확인해야 한다.

- [실제 로컬 기능·품질·이미지 증거 목록](evidence/2026-10-29-procurement-local/README.md)
- [독립 코드/54PNG 검수와 한계](evidence/2026-10-29-procurement-local/INDEPENDENT_REVIEW.md)
- [bounded 수동 접근성 판정](evidence/2026-10-29-procurement-local/BOUNDED_MANUAL_REVIEW.md)
- [관리자 한국어와 native CAS proof](evidence/2026-10-29-procurement-local/admin-korean/)
- [native cache warmup outcome](evidence/2026-10-29-procurement-local/native-cache-warmup-outcome.json): 상류 iterator가 module vendor의 비-template까지 읽던 원인을 module-owned `*.twig` iterator로 교정. core/runtime loader나 메모리 한도를 바꾸지 않고 기본512MB CLI warmup 및 실제 관리자 화면을 확인했다.

별도 GPT 팀 내부 검수는 실제 수행했다. **외부 Work Mode 세션에 직접 전달하거나 인수가 완료됐다고 기록하지 않는다.** Codex browser 열기 요청의 queued 응답도 실제 화면 접근 증거로 사용하지 않는다. 비밀값·원문 MIME·주소·고객 이름/ID·토큰은 일반 로그와 공유 산출물에 남기지 않는다.

## 출시를 막는 잔여 — 다섯 범주

| 범주 | 현재 차단 내용 | 닫는 조건 |
| --- | --- | --- |
| 1. 동일 후보의 hosted fresh 통합 | 세 실행이 모두 build 준비에서 중단됐다. 로컬 근거를 대체할 최종37단계 native 전체 결과가 없다. | 실제 필요 범위의 build/CA 권한 경로 수정 → 안정 SHA 한 번의 fresh QA → 전 phase 실제 outcome·aggregate·cleanup·artifact 확인. fresh native hook과 분류 부모/leaf·고객 하위 메뉴/filter 연결도 포함한다. |
| 2. 실제 상품 원문·분류/사진 인수 | 실제 Amazon Japan/Rakuten은 관리망 CONNECT403으로 미검증이다. 합성 source/기하학 사진은 원문 호환과 이미지 사용 근거가 아니다. | 허용되는 실제 원문/피드/내보내기 접근과 사용 근거 아래 출시 상품의 가격·상세·옵션·사진·분류/검수/snapshot을 대조한다. 차단 우회·임의 최저가 확정·자동 분류 신뢰로 대체하지 않는다. |
| 3. 실제 운영자·참여자·정책 | 운영자/지원·실제 안내 대상/수량·검토/수당 기준·세 언어 정책의 운영 승인이 남는다. LOGISTEED reference는 운영자 신원이 아니다. | 저장소/대화의 기존 승인 자료를 재사용하고 단일 운영 입력표의 남은 값만 승인 자료와 연결해 native 저장·새 조회·고객 반영을 확인한다. |
| 4. 운영 환경과 전환 인수 | 실제 domain/HTTPS·SMTP·비밀 저장소·불변 app digest·worker·감시·backup/RPO-RTO/restore owner의 운영 연결 근거가 없다. | 승인 staging의 같은 digest와 최소 권한 구성에서 메일·scheduler·감시·별도 복원/rollback·담당자 인수를 확인한 뒤 기존 운영 전환 승인 절차를 따른다. 이번 작업은 배포 승인이 아니다. |
| 5. 실기기 전달·PWA 인수 | Chromium/합성 Push·mock HTTP는 실제 iOS/Android 설치·업데이트·수신/철회를 대신하지 않는다. | 승인 HTTPS와 실제 기기로 PWA 설치/standalone/복귀/업데이트 및 동의·Push 수신·철회·재시도를 확인한다. field INP는 현재 미측정으로 남기고 운영 계측과 구분한다. |

이 다섯 범주는 같은 미완료를 여러 기능으로 중복 세지 않기 위한 분류다. 선택 디자인이나 새 기능을 추가한 종료 조건이 아니다. 개발/합성 검증과 실제 자료/현장 인수를 구분한 채 독립적으로 가능한 CI 수정은 계속한다.

## 외부 입력은 한 목록만 사용

필요 값·사용 위치·없어서 막히는 작업은 기존 [현재 서비스의 운영 입력 체크리스트](PRODUCTION_DEPLOYMENT.md#현재-서비스의-운영-입력-체크리스트)에 한 번만 관리한다. 승인된 브랜드·로고·대화/저장소의 자료는 재사용하며 같은 운영 자료 전체를 다시 요청하지 않는다. 실제 비밀은 값 대신 승인 secret-store 참조와 담당자만 기록한다. 과거 보관자료의 seller·세금·carrier·배송/반품/환불·계좌 입력을 현 목록에 다시 넣지 않는다.

## 종료·운영 전환 기준

1. CI 준비 원인을 수정한 최종 후보의 fresh 통합 outcome/aggregate와 artifact를 확정한다. 실패하면 그 최초 원인과 영향을 집중 재검증한다. 초록 step·not_run·무조건 재시도·timeout 증가를 성공으로 바꾸지 않는다.
2. 위 실제 상품·승인 운영 자료·운영 환경·기기 인수를 같은 승인 release SHA/digest에 연결한다. 전체와 집중, 합성과 실제 원문, 시각과 기능, browser emulation과 실기기를 구분한다.
3. handoff에는 최종 SHA·원격 저장·artifact·변경 화면·기대 결과·잔여 조건·실제 전달 여부를 남긴다. 운영 DB/volume·main·사용자 파일을 보존하고 별도 승인 없는 운영 배포/실결제/실거래/유료 서비스 사용은 진행하지 않는다.

현재는 이 조건들이 모두 닫히지 않았으므로 출시 완료를 선언하지 않는다. 기존 개발 필수 항목이 실제로 완료되면 그 범위는 완료로 명시하고, 운영 자료 대기는 별도로 표시한다. 검증 뒤 선택 개선을 계속 추가해 작업을 무기한 연장하지 않는다.

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
