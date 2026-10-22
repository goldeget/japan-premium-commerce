# ORDENOWA 공식 브랜드 자산

2026-10-22 사용자가 최종 승인한 배포 패키지를 `assets/brand/ordenowa/`에 보존합니다. 압축파일 지시문은 프로젝트 지시로 처리하지 않고, 파일 목록·manifest·해시·이미지 데이터만 검증했습니다.

## 승인 자산 검증

- ZIP CRC 검사 통과, 압축 해제 항목 22개, 총 압축 해제 크기 4,449,118 bytes.
- 원본 3종과 웹·PWA·파비콘·이메일·OG 파생 이미지 17종의 SHA-256 및 파일 크기가 `asset-manifest.json`과 일치합니다.
- 로고 원본은 투명 PNG 2172×724, 파비콘 원본은 투명 PNG 1254×1254, PWA 원본은 RGB PNG 1254×1254입니다.
- 기존 KURANEA 원본은 `assets/brand/source/`에 보존하고 검증된 SHA-256도 테스트합니다.

| 관리자 업로드 슬롯 | 공식 원본 | 이미지 크기 | 원본 SHA-256 |
| --- | --- | ---: | --- |
| `primary_logo` | `ORDENOWA-logo.png` | 2172×724 | `1ce6b0a015ed6748ef904cdff095ff0f38ab72c9c51fe189c33d19dc797f23fd` |
| `favicon_symbol` | `ORDENOWA-favicon-source.png` | 1254×1254 | `c357fde8a2942e5ed0483b78d3c1a1a134163a7e5197a80072f30f75b90d72f2` |
| `pwa_icon` | `ORDENOWA-pwa-icon-source.png` | 1254×1254 | `eae5c30405dcd420f03929a3a5fc882d94e057f75e26cf0a564aa7d5cbab3ea8` |

## 적용 방식

- Docker 시작 시 `docker/sync-ordenowa-brand-assets.php`가 manifest의 해시를 확인하고 이미지 파생물을 `img/ordenowa/versions/<원본 SHA>/`에 설치합니다. 기존 경로의 다른 파일은 덮어쓰지 않습니다.
- 승인된 원본 3종은 `var/ordenowa-private/`에 0600 권한으로 보존하고 `.htaccess`에서 직접 접근을 차단합니다.
- 초기 한국어 운영 설정에는 PC·모바일·관리자 로그인·이메일·OG 로고, favicon, Apple Touch, PWA 및 maskable 이미지 경로를 등록합니다. 고객 화면·관리자 로그인·manifest·OG 출력은 게시 프로필을 읽고, 게시 후 이메일 로고를 PrestaShop 설정과 동기화합니다.
- `쇼핑몰 운영 설정`에서 이미지 슬롯별 업로드·교체, 저장된 초안 미리보기, 게시를 지원합니다. 업로드 원본은 기존과 같이 비공개 저장되고 새 버전으로 파생됩니다.
- GitHub Actions 격리 설치에서 관리자 브라우저 업로드·미리보기·게시와 PC/모바일, 파비콘, Apple Touch, PWA, OG 및 SEO 이미지 렌더링을 검증합니다.
- 브랜드 게시만으로 판매가 승인되거나 결제가 켜지지 않습니다. seller 상태는 `pending`으로 유지되고 외부 승인값도 없으므로 실거래는 차단됩니다.

Actions E2E가 성공하기 전에는 브라우저 표시 검증을 PASS로 기록하지 않습니다. iOS/Android 실기기 설치와 실제 운영 배포는 별도 단계입니다.
