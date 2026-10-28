# 실제 native 2단계 분류 합성 D 집중 검사

기존 소유 격리 DB/volume에서 기존 승인 상품·A/B/C·요청·80P 원장을 보존하며 별도 D 합성 상품/고객을 준비했다. 실제 쇼핑몰 상품/운영 고객 데이터가 아니다.

최초 setup은 예상 native append-table 목록에서3개를 빠뜨려 중단했으며 생성기를 재실행하거나 새 행을 삭제하지 않았다. 이후 읽기전용 비교에서 검색 facet의 `layered_price_index`3/`layered_product_attribute`2와 native 옵션의 `product_attribute_lang`6 모두 새 D 상품에만 연결됨을 확인했다. 해당 생성은 기존 parser/review/native ProductManager/Combination과 native 상품저장 hook의 정상 결과다.

모든 기존 native 행과 기존 이미지가 보존됐다. native Category::add가 기존 두 category 행의 `nleft`/`nright`만 재번호한 것은 명시적으로 허용·분리 기록한다. 원본 AFTER13 baseline을 덮어쓰지 않고 통제된 append 뒤 별도 AFTER_D baseline을 사용한다. 이 파일만으로 최종 화면 인수 성공이나 D identity 복구 완료를 주장하지 않는다.

## 실제 최초 실패 원인

`exact-native-d-first-outcome.json`에서 본인 native identity와 실제 parent/leaf XPath, 모든 메뉴 링크의 full rect/center hit, 즉시 privacy geometry는 true다. screenshot 뒤 문서 높이1930→1924/scroll329→326이 되어 기존 strict scroll assertion이 실패했고 PNG를 삭제했다.

`exact-native-d-transition-outcome.json`에서 native 부모 테마의 모든 링크200ms CSS transition과 실제 font-size/padding 애니메이션을 확인했다. screenshot 전99.9ms/progress0.499, 후166.6ms/progress0.944로 여전히 running이었다. 이미지 complete/natural size·폰트 loaded·viewport는 같았다. viewport 변경 뒤 실제 CSS 전환을 완료하기 전에 캡처한 QA 순서 문제다. CSS를 끄거나 timeout/geometry/scroll 조건을 약화하지 않고 기존 budget 안에서 완료 이벤트를 관찰해 집중 검증한다.

## 수정 후 집중 완료

최종 helper SHA256 `43cfb52d9c95ad5c11ff2ba88603c5ae6db1f72b9153d0b8271556282a810f80`는 기존30초 안에서 pending/running/paused/unknown CSS 전환을 거부하고 finished/idle만 허용한다. capture_static·privacy·rect/hit·scroll·ACL 조건은 바꾸지 않았다.13CIunit과 독립 상태/코드 검토를 통과했다.

`final-targets/`의 실제 D20PNG+실제 필터/미등록 빈 결과/3언어 미제출 확인을 통과했고 별도 GPT가20장을 모두 열어 검수·hash 대조했다. `d-category-after-final20-verify-safe.json`은 모든 보호 업무/권한/상품/사진과 원래A/B/C·80P 원장의 보존, DACTIVE1/request0/ledger0/point-account0을 확인한다. D의 `id_lang/date_upd`만 native3언어 전환으로 바뀐 것과 접속/session telemetry 추가는 명시 분리했다. 나머지D필드와 D이전 모든 고객행은 완전히 같다.

수정 코드 `91c6098c6b551946cc8291b31c868656d50c9b34`를 원격work에 저장하고2개 변경 파일을 GitHub로 다시 읽어 blobSHA가 로컬과 같은 것을 확인했다. 동일후보 전체 #40763074207은 별도 결과로 판정하며 위 로컬 집중 결과로 전체PASS를 주장하지 않는다.
