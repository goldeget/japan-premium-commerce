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
if [[ -n ${ORDENOWA_CI_IMAGE_REF:-} ]]; then
  [[ ${GITHUB_SHA:-} =~ ^[0-9a-f]{40}$ ]]
  [[ ${ORDENOWA_CI_SOURCE_SHA:-} == "$GITHUB_SHA" ]]
  [[ ${ORDENOWA_CI_ARCHIVE_SHA256:-} =~ ^[0-9a-f]{64}$ ]]
  [[ ${ORDENOWA_CI_IMAGE_ID:-} =~ ^sha256:[0-9a-f]{64}$ ]]
  [[ ${ORDENOWA_CI_IMAGE_REF:-} == "local-only/ordenowa-procurement-ci:run-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}" ]]
  release_prefix="$GITHUB_WORKSPACE/release-artifacts/ordenowa-prestashop-sha-$GITHUB_SHA"
  [[ ${ORDENOWA_CI_PACKAGE_PROOF:-} == "$release_prefix.package.json" ]]
  [[ ${ORDENOWA_CI_RELEASE_MANIFEST:-} == "$release_prefix.release.json" ]]
  [[ ${ORDENOWA_CI_ARCHIVE_PATH:-} == "$release_prefix.docker.tar" ]]
  [[ ${ORDENOWA_CI_PACKAGE_SELECTION:-} == "$QA_ARTIFACT_DIR/ci-package-selection.json" ]]
fi
private_dir=$(mktemp -d "$RUNNER_TEMP/procurement-private.XXXXXXXX")
mkdir -p "$QA_ARTIFACT_DIR"
export PROCUREMENT_IDENTITY_FILE="$private_dir/identity.json"
compose() {
  local -a files=(-f compose.yaml -f tests/procurement/ci.compose.yaml)
  if [[ -n ${ORDENOWA_CI_IMAGE_REF:-} ]]; then
    files+=(-f tests/procurement/ci.package.compose.yaml)
  fi
  docker compose "${files[@]}" -p "$CI_COMPOSE_PROJECT_NAME" "$@"
}
source tests/procurement/ci_acceptance_copy.sh
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
required = ('image_build','fresh_install','native_source','module_seed','native_gallery','requests_database','requests_behavior','requests_concurrency','points_behavior','points_concurrency','notifications_behavior','notifications_native','notifications_concurrency','notifications_health','native_boundary','native_push_settings','policies_behavior','policies_concurrency','policies_smarty','support_database','support_concurrency_review','support_controller','support_smarty','customer_ui','customer_smarty','navigation_smarty','signin_smarty','pwa_worker','pwa_registration','native_browser','native_notifications','native_push_provider','native_accounts','native_acl','native_quality','durable_readback','restart_readback','restart_source','restore')
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
  if [[ -n ${ORDENOWA_CI_IMAGE_REF:-} ]]; then
    : >"$private_dir/image-build.log"
    if compose config --format json >"$private_dir/compose-config.json" 2>"$private_dir/image-build.log"; then
      :
    else
      setup_status=$?
      python3 tests/procurement/ci_safe_failure.py image_build "$private_dir/image-build.log" "$QA_ARTIFACT_DIR/image-build-outcome.json" "$setup_status" || :
      return "$setup_status"
    fi
    python3 tools/release/ci_release.py verify \
      --root "$GITHUB_WORKSPACE" \
      --package-proof "$ORDENOWA_CI_PACKAGE_PROOF" \
      --release-manifest "$ORDENOWA_CI_RELEASE_MANIFEST" \
      --archive "$ORDENOWA_CI_ARCHIVE_PATH" \
      --source-sha "$GITHUB_SHA" \
      --image-ref "$ORDENOWA_CI_IMAGE_REF" \
      --image-id "$ORDENOWA_CI_IMAGE_ID" \
      --selection "$ORDENOWA_CI_PACKAGE_SELECTION" \
      --compose-config "$private_dir/compose-config.json" \
      >>"$private_dir/image-build.log" 2>&1 || return "$?"
    python3 tests/procurement/ci_safe_failure.py image_build "$private_dir/image-build.log" "$QA_ARTIFACT_DIR/image-build-outcome.json" 0
    return "$?"
  fi
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
copy_acceptance_files
if [[ -n ${ORDENOWA_CI_IMAGE_REF:-} ]]; then
  # Runtime identity is attested only after package mode has skipped every
  # application source copy and permission repair.
  [[ ${ORDENOWA_APPLICATION_HOT_COPY:-} == false ]]
  app_container=$(compose ps -q prestashop)
  [[ $app_container =~ ^[0-9a-f]{12,64}$ ]]
  observed_image_id=$(docker inspect --format '{{.Image}}' "$app_container")
  observed_image_ref=$(docker inspect --format '{{.Config.Image}}' "$app_container")
  python3 tools/release/ci_release.py attest-runtime \
    --selection "$ORDENOWA_CI_PACKAGE_SELECTION" \
    --output "$QA_ARTIFACT_DIR/package-runtime-binding.json" \
    --image-id "$observed_image_id" \
    --image-ref "$observed_image_ref" \
    --application-hot-copy "$ORDENOWA_APPLICATION_HOT_COPY"
fi
# No credentials/identity data are emitted; only a private file crosses the
# container boundary and is deleted at the end of this acceptance process.
seed_module() {
  local seed_status=0
  compose exec -T -u www-data prestashop php /tmp/ordenowa-procurement-ci/ci_seed.php || seed_status=$?
  # This file contains only fixed public class names, enums, counts and booleans.
  # Copy it on failure as well, before the private log/container cleanup.
  if ! compose cp prestashop:/tmp/ordenowa-procurement-ci/seed-metadata-outcome.json "$QA_ARTIFACT_DIR/seed-metadata-outcome.json" >/dev/null 2>&1; then
    if (( seed_status == 0 )); then return 1; fi
  fi
  return "$seed_status"
}
run_phase module_seed seed_module
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

health_snapshot_acceptance() {
  behavior notifications_health || return "$?"
  local health_exit=0
  compose exec -T -u www-data prestashop php /var/www/html/modules/ordenowaprocurement/bin/health-snapshot.php --shop=1 >"$private_dir/health-native.json" || health_exit=$?
  python3 - "$private_dir/health-native.json" "$QA_ARTIFACT_DIR/health-snapshot-outcome.json" "$health_exit" <<'PYHEALTH'
import json, math, sys
from pathlib import Path

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result

outcome = {"schema": 1, "scope": "native_cli_snapshot_schema_and_exit", "passed": False,
           "bootstrap_side_effects_instrumented": False}
try:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    required = {"status", "shop_id", "database_select_1", "disk_free_ratio", "notification_counts"}
    count_keys = {"backlog", "future_retry", "undelivered_events", "failed", "uncertain", "oldest_stale_age_seconds"}
    expected_exit = {"ok": 0, "warning": 1, "critical": 2}
    if type(data) is not dict or set(data) != required:
        raise ValueError("shape")
    if data["status"] not in expected_exit or int(sys.argv[3]) != expected_exit[data["status"]]:
        raise ValueError("status")
    if type(data["shop_id"]) is not int or data["shop_id"] != 1 or data["database_select_1"] is not True:
        raise ValueError("shop")
    ratio = data["disk_free_ratio"]
    if type(ratio) not in (int, float) or not math.isfinite(ratio) or not 0 <= ratio <= 1:
        raise ValueError("disk")
    counts = data["notification_counts"]
    if type(counts) is not dict or set(counts) != count_keys:
        raise ValueError("counts")
    if any(type(value) is not int or not 0 <= value <= 2147483647 for value in counts.values()):
        raise ValueError("count bounds")
    outcome.update(passed=True, exit_code=int(sys.argv[3]), snapshot=data)
except (OSError, UnicodeError, ValueError, TypeError, KeyError, OverflowError):
    outcome["failure_code"] = "health_snapshot_schema_or_exit"
Path(sys.argv[2]).write_text(json.dumps(outcome, sort_keys=True) + "\n", encoding="utf-8")
raise SystemExit(0 if outcome["passed"] else 1)
PYHEALTH
}
run_phase notifications_health health_snapshot_acceptance

# These isolated database contracts are independent of the native admin HTTP
# fixture. Preserve their evidence even if that later boundary finds a defect.
run_phase policies_behavior behavior policies_behavior
run_phase policies_concurrency behavior policies_concurrency

source tests/admin_locale/ci_authenticated_mbo.sh
native_boundaries() {
  behavior native_integration_test || return "$?"
  compose exec -T -u www-data -e PROCUREMENT_TEST_DSN='mysql:host=mariadb;dbname=ordenowa_procurement_test;charset=utf8mb4' \
    -e PROCUREMENT_TEST_USER=root -e "PROCUREMENT_TEST_PASSWORD=$MARIADB_ROOT_PASSWORD" prestashop php /var/www/html/tests/admin_locale/korean_tab_labels.php || return "$?"
  compose exec -T -u www-data prestashop php /var/www/html/tests/admin_locale/twig_warmup_templates.php || return "$?"
  compose exec -T -u www-data prestashop php /var/www/html/tests/admin_locale/copy_language_labels.php || return "$?"
  compose exec -T -u www-data prestashop php /var/www/html/tests/admin_locale/locale_lifecycle.php /var/www/html/vendor/autoload.php /var/www/html || return "$?"
  local native_cli_memory_limit
  native_cli_memory_limit=$(compose exec -T -u www-data prestashop php -r 'echo ini_get("memory_limit");') || return "$?"
  # Exercise the actual native warmer with the image's default CLI memory.
  # No memory override, no --no-warmup, and no hidden failed command.
  compose exec -T -u www-data prestashop php /var/www/html/bin/console cache:clear --env=prod --no-debug || return "$?"
  compose exec -T -u www-data prestashop php /var/www/html/tests/admin_locale/native_mbo_error_render.php >"$QA_ARTIFACT_DIR/native-mbo-error-render.json" || return "$?"
  authenticated_mbo_acceptance || return "$?"
  authenticated_facebook_acceptance || return "$?"
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
