# Push backend contracts

Run PHP behavioral contracts without PrestaShop or network access:

```sh
php tests/pwa/php/run.php
find modules/kuraneapush -name '*.php' -print0 | xargs -0 -n1 php -l
```

Local source checks (do not replace PHP/runtime validation):

```sh
python3 -m unittest discover -s tests/pwa/php -p 'test_*.py'
```

Module API: `index.php?fc=module&module=kuraneapush&controller=subscription`.
`GET action=status` returns exactly `active` and `can_subscribe` booleans.
Mutations require JSON, POST, exact configured shop Origin, an authenticated
non-guest customer, and `Tools::getToken('kuraneapush', $context)`. POST bodies
carry `action` (`subscribe` or `revoke`); query action is also accepted for
compatibility. Subscribe fields are `token`, `consent: true`, `locale` (`ja`,
`en`, `ko`), `notice_version` (the SHA-256 version of the exact localized
notice displayed), and `subscription` (`endpoint`, `keys.p256dh`, `keys.auth`).
Revoke accepts only `action` and `token`, and does not require configuration,
copy, readiness, or permission. It removes all current shop/customer devices.
No client customer or shop identifier is accepted.

Storage needs base64-encoded 32-byte `ORDENOWA_PUSH_STORAGE_KEY`; there is no
fallback to a platform secret. Changing/removing the key disables new saves;
revocation remains possible. Production sender readiness is always unavailable.
The isolated synthetic delivery provider can be constructed only when every
exact isolated GitHub run flag is present. It never opens a network connection
and returns deterministic delivered, permanently-gone, or retryable-failure
outcomes for behavioral tests. The live provider remains disabled until an
approved provider, delivery policy, and operational secret handling are
supplied.

An explicit subscribe records the accepted notice version, locale and server
UTC timestamp per owner-scoped subscription. A notice changed after page load
is rejected. Existing rows receive nullable fields on upgrade and are never
backfilled as if the customer had accepted a notice. Revoke continues to erase
the owner's active subscription rows; no separate retention policy or historic
consent archive is implied.

Config keys: `ORDENOWA_PUSH_EVENT_ORDER`, `_DELIVERY`, `_SUPPORT` (initially 0),
and `ORDENOWA_PUSH_CONSENT_NOTICE_JA`, `_EN`, `_KO` (initially empty). Reinstall
preserves existing values and rows. Customer deletion erases owned rows across
all shops. Module uninstall only removes its admin tab and preserves data.

The standalone PHP contracts cover pure validation, crypto, request guards,
readiness, API operations, owner-scoped consent-gated delivery, synthetic
provider outcomes, invalid-row isolation, and the SQL repository contract.
Actual PrestaShop ACL, DB unique-key concurrency, lifecycle hooks and
browser/runtime integration need the isolated workflow; source checks cannot
establish those behaviors.
