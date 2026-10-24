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
