# syntax=docker/dockerfile:1
FROM composer:2@sha256:b6dcd72ca98fa19d0e5b8476de179859704891fad06dd9e0b96833d4c430a5fc AS push_dependencies
WORKDIR /app
COPY modules/kuraneapush/composer.json modules/kuraneapush/composer.lock ./
# A managed runner may supply its approved CA as a transient build secret.
# Dependency credentials and trust bundles are never copied into the image.
RUN --mount=type=secret,id=composer_ca \
    if [ -f /run/secrets/composer_ca ]; then export COMPOSER_CAFILE=/run/secrets/composer_ca GIT_SSL_CAINFO=/run/secrets/composer_ca; fi; \
    composer install --no-dev --prefer-source --no-interaction --no-progress --optimize-autoloader \
    && rm -rf vendor/*/*/.git

# Assemble small application layers without copying the 1.8GB base for every COPY
# on supported Docker VFS environments. Numeric 33 is Debian www-data.
FROM scratch AS application_files
COPY themes/hummingbird/ /opt/kuranea/themes/hummingbird/
COPY themes/kuranea/ /opt/kuranea/themes/kuranea/
COPY mails/ /opt/kuranea/mails/
COPY assets/brand/ordenowa/asset-manifest.json /opt/ordenowa-brand/asset-manifest.json
COPY assets/brand/ordenowa/official_originals/ /opt/ordenowa-brand/official_originals/
COPY assets/brand/ordenowa/web_assets/ /opt/ordenowa-brand/web_assets/
COPY modules/kuraneapostcode/ /opt/kuranea/modules/kuraneapostcode/
COPY modules/kuraneabackoffice/ /opt/kuranea/modules/kuraneabackoffice/
COPY modules/kuraneabusinessprofile/ /opt/kuranea/modules/kuraneabusinessprofile/
COPY modules/kuraneacatalog/ /opt/kuranea/modules/kuraneacatalog/
COPY modules/kuraneapush/ /opt/kuranea/modules/kuraneapush/
COPY --from=push_dependencies /app/vendor/ /opt/kuranea/modules/kuraneapush/vendor/
COPY modules/ordenowaprocurement/ /opt/kuranea/modules/ordenowaprocurement/
COPY --chmod=0755 docker/kuranea-entrypoint.sh /usr/local/bin/kuranea-entrypoint
COPY --chmod=0755 docker/patch-docker-run.sh /usr/local/bin/kuranea-patch-docker-run
COPY --chown=0:33 --chmod=0640 docker/kuran-post-install.php /usr/local/bin/kuran-post-install.php
COPY --chown=0:33 --chmod=0640 docker/kuran-install-modules.php /usr/local/bin/kuran-install-modules.php
COPY --chown=0:33 --chmod=0640 docker/kuran-configure-jpy.php /usr/local/bin/kuran-configure-jpy.php
COPY --chmod=0644 docker/sync-ordenowa-brand-assets.php /usr/local/bin/sync-ordenowa-brand-assets.php
COPY --chmod=0755 docker/pre-install/10-kuranea-cache-ownership.sh /tmp/pre-install-scripts/10-kuranea-cache-ownership.sh
COPY --chmod=0755 docker/init/10-kuranea-bootstrap.sh /tmp/init-scripts/10-kuranea-bootstrap.sh

FROM prestashop/prestashop:9.2.0@sha256:2b8f90176b3fad68f8f5c7fbdeaa137f2f05578d2ccff92ab581efa6b317c1d8
COPY --from=application_files / /
# The scratch bundle supplies /tmp scripts; retain the base image's shared
# temporary-directory permissions for the non-root Symfony/PrestaShop runtime.
RUN chmod 1777 /tmp \
    && find /opt/kuranea /opt/ordenowa-brand -type d -exec chmod 0755 {} + \
    && find /opt/kuranea /opt/ordenowa-brand -type f -exec chmod 0644 {} +

ENTRYPOINT ["/usr/local/bin/kuranea-entrypoint"]
CMD ["/tmp/docker_run.sh"]
