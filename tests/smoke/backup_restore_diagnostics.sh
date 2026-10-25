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
  local restore_project=${5:-}

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
  if [[ -n "$restore_project" ]]; then
    printf '; %s' "$(capture_restore_create_context "$restore_project")"
  fi
}

safe_version_field() {
  local value=${1:-}
  if [[ "$value" =~ ^v?[0-9]+(\.[0-9]+){1,3}([+-][A-Za-z0-9._-]+)?$ ]]; then
    printf '%s' "$value"
  else
    printf 'unavailable'
  fi
}

safe_count_from_listing() {
  local listing=${1:-}
  local line count=0
  [[ -n "$listing" ]] || { printf '0'; return 0; }
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    count=$((count + 1))
    if ((count > 9999)); then
      printf 'unavailable'
      return 0
    fi
  done <<< "$listing"
  printf '%s' "$count"
}

restore_resource_count() {
  local kind=$1
  local project=$2
  local listing
  case "$kind" in
    containers)
      if ! listing=$(docker ps -a -q --filter "label=com.docker.compose.project=$project" 2>/dev/null); then
        printf 'unavailable'
        return 0
      fi
      ;;
    volumes)
      if ! listing=$(docker volume ls -q --filter "label=com.docker.compose.project=$project" 2>/dev/null); then
        printf 'unavailable'
        return 0
      fi
      ;;
    networks)
      if ! listing=$(docker network ls -q --filter "label=com.docker.compose.project=$project" 2>/dev/null); then
        printf 'unavailable'
        return 0
      fi
      ;;
    *)
      printf 'unavailable'
      return 0
      ;;
  esac
  safe_count_from_listing "$listing"
}

restore_service_state() {
  local project=$1
  local service=$2
  local container_ids container_id state
  if ! container_ids=$(docker compose -p "$project" ps -a -q "$service" 2>/dev/null); then
    printf 'unavailable'
    return 0
  fi
  if [[ -z "$container_ids" ]]; then
    printf 'none'
    return 0
  fi
  if [[ "$container_ids" == *$'\n'* ]] || ! [[ "$container_ids" =~ ^[a-f0-9]{12,64}$ ]]; then
    printf 'ambiguous'
    return 0
  fi
  container_id=$container_ids
  if ! state=$(docker inspect -f '{{.State.Status}}' "$container_id" 2>/dev/null); then
    printf 'unavailable'
    return 0
  fi
  case "$state" in
    created|running|paused|restarting|removing|exited|dead) printf '%s' "$state" ;;
    *) printf 'unknown' ;;
  esac
}

capture_restore_create_context() {
  local project=$1
  local engine_versions='' compose_version=''
  local client_version='' client_api='' server_version='' server_api=''

  if [[ ! "$project" =~ ^kuranea-ci-[0-9]+-[0-9]+-restore$ ]]; then
    printf 'docker_client_version=unavailable; docker_client_api=unavailable; docker_server_version=unavailable; docker_server_api=unavailable; compose_version=unavailable; restore_containers=unavailable; restore_volumes=unavailable; restore_networks=unavailable; mariadb_state=unavailable; prestashop_state=unavailable'
    return 0
  fi

  if engine_versions=$(docker version --format '{{.Client.Version}}|{{.Client.APIVersion}}|{{.Server.Version}}|{{.Server.APIVersion}}' 2>/dev/null); then
    IFS='|' read -r client_version client_api server_version server_api <<< "$engine_versions"
  fi
  if ! compose_version=$(docker compose version --short 2>/dev/null); then
    compose_version=''
  fi

  printf 'docker_client_version=%s; docker_client_api=%s; docker_server_version=%s; docker_server_api=%s; compose_version=%s; restore_containers=%s; restore_volumes=%s; restore_networks=%s; mariadb_state=%s; prestashop_state=%s' \
    "$(safe_version_field "$client_version")" \
    "$(safe_version_field "$client_api")" \
    "$(safe_version_field "$server_version")" \
    "$(safe_version_field "$server_api")" \
    "$(safe_version_field "$compose_version")" \
    "$(restore_resource_count containers "$project")" \
    "$(restore_resource_count volumes "$project")" \
    "$(restore_resource_count networks "$project")" \
    "$(restore_service_state "$project" mariadb)" \
    "$(restore_service_state "$project" prestashop)"
}
