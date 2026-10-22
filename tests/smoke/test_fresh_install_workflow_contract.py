"""Keep the isolated installer pointed at Japan Post's published KEN_ALL archive."""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "fresh-install.yml"
POSTAL_IMPORT = ROOT / "modules" / "kuraneapostcode" / "bin" / "import-ken-all.php"
POSTAL_UPDATER = ROOT / "modules" / "kuraneapostcode" / "bin" / "update-ken-all.sh"
FRESH_INSTALL_SMOKE = ROOT / "tests" / "smoke" / "fresh_install.sh"


class FreshInstallWorkflowContractTests(unittest.TestCase):
    def test_customer_account_e2e_uses_isolated_mailpit_and_publishes_browser_logs(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        self.assertTrue("axllent/mailpit:v1.31.6" in workflow, "missing version-pinned disposable mail capture service")
        self.assertTrue('Configuration::updateValue("PS_MAIL_SERVER", "mailpit")' in workflow, "PrestaShop SMTP is not pointed at the CI-only mail service")
        self.assertTrue('Configuration::updateValue("PS_MAIL_SMTP_PORT", 1025)' in workflow, "PrestaShop SMTP port is not set for Mailpit")
        self.assertTrue("tests/e2e/verify_customer_account_browser.py" in workflow, "customer account browser flow is not run")
        self.assertTrue("MAILPIT_API_URL: http://127.0.0.1:8025" in workflow, "browser test cannot read captured reset mail")
        self.assertTrue("customer-account-e2e.log" in workflow, "account browser execution log is not preserved")
        self.assertTrue("docker rm -f \"${CI_COMPOSE_PROJECT_NAME}-mailpit\"" in workflow, "CI mail service cleanup is missing")
        self.assertTrue('input[name="email"]' in account_flow and 'get_attribute("type") != "email"' in account_flow, "customer login is not verified as email-based")
        self.assertTrue("reset_link_for(account_email)" in account_flow, "password reset does not follow the captured test email")
        self.assertIn('a[data-link-action="display-register-form"]', account_flow, "registration must follow the theme's actual registration link")
        self.assertIn("click_centered(driver, registration_link)", account_flow)
        self.assertNotIn("controller=authentication&create_account=1", account_flow, "registration must not rely on a legacy authentication query")
        self.assertIn("registration form is missing the required", account_flow)
        self.assertIn("registration form has invalid controls:", account_flow)
        self.assertIn("parsed_reset.scheme != base.scheme", account_flow, "password reset must remain on the isolated shop protocol")
        self.assertIn('"cid:shop_logo"', account_flow, "captured reset email must render the approved brand logo")
        self.assertIn('attachment.get("ContentID", "")', account_flow)
        self.assertIn("published ORDENOWA derivative", account_flow)

    def test_customer_account_browser_proves_my_page_and_logout_transitions(self) -> None:
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        self.assertIn("def assert_my_page", account_flow)
        my_page = account_flow.split("def assert_my_page", 1)[1].split("def prepare_required_registration_fields", 1)[0]
        logout = account_flow.split("def logout", 1)[1].split("def run_viewport", 1)[0]
        self.assertEqual(account_flow.count("        assert_my_page(driver,"), 3)
        for selector in ("identity_main_link", "signout_link"):
            self.assertIn(selector, my_page)
        self.assertIn("expected_first_name", my_page)
        self.assertIn('driver.get(f"{BASE}/index.php?controller=my-account")', logout)
        self.assertIn("identity_main_link", logout)
        self.assertIn('#login-form input[name="email"]', logout)

    def test_account_signout_selects_a_visible_duplicate_for_mobile_and_desktop(self) -> None:
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        signout = account_flow.split("def visible_signout_link", 1)[1].split("def assert_my_page", 1)[0]
        my_page = account_flow.split("def assert_my_page", 1)[1].split("def click_required_checkbox_label", 1)[0]
        logout = account_flow.split("def logout", 1)[1].split("def run_viewport", 1)[0]

        self.assertIn('find_elements(By.CSS_SELECTOR, "a.account-menu__link--signout")', signout)
        self.assertIn("link.is_displayed()", signout)
        self.assertIn("link.is_enabled()", signout)
        self.assertIn("visible_signout_link(driver)", my_page)
        self.assertNotIn('"#signout_link"', my_page)
        self.assertIn("link = visible_signout_link(driver)", logout)
        self.assertIn("if any(", logout)
        self.assertIn("link.is_displayed()", logout)
        self.assertIn('driver.find_elements(By.CSS_SELECTOR, "a.account-menu__link--signout")', logout)
        self.assertNotIn('visible(driver, "a.account-menu__link--signout")', logout)

    def test_brand_and_account_e2e_run_before_product_admin_and_checkout_qa(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        step_names = re.findall(r"^\s+- name: (.+)$", workflow, flags=re.MULTILINE)
        brand_step = "Verify official ORDENOWA brand upload and publish in Chromium"
        account_step = "Verify customer registration, email login, logout, password reset, and my page in Chromium"
        product_admin_step = "Verify Korean admin native product create and edit in Chromium"
        storefront_step = "Verify real product detail and cart in Chromium (no payment)"
        checkout_gate_step = "Enable run-scoped checkout only for the isolated order browser QA"
        order_step = "Verify browser customer search, Japan checkout, and unpaid offline order"

        brand_position = step_names.index(brand_step)
        account_position = step_names.index(account_step)
        product_admin_position = step_names.index(product_admin_step)
        self.assertEqual(step_names[brand_position + 1], account_step)
        self.assertEqual(step_names[account_position + 1], product_admin_step)
        self.assertLess(product_admin_position, step_names.index(storefront_step))
        self.assertLess(product_admin_position, step_names.index(checkout_gate_step))
        self.assertLess(product_admin_position, step_names.index(order_step))

    def test_official_brand_upload_preview_publish_and_browser_checks_run_in_isolated_ci(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        brand_flow_path = ROOT / "tests" / "e2e" / "verify_brand_admin_browser.py"
        self.assertTrue(brand_flow_path.is_file(), "official brand admin browser QA is missing")
        brand_flow = brand_flow_path.read_text(encoding="utf-8")
        self.assertIn("Verify official ORDENOWA brand upload and publish in Chromium", workflow)
        self.assertIn("tests/e2e/verify_brand_admin_browser.py", workflow)
        self.assertIn("ADMIN_MAIL: ci-kuranea@example.invalid", workflow)
        self.assertIn("ADMIN_PASSWD: Ci-Only-Admin-Password-92!", workflow)
        self.assertIn("ordenowa-brand-e2e.log", workflow)
        self.assertIn("brand-desktop-published.png", brand_flow)
        self.assertIn("brand-mobile-published.png", brand_flow)
        self.assertIn('controller == ["AdminBusinessProfile"]', brand_flow)
        self.assertIn("submitOrdenowaPreview", brand_flow)
        self.assertIn("submitOrdenowaPublish", brand_flow)
        for expected_value in (
            "ORDENOWA CI REFERENCE",
            "ORDENOWA CI SUPPORT HOURS",
            "ORDENOWA CI SHIPPING POLICY",
            "ORDENOWA CI REFUND POLICY",
            "ORDENOWA CI SEO description",
            "#244a7d",
            "#f5f7fa",
        ):
            self.assertIn(expected_value, brand_flow)
        self.assertIn('brand_uploads[{slot}]', brand_flow)
        for source_slot in ('"primary_logo"', '"favicon_symbol"', '"pwa_icon"'):
            self.assertIn(source_slot, brand_flow)
        self.assertIn("확인 대기", brand_flow)
        self.assertNotIn("submitOrdenowaApproveSeller", brand_flow)
        storefront_flow = (ROOT / "tests" / "e2e" / "verify_storefront_browser.py").read_text(encoding="utf-8")
        self.assertIn("payment-option", storefront_flow, "the browser suite must keep live checkout controls inaccessible")

    def test_brand_settings_browser_failure_emits_redacted_page_state_and_screenshot(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        brand_flow = (ROOT / "tests" / "e2e" / "verify_brand_admin_browser.py").read_text(encoding="utf-8")
        for field in (
            "settings_form_visible",
            "brand_section_visible",
            "access_denied_marker",
            "controller_load_error_marker",
            "general_error_marker",
            "login_form_visible",
            "pathname",
            "title",
        ):
            self.assertIn(field, brand_flow)
        navigation = brand_flow.split('stage = "korean_brand_settings_form"', 1)[1].split(
            'stage = "official_asset_upload"', 1
        )[0]
        diagnostics = brand_flow.split("def emit_brand_settings_diagnostics", 1)[1].split("def assert_public_brand_assets", 1)[0]
        self.assertLess(navigation.index('driver.save_screenshot(str(DEST / "brand-settings-after-navigation.png"))'), navigation.index('visible(driver, "form.ordenowa-profile-settings")'))
        self.assertIn("emit_brand_settings_diagnostics(driver)", navigation)
        self.assertIn("ORDENOWA_BRAND_SETTINGS_DIAGNOSTICS=", diagnostics)
        self.assertIn("window.location.pathname", diagnostics)
        self.assertNotIn("window.location.search", diagnostics)
        self.assertIn('rg \'^ORDENOWA_BRAND_SETTINGS_DIAGNOSTICS=\' "$log_file"', workflow)
        self.assertIn('diagnostics_line', workflow)

    def test_brand_publish_button_is_centered_and_checked_for_obstruction_before_click(self) -> None:
        brand_flow = (ROOT / "tests" / "e2e" / "verify_brand_admin_browser.py").read_text(encoding="utf-8")
        helper = brand_flow.split("def click_centered", 1)[1].split("def image_is_rendered", 1)[0]
        publish_stage = brand_flow.split('stage = "publish_button_click"', 1)[1].split('stage = "publish_confirmation"', 1)[0]
        self.assertIn("scrollIntoView({block: 'center'", helper)
        self.assertIn("EC.element_to_be_clickable(element)", helper)
        self.assertIn("document.elementFromPoint", helper)
        self.assertIn("element.click()", helper)
        self.assertIn("click_centered(driver, publish_button)", publish_stage)

    def test_account_registration_failure_emits_redacted_browser_state_in_ci_summary(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        diagnostics = account_flow.split("def emit_registration_diagnostics", 1)[1].split("def fill", 1)[0]
        registration = account_flow.split('stage = "registration_form_load"', 1)[1].split('stage = "profile_update"', 1)[0]
        self.assertLess(registration.index('stage = "registration_submit"'), registration.index('stage = "registration_post_submit"'))
        for field in (
            "registration_form_visible",
            "registration_link_visible",
            "registration_center_unobstructed",
            "registration_center_target_tag",
            "identity_link_visible",
            "submit_button_enabled",
            "registration_form_valid",
            "visible_invalid_control_count",
            "first_invalid_control_name",
            "email_valid",
            "password_controls_valid",
            "account_error_marker",
            "pathname",
        ):
            self.assertIn(field, diagnostics)
        self.assertIn("ORDENOWA_ACCOUNT_REGISTRATION_DIAGNOSTICS=", diagnostics)
        self.assertNotIn("window.location.search", diagnostics)
        self.assertNotIn("email.value", diagnostics)
        self.assertIn('rg \'^ORDENOWA_ACCOUNT_REGISTRATION_DIAGNOSTICS=\' "$log_file"', workflow)
        self.assertIn("customer-account-e2e.log", workflow)

    def test_registration_link_is_scrolled_and_hit_tested_before_native_click(self) -> None:
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        helper = account_flow.split("def click_centered", 1)[1].split("def emit_registration_diagnostics", 1)[0]
        registration = account_flow.split('stage = "registration_link_click"', 1)[1].split('stage = "registration_submit"', 1)[0]
        self.assertIn("scrollIntoView({block: 'center'", helper)
        self.assertIn("EC.element_to_be_clickable(element)", helper)
        self.assertIn("document.elementFromPoint", helper)
        self.assertIn("element.click()", helper)
        self.assertIn("click_centered(driver, registration_link)", registration)

    def test_registration_submit_uses_the_centered_native_click_helper(self) -> None:
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        registration = account_flow.split('stage = "registration_submit"', 1)[1].split(
            'stage = "registration_post_submit"', 1
        )[0]

        self.assertIn('visible(driver, "#customer-form button.form-control-submit")', registration)
        self.assertIn("click_centered(driver,", registration)
        self.assertNotIn('button.form-control-submit").click()', registration)

    def test_registration_post_submit_accepts_the_authenticated_header_redirect(self) -> None:
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        self.assertIn("def wait_for_registration_success", account_flow)
        success_wait = account_flow.split("def wait_for_registration_success", 1)[1].split(
            "def set_registration_control", 1
        )[0]
        post_submit = account_flow.split('stage = "registration_post_submit"', 1)[1].split(
            'stage = "profile_update"', 1
        )[0]
        sign_in_template = (ROOT / "themes" / "hummingbird" / "modules" / "ps_customersignin" / "ps_customersignin.tpl").read_text(
            encoding="utf-8"
        )
        my_account_template = (ROOT / "themes" / "hummingbird" / "templates" / "customer" / "my-account.tpl").read_text(
            encoding="utf-8"
        )

        self.assertIn("getElementById('userMenuButton')", success_wait)
        self.assertIn("getElementById('identity_main_link')", success_wait)
        self.assertIn('driver.get(f"{BASE}/index.php?controller=my-account")', success_wait)
        self.assertIn("wait_for_registration_success(driver)", post_submit)
        self.assertIn('assert_my_page(driver, "CI")', post_submit)
        self.assertIn("{if $customer.is_logged}", sign_in_template)
        self.assertIn('id="userMenuButton"', sign_in_template)
        self.assertIn('id="identity_main_link"', my_account_template)

    def test_registration_link_host_must_match_the_base_shop_host(self) -> None:
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        registration_guard = account_flow.split('stage = "registration_link_validation"', 1)[1].split(
            'stage = "registration_link_click"', 1
        )[0]
        success_wait = account_flow.split("def wait_for_registration_success", 1)[1].split(
            "def set_registration_control", 1
        )[0]

        base_host = urlparse("http://localhost:18080").hostname
        alternate_host = urlparse("http://127.0.0.1:18080/register").hostname
        self.assertNotEqual(base_host, alternate_host, "the alternate loopback host must be a separate browser origin")
        self.assertIn(
            "registration_location.hostname != base_location.hostname",
            registration_guard,
            "registration links must keep the same browser cookie host as SHOP_BASE_URL",
        )
        self.assertNotIn('hostname not in {"localhost", "127.0.0.1"}', registration_guard)
        self.assertIn('driver.get(f"{BASE}/index.php?controller=my-account")', success_wait)

    def test_password_reset_links_must_match_the_exact_base_origin(self) -> None:
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        reset_mail_filter = account_flow.split("def reset_link_for", 1)[1].split("def visible", 1)[0]
        reset_navigation = account_flow.split('stage = "password_reset"', 1)[1].split(
            "driver.get(reset_url)", 1
        )[0]

        base_url = "http://localhost:18080"
        alternate_host_url = "http://127.0.0.1:18080/password?token=synthetic"
        self.assertNotEqual(urlparse(base_url).hostname, urlparse(alternate_host_url).hostname)
        for guard, candidate_prefix, base_prefix, comparator in (
            (reset_mail_filter, "parsed", "base_location", "=="),
            (reset_navigation, "parsed_reset", "base", "!="),
        ):
            self.assertIn(f"{candidate_prefix}.scheme {comparator} {base_prefix}.scheme", guard)
            self.assertIn(f"{candidate_prefix}.hostname {comparator} {base_prefix}.hostname", guard)
            self.assertIn(f"{candidate_prefix}.port {comparator} {base_prefix}.port", guard)
        self.assertNotIn('hostname in {"localhost", "127.0.0.1"}', reset_mail_filter)
        self.assertNotIn('hostname in {"localhost", "127.0.0.1"}', reset_navigation)

    def test_registration_failure_diagnostics_fall_back_to_safe_page_markers(self) -> None:
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        diagnostics = account_flow.split("def emit_registration_diagnostics", 1)[1].split("def fill", 1)[0]

        self.assertIn("window.location.pathname", diagnostics)
        self.assertIn("header_user_menu_button_present", diagnostics)
        self.assertIn("header_user_menu_button_visible", diagnostics)
        self.assertIn("login_form_visible", diagnostics)
        self.assertIn("alert_visible", diagnostics)
        self.assertIn("urlparse(driver.current_url).path", diagnostics)
        self.assertIn('diagnostics["diagnostics_collection_error"] = type(error).__name__', diagnostics)
        self.assertNotIn("window.location.search", diagnostics)
        self.assertNotIn("email.value", diagnostics)
        self.assertNotIn("password.value", diagnostics)

    def test_account_registration_reports_link_and_required_control_stages_safely(self) -> None:
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        registration = account_flow.split("def run_viewport", 1)[1].split("if __name__", 1)[0]
        diagnostics = account_flow.split("def emit_registration_diagnostics", 1)[1].split("def fill", 1)[0]

        stage_markers = (
            'stage = "registration_link_load"',
            'stage = "registration_link_validation"',
            'stage = "registration_link_click"',
            'stage = "registration_form_load"',
            'stage = "registration_required_controls"',
            'stage = "registration_submit"',
            'stage = "registration_post_submit"',
        )
        for marker in stage_markers:
            self.assertIn(marker, registration)
        stage_positions = [registration.index(marker) for marker in stage_markers]
        self.assertEqual(stage_positions, sorted(stage_positions))
        self.assertIn("registration_stage: arguments[0]", diagnostics)
        self.assertIn("registration_control_name: arguments[1].name || ''", diagnostics)
        self.assertIn("registration_control_type: arguments[1].type || ''", diagnostics)
        self.assertIn('emit_registration_diagnostics(driver, stage, failure_control)', account_flow)
        self.assertIn('set_registration_control(failure_control, "display-register-form", "anchor")', registration)
        self.assertIn('set_registration_control(failure_control, "customer-form", "form")', registration)
        self.assertIn('set_registration_control(failure_control, "save-customer", "submit")', registration)
        self.assertNotIn("email_address", diagnostics)
        self.assertNotIn(".value", diagnostics)
        self.assertNotIn("window.location.search", diagnostics)
        control_metadata = account_flow.split("def set_registration_control", 1)[1].split("def emit_registration_diagnostics", 1)[0]
        self.assertIn("re.sub", control_metadata)

    def test_account_browser_error_annotation_reports_sanitized_control_metadata_only(self) -> None:
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        failure = account_flow.split("except Exception as error:", 1)[1].split("raise SystemExit", 1)[0]
        annotation = failure.split("::error title=Customer account browser QA::", 1)[1].split("file=sys.stderr", 1)[0]
        account_step = workflow.split("- name: Verify customer registration, email login, logout, password reset, and my page in Chromium", 1)[1].split(
            "- name:", 1
        )[0]
        aggregate = workflow.split("- name: Aggregate browser QA and postal verification failures", 1)[1].split(
            "- name:", 1
        )[0]

        self.assertIn("control_name={failure_control.get('name') or 'none'}", annotation)
        self.assertIn("control_type={failure_control.get('type') or 'none'}", annotation)
        self.assertNotIn("account_email", annotation)
        self.assertNotIn("initial_password", annotation)
        self.assertNotIn("reset_password", annotation)
        self.assertNotIn("str(error)", annotation)
        self.assertIn("browser_status=${PIPESTATUS[0]}", account_step)
        self.assertIn('exit "$browser_status"', account_step)
        self.assertIn('diagnostics_lines=$(rg \'^ORDENOWA_ACCOUNT_REGISTRATION_DIAGNOSTICS=\' "$log_file" || true)', account_step)
        self.assertIn('::error title=Customer account registration diagnostics::%s\\n', account_step)
        self.assertIn('ACCOUNT_BROWSER_QA_OUTCOME: ${{ steps.account_browser_qa.outcome }}', aggregate)
        self.assertIn('"account=$ACCOUNT_BROWSER_QA_OUTCOME"', aggregate)
        self.assertIn('if [[ "$entry" == *=failure || "$entry" == *=cancelled ]]; then', aggregate)

    def test_account_registration_failure_annotation_exposes_only_safe_response_state(self) -> None:
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        diagnostics = account_flow.split("def emit_registration_diagnostics", 1)[1].split("def fill", 1)[0]
        state_builder = diagnostics.split("safe_state: dict[str, object] = {", 1)[1].split(
            "safe_state_json =", 1
        )[0]
        annotation_output = diagnostics.split("safe_state_json =", 1)[1]

        self.assertIn('::error title=Customer account registration response state::', annotation_output)
        self.assertIn('ORDENOWA_ACCOUNT_REGISTRATION_SAFE_STATE=', annotation_output)
        for field in (
            '"stage"',
            '"path"',
            '"registration_form_valid"',
            '"visible_invalid_control_count"',
            '"first_invalid_control_name"',
            '"first_invalid_control_type"',
            '"alert_visible"',
            '"identity_link_visible"',
            '"login_form_visible"',
            '"header_user_menu_button_visible"',
        ):
            self.assertIn(field, state_builder)
        self.assertIn('safe_path = diagnostics.get("pathname")', diagnostics)
        self.assertIn('safe_path = safe_path if safe_path in {"/", "/index.php"} else "/<other>"', diagnostics)
        self.assertIn("safe_diagnostic_name", state_builder)
        self.assertIn("safe_registration_path", account_flow)
        self.assertNotIn("email", state_builder)
        self.assertNotIn("password", state_builder)
        self.assertNotIn("token", state_builder)
        self.assertNotIn("bodyText", state_builder)
        self.assertNotIn("window.location.search", state_builder)

    def test_required_registration_checkbox_uses_its_visible_label(self) -> None:
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        checkbox_click = account_flow.split("def click_required_checkbox_label", 1)[1].split("def prepare_required_registration_fields", 1)[0]
        registration = account_flow.split("def prepare_required_registration_fields", 1)[1].split("def submit_login", 1)[0]
        hummingbird_fields = (ROOT / "themes" / "hummingbird" / "templates" / "_partials" / "form-fields.tpl").read_text(encoding="utf-8")

        self.assertIn('find_elements(By.CSS_SELECTOR, "label[for]")', checkbox_click)
        self.assertIn('candidate.get_attribute("for") == checkbox_id', checkbox_click)
        self.assertIn("candidate.is_displayed()", checkbox_click)
        self.assertIn("label.click()", checkbox_click)
        self.assertIn("checkbox.is_selected()", checkbox_click)
        self.assertIn("click_required_checkbox_label(form, element)", registration)
        self.assertIn('id="{$id_prefix}field-{$field.name}"', hummingbird_fields)
        self.assertIn('for="{$id_prefix}field-{$field.name}"', hummingbird_fields)
        self.assertNotIn("execute_script", checkbox_click)
        self.assertNotIn(".checked =", checkbox_click)

    def test_required_registration_checkbox_uses_native_keyboard_after_intercepted_label_click(self) -> None:
        account_path = ROOT / "tests" / "e2e" / "verify_customer_account_browser.py"
        account_flow = account_path.read_text(encoding="utf-8")
        checkbox_click = account_flow.split("def click_required_checkbox_label", 1)[1].split(
            "def prepare_required_registration_fields", 1
        )[0]

        self.assertIn("from selenium.common.exceptions import ElementClickInterceptedException", account_flow)
        self.assertIn("from selenium.webdriver.common.keys import Keys", account_flow)
        self.assertLess(checkbox_click.index("label.click()"), checkbox_click.index("except ElementClickInterceptedException:"))
        fallback = checkbox_click.split("except ElementClickInterceptedException:", 1)[1]
        self.assertIn("checkbox.is_displayed()", fallback)
        self.assertIn("checkbox.is_enabled()", fallback)
        self.assertIn("if not checkbox.is_selected():", fallback)
        self.assertIn("checkbox.send_keys(Keys.SPACE)", fallback)
        self.assertIn("if not checkbox.is_selected():", checkbox_click)
        self.assertNotIn("execute_script", checkbox_click)

    def test_customer_account_runs_both_viewports_before_reporting_failures(self) -> None:
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        viewport_runner = account_flow.split("def run_viewport", 1)[1].split("if __name__", 1)[0]
        main = account_flow.split("if __name__ == \"__main__\":", 1)[1]

        self.assertIn("return success", viewport_runner)
        self.assertIn("driver = None", viewport_runner)
        self.assertIn("driver.quit()", viewport_runner)
        self.assertIn("for viewport in ((1440, 960, \"desktop\"), (390, 844, \"mobile\"))", main)
        self.assertIn("failed_viewports.append(viewport[2])", main)
        self.assertIn("if failed_viewports:", main)
        self.assertIn("raise SystemExit", main)

    def test_password_reset_rejects_the_old_password_before_accepting_the_new_one(self) -> None:
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        self.assertIn("def assert_login_rejected", account_flow)
        old_password_check = account_flow.split("def assert_login_rejected", 1)[1].split("def logout", 1)[0]
        reset_login = account_flow.split('stage = "password_reset_old_password_rejected"', 1)[1].split(
            'driver.save_screenshot(str(DEST / f"{label}-customer-password-reset-login.png"))', 1
        )[0]
        login_errors = (ROOT / "themes" / "hummingbird" / "templates" / "_partials" / "form-errors.tpl").read_text(
            encoding="utf-8"
        )

        self.assertIn("assert_login_rejected(driver, account_email, initial_password)", reset_login)
        self.assertLess(
            reset_login.index("assert_login_rejected(driver, account_email, initial_password)"),
            reset_login.index("submit_login(driver, account_email, reset_password)"),
        )
        self.assertIn(".alert.alert-danger[role=", old_password_check)
        self.assertIn("#login-form input[name=\"email\"]", old_password_check)
        self.assertIn('By.ID, "identity_main_link"', old_password_check)
        self.assertIn('a.account-menu__link--signout', old_password_check)
        self.assertIn('class="alert alert-danger', login_errors)
        self.assertIn('role="alert"', login_errors)

    def test_ci_uses_the_module_updater_for_the_official_japan_post_archive(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        postal_step = workflow.split("- name: Download and import official Japan Post KEN_ALL data", 1)[1].split("- name:", 1)[0]
        updater = POSTAL_UPDATER.read_text(encoding="utf-8")
        self.assertIn("https://www.post.japanpost.jp/service/search/zipcode/download/kogaki/zip/ken_all.zip", updater)
        self.assertIn("bash tests/smoke/run_postal_updater.sh \"$CI_COMPOSE_PROJECT_NAME\"", postal_step)
        self.assertNotIn("curl ", postal_step)
        self.assertNotIn("unzip", postal_step)
        runner = (ROOT / "tests" / "smoke" / "run_postal_updater.sh").read_text(encoding="utf-8")
        self.assertIn("runuser -g www-data -u www-data --", runner)
        self.assertIn("/var/www/html/modules/kuraneapostcode/bin/update-ken-all.sh", runner)

    def test_postal_updater_failure_is_summarized_without_raw_output(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("tests/smoke/run_postal_updater.sh", workflow)
        self.assertIn("tests/smoke/run_postal_updater.sh", workflow.split("paths:", 1)[1].split("permissions:", 1)[0])
        runner = (ROOT / "tests" / "smoke" / "run_postal_updater.sh").read_text(encoding="utf-8")
        self.assertIn("KURANEA_POSTAL_DOWNLOAD_FAILURE curl_exit=", runner)
        self.assertIn("GITHUB_STEP_SUMMARY", runner)
        self.assertIn("::error title=Japan Post postcode update::", runner)
        self.assertIn("updater/import failed; raw updater output was suppressed", runner)
        self.assertIn('>"$log_file" 2>&1', runner)

    def test_failed_compose_bootstrap_uses_the_shared_redacting_diagnostics_script(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("- name: Start the empty-volume shop", workflow)
        self.assertIn("id: compose_up", workflow)
        self.assertIn("bash tests/smoke/collect_failure_diagnostics.sh", workflow)
        self.assertIn("docker compose -p \"$project_name\" logs --tail=160 mariadb prestashop", (ROOT / "tests/smoke/collect_failure_diagnostics.sh").read_text(encoding="utf-8"))

    def test_first_boot_marker_is_verified_before_any_ci_container_recreation(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        start = workflow.index("- name: Start the empty-volume shop")
        initial_marker = workflow.index("- name: Verify the first empty-volume bootstrap marker")
        first_module_restart = workflow.index("docker compose -p \"$CI_COMPOSE_PROJECT_NAME\" restart prestashop")
        checkout_restore = workflow.index("- name: Restore the fail-closed base checkout environment")
        self.assertLess(start, initial_marker)
        self.assertLess(initial_marker, first_module_restart)
        self.assertLess(initial_marker, checkout_restore)
        step = workflow[initial_marker:first_module_restart]
        self.assertIn("ORDENOWA bootstrap: storefront=ja, en/ko=enabled, admin=ko, theme=kuranea", step)

    def test_post_restore_smoke_accepts_existing_container_bootstrap_marker(self) -> None:
        script = FRESH_INSTALL_SMOKE.read_text(encoding="utf-8")
        marker_check = script.split('verification_phase="initial_bootstrap_marker"', 1)[1].split(
            'verification_phase="restart_service_recovery"', 1
        )[0]
        self.assertIn("ORDENOWA bootstrap: storefront=ja, en/ko=enabled, admin=ko, theme=kuranea", marker_check)
        self.assertIn("KURANEA bootstrap already completed\\.", marker_check)
        self.assertIn("initial_storefront_http_request", script)
        self.assertIn("initial_admin_login_http_request", script)

    def test_isolated_preinstall_probe_repairs_a_root_owned_class_index(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        probe = workflow.split("- name: Verify fresh cache ownership in an isolated probe project", 1)[1].split("- name:", 1)[0]
        self.assertIn('probe_project="${CI_COMPOSE_PROJECT_NAME}-cache-probe"', probe)
        self.assertIn("run --rm --no-deps", probe)
        self.assertIn('chown -R root:root "$cache_dir"', probe)
        self.assertIn("/tmp/pre-install-scripts/10-kuranea-cache-ownership.sh", probe)
        self.assertIn('test "$(stat -c "%U:%G" "$cache_dir/class_index.php")" = www-data:www-data', probe)
        self.assertIn("runuser -g www-data -u www-data -- test -w", probe)
        self.assertIn('docker compose -p "$probe_project" down -v --remove-orphans', probe)
        start = workflow.split("- name: Start the empty-volume shop", 1)[1].split("- name:", 1)[0]
        self.assertIn('docker compose -p "$CI_COMPOSE_PROJECT_NAME" up -d --wait --wait-timeout 900', start)

    def test_catalog_install_and_queue_persistence_check_precedes_postal_download(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        shop_start = workflow.index("- name: Start the empty-volume shop")
        catalog_check = workflow.index("- name: Verify the installed KURANEA catalog review module and persistent queue")
        postal_download = workflow.index("- name: Download and import official Japan Post KEN_ALL data")
        self.assertLess(shop_start, catalog_check)
        self.assertLess(catalog_check, postal_download)

        catalog_step = workflow[catalog_check:postal_download]
        self.assertIn("tests/catalog/verify_catalog_installation.php", catalog_step)
        self.assertIn("tests/catalog/fixtures/amazon-jp-product.synthetic.html", catalog_step)
        self.assertIn("restart prestashop", catalog_step)
        self.assertGreaterEqual(catalog_step.count("php /tmp/verify_catalog_installation.php"), 2)

    def test_synthetic_order_qa_is_isolated_from_live_japan_post_download(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        fixture = workflow.index("- name: Import synthetic Tokyo postcode fixture for isolated checkout QA")
        postcode = workflow.index("- name: Verify isolated CI Tokyo postcode lookup")
        address = workflow.index("- name: Verify saved native CI Tokyo address")
        order = workflow.index("- name: Verify synthetic Tokyo address in an unpaid native order and Back Office view")
        official = workflow.index("- name: Download and import official Japan Post KEN_ALL data")
        self.assertLess(fixture, postcode)
        self.assertLess(postcode, address)
        self.assertLess(address, order)
        self.assertLess(order, official)
        self.assertIn("ISOLATED CI FIXTURE:", workflow)
        self.assertIn("Verify official Japan Post import contains national address data", workflow)
        self.assertIn("ps_kuraneapostcode_address", workflow)

    def test_failed_compose_bootstrap_publishes_a_redacted_step_summary(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        capture = workflow.split("- name: Capture bounded diagnostics on failure", 1)[1].split("- name:", 1)[0]
        diagnostics = (ROOT / "tests/smoke/collect_failure_diagnostics.sh").read_text(encoding="utf-8")
        self.assertIn("if: failure()", capture)
        self.assertIn("steps.image_build.outcome", capture)
        self.assertIn("steps.cache_probe.outcome", capture)
        self.assertIn("steps.compose_up.outcome", capture)
        self.assertIn("bash tests/smoke/collect_failure_diagnostics.sh", capture)
        self.assertIn("GITHUB_STEP_SUMMARY", diagnostics)
        self.assertIn("[REDACTED]", diagnostics)
        self.assertIn("Upload redacted install diagnostics", workflow)
        self.assertIn("retention-days: 2", workflow)

    def test_every_workflow_failure_uses_the_redacting_collector(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        capture = workflow.split("- name: Capture bounded diagnostics on failure", 1)[1].split("- name:", 1)[0]
        self.assertIn("if: failure()", capture)
        self.assertIn("bash tests/smoke/collect_failure_diagnostics.sh", capture)
        self.assertNotIn("docker compose", capture)

    def test_native_order_persistence_test_is_guarded_to_its_isolated_github_project(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        order_step = workflow.split("- name: Verify synthetic Tokyo address in an unpaid native order and Back Office view", 1)[1].split("- name:", 1)[0]
        order_test = (ROOT / "tests/postcode/verify_native_order_persistence.php").read_text(encoding="utf-8")
        self.assertIn("KURANEA_ISOLATED_CI=1", order_step)
        self.assertIn('KURANEA_CI_PROJECT_NAME="$CI_COMPOSE_PROJECT_NAME"', order_step)
        self.assertIn('KURANEA_CI_RUN_ID="$GITHUB_RUN_ID"', order_step)
        self.assertIn('KURANEA_CI_RUN_ATTEMPT="$GITHUB_RUN_ATTEMPT"', order_step)
        self.assertIn("getenv('CI') !== 'true'", order_test)
        self.assertIn("getenv('GITHUB_ACTIONS') !== 'true'", order_test)
        self.assertIn("$projectName !== $expectedProjectName", order_test)
        self.assertIn("instanceof PaymentModule", order_test)
        self.assertIn("GetOrderForViewing", order_test)
        self.assertIn("get('prestashop.core.query_bus')", order_test)
        self.assertIn("QuerySorting::DESC", order_test)
        self.assertNotIn("CommandBusInterface::class", order_test)
        self.assertIn("KURANEA_NATIVE_ORDER_STAGE", order_test)
        self.assertIn("::error title=KURANEA native order::", order_test)
        for stage in (
            "PrestaShop bootstrap",
            "Back Office kernel boot",
            "Japanese shop context",
            "offline payment module",
            "isolated CI postcode candidate",
            "customer and address persistence",
            "CI-only product creation",
            "CI-only carrier setup",
            "native cart and quantity",
            "delivery option",
            "unpaid native order",
            "Back Office shipping address projection",
        ):
            self.assertIn(stage, order_test)

    def test_postcode_lookup_and_native_address_save_report_separate_ci_failures(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python3 -m unittest tests.smoke.test_fresh_install_workflow_contract", workflow)
        self.assertIn("- name: Verify isolated CI Tokyo postcode lookup", workflow)
        self.assertIn("- name: Verify saved native CI Tokyo address", workflow)
        address_step = workflow.split("- name: Verify saved native CI Tokyo address", 1)[1].split("- name:", 1)[0]
        self.assertIn("tests/postcode/verify_native_address_persistence.php", address_step)

        verifier = (ROOT / "tests" / "postcode" / "verify_native_address_persistence.php").read_text(encoding="utf-8")
        self.assertIn("KURANEA_NATIVE_ADDRESS_STAGE", verifier)
        self.assertIn("::error title=KURANEA address persistence::", verifier)
        for stage in (
            "bootstrap",
            "Japan and state lookup",
            "isolated CI postcode candidate",
            "customer creation",
            "native address save",
            "saved address reload",
        ):
            self.assertIn(stage, verifier)

    def test_native_address_verifiers_do_not_assign_unsupported_shop_property(self) -> None:
        verifier_paths = (
            ROOT / "tests" / "postcode" / "verify_native_address_persistence.php",
            ROOT / "tests" / "postcode" / "verify_native_order_persistence.php",
        )
        for verifier_path in verifier_paths:
            with self.subTest(verifier=verifier_path.name):
                verifier = verifier_path.read_text(encoding="utf-8")
                self.assertNotRegex(verifier, r"\$address->id_shop\s*=")
                self.assertIn("$address->id_customer =", verifier)

    def test_successful_postal_import_clears_only_the_staging_copy(self) -> None:
        importer = POSTAL_IMPORT.read_text(encoding="utf-8")
        smoke = FRESH_INSTALL_SMOKE.read_text(encoding="utf-8")
        commit = importer.index("$database->execute('COMMIT')")
        cleanup = importer.index("$database->execute('TRUNCATE TABLE ' . $stageTable)", commit)
        self.assertGreater(cleanup, commit, "staging may only be cleared after the new main table commits")
        self.assertIn("ps_kuraneapostcode_stage", smoke)
        self.assertIn('test "$postcode_stage_rows" = 0', smoke)

    def test_catalog_parser_failure_diagnostics_are_bounded_and_escaped(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "catalog-parser.yml").read_text(encoding="utf-8")
        step = workflow.split("- name: Run synthetic offline Amazon Japan and Rakuten parser tests", 1)[1].split("- name:", 1)[0]
        failure_branch = step.split('if [ "$test_status" -ne 0 ]; then', 1)[1].split("fi", 1)[0]
        self.assertIn('tail -n 80 "$test_log"', failure_branch)
        self.assertIn("cut -c1-500", failure_branch)
        self.assertIn("%25", failure_branch)
        self.assertIn("%0D", failure_branch)
        self.assertIn("%0A", failure_branch)
        self.assertLess(step.index('if [ "$test_status"'), step.index('cat "$test_log"'))

    def test_catalog_parser_contract_checks_out_hummingbird_submodule(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "catalog-parser.yml").read_text(encoding="utf-8")
        checkout = workflow.split("- name: Check out work", 1)[1].split("- name:", 1)[0]
        path_filter = workflow.split("    paths:", 1)[1].split("\n\npermissions:", 1)[0]

        self.assertRegex(checkout, r"uses: actions/checkout@v4\s+with:\s+submodules: recursive")
        self.assertIn(".gitmodules", path_filter)
        self.assertIn("themes/hummingbird", path_filter)

    def test_checkout_restore_only_runs_after_checkout_override_was_attempted(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        restore_step = workflow.split("id: checkout_restore", 1)[1].split("- name:", 1)[0]

        self.assertRegex(
            restore_step,
            r"if:\s*always\(\)\s*&&\s*steps\.checkout_override\.outcome\s*!=\s*'skipped'",
            "restoration should run after a failed or successful override, but not when checkout QA never started",
        )


if __name__ == "__main__":
    unittest.main()
