from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / "tests" / "e2e" / "verify_ci_native_customer_return_browser.py"


class CiNativeCustomerReturnBrowserContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not FLOW.is_file():
            raise AssertionError("the isolated native customer return browser flow is missing")
        cls.source = FLOW.read_text(encoding="utf-8")

    def assertContract(self, source: str, required: str) -> None:
        if required not in source:
            self.fail(f"missing required contract: {required}")

    def test_customer_return_browser_requires_exact_isolated_actions_project(self) -> None:
        for required in (
            'os.environ.get("CI") != "true"',
            'os.environ.get("GITHUB_ACTIONS") != "true"',
            'os.environ.get("KURANEA_ISOLATED_CI") != "1"',
            'run_id = os.environ.get("GITHUB_RUN_ID", "")',
            'run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")',
            'expected_project_name = f"kuranea-ci-{run_id}-{run_attempt}"',
            'os.environ.get("KURANEA_CI_PROJECT_NAME") != expected_project_name',
        ):
            with self.subTest(required=required):
                self.assertContract(self.source, required)

    def test_customer_credentials_are_only_sent_to_loopback_http_shop(self) -> None:
        for required in (
            'parsed.scheme != "http"',
            '(parsed.hostname or "").lower() not in {"localhost", "127.0.0.1", "::1"}',
            "parsed.username is not None",
            "parsed.password is not None",
            "parsed.query",
            "parsed.fragment",
            "if port != 18080:",
        ):
            with self.subTest(required=required):
                self.assertContract(self.source, required)

        target_validation = self.source.index("base_url = read_isolated_shop_url()")
        credential_load = self.source.index('email = str(checkout_artifact.get("email", ""))')
        browser_start = self.source.index("stage = \"webdriver.startup\"")
        self.assertLess(target_validation, credential_load)
        self.assertLess(target_validation, browser_start)

    def test_checkout_override_is_explicit_in_the_workflow(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        step = workflow.split("- name: Submit customer return request in Chromium", 1)[1].split(
            "- name:", 1
        )[0]
        for required in (
            "CI: 'true'",
            "KURANEA_ISOLATED_CI: '1'",
            "KURANEA_CI_PROJECT_NAME: ${{ env.CI_COMPOSE_PROJECT_NAME }}",
            "SHOP_BASE_URL: http://localhost:18080",
        ):
            with self.subTest(required=required):
                self.assertContract(step, required)

    def test_order_detail_interactions_have_distinct_stages_and_pointer_diagnostics(self) -> None:
        self.assertContract(self.source, 'stage = "return_quantity_select"')
        self.assertContract(self.source, 'stage = "return_product_checkbox"')
        quantity_stage = self.source.index('stage = "return_quantity_select"')
        quantity_selection = self.source.index('Select(quantity).select_by_value("1")')
        checkbox_stage = self.source.index('stage = "return_product_checkbox"')
        centered_scroll = self.source.index('scrollIntoView({block: "center", inline: "nearest"})')
        checkbox_click = self.source.index("checkbox.click()")
        self.assertLess(quantity_stage, quantity_selection)
        self.assertLess(quantity_selection, checkbox_stage)
        self.assertLess(checkbox_stage, centered_scroll)
        self.assertLess(centered_scroll, checkbox_click)

        for required in (
            "ElementClickInterceptedException",
            "TimeoutException",
            "poll_frequency=0.1",
            "def checkbox_center_is_unobstructed(browser)",
            "WebDriverWait(driver, 3, poll_frequency=0.1).until(checkbox_center_is_unobstructed)",
            "target === element || element.contains(target)",
            "document.elementFromPoint",
            'tag: target.tagName.toLowerCase()',
            "id: target.id",
            'class: typeof target.className === "string" ? target.className : ""',
            'limits = {"tag": 24, "id": 80, "class": 120}',
            '[:limit]',
            "ORDENOWA_RETURN_CLICK_BLOCKER_SAFE_STATE=",
            "::error title=Return checkbox pointer target::",
            'customer-return-click-intercepted.png',
            '"click_intercept_target": click_intercept_target',
            '"failure_screenshot": failure_screenshot',
        ):
            with self.subTest(required=required):
                self.assertContract(self.source, required)

        self.assertLess(self.source.index("WebDriverWait(driver, 3, poll_frequency=0.1)"),
                        self.source.index("checkbox.click()"))
        self.assertIn("except (ElementClickInterceptedException, TimeoutException):", self.source)

    def test_submit_button_interception_emits_bounded_safe_diagnostics_before_quit(self) -> None:
        self.assertContract(self.source, "def capture_submit_click_blocker(")
        submit_block = self.source.split('stage = "return_form_submit"', 1)[1].split(
            'stage = "return_list_readback"', 1
        )[0]
        self.assertIn("except ElementClickInterceptedException:", submit_block)
        self.assertIn("capture_submit_click_blocker(driver, submit_button, artifact_dir)", submit_block)
        self.assertIn("submit_button.click()", submit_block)
        self.assertLess(submit_block.index("submit_button.click()"), submit_block.index("except ElementClickInterceptedException:"))
        self.assertLess(submit_block.index("capture_submit_click_blocker("), submit_block.index("raise"))

        for required in (
            "document.elementFromPoint",
            'tag: target.tagName.toLowerCase()',
            "id: target.id",
            'class: typeof target.className === "string" ? target.className : ""',
            'limits = {"tag": 24, "id": 80, "class": 120}',
            "ORDENOWA_RETURN_SUBMIT_BLOCKER_SAFE_STATE=",
            "::error title=Return submit click target::",
            'GITHUB_STEP_SUMMARY',
            'customer-return-submit-click-intercepted.png',
            '"submit_click_intercept_target": submit_click_intercept_target',
            '"submit_failure_screenshot": submit_failure_screenshot',
        ):
            with self.subTest(required=required):
                self.assertContract(self.source, required)


if __name__ == "__main__":
    unittest.main()
