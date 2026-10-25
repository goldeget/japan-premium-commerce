#!/usr/bin/env bash
set -euo pipefail
umask 077
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$script_dir/backup_restore_diagnostics.sh"

fail() {
  printf 'FAIL: isolated backup/restore drill: %s\n' "$1" >&2
  exit 1
}

compare_file_tree_archives() {
  python3 - "$1" "$2" <<'FILE_TREE_COMPARATOR_PY'
import hashlib
import sys
import tarfile
from decimal import Decimal

DIAGNOSTIC_CATEGORIES = (
    "missing",
    "extra",
    "type",
    "mode",
    "uid_gid",
    "mtime",
    "size_content",
    "link",
    "xattr_acl",
    "device",
    "root_entry",
)
MAX_DIAGNOSTIC_COUNT = 999999


def canonical_name(name):
    if name.startswith("/") or "\0" in name:
        raise ValueError
    parts = []
    for part in name.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError
        parts.append(part)
    return "/".join(parts)


def canonical_mtime(member):
    raw = member.pax_headers.get("mtime")
    if raw is None:
        raw = str(member.mtime)
    return Decimal(raw)


def file_digest(archive, member):
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError
    digest = hashlib.sha256()
    with stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.digest()


def semantic_pax_metadata(member):
    prefixes = ("SCHILY.xattr.", "LIBARCHIVE.xattr.", "SCHILY.acl.", "LIBARCHIVE.acl.")
    return tuple(sorted((key, value) for key, value in member.pax_headers.items() if key.startswith(prefixes)))


def manifest(path):
    tree = {}
    with tarfile.open(path, "r:*") as archive:
        for member in archive:
            name = canonical_name(member.name)
            if not name and not member.isdir():
                raise ValueError
            if name in tree:
                raise ValueError

            metadata = (member.mode & 0o7777, member.uid, member.gid, semantic_pax_metadata(member))
            if member.isdir():
                # Restoring children can change directory timestamps; stable metadata still matters.
                value = ("directory",) + metadata
            elif member.isfile():
                value = ("file",) + metadata + (member.size, canonical_mtime(member), file_digest(archive, member))
            elif member.issym():
                value = ("symlink",) + metadata + (canonical_mtime(member), member.linkname)
            elif member.islnk():
                value = ("hardlink",) + metadata + (canonical_mtime(member), canonical_name(member.linkname))
            elif member.isfifo():
                value = ("fifo",) + metadata + (canonical_mtime(member),)
            elif member.ischr():
                value = ("character-device",) + metadata + (canonical_mtime(member), member.devmajor, member.devminor)
            elif member.isblk():
                value = ("block-device",) + metadata + (canonical_mtime(member), member.devmajor, member.devminor)
            else:
                raise ValueError
            tree[name] = value
    return tree


def increment(counts, category):
    counts[category] = min(counts[category] + 1, MAX_DIAGNOSTIC_COUNT)


def mismatch_counts(original, restored):
    counts = {category: 0 for category in DIAGNOSTIC_CATEGORIES}
    for name in original.keys() | restored.keys():
        original_entry = original.get(name)
        restored_entry = restored.get(name)
        is_root = name == ""

        if original_entry is None or restored_entry is None:
            if is_root:
                increment(counts, "root_entry")
            else:
                increment(counts, "extra" if original_entry is None else "missing")
            continue

        changed = False
        if original_entry[0] != restored_entry[0]:
            increment(counts, "type")
            changed = True
        else:
            if original_entry[1] != restored_entry[1]:
                increment(counts, "mode")
                changed = True
            if original_entry[2:4] != restored_entry[2:4]:
                increment(counts, "uid_gid")
                changed = True
            if original_entry[4] != restored_entry[4]:
                increment(counts, "xattr_acl")
                changed = True

            kind = original_entry[0]
            if kind == "file":
                if original_entry[6] != restored_entry[6]:
                    increment(counts, "mtime")
                    changed = True
                if original_entry[5] != restored_entry[5] or original_entry[7] != restored_entry[7]:
                    increment(counts, "size_content")
                    changed = True
            elif kind in ("symlink", "hardlink"):
                if original_entry[5] != restored_entry[5]:
                    increment(counts, "mtime")
                    changed = True
                if original_entry[6] != restored_entry[6]:
                    increment(counts, "link")
                    changed = True
            elif kind in ("fifo", "character-device", "block-device"):
                if original_entry[5] != restored_entry[5]:
                    increment(counts, "mtime")
                    changed = True
                if kind in ("character-device", "block-device") and original_entry[6:8] != restored_entry[6:8]:
                    increment(counts, "device")
                    changed = True

        if is_root and changed:
            increment(counts, "root_entry")
    return counts


def print_mismatch_counts(counts):
    summary = " ".join(f"{category}={counts[category]}" for category in DIAGNOSTIC_CATEGORIES)
    sys.stdout.write("FILE_TREE_MISMATCH " + summary + "\n")


try:
    original = manifest(sys.argv[1])
    restored = manifest(sys.argv[2])
    if original == restored:
        sys.exit(0)
    counts = mismatch_counts(original, restored)
except Exception:
    sys.exit(1)
print_mismatch_counts(counts)
sys.exit(1)
FILE_TREE_COMPARATOR_PY
}

[[ "${GITHUB_ACTIONS:-}" == true ]] || fail 'GitHub Actions guard did not match.'
[[ "${KURANEA_ISOLATED_CI:-}" == 1 ]] || fail 'isolated CI guard did not match.'
[[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]+$ ]] || fail 'run ID is not numeric.'
[[ "${GITHUB_RUN_ATTEMPT:-}" =~ ^[0-9]+$ ]] || fail 'run attempt is not numeric.'

expected_source="kuranea-ci-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
[[ "${CI_COMPOSE_PROJECT_NAME:-}" == "$expected_source" ]] || fail 'source Compose project did not match this run.'
source_project=$expected_source
restore_project="${source_project}-restore"

[[ "${RUNNER_TEMP:-}" == /* && -d "$RUNNER_TEMP" && -w "$RUNNER_TEMP" ]] || fail 'private runner temp storage is unavailable.'
[[ "${SHOP_PORT:-}" =~ ^[0-9]{2,5}$ ]] || fail 'shop port is not a valid local test port.'
[[ "${GITHUB_OUTPUT:-}" == "$RUNNER_TEMP"/* ]] || fail 'run-scoped cleanup output is not inside runner temp storage.'

restore_volumes=(
  "${restore_project}_mariadb_data"
  "${restore_project}_prestashop_html"
  "${restore_project}_catalog_review_data"
)

# Refuse any pre-existing target resource. Cleanup is enabled only after these
# checks pass, so a collision can never cause this script to remove old data.
docker_resource_exists() {
  local resource_type=$1
  local resource_name=$2
  local candidate
  local matches
  matches=$(docker "$resource_type" ls --format '{{.Name}}' --filter "name=$resource_name" 2>/dev/null) \
    || fail 'restore project resources could not be inspected.'
  while IFS= read -r candidate; do
    [[ "$candidate" == "$resource_name" ]] && return 0
  done <<< "$matches"
  return 1
}

for volume in "${restore_volumes[@]}"; do
  if docker_resource_exists volume "$volume"; then
    fail 'restore project already has a named volume.'
  fi
done
existing_containers=$(docker ps -a -q --filter "label=com.docker.compose.project=$restore_project" 2>/dev/null) \
  || fail 'restore project containers could not be inspected.'
if [[ -n "$existing_containers" ]]; then
  fail 'restore project already has containers.'
fi
existing_volumes=$(docker volume ls -q --filter "label=com.docker.compose.project=$restore_project" 2>/dev/null) \
  || fail 'restore project volumes could not be inspected.'
if [[ -n "$existing_volumes" ]]; then
  fail 'restore project already has volumes.'
fi
existing_networks=$(docker network ls -q --filter "label=com.docker.compose.project=$restore_project" 2>/dev/null) \
  || fail 'restore project networks could not be inspected.'
if [[ -n "$existing_networks" ]]; then
  fail 'restore project already has networks.'
fi
if docker_resource_exists network "${restore_project}_default"; then
  fail 'restore project default network already exists.'
fi

single_container_id() {
  local container_id=$1
  [[ -n "$container_id" && "$container_id" != *$'\n'* ]]
}

source_db_container=$(docker compose -p "$source_project" ps -q mariadb 2>/dev/null) \
  || fail 'source database container is unavailable.'
source_app_container=$(docker compose -p "$source_project" ps -q prestashop 2>/dev/null) \
  || fail 'source application container is unavailable.'
single_container_id "$source_db_container" || fail 'source database container is ambiguous.'
single_container_id "$source_app_container" || fail 'source application container is ambiguous.'

source_db_labels=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{.State.Running}}' "$source_db_container" 2>/dev/null) \
  || fail 'source database container labels are unavailable.'
source_app_labels=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{.State.Running}}' "$source_app_container" 2>/dev/null) \
  || fail 'source application container labels are unavailable.'
[[ "$source_db_labels" == "${source_project}|mariadb|true" ]] || fail 'source database container identity is unsafe.'
[[ "$source_app_labels" == "${source_project}|prestashop|true" ]] || fail 'source application container identity is unsafe.'

source_db_volume=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Name}}{{end}}{{end}}' "$source_db_container" 2>/dev/null) \
  || fail 'source database volume could not be identified.'
source_app_volume=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/www/html"}}{{.Name}}{{end}}{{end}}' "$source_app_container" 2>/dev/null) \
  || fail 'source application volume could not be identified.'
source_queue_volume=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/kuranea/catalog-review"}}{{.Name}}{{end}}{{end}}' "$source_app_container" 2>/dev/null) \
  || fail 'source catalog queue volume could not be identified.'

assert_compose_volume() {
  local actual_name=$1
  local logical_name=$2
  local project_name=$3
  local expected_name="${project_name}_${logical_name}"
  local labels
  [[ "$actual_name" == "$expected_name" ]] || return 1
  labels=$(docker volume inspect -f '{{index .Labels "com.docker.compose.project"}}|{{index .Labels "com.docker.compose.volume"}}' "$actual_name" 2>/dev/null) || return 1
  [[ "$labels" == "${project_name}|${logical_name}" ]]
}

assert_compose_volume "$source_db_volume" mariadb_data "$source_project" || fail 'source database volume identity is unsafe.'
assert_compose_volume "$source_app_volume" prestashop_html "$source_project" || fail 'source application volume identity is unsafe.'
assert_compose_volume "$source_queue_volume" catalog_review_data "$source_project" || fail 'source catalog queue volume identity is unsafe.'

snapshot_dir=$(mktemp -d "$RUNNER_TEMP/ordenowa-restore-drill-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}.XXXXXX") \
  || fail 'private snapshot directory could not be created.'
chmod 0700 "$snapshot_dir" || fail 'private snapshot directory could not be protected.'

restore_project_owned=0
source_application_stopped=0
cleanup() {
  local result=$?
  local cleanup_failed=0
  trap - EXIT

  if [[ "$restore_project_owned" == 1 ]]; then
    if ! docker compose -p "$restore_project" down -v --remove-orphans >/dev/null 2>&1; then
      cleanup_failed=1
    fi
  fi

  if [[ "$source_application_stopped" == 1 ]]; then
    if ! docker compose -p "$source_project" start prestashop >/dev/null 2>&1; then
      cleanup_failed=1
    fi
  fi

  case "${snapshot_dir:-}" in
    "$RUNNER_TEMP"/ordenowa-restore-drill-"${GITHUB_RUN_ID}"-"${GITHUB_RUN_ATTEMPT}".*)
      rm -rf -- "$snapshot_dir" || cleanup_failed=1
      ;;
    '')
      ;;
    *)
      cleanup_failed=1
      ;;
  esac

  if [[ "$cleanup_failed" == 1 ]]; then
    printf 'FAIL: isolated backup/restore drill: scoped cleanup failed.\n' >&2
    result=1
  fi
  if [[ "$result" == 0 ]]; then
    printf 'PASS: isolated database, PrestaShop files, and catalog queue restored and restarted.\n'
  fi
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

stderr_file="$snapshot_dir/command.stderr"
database_dump="$snapshot_dir/database.sql"
app_archive="$snapshot_dir/prestashop-files.tar"
queue_archive="$snapshot_dir/catalog-queue.tar"
restored_database_dump="$snapshot_dir/restored-database.sql"
restored_app_archive="$snapshot_dir/restored-prestashop-files.tar"
restored_queue_archive="$snapshot_dir/restored-catalog-queue.tar"

create_restore_service() {
  local service=$1
  local stdout_path="$snapshot_dir/compose-create-${service}.stdout"
  local stderr_path="$snapshot_dir/compose-create-${service}.stderr"
  local create_status

  if docker compose -p "$restore_project" create "$service" >"$stdout_path" 2>"$stderr_path"; then
    return 0
  else
    create_status=$?
  fi

  fail "run-scoped restore container creation failed ($(format_compose_create_failure "$service" "$create_status" "$stdout_path" "$stderr_path" "$restore_project"))."
}

# Validate the effective Compose volume mapping without printing the config,
# which contains the run-scoped database and Back Office credentials.
if ! docker compose -p "$restore_project" config --format json 2>"$stderr_file" \
  | python3 -c '
import json
import sys

try:
    config = json.load(sys.stdin)
    project = sys.argv[1]
    expected = {
        "mariadb_data": f"{project}_mariadb_data",
        "prestashop_html": f"{project}_prestashop_html",
        "catalog_review_data": f"{project}_catalog_review_data",
    }
    for logical_name, volume_name in expected.items():
        volume = config.get("volumes", {}).get(logical_name, {})
        if volume.get("name") != volume_name or volume.get("external", False):
            raise ValueError
    mounts = {
        "mariadb": {mount.get("target"): mount.get("source") for mount in config["services"]["mariadb"]["volumes"]},
        "prestashop": {mount.get("target"): mount.get("source") for mount in config["services"]["prestashop"]["volumes"] if mount.get("type") == "volume"},
    }
    if mounts["mariadb"].get("/var/lib/mysql") != "mariadb_data":
        raise ValueError
    if mounts["prestashop"].get("/var/www/html") != "prestashop_html":
        raise ValueError
    if mounts["prestashop"].get("/var/lib/kuranea/catalog-review") != "catalog_review_data":
        raise ValueError
except Exception:
    sys.exit("Run-scoped Compose volumes do not match the expected isolated names.")
' "$restore_project" >/dev/null 2>"$stderr_file"; then
  fail 'restore Compose volume mapping did not resolve to run-scoped names.'
fi

# Stop only the run-scoped app. Its database remains available for a logical
# dump; named file volumes are read with docker cp and are never mounted writable.
source_application_stopped=1
if ! docker compose -p "$source_project" stop prestashop >/dev/null 2>"$stderr_file"; then
  fail 'source application could not be quiesced.'
fi

if ! docker compose -p "$source_project" exec -T mariadb sh -ec '
  MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb-dump \
    --protocol=tcp -h127.0.0.1 -uroot \
    --single-transaction --routines --triggers --events --hex-blob \
    --skip-dump-date --order-by-primary --default-character-set=utf8mb4 \
    "$MARIADB_DATABASE"
' >"$database_dump" 2>"$stderr_file"; then
  fail 'logical database backup failed.'
fi
[[ -s "$database_dump" ]] || fail 'logical database backup is empty.'

# docker cp streams tar archives without listing member names or contents.
if ! docker cp -a "$source_app_container:/var/www/html/." - >"$app_archive" 2>"$stderr_file"; then
  fail 'PrestaShop file backup failed.'
fi
if ! docker cp -a "$source_app_container:/var/lib/kuranea/catalog-review/." - >"$queue_archive" 2>"$stderr_file"; then
  fail 'catalog queue backup failed.'
fi
[[ -s "$app_archive" && -s "$queue_archive" ]] || fail 'a file backup is empty.'

# The target was proven absent and its effective Compose mapping was verified.
# From here the trap may remove only this exact run-scoped restore project.
restore_project_owned=1
printf 'restore_project_owned=true\n' >> "$GITHUB_OUTPUT"
create_restore_service mariadb
create_restore_service prestashop

restore_db_container=$(docker compose -p "$restore_project" ps -a -q mariadb 2>/dev/null) \
  || fail 'restore database container is unavailable.'
single_container_id "$restore_db_container" || fail 'restore database container is ambiguous.'
restore_db_labels=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{.State.Running}}' "$restore_db_container" 2>/dev/null) \
  || fail 'restore database container labels are unavailable.'
[[ "$restore_db_labels" == "${restore_project}|mariadb|false" ]] || fail 'restore database container identity is unsafe.'
restore_db_volume=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Name}}{{end}}{{end}}' "$restore_db_container" 2>/dev/null) \
  || fail 'restore database volume could not be identified.'
assert_compose_volume "$restore_db_volume" mariadb_data "$restore_project" || fail 'restore database volume identity is unsafe.'

restore_app_container=$(docker compose -p "$restore_project" ps -a -q prestashop 2>/dev/null) \
  || fail 'restore application container is unavailable.'
single_container_id "$restore_app_container" || fail 'restore application container is ambiguous.'
restore_app_labels=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{.State.Running}}' "$restore_app_container" 2>/dev/null) \
  || fail 'restore application container labels are unavailable.'
[[ "$restore_app_labels" == "${restore_project}|prestashop|false" ]] || fail 'restore application container identity is unsafe.'
restore_app_volume=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/www/html"}}{{.Name}}{{end}}{{end}}' "$restore_app_container" 2>/dev/null) \
  || fail 'restore application volume could not be identified.'
restore_queue_volume=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/kuranea/catalog-review"}}{{.Name}}{{end}}{{end}}' "$restore_app_container" 2>/dev/null) \
  || fail 'restore catalog queue volume could not be identified.'
assert_compose_volume "$restore_app_volume" prestashop_html "$restore_project" || fail 'restore application volume identity is unsafe.'
assert_compose_volume "$restore_queue_volume" catalog_review_data "$restore_project" || fail 'restore catalog queue volume identity is unsafe.'

if ! docker compose -p "$restore_project" up -d --wait --wait-timeout 300 mariadb >/dev/null 2>"$stderr_file"; then
  fail 'restore database did not start.'
fi

# Clear Docker's image copy-up content only after actual target mount names and
# Compose labels have matched this run's new project.
if ! docker compose -p "$restore_project" run --rm --no-deps -T --user 0:0 \
  --entrypoint /bin/sh prestashop -ec '
    find /var/www/html -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
    mkdir -p /var/lib/kuranea/catalog-review
    find /var/lib/kuranea/catalog-review -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  ' >/dev/null 2>"$stderr_file"; then
  fail 'restore file volumes could not be prepared.'
fi

if ! docker cp -a - "$restore_app_container:/var/www/html" <"$app_archive" >/dev/null 2>"$stderr_file"; then
  fail 'PrestaShop files could not be restored.'
fi
if ! docker cp -a - "$restore_app_container:/var/lib/kuranea/catalog-review" <"$queue_archive" >/dev/null 2>"$stderr_file"; then
  fail 'catalog queue could not be restored.'
fi
if ! docker cp -a "$restore_app_container:/var/www/html/." - >"$restored_app_archive" 2>"$stderr_file"; then
  fail 'restored PrestaShop files could not be read back.'
fi
if ! compare_file_tree_archives "$app_archive" "$restored_app_archive"; then
  fail 'restored PrestaShop file tree did not match the private CI snapshot.'
fi
if ! docker cp -a "$restore_app_container:/var/lib/kuranea/catalog-review/." - >"$restored_queue_archive" 2>"$stderr_file"; then
  fail 'restored catalog queue files could not be read back.'
fi
if ! compare_file_tree_archives "$queue_archive" "$restored_queue_archive"; then
  fail 'restored catalog queue file tree did not match the private CI snapshot.'
fi

if ! docker compose -p "$restore_project" exec -T mariadb sh -ec '
  MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb \
    --protocol=tcp -h127.0.0.1 -uroot "$MARIADB_DATABASE"
' <"$database_dump" >/dev/null 2>"$stderr_file"; then
  fail 'logical database restore failed.'
fi

# Compare deterministic logical dumps before application startup can mutate
# cache/config state. cmp emits no values, filenames, or hashes.
if ! docker compose -p "$restore_project" exec -T mariadb sh -ec '
  MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb-dump \
    --protocol=tcp -h127.0.0.1 -uroot \
    --single-transaction --routines --triggers --events --hex-blob \
    --skip-dump-date --order-by-primary --default-character-set=utf8mb4 \
    "$MARIADB_DATABASE"
' >"$restored_database_dump" 2>"$stderr_file"; then
  fail 'restored database could not be read back.'
fi
if ! cmp -s "$database_dump" "$restored_database_dump"; then
  fail 'restored database contents did not match the CI snapshot.'
fi

shop_base_url="http://127.0.0.1:${SHOP_PORT}"
check_queue_read_only() {
  local project=$1
  if ! docker compose -p "$project" exec -T prestashop php -r '
    $path = "/var/lib/kuranea/catalog-review/review-queue.json";
    $contents = @file_get_contents($path);
    $document = $contents === false ? null : json_decode($contents, true);
    $key = "amazon_jp:B0KURANEA1";
    if (!is_array($document)
        || ($document["schemaVersion"] ?? null) !== 1
        || !is_array($document["entries"] ?? null)
        || !isset($document["entries"][$key])
        || !is_array($document["entries"][$key])) {
        exit(1);
    }
  ' >/dev/null 2>"$stderr_file"; then
    return 1
  fi
  return 0
}

check_restored_shop() {
  local project=$1
  local db_probe
  if ! curl --fail --location --max-redirs 5 --silent --output /dev/null "$shop_base_url/" 2>"$stderr_file"; then
    return 1
  fi
  if ! curl --fail --location --max-redirs 5 --silent --output /dev/null "$shop_base_url/admin-kuranea/login" 2>"$stderr_file"; then
    return 1
  fi
  db_probe=$(docker compose -p "$project" exec -T mariadb sh -ec '
    MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb --protocol=tcp -h127.0.0.1 -uroot -N "$MARIADB_DATABASE" \
      -e "SELECT COUNT(*) FROM ps_shop WHERE id_shop=1 AND name=\"ORDENOWA\""
  ' 2>"$stderr_file") || return 1
  [[ "$db_probe" == 1 ]] || return 1
  check_queue_read_only "$project" || return 1
  return 0
}

if ! docker compose -p "$restore_project" up -d --wait --wait-timeout 900 prestashop >/dev/null 2>"$stderr_file"; then
  fail 'restored application did not become ready.'
fi
check_restored_shop "$restore_project" || fail 'restored application, database, or queue did not pass readiness checks.'

if ! docker compose -p "$restore_project" restart mariadb prestashop >/dev/null 2>"$stderr_file"; then
  fail 'restored services could not be restarted.'
fi
if ! docker compose -p "$restore_project" up -d --wait --wait-timeout 300 mariadb prestashop >/dev/null 2>"$stderr_file"; then
  fail 'restored services did not recover after restart.'
fi
check_restored_shop "$restore_project" || fail 'restored data or read-only queue check failed after restart.'
