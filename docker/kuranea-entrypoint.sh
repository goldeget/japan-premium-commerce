#!/bin/sh
set -eu

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
}

sync_theme hummingbird
sync_theme kuranea

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
