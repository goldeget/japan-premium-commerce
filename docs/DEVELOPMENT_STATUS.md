# KURANEA 개발 현황

기준일: 2026-10-22

작업 브랜치: `work`
마지막 검증 원격 코드 체크포인트 SHA: `994a3f6b12a3b12d022dcebdc4fbbc7c09c17722`

## 실행 기반

- PrestaShop 9.2.0, Hummingbird 2.1.2, MariaDB 10.11, Docker Compose를 사용한다.
- 마지막 확인에서 PrestaShop은 healthy, MariaDB는 unhealthy였다. 쇼핑몰 개발 포트는 `127.0.0.1:8080`에 바인딩돼 있으며 기존 컨테이너와 데이터 볼륨은 건드리지 않았다.
- `main`은 `ee02a3657448d563508687614a246e05ac61eecd` 상태로 보존한다.
- 이 Codex 환경에서 관측한 cloud environment `spec_revision=2`, `observed_spec_revision=2`다. 이후 개정 설정이 실제 적용되지 않았다. 읽기 draft revision 4는 이전 SHA `2db98927a9ede2b2423456873f0994ddd19ffe4e`를 고정하며, 활성 사용자 지정 egress는 `i18n.prestashop-project.org`뿐이다. draft를 현재 SHA와 필요한 개발 도메인으로 갱신하는 작업은 아직 게시 전이다.
- 호스트 작업공간 overlay는 여유 블록 0 bytes, inode 사용률 100%(약 7천 개 여유)로 고갈됐다. Docker에는 이미지 2.216 GB, 활성 volume 1.114 GB, build cache 8.284 MB가 있다. 활성 named volume `kuranea_mariadb_data`, `kuranea_prestashop_html`과 출처가 확인되지 않은 세 번째 volume을 보존했다. Docker prune, 기존 volume 삭제·초기화, 로컬 재빌드는 하지 않았다. 마지막 관찰에서 MariaDB healthcheck는 unhealthy였고 PrestaShop은 healthy였다.

## 구현 상태

| 영역 | 상태 | 확인 내용 |
| --- | --- | --- |
| KURANEA 공식 브랜드 | 완료 | 첨부한 3개 원본 ZIP과 저장소 `assets/brand/source/` SHA-256이 모두 일치한다. 파생 로고·아이콘은 storefront 및 관리자 로그인에 적용했다. |
| 일본어 storefront 및 반응형 홈 | 부분 완료 | 일본어 기본값, 영어·한국어 표시, PC/모바일 홈, 카테고리·검색 빈 결과, 푸터 링크 및 모바일 하단 메뉴를 자식 테마로 구현했다. PC 1440px와 모바일 390px 및 10개 뷰포트 폭에서 가로 넘침이 없는 것을 확인했다. 현재 카탈로그는 0개라 실제 상품 카드·상세·구매 여정은 확인하지 못했다. |
| JPY 기본 통화 | 구현·로컬 확인 | JPY 기본 통화와 ja/en/ko 표시명, 0자리 정밀도를 설정했다. 근거 없는 EUR/USD 환율을 노출하지 않도록 두 통화를 비활성화했다. |
| 일본 주소 자동완성 | 모듈·API PASS, 실제 checkout/주문 부분 미검증 | 7자리/하이픈/전각 숫자, 일본어 후보 검색, 복수 후보, 네이티브 필드 매핑, 수동 수정, ja/en/ko를 제공한다. 실제 Japan Post 데이터 조회와 주소 검증은 읽기 전용 통합 검사로 확인했다. Japan Post 설명용 `（次のビルを除く）`는 입력 주소에서 제거하고 `以下に掲載がない場合`는 빈 주소란으로 남기도록 수정했다. 고객 checkout 브라우저와 저장된 주문은 격리 CI 설치 실패로 미검증이다. |
| 공식 주소 데이터·갱신 | 기존 dev DB/API PASS, 신규 설치 및 자동화 미검증 | 공식 KEN_ALL 124,840행을 파싱해 고유 후보 124,839건을 기존 dev DB에 적재했다. 재실행 가능한 수동 갱신 CLI가 Japan Post 공식 HTTPS ZIP, 호스트, ZIP 무결성, CSV 항목을 검증하고 기존 트랜잭션 importer를 호출한다. 실제 재수입은 실행하지 않았다. 관리자 갱신 화면/일정은 없다. |
| 관리자 한국어 | 로그인·대시보드·주문 목록 부분 검증, 전체 100% 미완료 | 실제 로그인 후 대시보드 및 주문 목록 PC/모바일을 확인했다. 주문 목록은 HTTP 200, 화면 문구와 메뉴 한국어, 브라우저 오류 0건이다. 화면에 주문이 없어 주소 표시 행은 아직 확인하지 못했다. 빈 상태 삽화 안의 샘플 영문/달러 그림도 표시된다. 전체 관리자 화면의 한국어 100%는 완료되지 않았다. |
| PWA | 부분 완료 | manifest, 아이콘, 공개 정적 자산 전용 service worker 기반을 갖췄다. 실제 iOS/Android 설치 검증은 미실행이다. |
| 현재 로컬 회귀 실행 | 부분 실패 | 최신 38개 storefront/smoke 실행에서 35건 통과, 빈 카테고리 ja/en/ko 경로 3건이 `Category.php`/`CategoryController.php`의 false 조회 결과 foreach 경고와 함께 HTTP 500으로 실패했다. 주소·관리자 번역 계약은 별도 6/6·8/8 통과했다. 여유 공간·inode가 0/100%인 상태에서 MariaDB도 unhealthy로 관찰되어 DB 변경이나 컨테이너 재시작 없이 중단했다. |
| 신규 설치 CI | 설치·CSV·주소 조회 PASS, 주소/주문 저장 회귀 보완·CI 대기 | run `39734469874`에서 empty-volume 기동, 공식 Japan Post CSV import와 `1000004` Tokyo/Otemachi API 후보가 통과했다. 주소 저장 QA script의 `$address->id_shop` 대입이 `Cannot access protected property Address::$id_shop`로 실패해 해당 harness 오류를 제거했다. 후속 검증기 사전 점검에서 native-order QA script에도 같은 잘못된 대입을 찾아 함께 제거하고 두 verifier를 회귀 계약에 포함했다. run `39735099736`은 이전 verifier 수정으로 진행 중이며 아직 주소/주문 결과를 확인하지 않았다. 새 수정의 native Address·Order·Back Office·restart 검증은 후속 격리 CI 전까지 미완료다. |
| Amazon Japan·Rakuten 상품 수집 | 차단 | 공개 홈페이지를 읽기 전용 HTTP 요청했으나 둘 다 개발환경 egress proxy의 CONNECT `403`으로 거부됐다. 우회하지 않았으며 실제 페이지 파싱·상품 수집·등록을 하지 않았다. |
| 주문·상품 운영 | 미완료 | 카탈로그가 비어 있고 신규 설치 CI가 실패한다. 실제 상품 수집, 주문, 주문관리 브라우저 여정은 완료되지 않았다. |

## 최근 작업

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

1. run `39728912492`의 실패 단계 로그나 진단 artifact를 확보해 Compose 시작 실패 원인을 확인한다. 코드 변경 없이 같은 신규 설치 CI를 다시 실행하지 않는다. 원인을 고친 뒤 빈 DB 설치와 전체 smoke를 다시 검증한다.