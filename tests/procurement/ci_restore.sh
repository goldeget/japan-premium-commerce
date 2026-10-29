#!/usr/bin/env bash
# Restore the CI snapshot only after an age-authenticated byte-for-byte round trip.
set -euo pipefail
umask 077
[[ ${CI:-} == true && ${KURANEA_ISOLATED_CI:-} == 1 ]]
[[ ${CI_COMPOSE_PROJECT_NAME:-} == "ordenowa-procurement-ci-${GITHUB_RUN_ID:-}-${GITHUB_RUN_ATTEMPT:-}" ]]
[[ ${GITHUB_RUN_ID:-} =~ ^[0-9]+$ && ${GITHUB_RUN_ATTEMPT:-} =~ ^[0-9]+$ ]]
[[ ${RUNNER_TEMP:-} == /* && -d $RUNNER_TEMP ]]
[[ ${QA_ARTIFACT_DIR:-} == "$RUNNER_TEMP/procurement-safe-artifacts" ]]
[[ ! -L $QA_ARTIFACT_DIR ]]
mkdir -p -- "$QA_ARTIFACT_DIR"
[[ ! -L $QA_ARTIFACT_DIR ]]

source_project=$CI_COMPOSE_PROJECT_NAME
restore_project="${source_project}-restore"
private_dir=$(mktemp -d "$RUNNER_TEMP/procurement-restore.XXXXXXXX")
chmod 700 "$private_dir"
age_version=unknown
roundtrip_verified=false
tampered_ciphertext_rejected=false
wrong_identity_rejected=false
database_restore_verified=false
compose() {
  local -a files=(-f compose.yaml -f tests/procurement/ci.compose.yaml)
  if [[ -n ${ORDENOWA_CI_IMAGE_REF:-} ]]; then
    files+=(-f tests/procurement/ci.package.compose.yaml)
  fi
  docker compose "${files[@]}" -p "$source_project" "$@"
}

write_outcome() {
  local exit_code=$1
  python3 - "$QA_ARTIFACT_DIR/encrypted-restore-outcome.json" "$age_version" \
    "$roundtrip_verified" "$tampered_ciphertext_rejected" "$wrong_identity_rejected" \
    "$database_restore_verified" "$exit_code" <<'PY'
import json
import os
import sys
import tempfile
from pathlib import Path

destination = Path(sys.argv[1])
if destination.is_symlink():
    raise SystemExit(1)
age_version, roundtrip, tampered, wrong_identity, restored, exit_code = sys.argv[2:]
boolean = {"true": True, "false": False}
if any(value not in boolean for value in (roundtrip, tampered, wrong_identity, restored)):
    raise SystemExit(1)
result = {
    "age_version": age_version,
    "ciphertext_tamper_rejected": boolean[tampered],
    "database_restore_verified": boolean[restored],
    "decrypt_roundtrip_verified": boolean[roundtrip],
    "passed": exit_code == "0" and all(boolean[value] for value in (roundtrip, tampered, wrong_identity, restored)),
    "wrong_identity_rejected": boolean[wrong_identity],
}
descriptor, temporary_name = tempfile.mkstemp(prefix=".restore-outcome-", suffix=".tmp", dir=destination.parent)
try:
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary_name, destination)
finally:
    try:
        os.unlink(temporary_name)
    except FileNotFoundError:
        pass
PY
}

cleanup() {
  result=$?
  trap - EXIT
  python3 tests/procurement/ci_owned_resources_cleanup.py container \
    --container-name "$restore_project" >"$private_dir/restore-container-cleanup.log" 2>&1 || result=1
  rm -rf -- "$private_dir" || result=1
  write_outcome "$result" || result=1
  exit "$result"
}
trap cleanup EXIT

age_version=$(age --version 2>/dev/null)
[[ $age_version =~ ^v?[0-9]+\.[0-9]+\.[0-9]+$ ]]
age-keygen -o "$private_dir/restore.agekey" >/dev/null 2>&1
chmod 600 "$private_dir/restore.agekey"
restore_recipient=$(age-keygen -y "$private_dir/restore.agekey" 2>/dev/null)
[[ $restore_recipient =~ ^age1[0-9a-z]+$ ]]

compose exec -T -u www-data prestashop php /tmp/ordenowa-procurement-ci/ci_readback.php manifest
# The SQL snapshot, ephemeral identity, ciphertext, and plaintext round-trip
# stay together in a mode-0700 run-private directory and are never uploaded.
compose exec -T mariadb sh -ec 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb-dump -uroot --single-transaction --skip-comments "$MARIADB_DATABASE"' > "$private_dir/backup.sql"
[[ -s $private_dir/backup.sql ]]
age --encrypt --recipient "$restore_recipient" --output "$private_dir/backup.sql.age" "$private_dir/backup.sql" >/dev/null 2>&1
age --decrypt --identity "$private_dir/restore.agekey" --output "$private_dir/decrypted.sql" "$private_dir/backup.sql.age" >/dev/null 2>&1
[[ -s $private_dir/decrypted.sql ]]
cmp -s -- "$private_dir/backup.sql" "$private_dir/decrypted.sql"
roundtrip_verified=true

# Prove authentication failures are rejected before any database import.
python3 - "$private_dir/backup.sql.age" "$private_dir/tampered.sql.age" <<'PY'
import sys
from pathlib import Path

source, target = map(Path, sys.argv[1:])
data = bytearray(source.read_bytes())
if len(data) < 32:
    raise SystemExit(1)
data[len(data) // 2] ^= 1
target.write_bytes(data)
PY
if age --decrypt --identity "$private_dir/restore.agekey" --output "$private_dir/tampered.sql" "$private_dir/tampered.sql.age" >/dev/null 2>&1; then
  rm -f -- "$private_dir/tampered.sql"
  printf 'FAIL encrypted restore accepted tampered ciphertext\n' >&2
  exit 1
fi
rm -f -- "$private_dir/tampered.sql"
tampered_ciphertext_rejected=true

age-keygen -o "$private_dir/wrong.agekey" >/dev/null 2>&1
chmod 600 "$private_dir/wrong.agekey"
if age --decrypt --identity "$private_dir/wrong.agekey" --output "$private_dir/wrong-key.sql" "$private_dir/backup.sql.age" >/dev/null 2>&1; then
  rm -f -- "$private_dir/wrong-key.sql"
  printf 'FAIL encrypted restore accepted the wrong identity\n' >&2
  exit 1
fi
rm -f -- "$private_dir/wrong-key.sql"
wrong_identity_rejected=true

source_image=$(docker inspect --format '{{.Config.Image}}' "$(compose ps -q mariadb)")
docker run --detach --name "$restore_project" --network "${source_project}_default" --network-alias procurement-restore \
  --env MARIADB_ROOT_PASSWORD --env MARIADB_DATABASE=prestashop \
  --tmpfs /var/lib/mysql "$source_image" >/dev/null
for ((attempt=0; attempt<60; attempt++)); do
  if docker exec "$restore_project" sh -ec 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb -uroot -N -e "SELECT 1"' >/dev/null 2>&1; then break; fi
  sleep 2
done
# Import only the plaintext whose authenticated round-trip matched byte-for-byte.
docker exec -i "$restore_project" sh -ec 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb -uroot prestashop' < "$private_dir/decrypted.sql"
# Point a one-off PHP process at the independent restored connection without
# modifying the installed shop's parameters or the original database.
compose exec -T -u www-data -e PROCUREMENT_RESTORE_HOST=procurement-restore -e "MARIADB_ROOT_PASSWORD=$MARIADB_ROOT_PASSWORD" prestashop php /tmp/ordenowa-procurement-ci/ci_restore_readback.php
database_restore_verified=true
printf 'PASS encrypted round-trip, tamper rejection, wrong-identity rejection, and independent database restore\n'
