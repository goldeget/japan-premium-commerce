# Private notification health snapshot

This is a private monitoring collector for `modules/ordenowaprocurement`, based on the database/schema/dispatcher and isolated-test contracts at candidate commit `769577577e2d545045cd6ee5e49264ca2f1cb91d`. The SQL collector is SELECT-only; native bootstrap side effects are not instrumented.

## Private command

`modules/ordenowaprocurement/bin/health-snapshot.php` is CLI-only and returns 404 under non-CLI PHP. It checks one `SELECT 1`, reads `disk_free_space` and `disk_total_space` for the PrestaShop root volume, and runs two aggregates scoped to one validated `id_shop`: a status/timing aggregate over only the five monitored `notification_delivery` states and an anti-join count of notification events with no delivery row of any channel.

- `backlog` counts due `PENDING`/`RETRY` and all `SENDING` channel-delivery rows, plus events with no delivery row of any channel.
- `future_retry` separately counts `RETRY` rows whose `available_at` is still in the future; these are not due backlog and do not increase stale age.
- `undelivered_events` counts events that have no channel-delivery row at all. The CLI has no channel-set option, so it does not report a missing expected channel when another channel row already exists.
- `failed` counts `FAILED` channel-delivery rows.
- `uncertain` counts `UNCERTAIN` channel-delivery rows.
- `oldest_stale_age_seconds` is the maximum age among due pending/retry rows (`available_at`), claimed `SENDING` rows (`claimed_at`), and undelivered events (`created_at`). Once it reaches the stale-age threshold, overall status is at least `warning`.

Delivery counts are per channel, not distinct notification-event counts. The anti-join reads only `id_shop`, event ID linkage, and `created_at`; it does not read recipient, message, event name, target, provider response, or payload fields. The collector never invokes `Dispatcher` or a transport. Runtime errors are replaced with a fixed message; input errors print fixed usage text without echoing values.

Successful stdout is one JSON object containing only overall status, the selected shop ID, `database_select_1`, the numeric disk-free ratio from 0 through 1, and numeric aggregate counts/ages. Thresholds do not claim an approved SLA; the technical CLI defaults are disk free warning/critical `0.10` / `0.05`, backlog warning/critical `100` / `500`, failed `1` / `10`, uncertain `1` / `5`, and stale age `900` seconds.

Exit codes follow monitoring conventions: `0` means `ok`, `1` means `warning`, `2` means `critical`, `3` means an unavailable/runtime failure, and `64` means invalid usage. Warning and critical runs still emit the validated JSON snapshot before exiting with their nonzero status. Runtime failures emit no JSON and write only a fixed redacted message to stderr; invalid usage emits fixed usage text without echoing supplied values.

Example:

```sh
php modules/ordenowaprocurement/bin/health-snapshot.php --shop=1
```

Thresholds are explicit and validated when overridden:

```sh
php modules/ordenowaprocurement/bin/health-snapshot.php --shop=1 --disk-warning-ratio=0.10 --disk-critical-ratio=0.05 --backlog-warning=100 --backlog-critical=500 --failed-warning=1 --failed-critical=10 --uncertain-warning=1 --uncertain-critical=5 --stale-after-seconds=900
```

## Required isolated acceptance

`tests/procurement/notifications_health.php` uses the existing `points_support.php` test helper, `Database`, `Schema`, and a random test table prefix. It checks empty/backlog/failed/uncertain counts, shop isolation, threshold validation, output fields, before/after row hashes for read-only behavior, healthy/warning/critical/unavailable/invalid-usage exit codes, and redaction when the actual collector receives a database exception carrying a synthetic secret. Its isolated subprocess case also verifies that native bootstrap stdout is discarded and a premature bootstrap `exit(0)` is converted to unavailable exit `3` rather than false health.

`ci_acceptance.sh` copies `tests/procurement/notifications*.php` into the disposable PrestaShop container and exposes the isolated `ordenowa_procurement_test` DSN through its `behavior` helper. The integrated required phase runs behavior checks followed by the actual native CLI:

```sh
run_phase notifications_health health_snapshot_acceptance
```

The phase is included in the required aggregate phase set beside the notification behavior/concurrency checks. It captures native CLI output privately and validates exact keys, shop, numeric bounds and status/exit agreement before retaining the sanitized observation.

## Boundaries

The database collector calls `Database::value()` once for `SELECT 1` and `Database::one()` twice for the shop/status and undelivered-event aggregates. The only write SQL is in the isolated test fixture setup and its cleanup. The collector itself has no DDL/DML, retry/acknowledgement options, provider transport, environment/secret output, or HTTP controller. The normal PrestaShop bootstrap still runs and is not claimed to be side-effect-free; the CLI entry point buffers and discards its stdout, and guards premature bootstrap termination so it cannot appear healthy. Disk and database runtime failures share a fixed redacted CLI failure response.

The host has no standalone PHP CLI. Actual PHP/MariaDB and native bootstrap execution is performed by the isolated procurement acceptance workflow; exact tested commit, run and outcome are recorded in TEST_RESULTS.md.


The native CLI output is first captured privately, validated for exact numeric schema/shop/exit status, and only the bounded observation is written to health-snapshot-outcome.json. Required phase notifications_health prevents an omitted check from passing the aggregate.

The CI phase validates collection and redaction; it does not relabel an observed warning or critical snapshot as an operationally healthy service.
