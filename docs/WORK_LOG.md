# KURANEA 작업 기록

## 2026-10-21 — 빈 설치 캐시 권한 P0 수정

- 시작 상태: `work`의 로컬 및 GitHub 원격 SHA가 `6ddf52b0b3dc63a873bb39019fd93060a9d4b645`로 일치했고, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다.
- 원인 근거: 공식 컨테이너의 `/tmp/docker_run.sh`는 `/tmp/data-ps/prestashop`에서 webroot로 파일을 복사한 뒤 `/tmp/pre-install-scripts/`를 실행하고, 설치 CLI를 `www-data` 사용자로 시작한다. 설치 전후 캐시 소유권을 보정하는 프로젝트 hook은 없었다.
- 변경: `var/cache/prod`만 대상으로 하는 pre-install hook을 추가해 설치 CLI보다 먼저 `www-data:www-data` 소유권을 설정한다. 전체 권한을 열거나 기존 DB·named volume을 초기화하지 않는다.
- 검증: 스모크·테마 계약 테스트 11개 PASS, pre-install 셸 구문 검사 PASS, `docker compose config --quiet` PASS, `git diff --check` PASS.
- 제한: 이번 실행환경의 빈 named volume 신규 설치는 아직 재검증하지 않았다. 실제 PASS는 격리된 GitHub Actions runner의 성공 결과를 확인한 뒤 기록한다.

## 2026-10-21 — PWA manifest 경로 및 storefront smoke 보강

- 변경: PrestaShop의 제한된 테마 디렉터리 접근 정책을 피하도록 manifest를 webroot `/manifest.webmanifest`에서 제공하고, HTML의 manifest 링크를 그 경로로 갱신했다. smoke 테스트는 manifest의 `ja-JP`와 아이콘 크기를 확인한다.
- 검증: 기존 실행 사이트에서 manifest HTTP 200 및 JSON을 확인했다. 10개 뷰포트에서 일본어 문서 언어, HTTP 200, 가로 넘침 없음, 브라우저 페이지 오류 0건을 기록했다. service worker 범위는 루트이고 Cache API 목록은 비어 있으며, 네트워크 실패 시 503 오프라인 안내를 확인했다.
- 범위 제한: 카테고리 캡처 URL은 현재 홈페이지로 리다이렉트되어 카테고리 화면 검증으로 인정하지 않는다. 현재 카탈로그가 비어 있어 상품 상세·주문과 실제 기기 설치도 검증하지 않았다.
