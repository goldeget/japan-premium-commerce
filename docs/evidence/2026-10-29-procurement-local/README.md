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

## 최초 native 로그인 진입 실패

`remote-40749362584-*.json`: 6f9c301 실제 hosted 빌드·fresh 설치·소스·bootstrap·검수 이미지/2단계 카테고리·기본512M warmup 포함28phase PASS, native_browser FAIL/후행9 not_run, cleanup success. artifact12843502379 ZIP SHA256 `13978d20868ce9629743cafd1c8c283167d1ca49a360e63b0b470cdf58feaef0`. browser 단계명은 category이지만 실제 최초 실패는 그 전 login_customer의 이메일 입력란 대기였다. 카테고리 UI에는 도달하지 않았다.

`login-route-focus/`: 같은 소유 격리 설치에서 정책9경로200 후 raw authentication+id_lang는404/폼0, id_lang 없는 raw route와 native 생성 JA 로그인은200/폼1로 대조했다. 첫 이동만 native 링크로 바꾼 기존 helper와 정확 A 신원 검사가 통과했다. domain12/ACL·감사8/critical3은 불변이다. 비밀번호 입력 전 실패였으며 인증 실패나 정보 유출로 판정하지 않는다. CI는 native Link 생성 URL과 same-origin 검사를 사용하도록 수정하며 기존 로그인/고객 격리/시간 제한은 유지한다. 실제 수정 helper 재검증·새 전체 결과는 후속 기록을 따른다.

## 정책 저장 완료 대기 원인

`remote-40750834639-*.json`은1aca9e9의 실제28phase PASS/native_browser FAIL/9not_run/cleanup success다. native_policy_save_fresh_readback의 새 세션 version==1에서 실패했다. artifact12844705387 ZIP SHA256 `2ea6f0f498b26eefc800b4b23c6adfbcf85d78d8276caad84e7db089f9b8c795`.

`policy-submit-focus/` 실제 native 단1회 합성 저장에서 click RPC가27.52ms에 끝나고 정책 POST가33.33ms에 시작,302는161.79ms·최종200문서는4313.06ms에 도착함을 확인했다. 즉시 브라우저 종료/이전 문서 readyState 검사에는 저장 완료 근거가 없었다. 새 관리자 세션의 version+1/필수11+선택2값 일치, 정확1policy+1audit 추가·기존행 보존·다른10domain/9native ACL·고객/3critical 무변경을 확인했다. 초기 진단은 배경 Ajax까지4POST를 세어 false였으며 그 false와 원인을 원본결론에 보존한다. 저장 횟수는 실제 DB delta로 검증했다. 운영 정책 변경이 아닌 소유 격리 합성값의 동일내용 새 버전이다.

후속 CI는 정책과 공통 관리자 저장에서 이전 form의 stale 및 새 문서 complete를 **같은30초** 안에 함께 기다린다. 새 helper의 순서/거부 계약은 오프라인 검증했고 실제 수정 helper의 full native 실행은 후속 후보에서 판정한다. 무조건 재시도/timeout 연장/저장값 assertion 생략은 없다.

## ad51cff 관리자 확장 검증과 최신 후보

`admin-expanded/`: 최초17화면 외 실제 sidebar의69메뉴노드(부모/별칭 포함, 정규화60목적지)를3독립브라우저가 읽었다.66건은HTTP200·한국어·인증 본문,3실패는2외부 목적지다. source/domain에 맞는69Korean 추가와13Tab의 정확CAS, nativeCopyLanguageType의 rawFrom/To만 보강해 변경 영향19건을 실제 재조회했다. 사용자 지정/다른 언어/177Tab/ACL/12domain/critical manifest 보존 및 idempotence를 확인했다. dateFrom/To·WebP/AVIF·문서URL은 보존한다.

원본 whole-label strict false는 native 필수표시 span `*` 때문임을 실제 direct textnode로 구분했다. 각 라벨은 정확원본 언어/대상 언어이고, 두 select의 visible/enabled/4options를 확인했다. 느슨한 contains나 단순영문부재만으로 통과시키지 않았다. 단위검사도 실제nativeFormFactory62체크로 choices/selectedvalues/CSRF/모든 viewvars/custom/다른locale 보존을 검증한다.

최종 source1140/vendor1426 정렬/unknown0, 기본512M에서 onecache warmup5.9초, fresh현재소스의 경량24workflow명령군·locale60/audit13/CI9 및CAS33 PASS를 별도JSON에 보존한다. 로컬base imagebd1ced8+명시적ad51cffoverlay이며 깨끗한 이미지의 전체 성공이 아니다. codead51cff15f58778a5454a8b5d93014ca91740e04의 원격 #40755121454 전체38phase는 진행 중, 경량#40755121457은SUCCESS다.

외부 테마 marketplace503은 native retrieval circuit fallback(기저transport상세미확정), Facebook500은 기존로그 cURL56 CONNECT403으로 분리했다. 2외부페이지가 정상가용하거나 시각검수됐다고 주장하지 않는다. 실제Amazon/Rakuten원문/물리기기/운영정책승인과도 구분한다.

## 신규 설치 metadata assertion 원인 미확정 기록

`remote-40755121454-*.json` 원본은 ad51cff의3phase PASS/module_seed FAIL/후속34not_run/cleanup success다. artifact12845373313 ZIP SHA256 `115a8c0c4d9e4c4a112b3814aaead0feed688a4e02c54134753cc12620786cca`. 새13메뉴 엄격 기대값의 어느 클래스가 달랐는지는 원래로그에 없다. 보존되는 올바른 한국어 기본값과 검증 기대값 차이인지 실제 bootstrap 결함인지 추정으로 확정하지 않는다.

8663e96/#40756263392는 앱 변경 없이 원래 assertion 전에 고정13클래스 상태의 bounded 비식별 JSON을 보존해 새 증거를 수집한다. rawname/IDs/tokens를 기록하지 않고 최대3중복행의 boolean·enum·count만 보존한다. 진단 fixture5cases PASS이며, 이 변경만으로 이전 실패가 해결됐다고 선언하지 않는다.

## 시작 메뉴 번역 불일치 확정·최소 수정

`remote-40756263392-seed-metadata-outcome.json`은 원격 이름 원문 없이 HOME 한 행만 expectedowner/Hangul13bytes/target불일치, 나머지12정확 일치를 보존했다. `admin-expanded/native-home-translation-proof.json`은 실제 native TabsInstaller+Translator+XliffLoader를 사용하되 Tab/Language 저장 경계만 RAM으로 대체해 이전 Welcome13→수정canonical12byte를 재현한다. 운영 config/DB/메뉴를 쓰지 않았다. 원격 실제 rawname 동일성을 추정으로 확정하지 않는다.

`d4e470a`는 XLF Welcome 한 값을 기존 CAS/strictseed의 시작하기로 통일하고 세 경로 일치 회귀검사를 추가했다(locale61 PASS). `welcome-*.json`은 한 XLF만 opt/live반영·기본512M warmup5.68초·1140app/1426vendor 일치·실제 단일 CareCenter200KO/두 한국어 라벨·기존 protectedbaseline 보존의 근거다. 메타데이터 재보정이나 사용자 지정 한국어 덮어쓰기 없이 통과했다.

최신 전체38phase #40757330613/d4e470a는 진행 중이고 경량 #40757330533은 SUCCESS다. 이 README의 앞선 실행 중/최신 표기는 각 커밋 기록 시점이며 현재 판정은 TEST_RESULTS 맨 위를 따른다.

## 587bdf4 원격 실패와 native 조회전용 토큰 집중 근거

- `fresh-587bdf4-partial/`: 전체 #40759815264의 실제28PASS/브라우저FAIL/9not_run/cleanup success. artifact12847477729 ZIP SHA256 `57f41209767259df3d2517f94de8f204fabc7cf56f5b9d72619e69168532fecb`. CJK glyph 검사는 통과했으나 실제2단계 category target capture 첫PNG 전 실패다. 아직 시각 인수나 정확한 내부 predicate 원인을 확정하지 않았다.
- `native-reader-token-focus/`: 원본 d4e helper403와 untouched native 대상form action200·각 READ권한/shop관계 확인, 현587 helper의 새 세션3READ200/4유효 body token POST403와12domain/8ACL감사/2nav/3critical 무변경. 최초 directory-path guard 실패도 유지했다. CLI 인증없는 actor false는 브라우저 권한 실패 근거로 쓰지 않는다.
- `fresh-d4e470a-partial/`: 이전 full #40757330613의20PNG 실제 독립 검수에서 JA/KO 글리프·target 위치 결함이 확인됐다. 시각 PASS가 아니다.
- `current-native-target-focus/`: 현587 helper의 로컬 target15PNG 실제 제한된 독립 검수 PASS. JAENKO 확인9/JA사진3/JAHome-only 메뉴3이며 실제2단계 category 화면을 대체하지 않는다.

새 D 합성 상품/고객은 실제 parser→검수→native 부모/하위 분류→private 상품·원본CI이미지쌍→배정으로만 준비하며 최종 제출·포인트·외부 전달을 하지 않는다. 기존 customer/request/ledger와 approved snapshot은 보존하고 nativeCategory::add의 기존 nleft/nright 구조 재번호만 별도 기록한다. 실제 Amazon/Rakuten 데이터 인수와 구분한다.

## 최종 동일 후보 fresh 통합 완료 — 91c6098

`fresh-91c6098-complete/`는 실제#40763074207 SUCCESS의 원본12JSON/24PNG, 전체36파일 무결성 명세와 안전한 요약을 보존한다.38/38phase PASS·native browser16단계 PASS·aggregate true·cleanup success다. 초기/재시작1140app+1426vendor가 정확91코드와 같다. artifact12850640042 ZIP SHA256 `5c01e0d4b070875e3bac1e75b4586ee20113748a298039dc1a2f5589c4c69802`를 루트가 직접 대조했다.

별도 GPT는 hosted24PNG 모두를 실제 열고 핵심20target(3언어9분류/9확인/2사진)을 인수했다. JA/KO글리프·하위분류·최종버튼/사진쌍이 보인다. 나머지4포인트 broad-redaction 이미지는 텍스트 치환의 인공 wrap/overflow 때문에 의미/geometry 근거에서 제외했다. 앱 결함으로 단정하지 않는다.

최신 fresh품질은7privacy/84layout/84axe/14trustedclick/14Lighthouse PASS, 성능/접근성100·공개SEO100·모바일LCP최대1747.3ms·CLS0.0001이다. incomplete84셀의2rule은 유지하며, 이전과 신규rule/노드수증가가 없다는 비교가 모든현재노드 재검수는 아니다. 기존13패턴 제한·fieldINP/전체WCAG/기기 미검증을 유지한다. 실제 Amazon/Rakuten 호환·운영 설정/정책·기기는 별도 출시 조건이다.
