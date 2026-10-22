#!/bin/sh
set -eu

if [ ! -f /var/www/html/app/config/parameters.php ]; then
    echo "PrestaShop has not created its application parameters; refusing to start an incomplete shop." >&2
    exit 1
fi

admin_final_name=${KURANEA_ADMIN_FOLDER:-admin-kuranea}
case "$admin_final_name" in
    ''|.|..|*/*) echo "Invalid KURANEA admin folder name." >&2; exit 1 ;;
esac

admin_dir="/var/www/html/$admin_final_name"
# Keep the installer's detected admin path intact until the PHP bootstrap runs
# its official post-install work and moves that populated directory safely.
runuser -g www-data -u www-data -- php /usr/local/bin/kuran-post-install.php
runuser -g www-data -u www-data -- php /usr/local/bin/kuran-install-modules.php

if [ ! -d "$admin_dir" ]; then
    echo "The completed KURANEA admin directory is missing: $admin_dir" >&2
    exit 1
fi
if [ -d /var/www/html/admin-dev ]; then
    echo "The public admin-dev path remains after finalizing KURANEA admin." >&2
    exit 1
fi
