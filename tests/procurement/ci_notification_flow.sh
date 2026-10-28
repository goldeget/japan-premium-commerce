#!/usr/bin/env bash
set -euo pipefail
[[ ${CI:-} == true && ${KURANEA_ISOLATED_CI:-} == 1 ]]
[[ ${GITHUB_RUN_ID:-} =~ ^[0-9]+$ && ${GITHUB_RUN_ATTEMPT:-} =~ ^[0-9]+$ ]]
[[ ${CI_COMPOSE_PROJECT_NAME:-} == "ordenowa-procurement-ci-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}" ]]
compose() { docker compose -f compose.yaml -f tests/procurement/ci.compose.yaml -p "$CI_COMPOSE_PROJECT_NAME" "$@"; }
native() { compose exec -T prestashop php /tmp/ordenowa-procurement-ci/ci_notifications.php "$@"; }
worker() { compose exec -T prestashop php /var/www/html/modules/ordenowaprocurement/bin/dispatch-notifications.php --shop=1 --channels=mail "--limit=$1"; }
native locale en
worker 1
native locale ko
worker 1
native locale ja
worker 100
# A completed delivery must not resend or rerun a point award.
worker 100
native verify
python3 tests/procurement/ci_mailpit.py
