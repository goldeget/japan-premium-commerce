from pathlib import Path
import os
import json
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
SUBSCRIBER = ROOT / "modules" / "kuraneabackoffice" / "src" / "AdminFacebookTransportExceptionSubscriber.php"
TEMPLATE = ROOT / "modules" / "kuraneabackoffice" / "views" / "templates" / "admin" / "facebook_transport_error.html.twig"
PROBE = Path(__file__).resolve().parent / "native_facebook_transport_fallback.php"
CLASS_LOAD_TEST = Path(__file__).resolve().parent / "test_admin_facebook_subscriber_class_load.php"
MODULE_INVENTORY_TEST = Path(__file__).resolve().parent / "facebook_module_inventory_behavior.php"
SERVICE_FRAGMENT = ROOT / "modules/kuraneabackoffice/config/services.yml"
EVIDENCE = ROOT / "docs/evidence/native-facebook-transport-source-2026-10-29.md"


class NativeFacebookTransportFallbackContractTests(unittest.TestCase):
    def test_real_php_subscriber_load_and_project_module_metadata(self):
        php = os.environ.get('ORDENOWA_TEST_PHP') or shutil.which('php')
        if not php:
            self.skipTest('PHP required for class-load and module regressions')
        for script in (CLASS_LOAD_TEST, MODULE_INVENTORY_TEST):
            with self.subTest(script=script.name):
                result = subprocess.run([php, '-n', str(script)], capture_output=True, text=True, timeout=20)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_guard_failure_reports_symbolic_class_without_regex_warning(self):
        php = os.environ.get('ORDENOWA_TEST_PHP') or shutil.which('php')
        if not php:
            self.skipTest('PHP required for guard-failure regression')
        environment = os.environ.copy()
        environment['CI'] = 'false'
        result = subprocess.run([php, '-n', str(PROBE)], env=environment,
                                capture_output=True, text=True, timeout=20)
        self.assertNotEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload['passed'])
        self.assertEqual(payload['exception_class'], 'RuntimeException')
        self.assertEqual(payload['failed_stage'], 'ci_guard')
        self.assertNotIn('preg_match', result.stderr + result.stdout)

    @classmethod
    def setUpClass(cls):
        cls.subscriber = SUBSCRIBER.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.probe = PROBE.read_text(encoding="utf-8")
        cls.services = SERVICE_FRAGMENT.read_text(encoding="utf-8")
        cls.evidence = EVIDENCE.read_text(encoding="utf-8")

    def test_exception_fallback_has_narrow_authenticated_route_and_source_gates(self):
        self.assertIn("use Symfony\\Component\\EventDispatcher\\EventSubscriberInterface;", self.subscriber)
        self.assertNotIn("use Symfony\\Component\\HttpKernel\\EventSubscriberInterface;", self.subscriber)
        self.assertIn("isAuthenticatedFacebookReadForIsolatedTest(Request $request)", self.subscriber)
        self.assertTrue(CLASS_LOAD_TEST.is_file())
        self.assertTrue(MODULE_INVENTORY_TEST.is_file())
        for required in (
            "KernelEvents::EXCEPTION",
            "isMainRequest()",
            "admin_legacy_controller_route",
            "AdminPsfacebookModuleController",
            "AdminPsfacebookModule",
            "_legacy_controller_action",
            "_legacy_controller_is_module",
            "_anonymous_controller",
            "in_array('ps_facebook', $this->activeModules, true)",
            "IS_AUTHENTICATED_FULLY",
            "isGranted(self::FACEBOOK_ACTION, self::FACEBOOK_CONTROLLER_NAME)",
            "get_class($failure) !== RuntimeException::class",
            "cURL error",
            "classes' . DIRECTORY_SEPARATOR . 'Http' . DIRECTORY_SEPARATOR . 'HttpClient.php",
            "PrestaShop\\\\Module\\\\PrestashopFacebook\\\\Http\\\\HttpClient",
            "['get', 'request']",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.subscriber)

    def test_response_uses_fixed_project_template_and_does_not_expose_exception(self):
        self.assertIn("$this->twig->render(self::TEMPLATE, [", self.subscriber)
        self.assertIn("@Modules/kuraneabackoffice/views/templates/admin/facebook_transport_error.html.twig", self.subscriber)
        self.assertIn("Response::HTTP_SERVICE_UNAVAILABLE", self.subscriber)
        self.assertIn("Cache-Control", self.subscriber)
        self.assertIn("X-Robots-Tag", self.subscriber)
        render_start = self.subscriber.index("$this->twig->render")
        render_end = self.subscriber.index("]);", render_start)
        self.assertNotIn("getMessage", self.subscriber[render_start:render_end])
        self.assertIn("@PrestaShop/Admin/layout.html.twig", self.template)
        self.assertIn("Facebook 계정 연결을 일시적으로 사용할 수 없습니다", self.template)
        self.assertIn("Facebook 서비스에 연결하는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.", self.template)
        self.assertNotIn("cURL", self.template)
        self.assertNotIn("billing-api", self.template)

    def test_native_probe_uses_authenticated_kernel_route_and_bind_only_transport(self):
        for required in (
            "KernelBrowser($kernel",
            "form[@id=\"login_form\"]",
            "getAdminLink('AdminPsfacebookModule', true)",
            "admin_legacy_controller_route",
            "isAuthenticatedFacebookReadForIsolatedTest($request)",
            "isKnownFacebookRequest",
            "native_facebook_request_route_attribute_mismatch",
            "native_facebook_target_controller_event_in_disabled_mode",
            "known_facebook_request_controller_events",
            "beforeUnauthenticatedTargetEvents",
            "native_authenticated_read_gate_verified",
            "$authenticatedReadGatePasses === 3",
            "nativeSessionCsrfProbeCount === 1",
            "nativeSessionCsrfVerified",
            "getCurrentRequest() !== $event->getRequest()",
            "AdminPostTokenValidator::class",
            "valid($nativeToken)",
            "!$validator->valid(str_repeat('a', 64))",
            "'archive_sha256' => $archiveSha256",
            "'archive_required' => true",
            "Module::getInstanceByName($name)",
            "project_module_instance_mismatch",
            "native_authenticated_read_gate_verified",
            "STREAM_SERVER_BIND",
            "STREAM_SERVER_LISTEN is intentionally absent",
            "https://127.0.0.1:' . $port",
            "curl_transport",
            "generic_facebook_runtime",
            "facebook_access_denied",
            "other_route_runtime",
            "unauthenticated_facebook_negative",
            "new $httpClientClass('https://127.0.0.1:' . $port)",
            "HttpClient.php",
            "1.38.19",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.probe)
        self.assertNotIn("->initContent(", self.probe)
        self.assertNotIn("PsAccountsInstaller", self.probe)
        self.assertNotIn("getMessage()", self.probe)
        self.assertNotIn("echo $facebookToken", self.probe)
        self.assertNotIn("$container->get('security.helper')", self.probe)

    def test_service_and_source_note_preserve_boundaries(self):
        self.assertIn("Kuranea\\Backoffice\\AdminFacebookTransportExceptionSubscriber", self.services)
        self.assertIn("@security.helper", self.services)
        self.assertIn("%prestashop.active_modules%", self.services)
        self.assertIn("must therefore not be invoked", self.evidence)
        self.assertIn("STREAM_SERVER_BIND", self.evidence)
        self.assertIn("database/session/audit work", self.evidence)
        self.assertIn("kernel/configuration bootstrap", self.evidence)


if __name__ == "__main__":
    unittest.main()
