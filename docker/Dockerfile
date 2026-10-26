FROM prestashop/prestashop:9.2.0@sha256:2b8f90176b3fad68f8f5c7fbdeaa137f2f05578d2ccff92ab581efa6b317c1d8

# Keep the upstream submodule read-only in Git; copy its pinned files into the
# image so PrestaShop's first-run file copy does not write through a bind mount.
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
COPY --chmod=0755 docker/kuranea-entrypoint.sh /usr/local/bin/kuranea-entrypoint
COPY --chmod=0755 docker/patch-docker-run.sh /usr/local/bin/kuranea-patch-docker-run
COPY --chown=root:www-data --chmod=0640 docker/kuran-post-install.php /usr/local/bin/kuran-post-install.php
COPY --chown=root:www-data --chmod=0640 docker/kuran-install-modules.php /usr/local/bin/kuran-install-modules.php
COPY --chown=root:www-data --chmod=0640 docker/kuran-configure-jpy.php /usr/local/bin/kuran-configure-jpy.php
COPY --chmod=0644 docker/sync-ordenowa-brand-assets.php /usr/local/bin/sync-ordenowa-brand-assets.php
COPY --chmod=0755 docker/pre-install/10-kuranea-cache-ownership.sh /tmp/pre-install-scripts/10-kuranea-cache-ownership.sh
COPY --chmod=0755 docker/init/10-kuranea-bootstrap.sh /tmp/init-scripts/10-kuranea-bootstrap.sh

ENTRYPOINT ["/usr/local/bin/kuranea-entrypoint"]
CMD ["/tmp/docker_run.sh"]
