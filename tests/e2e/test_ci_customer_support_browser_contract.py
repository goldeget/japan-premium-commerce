"""Contracts for the isolated PrestaShop 9.2 native support-thread browser acceptance."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
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
            "admin_login_completed", "admin_service_route_discovery",
            "customer_service_route_candidate_count", "customer_service_route_safe_count",
            "customer_service_route_modern_count", "customer_service_route_legacy_count",
            "customer_service_route_invalid_count",
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

    def test_contact_controls_scroll_clear_and_keep_native_select_and_upload_assertions(self):
        module = load_script()

        class Driver:
            def __init__(self, unobscured: bool) -> None:
                self.unobscured = unobscured
                self.scripts: list[str] = []

            def execute_script(self, script: str, _element: object) -> object:
                self.scripts.append(script)
                return None if len(self.scripts) == 1 else self.unobscured

        clear_driver = Driver(True)
        element = object()
        module.center_native_control(
            clear_driver, element, "message submit",
            scroll_substage="submit_control_scroll", hit_test_substage="submit_control_hit_test",
        )
        self.assertIn("scrollIntoView", clear_driver.scripts[0])
        self.assertIn("block: 'center'", clear_driver.scripts[0])
        self.assertIn("elementFromPoint", clear_driver.scripts[1])
        self.assertNotIn(".click()", "\n".join(clear_driver.scripts))

        obstructed_driver = Driver(False)
        with self.assertRaisesRegex(AssertionError, "message submit control is obstructed"):
            module.center_native_control(
                obstructed_driver, element, "message submit",
                scroll_substage="submit_control_scroll", hit_test_substage="submit_control_hit_test",
            )

        source = SCRIPT.read_text(encoding="utf-8")
        submit_helper = source[source.index("def submit_contact_message("):source.index("def assert_support_denied_response")]
        self.assertIn("select_contact_order(", submit_helper)
        self.assertIn('str(order["order_id"]), diagnostic_result=diagnostic_result', submit_helper)
        self.assertIn('select_contact_order(driver, order_selects[0], "", diagnostic_result=diagnostic_result)', submit_helper)
        self.assertIn('order["reference"] not in matching_options[0].text', submit_helper)
        self.assertIn('submit = visible(driver, "button[name=\'submitMessage\']")', submit_helper)
        self.assertIn("center_native_control(", submit_helper)
        self.assertIn('scroll_substage="submit_control_scroll"', submit_helper)
        self.assertIn('hit_test_substage="submit_control_hit_test"', submit_helper)
        self.assertIn("submit.click()", submit_helper)
        self.assertIn('driver.find_elements(By.CSS_SELECTOR, ".contact-form .alert.alert-danger")', submit_helper)
        self.assertNotIn("arguments[0].click()", submit_helper)
        native_select = source[source.index("def select_contact_order("):source.index("def visit(")]
        self.assertIn("Select(select_element).select_by_value(value)", native_select)
        self.assertNotIn("select_element.click()", native_select)
        self.assertNotIn("Keys.HOME", native_select)
        self.assertNotIn("Keys.ARROWDOWN", native_select)
        self.assertNotIn("execute_script", native_select)
        self.assertIn('select_element.get_attribute("value") != value', native_select)

    def test_native_order_select_uses_exact_value_and_records_native_option_failure(self):
        module = load_script()
        module.By = SimpleNamespace(TAG_NAME="tag name")

        class Option:
            text = "ORDENOWA-REF-42"

            def get_attribute(self, name: str) -> str | None:
                return "order-42" if name == "value" else None

            def is_enabled(self) -> bool:
                return True

        class NativeSelect:
            selected_value = ""

            def find_elements(self, *_args: object) -> list[Option]:
                return [Option()]

            def click(self) -> None:
                raise AssertionError("native select control must not be clicked")

            def get_attribute(self, name: str) -> str | None:
                return self.selected_value if name == "value" else None

        class NativeSelectWrapper:
            def __init__(self, element: NativeSelect) -> None:
                self.element = element

            def select_by_value(self, value: str) -> None:
                self.element.selected_value = value

        module.Select = NativeSelectWrapper

        class Driver:
            calls = 0

            def execute_script(self, _script: str, _element: object) -> object:
                self.calls += 1
                return None if self.calls == 1 else True

        diagnostic = {"browser_substage": "not_applicable"}
        select = NativeSelect()
        module.select_contact_order(Driver(), select, "order-42", diagnostic_result=diagnostic)
        self.assertEqual("order-42", select.selected_value)
        self.assertEqual("order_select_readback", diagnostic["browser_substage"])

        class FailingNativeSelectWrapper(NativeSelectWrapper):
            def select_by_value(self, _value: str) -> None:
                raise RuntimeError("synthetic native option failure with private sentinel")

        module.Select = FailingNativeSelectWrapper
        diagnostic = {"browser_substage": "not_applicable"}
        with self.assertRaisesRegex(RuntimeError, "synthetic native option failure"):
            module.select_contact_order(Driver(), NativeSelect(), "order-42", diagnostic_result=diagnostic)
        self.assertEqual("order_select_native_option", diagnostic["browser_substage"])
        self.assertIn(diagnostic["browser_substage"], module.SAFE_BROWSER_SUBSTAGES)
        self.assertNotIn("private sentinel", diagnostic["browser_substage"])

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
            "/contact?id_customer_thread=47&token=AbC123xYz890&unexpected=private",
        ):
            with self.subTest(candidate=candidate):
                self.assertFalse(module.validate_customer_thread_url(candidate, shop, 47))
        self.assertTrue(module.validate_customer_thread_url(
            "/?controller=contact&id_lang=1&id_customer_thread=47&token=AbC123xYz890", shop, 47,
            locale="ja",
        ))
        canonical_thread_url = module.native_customer_thread_url(
            "/?controller=contact&id_lang=1", shop, 47, "AbC123xYz890",
            locale="ja", localized_rewrite=None,
        )
        self.assertEqual(
            {"controller": ["contact"], "id_lang": ["1"],
             "id_customer_thread": ["47"], "token": ["AbC123xYz890"]},
            parse_qs(urlparse(canonical_thread_url).query),
        )
        self.assertEqual("/", urlparse(canonical_thread_url).path)
        for route in ("https://outside.example/contact", "/private", "/index.php?controller=authentication"):
            with self.subTest(route=route), self.assertRaisesRegex(ValueError, "contact route fixture"):
                module.native_customer_thread_url(
                    route if "://" in route else shop + route,
                    shop, 47, "AbC123xYz890", locale="ja", localized_rewrite=None,
                )
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

    def test_order_association_uses_exact_native_route_specific_evidence(self):
        module = load_script()
        module.By = SimpleNamespace(CSS_SELECTOR="a[href]")

        class Link:
            def __init__(self, href, displayed=True):
                self.href = href
                self.displayed = displayed

            def is_displayed(self):
                return self.displayed

            def get_attribute(self, name):
                return self.href if name == "href" else None

        class TimelineItem:
            def __init__(self, text, displayed=True):
                self.text = text
                self.displayed = displayed

            def is_displayed(self):
                return self.displayed

        class Driver:
            def __init__(self, current_url, links=(), timeline_items=()):
                self.current_url = current_url
                self.links = links
                self.timeline_items = timeline_items

            def find_elements(self, _by, selector):
                if selector in {"a[href]", "[data-role='messages_timeline'] a[href]"}:
                    return self.links
                if selector == "#orders-and-messages-block .timeline-item":
                    return self.timeline_items
                return []

        admin = "http://127.0.0.1:18080/admin-kuranea"
        modern_url = admin + "/sell/customer-service/customer-threads/47/view"
        modern_exact = Driver(
            modern_url,
            links=[Link(admin + "/index.php?controller=AdminOrders&vieworder=1&id_order=42")],
        )
        modern_wrong_order = Driver(
            modern_url,
            links=[Link(admin + "/index.php?controller=AdminOrders&vieworder=1&id_order=43")],
        )
        modern_foreign = Driver(
            modern_url,
            links=[Link("https://outside.example/admin-kuranea/index.php?controller=AdminOrders&id_order=42")],
        )
        modern_hidden = Driver(
            modern_url,
            links=[Link(admin + "/index.php?controller=AdminOrders&vieworder=1&id_order=42", displayed=False)],
        )
        modern_wrong_controller = Driver(
            modern_url,
            links=[Link(admin + "/index.php?controller=AdminCustomers&id_order=42")],
        )
        modern_order_list = Driver(
            modern_url,
            links=[Link(admin + "/index.php?controller=AdminOrders&id_order=42")],
        )
        modern_rewritten_path = Driver(
            modern_url,
            links=[Link(admin + "/index.php/sell/orders/42/view")],
        )
        self.assertTrue(module.has_thread_order_association(modern_exact, 42, "modern_thread_view", 47, admin))
        self.assertFalse(module.has_thread_order_association(modern_wrong_order, 42, "modern_thread_view", 47, admin))
        self.assertFalse(module.has_thread_order_association(modern_foreign, 42, "modern_thread_view", 47, admin))
        self.assertFalse(module.has_thread_order_association(modern_hidden, 42, "modern_thread_view", 47, admin))
        self.assertFalse(module.has_thread_order_association(modern_wrong_controller, 42, "modern_thread_view", 47, admin))
        self.assertFalse(module.has_thread_order_association(modern_order_list, 42, "modern_thread_view", 47, admin))
        self.assertTrue(module.has_thread_order_association(modern_rewritten_path, 42, "modern_thread_view", 47, admin))

        legacy_url = admin + "/index.php?controller=AdminCustomerThreads&id_customer_thread=47&viewcustomer_thread=1&token=safe"
        legacy_exact = Driver(legacy_url, timeline_items=[TimelineItem("Message Order #42")])
        legacy_other = Driver(legacy_url, timeline_items=[TimelineItem("Message Order #142")])
        legacy_hidden = Driver(legacy_url, timeline_items=[TimelineItem("Message Order #42", displayed=False)])
        wrong_thread = Driver(
            admin + "/index.php?controller=AdminCustomerThreads&id_customer_thread=48&viewcustomer_thread=1&token=safe",
            timeline_items=[TimelineItem("Message Order #42")],
        )
        self.assertTrue(module.has_thread_order_association(legacy_exact, 42, "legacy_thread_view", 47, admin))
        self.assertFalse(module.has_thread_order_association(legacy_other, 42, "legacy_thread_view", 47, admin))
        self.assertFalse(module.has_thread_order_association(legacy_hidden, 42, "legacy_thread_view", 47, admin))
        self.assertFalse(module.has_thread_order_association(wrong_thread, 42, "legacy_thread_view", 47, admin))

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
                "browser_substage": "not_applicable",
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
                "support_denial_status": 403, "support_denial_form_count": 0,
                "support_denial_redirected": False, "support_denial_same_origin": True,
                "customer_service_route_candidate_count": 1,
                "customer_service_route_safe_count": 1,
                "customer_service_route_modern_count": 0,
                "customer_service_route_legacy_count": 1,
                "customer_service_route_invalid_count": 0,
                "admin_thread_message_marker_present": True,
                "admin_thread_order_association_present": True,
            }
            module.write_result(path, result)
            content = path.read_text(encoding="utf-8")
            for sensitive in ("token", "password", "email", "thread_url", "customer_name"):
                with self.subTest(sensitive=sensitive):
                    self.assertNotIn(f'"{sensitive}"', content)
            unsafe = dict(result, token="never-write")
            with self.assertRaises(ValueError):
                module.write_result(path, unsafe)
            unsafe_substage = dict(result, browser_substage="contact:private-email-sentinel")
            with self.assertRaises(ValueError):
                module.write_result(path, unsafe_substage)
            incomplete = dict(result, assignment_actor_history=False)
            with self.assertRaises(ValueError):
                module.write_result(path, incomplete)

    def test_contact_failure_diagnostics_are_safe_and_record_status_route_and_form(self):
        browser = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "def contact_page_evidence(",
            "contact_document_status", "contact_same_origin", "contact_native_route",
            "contact_form_count", "contact_form_visible",
            "support_denial_status", "support_denial_form_count", "support_denial_redirected",
            "support_denial_same_origin", "foreign_invalid_token_probe",
            "foreign_owned_thread_probe", "foreign_orderless_thread_probe",
            "foreign_orderless_post_probe",
            "browser_substage={result['browser_substage']}", "SAFE_BROWSER_SUBSTAGES",
            "result.update(contact_page_evidence(",
            "locale=locale", "localized_rewrite=localized_rewrite",
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

        route_helper = browser[browser.index("def generated_customer_threads_links("):browser.index("def admin_login(")]
        self.assertIn("diagnostic_result: dict[str, Any] | None = None", route_helper)
        self.assertIn('diagnostic_result["customer_service_route_candidate_count"]', route_helper)
        self.assertIn('diagnostic_result["customer_service_route_safe_count"]', route_helper)
        self.assertIn("return [href for _route_kind, _alias_rank, href in sorted(ordered)]", route_helper)
        self.assertIn('customer_threads_navigation_identity(href, admin_url)', route_helper)
        self.assertIn('native Customer service navigation exposed a noncanonical route', route_helper)
        self.assertIn("resolve_customer_threads_index(", browser)
        self.assertIn("thread_id == expected_thread_id", browser)
        self.assertNotIn('return sorted(safe_candidates', route_helper)
        self.assertNotIn("print(", route_helper)
        resolver = browser[browser.index("def resolve_customer_threads_index("):browser.index("def has_thread_order_link(")]
        self.assertIn("candidate_budget = remaining / (len(candidates) - candidate_index)", resolver)
        self.assertIn("navigation_budget = min(10.0, max(0.1, candidate_budget / 2))", resolver)
        self.assertIn("timeout=readback_budget", resolver)
        detail = browser[browser.index("def visit_exact_customer_thread_detail("):browser.index("def has_thread_order_link(")]
        self.assertIn('"admin_thread_detail_navigation"', detail)
        self.assertIn('"admin_thread_detail_readback"', detail)
        self.assertIn("except TimeoutException:", detail)
        self.assertIn("thread_route_identity(browser.current_url, admin_url)", detail)
        self.assertIn("identity != requested_identity", detail)
        self.assertIn("identity[1] != expected_thread_id", detail)
        self.assertIn("customer_thread_detail_selector(requested_identity[0])", detail)
        selector_helper = browser[browser.index("def customer_thread_detail_selector("):browser.index("def has_thread_order_link(")]
        self.assertIn('if route_kind == "modern_thread_view"', selector_helper)
        self.assertIn('return "[data-role=\'messages-thread\']"', selector_helper)
        self.assertIn('if route_kind == "legacy_thread_view"', selector_helper)
        self.assertIn('return ".message-item-initial"', selector_helper)
        self.assertIn("native legacy customer_threads view renders the original", selector_helper)
        self.assertIn("visit_exact_customer_thread_detail(", browser)
        self.assertIn("thread_view_url = index_thread_view_url", browser)
        self.assertNotIn("modern_customer_thread_detail_url(ctx.admin, thread_id)", browser)
        self.assertIn('mark_browser_substage(result, "admin_thread_message_readback")', browser)
        self.assertIn('mark_browser_substage(result, "admin_thread_order_association_readback")', browser)
        self.assertIn('"admin_thread_message_marker_present"', browser)
        self.assertIn('"admin_thread_order_association_present"', browser)
        identity_helper = browser[browser.index("def customer_threads_navigation_identity("):browser.index("def thread_route_identity(")]
        self.assertIn('parse_qsl(candidate.query, keep_blank_values=True, strict_parsing=True)', identity_helper)
        self.assertIn('if key in query:', identity_helper)
        self.assertIn('set(query) == {"controller", "token"}', identity_helper)
        self.assertIn('return "legacy", token', identity_helper)
        run = browser[browser.index("stage = result[\"stage\"] = \"admin_login\"", browser.index("def run()")):]
        self.assertLess(run.index('mark_browser_substage(result, "admin_login_completed")'),
                        run.index('stage = result["stage"] = "admin_thread_lookup"'))
        self.assertLess(run.index('stage = result["stage"] = "admin_thread_lookup"'),
                        run.index('mark_browser_substage(result, "admin_service_route_discovery")'))
        self.assertIn("generated_customer_threads_links(admin, ctx.admin, result)", run)
        self.assertIn("resolve_customer_threads_index(", run)
        self.assertIn('admin_route_candidates={result[\'customer_service_route_candidate_count\']}', run)

    def test_multiple_safe_native_thread_route_aliases_are_candidates_for_thread_readback(self):
        module = load_script()
        module.By = SimpleNamespace(CSS_SELECTOR="css selector")
        admin_root = "http://127.0.0.1:18080/admin-test"
        modern = admin_root + "/index.php/sell/customer-service/customer-threads?token=modern-safe"
        legacy = admin_root + "/index.php?controller=AdminCustomerThreads&token=legacy-safe"

        class Link:
            def __init__(self, href: str) -> None:
                self.href = href

            def get_attribute(self, _name: str) -> str:
                return self.href

        class Driver:
            def find_elements(self, _by: str, _selector: str) -> list[Link]:
                return [Link(legacy), Link(modern)]

        diagnostic: dict[str, object] = {}
        self.assertEqual([modern, legacy], module.generated_customer_threads_links(Driver(), admin_root, diagnostic))
        self.assertEqual(2, diagnostic["customer_service_route_candidate_count"])
        self.assertEqual(2, diagnostic["customer_service_route_safe_count"])
        self.assertEqual(1, diagnostic["customer_service_route_modern_count"])
        self.assertEqual(1, diagnostic["customer_service_route_legacy_count"])
        self.assertEqual(0, diagnostic["customer_service_route_invalid_count"])

    def test_duplicate_identical_customer_threads_hrefs_are_deduplicated(self):
        module = load_script()
        module.By = SimpleNamespace(CSS_SELECTOR="css selector")
        admin_root = "http://127.0.0.1:18080/admin-test"
        modern = admin_root + "/index.php/sell/customer-service/customer-threads?token=safe"

        class Link:
            def get_attribute(self, _name: str) -> str:
                return modern

        class Driver:
            def find_elements(self, _by: str, _selector: str) -> list[Link]:
                return [Link(), Link()]

        diagnostic: dict[str, object] = {}
        self.assertEqual([modern], module.generated_customer_threads_links(Driver(), admin_root, diagnostic))
        self.assertEqual(1, diagnostic["customer_service_route_candidate_count"])
        self.assertEqual(1, diagnostic["customer_service_route_modern_count"])

    def test_multiple_distinct_customer_threads_tokens_remain_candidates(self):
        module = load_script()
        module.By = SimpleNamespace(CSS_SELECTOR="css selector")
        admin_root = "http://127.0.0.1:18080/admin-test"
        modern_one = admin_root + "/sell/customer-service/customer-threads?token=one"
        modern_two = admin_root + "/index.php/sell/customer-service/customer-threads?token=two"

        class Link:
            def __init__(self, href: str) -> None:
                self.href = href

            def get_attribute(self, _name: str) -> str:
                return self.href

        class Driver:
            def find_elements(self, _by: str, _selector: str) -> list[Link]:
                return [Link(modern_one), Link(modern_two)]

        self.assertEqual(
            [modern_one, modern_two],
            module.generated_customer_threads_links(Driver(), admin_root),
        )

    def test_candidate_is_accepted_only_after_exact_expected_thread_readback(self):
        module = load_script()
        first = "http://127.0.0.1:18080/admin-test/index.php?controller=AdminCustomerThreads&token=stale"
        second = "http://127.0.0.1:18080/admin-test/index.php?controller=AdminCustomerThreads&token=current"
        expected_thread = "http://127.0.0.1:18080/admin-test/index.php?controller=AdminCustomerThreads&id_customer_thread=47&viewcustomer_thread=1&token=current"
        attempts: list[str] = []

        def visit(_driver, url: str, timeout: float = 35) -> None:
            attempts.append(url)

        def readback(_driver, _ctx, _buyer, expected_thread_id: int, timeout: float = 40):
            if attempts[-1] == first:
                self.assertLessEqual(timeout, 20.0)
                raise module.TimeoutException("stale token did not expose the expected thread")
            self.assertEqual(47, expected_thread_id)
            self.assertLessEqual(timeout, 40.0)
            return expected_thread, 47

        module.visit = visit
        module.view_link_from_index = readback
        selected, thread_url, thread_id = module.resolve_customer_threads_index(
            object(), SimpleNamespace(), {"email": "fixture@example.invalid"}, 47, [first, second]
        )
        self.assertEqual([first, second], attempts)
        self.assertEqual((second, expected_thread, 47), (selected, thread_url, thread_id))

    def test_detail_readback_continues_after_navigation_timeout_only_for_exact_thread(self):
        module = load_script()
        module.By = SimpleNamespace(CSS_SELECTOR="css selector")

        class Thread:
            text = "isolated inquiry"

            def is_displayed(self) -> bool:
                return True

        class Driver:
            def __init__(self, current_thread_id: int, route_kind: str = "legacy_thread_view") -> None:
                self.current_thread_id = current_thread_id
                self.route_kind = route_kind
                self.current_url = "about:blank"
                self.page_load_timeouts: list[float] = []
                self.selectors: list[str] = []

            def set_page_load_timeout(self, timeout: float) -> None:
                self.page_load_timeouts.append(timeout)

            def get(self, _url: str) -> None:
                if self.route_kind == "legacy_thread_view":
                    self.current_url = (
                        "http://127.0.0.1:18080/admin-test/index.php?controller=AdminCustomerThreads"
                        f"&id_customer_thread={self.current_thread_id}&viewcustomer_thread=1&token=safe"
                    )
                else:
                    self.current_url = (
                        "http://127.0.0.1:18080/admin-test/sell/customer-service/customer-threads/"
                        f"{self.current_thread_id}/view"
                    )
                raise module.TimeoutException("document load continued after Selenium timeout")

            def execute_script(self, _script: str) -> str:
                return "complete"

            def find_elements(self, _by: str, selector: str) -> list[Thread]:
                self.selectors.append(selector)
                return [Thread()]

        class ImmediateWait:
            def __init__(self, driver: Driver, _timeout: float) -> None:
                self.driver = driver

            def until(self, predicate):
                result = predicate(self.driver)
                if not result:
                    raise module.TimeoutException("exact thread DOM was not available")
                return result

        module.WebDriverWait = ImmediateWait
        admin_root = "http://127.0.0.1:18080/admin-test"
        thread_url = admin_root + "/index.php?controller=AdminCustomerThreads&id_customer_thread=47&viewcustomer_thread=1&token=safe"
        diagnostic: dict[str, object] = {}

        exact_driver = Driver(47)
        thread = module.visit_exact_customer_thread_detail(
            exact_driver, thread_url, admin_root, 47, diagnostic, timeout=35
        )
        self.assertEqual("isolated inquiry", thread.text)
        self.assertLessEqual(exact_driver.page_load_timeouts[0], 17.5)
        self.assertEqual([".message-item-initial"], exact_driver.selectors)
        self.assertEqual("admin_thread_detail_readback", diagnostic["browser_substage"])
        self.assertEqual("[data-role='messages-thread']", module.customer_thread_detail_selector("modern_thread_view"))
        with self.assertRaises(ValueError):
            module.customer_thread_detail_selector("unexpected_thread_route")

        wrong_thread_driver = Driver(48)
        diagnostic.clear()
        with self.assertRaises(module.TimeoutException):
            module.visit_exact_customer_thread_detail(
                wrong_thread_driver, thread_url, admin_root, 47, diagnostic, timeout=35
            )
        self.assertEqual("admin_thread_detail_readback", diagnostic["browser_substage"])

        wrong_route_driver = Driver(47, "modern_thread_view")
        with self.assertRaises(module.TimeoutException):
            module.visit_exact_customer_thread_detail(
                wrong_route_driver, thread_url, admin_root, 47, diagnostic, timeout=35
            )
        self.assertEqual([], wrong_route_driver.selectors)

    def test_forward_modal_uses_native_visibility_form_location_and_exact_thread_action(self):
        module = load_script()
        module.By = SimpleNamespace(CSS_SELECTOR="css selector", XPATH="xpath")
        admin_root = "http://127.0.0.1:18080/admin-test"
        legacy_view = admin_root + "/index.php?controller=AdminCustomerThreads&id_customer_thread=47&viewcustomer_thread=1&token=safe"
        legacy_form = legacy_view
        modern_view = admin_root + "/sell/customer-service/customer-threads/47/view?token=safe"
        modern_index_view = admin_root + "/index.php/sell/customer-service/customer-threads/47/view?token=safe"
        modern_forward = admin_root + "/sell/customer-service/customer-threads/47/forward?token=safe"

        self.assertEqual(("legacy_thread_view", 47), module.thread_action_route_identity(legacy_form, admin_root))
        self.assertEqual(("modern_thread_view", 47), module.thread_route_identity(modern_view, admin_root))
        self.assertEqual(("modern_thread_view", 47), module.thread_route_identity(modern_index_view, admin_root))
        self.assertEqual(("modern_thread_view", 47), module.thread_action_route_identity(modern_forward, admin_root))
        self.assertEqual(("modern_thread_view", 48), module.thread_action_route_identity(
            admin_root + "/sell/customer-service/customer-threads/48/forward?token=safe", admin_root
        ))
        self.assertIsNone(module.thread_action_route_identity(
            "https://outside.invalid/sell/customer-service/customer-threads/47/forward?token=safe", admin_root
        ))
        self.assertIsNone(module.thread_route_identity(
            admin_root + "/unexpected/sell/customer-service/customer-threads/47/view?token=safe", admin_root
        ))
        self.assertIsNone(module.thread_action_route_identity(
            admin_root + "/unexpected/sell/customer-service/customer-threads/47/forward?token=safe", admin_root
        ))
        self.assertEqual("#myModal", module.customer_thread_forward_target("legacy_thread_view"))
        self.assertEqual("#myModal.in", module.customer_thread_forward_visible_modal("legacy_thread_view"))
        self.assertEqual("#forwardThreadModal.show", module.customer_thread_forward_visible_modal("modern_thread_view"))
        self.assertIn('visible(admin, f\'button[data-target="{forward_target}"]\')', SCRIPT.read_text(encoding="utf-8"))

        class Modal:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def find_elements(self, by: str, selector: str) -> list[object]:
                self.calls.append((by, selector))
                return [object()]

        legacy_modal = Modal()
        modern_modal = Modal()
        self.assertEqual(1, len(module.customer_thread_forward_forms(legacy_modal, "legacy_thread_view")))
        self.assertEqual(1, len(module.customer_thread_forward_forms(modern_modal, "modern_thread_view")))
        self.assertEqual([("xpath", "./ancestor::form[1]")], legacy_modal.calls)
        self.assertEqual([("css selector", "form")], modern_modal.calls)

    def test_legacy_reply_and_status_controls_are_scoped_to_the_exact_thread_action(self):
        module = load_script()
        module.By = SimpleNamespace(CSS_SELECTOR="css selector")
        admin_root = "http://127.0.0.1:18080/admin-test"
        current = admin_root + "/index.php?controller=AdminCustomerThreads&id_customer_thread=47&viewcustomer_thread=1&token=safe"

        class Control:
            def is_displayed(self) -> bool:
                return True

            def is_enabled(self) -> bool:
                return True

        textarea = Control()
        reply_button = Control()
        close_button = Control()

        class Form:
            def __init__(self, action: str) -> None:
                self.action = action

            def get_attribute(self, name: str) -> str:
                return self.action if name == "action" else ""

            def find_elements(self, _by: str, selector: str) -> list[Control]:
                if selector in {"textarea[name='reply_message']", "button[name='submitReply']"}:
                    return [textarea if selector.startswith("textarea") else reply_button]
                if selector == "button[name='setstatus'][value='2']":
                    return [close_button]
                return []

        wrong_action = admin_root + "/index.php?controller=AdminCustomerThreads&id_customer_thread=48&viewcustomer_thread=1&token=safe"

        class Driver:
            current_url = current

            def find_elements(self, _by: str, selector: str) -> list[Form]:
                if selector != "form":
                    raise AssertionError("legacy control lookup must be scoped to native forms")
                return [Form(wrong_action), Form(current)]

        driver = Driver()
        form, found_textarea, found_reply_button = module.customer_thread_reply_form(
            driver, "legacy_thread_view", 47, admin_root
        )
        self.assertEqual(current, form.get_attribute("action"))
        self.assertIs(textarea, found_textarea)
        self.assertIs(reply_button, found_reply_button)
        found_status_form, found_close_button = module.status_action_form(
            driver, "closed", "legacy_thread_view", 47, admin_root
        )
        self.assertEqual(current, found_status_form.get_attribute("action"))
        self.assertIs(close_button, found_close_button)

        driver.current_url = current.replace("id_customer_thread=47", "id_customer_thread=48")
        with self.assertRaisesRegex(AssertionError, "exact customer thread route"):
            module.customer_thread_reply_form(driver, "legacy_thread_view", 47, admin_root)

    def test_status_readback_reacquires_after_stale_poll_without_replaying_mutation(self):
        module = load_script()
        admin_root = "http://127.0.0.1:18080/admin-test"
        current = admin_root + "/index.php?controller=AdminCustomerThreads&id_customer_thread=47&viewcustomer_thread=1&token=safe"

        class Button:
            def __init__(self, *, stale_on_click=False):
                self.click_count = 0
                self.stale_on_click = stale_on_click

            def click(self):
                self.click_count += 1
                if self.stale_on_click:
                    raise module.StaleElementReferenceException("the status control detached before click")

        class Driver:
            current_url = current

        driver = Driver()
        button = Button()
        readback_calls = 0

        def status_action_form(_driver, status, _route_kind, _thread_id, _admin_url):
            nonlocal readback_calls
            if status == "closed":
                return object(), button
            readback_calls += 1
            if readback_calls == 1:
                raise module.StaleElementReferenceException("native thread DOM is being replaced")
            return object(), object()

        module.status_action_form = status_action_form

        wait_timeouts = []

        class ImmediateRetryWait:
            def __init__(self, _driver, timeout):
                self.timeout = timeout
                wait_timeouts.append(timeout)

            def until(self, predicate):
                for _ in range(3):
                    if predicate(driver):
                        return True
                raise AssertionError("the unchanged status readback wait did not resolve")

        module.WebDriverWait = ImmediateRetryWait
        diagnostic = {}
        module.update_thread_status(
            driver, "closed", "open", "legacy_thread_view", 47, admin_root, diagnostic
        )
        self.assertEqual(1, button.click_count)
        self.assertEqual(2, readback_calls)
        self.assertEqual([25], wait_timeouts)
        self.assertEqual("status_action_readback", diagnostic["browser_substage"])

        stale_button = Button(stale_on_click=True)
        lookup_calls = 0

        def stale_status_action_form(_driver, _status, _route_kind, _thread_id, _admin_url):
            nonlocal lookup_calls
            lookup_calls += 1
            return object(), stale_button

        module.status_action_form = stale_status_action_form
        diagnostic.clear()
        with self.assertRaises(module.StaleElementReferenceException):
            module.update_thread_status(
                driver, "open", "closed", "legacy_thread_view", 47, admin_root, diagnostic
            )
        self.assertEqual(1, lookup_calls)
        self.assertEqual(1, stale_button.click_count)
        self.assertEqual("status_action_click", diagnostic["browser_substage"])

    def test_equivalent_legacy_customer_threads_aliases_ignore_query_order_and_path_alias(self):
        module = load_script()
        module.By = SimpleNamespace(CSS_SELECTOR="css selector")
        admin_root = "http://127.0.0.1:18080/admin-test"
        legacy_rewritten = admin_root + "?controller=AdminCustomerThreads&token=same-token"
        legacy_index = admin_root + "/index.php?token=same-token&controller=AdminCustomerThreads"

        class Link:
            def __init__(self, href: str) -> None:
                self.href = href

            def get_attribute(self, _name: str) -> str:
                return self.href

        class Driver:
            def find_elements(self, _by: str, _selector: str) -> list[Link]:
                return [Link(legacy_rewritten), Link(legacy_index)]

        diagnostic: dict[str, object] = {}
        self.assertEqual([legacy_index], module.generated_customer_threads_links(Driver(), admin_root, diagnostic))
        self.assertEqual(2, diagnostic["customer_service_route_candidate_count"])
        self.assertEqual(2, diagnostic["customer_service_route_safe_count"])
        self.assertEqual(1, diagnostic["customer_service_route_legacy_count"])
        self.assertEqual(0, diagnostic["customer_service_route_invalid_count"])

    def test_distinct_legacy_tokens_remain_candidates_and_unexpected_query_keys_remain_invalid(self):
        module = load_script()
        module.By = SimpleNamespace(CSS_SELECTOR="css selector")
        admin_root = "http://127.0.0.1:18080/admin-test"
        legacy_one = admin_root + "/index.php?controller=AdminCustomerThreads&token=one"
        legacy_two = admin_root + "?controller=AdminCustomerThreads&token=two"

        class Link:
            def __init__(self, href: str) -> None:
                self.href = href

            def get_attribute(self, _name: str) -> str:
                return self.href

        class Driver:
            def __init__(self, hrefs: list[str]) -> None:
                self.hrefs = hrefs

            def find_elements(self, _by: str, _selector: str) -> list[Link]:
                return [Link(href) for href in self.hrefs]

        self.assertEqual(
            [legacy_one, legacy_two],
            module.generated_customer_threads_links(Driver([legacy_one, legacy_two]), admin_root),
        )

        diagnostic: dict[str, object] = {}
        unexpected = admin_root + "/index.php?controller=AdminCustomerThreads&token=safe&id_customer_thread=47"
        with self.assertRaisesRegex(AssertionError, "noncanonical route"):
            module.generated_customer_threads_links(Driver([unexpected]), admin_root, diagnostic)
        self.assertEqual(1, diagnostic["customer_service_route_invalid_count"])

    def test_nested_false_modern_route_fails_closed(self):
        module = load_script()
        module.By = SimpleNamespace(CSS_SELECTOR="css selector")
        admin_root = "http://127.0.0.1:18080/admin-test"
        nested = admin_root + "/extra/sell/customer-service/customer-threads?token=safe"

        class Link:
            def get_attribute(self, _name: str) -> str:
                return nested

        class Driver:
            def find_elements(self, _by: str, _selector: str) -> list[Link]:
                return [Link()]

        diagnostic: dict[str, object] = {}
        with self.assertRaisesRegex(AssertionError, "noncanonical route"):
            module.generated_customer_threads_links(Driver(), admin_root, diagnostic)
        self.assertEqual(1, diagnostic["customer_service_route_invalid_count"])

    def test_any_unsafe_customer_threads_route_candidate_still_fails_closed(self):
        module = load_script()
        module.By = SimpleNamespace(CSS_SELECTOR="css selector")
        admin_root = "http://127.0.0.1:18080/admin-test"

        class Link:
            def get_attribute(self, _name: str) -> str:
                return "https://outside.invalid/admin/index.php?controller=AdminCustomerThreads&token=unsafe"

        class Driver:
            def find_elements(self, _by: str, _selector: str) -> list[Link]:
                return [Link()]

        with self.assertRaisesRegex(AssertionError, "left the isolated Back Office"):
            module.generated_customer_threads_links(Driver(), admin_root)

    def test_contact_uses_shop_generated_locale_routes_and_probes_legacy_query_route(self):
        browser = SCRIPT.read_text(encoding="utf-8")
        route_helper = (ROOT / "tests/e2e/native_contact_route.py").read_text(encoding="utf-8")
        for required in (
            "CONTACT_ROUTE_FIXTURE", "contact_url=route_fixture[\"urls_by_iso\"][\"ja\"]",
            "probe_contact_route(", "query_route, ctx.shop, locale=\"ja\"",
            "ctx.contact_url, ctx.shop, locale=\"ja\"",
            "CONTACT_ROUTE_DIAGNOSTIC", "contact_route_class(",
            "driver.current_url", "localized_rewrite=localized_rewrite",
            "private_no_store", "credentials: 'same-origin'", "cache: 'no-store'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, browser + route_helper)
        self.assertIn("getPageLink('contact', null, $idLang)", (ROOT / "tests/business_profile/read_native_contact_route.php").read_text())
        self.assertIn("Module::isEnabled('contactform')", (ROOT / "tests/business_profile/read_native_contact_route.php").read_text())


if __name__ == "__main__":
    unittest.main()
