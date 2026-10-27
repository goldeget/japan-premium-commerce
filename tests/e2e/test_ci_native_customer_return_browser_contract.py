from __future__ import annotations

import ast
import json
import re
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
        main_flow = self.source.split('stage = "return_quantity_select"', 1)[1].split(
            'stage = "return_form_submit"', 1
        )[0]
        quantity_selection = main_flow.index('Select(quantity).select_by_value("1")')
        checkbox_stage = main_flow.index('stage = "return_product_checkbox"')
        checkbox_wait = main_flow.index(
            "wait_for_return_checkbox(driver, order_id, checkbox_name)"
        )
        checkbox_click = main_flow.index("checkbox.click()")
        self.assertLess(quantity_selection, checkbox_stage)
        self.assertLess(checkbox_stage, checkbox_wait)
        self.assertLess(checkbox_wait, checkbox_click)

        for required in (
            "ElementClickInterceptedException",
            "StaleElementReferenceException",
            "TimeoutException",
            "poll_frequency=0.1",
            "def checkbox_center_is_unobstructed(browser)",
            "WebDriverWait(driver, 3, poll_frequency=0.1).until(checkbox_center_is_unobstructed)",
            'browser.find_elements(By.CSS_SELECTOR, "#order-return-form")',
            'return_form.find_elements(By.NAME, "id_order")',
            'By.CSS_SELECTOR, "input[name^=\'ids_order_detail[\']"',
            'checkbox.get_attribute("name") or "") != checkbox_name',
            'except StaleElementReferenceException:',
            "target === element || element.contains(target)",
            "document.elementFromPoint",
            'tag: target.tagName.toLowerCase()',
            "id: target.id",
            'class: typeof target.className === "string" ? target.className : ""',
            "sanitize_click_target_metadata(topmost)",
            '"btn-primary"',
            '"modal-backdrop"',
            "ORDENOWA_RETURN_CLICK_BLOCKER_SAFE_STATE=",
            "::error title=Return checkbox pointer target::",
            'customer-return-click-intercepted.png',
            '"click_intercept_target": click_intercept_target',
            '"failure_screenshot": failure_screenshot',
        ):
            with self.subTest(required=required):
                self.assertContract(self.source, required)

        helper = self.source.split("def wait_for_return_checkbox(", 1)[1].split(
            "\ndef same_origin", 1
        )[0]
        self.assertIn("WebDriverWait(driver, 3, poll_frequency=0.1)", helper)
        self.assertIn("except (ElementClickInterceptedException, TimeoutException):", self.source)

    def test_checkbox_readiness_reacquires_after_stale_reference_without_clicking(self) -> None:
        tree = ast.parse(self.source)
        helper = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "wait_for_return_checkbox"
        )

        class FakeStaleElementReference(Exception):
            pass

        class FakeBy:
            CSS_SELECTOR = "css selector"
            NAME = "name"

        class FakeWait:
            calls: list[tuple[int, float]] = []

            def __init__(self, driver, timeout, poll_frequency):
                self.driver = driver
                self.calls.append((timeout, poll_frequency))

            def until(self, predicate):
                for _ in range(3):
                    result = predicate(self.driver)
                    if result:
                        return result
                raise AssertionError("read-only checkbox readiness predicate did not become true")

        class FakeField:
            def __init__(self, value):
                self.value = value

            def get_attribute(self, name):
                assert name == "value"
                return self.value

        class FakeCheckbox:
            def __init__(self, name, stale=False):
                self.name = name
                self.stale = stale
                self.clicks = 0

            def get_attribute(self, name):
                assert name == "name"
                if self.stale:
                    raise FakeStaleElementReference("old node was detached")
                return self.name

            def is_enabled(self):
                return True

            def click(self):
                self.clicks += 1

        class FakeForm:
            def __init__(self, checkbox, order_id):
                self.checkbox = checkbox
                self.order_id = order_id

            def is_displayed(self):
                return True

            def find_elements(self, by, selector):
                if by == FakeBy.NAME and selector == "id_order":
                    return [FakeField(self.order_id)]
                if by == FakeBy.CSS_SELECTOR and selector == "input[name^='ids_order_detail[']":
                    return [self.checkbox]
                raise AssertionError(f"unexpected form lookup: {by} {selector}")

        stale_checkbox = FakeCheckbox("ids_order_detail[731]", stale=True)
        fresh_checkbox = FakeCheckbox("ids_order_detail[731]")
        stale_form = FakeForm(stale_checkbox, "842")
        fresh_form = FakeForm(fresh_checkbox, "842")

        class FakeDriver:
            def __init__(self):
                self.form_reads = 0

            def find_elements(self, by, selector):
                assert by == FakeBy.CSS_SELECTOR
                assert selector == "#order-return-form"
                self.form_reads += 1
                return [stale_form if self.form_reads == 1 else fresh_form]

            def execute_script(self, script, element):
                if "scrollIntoView" in script:
                    assert element is fresh_checkbox
                    return None
                assert "document.elementFromPoint" in script
                assert element is fresh_checkbox
                return True

        namespace = {
            "By": FakeBy,
            "WebDriverWait": FakeWait,
            "StaleElementReferenceException": FakeStaleElementReference,
        }
        exec(compile(ast.Module(body=[helper], type_ignores=[]), str(FLOW), "exec"), namespace)
        driver = FakeDriver()
        refreshed_form, checkbox = namespace["wait_for_return_checkbox"](
            driver, 842, "ids_order_detail[731]"
        )

        self.assertIs(refreshed_form, fresh_form)
        self.assertIs(checkbox, fresh_checkbox)
        self.assertEqual(driver.form_reads, 2)
        self.assertEqual(FakeWait.calls, [(3, 0.1)])
        self.assertEqual(stale_checkbox.clicks, 0)
        self.assertEqual(fresh_checkbox.clicks, 0)

    def test_submit_button_interception_emits_bounded_safe_diagnostics_before_quit(self) -> None:
        self.assertContract(self.source, "def capture_submit_click_blocker(")
        submit_block = self.source.split('stage = "return_form_submit"', 1)[1].split(
            'stage = "return_list_readback"', 1
        )[0]
        self.assertIn(
            '\'arguments[0].scrollIntoView({block: "center", inline: "nearest"});\', submit_button',
            submit_block,
        )
        self.assertIn("def submit_button_center_is_unobstructed(browser)", submit_block)
        self.assertIn(
            "WebDriverWait(driver, 3, poll_frequency=0.1).until(submit_button_center_is_unobstructed)",
            submit_block,
        )
        self.assertIn("target === element || element.contains(target)", submit_block)
        self.assertIn("except (ElementClickInterceptedException, TimeoutException):", submit_block)
        self.assertIn("capture_submit_click_blocker(", submit_block)
        self.assertIn("submit_button.click()", submit_block)
        self.assertLess(submit_block.index("scrollIntoView"), submit_block.index("submit_button.click()"))
        self.assertLess(submit_block.index("submit_button_center_is_unobstructed(browser)"), submit_block.index("submit_button.click()"))
        self.assertLess(
            submit_block.index("WebDriverWait(driver, 3, poll_frequency=0.1).until(submit_button_center_is_unobstructed)"),
            submit_block.index("submit_button.click()"),
        )
        self.assertLess(
            submit_block.index("submit_button.click()"),
            submit_block.index("except (ElementClickInterceptedException, TimeoutException):"),
        )
        self.assertLess(submit_block.index("capture_submit_click_blocker("), submit_block.index("raise"))

        for required in (
            "document.elementFromPoint",
            'tag: target.tagName.toLowerCase()',
            "id: target.id",
            'class: typeof target.className === "string" ? target.className : ""',
            'status: target ? "target" : "no_target"',
            '"status": "unexpected_result"',
            '"status": "script_error"',
            'result_status = topmost.get("status")',
            '"ready_state": ready_state',
            '"center_in_viewport": topmost.get("center_in_viewport") is True',
            '"button_rect": {',
            '"viewport": {',
            '"exception_type": exception_type',
            '"submit_click_diagnostic": submit_click_diagnostic',
            "ORDENOWA_RETURN_SUBMIT_BLOCKER_SAFE_STATE=",
            "::error title=Return submit click target::",
            'GITHUB_STEP_SUMMARY',
            'customer-return-submit-click-intercepted.png',
            '"submit_click_intercept_target": submit_click_intercept_target',
            '"submit_failure_screenshot": submit_failure_screenshot',
        ):
            with self.subTest(required=required):
                self.assertContract(self.source, required)

    def test_submit_blocker_selector_metadata_redacts_unknown_identifiers(self) -> None:
        tree = ast.parse(self.source)
        sanitizer = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "sanitize_click_target_metadata"
            ),
            None,
        )
        self.assertIsNotNone(sanitizer, "click blocker needs a strict selector metadata sanitizer")
        namespace = {"re": re}
        exec(compile(ast.Module(body=[sanitizer], type_ignores=[]), str(FLOW), "exec"), namespace)
        sanitize = namespace["sanitize_click_target_metadata"]

        examples = (
            "Jane Doe",
            "JaneDoe",
            "jane.doe@example.com",
            "customer-12345",
        )
        for example in examples:
            with self.subTest(example=example):
                safe = sanitize({"tag": "div", "id": example, "class": example})
                serialized = json.dumps(safe, ensure_ascii=True, sort_keys=True)
                self.assertNotIn(example, serialized)
                self.assertEqual(safe["id"], "")

        safe = sanitize({"tag": "button", "id": "submitButton", "class": "btn btn-primary customer-12345"})
        self.assertEqual(safe["class"], "btn btn-primary")
        self.assertEqual(safe["tag"], "button")

        for required in (
            'print("ORDENOWA_RETURN_SUBMIT_BLOCKER_SAFE_STATE=" + diagnostic_json)',
            '"::error title=Return submit click target::" + annotation',
            'summary.write(f"Safe browser hit-test state: `{diagnostic_json}`\\n")',
            '"submit_click_diagnostic": submit_click_diagnostic',
            "submit_click_diagnostic, submit_failure_screenshot_name = capture_submit_click_blocker(",
        ):
            with self.subTest(required=required):
                self.assertContract(self.source, required)

    def test_checkbox_and_submit_blocker_share_strict_selector_metadata_allowlist(self) -> None:
        tree = ast.parse(self.source)
        sanitizer = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "sanitize_click_target_metadata"
            ),
            None,
        )
        self.assertIsNotNone(sanitizer, "click blocker diagnostics need a shared selector metadata sanitizer")
        namespace = {"re": re}
        exec(compile(ast.Module(body=[sanitizer], type_ignores=[]), str(FLOW), "exec"), namespace)
        sanitize = namespace["sanitize_click_target_metadata"]

        for function_name in ("capture_checkbox_click_blocker", "capture_submit_click_blocker"):
            function = next(
                node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == function_name
            )
            calls = {
                node.func.id
                for node in ast.walk(function)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
            self.assertIn("sanitize_click_target_metadata", calls, function_name)

        private_values = (
            "Jane Doe",
            "JaneDoe",
            "jane.doe@example.com",
            "customer-12345",
        )
        for private_value in private_values:
            with self.subTest(private_value=private_value):
                safe = sanitize({"tag": "div", "id": private_value, "class": private_value})
                serialized = json.dumps(safe, ensure_ascii=True, sort_keys=True)
                self.assertNotIn(private_value, serialized)
                self.assertEqual(safe["id"], "")
                self.assertEqual(safe["class"], "")

        safe = sanitize({"tag": "button", "id": "submitButton", "class": "btn btn-primary customer-12345"})
        self.assertEqual(safe, {"tag": "button", "id": "", "class": "btn btn-primary"})


if __name__ == "__main__":
    unittest.main()
