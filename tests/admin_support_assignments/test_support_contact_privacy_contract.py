"""Module boundary and isolated browser wiring for account-owned contact privacy."""
from pathlib import Path

from tests.e2e.test_ci_customer_support_browser_contract import load_script
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SupportContactPrivacyContractTests(unittest.TestCase):
    def test_owned_module_hook_guards_native_contact_before_render_and_submission(self):
        module = (ROOT / 'modules/kuraneabackoffice/kuraneabackoffice.php').read_text()
        self.assertTrue('hookActionFrontControllerInitAfter' in module, 'contact privacy requires a module-owned initialization guard')
        self.assertTrue('SupportContactAccessGuard::allows' in module)
        self.assertTrue("$controller->php_self" in module)
        self.assertTrue("'contact'" in module)
        self.assertTrue('http_response_code(403)' in module)
        upgrade = ROOT / 'modules/kuraneabackoffice/upgrade/upgrade-1.0.4.php'
        self.assertTrue(upgrade.is_file(), 'installed modules must register the privacy hook through an upgrade')
        self.assertTrue('installSupportContactPrivacy' in upgrade.read_text())

    def test_project_bootstrap_repairs_privacy_hook_for_preinstalled_modules(self):
        module_bootstrap = (ROOT / 'docker/kuran-install-modules.php').read_text()
        self.assertIn("$backofficeModule->installSupportContactPrivacy()", module_bootstrap)
        self.assertLess(
            module_bootstrap.index("foreach (['kuraneapostcode'"),
            module_bootstrap.index("$backofficeModule->installSupportContactPrivacy()"),
        )

    def test_isolated_browser_covers_valid_links_and_orderless_post_with_admin_readback(self):
        source = (ROOT / 'tests/e2e/verify_ci_customer_support_browser.py').read_text()
        for boundary in ('foreign_valid_thread_denied', 'foreign_orderless_post_denied',
                         'orderless_thread_unchanged', 'order_linked=False',
                         'assert_foreign_thread_denied(foreign, valid_customer_thread_url)',
                         'assert_foreign_orderless_post_denied(foreign, ctx, attack_marker)',
                         'orderless_marker not in orderless_body or attack_marker in orderless_body'):
            with self.subTest(boundary=boundary):
                self.assertTrue(boundary in source, 'missing customer-isolation acceptance boundary: ' + boundary)

    def test_denial_probe_rejects_success_login_redirect_and_transport_failure(self):
        support = load_script()
        support.assert_support_denied_response({'status': 403, 'formPresent': False})
        for response in (None, {}, {'status': 0, 'formPresent': False},
                         {'status': 200, 'formPresent': False}, {'status': 403, 'formPresent': True}):
            with self.subTest(response=response), self.assertRaises(AssertionError):
                support.assert_support_denied_response(response)

    def test_behavior_fixture_is_in_existing_assignment_php_entrypoint(self):
        fixture = ROOT / 'tests/admin_support_assignments/contact_privacy_guard.php'
        self.assertTrue(fixture.is_file(), 'the guard needs isolated native-object behavior cases')
        source = (ROOT / 'tests/admin_support_assignments/assignment_repository.php').read_text()
        self.assertTrue("require_once __DIR__ . '/contact_privacy_guard.php'" in source)


if __name__ == '__main__':
    unittest.main()
