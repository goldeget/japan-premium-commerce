# ORDENOWA 상품 발주 요청·검토·수동 포인트 출시 요구사항표

2026-10-29 한국시간 사용자 최종 정의: **운영자가 고객에게 상품 발주를 안내 → 고객이 쇼핑몰 주문하듯 상품·수량을 확인하고 발주 요청 → 운영자 수동 검토 → 운영자 수동 포인트 지급 → 고객 잔액·내역 조회**.

[최종 아키텍처](superpowers/specs/2026-10-29-ordenowa-procurement-points-platform-design.md)가 기준이다. 일반 업무 결과/증거 제출 시스템으로 확장하지 않는다. 포인트는 잔액/내역만 표시하며 외부 별도 처리는 운영자가 맡는다. 쇼핑형 상품 UX는 필요하지만 판매 checkout·배송·반품·상품 환불·충전/사용/양도·현금환산/출금은 현재 범위에 없다.

과거 [쇼핑몰39항목표](history/2026-10-29-retail-requirements-matrix.md)와 QA는 역사적 해당 범위로 보존한다. 이전 성공을 새 핵심흐름 인수로 재사용하거나 예전7개 실패를 그대로 현재 출시 차단 목록에 두지 않는다. 과거 전체 성공 `f5b1cca` #40508152705와 새 플랫폼 결과를 구분한다.

**아래 완료 상태는 명시한 격리·합성 데이터 검증 범위의 완료다. 최종 동일 SHA의 immutable 이미지 fresh 설치·현행38단계 aggregate 완료를 뜻하지 않는다.** 실제 증거는 [로컬 집중 검증 목록](evidence/2026-10-29-procurement-local/README.md)에 보존했다. 기존 이미지의 재시작 sync가 hotcopy를 되돌린 문제를 발견한 뒤 `bd1ced8` 이미지로 shop만 재생성하고 DB/볼륨을 보존했다. 이후 앱·vendor 소스 정렬/재시작, `cc99bbb` 정렬과 후속 명시적 overlay 검증을 각각 기록했으며 이를 단일 immutable 이미지 검증으로 합치지 않았다.

최신 검증 후보는 `8663e96cdd240be52cd812f4e1d62e1edaa55ee4`이며 전체38phase #40756263392는 진행 중이다. 앱과 경량 SUCCESS #40755121457의 소스는 ad51cff와 동일하다. ad51cff 전체 #40755121454는3phase 성공 뒤13개 메뉴 초기값 assertion에서 실패했다. 대상 클래스가 남지 않아 원인을 단정하지 않고 원래 assertion을 유지한 채 고정13클래스의 비식별 상태 JSON을 추가 수집한다. 초기3실행의 build 준비 실패는6f9c301에서 수정했다. 이후28단계 성공 뒤 auth 진입 URL404와 정책 저장 완료 전 종료 가능성을 실제 대조해 수정하고 집중 재검증했다. 기존 FAIL/not_run을 성공으로 덮어쓰지 않는다. 최종 결과·artifact는 [TEST_RESULTS](TEST_RESULTS.md)를 따른다. **전체 fresh aggregate는 아직 출시 검증 차단 항목**이다.

| ID | 필수 범위 | 현재 상태 | 완료 조건·재사용 |
| --- | --- | --- | --- |
| BASE-001 | native 상품/회원/관리자·브랜드·DB·자식테마 | 구현과 해당 범위 검증 완료 | native 기반 성공·소유 격리 설치·현재 소스 정렬/재시작 증거 보존. 최종 fresh gate는 RELEASE-001 |
| ACCESS-001 | 회원·발주요청 진입과 seller gate 분리 | 구현과 해당 범위 검증 완료 | 실제 native 회원 접근·retail7경로404 통과. order는 최초 native redirect→본인 workspace/private/noindex·판매/로그인 폼 없음·요청 전후 본인 인증·commerce DB 불변까지 검증. 단순 최종200만으로 허용하지 않음 |
| ACCOUNT-001 | 가입/login/logout/reset·내 요청 연결 | 구현과 해당 범위 검증 완료 | JA/EN 실제 가입·주소 없음·중복 거부·logout/login/reset 통과. KO reset 중간 실패는 보존하고 원인 수정 후 KO 집중 성공으로 구분. 최종 fresh에서는3언어 전체 재검증 |
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
| LOCALE-001 | 고객JA/EN/KO·전체노출admin한국어 | 구현됐으나 검증 미완료 | 실제 고객3언어/Smarty·접근성 이름 확인. 기존17화면 외69native 메뉴노드(60정규화 목적지) 중66건200KO 인증 본문,69번역/13Tab CAS/언어 복사 raw label 보강 뒤 영향19건 집중 재조회 PASS. 실제 폼62/DB33/locale60 및 보호 데이터 보존. 외부2페이지 정상 가용·시각과 모든 미진입 오류 분기의100% 인증은 남음 |
| QUALITY-001 | 새UI10폭·접근성·성능·독립시각 | 구현과 해당 범위 검증 완료 | native-quality3 실제7privacy·84layout/axe·14실험실 상호작용·14Lighthouse PASS. JA10폭 자동 측정과3언어 대표 화면75PNG·정적42개 crop/대표27셀·13개 공통 incomplete 유형의 제한된 독립 수동 검토를 구분. 전체 WCAG 인증·현장 INP·실기기 성공은 주장하지 않음 |
| PWA-001 | 공개정적cache·설치안내·업데이트/오프라인 | 구현과 해당 범위 검증 완료 | 공개 static64개 상한·MIME/no-store/Vary 방어·offline fallback/업데이트·사용자 클릭 설치 안내 구현, 새 Node2개+기존73개 회귀·실제 안내 화면 검수 통과. standalone 설치/복귀는 DEVICE-001 |
| DEVICE-001 | native 설치·standalone/복귀 | 외부 자료·운영 환경 대기 | HTTPS·승인 iOS/Android기기, 에뮬레이션 대체불가 |
| BACKUP-001 | 새요청·snapshot·원장/잔액·감사 복구 | 구현과 해당 범위 검증 완료 | 소유 격리 환경 실제 durable/restart/독립 DB restore 통과. 전용12테이블과 native 문의 스레드/메시지·ACL 감사의 private 스키마/데이터 hash,80P 합계·요청 owner·inactive 상품 검증. 운영 volume 복구훈련과 최종 immutable fresh gate는 별도 |
| OPS-001 | 운영정책·환경·digest/rollback/감시 | 외부 자료·운영 환경 대기 | 운영자/발주·포인트/개인정보정책·HTTPS/SMTP/secrets/backup 연결과 검증 |
| RELEASE-001 | 새집중/통합 QA·증거/handoff | 구현됐으나 검증 미완료 | 로컬 범위별 실제 결과·실패 이력·소스 정렬·24개 경량 workflow 명령과 독립 GPT 검수 증거 보존. 이전28단계 성공 뒤 로그인 진입/정책 저장 QA 순서 실패를 수정하고 현재 `8663e96`/#40756263392의38단계 진행을 구분하며, 동일 최종SHA 전체 aggregate PASS는 아직 없음. 다른 외부 워크모드에 전달 완료라고 기록하지 않음 |
| CAT-001 | Amazon Japan·Rakuten 가격·상세·사진 후보·출처 파싱 | 구현됐으나 검증 미완료 | 합성38행동·기존 parser·차단/인증/서로 다른 가격 거부·검수 evidence 통과. AggregateOffer 범위/누락을 단일 참고가격으로 축약하지 않도록 수정·독립 검토, 모호한 재수집 시 기존 검수 snapshot 보존 확인. 실제 원문 HTTPS는 관리망 CONNECT403으로 미검증 |
| CAT-002 | 검수 카테고리·하위메뉴·고객별 상품 배치 | 구현됐으나 검증 미완료 | 원본 breadcrumbs·직원 선택 native 분류 저장·조상 경로·snapshot·본인 메뉴/검색 구현 및 소스/집중 검토 완료. 기존 local gallery의 승인 Home 분류는 fresh 부모/하위2단계 생성·배치·3언어 메뉴/filter 성공을 증명하지 않음. 최종 fresh의 명시적 검증과 실제 원문 분류 대조가 남음 |
| CAT-ENV-001 | 실제 쇼핑몰 접근·상품/사진 게시 근거 | 외부 자료·운영 환경 대기 | 실제 원문 도메인 허용·공개 이미지 사용 근거가 필요. 차단 우회·합성 상품을 실상품 성공으로 보고하지 않음 |
| SCOPE-001 | 판매결제·배송·반품/상품환불·충전/사용/양도/출금 | 기존에 명시적으로 확정된 범위 제외 | 사용자 최신 정의 적용, 기존데이터/코드 보존·retail 직접노출차단 |

## 이전39항목 이관

- 유지·현재 화면/도메인으로 전환: PLAT-001, BRAND-001, DOC-001, ACCT-001, LOCALE-001, CS-001, ADMIN-KO-001, ADMIN-REC-001, PWA-001, PWA-DEVICE-001, PERF-A11Y-001, SECURITY-001, AUDIT-001, BACKUP-001, VIS-001, OPS-ENV-001.
- 상품참조·발주요청·검토·포인트로 대체: QA-REG-001, PROFILE-001, CAT-002, CAT-003, CAT-004, CAT-SCALE-001, GAP-002, ADDR-002, ORD-001, WAL-001, PWA-002, MAIL-001, SEO-001, SEARCH-001, SELLER-001. 상품 카드/상세는 재사용하고 native판매/배송으로 이어지는 의미는 제외한다. 포인트수동지급 포함은 현금지갑/출금전체 부활이 아니다.
- 현재출시 제외·노출차단회귀: LOCALE-002, LOCALE-003, DISC-001, ADDR-001, OPS-RET-001, OPS-SHIP-001.
- 후속 사용자 지시로 필수 추가: CAT-001, CAT-002, CAT-ENV-001. Amazon Japan·Rakuten 파싱·분류 연결을 구현하고 실제 원문 검증을 별도로 남긴다. 수동 상품등록 경로도 유지한다.

## 최소 운영 입력

운영자 신원·고객지원/초기권한, 안내할 상품/수량·참여고객·실제발주요청샘플, 수동검토기준·포인트지급/정정/이의문의/보존·개인정보정책, host/domain/TLS/SMTP/secrets/registry·backup/감시/복구 담당·기기다. 승인된 브랜드자료는 재사용한다. **판매자계좌·상품판매세금표·배송지·운송계약·배송/반품/환불조건은 요구하지 않는다.**

신규 핵심 코드와 집중 검사는 완료 범위가 생겼으며 실제 통합 검증을 진행 중이다. 운영 배포·운영 DB 변경·실결제·실거래는 실행하지 않았다. 실제 코드/QA SHA·artifact는 TEST_RESULTS와 handoff 최신 절에서 최종 기록한다.

현재 변경 범위와 원본 FAIL·집중 결과는 [테스트 결과](TEST_RESULTS.md)를 따른다. 배송/반품/판매결제는 기존 UI 번역을 정비했어도 출시 기능으로 다시 추가하지 않는다.
