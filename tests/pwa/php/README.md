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
`en`, `ko`), and `subscription` (`endpoint`, `keys.p256dh`, `keys.auth`).
Revoke accepts only `action` and `token`, and does not require configuration,
copy, readiness, or permission. It removes all current shop/customer devices.
No client customer or shop identifier is accepted.

Storage needs base64-encoded 32-byte `ORDENOWA_PUSH_STORAGE_KEY`; there is no
fallback to a platform secret. Changing/removing the key disables new saves;
revocation remains possible. Production sender readiness is always unavailable.
The sole positive readiness path requires all exact isolated GitHub run flags
from the approved design and synthetic seller copy. No network provider path
exists in this module.

Config keys: `ORDENOWA_PUSH_EVENT_ORDER`, `_DELIVERY`, `_SUPPORT` (initially 0),
and `ORDENOWA_PUSH_CONSENT_NOTICE_JA`, `_EN`, `_KO` (initially empty). Reinstall
preserves existing values and rows. Customer deletion erases owned rows across
all shops. Module uninstall only removes its admin tab and preserves data.

The standalone PHP contracts cover pure validation, crypto, request guards,
readiness, and API operations with an in-memory store. Actual PrestaShop ACL,
DB unique-key concurrency, lifecycle hooks and browser/runtime integration need
the isolated workflow; source checks cannot establish those behaviors.
