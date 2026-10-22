#!/bin/sh
set -eu

# docker_run.sh copies the official source tree into the persistent webroot
# before running pre-install hooks. Repair only the generated production cache
# tree so the installer, which runs as www-data, can replace class_index.php.
cache_dir=/var/www/html/var/cache/prod
mkdir -p "$cache_dir"
chown -R www-data:www-data "$cache_dir"
