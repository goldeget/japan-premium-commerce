## 2026-10-23 — 출시 가격 정책 QA 상태 갱신 (13:00 UTC)

- 현재 기준 `work` SHA `6a371a912d436c354b0ab91f67c458a3d9131439`; `main` SHA `ee02a3657448d563508687614a246e05ac61eecd`는 변경하지 않았다.
- 사용자가 확정한 가격 정책은 일본 지원 지역 배송비 ¥0, 상품 표시 세금 포함 판매가격과 결제 상품 금액의 일치, 결제 단계 추가 배송비·세금·플랫폼 이용료 미청구다. 과세 대상은 실제로 지정된 판매자·상품 세금 규칙을 유지하고, 규칙 미할당을 면세 또는 0%로 허위 기록하지 않는 범위로 QA한다.
- 로컬에서 storefront 네트워크 검사 파일을 제외한 smoke 361개와 무료배송·세금 집중 계약 23개가 통과했다. 이 결과는 계약/정적 테스트이며 실제 브라우저, PrestaShop 주문 저장, 관리자 금액 검증이 아니다. Codex Cloud에서 Docker 빌드를 하지 않는다.
- 최종 코드 SHA `6a371a9`의 격리 fresh-install Actions [#39957544456](https://github.com/goldeget/japan-premium-commerce/actions/runs/39957544456)는 진행 중이다. 이전 코드 SHA `0aafdd8`의 [#39957326795](https://github.com/goldeget/japan-premium-commerce/actions/runs/39957326795)도 상태 행 재사용을 검증하기 위해 실행 중이다. 실제 설치·가격 QA 결과는 관련 단계 완료 전 미확정이다.
- 이전 full run [#39956044032](https://github.com/goldeget/japan-premium-commerce/actions/runs/39956044032)은 일본 지원 도도부현 행이 중복이라고 판정되어 무료배송 fixture에서 실패했다. checkout 가격 브라우저 단계는 실행되지 않았다.
- 최신 배송 fixture는 PrestaShop State API로 47개 카탈로그 행을 재사용한다. 상태 조회가 실패하거나 중복 ISO 코드가 존재하면 쓰기 전에 중단하고, 비지원 활성 상태가 country zone fallback으로 무료배송을 받는 것도 거부한다. 브라우저 표본은 Tokyo desktop qty 2+coupon와 같은 장바구니 mobile viewport 대조, Osaka mobile qty 1/no coupon, 별도 synthetic-tax Tokyo 주문이며 모든 지역·조건 조합을 의미하지 않는다.
- 한국어 배송 패널은 현재 PrestaShop AdminCarriers/AdminShipping 설정을 링크한다. 이번 QA는 그 native 화면에서 무료 운송사를 run-scoped 일본 zone에 저장하고 재조회하는 동작을 CI 격리 DB에서만 수행하며, 운영 배송 설정을 변경하지 않는다.
- 합성 10% 세금은 산술·저장 검증용 CI fixture이며 일본의 적법한 세율이나 판매자의 실제 세무 판단이 아니다. 실제 과세/면세 구분은 판매자·상품 세금 규칙으로 확인해야 한다.
- 현 시점에는 무료배송 가격, 브라우저 주문, 저장 주문, 주문내역, 관리자 주문액의 runtime PASS가 없다. Actions 각 단계가 완료되고 성공한 뒤에만 결과를 갱신한다. 운영 DB/named volume/carrier 설정은 변경하지 않았고, 실결제와 운영 배포를 실행하지 않았다.

# KURANEA 작업 기록

## 2026-10-23 — ORDENOWA 출시 가격 정책 격리 QA (이전 checkpoint)

- 시작 기준 local `HEAD`, live remote `work`는 `8808791057349c46dd37f4bab055c84a9fd04319`; `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. Codex Cloud에서 Docker 이미지 빌드나 production DB 접근을 하지 않았다.
- 세금 포함 상품 가격 구현은 고객 표시 가격을 기준으로 PrestaShop 저장가격을 환산하고, 선택 세금 규칙·주문 세액을 검증한다. 일본 규칙을 알 수 없을 때 실제 세금을 0으로 기록하지 않고 저장을 거부한다. 합성 10%는 CI 전용이며 법정 세율 근거가 아니다.
- 배송 QA는 격리된 run별 일본 전용 존·무료 운송사를 생성하고 Back Office 저장 후 PrestaShop을 재시작해 다시 읽는다. 일반 주문 QA보다 이 설정을 먼저 수행한다. 도쿄 PC 수량 2+쿠폰, 오사카 모바일 수량 1+쿠폰 없음, 과세 상품 주문, native 저장 데이터와 관리자 금액을 대조한다. 도쿄 검증 실패가 오사카 모바일 검증을 건너뛰지 않도록 했다.
- 리뷰에서 발견한 CI 결함 두 가지를 회귀 테스트로 먼저 재현했다. 일본 국가/상품의 MariaDB 조회는 SQL에 역슬래시가 포함된 따옴표를 넘겼고, Osaka QA는 Tokyo 단계 성공을 선행 조건으로 요구했다. 쿼리 인자 검증과 지역 단계 의존 조건을 수정했다. PWA 고객 생성 경로도 exact run/project/port 검사를 Chromium 시작 전에 요구한다.
- 로컬 정적 검증: 통합 QA 계약 182개, checkout·상품·브랜드 계약 75개, Japan Post updater 7개 통과. Python 구문, workflow YAML, 63개 step, 셸 60개, 고유 workflow step ID 40개, `git diff --check` 통과. PHP·DB·Chromium은 GitHub Actions에만 둔다.
- 독립 push 체크포인트: `561cba7487610c00b05e87dd71ce033f268c1394` (`feat(catalog): preserve tax-inclusive JPY sale prices`), `081e0b87b98773a6b2409e92c280babf3dc7580b` (`test(storefront): cover account and brand workflows`), `29766718481a2c594ab7aa7896bb563de784c856` (`test(checkout): verify taxable prices and free Japan shipping`). 각 push 후 `git ls-remote` SHA와 `origin/work` tracking ref를 대조하고 원격 파일을 다시 읽었다. `main`은 변경하지 않았다.
- Actions `39940265549`는 통합 workflow보다 먼저 실행되어 preflight 계약에서 실패했다. 통합 SHA `2976671`의 최신 run `39940305885`는 사전 계약과 이미지 빌드를 통과했지만 synthetic postcode fixture와 tax fixture가 각각 실패했다. 이후 상품·장바구니·계정·배송 브라우저 단계는 건너뛰었다. 로그 접근은 403 Forbidden이므로 다음 run에는 합성 주문 금액의 기대/관측 필드만 출력하도록 진단을 보강했다. Osaka `State.name`을 PrestaShop 9.2 scalar 모델에 맞게 수정했고, postcode 오류가 독립 browser QA를 중단하지 않게 aggregate 조건을 추가했다. 주문 확인 화면에서 상품 합계·배송·세금·최종 합계를 주문내역 이동 전에 대조한다. 새 격리 runtime QA와 artifact가 통과하기 전까지 브라우저·주문 결과를 PASS로 기록하지 않는다.
- Production DB/volume, 운영 배송 설정, 실제 결제는 변경하지 않았다. Actions QA의 두 일본 주소는 격리 테스트이며 일본 전 지역에 대한 운영 carrier 설정의 증거로 확장하지 않는다.

## 2026-10-22 — Actions 분리 기준 및 SEO escape 보안 체크포인트

- 시작 전 `work`와 `origin/work`는 `f8de2015d14cfefb5f25982bd56d781007d91ff3`, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. 미커밋 변경은 없었다. Codex Cloud에서 Docker `vfs`/32 GB 이미지 빌드를 재시도하지 않고 Docker·MariaDB·브라우저 실행을 GitHub Actions에 둔다.
- Draft PR #3 (`095d19baec40400e3b7c286e98af7886532290b2`)의 SEO diff를 검토했다. title/description/robots/canonical/hreflang/Open Graph 속성 값의 HTML escaping과 JSON-LD `JSON_HEX_TAG`를 적용하고, PR 검사에서 빠졌던 PWA `data-service-worker`·`data-scope`의 `$urls.base_url`도 escape하도록 보완했다. 기존 KURANEA 원본 자산은 변경하지 않았다.
- TDD: 새 SEO source contract를 먼저 실행해 현재 head template에서 2개 테스트 실패를 확인했다. 수정 적용 후 SEO contract 2/2, 기존 theme contract 15/15, `git diff --check`가 통과했다.
- `security(seo): escape dynamic metadata and JSON-LD` 커밋 `000b0661937c9d4f48e4408d7fb88598cd426e45`를 `work`에 push했다. 원격 SHA와 새 파일 내용을 확인했고, GitHub Actions SEO contract run `39786618881`이 성공했다. 해당 workflow는 source contract만 실행했으며 실제 PrestaShop/Smarty 렌더링은 검증하지 않았다.
- `main`은 변경하지 않았다. `work` checkpoint를 별도 `/tmp` clone으로 복제해 SHA와 세 변경 파일을 검증했다. ORDENOWA 공식 원본 ZIP은 아직 저장소나 작업공간에서 찾지 못해 이미지 배포는 대기 중이다.

## 2026-10-22 — P0 Docker 설치 후처리 실패 진단 및 로컬 수정

- 시작 기준: 원격 `work`는 `c2e3d9f11dc0cfeb3c116fde8d0c03274d7e88a3`, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. checkpoint clone에 있던 미커밋 카탈로그 파서·workflow·문서 변경을 보존했고 main이나 기존 개발 DB/named volume을 수정하지 않았다.
- 사용자가 전달한 run `39728912492` 로그에서 설치 CLI가 성공해 `/install`을 제거한 뒤, 공식 Docker 스크립트가 같은 경로를 다시 삭제하다 실패한 것을 확인했다. 스크립트는 `set -e`라 post-install hook과 뒤쪽 설치 완료 단계까지 진행하지 않는다. Compose `restart: unless-stopped`는 parameters 파일을 보고 `PrestaShop Core already installed` 분기로 재시작했고, first-install 전용 후처리를 건너뛰었다. 이후 HTTP 진입점에서 `var/cache/prod/appParameters.php` 누락 fatal이 발생했다.
- 검증 출처: 고정 이미지의 `/tmp/docker_run.sh` 원본 SHA-256 `422f08ac00c69614936f0eb2d9e5ea8316de6dd6e4b2fa5904720b1f901b9f2f`; PrestaShop 9.2.0 공식 `Install::postInstall()`은 `install.lock`, `Install::finalize()`는 install 디렉터리를 제거한다. 설정 캐시 파일은 실제 PrestaShop config bootstrap으로 생성되어야 하며 테스트나 초기화에서 가짜 파일은 만들지 않는다.
- 수정 후보: 두 중복 삭제를 대상 존재 시에만 수행하도록 고정 upstream 구문을 fail-closed patcher로 바꾼다. KURANEA bootstrap과 module setup을 first-install post hook에서 모든 시작 시 호출되는 init hook으로 이동해 최초 부팅·재시작에서 실행되게 한다. `/var/www/html/var/cache/prod`만 `www-data` 소유로 맞추고 신규 smoke에 `parameters.php`, 실 cache 파일, marker, 초기화 로그 및 재시작 실행 로그를 확인하도록 추가했다. PrestaShop PHP 코어는 변경하지 않았다.
- 검증: P0 회귀 계약 3/3, 관리자 경로 계약 4/4, 주소 갱신 계약 6/6, shell 구문 및 upstream 스크립트 복사본의 patch/idempotence 통과. 전체 storefront/smoke 계약의 기존 로컬 사이트 카테고리 3건은 빈 카테고리 URL에서 HTTP 500으로 실패했고 이는 이미 기록된 별도 결함이다. 로컬 Docker 설치/DB 접근은 공간 및 실행환경 문제 때문에 시도하지 않았다.
- 이 커밋은 원격 저장 및 신규 설치 Actions 실행 전이다. 코드 리뷰 후 `work`에 저장해 격리된 fresh-install workflow를 단 한 번 실행한다. 그때 신규 설치 성공이 확인되기 전까지 주문/address E2E는 PASS로 기록하지 않는다.

## 2026-10-22 — 관리자 폴더 설치 경로 후속 수정

- 원격 최신 SHA는 `175d75dac132ddb0a8f54777519795208df8ae4d`였다. 첫 수정 커밋의 Actions run `39727310686`은 이미지 빌드/정적 검사를 통과했지만 빈 DB 설치 단계에서 실패했다. 이 실행의 상세 로그는 현재 환경에서 404/접근 오류여서 실패 세부를 추정하지 않았다.
- 후속 후보는 `PS_FOLDER_ADMIN=admin-dev`로 공식 Docker entrypoint가 실제 관리자 파일을 `/admin-dev`에 놓게 한다. 공식 CLI 자산 설치가 반환된 뒤 post-install helper가 실행되고, PHP bootstrap의 official post-install 처리 이후 실제 감지한 관리 디렉터리를 `admin-kuranea`로 옮겨 최종 assets를 확인한다. 빈 관리자 디렉터리나 `chmod 777`을 사용하지 않는다.
- 테스트: 관리자 설치 순서 계약 4/4, 주소 갱신 계약 6/6, 관리자 번역 계약 8/8 통과. 전체 storefront smoke는 38건 중 35건 통과, 3개 언어의 빈 카테고리 URL에서 HTTP 500이 발생했다. 로컬 category 응답에는 `Category.php`와 `CategoryController.php`의 `foreach(false)` 경고가 있으나 원인 분석은 미완료다. `docker compose exec` PHP lint는 runc runtime 오류로 재시도 불가했다.
- 안전: overlay 여유 0 bytes·inode 100%, MariaDB unhealthy를 관찰했다. 실행 중인 컨테이너와 모든 named volume을 보존하고 재시작, DB 변경, prune, 재빌드는 하지 않았다. 동일한 이유로 신규 설치/실주문 검증은 하지 않았다.
- 현재 후속 코드는 로컬 수정이며 다음 원격 checkpoint SHA는 아직 없다. 코드와 이 기록을 `work`에 push/원격 SHA 확인한 뒤 fresh-install Actions를 확인하고, 성공 전에 주문 E2E를 실행하지 않는다.

## 2026-10-22 — PrestaShop 신규 설치 admin-dev 경로 오류

- 시작 기준: 로컬 `work`와 원격 `work`가 `4c6d38d7cf94506e2427c2fc904074055a070312`였고 원격 `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. 미추적 QA 캡처/JSON/pycache, 실행 중인 PrestaShop·MariaDB, 기존 named volume과 미연결 volume을 보존했다.
- 신규 원인: 최신 Actions 로그의 `assets:install admin-dev --symlink=1` 오류를 PrestaShop 9.2.0 `Install::finalize()`와 Docker 시작 순서에 대조했다. Docker가 설치 전에 `/admin`을 `admin-kuranea`로 이동해 CLI 설치기가 존재하지 않는 `admin-dev`를 target으로 선택했다. 과거 `errno 28`은 이전 실패 기록이며 이번 직접 원인으로 취급하지 않는다. 공식 이슈는 PrestaShop #40348 및 Docker #465다.
- 변경: Compose 신규 설치에는 `PS_FOLDER_ADMIN=admin`, 최종 이름은 별도 `KURANEA_ADMIN_FOLDER=admin-kuranea`로 분리했다. post-install helper가 설치기가 감지한 관리자 경로를 확인하고, 대상 충돌을 거부한 뒤 최종 경로로 이동하고 공식 `AssetsInstaller`를 다시 호출한다. 최종 폴더와 관리자 CSS/로그인 URL 검증을 smoke에 추가하고 CI에서 경로 순서 계약을 확인한다. 코어, 기존 DB, named volume은 수정하지 않았다.
- 테스트: 회귀 계약은 구현 전 3건 실패를 재현한 뒤 3/3 통과, 기존 fresh-install workflow 계약과 합계 10/10 통과했다. PHP lint, shell syntax, `docker compose config --quiet`, `git diff --check`도 통과했다. 실제 신규 설치는 작업공간 85 MB 여유로 로컬 실행하지 않았다.
- 보존: 커밋 `175d75dac132ddb0a8f54777519795208df8ae4d`를 즉시 원격 `work`에 push했다. `git ls-remote`, `origin/work`, 로컬 HEAD가 일치하고 원격 파일을 재조회했다. 새 shallow clone `/tmp/kuran-recovery-175d75d`의 HEAD와 helper/회귀 테스트 복구를 확인했다. `main`은 그대로다. Actions run `39727310686`은 이미지 빌드·사전 계약 검사를 통과했고 격리 설치 결과는 아직 진행 중이다.
- 다음: 동일 CI 실행에서 빈 설치, ja/en/ko, KURANEA theme, 최종 `admin-kuranea` assets/login, 재시작 보존을 확인한다. 실패하면 로그에서 새 직접 원인을 확인하고 필요한 수정만 별도 체크포인트로 저장한다. 이후 실제 storefront checkout/browser order를 격리 runner에서 검증한다.

## 2026-10-22 — 주소 데이터 안전성·갱신과 환경 상태 점검

- 시작 기준: 로컬 `HEAD`, `origin/work`, GitHub `work` 원격 SHA가 `1690a073bc25f38d3c02cc7616dd7b8f9f5a3cc7`로 일치했다. `main`은 `ee02a3657448d563508687614a246e05ac61eecd`다. 기존 미추적 브라우저 캡처와 테스트 캐시는 변경하거나 삭제하지 않았다.
- 주소 코드 체크포인트: `06617f6`에서 Japan Post의 설명용 `（次のビルを除く）`를 고객 주소에서 제거하고 `以下に掲載がない場合`를 상세 주소 빈값으로 처리했다. `a444238`은 공식 `1000004` 주소 검증이 `大手町`를 정확히 기대하게 했다. `1690a07`은 공식 KEN_ALL ZIP을 검증한 뒤 기존 트랜잭션 importer를 실행하는 수동 갱신 CLI를 추가했다. 세 체크포인트 모두 `work`에 푸시 후 원격 SHA와 파일 재조회를 확인했다.
- 검증: Python smoke/CI 계약 34/34, 관리자 번역 계약 8/8, 주소 갱신 CLI 계약 6/6, workflow 계약 7/7 통과. PHP 도메인/후보 응답 테스트 및 기존 DB read-only 통합 주소 검증, PHP lint, JavaScript·shell 문법, `docker compose config --quiet`도 통과했다. 이 turn에는 주소 데이터를 다시 적재하거나 고객·주소·주문 행을 만들지 않았다.
- CI 상태: run `39703327857`, `39704824787`은 이미지 빌드와 격리 캐시 권한 검사 뒤 `Start the empty-volume shop`에서 실패했다. 공개 실행 목록에서 후속 `39705702536`, `39706052890`, `39706126218`도 Failure로 확인했다. 마지막 run은 `1690a07`에서 2분 39초 후 실패하고 3.37 KB artifact(SHA-256 `5ba78e90152543f775930472455c8434fae47018303373b8a93711506dcb2500`)를 생성했다. GitHub 페이지는 로그 열람에 로그인하라고 표시하며 API `403`, artifact 익명 다운로드 `404`다. 최신 실패 단계와 `errno 28` 여부는 확인할 수 없어 추측하지 않는다.
- 상품 수집 접근: Amazon Japan 및 Rakuten 공개 홈페이지에 보낸 읽기 전용 HTTPS 요청은 개발환경 egress proxy CONNECT `403`으로 차단됐다. 허용되지 않은 도메인을 통한 우회는 하지 않았고 실제 상품을 scrape/등록하지 않았다. 현재 사용자 제공 개별 상품 URL과 HTML fixture도 저장소에 없다.
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
- 관리자 브라우저 로그인 후 PC 1440×1000에서 `lang=ko`, 한국어 날짜 labels/placeholders/요약, 한국어 메뉴, page error 0건을 검증하고 `artifacts/qa/phase1a/admin-dashboard-korean-after-date-overlay.png`를 저장했다. 관리자 locale 계약 8/8, JS syntax,
## 2026-10-22 — Fresh install 주소 저장 실패 진단 분리

- 시작 기준: `work` 원격·로컬 SHA `1cfc24c9585ebe4169250dcc38321ad6c5825c68`, `main` SHA `ee02a3657448d563508687614a246e05ac61eecd`. 기존 카탈로그 파서 등 미커밋 파일과 저장소 밖 개발 DB/named volume을 보존했다.
- 직전 수정 후 격리 Actions run `39732730236`은 이미지 빌드, 캐시 권한 probe, 빈 볼륨 Compose 기동, 공식 Japan Post CSV import 단계까지 성공했다. `Verify real Tokyo postcode lookup and saved native address` 결합 단계는 종료 코드 255로 실패했고 이후 native order 및 restart smoke는 실행되지 않았다. run artifact는 공개 실행 페이지에서 본문을 읽을 수 없으므로 예외의 실제 발생 위치를 추측하지 않는다.
- 진단 보강: CI를 도쿄 API 조회와 PrestaShop 네이티브 주소 저장으로 분리했다. PHP 저장 검증은 bootstrap, Japan/state 조회, CSV 후보, 고객 생성, 주소 저장, reload 단계를 기록하고 예외 클래스·메시지를 GitHub error annotation으로 제한 출력한다. 회귀 계약 테스트가 두 workflow step 분리와 진단 단계를 고정한다. 프로덕션 모듈/코어는 수정하지 않았다.
- 로컬 검증: fresh-install workflow contract 및 주소 데이터 갱신 계약 테스트 14개 통과, Docker Compose 정적 config와 `git diff --check` 통과. 호스트에 PHP CLI가 없고 활성 로컬 Docker/DB 상태를 보존하기 위해 실행 DB에 테스트 데이터를 넣지 않았다.
- 다음 검증은 새 원격 커밋에 의해 실행되는 격리 Actions 1회다. 주소 API, 네이티브 Address, 무결제 Order, 관리자 배송지 표시, 일본어/다국어·JPY·테마·관리자 로그인, 재시작 후 지속성은 실제 각 단계가 성공하기 전까지 미검증이다.
## 2026-10-22 — Native Address 저장 CI 오류 수정

- 격리 Actions run `39734469874`에서 workflow contract, 이미지 build, cache ownership probe, 빈 볼륨 shop 기동, 공식 Japan Post CSV import와 `1000004` postcode API lookup이 모두 통과했다. 실패 단계 annotation은 `KURANEA_NATIVE_ADDRESS_STAGE=native address save; exception=Error; message=Cannot access protected property Address::$id_shop`였다. 이후 native order와 restart smoke는 실행되지 않았다.
- PrestaShop 9.2.0 공식 `AddressCore`를 확인해 `id_shop`가 Address public property나 ObjectModel field가 아닌 것을 대조했다. 테스트 harness의 불필요한 `$address->id_shop = 1`만 제거했고 코어/운영 모듈을 수정하지 않았다.
- TDD: 먼저 Address의 미지원 shop 속성 대입을 금지하는 workflow contract를 추가하고 실패를 확인한 다음 잘못된 대입을 지웠다. postcode workflow 및 Japan Post refresh contract 15/15 통과, Compose 정적 설정과 `git diff --check` 통과.
- 새 격리 CI에서 native address save, unpaid Order 생성, 관리자 배송지 조회, restart/data persistence는 다시 확인해야 하므로 아직 PASS가 아니다. 기존 개발 DB, named volume 및 미커밋 catalog parser 변경은 보존했다.
## 2026-10-22 — Native order verifier의 미지원 Address 속성 제거

- run `39735099736`은 주소 저장 verifier의 첫 수정 커밋으로 진행 중이었다. 이 실행에서 다음 단계로 넘어가기 전에 `tests/postcode/verify_native_order_persistence.php`도 같은 `$address->id_shop` 대입을 하고 있음을 확인했다. 이전 CI annotation으로 확인된 PrestaShop 9.2.0 `AddressCore` 계약과 같은 원인이므로 주소·주문 검증기를 함께 고친다.
- 회귀 검사를 먼저 확장해 두 스크립트에서 해당 대입을 거부하는 검사가 기존 코드에서 실패함을 확인했다. native order verifier의 한 줄 대입을 삭제했으며, 주소/주문 로직과 코어는 변경하지 않았다.
- fresh-install workflow contract 및 Japan Post refresh 테스트 15/15 통과, Compose 설정·diff 검사 통과. 이 수정은 다음 격리 CI에서 검증하며 `39735099736`은 수정 전 snapshot이므로 별도로 결과를 기록한다.
## 2026-10-22 — Native order E2E 실패 경계 계측

- run `39735099736`은 empty-volume install, 공식 CSV import, `1000004` postcode lookup 및 native Address 저장까지 통과했다. Order step 실패 후 확인하니 그 run의 checkout SHA `dad3066`에서 주문 verifier에 Address의 미지원 `id_shop` 대입이 남아 있었다. 같은 속성을 거부하는 회귀 계약을 확장하고 해당 대입을 제거해 `994a3f6`에 저장했다.
- 새 수정 run `39735277398`에서 empty-volume startup, Japan Post CSV import, Tokyo/Otemachi API lookup 및 native Address save가 통과했지만 native unpaid-order/Back Office projection step은 exit 255로 실패했다. 당시 order verifier의 uncaught exception은 public job page에서 상세 로그로 읽을 수 없어 실패 경계를 추정하지 않는다. restart step은 skipped.
- 개선: native order verifier에 bootstrap, Back Office kernel, JP context, payment module, address, product, cart/quantity, delivery, order 및 Back Office projection stage를 추가한다. Uncaught Throwable은 제한된 메시지와 stage를 GitHub annotation으로 출력한다. 다음 CI의 오류 증거로 실제 root cause를 판정한다.
- TDD/로컬 검사: stage contract를 먼저 추가해 fail을 확인한 뒤 handler와 stage marker를 넣었다. fresh-install contract 및 Japan Post refresh 테스트 15/15, Compose YAML 검증, `git diff --check` 통과. 실제 PHP/MySQL 동작은 다음 격리 CI에서 확인한다.
## 2026-10-22 — Back Office order projection query bus 수정

- run `39736010830`에서 workflow/image/cache probe, 빈 볼륨 설치, official CSV import, `1000004` Tokyo/Otemachi API lookup 및 native Address 저장이 통과했다. annotation의 실패 단계는 `Back Office shipping address projection`; 예외는 Symfony `ServiceNotFoundException`으로 `CommandBusInterface`가 컴파일된 컨테이너에서 removed/inlined 됐다는 내용이었다. restart step은 실행하지 않았다.
- PrestaShop 9.2.0 공식 `FrameworkBundleAdminController::getQueryBus()`가 `prestashop.core.query_bus` 서비스를 사용하고 공식 OrderController가 `GetOrderForViewing($orderId, QuerySorting::DESC)`를 dispatch하는 것을 확인했다. 검증기는 같은 query bus service id 및 정렬값을 사용하도록 바꿨으며 PHP 코어/쇼핑몰 모듈은 변경하지 않았다.
- 회귀 contract를 먼저 추가해 기존 direct `CommandBusInterface::class` 호출에서 실패를 확인하고, 공식 query bus alias 적용 후 green을 확인했다. fresh-install contract 및 Japan Post refresh 15/15, Compose config, `git diff --check` 통과.
- 실제 관리자 order projection, unpaid Order의 저장/주소 표시 및 restart/data persistence는 다음 격리 GitHub Actions 실행 전까지 미완료다.
## 2026-10-22 — 빈 DB 설치·일본 주소 주문 native E2E 통과

- query bus 수정 코드 `6b05ae8`로 실행한 GitHub Actions run `39736745903`은 job 및 workflow `Success`였다. 이미지 build, isolated cache ownership probe, 빈 MariaDB named volume의 신규 설치, Japan Post 공식 KEN_ALL 다운로드/import, postcode `1000004` 도쿄/오테마치 HTTP lookup, native Address 생성 및 재조회, unpaid Order와 Back Office projection, fresh-shop restart smoke 순서로 통과했다.
- Order fixture는 `[CI ONLY]` product, 전용 Customer, `1-2-3` 집주소와 CI 전용 건물/호수, native Cart 및 free CI-only carrier를 격리 DB에 만들고 `ps_checkpayment`의 unpaid/non-logable state로 `validateOrder()`를 실행한다. `total_paid_real=0`, delivery address 연결, postcode/도도부현/시구정촌/町域/번지/건물 필드를 확인했다. 실제 결제·은행 입금은 없었다. official `GetOrderForViewing` query로 Back Office 배송지 문자열도 검증했다.
- Restart smoke는 storefront HTTP 200, 관리자 `admin-kuranea` 로그인 화면/공식 로고, ja 기본 및 en/ko 활성, JPY, KURANEA theme/CSS, 캐시/bootstrap marker와 DB 테이블 수/구성을 재확인했다. 이는 격리된 GitHub runner의 신규 DB만 대상으로 했고 기존 개발 named volume은 건드리지 않았다.
- 한계: 이 검증은 PrestaShop native model/service를 통한 주소·장바구니·주문 저장이며 실제 고객 브라우저에서 상품 카드→장바구니→checkout UI를 완료한 browser E2E는 아니다. Restart 후 방금 만든 특정 주문/배송지 row를 다시 조회하는 개별 assertion도 없다. 이 두 항목을 후속 격리 browser/persistence QA로 남긴다.

## 2026-10-22 — ORDENOWA 유지보수 이어가기

- 시작 원격 `work` SHA는 `d8896c346215f73ec36f806b17d277ef3a899ec9`, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. 기존 변경·named volume은 건드리지 않았다.
- `Offline catalog parser` run `39751104912`는 PHP 8.3 lint, synthetic Amazon Japan/Rakuten parser 테스트, fresh-install 계약 테스트를 통과했다. 실제 외부 페이지 접속·상품 등록은 이 실행으로 검증되지 않는다.
- fresh-install run `39749482357`는 상점 Compose 시작 뒤 공식 Japan Post KEN_ALL 다운로드 단계에서 curl exit 22로 실패했다. 공개 로그는 상세 HTTP 응답을 숨기고 artifact는 인증 없이 다운로드되지 않아 상태 코드와 응답 본문은 미확정이다. 시작 때 지적된 `admin-dev` 오류는 이 run에서 나타나지 않았다.
- CI는 모듈의 기존 HTTPS·최종 호스트·ZIP/CSV 검증 및 트랜잭션 importer를 직접 실행하도록 변경했다. 다운로드 실패 시 exit/status와 URL query를 제외한 호스트만 기록하고, 실패 후 importer 미호출을 회귀 테스트로 고정했다. 관련 검사 16/16 통과 후 `ba5de866d2ca771e2cdad5f36d5d40a6ce7573fa`를 `work`에 push했다. `git ls-remote`, 별도 shallow clone 및 원격 파일 재조회로 SHA와 변경 내용을 확인했으며 `main`은 유지됐다. 이 수정 커밋의 fresh-install run `39751809078`은 확인 시점에 진행 중이었다.
- ORDENOWA 공식 이미지는 사용자 메시지에서 미리보기로 보였지만, 실제 ZIP/PNG 바이트는 이번 실행환경에서 접근할 수 없었다. 이 환경의 attachments에는 기존 KURANEA 원본만 확인됐다. 따라서 신규 ORDENOWA 로고·favicon·PWA/OG 아이콘을 저장하거나 적용했다고 기록하지 않으며 기존 원본/이력을 유지한다.
- cloud environment의 현재 `spec_revision`과 `observed_spec_revision`은 2다. 일본 우편 호스트는 현재 restricted egress 정책에 없다. revision 3 적용은 확인되지 않았고 환경 draft 변경·게시도 하지 않았다.
- 신규 설치/주소 자동완성·저장 주문·관리자 배송지 화면, 실제 브라우저 E2E, 전체 관리자 한국어, PWA 실기기 설치, 영업 승인·실거래는 완료로 표시하지 않는다.

## 2026-10-22 — ORDENOWA 카탈로그 parser 체크포인트

- Amazon Japan/Rakuten을 위한 합성 HTML fixture 파서와 독립 Actions workflow를 `d8896c346215f73ec36f806b17d277ef3a899ec9`에 저장했다. run `39751104912`가 성공했다. 페이지 네트워크는 제한을 우회하지 않았고 실제 상품 수집은 0건이다.
- parser의 검수 큐는 메모리 기반이며 관리자 지속형 검수/승인, PrestaShop 네이티브 상품 생성, TEST/DEMO 상품 10개 등록은 후속 작업이다.

## 2026-10-22 — ORDENOWA 관리자 설정·검증 이어가기

- 시작 시 원격 `work` SHA `6f6ff5e5a99210f916b7064dacd00c73932ded6c`, `main` SHA `ee02a3657448d563508687614a246e05ac61eecd`를 확인했다. `/workspace/japan-premium-commerce`의 기존 미커밋 파일·스크린샷·테스트 폴더 및 named volume은 수정·삭제·초기화하지 않았다. 실제 변경은 별도 `/tmp/kuran-p0-checkpoint` work clone에서 진행했다.
- `ba508b4`는 관리자 운영 설정의 특정상거래법 필드 라벨을 한국어로 바꿨다. CI `39756576373`가 새 assertion의 다국어 접미어 `· 일본어` 누락을 확인했고, `3ec583c`에서 기대값을 실제 필드 라벨과 일치시켰다.
- `3404116`은 법률 페이지 PHP 테스트의 실패 메시지를 Workflow summary와 step output에 노출하도록 보완했다. 정확한 예외는 `PublishedLegalPageBuilder::build()`가 locale `title`을 본문 `<h1>`에 렌더링하지 않는 것이었다. `7cf8c41`에 localized `<h1>` 및 회귀 테스트를 추가했다. 같은 커밋에 은행 계좌이체 결제 활성화/계좌 연결을 추가했고, 게시된 법률 페이지·푸터·HTML/텍스트 주문 이메일은 선택된 완전한 활성 계좌 하나만 표시한다. `39757526475`에서 business-profile Actions 전체가 성공했다.
- `cc448a6`은 `kuraneabackoffice`, `kuraneapostcode` Module Manager 이름과 설명을 한국어로 바꾸고 회귀 테스트를 추가했다. 이번 로컬 실행: business-profile Python 10/10, admin locale 13/13, fresh-install workflow contract 10/10, `git diff --check` 통과.
- fresh-install run `39756769346`은 빈 볼륨 Compose `--wait` 기동까지 성공했다. 이어 공식 Japan Post KEN_ALL을 받는 단계가 `curl_exit=22 http_status=503 effective_host=www.post.japanpost.jp`로 실패하여 주소 조회, 네이티브 주소·주문 저장, 관리자 주문 조회, 재시작 보존은 실행되지 않았다. 같은 네트워크 실패를 근거 없이 성공 처리하거나 무작정 재시도하지 않는다. 최신 `39757526456`은 당시 실행 중이었다.
- business-profile run `39756769193`의 실제 예외는 영어 법률 페이지 제목 누락이었다. 이 문제는 `7cf8c41`에서 수정되었고 `39757526475`가 통과했다. 따라서 해당 기능의 PHP 코드 계약은 Actions에서 확인됐으나, 관리자/고객 브라우저 E2E는 별도 미완료다.
- 첨부 ORDENOWA 세 이미지 미리보기는 대화에서 확인되지만 `download_file`은 `cannot create attachment directory: Not a directory`로 실패했다. `/workspace`와 `/tmp`를 검색해도 ORDENOWA 원본 바이너리가 없었다. 기존 KURANEA `assets/brand/source/` 및 과거 이미지는 보존했고, 공식 ORDENOWA 로고·favicon·PWA·OG 산출물을 만들거나 교체하지 않았다.
- 현재 cloud environment는 `spec_revision=2`, `observed_spec_revision=2`로 revision 3 적용이 확인되지 않았다. 이전 SHA를 가리키는 draft를 수정하거나 게시하지 않았다. `/workspace` 여유 공간은 0 bytes이고 현재 기존 PrestaShop/MariaDB 컨테이너 모두 unhealthy다. Docker 상태만 읽었으며 기존 named volume을 건드리거나 새 컨테이너를 만들지 않았다.
- 검증 한계: 이 셸에는 PHP CLI가 없다. PHP 변경은 remote Actions에서 검사했다. 현재 로컬에서 새 browser screenshot, 실제 상품 수집·등록·주문, 기기 PWA 설치 검증은 하지 않았다. 실제 외부 상품 수집 0건, 실제 신규 주문 0건으로 보고한다.

## 2026-10-22 — Catalog CI false-positive 수정 및 원격 확인

- 시작 시 격리 clone `/tmp/kuran-p0-checkpoint`의 원격 `work` SHA는 `940d8a0d5ab5fcf3832983e44a1ad88bd7597ef3`, `main`은 `ee02a3657448d563508687614a246e05ac61eecd`였다. 원래 `/workspace/japan-premium-commerce`의 미커밋 코드·스크린샷은 읽기만 했으며 기존 named volume, DB와 `main`은 변경하지 않았다.
- cloud environment status는 revision 2가 활성 관측 상태이며 revision 3 적용 증거가 없다. 읽은 설정 draft는 revision 4이나 저장소 ref가 이전 SHA `2db98927a9ede2b2423456873f0994ddd19ffe4e`를 가리킨다. active network policy state는 `unknown`; draft/활성 설정은 수정하거나 게시하지 않았다.
- run `39759208949`는 `940d8a0`에서 synthetic parser 테스트가 exit 255로 실패했다. controller 화면의 이미지 메타데이터만 검사하려던 테스트가 전체 페이지에서 `amazon_jp` slug가 없어야 한다고 단언했지만, 화면에는 provider slug가 포함된 deduplication key도 정상 표시된다. 이 테스트 조건이 확인된 false-positive였다.
- `tests/catalog/admin_review_controller.php`는 deduplication key를 별도 확인하고 `이미지 메타데이터` 블록에서만 한국어 출처명을 검증하도록 수정했다. parser/controller production behavior는 바꾸지 않았다. CI 실패는 기존에 전체 로그를 그대로 출력하고 annotation 특수문자를 escape하지 않아 실제 원인을 보여주지 못했다. 실패 시 summary에는 최근 80줄, annotation에는 500자 이하 마지막 줄을 출력하고 `%`, CR, LF를 escape하며 PHP exit code를 보존하도록 보완했다. 회귀 계약은 먼저 실행해 `%25` 이스케이프가 없어 실패하는 RED를 확인한 뒤 수정 후 GREEN을 확인했다.
- `fix(ci): scope parser assertion and bound failure logs` 커밋 `5b2a1cb8d2193458a088174eb04228f252cd9e0e`를 `work`에 push했다. `git ls-remote`, fresh shallow clone `/tmp/ordenowa-remote-check`, 원격 파일 재조회 결과가 동일 SHA였다. 원격 `main`은 변하지 않았다.
- 새 parser run [39760154509](https://github.com/goldeget/japan-premium-commerce/actions/runs/39760154509)은 성공했다. 이는 PHP lint 및 synthetic Amazon Japan/Rakuten parser 검증이다. 실제 외부 상품 수집과 PrestaShop 네이티브 상품 등록은 0건/미검증이다.
- fresh-install run [39759208769](https://github.com/goldeget/japan-premium-commerce/actions/runs/39759208769)은 image build, isolated cache probe, 빈 볼륨 상점 시작, catalog 모듈 설치 및 PrestaShop 재시작 후 별도 queue 보존까지 통과했다. 공식 Japan Post archive download가 `curl_exit=22 http_status=503 effective_host=www.post.japanpost.jp`로 실패해 lookup/address/order/admin/restart 후속 검사는 건너뛰었다. 후속 run [39760154414](https://github.com/goldeget/japan-premium-commerce/actions/runs/39760154414)도 같은 HTTP 503으로 실패했으며 updater의 기존 `curl --retry 3 --retry-delay 2` 이후에도 지속됐다. 주소/주문 E2E는 여전히 검증되지 않았다.
- 최신 로컬 확인: business-profile Python 계약 10/10, admin-locale 13/13, fresh-install workflow 계약 12/12, `git diff --check`, `bash -n docker/kuranea-entrypoint.sh`, Compose 및 두 workflow YAML parse 통과. 호스트 PHP CLI가 없어 로컬 PHP 직접 실행은 하지 않았다. 로컬 운영 DB/컨테이너 변경과 브라우저 캡처는 없고 기존 KURANEA/ORDENOWA 자산 상태를 바꾸지 않았다.
