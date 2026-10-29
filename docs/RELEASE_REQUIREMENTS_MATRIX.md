# ORDENOWA 상품 발주 요청·검토·수동 포인트 출시 요구사항표

## 2026-10-29 최신 Amazon HTML 파서·격리 QA

검증 코드 [`d107cf9042c1a041c7c32b820c10e0b3874056e9`](https://github.com/goldeget/japan-premium-commerce/commit/d107cf9042c1a041c7c32b820c10e0b3874056e9)는 원격 `work`의 현재 애플리케이션 후보이며 `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지된다. Amazon HTML fallback은 `#wayfinding-breadcrumbs_feature_div`의 순서 경로와 `#altImages`의 `IMAGE` 사진별 대표 URL을 읽는다. 사진 크기 후보를 한 사진으로 합치고, 기존 가격·상품명 확인과 옵션 추론 금지 동작은 유지한다.

집중 [파서/접근 제한/워크플로 검사 #40774173388](https://github.com/goldeget/japan-premium-commerce/actions/runs/40774173388)은 **SUCCESS**: PHP lint, 합성 offline parser 41개 동작, challenge rejection 및 workflow 계약을 통과했다. 전체 [격리 fresh-install #40774173140](https://github.com/goldeget/japan-premium-commerce/actions/runs/40774173140)은 **SUCCESS**: 38/38 단계 PASS, aggregate `passed=true`, run-scope cleanup 성공. [artifact #12855260313](https://github.com/goldeget/japan-premium-commerce/actions/runs/40774173140/artifacts/12855260313)의 GitHub SHA-256 digest는 `sha256:1b5aa21a03492ed6ad631ea0710f04ae968af45914b81e969cad196cea0bae4a`다.

이 결과는 격리·합성 데이터 검증이다. Amazon [B0H4V3GT4J](https://www.amazon.co.jp/dp/B0H4V3GT4J)는 Product JSON-LD/microdata 없이 `#productTitle`, HTML breadcrumb와 7개 이미지 항목을 보였지만 정확한 현재 JPY 가격은 페이지에서 확인되지 않아 계속 fail-closed로 거부한다. 이 페이지 본문 timestamp는 2026-10-20이라 현재 재고/가격 근거로 쓰지 않는다. Rakuten 후보는 원문 페이지 응답이 시간 초과되어 정확 가격·옵션을 검증하지 못했다. 어떤 상품/이미지도 승인되거나 가져오지 않았다.

따라서 CAT-001/CAT-002/CAT-ENV-001, LOCALE-001, OPS-001, PUSH-001, DEVICE-001의 실제 원문·권리·관리자 외부오류·운영환경·기기 인수는 계속 남는다. production deploy, production DB 변경, 실제 거래/결제는 실행하지 않았다. 세부 입력은 [운영 배포 체크리스트](PRODUCTION_DEPLOYMENT.md)를 따른다.

2026-10-29 한국시간 사용자 최종 정의: **운영자가 고객에게 상품 발주를 안내 → 고객이 쇼핑몰 주문하듯 상품·수량을 확인하고 발주 요청 → 운영자 수동 검토 → 운영자 수동 포인트 지급 → 고객 잔액·내역 조회**.

[최종 아키텍처](superpowers/specs/2026-10-29-ordenowa-procurement-points-platform-design.md)가 기준이다. 일반 업무 결과/증거 제출 시스템으로 확장하지 않는다. 포인트는 잔액/내역만 표시하며 외부 별도 처리는 운영자가 맡는다. 쇼핑형 상품 UX는 필요하지만 판매 checkout·배송·반품·상품 환불·충전/사용/양도·현금환산/출금은 현재 범위에 없다.

과거 [쇼핑몰39항목표](history/2026-10-29-retail-requirements-matrix.md)와 QA는 역사적 해당 범위로 보존한다. 이전 성공을 새 핵심흐름 인수로 재사용하거나 예전7개 실패를 그대로 현재 출시 차단 목록에 두지 않는다. 과거 전체 성공 `f5b1cca` #40508152705와 새 플랫폼 결과를 구분한다.

**아래 완료 상태는 명시한 격리·합성 데이터 검증 범위의 완료다. 이번 동일 SHA의 fresh 설치·38단계 결과는 아래에 별도 기록한다.** 실제 증거는 [로컬 집중 검증 목록](evidence/2026-10-29-procurement-local/README.md)에 보존했다. 기존 이미지의 재시작 sync가 hotcopy를 되돌린 문제를 발견한 뒤 `bd1ced8` 이미지로 shop만 재생성하고 DB/볼륨을 보존했다. 이후 앱·vendor 소스 정렬/재시작, `cc99bbb` 정렬과 후속 명시적 overlay 검증을 각각 기록했으며 이를 단일 immutable 이미지 검증으로 합치지 않았다.

검증 코드 `91c6098c6b551946cc8291b31c868656d50c9b34`의 전체 #40763074207은 **38/38PASS/aggregate true/cleanup success/workflow SUCCESS**다. 실제 source/restart1140app+1426vendor 일치, native16브라우저단계·계정/메일/권한/품질/복원까지 통과했다. artifact12850640042 ZIP SHA256 `5c01e0d4b070875e3bac1e75b4586ee20113748a298039dc1a2f5589c4c69802`; 별도 GPT가 실제hosted24PNG를 모두 열어20핵심target을 인수했다(4broad포인트는 의미/geometry 근거 제외). 직전 실패 원본과 실제 CSS 전환 원인·같은30초/모든 assertion 유지 수정은 [TEST_RESULTS](TEST_RESULTS.md)에 보존한다. 아래 완료는 명시한 합성 범위이며 실제 원문·운영 환경·기기 인수는 별도다.

| ID | 필수 범위 | 현재 상태 | 완료 조건·재사용 |
| --- | --- | --- | --- |
| BASE-001 | native 상품/회원/관리자·브랜드·DB·자식테마 | 구현과 해당 범위 검증 완료 | native 기반 성공·소유 격리 설치·현재 소스 정렬/재시작 증거 보존. 최종 fresh gate는 RELEASE-001 |
| ACCESS-001 | 회원·발주요청 진입과 seller gate 분리 | 구현과 해당 범위 검증 완료 | 실제 native 회원 접근·retail7경로404 통과. order는 최초 native redirect→본인 workspace/private/noindex·판매/로그인 폼 없음·요청 전후 본인 인증·commerce DB 불변까지 검증. 단순 최종200만으로 허용하지 않음 |
| ACCOUNT-001 | 가입/login/logout/reset·내 요청 연결 | 구현과 해당 범위 검증 완료 | JA/EN 실제 가입·주소 없음·중복 거부·logout/login/reset 통과. KO reset 중간 실패는 보존하고 원인 수정 후 KO 집중 성공으로 구분. 최신91 fresh에서도3언어 전체 재검증 PASS |
| PRODUCT-001 | 운영 상품 등록/선택·이미지/번역 | 구현과 해당 범위 검증 완료 | 합성 parser→검수→inactive/hidden/nonorderable native 상품·정확 옵션·승인된 로컬 원본2사진·배정 snapshot을 실제 연결/표시. 실제 쇼핑몰 상품 검증은 CAT-001/ENV 별도 |
| PROC-001 | 고객별 상품 발주 안내/수량한도/기한 | 구현과 해당 범위 검증 완료 | DB 수량/기한/version·회수·동시성 및 native 관리자 배정→본인 확인·수량2 제출·새 세션 재조회 통과. 새 하위분류 인수는 CAT-002 별도 |
| PROC-002 | 상품 카드/상세·수량·요청 확인 UX | 구현과 해당 범위 검증 완료 | controller52/Smarty72, 실제 JA/EN/KO 화면·키보드·상품사진 검증. v5의21PNG와 새 C 확인을 포함한 v6의54PNG를 별도 GPT가 검수; C는 최종 제출하지 않아 기존 A/B 원장·요청 보존 |
| PROC-003 | 전용 발주요청 저장·멱등·중복방지 | 구현과 해당 범위 검증 완료 | 고유 제약·snapshot·멱등·실패 rollback·12개 실제 DB 동시 경합과 native 고객 확인→제출→재조회 통과 |
| PROC-004 | 운영자 수동 승인/반려/취소·사유 | 구현과 해당 범위 검증 완료 | 승인/반려/취소·사유·감사 DB 검사 통과. 실제 native 수동 승인과 조회 전용 운영자의 정상 세션 토큰을 사용한 변경 거부 통과. 승인이 자동 포인트를 만들지 않음 |
| PROC-005 | 고객 본인 요청내역·상태·검색 | 구현과 해당 범위 검증 완료 | 본인 요청/상태/검색·50건 cursor·snapshot DB/controller 및 실제 요청 목록/상세·A/B 직접URL·POST 거부·새 로그인 재조회 통과 |
| POINT-001 | 승인요청별 수동 기본지급 | 구현과 해당 범위 검증 완료 | 승인 후0P 유지→별도 native 수동100P 지급→고객 새 로그인100P 확인. 조회 전용 운영자 지급 거부·승인요청별 기본1회·DB 재조회 통과 |
| POINT-002 | 원장·잔액·지급·감사·outbox transaction | 구현과 해당 범위 검증 완료 | 원장/잔액/지급/감사/outbox 단일 transaction 및 각 쓰기 실패 rollback 실제 DB 통과 |
| POINT-003 | 중복/동시지급·idempotency | 구현과 해당 범위 검증 완료 | 같은/다른 key·실제 대기 관찰 동시 운영자 경합·payload 충돌/범위 검사 통과 |
| POINT-004 | 원본 연결 정정 | 구현과 해당 범위 검증 완료 | 원본 연결 signed delta·원본 덮어쓰기 없음·net0..원본 한도·부분 실패 rollback 검사 통과 |
| POINT-005 | 고객 잔액·적립/정정 내역 | 구현과 해당 범위 검증 완료 | 실제 native100P 지급→연결 -20P 정정→80P·두 원장 행·합계·원본 링크와 고객 새 세션 재조회 통과. JA/EN/KO 표시·안전한 화면 검수 증거 보존 |
| POINT-006 | 원장합계 대조·불일치 차단 | 구현과 해당 범위 검증 완료 | SUM(delta)=projection 대조·불일치 새 지급 차단·안전한 감사 기록 실제 DB 통과 |
| SECURITY-001 | 배정상품/요청/포인트 owner·shop·role·CSRF | 구현과 해당 범위 검증 완료 | 실제 A/B 세션·타인 GET/정상 own-CSRF POST 거부·거부 후 실제 로그인 고객·원소유자 요청/잔액 불변 통과. native masked 토큰의 정상 저장과 잘못된 POST body403/DB 불변, 역할별 검토/지급/정정 거부까지 확인 |
| AUDIT-001 | 안내/회수·요청·검토·지급/정정·권한변경 | 구현과 해당 범위 검증 완료 | 도메인 감사/rollback·native ACL MariaDB31검사 통과. 실제 공식 권한 화면 체크박스의 부모 포함 READ3개 부여·회수 AJAX6건/감사6행·trusted actor/target·global scope·다른 프로필/직원 보존·최종 전용 프로필 권한0 확인. 모듈권한 경로는 DB 집중 검사 범위 |
| CS-001 | 요청별 문의·공개안내/내부메모 | 구현과 해당 범위 검증 완료 | native 문의 저장·멱등 재전송·공개 답변/내부 메모 분리·고객 A/B GET/POST 격리와 본인 재조회 통과. 문의 도메인과 native 스레드/메시지 복원도 포함 |
| NOTIFY-001 | 발주안내/검토/포인트 알림·메일 | 구현과 해당 범위 검증 완료 | 실제 격리 SMTP/Mailpit5건·JA/EN/KO MIME·수신자 격리·재실행 중복0·native delivery 재조회 통과. killed-worker UNCERTAIN/최대5회 DB 검사 통과. 운영 SMTP 전달성은 OPS-001 별도 |
| PUSH-001 | 현재 event의 실제Push | 외부 자료·운영 환경 대기 | 구현·동의/철회·outbox 및 실제 native autoload와 locked vendor 공존, mock HTTP/VAPID/AES128GCM·TLS/expiry/retry 검증 완료. 운영 HTTPS/VAPID/저장키·실제 provider·기기 수신은 미검증 |
| PRIVACY-001 | 새private 경로 no-store/noindex·SW제외 | 구현과 해당 범위 검증 완료 | 실제7개 고객/공개 경로의 HTTP/privacy 검사·native 거부 응답·private no-store/noindex 통과. Node worker/cache 회귀도 통과; 운영 CDN/HTTPS 인수는 별도 |
| LOCALE-001 | 고객JA/EN/KO·전체노출admin한국어 | 구현됐으나 검증 미완료 | 실제 고객3언어/Smarty·접근성 이름 확인. 기존17화면 외69native 메뉴노드(60정규화 목적지) 중66건200KO 인증 본문,69번역/13Tab CAS/언어 복사 raw label 보강 뒤 영향19건 집중 재조회 PASS. 실제 폼62/DB33/locale61 및 보호 데이터 보존. 외부2페이지 정상 가용·시각과 모든 미진입 오류 분기의100% 인증은 남음 |
| QUALITY-001 | 새UI10폭·접근성·성능·독립시각 | 구현과 해당 범위 검증 완료 | 최신91 fresh의 JA7경로/10폭+일부dark:7privacy·84layout/axe·14클릭/Lighthouse PASS, 성능/접근성100·공개SEO100·모바일LCP최대1747.3ms·CLS0.0001. hosted20target 실제 인수. incomplete84셀·수동13패턴 범위와 fieldINP/전체WCAG/기기 미검증 유지 |
| PWA-001 | 공개정적cache·설치안내·업데이트/오프라인 | 구현과 해당 범위 검증 완료 | 공개 static64개 상한·MIME/no-store/Vary 방어·offline fallback/업데이트·사용자 클릭 설치 안내 구현, 새 Node2개+기존73개 회귀·실제 안내 화면 검수 통과. standalone 설치/복귀는 DEVICE-001 |
| DEVICE-001 | native 설치·standalone/복귀 | 외부 자료·운영 환경 대기 | HTTPS·승인 iOS/Android기기, 에뮬레이션 대체불가 |
| BACKUP-001 | 새요청·snapshot·원장/잔액·감사 복구 | 구현과 해당 범위 검증 완료 | 소유 격리 환경 실제 durable/restart/독립 DB restore 통과. 전용12테이블과 native 문의 스레드/메시지·ACL 감사의 private 스키마/데이터 hash,80P 합계·요청 owner·inactive 상품 검증. 운영 volume 복구훈련과 최종 immutable fresh gate는 별도 |
| OPS-001 | 운영정책·환경·digest/rollback/감시 | 외부 자료·운영 환경 대기 | 운영자/발주·포인트/개인정보정책·HTTPS/SMTP/secrets/backup 연결과 검증 |
| RELEASE-001 | 새집중/통합 QA·증거/handoff | 구현과 해당 범위 검증 완료 | 코드 `d107cf9042c1a041c7c32b820c10e0b3874056e9`: 전체 #40774173140 38/38단계·aggregate true·cleanup success, 집중 #40774173388 parser 41개 동작 PASS. artifact #12855260313 digest `sha256:1b5aa21a03492ed6ad631ea0710f04ae968af45914b81e969cad196cea0bae4a`. 기존 91c 시각검수는 UI 무변경 범위만 유지하며 실제 원문·운영·기기 인수는 별도 |
| CAT-001 | Amazon Japan·Rakuten 가격·상세·사진 후보·출처 파싱 | 구현됐으나 검증 미완료 | `d107cf9042c1a041c7c32b820c10e0b3874056e9` parser change, 집중 #40774173388의 41 synthetic offline behaviors PASS. Amazon sample `B0H4V3GT4J`는 HTML breadcrumb·7 image entry를 보였지만 exact current JPY offer 없음이라 정상 거부; Rakuten 후보 응답 timeout. 현재 판매 SKU·정확 가격/옵션·원문 권한 미검증, 상품 미수입 |
| CAT-002 | 검수 카테고리·하위메뉴·고객별 상품 배치 | 구현됐으나 검증 미완료 | 합성 parser→검수→native 2단계 저장/배치 기존 검증 유지. Amazon source breadcrumb `文房具・オフィス用品 > 事務用品 > 文具収納 > ペンケース`는 출처 경로로만 보존하며 native taxonomy로 자동 매핑하지 않음. 실 SKU 대조와 운영자 분류 승인 필요 |
| CAT-ENV-001 | 실제 쇼핑몰 접근·상품/사진 게시 근거 | 외부 자료·운영 환경 대기 | 승인된 현행 source access/feed, exact in-stock SKU 및 공개 이미지 사용권 증거가 필요. sample/cache/synthetic 결과는 판매·게시 권한이 아님; 접근 차단을 우회하거나 상품을 가져오지 않음 |
| SCOPE-001 | 판매결제·배송·반품/상품환불·충전/사용/양도/출금 | 기존에 명시적으로 확정된 범위 제외 | 사용자 최신 정의 적용, 기존데이터/코드 보존·retail 직접노출차단 |

## 이전39항목 이관

- 유지·현재 화면/도메인으로 전환: PLAT-001, BRAND-001, DOC-001, ACCT-001, LOCALE-001, CS-001, ADMIN-KO-001, ADMIN-REC-001, PWA-001, PWA-DEVICE-001, PERF-A11Y-001, SECURITY-001, AUDIT-001, BACKUP-001, VIS-001, OPS-ENV-001.
- 상품참조·발주요청·검토·포인트로 대체: QA-REG-001, PROFILE-001, CAT-002, CAT-003, CAT-004, CAT-SCALE-001, GAP-002, ADDR-002, ORD-001, WAL-001, PWA-002, MAIL-001, SEO-001, SEARCH-001, SELLER-001. 상품 카드/상세는 재사용하고 native판매/배송으로 이어지는 의미는 제외한다. 포인트수동지급 포함은 현금지갑/출금전체 부활이 아니다.
- 현재출시 제외·노출차단회귀: LOCALE-002, LOCALE-003, DISC-001, ADDR-001, OPS-RET-001, OPS-SHIP-001.
- 후속 사용자 지시로 필수 추가: CAT-001, CAT-002, CAT-ENV-001. Amazon Japan·Rakuten 파싱·분류 연결을 구현하고 실제 원문 검증을 별도로 남긴다. 수동 상품등록 경로도 유지한다.

## 남은 작업의 자동 수행과 최종 인수

상품 URL 선정과 가격·옵션·분류 대조는 GPT가 직접 조사한다. 사용자에게 상품 URL 목록을 다시 요청하지 않는다. 공개 사진 사용 근거도 직접 확인하고, 확인되지 않은 자료는 게시하지 않은 상태로 기록한다.

GPT는 기존 승인자료와 연결된 환경을 먼저 조사하고 다음 준비를 독립적으로 수행한다.

1. Amazon Japan/Rakuten 실제 원문 호환 조사와 필요한 parser 수정, 검수·상품·분류·배정 연결 검증.
2. 외부 관리자 페이지의 정상/오류 분기와 실제 한국어 표시 조사 및 격리 검증 준비.
3. 불변 배포 artifact·SHA/digest manifest, staging 검증, migration/rollback 호환 절차 구체화.
4. 메일/Push worker 실행, 비밀 저장소 주입 방식, 스케줄·감시·암호화 backup/보존/복원 자동화의 구현과 격리 검증.
5. 기존 정책 초안을 재사용해 게시 직전 검토본과 반영 절차 준비. 미확정 운영자 신원·계약·정책을 사실로 만들지 않는다.
6. 실제 기기·HTTPS 검증 경로와 계정이 연결되어 있는지 조사하고 가능한 인수를 수행한다.

외부 승인·접근이 실제로 필요한 경우에만 정확한 대상, 사용 위치, 독립적으로 시도한 작업과 결과, 최종 승인할 구체적인 선택안을 한 목록으로 기록한다. 문서에 설정 이름이 있다는 이유만으로 사용자에게 전체 값을 입력하도록 요구하지 않는다. 기술 작업·운영 구성·실행 검증을 단순한 값 입력 대기로 바꾸지 않는다.

실제 운영자 신원, 타인 사진의 이용 허락, 사용할 수 없는 실기기, 미연결 운영 계정의 접근권한 및 비용·운영 전환 승인은 근거 없이 보유한 것으로 취급하지 않는다. 준비 가능한 작업은 이 항목과 독립적으로 계속 진행한다.

이미 승인된 브랜드 표기·자산, 일본어 설명, JPY 세금포함 표시와 지원 지역 무료배송은 재사용한다. 판매자 계좌·실제 판매 세금표·배송/반품/환불 조건은 현재 범위에 추가하지 않는다.

코드 d107cf9042c1a041c7c32b820c10e0b3874056e9의 38단계 전체 격리 검증과 41개 파서 행동 집중 검증을 완료했다. 실제 원문·상품/이미지 권리·운영·기기 인수는 남는다. 운영 배포·운영 DB 변경·실결제·실거래는 실행하지 않았다. 실제 코드/QA SHA·artifact는 TEST_RESULTS와 handoff 최신 절에 기록했다.

현재 변경 범위와 원본 FAIL·집중 결과는 [테스트 결과](TEST_RESULTS.md)를 따른다. 배송/반품/판매결제는 기존 UI 번역을 정비했어도 출시 기능으로 다시 추가하지 않는다.
