# PWA Web Push Design

## Intent

Implement the approved Web Push foundations for ORDENOWA without sending messages to real customers. Customers need an explicit, revocable notification subscription, and the service worker must show only generic, localized messages that remain safe on a lock screen. The feature must preserve the existing rule that account, order, cart, and other private pages are never cached.

## Current state

`themes/kuranea/assets/sw.js` currently handles install, activate, fetch, offline fallback, and logout redirects. `themes/kuranea/assets/js/pwa-register.js` registers the root worker. The account page exposes `displayCustomerAccount`, but no push consent UI, subscription storage, or push handlers exist. `kuraneabusinessprofile` owns brand and seller settings and will remain separate.

## Goals

- Add a dedicated `kuraneapush` module with an authenticated customer account control and POST-only subscription/revocation endpoint.
- Bind every subscription to the logged-in PrestaShop customer and shop; never accept a client-supplied customer ID.
- Require a purpose-specific PrestaShop token, same-origin request, explicit application consent, browser permission, and valid subscription fields.
- Encrypt endpoint and key material at rest, index ownership with an HMAC digest, and never return or log raw endpoint/key values.
- Require a stable `ORDENOWA_PUSH_STORAGE_KEY` for encrypted storage. Missing or malformed key material disables new subscriptions. CI generates a throwaway per-run value; production custody remains an external requirement.
- Support localized JA/EN/KO UI and configurable consent notice fields. Notice fields start empty; production subscription stays unavailable until seller-approved text and server notification configuration exist.
- Handle synthetic push events with bounded, allowlisted event types, generic localized text, and fixed same-origin account destinations. Reject arbitrary payload text and destinations.
- Add isolated tests that use synthetic subscription data and a fake sender/event harness with no outbound network. Keep real sender credentials and customer delivery out of CI.
- Keep existing private-route cache protections unchanged.

## Non-goals and anti-goals

- No real customer notifications, production VAPID key generation/storage, provider registration, live sending, or production deployment in this change.
- No tracking, order number, item, address, payment, customer name, customer support contents, or free-form delivery content in notification payloads.
- No broad service-worker cache changes, bypass of consent, JavaScript-forced authorization, or reliance on browser permission as application consent.
- No claim that support notifications are connected until the customer-support workflow has a producer.
- No claim of physical iOS/Android delivery verification from desktop Chromium or a synthetic push event.

## Approaches considered

1. **Extend `kuraneabusinessprofile`.** This reuses an installed module but mixes seller/brand versioning with private customer subscription state and delivery lifecycle. Rejected because those data and access boundaries are different.
2. **Put all behavior in the theme and service worker.** This can render controls but cannot enforce subscription ownership, persist revocation, or protect endpoint capabilities. Rejected.
3. **Add a dedicated `kuraneapush` module and narrow service-worker handlers.** This isolates persistence, customer authorization, admin controls, and delivery readiness while reusing the existing worker and account hook. Selected because it preserves the current cache boundary and gives synthetic QA a clear seam.

## Proposed behavior

The module renders controls only for an authenticated customer. The interface presents its localized static label and any configured consent notice. It requests browser notification permission only after the customer explicitly chooses to enable notifications and accepts the app-level notice. The module endpoint accepts only same-origin POSTs carrying the purpose token `Tools::getToken('kuraneapush', $context)` (the pinned PrestaShop 9.2 API accepts a string page value and hashes it with the authenticated customer's identity). It uses authenticated context customer/shop IDs and treats subscribe/revoke as idempotent. Readiness and copy gates apply to new subscription only; an authenticated customer may always revoke all of their shop subscriptions even if copy, key configuration, or browser permission later becomes unavailable. The browser also unsubscribes the current device. If the server save fails after a browser subscription is created, the browser subscription is revoked to avoid a local/server mismatch.

Subscriptions are stored per customer and shop. Endpoint, `p256dh`, and `auth` values are encrypted together with authenticated encryption using a key read from `ORDENOWA_PUSH_STORAGE_KEY`; a separately derived keyed digest supports uniqueness and ownership lookup. The configured master value must decode to exactly 32 random bytes. AEAD associated data binds shop ID, customer ID, and endpoint digest. A shop-wide unique index prevents an endpoint from being transferred between customers; reads/deletes also require the current customer ID. Missing or malformed key configuration or invalid cryptographic/storage state fails closed. Customer deletion removes that customer's subscription records. Routine module disable/uninstall preserves rows but disables use; retention and secure deletion policy still require seller approval.

The service worker accepts only a small event enum (`order`, `delivery`, `support`) and locale enum (`ja`, `en`, `ko`). It chooses message text from source-controlled localized constants, drops oversized/malformed payloads, and uses a fixed account/order-history route on the worker's own origin. The click handler never trusts a URL from a push payload. Existing private navigation and no-cache rules remain intact.

The admin control screen is Korean-first and exposes delivery readiness, order/delivery/support event toggles, and JA/EN/KO consent notice fields. Notice fields are blank by default; empty copy disables new consent/subscription. The screen reports that no real sender is configured without displaying keys. CI may seed clearly synthetic copy only within the exact run-scoped environment. CI must not call `PushManager.subscribe()` against a real browser push service; positive persistence tests submit an isolated synthetic subscription at the API boundary, and service-worker push/click events run inside the local Node harness.

## API and runtime contract

- The account hook renders `data-ordenowa-push` with `data-status-url`, `data-subscription-url`, a purpose token, locale, and only boolean readiness. It renders one localized consent notice and no customer ID or subscription secret.
- The module route is `index.php?fc=module&module=kuraneapush&controller=subscription`. `GET ?action=status` returns only `{active, can_subscribe}`. JSON `POST {action:subscribe, token, consent, locale, subscription:{endpoint,keys:{p256dh,auth}}}` saves a subscription. JSON `POST {action:revoke, token}` removes all subscriptions for the authenticated customer/shop, so revoke still works when encryption configuration is unavailable. All responses use `Cache-Control: private, no-store` and contain no endpoint/key values.
- The subscription payload is capped at 8 KiB; endpoint is HTTPS with no userinfo/fragment, bounded to 2 KiB; encoded key strings are bounded and validated before storage. Exact RFC key length checks are applied to decoded base64url values. A same-shop digest owned by a different customer is rejected, never reassigned.
- The worker event payload is capped at 2 KiB and accepts only `{event: order|delivery|support, locale: ja|en|ko}`. The notification text comes from fixed source-controlled strings. Click destination is exactly the worker's same-origin `/index.php?controller=my-account` route.
- `ORDENOWA_PUSH_TEST_MODE=1` enables synthetic subscription readiness only when `CI=true`, `GITHUB_ACTIONS=true`, `KURANEA_ISOLATED_CI=1`, and `KURANEA_CI_PROJECT_NAME` exactly matches the current GitHub run/attempt project. It has no sender and cannot perform network I/O. Production readiness remains false until a separate reviewed provider transport and secret binding exist.
- The isolated browser phase briefly uses the existing run-scoped CI gate to register two disposable customer accounts. It does not visit checkout or create orders; the workflow trap force-recreates the base service configuration afterward.

## Verification

- PHP domain/contract tests cover invalid values, customer/shop ownership, idempotent subscribe/revoke, token/origin checks, encrypted storage, blank consent copy, and fail-closed delivery configuration.
- Node service-worker tests cover accepted synthetic event types/locales, generic localized copy, payload size/type rejection, safe fixed destinations, and unchanged private-route/no-cache behavior.
- Isolated browser QA verifies account control visibility/locales and consent gating, while synthetic API tests verify saved/revoked subscription readback for two customers. It must not contact a push provider or an arbitrary endpoint.
- Focused CI and the existing full isolated suite verify module installation, lifecycle, and aggregate outcomes. Desktop emulation is not a physical device result.

## Open release boundary

This design delivers the consent/subscription and synthetic service-worker path. Provider-backed Web Push transmission remains a distinct release task until a maintained sender dependency and deployment secret custody are reviewed and implemented. Production consent copy, privacy retention/erasure policy, HTTPS, VAPID secret custody, sender ownership, support-event source, and physical-device checks remain release inputs or separate work. The matrix must report this foundation as partial, never as production push completion.
