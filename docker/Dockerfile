FROM prestashop/prestashop:9.2.0@sha256:2b8f90176b3fad68f8f5c7fbdeaa137f2f05578d2ccff92ab581efa6b317c1d8

# Keep the upstream submodule read-only in Git; copy its pinned files into the
# image so PrestaShop's first-run file copy does not write through a bind mount.
COPY themes/hummingbird/ /opt/kuranea/themes/hummingbird/
COPY themes/kuranea/ /opt/kuranea/themes/kuranea/
COPY docker/kuranea-entrypoint.sh /usr/local/bin/kuranea-entrypoint

RUN chmod 0755 /usr/local/bin/kuranea-entrypoint

ENTRYPOINT ["/usr/local/bin/kuranea-entrypoint"]
CMD ["/tmp/docker_run.sh"]
