import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("safe_authenticated_outcome.py")
SPEC = importlib.util.spec_from_file_location("safe_authenticated_outcome", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def valid_helper_payload():
    return {
        "schema": 1,
        "passed": True,
        "test_dependency_sources": {
            "symfony/browser-kit": {
                "version": "6.4.44",
                "source_commit": "4f631476bb549d882a173c47bf693f3ef84c722d",
                "archive_sha256": "a" * 64,
            },
            "symfony/css-selector": {
                "version": "6.4.45",
                "source_commit": "5484e316cd8125f5215bbf829151e2211aa6d101",
                "archive_sha256": "b" * 64,
            },
            "symfony/dom-crawler": {
                "version": "6.4.44",
                "source_commit": "998855f6c3699f148b54096d1d7d2b8b0b0fc298",
                "archive_sha256": None,
            },
        },
        "module_inventory": {
            "private_module": "must not be copied",
        },
        "mbo_error_render": {
            "mode": "authenticated_production_kernel_browserkit_request",
            "actual_admin_login_form_post": True,
            "native_login_transport": "loopback_http_native_front_controller",
            "native_login_loopback_http_requests": 4,
            "native_login_cookie_count": 2,
            "kernel_browser_target_request_count": 1,
            "private_response_snapshot_sha256": "c" * 64,
            "native_route": "admin_mbo_catalog_theme",
            "controller": "ThemeCatalogController::indexAction",
            "response_status": 503,
            "injected_header_verified": True,
            "full_native_layout": True,
            "korean_document_language": True,
            "korean_message_occurrences": 2,
            "english_source_absent": True,
            "injected_provider_invocations": 1,
            "injected_provider_http_calls": 0,
            "browser_socket_requests": 0,
            "script_initiated_business_mutations": False,
            "authentication_session_or_audit_writes_possible": True,
            "bootstrap_database_side_effects_instrumented": False,
            "bootstrap_network_side_effects_instrumented": False,
            "native_session_csrf_verified": True,
            "native_session_csrf_probe_count": 1,
        },
    }


def raw_json(payload):
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class SafeAuthenticatedOutcomeTests(unittest.TestCase):
    def test_failed_helper_emits_only_fixed_native_auth_landing_facts(self):
        auth_landing = {
            "post_status": 302,
            "redirect_count": 1,
            "final_status": 200,
            "final_path_kind": "index",
            "final_controller_kind": "dashboard",
            "redirect_token_kind": "masked",
            "body_token_kind": "missing",
            "body_page_kind": "dashboard",
        }
        payload = {
            "schema": 1,
            "passed": False,
            "failed_stage": "native_login_post_redirects",
            "auth_landing": auth_landing,
            "final_uri": "http://localhost/admin-kuranea/index.php?token=PRIVATE_URL_TOKEN",
            "native_body_token": "PRIVATE_BODY_TOKEN",
            "email": "PRIVATE_EMAIL",
        }
        result = MODULE.collect_safe_outcome(raw_json(payload), 1)
        self.assertEqual(result["auth_landing"], auth_landing)
        encoded = json.dumps(result)
        for secret in ("localhost", "admin-kuranea", "PRIVATE_URL_TOKEN", "PRIVATE_BODY_TOKEN", "PRIVATE_EMAIL"):
            self.assertNotIn(secret, encoded)

    def test_malformed_or_extended_auth_landing_fact_object_is_dropped_as_a_whole(self):
        facts = {
            "post_status": 200,
            "redirect_count": 0,
            "final_status": 200,
            "final_path_kind": "login",
            "final_controller_kind": "none",
            "redirect_token_kind": "missing",
            "body_token_kind": "plain_hex32",
            "body_page_kind": "login",
        }
        invalid = [
            {**facts, "url": "http://localhost/PRIVATE"},
            {**facts, "final_status": True},
            {**facts, "redirect_count": 7},
            {**facts, "body_token_kind": "PRIVATE_TOKEN"},
            {**facts, "body_page_kind": []},
        ]
        for value in invalid:
            with self.subTest(value=value):
                result = MODULE.collect_safe_outcome(raw_json({"schema": 1, "passed": False, "auth_landing": value}), 1)
                self.assertNotIn("auth_landing", result)
                serialized = json.dumps(result)
                self.assertNotIn("PRIVATE", serialized)
                self.assertNotIn("localhost", serialized)

    def test_failed_mbo_assertion_and_bounded_response_facts_are_exactly_allowlisted(self):
        facts = {
            "response_status": 503,
            "injected_header_present": True,
            "html_content_type": True,
            "korean_document_language": True,
            "korean_message_occurrences": 2,
            "english_source_present": False,
            "provider_calls": 1,
            "csrf_verified": True,
            "csrf_probe_count": 1,
            "body_token_present": True,
        }
        payload = {
            "schema": 1,
            "passed": False,
            "failed_stage": "assert_authenticated_korean_error",
            "failed_assertion": "native_mbo_session_csrf_not_verified",
            "failure_facts": facts,
            "request_uri": "http://localhost/admin-kuranea/?_token=PRIVATE_TOKEN",
            "body": "PRIVATE_HTML",
            "exception_message": "PRIVATE_MESSAGE",
        }
        result = MODULE.collect_safe_outcome(raw_json(payload), 1)
        self.assertEqual(result["failed_assertion"], "native_mbo_session_csrf_not_verified")
        self.assertEqual(result["failure_facts"], facts)
        encoded = json.dumps(result)
        for secret in ("localhost", "admin-kuranea", "PRIVATE_TOKEN", "PRIVATE_HTML", "PRIVATE_MESSAGE"):
            self.assertNotIn(secret, encoded)

    def test_native_exception_observation_keeps_only_bounded_safe_chain(self):
        observation = {
            "phase": "main_request",
            "chain": [{
                "class": "Symfony\\Component\\HttpKernel\\Exception\\ServiceUnavailableHttpException",
                "source": "ThemeCatalogController.php:58",
                "http_status": 503,
                "twig_template": None,
                "twig_line": None,
            }, {
                "class": "Twig\\Error\\RuntimeError",
                "source": "Template.php:44",
                "http_status": None,
                "twig_template": "@PrestaShop/Admin/Layout/light_layout.html.twig",
                "twig_line": 6,
            }],
        }
        payload = {
            "schema": 1, "passed": False, "failed_stage": "assert_authenticated_korean_error",
            "exception_observation": observation,
            "exception_message": "PRIVATE_MESSAGE", "request_uri": "PRIVATE_URL",
        }
        result = MODULE.collect_safe_outcome(raw_json(payload), 1)
        self.assertEqual(result["exception_observation"], observation)
        serialized = json.dumps(result)
        self.assertNotIn("PRIVATE_MESSAGE", serialized)
        self.assertNotIn("PRIVATE_URL", serialized)

    def test_native_exception_observation_rejects_extra_fields_bad_pairs_and_long_chains(self):
        entry = {
            "class": "RuntimeException", "source": "ErrorController.php:27", "http_status": 500,
            "twig_template": None, "twig_line": None,
        }
        invalid = [
            {"phase": "main_request", "chain": [{**entry, "message": "PRIVATE"}]},
            {"phase": "main_request", "chain": [{**entry, "twig_template": "@Modules/ps_mbo/error.html.twig"}]},
            {"phase": "main_request", "chain": [{**entry, "source": "/private/ErrorController.php:27"}]},
            {"phase": "main_request", "chain": [entry] * 5},
            {"phase": "private_phase", "chain": [entry]},
        ]
        for observation in invalid:
            with self.subTest(observation=observation):
                payload = {"schema": 1, "passed": False, "exception_observation": observation}
                result = MODULE.collect_safe_outcome(raw_json(payload), 1)
                self.assertNotIn("exception_observation", result)
                self.assertNotIn("PRIVATE", json.dumps(result))

    def test_malformed_mbo_assertion_metadata_is_dropped_without_crashing(self):
        facts = {
            "response_status": 503,
            "injected_header_present": True,
            "html_content_type": True,
            "korean_document_language": True,
            "korean_message_occurrences": 2,
            "english_source_present": False,
            "provider_calls": 1,
            "csrf_verified": True,
            "csrf_probe_count": 1,
            "body_token_present": True,
        }
        bad_facts = [
            {**facts, "private_url": "PRIVATE_URL"},
            {**facts, "response_status": True},
            {**facts, "korean_message_occurrences": 11},
            {**facts, "provider_calls": 101},
            {**facts, "csrf_verified": 1},
            {**facts, "body_token_present": []},
        ]
        for item in bad_facts:
            with self.subTest(item=item):
                payload = {
                    "schema": 1, "passed": False,
                    "failed_assertion": "native_mbo_response_status_not_503",
                    "failure_facts": item,
                }
                result = MODULE.collect_safe_outcome(raw_json(payload), 1)
                self.assertEqual(result["failed_assertion"], "native_mbo_response_status_not_503")
                self.assertNotIn("failure_facts", result)
                self.assertNotIn("PRIVATE", json.dumps(result))
        for value in ("PRIVATE_ASSERTION", ["native_mbo_response_status_not_503"], 1):
            payload = {"schema": 1, "passed": False, "failed_assertion": value, "failure_facts": facts}
            result = MODULE.collect_safe_outcome(raw_json(payload), 1)
            self.assertNotIn("failed_assertion", result)

    def test_success_rebuilds_a_whitelist_and_discards_raw_extra_fields(self):
        payload = valid_helper_payload()
        payload["password"] = "PRIVATE_TOP_LEVEL_SECRET"
        payload["raw_html"] = "<html>PRIVATE_HTML_SECRET</html>"
        payload["mbo_error_render"]["exception_message"] = "PRIVATE_EXCEPTION_SECRET"
        result = MODULE.collect_safe_outcome(raw_json(payload), 0)

        self.assertTrue(result["passed"])
        encoded = json.dumps(result, ensure_ascii=False)
        for secret in ("PRIVATE_TOP_LEVEL_SECRET", "PRIVATE_HTML_SECRET", "PRIVATE_EXCEPTION_SECRET"):
            self.assertNotIn(secret, encoded)
        self.assertNotIn("module_inventory", result)
        self.assertEqual(result["mbo_error_render"]["korean_message_occurrences"], 2)
        self.assertTrue(result["mbo_error_render"]["native_session_csrf_verified"])

    def test_duplicate_json_keys_are_rejected_even_when_values_look_valid(self):
        payload = raw_json(valid_helper_payload())
        duplicate_top = payload.replace('"schema":1,', '"schema":1,"schema":1,', 1)
        duplicate_nested = payload.replace(
            '"native_session_csrf_verified":true,',
            '"native_session_csrf_verified":true,"native_session_csrf_verified":false,',
            1,
        )
        for raw in (duplicate_top, duplicate_nested):
            with self.subTest(raw=raw[:40]):
                result = MODULE.collect_safe_outcome(raw, 0)
                self.assertFalse(result["passed"])
                self.assertEqual(result["failure_code"], "invalid_helper_json")

    def test_nonzero_helper_exit_cannot_be_overridden_by_passed_true(self):
        payload = valid_helper_payload()
        payload["failed_stage"] = "native_route_services"
        payload["exception_class"] = "Symfony\\Component\\RuntimeException"
        payload["exception_message"] = "PRIVATE_FAILURE_SECRET"
        result = MODULE.collect_safe_outcome(raw_json(payload), 1)

        self.assertFalse(result["passed"])
        self.assertEqual(result["failure_code"], "helper_exit_nonzero")
        self.assertEqual(result["failed_stage"], "native_route_services")
        self.assertEqual(result["exception_class"], "Symfony\\Component\\RuntimeException")
        self.assertNotIn("PRIVATE_FAILURE_SECRET", json.dumps(result))

    def test_html_or_secret_prefixed_output_fails_without_echoing_private_input(self):
        for raw in (
            "<html>PRIVATE_HTML_SECRET</html>",
            "PRIVATE_STDOUT_SECRET\n" + raw_json(valid_helper_payload()),
            "not-json PRIVATE_RAW_SECRET",
        ):
            with self.subTest(raw=raw[:24]):
                result = MODULE.collect_safe_outcome(raw, 0)
                self.assertFalse(result["passed"])
                self.assertEqual(result["failure_code"], "invalid_helper_json")
                self.assertNotIn("PRIVATE_", json.dumps(result))

    def test_failed_helper_payload_exposes_only_safe_stage_and_exception_class(self):
        payload = {
            "schema": 1,
            "passed": False,
            "failed_stage": "admin_kernel_boot",
            "exception_class": "Twig\\Error\\RuntimeError",
            "cause_class": "Twig\\Error\\RuntimeError",
            "failure_source": "AdminKernel.php:1000000",
            "twig_template": "@Modules/ps_mbo/views/templates/admin/error.html.twig",
            "twig_template_line": 100000,
            "exception_message": "PRIVATE_CREDENTIAL_OR_PATH_SECRET",
            "trace": "PRIVATE_STACK_SECRET",
        }
        result = MODULE.collect_safe_outcome(raw_json(payload), 1)

        self.assertEqual(result["failure_code"], "helper_exit_nonzero")
        self.assertEqual(result["failed_stage"], "admin_kernel_boot")
        self.assertEqual(result["exception_class"], "Twig\\Error\\RuntimeError")
        self.assertEqual(result["cause_class"], "Twig\\Error\\RuntimeError")
        self.assertEqual(result["failure_source"], "AdminKernel.php:1000000")
        self.assertEqual(result["twig_template"], "@Modules/ps_mbo/views/templates/admin/error.html.twig")
        self.assertEqual(result["twig_template_line"], 100000)
        encoded = json.dumps(result)
        self.assertNotIn("PRIVATE_", encoded)
        self.assertNotIn("trace", encoded)

    def test_twig_diagnostics_allow_only_fixed_native_namespaces_and_pair_line_with_template(self):
        for template in (
            "@PrestaShop/Admin/Layout/light_layout.html.twig",
            "@PrestaShopCore/Resources/views/Admin/layout.html.twig",
            "@Modules/ps_mbo/views/templates/admin/error.html.twig",
            "@Modules/ps_facebook/views/templates/admin/error.html.twig",
        ):
            with self.subTest(template=template):
                payload = {
                    "schema": 1,
                    "passed": False,
                    "failed_stage": "admin_kernel_boot",
                    "twig_template": template,
                    "twig_template_line": 17,
                    "exception_message": "PRIVATE_MESSAGE",
                }
                result = MODULE.collect_safe_outcome(raw_json(payload), 1)
                self.assertEqual(result["twig_template"], template)
                self.assertEqual(result["twig_template_line"], 17)

        for payload in (
            {"schema": 1, "passed": False, "twig_template_line": 17},
            {"schema": 1, "passed": False, "twig_template": "@Modules/other_module/error.html.twig", "twig_template_line": 17},
        ):
            result = MODULE.collect_safe_outcome(raw_json(payload), 1)
            self.assertNotIn("twig_template", result)
            self.assertNotIn("twig_template_line", result)

    def test_optional_failure_metadata_drops_unallowlisted_paths_and_stages(self):
        payload = {
            "schema": 1,
            "passed": False,
            "failed_stage": "private_secret_stage",
            "cause_class": "RuntimeException: PRIVATE_SECRET",
            "failure_source": "/var/www/html/config/secrets.php:12",
            "twig_template": "@Modules/other_module/secrets.twig",
            "twig_template_line": 100001,
            "getMessage": "PRIVATE_MESSAGE_SECRET",
        }
        result = MODULE.collect_safe_outcome(raw_json(payload), 1)
        self.assertEqual(result["failure_code"], "helper_exit_nonzero")
        for key in ("failed_stage", "cause_class", "failure_source", "twig_template", "twig_template_line"):
            self.assertNotIn(key, result)

    def test_failure_stack_keeps_identifiers_only_and_discards_arguments_and_paths(self):
        payload = {'schema': 1, 'passed': False, 'failure_trace': [
            {'class': 'PrestaShop\\Core\\Context', 'function': 'getShop', 'source': 'ShopId.php:49',
             'args': ['PRIVATE_PASSWORD'], 'file': '/private/config.php'},
            {'class': 'PRIVATE:SECRET', 'function': 'getShop', 'source': 'ShopId.php:49'},
            {'class': 'Context', 'function': 'getShop', 'source': '/private/ShopId.php:49'},
            {'class': 'Context', 'function': 'PRIVATE SECRET', 'source': 'ShopId.php:49'},
        ]}
        result = MODULE.collect_safe_outcome(raw_json(payload), 1)
        self.assertEqual(result['failure_trace'], [
            {'class': 'PrestaShop\\Core\\Context', 'function': 'getShop', 'source': 'ShopId.php:49'}])
        self.assertNotIn('PRIVATE', json.dumps(result))
        payload['failure_trace'] *= 3
        self.assertNotIn('failure_trace', MODULE.collect_safe_outcome(raw_json(payload), 1))
        self.assertNotIn("PRIVATE_", json.dumps(result))

    def test_missing_or_invalid_native_session_csrf_proof_fails_closed(self):
        for field, value in (
            ("native_session_csrf_verified", False),
            ("native_session_csrf_verified", 1),
            ("native_session_csrf_probe_count", 0),
            ("native_session_csrf_probe_count", True),
        ):
            payload = valid_helper_payload()
            payload["mbo_error_render"][field] = value
            result = MODULE.collect_safe_outcome(raw_json(payload), 0)
            with self.subTest(field=field, value=value):
                self.assertFalse(result["passed"])
                self.assertEqual(result["failure_code"], "outcome_contract_mismatch")

    def test_status_counts_and_booleans_are_strictly_typed_and_bounded(self):
        cases = (
            ("response_status", True),
            ("response_status", 200),
            ("korean_message_occurrences", True),
            ("korean_message_occurrences", 11),
            ("injected_provider_invocations", 2),
            ("browser_socket_requests", False),
            ("actual_admin_login_form_post", 1),
            ("bootstrap_network_side_effects_instrumented", True),
            ("kernel_browser_target_request_count", 2),
            ("native_login_cookie_count", True),
            ("native_login_cookie_count", 0),
            ("native_login_loopback_http_requests", 2),
            ("native_login_loopback_http_requests", 15),
        )
        for field, value in cases:
            payload = valid_helper_payload()
            payload["mbo_error_render"][field] = value
            with self.subTest(field=field, value=value):
                result = MODULE.collect_safe_outcome(raw_json(payload), 0)
                self.assertFalse(result["passed"])
                self.assertEqual(result["failure_code"], "outcome_contract_mismatch")

    def test_login_transport_metadata_is_fixed_and_sanitized(self):
        result = MODULE.collect_safe_outcome(raw_json(valid_helper_payload()), 0)
        self.assertTrue(result["passed"])
        render = result["mbo_error_render"]
        self.assertEqual(render["native_login_transport"], "loopback_http_native_front_controller")
        self.assertEqual(render["native_login_loopback_http_requests"], 4)
        self.assertEqual(render["native_login_cookie_count"], 2)
        self.assertEqual(render["kernel_browser_target_request_count"], 1)

        for field, value in (
            ("native_login_transport", "browserkit_fake_login"),
            ("native_login_transport", True),
        ):
            payload = valid_helper_payload()
            payload["mbo_error_render"][field] = value
            rejected = MODULE.collect_safe_outcome(raw_json(payload), 0)
            self.assertFalse(rejected["passed"])
            self.assertEqual(rejected["failure_code"], "outcome_contract_mismatch")

    def test_dependency_sources_require_allowlisted_packages_versions_and_sha_shapes(self):
        cases = (
            ("symfony/unknown", {"version": "1.0", "source_commit": "a" * 40, "archive_sha256": "b" * 64}),
            ("symfony/browser-kit", {"version": "6.4.99", "source_commit": "a" * 40, "archive_sha256": "b" * 64}),
            ("symfony/css-selector", {"version": "6.4.45", "source_commit": "not-a-sha", "archive_sha256": "b" * 64}),
            ("symfony/browser-kit", {"version": "6.4.44", "source_commit": "a" * 40, "archive_sha256": "short"}),
        )
        for package, value in cases:
            payload = valid_helper_payload()
            if package == "symfony/unknown":
                payload["test_dependency_sources"][package] = value
            else:
                payload["test_dependency_sources"][package] = value
            with self.subTest(package=package, value=value):
                result = MODULE.collect_safe_outcome(raw_json(payload), 0)
                self.assertFalse(result["passed"])
                self.assertEqual(result["failure_code"], "outcome_contract_mismatch")

    def test_cli_writes_only_sanitized_json_and_uses_exit_status_for_acceptance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private_input = root / "helper.stdout.private"
            safe_output = root / "qa-safe.json"
            payload = valid_helper_payload()
            payload["password"] = "CLI_PRIVATE_SECRET"
            private_input.write_text(raw_json(payload), encoding="utf-8")
            if os.name == "posix":
                private_input.chmod(0o600)

            run = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--private-input",
                    str(private_input),
                    "--safe-output",
                    str(safe_output),
                    "--helper-exit-status",
                    "0",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout, "")
            safe_text = safe_output.read_text(encoding="utf-8")
            self.assertNotIn("CLI_PRIVATE_SECRET", safe_text)
            self.assertTrue(json.loads(safe_text)["passed"])
            if os.name == "posix":
                self.assertEqual(safe_output.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
