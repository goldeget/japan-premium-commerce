"""Behavior checks for the public service worker's navigation policy."""
from __future__ import annotations

import ast
from contextlib import redirect_stderr
import io
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.e2e import verify_pwa_browser as pwa_browser
from tests.e2e.verify_pwa_browser import (
    ChromeBrowserCdp,
    ChromeBrowserCdpError,
    execute_browser_cdp_command,
    exposes_test_identity,
    manifest_installability_issues,
    response_has_private_cache_policy,
    restore_offline_network_state,
    same_origin,
    validate_isolated_ci_target,
    verify_offline_fallback,
)


ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "themes" / "kuranea" / "assets" / "sw.js"
PWA_BROWSER = ROOT / "tests" / "e2e" / "verify_pwa_browser.py"


def function_source(source: str, function_name: str) -> str:
    """Return one top-level function for focused browser-flow contract checks."""
    lines = source.splitlines(keepends=True)
    function = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    return "".join(lines[function.lineno - 1 : function.end_lineno])


NODE_HARNESS = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const config = JSON.parse(process.argv[2]);
const listeners = {};
let fetchCalls = 0;
let cacheOpenCalls = 0;
let responsePromise = null;
let fetchOptions = null;
const opaqueRedirectResponse = {
  type: 'opaqueredirect',
  status: 0,
  headers: {get: () => null},
  text: async () => '',
};
const self = {
  addEventListener: (name, callback) => { listeners[name] = callback; },
  clients: {claim: async () => {}},
  navigator: {language: 'en-US'},
  skipWaiting: async () => {},
};
const fetch = async (_request, options) => {
  fetchCalls += 1;
  fetchOptions = options ?? null;
  if (config.offline) throw new TypeError('offline');
  if (config.opaqueRedirect) return opaqueRedirectResponse;
  return new Response('online response', {status: 200});
};
const caches = {open: async () => { cacheOpenCalls += 1; throw new Error('cache must not be opened'); }};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {self, fetch, Response, caches});
const request = {
  url: 'http://localhost:18080/ja/identity',
  method: config.method,
  mode: config.mode,
  redirect: config.redirect || 'manual',
  referrer: 'http://localhost:18080/ja/my-account',
  referrerPolicy: 'strict-origin-when-cross-origin',
  headers: {get: name => name === 'Accept-Language' ? config.language : null},
};
listeners.fetch({request, respondWith: promise => { responsePromise = promise; }});
(async () => {
  let response = null;
  let body = '';
  if (responsePromise) {
    response = await responsePromise;
    body = await response.text();
  }
  process.stdout.write(JSON.stringify({
    intercepted: responsePromise !== null,
    status: response?.status ?? null,
    responseType: response?.type ?? 'default',
    opaqueRedirectReturned: response === opaqueRedirectResponse,
    cacheControl: response?.headers.get('Cache-Control') ?? null,
    body,
    fetchCalls,
    fetchOptions,
    cacheOpenCalls,
  }));
})().catch(error => { console.error(error); process.exitCode = 1; });
"""


class PublicServiceWorkerBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.node = shutil.which("node")

    def run_worker(self, **config: object) -> dict[str, object]:
        if self.node is None:
            self.skipTest("Node.js is required to execute the service-worker behavior test")
        result = subprocess.run(
            [
                self.node,
                "-e",
                NODE_HARNESS,
                str(WORKER),
                json.dumps(config),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def test_offline_navigation_returns_localized_no_store_fallback(self) -> None:
        result = self.run_worker(
            method="GET", mode="navigate", offline=True, language="ko-KR,ko;q=0.9"
        )

        self.assertIs(result["intercepted"], True)
        self.assertEqual(503, result["status"])
        self.assertEqual("no-store", result["cacheControl"])
        self.assertIn('<html lang="ko">', result["body"])
        self.assertIn("연결을 확인해 주세요", result["body"])
        self.assertEqual(0, result["cacheOpenCalls"])

    def test_online_navigation_keeps_the_network_response_without_opening_cache(self) -> None:
        result = self.run_worker(
            method="GET", mode="navigate", offline=False, language="ja-JP"
        )

        self.assertIs(result["intercepted"], True)
        self.assertEqual(200, result["status"])
        self.assertEqual("online response", result["body"])
        self.assertEqual(
            {
                "redirect": "manual",
                "referrer": "http://localhost:18080/ja/my-account",
                "referrerPolicy": "strict-origin-when-cross-origin",
            },
            result["fetchOptions"],
        )
        self.assertEqual(0, result["cacheOpenCalls"])

    def test_opaque_redirect_response_is_returned_unchanged_for_browser_navigation(self) -> None:
        result = self.run_worker(
            method="GET",
            mode="navigate",
            offline=False,
            opaqueRedirect=True,
            language="ja-JP",
        )

        self.assertIs(result["intercepted"], True)
        self.assertEqual("opaqueredirect", result["responseType"])
        self.assertEqual(0, result["status"])
        self.assertIs(result["opaqueRedirectReturned"], True)
        self.assertEqual("manual", result["fetchOptions"]["redirect"])

    def test_non_navigation_and_non_get_requests_are_left_to_the_browser(self) -> None:
        for method, mode in (("GET", "cors"), ("POST", "navigate")):
            with self.subTest(method=method, mode=mode):
                result = self.run_worker(
                    method=method, mode=mode, offline=True, language="en-US"
                )

                self.assertIs(result["intercepted"], False)
                self.assertEqual(0, result["fetchCalls"])
                self.assertEqual(0, result["cacheOpenCalls"])


class PwaOfflineWorkerNetworkTests(unittest.TestCase):
    def test_chromedriver_debugger_address_discovers_local_browser_websocket(self) -> None:
        websocket_url = "ws://localhost:9222/devtools/browser/test-only-token"
        connection = object()
        http_calls: list[tuple[str, int, int, str, str]] = []

        class Driver:
            capabilities = {
                "goog:chromeOptions": {"debuggerAddress": "localhost:9222"},
            }

        class Response:
            status = 200

            def read(self, amount: int) -> bytes:
                self_read_sizes.append(amount)
                return json.dumps({"webSocketDebuggerUrl": websocket_url}).encode()

        self_read_sizes: list[int] = []

        class HttpConnection:
            def __init__(self, host: str, port: int, timeout: float) -> None:
                self.host = host
                self.port = port
                self.timeout = timeout

            def request(self, method: str, path: str) -> None:
                http_calls.append((self.host, self.port, self.timeout, method, path))

            def getresponse(self) -> Response:
                return Response()

            def close(self) -> None:
                pass

        opened_urls: list[str] = []

        def open_websocket(url: str):
            opened_urls.append(url)
            return connection

        with patch.object(pwa_browser, "HTTPConnection", HttpConnection, create=True), patch.object(
            pwa_browser, "WebSocketConnection", side_effect=open_websocket, create=True
        ):
            browser_cdp = pwa_browser.connect_browser_cdp(Driver())

        self.assertIs(browser_cdp.connection, connection)
        self.assertEqual([("localhost", 9222, 3, "GET", "/json/version")], http_calls)
        self.assertEqual([65537], self_read_sizes)
        self.assertEqual([websocket_url], opened_urls)

    def test_chromedriver_debugger_address_rejects_nonloopback_before_http(self) -> None:
        class Driver:
            capabilities = {
                "goog:chromeOptions": {"debuggerAddress": "remote.example:9222"},
            }

        with patch.object(pwa_browser, "HTTPConnection", create=True) as open_http, patch.object(
            pwa_browser, "WebSocketConnection", create=True
        ), self.assertRaises(ChromeBrowserCdpError) as raised:
            pwa_browser.connect_browser_cdp(Driver())

        self.assertEqual(
            "devtools_debugger_address_invalid",
            getattr(raised.exception, "diagnostic_code", None),
        )
        open_http.assert_not_called()

    def test_devtools_connection_uses_only_a_loopback_browser_websocket(self) -> None:
        created_urls: list[str] = []
        connection = object()

        class Driver:
            capabilities = {
                "se:cdp": "ws://localhost:9222/devtools/browser/test-only-token",
            }

            def start_devtools(self):
                raise AssertionError("version-specific Selenium DevTools import must not be used")

        def open_websocket(url: str):
            created_urls.append(url)
            return connection

        with patch.object(pwa_browser, "WebSocketConnection", side_effect=open_websocket, create=True):
            browser_cdp = pwa_browser.connect_browser_cdp(Driver())

        self.assertIs(browser_cdp.connection, connection)
        self.assertEqual(
            ["ws://localhost:9222/devtools/browser/test-only-token"],
            created_urls,
        )

    def test_devtools_connection_rejects_nonlocal_or_non_browser_targets(self) -> None:
        class Driver:
            def __init__(self, url: str) -> None:
                self.capabilities = {"se:cdp": url}

            def start_devtools(self):
                raise AssertionError("must validate the endpoint without invoking Selenium DevTools")

        invalid_urls = (
            "ws://remote.example:9222/devtools/browser/token",
            "wss://localhost:9222/devtools/browser/token",
            "ws://localhost:9222/devtools/page/token",
            "ws://user@localhost:9222/devtools/browser/token",
            "ws://localhost:9222/devtools/browser/token?target=elsewhere",
        )
        opened_urls: list[str] = []

        def open_websocket(url: str):
            opened_urls.append(url)
            raise AssertionError("invalid DevTools endpoint must not be opened")

        for url in invalid_urls:
            with self.subTest(url=url), patch.object(
                pwa_browser,
                "WebSocketConnection",
                side_effect=open_websocket,
                create=True,
            ), self.assertRaises(ChromeBrowserCdpError):
                pwa_browser.connect_browser_cdp(Driver(url))
        self.assertEqual([], opened_urls)

    def test_devtools_open_failure_has_safe_operation_diagnostic(self) -> None:
        class Driver:
            capabilities = {"se:cdp": "ws://127.0.0.1:9222/devtools/browser/private-token"}

        with patch.object(
            pwa_browser,
            "WebSocketConnection",
            side_effect=RuntimeError("ws://127.0.0.1:9222/devtools/browser/private-token"),
            create=True,
        ), self.assertRaises(ChromeBrowserCdpError) as raised:
            pwa_browser.connect_browser_cdp(Driver())

        self.assertEqual(
            "devtools_connection_open",
            getattr(raised.exception, "diagnostic_code", None),
        )
        self.assertEqual("RuntimeError", getattr(raised.exception, "cause_type", None))
        self.assertNotIn("private-token", str(raised.exception))

    def test_customer_order_private_route_requires_a_nonempty_isolated_cart(self) -> None:
        source = PWA_BROWSER.read_text(encoding="utf-8")
        viewport = function_source(source, "run_viewport")
        self.assertIn("CI_TEST_PRODUCT_ID", source)
        self.assertIn("add_isolated_product_to_customer_cart", source)
        self.assertLess(
            viewport.index("add_isolated_product_to_customer_cart("),
            viewport.index('"customer_order_route"'),
        )
        self.assertIn("cart contents could not be confirmed", source)

    def test_customer_registration_native_click_waits_for_unobstructed_center(self) -> None:
        click = getattr(pwa_browser, "click_native_when_unobstructed", None)
        self.assertTrue(callable(click), "PWA customer setup needs a guarded native click helper")

        class Element:
            clicked = False

            def is_displayed(self) -> bool:
                return True

            def is_enabled(self) -> bool:
                return True

            def click(self) -> None:
                self.clicked = True

        class Driver:
            def __init__(self) -> None:
                self.center_visibility = iter((False, True))
                self.scripts: list[str] = []

            def execute_script(self, script: str, _element) -> bool | None:
                self.scripts.append(script)
                if "elementFromPoint" in script:
                    return next(self.center_visibility)
                return None

        class ImmediateWait:
            def __init__(self, driver, *_args, **_kwargs) -> None:
                self.driver = driver

            def until(self, condition, message=None):
                for _ in range(3):
                    result = condition(self.driver)
                    if result:
                        return result
                raise TimeoutError(message or "condition was not met")

        driver = Driver()
        element = Element()
        with patch.object(pwa_browser, "WebDriverWait", ImmediateWait):
            click(driver, element)

        self.assertTrue(element.clicked)
        self.assertEqual(2, sum("elementFromPoint" in script for script in driver.scripts))

    def test_browser_cdp_wakes_the_pinned_receiver_before_closing(self) -> None:
        class Socket:
            closed = False

            def close(self):
                self.closed = True

        class Connection:
            def __init__(self) -> None:
                self._ws = Socket()

            def close(self):
                if not self._ws.closed:
                    raise AssertionError("Selenium close would wait for the receiver timeout")

        connection = Connection()
        browser_cdp = ChromeBrowserCdp(connection)

        browser_cdp.close()

        self.assertTrue(connection._ws.closed)
        self.assertTrue(browser_cdp.closed)

    def test_flattened_command_waits_for_worker_response_and_restores_page_session(self) -> None:
        class Connection:
            def __init__(self) -> None:
                self.session_id: str | None = "page-session"
                self.payloads: list[tuple[dict[str, object], str | None]] = []
                self.reject = False

            def execute(self, command):
                payload = next(command)
                self.payloads.append((payload, self.session_id))
                if self.reject:
                    raise RuntimeError("raw protocol details")
                try:
                    command.send({"accepted": True})
                except StopIteration as result:
                    return result.value
                raise AssertionError("CDP command did not finish after its response")

        connection = Connection()
        result = execute_browser_cdp_command(
            connection, "Network.enable", {"maxTotalBufferSize": 10}, "worker-session"
        )

        self.assertEqual({"accepted": True}, result)
        self.assertEqual(
            ({"method": "Network.enable", "params": {"maxTotalBufferSize": 10}}, "worker-session"),
            connection.payloads[0],
        )
        self.assertEqual("page-session", connection.session_id)

        connection.reject = True
        with self.assertRaisesRegex(
            ChromeBrowserCdpError, "Chrome rejected or did not answer Network.enable"
        ) as rejected:
            execute_browser_cdp_command(connection, "Network.enable", session_id="worker-session")
        self.assertEqual("cdp_command_network_enable", rejected.exception.diagnostic_code)
        self.assertEqual("RuntimeError", rejected.exception.cause_type)
        self.assertEqual("page-session", connection.session_id)

    def test_worker_protocol_rejection_stops_before_the_offline_navigation(self) -> None:
        class Driver:
            page_source = "ORDENOWA"

            def __init__(self) -> None:
                self.commands: list[str] = []
                self.body = "ORDENOWA"

            def execute_cdp_cmd(self, command, _parameters):
                self.commands.append(command)
                if command == "Target.getTargets":
                    return {"targetInfos": [{
                        "type": "service_worker",
                        "url": "http://localhost:18080/sw.js",
                        "targetId": "shop-worker",
                    }]}
                if command == "Target.attachToTarget":
                    return {"sessionId": "worker-session"}
                # This is only the outer forwarding acknowledgement. The nested
                # Network command has not succeeded and the worker stays online.
                if command == "Target.sendMessageToTarget":
                    return {}
                return {}

            def get(self, _url):
                self.commands.append("Page.navigate")

            def find_element(self, *_args):
                return SimpleNamespace(text=self.body)

            def save_screenshot(self, _path):
                return True

        class BrowserCdp:
            def __init__(self) -> None:
                self.commands: list[tuple[str, str | None]] = []

            def execute(self, method, parameters=None, session_id=None):
                self.commands.append((method, session_id))
                if method == "Target.getTargets":
                    return {"targetInfos": [{
                        "type": "service_worker",
                        "url": "http://localhost:18080/sw.js",
                        "targetId": "shop-worker",
                    }]}
                if method == "Target.attachToTarget":
                    return {"sessionId": "worker-session"}
                if (
                    method == "Network.emulateNetworkConditions"
                    and session_id == "worker-session"
                    and parameters["offline"]
                ):
                    raise ChromeBrowserCdpError(
                        "Chrome rejected Network.emulateNetworkConditions",
                        diagnostic_code="cdp_command_network_emulate_network_conditions",
                    )
                return {}

            def close(self):
                self.commands.append(("close", None))

        driver = Driver()
        browser_cdp = BrowserCdp()
        stages: list[str] = []
        with patch("tests.e2e.verify_pwa_browser.By", SimpleNamespace(TAG_NAME="tag name")), patch(
            "tests.e2e.verify_pwa_browser.connect_browser_cdp",
            return_value=browser_cdp,
            create=True,
        ):
            with self.assertRaises(ChromeBrowserCdpError) as rejected:
                verify_offline_fallback(
                    driver, "http://localhost:18080", "en", Path("unused.png"), stages.append
                )

        self.assertRegex(str(rejected.exception), "Chrome rejected Network.emulateNetworkConditions")
        self.assertNotIn("Page.navigate", driver.commands)
        self.assertNotIn("offline_fallback_navigation", stages)
        self.assertIn(("Network.emulateNetworkConditions", "worker-session"), browser_cdp.commands)
        self.assertIn(("close", None), browser_cdp.commands)

    def test_offline_fallback_applies_and_restores_worker_target_network(self) -> None:
        # Page-target emulation leaves service-worker fetches online in Chromium.
        # Model that boundary so removing worker emulation breaks this regression.
        class Driver:
            page_source = "ORDENOWA"

            def __init__(self) -> None:
                self.worker_offline = False
                self.worker_states: list[bool] = []
                self.commands: list[str] = []
                self.body = ""

            def execute_cdp_cmd(self, command, _parameters):
                self.commands.append(command)
                return {}

            def get(self, _url):
                self.body = "You are offline" if self.worker_offline else "ORDENOWA"

            def find_element(self, _by, selector):
                if selector == "html":
                    return SimpleNamespace(get_attribute=lambda _name: "en")
                return SimpleNamespace(text=self.body)

            def save_screenshot(self, _path):
                return True

        class BrowserCdp:
            def __init__(self) -> None:
                self.commands: list[tuple[str, str | None]] = []
                self.worker_states: list[bool] = []
                self.attached_target: str | None = None
                self.closed = False

            def execute(self, method, parameters=None, session_id=None):
                self.commands.append((method, session_id))
                if method == "Target.getTargets":
                    return {"targetInfos": [
                        {"type": "service_worker", "url": "http://other.invalid/sw.js", "targetId": "other"},
                        {"type": "service_worker", "url": "http://localhost:18080/sw.js", "targetId": "shop"},
                    ]}
                if method == "Target.attachToTarget":
                    self.attached_target = parameters["targetId"]
                    return {"sessionId": "shop-worker"}
                if method == "Network.emulateNetworkConditions" and session_id == "shop-worker":
                    self.worker_states.append(parameters["offline"])
                    driver.worker_offline = parameters["offline"]
                return {}

            def close(self):
                self.closed = True

        driver = Driver()
        browser_cdp = BrowserCdp()
        with patch("tests.e2e.verify_pwa_browser.By", SimpleNamespace(TAG_NAME="tag name")), patch(
            "tests.e2e.verify_pwa_browser.assert_empty_cache_storage"
        ), patch("tests.e2e.verify_pwa_browser.connect_browser_cdp", return_value=browser_cdp):
            verify_offline_fallback(
                driver, "http://localhost:18080", "en", Path("unused.png"), lambda _stage: None
            )

        self.assertEqual("shop", browser_cdp.attached_target)
        self.assertEqual([True, False], browser_cdp.worker_states)
        self.assertFalse(driver.worker_offline)
        self.assertIn(("Network.enable", "shop-worker"), browser_cdp.commands)
        self.assertIn(("Target.detachFromTarget", None), browser_cdp.commands)
        self.assertTrue(browser_cdp.closed)
        self.assertLess(
            browser_cdp.commands.index(("Network.enable", "shop-worker")),
            browser_cdp.commands.index(("Network.emulateNetworkConditions", "shop-worker")),
        )

    def test_worker_reset_failure_still_restores_page_and_detaches(self) -> None:
        class Driver:
            def __init__(self) -> None:
                self.commands: list[str] = []

            def execute_cdp_cmd(self, command, _parameters):
                self.commands.append(command)

        class BrowserCdp:
            def __init__(self) -> None:
                self.commands: list[tuple[str, str | None]] = []

            def execute(self, method, _parameters=None, session_id=None):
                self.commands.append((method, session_id))
                if method == "Network.emulateNetworkConditions":
                    raise RuntimeError("worker reset failed")
                return {}

            def close(self):
                self.commands.append(("close", None))

        driver = Driver()
        browser_cdp = BrowserCdp()
        with redirect_stderr(io.StringIO()):
            restore_offline_network_state(
                driver, AssertionError("original failure"), "shop-worker", browser_cdp
            )
        self.assertEqual([
            "Network.emulateNetworkConditions",
            "Network.setCacheDisabled",
        ], driver.commands)
        self.assertEqual([
            ("Network.emulateNetworkConditions", "shop-worker"),
            ("Target.detachFromTarget", None),
            ("close", None),
        ], browser_cdp.commands)


class PwaInstallabilityContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base_url = "http://localhost:18080/store/"
        self.manifest = {
            "id": "/store/",
            "name": "ORDENOWA",
            "start_url": "/store/",
            "scope": "/store/",
            "display": "standalone",
            "icons": [
                {"src": "/store/icon-192.png", "sizes": "192x192", "purpose": "any"},
                {"src": "/store/icon-512.png", "sizes": "512x512", "purpose": "any"},
                {"src": "/store/icon-maskable.png", "sizes": "512x512", "purpose": "maskable"},
            ],
        }

    def test_secure_scoped_manifest_with_standard_and_maskable_icons_is_installable(self) -> None:
        issues = manifest_installability_issues(self.manifest, self.base_url, True)

        self.assertEqual([], issues)

    def test_insecure_context_is_not_reported_as_installable(self) -> None:
        issues = manifest_installability_issues(self.manifest, "http://shop.example/", False)

        self.assertIn("page is not a secure context", issues)

    def test_mismatched_scope_and_missing_maskable_icon_are_reported(self) -> None:
        broken = {**self.manifest, "scope": "/"}
        broken["icons"] = self.manifest["icons"][:2]

        issues = manifest_installability_issues(broken, self.base_url, True)

        self.assertTrue(any("scope" in issue for issue in issues))
        self.assertIn("manifest is missing a 512x512 maskable icon", issues)

    def test_generated_links_must_match_the_full_origin(self) -> None:
        self.assertTrue(same_origin("https://shop.example/store/", "https://shop.example/login"))
        self.assertFalse(same_origin("https://shop.example/store/", "http://shop.example/login"))
        self.assertFalse(same_origin("https://shop.example/store/", "https://other.example/login"))

    def test_private_document_responses_require_private_or_no_store_cache_control(self) -> None:
        self.assertTrue(response_has_private_cache_policy({"Cache-Control": "private, max-age=60"}))
        self.assertTrue(response_has_private_cache_policy({"cache-control": "no-store"}))
        self.assertFalse(response_has_private_cache_policy({"Pragma": "no-cache", "Expires": "0"}))
        self.assertFalse(response_has_private_cache_policy({}))

    def test_logout_history_check_detects_either_name_or_email(self) -> None:
        self.assertTrue(exposes_test_identity("Hello Pwa", "Pwa", "Session", "qa@example.invalid"))
        self.assertTrue(exposes_test_identity("Session", "Pwa", "Session", "qa@example.invalid"))
        self.assertTrue(exposes_test_identity("qa@example.invalid", "Pwa", "Session", "qa@example.invalid"))
        self.assertFalse(exposes_test_identity("Sign in", "Pwa", "Session", "qa@example.invalid"))


class PwaBrowserLifecycleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PWA_BROWSER.read_text(encoding="utf-8")

    def test_account_route_comes_from_authenticated_header_and_all_links_check_full_origin(self) -> None:
        create_customer = function_source(self.source, "create_session_customer")
        account_link = function_source(self.source, "authenticated_account_url")

        self.assertIn("if not same_origin(base_url, signin_url):", create_customer)
        self.assertIn("if not same_origin(base_url, registration_url):", create_customer)
        self.assertIn("account_url = authenticated_account_url(driver, base_url)", create_customer)
        self.assertIn('div.dropdown-menu[aria-labelledby="userMenuButton"] a[href]', account_link)
        self.assertIn("if not same_origin(base_url, account_url):", account_link)

    def test_logout_and_history_require_login_form_and_check_both_test_names(self) -> None:
        logout = function_source(self.source, "verify_logout_protection")
        login_wait = function_source(self.source, "wait_for_logout_login_form")
        identity_check = function_source(self.source, "exposes_test_identity")
        viewport = function_source(self.source, "run_viewport")

        self.assertIn("wait_for_logout_login_form(driver, shop_url)", logout)
        self.assertIn('wait_visible(driver, "#login-form input[name=\'email\']")', login_wait)
        self.assertIn(
            'for history_stage in ("browser_history_first_back", "browser_history_second_back"):',
            logout,
        )
        self.assertGreaterEqual(logout.count("exposes_test_identity(body_text, first_name, last_name, email)"), 2)
        self.assertIn("for name in (first_name, last_name):", identity_check)
        self.assertIn('"Pwa",\n            "Session",', viewport)

    def test_pwa_browser_uses_generated_locale_destinations_and_exact_browser_language(self) -> None:
        locale_selection = function_source(self.source, "select_storefront_locale")
        offline_check = function_source(self.source, "verify_offline_fallback")
        viewport = function_source(self.source, "run_viewport")

        self.assertIn("resolve_storefront_locale_url(option_values, locale, shop_url)", locale_selection)
        self.assertIn('"Network.setExtraHTTPHeaders"', viewport)
        self.assertIn('"Accept-Language": locale_profile["accept_language"]', viewport)
        self.assertIn("assert_offline_fallback_content(driver, locale)", offline_check)

    def test_logout_qa_reports_only_a_bounded_substage_for_assertion_failures(self) -> None:
        logout = function_source(self.source, "verify_logout_protection")
        viewport = function_source(self.source, "run_viewport")
        for substage in (
            "resolve_signout_link",
            "click_signout",
            "wait_signed_out_header",
            "assert_logout_destination",
            "request_protected_account",
            "wait_protected_document",
            "assert_no_account_links",
            "require_login_form",
            "assert_no_identity_on_protected_page",
            "assert_empty_logged_out_cache",
            "browser_history_first_back",
            "browser_history_second_back",
            "reopen_protected_account",
            "require_login_form_after_history",
            "assert_empty_account_cache_after_history",
        ):
            with self.subTest(substage=substage):
                self.assertIn(f'"{substage}"', logout)
        self.assertIn('set_substage=update_logout_substage', viewport)
        self.assertIn('re.fullmatch(r"[a-z][a-z0-9_]{0,63}", logout_substage)', viewport)
        self.assertIn('diagnostic = f"; substage={logout_substage}"', viewport)
        self.assertNotIn("str(error)", viewport)

    def test_clicked_logout_response_is_validated_before_the_protected_route_revisit(self) -> None:
        logout = function_source(self.source, "verify_logout_protection")

        self.assertIn("validate_logout_navigation_trace(logout_trace)", logout)
        self.assertLess(
            logout.index("validate_logout_navigation_trace(logout_trace)"),
            logout.index('mark_stage("request_protected_account")'),
        )
        self.assertIn('expected_final_url=expected_login_url', logout)

    def test_private_routes_fail_closed_when_document_cache_headers_are_unavailable(self) -> None:
        matcher = function_source(self.source, "matching_document_responses")
        cache_check = function_source(self.source, "assert_private_document_cache_headers")
        navigate = function_source(self.source, "navigate_private_document")
        viewport = function_source(self.source, "run_viewport")

        self.assertIn('driver.get_log("performance")', matcher)
        self.assertIn("UNVERIFIED: document cache headers could not be observed", cache_check)
        self.assertIn("response_has_private_cache_policy(headers)", cache_check)
        self.assertIn('"customer_cart_route"', viewport)
        self.assertIn('"authenticated cart"', viewport)
        self.assertIn('"customer_order_route"', viewport)
        self.assertIn('"authenticated order"', viewport)
        self.assertIn("assert_private_document_cache_headers(driver, requested_url, shop_url, route_label)", navigate)
        self.assertNotIn("pwa-{label}-failure.png", self.source)
        self.assertNotIn("print(body_text", self.source)

    def test_logged_out_private_route_reports_only_safe_cache_response_metadata(self) -> None:
        shop_url = "http://localhost:18080"
        secret_url = shop_url + "/ko/my-account?token=private-token-sentinel"

        class Driver:
            def __init__(self, entries: list[dict[str, str]]) -> None:
                self.entries = entries

            def get_log(self, _log_type: str) -> list[dict[str, str]]:
                return self.entries

        with self.assertRaises(AssertionError) as no_response:
            pwa_browser.assert_private_document_cache_headers(
                Driver([]), secret_url, shop_url, "logged-out account"
            )
        self.assertEqual(no_response.exception.diagnostic_code, "document_response_missing")
        self.assertEqual(no_response.exception.safe_metadata, {"response_count": 0})
        self.assertNotIn("private-token-sentinel", str(no_response.exception))

        missing_policy_event = {
            "message": json.dumps(
                {
                    "message": {
                        "method": "Network.responseReceived",
                        "params": {
                            "type": "Document",
                            "response": {
                                "url": secret_url,
                                "status": 302,
                                "headers": {"Cache-Control": "no-cache, max-age=0"},
                                "fromServiceWorker": True,
                                "fromDiskCache": False,
                            },
                        },
                    }
                }
            )
        }
        with self.assertRaises(AssertionError) as missing_policy:
            pwa_browser.assert_private_document_cache_headers(
                Driver([missing_policy_event] * 25), secret_url, shop_url, "logged-out account"
            )
        self.assertEqual(missing_policy.exception.diagnostic_code, "cache_policy_missing")
        self.assertEqual(
            missing_policy.exception.safe_metadata,
            {
                "response_count": 20,
                "status": 302,
                "cache_control_directives": ["max-age", "no-cache"],
                "pragma_present": False,
                "expires_present": False,
                "from_disk_cache": False,
                "from_service_worker": True,
            },
        )
        self.assertNotIn("private-token-sentinel", str(missing_policy.exception))
        self.assertEqual(
            pwa_browser.response_count_diagnostic(missing_policy.exception.safe_metadata["response_count"]),
            "; response_count=20",
        )
        self.assertEqual(pwa_browser.response_count_diagnostic(1000), "; response_count=20")

    def test_emitted_private_response_count_uses_the_bounded_formatter(self) -> None:
        viewport = function_source(self.source, "run_viewport")
        self.assertIn('response_count_diagnostic(metadata.get("response_count"))', viewport)

    def test_logged_out_private_navigation_reports_its_sanitized_substage(self) -> None:
        navigate = function_source(self.source, "navigate_private_document")
        self.assertIn("set_substage", navigate)
        self.assertIn('mark_substage("same_origin")', navigate)
        self.assertIn('mark_substage("performance_log")', navigate)
        self.assertIn('mark_substage("document_request")', navigate)
        self.assertIn('mark_substage("document_ready")', navigate)
        self.assertIn('mark_substage("cache_policy")', navigate)

    def test_authenticated_order_qa_uses_the_canonical_checkout_link_from_the_cart(self) -> None:
        checkout_url = getattr(pwa_browser, "customer_checkout_url_from_cart", None)
        self.assertTrue(callable(checkout_url), "PWA QA must use PrestaShop's generated checkout link")

        canonical_url = "http://localhost:18080/checkout?token=private-token-sentinel"

        class Link:
            def is_displayed(self) -> bool:
                return True

            def is_enabled(self) -> bool:
                return True

            def get_attribute(self, name: str) -> str | None:
                return canonical_url if name == "href" else None

        class Driver:
            selector = ""

            def find_elements(self, by: str, selector: str) -> list[Link]:
                self.selector = selector
                return [Link()]

        driver = Driver()
        with patch("tests.e2e.verify_pwa_browser.By", SimpleNamespace(CSS_SELECTOR="css selector")):
            self.assertEqual(
                canonical_url,
                checkout_url(driver, "http://localhost:18080"),
            )
        self.assertEqual(
            ".js-cart-detailed-actions > .d-grid > a.btn-primary[href]",
            driver.selector,
        )

        viewport = function_source(self.source, "run_viewport")
        self.assertIn("customer_checkout_url_from_cart(driver, base_url)", viewport)
        self.assertIn("navigate_private_document(driver, order_url, base_url, \"authenticated order\")", viewport)

    def test_canonical_checkout_link_requires_one_visible_same_origin_target_without_echoing_url(self) -> None:
        checkout_url = getattr(pwa_browser, "customer_checkout_url_from_cart", None)
        self.assertTrue(callable(checkout_url), "PWA QA must validate its generated checkout target")

        class Link:
            def __init__(self, href: str, *, visible: bool = True, enabled: bool = True) -> None:
                self.href = href
                self.visible = visible
                self.enabled = enabled

            def is_displayed(self) -> bool:
                return self.visible

            def is_enabled(self) -> bool:
                return self.enabled

            def get_attribute(self, name: str) -> str | None:
                return self.href if name == "href" else None

        class Driver:
            def __init__(self, links: list[Link]) -> None:
                self.links = links

            def find_elements(self, _by: str, _selector: str) -> list[Link]:
                return self.links

        base_url = "http://localhost:18080"
        secret_url = "https://outside.invalid/checkout?token=private-token-sentinel"
        for links in (
            [],
            [Link("http://localhost:18080/checkout", visible=False)],
            [Link("http://localhost:18080/checkout", enabled=False)],
            [Link("http://localhost:18080/checkout"), Link("http://localhost:18080/checkout")],
            [Link(secret_url)],
        ):
            with self.subTest(links=len(links)):
                with patch("tests.e2e.verify_pwa_browser.By", SimpleNamespace(CSS_SELECTOR="css selector")):
                    with self.assertRaises(AssertionError) as raised:
                        checkout_url(Driver(links), base_url)
                    self.assertNotIn("private-token-sentinel", str(raised.exception))

    def test_canonical_order_cache_check_uses_final_document_not_legacy_redirect(self) -> None:
        shop_url = "http://localhost:18080"
        canonical_url = shop_url + "/checkout"
        redirect_response = {
            "url": shop_url + "/index.php?controller=order&token=private-token-sentinel",
            "status": 301,
            "headers": {"Cache-Control": "no-store"},
        }

        def response_log(url: str, headers: dict[str, str], status: int) -> dict[str, str]:
            return {
                "message": json.dumps(
                    {
                        "message": {
                            "method": "Network.responseReceived",
                            "params": {
                                "type": "Document",
                                "response": {"url": url, "status": status, "headers": headers},
                            },
                        }
                    }
                )
            }

        redirect_log = {
            "message": json.dumps(
                {
                    "message": {
                        "method": "Network.requestWillBeSent",
                        "params": {"type": "Document", "redirectResponse": redirect_response},
                    }
                }
            )
        }

        class Driver:
            def __init__(self, final_headers: dict[str, str]) -> None:
                self.entries = [
                    redirect_log,
                    response_log(canonical_url, final_headers, 200),
                ]

            def get_log(self, _log_type: str) -> list[dict[str, str]]:
                return self.entries

        observed = pwa_browser.assert_private_document_cache_headers(
            Driver({"Cache-Control": "private, no-store"}),
            canonical_url,
            shop_url,
            "authenticated order",
        )
        self.assertEqual(200, observed["status"])
        self.assertEqual("private, no-store", observed["cache_control"])

        with redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(AssertionError, "lacks Cache-Control private/no-store semantics"):
                pwa_browser.assert_private_document_cache_headers(
                    Driver({"Cache-Control": "public, max-age=3600"}),
                    canonical_url,
                    shop_url,
                    "authenticated order",
                )

    def test_pwa_order_route_qa_temporarily_opens_only_its_run_scoped_checkout(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        pwa_step = workflow.split(
            "- name: Verify Chromium PWA lifecycle and private-route cache protection", 1
        )[1].split("- name:", 1)[0]

        self.assertIn("GITHUB_RUN_ID: ${{ github.run_id }}", pwa_step)
        self.assertIn("GITHUB_RUN_ATTEMPT: ${{ github.run_attempt }}", pwa_step)
        self.assertIn('expected_project="kuranea-ci-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"', pwa_step)
        self.assertIn('[[ "$CI_COMPOSE_PROJECT_NAME" != "$expected_project" ]]', pwa_step)
        self.assertIn("tests/fixtures/ci-checkout.compose.yaml", pwa_step)
        self.assertIn("trap restore_base_checkout EXIT", pwa_step)
        self.assertLess(pwa_step.index("trap restore_base_checkout EXIT"), pwa_step.index("tests/e2e/verify_pwa_browser.py"))
        self.assertLess(pwa_step.index("ci-checkout.compose.yaml"), pwa_step.index("tests/e2e/verify_pwa_browser.py"))
        restore = pwa_step.split("restore_base_checkout() {", 1)[1].split("\n          }", 1)[0]
        self.assertIn('if [[ "$pwa_checkout_override_attempted" == 1 ]]', restore)
        self.assertIn("--force-recreate", restore)
        self.assertIn("fail-closed base checkout environment", restore)

    def test_pwa_customer_creation_requires_exact_run_scoped_ci_shop_before_chromium(self) -> None:
        main = function_source(self.source, "main")
        self.assertIn("validate_isolated_ci_target(base_url)", main)
        self.assertLess(main.index("validate_isolated_ci_target(base_url)"), main.index("run_viewport("))

        valid = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "KURANEA_ISOLATED_CI": "1",
            "GITHUB_RUN_ID": "123456789",
            "GITHUB_RUN_ATTEMPT": "2",
            "CI_COMPOSE_PROJECT_NAME": "kuranea-ci-123456789-2",
        }
        with patch.dict(os.environ, valid, clear=False):
            validate_isolated_ci_target("http://localhost:18080")
            for base_url in (
                "http://localhost:18081",
                "http://shop.example:18080",
                "https://localhost:18080",
                "http://localhost:18080/store/?target=elsewhere",
            ):
                with self.subTest(base_url=base_url), self.assertRaises(ValueError):
                    validate_isolated_ci_target(base_url)

            for key, value in (
                ("CI", "false"),
                ("GITHUB_ACTIONS", "false"),
                ("KURANEA_ISOLATED_CI", "0"),
                ("GITHUB_RUN_ID", "123x"),
                ("GITHUB_RUN_ATTEMPT", "2 "),
                ("CI_COMPOSE_PROJECT_NAME", "kuranea-ci-123456789-3"),
            ):
                with self.subTest(variable=key), patch.dict(os.environ, {key: value}), self.assertRaises(ValueError):
                    validate_isolated_ci_target("http://localhost:18080")

    def test_pwa_browser_failure_reports_safe_stage_and_path_annotation(self) -> None:
        viewport = function_source(self.source, "run_viewport")
        for stage in (
            "chrome_start",
            "network_enable",
            "storefront_navigation",
            "storefront_ready",
            "manifest",
            "service_worker_registration",
            "service_worker_update",
            "online_refresh",
            "offline_fallback",
            "customer_account_setup",
            "customer_account_route",
            "customer_cart_route",
            "customer_order_route",
            "customer_account_before_logout",
            "customer_logout",
            "guest_authentication_route",
            "guest_account_route",
            "guest_cart_route",
            "guest_order_route",
            "chrome_shutdown",
        ):
            with self.subTest(stage=stage):
                self.assertIn(stage, viewport)
        self.assertIn("::error title=ORDENOWA PWA browser QA::", viewport)
        self.assertIn("type(error).__name__", viewport)
        self.assertNotIn("str(error)", viewport)
        self.assertNotIn("{error}", viewport)
        self.assertIn("urlparse(driver.current_url).path", viewport)
        failure_handler = viewport.split("except Exception as error:", 1)[1].split("finally:", 1)[0]
        path_diagnostics = failure_handler.split("try:", 1)[1].split("error_type =", 1)[0]
        self.assertIn("except Exception:", path_diagnostics)
        self.assertIn('current_path = ""', path_diagnostics)

    def test_offline_fallback_bypasses_http_cache_and_restores_network_state(self) -> None:
        offline = function_source(self.source, "verify_offline_fallback")
        disable_cache = offline.index(
            'driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})'
        )
        offline_navigation = offline.index('driver.get(base_url + "/")')
        offline_mode = offline.index("worker_network_conditions(True)")
        worker_enable = offline.index('worker_cdp.execute("Network.enable", {}, session_id=worker_session)')
        cleanup = function_source(self.source, "restore_offline_network_state")
        finally_block = offline.split("    finally:\n", 1)[1]

        self.assertLess(disable_cache, offline_mode)
        self.assertLess(worker_enable, offline_mode)
        self.assertLess(offline_mode, offline_navigation)
        self.assertIn("restore_offline_network_state(driver, primary_error, worker_session, worker_cdp)", finally_block)
        self.assertIn("worker_network_conditions(False)", cleanup)
        self.assertLess(
            cleanup.index("worker_network_conditions(False)"),
            cleanup.index("for command, parameters in resets:"),
        )
        self.assertIn("for command, parameters in resets:", cleanup)
        self.assertIn("driver.execute_cdp_cmd(command, parameters)", cleanup)
        self.assertIn('worker_cdp.execute("Target.detachFromTarget", {"sessionId": worker_session})', cleanup)
        self.assertIn("worker_cdp.close()", cleanup)
        self.assertIn("cleanup_errors.append(error)", cleanup)
        self.assertIn("if primary_error is not None:", cleanup)
        self.assertIn("raise cleanup_errors[0]", cleanup)
        self.assertIn('assert_empty_cache_storage(driver, "offline navigation")', offline)

        self.assertIn("primary_error: BaseException | None = None", offline)
        self.assertIn("except BaseException as error:", offline)
        self.assertIn("primary_error = error", offline)
        self.assertIn("restore_offline_network_state(driver, primary_error, worker_session, worker_cdp)", offline)

    def test_offline_failure_annotation_distinguishes_fallback_cache_and_recovery(self) -> None:
        offline = function_source(self.source, "verify_offline_fallback")
        viewport = function_source(self.source, "run_viewport")
        for stage in (
            "offline_devtools_enable",
            "offline_cache_bypass",
            "offline_network_emulation",
            "offline_devtools_connect",
            "offline_worker_target_list",
            "offline_worker_target_attach",
            "offline_worker_network_emulation",
            "offline_fallback_navigation",
            "offline_fallback_content",
            "offline_cache_storage",
            "offline_state_restore",
            "online_recovery_navigation",
            "online_recovery_content",
        ):
            with self.subTest(stage=stage):
                self.assertIn(f'set_stage("{stage}")', offline)
        ordered_stages = (
            "offline_devtools_enable",
            "offline_cache_bypass",
            "offline_network_emulation",
            "offline_devtools_connect",
            "offline_worker_target_list",
            "offline_worker_target_attach",
            "offline_worker_network_emulation",
            "offline_fallback_navigation",
            "offline_fallback_content",
            "offline_cache_storage",
        )
        for earlier, later in zip(ordered_stages, ordered_stages[1:]):
            self.assertLess(offline.index(f'set_stage("{earlier}")'), offline.index(f'set_stage("{later}")'))
        self.assertIn("assert_offline_fallback_content(driver, locale)", offline)
        self.assertLess(
            offline.index('set_stage("offline_cache_storage")'),
            offline.index('assert_empty_cache_storage(driver, "offline navigation")'),
        )
        self.assertIn("nonlocal stage", viewport)
        self.assertIn("diagnostic_code", viewport)
        self.assertIn("diagnostic=", viewport)
        offline_call = viewport.split("verify_offline_fallback(", 1)[1].split("\n        )", 1)[0]
        self.assertIn("update_offline_stage", offline_call)

    def test_pwa_registration_clicks_use_native_center_visibility_guard(self) -> None:
        customer = function_source(self.source, "create_session_customer")
        viewport = function_source(self.source, "run_viewport")

        self.assertIn("click_native_when_unobstructed(driver, label)", customer)
        self.assertIn("click_native_when_unobstructed(driver, submit)", customer)
        for stage in (
            "customer_registration_required_consent",
            "customer_registration_submit",
            "customer_registration_success_wait",
        ):
            with self.subTest(stage=stage):
                self.assertIn(f'"{stage}"', customer)
        self.assertIn("set_stage=update_offline_stage", viewport)

    def test_offline_cleanup_attempts_both_resets_and_preserves_primary_failure(self) -> None:
        class FakeDriver:
            def __init__(self) -> None:
                self.commands: list[str] = []

            def execute_cdp_cmd(self, command: str, _params: dict[str, object]) -> None:
                self.commands.append(command)
                if command == "Network.emulateNetworkConditions":
                    raise RuntimeError("sensitive cleanup details")

        driver = FakeDriver()
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            restore_offline_network_state(driver, AssertionError("offline assertion failed"))

        self.assertEqual(
            driver.commands,
            ["Network.emulateNetworkConditions", "Network.setCacheDisabled"],
        )
        self.assertIn("RuntimeError", stderr.getvalue())
        self.assertNotIn("sensitive cleanup details", stderr.getvalue())

    def test_offline_cleanup_failure_fails_when_there_is_no_primary_failure(self) -> None:
        class FakeDriver:
            def __init__(self) -> None:
                self.commands: list[str] = []

            def execute_cdp_cmd(self, command: str, _params: dict[str, object]) -> None:
                self.commands.append(command)
                if command == "Network.setCacheDisabled":
                    raise RuntimeError("offline cleanup failed")

        driver = FakeDriver()
        with self.assertRaisesRegex(RuntimeError, "offline cleanup failed"):
            restore_offline_network_state(driver, None)

        self.assertEqual(
            driver.commands,
            ["Network.emulateNetworkConditions", "Network.setCacheDisabled"],
        )


if __name__ == "__main__":
    unittest.main()
