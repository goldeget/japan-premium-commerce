# KURANEA 작업 기록

## 2026-10-21 — Phase 1A 일본어 홈 UI 및 반응형 QA

- 시작 SHA: 로컬 `work`와 GitHub 원격 `work`가 모두 `34b97b6982e42361018f1746eb0214efe5fe366b`였다. 기존 컨테이너와 named volume은 유지했다.
- 변경: 홈 편집 문구와 하단 모바일 메뉴를 일본어·영어·한국어로 적용하고, Hummingbird 데모 배너를 홈에서 숨겼다. 뉴스레터 입력 대비와 공식 워드마크 크기를 조정했다.
- 검증: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/smoke -v` 12개 통과. 실제 브라우저에서 데스크톱 1440px과 모바일 390px을 열어 HTTP 200, `ja-JP`, 가로 넘침 없음, 브라우저 오류 0건을 확인했다. 현재 캡처는 `artifacts/qa/phase1a/home-desktop-current.png`, `home-mobile-current.png`, `admin-login-current.png`, 결과는 `browser-results-current.json`에 보존했다.
- 제한: 기존 카탈로그에 상품이 없어 유효한 카테고리·상품 상세 경로와 주문 흐름은 검증하지 않았다. 관리자 로그인은 접근 가능하지만 한국어/공식 관리자 로고 적용 전 상태로 촬영했다. 이번 UI 소스는 로컬 검토용으로 기존 webroot에 복사했으며, Compose 이미지는 빌드·배포하지 않았다.

## 2026-10-21 — 빈 설치 캐시 권한 P0 수정

- 시작 상태: `work`의 로컬 및 GitHub 원격 SHA가 `6ddf52b0b3dc63a873bb39019fd93060a9d4b645`로 일치했고, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다.
- 원인 근거: 공식 컨테이너의 `/tmp/docker_run.sh`는 `/tmp/data-ps/prestashop`에서 webroot로 파일을 복사한 뒤 `/tmp/pre-install-scripts/`를 실행하고, 설치 CLI를 `www-data` 사용자로 시작한다. 설치 전후 캐시 소유권을 보정하는 프로젝트 hook은 없었다.
- 변경: `var/cache/prod`만 대상으로 하는 pre-install hook을 추가해 설치 CLI보다 먼저 `www-data:www-data` 소유권을 설정한다. 전체 권한을 열거나 기존 DB·named volume을 초기화하지 않는다.
- 검증: 스모크·테마 계약 테스트 11개 PASS, pre-install 셸 구문 검사 PASS, `docker compose config --quiet` PASS, `git diff --check` PASS.
- 제한: 이번 실행환경의 빈 named volume 신규 설치는 아직 재검증하지 않았다. 실제 PASS는 격리된 GitHub Actions runner의 성공 결과를 확인한 뒤 기록한다.

### P0 원인 범위 축소 — CI assertion 추가

- 소스 검토로 확인: KURANEA entrypoint가 CA 파일을 위해 `var/cache/prod`를 root로 먼저 만들고, 공식 PrestaShop 파일 복사 원본에는 이 하위 디렉터리가 없다. 따라서 installer가 `www-data`로 실행될 때 디렉터리 쓰기 권한이 없을 수 있다. 실패한 Actions 상세 로그는 현재 GitHub API에서 403으로 접근되지 않아 이 원인은 소스 기반 진단이다.
- 후속 수정: pre-install hook은 `var/cache/prod` 디렉터리의 소유자만 `www-data`로 설정한다. CI 설치 스크립트에는 디렉터리와 `class_index.php` 소유자, `www-data` 쓰기 가능 여부 검사를 추가했다.
- 신규 빈 볼륨 결과는 GitHub Actions 완료 후 별도로 기록한다.

## 2026-10-21 — PWA manifest 경로 및 storefront smoke 보강

- 변경: PrestaShop의 제한된 테마 디렉터리 접근 정책을 피하도록 manifest를 webroot `/manifest.webmanifest`에서 제공하고, HTML의 manifest 링크를 그 경로로 갱신했다. smoke 테스트는 manifest의 `ja-JP`와 아이콘 크기를 확인한다.
- 검증: 기존 실행 사이트에서 manifest HTTP 200 및 JSON을 확인했다. 10개 뷰포트에서 일본어 문서 언어, HTTP 200, 가로 넘침 없음, 브라우저 페이지 오류 0건을 기록했다. service worker 범위는 루트이고 Cache API 목록은 비어 있으며, 네트워크 실패 시 503 오프라인 안내를 확인했다.
- 범위 제한: 카테고리 캡처 URL은 현재 홈페이지로 리다이렉트되어 카테고리 화면 검증으로 인정하지 않는다. 현재 카탈로그가 비어 있어 상품 상세·주문과 실제 기기 설치도 검증하지 않았다.
