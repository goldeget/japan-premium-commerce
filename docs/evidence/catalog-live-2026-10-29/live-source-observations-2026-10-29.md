# 라이브 상품 출처 확인 (2026-10-29)

관찰 시각: 2026-10-29 03:05 UTC 전후 (KST 12:05 전후). 도구: TinyFish 공개 페이지 fetch와 일반 웹 페이지 열기. CUA는 `Browser is not available: iab` 및 `Browser is not available: chrome`를 반환했고 브라우저 표면 목록이 비어 있어 실제 화면/DOM을 확인하지 못했다. TinyFish의 추출 HTML은 원본 HTTP 응답 HTML과 동일하다고 간주하지 않는다.

## 검토한 출처

### Rakuten, MUJI 공식 스토어

URL: <https://item.rakuten.co.jp/mujirushi-ryohin/4550723058445/>

- 제목: `立体メッシュ ペンケース マチ付き・約幅170×高さ50×マチ50mm`.
- 상품 번호: `4550723058445`.
- 원본 경로: `◇ 定番商品 > 文具 > 文房具・事務小物`.
- 본문 설명 및 사양은 공개 응답에 있음. 상품 이미지 메타데이터는 `https://shop.r10s.jp/mujirushi-ryohin/cabinet/item57/4550723058445.jpg`.
- 공개된 페이지 본문/추출 마크업에는 상품 본체의 현재 가격, 재고, 명시적 옵션이 확인되지 않음. 가격처럼 보이는 본문은 인기상품 랭킹의 빈 `円` 자리뿐임. 검색엔진 카테고리 결과 가격을 이 상품 페이지의 현재 가격으로 대체하지 않음.
- 판정: 현재 가격이 검증되지 않아 카탈로그 샘플/SKU로 승인하지 않음.

### Rakuten, 和宅良品

URL: <https://item.rakuten.co.jp/tetuya/gro-9733/>

- 제목: `ソープフラワー 花束 ... 全14色`.
- 상품 번호: `GRO-9733`.
- 원본 카테고리 경로: `ランキング受賞商品一覧 > 生活雑貨 > プレゼントにお勧め`.
- 상품 설명에는 14개 꽃색/구성 선택과 각각의 가격 표가 있음. 공개된 텍스트 표의 금액은 ¥1,280, ¥1,480, ¥1,680, ¥1,980, ¥2,380이며, 예를 들어 `カーネーション ピンク` 행은 ¥1,480으로 표시됨.
- 이는 설명 안의 옵션별 표이며 선택된 옵션, 현재 구매창의 가격, 재고를 보여주는 화면/DOM 증거가 아님. 표가 한 단일 가격을 정의하지 않으므로 가격을 선택해 저장하지 않음. 일반 웹 열기 결과의 수집 표시는 `Crawled: 6 days ago`.
- OGP 이미지 URL: `https://shop.r10s.jp/tetuya/cabinet/g9733v2/g9733v2_1.jpg`. 공개 이미지 URL은 재사용 권한 증거가 아님. 페이지에서 별도 이미지 라이선스/사용 허가를 확인하지 못함.
- 판정: 다중 가격 및 선택 상태·재고 불명으로 승인/가져오기하지 않음.

### Amazon Japan, PILOT Hi-Tec-C Coleto 리필

URL: <https://www.amazon.co.jp/dp/B0836L96DZ>

- 공개 페이지 제목은 PILOT Hi-Tec-C Coleto Metallic Color 0.4 리필, 선택색 Metallic Pink, ASIN `B0836L96DZ`, 제조사 부품번호 `LHKRF10S4MP`로 식별됨.
- 같은 페이지는 `No featured offers available`와 `See 5 options with no featured offers`를 표시하고 가격을 제공하지 않음. 페이지 텍스트 상단의 `Image Unavailable`와 상품 이미지 링크가 함께 반환됨.
- 미디어 URL 예시: `https://m.media-amazon.com/images/I/41XO9tPtnaL._AC_SL1500_.jpg`. 이미지 URL 노출은 사용 권한 증거가 아님.
- 검색 스니펫은 일부 색상에 가격/재고를 표시했지만 직접 페이지 fetch 결과와 일치하지 않음. 스니펫을 현재 가격 근거로 사용하지 않음.
- 판정: 현재 선택 상품에 구매 가능한 정확한 가격이 없어 승인하지 않음.

### Amazon Japan, PILOT FriXion Ball Slim

URL: <https://www.amazon.co.jp/dp/B0FFB6G9BC>

- 선택 색상은 Non-Color: Black, ASIN `B0FFB6G9BC`.
- 직접 페이지는 `Currently unavailable` 및 `See 4 options with no featured offers`를 표시하며 가격을 제공하지 않음. 검색 스니펫과 직접 페이지가 상충해 스니펫은 사용하지 않음.
- 판정: 재고 및 가격 미확인으로 승인하지 않음.

### Rakuten, 特価COM (Tokka-COM) — 현재 필드 검증 후보

관찰 시각: 2026-10-29 03:17:26 UTC / 12:17:26 JST. 일반 공개 TinyFish `fetch_content`로 두 개의 first-party 페이지를 각각 새로 가져와 일치 여부를 확인했다. 상품 상세 URL은 현재 재고 표시를 제공하지만 가격은 없고, 같은 판매점으로 필터링한 Rakuten 검색결과 카드가 정확한 현재 가격과 배송비를 표시한다. 이 조합은 출처 필드 검증이며 단일 상세 페이지 파서의 가격 추출을 증명하지 않는다.

- 상세: <https://item.rakuten.co.jp/tokka-com/4549980616819/>
- 판매점 검색 결과: <https://search.rakuten.co.jp/search/mall/4549980616819/?sid=313470>
- 카드의 정확한 상품 링크: <https://item.rakuten.co.jp/tokka-com/4549980616819/?variantId=4549980616819>
- 판매점 분류: Rakuten Ichiba의 特価COM 판매점, shop id `313470`; 제조사 Panasonic의 공식/승인 판매점이라고 확인하지 않음.
- 상품명: `パナソニック(Panasonic) N-W1A 洗濯槽クリーナー 塩素系 縦型全自動式用`; 상품 식별자 `4549980616819`; Rakuten listing item id `313470/10765360`.
- 고정 규격: 1회분 1500ml. 상세 추출물에는 옵션 selector가 나타나지 않음.
- 원본 Rakuten 카테고리 경로: `家電 > 洗濯機・衣類乾燥機 > 洗濯機関連アクセサリー`.
- 검색 결과 카드 가격: ¥2,106 + 배송비 ¥550 = 가격+배송비 합계 ¥2,656.
- 상세 페이지의 가용 상태 표시: `【在庫あり】`. 같은 상세 페이지에 정확한 재고는 위쪽 재고 확인 배너를 클릭해 확인하라는 안내가 있음. 배너는 누르지 않았으며, 표시된 상태와 판매자 주의문을 함께 보존한다.
- 검색 카드 배송 문구: `15:00までの注文で最短10/30(翌日)お届け`. Rakuten은 배송일을 예상치로 안내하고 실제 일정은 주문 화면에서 확인하라고 고지한다. 결제/주문 화면에는 들어가지 않음.
- 이미지 metadata URL: `https://shop.r10s.jp/tokka-com/cabinet/441/4549980616819.jpg`. 공개 URL은 이미지 사용권을 증명하지 않으므로 이미지를 재사용하지 않음.
- 저장된 TinyFish DOM 추출물: `rakuten-tokka-com-4549980616819-item-capture.html` (9079 bytes, SHA-256 `5D3140A546B1A1E44D2FC92229CFC4DC3015C758F42F470E46F1BB52E995A17A`), `rakuten-tokka-com-4549980616819-offer-card.html` (8349 bytes, SHA-256 `81F75B1F74C1C73B50EA82B69E7EB29CFBEE6B86A51ABE6A4F8275A4143F7BF1`). 두 파일은 도구가 반환한 rendered-DOM 추출이며 원본 wire-response HTML이라고 주장하지 않는다. 상세/가격 분리와 제약은 `rakuten-tokka-com-4549980616819-evidence.md`에 기록했다.

### Amazon Japan, 아동 그림책 페이지의 일본 오퍼 확인 실패

URL: <https://www.amazon.co.jp/dp/4591191028>

- 공개 상품 페이지는 US 배송지 문맥으로 렌더되어 `Deliver to United States`, USD 10.44, USD 21.02 delivery to US로 표시되며, 상품 상세에는 가격 영역 로드 오류/이미지 불가 메시지가 나타났다. 이를 일본 내 JPY 오퍼나 일본 재고로 간주하지 않음.
- 검색 스니펫의 재고 문구는 직접 페이지에서 일본 가격·재고로 확인되지 않았다. 샘플로 승인하지 않음.
- 2026-10-29 03:20:12 UTC / 12:20:12 JST에 같은 ISBN의 일반 공개 URL `https://www.amazon.co.jp/dp/4591191028?language=ja_JP&currency=JPY`를 한 번 확인했다. 응답 언어는 일본어이고 buying option metadata locale은 `ja-JP`였지만, 가격은 계속 USD 10.44이고 배송 문맥도 United States로 유지됐다. 이를 JPY 가격으로 변환하거나 일본 내 offer/재고로 간주하지 않음. 주소·쿠키·로그인·구매 흐름은 사용하지 않음.

### Rakuten24 후보 — 직접 상세의 재고 라벨 없음

상세: <https://item.rakuten.co.jp/rakuten24/4549980616819/>; 상점 검색 결과: <https://search.rakuten.co.jp/search/mall/4549980616819/?sid=261122>. 상세 페이지는 Panasonic N-W1A, 1개입/1500ml, 원본 카테고리, 제목을 제공한다. 판매점 필터 검색 카드에는 ¥2,246 + 배송비 ¥770 = ¥3,016, 상품 코드/1개입 링크, 10/30 12:00까지 주문하면 최단 10/31 배송이 표시되지만, 상세 및 카드 모두 재고 문자열은 표시하지 않는다. 이 후보는 재고 표시가 확인되지 않은 사례로만 기록한다. 캡처와 상세는 `rakuten24-4549980616819-evidence.md` 및 같은 접두어의 `.html` 파일에 보관했다.

## 파서 결론

검토한 최신 클론은 `8c0ada0814697f6fbcd866085422427a4ec87d4b`이다. 이번 페이지 관찰로 바로 적용할 파서 수정은 확인하지 못했다.

- `RakutenHtmlParser`는 상품 식별자와 공급자 경계를 제공하며, 상품 필드 추출은 `AbstractProductPageParser`의 JSON-LD Product, schema.org Product microdata, 명시적 Open Graph 가격 메타데이터에 의존한다. MUJI 페이지에서 가격 증거를 찾지 못했으므로 가격 누락으로 거부하는 동작이 안전하다.
- Amazon HTML fallback은 `productTitle`과 정확한 가격 요소가 필요하다. 검토한 상품은 페이지 자체가 현재 구매 가능한 대표 가격을 제공하지 않아 가져오면 안 된다. HTML 선택자/DOM 구조를 직접 확인하지 못했으므로 옵션 추출 결함을 단정하거나 수정하지 않는다.
- Tetuya의 설명 안 옵션별 가격을 자유 텍스트 파싱해 대표가격을 고르는 것은 부정확하다. 사용자가 선택하지 않은 서로 다른 가격의 옵션을 단일 상품 가격으로 바꾸면 안 된다.
- 공개 페이지에 보이는 이미지 URL만으로는 상품 이미지 권한을 증명하지 못한다. 권리 증거가 없어 이미지를 다운로드/재사용하지 않았다.

## 남은 검증 조건

Tokka-COM Rakuten SKU는 서로 일치하는 상세 및 판매점 필터 검색 페이지에서 제목·규격·판매점 분류·현재 검색 가격과 배송비·상세 재고 라벨·ETA를 검증한 field-acceptance 후보이다. 다만 가격은 상품 상세 HTML에 없고 별도 검색 카드에서만 확인되므로 현재 item-page-only parser로 완전한 단일 페이지 수집이 가능한 것은 아니다. 이를 현 출시 상품으로 승인하거나 데이터를 가져오지는 않았다. Amazon Japan에서는 일본 배송 문맥의 정확한 JPY 오퍼를 확보하지 못했다.

최신 브라우저 점검: CUA IAB/Chrome 표면은 unavailable로 반환되었다. 이후 @oai/sky로 Windows Chrome을 실행했지만 대상 창 캡처가 타임아웃되었고, 새로 창 목록을 조회한 뒤 한 차례 재시도도 동일하게 실패해 skill recovery 절차에 따라 중단했다. PowerShell의 일반 공개 URL 요청도 `search.rakuten.co.jp:443` 호스트 DNS 실패로 raw wire HTML을 받지 못했다. TinyFish의 일반 공개 `fetch_content`는 정상 동작했다. 이미지 URL 공개 여부는 별도 이미지 사용 권한을 증명하지 않는다.

Evidence storage: referenced rendered-DOM capture files remain in the task private work/catalog-round2 folder; their bytes are not included in this Git source record. No native browser screenshot was obtained.
