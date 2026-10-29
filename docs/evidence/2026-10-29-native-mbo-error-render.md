# Native MBO error render and installed-module readback (staged)

## Scope

- This bundle is isolated under work/admin-native-error-prep; it does not alter the current candidate, shared checkout, core, or vendor modules.
- The native PHP probe is strictly gated to the run-scoped disposable procurement CI environment. The probe code reads installed-module parameters, module config files, module source, and the translation catalogue; it performs no explicit application mutations (`script_app_mutations=false`). The PHP kernel and configuration bootstrap run before the probe and their database/network side effects are not instrumented (`bootstrap_database_side_effects_instrumented=false`, `bootstrap_network_side_effects_instrumented=false`), so this does not claim zero bootstrap DB/network activity.
- It invokes the installed ps_mbo ThemeCatalogController directly with an in-memory LinksProvider subclass and a fake ExternalContentProviderInterface. The fake is invoked once and throws ServiceUnavailableHttpException without issuing HTTP (`injected_provider_invocations=1`, `injected_provider_http_calls=0`). The probe verifies the actual controller response and native Twig rendering of the installed error template.
- This is a native container/controller/template render, not a logged-in HTTP request or browser route acceptance. The probe does not create or modify employee, customer, module, or other database rows. The direct fixture has no authenticated employee/session.
- The installed error template extends `@PrestaShop/Admin/layout.html.twig` on a regular request. The official 9.2.0 layout includes `EmployeeDropdown`, `NavBar`, and a session flashbag. The dropdown dereferences the employee context, while the nav bar reads the legacy context employee's default tab. To avoid inventing an authenticated identity or mutating employee state, the probe sets the request's supported `liteDisplaying=1` flag. The real layout template then selects its native light-layout branch; neither the MBO error template nor its layout is stubbed. The assertion covers the actual translated error content, response status, and exception-header pass-through, but not the full authenticated admin chrome/ACL or browser dispatch.

## Verified upstream contracts

- PrestaShop base image is pinned to PrestaShop 9.2.0 in docker/Dockerfile.
- The official [PrestaShop 9.2.0 AdminKernel](https://github.com/PrestaShop/PrestaShop/blob/9.2.0/app/AdminKernel.php), [AppKernel](https://github.com/PrestaShop/PrestaShop/blob/9.2.0/app/AppKernel.php), and [module repository](https://github.com/PrestaShop/PrestaShop/blob/9.2.0/src/Adapter/Module/Repository/ModuleRepository.php) confirm the CLI kernel bootstrap and the read-only installed/active module-name parameters used by the probe.
- MBO upstream snapshot is PrestaShopCorp/ps_mbo commit 7f694df47340d1399dd4ad8cb395bc4fc91d2ab1 (config.xml reports 5.3.3). The controller route is admin_mbo_catalog_theme and legacy controller is AdminPsMboTheme.
- That controller accepts LinksProvider and ExternalContentProviderInterface, catches ServiceUnavailableHttpException, renders @Modules/ps_mbo/views/templates/admin/error.html.twig, and returns the exception status.
- Its catch branch also forwards exception headers with `$response->headers->add($exception->getHeaders())`; the test injects a fixed header and asserts it survives on the native response.
- The MBO error template uses the exact source string in alt text and visible paragraph, both under Modules.Mbo.Errors.
- In PrestaShop 9.2.0, [the standard admin layout](https://github.com/PrestaShop/PrestaShop/blob/9.2.0/src/PrestaShopBundle/Resources/views/Admin/Layout/default_layout.html.twig) renders `EmployeeDropdown` and `NavBar`; [the employee dropdown component template](https://github.com/PrestaShop/PrestaShop/blob/9.2.0/src/PrestaShopBundle/Resources/views/Admin/Component/Layout/employee_dropdown.html.twig) reads employee fields, and [the nav-bar component](https://github.com/PrestaShop/PrestaShop/blob/9.2.0/src/PrestaShopBundle/Twig/Component/NavBar.php) reads the legacy employee's `default_tab`. The error template's regular parent [supports the native light-display branch](https://github.com/PrestaShop/PrestaShop/blob/9.2.0/src/PrestaShopBundle/Resources/views/Admin/layout.html.twig), selected by the probe's request query flag.
- Facebook inventory source is PrestaShopCorp/ps_facebook commit f4b63c967f4d898cecabd8e234a4c5df5bffe21a (config.xml reports 1.38.19). The probe reads the actual installed config.xml version and hashes, it does not infer the installed version from upstream.
- The exact installed versions remain runtime evidence: the output JSON captures versions/config hashes for ps_mbo and ps_facebook from the disposable shop. Missing/uninstalled modules, invalid version metadata, absent MBO controller/template, API signature mismatch, or wrong rendered output fails the probe and emits a bounded failure stage.

## Integration point

Stage the invocation in tests/procurement/ci_acceptance.sh inside native_boundaries(), immediately after the existing production cache warmup:

    compose exec -T -u www-data prestashop php /var/www/html/tests/admin_locale/native_mbo_error_render.php >"$QA_ARTIFACT_DIR/native-mbo-error-render.json" || return "$?"

The workflow copies all tests/admin_locale files into the disposable container and native_boundaries runs the production cache warmup first. The host acceptance script validates `CI=true`, `KURANEA_ISOLATED_CI=1`, numeric `GITHUB_RUN_ID`/`GITHUB_RUN_ATTEMPT`, the run-scoped compose project name, and `PS_DOMAIN=localhost:18081`; the disposable compose service must pass the same CI/run identifiers, `GITHUB_ACTIONS=true`, `KURANEA_CI_PROJECT_NAME`, `KURANEA_ISOLATED_CI=1`, and `PS_DOMAIN=localhost:18081` to satisfy the probe's additional container-side guard. The JSON contains module names, install/active booleans, version strings, SHA-256 values, status/header/translation assertions, explicit probe-level mutation/network scope, and bounded failure diagnostics. Exception messages, traces, absolute paths, tokens, and identity data are never emitted. Twig failures may expose only a template name from fixed PrestaShop/ps_mbo namespaces and a bounded template line number.

## Local validation limits

Run the contract test with:

    python -B work/admin-native-error-prep/tests/admin_locale/test_native_mbo_error_render_contract.py

This workspace has no PHP executable and the native Docker engine was unavailable. The contract test checks the staged wiring, fixed diagnostic allowlist, scope claims, and fail-closed properties; runtime PHP/Twig rendering must be verified by the next isolated native_boundaries CI run. The staged test makes no browser/authentication or full-layout acceptance claim.



The integrated probe attaches a memory-only Symfony request session for native flashbag access. It creates no login identity and retains authenticated_http_dispatch=false.
