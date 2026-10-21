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

brand_dir="/var/www/html/themes/kuranea/assets/img/brand"
if [ ! -f "$brand_dir/kuranea-logo-desktop.png" ] || [ ! -f "$brand_dir/favicon.ico" ]; then
    echo "KURANEA brand assets are incomplete: $brand_dir" >&2
    exit 1
fi
mkdir -p /var/www/html/img
cp "$brand_dir/kuranea-logo-desktop.png" /var/www/html/img/logo.png
cp "$brand_dir/favicon.ico" /var/www/html/img/favicon.ico
chown www-data:www-data /var/www/html/img/logo.png /var/www/html/img/favicon.ico
cp /var/www/html/themes/kuranea/assets/sw.js /var/www/html/sw.js
chown www-data:www-data /var/www/html/sw.js

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
