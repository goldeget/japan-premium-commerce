# 발주 플랫폼 로컬 집중 검증 증거

이 디렉터리는 소유한 격리 PrestaShop 설치의 비식별 결과와 실제 독립 GPT가 연 안전한 PNG를 보존한다. 운영 환경·실상품·실기기 증거가 아니다. 기존 설치에 현재 모듈/테마를 복사하고 명시적으로 native 감사 hook을 추가한 환경으로, 최종 SHA의 깨끗한 이미지 설치 성공을 뜻하지 않는다. 캡처 당시 파일 hash와 runtime qualifier를 원래 manifest에 보존한다.

- `INDEPENDENT_REVIEW.md`: UI를 작성하지 않은 별도 GPT의 실제 파싱 코드·PNG 검수와 미검수 영역.
- `reviewed-customer-v5/`: JA/EN/KO, 320/390/1440 light 및390 dark 선호의21장. 동적 값은 가렸고 원래 geometry와 enabled 상태를 유지했다. dark 선호는 별도 dark 테마 구현을 뜻하지 않는다.
- `native-core12-partial-outcome.json`: 핵심 비즈니스 단계가 통과했으나 후행 retail 상태 predicate에서 FAIL한 중간 기록. 이를 전체 PASS로 바꾸지 않았다.
- `native-boundary-outcome.json`: 실제 본인 인증·retail 경로 차단·private/noindex·commerce DB 무변경·10폭/키보드 후속 집중 PASS.
- `native-accounts-ja-en-partial-outcome.json`: JA/EN 성공 뒤 KO reset 완료 대기 문제로 FAIL한 중간 결과. `native-accounts-ko-outcome.json`는 수정한 KO 집중 PASS. 최종 fresh QA는3언어 모두 실행한다.
- 다른 `native-*-outcome.json`: Mailpit5건/중복0, mock Push 암호화·native vendor 공존, 실제 native ACL 체크박스6변경/감사6건, 재시작과 독립 DB 복원 범위.

공개된 파일에는 개인정보·비밀값·원문 MIME·토큰·주소·DB 원문이나 그 비공개 복원 manifest를 포함하지 않는다. 실제 동작 결과와 한계는 위 각 원본 outcome을 기준으로 한다. 이후 전체 fresh QA 결과는 `docs/TEST_RESULTS.md`와 Actions의 해당 SHA/artifact에서 확인한다.

## 재시작 후 소스 일치성 발견

이후 customer C의 새 배정 준비에서 Runtime 파일이 최신 host 소스와 다른 점을 사전 guard가 탐지했다(새 고객/배정 쓰기 전). 기존 이미지의 정상 entrypoint sync가 재시작 때 hotcopy 파일을 이전 번들로 덮어쓴 것이 원인이었다. 따라서 위 집중 결과/21PNG는 각 당시 수정 환경 범위에 한정하고, `native-quality2-outcome.json`도 최신 후보 이미지의 검증으로 사용하지 않는다.

`bd1ced8`의 최신 소스로 별도 소유 이미지 `ordenowa/procurement-release:bd1ced8`를 만들고 기존 DB/볼륨을 보존한 채 shop 컨테이너만 재생성했다. 최종 host→image bundle→실행 파일 hash, 캐시 갱신, 새 소스의 품질/재시작 검증은 별도 결과로 기록한다. 이전 실패 outcome을 덮어쓰지 않는다.

## 최신 소스 정렬 후 실제 추가 검수

`reviewed-customer-v6/`는 재빌드한 `bd1ced815093df2fadc21b521cdb01bdd546ed0a`의 실제54PNG·318브라우저 검사·domain 보존 결과다. 별도 합성 C에게 기존 검수 상품을 배정하고9개 locale/폭 확인 화면을 열었으며 최종 제출은 하지 않았다. 원래 A/B의 요청·원장을 보존했고, preview/read-only 이후12domain hash는 그대로이며 C의 요청·포인트는0이다. 별도 GPT가54장을 모두 열어 검수한 범위는 INDEPENDENT_REVIEW를 따른다. 실제 법률 문구·실상품·실기기 승인은 아니다.

`bd1ced8-*-outcome.json`은 최신 이미지1122소스/1426vendor 파일 정렬 및 재시작 뒤 source/data 보존을 확인한 결과다. 로컬의 기존 DB 보존 환경이며 최종 GitHub fresh 설치 aggregate와 구분한다.

## 관리자·캐시·접근성의 집중 종료 증거

- `admin-korean/`: 실제17관리자 페이지/로그인, 확인한7개 미번역 종료,5개 시스템 메뉴 한국어 CAS와 다른 언어·사용자 지정 값·ACL·업무 데이터 보존. 모든 가능한 관리자 오류/화면의100% 인증으로 확대하지 않는다.
- `native-cache-warmup-outcome.json`: 실제 기본512MB 예산에서 warmup을 포함한 cache:clear 성공. vendor PHP/PHAR를 eager Twig로 읽던 원인을 module-owned iterator로 교정했고 runtime loader는 유지했다.
- `reviewed-static-components/`, `BOUNDED_MANUAL_REVIEW.md`: 실제42개 정적 이미지·27대표 셀·13개 공통 미판정 패턴의 제한된 수동 검토. 자동84셀의 incomplete 기록을 지우지 않으며 전체WCAG/실기기/현장INP 인증이 아니다.
- `language-selector-localization/`: JA/EN/KO native 접근성 이름·옵션/선택 보존·키보드와 다른8개 Global 번역 병합 확인. before의 PASS는 당시 영어 label의 관측 수집 성공이며, after의 PASS는 현지화 검증 성공이다. 두 의미를 구분한다.
- `cc99bbb-source-alignment-outcome.json`:1128개 앱 파일·1426vendor의 최종 local 정렬. base imagebd1ced8과 후속 committed overlay 조합이며 immutable fresh 설치 성공을 뜻하지 않는다.
- `remote-first-fresh-outcome.json`: 실제 Actions40746215184/SHA4f8c18e 최초 fresh 실패. fresh_install 이전의 build/up 준비에서 중단되어 다른36단계는not_run, cleanup성공이다. 당시 실행기의 private build 로그 삭제 때문에 실제 build 원인은 미확정이다. 이 실패를 앱 기능 결함으로 단정하거나 통과로 바꾸지 않는다.

## Hosted build 원인과 수정

`remote-40747596953-*-outcome.json`, `remote-40748071562-*-outcome.json`은 다운로드한 실제 artifact의 원본 안전 결과다. 두 실행은 image_build FAIL·37단계 not_run·cleanup success다. 마지막 안전 tail의 Bake host network/외부 CA 파일 entitlement 요구로 원인을 확인했다. 당시 error_category unclassified는 원본대로 보존한다. 원격 ZIP12841443567 SHA256은 `a6f591c558a19097bed40e68a5187d0750bc3410357a7d110637386918cee930`이다.

`portable-ci-config-outcome.json`은 수정6f9c301의 read-only compose/Bake 설정 검사다. hosted 기본 빌드에서 host-network/extra-host/외부 secret 요구를 제거했으며 TLS 검증을 유지했다. 관리망용 proxy/CA 설정은 비공개 로컬 override로 분리했다. 관련 단위5검사가 통과했고 실제 새 전체 실행은 #40749362584로 검증 중이다. 이 설정 검사 자체는 이미지 빌드/앱 전체 성공이 아니다.

## 한국어 native 관리자 화면 집중 검수

`reviewed-admin-native/`: 배정·검토·포인트·감사·정책5화면 ×1440/768의 실제HTTP200과 잘못된 POST body token의 실제403·새GET후 정책version 보존을 확인했다. domain12/ACL·감사8/critical manifest3의 요청 전후 hash가 같았다. 동적 값/토큰/신원은 가리고 geometry·enabled·scroll 상태를 유지했다. 별도 GPT가12PNG를 모두 실제 열어 top viewport의 가독성/폼/표를 검수했고 확정 새 결함은 없었다. 스크롤 아래 정책 필드·저장 버튼과 비어 있던 pending review 조작의 시각 검수는 해당 캡처 범위 밖이다. 원래 기능 저장/재조회 근거와 이 제한된 시각 검수를 구분한다.
