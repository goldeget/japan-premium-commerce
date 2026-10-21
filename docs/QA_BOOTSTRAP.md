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

각 기능 커밋은 `work`로 개별 푸시하고 `git ls-remote`와 별도 복제본에서 파일을 확인한다. 마지막 QA/문서 커밋의 SHA 및 새 복제본 검증 결과는 작업 완료 후 이 문서와 `docs/CLOUD_RECOVERY.md`에 기록한다.
