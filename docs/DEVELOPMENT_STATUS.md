# ORDENOWA 개발 현황

## 최신 이어가기 기준 (2026-10-23 02:33 UTC)

작업 브랜치: **work**
최신 기능 코드 및 full Chromium 검증 SHA: **dfa30a1127a50d2eb4926d7c1fb6d75030a64121**
`main`: **ee02a3657448d563508687614a246e05ac61eecd** (수정하지 않음)

### 현재 검증 현황

| 영역 | 상태 | 근거와 한계 |
| --- | --- | --- |
| ORDENOWA 브랜드 자산 | 브라우저 PASS | ZIP 22개 항목 CRC, 원본 3종·파생 17종 SHA-256 및 KURANEA 백업을 검증했다. #39888149608 Steps 28–29와 #39889443441 Steps 28–29에서 업로드·초안·미리보기·게시·교체복원, PC·모바일·관리자 로그인·favicon·Apple·PWA·OG·SEO 이미지 출력 및 Mailpit 재설정 이메일 로고가 통과했다. #39889264268과 #39889443441의 Step 28에서 영문 공개 페이지 브랜드/SEO/PWA 검사가, Step 41에서 필수 캡처 gate가 통과했다. |
| 회원 계정 | Chromium PASS | #39888149608, #39889264268, #39889443441 Step 30 및 각 전체 aggregate에서 가입·이메일 로그인·로그아웃·비밀번호 재설정·마이페이지가 통과했다. #39888370630의 `account=failure`는 reset 이후 이전 로그인 오류 상태 오판이었다. `dfa30a1`은 검증된 로그인 URL을 다시 열고 오류 알림 부재를 확인하도록 수정했고 #39889443441에서 통과했다. |
| 한국어 관리자 상품 | Chromium PASS | #39888149608, #39889264268, #39889443441 Step 31에서 실제 관리자 상품 생성·수정과 옵션별 재고 확인이 성공했다. 등록 fixture는 비활성이고 checkout 검증은 별도의 활성 synthetic CI 상품을 사용했다. |
| 상품·장바구니·무결제 주문 | Chromium PASS | #39888149608, #39889264268, #39889443441 Steps 32–39에서 검색·상품 상세·장바구니, PC·모바일 일본 주소 주문, 오프라인 `ps_checkpayment` 저장, 별도 관리자 주문 조회와 checkout fail-closed 복구가 통과했다. 실결제는 실행하지 않았다. |
| 스크린샷·재시작·주소 데이터 | 전체 coverage PASS | #39888149608, #39889264268, #39889443441 screenshot coverage, 빈 설치 재시작, Japan Post import 및 전국 주소 수 검사가 통과했다. #39888370630은 계정 실패 뒤 진단 fallback만 실행해 전체 screenshot coverage를 인증하지 않았다. |
| 한국어 운영·SEO·PWA 설정 | 브라우저 설정 흐름 PASS, 운영 일부 미검증 | c078 브랜드 관리자 화면은 회사·고객지원·배송/환불 문구·SEO·PWA 필드를 저장·재조회·미리보기·게시하고 공개 출력을 확인했다. 배송 정책 편집과 관리자 배송 화면 연결을 확인했지만 배송 요율 변경, 환불 거래, iOS/Android 홈 화면 설치는 테스트하지 않았다. |
| Codex Cloud 실행 범위 | Docker 빌드 미실행 | 이미지·DB·Mailpit·Chromium 검증은 GitHub Actions에서 수행한다. Codex Cloud의 `vfs`/32 GB 제한을 넘기는 빌드, 운영 배포, 실결제는 실행하지 않았다. |

### 최신 GitHub Actions

- [dfa30a1 — Isolated fresh install #39889443441](https://github.com/goldeget/japan-premium-commerce/actions/runs/39889443441): 전체 PASS. Steps 28–30 브랜드·메일·계정, 31–39 상품·장바구니·일본 무결제 주문·관리자 조회·checkout 복구, 40–41 캡처/coverage, 42 재시작, 43–44 Japan Post, 45 aggregate가 성공했다. Step 35 진단은 조건부 건너뜀이다.
- [021214d — Isolated fresh install #39889264268](https://github.com/goldeget/japan-premium-commerce/actions/runs/39889264268): 전체 PASS. 영문 브랜드 검사와 필수 screenshot gate를 포함한 브라우저, 계정, 상품, 주문, 재시작 및 주소 데이터 단계가 성공했다. Step 35 진단은 조건부 건너뜀이다.
- [021214d — Offline catalog parser #39889264241](https://github.com/goldeget/japan-premium-commerce/actions/runs/39889264241): PASS (범위 제한). PHP lint/parser와 fresh-install 계약 검사; 통합 설치/브라우저 QA 판정은 아니다.
- [49bad87 — Isolated fresh install #39888370630](https://github.com/goldeget/japan-premium-commerce/actions/runs/39888370630): FAIL; aggregate는 `account=failure`. 계정 진단은 `/ko/`에서 `authenticated`와 사용자 메뉴 표시를 확인했고 이전 로그인 오류 알림과 인증 후 결과의 오판 경계가 드러났다. 브랜드·상품·무결제 주문·스크린샷·재시작·주소 단계는 통과했다.
- [60a82f3 — Isolated fresh install #39888149608](https://github.com/goldeget/japan-premium-commerce/actions/runs/39888149608): 전체 PASS. 브랜드·메일·계정·상품·무결제 주문·관리자 조회·전체 screenshot gate·재시작·Japan Post 단계가 통과했다. Step 35 진단은 조건부 건너뜀이다.
- [8423011 — Isolated fresh install #39879610940](https://github.com/goldeget/japan-premium-commerce/actions/runs/39879610940): completed FAIL, raw aggregate `account=failure`만 남았다. 브랜드·상품·장바구니·무결제 주문/관리자 조회·전체 screenshot coverage·재시작·Japan Post 검사는 통과했다. 회원은 동의 선택 뒤 `email_login`의 구체 하위 대기에서 timeout됐으며 비밀번호 재설정은 수행되지 않았다.
- [9525b37 — Isolated fresh install #39879191400](https://github.com/goldeget/japan-premium-commerce/actions/runs/39879191400): completed FAIL, raw aggregate `account=failure`만 남았다. PC·모바일 `/identity`에서 실제 필수 입력 `psgdpr`가 비어 있었고, 초록 Step 30은 이 실패를 덮지 않았다. 이 커밋은 잘못된 selector를 사용했다.
- [9525b37 — Offline catalog parser #39879191441](https://github.com/goldeget/japan-premium-commerce/actions/runs/39879191441): PASS (범위 제한). 통합 설치/브라우저 QA 판정은 아니다.
- [c078b38 — Isolated fresh install #39878462667](https://github.com/goldeget/japan-premium-commerce/actions/runs/39878462667): raw aggregate FAIL, `account=failure`만 남았다. 실제 invalid control은 `name=psgdpr`; 초록색 browser step은 이 annotation을 덮지 않는다. Brand/email, product, cart/order/admin, fail-closed, screenshot, restart 및 KEN_ALL 단계에는 실패 annotation이 없다.
- [c078b38 — Offline catalog parser #39878462635](https://github.com/goldeget/japan-premium-commerce/actions/runs/39878462635): PASS (범위 제한).

### 최근 기능 커밋

| 커밋 | 변경 | 검증 |
| --- | --- | --- |
| `dfa30a1` | 이전 비밀번호 거부 화면을 닫고 검증된 한국어 로그인 URL에서 새 비밀번호를 제출하도록 계정 QA 수정 | 회귀 계약 RED→GREEN, 계정 계약 22개, 오프라인 전체 304개, Python 구문 통과. #39889443441 full Chromium QA PASS. |
| `021214d` | 영문 고객 페이지 SEO·OG·JSON-LD·manifest·브랜드 이미지 검사와 필수 캡처 추가 | 브랜드/SEO 계약 및 오프라인 전체 303개 통과. #39889264268 full Chromium QA PASS; Offline parser PASS. |
| `49bad87` | 재설정 뒤 로그인 실패 지점을 안전한 하위 상태로 진단 | #39888370630에서 이전 로그인 오류 알림과 인증 결과 충돌 확인; diagnostic-only CI 실패. |
| `60a82f3` | 한국어 가입 경로 언어 보존 검사 | #39888149608 full fresh-install Chromium QA PASS. |
| `cf3c413` | 로그인·로그아웃의 브라우저 결과를 검증 | #39887294434에서 계정 실패가 재현되어 후속 진단 수행. |
| `f6dd110` | email login/logout/authentication 대기 결과를 분리하고 개인정보 없는 CI 상태 진단 추가 | 계약·오프라인 검사 및 범위 제한 parser workflow 통과. |
| `8423011` | 계정 QA가 실제 필수 `/identity` 입력 `psgdpr`를 선택하도록 수정 | 회귀 계약을 먼저 RED로 확인한 뒤 수정. 동의 선택 오류는 사라졌으나 #39879610940에서 계정 login 단계 timeout으로 aggregate 실패. |
| `9525b37` | 프로필 동의 체크박스 직접 클릭 및 상태 확인 | Fresh-install #39879191400 raw aggregate `account=failure`; PC·모바일에서 `psgdpr`가 계속 선택되지 않았다. 잘못된 selector였다. |
| `c078b38` | PrestaShop 현지화된 재설정 경로를 메일·브라우저 검증과 일치 | 브랜드와 주문 흐름 단계 성공; aggregate의 유일 실패는 계정 `psgdpr` 입력 선택. |
| `143d984` | 인증 전 관리자 로그인 로고 URL 캡처 | 후속 c078 run의 brand/login 검증에는 실패 annotation이 없었다. |

## 이전 완료 기준 결과

- `b58a2eb`의 #656은 `account=failure` raw aggregate였고 brand upload/publish와 product/cart/order 경로 단계가 성공했다.
- `fc00804`의 #662은 `account=failure`; 한국어 login form/email-label assertions 뒤 reset-link polling 중 controller 404 → 일본어 경로 302가 관측됐다. 원인은 미확정이며 Mailpit logo assertion은 실행되지 않았다.
- `f8719ee`의 #670은 `shipping_admin=failure account=failure`; 배송 요율을 바꾸지 않았다.
- `761cc62`의 #835는 `brand=failure shipping_admin=failure account=failure`; brand replacement timeout이 보고됐다.
- Scope-limited SEO, business-profile, parser workflows는 각각의 계약 범위에서 PASS이며 전체 fresh-install/browser QA를 대체하지 않는다.

## 실행 기반

- PrestaShop 9.2.0, Hummingbird 2.1.2, MariaDB 10.11, Docker Compose를 사용한다. 개발 포트는 `127.0.0.1:8080`에 바인딩된다.
- Codex Cloud는 코드 분석·수정·Python 계약 테스트에 사용한다. 이 런타임은 Docker `vfs` storage driver와 32 GB 파일시스템을 사용하며 PrestaShop 이미지 빌드가 공간 부족으로 실패했다. 호스트 기본 PHP CLI는 없지만, 서명된 배포판 패키지를 격리 경로 `/tmp/brand-php-runtime`에서 검증한 PHP 8.4/GD 런타임으로 사업자 프로필 PHP 계약을 실행했다. 시스템 패키지는 설치하지 않았다. 여기서 Docker 빌드·Compose 구동을 반복하지 않고, 이미지·DB·Chromium 검증은 격리된 GitHub Actions에서 수행한다.
- 현재 작업트리는 `/workspace/japan-premium-commerce`의 `work`다. 미추적 `tests/admin_locale/__pycache__/`, `tests/business_profile/__pycache__/`, `tests/e2e/__pycache__/`, `tests/postcode/__pycache__/`, `tests/smoke/__pycache__/`는 삭제하지 않았다. `main` SHA `ee02a3657448d563508687614a246e05ac61eecd`는 보존한다. 이 설정 작업에서 컨테이너나 named volume을 만들거나 초기화하지 않았다.

## 구현 상태 기록 (이전 관찰)

| 영역 | 상태 | 확인 내용 |
| --- | --- | --- |
| ORDENOWA 공식 이미지 | BLOCKED | 세 이미지 미리보기는 대화에 표시되지만 첨부 다운로드가 `cannot create attachment directory: Not a directory`로 실패했고 로컬 원본 바이트를 찾지 못했다. 저장소에는 KURANEA 원본만 있어 이를 보존했다. ORDENOWA 로고·파비콘·PWA 아이콘은 생성·교체하지 않았다. |
| 쇼핑몰 운영 설정 모듈 | 코드·CI PASS, 실제 운영 화면 QA 미완료 | 한국어 설정 폼, 다국어 브랜드·회사 참조/판매자 분리, 이미지 업로드 파생물, 초안·게시·이력·복원, 공개 법률 페이지·푸터·SEO·manifest·메일 연결이 있다. bank transfer는 사용 여부와 계좌 연결을 별도로 선택하고 선택된 활성 계좌 하나만 공개한다. CI run `39757526475`에서 PHP lint와 모듈·법률·메일 계약이 통과했다. 실제 관리자 브라우저 저장·미리보기·게시 및 세 언어 확인은 미실행이다. |
| SEO 메타데이터 보안 | 소스 계약 CI PASS, 실제 Smarty 렌더링 QA 미실행 | Draft PR #3의 동적 title/description/robots/canonical/hreflang/Open Graph 이스케이프와 JSON-LD `JSON_HEX_TAG` 수정을 검토해 `000b066`에 반영했다. PWA script URL 속성도 HTML 이스케이프한다. 전용 Actions run `39786618881`의 2개 Python 계약 테스트와 기존 테마 계약 15개가 통과했다. |
| LOGISTEED 운영 법인 참조 | 초깃값 구성·미확인 | ロジスティード株式会社, LOGISTEED, Ltd., 법인번호·주소·대표전화·대표자를 참고정보로 분리했다. 실제 판매사업 정보는 별도 빈 설정이고 승인 상태는 pending이므로 공식 판매처 표기와 거래는 fail-closed다. |
| Storefront 및 반응형 | 기존 화면 일부 확인, ORDENOWA 최종 QA 미실행 | 일본어/영어/한국어 빈 카탈로그 화면과 반응형 자식 테마의 과거 캡처가 남아 있다. 현재 상품은 0개다. 이 작업에서 새로운 ORDENOWA 실제 브라우저 스크린샷, 상품 카드·상세·주문 여정은 확보하지 않았다. |
| JPY 기본 통화 | 설정 코드·이전 읽기 확인 | JPY 기본 통화와 ja/en/ko 표시명·0자리 정밀도 설정 코드가 있다. 최근 신규 설치 CI는 우편 CSV 단계에서 중단되어 이번 실행에서 JPY·테마·관리자 로그인 설정을 검증하지 못했다. |
| 일본 주소 자동완성 | 기존 DB/API 확인, 빈 설치·주문 E2E 미검증 | 7자리·하이픈·전각 숫자, 일본어 검색, 후보 선택, 수동 주소 입력, ja/en/ko를 지원한다. 이전 dev DB에 공식 KEN_ALL 고유 후보 124,839건이 있었고 읽기 전용 조회는 통과했다. 새 빈 설치 CI는 Japan Post가 HTTP 503을 반환해 import 이후 lookup·주소·주문 검사가 건너뛰어졌다. |
| 관리자 한국어 | 부분 적용, 100% 미완료 | 로그인·대시보드·주문 목록의 과거 PC/모바일 점검과 프로젝트 소유 Module Manager 표시명 수정이 있다. CI에서 운영 설정 폼 한국어 계약이 통과했다. 전체 PrestaShop core·모든 메뉴·상품/고객/주문/설정 화면의 100% 한국어와 현재 브라우저 검증은 미완료다. |
| PWA | manifest·service worker 기반, 공식 아이콘·기기 QA 미완료 | 동적 manifest 및 정적 자산 전용 offline page가 있으나 ORDENOWA 원본 이미지가 없어 아이콘 목록이 비어 있다. iOS·Android 실기기 설치도 미실행이다. |
| 카탈로그 파서·검수 | fixture parser CI PASS, 실제 상품 등록 미검증 | Amazon Japan/Rakuten HTML fixture 파서, 영속 JSON queue, TEST/DEMO 승인 서비스, 비활성 native product adapter 및 한국어 검수 탭이 있다. run `39760154509`에서 PHP 8.3 lint와 parser/관리자 계약이 성공했다. 빈 설치 CI의 카탈로그 모듈·queue 재시작 보존도 run `39759208769`에서 Japan Post 다운로드 단계 전까지 통과했다. 실제 PrestaShop 상품 생성·브라우저 검수는 아직 미검증이고 외부 수집 0건이다. |
| 실제 상품·주문 | 0건 / E2E 미실행 | 로컬 DB에서 상품·주문 0건으로 이전 확인됐다. 신규 설치 503 때문에 주소가 들어간 무결제 주문 저장·한국어 관리자 조회·재시작 보존은 이번 작업에서 확인되지 않았다. |
| 신규 설치 CI | FAIL / Japan Post HTTP 503 | run `39760154414`도 기존 `--retry 3`을 거친 뒤 공식 KEN_ALL 다운로드에서 `curl_exit=22 http_status=503 effective_host=www.post.japanpost.jp`로 실패했다. 앞선 이미지 build/cache/startup/catalog queue 검사가 통과했고, 주소 조회·주소/주문 저장·관리자 조회·최종 재시작 검사는 건너뛰었다. 반복 실행을 성공으로 취급하지 않으며 외부 주소 데이터 단계의 제한을 별도로 기록한다. |

## 이전 작업 기록

- `6f6ff5e`에서 synthetic Amazon Japan/Rakuten 파서를 파일 기반 검수 큐, 원자적 승인 서비스 및 숨김 상태 PrestaShop Product 등록 어댑터에 연결했다. 전용 Actions run `39756075106`은 PHP lint와 fixture 테스트에서 성공했지만 실제 PrestaShop DB 등록·관리자 화면은 검증되지 않았다.
- `ba508b4`에서 관리자 특정상거래법 라벨을 한국어로 바꿨다. 후속 run `39756576373`에서 다국어 필드에 붙는 `· 일본어`를 테스트 기대값이 빠뜨린 것이 확인되어 `3ec583c`에서 assertion을 수정했다. 그 뒤 CI는 법률 페이지에서 `<h1>` 제목이 렌더링되지 않는 실제 결함을 드러냈다.
- `3404116`은 PHP 예외를 Actions 요약에 노출하도록 진단을 보강했다. `7cf8c41`에서 localized `<h1>`와 bank-transfer 계좌 링크를 구현했고 business-profile Actions run `39757526475`는 PHP lint, 설정·법률·공개 프로필·메일 검사 모두 통과했다.
- `cc448a6`에서 두 프로젝트 모듈의 Module Manager 이름/설명을 한국어로 바꿨다. admin locale Python 검사 13/13, business-profile Python 계약 검사 10/10, fresh-install workflow 계약 10/10이 통과했다. 이 계약 테스트들은 실제 관리자 브라우저 UI 검증을 대신하지 않는다.
- `940d8a0`에서 카탈로그 파서 검수 모듈·한국어 Back Office 탭과 별도 named volume 영속 queue를 연결했다. fresh-install run `39759208769`에서 해당 모듈 설치와 PrestaShop 재시작 후 queue 유지가 확인됐지만 Japan Post HTTP 503 뒤 주소·주문 단계는 실행되지 않았다.
- run `39759208949`는 `amazon_jp`가 의도된 중복 키에도 나타나는데 페이지 전체에서 금지하던 과도한 assertion 때문에 실패했다. `5b2a1cb`에서 중복 키와 이미지 메타데이터의 출처 표기를 분리해 검사하고 실패 로그를 80줄/500자로 제한 및 GitHub annotation escape 처리했다. parser run `39760154509`가 성공했다. 이 수정은 실제 파서 로직을 바꾸지 않았다.
- fresh-install run `39760154414`도 공식 Japan Post host HTTP 503으로 종료됐다. `update-ken-all.sh`에 이미 `curl --retry 3 --retry-delay 2`가 있어 같은 동작의 재실행만으로는 해결되지 않는다. 이 run은 빈 설치의 전체 주문 E2E를 PASS로 만들지 못했다.
- fresh-install run `39756769346`은 빈 볼륨 Compose 기동까지 통과했으나 `www.post.japanpost.jp`가 HTTP 503을 반환해 KEN_ALL import 이후 주소·주문·재시작 단계를 수행하지 못했다. 해당 실패를 새 설치 PASS로 기록하지 않는다.
- ORDENOWA 이미지 3장은 대화 미리보기로 보이나 Sediment 파일 다운로드가 staging 오류로 실패했다. 저장소 `assets/brand/source/`의 KURANEA 원본은 보존했고, 이를 새 공식 로고로 가장하지 않았다.
- JPY 설정을 신규 설치 및 기존 설치 부트스트랩에 연결했다. DB에서 JPY 활성·기본값, ja/en/ko 통화명을 확인했고 상품/주문 수는 각각 0건임을 읽기 전용 조회로 확인했다.
- 우편번호 테스트는 `1000004` 샘플뿐 아니라 CP932 파싱, 전각 입력, 복수 후보, 후보 선택, 네이티브 주소 필드 및 수동 건물명 매핑을 포함한다.
- 관리자 계약 테스트는 특정 로그인·번역 오버레이만 확인한다. 전체 관리자 한국어 수용 기준을 충족한다고 표시하지 않는다.
- CI 실패 진단 스크립트는 로그를 stdout·요약·artifact에 쓰기 전에 자격 증명 형태를 가리고, 이후 설치 단계의 실패에도 같은 수집기를 사용한다. 테스트용 민감 문자열을 실제 로그와 요약에서 제거하는 회귀 검사를 추가했다.
- 2026-10-22: Hummingbird featured-products 모듈은 대상 상품이 없을 때 템플릿 렌더링 자체를 건너뛴다. 자식 테마 홈 템플릿에 일본어·영어·한국어 빈 카탈로그 안내를 배치했고, 실제 상품 목록이 렌더링되면 안내를 감추도록 했다. 최신 PC·모바일 캡처는 `artifacts/qa/phase1a/home-empty-state-desktop-v2.png`와 `home-empty-state-mobile-v2.png`다.
- 2026-10-22: 공식 KEN_ALL archive를 기존 모듈 importer로 개발 DB에 적재하고 API를 확인했다. 활성 데이터 124,839건, staging 0건이다. importer는 성공적으로 교체한 뒤에만 staging 복사본을 비우며 신규 설치 smoke도 이를 검사한다. 주소 위젯 캡처는 주소 폼 계약 fixture를 사용했으므로 실제 checkout 화면 증거는 아니다.
- 2026-10-22: 체크포인트 `2636d67`에서 일본어·영어·한국어 검색 및 빈 카테고리 상태, 푸터 접근성 문구를 보강했다. PC·모바일 화면을 실제 Chromium에서 확인하고 해당 캡처를 `artifacts/qa/phase1a/`에 저장했다.
- 2026-10-22: 체크포인트 `bb40026`에서 Japan Post 후보가 있는 경우 주소 저장 전에 도도부현·시구정촌·町域이 일치하는지 서버 검증한다. 테스트용 synthetic rows와 기존 dev DB의 실제 `1000004` 후보로 조회·오류·수동 fallback을 검증했다. live 검증은 DB를 변경하지 않았다.
- 2026-10-22: 체크포인트 `46fc912`에서 관리자 한국어 XLIFF overlay 도메인을 PrestaShop 표기와 맞추고, 대시보드의 영어 날짜 필드/요약을 KURANEA 모듈 JS로 번역했다. 실제 관리자 브라우저에서 PC 1440px, `lang=ko`, 날짜 입력/요약 한국어, JS 오류 0건을 확인했다. 전체 관리자 100% 한국어는 아직 아니다.
- 2026-10-22: `1f5f552`에서 격리 GitHub Actions에만 실행되는 일본 우편 주소 주문 저장 검증을 추가했다. 실행 ID와 Compose 프로젝트명이 일치하는 CI 가드, 오프라인 무결제 모듈, CI 전용 무료 배송사, 공식 `1000004` 주소, 수정 가능한 번지·건물명, 네이티브 Order와 관리자 주문 조회 주소 projection 검사를 포함한다. 로컬 PHP 컨테이너에서 문법만 검사했고, 스크립트는 운영 중인 dev DB에서 실행하지 않았다.
- 2026-10-22: 관리자 주문 목록을 인증된 메뉴 링크로 열어 데스크톱 1440×1000 및 모바일 390×844, HTTP 200, JS 오류 0건을 확인했다. 주문 0건이라 실제 배송지 행은 없으며 캡처는 `artifacts/qa/phase1a/admin-orders-list-korean-desktop-qa.png`, `admin-orders-list-korean-mobile-qa.png`다. 화면 전체 번역 상태와 빈 상태 삽화의 영어 샘플 문구는 후속 점검이 필요하다.
- 2026-10-22: 첨부 ZIP에 든 KURANEA 공식 로고·파비콘·PWA 원본 SHA-256을 저장소 `assets/brand/source/`와 비교해 세 파일 모두 일치함을 확인했다.
- 2026-10-22: 체크포인트 `06617f6`에서 Japan Post town 설명 접미어를 고객용 주소·API 후보에서 제거하고 `以下に掲載がない場合`를 빈 주소란으로 처리했다. 원본 공식 CSV 값은 변경하지 않는다. `a444238`은 실데이터 검사에서 `大手町` 정규화를 단언하고, `1690a07`은 안전한 공식 데이터 갱신 CLI와 6개 계약 테스트를 CI 앞단에 추가했다. 도메인·응답 fixture 테스트, 실제 dev DB 읽기 전용 주소 검증에서 통과했으며 고객/주소/주문 행은 생성하지 않았다.
- 2026-10-22: 시작 후 cloud status를 다시 읽었다. 활성 revision 2, 저장 draft revision 4이며 draft의 repository SHA는 이전 기준 `2db9892`다. revision 3 적용 증거는 없고 draft를 수정하거나 게시하지 않았다. active network status에서 `api.github.com`을 확인할 수 없어 실패 실행의 상세 로그는 계속 접근 불가다.
- 2026-10-22: 최신 Actions 진단에서 이전 `errno 28` 가정과 다른 직접 원인을 확인했다. PrestaShop `Install::finalize()`는 `/admin/`이 없으면 기본 target `admin-dev`를 사용하지만 Docker entrypoint가 설치 전에 관리자 폴더를 옮겼다. 첫 수정안 `175d75d`는 CI run `39727310686`에서 이미지 빌드와 사전 검사를 통과했으나 빈 설치 단계는 실패했다. 현재 환경에서 상세 로그가 제공되지 않아 이 시도의 실패 세부를 확정하지 않는다.
- 2026-10-22: 후속 수정안 `fcf78ad`는 `PS_FOLDER_ADMIN=admin-dev`를 사용해 Docker entrypoint가 실제 관리자 파일을 기본 설치 경로에 유지하고, 공식 post-install 이후 PHP 부트스트랩이 `admin-kuranea`로 이동해 assets를 설치한다. 정적 경로 계약 4/4 통과, 원격 CI run `39728912492`는 Compose의 빈 상점 시작에서 실패했다. 실패 artifact는 존재하지만 현재 환경에서 읽을 수 없어 새 직접 원인은 미확정이다.

## 이전 우선순위 기록

1. 코드 리뷰 후 수정 후보를 `work`에 원격 보존하고 신규 설치 Actions를 한 번 실행한다. 실제 결과로 빈 DB 설치 및 주문 E2E를 판정한다.
