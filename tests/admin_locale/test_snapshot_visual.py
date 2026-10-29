from __future__ import annotations

import http.client
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from unittest.mock import patch
from urllib.request import urlopen


sys.path.insert(0, str(Path(__file__).resolve().parent))
import snapshot_visual as visual


MBO_MESSAGE = "Addons에 연결하는 데 문제가 있는 것 같습니다. 페이지를 새로고침하거나 방화벽 설정을 확인해 주세요."
FB_TITLE = "Facebook 계정 연결을 일시적으로 사용할 수 없습니다"
FB_MESSAGE = "Facebook 서비스에 연결하는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."


def native_snapshot(kind: str = "mbo", *, lang: str = "ko-KR", message: str | None = None, extras: str = "") -> bytes:
    styles = (
        '<link rel="stylesheet" href="/admin-kuranea/themes/new-theme/public/theme.css">'
        '<link rel="stylesheet" href="/js/jquery/plugins/chosen/jquery.chosen.css">'
        '<script src="https://evil.invalid/tracker.js"></script>'
    )
    if kind == "mbo":
        marker = message or MBO_MESSAGE
        error = (
            '<div class="row"><div class="col"><div class="card"><div class="card-body text-center">'
            '<img class="img-responsive" src="../modules/ps_mbo/views/img/error.svg" '
            f'alt="{MBO_MESSAGE}"><p class="mt-3 error-header">{marker}</p>'
            '</div></div></div></div>'
        )
    else:
        title, body = (message.split("|", 1) if message and "|" in message else (FB_TITLE, FB_MESSAGE))
        error = (
            '<div class="row"><div class="col"><div class="card">'
            '<div id="ordenowa-facebook-transport-error" class="card-body text-center" role="alert" aria-live="polite">'
            f'<h1 class="h3">{title}</h1><p class="mt-3">{body}</p>'
            '</div></div></div></div>'
        )
    return (
        '<!doctype html><html lang="' + lang + '"><head><meta charset="utf-8">' + styles + '</head>'
        '<body class="ps-bo-rebrand" data-token="csrf-private-value" data-base-url="/admin-kuranea?token=private">'
        '<header id="header"><div id="header-employee-container"><span class="employee_profile">'
        'procurement-admin-999@example.invalid</span></div></header>'
        '<nav id="nav-sidebar"><a href="/admin-kuranea/logout?token=private">Logout</a></nav>'
        '<div class="header-toolbar"><div class="container-fluid"><div class="title-row">'
        '<h1 class="title">테마 카탈로그</h1><a href="/private?token=private" title="private URL">Help</a>'
        '</div></div></div>'
        '<div id="main-div"><div class="content-div"><div id="content-message-box"></div>'
        + extras + error + '</div></div>'
        '<form action="https://evil.invalid/post" method="post"><input type="hidden" name="token" value="csrf-private-value">'
        '<input type="password" value="private-password"></form>'
        '<footer>unrelated footer text</footer></body></html>'
    ).encode("utf-8")


class SnapshotSanitizerTests(unittest.TestCase):
    def test_only_pinned_prestashop_asset_version_is_accepted_and_removed(self):
        source = native_snapshot('mbo').replace(b'theme.css"', b'theme.css?9.2.0"')
        result = visual.sanitize_snapshot(source, 'mbo')
        self.assertNotIn('?9.2.0', result.html)
        self.assertIn('/admin-kuranea/themes/new-theme/public/theme.css', result.asset_paths)
        for query in ('9.2.1', 'token=private', '9.2.0&token=private', '9.2.0#private'):
            with self.subTest(query=query):
                with self.assertRaises(visual.SnapshotError):
                    visual.normalize_asset_url('/admin-kuranea/themes/new-theme/public/theme.css?' + query)

    def test_mbo_keeps_native_toolbar_and_korean_card_but_removes_private_fields(self):
        result = visual.sanitize_snapshot(native_snapshot("mbo"), "mbo")
        text = result.html
        for private in (
            "csrf-private-value", "procurement-admin-999@example.invalid", "private-password",
            "private URL", "evil.invalid", "Logout", "unrelated footer text", "data-token",
            "data-base-url", "<script", "<form", "<input", "employee_profile", "onerror=",
        ):
            self.assertNotIn(private, text)
        self.assertIn('class="header-toolbar"', text)
        self.assertIn('<h1 class="title">테마 카탈로그</h1>', text)
        self.assertNotIn("Help", text)
        self.assertIn(f'<p class="mt-3 error-header">{MBO_MESSAGE}</p>', text)
        self.assertIn('src="/asset/modules/ps_mbo/views/img/error.svg"', text)
        self.assertNotIn("alt=", text)
        self.assertIn("/admin-kuranea/themes/new-theme/public/theme.css", result.asset_paths)
        self.assertIn("/js/jquery/plugins/chosen/jquery.chosen.css", result.asset_paths)
        self.assertIn("/modules/ps_mbo/views/img/error.svg", result.asset_paths)
        self.assertEqual("mbo", result.kind)

    def test_facebook_keeps_only_the_exact_native_error_fragment(self):
        result = visual.sanitize_snapshot(native_snapshot("facebook"), "facebook")
        self.assertIn(f"<h1 class=\"h3\">{FB_TITLE}</h1>", result.html)
        self.assertIn(f"<p class=\"mt-3\">{FB_MESSAGE}</p>", result.html)
        self.assertNotIn("127.0.0.1", result.html)
        self.assertNotIn("cURL error", result.html)
        self.assertNotIn("billing-api.distribution.prestashop.net", result.html)
        self.assertNotIn("employee_profile", result.html)

    def test_error_copy_is_preserved_without_body_wide_replacement(self):
        result = visual.sanitize_snapshot(native_snapshot("mbo"), "mbo")
        self.assertIn("테마 카탈로그", result.html)
        self.assertIn(MBO_MESSAGE, result.html)
        self.assertNotIn("[synthetic acceptance]", result.html)

    def test_wrong_language_or_error_text_fails_closed(self):
        with self.assertRaisesRegex(visual.SnapshotError, "korean_document_language_missing"):
            visual.sanitize_snapshot(native_snapshot("mbo", lang="en"), "mbo")
        with self.assertRaisesRegex(visual.SnapshotError, "error_copy_mismatch"):
            visual.sanitize_snapshot(native_snapshot("mbo", message="safe-looking but unapproved copy"), "mbo")

    def test_selenium_async_bridge_uses_kind_then_webdriver_completion_callback(self):
        script = visual._CAPTURE_STATE_SCRIPT
        self.assertIn("const kind=arguments[0];", script)
        self.assertIn("const done=arguments[arguments.length-1];", script)
        self.assertNotIn("arguments[1]", script)
        self.assertIn("kind === 'mbo'", script)
        self.assertIn("done({ok:", script)

    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable for the DOM-stub bridge check")
    def test_capture_state_script_completes_for_both_native_error_kinds(self):
        harness = r"""
const script = __SCRIPT__;
const mboText = __MBO__;
const fbText = __FB__;
async function run(kind) {
  const card = {getBoundingClientRect:()=>({x:12,y:80,right:378,bottom:320,width:366,height:240})};
  const title = {textContent:'테마 카탈로그',getBoundingClientRect:()=>({x:10,y:0,right:300,bottom:50,width:290,height:50})};
  const toolbar = {querySelector:()=>title,getBoundingClientRect:()=>({x:0,y:0,right:390,bottom:60,width:390,height:60})};
  const marker = {
    innerText:kind==='mbo'?mboText:fbText.replace('없습니다 Facebook','없습니다'+String.fromCharCode(10)+'Facebook'),
    textContent:kind==='mbo'?mboText:fbText.replace('없습니다 Facebook','없습니다Facebook'),
    closest:()=>card
  };
  global.document = {
    fonts:{ready:Promise.resolve()}, images:[],
    documentElement:{lang:'ko-KR',scrollWidth:390},
    body:{hasAttribute:()=>false},
    querySelector:(selector)=>{
      if(selector==='.header-toolbar') return toolbar;
      if(selector==='#main-div' || selector==='#main-div .content-div') return card;
      if(selector==='.error-header' && kind==='mbo') return marker;
      if(selector==='#ordenowa-facebook-transport-error' && kind==='facebook') return marker;
      return null;
    },
    querySelectorAll:()=>[]
  };
  global.innerWidth=390; global.innerHeight=1100;
  return await new Promise((resolve,reject)=>{
    const timeout=setTimeout(()=>reject(new Error('async callback was not invoked')),1000);
    const done=(value)=>{clearTimeout(timeout);resolve(value);};
    try { new Function(script)(kind,done); }
    catch(error) { reject(error); }
  });
}
(async()=>{
  const mbo=await run('mbo'); const facebook=await run('facebook');
  if(!mbo.ok||!facebook.ok||!mbo.expectedCopy||!facebook.expectedCopy) process.exit(2);
  process.stdout.write('ok');
})().catch(()=>process.exit(3));
"""
        harness = (harness
                   .replace("__SCRIPT__", json.dumps(visual._CAPTURE_STATE_SCRIPT, ensure_ascii=False))
                   .replace("__MBO__", json.dumps(MBO_MESSAGE, ensure_ascii=False))
                   .replace("__FB__", json.dumps(FB_TITLE + " " + FB_MESSAGE, ensure_ascii=False)))
        result = subprocess.run([shutil.which("node"), "-e", harness], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("ok", result.stdout)

    def test_duplicate_error_card_fails_closed(self):
        duplicate = '<div class="row"><div class="card"><p class="error-header">' + MBO_MESSAGE + '</p></div></div>'
        with self.assertRaisesRegex(visual.SnapshotError, "error_marker_cardinality"):
            visual.sanitize_snapshot(native_snapshot("mbo", extras=duplicate), "mbo")

    def test_visual_fragment_excludes_sibling_row_content_and_rejects_extra_card_text(self):
        source = native_snapshot("mbo").decode("utf-8").replace(
            '<div class="row"><div class="col">',
            '<div class="row"><div class="private-sibling">private-row-account@example.invalid</div><div class="col">',
            1,
        )
        result = visual.sanitize_snapshot(source.encode("utf-8"), "mbo")
        self.assertNotIn("private-row-account@example.invalid", result.html)
        extra_text = source.replace(
            "</p></div></div></div></div>",
            "</p><span>private-card-name@example.invalid</span></div></div></div></div>",
            1,
        )
        with self.assertRaisesRegex(visual.SnapshotError, "error_card_unexpected_text"):
            visual.sanitize_snapshot(extra_text.encode("utf-8"), "mbo")

    def test_target_card_must_be_inside_native_content(self):
        source = native_snapshot("mbo").decode("utf-8")
        main_start = source.index('<div id="main-div">')
        row_start = source.index('<div class="row">', main_start)
        form_start = source.index('<form action=', row_start)
        row_markup = source[row_start:form_start].removesuffix("</div></div>")
        source = (
            source[:main_start]
            + '<div id="main-div"><div class="content-div"><div id="content-message-box"></div></div>'
            + row_markup + "</div>"
            + source[form_start:]
        )
        with self.assertRaises(visual.SnapshotError):
            visual.sanitize_snapshot(source.encode("utf-8"), "mbo")

    def test_page_title_must_be_inside_native_toolbar(self):
        source = native_snapshot("mbo").decode("utf-8")
        title = '<h1 class="title">테마 카탈로그</h1>'
        source = source.replace(title, "", 1)
        source = source.replace('<div id="main-div">', title + '<div id="main-div">', 1)
        with self.assertRaisesRegex(visual.SnapshotError, "native_toolbar_structure_invalid"):
            visual.sanitize_snapshot(source.encode("utf-8"), "mbo")

    def test_employee_shaped_title_and_class_values_fail_closed(self):
        title_source = native_snapshot("mbo").decode("utf-8").replace(
            "테마 카탈로그", "owner@example.invalid", 1
        )
        with self.assertRaisesRegex(visual.SnapshotError, "native_toolbar_structure_invalid"):
            visual.sanitize_snapshot(title_source.encode("utf-8"), "mbo")
        class_source = native_snapshot("mbo").decode("utf-8").replace(
            'class="ps-bo-rebrand"', 'class="ps-bo-rebrand employee@example.invalid"', 1
        )
        with self.assertRaisesRegex(visual.SnapshotError, "unsafe_body_class"):
            visual.sanitize_snapshot(class_source.encode("utf-8"), "mbo")

    def test_stylesheet_query_external_origin_and_private_asset_paths_are_rejected(self):
        for href in (
            "https://evil.invalid/theme.css",
            "http://localhost:18081/admin-kuranea/themes/new-theme/public/theme.css?token=private",
            "/admin-kuranea/themes/new-theme/public/../private.css",
            "/admin-kuranea/themes/new-theme/public/private.css#employee",
        ):
            with self.subTest(href=href):
                source = native_snapshot("mbo").decode("utf-8").replace(
                    "/admin-kuranea/themes/new-theme/public/theme.css", href
                )
                with self.assertRaises(visual.SnapshotError):
                    visual.sanitize_snapshot(source.encode("utf-8"), "mbo")

    def test_external_or_query_image_reference_is_rejected(self):
        for src in (
            "https://evil.invalid/error.svg",
            "/modules/ps_mbo/views/img/error.svg?token=private",
        ):
            with self.subTest(src=src):
                source = native_snapshot("mbo").decode("utf-8").replace(
                    "../modules/ps_mbo/views/img/error.svg", src
                )
                with self.assertRaises(visual.SnapshotError):
                    visual.sanitize_snapshot(source.encode("utf-8"), "mbo")

    def test_asset_url_allowlist_rejects_credentials_queries_and_path_tricks(self):
        safe, ext = visual.normalize_asset_url("/admin-kuranea/themes/new-theme/public/theme.css")
        self.assertEqual("/admin-kuranea/themes/new-theme/public/theme.css", safe)
        self.assertEqual(".css", ext)
        safe, ext = visual.normalize_asset_url(
            "http://localhost:18081/admin-kuranea/../modules/ps_mbo/views/img/error.svg"
        )
        self.assertEqual("/modules/ps_mbo/views/img/error.svg", safe)
        self.assertEqual(".svg", ext)
        safe, ext = visual.normalize_asset_url("/modules/klaviyopsautomation/dist/admin.css")
        self.assertEqual("/modules/klaviyopsautomation/dist/admin.css", safe)
        self.assertEqual(".css", ext)
        safe, ext = visual.normalize_asset_url("/admin-kuranea/themes/default/css/admin.css")
        self.assertEqual("/admin-kuranea/themes/default/css/admin.css", safe)
        self.assertEqual(".css", ext)
        for url in (
            "https://localhost:18081/admin-kuranea/themes/new-theme/public/theme.css",
            "http://user:pass@localhost:18081/admin-kuranea/themes/new-theme/public/theme.css",
            "http://localhost:18081/admin-kuranea/themes/new-theme/public/theme.css?x=1",
            "http://localhost:18081/admin-kuranea/themes/new-theme/public/%2e%2e/secret.css",
            "http://localhost:18082/admin-kuranea/themes/new-theme/public/theme.css",
            "http://localhost:18081/admin-kuranea/../../etc/passwd",
            "http://localhost:18081/admin-kuranea/../../private/token.css",
            "/modules/klaviyopsautomation/dist/admin.js",
            "/modules/klaviyopsautomation/dist/../private/admin.css",
            "/admin-kuranea/themes/default/css/admin.php",
            "/admin-kuranea/themes/default/../private/admin.css",
            "//evil.invalid/theme.css",
        ):
            with self.subTest(url=url):
                with self.assertRaises(visual.SnapshotError):
                    visual.normalize_asset_url(url)

    def test_unlisted_asset_failure_exposes_only_a_bounded_root_hint(self):
        with self.assertRaises(visual.SnapshotError) as captured:
            visual.normalize_asset_url("/themes/kuranea/assets/admin.css")
        self.assertEqual("asset_path_rejected", str(captured.exception))
        self.assertEqual("/themes/kuranea/assets", captured.exception.asset_path_prefix_hint)
        self.assertNotIn("admin.css", str(captured.exception.asset_path_prefix_hint))


class AssetProxyTests(unittest.TestCase):
    class FakeResponse:
        def __init__(self, status=200, content_type="text/css", data=b"body{color:#123}", location=None):
            self.status = status
            self._headers = {"Content-Type": content_type}
            if location:
                self._headers["Location"] = location
            self.data = data

        def getheader(self, name):
            return self._headers.get(name)

        def read(self, size):
            return self.data[:size]

    class FakeConnection:
        calls = []
        response = None

        def __init__(self, host, port, timeout):
            self.calls.append(("init", host, port, timeout))

        def request(self, method, path, headers):
            self.calls.append(("request", method, path, headers))

        def getresponse(self):
            return self.response

        def close(self):
            self.calls.append(("close",))

    def setUp(self):
        self.FakeConnection.calls = []
        self.FakeConnection.response = self.FakeResponse()

    def test_proxy_uses_only_localhost_static_get_without_cookies_or_auth(self):
        with patch.object(visual.http.client, "HTTPConnection", self.FakeConnection):
            body, mime = visual.fetch_static_asset("/admin-kuranea/themes/new-theme/public/theme.css")
        self.assertEqual(b"body{color:#123}", body)
        self.assertEqual("text/css", mime)
        request = next(call for call in self.FakeConnection.calls if call[0] == "request")
        self.assertEqual(("request", "GET", "/admin-kuranea/themes/new-theme/public/theme.css"), request[:3])
        self.assertEqual("localhost:18081", request[3]["Host"])
        self.assertNotIn("Cookie", request[3])
        self.assertNotIn("Authorization", request[3])

    def test_proxy_rejects_non_static_paths_before_connecting(self):
        for path in (
            "/admin-kuranea/index.php?controller=AdminPsfacebookModule",
            "/modules/kuraneabackoffice/private.php",
            "/admin-kuranea/themes/new-theme/public/theme.css?token=x",
        ):
            with self.subTest(path=path):
                with patch.object(visual.http.client, "HTTPConnection", self.FakeConnection):
                    with self.assertRaises(visual.SnapshotError):
                        visual.fetch_static_asset(path)
                self.assertFalse(any(call[0] == "request" for call in self.FakeConnection.calls))

    def test_proxy_rejects_redirects_wrong_mime_and_oversize_assets(self):
        cases = (
            self.FakeResponse(status=302, location="https://evil.invalid/"),
            self.FakeResponse(content_type="text/html", data=b"<html>secret</html>"),
            self.FakeResponse(data=b"x" * (visual.MAX_ASSET_BYTES + 1)),
        )
        for response in cases:
            with self.subTest(response=response.status, content_type=response.getheader("Content-Type")):
                self.FakeConnection.response = response
                with patch.object(visual.http.client, "HTTPConnection", self.FakeConnection):
                    with self.assertRaises(visual.SnapshotError):
                        visual.fetch_static_asset("/admin-kuranea/themes/new-theme/public/theme.css")

    def test_preview_server_sets_strict_csp_and_serves_only_the_sanitized_snapshot(self):
        snapshot = visual.sanitize_snapshot(native_snapshot("facebook"), "facebook")
        server = visual._PreviewServer(snapshot)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(server.url, timeout=3) as response:
                payload = response.read().decode("utf-8")
                csp = response.headers.get("Content-Security-Policy", "")
                self.assertEqual(200, response.status)
            self.assertIn("script-src 'none'", csp)
            self.assertIn("connect-src 'none'", csp)
            self.assertIn("form-action 'none'", csp)
            self.assertIn("frame-src 'none'", csp)
            self.assertIn("img-src 'self'", csp)
            self.assertNotIn("data:", csp)
            self.assertNotIn("data-token", payload)
            self.assertIn(FB_TITLE, payload)
            self.assertNotIn("csrf-private-value", payload)
            self.assertEqual(0, server.mutation_attempts)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_preview_server_proxies_root_relative_static_assets_but_not_admin_routes(self):
        snapshot = visual.sanitize_snapshot(native_snapshot("mbo"), "mbo")
        server = visual._PreviewServer(snapshot)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        static_path = "/admin-kuranea/themes/new-theme/public/theme.css"
        with patch.object(visual, "fetch_static_asset", return_value=(b"body{}", "text/css")) as fetch:
            try:
                with urlopen(server.url.rstrip("/") + static_path, timeout=3) as response:
                    self.assertEqual(200, response.status)
                    self.assertEqual(b"body{}", response.read())
                self.assertEqual(static_path, fetch.call_args.args[0])
                with self.assertRaises(HTTPError):
                    urlopen(server.url.rstrip("/") + "/admin-kuranea/index.php", timeout=3)
                self.assertEqual(1, server.blocked_asset_requests)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


class OutputSafetyTests(unittest.TestCase):
    def test_changed_native_html_is_rejected_before_browser_and_private_input_is_consumed(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = Path(directory)
            private = runner / 'private'
            private.mkdir(mode=0o700)
            artifacts = runner / 'safe'
            artifacts.mkdir()
            html_path = private / 'mbo.html'
            body = native_snapshot('mbo')
            html_path.write_bytes(body)
            html_path.chmod(0o600)
            with self.assertRaisesRegex(visual.SnapshotError, 'native_response_snapshot_hash_mismatch'):
                visual.render_private_snapshot(html_path, private, artifacts, runner, 'mbo', hashlib.sha256(body + b'changed').hexdigest())
            self.assertFalse(html_path.exists())
            self.assertEqual(list(artifacts.iterdir()), [])

    def test_failed_atomic_artifact_write_removes_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "partial.png"
            with patch.object(visual.os, "fsync", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    visual._safe_write(path, b"partial image")
            self.assertFalse(path.exists())

    def test_artifacts_are_created_private_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "safe.json"
            visual._safe_write(path, b'{"passed":true}\n')
            self.assertEqual(b'{"passed":true}\n', path.read_bytes())
            if visual.os.name == "posix":
                self.assertEqual(0o600, path.stat().st_mode & 0o777)
            with self.assertRaisesRegex(visual.SnapshotError, "output_already_exists"):
                visual._safe_write(path, b"overwrite")


if __name__ == "__main__":
    unittest.main(verbosity=2)
