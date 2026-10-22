#!/bin/sh
set -eu

/usr/local/bin/kuranea-patch-docker-run /tmp/docker_run.sh
/tmp/pre-install-scripts/10-kuranea-cache-ownership.sh

sync_theme() {
    theme_name="$1"
    source_dir="/opt/kuranea/themes/${theme_name}"
    target_dir="/var/www/html/themes/${theme_name}"

    if [ ! -d "$source_dir" ]; then
        echo "Missing bundled theme source: $source_dir" >&2
        exit 1
    fi

    mkdir -p "$target_dir"
    cp -R "$source_dir"/. "$target_dir"/
    chown -R www-data:www-data "$target_dir"
    find "$target_dir" -type d -exec chmod 0755 {} +
    find "$target_dir" -type f -exec chmod 0644 {} +
}

sync_theme hummingbird
sync_theme kuranea

sync_module() {
    module_name="$1"
    source_dir="/opt/kuranea/modules/${module_name}"
    target_dir="/var/www/html/modules/${module_name}"

    if [ ! -d "$source_dir" ]; then
        echo "Missing bundled module source: $source_dir" >&2
        exit 1
    fi

    mkdir -p "$target_dir"
    cp -R "$source_dir"/. "$target_dir"/
    chown -R www-data:www-data "$target_dir"
}

sync_module kuraneapostcode
sync_module kuraneabackoffice
sync_module kuraneabusinessprofile
sync_module kuraneacatalog

php /usr/local/bin/sync-ordenowa-brand-assets.php

catalog_queue_dir="${KURANEA_CATALOG_QUEUE_DIR:-/var/lib/kuranea/catalog-review}"
case "$catalog_queue_dir" in
    /var/www/html|/var/www/html/*)
        echo "Catalog review storage must stay outside the public PrestaShop webroot." >&2
        exit 1
        ;;
esac
if [ -L "$catalog_queue_dir" ]; then
    echo "Catalog review storage directory cannot be a symbolic link." >&2
    exit 1
fi
mkdir -p "$catalog_queue_dir"
if [ -L "$catalog_queue_dir" ]; then
    echo "Catalog review storage directory cannot be a symbolic link." >&2
    exit 1
fi
chown www-data:www-data "$catalog_queue_dir"
chmod 0750 "$catalog_queue_dir"

cp /var/www/html/themes/kuranea/assets/sw.js /var/www/html/sw.js
cp /var/www/html/themes/kuranea/assets/manifest.webmanifest /var/www/html/manifest.webmanifest
chown www-data:www-data /var/www/html/sw.js /var/www/html/manifest.webmanifest

# A child theme's theme.css replaces the parent's main stylesheet in
# PrestaShop's asset resolver. Keep the parent stylesheet active and load
# KURANEA's overrides from custom.css instead.
rm -f /var/www/html/themes/kuranea/assets/css/theme.css

# PrestaShop's language downloader uses its own cached CA file instead of the
# operating system bundle. Seed that file from the verified host trust store so
# HTTPS remains verified through the managed development proxy.
ca_bundle="/etc/ssl/certs/ca-certificates.crt"
ca_cache="/var/www/html/var/cache/prod/cacert.pem"
if [ ! -r "$ca_bundle" ]; then
    echo "Missing readable CA bundle: $ca_bundle" >&2
    exit 1
fi
mkdir -p "$(dirname "$ca_cache")"
cp "$ca_bundle" "$ca_cache"
chown www-data:www-data "$ca_cache"

exec docker-php-entrypoint "$@"
