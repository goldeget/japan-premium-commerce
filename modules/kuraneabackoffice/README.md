# ORDENOWA Back Office support

PrestaShop 9.2 module that sets every `admin_` Back Office route to Korean, reads the published ORDENOWA brand from the business profile module, and provides source controlled Korean XLIFF overlays for missing Back Office strings. The approved ORDENOWA admin logo is served from the current published profile, with the bundled official logo as the initial display. Legacy KURANEA source images remain preserved separately.

## Install

New empty Compose installations bundle and install this module during the first project bootstrap. For an already-installed shop, deploy the directory as `modules/kuraneabackoffice` and install it from **Modules > Module Manager**. PrestaShop rebuilds its Symfony cache while loading the module's XLIFF translations so it can discover `config/services.yml` and the subscriber. This module does not change PrestaShop core or the `psgdpr` module.

## Translation behavior

- On every `admin_` route and native router-identified BO module route, the request-scoped subscriber selects active `ko-KR` in PrestaShop's lazy language context. The additional module classification uses only router attributes `_route`/`_legacy_controller`, never query/body controller names, and grants no authentication or ACL. Storefront/API routes without trusted BO metadata remain independent.
- The subscriber runs after PrestaShop's default user locale selection. It loads the Korean catalogue with `TranslatorLanguageLoader`, then registers the module-owned overlays through Symfony's XLIFF resource API.
- `AdminActions.ko-KR.xlf` supplies the missing `Back to` value for the normalized `Admin.Actions` domain.
- `messages.ko-KR.xlf` supplies initial psgdpr admin wording that the legacy module translator falls back to the Symfony `messages` domain for. Add further audited source strings to this file as coverage work continues.

No translation catalogue overrides are written to the native translation table, and no files are copied into `modules/psgdpr`.

The native translation-copy form passes raw `From`/`To` labels to a theme that renders labels without translating them. A module-owned `CopyLanguageType` extension replaces only those two exact language-field labels in Korean requests. Custom labels, other locales, locale/theme choices, values and CSRF remain unchanged; the global date-context translations of `From`/`To` are preserved. `tests/admin_locale/copy_language_labels.php` uses the installed native Symfony form implementation to verify this boundary without bootstrapping the shop database.

Upgrades `1.0.7`/`1.0.8`, first install, and the idempotent project bootstrap call `installKoreanAdminTabLabels()` repair thirteen explicitly identified native tab fallbacks. The original Community, Wall of Fame, Extra Properties and Security parent/page mappings are retained; the expanded set adds Themes Catalog, Employee/Customer Sessions, Care Center, Pages Configuration, Advanced Customization, Welcome and the known incorrect Korean email default `Epos`, with exact native controller/module ownership. Native navigation prints persisted `tab_lang.name`, so loading XLIFF alone cannot repair these installer fallbacks. Only an exact recorded fallback or empty Korean name is replaced; a missing Korean row is filled. Custom names, other locales, tab IDs/wording, ACL and business data remain intact. This never runs from administrator GET requests. Module-category labels use the native `Admin.Modules.Feature` domain.

`tests/admin_locale/korean_tab_labels.php` exercises the repair against dedicated test-DB tables, including repeated calls, custom/case-sensitive names, other languages, wrong module owners, missing rows and unchanged ACL/metadata. Actual browser inventory remains a separate acceptance step.

## Synthetic checks

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/admin_locale -v
```

These checks validate module wiring, the all-route Korean locale contract, overlay XLIFF entries, and the official logo asset. They do not replace authenticated browser QA of the login page or psgdpr screens. Current overlay coverage is partial; it does not establish 100% Korean Back Office coverage.

## Native permission changes

`installNativeAclAudit()` and upgrade `1.0.6` add `kuraneabackoffice_native_acl_audit` and the official `actionAdminUpdateAccessBefore` / `actionAdminUpdateModuleAccessBefore` hooks. Inspection of the pinned PrestaShop 9.2 `AdminController::postProcess`, `AdminAccessController` and `Access` confirms these hooks precede native permission writes; the two AJAX methods end with `die()`, so their generic After hooks do not execute. Native permission-grid requests use GET with the native session token.

The observer verifies the native controller, authenticated employee, current native EDIT permission, native token and existing target profile. It requires InnoDB for the native access table and audit table, then uses the same primary database connection for the native permission write and append-only audit insert. A target-profile lock and native permission-range lock keep the baseline stable. The AJAX response is buffered until shutdown: only an exact native `ok`, successful persisted readback, audit insert and commit release `ok`. Partial failure, fatal shutdown or audit failure rolls back permissions and audit together and emits only `error`. Preparation failure stops the native action through PrestaShop's `ModuleErrorInterface`; attempted or unchanged writes create no changed event.

The audit stores actor/profile/role identifiers, actual previous and new grants, correlation and UTC time. Profile permissions are native global settings (`id_shop=0`); `context_shop_id` records the selected shop without implying per-shop ACL scope. It stores no request body, session token or credential. The existing read-only administrator audit page displays these rows only with both its native READ permission and native AdminAccess READ. Employee-profile assignment auditing remains separate. Uninstall retains audit data; whole-database backups must include the new table.

## Owned admin form tokens and responses

`AdminPostTokenValidator` is a public native Symfony service using `CsrfTokenManagerInterface` and the authenticated native security user. It validates the submitted POST value against the stored native CSRF seed, including valid tokens masked in a previous request. A valid URL token cannot replace a forged body token. Missing services, user or nonempty scalar body token fail closed. No new token is generated during validation.

`AdminResponseSubscriber` applies only to the procurement module's five admin controllers and Push settings on native admin routes. It carries explicit 403/404/409/422/503 status metadata through PrestaShop 9's legacy-to-Symfony Response wrapper and applies private/no-store/noindex headers, including invalid-token responses. Other native controllers and subrequests retain their behavior. Recompile the native Symfony admin container after deploying `config/services.yml` changes.

Focused checks are `tests/admin_audit/native_acl_atomic.php`, `admin_post_token.php` and `admin_response.php`; `tests/procurement/acl_browser.py` additionally exercises the actual official native hook against a dedicated employee-free profile in the exact disposable CI project. It grants one known native READ role and revokes it through native AJAX, then checks fresh audit readback and unchanged unrelated profiles. These tests do not authorize changes to an existing shop database.
# Native Twig cache warmup

The module decorates `twig.template_iterator` with Symfony's documented `*.twig`
filename boundary for eager compilation. PrestaShop registers the entire modules
directory as the `Modules` Twig namespace; without this boundary its optional
warmer also compiles PHP libraries and PHAR archives as Twig templates. Runtime
Twig loader paths and rendering remain unchanged. Nonstandard template names can
still render lazily; real `.twig` templates continue to warm, and enumeration
errors remain visible.

Focused verification: `php tests/admin_locale/twig_warmup_templates.php`.
