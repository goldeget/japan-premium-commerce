# Source from the guarded disposable procurement acceptance process only.
authenticated_mbo_acceptance() {
  authenticated_admin_probe mbo
}

authenticated_facebook_acceptance() {
  authenticated_admin_probe facebook
}

authenticated_admin_probe() {
  local probe=$1 php_helper collector artifact
  case "$probe" in
    mbo)
      php_helper=native_mbo_error_authenticated.php
      collector=safe_authenticated_outcome.py
      artifact=native-mbo-authenticated-outcome.json ;;
    facebook)
      php_helper=native_facebook_transport_fallback.php
      collector=
      artifact=native-facebook-transport-outcome.json ;;
    *) return 64 ;;
  esac
  local helper_status=0 result=0 cleanup_status=0 visual_status=not_run
  local raw="$private_dir/$probe-authenticated.private.json"
  local safe="$QA_ARTIFACT_DIR/$artifact"
  if KURANEA_CI_PROJECT_NAME="$CI_COMPOSE_PROJECT_NAME" bash tests/admin_locale/prepare_test_browserkit.sh \
      >"$private_dir/admin-test-dependencies.log" 2>&1; then
    if [[ "$probe" == facebook ]]; then
      source tests/admin_locale/run_native_facebook_cases.sh
      native_facebook_fresh_case_acceptance || result=$?
    else
      compose exec -T -u www-data -e ADMIN_MAIL -e ADMIN_PASSWD prestashop \
        php "/var/www/html/tests/admin_locale/$php_helper" \
        >"$raw" 2>"$private_dir/$probe-authenticated.stderr" || helper_status=$?
      python3 "tests/admin_locale/$collector" \
        --private-input "$raw" --safe-output "$safe" --helper-exit-status "$helper_status" || result=$?
    fi
  else
    helper_status=$?
    python3 - "$safe" <<'PYADMINPREPFAIL' || result=1
import json, sys
from pathlib import Path
with Path(sys.argv[1]).open('x', encoding='utf-8') as stream:
    stream.write(json.dumps({'schema':1,'passed':False,'failed_stage':'test_only_dependency_bootstrap'})+'\n')
PYADMINPREPFAIL
    result=1
  fi

  if (( result == 0 )); then
    authenticated_admin_visual "$probe" "$safe" || result=$?
    if (( result == 0 )); then visual_status=passed; else visual_status=failed; fi
  fi

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

  python3 - "$safe" "$cleanup_status" "$visual_status" <<'PYADMINCLEANUP' || result=1
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
if path.is_symlink():
    raise SystemExit(1)
value = json.loads(path.read_text(encoding='utf-8'))
clean = sys.argv[2] == '0'
value['test_dependencies_cleanup'] = 'success' if clean else 'failed'
value['private_snapshot_visual'] = sys.argv[3]
value['passed'] = value.get('passed') is True and clean and sys.argv[3] == 'passed'
path.write_text(json.dumps(value, sort_keys=True)+'\n', encoding='utf-8')
PYADMINCLEANUP
  if (( cleanup_status != 0 )); then result=1; fi
  return "$result"
}

authenticated_admin_visual() {
  local probe=$1 safe=$2 result=0 snapshot_hash
  local snapshot="$private_dir/$probe-snapshot.private.html"
  local raw_render="$private_dir/$probe-renderer.private.json"
  local visual_outcome="$QA_ARTIFACT_DIR/$probe-native-kernelbrowser-visual-outcome.json"
  snapshot_hash=$(python3 - "$safe" "$probe" <<'PYADMINSNAPSHOTHASH'
import json, re, sys
from pathlib import Path
value=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
branch='mbo_error_render' if sys.argv[2]=='mbo' else 'facebook_transport_fallback'
digest=value[branch]['private_response_snapshot_sha256']
if value.get('passed') is not True or not isinstance(digest,str) or re.fullmatch('[0-9a-f]{64}',digest) is None:
    raise SystemExit(1)
print(digest)
PYADMINSNAPSHOTHASH
  ) || result=1
  if (( result == 0 )); then
    compose cp "prestashop:/tmp/owned/kuranea-admin-test-deps/private-snapshots/$probe.html" "$snapshot" \
      >"$private_dir/$probe-snapshot-copy.log" 2>&1 || result=1
  fi
  if (( result == 0 )); then
    python3 tests/admin_locale/snapshot_visual.py --kind "$probe" \
      --private-html "$snapshot" --private-dir "$private_dir" \
      --artifact-dir "$QA_ARTIFACT_DIR" --runner-temp "$RUNNER_TEMP" \
      --expected-sha256 "$snapshot_hash" >"$raw_render" 2>"$private_dir/$probe-renderer.stderr" || result=$?
  fi
  rm -f -- "$snapshot" || result=1
  python3 - "$raw_render" "$visual_outcome" "$probe" "$snapshot_hash" "$result" <<'PYADMINVISUALOUTCOME' || result=1
import json, re, sys
from pathlib import Path
result={'schema':1,'passed':False,'kind':sys.argv[3],'failure_code':'private_snapshot_visual_failed'}
try:
    value=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    if (sys.argv[5]=='0' and value.get('passed') is True and value.get('kind')==sys.argv[3]
            and value.get('render_scope')=='chromium_render_of_native_kernelbrowser_snapshot'
            and value.get('native_response_snapshot_sha256')==sys.argv[4]):
        result={'schema':1,'passed':True,'kind':sys.argv[3],
                'render_scope':value['render_scope'],'native_response_snapshot_sha256':sys.argv[4]}
    else:
        code=value.get('failure_code')
        if isinstance(code,str) and re.fullmatch('[a-z_]{1,80}',code): result['failure_code']=code
except (OSError, ValueError, TypeError, AttributeError):
    pass
with Path(sys.argv[2]).open('x',encoding='utf-8') as stream: stream.write(json.dumps(result,sort_keys=True)+'\n')
raise SystemExit(0 if result['passed'] else 1)
PYADMINVISUALOUTCOME
  return "$result"
}
