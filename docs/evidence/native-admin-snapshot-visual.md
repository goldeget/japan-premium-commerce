# Sanitized native admin snapshot renderer

This staging tool renders only the already-captured HTML response produced by the authenticated KernelBrowser MBO/Facebook fixture. It does **not** open an admin route in Chromium and does not call the live Facebook provider. Report its scope as `chromium_render_of_native_kernelbrowser_snapshot`, never as native HTTP browser proof.

It builds a reduced document from the original native DOM: the actual `.header-toolbar` ancestry down to its `h1.title`, plus the real error card ancestry under `#main-div .content-div`. It retains no sibling toolbar actions or sibling row content; card text must equal the expected Korean error exactly. Heading/title, element IDs and classes are bounded and checked for identity-like values. Forms, controls, scripts, frames, employee-dropdown subtree, all links, data attributes, and unrelated page content are excluded. CSS and image references must be same-origin, query-free static assets under the explicit PrestaShop theme/admin and MBO image roots. Chromium gets a loopback preview document with a restrictive CSP; the preview server proxies only bounded `GET` requests to those static paths on `localhost:18081`, without cookies or authorization. Both rewritten `/asset/...` URLs and root-relative paths emitted by static CSS pass through the same path/MIME allowlist; admin routes such as `index.php` are refused. Any blocked/non-allowlisted request, unexpected DOM state, failed image, overflow, or crop outside the viewport fails the run and removes partial screenshots.

The only successful outputs are two cropped PNGs (390 px and 1440 px viewport widths, light mode) and a fixed-field JSON summary. No raw HTML, employee identity, CSRF token, route URL, asset URL, browser log, or full DOM is written to the artifact directory. The one-shot HTML input is deleted as soon as it is read. The renderer uses a fresh private Chrome profile and deletes it at shutdown.

## CI handoff

The PHP helper should write each response only after its native KernelBrowser and authentication/CSRF assertions pass. Write it to a private directory such as `/tmp/owned/kuranea-admin-test-deps/private-snapshots/` inside the test container, with directory mode `0700`, owner `www-data`, and one-shot HTML file mode `0600`. Before tearing down the disposable shop/dependency container, copy the file to a host-side run-private directory, for example `$RUNNER_TEMP/private-admin-visual/`; create that directory with mode `0700` and never place raw HTML under the artifact path. The renderer requires `--private-html` to be a direct child of `--private-dir`, and both that directory and the artifact directory must be under `--runner-temp`.

Create the artifact directory under the runner temp path, then run once per kind while the disposable static asset origin at `localhost:18081` is available:

```sh
python3 tests/admin_locale/snapshot_visual.py \
  --kind mbo \
  --private-html "$RUNNER_TEMP/private-admin-visual/mbo.html" \
  --private-dir "$RUNNER_TEMP/private-admin-visual" \
  --artifact-dir "$RUNNER_TEMP/qa-artifacts" \
  --runner-temp "$RUNNER_TEMP" \
  --expected-sha256 "$NATIVE_RESPONSE_SHA256"
```

Repeat with `--kind facebook` and `facebook.html`. The input is consumed and deleted, so retain only sanitized PNG/JSON outputs. A shell cleanup trap must remove the private directory even when copying or rendering fails. Upload only `*-native-kernelbrowser-snapshot*.png` and `*-native-kernelbrowser-snapshot.json`; do not upload logs or private HTML. If a stylesheet, font, or image needs a path outside the current allowlist or a query parameter, stop and review the exact static dependency before changing the allowlist.

Run the focused suite with:

```sh
python3 tests/admin_locale/test_snapshot_visual.py
```

The focused tests exercise sanitization, the Selenium async callback argument shape, same-origin static-only proxy behavior, CSP, request rejection, asset limits, and partial-output cleanup. This workspace has no installed Selenium package or `chromedriver`, so it cannot itself produce or visually inspect a PNG. A target CI run with its pinned Chromium/Selenium must produce the artifacts, and a separate independent reviewer must inspect both screenshots before visual acceptance is claimed.

Current acceptance invokes this automatically through `tests/admin_locale/ci_authenticated_mbo.sh`. The hash is read from the successful native MBO/Facebook safe outcome and checked against the exact private HTML bytes before Chromium starts; it is not a manually supplied approval. PNG names contain `-redacted-` and match the existing safe-artifact upload pattern. The retained toolbar/card crop is a reduced native DOM render, not a screenshot of authenticated browser navigation or the complete admin chrome.
