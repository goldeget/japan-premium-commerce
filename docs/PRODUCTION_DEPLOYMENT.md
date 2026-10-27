# ORDENOWA 운영 배포 준비 안내

## 현재 경계

현재 Compose는 로컬 개발과 격리 QA용이다. 기본 웹 포트는 loopback 주소에만 바인딩되고, 기본 `PS_DOMAIN`은 `localhost:<SHOP_PORT>`다. 이 저장소에서 실제 운영 서버, 공개 DNS, TLS 종료 프록시, 운영 메일 발신 또는 배포 롤백을 검증하지 않았다. 이 안내는 운영 배포 승인이 아니며 운영 배포를 실행하지 않는다.

## 최초 설치 시 필요한 값

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

## 조건부 배포 실행 순서 템플릿 (실행·검증되지 않음)

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

## 조건부 운영 runbook

이 순서는 배포 승인이 아니라, 필요한 운영 값과 담당자가 정해진 뒤 환경 담당자가 구체화할 절차다. 아래 필수 입력 중 하나라도 비어 있으면 해당 단계에서 멈춘다. 임시 주소, 임의 seller/tax 값, placeholder 비밀값으로 실제 서비스를 시작하지 않는다.

### 배포 전 필수 입력과 중단 조건

| 준비 항목 | 배포 전에 남길 증거 | 중단 조건 |
| --- | --- | --- |
| 호스트·격리 경계 | 운영 host/project 식별자, 승인된 Docker Engine/Compose 버전, CPU/RAM/저장공간/파일시스템 기준, 방화벽·접근 책임자 | host, 버전, 용량 또는 네트워크 소유자가 미정이면 시작하지 않는다. |
| 영속 데이터 식별 | 기존 Compose project 이름, 실제 named volume 이름·용도, DB/webroot/catalog queue 위치와 소유자 | 기존 project/volume을 정확히 확인할 수 없으면 `-p` 이름을 추정하거나 새 project로 붙지 않는다. `down -v`, prune, volume 재생성으로 복구하지 않는다. |
| 릴리스 artifact | 승인된 Git SHA, pinned Hummingbird gitlink 일치, PrestaShop/MariaDB를 포함한 모든 이미지의 immutable registry reference와 digest, 승격·승인 담당자 | 로컬에서 매번 다시 빌드되는 mutable tag만 있거나 digest/SHA를 기록할 수 없으면 운영 배포를 중단한다. 현재 Compose는 registry 승격/rollback 체계를 제공하지 않는다. |
| 운영 주소·보안 | 최종 domain/DNS 소유자, proxy 경로, TLS 인증서/신뢰 체인, 방화벽 규칙, secret manager의 DB/Admin/SMTP 값과 교체 책임자 | 실제 domain, 인증서 또는 비밀 전달 경로가 없으면 공개 bind를 열지 않는다. 비밀값을 `.env.example`, Git, 명령 기록이나 Actions log에 쓰지 않는다. |
| 상점 운영정보 | 승인된 실제 seller identity, 사업자 참고정보와 seller legal information의 구분, 고객센터, 상품/SKU·이미지 권리, 상품별 세금, 배송 범위·무료배송 정책, 환불/약관/개인정보 값 | 항목별 승인 자료가 없으면 상점 게시, 세금·배송 판단, 판매 가능한 상태로의 전환을 멈춘다. 값을 추정해 채우지 않는다. |
| 메일·결제 경계 | 발신 domain 및 authorized SMTP/mail service owner, reset/주문 메일 수신 검증, 결제 provider 계약·실거래 승인자, checkout gate의 관리 책임자 | 운영 메일 권한/전달 검증 전 reset·주문 메일을 인수 처리하지 않는다. 실결제는 별도 명시 승인이 없으면 계속 비활성으로 둔다. |
| 백업·롤백 | 암호화 저장소와 접근자, 보존기간, 실제 승인 RPO/RTO, restore 승인자, 복구 target, schema migration과 이전 릴리스의 호환성 판정 | 저장소, 보존정책, 승인된 RPO/RTO 또는 복구 책임자가 없으면 쓰기 트래픽을 받지 않는다. RPO/RTO는 판매자/운영자가 정하며 이 문서에서 기본값을 정하지 않는다. |

### 배포 순서

1. **Release 고정:** 승인자가 Git SHA, Hummingbird gitlink, app image digest, DB image digest, migration 집합을 함께 기록한다. staging과 production에서 같은 digest를 승격한다. staging/production이 다른 이미지를 다시 빌드하지 않는다.
2. **격리 staging 배포:** 운영과 다른 project/DB/volume을 쓰고 운영 고객·계정·주문 데이터를 복사하지 않는다. secret은 승인된 비밀 저장소에서 주입한다. 현재 `compose.yaml`은 local build 및 mutable image 예시이므로, immutable reference를 주입할 승인된 배포 정의가 준비되기 전에는 production 명령으로 사용하지 않는다.
3. **정적 구성 확인:** staging에서 승인된 project/env 경로로 Compose 구성이 해석되는지 확인한다. `docker compose config --quiet`는 문법 확인만 하며, project/volume 식별, 외부 공개 방화벽, TLS, mail, rollback이나 데이터 안전을 증명하지 않는다.
4. **Staging 인수:** 공개 HTTPS 경로, 관리자 접근, ja/en/ko의 주요 고객 화면, 상품·세금·무료배송 주문 금액, 고객 reset/주문 메일, 비밀 없는 로그 수집을 확인한다. 실제 결제를 호출하지 않는 주문 경로만 사용한다. 이전 release 복귀와 호환되지 않는 migration이 있으면 production 승인을 요청하지 않는다.
5. **동일 artifact 운영 배포:** 승인된 변경 시간과 담당자가 확보되고 모든 prerequisite 증거가 있을 때만 staging에서 확인한 immutable digest를 사용한다. project 이름과 volume mapping을 staging과 혼동하지 않는다. 사전 DB/webroot/queue snapshot과 복구 확인 결과를 기록하고, 승인된 maintenance/traffic gate를 사용한다.
6. **Post-deploy acceptance:** health 상태 이외에 실제 public HTTPS host, 인증서, redirect/canonical host, 관리자 접근 제한, reset/주문 mail 수신, shop 기본 화면과 비밀 없는 운영 로그를 확인한다. 승인된 seller/product/tax/shipping/policy가 고객 화면에 보이는지 read-only로 대조한다. 이 확인 중 하나라도 실패하면 traffic gate를 열거나 checkout을 활성화하지 않는다.

### 롤백 순서

1. 담당자가 traffic/checkout gate를 닫고 실패 시각, release SHA/digest, migration 단계 및 비밀을 제외한 오류 증거를 보존한다. 실패한 데이터 volume을 삭제하거나 덮어쓰지 않는다.
2. 승인된 호환성표가 application-only rollback을 허용할 때만 이전 digest로 되돌린다. DB schema 또는 webroot state가 이전 release와 호환되지 않으면 app image만 되돌리지 않는다.
3. 상태 복구가 필요하면 아래 백업 절차를 사용해 **별도 격리 target**에 DB, webroot, queue를 같은 snapshot set으로 복원한다. 서비스와 데이터 검증, 재시작 및 담당자 승인 전까지 기존 production state를 교체하지 않는다.
4. HTTPS/mail/customer smoke와 주요 주문·주소 readback을 완료하고 지정된 release/restore 책임자가 승인한 뒤에만 traffic을 되돌린다. 검증이 실패하거나 입력/권한이 없으면 중단하고 해당 담당자에게 이관한다.

이 저장소에는 승인된 immutable production image, 실제 운영 환경값, migration rollback contract, provider별 deploy 명령이 없다. 따라서 위 절차는 host-agnostic checklist이며 현재 구현으로 수행 가능한 운영 배포/rollback 절차라고 주장하지 않는다.

## 백업과 복원

`tests/smoke/backup_restore_drill.sh`는 GitHub Actions의 해당 실행 전용 `kuranea-ci-<run id>-<attempt>` 프로젝트만 복제해 DB·PrestaShop 파일·카탈로그 검토 queue를 별도 임시 프로젝트에 복원한다. 스냅샷에는 CI 계정 설정과 합성 고객 데이터가 포함될 수 있으므로 `$RUNNER_TEMP` 밖으로 내보내거나 Artifact에 올리지 않는다. 이 검사는 운영 백업이나 운영 복원이 아니다.

운영용 backup/restore는 아래 자료가 승인되고 staging drill로 확인된 뒤에만 실행한다.

1. **일관된 snapshot set 생성:** 주문/설정 쓰기를 멈추거나 승인된 maintenance gate를 사용해 같은 consistency point에서 database dump, PrestaShop `prestashop_html` webroot, `/var/lib/kuranea/catalog-review` queue를 기록한다. 각 component에 release SHA/image digest, schema/migration version, capture time을 연결한다. DB만 복원하거나 서로 다른 시점의 webroot/queue를 섞지 않는다.
2. **보호 및 catalog:** snapshot을 승인된 durable storage에 암호화해 저장하고 접근을 복구 담당자로 제한한다. 무결성 checksum/manifest를 기록하되 고객/계정 데이터, 비밀값 또는 raw dump를 CI artifact와 일반 로그에 남기지 않는다. 보존기간, 삭제 승인, RPO/RTO는 별도 승인값을 사용한다.
3. **격리 복원:** production과 이름·volume이 분리된 restore project/host에 같은 snapshot set을 복구한다. 원본 운영 volume에 쓰지 않는다. 실제 volume mapping과 ownership을 확인하고 DB, webroot, queue를 복원한 뒤만 서비스를 시작한다.
4. **복구 검증:** DB schema 및 핵심 shop/config/order counts, 무결성 manifest와 file metadata/content, queue schema 및 fixture references를 비교한다. 승인된 shop domain의 local/isolated URL에서 storefront와 관리자 로그인 페이지를 확인하고, 권한이 있는 관리자 세션에서 sample order/address projection을 read-only로 대조한다. 외부 발신 mail이나 결제 provider를 호출하지 않는다.
5. **재시작·인수:** 복구 target을 재시작하고 같은 핵심 read-only 검사를 반복한다. snapshot set, release/migration pairing, restore operator, 검증 결과, 예외와 삭제/보존 기한을 기록한 뒤 restore 승인자가 수락/거부한다.

검증 중 file/DB/queue mismatch가 하나라도 남거나 snapshot set/release/schema pairing을 확인할 수 없으면 복구본을 production으로 승격하지 않는다. 최신 CI run [#40281533046](https://github.com/goldeget/japan-premium-commerce/actions/runs/40281533046)의 Step 80은 격리 DB·PrestaShop 파일·catalog queue restore/restart를 통과했고, run aggregate도 SUCCESS로 종료됐다. 이는 synthetic single-run data와 disposable volumes만 검증하며, 운영 암호화 저장소·보존 정책·실제 restore owner를 검증하지 않았다.

운영 복구 runbook을 확정하려면 백업 저장 위치와 접근권한, 보존기간, 암호화, RPO/RTO, 백업 담당자, 복원 승인과 격리 복원 대상이 먼저 정해져야 한다. 이 항목들이 없으므로 실제 운영 DB 또는 named volume에 백업·복원을 실행하지 않는다.

## 배포 전 확인이 필요한 외부 준비

- 외부 값·사용 위치·차단 작업의 유일한 체크리스트는 [RELEASE_REQUIREMENTS_MATRIX.md의 외부 입력 대기 목록](RELEASE_REQUIREMENTS_MATRIX.md#외부-입력-대기-목록)이다. 이 runbook은 해당 승인 값을 받은 뒤 단계와 owner만 기록하며 같은 입력 목록을 복제하지 않는다.
- Production owner는 배포 승인 때 matrix의 각 항목을 승인 자료/secret-store reference와 연결한다. 실제 secret은 이 문서, 채팅, Git, CI artifact에 복사하지 않는다.

위 실제 값과 권한이 확인되고 별도 운영 승인이 있기 전까지 사이트를 공개 배포하거나 실결제를 활성화하지 않는다.
