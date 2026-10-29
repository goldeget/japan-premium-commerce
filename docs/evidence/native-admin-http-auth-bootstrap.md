# Native admin authentication bootstrap handoff

## Scope

This isolated stage fixes the MBO authenticated error-route fixture's request lifecycle. It does not change the production storefront, core, or vendor packages, and it has not been merged into the active candidate or run through remote CI yet.

The previous fixture logged in and followed redirects through repeated in-process `KernelBrowser` requests. The latest failed native run had already completed the login GET and POST, then failed on the POST redirect with `ShopConstraint::shop(0)` in `Adapter\Configuration::buildShopConstraintFromContext`, called while `ThemeRepository` loaded the theme through `Shop::setTheme`. The safe fix is to let Apache perform the actual admin login in its own HTTP request lifecycle, then use a newly booted in-process `AdminKernel` for one authenticated target GET. The fixture never assigns a shop ID, employee identity, or authentication context itself.

## Request and cookie boundaries

`native_admin_http_login.php` authenticates only against the fixed `http://localhost:18081` admin origin. cURL maps that origin to `127.0.0.1:80` with `CURLOPT_CONNECT_TO`, disables proxies and automatic redirects, and permits HTTP only. Redirects are handled manually, capped at six, and revalidated against the installed `/admin-kuranea` path before another request. The login form is parsed from the real page, including its hidden token fields; the isolated CI credentials are posted to the real local front controller.

cURL's cookie engine is memory-only. Cookie records are accepted only for `localhost` and the installed admin path. They are never written to a file or included in the output. PHP 8.4 local loopback verification confirmed that `$_COOKIE` decodes both `%2B` and a literal `+` to `+`; the helper therefore uses `rawurldecode`, matching the pinned Symfony BrowserKit `Cookie` implementation's encoded-value path ([pinned source](https://github.com/symfony/browser-kit/blob/4f631476bb549d882a173c47bf693f3ef84c722d/Cookie.php)). The semantic regression covers both forms.

After successful real HTTP login and a safe dashboard response, the helper installs the scoped cookies in BrowserKit and sends exactly one target GET through the production `AdminKernel`. The existing route/controller, injected MBO failure provider, native layout, Korean text, 503 status, response header, and native session-CSRF assertions remain in place. The sanitized result records the fixed login transport name, bounded loopback HTTP request count, cookie count, and exactly one KernelBrowser target request. `browser_socket_requests: 0` refers only to the in-process KernelBrowser target dispatch; it does not describe the preceding loopback cURL login. Bootstrap network side effects remain explicitly uninstrumented.

## Focused checks run locally

- PHP syntax checks passed for the HTTP-login helper, its semantic test, its cURL method test, and the MBO native fixture.
- The helper semantic test passed, including same-origin redirect limits, cookie scope, `%2B`/literal-plus handling, and ordered GET/POST options.
- The cURL method test passed against an ephemeral `127.0.0.1` HTTP server using the bundled PHP 8.4 cURL extension. The server observed exactly one bodyless GET and one POST carrying the synthetic `mode=probe` form.
- MBO fixture contract tests passed (7 tests); sanitized outcome tests passed (12 tests).
- The full isolated container/PrestaShop integration run is still required. Do not treat this local transport test as proof that the authenticated native MBO page has passed.

## Integration note

`native_mbo_error_authenticated.php` emits only the safe `mbo_error_render` fields; the raw login body, credentials, cookies, and target HTML are not included. When integrating, the root-owned private snapshot helper may be called only after all strict MBO response, header, language, source-absence, provider-call, and CSRF assertions succeed. Keep the snapshot in the existing private, non-webroot handoff and use the established sanitizer before visual review.
