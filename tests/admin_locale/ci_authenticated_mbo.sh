# Source from the guarded disposable procurement acceptance process only.
authenticated_mbo_acceptance() {
  authenticated_admin_probe mbo
}

authenticated_facebook_acceptance() {
  authenticated_admin_probe facebook
}

# Keep evidence for both independent probes, while requiring both to pass.
authenticated_admin_pair_acceptance() {
  local mbo_status=0 facebook_status=0
  authenticated_mbo_acceptance || mbo_status=$?
  authenticated_facebook_acceptance || facebook_status=$?
  if (( mbo_status != 0 || facebook_status != 0 )); then
    return 1
  fi
  return 0
}

# Copy only a marker-owned private diagnostic capture, encrypt it to the
# repository's pinned public recipient, and immediately remove runner plaintext.
# This helper never prints response data, URLs, tokens, or encryption details.
native_admin_encrypt_private_capture() {
  local kind=$1 snapshot artifact container_path host_plain cipher_tmp recipient expected_fp actual_fp status=0
  case "$kind" in
    mbo-auth-landing)
      snapshot='mbo-auth-landing.html'
      artifact='mbo-auth-landing-encrypted.cms' ;;
    facebook-unauthenticated)
      snapshot='facebook-unauthenticated.html'
      artifact='facebook-unauthenticated-encrypted.cms' ;;
    *) return 64 ;;
  esac

  [[ ${CI:-} == true && ${KURANEA_ISOLATED_CI:-} == 1 && ${GITHUB_ACTIONS:-} == true ]] || return 1
  [[ ${GITHUB_RUN_ID:-} =~ ^[0-9]{1,20}$ && ${GITHUB_RUN_ATTEMPT:-} =~ ^[0-9]{1,8}$ ]] || return 1
  [[ ${CI_COMPOSE_PROJECT_NAME:-} == "ordenowa-procurement-ci-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}" ]] || return 1
  [[ ${RUNNER_TEMP:-} == /* && -d $RUNNER_TEMP && ! -L $RUNNER_TEMP ]] || return 1
  [[ ${QA_ARTIFACT_DIR:-} == "$RUNNER_TEMP/procurement-safe-artifacts" && -d $QA_ARTIFACT_DIR && ! -L $QA_ARTIFACT_DIR ]] || return 1
  [[ ${private_dir:-} == "$RUNNER_TEMP"/procurement-private.* && -d $private_dir && ! -L $private_dir ]] || return 1
  [[ ${GITHUB_WORKSPACE:-} == /* && -d $GITHUB_WORKSPACE ]] || return 1

  recipient="$GITHUB_WORKSPACE/tests/admin_locale/qa-debug-recipient.pem"
  [[ ${ORDENOWA_NATIVE_AUTH_DEBUG_RECIPIENT:-} == "$recipient" && -f $recipient && ! -L $recipient ]] || return 1
  [[ $(realpath "$recipient") == "$recipient" ]] || return 1
  command -v openssl >/dev/null 2>&1 || return 1
  expected_fp='sha256 Fingerprint=0C:8E:7D:03:B9:FE:49:A0:88:01:C7:0F:5C:06:16:CA:20:31:9F:1E:B2:6B:DB:AA:FD:CD:D8:59:92:D2:7C:0D'
  actual_fp=$(openssl x509 -in "$recipient" -noout -fingerprint -sha256 2>/dev/null) || return 1
  [[ $actual_fp == "$expected_fp" ]] || return 1

  container_path="/tmp/owned/kuranea-admin-test-deps/private-snapshots/$snapshot"
  host_plain="$private_dir/$kind.private.json"
  [[ ! -e $host_plain && ! -L $host_plain ]] || return 1
  [[ ! -e "$QA_ARTIFACT_DIR/$artifact" && ! -L "$QA_ARTIFACT_DIR/$artifact" ]] || return 1

  compose exec -T -u root -e "ORDENOWA_EXPECTED_PROJECT=$CI_COMPOSE_PROJECT_NAME" prestashop sh -euc '
    root=/tmp/owned/kuranea-admin-test-deps
    file="$root/private-snapshots/$1"
    test "$KURANEA_CI_PROJECT_NAME" = "$ORDENOWA_EXPECTED_PROJECT"
    test ! -L /tmp/owned && test "$(realpath /tmp/owned)" = /tmp/owned
    test ! -L "$root" && test "$(realpath "$root")" = "$root"
    test -f "$root/.ordenowa-ci-project" && test ! -L "$root/.ordenowa-ci-project"
    test "$(cat "$root/.ordenowa-ci-project")" = "$ORDENOWA_EXPECTED_PROJECT"
    test ! -L "$root/private-snapshots" && test "$(realpath "$root/private-snapshots")" = "$root/private-snapshots"
    test -f "$file" && test ! -L "$file" && test "$(realpath "$file")" = "$file"
    size=$(wc -c < "$file")
    test "$size" -ge 100 && test "$size" -le 8388608
    test "$(stat -c %a "$file")" = 600
  ' sh "$snapshot" >"$private_dir/$kind-source-check.log" 2>&1 || return 1

  compose cp "prestashop:$container_path" "$host_plain" >"$private_dir/$kind-copy.log" 2>&1 || status=$?
  if (( status == 0 )); then
    chmod 0600 -- "$host_plain" || status=$?
    if (( status == 0 )) && [[ -f $host_plain && ! -L $host_plain ]] \
        && (( $(wc -c <"$host_plain") >= 100 && $(wc -c <"$host_plain") <= 8388608 )); then
      compose exec -T -u root -e "ORDENOWA_EXPECTED_PROJECT=$CI_COMPOSE_PROJECT_NAME" prestashop sh -euc '
        root=/tmp/owned/kuranea-admin-test-deps
        file="$root/private-snapshots/$1"
        test "$KURANEA_CI_PROJECT_NAME" = "$ORDENOWA_EXPECTED_PROJECT"
        test ! -L "$root" && test "$(realpath "$root")" = "$root"
        test -f "$root/.ordenowa-ci-project" && test ! -L "$root/.ordenowa-ci-project"
        test "$(cat "$root/.ordenowa-ci-project")" = "$ORDENOWA_EXPECTED_PROJECT"
        test -f "$file" && test ! -L "$file" && test "$(realpath "$file")" = "$file"
        rm -f -- "$file"
      ' sh "$snapshot" >"$private_dir/$kind-source-remove.log" 2>&1 || status=$?
    else
      status=1
    fi
  fi

  cipher_tmp=''
  if (( status == 0 )); then
    cipher_tmp=$(mktemp "$QA_ARTIFACT_DIR/.${kind}-encrypted.XXXXXXXX") || status=$?
  fi
  if (( status == 0 )); then
    openssl cms -encrypt -aes-256-gcm -binary -outform DER -recip "$recipient" \
      -in "$host_plain" -out "$cipher_tmp" 2>"$private_dir/$kind-encrypt.stderr" || status=$?
  fi
  if (( status == 0 )) && [[ -f $cipher_tmp && ! -L $cipher_tmp ]] \
      && (( $(wc -c <"$cipher_tmp") >= 100 && $(wc -c <"$cipher_tmp") <= 8388608 )) \
      && [[ ! -e "$QA_ARTIFACT_DIR/$artifact" && ! -L "$QA_ARTIFACT_DIR/$artifact" ]]; then
    chmod 0600 -- "$cipher_tmp" || status=$?
    if (( status == 0 )); then
      if mv -- "$cipher_tmp" "$QA_ARTIFACT_DIR/$artifact"; then
        cipher_tmp=''
      else
        status=$?
      fi
    fi
  else
    status=1
  fi

  if [[ -n $cipher_tmp ]]; then rm -f -- "$cipher_tmp" || status=1; fi
  rm -f -- "$host_plain" || status=1
  if (( status == 0 )); then
    [[ -f "$QA_ARTIFACT_DIR/$artifact" && ! -L "$QA_ARTIFACT_DIR/$artifact" ]] || status=1
  fi
  return "$status"
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
      if [[ "$probe" == mbo && $helper_status -ne 0 && -f $safe && ! -L $safe ]]; then
        if python3 - "$safe" <<'PYADMINMBOAUTHCAPTURE' >/dev/null 2>&1
import json, sys
from pathlib import Path
try:
    value = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    facts = value.get('auth_landing')
    auth_landing_failure = (
        value.get('failed_stage') == 'native_login_post_redirects'
        and isinstance(facts, dict) and facts.get('post_status') == 302
        and type(facts.get('final_status')) is int and 100 <= facts['final_status'] <= 599
    )
    assertion_ids = {
        'native_kernel_browser_target_request_count_invalid',
        'native_mbo_response_status_not_503', 'native_mbo_injected_header_missing',
        'native_mbo_content_type_not_html', 'native_mbo_document_language_not_korean',
        'native_mbo_korean_message_occurrences_insufficient', 'native_mbo_english_source_message_present',
        'native_mbo_provider_invocation_count_invalid', 'native_mbo_session_csrf_probe_count_invalid',
        'native_mbo_session_csrf_not_verified',
    }
    expected_fact_keys = {
        'response_status', 'injected_header_present', 'html_content_type', 'korean_document_language',
        'korean_message_occurrences', 'english_source_present', 'provider_calls',
        'csrf_verified', 'csrf_probe_count', 'body_token_present',
    }
    response_facts = value.get('failure_facts')
    assertion_failure = (
        value.get('failed_stage') == 'assert_authenticated_korean_error'
        and value.get('failed_assertion') in assertion_ids
        and isinstance(response_facts, dict) and set(response_facts) == expected_fact_keys
        and type(response_facts.get('response_status')) is int
        and 100 <= response_facts['response_status'] <= 599
    )
    ok = value.get('passed') is False and (auth_landing_failure or assertion_failure)
except (OSError, ValueError, TypeError, AttributeError):
    ok = False
raise SystemExit(0 if ok else 1)
PYADMINMBOAUTHCAPTURE
        then
          native_admin_encrypt_private_capture mbo-auth-landing || :
        fi
      fi
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
