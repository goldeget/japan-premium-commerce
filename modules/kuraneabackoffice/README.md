# ORDENOWA Back Office support

PrestaShop 9.2 module that sets every `admin_` Back Office route to Korean, reads the published ORDENOWA brand from the business profile module, and provides source controlled Korean XLIFF overlays for missing Back Office strings. The approved ORDENOWA admin logo is served from the current published profile, with the bundled official logo as the initial display. Legacy KURANEA source images remain preserved separately.

## Install

New empty Compose installations bundle and install this module during the first project bootstrap. For an already-installed shop, deploy the directory as `modules/kuraneabackoffice` and install it from **Modules > Module Manager**. PrestaShop rebuilds its Symfony cache while loading the module's XLIFF translations so it can discover `config/services.yml` and the subscriber. This module does not change PrestaShop core or the `psgdpr` module.

## Translation behavior

- On every `admin_` route, the request-scoped subscriber selects the active `ko-KR` language in PrestaShop's lazy language context. The storefront locale remains independent.
- The subscriber runs after PrestaShop's default user locale selection. It loads the Korean catalogue with `TranslatorLanguageLoader`, then registers the module-owned overlays through Symfony's XLIFF resource API.
- `AdminActions.ko-KR.xlf` supplies the missing `Back to` value for the normalized `Admin.Actions` domain.
- `messages.ko-KR.xlf` supplies initial psgdpr admin wording that the legacy module translator falls back to the Symfony `messages` domain for. Add further audited source strings to this file as coverage work continues.

No translation rows are written to the database, and no files are copied into `modules/psgdpr`.

## Synthetic checks

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/admin_locale -v
```

These checks validate module wiring, the all-route Korean locale contract, overlay XLIFF entries, and the official logo asset. They do not replace authenticated browser QA of the login page or psgdpr screens. Current overlay coverage is partial; it does not establish 100% Korean Back Office coverage.
