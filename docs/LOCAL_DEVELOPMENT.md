# 로컬 개발 환경

이 구성은 공식 PrestaShop `9.2.0` 이미지와 MariaDB `10.11`을 사용합니다. 공식 Hummingbird `v2.1.2`는 PrestaShop `9.2.x` 호환 범위로 고정합니다. 컨테이너는 호스트의 `127.0.0.1:8080`에서만 접근할 수 있습니다.

## 사전 준비

- Docker Engine과 Docker Compose V2
- 공식 Hummingbird `v2.1.2` 소스가 들어 있는 `themes/hummingbird/`
- KURANEA 자식 테마가 들어 있는 `themes/kuranea/`

두 테마 경로는 PrestaShop의 `themes/` 전체가 아니라 각각의 하위 경로만 마운트합니다. PrestaShop 컨테이너를 시작하기 전에 두 디렉터리가 존재하고 해당 테마 파일을 포함하는지 확인하세요. 빈 디렉터리를 마운트하면 이미지 안의 해당 테마 파일을 가립니다.

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

테마 경로가 준비된 뒤 저장소 루트에서 실행합니다.

```sh
docker compose up -d
docker compose ps
docker compose logs -f prestashop
```

PrestaShop 자동 설치가 완료되면 `http://localhost:8080`에서 확인합니다. MariaDB healthcheck가 통과한 뒤 PrestaShop이 시작됩니다. PrestaShop healthcheck는 내부 HTTP 포트의 응답 소켓을 확인합니다.

## 데이터 보존

데이터베이스와 PrestaShop 파일은 각각 `mariadb_data`, `prestashop_html` named volume에 보관됩니다. 컨테이너를 중지할 때는 `docker compose stop`을 사용하세요. `docker compose down`도 named volume은 보존하지만, 이 프로젝트에서는 DB 초기화나 볼륨 제거가 허용되지 않습니다. `docker compose down -v`, `docker volume rm`, `docker volume prune` 명령은 실행하지 마세요.
