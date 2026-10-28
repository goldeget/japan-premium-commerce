# Web Push provider setup

`WebPushDeliveryProvider` uses the locked `minishlink/web-push` 9 dependency for Web Push payload encryption and VAPID signing. No custom Web Push cryptography is implemented. `DeliveryPayload` contains only an allowlisted event (`procurement`, `points`, or a retained legacy event) and locale (`ja`, `en`, `ko`). It contains no customer identity, product/request identifier, point amount or account balance.

## Build

Commit `composer.json` and `composer.lock`; keep `vendor/` out of Git. Install the locked dependencies in the image build:

```sh
composer install --working-dir=modules/kuraneapush --no-dev --prefer-dist --no-interaction --no-progress --no-scripts --optimize-autoloader
```

Copy the resulting module including `vendor/` into `/opt/kuranea/modules/kuraneapush/` before the existing module sync. The installed runtime needs the extensions required by the lock file. Keep TLS verification enabled when downloading dependencies. Do not copy local caches or secrets into the image.

## Configuration

Provide these values through the deployment secret/environment mechanism, never through source files or customer input:

| Variable | Purpose |
| --- | --- |
| `ORDENOWA_PUSH_VAPID_PUBLIC_KEY` | The application's persistent uncompressed P-256 public key, encoded as base64url. This public value is supplied to the browser only when ready. |
| `ORDENOWA_PUSH_VAPID_PRIVATE_KEY` | Matching persistent private key. Keep secret. |
| `ORDENOWA_PUSH_VAPID_SUBJECT` | Operator contact using a valid `mailto:` address or HTTPS URL. |
| `ORDENOWA_PUSH_STORAGE_KEY` | Existing base64-encoded 32-byte master key for encrypted subscription storage; independent from VAPID keys. |

Use the maintained library's VAPID key creation facility under the operator's secure provisioning process. Keep VAPID and storage keys stable across restarts. A different VAPID key invalidates the application's existing browser subscription relationship; changing the storage key makes existing encrypted subscription records unreadable.

For each native shop, the Korean notification settings must explicitly enable `ORDENOWA_PUSH_LIVE_ENABLED` and acknowledge `ORDENOWA_PUSH_HTTPS_VALIDATED`. Both default to off. Complete actual configured-origin and browser HTTPS validation before setting the acknowledgement. The subscription controller separately enforces trusted current HTTPS, origin/token, login, consent and storage readiness. The factory does not interpret a flag as browser or delivery evidence.

Enable only the wanted event categories, including `ORDENOWA_PUSH_EVENT_PROCUREMENT` and `ORDENOWA_PUSH_EVENT_POINTS`; install localized consent notices. New subscriptions require explicit current consent. Missing flags, keys, dependency or invalid VAPID details keep the provider unavailable. Missing storage key keeps encrypted delivery unavailable. In-app history remains the durable user-visible record.

## Delivery behavior

`LivePushFactory::outbox($shop)` binds the existing owner-scoped SQL outbox, subscription repository, cipher and configured provider. The procurement notification dispatcher invokes this explicitly. The provider validates every decrypted endpoint with `SubscriptionValidator` before HTTP. Only supported HTTPS browser push service domains are accepted; credentials, nonstandard ports, local/IP and unrelated destinations fail.

The HTTP client enforces TLS verification, no redirects, a 10-second total timeout and 3-second connection timeout. Payload TTL is 300 seconds. Provider success maps to delivered; HTTP 404/410 maps to gone and the outbox removes that owner's expired target. Other responses or exceptions map to retryable failure. Existing outbox consent checks, deduplication, uncertain-attempt handling and explicit retry remain authoritative. No endpoint, key, response body or exception detail is logged by the adapter.

## Evidence

Run `php tests/pwa/php/live_provider.php` after installing dependencies. It uses real library encryption and a mocked Guzzle HTTP handler: success, expired target, retryable error, strict endpoint rejection, unavailable configuration, TLS options and timeout bounds. It sends no real push notifications and uses generated ephemeral test keys only in process memory.

The implemented adapter and offline tests do not establish production HTTPS, installed-device permission, browser push service reachability or real delivery. Those require the approved environment and operator-controlled credentials. No live push was sent during this implementation.
