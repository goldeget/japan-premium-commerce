#!/usr/bin/env bash
set -euo pipefail
umask 077

phase=guard
on_error() {
  local status=$?
  printf 'FAIL admin kernel test dependencies stage=%s\n' "$phase" >&2
  exit "$status"
}
trap on_error ERR

[[ ${CI:-} == true && ${GITHUB_ACTIONS:-} == true && ${KURANEA_ISOLATED_CI:-} == 1 ]]
[[ ${GITHUB_RUN_ID:-} =~ ^[0-9]{1,20}$ && ${GITHUB_RUN_ATTEMPT:-} =~ ^[0-9]{1,8}$ ]]
expected_project="ordenowa-procurement-ci-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
[[ ${CI_COMPOSE_PROJECT_NAME:-} == "$expected_project" ]]
[[ ${KURANEA_CI_PROJECT_NAME:-} == "$expected_project" ]]
[[ ${PS_DOMAIN:-} == localhost:18081 ]]
[[ ${RUNNER_TEMP:-} == /* && -d ${RUNNER_TEMP:-/nonexistent} ]]

phase=stage_offline_source
browser_kit_commit=4f631476bb549d882a173c47bf693f3ef84c722d
css_selector_commit=5484e316cd8125f5215bbf829151e2211aa6d101
stage=$(mktemp -d "$RUNNER_TEMP/admin-kernel-test-deps.XXXXXXXX")
trap 'rm -rf -- "$stage"' EXIT
chmod 0700 "$stage"

stage_component() {
  local repository=$1
  local commit=$2
  local package=$3
  local checkout="$stage/checkout-$package"
  mkdir -m 0700 "$checkout" || return "$?"
  git -C "$checkout" init --quiet || return "$?"
  git -C "$checkout" remote add origin "https://github.com/$repository.git" || return "$?"
  git -C "$checkout" fetch --quiet --depth=1 origin "$commit" >/dev/null 2>&1 || return "$?"
  local actual
  actual=$(git -C "$checkout" rev-parse FETCH_HEAD) || return "$?"
  [[ "$actual" == "$commit" ]] || return 1
  git -C "$checkout" archive --format=tar "$commit" >"$stage/$package.tar" || return "$?"
  local digest
  digest=$(sha256sum "$stage/$package.tar" | cut -d ' ' -f 1) || return "$?"
  [[ "$digest" =~ ^[0-9a-f]{64}$ ]] || return 1
  printf '%s %s\n' "$commit" "$digest"
}

browser_kit_evidence=$(stage_component symfony/browser-kit "$browser_kit_commit" browser-kit)
css_selector_evidence=$(stage_component symfony/css-selector "$css_selector_commit" css-selector)
browser_kit_digest=${browser_kit_evidence##* }
browser_kit_verified=${browser_kit_evidence% *}
css_selector_digest=${css_selector_evidence##* }
css_selector_verified=${css_selector_evidence% *}
[[ "$browser_kit_verified" == "$browser_kit_commit" && "$css_selector_verified" == "$css_selector_commit" ]]

python3 - "$stage/source-revisions.json" "$browser_kit_commit" "$browser_kit_digest" \
  "$css_selector_commit" "$css_selector_digest" <<'PY'
import json
import re
import sys
from pathlib import Path

target = Path(sys.argv[1])
values = sys.argv[2:]
if len(values) != 4 or any(re.fullmatch(r"[0-9a-f]{40}", values[i]) is None for i in (0, 2)) \
        or any(re.fullmatch(r"[0-9a-f]{64}", values[i]) is None for i in (1, 3)):
    raise SystemExit(1)
manifest = {
    "symfony/browser-kit": {"version": "6.4.44", "source_commit": values[0], "archive_sha256": values[1]},
    "symfony/css-selector": {"version": "6.4.45", "source_commit": values[2], "archive_sha256": values[3]},
    "symfony/dom-crawler": {"version": "6.4.44", "source_commit": "998855f6c3699f148b54096d1d7d2b8b0b0fc298"},
}
target.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
target.chmod(0o600)
PY

phase=copy_to_isolated_container_tmp
compose=(docker compose -f compose.yaml -f tests/procurement/ci.compose.yaml -p "$CI_COMPOSE_PROJECT_NAME")
container_root=/tmp/owned/kuranea-admin-test-deps
"${compose[@]}" exec -T -u root prestashop sh -eu -c '
  test ! -L /tmp/owned
  if [ -e /tmp/owned ]; then test -d /tmp/owned; else install -d -o root -g root -m 0755 /tmp/owned; fi
  test "$(realpath /tmp/owned)" = /tmp/owned
  test ! -e /tmp/owned/kuranea-admin-test-deps
  test ! -L /tmp/owned/kuranea-admin-test-deps
  install -d -o root -g www-data -m 0750 /tmp/owned/kuranea-admin-test-deps
  printf "%s\n" "$KURANEA_CI_PROJECT_NAME" > /tmp/owned/kuranea-admin-test-deps/.ordenowa-ci-project
  install -d -o root -g www-data -m 0750 /tmp/owned/kuranea-admin-test-deps/source
' >/dev/null
"${compose[@]}" cp "$stage/browser-kit.tar" "prestashop:$container_root/browser-kit.tar" >/dev/null
"${compose[@]}" cp "$stage/css-selector.tar" "prestashop:$container_root/css-selector.tar" >/dev/null
"${compose[@]}" cp "$stage/source-revisions.json" "prestashop:$container_root/source-revisions.json" >/dev/null

phase=verify_and_extract
"${compose[@]}" exec -T -u root prestashop sh -eu -c '
  root=/tmp/owned/kuranea-admin-test-deps
  test "$(realpath "$root")" = "$root"
  case "$root" in /var/www/html|/var/www/html/*) exit 1;; esac
  test -f "$root/browser-kit.tar" -a -f "$root/css-selector.tar" -a -f "$root/source-revisions.json"
  browser_digest=$(php -r '\''$m=json_decode(file_get_contents($argv[1]), true); echo $m["symfony/browser-kit"]["archive_sha256"] ?? "";'\'' "$root/source-revisions.json")
  css_digest=$(php -r '\''$m=json_decode(file_get_contents($argv[1]), true); echo $m["symfony/css-selector"]["archive_sha256"] ?? "";'\'' "$root/source-revisions.json")
  printf "%s  %s\\n" "$browser_digest" "$root/browser-kit.tar" | sha256sum --check --status
  printf "%s  %s\\n" "$css_digest" "$root/css-selector.tar" | sha256sum --check --status
  mkdir -m 0750 "$root/source/browser-kit" "$root/source/css-selector"
  tar -xf "$root/browser-kit.tar" -C "$root/source/browser-kit"
  tar -xf "$root/css-selector.tar" -C "$root/source/css-selector"
  rm -f -- "$root/browser-kit.tar" "$root/css-selector.tar"
  test ! -e "$root/source/browser-kit/.git" -a ! -e "$root/source/css-selector/.git"
  test -f "$root/source/browser-kit/AbstractBrowser.php"
  test -f "$root/source/css-selector/CssSelectorConverter.php"
  chown -R root:www-data "$root"
  find "$root" -type d -exec chmod 0750 {} +
  find "$root" -type f -exec chmod 0640 {} +
  runuser -u www-data -- test -r "$root/source-revisions.json"
  runuser -u www-data -- test -r "$root/source/browser-kit/AbstractBrowser.php"
  runuser -u www-data -- test -r "$root/source/css-selector/CssSelectorConverter.php"
' >/dev/null

trap - EXIT
rm -rf -- "$stage"
printf 'PASS isolated admin test dependencies browser-kit=%s css-selector=%s\n' \
  "$browser_kit_commit" "$css_selector_commit"
