# 로컬 개발 환경

이 구성은 공식 PrestaShop `9.2.0` 이미지를 바탕으로 한 로컬 이미지와 MariaDB `10.11`을 사용합니다. 로컬 이미지는 고정된 공식 Hummingbird `v2.1.2`와 KURANEA 자식 테마를 포함합니다. 컨테이너는 호스트의 `127.0.0.1:8080`에서만 접근할 수 있습니다.

## 사전 준비

- Docker Engine과 Docker Compose V2
- 공식 Hummingbird `v2.1.2` 소스가 들어 있는 `themes/hummingbird/`
- KURANEA 자식 테마가 들어 있는 `themes/kuranea/`

PrestaShop 공식 이미지의 첫 실행 스크립트는 앱 파일을 영속 볼륨으로 복사합니다. 테마 디렉터리를 직접 bind mount하면 복사와 파일 메타데이터 기록이 충돌할 수 있어, Dockerfile이 저장소의 두 테마를 이미지 안에 넣고 래퍼가 이를 `prestashop_html` 볼륨으로 동기화합니다. Hummingbird 원본 submodule은 저장소에서 수정하지 않습니다.

컨테이너는 호스트의 CA bundle을 읽기 전용으로 사용합니다. 시작 스크립트가 PrestaShop 언어팩 다운로드가 참조하는 캐시에도 같은 bundle을 복사합니다. 클라우드 개발 환경의 HTTPS 프록시가 자체 CA로 TLS를 검사하는 경우에도 인증서 검증을 끄지 않습니다. 다른 Linux 개발 호스트에서 CA bundle 경로가 다르면 `.env`에 `HOST_CA_BUNDLE`을 지정하세요.

## 설정 및 정적 구성 확인

저장소 루트에서 `.env.example`을 복사해 `.env`를 만들고, 데이터베이스 암호와 관리자 암호 placeholder를 로컬 전용 값으로 바꾸세요. 관리자 계정은 `ADMIN_MAIL`과 `ADMIN_PASSWD`로 지정합니다. `.env`는 Git에서 무시됩니다.

```sh
cp .env.example .env
docker compose config --quiet
```

Compose 설정만 확인할 때는 실제 컨테이너나 데이터베이스를 시작하지 않고 다음 명령을 사용할 수 있습니다.

```sh
docker compose --env-file .env.example config --quiet
```

## 시작 및 확인

submodule을 초기화한 뒤 저장소 루트에서 실행합니다.

```sh
git submodule update --init --recursive
docker compose pull mariadb
docker compose build --pull
docker compose up -d --wait
docker compose ps
docker compose logs -f prestashop
```

PrestaShop 자동 설치가 완료되면 `http://localhost:8080`에서 확인합니다. MariaDB healthcheck가 통과한 뒤 PrestaShop이 시작됩니다. 관리자 로그인 경로는 `/admin-kuranea/`입니다. PrestaShop healthcheck는 내부 HTTP 요청에 `Host: localhost:8080`을 넣고 HTTP 200 응답을 확인합니다.

## 데이터 보존

데이터베이스와 PrestaShop 파일은 각각 `mariadb_data`, `prestashop_html` named volume에 보관됩니다. 컨테이너를 중지할 때는 `docker compose stop`을 사용하세요. `docker compose down`도 named volume은 보존하지만, 이 프로젝트에서는 DB 초기화나 볼륨 제거가 허용되지 않습니다. `docker compose down -v`, `docker volume rm`, `docker volume prune` 명령은 실행하지 마세요.


## 설치된 볼륨에 KURANEA 기본 설정 적용

PrestaShop 설치 시 기존 DB 볼륨이 이미 초기화되어 있으면 공식 이미지의 첫 설치 후크가 다시 실행되지 않습니다. 이미지의 멱등 후크를 수동으로 실행하면 일본어 기본 언어, 영어·한국어 추가, 한국어 관리자 직원 언어와 KURANEA 자식 테마를 설정합니다. 완료 표식이 있으면 변경 없이 종료합니다.

```sh
docker compose exec -T prestashop /tmp/post-install-scripts/10-kuranea-bootstrap.sh
```

이 스크립트는 DB를 초기화하거나 테이블을 지우지 않습니다. DB 초기화 옵션을 변경하거나 named volume을 삭제하지 마세요.
