# 최종 호스팅 새 설치 독립 시각 검수

## 대상과 방법

- 코드 SHA: `91c6098c6b551946cc8291b31c868656d50c9b34`
- GitHub Actions: `40763074207`
- Artifact: `12850640042`
- 루트/CI 담당자가 검증한 ZIP SHA256: `5c01e0d4b070875e3bac1e75b4586ee20113748a298039dc1a2f5589c4c69802`
- 실제 검사 폴더: `/tmp/ordenowa-remote-qa-40763074207/`
- 검토자: `/root/independent_review`, UI 작성자·CI 실행 담당자와 별도.

**이 artifact의 PNG 24개를 모두 실제로 `view_image`로 열었습니다.** 이전 로컬 D 또는 Home-only 이미지를 호스팅 증거로 재사용하지 않았습니다. 24개 각각의 SHA256·바이트·실제 크기를 직접 계산한 명세를 함께 남겼습니다. 브라우저·CI·앱·DB를 재실행하거나 변경하지 않았습니다.

## 단계별 실제 화면 판정

| 단계 | 실제 파일 범위 | 일반 상태 |
| --- | --- | --- |
| 1. 카테고리와 하위 메뉴 | `categories-target-redacted-static-labels-{ja,en,ko}-{320,390,1440}.png`, 9개 | **검토 범위 통과.** `生活用品 → キッチン用品`, `Daily necessities → Kitchenware`, `생활용품 → 주방용품`이 들여쓰기·경계선으로 연결돼 보입니다. 모든 해당 메뉴 링크가 화면 안에 있고 JA/KO 글리프도 실제로 읽을 수 있습니다. 확인된 잘림·겹침 없음. |
| 2. 발주 확인 | `confirmation-{ja,en,ko}-target-redacted-static-labels-{320,390,1440}.png`, 9개 | **검토 범위 통과.** 최종 제출 버튼과 수량 변경 링크가 화면 안에 명확하게 표시됩니다. 각 현지어 레이블이 읽히고 버튼이 가려지지 않습니다. 마스킹된 수량·상품 원문은 정확한 값의 시각 승인 대상이 아닙니다. |
| 3. 상품 사진 | `gallery-light-target-redacted-static-labels-1440.png`, `gallery-dark-target-redacted-static-labels-390.png`, 2개 | **검토 범위 통과.** 파란색·갈색의 서로 다른 합성 네이티브 사진 두 장이 실제로 함께 표시됩니다. 어두운 환경 선호 캡처는 기존 밝은 UI 팔레트를 유지하며 별도 다크 테마 구현을 의미하지 않습니다. |
| 4. 추가 포인트 화면 | `points-redacted-{390,1440}-{light,dark}.png`, 4개 | **열어 확인했으나 의미·배치 검수 근거로 채택하지 않음.** 텍스트를 `[synthetic acceptance]`로 대체하는 과거 방식이라 원문·값을 읽을 수 없고 인공적인 줄바꿈/가로 넘침도 생깁니다. 이를 앱 결함이나 실제 포인트 화면 배치로 판정하지 않습니다. 밝음/어두움 쌍은 각각 바이트가 같습니다. |

**독립 시각 결과: 핵심 대상 20개 호스팅 새 설치 화면 영역에서 확인된 차단 결함 없음.** 이전 실행에서 발견한 CJK 대체 사각형과 메뉴·제출 버튼·갤러리가 화면 아래에 남던 증거 문제는 이번 실제 호스팅 대상 이미지에서 해소됐습니다. 추가 포인트 4개는 제한을 유지하며, 마스킹으로 생긴 하단 메뉴 사각형도 실제 앱 표시로 해석하지 않습니다.

## 별도 실제 실행 결과 확인

이 검토자가 artifact의 안전한 JSON을 직접 읽어 다음 결과를 확인했습니다. 직접 테스트를 재실행했다는 주장은 아닙니다.

- `outcome.json`: **aggregate true, 38개 phase 모두 passed, cleanup success**. 새 설치·계정·권한·메일/푸시 계약·저장 재조회·재시작·복원이 포함됩니다.
- `browser-outcome.json`: **16개 stage 모두 true, failed_stage=null**. 카테고리 필터·고객 제출/격리·읽기 전용 관리자 쓰기 차단·수동 검토·명시적 포인트 지급·새 고객 로그인 재조회·연결 정정·문의·비공개/상거래 경계 등이 포함됩니다.
- `fonts-cjk-outcome.json`: JA 필수 고유 글리프 17/17, KO 12/12, 지정 폰트 매칭/파일 존재 모두 true. 이 수치만으로 끝내지 않고 위 실제 캡처의 읽기 가능 상태를 별도 확인했습니다.
- `procurement-quality-outcome.json`: privacy 7, layout 84, axe 84, 실제 클릭 14, Lighthouse 14 항목의 aggregate true와 failures=[]를 확인했습니다. **field INP는 NOT_TESTED**이며, 자동 axe incomplete의 별도 수동 검토 한계를 유지합니다.

## 완료 범위와 한계

이번 검수는 합성 데이터의 격리 호스팅 Chromium 새 설치에 대한 것입니다. 실제 Amazon/Rakuten 원문 호환·실제 이미지 사용권·운영자/정책 원문·실기기·전체 WCAG 준수·실운영 배포·실거래를 입증하지 않습니다. 기존 로컬 정책/문의/관리자/정적 컴포넌트 시각 검수와 이번 호스팅 범위를 구분합니다. 외부 Work Mode 전달 완료를 주장하지 않습니다.

독립 무결성 명세: `/workspace/scratch/ordenowa-independent-final-hosted-40763074207-image-manifest.json` — **24개 실제 열람, 핵심 대상 채택 20개, 제한된 추가 자료 4개**.
