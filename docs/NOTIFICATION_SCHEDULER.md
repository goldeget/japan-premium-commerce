# Ordenowa private notification scheduler preparation

This directory contains a renderer and generated **sample** systemd units. The renderer writes only into the supplied output directory. It does not contact the Docker daemon, invoke the notification command, call `systemctl`, install or enable a unit, or alter the application repository.

## Source contract inspected

The scheduler contract was read at immutable repository commit `769577577e2d545045cd6ee5e49264ca2f1cb91d`:

- `modules/ordenowaprocurement/bin/dispatch-notifications.php` accepts `--shop=ID`, `--channels=mail,push`, and `--limit=1..100` (default 25). The channel set may also be a single `mail` or `push` channel.
- `modules/ordenowaprocurement/bin/NOTIFICATIONS.md` documents a once-per-minute schedule for each explicit shop. Uncertain deliveries require operator review; the generated command never passes `--retry-uncertain` or `--ack-possible-duplicate`.
- `compose.yaml` defines the running application as the `prestashop` service and injects runtime credentials through Compose environment settings. `docker/kuranea-entrypoint.sh` copies the procurement module into `/var/www/html/modules/ordenowaprocurement`.

The command shape follows [Docker Compose `exec`](https://docs.docker.com/reference/cli/docker/compose/exec/), including `-T` for non-interactive execution. The completion-based cadence uses systemd's documented [`OnBootSec=` and `OnUnitInactiveSec=` timer directives](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html). The bounded oneshot start timeout follows the [`systemd.service` timeout behavior](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html).

The generated service uses one oneshot per shop and defaults to `--channels=mail,push`. This keeps that shop's channel dispatch in one scheduled process and avoids competing per-channel timers. The host service runs as an explicitly supplied non-root worker account/group with Docker daemon access; `docker compose exec -T --user www-data` runs PHP as the container's existing web owner. The command only execs into the already-running `prestashop` container.

## Generate sample units

On a Linux deployment host, replace the example project path, explicit Compose project name, shop ID, and host account/group with values verified for that installation. Confirm the project name against the exact running stack (for example, with `docker compose ls`) and confirm the Docker `default` context points to the intended local daemon. The generator itself does not contact Docker. The host account needs access to that daemon and read access to the Compose project and its private `.env` file.

```sh
python3 tools/release/scheduler/generate_units.py \
  --project-dir /srv/ordenowa \
  --project-name kuranea \
  --docker-bin /usr/bin/docker \
  --shop-id 1 \
  --channels mail,push \
  --limit 25 \
  --host-user ordenowa-worker \
  --host-group docker \
  --timeout-seconds 600 \
  --output-dir ./generated
```

The output directory must already exist and must not be a live systemd unit directory. The renderer refuses any destination with a `systemd/system` or `systemd/user` path pair, including common `/etc`, `/run`, `/usr/lib`, `/usr/local/lib`, `/lib`, and home `.config` locations. Existing generated filenames are never overwritten. Project and Docker paths are restricted to absolute POSIX paths without whitespace, systemd `%` specifiers, shell metacharacters, or dot traversal. The required Compose project name is 1–63 characters matching `[a-z0-9][a-z0-9_-]*`; it is included in unit names and the journal identifier so separate projects with the same shop ID do not collide. Shop, batch, timeout, channel, and account values have strict allowlists/ranges.

The timer makes its first run one minute after boot, then schedules the next run one minute after the previous service becomes inactive, with a small randomized delay. This cycle-after-completion cadence prevents overlapping runs while allowing a slow batch to finish. The service is `Type=oneshot`, so systemd does not start a second copy of that same shop unit while it is active. `TimeoutStartSec` bounds the oneshot runtime (60–3600 seconds; sample 600 seconds). The default leaves ten minutes for provider calls; adjust it based on observed dispatch duration. If that explicit upper bound is reached, the CLI is terminated and its existing uncertain-delivery handling still requires operator review. `RuntimeMaxSec` is intentionally omitted because systemd does not apply it to `Type=oneshot` services.

## Secrets and logs

No secret values, environment assignments, environment-file paths, provider credentials, or recipient data are rendered into unit text. Compose reads its own runtime configuration from the project. The worker's stdout and stderr go to journald; the inspected CLI emits aggregate status counts and a generic failure line. Keep the project `.env` private and readable only by the intended deployment operators/worker.

The renderer refuses root as the host service account, but membership in a Docker daemon access group is still powerful. Select the host account and group according to the deployment's existing policy; this artifact does not create accounts or change group membership.

## Verify

The focused test suite checks exact Compose context/project selection and CLI flags, single-shop serialization, valid channel choices, timeout/batch bounds, malformed paths and values, injection-shaped strings, output-directory behavior, and the absence of environment secrets or manual uncertain-retry flags. On Linux it checks the protected systemd search paths and runs `systemd-analyze verify` against generated temporary units.

```sh
python3 -m unittest discover -s tests/release -p 'test_notification_scheduler.py' -v
```

`.github/workflows/notification-scheduler.yml` runs the focused GitHub Actions checks. It uses `/usr/bin/true` as the command path solely so unit verification does not depend on Docker being installed in the CI runner. It never enables or starts generated units.

## Sample output

`generated/ordenowa-kuranea-notify-shop1.service` and `generated/ordenowa-kuranea-notify-shop1.timer` use illustrative values (`/srv/ordenowa`, project `kuranea`, shop 1, `ordenowa-worker`, group `docker`). They are not installed or enabled on any host and are not production settings.
