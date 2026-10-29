from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).parent
PHP = (ROOT / "native_facebook_transport_fallback.php").read_text(encoding="utf-8")
RUNNER = (ROOT / "run_native_facebook_cases.sh").read_text(encoding="utf-8")


class NativeFacebookHttpCasesContractTests(unittest.TestCase):
    def test_only_five_fixed_case_names_are_accepted(self) -> None:
        expected = {
            "unauthenticated", "other_route", "generic_facebook", "access_denied", "curl_transport"
        }
        start = PHP.index("$caseModes = [")
        end = PHP.index("];", start)
        mapping = set(re.findall(r"'([a-z_]+)'\s*=>", PHP[start:end]))
        self.assertEqual(mapping, expected)
        self.assertIn("array_key_exists($caseName, $caseModes)", PHP)
        self.assertEqual(len(re.findall(r"(?m)^\$mode\s*=", PHP)), 1)

    def test_real_login_precedes_vendor_and_config_bootstrap(self) -> None:
        authenticate = PHP.index("NativeAdminHttpLogin::authenticate(")
        loader = PHP.index("require_once $baseVendorAutoload")
        config = PHP.index("require_once $shopRoot . '/config/config.inc.php'")
        self.assertLess(authenticate, loader)
        self.assertLess(authenticate, config)
        self.assertIn("NativeAdminHttpLogin::globalsForUri", PHP)
        self.assertIn("NativeAdminHttpLogin::installInBrowserKit($browser->getCookieJar(), $nativeCookies)", PHP)
        self.assertIn("$caseName !== 'unauthenticated'", PHP)
        self.assertIn("$_COOKIE = [];", PHP)

    def test_one_target_get_and_no_browserkit_login_or_case_loop(self) -> None:
        self.assertEqual(PHP.count("$browser->request("), 1)
        self.assertIn("$browser->request('GET', $requestUri);", PHP)
        self.assertNotRegex(PHP, r"\$browser->request\(\s*['\"]POST")
        self.assertNotIn("foreach ($caseModes", PHP)
        self.assertNotIn("$unauthenticatedBrowser", PHP)
        self.assertIn("$browserRequests = $browser->nativeRequestCount;", PHP)

    def test_positive_snapshot_is_private_and_written_after_proof(self) -> None:
        snapshot = PHP.index("persistNativeAdminSnapshot('facebook'")
        csrf = PHP.index("$nativeSessionCsrfVerified && $nativeSessionCsrfProbeCount === 1")
        safe_response = PHP.index("$caseChecks['facebook_fallback_response_safe']")
        self.assertGreater(snapshot, csrf)
        self.assertGreater(snapshot, safe_response)
        self.assertIn("if ($caseName === 'curl_transport')", PHP)
        self.assertIn("$snapshotHash = hash('sha256', $body);", PHP)
        self.assertNotIn("$nativeCookies' =>", PHP)
        self.assertNotIn("'facebookToken' =>", PHP)

    def test_loopback_transport_is_bound_only_and_never_calls_vendor_action(self) -> None:
        self.assertIn("STREAM_SERVER_BIND", PHP)
        uncommented = re.sub(r"(?m)^\s*//.*$", "", PHP)
        self.assertNotIn("STREAM_SERVER_LISTEN", uncommented)
        self.assertIn("new $httpClientClass('https://127.0.0.1:' . $port)", PHP)
        self.assertIn("$client->get('/')", PHP)
        self.assertIn("'facebook_vendor_initContent_called_by_fixture' => false", PHP)
        self.assertNotIn("Shop::setContext", PHP)
        self.assertNotIn("loginUser(", PHP)

    def test_host_runner_executes_each_case_synchronously_to_private_files(self) -> None:
        for case in ("unauthenticated", "other_route", "generic_facebook", "access_denied", "curl_transport"):
            self.assertIn(case, RUNNER)
        self.assertIn("compose exec -T", RUNNER)
        self.assertIn("-e \"ORDENOWA_FACEBOOK_CASE=$case_name\"", RUNNER)
        self.assertIn('if [[ "$case_name" != unauthenticated ]]', RUNNER)
        self.assertIn("auth_env=(-e ADMIN_MAIL -e ADMIN_PASSWD)", RUNNER)
        self.assertIn('>"$raw" 2>"$stderr"', RUNNER)
        self.assertIn("safe_native_facebook_cases.py", RUNNER)
        self.assertIn("mkdir -m 0700", RUNNER)
        self.assertNotIn("curl_transport.private.json", RUNNER)
        self.assertNotIn("QA_ARTIFACT_DIR/$case_name", RUNNER)


if __name__ == "__main__":
    unittest.main()
