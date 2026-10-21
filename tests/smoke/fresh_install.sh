#!/usr/bin/env bash
set -euo pipefail

project_name=${1:?Pass the unique Compose project name}
base_url=${SHOP_BASE_URL:-http://127.0.0.1:8080}

compose() {
  docker compose -p "$project_name" "$@"
}

db_query() {
  compose exec -T mariadb sh -ec 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb --protocol=tcp -h127.0.0.1 -uroot -N "$MARIADB_DATABASE" -e "$1"' -- "$1"
}

storefront_status=$(curl --fail --silent --show-error --location --output /tmp/kuranea-home.html --write-out '%{http_code}' "$base_url/")
test "$storefront_status" = 200
grep -q '<html[^>]*lang="ja-JP"' /tmp/kuranea-home.html
admin_status=$(curl --fail --silent --show-error --location --output /dev/null --write-out '%{http_code}' "$base_url/admin-kuranea/login")
test "$admin_status" = 200

db_ok=$(db_query 'SELECT 1')
test "$db_ok" = 1
theme=$(db_query 'SELECT theme_name FROM ps_shop WHERE id_shop=1')
test "$theme" = kuranea
languages=$(db_query "SELECT COUNT(*) FROM ps_lang WHERE active=1 AND iso_code IN ('ja','en','ko')")
test "$languages" = 3
shop_default=$(db_query "SELECT COUNT(*) FROM ps_configuration c JOIN ps_lang l ON l.id_lang=CAST(c.value AS UNSIGNED) WHERE c.name='PS_LANG_DEFAULT' AND l.iso_code='ja'")
test "$shop_default" = 1
employee_locale=$(db_query 'SELECT l.iso_code FROM ps_employee e JOIN ps_lang l ON l.id_lang=e.id_lang WHERE e.id_employee=1')
test "$employee_locale" = ko
table_count_before=$(db_query 'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()')

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

cache_dir_owner=$(compose exec -T prestashop stat -c '%U:%G' /var/www/html/var/cache/prod)
test "$cache_dir_owner" = www-data:www-data
cache_index_owner=$(compose exec -T prestashop stat -c '%U:%G' /var/www/html/var/cache/prod/class_index.php)
test "$cache_index_owner" = www-data:www-data
compose exec -T prestashop sh -ec 'runuser -g www-data -u www-data -- test -w /var/www/html/var/cache/prod/class_index.php'

compose restart mariadb prestashop
for attempt in $(seq 1 60); do
  if curl --fail --silent --show-error --location --output /dev/null "$base_url/" && [ "$(db_query 'SELECT 1')" = 1 ]; then
    break
  fi
  if [ "$attempt" -eq 60 ]; then
    echo 'Services did not recover after restart' >&2
    exit 1
  fi
  sleep 5
done

table_count_after=$(db_query 'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()')
test "$table_count_before" = "$table_count_after"
test "$(db_query 'SELECT theme_name FROM ps_shop WHERE id_shop=1')" = kuranea
test "$(db_query 'SELECT 1')" = 1
printf 'PASS: empty-volume install, www-data cache ownership/writeability, ja/en/ko setup, ko employee locale, active KURANEA theme, CSS, BO login, and restart persistence (%s tables)\n' "$table_count_after"
