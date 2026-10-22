# KURANEA 작업 기록

## 2026-10-22 — 주소 데이터 안전성·갱신과 환경 상태 점검

- 시작 기준: 로컬 `HEAD`, `origin/work`, GitHub `work` 원격 SHA가 `1690a073bc25f38d3c02cc7616dd7b8f9f5a3cc7`로 일치했다. `main`은 `ee02a3657448d563508687614a246e05ac61eecd`다. 기존 미추적 브라우저 캡처와 테스트 캐시는 변경하거나 삭제하지 않았다.
- 주소 코드 체크포인트: `06617f6`에서 Japan Post의 설명용 `（次のビルを除く）`를 고객 주소에서 제거하고 `以下に掲載がない場合`를 상세 주소 빈값으로 처리했다. `a444238`은 공식 `1000004` 주소 검증이 `大手町`를 정확히 기대하게 했다. `1690a07`은 공식 KEN_ALL ZIP을 검증한 뒤 기존 트랜잭션 importer를 실행하는 수동 갱신 CLI를 추가했다. 세 체크포인트 모두 `work`에 푸시 후 원격 SHA와 파일 재조회를 확인했다.
- 검증: Python smoke/CI 계약 34/34, 관리자 번역 계약 8/8, 주소 갱신 CLI 계약 6/6, workflow 계약 7/7 통과. PHP 도메인/후보 응답 테스트 및 기존 DB read-only 통합 주소 검증, PHP lint, JavaScript·shell 문법, `docker compose config --quiet`도 통과했다. 이 turn에는 주소 데이터를 다시 적재하거나 고객·주소·주문 행을 만들지 않았다.
- CI 상태: run `39703327857`, `39704824787`은 이미지 빌드와 격리 캐시 권한 검사 뒤 `Start the empty-volume shop`에서 실패했다. 공개 실행 목록에서 후속 `39705702536`, `39706052890`, `39706126218`도 Failure로 확인했다. 마지막 run은 `1690a07`에서 2분 39초 후 실패하고 3.37 KB artifact(SHA-256 `5ba78e90152543f775930472455c8434fae47018303373b8a93711506dcb2500`)를 생성했다. GitHub 페이지는 로그 열람에 로그인하라고 표시하며 API `403`, artifact 익명 다운로드 `404`다. 최신 실패 단계와 `errno 28` 여부는 확인할 수 없어 추측하지 않는다.
- 환경: cloud status의 활성/관측 revision은 2다. 저장 draft revision 4는 checkout `2db98927a9ede2b2423456873f0994ddd19ffe4e`를 가리켜 현재 `work`와 일치하지 않는다. 유효 egress 목록에는 `api.github.com`이 없다. 사용자가 언급한 revision 3의 적용 증거는 없으며 설정을 수정·게시하지 않았다.
- 보존: 작업공간 여유는 약 86 MB, inode 사용률 95%다. Compose의 healthy PrestaShop/MariaDB와 모든 기존 named volume을 보존했다. Docker prune·재빌드·DB 초기화는 수행하지 않았다. 사용자가 첨부한 공식 브랜드 ZIP의 세 이미지 SHA-256은 `assets/brand/source/` 원본과 모두 일치했다.
- 다음: 먼저 새 빈 볼륨 CI의 상세 stderr를 접근 가능한 환경에서 확보하고 설치를 통과시킨다. 그 다음 실제 checkout/주문 저장, 상품 파서와 상품 등록, 관리자 한국어 범위, PWA를 독립적으로 검증한다. 실제 상품 URL/fixture가 없고 상품 파서 구현도 아직 없어 외부 사이트 상품을 수집하거나 실제 상품처럼 등록하지 않았다.

## 2026-10-22 — Japan Post 배송지의 격리 주문 저장 QA 추가

- 시작 기준: 원격 `work`와 로컬 `HEAD`가 `9a187efbb465c622b1e13afe18ed3f5d34aaf119`로 일치했고, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. 기존 미추적 파일과 두 활성 named volume을 보존했다.
- 변경: `tests/postcode/verify_native_order_persistence.php`는 `CI=true`, `GITHUB_ACTIONS=true`, 실행 ID·시도·고유 Compose 프로젝트 이름이 맞을 때만 작동한다. 고유 CI DB에서 공식 오프라인 `ps_checkpayment`, CI 전용 무료 배송사와 상품, 일본우편 `1000004` 배송지·수정 건물명, 실제 `PaymentModule::validateOrder()` 주문 저장, `id_address_delivery`, Back Office `GetOrderForViewing` 주소 projection을 확인하도록 추가했다. workflow가 실행 ID 환경을 전달한다.
- 추가 발견: CI 설치 계약 테스트 4개가 기존 합쳐진 step 이름을 찾고 있어 분리된 새 workflow를 대상으로 실패했다. 테스트를 개별 이미지 빌드·캐시 권한 probe·Compose 시작·공통 실패 진단 구조에 맞게 업데이트했다.
- 검증: smoke 및 CI 계약 34/34, 관리자 번역 계약 8/8, 주문 스크립트 PHP lint, postcode 도메인 및 read-only live address 검증, Compose 설정, 실제 storefront HTTP 200을 확인했다. 로컬 DB의 주문 0건·상품 0건을 읽기 전용 조회로 재확인했다. 관리자 주문 목록은 한국어 PC 1440×1000·모바일 390×844에서 HTTP 200, 브라우저 오류 0건이며 캡처를 저장했다. 빈 목록이라 주문별 주소 표시는 확인하지 못했다.
- 빈 설치 CI: run `39703327857`과 주문 스크립트를 포함한 `39704824787` 모두 이미지 빌드·캐시 권한 probe PASS 후 `Start the empty-volume shop`에서 실패했다. 진단 단계/artifact 업로드는 완료됐지만 이 환경의 GitHub API·익명 artifact 접근 제한으로 본문 로그를 읽지 못해 root cause 및 `errno 28` 여부를 확정하지 않았다. 두 run 모두 설치 완료 전 주문 검증은 건너뛰었다.
- 환경·데이터 보존: cloud spec revision은 실제 status에서 2로 확인되어 요청된 3이 미적용이다. 로컬 workspace는 91 MB 여유, inode 95%여서 로컬 이미지 재빌드를 하지 않았다. 기존 `kuranea_mariadb_data`, `kuranea_prestashop_html`, 알 수 없는 미연결 볼륨을 초기화하거나 삭제하지 않았다.
- 원격 checkpoint: `1f5f552316a7e9b860ff551b8998e14313f8bac0`을 `work`에 푸시하고 `git rev-parse`, `git ls-remote`, `git show origin/work:<file>`로 SHA와 주문 테스트·workflow 파일을 재조회했다. `main`은 변경하지 않았다.
- 미완료: 새 빈 설치와 주소 적재, CI 네이티브 주문 및 관리자 주소 projection은 미검증이다. Back Office 전체 한국어 100%, PWA 실제 설치, 실제 checkout 브라우저 주문도 미완료다.

## 2026-10-22 — 빈 카탈로그 메인 화면 보완

- 시작 기준: `work` 로컬·원격 SHA `15a3d82de3df746994eac88c194bdf3caf4e1779`, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`; 기존 미추적 파일과 named volume을 보존했다.
- 원인: Hummingbird `ps_featuredproducts::getWidgetVariables()`는 상품이 없으면 `false`를 반환해 테마 모듈 템플릿을 호출하지 않는다. 실행 중인 PrestaShop은 수정 전 Smarty 컴파일본과 CSS 합본 캐시도 사용하고 있었다.
- 변경: 자식 테마 메인 템플릿에 ja/en/ko 안내와 검색 링크를 넣고, 실제 featured product list가 있을 때만 안내를 숨긴다. 모듈 템플릿은 Hummingbird의 네이티브 상품 카드 출력을 유지한다. CSS는 작은 화면에서 문구와 링크를 세로로 배치한다.
- 검증: 상품 상태 계약 테스트를 먼저 실행해 실패를 확인한 뒤 구현했다. Smarty 홈 컴파일 캐시와 CSS 합본 한 파일만 `/tmp`에 백업 후 무효화해 재생성했다. 실제 페이지 HTTP 200, ja/en/ko 홈 문구, Chromium 데스크톱 1440×1000 및 모바일 390×844, 수평 넘침 0, 브라우저 오류 0을 확인했다. Python smoke/계약 27/27, 관리자 계약 6/6, postcode PHP lint 및 도메인/API 단위 테스트 통과, `docker compose config --quiet`, healthy 컨테이너 및 `git diff --check` 확인.
- 캡처: `artifacts/qa/phase1a/home-empty-state-desktop-v2.png` 및 `home-empty-state-mobile-v2.png`.
- 범위: 실제 상품이 아직 0개이므로 상품 카드의 숨김 조건은 계약 검사로 확인했고, 실상품 카드 UI는 아직 브라우저에서 검증하지 않았다. DB와 기존 주문은 변경하지 않았다.
- GitHub 보존: 기능 커밋 `1af5fda05285b423baad2c7751bb7898c3257caa`를 `work`에 푸시하고 `git ls-remote`·`origin/work`와 비교했다. 별도 shallow clone `/tmp/kuranea-checkpoint-1af5fda`에서 같은 HEAD, 템플릿, 두 캡처 파일의 SHA-256을 재확인했다. `main`은 변경하지 않았다.

## 2026-10-21 — 검색 다국어와 모바일 내비게이션 대비 개선

- 시작 기준: `work` 원격 SHA `d1b2166d6380348e855989b6dbe79650cc9ecedc`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다.
- 원인: Hummingbird의 검색 템플릿은 `Search products...`를 일본어·한국어에도 출력했고, 모바일 하단 메뉴는 `#fffefa` 배경 위에서 푸터 링크 색상 `#e9e5dc`를 상속해 대비가 약 1.25:1이었다.
- 변경: Hummingbird 원본은 유지하고 KURANEA 자식 테마의 `ps_searchbar` 템플릿 오버라이드를 추가해 일본어·영어·한국어 검색창과 검색 관련 접근성 문구를 현지화했다. 모바일 메뉴에 `#footer` 고특이도 선택자를 적용해 브랜드 잉크색으로 표시한다.
- 검증: locale별 검색 문구 smoke를 포함한 smoke 19/19 PASS. 실제 Chromium에서 데스크톱 1440×1000·모바일 390×844를 열어 HTTP 200, 올바른 `ja-JP` 및 검색 문구, 모바일 메뉴색 `rgb(23, 38, 56)`, 가로 넘침 없음, 페이지 오류 0건을 확인했다. 캡처: `artifacts/qa/phase1a/home-desktop-locale-contrast.png`, `home-mobile-locale-contrast.png`.
- 미완료: 푸터의 일부 링크 문구가 영어이며, 기본 통화는 아직 EUR이고 상품 카탈로그는 비어 있다. 해당 사항은 후속 작업으로 남긴다. 기존 상품/주문 데이터와 named volume은 변경하지 않았다.

## 2026-10-21 — 신규 설치 CI의 공식 우편 CSV 경로 복구

- 시작 기준: `work` 로컬·원격 SHA `ec2059c519121e0a73640b75e6f62be95a1f1797`, `main` SHA `ee02a3657448d563508687614a246e05ac61eecd`; 기존 미추적 QA 캡처와 테스트 캐시는 그대로 보존했다.
- 실패 증거: GitHub Actions 실행 #9 `39692749750` 및 #8 `39691897612`는 `Build and install into unique empty volumes` 단계에서 실패했다. 공개 실행 페이지에서는 상세 로그가 차단되어 원래 stderr는 확인되지 않았다.
- 원인 확인: Actions의 기존 Japan Post KEN_ALL 주소는 HTTP 404였다. 공식 다운로드 페이지에서 확인한 `/service/search/zipcode/download/kogaki/zip/ken_all.zip`은 HTTP 200 및 ZIP 응답을 반환했다.
- 변경: 신규 설치 Actions에서 Compose 기동 실패 시 해당 격리 실행의 파일시스템·Docker 사용량, 컨테이너 상태와 제한된 서비스 로그를 즉시 출력하도록 했다. Japan Post 공식 CSV 경로를 수정하고, 두 동작을 고정하는 회귀 계약 테스트를 추가했다.
- 검증: 회귀 계약 2/2, 전체 smoke 16/16 PASS; 공식 URL HEAD 200, Compose YAML parse 및 `docker compose config --quiet` PASS. 격리된 GitHub Actions 신규 설치 결과는 새 실행이 끝나기 전까지 미검증이다.
- 데이터 보존: 로컬 overlay에는 약 197 MB 여유와 95% inode 사용률이 남아 있어 Docker 빌드·prune을 실행하지 않았다. 기존 `kuranea_mariadb_data` 및 `kuranea_prestashop_html` 볼륨과 실행 중인 컨테이너를 유지했고, DB에는 주소 CSV를 가져오지 않았다.

## 2026-10-21 — PrestaShop 9 주소 조회 응답 및 신규 설치 요청 보강

- 시작 기준: `work` 로컬 HEAD 및 원격 SHA `6044653535c7e37d88c2b6c2c23bd22d7eb3f3f0`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다.
- 원인: PrestaShop 9.2에서 이전 응답 API `Tools::jsonEncode()`와 `ajaxDie()`는 사용할 수 없어 postcode 후보 라우트가 503을 반환했다. 테스트 더블도 존재하지 않는 `ajaxDie()`를 제공해 실제 코어 동작을 잘못 모사하고 있었다.
- 변경: 컨트롤러는 표준 `json_encode()`와 PS9 `ajaxRender()`로 상태 코드가 포함된 JSON을 출력하고 종료한다. 주소 테스트는 격리된 PHP 자식 프로세스에서 `ajaxRender()` 응답을 받아 검증한다. 빈 설치 CI의 주소 조회 `curl`에는 canonical-host 리다이렉트 추적을 추가했다.
- 검증: 기존 실행 중인 쇼핑몰에서 주소 lookup 경로 HTTP 200, JSON 응답, `manual_entry_available=true`를 확인했다. 응답 후보는 0개이며 공식 Japan Post CSV가 아직 적재되지 않았으므로 실제 `100-0004` 주소 매핑은 PASS로 기록하지 않는다. 스모크 13/13, 관리자 계약 테스트 6/6, postcode PHP 도메인·컨트롤러 테스트, PHP lint 통과.
- 보존: 실행 중인 PrestaShop/MariaDB와 named volume은 초기화하거나 삭제하지 않았다. GitHub Actions API는 이 환경에서 `403 Forbidden`을 반환해 신규 빈 DB 설치 결과를 직접 확인할 수 없었다.

## 2026-10-21 — 관리자 로그인 한국어·공식 로고 및 모듈 파일 권한

- 시작 기준: 주소 기능 체크포인트 `6531d64f419e24867f5aff6832ef240c7fa7762c`가 원격 `work`와 일치했다.
- 원인: 기존 Back Office의 `AdminGlobal` 한국어 XLIFF에는 Dutch 대상 문자열이 남아 있었고, PrestaShop 번역기는 XLIFF 뒤에 DB 번역 리소스를 붙여 단순 `addResource()` 오버레이보다 DB 문자열이 우선했다. 컨테이너에 수동 복사한 로컬 파일도 호스트 `0600` 모드가 전파되어 `www-data`가 읽지 못했다.
- 변경: Back Office 모듈이 한국어 XLIFF를 완성된 번역 카탈로그 뒤에 병합해 DB 값보다 우선하도록 했다. 로그인 화면은 제공된 공식 로고를 이미지로 표시하고 PrestaShop 상단·푸터 브랜딩을 감춘다. `docker/kuranea-entrypoint.sh`는 두 KURANEA 모듈 트리만 `www-data` 소유·디렉터리 0755·파일 0644로 동기화하고, fresh-install QA가 해당 파일을 실제 `www-data`로 읽을 수 있는지 확인한다.
- 브라우저 검증: 실제 관리자 로그인 데스크톱 1440×1000과 모바일 390×844에서 HTTP 200, `lang=ko`, 비밀번호 라벨 한국어, 공식 로고 표시, stock header/footer 숨김, 가로 넘침 없음, 페이지 오류 0건을 확인했다. 캡처는 `artifacts/qa/phase1a/admin-login-desktop-brand-fix.png`, `admin-login-mobile-brand-fix.png`에 저장했다.
- 제한: 로그인 외 관리자 전체 메뉴·대시보드의 한국어 100%는 아직 검증되지 않았다. 새 빈 DB Actions 실행과 공식 Japan Post CSV 실데이터 lookup도 아직 미확인이다.

## 2026-10-21 — Phase 1A 일본어 홈 UI 및 반응형 QA

- 시작 SHA: 로컬 `work`와 GitHub 원격 `work`가 모두 `34b97b6982e42361018f1746eb0214efe5fe366b`였다. 기존 컨테이너와 named volume은 유지했다.
- 변경: 홈 편집 문구와 하단 모바일 메뉴를 일본어·영어·한국어로 적용하고, Hummingbird 데모 배너를 홈에서 숨겼다. 뉴스레터 입력 대비와 공식 워드마크 크기를 조정했다.
- 검증: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/smoke -v` 12개 통과. 실제 브라우저에서 데스크톱 1440px과 모바일 390px을 열어 HTTP 200, `ja-JP`, 가로 넘침 없음, 브라우저 오류 0건을 확인했다. 현재 캡처는 `artifacts/qa/phase1a/home-desktop-current.png`, `home-mobile-current.png`, `admin-login-current.png`, 결과는 `browser-results-current.json`에 보존했다.
- 제한: 기존 카탈로그에 상품이 없어 유효한 카테고리·상품 상세 경로와 주문 흐름은 검증하지 않았다. 관리자 로그인은 접근 가능하지만 한국어/공식 관리자 로고 적용 전 상태로 촬영했다. 이번 UI 소스는 로컬 검토용으로 기존 webroot에 복사했으며, Compose 이미지는 빌드·배포하지 않았다.

## 2026-10-21 — 일본 우편번호 모듈 및 관리자 한국어 기반

- 변경: `kuraneapostcode` 모듈이 7자리/하이픈/전각 우편번호, 일본어 주소 검색, 복수 후보, 수동 입력, 공식 KEN_ALL CSV 가져오기, 일본어·영어·한국어 문구와 네이티브 주소 매핑을 제공한다. `kuraneabackoffice`는 익명 로그인 한국어 context, 제공된 공식 로고 hook, 누락 번역 overlay의 시작 범위를 제공한다.
- 런타임 경로: Compose 이미지가 두 모듈을 포함하고 기존 설치에서도 멱등 설치 helper를 실행하도록 연결했다. 신규 빈 설치 CI는 별도 GitHub-hosted project/volume을 사용해 공식 Japan Post CSV 다운로드·가져오기, 실제 `1000004` lookup, 수동 건물명이 있는 네이티브 Address 저장, 관리자 로그인 브랜드/한국어, 재시작 후 테이블 유지를 검증하도록 구성했다.
- 로컬 검증: smoke 12/12, 관리자 overlay 5/5, 우편번호 도메인 테스트 통과, 모듈 PHP lint 및 helper PHP lint 통과, JS 구문 검사, 셸 구문 검사, XLIFF XML 파싱, `docker compose config --quiet`, `git diff --check` 통과.
- 미검증: 공식 CSV 네트워크 다운로드와 실제 `1000004` 통합 테스트는 GitHub Actions 실행이 완료되어야 PASS로 기록한다. 브라우저 주소 입력/주문 생성/관리자 주문 화면도 아직 미검증이다. 기존 DB/named volume은 변경하지 않았다. 한국어 관리자 전체 화면 100%는 미완료이며 로그인 및 소수 번역 보완 코드만 검토했다.

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

## 2026-10-21 — JPY 기본 통화 및 재시작 smoke 검증

- 시작 기준: `work` 로컬 및 원격 SHA `69a99c4ef6f14882d7151ea109e86a47d2c4d2a8`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다. 로컬 변경과 미추적 QA 산출물을 먼저 점검하고 기존 파일을 삭제하거나 초기화하지 않았다.
- 변경: 신규 설치와 기존 설치 helper가 같은 멱등 JPY 부트스트랩을 사용하도록 했다. 기본 통화는 JPY, 정밀도는 0, ja/en/ko 표시명을 설정한다. 확인된 환율이 없는 EUR/USD는 비활성화한다. 신규 설치 smoke는 재시작 후 JPY 기본값과 3개 언어 번역을 다시 검사한다.
- 테스트: smoke 23/23, 관리자 계약 테스트 6/6, 우편번호 도메인·후보 API 테스트, PHP lint, shell/JS 문법, Compose 설정, `git diff --check` 통과. 기존 DB 읽기 전용 조회에서 JPY 활성/기본값 및 ja/en/ko 이름을 확인했고 상품/주문은 각각 0건이었다.
- 제한: 새 빈 볼륨 Actions run `39693892012`는 `Build and install into unique empty volumes`에서 실패했다. 익명 로그 및 무효한 현재 `GH_TOKEN`으로 상세 로그를 열지 못했으므로 설치 성공은 PASS로 기록하지 않는다. 공식 CSV 적재, 저장주소/주문/관리자 주문 화면, 관리자 전체 한국어, PWA 실기기 설치는 미완료다.
- 환경/보존: 관측된 cloud environment revision은 2로, 요청된 3이 적용되지 않았다. workspace 여유는 약 194 MB이고 inode 사용률은 95%다. 실행 중인 컨테이너, DB 데이터 및 named volume을 보존했고 prune/재빌드/초기화를 실행하지 않았다.

### 검증 추가 — 공식 우편 CSV 및 기존 볼륨 재시작

- Japan Post 공식 `ken_all.zip`을 내려받아 SHA-256 `c976cb0ff691a1aa7480b47b7e1f61bea08c2eadb3278f0366e474cd82dbf4b8`를 기록했다. 최신 CSV 124,840행을 기존 모듈 importer로 메모리 파싱했으며 저장 DB를 건드리지 않았다.
- PASS: `1000004`/`100-0004`가 각각 같은 실제 후보 1개를 찾고, `千代田区大手町` 부분검색 결과에 해당 주소가 포함됐다. 공식 CSV의 중복 우편번호 `004-0000`에서 서로 다른 후보 2개를 선택했고, `1000004` 후보가 `id_state`/도시/町域과 고객 입력 건물명을 네이티브 주소 필드로 보존했다.
- 기존 MariaDB/PrestaShop 컨테이너만 재시작했다. 두 컨테이너 healthy 및 쇼핑몰 HTTP 200을 확인하고 JPY 기본값·3개 언어 행·상품 0건·주문 0건을 읽기 전용 조회했다. 기존 named volume은 유지했다.
- 범위 제한: 위 공식 데이터 검증은 parser와 in-memory lookup까지다. 데이터베이스/API/checkout 주문 저장/Back Office 주문 화면 통합은 새 빈 볼륨 Actions 실패를 해결한 뒤 실행한다.
- 체크포인트: 구현 커밋 `ec7af91b66bdb31a36ea073957fdd8c7d428d334`를 `work` 원격과 대조했다. `git show`로 원격 PHP helper와 개발 현황 문서를 다시 읽고 데스크톱·모바일 증거 PNG 존재를 확인했다. 원격 `main`은 그대로다.

## 2026-10-21 — 신규 설치 실패 진단 가시성

- 확인: GitHub Actions run `39694912661`도 `Build and install into unique empty volumes` 단계에서 실패했다. 익명 Actions 화면은 상세 stderr/stdout을 숨기며 현재 `GH_TOKEN`은 유효하지 않고 Git credential helper에도 Actions 읽기 자격 증명이 없었다. 기존 로그의 원인을 추측해 설치 성공으로 보고하지 않았다.
- 변경: 실패 시 Docker 사용량, 디스크/inode, 격리 Compose 상태, 서비스 최근 160줄을 수집해 비밀번호/토큰 형태를 제거하고 `$GITHUB_STEP_SUMMARY`와 job log에 출력하도록 워크플로우를 보완했다.
- 검증: 전체 smoke 24/24, CI 워크플로우 계약 3/3 PASS. GitHub Actions `run:` bash 블록을 추출해 `bash -n` 및 모의 Docker 실패 실행을 했고, summary에 실패 진단이 포함되며 `MARIADB_ROOT_PASSWORD` 예시 값은 `[REDACTED]`로 변환됨을 확인했다. 새 Actions 실행 결과는 푸시 뒤 확인한다.
- 안전: 로컬 컨테이너/named volume을 조작하지 않았고 Docker prune/build를 실행하지 않았다.
- 원격 보존: `62690b81bcee67a6589981a6004956131e974943`를 `git ls-remote` 및 `origin/work`과 대조했다. 원격 workflow와 계약 테스트를 `git show`로 다시 읽었다. `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다.

## 2026-10-21 — 신규 설치 CI 진단 마스킹 및 artifact 보존

- 시작 기준: 로컬과 원격 `work` SHA `1238c7cc0a7e1590b4eb372b2dbb80d68dd8580c`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지했다. 기존 미추적 QA 캡처·테스트 캐시는 그대로 뒀다.
- CI 증거: run `39695319325` (`62690b81bcee67a6589981a6004956131e974943`)는 2분 15초 뒤 `Build and install into unique empty volumes` 단계에서 실패했다. 공개 job 화면은 exit code만 보였고 GitHub API 호출은 403을 반환해 원인을 검증할 상세 요약/로그에 접근하지 못했다.
- 변경: 시작 단계와 이후 실패 단계가 공통 수집기를 사용한다. Docker 상태와 최대 160줄의 서비스 로그를 마스킹한 뒤에만 stdout·step summary·2일 보존 artifact에 쓴다. 시작 실패 후 후속 단계에서 원시 서비스 로그를 다시 출력하던 경로를 제거했다.
- 검증: 테스트 우선으로 수집기 부재 시 회귀 테스트 실패를 확인한 뒤 구현했다. 전체 smoke 26/26, admin locale 계약 6/6, bash 구문, workflow YAML 파싱, `docker compose config --quiet`, `git diff --check` 통과. 현재 실행 중인 컨테이너와 named volume은 유지했고 Docker 빌드/prune을 하지 않았다.
- 원격 보존: `f636d40738c217f9c1f587b50c70742789583d99`를 `work`로 푸시한 뒤 로컬 HEAD·`git ls-remote`·`origin/work`이 일치하는 것을 확인하고 원격 workflow/수집기/회귀 테스트를 다시 읽었다. 이 커밋은 run `39695971760`을 시작했으며 마지막 확인 시 실행 중이었다.
- 후속 검증: run `39695971760`은 2분 32초 뒤 같은 시작 단계에서 실패했다. 공개 run 페이지에서 `fresh-install-diagnostics-39695971760-1` artifact ID `12391041696`, 크기 3.71 KB, digest `sha256:d2dbb7b5a52cf41d8fd4663c4823cf0b8bd1d8af6c4ed35a5a2642184bcfabd0`를 확인했다. artifact 본문과 상세 job 로그는 이 환경에서 다운로드/API 403/404로 접근할 수 없어 근본 원인을 추측하거나 PASS로 기록하지 않았다.

## 2026-10-22 — 공식 주소 데이터 로컬 통합 및 staging 공간 회수

- 시작 보호 확인: 현재 `work` 로컬/원격 SHA `e84fb2a238ef6f999d8d508e422c87f0b68e7dff`가 일치했고 `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지됐다. 기존 미추적 QA 캡처와 pycache는 삭제·초기화하지 않았다. MariaDB와 PrestaShop 컨테이너 및 named volume은 계속 실행 상태로 보존했다.
- 공식 주소 데이터: Japan Post 공식 `ken_all.zip`의 SHA-256 `c976cb0ff691a1aa7480b47b7e1f61bea08c2eadb3278f0366e474cd82dbf4b8`을 기록하고 CSV 124,840행을 파싱했다. 기존 DB의 모듈 주소 테이블에 고유 후보 124,839건을 적재했다. `1000004`와 `100-0004` 모두 도쿄도·지요다구·오테마치를 반환했고, `千代田区大手町` 검색과 복수 주소 `004-0000`의 후보 2개를 HTTP API에서 확인했다.
- 디스크 안전: import 뒤 active와 staging 테이블이 같은 데이터 124,839건을 보유하는 것을 양방향 전체 비교로 확인했다. 기존 주소 테이블을 유지하면서 staging 테이블만 비웠다. 주소 행은 124,839건 유지되고 staging은 0건이며 workspace 가용 공간은 42 MB에서 118 MB로 늘었다. 운영 중인 named volume, 기존 고객·주문 데이터는 초기화하지 않았다.
- 코드: importer가 새 주소 데이터의 `COMMIT` 성공 뒤에만 staging 복사본을 비우도록 수정하고, 빈 설치 smoke가 staging 행 0개를 확인하게 했다. 실패한 가져오기는 기존 active 데이터를 교체하지 않는다.
- 브라우저: 실제 사이트 origin의 모듈 JS와 DB-backed API를 주소 폼 계약 fixture에 연결했다. PC 1440×900 및 모바일 390×844에서 `1000004` 후보 선택, 도도부현/도시/町域 매핑, 일본어 문자열 검색, `004-0000`의 복수 선택, 건물명 수동 편집 보존을 확인했다. 브라우저 JS 오류는 0건이다. 증거 PNG는 `artifacts/qa/phase1a/postcode-widget-desktop.png`, `postcode-widget-mobile.png`다. 실제 checkout 페이지·주문 저장 화면은 아니므로 해당 검증은 미완료다.
- 테스트: smoke/계약 28/28, 관리자 번역 계약 6/6, PHP importer lint, 주소 도메인 및 후보 API 테스트, `bash -n`, `docker compose config --quiet`, `git diff --check` 통과. 관리자 한국어 100%와 실제 checkout 주소/주문 및 관리자 주문 표시 검증은 미완료다.
- 신규 설치/환경: 새 빈 설치 run `39697612835`가 `Build and install into unique empty volumes`에서 2분 38초 후 실패했다. 이 실행환경에서는 상세 로그와 artifact를 읽을 수 없어 errno 28 재현 여부를 확정하지 못했다. 로컬 workspace는 117 MB 여유, inode 사용률 95%여서 Docker 재빌드를 하지 않았다. 관측된 클라우드 environment revision은 2이며 사용자 지정 revision 3은 적용 증거가 없다.
- 커밋 범위는 importer·관련 테스트/CI 체크와 해당 브라우저 증거만 명시적으로 stage했다. 미추적 QA 캡처와 pycache는 그대로 보존했다.

## 2026-10-22 — 다국어 storefront 상태 및 QA 캡처

- 시작 시 로컬 `HEAD`, `origin/work`, 원격 `work`가 `b437e2dc6af0f7548f840103d537c9b03e74e708`에서 일치했고 `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다.
- 자식 테마에 일본어·영어·한국어 검색 및 빈 카테고리 상태, footer 링크/accessibility 문구를 추가했다. PC 1440px, 모바일 390px 캡처와 ja/en/ko 페이지 검증을 저장했다. smoke/contract 33/33 통과.
- 커밋 `2636d67cb1d155d5f9993a2476292d6fe11970e8`를 `work`에 push하고 `git ls-remote`, `origin/work`, remote file re-read로 확인했다. CI run #18 `39701030162`는 실패했다.

## 2026-10-22 — 주소 저장 전 우편번호 일치 검증

- Japan Post 후보가 존재하면 PrestaShop 주소 저장 전에 state/city/town 영역을 같은 우편번호 후보와 비교한다. 여러 town 후보는 각각 허용하고 건물·호수 입력은 유지한다. 인덱스에 후보가 없거나 조회가 실패하면 수동 입력을 허용한다. 메시지는 일본어·영어·한국어다.
- PHP synthetic harness와 PHP lint를 기존 PrestaShop 컨테이너의 임시 경로에서 실행했다. 기존 dev DB를 읽는 통합 검증에서 공식 `1000004` Tokyo/千代田区/大手町의 정상 저장 검증, 1000004/100-0004, 불일치 시구정촌 거부, 건물명 허용 및 수동 fallback을 확인했다. 이 테스트는 DB 데이터를 생성하지 않는다.
- 커밋 `bb40026956f98e51ff0158c1c095dab8c7f72d8a`를 push하고 원격 SHA·원격 테스트 파일을 다시 확인했다. CI run #19 `39701310507`는 실패; public job 화면에서 실패 단계는 확인했으나 상세 원인은 얻지 못했다.

## 2026-10-22 — 관리자 대시보드 날짜 필드 한국어

- 실제 관리자 대시보드에서 영어 `From`, `Start`, `End`를 확인했다. PrestaShop core는 수정하지 않고 KURANEA 관리자 모듈의 XLIFF 도메인을 PrestaShop 명명 규칙에 맞췄으며, dashboard 전용 module JS가 날짜 입력 label/placeholder와 요약을 한국어로 표시하도록 했다.
- 관리자 브라우저 로그인 후 PC 1440×1000에서 `lang=ko`, 한국어 날짜 labels/placeholders/요약, 한국어 메뉴, page error 0건을 검증하고 `artifacts/qa/phase1a/admin-dashboard-korean-after-date-overlay.png`를 저장했다. 관리자 locale 계약 8/8, JS syntax, XLIFF XML, PHP lint 통과. 전 관리자 100% 범위 검증은 미완료다.
- 필요한 admin media hook을 현재 dev shop에서 등록했으며 고객·주문 데이터는 변경하지 않았다. 커밋 `46fc912d74c818023db08b18a8a5528f07117ef5`를 push하고 원격 SHA/file을 확인했다. CI run #20 `39701883450`는 마지막 확인에서 실행 중.

## 2026-10-22 — 디스크·환경 재확인

- `df -h /workspace`: overlay 32 GB 중 30 GB 사용, 91 MB 여유, 100% 표시; inode 95% 사용. `docker system df -v`: 활성 `kuranea/prestashop:9.2.0` 및 `mariadb:10.11`, shared base, 미사용 dangling image 8.29 MB, build cache 8.284 MB, 활성 named volumes `kuranea_mariadb_data` 320.6 MB / `kuranea_prestashop_html` 538.9 MB, 미연결 254 MB volume 확인.
- 이미지/build cache는 프로젝트 복구/재빌드에 쓰일 수 있고 미연결 volume의 출처도 확실하지 않아 삭제하지 않았다. 어떤 Docker prune/재빌드/DB 초기화도 실행하지 않았다. 새 설치를 로컬에서 실행할 수 있는 저장 공간은 확보되지 않았다.
- Cloud environment status는 `spec_revision=2`, `observed_spec_revision=2`, connected/running을 보고한다. revision 3 설정은 이 runtime에 적용되지 않았다. 설정을 수정하지 않았다.
- run #20 `39701883450` 완료 상태를 다시 확인했다. 공개 job 화면은 `Build and install into unique empty volumes` 실패만 노출했고 상세 stderr/artifact는 접근할 수 없었다. run #18–20은 모두 이 단계에서 실패했으므로 clean install은 계속 FAIL이며 errno 28의 현재 원인은 확정되지 않았다.
