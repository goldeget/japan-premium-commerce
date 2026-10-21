FROM prestashop/prestashop:9.2.0@sha256:2b8f90176b3fad68f8f5c7fbdeaa137f2f05578d2ccff92ab581efa6b317c1d8

# Keep the upstream submodule read-only in Git; copy its pinned files into the
# image so PrestaShop's first-run file copy does not write through a bind mount.
COPY themes/hummingbird/ /opt/kuranea/themes/hummingbird/
COPY themes/kuranea/ /opt/kuranea/themes/kuranea/
COPY modules/kuraneapostcode/ /opt/kuranea/modules/kuraneapostcode/
COPY modules/kuraneabackoffice/ /opt/kuranea/modules/kuraneabackoffice/
COPY --chmod=0755 docker/kuranea-entrypoint.sh /usr/local/bin/kuranea-entrypoint
COPY --chown=root:www-data --chmod=0640 docker/kuran-post-install.php /usr/local/bin/kuran-post-install.php
COPY --chown=root:www-data --chmod=0640 docker/kuran-install-modules.php /usr/local/bin/kuran-install-modules.php
COPY --chmod=0755 docker/pre-install/10-kuranea-cache-ownership.sh /tmp/pre-install-scripts/10-kuranea-cache-ownership.sh
COPY --chmod=0755 docker/post-install/10-kuranea-bootstrap.sh /tmp/post-install-scripts/10-kuranea-bootstrap.sh

ENTRYPOINT ["/usr/local/bin/kuranea-entrypoint"]
CMD ["/tmp/docker_run.sh"]
