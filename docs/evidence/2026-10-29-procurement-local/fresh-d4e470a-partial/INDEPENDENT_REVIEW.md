# 새 설치 QA 40757330613 독립 화면 검수

- 코드: `d4e470ae005a27568b260653107dfe62074fbc6a`
- 실행: `40757330613`, artifact `12847660925`
- CI 담당자가 확인한 ZIP SHA256: `c8852f034046a2affba508ca264114732e4785cc478ef02c1a5816eebbc96433`
- 실제 검토 폴더: `/tmp/ordenowa-remote-qa-40757330613/`
- 검토자: `/root/independent_review`. **실제 PNG 20개를 모두 `view_image`로 열었습니다.** 브라우저·CI·앱 변경을 실행하지 않았습니다.

## 실제 실행 결과와 시각 검수 구분

`outcome.json`의 전체 `passed`는 **false**, cleanup은 success입니다. 새 이미지 빌드·설치·seed·native gallery/source 등은 passed이지만 native browser는 failed입니다. 계정·네이티브 ACL·품질·재시작·복원 등 후속 단계는 not_run이며 이번 실행에서 통과했다고 처리하지 않습니다.

`browser-outcome.json`은 정책 잘못된 토큰 거부/저장 후 새 로그인 재조회, 관리자 상품 배정, 검토된 카테고리 경로/필터, 고객 A 확인·제출, 고객 B 소유권 차단의 여섯 단계를 true로 기록합니다. 최초 관측 실패 단계는 `native_readonly_review_denial`입니다. 이 문서는 그 실패의 확정 원인을 추정하지 않습니다.

## 실제 20개 이미지의 판정

| 단계 | 파일/수량 | 실제 관측과 판정 |
| --- | --- | --- |
| 1 | `categories-redacted-static-labels-{ja,en,ko}-{320,390,1440}.png` / 9개 | 영어 1440px에서 `Daily necessities` 아래 `Kitchenware`가 들여쓰기된 하위 항목으로 표시됩니다. 320/390px은 상단 캡처라 하위 항목이 화면 아래로 벗어나 있습니다. 일본어·한국어의 정적 CJK 문자는 모두 사각형 대체 글리프로 보여 읽을 수 없습니다. **9개 전체 카테고리 시각 검수 통과로 판정할 수 없습니다.** |
| 2 | `confirmation-{ja,en,ko}-redacted-static-labels-{320,390,1440}.png` / 9개 | 영어 확인 제목·제출 후 변경 불가 안내와 첫 사진은 보입니다. **9개 모두 최종 제출 버튼·수량 변경 링크가 화면 아래에 있어 직접 보이지 않습니다.** JA/KO는 CJK 대체 글리프로 문구를 읽을 수 없습니다. 기존 로컬 v6의 확인 버튼 검수를 이번 새 설치 증거로 전용하지 않습니다. |
| 3 | `gallery-light-redacted-static-labels-1440.png`, `gallery-dark-redacted-static-labels-390.png` / 2개 | 합성 주 사진은 렌더링됩니다. 두 썸네일을 함께 볼 수 있는 영역은 화면 아래에 있어 이번 이미지에서 직접 확인되지 않습니다. CJK 문구도 대체 글리프로 보입니다. native gallery의 DOM/서버 검사와 실제 두 사진 시각 확인은 별도입니다. |

## 확인된 증거 문제와 필요한 집중 보완

1. **CJK 글리프 렌더링 문제:** JA/KO 텍스트가 대체 사각형으로 보이는 것은 실제 관측입니다. DOM의 정확한 현지어 카테고리 XPath 검사는 통과했고 캡처 함수는 글자를 바꾸지 않는 픽셀 마스크를 사용합니다. 현재 workflow에는 Selenium 설치는 있으나 CJK 폰트 준비가 보이지 않아, 우선 호스팅 브라우저의 폰트 환경을 확인해야 합니다. 앱 결함으로 단정하지 않습니다. 읽기와 실제 글꼴 너비가 확인되기 전에는 해당 시각/배치 검수를 완료 처리하지 않습니다.
2. **캡처 대상 위치 문제:** 함수가 매번 상단으로 스크롤하여 핵심 메뉴/버튼/두 사진이 화면 밖에 남습니다. 카테고리 navigation, 확인 제출 영역, gallery를 각각 화면 안으로 가져온 뒤 위치·enabled 상태·개인정보 마스크 불변 조건을 유지하여 캡처해야 합니다. assertion 생략이나 상품 재분류가 필요한 문제가 아닙니다.
3. **전체 실행 실패:** 위 캡처 보완으로 후속 기능이 통과했다고 판단할 수 없습니다. 최초 실패를 별도 집중 해결하고 실제 aggregate·not_run을 유지해야 합니다.

이 검수는 합성 상품과 호스팅 Chromium의 화면이며 실제 쇼핑몰 원문 호환·실제 사진 사용권·물리 기기·운영 배포를 입증하지 않습니다.

독립 이미지 SHA256/크기 명세: `/workspace/scratch/ordenowa-independent-fresh-40757330613-image-manifest.json`.
