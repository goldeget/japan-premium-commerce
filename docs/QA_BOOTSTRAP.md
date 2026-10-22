# KURANEA bootstrap QA 기록

실행일: 2026-10-21 UTC
대상 브랜치: `work`
대상 구성: PrestaShop 9.2.0, MariaDB 10.11.19, Hummingbird v2.1.2 (`4e52b64d3c772f19d9974409b73d55fb532e9e22`)

## 실행 결과

| 확인 항목 | 결과 | 근거 |
|---|---|---|
| Compose 이미지 빌드 및 시작 | PASS | `docker compose build`, `docker compose up -d --wait`; MariaDB와 PrestaShop 모두 healthy |
| 호스트 포트 바인딩 | PASS | PrestaShop은 `127.0.0.1:8080`에만 바인딩 |
| DB 연결 및 설치 상태 | PASS | PrestaShop DB 버전 `9.2.0`, `SELECT 1` 정상, 기존 DB의 테이블 282개 확인 |
| 고객 언어 | PASS | `ja` 기본 언어, `en`/`ko` 활성 언어, HTML `lang=ja-JP` |
| KURANEA 자식 테마 | PASS | 활성 테마 `kuranea`, 부모 `hummingbird`; 테마 manifest·preview·CSS 저장소/컨테이너 해시 일치 |
| CSS 적용 | PASS | 테마 CSS HTTP 200; 페이지에서 KURANEA 색상 토큰, 반응형 컨테이너 및 `:focus-visible` 규칙 확인 |
| 쇼핑몰/관리자 HTTP | PASS | 쇼핑몰 `/` 및 `/admin-kuranea/` 로그인 페이지 HTTP 200 |
| 재시작 후 데이터 유지 | PASS | 두 기존 컨테이너를 재시작한 뒤 healthcheck, 언어/테마 설정, 282개 테이블 유지 확인 |
| PC/모바일 기본 렌더링 | PASS | 1440×1000 및 390×844 뷰포트, 가로 넘침 없음, 브라우저 콘솔/페이지 오류 없음 |
| 독립 격리 빈 DB 자동 설치 | BLOCKED | 디스크 부족으로 MariaDB 시스템 테이블 생성 중 `errno 28`; 이 검증을 통과로 표시하지 않음 |
| 관리자 UI 한국어 100% | NOT VERIFIED | 직원 계정 언어 코드는 한국어로 설정됐으나 로그인 화면은 일본어/영어 문자열을 표시함. 번역 완결성은 후속 작업 |
| 공식 로고 3종과 이미지 파생물 | BLOCKED | 실제 원본 바이너리를 개발환경에서 찾지 못함. 대체 로고를 만들거나 적용하지 않음 |
| PWA 설치 및 iOS/Android 검증 | NOT IMPLEMENTED | 후속 단계 |

현재 데이터베이스는 이미 초기화된 기존 named volume에서 확인했다. 새 빈 볼륨으로 자동 설치하는 검증은 별도 격리 환경에서 두 차례 시도했으나 Docker 저장 공간 부족으로 실패했다. 실패한 격리 테스트 컨테이너와 그 테스트 전용 볼륨만 정리했다. 운영 중인 `kuranea_mariadb_data`와 `kuranea_prestashop_html`에는 삭제, 재생성 또는 초기화를 수행하지 않았다.

## 브라우저 캡처

- [PC 쇼핑몰 1440×1000](../artifacts/qa/store-desktop.png)
- [모바일 쇼핑몰 390×844](../artifacts/qa/store-mobile.png)
- [관리자 로그인 1440×1000](../artifacts/qa/admin-login.png)

관리자 캡처는 접근성 및 로그인 화면 표시 확인용이며, 한국어 번역 완료를 의미하지 않는다. 쇼핑몰은 PrestaShop 기본 샘플 상품과 기본 로고가 아직 표시된다. 공식 자산 파일을 받지 못했으므로 브랜드 적용을 완료했다고 주장하지 않는다.

## 재실행 가능한 HTTP smoke 테스트

현재 구동 중인 Compose 환경에서 저장소 루트에서 실행한다.

```sh
SHOP_BASE_URL=http://127.0.0.1:8080 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/smoke -v
```

검증된 결과: 3 tests, 모두 PASS. 테스트는 일본어 쇼핑몰 HTTP 200, 자식 테마 CSS 규칙 제공, 관리자 로그인 접근을 확인한다. 이는 기존 설치의 smoke 확인이며 새 설치나 100% 관리자 번역의 검증이 아니다.

## 원격 복구 체크포인트

QA/테스트/캡처 커밋 `ecd528ce5e2d2f9e91de89d92d379bcad3bde274`는 `work` 원격 SHA와 일치했다. 새 shallow clone `/tmp/kuran-final-recovery-ecd528c`에서 이 SHA, 스모크 테스트, QA 문서와 세 캡처 파일을 조회했고 복제본은 clean이었다. 자세한 복구 절차는 `docs/CLOUD_RECOVERY.md`에 있다.

## 2026-10-22 — P0 Docker 설치 후처리 중단 원인 및 수정 후보

- run `39728912492`의 사용자가 제공한 실제 로그는 설치 CLI의 `Installation successful`, `/var/www/html/install/` 재삭제 실패, Compose 재시작 뒤 `PrestaShop Core already installed`, 그리고 Apache 요청 중 `/var/www/html/var/cache/prod/appParameters.php`를 열지 못한 fatal을 보여준다.
- 고정 이미지 `prestashop/prestashop:9.2.0@sha256:2b8f90176b3fad68f8f5c7fbdeaa137f2f05578d2ccff92ab581efa6b317c1d8`의 `/tmp/docker_run.sh`(추출 SHA-256 `422f08ac00c69614936f0eb2d9e5ea8316de6dd6e4b2fa5904720b1f901b9f2f`)는 `set -e`를 설정하고 설치 후 이미 제거된 install 경로를 무조건 `rm -r`한다. 같은 스크립트가 `install.lock`도 무조건 삭제한다. 공식 PrestaShop 9.2.0 `Install::finalize()`는 설치 디렉터리를 제거하고 `Install::postInstall()`은 lock을 먼저 제거하므로 Docker의 중복 삭제가 실패할 수 있다.
- 첫 `/install` 재삭제에서 `set -e`가 시작 스크립트를 끝내므로 Docker의 post-install hook과 후속 setup이 실행되지 않는다. `restart: unless-stopped` 재시작은 parameters 파일이 있어 “Core already installed” 분기로 들어가고 first-install 전용 post-install hook을 건너뛴다. 따라서 KURANEA 초기화가 실행되지 않는다. `appParameters.php`는 PrestaShop 설정 bootstrap에서 실제 생성되어야 하며 임의 파일을 만들면 안 된다.
- 수정 후보는 공식 `docker_run.sh`의 두 중복 `rm`만 존재 확인 조건으로 바꾸는 fail-closed patcher다. 고정 upstream 줄과 달라지면 시작을 중단한다. KURANEA bootstrap 및 모듈 설정은 `/tmp/init-scripts/`로 옮겨 첫 설치와 재시작 모두에서 실행하고, marker로 초기화만 멱등화한다. 생성 cache 경로는 기존처럼 `www-data`에 한정해 복구하며 전체 권한을 열지 않는다. PHP 코어와 DB 볼륨은 수정하지 않는다.
- 로컬 회귀 테스트 3/3 및 관리자 설치 순서 테스트 4/4, shell 구문 검사, 고정 upstream script 복사본 patcher 적용·멱등 재실행을 통과했다. 실제 빈 named volume 신규 설치와 HTTP 200, 주문 E2E는 독립 Actions 결과 대기 중이며 PASS가 아니다. 로컬 전체 `tests/smoke`의 카테고리 3건은 기존 개발 서버에서 HTTP 500으로 실패했고(기존 기록과 같은 빈 카테고리 결함), P0 계약 테스트와는 별개다.
- 기존 로컬 named volume과 DB는 손대지 않았다. 현재 수정은 격리 CI 검증 전이다.
