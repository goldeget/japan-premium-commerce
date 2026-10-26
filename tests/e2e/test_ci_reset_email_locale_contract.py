"""Contracts and adversarial examples for isolated native reset email localization."""
import ast
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

VERIFIER = Path(__file__).with_name('verify_ci_reset_email_locale.py')
WORKFLOW = Path(__file__).resolve().parents[2] / '.github/workflows/fresh-install.yml'


class ResetEmailLocaleContract(unittest.TestCase):
    def test_verifier_exists_and_keeps_order_delivery_out_of_scope(self):
        self.assertTrue(VERIFIER.is_file(), 'native reset email locale verifier is missing')
        source = VERIFIER.read_text()
        for marker in ('order confirmation', 'METHOD_DISABLE', 'CI_COMPOSE_PROJECT_NAME',
                       'KURANEA_ISOLATED_CI', 'PS_MAIL_SERVER', 'mailpit', 'new Customer()',
                       "('ja', 'en', 'ko')", 'getPageLink', 'id_lang', 'capture_output=True',
                       "'raw_password' => $rawPassword", "'password_hash' => $customer->passwd",
                       "'customer_secure_key' => $customer->secure_key"):
            self.assertIn(marker, source)
        self.assertNotIn('Configuration::updateValue', source)
        tree = ast.parse(source)
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                             and n.func.id == 'print' and any(isinstance(x, ast.Name) and x.id in
                             {'message', 'email', 'error', 'fixture', 'result'} for x in ast.walk(n))
                             for n in ast.walk(tree)))

    def module(self):
        self.assertTrue(VERIFIER.is_file(), 'native reset email locale verifier is missing')
        spec = importlib.util.spec_from_file_location('locale_email_verifier', VERIFIER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def message(self, language='en', url=None):
        markers = {'ja': 'パスワード', 'en': 'password', 'ko': '비밀번호'}
        url = url or 'http://127.0.0.1:18080/reset?token=synthetic-token&reset_token=synthetic-reset'
        return {'HTML': f'<html><body>{markers[language]} <a href="{url}">reset</a></body></html>',
                'Text': markers[language] + ' ' + url}

    def forbidden(self):
        return {
            'raw_password': 'synthetic-raw-password',
            'password_hash': 'synthetic-password-hash',
            'customer_secure_key': 'synthetic-customer-secure-key',
        }

    def test_language_and_native_link_required(self):
        module = self.module()
        for language in ('ja', 'en', 'ko'):
            module.assert_message(self.message(language), language, 'http://127.0.0.1:18080', '/reset', self.forbidden())
            with self.assertRaises(module.MessageValidationError) as caught:
                module.assert_message(self.message('en' if language != 'en' else 'ko'), language,
                                      'http://127.0.0.1:18080', '/reset', self.forbidden())
            self.assertEqual('locale_marker_missing', caught.exception.check)
        with self.assertRaises(module.MessageValidationError):
            module.assert_message(self.message('ja', url='http://127.0.0.1:18080/password?token=x&reset_token=y'),
                                  'en', 'http://127.0.0.1:18080', '/password', self.forbidden())
        for url in ('https://evil.invalid/reset?token=x&reset_token=y',
                    'http://user:secret@127.0.0.1:18080/reset?token=x&reset_token=y',
                    'http://127.0.0.1:18080/other?token=x&reset_token=y'):
            with self.assertRaises(module.MessageValidationError) as caught:
                module.assert_message(self.message(url=url), 'en', 'http://127.0.0.1:18080', '/reset', self.forbidden())
            self.assertIn(caught.exception.check, {'reset_link_origin_mismatch', 'reset_link_path_mismatch'})

    def test_credentials_and_generic_bank_details_fail_without_logging_payload(self):
        module = self.module()
        for category, secret, expected in (
            ('raw_password', 'synthetic-raw-password', 'raw_password_disclosure'),
            ('password_hash', 'synthetic-password-hash', 'password_hash_disclosure'),
        ):
            for part in ('HTML', 'Text'):
                with self.subTest(category=category, part=part):
                    message = self.message()
                    message[part] += ' ' + secret
                    forbidden = self.forbidden()
                    forbidden[category] = secret
                    output = io.StringIO()
                    with contextlib.redirect_stderr(output), contextlib.redirect_stdout(output):
                        with self.assertRaises(module.MessageValidationError) as caught:
                            module.assert_message(message, 'en', 'http://127.0.0.1:18080', '/reset', forbidden)
                    self.assertEqual(expected, caught.exception.check)
                    self.assertNotIn(secret, str(caught.exception))
                    self.assertEqual('', output.getvalue())
        for secret in ('Account number: 1234567', '口座番号：1234567', '계좌번호: 1234567'):
            message = self.message()
            message['Text'] += ' ' + secret
            output = io.StringIO()
            with contextlib.redirect_stderr(output), contextlib.redirect_stdout(output):
                with self.assertRaises(module.MessageValidationError) as caught:
                    module.assert_message(message, 'en', 'http://127.0.0.1:18080', '/reset', self.forbidden())
            self.assertEqual('generic_bank_details', caught.exception.check)
            self.assertNotIn(secret, str(caught.exception))
            self.assertEqual('', output.getvalue())

    def test_native_reset_link_may_carry_secure_key_only_as_the_token(self):
        module = self.module()
        secure_key = self.forbidden()['customer_secure_key']
        url = ('http://127.0.0.1:18080/reset?token=' + secure_key
               + '&id_customer=7&reset_token=synthetic-reset')
        message = self.message('ja', url=url)
        self.assertEqual(url, module.assert_message(
            message, 'ja', 'http://127.0.0.1:18080', '/reset', self.forbidden()))

    def test_secure_key_outside_native_reset_token_still_fails_safely(self):
        module = self.module()
        secure_key = self.forbidden()['customer_secure_key']
        url = ('http://127.0.0.1:18080/reset?token=' + secure_key
               + '&id_customer=7&reset_token=synthetic-reset')
        message = self.message('ja', url=url)
        message['Text'] += ' ' + secure_key
        with self.assertRaises(module.MessageValidationError) as caught:
            module.assert_message(message, 'ja', 'http://127.0.0.1:18080', '/reset', self.forbidden())
        self.assertEqual('customer_secure_key_outside_reset_link', caught.exception.check)
        self.assertNotIn(secure_key, str(caught.exception))

    def test_secure_key_is_not_allowed_as_another_reset_credential(self):
        module = self.module()
        secure_key = self.forbidden()['customer_secure_key']
        url = ('http://127.0.0.1:18080/reset?token=synthetic-token'
               + '&reset_token=' + secure_key)
        message = self.message('ja', url=url)
        with self.assertRaises(module.MessageValidationError) as caught:
            module.assert_message(message, 'ja', 'http://127.0.0.1:18080', '/reset', self.forbidden())
        self.assertEqual('customer_secure_key_outside_reset_link', caught.exception.check)
        self.assertNotIn(secure_key, str(caught.exception))

    def test_all_named_secret_categories_are_required(self):
        module = self.module()
        forbidden = self.forbidden()
        del forbidden['password_hash']
        with self.assertRaisesRegex(ValueError, 'native reset secret categories required'):
            module.assert_message(self.message(), 'en', 'http://127.0.0.1:18080', '/reset', forbidden)

    def test_both_email_parts_must_identify_the_same_reset_credentials(self):
        module = self.module()
        message = self.message()
        message['Text'] = message['Text'].replace('synthetic-reset', 'different-reset')
        with self.assertRaises(module.MessageValidationError) as caught:
            module.assert_message(message, 'en', 'http://127.0.0.1:18080', '/reset', self.forbidden())
        self.assertEqual('parts_credentials_mismatch', caught.exception.check)

    def test_reset_credentials_must_be_nonempty_and_unambiguous(self):
        module = self.module()
        for query in ('token=&reset_token=x', 'token=x&reset_token=',
                      'token=x&token=y&reset_token=z', 'token=x&reset_token=z&id_customer='):
            with self.subTest(query=query), self.assertRaises(module.MessageValidationError) as caught:
                module.assert_message(self.message(url='http://127.0.0.1:18080/reset?' + query),
                                      'en', 'http://127.0.0.1:18080', '/reset', self.forbidden())
            self.assertEqual('reset_credentials_invalid', caught.exception.check)

    def test_message_failure_reason_is_closed_and_does_not_contain_message_data(self):
        module = self.module()
        secret = 'synthetic-reset-secret@example.invalid'
        url = 'https://outside.invalid/reset?token=' + secret + '&reset_token=another'
        with self.assertRaises(module.MessageValidationError) as caught:
            module.assert_message(self.message('ja', url=url), 'ja', 'http://127.0.0.1:18080', '/reset', self.forbidden())
        self.assertEqual('reset_link_origin_mismatch', caught.exception.check)
        self.assertNotIn(secret, str(caught.exception))

    def test_verified_email_link_is_returned_for_native_browser_navigation(self):
        module = self.module()
        message = self.message()
        message['HTML'] = message['HTML'].replace('http://127.0.0.1:18080/reset?', '/reset?')
        self.assertEqual('http://127.0.0.1:18080/reset?token=synthetic-token&reset_token=synthetic-reset',
                         module.assert_message(message, 'en', 'http://127.0.0.1:18080', '/reset', self.forbidden()))

    def test_native_reset_page_requires_expected_origin_path_and_document_language(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'assert_reset_page'), 'email link destination validator is missing')
        for language in ('ja', 'en', 'ko'):
            document = SimpleNamespace(get_attribute=lambda name: language)
            driver = SimpleNamespace(current_url='http://127.0.0.1:18080/reset?token=private',
                                     find_element=lambda *args: document)
            module.assert_reset_page(driver, language, 'http://127.0.0.1:18080', '/reset')
            for bad in ('http://external.invalid/reset', 'http://127.0.0.1:18080/login'):
                driver.current_url = bad
                with self.assertRaises(AssertionError):
                    module.assert_reset_page(driver, language, 'http://127.0.0.1:18080', '/reset')
            driver.current_url = 'http://127.0.0.1:18080/reset'
            driver.find_element = lambda *args: SimpleNamespace(get_attribute=lambda name: 'fr')
            with self.assertRaises(AssertionError):
                module.assert_reset_page(driver, language, 'http://127.0.0.1:18080', '/reset')

    def test_failure_output_excludes_exception_payload_tokens_and_addresses(self):
        module = self.module()
        secret = 'private@example.invalid token=synthetic-token password=synthetic-password'
        output = io.StringIO()
        with patch.object(module, 'validate_context', side_effect=RuntimeError(secret)):
            with contextlib.redirect_stderr(output), contextlib.redirect_stdout(output):
                self.assertFalse(module.run())
        self.assertEqual(
            output.getvalue(),
            'FAIL: isolated native reset email locale=none stage=context exception=RuntimeError; '
            'response_status=unavailable; message_check=none; same_origin=false; native_route=false; language_matches=false; '
            'email_field=false; submit_control=false; submit_center_in_viewport=false; '
            'submit_center_unobstructed=false; success_alert=false; reset_fields=false\n',
        )

    def test_failure_artifact_keeps_only_bounded_browser_facts(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as temp:
            artifact = Path(temp) / "ordenowa-browser-qa"
            result = {
                "status": "failure", "language": "ja", "stage": "native_request_email_field",
                "exception_type": "TimeoutException", "response_status": 404,
                "message_check": "none",
                "same_origin": True, "native_route": True, "language_matches": False,
                "email_field_present": False, "submit_control_present": False,
                "submit_center_in_viewport": False, "submit_center_unobstructed": False,
                "success_alert_present": False, "reset_fields_present": False,
            }
            with patch.dict(module.os.environ, {"RUNNER_TEMP": temp, "QA_ARTIFACT_DIR": str(artifact)}):
                module.write_diagnostics(result)
                path = artifact / "reset-email-locale-result.json"
                self.assertTrue(path.is_file())
                contents = path.read_text(encoding="utf-8")
                self.assertIn('"response_status": 404', contents)
                for sensitive in ("token", "password", "email@example", "http://", "current_url"):
                    self.assertNotIn(sensitive, contents)
                self.assertIn('"message_check": "none"', contents)
                category_result = dict(result, message_check='customer_secure_key_outside_reset_link')
                module.write_diagnostics(category_result)
                contents = path.read_text(encoding="utf-8")
                self.assertIn('"message_check": "customer_secure_key_outside_reset_link"', contents)
                self.assertNotIn('synthetic-customer-secure-key', contents)
                module.write_diagnostics(dict(result, token="never-write"))
                self.assertEqual(path.read_text(encoding="utf-8"), contents)

    def test_native_request_failure_is_split_into_safe_browser_substages(self):
        source = VERIFIER.read_text(encoding="utf-8")
        for stage in (
            "native_request_document", "native_request_email_field",
            "native_request_submit_control", "native_request_submit", "native_request_readback",
        ):
            with self.subTest(stage=stage):
                self.assertIn(stage, source)
        self.assertIn("navigation_status(driver)", source)
        self.assertIn("native_password_route(driver.current_url", source)
        self.assertIn("--window-size=1440,960", source)
        self.assertIn("document.elementFromPoint(x, y)", source)
        for exception in (
            "ElementClickInterceptedException", "ElementNotInteractableException",
            "StaleElementReferenceException",
        ):
            with self.subTest(exception=exception):
                self.assertIn(exception, source)

    def test_context_rejects_unowned_project_before_any_fixture_or_network_access(self):
        module = self.module()
        environment = {'CI': 'true', 'GITHUB_ACTIONS': 'true', 'KURANEA_ISOLATED_CI': '1',
                       'GITHUB_RUN_ID': '17', 'GITHUB_RUN_ATTEMPT': '2',
                       'CI_COMPOSE_PROJECT_NAME': 'kuranea-ci-17-2',
                       'SHOP_BASE_URL': 'http://127.0.0.1:18080',
                       'MAILPIT_API_URL': 'http://127.0.0.1:8025'}
        with patch.dict(module.os.environ, environment, clear=True):
            self.assertEqual(module.validate_context()[0], 'kuranea-ci-17-2')
            for key, value in (('CI_COMPOSE_PROJECT_NAME', 'live-shop'), ('CI', 'false'),
                               ('MAILPIT_API_URL', 'https://external.invalid:8025')):
                with patch.dict(module.os.environ, {key: value}):
                    with self.assertRaises(ValueError):
                        module.validate_context()

    def test_endpoint_validation_rejects_external_and_credential_urls(self):
        module = self.module()
        module.endpoint('http://127.0.0.1:8025', 8025)
        for url in ('http://evil.invalid:8025', 'http://u:p@localhost:8025',
                    'http://localhost:8025/path', 'https://localhost:8025'):
            with self.assertRaises(ValueError):
                module.endpoint(url, 8025)

    def test_native_locale_email_flow_is_run_and_aggregated_with_mailpit(self):
        workflow = WORKFLOW.read_text(encoding='utf-8')
        step = workflow.split('- name: Verify native password-reset emails in JA EN and KO', 1)[1].split('- name:', 1)[0]
        self.assertIn('id: reset_email_locale_browser_qa', step)
        self.assertIn("steps.mailpit_setup.outcome == 'success'", step)
        self.assertIn("steps.chromium_setup.outcome == 'success'", step)
        for key in ('CI: \'true\'', 'GITHUB_ACTIONS: \'true\'', 'KURANEA_ISOLATED_CI: \'1\'',
                    'KURANEA_CI_PROJECT_NAME:', 'MAILPIT_API_URL:', 'GITHUB_RUN_ID:', 'GITHUB_RUN_ATTEMPT:'):
            with self.subTest(key=key):
                self.assertIn(key, step)
        self.assertIn('tests/e2e/verify_ci_reset_email_locale.py', step)
        self.assertIn('reset-email-locale-e2e.log', step)
        self.assertIn('QA_ARTIFACT_DIR: ${{ runner.temp }}/ordenowa-browser-qa', step)
        coverage = workflow.split('- name: Verify browser QA screenshot coverage', 1)[1].split('- name:', 1)[0]
        self.assertIn('RESET_EMAIL_LOCALE_BROWSER_QA_OUTCOME: ${{ steps.reset_email_locale_browser_qa.outcome }}', coverage)
        self.assertIn('reset-email-locale-e2e.log', coverage)
        self.assertIn('reset-email-locale-result.json', coverage)
        aggregate = workflow.split('- name: Aggregate browser QA and postal verification failures', 1)[1].split('- name:', 1)[0]
        self.assertIn('RESET_EMAIL_LOCALE_BROWSER_QA_OUTCOME: ${{ steps.reset_email_locale_browser_qa.outcome }}', aggregate)
        self.assertIn('steps.reset_email_locale_browser_qa.outcome', aggregate)
        self.assertIn('"reset_email_locale=$RESET_EMAIL_LOCALE_BROWSER_QA_OUTCOME"', aggregate)
        preflight = workflow.split('- name: Verify fresh-install workflow contracts', 1)[1].split('- name:', 1)[0]
        self.assertIn('tests.e2e.test_ci_reset_email_locale_contract', preflight)


if __name__ == '__main__':
    unittest.main()
