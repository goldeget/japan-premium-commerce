#!/usr/bin/env bash
# Restore all domain tables into a newly created independent DB container.
set -euo pipefail
umask 077
[[ ${CI:-} == true && ${KURANEA_ISOLATED_CI:-} == 1 ]]
[[ ${CI_COMPOSE_PROJECT_NAME:-} == "ordenowa-procurement-ci-${GITHUB_RUN_ID:-}-${GITHUB_RUN_ATTEMPT:-}" ]]
[[ ${GITHUB_RUN_ID:-} =~ ^[0-9]+$ && ${GITHUB_RUN_ATTEMPT:-} =~ ^[0-9]+$ ]]
[[ ${RUNNER_TEMP:-} == /* && -d $RUNNER_TEMP ]]
source_project=$CI_COMPOSE_PROJECT_NAME
restore_project="${source_project}-restore"
private_dir=$(mktemp -d "$RUNNER_TEMP/procurement-restore.XXXXXXXX")
compose() { docker compose -f compose.yaml -f tests/procurement/ci.compose.yaml -p "$source_project" "$@"; }
cleanup() {
  result=$?
  trap - EXIT
  if docker container inspect "$restore_project" >/dev/null 2>&1; then
    docker rm -f "$restore_project" >/dev/null 2>&1 || result=1
  fi
  rm -rf -- "$private_dir"
  exit "$result"
}
trap cleanup EXIT
compose exec -T prestashop php /tmp/ordenowa-procurement-ci/ci_readback.php manifest
# Include native identities/products and parser provenance at the same point.
# Dump remains private and is erased even when the restoration fails.
compose exec -T mariadb sh -ec 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb-dump -uroot --single-transaction --skip-comments "$MARIADB_DATABASE"' > "$private_dir/backup.sql"
source_image=$(docker inspect --format '{{.Config.Image}}' "$(compose ps -q mariadb)")
docker run --detach --name "$restore_project" --network "${source_project}_default" --network-alias procurement-restore \
  --env MARIADB_ROOT_PASSWORD --env MARIADB_DATABASE=prestashop \
  --tmpfs /var/lib/mysql "$source_image" >/dev/null
for ((attempt=0; attempt<60; attempt++)); do
  if docker exec "$restore_project" sh -ec 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb -uroot -N -e "SELECT 1"' >/dev/null 2>&1; then break; fi
  sleep 2
done
docker exec -i "$restore_project" sh -ec 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb -uroot prestashop' < "$private_dir/backup.sql"
# Point a one-off PHP process at the independent restored connection without
# modifying the installed shop's parameters or the original database.
compose exec -T -e PROCUREMENT_RESTORE_HOST=procurement-restore -e "MARIADB_ROOT_PASSWORD=$MARIADB_ROOT_PASSWORD" prestashop php /tmp/ordenowa-procurement-ci/ci_restore_readback.php
printf 'PASS independent database restore of native references and procurement domain\n'
