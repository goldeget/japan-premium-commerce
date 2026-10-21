#!/bin/sh
set -eu

if [ ! -f /var/www/html/app/config/parameters.php ]; then
    echo "PrestaShop has not created its application parameters; refusing to start an incomplete shop." >&2
    exit 1
fi

runuser -g www-data -u www-data -- php /usr/local/bin/kuran-post-install.php
runuser -g www-data -u www-data -- php /usr/local/bin/kuran-install-modules.php
