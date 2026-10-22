# KURANEA 테스트 결과

기준일: 2026-10-22

## 로컬 실행 결과

| 검사 | 결과 | 근거 |
| --- | --- | --- |
| Python smoke 및 계약 테스트 | PASS | 2026-10-22 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/smoke -p 'test_*.py' -v`: 28/28. 신규 import 계약은 커밋 성공 뒤 staging 복사본이 비워지는지 검사한다. |
| 관리자 번역 계약 테스트 | PASS | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/admin_locale -p 'test_*.py' -v`: 6/6. 전체 Back Office 번역 커버리지 검증은 아니다. |
| 우편번호 도메인 테스트 | PASS | 기존 PrestaShop 컨테이너 PHP CLI에서 `tests/postcode/run.php` 실행 |
| 우편번호 후보 API 단위 테스트 | PASS | 격리 테스트 더블에서 JSON 후보 및 `manual_entry_available` 응답 확인 |
| 공식 Japan Post KEN_ALL 데이터 및 DB API | PASS (기존 dev DB) | 공식 ZIP SHA-256 `c976cb0ff691a1aa7480b47b7e1f61bea08c2eadb3278f0366e474cd82dbf4b8`; CSV 124,840행 파싱, 고유 후보 124,839건 DB에 적재. HTTP에서 `1000004`/`100-0004`, 일본어 검색, `004-0000` 후보 2개 확인. 활성 주소 124,839행, staging 0행. |
| 주소 자동완성 브라우저 동작 | PASS (주소 폼 fixture) | 실제 사이트 origin의 모듈 JS와 DB API를 사용해 1440px·390px에서 우편번호 후보 적용, 일본어 검색, 중복 후보 선택, 건물명 편집 보존을 확인했다. JS page error 0건. 캡처 `artifacts/qa/phase1a/postcode-widget-desktop.png`, `postcode-widget-mobile.png`. 실제 checkout 경로가 아니므로 checkout 검증 PASS가 아니다. |
| 우편번호 모듈 PHP 문법 검사 | PASS | 모듈 및 우편번호 테스트 PHP 파일 전체 lint |
| 셸/JavaScript/Compose 문법 | PASS | `bash -n`, `node --check`, `docker compose config --quiet` |
| 변경사항 공백 검사 | PASS | `git diff --check` |
| CI 진단 마스킹·워크플로우 계약 | PASS | 전체 smoke 28/28. startup/later-failure 경로, 민감값 마스킹, post-import staging 검사를 포함한다; workflow YAML 파싱 및 셸 구문 통과 |
| 컨테이너 상태 | PASS | PrestaShop 9.2.0 및 MariaDB 10.11 healthy |
| JPY DB 설정 | PASS | DB 읽기 전용 조회에서 JPY 활성·0자리·기본값, ja/en/ko 통화명 확인; EUR/USD 비활성 |
| 기존 DB 재시작 보존 | PASS | 기존 MariaDB/PrestaShop 컨테이너를 재시작한 뒤 HTTP 200, 양쪽 healthy, JPY 기본값과 3개 언어 행을 읽기 전용 확인 |
| 로컬 DB 상품/주문 현황 | PASS | 읽기 전용 조회 결과 상품 0건, 주문 0건 |
| 빈 카탈로그 다국어 화면 | PASS | Hummingbird가 상품이 없으면 featured-products 템플릿을 호출하지 않는 점을 확인하고, 자식 테마 홈에 일본어·영어·한국어 안내 및 검색 링크를 구현했다. localhost 실제 HTTP와 Chromium에서 각 언어 HTTP 200, 일본어 PC 1440px/모바일 390px, CSS 반응형 방향, 가로 넘침 없음, 브라우저 오류 0건을 확인했다. 캡처는 `artifacts/qa/phase1a/home-empty-state-desktop-v2.png`, `home-empty-state-mobile-v2.png`. |

## 제한 또는 실패

| 검사 | 결과 | 상세 |
| --- | --- | --- |
| 신규 빈 볼륨 설치 | FAIL | 최신 run `39697612835`가 `Build and install into unique empty volumes`에서 2분 38초 뒤 실패했다. run `39695971760`도 같은 단계에서 실패했다. 상세 로그를 이 환경에서 읽지 못해 정확한 원인 및 `errno 28` 여부를 확인하지 못했다. 신규 설치 PASS가 아니다. |
| 신규 설치 DB 적재 및 API lookup | BLOCKED | 기존 dev DB에서는 공식 데이터를 가져와 실제 HTTP lookup을 확인했다. 격리 CI 실패로 새 빈 DB import/조회는 검증하지 못했다. |
| 실제 checkout 주소 저장, 주문 및 관리자 주문 표시 | 미실행 | 브라우저 검증은 실제 checkout 대신 주소 폼 fixture를 썼다. 기존 DB에 테스트 고객/주문을 만들지 않았다. 격리 CI 네이티브 Address 저장 스크립트도 설치 실패로 실행되지 않았다. |
| PC/모바일 browser regression | 부분 PASS | 홈 빈 카탈로그 안내는 PC 1440px·모바일 390px에서 실제 렌더링했다. 화면별 증거는 위 캡처를 참조한다. 전체 반응형 폭 테스트와 상품 상세·주문 화면은 별도 미완료다. |
| 관리자 한국어 100% | 미실행 | 로그인과 계약된 문자열 일부만 확인했다. 전체 메뉴, 대시보드, 주요 설정은 수용 기준에 맞게 검증되지 않았다. |
| PWA 기기 설치 | 미실행 | manifest/service worker 정적 검증은 있지만 iOS/Android 홈 화면 설치 테스트는 없다. |
| Docker 재빌드 | 미실행 | workspace 여유 공간 117 MB, inode 사용률 95%다. 기존 이미지·볼륨을 지우지 않고 재빌드하지 않았다. |
| Cloud config revision 3 | 미확인/불일치 | 현재 environment status는 revision 2를 보고한다. revision 3 적용을 주장하지 않는다. |

새 기능의 최종 PASS는 반드시 실제 격리 환경 및 해당 기능의 end-to-end 검증으로 기록한다.
