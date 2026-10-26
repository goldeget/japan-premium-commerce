from __future__ import annotations

import hashlib
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneabackoffice"
NAMESPACE = {"x": "urn:oasis:names:tc:xliff:document:1.2"}


def translations(path: Path) -> dict[str, str]:
    root = ET.parse(path).getroot()
    return {
        unit.findtext("x:source", namespaces=NAMESPACE): unit.findtext(
            "x:target", namespaces=NAMESPACE
        )
        for unit in root.findall(".//x:trans-unit", NAMESPACE)
    }


class AdminLocaleOverlayContractTests(unittest.TestCase):
    def test_every_back_office_route_uses_the_korean_admin_locale(self) -> None:
        path = MODULE / "src" / "AdminLocaleSubscriber.php"
        source = path.read_text(encoding="utf-8")

        self.assertIn("str_starts_with($route, 'admin_')", source)
        self.assertIn("applyKoreanAdminLocale($request)", source)
        locale_handler = source.split("private function applyKoreanAdminLocale(", 1)[1]
        self.assertIn("setDefaultLocale(self::KOREAN_LOCALE)", locale_handler)
        self.assertIn("setLocale(self::KOREAN_LOCALE)", locale_handler)
        self.assertIn("setLanguageId($koreanLanguage->getId())", locale_handler)
        readme = (MODULE / "README.md").read_text(encoding="utf-8")
        self.assertIn("every `admin_` Back Office route", readme)
        self.assertNotIn("Other Back Office pages keep the employee's configured language", readme)

    def test_english_staff_fixture_sees_korean_settings_and_dashboard_in_chromium(self) -> None:
        fixture = (ROOT / "tests" / "business_profile" / "seed_security_fixtures.php").read_text(encoding="utf-8")
        browser = (ROOT / "tests" / "e2e" / "verify_admin_security_browser.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")

        self.assertIn("Language::getIdByIso('en', true)", fixture)
        self.assertIn("Korean locale", browser)
        locale_assertion = browser.split("def assert_korean_admin_locale(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('driver.find_element(By.TAG_NAME, "html").get_attribute("lang")', locale_assertion)
        self.assertTrue("is_korean_admin_language(document_locale)" in locale_assertion, "the browser QA must validate Korean as a language tag, not require the locale's region suffix")
        self.assertIn("AdminOrders", browser)
        self.assertIn("storefront_stays_japanese_after_admin_locale_test", browser)
        self.assertIn("admin-security-view-only-settings-korean.png", workflow)
        self.assertIn("admin-security-view-only-dashboard-korean.png", workflow)
        self.assertIn("admin-security-view-only-orders-korean.png", workflow)

    def test_legacy_korean_iso_tag_is_accepted_without_accepting_other_languages(self) -> None:
        from tests.e2e.shipping_admin_routes import is_korean_admin_language

        browser = (ROOT / "tests" / "e2e" / "verify_admin_security_browser.py").read_text(encoding="utf-8")
        self.assertTrue("from shipping_admin_routes import is_korean_admin_language" in browser, "the legacy browser check must share the supported Korean-tag parser")
        locale_assertion = browser.split("def assert_korean_admin_locale(", 1)[1].split("\ndef ", 1)[0]
        self.assertTrue("is_korean_admin_language(document_locale)" in locale_assertion, "the security browser check must accept PrestaShop's legacy `ko` tag")

        for language, expected in (("ko", True), ("ko-KR", True), ("KO-kr", True), ("en", False), ("fr-FR", False), ("", False)):
            with self.subTest(language=language):
                self.assertEqual(expected, is_korean_admin_language(language))

    def test_view_only_profile_locale_failure_reports_exact_render_boundary(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_admin_security_browser.py").read_text(encoding="utf-8")

        settings_check = browser.split('stage = "view_only_employee_settings_route"', 1)[1].split(
            'stage = "view_only_employee_dashboard_korean_locale"', 1
        )[0]
        form_stage = 'stage = "view_only_employee_settings_form_visible"'
        label_stage = 'stage = "view_only_employee_settings_korean_label"'
        locale_stage = 'stage = "view_only_employee_settings_document_locale"'
        self.assertIn(form_stage, settings_check)
        self.assertIn(label_stage, settings_check)
        self.assertIn(locale_stage, settings_check)
        self.assertLess(settings_check.index(form_stage), settings_check.index(label_stage))
        self.assertLess(settings_check.index(label_stage), settings_check.index(locale_stage))
        self.assertIn('safe_fields.append(f"profile_locale={diagnostic_locale_flags}")', browser)
        self.assertIn('r"korean=false"', browser)

    def test_anonymous_login_uses_korean_admin_language_context(self) -> None:
        path = MODULE / "src" / "AdminLocaleSubscriber.php"
        self.assertTrue(path.is_file(), "missing request-scoped locale subscriber")
        source = path.read_text()

        self.assertIn("str_starts_with($route, 'admin_')", source)
        self.assertIn("ko-KR", source)
        self.assertIn("setDefaultLocale", source)
        self.assertIn("setLocale", source)
        self.assertIn("LanguageContextBuilder", source)
        self.assertIn("setLanguageId", source)
        self.assertIn("getOneByLocaleOrIsoCode", source)
        self.assertIn("PRIORITY = LanguageContextSubscriber::KERNEL_REQUEST_PRIORITY - 1", source)

    def test_all_legacy_module_admin_headers_use_korean_context_language(self) -> None:
        controller_paths = (
            ROOT / "modules" / "kuraneabusinessprofile" / "controllers" / "admin" / "AdminBusinessProfileController.php",
            ROOT / "modules" / "kuraneabusinessprofile" / "controllers" / "admin" / "AdminBusinessProfileBanksController.php",
            ROOT / "modules" / "kuraneacatalog" / "controllers" / "admin" / "AdminOrdenowaProductManagerController.php",
            ROOT / "modules" / "kuraneacatalog" / "controllers" / "admin" / "AdminKuraneaCatalogReviewController.php",
        )
        language_assignment = "$this->context->language = new Language($koreanLanguageId);"
        for controller_path in controller_paths:
            with self.subTest(controller=controller_path.name):
                self.assertTrue(controller_path.is_file(), f"missing legacy Back Office controller: {controller_path}")
                controller = controller_path.read_text(encoding="utf-8")
                self.assertIn("extends ModuleAdminController", controller)
                self.assertTrue(
                    "public function initHeader()" in controller,
                    f"missing Korean legacy header override: {controller_path}",
                )
                init_header = controller.split("public function initHeader()", 1)[1].split(
                    "\n    public function initContent()", 1
                )[0]
                self.assertTrue(
                    "Language::getIdByIso('ko', true)" in init_header,
                    f"missing Korean language lookup: {controller_path}",
                )
                self.assertTrue(language_assignment in init_header, f"missing context language assignment: {controller_path}")
                self.assertLess(
                    init_header.index(language_assignment),
                    init_header.index("parent::initHeader();"),
                    f"language assignment must precede the PrestaShop header: {controller_path}",
                )

    def test_admin_browser_fixture_uses_english_employee_for_legacy_locale_routes(self) -> None:
        fixture = ROOT / "tests" / "business_profile" / "seed_security_fixtures.php"
        self.assertTrue(fixture.is_file(), "missing isolated admin browser fixture")
        source = fixture.read_text(encoding="utf-8")
        self.assertIn("$admin->id_lang = $englishLanguageId;", source)
        self.assertIn("$admin->update()", source)

    def test_security_fixture_changes_only_the_primary_ci_admin_language(self) -> None:
        fixture = ROOT / "tests" / "business_profile" / "seed_security_fixtures.php"
        source = fixture.read_text(encoding="utf-8")
        admin_load = source.index("getByEmail($adminEmail)")
        primary_admin_guard = source.index("securityFixtureRequire((int) $admin->id === 1", admin_load)
        language_change = source.index("$admin->id_lang = $englishLanguageId;")

        self.assertLess(admin_load, primary_admin_guard)
        self.assertLess(primary_admin_guard, language_change)

    def test_fixture_cleanup_continues_if_primary_admin_language_restore_throws(self) -> None:
        fixture = ROOT / "tests" / "business_profile" / "seed_security_fixtures.php"
        source = fixture.read_text(encoding="utf-8")
        catch_block = source.split("} catch (Throwable $exception) {", 1)[1]

        self.assertIn("catch (Throwable $restoreException)", catch_block)
        self.assertLess(catch_block.index("catch (Throwable $restoreException)"), catch_block.index("foreach ($customers as $customer)"))
        self.assertIn("throw $exception;", catch_block)

    def test_admin_response_sets_korean_lang_on_legacy_symfony_shell(self) -> None:
        source = (MODULE / "src" / "AdminLocaleSubscriber.php").read_text(encoding="utf-8")
        self.assertIn("public function onKernelResponse(ResponseEvent $event)", source)
        subscribed_events = source.split("public static function getSubscribedEvents()", 1)[1].split(
            "public function onKernelRequest", 1
        )[0]
        response_handler = source.split("public function onKernelResponse(", 1)[1].split(
            "\n    private function", 1
        )[0]

        self.assertIn("KernelEvents::RESPONSE", subscribed_events)
        self.assertRegex(
            subscribed_events,
            r"KernelEvents::RESPONSE\s*=>\s*\['onKernelResponse',\s*-\d+\]",
            "the response listener must run after Symfony prepares the response headers",
        )
        self.assertIn("$mediaType !== 'text/html'", response_handler)
        self.assertIn("explode(';', $contentType, 2)", response_handler)
        for marker in (
            "$event->isMainRequest()",
            "str_starts_with($route, 'admin_')",
            "self::KOREAN_LOCALE",
            "setContent(",
            "Content-Length",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, response_handler)

    def test_response_localization_targets_the_document_root(self) -> None:
        source = (MODULE / "src" / "AdminLocaleSubscriber.php").read_text(encoding="utf-8")
        response_handler = source.split("public function onKernelResponse(", 1)[1].split(
            "\n    private function", 1
        )[0]
        diagnostic = source.split("private static function diagnosticLanguageCategoryFromContent(", 1)[1].split(
            "\n    private static function", 1
        )[0]

        self.assertIn("use Kuranea\\Backoffice\\AdminDocumentLanguage;", source)
        self.assertIn("AdminDocumentLanguage::rootTag($content)", response_handler)
        self.assertIn(
            "AdminDocumentLanguage::setRootLocale($content, self::KOREAN_LOCALE)",
            response_handler,
        )
        self.assertIn("AdminDocumentLanguage::rootTag($content)", diagnostic)
        self.assertNotIn("preg_replace_callback(\n            '/<html\\b", response_handler)

    def test_legacy_shell_locale_failure_has_opt_in_safe_response_diagnostics(self) -> None:
        subscriber = (MODULE / "src" / "AdminLocaleSubscriber.php").read_text(encoding="utf-8")
        browser = (ROOT / "tests" / "e2e" / "verify_admin_security_browser.py").read_text(encoding="utf-8")
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

        self.assertIn("X-ORDENOWA-ADMIN-LOCALE-DIAGNOSTIC", subscriber)
        self.assertIn("$request->headers->get('X-ORDENOWA-ADMIN-LOCALE-DIAGNOSTIC') === '1'", subscriber)
        self.assertIn("$controllerQueryValue === 'AdminBusinessProfile'", subscriber)
        self.assertIn("self::isIsolatedCiDiagnosticRequest($request)", subscriber)
        for guard in (
            "$request->server->get('CI') === 'true'",
            "$request->server->get('GITHUB_ACTIONS') === 'true'",
            "$request->server->get('KURANEA_ADMIN_LOCALE_DIAGNOSTICS') === '1'",
            "$request->server->get('KURANEA_CI_PROJECT_NAME')",
            "'kuranea-ci-' . $serverRunId . '-' . $serverRunAttempt",
            "preg_match('/\\A[0-9]+\\z/D', $serverRunId)",
            "preg_match('/\\A[0-9]+\\z/D', $serverRunAttempt)",
        ):
            with self.subTest(guard=guard):
                self.assertIn(guard, subscriber)
        for environment in (
            'CI: ${CI:-false}',
            'GITHUB_ACTIONS: ${GITHUB_ACTIONS:-false}',
            'GITHUB_RUN_ID: ${GITHUB_RUN_ID:-}',
            'GITHUB_RUN_ATTEMPT: ${GITHUB_RUN_ATTEMPT:-}',
            'KURANEA_ADMIN_LOCALE_DIAGNOSTICS: ${KURANEA_ADMIN_LOCALE_DIAGNOSTICS:-0}',
            'KURANEA_CI_PROJECT_NAME: ${CI_COMPOSE_PROJECT_NAME:-}',
        ):
            with self.subTest(environment=environment):
                self.assertIn(environment, compose)
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        self.assertIn("KURANEA_ADMIN_LOCALE_DIAGNOSTICS: '1'", workflow)
        self.assertIn('KURANEA_ISOLATED_CI: "0"', compose)
        for field in (
            "module_active",
            "admin_route",
            "is_redirect",
            "http_status",
            "is_html",
            "body_present",
            "html_tags",
            "html_replacements",
            "lang_before",
            "lang_after",
            "rewritten",
        ):
            with self.subTest(field=field):
                self.assertIn(field, subscriber)
        self.assertIn("min(9999, count($originalHtmlTags[0] ?? []))", subscriber)
        self.assertIn("X-ORDENOWA-ADMIN-LOCALE-DIAGNOSTIC", browser)
        self.assertIn("admin_security_locale_diagnostics", browser)
        self.assertIn("PREG_UNMATCHED_AS_NULL", subscriber)
        self.assertIn('redirect: "manual"', browser)
        self.assertIn('response.type === "opaqueredirect"', browser)
        self.assertIn("SAFE_ADMIN_LOCALE_RESPONSE_PATTERN", browser)
        self.assertIn(r"/\s+lang\s*=", subscriber)
        self.assertNotIn(r"preg_match('/\blang\s*=", subscriber)

    def test_admin_locale_annotation_accepts_opaque_redirect_and_allowlists_response_fields(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_admin_security_browser.py").read_text(encoding="utf-8")
        self.assertIn("from admin_locale_diagnostics import", browser)
        self.assertIn("return parse_admin_locale_response_diagnostic(", browser)
        self.assertIn("response.headers.get(\"X-ORDENOWA-ADMIN-LOCALE-DIAGNOSTIC\")", browser)
        from tests.e2e.admin_locale_diagnostics import (
            SAFE_ADMIN_LOCALE_RESPONSE_PATTERN as pattern,
            parse_admin_locale_response_diagnostic,
        )

        valid = (
            "stage=rewritten;main_request=1;module_active=1;admin_route=1;is_redirect=0;http_status=200;"
            "is_html=1;body_present=1;html_tags=1;html_replacements=1;lang_before=other;lang_after=korean;rewritten=1"
            ";response_listener=1;isolated_ci_gate=1;probe_header=1;probe_controller=1;server_ci=1;server_actions=1;"
            "server_run_id_valid=1;server_run_attempt_valid=1;server_diagnostics=1;server_project_match=1;"
            "env_ci=1;env_actions=1;env_run_id_valid=1;env_run_attempt_valid=1;env_diagnostics=1;env_project_match=1"
        )

        self.assertIsNotNone(re.fullmatch(pattern, valid))
        self.assertIsNotNone(re.fullmatch(pattern, "redirect=opaque"))
        self.assertIsNotNone(re.fullmatch(pattern, "unavailable:JavascriptException"))
        self.assertIsNotNone(re.fullmatch(pattern, "unavailable:invalid_diagnostic"))
        self.assertIsNone(re.fullmatch(pattern, valid.replace("main_request=1", "request_url=https://secret.invalid")))
        self.assertEqual(parse_admin_locale_response_diagnostic(None), "unavailable:missing_header")

    def test_admin_locale_diagnostic_reports_safe_listener_and_gate_boundaries(self) -> None:
        subscriber = (MODULE / "src" / "AdminLocaleSubscriber.php").read_text(encoding="utf-8")
        required_fields = (
            "response_listener",
            "probe_header",
            "probe_controller",
            "server_ci",
            "server_actions",
            "server_run_id_valid",
            "server_run_attempt_valid",
            "server_diagnostics",
            "server_project_match",
            "env_ci",
            "env_actions",
            "env_run_id_valid",
            "env_run_attempt_valid",
            "env_diagnostics",
            "env_project_match",
        )
        missing_fields = [field for field in required_fields if field not in subscriber]
        self.assertEqual([], missing_fields, f"missing bounded diagnostic fields: {missing_fields}")
        self.assertIn("$gateFields = self::diagnosticGateFields($request);", subscriber)
        self.assertIn("$isolatedCiDiagnosticEnabled = self::isIsolatedCiDiagnosticRequest($request)", subscriber)
        self.assertIn("'env_diagnostics' => getenv('KURANEA_ADMIN_LOCALE_DIAGNOSTICS') === '1'", subscriber)
        isolated_gate = " ".join(subscriber.split()).split(
            "$isolatedCiDiagnosticEnabled =", 1
        )[1].split("$diagnosticProbeEnabled =", 1)[0]
        self.assertIn("$gateFields['probe_header'] === '1'", isolated_gate)
        self.assertIn("$gateFields['probe_controller'] === '1'", isolated_gate)
        self.assertIn("'response_listener' => '1'", subscriber)
        self.assertNotIn("'run_id' => $runId", subscriber)
        self.assertNotIn("'project_name' =>", subscriber)

    def test_admin_locale_probe_requires_a_complete_server_or_process_environment_ci_gate(self) -> None:
        subscriber = (MODULE / "src" / "AdminLocaleSubscriber.php").read_text(encoding="utf-8")
        normalized_subscriber = " ".join(subscriber.split())
        gate_method = normalized_subscriber.split(
            "private static function isIsolatedCiDiagnosticRequest(Request $request): bool", 1
        )[1].split("private static function diagnosticGateFields", 1)[0]
        self.assertIn("return $serverGate || $environmentGate;", gate_method)
        for gate_name, prefix in (("serverGate", "server"), ("environmentGate", "env")):
            with self.subTest(gate=gate_name):
                self.assertIn(f"${gate_name} =", gate_method)
                for field in ("ci", "actions", "run_id_valid", "run_attempt_valid", "diagnostics", "project_match"):
                    self.assertIn(f"$fields['{prefix}_{field}'] === '1'", gate_method)

        probe_gate = normalized_subscriber.split("$diagnosticProbeEnabled =", 1)[1].split(";", 1)[0]
        self.assertIn("$isolatedCiDiagnosticEnabled", probe_gate)
        self.assertNotIn("$diagnosticOptIn", probe_gate)

    def test_admin_locale_response_diagnostic_contract_is_executed_in_ci(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        checkout_contract_step = workflow.split("- name: Verify isolated unpaid checkout contracts", 1)[1].split(
            "- name:", 1
        )[0]
        self.assertIn("tests.admin_locale.test_admin_locale_response_diagnostic", checkout_contract_step)

    def test_admin_locale_browser_probe_captures_original_navigation_and_bounded_dom_categories(self) -> None:
        browser = (ROOT / "tests" / "e2e" / "verify_admin_security_browser.py").read_text(encoding="utf-8")
        for marker in (
            'options.set_capability("goog:loggingPrefs", {"performance": "ALL"})',
            'driver.execute_cdp_cmd("Network.enable", {})',
            'driver.execute_cdp_cmd("Network.setExtraHTTPHeaders",',
            'message.get("method") != "Network.responseReceived"',
            'params.get("type") != "Document"',
            'response.get("fromServiceWorker")',
            'response.get("fromDiskCache")',
            'response.get("fromPrefetchCache")',
            "navigation_url_exact=",
            "navigation_route_match=",
            "browser_url_exact=",
            "document_lang=",
            "response_html_lang=",
            "document_sw_controlled=",
            "navigation_worker_used=",
        ):
            with self.subTest(marker=marker):
                self.assertTrue(marker in browser, marker)

    def test_admin_locale_diagnostic_response_requires_explicit_probe_header_and_controller(self) -> None:
        subscriber = (MODULE / "src" / "AdminLocaleSubscriber.php").read_text(encoding="utf-8")
        normalized_subscriber = " ".join(subscriber.split())
        probe_gate = normalized_subscriber.split("$diagnosticProbeEnabled =", 1)[1].split(";", 1)[0]
        self.assertIn("$isolatedCiDiagnosticEnabled", probe_gate)
        self.assertNotIn("$diagnosticOptIn", normalized_subscriber)
        self.assertNotIn("$backOfficeControllerProbe", probe_gate)

    def test_admin_locale_diagnostic_bounds_browser_transport_metadata(self) -> None:
        from tests.e2e.admin_locale_diagnostics import parse_admin_locale_response_diagnostic

        parsed = parse_admin_locale_response_diagnostic(
            "missing;browser_status=200;browser_type=basic;"
            "browser_redirected=false;browser_same_route=true;browser_url_exact=true;"
            "document_lang=other;response_html_lang=korean;document_sw_controlled=false;"
            "navigation_worker_used=false;navigation_status=200"
        )
        self.assertEqual(
            "unavailable:missing_header;browser_status=200;browser_type=basic;"
            "browser_redirected=false;browser_same_route=true;browser_url_exact=true;"
            "document_lang=other;response_html_lang=korean;document_sw_controlled=false;"
            "navigation_worker_used=false;navigation_status=200",
            parsed,
        )

        invalid = parse_admin_locale_response_diagnostic(
            "secret-token=do-not-log;browser_status=https://private.invalid/path?token=secret;"
            "browser_type=basic;browser_redirected=false;browser_same_route=true;browser_url_exact=true;"
            "document_lang=other;response_html_lang=korean;document_sw_controlled=false;"
            "navigation_worker_used=false;navigation_status=200"
        )
        self.assertEqual(
            "unavailable:invalid_diagnostic;browser_status=unknown;browser_type=basic;"
            "browser_redirected=false;browser_same_route=true;browser_url_exact=true;"
            "document_lang=other;response_html_lang=korean;document_sw_controlled=false;"
            "navigation_worker_used=false;navigation_status=200",
            invalid,
        )

        browser = (ROOT / "tests" / "e2e" / "verify_admin_security_browser.py").read_text(encoding="utf-8")
        self.assertIn("browser_status=", browser)
        self.assertIn("browser_type=", browser)
        self.assertIn("browser_redirected=", browser)
        self.assertIn("browser_same_route=", browser)
        self.assertIn('response.headers.get("X-ORDENOWA-ADMIN-LOCALE-DIAGNOSTIC")', browser)
        self.assertIn("response.status", browser)
        self.assertIn("response.type", browser)
        self.assertIn("response.redirected", browser)
        self.assertIn("response.url", browser)

    def test_security_fixture_restores_primary_employee_language_before_restart_check(self) -> None:
        restore_path = ROOT / "tests" / "business_profile" / "restore_ci_admin_locale.php"
        self.assertTrue(restore_path.is_file(), "missing isolated employee-locale restoration fixture")
        restore_source = restore_path.read_text(encoding="utf-8")
        for required in (
            "getenv('CI') !== 'true'",
            "getenv('GITHUB_ACTIONS') !== 'true'",
            "getenv('KURANEA_ISOLATED_CI') !== '1'",
            "kuranea-ci-' . $runId . '-' . $runAttempt",
            "ADMIN_MAIL",
            "(int) $employee->id !== 1",
            "Language::getIdByIso('ko', true)",
            "$employee->update()",
            "Validate::isLoadedObject($savedEmployee)",
        ):
            with self.subTest(required=required):
                self.assertIn(required, restore_source)

        seed_source = (ROOT / "tests" / "business_profile" / "seed_security_fixtures.php").read_text(encoding="utf-8")
        self.assertIn("$adminOriginalLanguageId = (int) $admin->id_lang;", seed_source)
        self.assertIn("$admin->id_lang = $adminOriginalLanguageId;", seed_source)

        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        fixture_step = workflow.split("- name: Prepare isolated admin security and reset-token fixtures", 1)[1].split(
            "- name:", 1
        )[0]
        self.assertNotIn("KURANEA_SECURITY_FIXTURE_ATTEMPTED", fixture_step)
        seed_returned = fixture_step.index("php /tmp/seed_security_fixtures.php")
        mutation_marker = fixture_step.index("KURANEA_SECURITY_ADMIN_LOCALE_MUTATED=1")
        output_validation = fixture_step.index('python3 - "$fixture_log"')
        self.assertLess(seed_returned, mutation_marker)
        self.assertLess(mutation_marker, output_validation)
        restore_step = workflow.split("- name: Restore CI administrator language after locale QA", 1)[1].split(
            "- name:", 1
        )[0]
        self.assertIn("restore_ci_admin_locale.php", restore_step)
        self.assertIn("env.KURANEA_SECURITY_ADMIN_LOCALE_MUTATED == '1'", restore_step)
        self.assertLess(
            workflow.index("- name: Verify browser QA screenshot coverage"),
            workflow.index("- name: Restore CI administrator language after locale QA"),
        )
        self.assertLess(
            workflow.index("- name: Restore CI administrator language after locale QA"),
            workflow.index("- name: Verify the fresh shop and restart persistence"),
        )
        self.assertIn("SECURITY_LOCALE_RESTORE_OUTCOME: ${{ steps.security_locale_restore.outcome }}", workflow)
        self.assertIn('SECURITY_ADMIN_LOCALE_MUTATED: ${{ env.KURANEA_SECURITY_ADMIN_LOCALE_MUTATED }}', workflow)
        self.assertIn('if [[ "$SECURITY_ADMIN_LOCALE_MUTATED" == 1 && "$SECURITY_LOCALE_RESTORE_OUTCOME" != success ]]; then', workflow)

    def test_overlay_resources_use_prestashop_translator_loader(self) -> None:
        source_path = MODULE / "src" / "AdminLocaleSubscriber.php"
        services_path = MODULE / "config" / "services.yml"
        self.assertTrue(source_path.is_file(), "missing request-scoped locale subscriber")
        self.assertTrue(services_path.is_file(), "missing PrestaShop service registration")
        source = source_path.read_text()
        services = services_path.read_text()

        self.assertIn("TranslatorLanguageLoader", source)
        self.assertIn("XliffFileLoader", source)
        self.assertIn("getCatalogue", source)
        self.assertIn("addCatalogue", source)
        self.assertIn("loadLanguage", source)
        self.assertIn("addResource", source)
        self.assertIn("kernel.event_subscriber", services)
        self.assertIn("Admin.Global", source)
        self.assertIn("Admin.Actions", source)
        self.assertIn("Admin.Navigation.Header", source)
        self.assertIn("AdminGlobal.ko-KR.xlf", source)
        self.assertTrue((MODULE / "translations" / "ko-KR" / "AdminNavigationHeader.ko-KR.xlf").is_file())
        self.assertTrue((MODULE / "translations" / "ko-KR" / "AdminActions.ko-KR.xlf").is_file())
        self.assertTrue((MODULE / "translations" / "ko-KR" / "AdminGlobal.ko-KR.xlf").is_file())
        self.assertTrue((MODULE / "translations" / "ko-KR" / "messages.ko-KR.xlf").is_file())

    def test_admin_dashboard_date_range_is_localized_by_module_asset(self) -> None:
        module_source = (MODULE / "kuraneabackoffice.php").read_text()
        javascript_path = MODULE / "views" / "js" / "dashboard-korean.js"
        self.assertIn("actionAdminControllerSetMedia", module_source)
        self.assertIn("dashboard-korean.js", module_source)
        self.assertTrue(javascript_path.is_file(), "missing module-owned dashboard locale asset")
        javascript = javascript_path.read_text()
        self.assertIn("시작일", javascript)
        self.assertIn("종료일", javascript)
        self.assertIn("date_from", javascript)
        self.assertIn("compare_date_to", javascript)

    def test_admin_actions_overlay_fills_the_observed_back_to_gap(self) -> None:
        path = MODULE / "translations" / "ko-KR" / "AdminActions.ko-KR.xlf"
        self.assertTrue(path.is_file(), "missing module-owned Admin.Actions overlay")
        self.assertEqual("쇼핑몰로 돌아가기", translations(path).get("Back to"))

    def test_admin_global_overlay_translates_the_observed_password_gap(self) -> None:
        path = MODULE / "translations" / "ko-KR" / "AdminGlobal.ko-KR.xlf"
        self.assertTrue(path.is_file(), "missing module-owned Admin.Global overlay")
        entries = translations(path)
        self.assertEqual("비밀번호", entries.get("Password"))
        self.assertEqual("시작일", entries.get("From"))
        self.assertEqual("종료일", entries.get("To"))

    def test_admin_global_overlay_translates_orders_page_average_order_kpi(self) -> None:
        path = MODULE / "translations" / "ko-KR" / "AdminGlobal.ko-KR.xlf"
        self.assertTrue(path.is_file(), "missing module-owned Admin.Global overlay")
        self.assertEqual("평균 주문 금액", translations(path).get("Average Order Value"))

    def test_dashboard_overlay_translates_native_demo_mode_label(self) -> None:
        path = MODULE / "translations" / "ko-KR" / "AdminDashboardFeature.ko-KR.xlf"
        self.assertTrue(path.is_file(), "missing module-owned Admin.Dashboard.Feature overlay")
        self.assertEqual("데모 모드", translations(path).get("Demo mode"))

    def test_successful_update_overlay_preserves_both_verified_native_source_ids(self) -> None:
        path = MODULE / "translations" / "ko-KR" / "AdminNotificationsSuccess.ko-KR.xlf"
        self.assertTrue(path.is_file(), "missing module-owned Admin.Notifications.Success overlay")
        root = ET.parse(path).getroot()
        entries = {
            unit.attrib["id"]: (
                unit.findtext("x:source", namespaces=NAMESPACE),
                unit.findtext("x:target", namespaces=NAMESPACE),
            )
            for unit in root.findall(".//x:trans-unit", NAMESPACE)
        }
        self.assertEqual({
            "d4eab6753f9f3d4b57580427264beaa6": ("Successful update", "변경 사항을 저장했습니다."),
            "b4a34d3f58b039e7685c2e39b5413757": ("Successful update.", "변경 사항을 저장했습니다."),
        }, entries)

    def test_successful_update_overlay_is_registered_and_checked_in_both_locale_modes(self) -> None:
        subscriber = (MODULE / "src" / "AdminLocaleSubscriber.php").read_text(encoding="utf-8")
        lifecycle = (ROOT / "tests" / "admin_locale" / "locale_lifecycle.php").read_text(encoding="utf-8")
        self.assertIn("'Admin.Notifications.Success' => 'AdminNotificationsSuccess.ko-KR.xlf'", subscriber)
        for source in ("Successful update", "Successful update."):
            with self.subTest(source=source):
                self.assertIn(f"$translator->trans('{source}', [], 'Admin.Notifications.Success', 'ko-KR')", lifecycle)
                self.assertIn(f"$translator->trans('{source}', [], 'Admin.Notifications.Success')", lifecycle)

    def test_navigation_overlay_translates_native_payment_menu_variants(self) -> None:
        path = MODULE / "translations" / "ko-KR" / "AdminNavigationMenu.ko-KR.xlf"
        self.assertEqual("결제 수단", translations(path).get("Payment Methods"))
        self.assertEqual("결제 수단", translations(path).get("Payment methods"))

    def test_orders_locale_lifecycle_checks_the_runtime_admin_global_kpi_translation(self) -> None:
        lifecycle = (ROOT / "tests" / "admin_locale" / "locale_lifecycle.php").read_text(encoding="utf-8")
        self.assertIn("Average Order Value", lifecycle)
        self.assertIn("Admin.Global KPI translation", lifecycle)
        self.assertIn("default Admin.Global KPI translation", lifecycle)

    def test_dashboard_demo_mode_overlay_is_registered_and_lifecycle_checked(self) -> None:
        subscriber = (MODULE / "src" / "AdminLocaleSubscriber.php").read_text(encoding="utf-8")
        lifecycle = (ROOT / "tests" / "admin_locale" / "locale_lifecycle.php").read_text(encoding="utf-8")
        self.assertIn("'Admin.Dashboard.Feature' => 'AdminDashboardFeature.ko-KR.xlf'", subscriber)
        self.assertIn("$translator->trans('Demo mode', [], 'Admin.Dashboard.Feature', 'ko-KR')", lifecycle)

    def test_orders_feature_overlay_translates_new_order_toolbar_action(self) -> None:
        path = MODULE / "translations" / "ko-KR" / "AdminOrderscustomersFeature.ko-KR.xlf"
        self.assertTrue(path.is_file(), "missing module-owned Admin.Orderscustomers.Feature overlay")
        self.assertEqual("새 주문 추가", translations(path).get("Add new order"))

    def test_admin_navigation_header_overlay_translates_view_store_action(self) -> None:
        subscriber = (MODULE / "src" / "AdminLocaleSubscriber.php").read_text()
        self.assertIn("AdminNavigationHeader.ko-KR.xlf", subscriber)
        path = MODULE / "translations" / "ko-KR" / "AdminNavigationHeader.ko-KR.xlf"
        self.assertTrue(path.is_file(), "missing module-owned Admin.Navigation.Header overlay")
        self.assertEqual("내 쇼핑몰 보기", translations(path).get("View my store"))

    def test_admin_navigation_header_welcome_preserves_employee_name_placeholder(self) -> None:
        path = MODULE / "translations" / "ko-KR" / "AdminNavigationHeader.ko-KR.xlf"
        source = "Welcome back %name%"
        target = translations(path).get(source)
        self.assertEqual("%name%님, 환영합니다", target)
        self.assertEqual(re.findall(r"%[^%]+%", source), re.findall(r"%[^%]+%", target))

    def test_observed_admin_labels_are_checked_through_runtime_translator(self) -> None:
        lifecycle = (ROOT / "tests" / "admin_locale" / "locale_lifecycle.php").read_text(encoding="utf-8")
        self.assertIn("$translator->trans('Carriers', [], 'Admin.Navigation.Menu', 'ko-KR')", lifecycle)
        self.assertIn("$translator->trans('Payment Methods', [], 'Admin.Navigation.Menu', 'ko-KR')", lifecycle)
        self.assertIn("$translator->trans('Payment methods', [], 'Admin.Navigation.Menu', 'ko-KR')", lifecycle)
        self.assertIn("$translator->trans('Payment method', [], 'Admin.Orderscustomers.Feature', 'ko-KR')", lifecycle)
        self.assertIn("explicit Korean payment menu title", lifecycle)
        self.assertIn("explicit Korean payment menu label", lifecycle)
        self.assertIn("explicit Korean demo mode label", lifecycle)
        self.assertIn("explicit Korean carrier navigation", lifecycle)
        self.assertIn("explicit Korean payment method label", lifecycle)

    def test_observed_carrier_menu_label_is_korean(self) -> None:
        path = MODULE / "translations" / "ko-KR" / "AdminNavigationMenu.ko-KR.xlf"
        self.assertEqual("배송사", translations(path).get("Carriers"))

    def test_observed_order_payment_method_label_is_korean(self) -> None:
        path = MODULE / "translations" / "ko-KR" / "AdminOrderscustomersFeature.ko-KR.xlf"
        self.assertEqual("결제 방법", translations(path).get("Payment method"))

    def test_psgdpr_overlay_translates_the_observed_admin_gaps(self) -> None:
        path = MODULE / "translations" / "ko-KR" / "messages.ko-KR.xlf"
        self.assertTrue(path.is_file(), "missing module-owned psgdpr fallback overlay")
        observed = {
            "Data visualization and automatic actions",
            "Compliant module list",
            "Search for a customer name OR email",
            "Remove data",
            "Download invoices",
        }

        translated = translations(path)
        for source in observed:
            with self.subTest(source=source):
                self.assertTrue(translated.get(source), f"missing Korean overlay for {source!r}")
                self.assertNotEqual(source, translated[source])

    def test_admin_login_hook_uses_official_ordenowa_logo_without_legacy_fallback(self) -> None:
        module_path = MODULE / "kuraneabackoffice.php"
        template_path = MODULE / "views" / "templates" / "hook" / "admin-login.tpl"
        self.assertTrue(module_path.is_file(), "missing Back Office branding module")
        self.assertTrue(template_path.is_file(), "missing admin login hook template")
        module_source = module_path.read_text()
        hook_template = template_path.read_text()
        logo = MODULE / "views" / "img" / "kuranea-logo.png"

        self.assertIn("displayAdminLogin", module_source)
        self.assertIn("hookDisplayAdminLogin", module_source)
        self.assertIn("ordenowa_backoffice_brand_name", module_source)
        self.assertIn("ordenowa_backoffice_brand_name", hook_template)
        self.assertIn("ProfileDefaults::initial()", module_source)
        self.assertIn("ORDENOWA", module_source)
        self.assertNotIn("kuranea-logo.png", module_source)
        self.assertNotIn("KURANEA", hook_template)
        self.assertIn("#login-header", hook_template)
        self.assertIn("#login-footer", hook_template)
        self.assertIn("#shop-img img", hook_template)
        self.assertIn("display: none !important", hook_template)
        self.assertIn("content: \"←\";", hook_template)
        # Preserve the original outside the served module webroot.
        source_logo = ROOT / "assets" / "brand" / "source" / "kuranea-logo.png"
        source_manifest = ROOT / "assets" / "brand" / "source" / "SHA256SUMS.txt"
        self.assertFalse(logo.exists(), "legacy KURANEA logo must not remain in the public module webroot")
        self.assertTrue(source_logo.is_file(), "preserved KURANEA source logo is missing")
        source_bytes = source_logo.read_bytes()
        self.assertEqual(b"\x89PNG\r\n\x1a\n", source_bytes[:8])
        source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        self.assertEqual(
            "ae54c1ae9042cbef7de8c0a81a9d8d9e819f060b90ee2d46841a88f8f498de69",
            source_sha256,
            "preserved KURANEA source logo no longer matches the verified original",
        )
        self.assertIn(
            f"{source_sha256}  kuranea-logo.png",
            source_manifest.read_text(encoding="utf-8").splitlines(),
        )


if __name__ == "__main__":
    unittest.main()
