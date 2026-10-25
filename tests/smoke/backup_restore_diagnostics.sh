#!/usr/bin/env bash

# Classify private Docker Compose output into fixed labels. Never print the
# contents: runner output can contain paths, image references, or env values.
classify_compose_create_error() {
  local output_path=$1
  [[ -r "$output_path" ]] || { printf 'diagnostic_unavailable'; return 0; }
  [[ -s "$output_path" ]] || { printf 'no_diagnostic'; return 0; }

  if grep -Eiq '(no space left on device|disk quota exceeded)' "$output_path" 2>/dev/null; then
    printf 'storage_capacity'
  elif grep -Eiq '(permission denied|cannot connect to.*docker daemon|error during connect|is the docker daemon running)' "$output_path" 2>/dev/null; then
    printf 'docker_access'
  elif grep -Eiq '(pull access denied|unauthorized|authentication required|denied: requested access|error getting credentials|too many requests|toomanyrequests)' "$output_path" 2>/dev/null; then
    printf 'image_access'
  elif grep -Eiq '(manifest unknown|no matching manifest|no such image|image[^[:cntrl:]]*not found)' "$output_path" 2>/dev/null; then
    printf 'image_unavailable'
  elif grep -Eiq '(invalid reference format|invalid tag)' "$output_path" 2>/dev/null; then
    printf 'image_reference'
  elif grep -Eiq '(failed to create network|network[^[:cntrl:]]*(already exists|not found|conflict))' "$output_path" 2>/dev/null; then
    printf 'network_setup'
  elif grep -Eiq '(failed to create volume|volume[^[:cntrl:]]*(already exists|in use|conflict))' "$output_path" 2>/dev/null; then
    printf 'volume_setup'
  elif grep -Eiq '(invalid mount config|mounts denied|error while creating mount source|failed to mount|mount[^[:cntrl:]]*(permission denied|not found))' "$output_path" 2>/dev/null; then
    printf 'mount_setup'
  elif grep -Eiq '(context deadline exceeded|request canceled|operation timed out|timeout)' "$output_path" 2>/dev/null; then
    printf 'docker_timeout'
  elif grep -Eiq '(error response from daemon|failed to create|oci runtime|failed to start shim)' "$output_path" 2>/dev/null; then
    printf 'daemon_create'
  else
    printf 'unclassified'
  fi
}

format_compose_create_failure() {
  local service=$1
  local exit_code=$2
  local stdout_path=$3
  local stderr_path=$4

  case "$service" in
    mariadb|prestashop) ;;
    *) service=unknown ;;
  esac
  [[ "$exit_code" =~ ^[0-9]{1,3}$ ]] || exit_code=unknown

  local stdout_category stderr_category
  stdout_category=$(classify_compose_create_error "$stdout_path")
  stderr_category=$(classify_compose_create_error "$stderr_path")
  printf 'service=%s; exit=%s; stdout=%s; stderr=%s' \
    "$service" "$exit_code" "$stdout_category" "$stderr_category"
}
