# Split source application deployment from test fixture staging. In packaged
# mode the application already comes from the immutable image; copying source
# modules or repairing their permissions would invalidate that runtime proof.
copy_acceptance_files() {
  if [[ -n ${ORDENOWA_CI_IMAGE_REF:-} ]]; then
    ORDENOWA_APPLICATION_HOT_COPY=false
  else
    ORDENOWA_APPLICATION_HOT_COPY=true
    # Preserve the legacy local/integration path when no package image was
    # selected. These are the application's source files, not test fixtures.
    compose cp modules/ordenowaprocurement/. prestashop:/var/www/html/modules/ordenowaprocurement/
    compose cp themes/kuranea/templates/_partials/footer.tpl prestashop:/var/www/html/themes/kuranea/templates/_partials/footer.tpl
    compose cp themes/kuranea/templates/_partials/header.tpl prestashop:/var/www/html/themes/kuranea/templates/_partials/header.tpl
    compose cp themes/kuranea/templates/customer/my-account.tpl prestashop:/var/www/html/themes/kuranea/templates/customer/my-account.tpl
    compose exec -T prestashop sh -ec 'chown www-data:www-data /var/www/html/themes/kuranea/templates/_partials/footer.tpl /var/www/html/themes/kuranea/templates/_partials/header.tpl /var/www/html/themes/kuranea/templates/customer/my-account.tpl; chmod 0644 /var/www/html/themes/kuranea/templates/_partials/footer.tpl /var/www/html/themes/kuranea/templates/_partials/header.tpl /var/www/html/themes/kuranea/templates/customer/my-account.tpl; chown -R www-data:www-data /var/www/html/modules/ordenowaprocurement; find /var/www/html/modules/ordenowaprocurement -type d -exec chmod 0755 {} +; find /var/www/html/modules/ordenowaprocurement -type f -exec chmod 0644 {} +'
  fi

  # These copies are test fixtures and diagnostics only. They do not replace
  # runtime application code and remain available in both execution modes.
  compose exec -T prestashop mkdir -p /tmp/ordenowa-procurement-ci/catalog /var/www/html/tests/procurement /var/www/html/tests/catalog /var/www/html/tests/admin_audit /var/www/html/tests/admin_locale
  for source in tests/procurement/ci_*.php; do
    compose cp "$source" prestashop:/tmp/ordenowa-procurement-ci/
  done
  for source in tests/procurement/requests*.php tests/procurement/points*.php tests/procurement/native*.php tests/procurement/customer*.php tests/procurement/notifications*.php tests/procurement/policies*.php tests/procurement/support*.php tests/procurement/navigation*.php tests/procurement/signin*.php tests/procurement/language*.php; do
    compose cp "$source" prestashop:/var/www/html/tests/procurement/
  done
  compose cp tests/catalog/. prestashop:/tmp/ordenowa-procurement-ci/catalog/
  compose cp tests/catalog/. prestashop:/var/www/html/tests/catalog/
  compose cp tests/admin_audit/. prestashop:/var/www/html/tests/admin_audit/
  compose cp tests/admin_locale/. prestashop:/var/www/html/tests/admin_locale/
  compose cp tests/procurement/accounts_native.php prestashop:/tmp/ordenowa-procurement-ci/accounts_native.php
  compose exec -T prestashop sh -ec 'find /var/www/html/tests /tmp/ordenowa-procurement-ci -type d -exec chmod 0755 {} +; find /var/www/html/tests /tmp/ordenowa-procurement-ci -type f -exec chmod 0644 {} +'
  compose exec -T prestashop chown -R www-data:www-data /tmp/ordenowa-procurement-ci
}
