# ORDENOWA 상품 발주 요청·검토·수동 포인트 출시 요구사항표

2026-10-29 한국시간 사용자 최종 정의: **운영자가 고객에게 상품 발주를 안내 → 고객이 쇼핑몰 주문하듯 상품·수량을 확인하고 발주 요청 → 운영자 수동 검토 → 운영자 수동 포인트 지급 → 고객 잔액·내역 조회**.

[최종 아키텍처](superpowers/specs/2026-10-29-ordenowa-procurement-points-platform-design.md)가 기준이다. 일반 업무 결과/증거 제출 시스템으로 확장하지 않는다. 포인트는 잔액/내역만 표시하며 외부 별도 처리는 운영자가 맡는다. 쇼핑형 상품 UX는 필요하지만 판매 checkout·배송·반품·상품 환불·충전/사용/양도·현금환산/출금은 현재 범위에 없다.

과거 [쇼핑몰39항목표](history/2026-10-29-retail-requirements-matrix.md)와 QA는 역사적 해당 범위로 보존한다. 이전 성공을 새 핵심흐름 인수로 재사용하거나 예전7개 실패를 그대로 현재 출시 차단 목록에 두지 않는다. 현재 전용 모듈 구현과 PHP8.3/MariaDB10.11 집중 검사 결과를 반영한다. 원격 저장 체크포인트는 `887b256`(전용 도메인)·`d994c99`(파싱/Push)이며, 후속 native/UI/통합 코드는 검증 중이다. 과거 전체 QA 성공 `f5b1cca` #40508152705와 현재 통합 결과는 별도로 유지한다.

| ID | 필수 범위 | 현재 상태 | 완료 조건·재사용 |
| --- | --- | --- | --- |
| BASE-001 | native 상품/회원/관리자·브랜드·DB·자식테마 | 구현과 해당 범위 검증 완료 | 과거 native 기반 성공 재사용. 신규상품배정/요청/포인트 인수 아님 |
| ACCESS-001 | 회원·발주요청 진입과 seller gate 분리 | 구현됐으나 검증 미완료 | procurement 모드·seller gate 분리·retail 서버 차단 구현, native 경계 검사 통과. 실제 설치/직접URL 통합 대기 |
| ACCOUNT-001 | 가입/login/logout/reset·내 요청 연결 | 구현됐으나 검증 미완료 | native 기존 성공 유지, 새 workspace 연결·로그인/로그아웃 실제 브라우저 통합 대기 |
| PRODUCT-001 | 운영 상품 등록/선택·이미지/번역 | 구현됐으나 검증 미완료 | 검수 evidence·same-shop 상품/옵션·권리 승인 로컬 이미지·참고 가격 snapshot 구현 및 집중 통과. native 상품 연결 통합 대기 |
| PROC-001 | 고객별 상품 발주 안내/수량한도/기한 | 구현됐으나 검증 미완료 | 안내/회수/기한/수량/version·본인 카테고리 구현, DB/동시성 통과. 관리자/고객 native 통합 대기 |
| PROC-002 | 상품 카드/상세·수량·요청 확인 UX | 구현됐으나 검증 미완료 | JA/EN/KO 카드·상세·수량·확인 구현. controller40/Smarty57 검사 통과, 실제 화면·키보드 통합 대기 |
| PROC-003 | 전용 발주요청 저장·멱등·중복방지 | 구현과 해당 범위 검증 완료 | 고유 제약·snapshot·멱등·실패 rollback 구현, 실제 DB와 12개 동시 경합 검사 통과. native 제출 통합 별도 |
| PROC-004 | 운영자 수동 승인/반려/취소·사유 | 구현됐으나 검증 미완료 | 승인/반려/취소·사유·감사 저장 및 DB 재조회 통과. native 권한별 저장/새 문서 통합 대기 |
| PROC-005 | 고객 본인 요청내역·상태·검색 | 구현됐으나 검증 미완료 | 본인 요청/상태/검색·50건 cursor·snapshot 구현/집중 통과, 새 session native 통합 대기 |
| POINT-001 | 승인요청별 수동 기본지급 | 구현됐으나 검증 미완료 | 승인 요청에만 별도 수동 지급·자동 지급 없음·원본1회 구현/실제 DB 통과, native 버튼/재로그인 대기 |
| POINT-002 | 원장·잔액·지급·감사·outbox transaction | 구현과 해당 범위 검증 완료 | 원장/잔액/지급/감사/outbox 단일 transaction 및 각 쓰기 실패 rollback 실제 DB 통과 |
| POINT-003 | 중복/동시지급·idempotency | 구현과 해당 범위 검증 완료 | 같은/다른 key·실제 대기 관찰 동시 운영자 경합·payload 충돌/범위 검사 통과 |
| POINT-004 | 원본 연결 정정 | 구현과 해당 범위 검증 완료 | 원본 연결 signed delta·원본 덮어쓰기 없음·net0..원본 한도·부분 실패 rollback 검사 통과 |
| POINT-005 | 고객 잔액·적립/정정 내역 | 구현됐으나 검증 미완료 | JA/EN/KO 잔액/적립·정정/원본 링크 구현·controller/Smarty 통과. native100→80/재로그인 대기 |
| POINT-006 | 원장합계 대조·불일치 차단 | 구현과 해당 범위 검증 완료 | SUM(delta)=projection 대조·불일치 새 지급 차단·안전한 감사 기록 실제 DB 통과 |
| SECURITY-001 | 배정상품/요청/포인트 owner·shop·role·CSRF | 구현됐으나 검증 미완료 | owner/shop/role/native CREATE·UPDATE/CSRF 및 외부 이미지/입력 경계 집중 통과, 실제 A/B 세션·denied POST 통합 대기 |
| AUDIT-001 | 안내/회수·요청·검토·지급/정정·권한변경 | 구현됐으나 검증 미완료 | 안내/요청/검토/지급/정정/정책·문의 감사와 READ 화면 구현, rollback 통과. 전체 관리자 권한 변경은 기존 native 이력 재사용 |
| CS-001 | 요청별 문의·공개안내/내부메모 | 구현됐으나 검증 미완료 | 요청↔native 문의 연결·공개 답변/내부 메모 분리·멱등/rollback 실제 DB 통과. native 저장/답변/고객 A/B 재조회 대기 |
| NOTIFY-001 | 발주안내/검토/포인트 알림·메일 | 구현됐으나 검증 미완료 | outbox/독립 mail·push 상태/최대5회·중단 시 UNCERTAIN·중복 방지 구현. killed-worker 포함 실제 DB 통과, Mailpit 실제 MIME 대기 |
| PUSH-001 | 현재 event의 실제Push | 구현됐으나 검증 미완료 | minishlink9.0.4/VAPID·AES128GCM·TLS/무redirect/expiry/retry·실제HTTPS gate 구현 및 mocked HTTP 암호화 통과. 실제 기기 수신 대기 |
| PRIVACY-001 | 새private 경로 no-store/noindex·SW제외 | 구현됐으나 검증 미완료 | 새 private route no-store/noindex·SW bypass 구현/Node/controller 통과. 실제 HTTP 응답·브라우저 검증 대기 |
| LOCALE-001 | 고객JA/EN/KO·전체노출admin한국어 | 구현됐으나 검증 미완료 | 새 UI/메일/정책 JA/EN/KO·신규 관리자 한국어 구현, Smarty24 렌더 통과. native 전체 운영 메뉴 inventory/시각 검수 대기 |
| QUALITY-001 | 새UI10폭·접근성·성능·독립시각 | 구현됐으나 검증 미완료 | 반응형/키보드 focus·실제10폭/locale 시각·성능 측정은 native 브라우저 대기. 합성 렌더를 수동/실기기 PASS로 확대하지 않음 |
| PWA-001 | 공개정적cache·설치안내·업데이트/오프라인 | 구현됐으나 검증 미완료 | 공개 static64개 상한·MIME/no-store/Vary 방어·offline fallback/업데이트·Android 사용자클릭/iOS 안내 구현, 새 Node2개+기존73개 통과 |
| DEVICE-001 | native 설치·standalone/복귀 | 외부 자료·운영 환경 대기 | HTTPS·승인 iOS/Android기기, 에뮬레이션 대체불가 |
| BACKUP-001 | 새요청·snapshot·원장/잔액·감사 복구 | 구현됐으나 검증 미완료 | 전용12테이블+native 연결 백업/manifest·독립 복원 검사 구현, 실제 재시작/복원 통합 대기 |
| OPS-001 | 운영정책·환경·digest/rollback/감시 | 외부 자료·운영 환경 대기 | 운영자/발주·포인트/개인정보정책·HTTPS/SMTP/secrets/backup 연결과 검증 |
| RELEASE-001 | 새집중/통합 QA·증거/handoff | 구현됐으나 검증 미완료 | 집중 preflight 다수 통과, 격리 fresh-install/browser/Mailpit/restart/restore aggregate 실행 중. 아직 전체 통합 PASS 없음 |
| CAT-001 | Amazon Japan·Rakuten 가격·상세·사진 후보·출처 파싱 | 구현됐으나 검증 미완료 | 합성27행동·기존 parser·차단/인증/모호가격 거부·검수 evidence 통과. 실제 원문 HTTPS는 관리망 CONNECT403으로 미검증 |
| CAT-002 | 검수 카테고리·하위메뉴·고객별 상품 배치 | 구현됐으나 검증 미완료 | 원본 breadcrumbs 추출·native 승인 분류·snapshot·본인 메뉴/검색 구현. 실제 원문 분류 대조와 native UI 통합 대기 |
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
