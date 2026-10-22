# KURANEA 테스트 결과

기준일: 2026-10-22

## 로컬 실행 결과

| 검사 | 결과 | 근거 |
| --- | --- | --- |
| Python smoke 및 CI 계약 테스트 | PASS | 2026-10-22 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/smoke -p 'test_*.py' -v`: 34/34. 일본 주소 주문 검사가 GitHub CI 프로젝트에서만 실행되는지 guard 계약도 포함한다. |
| 관리자 번역 계약 테스트 | PASS | 2026-10-22 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/admin_locale -p 'test_*.py' -v`: 8/8. 전체 Back Office 번역 커버리지 검증은 아니다. |
| Japan Post 데이터 갱신 CLI 계약 테스트 | PASS | 2026-10-22 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/postcode -p 'test_*.py' -v`: 6/6. 공식 URL, TLS 리다이렉트 제한, ZIP/CSV 검증, 실패 시 importer 미호출, 임시 파일 제거를 stubs로 확인했다. 실제 다운로드/import는 실행하지 않았다. |
| 우편번호 도메인·주소 검증 테스트 | PASS | 호스트에 PHP CLI가 없어 기존 PrestaShop 컨테이너의 임시 `/tmp` 경로에 테스트 소스만 복사해 실행했다. 정규화, 후보 검색, 복수 후보, 주소 일치/불일치, 건물 입력 및 수동 fallback 통과. 영구 프로젝트 파일/DB 변경 없음. |
| 우편번호 후보 API 단위 테스트 | PASS | 격리 테스트 더블에서 JSON 후보 및 `manual_entry_available` 응답 확인 |
| 공식 Japan Post KEN_ALL 데이터 및 DB API | PASS (기존 dev DB) | 공식 ZIP SHA-256 `c976cb0ff691a1aa7480b47b7e1f61bea08c2eadb3278f0366e474cd82dbf4b8`; CSV 124,840행 파싱, 고유 후보 124,839건 DB에 적재. HTTP에서 `1000004`/`100-0004`, 일본어 검색, `004-0000` 후보 2개 확인. 활성 주소 124,839행, staging 0행. |
| 주소 자동완성 브라우저 동작 | PASS (주소 폼 fixture) | 실제 사이트 origin의 모듈 JS와 DB API를 사용해 1440px·390px에서 우편번호 후보 적용, 일본어 검색, 중복 후보 선택, 건물명 편집 보존을 확인했다. JS page error 0건. 캡처 `artifacts/qa/phase1a/postcode-widget-desktop.png`, `postcode-widget-mobile.png`. 실제 checkout 경로가 아니므로 checkout 검증 PASS가 아니다. |
| 실제 Japan Post API 및 서버 주소 검증 | PASS (읽기 전용) | 기존 dev DB의 공식 `1000004` 행을 새 모듈 소스로 검증했다. 입력 주소 `address1=大手町`, 1000004/100-0004, 저장 전 시구정촌 불일치 거부, 선택 주소/건물 입력 허용, 후보 미존재 시 수동 입력을 확인했다. 테스트 고객/주소/주문은 생성하지 않았다. |
| Japan Post 후보 응답 town 정규화 | PASS | PHP controller fixture의 원본 town `テスト町（次のビルを除く）`가 API 응답 `テスト町`으로 직렬화되는 것을 확인했다. GitHub Actions에서도 실제 `1000004` 응답 town을 `大手町`와 정확히 비교하도록 했다. |
| 실제 Japan Post HTTP 후보 API | PASS (기존 dev DB, 읽기 전용; 기존 런타임 소스) | 기존 API에서 `1000004`와 `100-0004`, `千代田区大手町`, 중복 `004-0000` 2건, 미일치 검색 0건 및 `manual_entry_available=true`를 확인했다. 이 API 캡처는 수정 전 런타임이므로 접미어 제거 검증은 새 PHP 소스의 controller fixture와 read-only 통합 검사로 별도 확인했다. |
| 공식 Japan Post 갱신 CLI | 구현·계약 테스트 PASS, 실제 download/import 미실행 | `modules/kuraneapostcode/bin/update-ken-all.sh`는 Japan Post 공식 HTTPS ZIP을 검증한 다음 기존 트랜잭션 importer를 호출한다. 신규 6개 테스트는 fake curl/unzip/php만 사용했다. 기존 dev 주소 DB를 다시 쓰지 않았다. |
| 우편번호 주문 검증 스크립트 | PASS (문법·가드만) | `tests/postcode/verify_native_order_persistence.php`를 기존 컨테이너에 임시 복사해 `php -l` 통과. 주문 검증은 실행하지 않았고 활성 DB 주문 수는 0건 그대로다. |
| 관리자 대시보드 및 주문 목록 브라우저 | 부분 PASS | 한국어 관리자 로그인 뒤 주문 목록 메뉴 링크에서 PC 1440×1000·모바일 390×844 HTTP 200, 제목/메뉴/본문 한국어, JavaScript 오류 0건을 확인했다. 실제 주문이 0건이라 배송지 주문 행은 미검증이다. 캡처 `artifacts/qa/phase1a/admin-orders-list-korean-desktop-qa.png`, `admin-orders-list-korean-mobile-qa.png`. 전체 관리자 100%는 아니다. |
| 우편번호 모듈 PHP 문법 검사 | PASS | 모듈 및 우편번호 테스트 PHP 파일 전체 lint |
| 셸/JavaScript/Compose 문법 | PASS | `bash -n`, `node --check`, `docker compose config --quiet` |
| 변경사항 공백 검사 | PASS | `git diff --check` |
| CI 진단 마스킹·워크플로우 계약 | PASS | smoke 34/34. 분리된 설치 단계, 실패 진단, 민감값 마스킹, 공식 주소 importer, 격리 주문 검증 가드를 포함한다. |
| 컨테이너 상태 | PASS | PrestaShop 9.2.0 및 MariaDB 10.11 healthy |
| JPY DB 설정 | PASS | DB 읽기 전용 조회에서 JPY 활성·0자리·기본값, ja/en/ko 통화명 확인; EUR/USD 비활성 |
| 기존 DB 재시작 보존 | PASS | 기존 MariaDB/PrestaShop 컨테이너를 재시작한 뒤 HTTP 200, 양쪽 healthy, JPY 기본값과 3개 언어 행을 읽기 전용 확인 |
| 로컬 DB 상품/주문 현황 | PASS | 읽기 전용 조회 결과 상품 0건, 주문 0건 |
| 빈 카탈로그·검색·푸터 다국어 화면 | PASS | 홈/카테고리/검색/푸터를 실제 PrestaShop+Chromium에서 ja/en/ko로 확인했다. 검색/카테고리 HTTP 200, 홈에서 320–1920px 10개 폭 가로 넘침 없음, PC·모바일 캡처를 `artifacts/qa/phase1a/`에 저장했다. 현재 상품이 없어 카드·상세 상태의 실제 상품 렌더링은 검증할 수 없다. |

## 제한 또는 실패

| 검사 | 결과 | 상세 |
| --- | --- | --- |
| 신규 빈 볼륨 설치 | FAIL / 추적 중 | run `39703327857`과 `39704824787`은 이미지 빌드·격리 cache 권한 probe PASS 후 `Start the empty-volume shop`에서 실패했다. 공개 실행 페이지에서 후속 runs `39705702536`, `39706052890`, `39706126218`도 Failure로 확인했다. 최신 run(`1690a07`, 2분 39초)의 진단 artifact는 3.37 KB지만, 로그 화면 로그인 요구·GitHub API 403·익명 artifact 다운로드 404로 세부 로그를 읽지 못했다. 최신 실패 단계와 `errno 28` 여부는 확정하지 않으며 신규 설치 PASS가 아니다. |
| 신규 설치 DB 적재 및 API lookup | BLOCKED | 기존 dev DB에서는 공식 데이터를 가져와 실제 HTTP lookup을 확인했다. 격리 CI 실패로 새 빈 DB import/조회는 검증하지 못했다. |
| checkout 주문 연결 및 관리자 배송지 | 미실행 | 무결제 네이티브 Order 생성, `id_address_delivery` 연결, PrestaShop 관리자 조회 주소 formatter를 검사하는 CI 전용 스크립트를 추가·원격 저장했고 PHP 문법 및 격리 가드만 확인했다. 실제 검증은 새 빈 설치 CI가 먼저 통과해야 한다. 브라우저 checkout 경로는 아직 주소 폼 fixture만 검증했다. |
| PC/모바일 browser regression | 부분 PASS | 홈 빈 카탈로그 안내는 PC 1440px·모바일 390px에서 실제 렌더링했다. 화면별 증거는 위 캡처를 참조한다. 전체 반응형 폭 테스트와 상품 상세·주문 화면은 별도 미완료다. |
| 관리자 한국어 100% | 미완료 | 로그인과 대시보드에서 한국어 메뉴·날짜 범위를 실제 브라우저로 확인했다. 모듈 계약 테스트는 8/8이지만 전체 메뉴, 모든 설정·주문관리·모듈 화면은 아직 범위별 audit을 하지 않았다. |
| PWA 기기 설치 | 미실행 | manifest/service worker 정적 검증은 있지만 iOS/Android 홈 화면 설치 테스트는 없다. |
| Docker 신규 설치/재빌드 | 미실행 | 현재 작업공간 overlay 여유는 약 86 MB(사용률 100%), inode 95%다. Docker 이미지·캐시·named volume을 조사했다. 기존 데이터와 볼륨은 보존했고 prune·재빌드를 하지 않았다. |
| Cloud config revision 3 | 미적용 | 활성 status는 revision 2/observed 2다. 저장 draft는 revision 4이며 repository ref가 과거 `2db9892`로 현재 `work`보다 뒤처진다. active egress에서 `api.github.com`을 허용한 evidence가 없어 CI 상세 로그를 직접 조회하지 못했다. 설정은 수정/게시하지 않았다. |

새 기능의 최종 PASS는 반드시 실제 격리 환경 및 해당 기능의 end-to-end 검증으로 기록한다.
