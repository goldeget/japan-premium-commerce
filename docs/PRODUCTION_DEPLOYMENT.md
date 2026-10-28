# ORDENOWA 상품 발주·수당 포인트 운영 준비

## 현재 구현과 배포 상태

2026-10-29 구현 후보는 PrestaShop 9.2.0·Hummingbird 자식 테마와 `ordenowaprocurement` 전용 데이터 모델을 사용한다. 최신 parser 후보 `d107cf9042c1a041c7c32b820c10e0b3874056e9`는 Amazon HTML breadcrumb·사진 갤러리 메타데이터를 추가했다. 집중 parser #40774173388은 41개 동작 PASS, 전체 fresh QA #40774173140은 38/38·aggregate/cleanup SUCCESS이며 artifact #12855260313 digest `sha256:1b5aa21a03492ed6ad631ea0710f04ae968af45914b81e969cad196cea0bae4a`다. 이들은 합성·격리 인수다. 실제 Amazon/Rakuten 가격/상품/이미지권리, 외부 관리자 오류페이지, 운영환경, real Push, 물리 iOS/Android 기기 인수는 남는다. 운영 배포·production DB 변경·실제 발신 SMTP·실거래는 실행하지 않았다. 상세 SHA/run/evidence는 TEST_RESULTS.md와 AI_BROWSER_QA_HANDOFF.md를 따른다.

현재 Compose와 테스트 DB·named volume은 개발·격리 QA 대상이다. 운영 서버·운영 DB·`main`을 이 문서 작업에서 변경하지 않았다. 실제 배포 전에 승인된 코드 SHA·이미지 digest·migration 집합·복구 절차와 담당자를 정한다. `ORDENOWA_APP_MODE=procurement`는 전용 회원·발주 경로와 legacy retail 차단을 선택하는 서버 설정이다. 상품 판매·결제·배송·반품·상품 환불·현금 환산·출금은 현재 서비스 범위에 없다.

## 현재 서비스의 운영 입력 체크리스트

아래는 현 플랫폼의 실제 외부 입력 목록이다. 값 자체가 없으면 표의 해당 작업을 인수할 수 없다. 비밀은 값 대신 비밀 저장소 참조와 담당자만 문서에 남긴다. 아래 보관자료의 과거 seller·세금·배송·결제 입력은 현 목록에 추가하지 않는다.

| 실제 입력 이름·자료 | 사용 위치 | 없을 때 차단되는 작업 |
| --- | --- | --- |
| `operator_name`, `support_email`; 선택 `support_phone`, HTTPS `support_url`; 초기 운영자·참여 고객과 권한 담당자 | **서비스 운영자·지원·정책**, 계정·문의 운영 | 실제 운영자·지원 공개와 운영 인수. LOGISTEED 참조정보에서 신원·권한을 추정하지 않는다. |
| `terms`, `privacy`, `points` 각각 `ja/en/ko`; 지급·정정·이의 문의·보존 기준과 승인자 | 정책 버전·공개 링크, 검토·수당·개인정보 운영 | 정책 공개 준비와 실제 참여자 운영 인수 |
| 안내할 실제 상품·정확한 옵션·기본/최대 수량·참여 고객·검토 기준·승인된 발주 샘플·원문/이미지 사용 근거 | 상품 등록/수집 검토, 고객별 안내와 수동 승인·지급 | 실제 상품 안내와 파싱 지원 범위 인수. 합성 성공을 실제 출처 승인으로 대체하지 않는다. |
| 운영 host/project/volume 식별, `PS_DOMAIN`, DNS/TLS·proxy 담당자, `SHOP_BIND_ADDRESS`, `SHOP_PORT`, `HOST_CA_BUNDLE`; 승인 SHA·app/DB image digest·registry 참조 | 배포 정의·도메인·접근·승격·롤백 | 공개 운영 배포. `.env`만 바꿔 기존 설치 DB의 도메인 이전을 완료했다고 보지 않는다. |
| `MARIADB_DATABASE`, `MARIADB_USER`, `MARIADB_PASSWORD`, `MARIADB_ROOT_PASSWORD`, `ADMIN_MAIL`, `ADMIN_PASSWD`; 실제 네이티브 SMTP 설정·발신 도메인·수신 검증·담당자 | 비밀 저장소, native 계정/DB, reset·발주·포인트 메일 | 운영 설치·계정 복구 및 실제 메일 전달 인수 |
| `ORDENOWA_PUSH_STORAGE_KEY`, `ORDENOWA_PUSH_VAPID_PUBLIC_KEY`, `ORDENOWA_PUSH_VAPID_PRIVATE_KEY`, `ORDENOWA_PUSH_VAPID_SUBJECT`; 승인 HTTPS host·실기기·동의 문구·Push 담당자 | 암호화 구독 저장소, Web Push 인증·실제 전달·철회 검증 | 구독 저장과 실제 기기 Push 인수. 비밀값을 Git·채팅·로그에 기록하지 않는다. |
| 비공개 scheduler 담당자, DB/disk/error·알림 채널 감시, 암호화 백업 저장소·접근자·보존기간·RPO/RTO·복구 대상/승인자·migration 호환성 | worker 운영, 감시·백업·복원·롤백 | 지속 운영과 복원/배포 인수. 실제 값과 담당자를 임의로 정하지 않는다. |

정책 문안은 [JA/EN/KO 이용약관·개인정보·포인트 9개 검토 초안](POLICY_DRAFTS_JA_EN_KO.md)을 재사용한다. 운영자는 초안을 확인·수정하고 위 단일 입력표의 운영자·연락처·보존·위탁/국가·이의 처리 미확정 값만 보완한 뒤, 승인된 본문만 기존 정책 버전 경로로 저장·게시한다. 초안 작성은 승인이나 게시가 아니며, 자리표시가 남은 문구를 운영 정책으로 저장하지 않는다.

## 후보 준비와 인수 순서

1. 승인된 Git SHA, Hummingbird gitlink와 app/DB 불변 image digest를 기록한다. 운영과 다른 project/DB/volume으로 staging을 준비한다. 실제 운영 고객 데이터나 기존 운영 volume을 테스트 대상으로 쓰지 않는다. 이 저장소의 local build·mutable tag만으로 production artifact 승격을 완료할 수 없다.
2. 공식 기반·자식 테마·전용 모듈을 배치하고 전용 Schema를 추가 설치한다. 기존 상거래 테이블을 변환하거나 초기화하지 않는다. 현재 전용 테이블은 assignment, request, review, point_account, point_award, point_ledger, activity, notification, notification_delivery, policy, support_link, support_post이며 설치 prefix가 붙는다.
3. 실제 운영자·지원·세 언어 정책을 입력하고 버전과 공개 링크를 확인한다. 해당 쇼핑몰의 담당자에게 메뉴별 READ/ADD/EDIT와 정책 권한을 부여한다. 고객을 판매자 gate와 분리해 native 가입/login/reset을 확인하고 retail 직접 진입 차단을 확인한다.
4. 같은 후보에서 고객 A 상품 안내·수량 확인·요청 → 운영자 승인 → 별도 합성 100P 지급 → A 새 로그인 100P → -20P 정정·원장/잔액 80P를 확인한다. 고객 B 접근 거부, 미승인 지급 거부, 동시·재시도 중복 방지, 단계별 rollback, 원장 대조와 검색·pagination도 확인한다. 이 수치는 QA용 합성값이다.
5. native SMTP로 reset 및 발주/검토/포인트 이벤트의 실제 수신자·언어·MIME를 확인한다. 채널 재시도가 포인트나 메일 중복을 만들지 않는지 조사한다. 격리 Mailpit 증거와 운영 SMTP 수신 증거를 구분한다.
6. 공개 HTTPS와 실기기에서 동의·구독·전달·철회·재시도, PWA 설치/업데이트, PC/모바일·키보드·세 언어 화면을 확인한다. 단위 검사·MockHandler·브라우저 에뮬레이션을 실제 Push 기기 전달의 증거로 대체하지 않는다.
7. 동일 snapshot set의 격리 복원·재시작 후 소유권·검토·원장 합계·정책·알림 상태를 재조회한다. 승인된 migration/rollback 호환성, 감시와 담당자 인수가 확보된 뒤에만 별도 운영 변경 승인을 진행한다. 이 문서는 운영 시작 명령이나 배포 승인을 발행하지 않는다.

## 메일·알림 scheduler

전용 outbox는 도메인 transaction에서 기록된다. 실제 외부 전달은 commit 후 비공개 서버 CLI에서 실행한다. 직접 HTTP endpoint나 고객 요청에서 dispatch하지 않는다. native 비밀번호 재설정은 기존 기능을 유지한다.

```sh
php modules/ordenowaprocurement/bin/dispatch-notifications.php --shop=1 --channels=mail,push --limit=25
```

서버 담당자가 실제 확인한 쇼핑몰 번호별로 1분 간격의 scheduler를 구성하고 명령의 종료 상태와 안전한 집계만 수집한다. 채널을 명시해야 하며 `mail` 또는 `push`만 별도로 실행할 수 있다. native SMTP·고객의 현재 same-shop 이메일/언어·실제 수신을 먼저 확인한다. 예시는 scheduler를 설치하거나 운영 배포를 수행하지 않는다.

채널 상태는 `notification_delivery`에 독립적으로 남는다. 성공은 재전송하지 않고 확정 실패는 backoff와 최대 5회 시도를 적용한다. 전송 중 crash·불확실한 결과는 `UNCERTAIN`이며 자동 재전송하지 않는다. 실제 provider/mail 기록을 조사하고 중복 가능성을 받아들이는 경우에만 지정 delivery를 명시적으로 요청한다.

```sh
php modules/ordenowaprocurement/bin/dispatch-notifications.php --shop=1 --channels=mail --retry-uncertain=DELIVERY_ID --ack-possible-duplicate --limit=25
```

이 명령도 시도 횟수를 초기화하지 않는다. `FAILED`·`UNCERTAIN` 감시 담당자와 조사 절차를 운영 인수에 포함한다. in-app 알림과 포인트 commit은 메일/Push 실패와 독립적이다. [worker 상세](../modules/ordenowaprocurement/bin/NOTIFICATIONS.md)를 참조한다.

## Web Push 활성 조건

`modules/kuraneapush/composer.json`·lock의 `minishlink/web-push` 9 계열 실제 라이브러리와 vendor를 승인 이미지에 포함한다. `LivePushFactory`는 다음 조건을 모두 충족할 때 live provider를 선택한다.

- 해당 쇼핑몰 설정 `ORDENOWA_PUSH_LIVE_ENABLED=1`, `ORDENOWA_PUSH_HTTPS_VALIDATED=1`.
- 실제 HTTPS·인증서·service worker·subscription 경로를 검증한 환경. HTTPS 검증 플래그는 그 증거를 남긴 뒤에만 설정한다.
- 비밀 저장소에서 주입한 `ORDENOWA_PUSH_VAPID_PUBLIC_KEY`, `ORDENOWA_PUSH_VAPID_PRIVATE_KEY`, 유효한 `ORDENOWA_PUSH_VAPID_SUBJECT`.
- `ORDENOWA_PUSH_STORAGE_KEY`: base64로 인코딩한 32바이트 구독 암호화 키. 재시작·복구에서 같은 키를 유지하고 교체는 별도 migration 절차로 다룬다.
- 쇼핑몰별 `ORDENOWA_PUSH_EVENT_PROCUREMENT`, `ORDENOWA_PUSH_EVENT_POINTS` 활성, `ORDENOWA_PUSH_CONSENT_NOTICE_JA/EN/KO`, 해당 고객의 현재 동의와 유효한 기기 구독.

실제 값이 없거나 gate가 닫히면 provider는 unavailable 상태를 유지한다. `procurement`/`points`와 locale만 Push payload에 들어가며 잔액·금액·상품·고객 식별정보는 넣지 않는다. worker의 목적지는 로그인 후 요청/포인트 워크스페이스다. endpoint 만료, 철회, 불확실한 전송과 기기별 전달을 실제 환경에서 확인해야 운영 Push를 인수할 수 있다. library 암호화/MockHandler 검사의 성공은 그 실기기 인수를 대신하지 않는다.

## 일관된 백업·복원·롤백

기존 native 고객·설정·상품을 보존하면서 새 안내·요청·스냅샷·최종 검토·지급·원장·잔액·정책·감사·인앱/채널 outbox·Push 구독/receipt, webroot·수집 검토 자료와 필요한 암호화 키 참조를 같은 복구 시점으로 묶는다. 승인된 maintenance/쓰기 gate를 사용하고 release SHA·image digest·schema/migration·시각·checksum을 manifest로 연결한다.

복원은 다른 host/project/DB/volume에서 수행한다. 복구본의 외부 메일/Push 발신을 닫고 A/B 소유권·최종 상태·기본 지급 한 번·`SUM(ledger.delta)=point_account.balance`·채널 불확실성을 조사한다. 이미 발신했을 수 있는 outbox를 복원했다는 이유로 자동 재전송하지 않는다. 재시작 뒤 같은 검사를 반복하고 restore 승인자가 수락하기 전에는 원본 운영 상태를 덮어쓰지 않는다.

장애 시 쓰기/traffic gate를 닫고 실패 시각·SHA/digest·migration과 개인정보를 제거한 증거를 보존한다. 호환성이 검증된 경우만 이전 app digest로 되돌린다. DB·파일·정책·원장이 이전 코드와 호환되지 않으면 image만 되돌리지 않는다. `down -v`, prune, volume 재생성 또는 운영 DB 초기화로 복구하지 않는다. snapshot set·소유권·원장·알림 상태가 맞지 않으면 공개 트래픽을 열지 않는다.

## 보관자료 — 이전 소매 상거래 배포 안내

아래는 이전 판매·주문·배송·환불 설계와 당시 QA 증거의 보관자료다. 현 상품 발주·수당 포인트의 출시 요구·입력·완료 증거로 적용하지 않는다. 과거 실행 URL과 성공 기록은 해당 과거 범위만 설명한다. 현재 누락 입력은 위 표, 현재 acceptance는 현재 후보의 실제 결과로 판단한다.

### ORDENOWA 운영 배포 준비 안내

#### 현재 경계

현재 Compose는 로컬 개발과 격리 QA용이다. 기본 웹 포트는 loopback 주소에만 바인딩되고, 기본 `PS_DOMAIN`은 `localhost:<SHOP_PORT>`다. 이 저장소에서 실제 운영 서버, 공개 DNS, TLS 종료 프록시, 운영 메일 발신 또는 배포 롤백을 검증하지 않았다. 이 안내는 운영 배포 승인이 아니며 운영 배포를 실행하지 않는다.

#### 최초 설치 시 필요한 값

`.env.example`에는 로컬 접속을 위한 안전한 loopback 기본값이 있다. `PS_DOMAIN`은 고정하지 않아 `SHOP_PORT`를 바꾸면 Compose 기본 host도 따라간다. 별도 도메인은 승인된 환경의 `.env`에 명시한다. 실제 설치 전에 `.env`를 만들고 다음 값을 비밀 저장소 또는 로컬 전용 파일로 채운다. 비밀값은 Git에 커밋하거나 명령 출력·Actions 로그·브라우저 증거에 기록하지 않는다.

| 값 | Compose에서 사용되는 곳 | 준비 조건 |
| --- | --- | --- |
| `MARIADB_DATABASE` | MariaDB와 PrestaShop DB 이름 | 환경별 고유 이름 |
| `MARIADB_USER`, `MARIADB_PASSWORD`, `MARIADB_ROOT_PASSWORD` | MariaDB 계정 | 서로 다른 강한 비밀번호. 실제 운영 값은 `.env.example`의 placeholder가 아님 |
| `ADMIN_MAIL`, `ADMIN_PASSWD` | 최초 Back Office 계정 | 담당자 소유의 운영 메일과 별도 비밀번호 보관 절차 |
| `SHOP_PORT` | 호스트 공개 포트 | 승인된 리버스 프록시 구성과 일치 |
| `SHOP_BIND_ADDRESS` | 웹 컨테이너의 호스트 바인딩 주소 | 기본값은 `127.0.0.1`; 외부 공개 값은 서버 방화벽·프록시 설계 승인 후에만 지정 |
| `PS_DOMAIN` | 최초 설치 및 health check의 shop host | 최초 설치 전에 최종 도메인과 포트 지정. PrestaShop은 도메인을 설치 DB에도 저장하므로 설치 뒤 `.env`만 바꾸는 것으로 도메인 이전이 끝나지 않음 |
| `HOST_CA_BUNDLE` | 컨테이너에서 읽는 호스트 CA 번들 | 배포 호스트의 신뢰 저장소 경로 |

현재 `.env.example` 값은 **로컬 전용 예시**다. 운영 도메인, 공개 bind 주소, 관리자 계정, 실제 데이터베이스 암호를 추정해 넣지 않는다. `PS_DOMAIN`은 첫 설치 전에 결정하고, 해당 값으로 `docker compose config --quiet`를 확인한 후 승인된 배포 호스트에서 설치 절차를 수행한다. 설치 후 도메인 변경은 별도 점검된 유지보수 절차가 필요하다.

#### 조건부 배포 실행 순서 템플릿 (실행·검증되지 않음)

아래 명령은 환경 담당자가 승인한 호스트와 비밀 파일을 준비한 뒤 참고할 구성 템플릿이다. 이 저장소의 Compose는 컨테이너 포트 80의 HTTP만 제공하며 DNS, TLS 종료 프록시, 방화벽, 발신 메일 또는 롤백을 설정하지 않는다. `docker compose config --quiet`는 구성이 해석되는지만 확인하며 안전한 운영 구성이나 실제 배포를 증명하지 않는다.

1. 승인된 불변 코드 SHA를 체크아웃하고 `git submodule update --init --recursive`로 pinned Hummingbird submodule을 준비한다. `git ls-tree HEAD themes/hummingbird`의 gitlink SHA와 `git -C themes/hummingbird rev-parse HEAD`가 일치하는지 확인한다. `.gitmodules`에는 경로와 URL만 기록된다. 운영 릴리스 SHA와 업데이트·롤백 순서는 아직 승인·검증되지 않았다.
2. 최초 설치 전에 최종 도메인, proxy 경로, 공개할 host bind/port, 영속 백업 정책을 결정한다. 기존 설치가 있으면 실제 Compose project name을 먼저 확인하고 이후 모든 명령에서 같은 값을 사용한다. 이름을 바꾸면 다른 named volume을 연결할 수 있다. 이 환경 문서는 기존 운영 volume이 있다고 가정하지 않는다.
3. `.env.example`을 복사하지 말고 운영 비밀 저장소에서 전용 env 파일을 준비한다. 아래 placeholder를 실제 비밀값이 아닌 기존/승인된 project 이름과 비밀 파일 경로로 교체한 뒤에만 명령을 사용한다. 특히 project 이름은 named volume을 결정하므로 추정하지 않는다.

   ```sh
   PRODUCTION_PROJECT='<existing-approved-project-name>'
   PRODUCTION_ENV_FILE='<private-env-file-path>'
   docker compose -p "$PRODUCTION_PROJECT" --env-file "$PRODUCTION_ENV_FILE" config --quiet
   ```

4. 현재 Compose 예시는 `kuranea/prestashop:9.2.0`을 로컬에서 빌드하며, 불변 digest로 registry에 승격하거나 이전 release로 되돌리는 절차를 제공하지 않는다. 이 파일에는 운영 서비스를 시작하는 명령이 없으며, `build`/`up`을 운영 배포로 실행하지 않는다. 승인된 immutable app/DB image reference와 digest, staging에서 검증한 promotion/rollback 절차가 준비되기 전에는 여기서 중단한다.
5. 승인된 배포 정의가 별도로 준비된 뒤에만 그 정의의 project/env/image 인자를 사용한다. Compose health 상태와 별도로 승인된 HTTPS public host와 인증서, 관리자 접근 제한, 실제 메일 전달, 백업 복원 증거를 확인한다. 현재 별도의 운영 인수 점검표나 승인된 운영 배포 정의는 없다. 배포 로그·명령 출력에 비밀값이나 고객 데이터를 남기지 않는다.

이 템플릿은 개발·격리 QA 설정에서 파생한 사전 준비 자료다. 현재 구성은 검증된 production release/upgrade/rollback 절차가 아니며, 운영 호스트, proxy/TLS, 비밀값, 메일, durable backup, 보존기간, RPO/RTO와 restore owner가 정해져야 실제 runbook을 완성할 수 있다. 로컬 테스트의 named volume 또는 데이터베이스를 운영 데이터로 승격하거나, volume 이름을 바꿔 초기 설치를 시작하지 않는다.

#### 조건부 운영 runbook

이 순서는 배포 승인이 아니라, 필요한 운영 값과 담당자가 정해진 뒤 환경 담당자가 구체화할 절차다. 아래 필수 입력 중 하나라도 비어 있으면 해당 단계에서 멈춘다. 임시 주소, 임의 seller/tax 값, placeholder 비밀값으로 실제 서비스를 시작하지 않는다.

##### 배포 전 필수 입력과 중단 조건

| 준비 항목 | 배포 전에 남길 증거 | 중단 조건 |
| --- | --- | --- |
| 호스트·격리 경계 | 운영 host/project 식별자, 승인된 Docker Engine/Compose 버전, CPU/RAM/저장공간/파일시스템 기준, 방화벽·접근 책임자 | host, 버전, 용량 또는 네트워크 소유자가 미정이면 시작하지 않는다. |
| 영속 데이터 식별 | 기존 Compose project 이름, 실제 named volume 이름·용도, DB/webroot/catalog queue 위치와 소유자 | 기존 project/volume을 정확히 확인할 수 없으면 `-p` 이름을 추정하거나 새 project로 붙지 않는다. `down -v`, prune, volume 재생성으로 복구하지 않는다. |
| 릴리스 artifact | 승인된 Git SHA, pinned Hummingbird gitlink 일치, PrestaShop/MariaDB를 포함한 모든 이미지의 immutable registry reference와 digest, 승격·승인 담당자 | 로컬에서 매번 다시 빌드되는 mutable tag만 있거나 digest/SHA를 기록할 수 없으면 운영 배포를 중단한다. 현재 Compose는 registry 승격/rollback 체계를 제공하지 않는다. |
| 운영 주소·보안 | 최종 domain/DNS 소유자, proxy 경로, TLS 인증서/신뢰 체인, 방화벽 규칙, secret manager의 DB/Admin/SMTP 값과 교체 책임자 | 실제 domain, 인증서 또는 비밀 전달 경로가 없으면 공개 bind를 열지 않는다. 비밀값을 `.env.example`, Git, 명령 기록이나 Actions log에 쓰지 않는다. |
| 상점 운영정보 | 승인된 실제 seller identity, 사업자 참고정보와 seller legal information의 구분, 고객센터, 상품/SKU·이미지 권리, 상품별 세금, 배송 범위·무료배송 정책, 환불/약관/개인정보 값 | 항목별 승인 자료가 없으면 상점 게시, 세금·배송 판단, 판매 가능한 상태로의 전환을 멈춘다. 값을 추정해 채우지 않는다. |
| 메일·결제 경계 | 발신 domain 및 authorized SMTP/mail service owner, reset/주문 메일 수신 검증, 결제 provider 계약·실거래 승인자, checkout gate의 관리 책임자 | 운영 메일 권한/전달 검증 전 reset·주문 메일을 인수 처리하지 않는다. 실결제는 별도 명시 승인이 없으면 계속 비활성으로 둔다. |
| 백업·롤백 | 암호화 저장소와 접근자, 보존기간, 실제 승인 RPO/RTO, restore 승인자, 복구 target, schema migration과 이전 릴리스의 호환성 판정 | 저장소, 보존정책, 승인된 RPO/RTO 또는 복구 책임자가 없으면 쓰기 트래픽을 받지 않는다. RPO/RTO는 판매자/운영자가 정하며 이 문서에서 기본값을 정하지 않는다. |

##### 배포 순서

1. **Release 고정:** 승인자가 Git SHA, Hummingbird gitlink, app image digest, DB image digest, migration 집합을 함께 기록한다. staging과 production에서 같은 digest를 승격한다. staging/production이 다른 이미지를 다시 빌드하지 않는다.
2. **격리 staging 배포:** 운영과 다른 project/DB/volume을 쓰고 운영 고객·계정·주문 데이터를 복사하지 않는다. secret은 승인된 비밀 저장소에서 주입한다. 현재 `compose.yaml`은 local build 및 mutable image 예시이므로, immutable reference를 주입할 승인된 배포 정의가 준비되기 전에는 production 명령으로 사용하지 않는다.
3. **정적 구성 확인:** staging에서 승인된 project/env 경로로 Compose 구성이 해석되는지 확인한다. `docker compose config --quiet`는 문법 확인만 하며, project/volume 식별, 외부 공개 방화벽, TLS, mail, rollback이나 데이터 안전을 증명하지 않는다.
4. **Staging 인수:** 공개 HTTPS 경로, 관리자 접근, ja/en/ko의 주요 고객 화면, 상품·세금·무료배송 주문 금액, 고객 reset/주문 메일, 비밀 없는 로그 수집을 확인한다. 실제 결제를 호출하지 않는 주문 경로만 사용한다. 이전 release 복귀와 호환되지 않는 migration이 있으면 production 승인을 요청하지 않는다.
5. **동일 artifact 운영 배포:** 승인된 변경 시간과 담당자가 확보되고 모든 prerequisite 증거가 있을 때만 staging에서 확인한 immutable digest를 사용한다. project 이름과 volume mapping을 staging과 혼동하지 않는다. 사전 DB/webroot/queue snapshot과 복구 확인 결과를 기록하고, 승인된 maintenance/traffic gate를 사용한다.
6. **Post-deploy acceptance:** health 상태 이외에 실제 public HTTPS host, 인증서, redirect/canonical host, 관리자 접근 제한, reset/주문 mail 수신, shop 기본 화면과 비밀 없는 운영 로그를 확인한다. 승인된 seller/product/tax/shipping/policy가 고객 화면에 보이는지 read-only로 대조한다. 이 확인 중 하나라도 실패하면 traffic gate를 열거나 checkout을 활성화하지 않는다.

##### 롤백 순서

1. 담당자가 traffic/checkout gate를 닫고 실패 시각, release SHA/digest, migration 단계 및 비밀을 제외한 오류 증거를 보존한다. 실패한 데이터 volume을 삭제하거나 덮어쓰지 않는다.
2. 승인된 호환성표가 application-only rollback을 허용할 때만 이전 digest로 되돌린다. DB schema 또는 webroot state가 이전 release와 호환되지 않으면 app image만 되돌리지 않는다.
3. 상태 복구가 필요하면 아래 백업 절차를 사용해 **별도 격리 target**에 DB, webroot, queue를 같은 snapshot set으로 복원한다. 서비스와 데이터 검증, 재시작 및 담당자 승인 전까지 기존 production state를 교체하지 않는다.
4. HTTPS/mail/customer smoke와 주요 주문·주소 readback을 완료하고 지정된 release/restore 책임자가 승인한 뒤에만 traffic을 되돌린다. 검증이 실패하거나 입력/권한이 없으면 중단하고 해당 담당자에게 이관한다.

이 저장소에는 승인된 immutable production image, 실제 운영 환경값, migration rollback contract, provider별 deploy 명령이 없다. 따라서 위 절차는 host-agnostic checklist이며 현재 구현으로 수행 가능한 운영 배포/rollback 절차라고 주장하지 않는다.

#### 백업과 복원

`tests/smoke/backup_restore_drill.sh`는 GitHub Actions의 해당 실행 전용 `kuranea-ci-<run id>-<attempt>` 프로젝트만 복제해 DB·PrestaShop 파일·카탈로그 검토 queue를 별도 임시 프로젝트에 복원한다. 스냅샷에는 CI 계정 설정과 합성 고객 데이터가 포함될 수 있으므로 `$RUNNER_TEMP` 밖으로 내보내거나 Artifact에 올리지 않는다. 이 검사는 운영 백업이나 운영 복원이 아니다.

운영용 backup/restore는 아래 자료가 승인되고 staging drill로 확인된 뒤에만 실행한다.

1. **일관된 snapshot set 생성:** 주문/설정 쓰기를 멈추거나 승인된 maintenance gate를 사용해 같은 consistency point에서 database dump, PrestaShop `prestashop_html` webroot, `/var/lib/kuranea/catalog-review` queue를 기록한다. 각 component에 release SHA/image digest, schema/migration version, capture time을 연결한다. DB만 복원하거나 서로 다른 시점의 webroot/queue를 섞지 않는다.
2. **보호 및 catalog:** snapshot을 승인된 durable storage에 암호화해 저장하고 접근을 복구 담당자로 제한한다. 무결성 checksum/manifest를 기록하되 고객/계정 데이터, 비밀값 또는 raw dump를 CI artifact와 일반 로그에 남기지 않는다. 보존기간, 삭제 승인, RPO/RTO는 별도 승인값을 사용한다.
3. **격리 복원:** production과 이름·volume이 분리된 restore project/host에 같은 snapshot set을 복구한다. 원본 운영 volume에 쓰지 않는다. 실제 volume mapping과 ownership을 확인하고 DB, webroot, queue를 복원한 뒤만 서비스를 시작한다.
4. **복구 검증:** DB schema 및 핵심 shop/config/order counts, 무결성 manifest와 file metadata/content, queue schema 및 fixture references를 비교한다. 승인된 shop domain의 local/isolated URL에서 storefront와 관리자 로그인 페이지를 확인하고, 권한이 있는 관리자 세션에서 sample order/address projection을 read-only로 대조한다. 외부 발신 mail이나 결제 provider를 호출하지 않는다.
5. **재시작·인수:** 복구 target을 재시작하고 같은 핵심 read-only 검사를 반복한다. snapshot set, release/migration pairing, restore operator, 검증 결과, 예외와 삭제/보존 기한을 기록한 뒤 restore 승인자가 수락/거부한다.

검증 중 file/DB/queue mismatch가 하나라도 남거나 snapshot set/release/schema pairing을 확인할 수 없으면 복구본을 production으로 승격하지 않는다. 최신 CI run [#40281533046](https://github.com/goldeget/japan-premium-commerce/actions/runs/40281533046)의 Step 80은 격리 DB·PrestaShop 파일·catalog queue restore/restart를 통과했고, run aggregate도 SUCCESS로 종료됐다. 이는 synthetic single-run data와 disposable volumes만 검증하며, 운영 암호화 저장소·보존 정책·실제 restore owner를 검증하지 않았다.

운영 복구 runbook을 확정하려면 백업 저장 위치와 접근권한, 보존기간, 암호화, RPO/RTO, 백업 담당자, 복원 승인과 격리 복원 대상이 먼저 정해져야 한다. 이 항목들이 없으므로 실제 운영 DB 또는 named volume에 백업·복원을 실행하지 않는다.

#### 배포 전 확인이 필요한 외부 준비

- 외부 값·사용 위치·차단 작업의 유일한 체크리스트는 [RELEASE_REQUIREMENTS_MATRIX.md의 외부 입력 대기 목록](RELEASE_REQUIREMENTS_MATRIX.md#외부-입력-대기-목록)이다. 이 runbook은 해당 승인 값을 받은 뒤 단계와 owner만 기록하며 같은 입력 목록을 복제하지 않는다.
- Production owner는 배포 승인 때 matrix의 각 항목을 승인 자료/secret-store reference와 연결한다. 실제 secret은 이 문서, 채팅, Git, CI artifact에 복사하지 않는다.

위 실제 값과 권한이 확인되고 별도 운영 승인이 있기 전까지 사이트를 공개 배포하거나 실결제를 활성화하지 않는다.
