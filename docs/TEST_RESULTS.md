# KURANEA 테스트 결과

기준일: 2026-10-22

## 로컬 실행 결과

| 검사 | 결과 | 근거 |
| --- | --- | --- |
| Python smoke 및 계약 테스트 | PASS | 2026-10-22 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/smoke -p 'test_*.py' -v`: 33/33. 메뉴/푸터, 검색·빈 카테고리 상태 ja/en/ko 회귀 검사를 포함한다. |
| 관리자 번역 계약 테스트 | PASS | 2026-10-22 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/admin_locale -p 'test_*.py' -v`: 8/8. 전체 Back Office 번역 커버리지 검증은 아니다. |
| 우편번호 도메인·주소 검증 테스트 | PASS | 호스트에 PHP CLI가 없어 기존 PrestaShop 컨테이너의 임시 `/tmp` 경로에 테스트 소스만 복사해 실행했다. 정규화, 후보 검색, 복수 후보, 주소 일치/불일치, 건물 입력 및 수동 fallback 통과. 영구 프로젝트 파일/DB 변경 없음. |
| 우편번호 후보 API 단위 테스트 | PASS | 격리 테스트 더블에서 JSON 후보 및 `manual_entry_available` 응답 확인 |
| 공식 Japan Post KEN_ALL 데이터 및 DB API | PASS (기존 dev DB) | 공식 ZIP SHA-256 `c976cb0ff691a1aa7480b47b7e1f61bea08c2eadb3278f0366e474cd82dbf4b8`; CSV 124,840행 파싱, 고유 후보 124,839건 DB에 적재. HTTP에서 `1000004`/`100-0004`, 일본어 검색, `004-0000` 후보 2개 확인. 활성 주소 124,839행, staging 0행. |
| 주소 자동완성 브라우저 동작 | PASS (주소 폼 fixture) | 실제 사이트 origin의 모듈 JS와 DB API를 사용해 1440px·390px에서 우편번호 후보 적용, 일본어 검색, 중복 후보 선택, 건물명 편집 보존을 확인했다. JS page error 0건. 캡처 `artifacts/qa/phase1a/postcode-widget-desktop.png`, `postcode-widget-mobile.png`. 실제 checkout 경로가 아니므로 checkout 검증 PASS가 아니다. |
| 실제 Japan Post API 및 서버 주소 검증 | PASS (읽기 전용) | live DB에서 `1000004` → 東京都・千代田区・大手町 후보를 확인했다. 1000004/100-0004, 저장 전 시구정촌 불일치 거부, 선택 주소/건물 입력 허용, 후보가 없을 때 수동 입력 허용을 `tests/postcode/verify_live_address_validation.php`로 확인했다. 고객/주소/주문 데이터는 생성하지 않았다. |
| 관리자 대시보드 브라우저 | PASS (대시보드 한정) | 실제 한국어 관리자 로그인 후 PC 1440×1000에서 `lang=ko`, 대시보드 날짜 필드·요약 한국어, 메뉴, 공식 로그인 로고 기반을 확인했고 브라우저 오류 0건이었다. 캡처 `artifacts/qa/phase1a/admin-dashboard-korean-after-date-overlay.png`. 전체 관리자 100%는 아니다. |
| 우편번호 모듈 PHP 문법 검사 | PASS | 모듈 및 우편번호 테스트 PHP 파일 전체 lint |
| 셸/JavaScript/Compose 문법 | PASS | `bash -n`, `node --check`, `docker compose config --quiet` |
| 변경사항 공백 검사 | PASS | `git diff --check` |
| CI 진단 마스킹·워크플로우 계약 | PASS | 전체 smoke 28/28. startup/later-failure 경로, 민감값 마스킹, post-import staging 검사를 포함한다; workflow YAML 파싱 및 셸 구문 통과 |
| 컨테이너 상태 | PASS | PrestaShop 9.2.0 및 MariaDB 10.11 healthy |
| JPY DB 설정 | PASS | DB 읽기 전용 조회에서 JPY 활성·0자리·기본값, ja/en/ko 통화명 확인; EUR/USD 비활성 |
| 기존 DB 재시작 보존 | PASS | 기존 MariaDB/PrestaShop 컨테이너를 재시작한 뒤 HTTP 200, 양쪽 healthy, JPY 기본값과 3개 언어 행을 읽기 전용 확인 |
| 로컬 DB 상품/주문 현황 | PASS | 읽기 전용 조회 결과 상품 0건, 주문 0건 |
| 빈 카탈로그·검색·푸터 다국어 화면 | PASS | 홈/카테고리/검색/푸터를 실제 PrestaShop+Chromium에서 ja/en/ko로 확인했다. 검색/카테고리 HTTP 200, 홈에서 320–1920px 10개 폭 가로 넘침 없음, PC·모바일 캡처를 `artifacts/qa/phase1a/`에 저장했다. 현재 상품이 없어 카드·상세 상태의 실제 상품 렌더링은 검증할 수 없다. |

## 제한 또는 실패

| 검사 | 결과 | 상세 |
| --- | --- | --- |
| 신규 빈 볼륨 설치 | FAIL / 추적 중 | run #20 `39701883450`, #19 `39701310507`, #18 `39701030162`가 `Build and install into unique empty volumes` 단계에서 실패했다. GitHub 공개 페이지에서 상세 stderr/artifact를 읽지 못해 정확한 원인 및 `errno 28` 여부를 확정하지 않았다. 신규 설치 PASS가 아니다. |
| 신규 설치 DB 적재 및 API lookup | BLOCKED | 기존 dev DB에서는 공식 데이터를 가져와 실제 HTTP lookup을 확인했다. 격리 CI 실패로 새 빈 DB import/조회는 검증하지 못했다. |
| 실제 checkout 주소 저장, 주문 및 관리자 주문 표시 | 미실행 | 주소 위젯 브라우저는 checkout 대신 폼 fixture이며, live 서버 검증은 읽기 전용이다. 기존 DB에 테스트 고객/주소/주문을 만들지 않았다. 격리 CI 네이티브 Address 저장 스크립트도 설치 실패로 실행되지 않았다. |
| PC/모바일 browser regression | 부분 PASS | 홈 빈 카탈로그 안내는 PC 1440px·모바일 390px에서 실제 렌더링했다. 화면별 증거는 위 캡처를 참조한다. 전체 반응형 폭 테스트와 상품 상세·주문 화면은 별도 미완료다. |
| 관리자 한국어 100% | 미완료 | 로그인과 대시보드에서 한국어 메뉴·날짜 범위를 실제 브라우저로 확인했다. 모듈 계약 테스트는 8/8이지만 전체 메뉴, 모든 설정·주문관리·모듈 화면은 아직 범위별 audit을 하지 않았다. |
| PWA 기기 설치 | 미실행 | manifest/service worker 정적 검증은 있지만 iOS/Android 홈 화면 설치 테스트는 없다. |
| Docker 신규 설치/재빌드 | 미실행 | 작업공간 overlay 91 MB 여유(사용률 100%), inode 95%다. `docker system df -v`: 활성 PrestaShop/MariaDB 이미지와 named volume, 빌드 캐시 8.284 MB, 출처 불명 미연결 254 MB volume을 확인했다. 기존 데이터와 볼륨은 보존했고 prune·재빌드를 하지 않았다. |
| Cloud config revision 3 | 미확인/불일치 | 현재 environment status는 revision 2를 보고한다. revision 3 적용을 주장하지 않는다. |

새 기능의 최종 PASS는 반드시 실제 격리 환경 및 해당 기능의 end-to-end 검증으로 기록한다.
