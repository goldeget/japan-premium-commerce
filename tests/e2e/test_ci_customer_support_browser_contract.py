"""Contracts for the isolated PrestaShop 9.2 native support-thread browser acceptance."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tests" / "e2e" / "verify_ci_customer_support_browser.py"
FIXTURE = ROOT / "tests" / "business_profile" / "prepare_customer_support_fixture.php"
CONTACT_TEMPLATE = ROOT / "themes" / "hummingbird" / "modules" / "contactform" / "views" / "templates" / "widget" / "contactform.tpl"
WORKFLOW = ROOT / ".github/workflows/fresh-install.yml"


def load_script():
    if not SCRIPT.is_file():
        raise AssertionError("the isolated native customer-support browser test is missing")
    spec = importlib.util.spec_from_file_location("ordenowa_native_customer_support", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("the isolated customer-support browser test cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CustomerSupportBrowserContractTests(unittest.TestCase):
    def test_official_hummingbird_contact_form_fields_match_native_acceptance(self):
        source = CONTACT_TEMPLATE.read_text(encoding="utf-8")
        for expected in (
            'id="contact-us-id-order-select" name="id_order"',
            'name="fileUpload"',
            'name="message"',
            'name="submitMessage"',
            'name="token"',
        ):
            with self.subTest(field=expected):
                self.assertIn(expected, source)

    def test_browser_acceptance_is_run_scoped_and_uses_native_customer_and_admin_controls(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for expected in (
            'f"ci-checkout-{viewport}.json"',
            "ps_checkpayment", "total_paid_real", "#contact-us-id-order-select",
            "input[type='file'][name='fileUpload']", "submitMessage",
            "/sell/customer-service/customer-threads", "AdminCustomerThreads",
            "[data-role='messages-thread']", "[data-role='employee-answer']",
            "[name='newStatus'][value='{status}']", "#forwardThreadModal",
            "VIEW_ONLY_EMAIL", "customer_reply_url", "attachment_admin_readback",
            "payment_provider_called",
        ):
            with self.subTest(contract=expected):
                self.assertIn(expected, source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("UPDATE `ps_", source)
        self.assertNotIn("INSERT INTO `ps_", source)

    def test_png_and_text_attachments_keep_same_thread_and_negative_access_checks(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for expected in (
            'suffix=".txt"', 'suffix=".png"', 'suffix=".php"',
            'expected_rejection=True', 'disallowed_attachment_rejected',
            'image_attachment_admin_readback', 'image_attachment_foreign_denied',
            'submit_contact_message(customer, ctx, ctx.buyer, followup_marker, image_file, customer_reply_url)',
            'read_native_image_attachment(admin, image_url, image_bytes)',
            'attachment_visible_to_session(foreign, image_url, image_marker)',
            'validate_synthetic_upload(attachment_path.name, attachment_path.read_bytes(), expected_mime)',
            'metadata.get("mime") != expected_mime',
        ):
            with self.subTest(boundary=expected):
                self.assertTrue(expected in source, "missing image acceptance boundary: " + expected)
        fixture = FIXTURE.read_text(encoding="utf-8")
        self.assertIn('Tools::getMaxUploadSize() >= 4096', fixture)

    def test_native_reply_form_is_found_through_its_official_9_2_wrapper(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('reply_card.find_element(By.XPATH, "./ancestor::form[1]")', source)
        self.assertIn("textarea[name$='[reply_message]']", source)
        self.assertIn('reply_form.find_elements(By.CSS_SELECTOR, "button")', source)
        self.assertNotIn('reply_card.find_element(By.CSS_SELECTOR, "form")', source)

    def test_thread_list_lookup_uses_the_untruncated_run_scoped_customer_identity(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('buyer["email"] in text', source)
        self.assertNotIn("marker in text or (buyer[\"reference\"] in text", source)

    def test_assignment_lifecycle_is_same_thread_persistent_and_role_gated(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for expected in (
            "AdminKuraneaSupportAssignments", "assign_thread(admin, thread_id, first_employee_id)",
            "assign_thread(admin, thread_id, second_employee_id)",
            "selected_assignment_employee(admin, thread_id) != first_employee_id",
            "selected_assignment_employee(admin, thread_id) != second_employee_id",
            "assert_assignment_history(admin, thread_id, first_employee_name, second_employee_name)",
            "assignment_limited_employee_denied",
            "latest support assignment history did not retain prior, new, and acting employees",
        ):
            with self.subTest(contract=expected):
                self.assertIn(expected, source)

    def test_thread_identity_and_customer_reply_links_fail_closed(self):
        module = load_script()
        admin = "http://localhost:18080/admin-kuranea"
        shop = "http://localhost:18080"
        self.assertEqual((47, "AbC123xYz890"), module.parse_thread_email_subject("Your message #ct47 #tcAbC123xYz890"))
        self.assertIsNone(module.parse_thread_email_subject("Your message #ct0 #tcAbC123xYz890"))
        self.assertTrue(module.validate_customer_thread_url(
            "/contact?id_customer_thread=47&token=AbC123xYz890", shop, 47
        ))
        self.assertTrue(module.validate_customer_thread_url(
            "/index.php?controller=contact&id_customer_thread=47&token=AbC123xYz890", shop, 47
        ))
        for candidate in (
            "https://outside.example/contact?id_customer_thread=47&token=AbC123xYz890",
            "/contact?id_customer_thread=48&token=AbC123xYz890",
            "/contact?id_customer_thread=47&token=AbC123xYz890&token=otherToken123",
            "/contact?controller=authentication&id_customer_thread=47&token=AbC123xYz890",
            "//outside.example/contact?id_customer_thread=47&token=AbC123xYz890",
        ):
            with self.subTest(candidate=candidate):
                self.assertFalse(module.validate_customer_thread_url(candidate, shop, 47))
        self.assertEqual(
            ("modern_thread_view", 47),
            module.thread_route_identity(f"{admin}/sell/customer-service/customer-threads/47/view", admin),
        )
        self.assertEqual(
            ("legacy_thread_view", 47),
            module.thread_route_identity(f"{admin}/index.php?controller=AdminCustomerThreads&id_customer_thread=47&viewcustomer_thread=1&token=workerToken", admin),
        )
        for candidate in (
            f"{admin}-evil/sell/customer-service/customer-threads/47/view",
            f"{admin}/sell/customer-service/customer-threads/47/view/extra",
            f"https://outside.example/admin-kuranea/sell/customer-service/customer-threads/47/view",
            f"{admin}/index.php?controller=AdminOrders&id_customer_thread=47&viewcustomer_thread=1",
        ):
            with self.subTest(candidate=candidate):
                self.assertIsNone(module.thread_route_identity(candidate, admin))

    def test_employee_scoped_routes_keep_native_session_tokens_separate(self):
        module = load_script()

        class Link:
            def __init__(self, href):
                self.href = href

            def get_attribute(self, name):
                return self.href if name == "href" else None

        class Driver:
            current_url = "http://localhost:18080/admin-kuranea/index.php?controller=AdminDashboard&token=limitedToken"

            def find_elements(self, *_args):
                return [Link("http://localhost:18080/admin-kuranea/index.php?controller=AdminDashboard&token=limitedToken")]

        admin = "http://localhost:18080/admin-kuranea"
        modern = f"{admin}/sell/customer-service/customer-threads/47/view?token=adminToken&_token=other"
        scoped = module.employee_scoped_thread_url(object(), modern, admin)
        self.assertEqual("/admin-kuranea/sell/customer-service/customer-threads/47/view", urlparse(scoped).path)
        self.assertEqual({}, parse_qs(urlparse(scoped).query))

        legacy = f"{admin}/index.php?controller=AdminCustomerThreads&id_customer_thread=47&viewcustomer_thread&token=adminToken"
        original_by = module.By
        module.By = type("By", (), {"CSS_SELECTOR": "css selector"})
        try:
            employee_url = module.employee_scoped_thread_url(Driver(), legacy, admin)
        finally:
            module.By = original_by
        parsed = urlparse(employee_url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        self.assertEqual(["limitedToken"], query["token"])
        self.assertNotIn("adminToken", employee_url)

    def test_unpaid_order_fixture_is_bound_to_each_run_scoped_customer(self):
        module = load_script()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = {
                "desktop": (41, "ABCD1234", "qa-ordenowa-checkout-403300-2-desktop@example.invalid"),
                "mobile": (42, "EFGH5678", "qa-ordenowa-checkout-403300-2-mobile@example.invalid"),
            }
            for viewport, (order_id, reference, email) in rows.items():
                (root / f"ci-checkout-{viewport}.json").write_text(json.dumps({
                    "viewport": viewport, "order_id": order_id, "reference": reference, "email": email,
                }), encoding="utf-8")
                (root / f"ci-checkout-{viewport}-verified.json").write_text(json.dumps({
                    "order_id": order_id, "reference": reference, "email": email,
                    "payment_module": "ps_checkpayment", "total_paid_real": 0,
                }), encoding="utf-8")
            self.assertEqual("desktop", module.load_order(root, "desktop", "403300", "2")["email"].split("-")[-1].split("@")[0])
            bad_path = root / "ci-checkout-desktop-verified.json"
            bad = json.loads(bad_path.read_text(encoding="utf-8"))
            bad["total_paid_real"] = 1100
            bad_path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                module.load_order(root, "desktop", "403300", "2")

    def test_fixture_only_enables_native_upload_and_confirmation_inside_disposable_ci(self):
        source = FIXTURE.read_text(encoding="utf-8")
        for expected in (
            "getenv('GITHUB_ACTIONS') === 'true'", "getenv('KURANEA_ISOLATED_CI') === '1'",
            "getenv('KURANEA_CI_PROJECT_NAME') === $expectedProject",
            "kuranea-ci-%s-%s", "Module::isEnabled('contactform')",
            "PS_CUSTOMER_SERVICE_FILE_UPLOAD", "CONTACTFORM_SEND_CONFIRMATION_EMAIL",
            "CONTACTFORM_SEND_NOTIFICATION_EMAIL",
        ):
            with self.subTest(contract=expected):
                self.assertIn(expected, source)
        self.assertNotIn("Mail::Send", source)
        self.assertNotIn("CustomerThread", source)

    def test_native_support_browser_runs_on_verified_unpaid_orders_before_admin_cancellation(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        fixture = workflow.split("- name: Prepare isolated native customer support settings", 1)[1].split("- name:", 1)[0]
        browser = workflow.split("- name: Verify native customer support lifecycle in Chromium", 1)[1].split("- name:", 1)[0]
        self.assertIn("id: customer_support_fixture", fixture)
        self.assertIn("steps.checkout_order_persistence.outcome == 'success'", fixture)
        self.assertIn("prepare_customer_support_fixture.php", fixture)
        self.assertIn("id: customer_support_browser_qa", browser)
        for dependency in ("steps.customer_support_fixture.outcome == 'success'",
                           "steps.security_fixture.outcome == 'success'",
                           "steps.mailpit_setup.outcome == 'success'",
                           "steps.chromium_setup.outcome == 'success'"):
            with self.subTest(dependency=dependency):
                self.assertIn(dependency, browser)
        self.assertIn("VIEW_ONLY_EMAIL: ${{ env.VIEW_ONLY_EMPLOYEE_EMAIL }}", browser)
        self.assertIn("tests/e2e/verify_ci_customer_support_browser.py", browser)
        self.assertIn("customer-support-e2e.log", browser)
        self.assertLess(workflow.index("- name: Verify native customer support lifecycle in Chromium"),
                        workflow.index("- name: Verify a separate admin session can view both browser orders"))
        coverage = workflow.split("- name: Verify browser QA screenshot coverage", 1)[1].split("- name:", 1)[0]
        self.assertIn("CUSTOMER_SUPPORT_BROWSER_QA_OUTCOME: ${{ steps.customer_support_browser_qa.outcome }}", coverage)
        self.assertIn('"$CUSTOMER_SUPPORT_BROWSER_QA_OUTCOME" == success', coverage)
        for evidence in (
            "customer-support-fixture.log", "customer-support-e2e.log",
            "customer-support-browser-result.json", "customer-support-inquiry-submitted.png",
            "customer-support-foreign-denied.png", "customer-support-admin-thread.png",
            "customer-support-assignment-created.png", "customer-support-assignment-history.png",
        ):
            with self.subTest(evidence=evidence):
                self.assertIn(evidence, coverage)
        aggregate = workflow.split("- name: Aggregate browser QA and postal verification failures", 1)[1].split("- name:", 1)[0]
        self.assertIn("CUSTOMER_SUPPORT_BROWSER_QA_OUTCOME: ${{ steps.customer_support_browser_qa.outcome }}", aggregate)
        self.assertIn("steps.customer_support_browser_qa.outcome", aggregate)
        self.assertIn('"customer_support=$CUSTOMER_SUPPORT_BROWSER_QA_OUTCOME"', aggregate)
        preflight = workflow.split("- name: Verify fresh-install workflow contracts", 1)[1].split("- name:", 1)[0]
        self.assertIn("tests.e2e.test_ci_customer_support_browser_contract", preflight)

    def test_diagnostic_writer_only_accepts_allowlisted_nonsecret_fields(self):
        module = load_script()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "result.json"
            result = {
                "status": "success", "stage": "complete", "exception_type": None,
                "customer_submitted": True, "order_association_verified": True,
                "attachment_admin_readback": True, "private_note_admin_only": True,
                "status_close_reopen": True, "admin_public_reply": True,
                "customer_followup_same_thread": True, "foreign_customer_denied": True,
                "limited_employee_denied": True, "mailpit_provider": "isolated_only",
                "paid": False, "payment_provider_called": False, "assignment_created": True,
                "assignment_reassigned": True, "assignment_actor_history": True,
                "assignment_limited_employee_denied": True,
                "image_attachment_admin_readback": True, "image_attachment_foreign_denied": True,
                "disallowed_attachment_rejected": True,
                "foreign_valid_thread_denied": True, "foreign_orderless_post_denied": True,
                "orderless_thread_unchanged": True,
                "contact_document_status": 200, "contact_same_origin": True,
                "contact_native_route": True, "contact_form_count": 1,
                "contact_form_visible": True,
            }
            module.write_result(path, result)
            content = path.read_text(encoding="utf-8")
            for sensitive in ("token", "password", "email", "thread_url", "customer_name"):
                with self.subTest(sensitive=sensitive):
                    self.assertNotIn(f'"{sensitive}"', content)
            unsafe = dict(result, token="never-write")
            with self.assertRaises(ValueError):
                module.write_result(path, unsafe)
            incomplete = dict(result, assignment_actor_history=False)
            with self.assertRaises(ValueError):
                module.write_result(path, incomplete)

    def test_contact_failure_diagnostics_are_safe_and_record_status_route_and_form(self):
        browser = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "def contact_page_evidence(driver, shop_url: str)",
            "contact_document_status", "contact_same_origin", "contact_native_route",
            "contact_form_count", "contact_form_visible",
            "result.update(contact_page_evidence(customer, ctx.shop))",
            "performance.getEntriesByType('navigation')",
        ):
            with self.subTest(required=required):
                self.assertIn(required, browser)
        helper = browser[browser.index("def contact_page_evidence"):browser.index("def safe_admin_path")]
        self.assertNotIn('"current_url"', helper)
        for safe_field in (
            "contact_status={contact_status}", "same_origin=",
            "native_route=", "form_count=", "form_visible=",
        ):
            with self.subTest(safe_field=safe_field):
                self.assertIn(safe_field, browser)

    def test_contact_uses_shop_generated_locale_routes_and_probes_legacy_query_route(self):
        browser = SCRIPT.read_text(encoding="utf-8")
        route_helper = (ROOT / "tests/e2e/native_contact_route.py").read_text(encoding="utf-8")
        for required in (
            "CONTACT_ROUTE_FIXTURE", "contact_url=route_fixture[\"urls_by_iso\"][\"ja\"]",
            "probe_contact_route(customer, query_route, ctx.shop)",
            "probe_contact_route(customer, ctx.contact_url, ctx.shop)",
            "CONTACT_ROUTE_DIAGNOSTIC", "contact_route_class(driver.current_url, shop_url)",
            "private_no_store", "credentials: 'same-origin'", "cache: 'no-store'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, browser + route_helper)
        self.assertIn("getPageLink('contact', null, $idLang)", (ROOT / "tests/business_profile/read_native_contact_route.php").read_text())
        self.assertIn("Module::isEnabled('contactform')", (ROOT / "tests/business_profile/read_native_contact_route.php").read_text())


if __name__ == "__main__":
    unittest.main()
