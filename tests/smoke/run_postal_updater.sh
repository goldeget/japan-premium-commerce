#!/usr/bin/env bash
set -euo pipefail

project_name=${1:?Pass the unique Compose project name}
temp_dir=${RUNNER_TEMP:-${TMPDIR:-/tmp}}
log_file=$(mktemp "$temp_dir/kuranea-postal-updater.XXXXXX")
cleanup() {
  rm -f -- "$log_file"
}
trap cleanup EXIT

if docker compose -p "$project_name" exec -T prestashop \
  runuser -g www-data -u www-data -- \
  /var/www/html/modules/kuraneapostcode/bin/update-ken-all.sh \
  >"$log_file" 2>&1; then
  cat "$log_file"
  exit 0
else
  updater_exit=$?
fi

safe_line=$(grep -E '^KURANEA_POSTAL_DOWNLOAD_FAILURE curl_exit=[0-9]+ http_status=([0-9]{3}|unknown) effective_host=(unavailable|[A-Za-z0-9.-]+)$' "$log_file" | tail -n 1 || true)
if [ -n "$safe_line" ]; then
  printf '%s\n' "$safe_line" >> "${GITHUB_STEP_SUMMARY:?GitHub Actions step summary is unavailable}"
  printf '::error title=Japan Post postcode update::%s\n' "$safe_line"
else
  safe_message='Japan Post address data updater/import failed; raw updater output was suppressed.'
  printf '%s\n' "$safe_message" >> "${GITHUB_STEP_SUMMARY:?GitHub Actions step summary is unavailable}"
  printf '::error title=Japan Post postcode update::%s\n' "$safe_message"
fi

exit "$updater_exit"
