# ORDENOWA 공식 브랜드 자산 — 배포·검증 지침

2026-10-22 기준, 사용자가 확정한 공식 브랜드는 **ORDENOWA / オーデノワ / 오데노와**입니다.

## 승인된 이미지 원본

원본은 대화에서 생성·전달된 `ORDENOWA_official_brand_images.zip`에 포함됩니다. GitHub에는 **현재 이 원본 바이너리가 올라와 있지 않습니다.** 기존 KURANEA 이미지 또는 임의 대체 이미지를 새 브랜드 원본이라고 표시하지 않습니다.

| 관리자 업로드 슬롯 | 공식 원본 파일 | 형식 | 이미지 크기 | 원본 SHA-256 |
| --- | --- | --- | --- | --- |
| `primary_logo` | `ORDENOWA-logo.png` | PNG (alpha) | 2172×724 | `1ce6b0a015ed6748ef904cdff095ff0f38ab72c9c51fe189c33d19dc797f23fd` |
| `favicon_symbol` | `ORDENOWA-favicon-source.png` | PNG (alpha) | 1254×1254 | `c357fde8a2942e5ed0483b78d3c1a1a134163a7e5197a80072f30f75b90d72f2` |
| `pwa_icon` | `ORDENOWA-pwa-icon-source.png` | PNG | 1254×1254 | `eae5c30405dcd420f03929a3a5fc882d94e057f75e26cf0a564aa7d5cbab3ea8` |

파생 패키지 `ORDENOWA_DEPLOYMENT_BRAND_PACK_20261022.zip`은 원본 3개와 Web/PWA/OG용 파생 파일 17개, `asset-manifest.json`을 포함합니다. 패키지는 사용자에게 전달된 별도 대화 첨부이며 이 저장소에 자동 배포되지 않습니다.

## 운영자 적용 절차

1. 관리자 `쇼핑몰 운영 설정`의 브랜드 이미지 업로드 기능에서 세 원본 PNG를 **각 슬롯에 따로** 업로드합니다. ZIP 자체를 이미지 업로드로 취급하지 않습니다.
2. 게시 전 업로드 SHA-256, 해상도, 표시 미리보기를 확인합니다. 기존 KURANEA 원본은 삭제하지 않습니다.
3. 먼저 브랜드 초안으로 저장하고 PC·모바일 로고, 파비콘, 192/512 PWA, maskable, Apple Touch, 이메일/OG 파생 파일 생성 여부를 확인합니다.
4. 승인된 브랜드 정보만 게시합니다. 등록된 판매자/LOGISTEED의 실제 운영 승인 여부와 브랜드 게시를 혼동하지 않습니다.
5. 런타임에서 헤더·관리자 로그인·manifest·icons·Open Graph를 확인하고 서비스 워커의 과거 캐시 잔존을 점검합니다.
6. 실제 상품 결제·판매자 법정 표시·실거래 활성화는 별도 승인 및 거래조건 확인 전에는 차단 상태를 유지합니다.

## 주의사항

- `modules/kuraneabusinessprofile/src/Infrastructure/BrandAssetProcessor.php`가 원본 비공개 저장과 공개 파생 파일 생성 기능을 소유합니다.
- 유효한 이미지 원본이 없어도 **기존 개발·테스트 환경에서 텍스트 브랜드 ORDENOWA를 표시**하고, 빈 이미지 슬롯에 이전 KURANEA 심벌을 넣지 않습니다.
- 지금 CI에서 검사하는 CI 전용 테스트 이미지와 실제 공식 PNG의 시각 QA는 다른 항목이며, 원본 3개가 적용되기 전에는 공식 PWA 아이콘 배포를 PASS 처리하지 않습니다.
- 실제 운영 법인명과 사업자 정보는 관리자가 입력·검증하도록 유지하되, 회사 참고정보만으로 LOGISTEED의 승인된 공식 판매처라고 주장하지 않습니다.
