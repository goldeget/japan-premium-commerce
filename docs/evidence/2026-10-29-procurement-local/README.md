# 발주 플랫폼 로컬 집중 검증 증거

이 디렉터리는 소유한 격리 PrestaShop 설치의 비식별 결과와 실제 독립 GPT가 연 안전한 PNG를 보존한다. 운영 환경·실상품·실기기 증거가 아니다. 기존 설치에 현재 모듈/테마를 복사하고 명시적으로 native 감사 hook을 추가한 환경으로, 최종 SHA의 깨끗한 이미지 설치 성공을 뜻하지 않는다. 캡처 당시 파일 hash와 runtime qualifier를 원래 manifest에 보존한다.

- `INDEPENDENT_REVIEW.md`: UI를 작성하지 않은 별도 GPT의 실제 파싱 코드·PNG 검수와 미검수 영역.
- `reviewed-customer-v5/`: JA/EN/KO, 320/390/1440 light 및390 dark 선호의21장. 동적 값은 가렸고 원래 geometry와 enabled 상태를 유지했다. dark 선호는 별도 dark 테마 구현을 뜻하지 않는다.
- `native-core12-partial-outcome.json`: 핵심 비즈니스 단계가 통과했으나 후행 retail 상태 predicate에서 FAIL한 중간 기록. 이를 전체 PASS로 바꾸지 않았다.
- `native-boundary-outcome.json`: 실제 본인 인증·retail 경로 차단·private/noindex·commerce DB 무변경·10폭/키보드 후속 집중 PASS.
- `native-accounts-ja-en-partial-outcome.json`: JA/EN 성공 뒤 KO reset 완료 대기 문제로 FAIL한 중간 결과. `native-accounts-ko-outcome.json`는 수정한 KO 집중 PASS. 최종 fresh QA는3언어 모두 실행한다.
- 다른 `native-*-outcome.json`: Mailpit5건/중복0, mock Push 암호화·native vendor 공존, 실제 native ACL 체크박스6변경/감사6건, 재시작과 독립 DB 복원 범위.

공개된 파일에는 개인정보·비밀값·원문 MIME·토큰·주소·DB 원문이나 그 비공개 복원 manifest를 포함하지 않는다. 실제 동작 결과와 한계는 위 각 원본 outcome을 기준으로 한다. 이후 전체 fresh QA 결과는 `docs/TEST_RESULTS.md`와 Actions의 해당 SHA/artifact에서 확인한다.
