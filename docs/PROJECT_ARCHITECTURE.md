# 초기 프로젝트 아키텍처

## 검증한 기반 버전

- PrestaShop 공식 안정 태그 `9.2.0`, upstream SHA `84db6bd3a3c1612535b15b9df934afd609085423`.
- Hummingbird 공식 안정 태그 `v2.1.2`, upstream SHA `4e52b64d3c772f19d9974409b73d55fb532e9e22`.
- Hummingbird `config/theme.yml`의 지원 범위는 `9.2.0`부터 `~9.2.0`까지로, PrestaShop 9.2.x와 일치한다.
- 공식 PrestaShop 컨테이너 태그 `prestashop/prestashop:9.2.0`을 앱 런타임 후보로 사용한다. MariaDB는 10.11 계열로 고정한다.

## 구성 경계

- `themes/kuranea`는 Hummingbird를 부모로 지정한 KURANEA 자식 테마다. 로고 배치, 반응형 헤더, 브랜드 색상·타이포그래피를 담당한다.
- 별도 PrestaShop 모듈은 Manifest, 서비스 워커, 설치 안내, 관리자 브랜드 요소 및 이메일 로고 연동을 담당한다.
- `modules/kuraneapostcode`는 일본우편 KEN_ALL 데이터를 별도 테이블에 저장하고, 고객이 선택한 도도부현·시구정촌·町域을 PrestaShop 네이티브 `id_state`, `city`, `address1`, `postcode` 필드로 기록한다. 번지와 건물·호수는 고객 입력을 보존한다. 주문 주소는 기존 PrestaShop 주소 관계를 사용한다.
- `modules/kuraneabackoffice`는 관리자 로그인 한국어 및 공식 로고, 관리자 번역 오버레이를 제공한다. 이는 코어 수정 없이 추가하며 전체 Back Office 번역 범위는 화면별 QA로 기록한다.
- 원본 브랜드 자산은 `assets/brand/source/`에 보존하고, 파생 파일은 재현 가능한 스크립트로 `assets/brand/generated/`에 만든다.
- PrestaShop 코어는 변경하지 않는다. Back Office 한국어 보완은 공식 번역을 우선 사용하고, 커스텀 번역을 별도 모듈/번역 파일로 제공한다.
- 고객 언어는 일본어를 기본으로 영어·한국어를 제공한다. Back Office는 한국어 번역 검증을 별도 acceptance gate로 둔다.

## PWA 및 개인정보

- Manifest는 앱 이름 `KURANEA`와 공식 아이콘 세트를 참조한다.
- 서비스 워커는 공개 정적 자산과 안전한 오프라인 안내만 캐시한다. 인증, 고객정보, 장바구니, 결제, 주문·입금 정보는 저장하지 않는다.
- 설치 동작은 HTTPS에서 Android, iOS 홈 화면, 설치 지원 데스크톱 브라우저별로 검증한다.

## 단계적 완료 기준

1. 원격 복구 규칙과 개발 요구사항을 저장한다.
2. 고정 버전 PrestaShop·MariaDB 로컬 환경과 Hummingbird 자식 테마를 구동한다.
3. 원본 브랜드 파일을 보존하고 필수 파생 파일을 생성한다.
4. 쇼핑몰·Back Office·이메일·Favicon·Manifest에 같은 공식 자산을 적용한다.
5. 관리자 한국어, 반응형 화면, PWA 설치를 기능별 테스트와 실제 브라우저 QA로 확인한다.
6. 각 단계 결과를 작은 커밋으로 `work`에 푸시하고 원격 SHA를 검증한다.

컨테이너 구동은 현재 클라우드 네트워크 정책의 enforcement 상태가 확인된 뒤 수행한다. 로고 원본이 파일로 로컬에 제공되기 전에는 브랜드 파생 파일을 만들지 않는다.
