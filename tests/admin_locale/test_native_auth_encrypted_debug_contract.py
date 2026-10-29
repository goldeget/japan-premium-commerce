from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
LOGIN = Path(__file__).with_name("native_admin_http_login.php").read_text(encoding="utf-8")
MBO = Path(__file__).with_name("native_mbo_error_authenticated.php").read_text(encoding="utf-8")
FACEBOOK = Path(__file__).with_name("native_facebook_transport_fallback.php").read_text(encoding="utf-8")
SNAPSHOT = Path(__file__).with_name("native_admin_private_snapshot.php").read_text(encoding="utf-8")
RUNNER = Path(__file__).with_name("ci_authenticated_mbo.sh").read_text(encoding="utf-8")
FACEBOOK_RUNNER = Path(__file__).with_name("run_native_facebook_cases.sh").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/procurement-platform.yml").read_text(encoding="utf-8")
RECIPIENT = Path(__file__).with_name("qa-debug-recipient.pem").read_text(encoding="ascii")


class NativeAuthEncryptedDebugContractTests(unittest.TestCase):
    def test_native_login_retains_raw_http_response_only_in_resettable_process_memory(self):
        self.assertIn("private static ?array $privateLastHttpResponse = null", LOGIN)
        self.assertIn("public static function privateLastHttpResponse(): ?array", LOGIN)
        self.assertIn("self::$privateLastHttpResponse = null;", LOGIN)
        self.assertIn("self::rememberPrivateResponse($uri, $response)", LOGIN)
        self.assertIn("self::rememberPrivateResponse($postUri, $postResponse)", LOGIN)
        self.assertIn("self::rememberPrivateResponse($uri, $response)", LOGIN)
        self.assertNotIn("privateLastHttpResponse' =>", LOGIN)

    def test_failure_capture_is_guarded_and_contains_exact_raw_bytes_only_inside_envelope(self):
        self.assertIn("$isolatedCiGuardPassed && $stage === 'native_login_post_redirects'", MBO)
        self.assertIn("'scope' => 'mbo_native_auth_landing_failure'", MBO)
        self.assertIn("'body_base64' => base64_encode($privateResponse['body'])", MBO)
        self.assertIn("$isolatedCiGuardPassed && $caseName === 'unauthenticated'", FACEBOOK)
        self.assertIn("$stage === 'case_specific_semantic_assertions'", FACEBOOK)
        self.assertIn("'scope' => 'facebook_unauthenticated_native_target_failure'", FACEBOOK)
        self.assertIn("'body_base64' => base64_encode($body)", FACEBOOK)
        self.assertNotIn("strlen($body) >= 100", FACEBOOK)
        self.assertNotIn("strlen($privateResponse['body']) >= 100", MBO)
        self.assertIn("['mbo', 'facebook', 'mbo-auth-landing', 'facebook-unauthenticated']", SNAPSHOT)

    def test_runner_encrypts_only_two_named_captures_and_deletes_runner_plaintext(self):
        self.assertIn("openssl cms -encrypt -aes-256-gcm -binary -outform DER", RUNNER)
        self.assertIn("0C:8E:7D:03:B9:FE:49:A0:88:01:C7:0F:5C:06:16:CA:20:31:9F:1E:B2:6B:DB:AA:FD:CD:D8:59:92:D2:7C:0D", RUNNER)
        self.assertIn('rm -f -- "$host_plain"', RUNNER)
        self.assertIn("mbo-auth-landing-encrypted.cms", RUNNER)
        self.assertIn("facebook-unauthenticated-encrypted.cms", RUNNER)
        self.assertIn("native_admin_encrypt_private_capture facebook-unauthenticated", FACEBOOK_RUNNER)
        self.assertNotIn("cms -decrypt", RUNNER.lower())
        self.assertNotIn("private-key", RUNNER.lower())

    def test_workflow_exposes_only_fixed_public_recipient_and_encrypted_glob(self):
        self.assertIn("ORDENOWA_NATIVE_AUTH_DEBUG_RECIPIENT: ${{ github.workspace }}/tests/admin_locale/qa-debug-recipient.pem", WORKFLOW)
        self.assertIn("${{ runner.temp }}/procurement-safe-artifacts/*-encrypted.cms", WORKFLOW)
        self.assertNotIn("procurement-safe-artifacts/*.html", WORKFLOW)
        self.assertIn("BEGIN CERTIFICATE", RECIPIENT)
        self.assertNotIn("PRIVATE KEY", RECIPIENT)


if __name__ == "__main__":
    unittest.main()
