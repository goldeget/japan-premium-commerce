# 클라우드 작업 복구 절차

## 원격 기준점

- 원격 저장소: `goldeget/japan-premium-commerce`
- 개발 브랜치: `work`
- 초기 `main` SHA 확인값: `ee02a3657448d563508687614a246e05ac61eecd`
- 첫 원격 쓰기 체크포인트: `fdfc0980314d7ab24da592510a54fc09d7be6ca3`
- 확인 파일: `docs/REMOTE_CHECKPOINT.md`

위 체크포인트는 `work`에 푸시된 뒤 새 임시 디렉터리에서 얕은 복제로 복구했고, 복제본 HEAD·원격 `work` SHA가 모두 `fdfc0980314d7ab24da592510a54fc09d7be6ca3`임을 확인했다. `main`은 변경하지 않았다.

## 새 환경에서 확인

최근 원격 코드 복구 체크포인트: `175d75dac132ddb0a8f54777519795208df8ae4d`. 이 커밋의 신규 설치 전략은 GitHub Actions run `39727310686`에서 실패했다. 당시 이미지 빌드와 정적 계약 검사는 통과했지만 빈 DB 설치 단계는 실패했고, 현재 환경에서 해당 실행의 상세 로그를 읽지 못했다. 이어진 로컬 수정은 아직 원격 체크포인트가 아니므로 push 후 별도 CI 실행이 필요하다.

현재 cloud runtime에는 revision 2가 적용돼 있고, 읽기 draft revision 4는 오래된 `2db98927a9ede2b2423456873f0994ddd19ffe4e`를 참조한다. 현재 `work`와 같은 SHA를 가진 환경 설정 draft를 저장하기 전까지 새 작업 환경에서 예전 ref가 체크아웃될 수 있다. 개정 설정이 현재 runtime에 적용됐다고 간주하지 않는다.

이전 체크포인트는 새 shallow clone `/tmp/kuran-recovery-175d75d`에서 `work` SHA와 `docker/kuran-post-install.php`, `tests/smoke/test_admin_folder_install_order.py`를 읽어 복구 확인했다. 그 CI 실행은 실패했으므로 새 설치 PASS를 뜻하지 않는다.

```bash
git status --short --branch
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git rev-parse origin/work
git ls-remote origin refs/heads/main refs/heads/work
```

`git status`에 변경사항이 있으면 보존 위치를 확보하고 파일별로 확인한다. 먼저 stash, reset, clean, checkout으로 덮어쓰지 않는다. 현재 커밋이 원격 `work`보다 앞서 있으면 해당 커밋과 파일을 보존한 뒤 새 작업을 시작한다.

## 원격 복제 복구 확인

```bash
git clone --depth 1 --branch work https://github.com/goldeget/japan-premium-commerce.git /tmp/kuran-prj-recovery
git -C /tmp/kuran-prj-recovery rev-parse HEAD
git -C /tmp/kuran-prj-recovery cat-file -e HEAD:docs/REMOTE_CHECKPOINT.md
```

복제본 SHA를 다음 결과와 비교한다.

```bash
git ls-remote origin refs/heads/work
```

복구 복제본은 확인 뒤 제거해도 된다. 실제 작업 체크아웃에서 로컬 파일을 삭제하거나 강제로 원격 상태에 맞추지 않는다. SHA가 다르면 작업을 중단하고 두 SHA와 로컬 변경사항을 먼저 보존한다.

## 커밋 보존

각 기능 단위로 커밋한 뒤 `work`에 푸시하고 원격 SHA를 재조회한다. 푸시 응답만으로 저장 완료를 판단하지 않는다. 새 작업 환경 복구 여부를 주장하려면 새 복제본에서 해당 SHA와 파일을 실제 확인해야 한다.


## Compose bootstrap 체크포인트

- `work`의 bootstrap 코드 체크포인트: `f37a59ecca0784055cecdb978285754e9ac4c3d4`
- PrestaShop 9.2.0, MariaDB 10.11, Hummingbird 2.1.2, KURANEA 자식 테마 파일 및 멱등 언어/테마 설정 후크가 포함된다.
- 기존 named volume에서 DB 연결, 일본어 기본값, 영어·한국어 언어, 관리자 직원의 한국어 언어 코드, 활성 자식 테마, HTTP 및 재시작 후 데이터 보존을 확인했다. 새 복제본에서 이 문서의 SHA와 `docker/kuran-post-install.php`를 재조회했다.
- 기존 DB 볼륨이 이미 설치된 상태에서는 공식 첫 설치 후크가 실행되지 않으므로, `docs/LOCAL_DEVELOPMENT.md`의 멱등 후크 실행 절차를 따른다.
- 격리된 빈 볼륨 자동 설치 검증은 MariaDB 초기 시스템 테이블 생성 중 Docker 저장 공간 부족(`errno 28`)으로 실패했다. 이 실패는 통과로 간주하지 않으며 기존 `kuranea_mariadb_data`와 `kuranea_prestashop_html`은 삭제하거나 초기화하지 않았다.
- 이후 커밋별 원격 SHA 및 별도 새 복제 검증은 `docs/QA_BOOTSTRAP.md`와 최종 작업 보고서에 기록한다.

### QA 복제 체크포인트

- QA/스모크 테스트/캡처 체크포인트: `ecd528ce5e2d2f9e91de89d92d379bcad3bde274`
- `git ls-remote`의 `work` SHA와 새 shallow clone `/tmp/kuran-final-recovery-ecd528c`의 HEAD가 모두 위 SHA와 일치했다. 복제본에서 테스트, QA 문서, 데스크톱·모바일·관리자 캡처 파일을 `git cat-file -e`로 확인했고 복제본 작업 트리는 clean이었다.
- `main`은 `ee02a3657448d563508687614a246e05ac61eecd`로 유지됐다.
