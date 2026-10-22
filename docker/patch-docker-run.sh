#!/bin/sh
set -eu

docker_run=${1:-/tmp/docker_run.sh}
webroot=${2:-/var/www/html}

case "$webroot" in
    /*) ;;
    *) echo "The PrestaShop webroot must be an absolute path." >&2; exit 2 ;;
esac
case "$webroot" in
    *[!A-Za-z0-9_./-]*) echo "The PrestaShop webroot contains unsupported characters." >&2; exit 2 ;;
esac
if [ ! -f "$docker_run" ] || [ ! -w "$docker_run" ]; then
    echo "The official PrestaShop start script is missing or not writable: $docker_run" >&2
    exit 2
fi

upstream_install_rm='            rm -r /var/www/html/$PS_FOLDER_INSTALL/'
upstream_lock_rm='    rm ./install.lock'
install_guard="            if [ -d \"$webroot/\$PS_FOLDER_INSTALL\" ]; then rm -r \"$webroot/\$PS_FOLDER_INSTALL/\"; fi"
lock_guard='    if [ -f ./install.lock ]; then rm ./install.lock; fi'

count_line() {
    grep -Fxc -- "$1" "$docker_run" || true
}

install_original_count=$(count_line "$upstream_install_rm")
lock_original_count=$(count_line "$upstream_lock_rm")
install_guard_count=$(count_line "$install_guard")
lock_guard_count=$(count_line "$lock_guard")

if [ "$install_original_count" -eq 1 ] && [ "$lock_original_count" -eq 1 ] \
    && [ "$install_guard_count" -eq 0 ] && [ "$lock_guard_count" -eq 0 ]; then
    :
elif [ "$install_original_count" -eq 0 ] && [ "$lock_original_count" -eq 0 ] \
    && [ "$install_guard_count" -eq 1 ] && [ "$lock_guard_count" -eq 1 ]; then
    echo "PrestaShop start script cleanup guards already applied."
    exit 0
else
    echo "Unexpected PrestaShop start script cleanup commands; refusing a partial patch." >&2
    exit 1
fi

temporary_file=$(mktemp "${docker_run}.kuranea.XXXXXX")
trap 'rm -f "$temporary_file"' EXIT HUP INT TERM
awk -v install_rm="$upstream_install_rm" \
    -v lock_rm="$upstream_lock_rm" \
    -v install_guard="$install_guard" \
    -v lock_guard="$lock_guard" '
    $0 == install_rm { print install_guard; next }
    $0 == lock_rm { print lock_guard; next }
    { print }
' "$docker_run" > "$temporary_file"
chmod --reference="$docker_run" "$temporary_file"
mv -f "$temporary_file" "$docker_run"
trap - EXIT HUP INT TERM

if [ "$(count_line "$upstream_install_rm")" -ne 0 ] \
    || [ "$(count_line "$upstream_lock_rm")" -ne 0 ] \
    || [ "$(count_line "$install_guard")" -ne 1 ] \
    || [ "$(count_line "$lock_guard")" -ne 1 ]; then
    echo "Could not verify the PrestaShop start script cleanup guards." >&2
    exit 1
fi

echo "Applied PrestaShop start script cleanup guards."
