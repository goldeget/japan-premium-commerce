# Source from the guarded disposable procurement acceptance process only.
# Each `compose exec ... php` is synchronous so the five PHP processes never
# share KernelBrowser, request-stack, or PHP employee/session state.
native_facebook_fresh_case_acceptance() {
  local case_name status result=0 private_cases safe_output
  local -a case_names=(unauthenticated other_route generic_facebook access_denied curl_transport)
  local -a auth_env=()
  local -a collector_args=()

  if [[ -z "${private_dir:-}" || -z "${QA_ARTIFACT_DIR:-}" || -z "${CI_COMPOSE_PROJECT_NAME:-}" \
      || "$CI_COMPOSE_PROJECT_NAME" != "ordenowa-procurement-ci-${GITHUB_RUN_ID:-}-${GITHUB_RUN_ATTEMPT:-}" ]] \
      || [[ ! -d "$private_dir" || -L "$private_dir" || ! -d "$QA_ARTIFACT_DIR" || -L "$QA_ARTIFACT_DIR" ]]; then
    return 64
  fi
  private_cases="$private_dir/native-facebook-cases"
  safe_output="$QA_ARTIFACT_DIR/native-facebook-transport-outcome.json"
  if [[ -e "$private_cases" || -L "$private_cases" || -e "$safe_output" || -L "$safe_output" ]]; then
    return 65
  fi
  mkdir -m 0700 -- "$private_cases" || return 66

  for case_name in "${case_names[@]}"; do
    local raw="$private_cases/$case_name.private.json"
    local stderr="$private_cases/$case_name.private.stderr"
    # Compose exec inherits container environment even without -e. Explicitly
    # clear the install credentials for the genuinely anonymous child.
    auth_env=(-e ADMIN_MAIL= -e ADMIN_PASSWD=)
    if [[ "$case_name" != unauthenticated ]]; then
      auth_env=(-e ADMIN_MAIL -e ADMIN_PASSWD)
    fi
    status=0
    compose exec -T -u www-data \
      "${auth_env[@]}" -e "ORDENOWA_FACEBOOK_CASE=$case_name" \
      prestashop php /var/www/html/tests/admin_locale/native_facebook_transport_fallback.php \
      >"$raw" 2>"$stderr" || status=$?
    chmod 0600 -- "$raw" "$stderr" || result=1
    collector_args+=(--case-input "$case_name=$raw" --case-status "$case_name=$status")
    if (( status != 0 )); then result=1; fi
  done

  python3 tests/admin_locale/safe_native_facebook_cases.py \
    "${collector_args[@]}" --safe-output "$safe_output" || result=1
  return "$result"
}
