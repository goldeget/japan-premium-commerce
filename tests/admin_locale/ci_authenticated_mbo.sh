# Source from the guarded disposable procurement acceptance process only.
authenticated_mbo_acceptance() {
  local helper_status=0 result=0 cleanup_status=0
  local raw="$private_dir/mbo-authenticated.private.json"
  local safe="$QA_ARTIFACT_DIR/native-mbo-authenticated-outcome.json"
  if KURANEA_CI_PROJECT_NAME="$CI_COMPOSE_PROJECT_NAME" bash tests/admin_locale/prepare_test_browserkit.sh \
      >"$private_dir/admin-test-dependencies.log" 2>&1; then
    compose exec -T -u www-data -e ADMIN_MAIL -e ADMIN_PASSWD prestashop \
      php /var/www/html/tests/admin_locale/native_mbo_error_authenticated.php \
      >"$raw" 2>"$private_dir/mbo-authenticated.stderr" || helper_status=$?
  else
    helper_status=$?
    printf '%s\n' '{"schema":1,"passed":false,"failed_stage":"test_only_dependency_bootstrap"}' >"$raw"
  fi

  python3 tests/admin_locale/safe_authenticated_outcome.py \
    --private-input "$raw" --safe-output "$safe" --helper-exit-status "$helper_status" || result=$?

  # The marker is created by this run's setup before any dependency files are
  # copied. A failed setup must never delete an unrelated pre-existing path.
  compose exec -T -u root -e "ORDENOWA_EXPECTED_PROJECT=$CI_COMPOSE_PROJECT_NAME" prestashop sh -euc '
    target=/tmp/owned/kuranea-admin-test-deps
    test "$KURANEA_CI_PROJECT_NAME" = "$ORDENOWA_EXPECTED_PROJECT"
    if [ -e "$target" ] || [ -L "$target" ]; then
      test ! -L /tmp/owned
      test ! -L "$target"
      test "$(realpath "$target")" = /tmp/owned/kuranea-admin-test-deps
      test -f "$target/.ordenowa-ci-project"
      test ! -L "$target/.ordenowa-ci-project"
      test "$(cat "$target/.ordenowa-ci-project")" = "$ORDENOWA_EXPECTED_PROJECT"
      rm -rf -- "$target"
    fi
  ' >"$private_dir/admin-test-dependencies-cleanup.log" 2>&1 || cleanup_status=$?

  python3 - "$safe" "$cleanup_status" <<'PYADMINCLEANUP' || result=1
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
if path.is_symlink():
    raise SystemExit(1)
value = json.loads(path.read_text(encoding='utf-8'))
clean = sys.argv[2] == '0'
value['test_dependencies_cleanup'] = 'success' if clean else 'failed'
value['passed'] = value.get('passed') is True and clean
path.write_text(json.dumps(value, sort_keys=True)+'\n', encoding='utf-8')
PYADMINCLEANUP
  if (( cleanup_status != 0 )); then result=1; fi
  return "$result"
}
