# KURANEA 테마 개발

## 기반과 고정 버전

- PrestaShop 공식 안정 버전: `9.2.0`
- Hummingbird 공식 테마: `v2.1.2`
- Hummingbird upstream SHA: `4e52b64d3c772f19d9974409b73d55fb532e9e22`
- 호환 범위: PrestaShop `~9.2.0`, Bootstrap `5.3.3`

`themes/hummingbird`는 공식 Hummingbird 저장소의 Git submodule이며 위 SHA에 고정한다. `themes/kuranea`는 `parent: hummingbird`를 지정하는 자식 테마다. 기본 템플릿과 스타일은 Hummingbird에서 상속하고 KURANEA의 화면 변경은 자식 테마에만 추가한다.

## 파일 경계

- `themes/kuranea/config/theme.yml`: 테마 식별, 부모 테마 및 PrestaShop 호환 범위
- `themes/kuranea/assets/css/custom.css`: 네이비·절제된 골드 기반 색상과 접근성 포커스 스타일. 부모의 `theme.css`는 Hummingbird에서 상속한다.
- `themes/kuranea/preview.png`: 테마 선택용 레이아웃 콘셉트 미리보기
- `themes/hummingbird`: 수정하지 않는 공식 상위 테마

미리보기는 실제 PrestaShop 브라우저 스크린샷이 아니며 쇼핑몰 레이아웃 콘셉트만 보여준다. KURANEA 공식 로고나 심벌을 포함하지 않는다. 공식 브랜드 원본은 별도 자산 단계에서 보존하고, 이 단계에서는 대체 로고를 추가하지 않는다.

## 개발 절차

저장소 루트에서 submodule을 초기화한다.

```sh
git submodule update --init --recursive
```

Hummingbird 원본 테마를 수정하지 않는다. 자식 테마의 레이아웃, 스타일, 자산만 변경하고 PrestaShop 코어는 수정하지 않는다. 상위 테마 자산을 다시 빌드해야 할 때는 Hummingbird 저장소의 `README.md`가 지정하는 Node.js 24와 npm 11 절차를 사용한다.

테마 검증은 설치된 PrestaShop 9.2.x에서 활성화와 storefront 렌더링을 확인한 후 완료로 보고한다. 로컬 샘플 미리보기는 실제 화면 검증을 대체하지 않는다.

## 빌드 검증 기록

- Node.js `v24.19.0`, npm `11.9.0`에서 실행했다.
- 실행 환경의 기본 npm 캐시 경로(`/home/agent`)에 쓰기 권한이 없어, 캐시를 `/tmp/kuran-npm-cache`로 지정해 `npm ci`를 완료했다.
- `npm test -- --runInBand`: 8개 스위트, 42개 테스트 통과.
- `npm run build`: exit 0. Webpack에서 경고 46개를 출력했으며, 빌드 뒤 Hummingbird submodule 작업 트리는 깨끗했다.
- PrestaShop 컨테이너에서의 테마 활성화 및 화면 검증은 라이브 런타임 단계에서 진행한다.

## 자산 로딩

PrestaShop은 자식 테마에 `assets/css/theme.css`가 있으면 Hummingbird의 메인 스타일시트를 대체한다. 기본 Hummingbird CSS를 유지하려면 브랜드 오버라이드를 `assets/css/custom.css`에 둔다. 기존 영속 웹 루트에 남아 있을 수 있는 이전 `theme.css`는 Compose 시작 시 제거한다.
