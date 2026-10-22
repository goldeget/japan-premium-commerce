# KURANEA 일본 배송지 우편번호 자동검색

## 필수 동작

- 일본우편 공식 KEN_ALL CSV를 로컬 PrestaShop DB에 가져와 조회한다. 주소 조회 시 유료 API나 외부 네트워크 요청을 사용하지 않는다.
- `1000004`, `100-0004`, 전각 숫자 및 지원되는 일본어 하이픈을 7자리 형식으로 정규화한다.
- 우편번호와 일본어 주소 문자열로 후보를 검색하고, 동일 우편번호의 여러 주소는 모두 선택할 수 있게 한다.
- 후보 선택은 도도부현, 시구정촌, 町域을 자동 입력한다. 번지, 건물명, 호수는 고객이 직접 입력·수정한다.
- 조회 실패에도 모든 네이티브 주소 입력란을 수동 입력할 수 있어야 한다.
- UI 문구는 일본어·영어·한국어를 제공한다. 주소는 PrestaShop의 네이티브 주소 필드에 저장해 기존 주문 및 관리자 주문 화면과 호환한다.
- PWA와 웹은 동일한 주소 폼 및 API를 사용한다. 서비스 워커는 주소·고객·주문 응답을 캐시하지 않는다.

## 데이터 갱신

공식 다운로드: <https://www.post.japanpost.jp/service/search/zipcode/download/>.
운영자가 해당 페이지에서 최신 KEN_ALL 압축 파일을 받아 공개 웹 루트 밖에서
압축 해제한 뒤 다음 명령으로 가져온다.

```sh
php modules/kuraneapostcode/bin/import-ken-all.php --file=/absolute/path/to/KEN_ALL.CSV
```

수입기는 UTF-8 및 CP932를 읽고 별도 staging 테이블에 적재한다. 유효 주소가
확인된 경우에만 기존 모듈 주소 데이터를 트랜잭션으로 교체한다. 빈 파일이나
잘못된 파일은 현재 주소 데이터를 지우지 않는다. 갱신은 운영자가 공식 페이지에서
새 CSV를 받아 위 명령을 다시 실행하는 방식이다. 교체 트랜잭션이 성공하면 staging
복사본을 비워 운영 주소 데이터가 디스크를 중복 점유하지 않도록 한다. 이번에 사용한
공식 archive의 SHA-256은 `c976cb0ff691a1aa7480b47b7e1f61bea08c2eadb3278f0366e474cd82dbf4b8`이다.

## 구현 및 확인 상태

- 공식 CSV 124,840행을 파싱했고 유효한 고유 후보 124,839건을 기존 개발 DB의
  `ps_kuraneapostcode_address`에 가져왔다. importer의 성공 커밋 뒤 staging 복사본을
  비우도록 수정했으며, DB 주소 행 124,839건과 staging 행 0건을 확인했다.
- 실제 로컬 HTTP API에서 `1000004`와 `100-0004` 모두 도쿄도·지요다구·오테마치를
  반환했고, `千代田区大手町` 검색과 중복 우편번호 `004-0000`의 후보 2개도 확인했다.
- 실제 KURANEA 사이트 origin에서 모듈 JS와 DB API를 연결해 PC 1440px 및 모바일
  390px 브라우저 검증을 했다. 주소 폼 계약 fixture에서 후보 선택, 건물명 수동 편집,
  일본어 검색, 중복 후보 선택이 동작했고 JS 오류는 없었다. 캡처는
  `artifacts/qa/phase1a/postcode-widget-desktop.png` 및
  `artifacts/qa/phase1a/postcode-widget-mobile.png`다. 실제 checkout 페이지 캡처는 아니다.
- 격리된 빈 설치 Action은 run `39697612835`에서 실패했다. 로그와 진단 artifact를 읽을
  수 없어 빈 설치, 새 DB 공식 데이터 적재, 네이티브 Address 저장, 실제 주문 및
  관리자 주문 표시를 PASS로 기록하지 않는다. 브라우저 checkout end-to-end 검증도 남아 있다.

## 보안 및 데이터 보호

- 후보 API는 공개 우편 주소만 읽는 GET이며 `Cache-Control: no-store`를 지정한다.
- 일본 주소 검색이 실패해도 저장을 막지 않고 수동 입력을 유지한다.
- 기존 데이터베이스 볼륨에서 테스트 고객·주문을 생성하지 않는다. 통합 저장 검증은
  GitHub Actions의 실행별 격리 DB에서만 수행한다.
