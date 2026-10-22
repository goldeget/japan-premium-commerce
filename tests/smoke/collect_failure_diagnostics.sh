#!/usr/bin/env bash
set -euo pipefail

project_name=${CI_COMPOSE_PROJECT_NAME:?CI_COMPOSE_PROJECT_NAME is required}
runner_temp=${RUNNER_TEMP:?RUNNER_TEMP is required}
redacted_diagnostics="$runner_temp/kuranea-compose-startup-diagnostics-redacted.txt"

{
  printf '%s\n' 'Fresh install failed; collecting bounded diagnostics for this isolated run.'
  df -h || true
  df -i || true
  docker system df || true
  docker compose -p "$project_name" ps -a || true
  docker compose -p "$project_name" logs --tail=160 mariadb prestashop || true
} 2>&1 \
  | sed -E \
      -e 's/((MARIADB_ROOT_PASSWORD|MARIADB_PASSWORD|ADMIN_PASSWD|MYSQL_PWD|password|passwd|token|secret)[[:space:]" ]*[:=][[:space:]" ]*)[^[:space:],"]*/\1[REDACTED]/Ig' \
      -e 's/(mysql[^[:cntrl:]]*[[:space:]]-p)[^[:space:]]+/\1[REDACTED]/Ig' \
  > "$redacted_diagnostics" || true

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    printf '%s\n' '## Isolated fresh-install diagnostics' ''
    printf '%s\n' 'Credential-like values are redacted; service logs are limited to the latest 160 lines.' ''
    printf '%s\n' '```text'
    cat "$redacted_diagnostics"
    printf '%s\n' '```'
  } >> "$GITHUB_STEP_SUMMARY"
fi

route_migration_signal=$(
  docker compose -p "$project_name" logs --tail=160 --no-color prestashop 2>&1 \
    | grep -Eo \
      'ORDENOWA_ROUTE_MIGRATION status=deferred (page=(order|identity|password|history) reason=(meta_missing|route_missing|update_failed|readback_mismatch|exception)|reason=(marker_write|configuration_exception))' \
    | tail -n 1 || true
)
if [ -n "$route_migration_signal" ]; then
  printf '::error title=ORDENOWA route startup diagnostic::%s\n' "$route_migration_signal"
fi

cat "$redacted_diagnostics"
