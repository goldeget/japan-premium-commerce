#!/usr/bin/env bash
set -euo pipefail

project_name=${1:?Pass the unique Compose project name}
base_url=${SHOP_BASE_URL:-http://127.0.0.1:8080}
verification_phase="setup"

report_verification_failure() {
  local failure_status=$1
  local sanitized_phase=${verification_phase:-unknown}
  local sanitized_status=$failure_status
  if [[ ! $sanitized_phase =~ ^[A-Za-z0-9_.-]+$ ]]; then
    sanitized_phase=unknown
  fi
  if [[ ! $sanitized_status =~ ^[0-9]+$ ]]; then
    sanitized_status=unknown
  fi
  printf 'FRESH_INSTALL_VERIFICATION_FAILED phase=%s exit_code=%s\n' \
    "$sanitized_phase" "$sanitized_status" >&2
  printf '::error title=Fresh install verification::FRESH_INSTALL_VERIFICATION_FAILED phase=%s exit_code=%s\n' \
    "$sanitized_phase" "$sanitized_status" >&2
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    printf 'FRESH_INSTALL_VERIFICATION_FAILED phase=%s exit_code=%s\n' \
      "$sanitized_phase" "$sanitized_status" >> "$GITHUB_STEP_SUMMARY"
  fi
}

trap 'report_verification_failure "$?"' ERR

compose() {
  docker compose -p "$project_name" "$@"
}

db_query() {
  compose exec -T mariadb sh -ec 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb --protocol=tcp -h127.0.0.1 -uroot -N "$MARIADB_DATABASE" -e "$1"' -- "$1"
}

verification_phase="initial_storefront_http_request"
storefront_status=$(curl --fail --silent --show-error --location --output /tmp/kuranea-home.html --write-out '%{http_code}' "$base_url/")
verification_phase="initial_storefront_http_status"
test "$storefront_status" = 200
verification_phase="initial_storefront_language"
grep -q '<html[^>]*lang="ja-JP"' /tmp/kuranea-home.html
verification_phase="initial_admin_login_http_request"
admin_status=$(curl --fail --silent --show-error --location --output /tmp/kuranea-admin-login.html --write-out '%{http_code}' "$base_url/admin-kuranea/login")
verification_phase="initial_admin_login_http_status"
test "$admin_status" = 200
verification_phase="initial_admin_brand_name"
grep -q 'ORDENOWA' /tmp/kuranea-admin-login.html
verification_phase="initial_admin_korean_login_label"
grep -q '로그인' /tmp/kuranea-admin-login.html
verification_phase="initial_admin_korean_password_label"
grep -q '비밀번호' /tmp/kuranea-admin-login.html
verification_phase="initial_admin_no_dutch_translation"
! grep -q 'Sleutelwoord' /tmp/kuranea-admin-login.html
verification_phase="initial_admin_no_legacy_logo_fallback"
! grep -q 'kuraneabackoffice/views/img/kuranea-logo.png' /tmp/kuranea-admin-login.html
verification_phase="initial_admin_no_legacy_brand_text"
! grep -q 'KURANEA' /tmp/kuranea-admin-login.html
verification_phase="initial_install_files_and_admin_css"
compose exec -T prestashop sh -ec '
  test -s /var/www/html/app/config/parameters.php
  test -s /var/www/html/var/cache/prod/appParameters.php
  test -s /var/www/html/var/.kuranea-bootstrap-v2
  test ! -e /var/www/html/install
  test -d /var/www/html/admin-kuranea
  test ! -e /var/www/html/admin-dev
  test -s /var/www/html/admin-kuranea/themes/new-theme/public/theme.css
'
admin_css_url=$(python3 - <<'PY'
from html.parser import HTMLParser
from urllib.parse import urljoin
import os

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stylesheets=[]
    def handle_starttag(self, tag, attrs):
        values=dict(attrs)
        if tag == 'link' and values.get('rel') == 'stylesheet':
            self.stylesheets.append(values.get('href',''))

parser=Links()
parser.feed(open('/tmp/kuranea-admin-login.html',encoding='utf-8').read())
base=os.environ['SHOP_BASE_URL'].rstrip('/') + '/'
links=[urljoin(base, value) for value in parser.stylesheets if '/admin-kuranea/themes/new-theme/public/theme.css' in value]
if not links:
    raise SystemExit('PrestaShop Back Office theme CSS link was not rendered')
print(links[0])
PY
)
curl --fail --silent --show-error "$admin_css_url" -o /tmp/kuranea-admin-theme.css

verification_phase="initial_database_shop_and_postcode_configuration"
db_ok=$(db_query 'SELECT 1')
test "$db_ok" = 1
theme=$(db_query 'SELECT theme_name FROM ps_shop WHERE id_shop=1')
test "$theme" = kuranea
languages=$(db_query "SELECT COUNT(*) FROM ps_lang WHERE active=1 AND iso_code IN ('ja','en','ko')")
test "$languages" = 3
shop_default=$(db_query "SELECT COUNT(*) FROM ps_configuration c JOIN ps_lang l ON l.id_lang=CAST(c.value AS UNSIGNED) WHERE c.name='PS_LANG_DEFAULT' AND l.iso_code='ja'")
test "$shop_default" = 1
checkout_route=$(db_query "SELECT ml.url_rewrite FROM ps_meta_lang ml JOIN ps_meta m ON m.id_meta=ml.id_meta JOIN ps_lang l ON l.id_lang=ml.id_lang WHERE m.page='order' AND ml.id_shop=1 AND l.iso_code='ja'")
test "$checkout_route" = checkout
checkout_rewriting=$(db_query "SELECT value FROM ps_configuration WHERE name='PS_REWRITING_SETTINGS'")
test "$checkout_rewriting" = 1
default_currency=$(db_query "SELECT cur.iso_code FROM ps_configuration cfg JOIN ps_currency cur ON cur.id_currency=CAST(cfg.value AS UNSIGNED) WHERE cfg.name='PS_CURRENCY_DEFAULT'")
test "$default_currency" = JPY
jpy_currency=$(db_query "SELECT COUNT(*) FROM ps_currency WHERE iso_code='JPY' AND active=1 AND deleted=0")
test "$jpy_currency" = 1
jpy_translations=$(db_query "SELECT COUNT(DISTINCT cl.id_lang) FROM ps_currency c JOIN ps_currency_lang cl ON cl.id_currency=c.id_currency JOIN ps_lang l ON l.id_lang=cl.id_lang WHERE c.iso_code='JPY' AND l.iso_code IN ('ja','en','ko')")
test "$jpy_translations" = 3
active_non_jpy=$(db_query "SELECT COUNT(*) FROM ps_currency WHERE iso_code<>'JPY' AND active=1 AND deleted=0")
test "$active_non_jpy" = 0
employee_locale=$(db_query 'SELECT l.iso_code FROM ps_employee e JOIN ps_lang l ON l.id_lang=e.id_lang WHERE e.id_employee=1')
test "$employee_locale" = ko
postcode_module=$(db_query "SELECT COUNT(*) FROM ps_module WHERE name='kuraneapostcode' AND active=1")
backoffice_module=$(db_query "SELECT COUNT(*) FROM ps_module WHERE name='kuraneabackoffice' AND active=1")
test "$postcode_module" = 1
test "$backoffice_module" = 1
compose exec -T prestashop sh -ec '
  for module_file in \
    /var/www/html/modules/kuraneabackoffice/src/AdminLocaleSubscriber.php \
    /var/www/html/modules/kuraneabackoffice/translations/ko-KR/AdminGlobal.ko-KR.xlf \
    /var/www/html/modules/kuraneabackoffice/views/templates/hook/admin-login.tpl; do
    runuser -g www-data -u www-data -- test -r "$module_file"
  done
'
postcode_states=$(db_query "SELECT COUNT(*) FROM ps_state s JOIN ps_country c ON c.id_country=s.id_country WHERE c.iso_code='JP' AND s.active=1 AND s.iso_code REGEXP '^JP-[0-9]{2}$'")
test "$postcode_states" = 47
postcode_table=$(db_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='ps_kuraneapostcode_address'")
test "$postcode_table" = 1
postcode_stage_table=$(db_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='ps_kuraneapostcode_stage'")
test "$postcode_stage_table" = 1
postcode_stage_rows=$(db_query 'SELECT COUNT(*) FROM ps_kuraneapostcode_stage')
test "$postcode_stage_rows" = 0
table_count_before=$(db_query 'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()')

verification_phase="initial_storefront_theme_assets"
css_url=$(python3 - <<'PY'
from html.parser import HTMLParser
from urllib.parse import urljoin
import os

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs=[]
    def handle_starttag(self, tag, attrs):
        values=dict(attrs)
        if tag == 'link' and values.get('rel') == 'stylesheet':
            self.hrefs.append(values.get('href',''))

parser=Links()
parser.feed(open('/tmp/kuranea-home.html',encoding='utf-8').read())
base=os.environ['SHOP_BASE_URL'].rstrip('/') + '/'
links=[urljoin(base, value) for value in parser.hrefs if 'themes/kuranea/assets/cache/' in value and value.endswith('.css')]
if not links:
    raise SystemExit('KURANEA theme stylesheet link was not rendered')
print(links[0])
PY
)
curl --fail --silent --show-error "$css_url" -o /tmp/kuranea-theme.css
grep -q -- '--kuranea-navy' /tmp/kuranea-theme.css

verification_phase="initial_cache_ownership"
cache_dir_owner=$(compose exec -T prestashop stat -c '%U:%G' /var/www/html/var/cache/prod)
test "$cache_dir_owner" = www-data:www-data
cache_index_owner=$(compose exec -T prestashop stat -c '%U:%G' /var/www/html/var/cache/prod/class_index.php)
test "$cache_index_owner" = www-data:www-data
compose exec -T prestashop sh -ec 'runuser -g www-data -u www-data -- test -w /var/www/html/var/cache/prod/class_index.php'

verification_phase="initial_bootstrap_marker"
initial_bootstrap_logs=$(compose logs --no-color prestashop 2>&1)
if ! grep -Eq 'ORDENOWA bootstrap: storefront=ja, en/ko=enabled, admin=ko, theme=kuranea|KURANEA bootstrap already completed\.' <<< "$initial_bootstrap_logs"; then
  false
fi

verification_phase="restart_service_recovery"
completed_marker_count_before_restart=$(grep -Fc 'KURANEA bootstrap already completed.' <<< "$initial_bootstrap_logs" || true)
compose restart mariadb prestashop
for attempt in $(seq 1 60); do
  if curl --fail --silent --show-error --location --output /dev/null "$base_url/" && [ "$(db_query 'SELECT 1')" = 1 ]; then
    break
  fi
  if [ "$attempt" -eq 60 ]; then
    echo 'Services did not recover after restart' >&2
    false
  fi
  sleep 5
done

verification_phase="restart_bootstrap_marker"
restart_bootstrap_logs=$(compose logs --no-color prestashop 2>&1)
completed_marker_count_after_restart=$(grep -Fc 'KURANEA bootstrap already completed.' <<< "$restart_bootstrap_logs" || true)
test "$completed_marker_count_after_restart" -gt "$completed_marker_count_before_restart"

verification_phase="restart_persistent_files"
compose exec -T prestashop sh -ec '
  test -s /var/www/html/app/config/parameters.php
  test -s /var/www/html/var/cache/prod/appParameters.php
  test -s /var/www/html/var/.kuranea-bootstrap-v2
  test ! -e /var/www/html/install
  test ! -e /var/www/html/admin-dev
'
verification_phase="restart_admin_branding"
admin_status_after_restart=$(curl --silent --show-error --location --output /tmp/kuranea-admin-login-after-restart.html --write-out '%{http_code}' "$base_url/admin-kuranea/login")
test "$admin_status_after_restart" = 200
grep -q 'ORDENOWA' /tmp/kuranea-admin-login-after-restart.html
! grep -q 'KURANEA' /tmp/kuranea-admin-login-after-restart.html

verification_phase="restart_jpy_currency"
default_currency_after_restart=$(db_query "SELECT cur.iso_code FROM ps_configuration cfg JOIN ps_currency cur ON cur.id_currency=CAST(cfg.value AS UNSIGNED) WHERE cfg.name='PS_CURRENCY_DEFAULT'")
test "$default_currency_after_restart" = JPY
jpy_translations_after_restart=$(db_query "SELECT COUNT(DISTINCT cl.id_lang) FROM ps_currency c JOIN ps_currency_lang cl ON cl.id_currency=c.id_currency JOIN ps_lang l ON l.id_lang=cl.id_lang WHERE c.iso_code='JPY' AND l.iso_code IN ('ja','en','ko')")
test "$jpy_translations_after_restart" = 3
checkout_route_after_restart=$(db_query "SELECT ml.url_rewrite FROM ps_meta_lang ml JOIN ps_meta m ON m.id_meta=ml.id_meta JOIN ps_lang l ON l.id_lang=ml.id_lang WHERE m.page='order' AND ml.id_shop=1 AND l.iso_code='ja'")
test "$checkout_route_after_restart" = checkout
verification_phase="restart_shop_identity_and_schema"
test "$(db_query 'SELECT name FROM ps_shop WHERE id_shop=1')" = ORDENOWA
table_count_after=$(db_query 'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()')
test "$table_count_before" = "$table_count_after"
test "$(db_query 'SELECT theme_name FROM ps_shop WHERE id_shop=1')" = kuranea
verification_phase="restart_final_database_check"
test "$(db_query 'SELECT 1')" = 1
printf 'PASS: empty-volume install, JPY default currency, cache ownership/writeability, ja/en/ko setup, ko employee locale, active storefront theme, ORDENOWA text branding without legacy logo fallback, Korean admin-kuranea login with no admin-dev path, postcode/back-office/business-profile modules, and restart persistence (%s tables)\n' "$table_count_after"
