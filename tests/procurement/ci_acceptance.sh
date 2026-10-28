#!/usr/bin/env bash
# One full acceptance entry point; all targets/volumes belong to this run.
set -euo pipefail
umask 077
[[ ${CI:-} == true && ${KURANEA_ISOLATED_CI:-} == 1 ]]
[[ ${GITHUB_RUN_ID:-} =~ ^[0-9]+$ && ${GITHUB_RUN_ATTEMPT:-} =~ ^[0-9]+$ ]]
[[ ${CI_COMPOSE_PROJECT_NAME:-} == "ordenowa-procurement-ci-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}" ]]
[[ ${RUNNER_TEMP:-} == /* && -d $RUNNER_TEMP ]]
[[ ${SHOP_BASE_URL:-} == http://localhost:18081 && ${SHOP_PORT:-} == 18081 ]]
[[ ${PS_DOMAIN:-} == localhost:18081 ]]
[[ ${QA_ARTIFACT_DIR:-} == "$RUNNER_TEMP"/* ]]
private_dir=$(mktemp -d "$RUNNER_TEMP/procurement-private.XXXXXXXX")
mkdir -p "$QA_ARTIFACT_DIR"
export PROCUREMENT_IDENTITY_FILE="$private_dir/identity.json"
compose() { docker compose -f compose.yaml -f tests/procurement/ci.compose.yaml -p "$CI_COMPOSE_PROJECT_NAME" "$@"; }
outcomes="$QA_ARTIFACT_DIR/outcomes.tsv"
: > "$outcomes"
phase=guard
finish() {
  local result=$?
  trap - EXIT
  if (( result != 0 )); then
    printf '%s\tfailed\n' "$phase" >> "$outcomes"
    printf 'FAIL procurement acceptance phase=%s exit=%d\n' "$phase" "$result" >&2
  fi
  python3 - "$outcomes" "$QA_ARTIFACT_DIR/outcome.json" "$result" <<'PY'
import json, sys
from pathlib import Path
outcomes = {}
for line in Path(sys.argv[1]).read_text().splitlines():
    phase, status = line.split('\t')
    outcomes[phase] = status
required = ('image_build','fresh_install','native_source','module_seed','native_gallery','requests_database','requests_behavior','requests_concurrency','points_behavior','points_concurrency','notifications_behavior','notifications_native','notifications_concurrency','native_boundary','native_push_settings','policies_behavior','policies_concurrency','policies_smarty','support_database','support_concurrency_review','support_controller','support_smarty','customer_ui','customer_smarty','navigation_smarty','signin_smarty','pwa_worker','pwa_registration','native_browser','native_notifications','native_push_provider','native_accounts','native_acl','native_quality','durable_readback','restart_readback','restart_source','restore')
Path(sys.argv[2]).write_text(json.dumps({'passed':int(sys.argv[3]) == 0 and all(outcomes.get(x) == 'passed' for x in required),
    'phases':{x:outcomes.get(x,'not_run') for x in required}}, sort_keys=True) + '\n')
PY
  rm -f -- "$outcomes"
  rm -rf -- "$private_dir"
  exit "$result"
}
trap finish EXIT
run_phase() {
  phase=$1
  shift
  if "$@" >"$private_dir/$phase.log" 2>&1; then
    printf '%s\tpassed\n' "$phase" >> "$outcomes"
    printf 'PASS procurement acceptance phase=%s\n' "$phase"
  else
    local result=$?
    # Private logs may include SQL/token/native identity data. Do not upload
    # them or print exception messages. The fixed phase locates the failure.
    printf 'FAIL procurement acceptance phase=%s exit=%d\n' "$phase" "$result" >&2
    # Only the setup classifier's already-redacted JSON may expose bounded
    # build/startup error evidence. Raw install logs remain private.
    if [[ $phase == image_build ]]; then
      python3 tests/procurement/ci_safe_failure.py emit "$QA_ARTIFACT_DIR/image-build-outcome.json" || :
    elif [[ $phase == fresh_install ]]; then
      python3 tests/procurement/ci_safe_failure.py emit "$QA_ARTIFACT_DIR/runtime-start-outcome.json" || :
    fi
    python3 - "$private_dir/$phase.log" <<'PYSAFE'
import re, sys
from pathlib import Path
content = Path(sys.argv[1]).read_text(errors='replace')
for line in content.splitlines():
    if re.fullmatch(r'FAIL procurement (?:browser|MIME) stage=[a-z_]+ type=[A-Za-z_]+',line):
        print(line, file=sys.stderr)
    elif re.fullmatch(r'FAIL procurement browser source=ci_browser\.py:[0-9]+',line):
        print(line, file=sys.stderr)
    elif re.fullmatch(r'FAIL procurement accounts (?:stage=[a-z_]+ type=[A-Za-z_]+|source=accounts_browser\.py:[0-9]+)',line):
        print(line, file=sys.stderr)
    elif re.fullmatch(r'FAIL procurement source integrity phase=(?:native_source|restart_source)',line):
        print(line, file=sys.stderr)
    elif re.fullmatch(r'FAIL procurement quality stage=[a-z_]+',line):
        print(line, file=sys.stderr)
    elif re.fullmatch(r'FAIL native ACL browser stage=[a-z_]+',line):
        print(line, file=sys.stderr)
    elif re.fullmatch(r'FAIL procurement native acceptance: [A-Za-z_\\]+ source=[A-Za-z0-9_.-]+:[0-9]+',line):
        print(line, file=sys.stderr)
match = re.search(r'(?:/tests/(?:procurement|catalog)/|/modules/ordenowaprocurement/)([A-Za-z0-9_./-]+\.php)(?:\(|:(?:[ ]*)| on line )([0-9]+)',content)
if match:
    print('Failure source=' + match[1] + ':' + match[2], file=sys.stderr)
PYSAFE
    return "$result"
  fi
}
wait_install() {
  for ((retry=0; retry<180; retry++)); do
    if compose exec -T prestashop test -f /var/www/html/var/.kuranea-bootstrap-v2 >/dev/null 2>&1 &&
       curl --silent --fail --output /dev/null "$SHOP_BASE_URL/admin-kuranea/login"; then
      return 0
    fi
    container=$(compose ps -q prestashop)
    if [[ -n $container ]]; then
      read -r restarts exit_code < <(docker inspect --format '{{.RestartCount}} {{.State.ExitCode}}' "$container")
      if [[ $restarts =~ ^[0-9]+$ && $exit_code =~ ^[0-9]+$ ]] && (( restarts >= 3 && exit_code != 0 )); then
        printf 'FAIL procurement install stage=persistent_container_restart\n' >&2
        docker logs --tail 200 "$container" 2>&1 | python3 -c '
import re,sys
content=sys.stdin.read()
classes=sorted(set(re.findall(r"Uncaught ([A-Za-z_\\]+)",content)))
sites=re.findall(r"/([A-Za-z0-9_.-]+\.php)(?::| on line )([0-9]+)",content)
for kind in classes[:3]:
    source=sites[-1] if sites else ("unknown.php","0")
    print("FAIL procurement native acceptance: "+kind+" source="+source[0]+":"+source[1],file=sys.stderr)
'
        return 1
      fi
    fi
    sleep 5
  done
  return 1
}
phase=fresh_install
# Existing projects, including stopped containers, are never repurposed.
[[ -z $(compose ps -aq) ]]
for volume in mariadb_data prestashop_html catalog_review_data; do
  if docker volume inspect "${CI_COMPOSE_PROJECT_NAME}_$volume" >/dev/null 2>&1; then
    printf 'BLOCKED: run-scoped volume already exists\n' >&2
    exit 77
  fi
done
image_build() {
  local setup_status
  if compose config --quiet >"$private_dir/image-build.log" 2>&1; then
    :
  else
    setup_status=$?
    python3 tests/procurement/ci_safe_failure.py image_build "$private_dir/image-build.log" "$QA_ARTIFACT_DIR/image-build-outcome.json" "$setup_status" || :
    return "$setup_status"
  fi
  if compose build prestashop >>"$private_dir/image-build.log" 2>&1; then
    python3 tests/procurement/ci_safe_failure.py image_build "$private_dir/image-build.log" "$QA_ARTIFACT_DIR/image-build-outcome.json" 0
  else
    setup_status=$?
    python3 tests/procurement/ci_safe_failure.py image_build "$private_dir/image-build.log" "$QA_ARTIFACT_DIR/image-build-outcome.json" "$setup_status" || :
    return "$setup_status"
  fi
}
fresh_install() {
  local setup_status
  if compose up --detach --no-build >"$private_dir/install.log" 2>&1; then
    python3 tests/procurement/ci_safe_failure.py runtime_start "$private_dir/install.log" "$QA_ARTIFACT_DIR/runtime-start-outcome.json" 0 || return "$?"
  else
    setup_status=$?
    python3 tests/procurement/ci_safe_failure.py runtime_start "$private_dir/install.log" "$QA_ARTIFACT_DIR/runtime-start-outcome.json" "$setup_status" || :
    return "$setup_status"
  fi
  wait_install
}
run_phase image_build image_build
run_phase fresh_install fresh_install
run_phase native_source python3 tests/procurement/source_integrity.py native_source
phase=copy_acceptance
# The integration diagnostic may run while peers finish source changes. A
# committed Actions checkout copies identical module files from the same SHA.
compose cp modules/ordenowaprocurement/. prestashop:/var/www/html/modules/ordenowaprocurement/
compose cp themes/kuranea/templates/_partials/footer.tpl prestashop:/var/www/html/themes/kuranea/templates/_partials/footer.tpl
compose cp themes/kuranea/templates/_partials/header.tpl prestashop:/var/www/html/themes/kuranea/templates/_partials/header.tpl
compose cp themes/kuranea/templates/customer/my-account.tpl prestashop:/var/www/html/themes/kuranea/templates/customer/my-account.tpl
compose exec -T prestashop sh -ec 'chown www-data:www-data /var/www/html/themes/kuranea/templates/_partials/footer.tpl /var/www/html/themes/kuranea/templates/_partials/header.tpl /var/www/html/themes/kuranea/templates/customer/my-account.tpl; chmod 0644 /var/www/html/themes/kuranea/templates/_partials/footer.tpl /var/www/html/themes/kuranea/templates/_partials/header.tpl /var/www/html/themes/kuranea/templates/customer/my-account.tpl; chown -R www-data:www-data /var/www/html/modules/ordenowaprocurement; find /var/www/html/modules/ordenowaprocurement -type d -exec chmod 0755 {} +; find /var/www/html/modules/ordenowaprocurement -type f -exec chmod 0644 {} +'
compose exec -T prestashop mkdir -p /tmp/ordenowa-procurement-ci/catalog /var/www/html/tests/procurement /var/www/html/tests/catalog /var/www/html/tests/admin_audit /var/www/html/tests/admin_locale
for source in tests/procurement/ci_*.php; do
  compose cp "$source" prestashop:/tmp/ordenowa-procurement-ci/
done
for source in tests/procurement/requests*.php tests/procurement/points*.php tests/procurement/native*.php tests/procurement/customer*.php tests/procurement/notifications*.php tests/procurement/policies*.php tests/procurement/support*.php tests/procurement/navigation*.php tests/procurement/signin*.php tests/procurement/language*.php; do
  compose cp "$source" prestashop:/var/www/html/tests/procurement/
done
compose cp tests/catalog/. prestashop:/tmp/ordenowa-procurement-ci/catalog/
compose cp tests/catalog/. prestashop:/var/www/html/tests/catalog/
compose cp tests/admin_audit/. prestashop:/var/www/html/tests/admin_audit/
compose cp tests/admin_locale/. prestashop:/var/www/html/tests/admin_locale/
compose cp tests/procurement/accounts_native.php prestashop:/tmp/ordenowa-procurement-ci/accounts_native.php
compose exec -T prestashop sh -ec 'find /var/www/html/tests /tmp/ordenowa-procurement-ci -type d -exec chmod 0755 {} +; find /var/www/html/tests /tmp/ordenowa-procurement-ci -type f -exec chmod 0644 {} +'
compose exec -T prestashop chown -R www-data:www-data /tmp/ordenowa-procurement-ci
# No credentials/identity data are emitted; only a private file crosses the
# container boundary and is deleted at the end of this acceptance process.
run_phase module_seed compose exec -T -u www-data prestashop php /tmp/ordenowa-procurement-ci/ci_seed.php
run_phase native_gallery compose exec -T -u www-data prestashop php /tmp/ordenowa-procurement-ci/ci_gallery.php
compose cp prestashop:/tmp/ordenowa-procurement-ci/identity.json "$PROCUREMENT_IDENTITY_FILE" > /dev/null
phase=behavior_database
compose exec -T mariadb sh -ec 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb -uroot -e "CREATE DATABASE ordenowa_procurement_test CHARACTER SET utf8mb4"'
behavior() {
  compose exec -T -u www-data -e PROCUREMENT_TEST_DSN='mysql:host=mariadb;dbname=ordenowa_procurement_test;charset=utf8mb4' \
    -e PROCUREMENT_TEST_USER=root -e "PROCUREMENT_TEST_PASSWORD=$MARIADB_ROOT_PASSWORD" prestashop php "/var/www/html/tests/procurement/$1.php"
}
run_phase requests_database behavior requests_database
run_phase requests_behavior behavior requests_behavior
run_phase requests_concurrency behavior requests_concurrency
run_phase points_behavior behavior points_behavior
run_phase points_concurrency behavior points_concurrency
run_phase notifications_behavior behavior notifications_behavior
run_phase notifications_native behavior notifications_native
run_phase notifications_concurrency behavior notifications_concurrency
native_boundaries() {
  behavior native_integration_test || return "$?"
  compose exec -T -u www-data -e PROCUREMENT_TEST_DSN='mysql:host=mariadb;dbname=ordenowa_procurement_test;charset=utf8mb4' \
    -e PROCUREMENT_TEST_USER=root -e "PROCUREMENT_TEST_PASSWORD=$MARIADB_ROOT_PASSWORD" prestashop php /var/www/html/tests/admin_locale/korean_tab_labels.php || return "$?"
  compose exec -T -u www-data prestashop php /var/www/html/tests/admin_locale/twig_warmup_templates.php || return "$?"
  local native_cli_memory_limit
  native_cli_memory_limit=$(compose exec -T -u www-data prestashop php -r 'echo ini_get("memory_limit");') || return "$?"
  # Exercise the actual native warmer with the image's default CLI memory.
  # No memory override, no --no-warmup, and no hidden failed command.
  compose exec -T -u www-data prestashop php /var/www/html/bin/console cache:clear --env=prod --no-debug || return "$?"
  python3 - "$QA_ARTIFACT_DIR/cache-warmup-outcome.json" "$native_cli_memory_limit" <<'PYCACHE'
import json,sys
from pathlib import Path
value=sys.argv[2]
if not value or len(value)>32 or any(character not in '-0123456789KMGkmg' for character in value):
    raise SystemExit(1)
Path(sys.argv[1]).write_text(json.dumps({'passed':True,'native_default_cli_memory_limit':value,'memory_override':False,'warmup_enabled':True,'user':'www-data','debug':False},sort_keys=True)+'\n')
PYCACHE
}
run_phase native_boundary native_boundaries
run_phase native_push_settings behavior native_push_settings
run_phase policies_behavior behavior policies_behavior
run_phase policies_concurrency behavior policies_concurrency
run_phase policies_smarty behavior policies_smarty
run_phase support_database behavior support_database
run_phase support_concurrency_review behavior support_concurrency_review
run_phase support_controller behavior support_controller
run_phase support_smarty behavior support_smarty
run_phase customer_ui behavior customer_ui
run_phase customer_smarty behavior customer_smarty
navigation_contracts() {
  behavior navigation_smarty || return "$?"
  behavior language_selector_smarty
}
run_phase navigation_smarty navigation_contracts
run_phase signin_smarty behavior signin_smarty
run_phase pwa_worker node tests/procurement/pwa_worker.cjs
run_phase pwa_registration node tests/procurement/pwa_registration.cjs
run_phase native_browser python3 tests/procurement/ci_browser.py
run_phase native_notifications bash tests/procurement/ci_notification_flow.sh
run_phase native_push_provider compose exec -T -u www-data prestashop php /tmp/ordenowa-procurement-ci/ci_push_provider.php
run_phase native_accounts python3 tests/procurement/accounts_browser.py
run_phase native_acl python3 tests/procurement/acl_browser.py
run_phase native_quality python3 tests/procurement/quality_browser.py
run_phase durable_readback compose exec -T -u www-data prestashop php /tmp/ordenowa-procurement-ci/ci_readback.php manifest
phase=restart
compose restart mariadb prestashop >"$private_dir/restart.log" 2>&1
run_phase restart_readback wait_install
run_phase restart_source python3 tests/procurement/source_integrity.py restart_source
run_phase restart_readback compose exec -T -u www-data prestashop php /tmp/ordenowa-procurement-ci/ci_readback.php compare
run_phase restore bash tests/procurement/ci_restore.sh
