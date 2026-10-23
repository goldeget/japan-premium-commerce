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

from tests.e2e.verify_pwa_browser import (
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
const self = {
  addEventListener: (name, callback) => { listeners[name] = callback; },
  clients: {claim: async () => {}},
  navigator: {language: 'en-US'},
  skipWaiting: async () => {},
};
const fetch = async () => {
  fetchCalls += 1;
  if (config.offline) throw new TypeError('offline');
  return new Response('online response', {status: 200});
};
const caches = {open: async () => { cacheOpenCalls += 1; throw new Error('cache must not be opened'); }};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {self, fetch, Response, caches});
const request = {
  method: config.method,
  mode: config.mode,
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
    cacheControl: response?.headers.get('Cache-Control') ?? null,
    body,
    fetchCalls,
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
        self.assertEqual(0, result["cacheOpenCalls"])

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

            def execute_cdp_cmd(self, command, parameters):
                self.commands.append(command)
                if command == "Target.getTargets":
                    return {"targetInfos": [
                        {"type": "service_worker", "url": "http://other.invalid/sw.js", "targetId": "other"},
                        {"type": "service_worker", "url": "http://localhost:18080/sw.js", "targetId": "shop"},
                    ]}
                if command == "Target.attachToTarget":
                    self.attached_target = parameters["targetId"]
                    return {"sessionId": "shop-worker"}
                if command == "Target.sendMessageToTarget":
                    if parameters["sessionId"] != "shop-worker":
                        raise AssertionError("wrong worker session")
                    message = json.loads(parameters["message"])
                    if message["method"] == "Network.emulateNetworkConditions":
                        self.worker_offline = message["params"]["offline"]
                        self.worker_states.append(self.worker_offline)
                return {}

            def get(self, _url):
                self.body = "You are offline" if self.worker_offline else "ORDENOWA"

            def find_element(self, *_args):
                return SimpleNamespace(text=self.body)

            def save_screenshot(self, _path):
                return True

        driver = Driver()
        with patch("tests.e2e.verify_pwa_browser.By", SimpleNamespace(TAG_NAME="tag name")), patch(
            "tests.e2e.verify_pwa_browser.assert_empty_cache_storage"
        ):
            verify_offline_fallback(driver, "http://localhost:18080", Path("unused.png"), lambda _stage: None)

        self.assertEqual("shop", driver.attached_target)
        self.assertEqual([True, False], driver.worker_states)
        self.assertFalse(driver.worker_offline)
        self.assertIn("Target.detachFromTarget", driver.commands)

    def test_worker_reset_failure_still_restores_page_and_detaches(self) -> None:
        class Driver:
            def __init__(self) -> None:
                self.commands: list[str] = []

            def execute_cdp_cmd(self, command, _parameters):
                self.commands.append(command)
                if command == "Target.sendMessageToTarget":
                    raise RuntimeError("worker reset failed")

        driver = Driver()
        with redirect_stderr(io.StringIO()):
            restore_offline_network_state(driver, AssertionError("original failure"), "shop-worker")
        self.assertEqual([
            "Target.sendMessageToTarget",
            "Network.emulateNetworkConditions",
            "Network.setCacheDisabled",
            "Target.detachFromTarget",
        ], driver.commands)


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
        identity_check = function_source(self.source, "exposes_test_identity")
        viewport = function_source(self.source, "run_viewport")

        self.assertIn('wait_visible(driver, "#login-form input[name=\'email\']")', logout)
        self.assertIn("for _ in range(2):", logout)
        self.assertGreaterEqual(logout.count("exposes_test_identity(body_text, first_name, last_name, email)"), 2)
        self.assertIn("for name in (first_name, last_name):", identity_check)
        self.assertIn('"Pwa",\n                "Session",', viewport)

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
        offline_mode = offline.index('"offline": True')
        cleanup = function_source(self.source, "restore_offline_network_state")
        finally_block = offline.split("    finally:\n", 1)[1]

        self.assertLess(disable_cache, offline_mode)
        self.assertLess(offline_mode, offline_navigation)
        self.assertIn("restore_offline_network_state(driver, primary_error, worker_session)", finally_block)
        self.assertIn('"offline": False', cleanup)
        restore_cache = cleanup.index('"Network.setCacheDisabled", {"cacheDisabled": False}')
        restore_network = cleanup.index('"offline": False')
        self.assertLess(restore_network, restore_cache)
        self.assertIn("for command, parameters in resets:", cleanup)
        self.assertIn("driver.execute_cdp_cmd(command, parameters)", cleanup)
        self.assertIn("cleanup_errors.append(error)", cleanup)
        self.assertIn("if primary_error is not None:", cleanup)
        self.assertIn("raise cleanup_errors[0]", cleanup)
        self.assertIn('assert_empty_cache_storage(driver, "offline navigation")', offline)

        self.assertIn("primary_error: BaseException | None = None", offline)
        self.assertIn("except BaseException as error:", offline)
        self.assertIn("primary_error = error", offline)
        self.assertIn("restore_offline_network_state(driver, primary_error, worker_session)", offline)

    def test_offline_failure_annotation_distinguishes_fallback_cache_and_recovery(self) -> None:
        offline = function_source(self.source, "verify_offline_fallback")
        viewport = function_source(self.source, "run_viewport")
        for stage in (
            "offline_devtools_enable",
            "offline_cache_bypass",
            "offline_network_emulation",
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
            "offline_fallback_navigation",
            "offline_fallback_content",
            "offline_cache_storage",
        )
        for earlier, later in zip(ordered_stages, ordered_stages[1:]):
            self.assertLess(offline.index(f'set_stage("{earlier}")'), offline.index(f'set_stage("{later}")'))
        self.assertLess(
            offline.index('set_stage("offline_fallback_content")'),
            offline.index("if not any(text in body"),
        )
        self.assertLess(
            offline.index('set_stage("offline_cache_storage")'),
            offline.index('assert_empty_cache_storage(driver, "offline navigation")'),
        )
        self.assertIn("nonlocal stage", viewport)
        offline_call = viewport.split("verify_offline_fallback(", 1)[1].split("\n        )", 1)[0]
        self.assertIn("update_offline_stage", offline_call)

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
