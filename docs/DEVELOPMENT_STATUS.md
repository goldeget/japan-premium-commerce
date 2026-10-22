# ORDENOWA 개발 현황

기준일: 2026-10-22

작업 브랜치: `work`
검증된 코드 체크포인트 `work` SHA: `5b2a1cb8d2193458a088174eb04228f252cd9e0e`

## 실행 기반

- PrestaShop 9.2.0, Hummingbird 2.1.2, MariaDB 10.11, Docker Compose를 사용한다. 개발 포트는 `127.0.0.1:8080`에 바인딩된다.
- 현재 실행환경에서 `/workspace` overlay는 0 bytes 여유 공간(100%)이고 `/tmp`에는 약 12 GB가 남아 있다. Docker CLI는 있지만 PHP CLI는 없다. 기존 `kuranea-prestashop-1` 및 `kuranea-mariadb-1` 컨테이너는 unhealthy로 관찰됐다. `kuranea_mariadb_data`, `kuranea_prestashop_html` 및 출처 미확인 볼륨을 그대로 보존했으며 삭제·초기화·중지·prune을 하지 않았다. 신규 컨테이너 생성과 로컬 이미지 빌드는 시도하지 않았다.
- 원래 `/workspace/japan-premium-commerce` 작업트리는 `175d75dac132ddb0a8f54777519795208df8ae4d`에 있으며 미커밋 파일과 QA 산출물이 다수 있다. 이를 수정하지 않고 `/tmp/kuran-p0-checkpoint`에서 변경을 만들고 원격 `work`에 보존했다.
- `main`은 `ee02a3657448d563508687614a246e05ac61eecd` 상태로 보존한다.
- cloud environment revision 2가 활성·관측 상태다. revision 3 적용은 확인되지 않았다. 저장된 draft는 revision 4지만 저장소 ref가 이전 SHA `2db98927a9ede2b2423456873f0994ddd19ffe4e`를 가리킨다. 설정은 수정·게시하지 않았다. 활성 네트워크 정책 상태는 `unknown`이며 custom egress 목록은 `i18n.prestashop-project.org` 및 `www.post.japanpost.jp`(draft)와 다르다.

## 구현 상태

| 영역 | 상태 | 확인 내용 |
| --- | --- | --- |
| ORDENOWA 공식 이미지 | BLOCKED | 세 이미지 미리보기는 대화에 표시되지만 첨부 다운로드가 `cannot create attachment directory: Not a directory`로 실패했고 로컬 원본 바이트를 찾지 못했다. 저장소에는 KURANEA 원본만 있어 이를 보존했다. ORDENOWA 로고·파비콘·PWA 아이콘은 생성·교체하지 않았다. |
| 쇼핑몰 운영 설정 모듈 | 코드·CI PASS, 실제 운영 화면 QA 미완료 | 한국어 설정 폼, 다국어 브랜드·회사 참조/판매자 분리, 이미지 업로드 파생물, 초안·게시·이력·복원, 공개 법률 페이지·푸터·SEO·manifest·메일 연결이 있다. bank transfer는 사용 여부와 계좌 연결을 별도로 선택하고 선택된 활성 계좌 하나만 공개한다. CI run `39757526475`에서 PHP lint와 모듈·법률·메일 계약이 통과했다. 실제 관리자 브라우저 저장·미리보기·게시 및 세 언어 확인은 미실행이다. |
| LOGISTEED 운영 법인 참조 | 초깃값 구성·미확인 | ロジスティード株式会社, LOGISTEED, Ltd., 법인번호·주소·대표전화·대표자를 참고정보로 분리했다. 실제 판매사업 정보는 별도 빈 설정이고 승인 상태는 pending이므로 공식 판매처 표기와 거래는 fail-closed다. |
| Storefront 및 반응형 | 기존 화면 일부 확인, ORDENOWA 최종 QA 미실행 | 일본어/영어/한국어 빈 카탈로그 화면과 반응형 자식 테마의 과거 캡처가 남아 있다. 현재 상품은 0개다. 이 작업에서 새로운 ORDENOWA 실제 브라우저 스크린샷, 상품 카드·상세·주문 여정은 확보하지 않았다. |
| JPY 기본 통화 | 설정 코드·이전 읽기 확인 | JPY 기본 통화와 ja/en/ko 표시명·0자리 정밀도 설정 코드가 있다. 최근 신규 설치 CI는 우편 CSV 단계에서 중단되어 이번 실행에서 JPY·테마·관리자 로그인 설정을 검증하지 못했다. |
| 일본 주소 자동완성 | 기존 DB/API 확인, 빈 설치·주문 E2E 미검증 | 7자리·하이픈·전각 숫자, 일본어 검색, 후보 선택, 수동 주소 입력, ja/en/ko를 지원한다. 이전 dev DB에 공식 KEN_ALL 고유 후보 124,839건이 있었고 읽기 전용 조회는 통과했다. 새 빈 설치 CI는 Japan Post가 HTTP 503을 반환해 import 이후 lookup·주소·주문 검사가 건너뛰어졌다. |
| 관리자 한국어 | 부분 적용, 100% 미완료 | 로그인·대시보드·주문 목록의 과거 PC/모바일 점검과 프로젝트 소유 Module Manager 표시명 수정이 있다. CI에서 운영 설정 폼 한국어 계약이 통과했다. 전체 PrestaShop core·모든 메뉴·상품/고객/주문/설정 화면의 100% 한국어와 현재 브라우저 검증은 미완료다. |
| PWA | manifest·service worker 기반, 공식 아이콘·기기 QA 미완료 | 동적 manifest 및 정적 자산 전용 offline page가 있으나 ORDENOWA 원본 이미지가 없어 아이콘 목록이 비어 있다. iOS·Android 실기기 설치도 미실행이다. |
| 카탈로그 파서·검수 | fixture parser CI PASS, 실제 상품 등록 미검증 | Amazon Japan/Rakuten HTML fixture 파서, 영속 JSON queue, TEST/DEMO 승인 서비스, 비활성 native product adapter 및 한국어 검수 탭이 있다. run `39760154509`에서 PHP 8.3 lint와 parser/관리자 계약이 성공했다. 빈 설치 CI의 카탈로그 모듈·queue 재시작 보존도 run `39759208769`에서 Japan Post 다운로드 단계 전까지 통과했다. 실제 PrestaShop 상품 생성·브라우저 검수는 아직 미검증이고 외부 수집 0건이다. |
| 실제 상품·주문 | 0건 / E2E 미실행 | 로컬 DB에서 상품·주문 0건으로 이전 확인됐다. 신규 설치 503 때문에 주소가 들어간 무결제 주문 저장·한국어 관리자 조회·재시작 보존은 이번 작업에서 확인되지 않았다. |
| 신규 설치 CI | FAIL / Japan Post HTTP 503 | run `39760154414`도 기존 `--retry 3`을 거친 뒤 공식 KEN_ALL 다운로드에서 `curl_exit=22 http_status=503 effective_host=www.post.japanpost.jp`로 실패했다. 앞선 이미지 build/cache/startup/catalog queue 검사가 통과했고, 주소 조회·주소/주문 저장·관리자 조회·최종 재시작 검사는 건너뛰었다. 반복 실행을 성공으로 취급하지 않으며 외부 주소 데이터 단계의 제한을 별도로 기록한다. |

## 최근 작업

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

## 다음 우선순위

1. 코드 리뷰 후 수정 후보를 `work`에 원격 보존하고 신규 설치 Actions를 한 번 실행한다. 실제 결과로 빈 DB 설치 및 주문 E2E를 판정한다.
