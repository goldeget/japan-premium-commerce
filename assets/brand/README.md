# KURANEA 브랜드 이미지 보관

`source/`에는 사용자가 제공한 ZIP에서 추출하고 SHA-256을 확인한 KURANEA 원본 PNG 3개가 보존되어 있다. 원본과 `source/SHA256SUMS.txt`는 덮어쓰지 않는다. ZIP README와 텍스트 파일은 이미지 출처 메타데이터로만 취급한다. 현재 고객용 공식 브랜드 자산은 `ordenowa/`에 별도로 보관한다.

파생 파일은 `python3 assets/brand/generate_assets.py`로 Pillow를 사용해 `generated/` 아래에만 재현한다. 영문·일문 워드마크의 투명 여백을 잘라내고 종횡비를 유지한다. `kuranea-logo-light`는 원본의 어두운 네이비 픽셀만 밝게 매핑해 어두운 배경에서 읽히도록 한 색상 변형이며, 모양·글자·금색 영역은 그대로 둔다. 벡터 파일은 생성하지 않았다.

이전에 테마와 관리자 모듈의 웹루트에 있던 KURANEA 파생 이미지 복사본은 `legacy-kuranea-webroot-archive/`로 옮겼다. 이 비공개 보관 디렉터리는 원래 경로 구조를 보존하며 `SHA256SUMS.txt`로 이동 전 바이트를 검증한다. Docker 이미지에는 이 아카이브를 복사하지 않으며 런타임이나 고객 페이지에서 사용하지 않는다. 표준 PWA 아이콘은 KURANEA 앱 원본을 192/512 크기로 축소한다. 마스크 가능 아이콘은 같은 원본 전체를 410px로 축소해 중앙 배치하므로 K 심벌이 중앙 안전 영역에 들어가며 바깥의 장식 프레임은 플랫폼 마스크에서 잘릴 수 있다.

## 생성 파일

- 데스크톱 및 모바일 투명 로고: PNG와 lossless WebP
- 어두운 배경용 투명 워드마크: PNG와 lossless WebP
- 브라우저 심벌: `favicon.ico`, 16×16 및 32×32 PNG
- 앱 아이콘: 192×192, 512×512, 512×512 maskable
- Apple Touch Icon: 180×180
- 브랜드 OG 이미지: 1200×630

투명 PNG와 WebP는 제공된 로고·심벌 원본에서 결정적으로 파생한다. 제공 이미지 자체를 SVG로 포장하거나 벡터화했다고 주장하지 않는다.
