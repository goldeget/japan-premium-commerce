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

1. 승인된 불변 코드 SHA를 체크아웃하고 `git submodule update --init --recursive`로 pinned Hummingbird submodule을 준비한 뒤 `.gitmodules`의 고정 SHA와 일치하는지 확인한다. 운영 릴리스 SHA와 업데이트·롤백 순서는 아직 승인·검증되지 않았다.
2. 최초 설치 전에 최종 도메인, proxy 경로, 공개할 host bind/port, 영속 백업 정책을 결정한다. 기존 설치가 있으면 실제 Compose project name을 먼저 확인하고 이후 모든 명령에서 같은 값을 사용한다. 이름을 바꾸면 다른 named volume을 연결할 수 있다. 이 환경 문서는 기존 운영 volume이 있다고 가정하지 않는다.
3. `.env.example`을 복사하지 말고 운영 비밀 저장소에서 전용 env 파일을 준비한다. 아래 placeholder를 실제 비밀값이 아닌 기존/승인된 project 이름과 비밀 파일 경로로 교체한 뒤에만 명령을 사용한다. 특히 project 이름은 named volume을 결정하므로 추정하지 않는다.

   ```sh
   PRODUCTION_PROJECT='<existing-approved-project-name>'
   PRODUCTION_ENV_FILE='<private-env-file-path>'
   docker compose -p "$PRODUCTION_PROJECT" --env-file "$PRODUCTION_ENV_FILE" config --quiet
   ```

4. 환경·백업·롤백 승인 후에만 같은 project/env 인자로 database image를 pull하고 PrestaShop image를 빌드한 다음 서비스를 시작한다. 다음 명령은 앞 단계와 같은 shell session에서 실행하거나 각 명령 전에 두 변수를 다시 지정한다.

   ```sh
   docker compose -p "$PRODUCTION_PROJECT" --env-file "$PRODUCTION_ENV_FILE" pull mariadb
   docker compose -p "$PRODUCTION_PROJECT" --env-file "$PRODUCTION_ENV_FILE" build prestashop
   docker compose -p "$PRODUCTION_PROJECT" --env-file "$PRODUCTION_ENV_FILE" up -d --wait
   docker compose -p "$PRODUCTION_PROJECT" --env-file "$PRODUCTION_ENV_FILE" ps
   ```

5. `ps`의 Compose health 상태, 승인된 HTTPS public URL과 인증서, 관리자 접근 권한, 메일 전달 및 백업 복원 증거를 별도 운영 점검표로 확인한다. Compose health check는 내부 HTTP 요청이며 HTTPS나 실제 고객 경로를 확인하지 않는다. 배포 로그·명령 출력에 비밀값이나 고객 데이터를 남기지 않는다.

이 템플릿은 개발·격리 QA 설정에서 파생한 사전 준비 자료다. 현재 구성은 검증된 production release/upgrade/rollback 절차가 아니며, 운영 호스트, proxy/TLS, 비밀값, 메일, durable backup, 보존기간, RPO/RTO와 restore owner가 정해져야 실제 runbook을 완성할 수 있다. 로컬 테스트의 named volume 또는 데이터베이스를 운영 데이터로 승격하거나, volume 이름을 바꿔 초기 설치를 시작하지 않는다.

## 백업과 복원

`tests/smoke/backup_restore_drill.sh`는 GitHub Actions의 해당 실행 전용 `kuranea-ci-<run id>-<attempt>` 프로젝트만 복제해 DB·PrestaShop 파일·카탈로그 검토 queue를 별도 임시 프로젝트에 복원한다. 스냅샷에는 CI 계정 설정과 합성 고객 데이터가 포함될 수 있으므로 `$RUNNER_TEMP` 밖으로 내보내거나 Artifact에 올리지 않는다. 이 검사는 운영 백업이나 운영 복원이 아니다.

운영 복구 runbook을 확정하려면 백업 저장 위치와 접근권한, 보존기간, 암호화, RPO/RTO, 백업 담당자, 복원 승인과 격리 복원 대상이 먼저 정해져야 한다. 이 항목들이 없으므로 실제 운영 DB 또는 named volume에 백업·복원을 실행하지 않는다.

## 배포 전 확인이 필요한 외부 준비

- 운영 호스트와 리버스 프록시/HTTPS 인증서 및 DNS 소유권
- 운영 발신 도메인, SMTP 또는 메일 제공자 설정과 전달성 확인
- 실제 판매자 법적 정보와 고객센터·배송·환불 정책
- 실제 SKU, 이미지 사용권, 재고와 상품별 세무 판단
- 판매자 승인, 결제 제공자 계약, 실거래 활성화 승인
- 백업 저장 위치와 보존·복원 책임자 및 RPO/RTO
- 실제 iOS·Android 기기에서 PWA 설치·업데이트·실행 확인

위 값이 확인되고 별도 운영 승인 전까지 사이트를 공개 배포하거나 실결제를 활성화하지 않는다.
