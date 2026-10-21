# 클라우드 작업 복구 절차

## 원격 기준점

- 원격 저장소: `goldeget/japan-premium-commerce`
- 개발 브랜치: `work`
- 초기 `main` SHA 확인값: `ee02a3657448d563508687614a246e05ac61eecd`
- 첫 원격 쓰기 체크포인트: `fdfc0980314d7ab24da592510a54fc09d7be6ca3`
- 확인 파일: `docs/REMOTE_CHECKPOINT.md`

위 체크포인트는 `work`에 푸시된 뒤 새 임시 디렉터리에서 얕은 복제로 복구했고, 복제본 HEAD·원격 `work` SHA가 모두 `fdfc0980314d7ab24da592510a54fc09d7be6ca3`임을 확인했다. `main`은 변경하지 않았다.

## 새 환경에서 확인

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
