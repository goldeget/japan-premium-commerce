"""Lock in the ordered customer account browser flow without Docker."""
from __future__ import annotations

import ast
import json
import re
import sys
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, parse_qsl, unquote, urljoin, urlparse


ROOT = Path(__file__).resolve().parents[2]
ACCOUNT_FLOW = ROOT / "tests" / "e2e" / "verify_customer_account_browser.py"


def stage_blocks(source: str) -> tuple[list[str], dict[str, str]]:
    """Return the source blocks delimited by run_viewport's stage assignments."""
    tree = ast.parse(source)
    run_viewport = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "run_viewport"
    )
    stages: list[tuple[int, str]] = []
    for node in ast.walk(run_viewport):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if node.targets[0].id != "stage" or not isinstance(node.value, ast.Constant):
            continue
        if isinstance(node.value.value, str):
            stages.append((node.lineno, node.value.value))

    stages.sort()
    lines = source.splitlines(keepends=True)
    blocks: dict[str, str] = {}
    for index, (line_number, stage) in enumerate(stages):
        end_line = stages[index + 1][0] - 1 if index + 1 < len(stages) else run_viewport.end_lineno
        blocks[stage] = "".join(lines[line_number - 1 : end_line])
    return [stage for _, stage in stages], blocks


class CustomerAccountBrowserFlowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = ACCOUNT_FLOW.read_text(encoding="utf-8")
        cls.stages, cls.blocks = stage_blocks(cls.source)

    def test_registration_profile_email_login_and_reset_are_ordered(self) -> None:
        required_stages = (
            "registration_submit",
            "registration_post_submit",
            "profile_update_route",
            "profile_update_persist_wait",
            "email_login",
            "password_reset_request",
            "password_reset",
            "password_reset_old_password_rejected",
            "password_reset_login",
        )
        positions = [self.stages.index(stage) for stage in required_stages]
        self.assertEqual(positions, sorted(positions))

        registration = self.blocks["registration_post_submit"]
        self.assertIn("wait_for_registration_success(driver)", registration)
        self.assertIn('assert_my_page(driver, "CI")', registration)

        profile_route = self.blocks["profile_update_route"]
        self.assertIn('driver.get(f"{BASE}/index.php?controller=identity")', profile_route)
        self.assertIn('assert_canonical_static_route(driver, "identity")', profile_route)

        profile_save = self.blocks["profile_update_persist_wait"]
        self.assertIn("expected_first_name", profile_save)
        self.assertIn("driver.get(account_url)", profile_save)
        self.assertIn(
            "assert_my_page(driver, expected_first_name, substage_callback=mark_profile_update_substage)",
            profile_save,
        )
        self.assertIn('driver.get(f"{BASE}/index.php?controller=identity")', profile_save)
        self.assertIn('#customer-form input[name="firstname"]', profile_save)
        account_reopen = profile_save.index("driver.get(account_url)")
        account_assertion = profile_save.index(
            "assert_my_page(driver, expected_first_name, substage_callback=mark_profile_update_substage)"
        )
        identity_reopen = profile_save.index('driver.get(f"{BASE}/index.php?controller=identity")')
        identity_route_assertion = profile_save.index(
            'assert_canonical_static_route(driver, "identity")', identity_reopen
        )
        persisted_field_wait = profile_save.index("WebDriverWait(driver, 30).until(")
        persisted_first_name = profile_save.index(
            "#customer-form input[name=\"firstname\"]", persisted_field_wait
        )
        return_to_account = profile_save.rindex("driver.get(account_url)")
        authenticated_account_assertion = profile_save.rindex(
            "assert_my_page(driver, expected_first_name, substage_callback=mark_profile_update_substage)"
        )
        self.assertLess(account_reopen, account_assertion)
        self.assertLess(account_assertion, identity_reopen)
        self.assertLess(identity_reopen, identity_route_assertion)
        self.assertLess(identity_route_assertion, persisted_field_wait)
        self.assertLess(persisted_field_wait, persisted_first_name)
        self.assertLess(persisted_first_name, return_to_account)
        self.assertLess(return_to_account, authenticated_account_assertion)

    def test_registration_accepts_authenticated_home_redirect_and_opens_my_page(self) -> None:
        wait_function = next(
            node
            for node in ast.parse(self.source).body
            if isinstance(node, ast.FunctionDef)
            and node.name == "wait_for_registration_success"
        )
        account_url = "http://localhost:18080/ko/my-account"
        account_link = object()
        state: dict[str, object] = {"visited": [], "open_menu": None}

        class Browser:
            current_url = "http://localhost:18080/ko/"

            def execute_script(self, _script: str) -> str:
                return "header"

            def get(self, url: str) -> None:
                state["visited"].append(url)
                self.current_url = url

        class ImmediateWait:
            def __init__(self, browser: Browser, _timeout: int) -> None:
                self.browser = browser

            def until(self, predicate, **_kwargs: object):
                return predicate(self.browser)

        def resolve_account(_browser: Browser, *, open_menu: bool = True):
            state["open_menu"] = open_menu
            return account_link, account_url

        def require_my_page(browser: Browser, selector: str):
            if selector != "#identity_main_link":
                raise AssertionError("registration success must verify the My Page identity link")
            if browser.current_url != account_url:
                raise AssertionError("authenticated home redirect must navigate to the account URL first")
            return object()

        namespace = {
            "webdriver": SimpleNamespace(Chrome=Browser),
            "WebDriverWait": ImmediateWait,
            "my_account_link_from_header": resolve_account,
            "visible": require_my_page,
        }
        exec(
            compile(ast.Module(body=[wait_function], type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )

        namespace["wait_for_registration_success"](Browser())

        self.assertEqual(state["visited"], [account_url])
        self.assertIs(state["open_menu"], False)

    def test_duplicate_email_registration_is_rejected_before_profile_update(self) -> None:
        required_stages = (
            "registration_post_submit",
            "registration_duplicate_email",
            "registration_duplicate_email_submit",
            "registration_duplicate_email_rejected",
            "registration_duplicate_email_relogin",
            "profile_update_route",
        )
        positions = [self.stages.index(stage) for stage in required_stages]
        self.assertEqual(positions, sorted(positions))

        duplicate_open = self.blocks["registration_duplicate_email"]
        self.assertIn("logout(driver, login_url=login_url)", duplicate_open)
        self.assertIn("driver.get(registration_url)", duplicate_open)
        self.assertIn("safe_generated_route_match", duplicate_open)

        duplicate_submit = self.blocks["registration_duplicate_email_submit"]
        self.assertIn("prepare_required_registration_fields", duplicate_submit)
        self.assertIn("account_email", duplicate_submit)
        self.assertIn("click_centered(driver, submit_button)", duplicate_submit)

        duplicate_rejected = self.blocks["registration_duplicate_email_rejected"]
        self.assertIn("assert_duplicate_email_rejected(driver)", duplicate_rejected)
        self.assertIn("def assert_duplicate_email_rejected", self.source)
        duplicate_pattern = next(
            node
            for node in ast.parse(self.source).body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "DUPLICATE_EMAIL_REJECTION"
                for target in node.targets
            )
        )
        namespace = {"re": re}
        exec(
            compile(ast.Module(body=[duplicate_pattern], type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )
        duplicate_email_rejection = namespace["DUPLICATE_EMAIL_REJECTION"]
        for message in (
            "An account using this email address has already been registered.",
            "이미 등록된 이메일 주소입니다.",
            "このメールアドレスは既に登録されています。",
        ):
            self.assertRegex(message, duplicate_email_rejection)
        self.assertNotRegex("The password field is required.", duplicate_email_rejection)

        relogin = self.blocks["registration_duplicate_email_relogin"]
        self.assertIn("driver.get(login_url)", relogin)
        self.assertIn("submit_login(driver, account_email, initial_password)", relogin)
        self.assertIn("assert_my_page(driver, \"CI\")", relogin)

    def test_customer_address_add_edit_and_reload_persistence_are_ordered(self) -> None:
        required_stages = (
            "profile_update_persist_wait",
            "customer_address_add",
            "customer_address_add_persist_wait",
            "customer_address_edit",
            "customer_address_edit_copy",
            "customer_address_edit_submit",
            "customer_address_edit_persist_wait",
            "email_login",
        )
        positions = [self.stages.index(stage) for stage in required_stages]
        self.assertEqual(positions, sorted(positions))

        address_add = self.blocks["customer_address_add"]
        self.assertIn("create_customer_address(", address_add)
        self.assertIn("substage_callback=mark_customer_address_substage", address_add)
        create_address = self.source.split("def create_customer_address", 1)[1].split(
            "def collect_customer_address_diagnostics", 1
        )[0]
        self.assertIn('visible(driver, "#address_main_link")', create_address)
        self.assertIn("click_centered(driver, address_link)", create_address)
        self.assertIn("urljoin(driver.current_url, href)", create_address)
        address_route_load = create_address.index('mark_substage("address_route_load")')
        native_address_link = create_address.index('visible(driver, "#address_main_link")')
        native_address_click = create_address.index("click_centered(driver, address_link)")
        address_form_load = create_address.index('mark_substage("address_form_load")')
        address_form_wait = create_address.index('visible(driver, ".js-address-form form")')
        self.assertLess(address_route_load, native_address_link)
        self.assertLess(native_address_link, native_address_click)
        self.assertLess(native_address_click, address_form_load)
        self.assertLess(address_form_load, address_form_wait)
        self.assertIn("address_location.scheme", create_address)
        self.assertNotIn("controller=address", create_address)
        address_add_persist = self.blocks["customer_address_add_persist_wait"]
        self.assertIn("wait_for_customer_address_card(driver, address_alias)", address_add_persist)

        address_edit = self.blocks["customer_address_edit"]
        self.assertRegex(
            address_edit,
            r"open_customer_address_edit\(\s*driver,\s*address_alias,\s*address_id,\s*"
            r"substage_callback=mark_customer_address_edit_substage,\s*"
            r"diagnostic_state=address_edit_state,\s*\)",
        )
        address_copy = self.blocks["customer_address_edit_copy"]
        self.assertIn("assert_korean_customer_address_edit_copy(driver)", address_copy)
        copy_assertion = self.source.split(
            "def assert_korean_customer_address_edit_copy", 1
        )[1].split("def save_customer_address_edit", 1)[0]
        self.assertIn('get_attribute("lang")', copy_assertion)
        self.assertIn('document_language.startswith("ko")', copy_assertion)
        self.assertIn("계정에 사용할 주소 정보를 입력해 주세요.", copy_assertion)
        address_submit = self.blocks["customer_address_edit_submit"]
        self.assertIn("save_customer_address_edit", address_submit)
        self.assertIn("edited_address_line", address_submit)
        address_persist = self.blocks["customer_address_edit_persist_wait"]
        self.assertIn("assert_customer_address_line", address_persist)
        self.assertIn("driver.refresh()", address_persist)
        self.assertIn("청구 및 배송 주소를 관리하여 다음 주문을 더 간편하게 진행하세요.", self.source)
        self.assertIn("Korean customer address list omitted its localized description", self.source)

        self.assertIn('data-link-action="edit-address"', self.source)
        self.assertIn('data-id-address', self.source)
        self.assertIn('name="kuraneapostcode_search"', self.source)
        self.assertIn('button[role="option"]', self.source)

    def test_customer_address_submission_waits_for_the_saved_card_before_navigation(self) -> None:
        create_address = self.source.split("def create_customer_address", 1)[1].split(
            "def collect_customer_address_diagnostics", 1
        )[0]
        submit = create_address.index(
            'click_centered(driver, visible(driver, ".js-address-form button.form-control-submit"))'
        )
        self.assertIn('mark_substage("address_submit_persistence")', create_address)
        persist_substage = create_address.index('mark_substage("address_submit_persistence")')
        saved_card_wait = create_address.index("wait_for_customer_address_card(driver, alias)")
        return_address = create_address.index("return alias, address_line")

        self.assertLess(submit, persist_substage)
        self.assertLess(persist_substage, saved_card_wait)
        self.assertLess(saved_card_wait, return_address)

    def test_customer_address_failure_reports_redacted_substage_state(self) -> None:
        address = self.source.split("def populate_japan_customer_address", 1)[1].split(
            "def assert_customer_address_line", 1
        )[0]
        for stage in (
            "address_route_load",
            "address_form_load",
            "address_country_select",
            "address_form_reload_after_country",
            "address_postcode_lookup",
            "address_postcode_candidate",
            "address_field_population",
            "address_native_validation",
            "address_submit",
        ):
            with self.subTest(stage=stage):
                self.assertIn(stage, address)
        self.assertLess(address.index("address_postcode_lookup"), address.index("address_postcode_candidate"))
        self.assertLess(address.index("address_postcode_candidate"), address.index("address_field_population"))
        self.assertIn("collect_customer_address_diagnostics", self.source)
        self.assertIn("emit_customer_address_diagnostics", self.source)
        collector = self.source.split("def collect_customer_address_diagnostics", 1)[1].split(
            "def emit_customer_address_diagnostics", 1
        )[0]
        self.assertIn("safe_same_origin_path(current_url)", collector)
        self.assertIn("invalid_controls", collector)
        self.assertNotIn(".value", collector)
        emitter = self.source.split("def emit_customer_address_diagnostics", 1)[1].split(
            "def fill", 1
        )[0]
        self.assertIn("::error title=Customer account address safe state::", emitter)
        run_viewport = self.source.split("def run_viewport", 1)[1].split(
            "\n\nif __name__", 1
        )[0]
        self.assertIn('stage == "customer_address_add"', run_viewport)
        self.assertIn("mark_customer_address_substage", run_viewport)
        self.assertIn('failure_control = {"name": "", "type": ""}', run_viewport)

    def test_customer_address_edit_records_each_navigation_boundary(self) -> None:
        edit_helper = self.source.split("def open_customer_address_edit", 1)[1].split(
            "def save_customer_address_edit", 1
        )[0]
        edit_substages = (
            "address_edit_card_wait",
            "address_edit_identity_check",
            "address_edit_link_lookup",
            "address_edit_link_origin_check",
            "address_edit_click_scroll",
            "address_edit_clickable_wait",
            "address_edit_center_hit_wait",
            "address_edit_native_click",
            "address_edit_native_click_returned",
            "address_edit_form_wait",
            "address_edit_form_identity_check",
        )
        for substage in edit_substages:
            with self.subTest(substage=substage):
                self.assertIn(substage, edit_helper)
        open_order = (
            'mark("address_edit_card_wait")',
            'mark("address_edit_identity_check")',
            'mark("address_edit_link_lookup")',
            'mark("address_edit_link_origin_check")',
            "center_unobstructed = click_centered(",
            'mark("address_edit_form_wait")',
            'mark("address_edit_form_identity_check")',
        )
        open_positions = [edit_helper.index(marker) for marker in open_order]
        self.assertEqual(open_positions, sorted(open_positions))
        click_helper = self.source.split("def click_centered", 1)[1].split(
            "def wait_for_registration_success", 1
        )[0]
        click_positions = [click_helper.index(marker) for marker in edit_substages[4:9]]
        self.assertEqual(click_positions, sorted(click_positions))

        self.assertIn("substage_callback", edit_helper)
        self.assertIn("last_completed_substage", edit_helper)
        self.assertIn("click_centered(", edit_helper)
        self.assertIn("edit_link,", edit_helper)
        self.assertIn("element.click()", self.source.split("def click_centered", 1)[1].split(
            "def wait_for_registration_success", 1
        )[0])

        run_viewport = self.source.split("def run_viewport", 1)[1].split(
            "\n\nif __name__", 1
        )[0]
        failure_handler = run_viewport.split("except Exception as error:", 1)[1].split(
            "inner_stage = (", 1
        )[0]
        self.assertIn('stage == "customer_address_edit"', failure_handler)
        self.assertIn("emit_customer_address_edit_diagnostics", failure_handler)
        self.assertIn('"customer_address_edit"', run_viewport)

    def test_customer_address_edit_diagnostics_are_redacted_and_bounded(self) -> None:
        tree = ast.parse(self.source)
        names = {
            "safe_diagnostic_boolean",
            "safe_diagnostic_name",
            "safe_same_origin_path",
            "collect_customer_address_edit_diagnostics",
            "emit_customer_address_edit_diagnostics",
        }
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names
        ]
        namespace = {
            "BASE": "https://shop.example.test",
            "json": json,
            "re": re,
            "sys": sys,
            "unquote": unquote,
            "urlparse": urlparse,
        }
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
                str(ACCOUNT_FLOW),
                "exec",
            ),
            namespace,
        )

        class FakeDriver:
            current_url = (
                "https://shop.example.test/ko/addresses/42?email=private%40example.test"
                "&token=secret-query-token"
            )

            @staticmethod
            def execute_script(_script: str, *_arguments: object) -> dict[str, object]:
                return {
                    "same_origin": True,
                    "document_path_changed": True,
                    "address_card_present": True,
                    "address_card_visible": True,
                    "expected_address_present": True,
                    "target_id_matches": True,
                    "edit_link_present": True,
                    "edit_link_visible": True,
                    "edit_link_enabled": True,
                    "edit_link_same_origin": True,
                    "native_click_attempted": True,
                    "native_click_returned": True,
                    "center_hit_relation": "other",
                    "occluder_classes": ["unlisted-layout-class"],
                    "edit_form_present": False,
                    "edit_form_visible": False,
                    "edit_form_id_matches": False,
                    "untrusted_address": "〒100-0004 private street",
                    "href": "https://shop.example.test/ko/addresses/42?token=secret-query-token",
                }

        state = {
            "substage": "address_edit_form_wait",
            "last_completed_substage": "address_edit_native_click_returned",
            "expected_address_id": "secret-address-id-42",
            "address_id": "secret-address-id-42",
            "alias": "private@example.test",
            "before_url": "https://shop.example.test/ko/addresses?token=secret-query-token",
            "native_click_attempted": True,
            "native_click_returned": True,
            "center_unobstructed": True,
            "center_hit_relation": "other",
            "failure_type": "TimeoutException",
        }
        output = StringIO()
        with redirect_stderr(output):
            namespace["emit_customer_address_edit_diagnostics"](FakeDriver(), state)
        rendered = output.getvalue()
        self.assertIn("ORDENOWA_CUSTOMER_ADDRESS_EDIT_SAFE_STATE=", rendered)
        for expected in (
            '"substage": "address_edit_form_wait"',
            '"last_completed_substage": "address_edit_native_click_returned"',
            '"same_origin": true',
            '"path": "/ko/addresses/<redacted>"',
            '"document_path_changed": true',
            '"expected_address_present": true',
            '"target_id_matches": true',
            '"native_click_returned": true',
            '"center_hit_relation": "other"',
            '"center_unobstructed": false',
            '"occluder_class": "other"',
            '"edit_form_present": false',
            '"edit_form_visible": false',
            '"edit_form_id_matches": false',
            '"failure_type": "TimeoutException"',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, rendered)
        for private_value in (
            "secret-address-id-42",
            "private@example.test",
            "secret-query-token",
            "private street",
            "unlisted-layout-class",
            "https://shop.example.test/ko/addresses/42?",
        ):
            with self.subTest(private_value=private_value):
                self.assertNotIn(private_value, rendered)

    def test_customer_address_persistence_reopens_native_list_and_reports_safe_state(self) -> None:
        persist = self.blocks["customer_address_add_persist_wait"]
        self.assertIn("driver.get(account_url)", persist)
        self.assertIn("assert_my_page(driver, expected_first_name)", persist)
        self.assertIn('visible(driver, "#addresses_main_link")', persist)
        self.assertIn("click_centered(driver, address_list_link)", persist)
        self.assertIn("wait_for_customer_address_card(driver, address_alias)", persist)
        self.assertIn("urljoin(driver.current_url, href)", persist)
        self.assertIn("address_list_location.scheme.lower()", persist)
        self.assertLess(persist.index("driver.get(account_url)"), persist.index("assert_my_page"))
        self.assertLess(
            persist.index("assert_my_page"),
            persist.index('visible(driver, "#addresses_main_link")'),
        )
        self.assertLess(
            persist.index('visible(driver, "#addresses_main_link")'),
            persist.index("click_centered(driver, address_list_link)"),
        )
        self.assertLess(
            persist.index("click_centered(driver, address_list_link)"),
            persist.index("wait_for_customer_address_card"),
        )

        run_viewport = self.source.split("def run_viewport", 1)[1].split(
            "\n\nif __name__", 1
        )[0]
        failure_handler = run_viewport.split("except Exception as error:", 1)[1].split(
            "inner_stage = (", 1
        )[0]
        self.assertIn('stage == "customer_address_add_persist_wait"', failure_handler)
        self.assertIn("emit_customer_address_persistence_diagnostics", failure_handler)

        persistence_collector = self.source.split(
            "def collect_customer_address_persistence_diagnostics", 1
        )[1].split("def emit_customer_address_persistence_diagnostics", 1)[0]
        self.assertNotIn(".value", persistence_collector)
        self.assertNotIn("body.text", persistence_collector)

        tree = ast.parse(self.source)
        names = {
            "safe_diagnostic_name",
            "safe_diagnostic_boolean",
            "safe_same_origin_path",
            "address_card_for_alias",
            "collect_customer_address_persistence_diagnostics",
            "emit_customer_address_persistence_diagnostics",
        }
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names
        ]
        namespace = {
            "BASE": "http://shop.example.test",
            "By": SimpleNamespace(CSS_SELECTOR="css selector", ID="id"),
            "json": json,
            "re": re,
            "sys": sys,
            "unquote": unquote,
            "urlparse": urlparse,
        }
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
                str(ACCOUNT_FLOW),
                "exec",
            ),
            namespace,
        )

        class FakeAlias:
            text = "private@example.test"

        class FakeCard:
            @staticmethod
            def find_elements(_by: str, selector: str) -> list[FakeAlias]:
                return [FakeAlias()] if selector == ".address-card__alias" else []

        class FakeElement:
            @staticmethod
            def is_displayed() -> bool:
                return True

        class FakeDriver:
            current_url = (
                "http://shop.example.test/addresses?email=private%40example.test&token=secret-reset-token"
            )

            @staticmethod
            def find_elements(_by: str, selector: str) -> list[object]:
                if selector == "article.address-card[data-id-address]":
                    return [FakeCard()]
                if selector == ".addresses__list":
                    return [FakeElement()]
                return []

        output = StringIO()
        with redirect_stderr(output):
            namespace["emit_customer_address_persistence_diagnostics"](
                FakeDriver(), "private@example.test", "address_card_wait"
            )
        rendered = output.getvalue()
        self.assertIn('"stage": "customer_address_add_persist_wait"', rendered)
        self.assertIn('"path": "/addresses"', rendered)
        self.assertIn('"expected_address_card_present": true', rendered)
        self.assertIn('"address_card_count": 1', rendered)
        for private_value in (
            "private@example.test",
            "secret-reset-token",
            "private%40example.test",
        ):
            with self.subTest(private_value=private_value):
                self.assertNotIn(private_value, rendered)

    def test_customer_address_diagnostic_output_omits_query_and_form_values(self) -> None:
        tree = ast.parse(self.source)
        names = {
            "safe_diagnostic_boolean",
            "safe_diagnostic_name",
            "safe_same_origin_path",
            "collect_customer_address_diagnostics",
            "emit_customer_address_diagnostics",
        }
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names
        ]
        namespace = {
            "BASE": "http://shop.example.test",
            "re": re,
            "urlparse": urlparse,
            "unquote": unquote,
            "json": json,
            "sys": sys,
            "webdriver": SimpleNamespace(Chrome=object),
        }
        exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), str(ACCOUNT_FLOW), "exec"), namespace)

        class FakeDriver:
            current_url = "http://shop.example.test/index.php?email=private%40example.test&token=secret-reset-token"

            @staticmethod
            def execute_script(script: str) -> dict[str, object]:
                if ".value" in script:
                    raise AssertionError("address diagnostics must not inspect form input values")
                return {
                    "form_present": True,
                    "form_visible": True,
                    "form_valid": False,
                    "country_present": True,
                    "country_selected": True,
                    "postal_search_present": True,
                    "postal_search_visible": True,
                    "postal_search_enabled": True,
                    "postal_candidate_count": 0,
                    "submit_present": True,
                    "submit_visible": True,
                    "submit_enabled": True,
                    "invalid_controls": [
                        {
                            "name": "postcode",
                            "type": "text",
                            "required": True,
                            "valid": False,
                            "value": "private-input-value",
                        }
                    ],
                    "validation_alert_count": 1,
                    "untrusted_customer_value": "private@example.test",
                }

        output = StringIO()
        with redirect_stderr(output):
            namespace["emit_customer_address_diagnostics"](
                FakeDriver(), "address_postcode_candidate"
            )
        rendered = output.getvalue()
        self.assertIn('"path": "/index.php"', rendered)
        self.assertIn('"substage": "address_postcode_candidate"', rendered)
        self.assertIn('"name": "postcode"', rendered)
        for private_value in ("private@example.test", "secret-reset-token", "private-input-value"):
            with self.subTest(private_value=private_value):
                self.assertNotIn(private_value, rendered)

    def test_address_edit_fixture_passes_saved_line_check_and_rejects_stale_line(self) -> None:
        tree = ast.parse(self.source)
        helper = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "assert_customer_address_line"
        )
        assignments = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id in {"address_line", "edited_address_line"}:
                    assignments[target.id] = node

        content = SimpleNamespace(text="")
        card = SimpleNamespace(
            get_attribute=lambda name: "42",
            find_element=lambda *args: content,
        )
        namespace = {
            "wait_for_customer_address_card": lambda *args: card,
            "By": SimpleNamespace(CSS_SELECTOR="css selector"),
            "webdriver": SimpleNamespace(Chrome=object),
        }
        exec(compile(ast.Module(body=[helper], type_ignores=[]), str(ACCOUNT_FLOW), "exec"), namespace)
        for label in ("desktop", "mobile"):
            with self.subTest(label=label):
                fixture = {"label": label}
                exec(compile(ast.Module(body=list(assignments.values()), type_ignores=[]), str(ACCOUNT_FLOW), "exec"), fixture)
                initial = fixture["address_line"]
                edited = fixture["edited_address_line"]
                content.text = f"ORDENOWA CI\n{edited}\n東京都 千代田区"
                namespace["assert_customer_address_line"](None, "CI", "42", edited, initial)
                content.text += f"\n{initial}"
                with self.assertRaisesRegex(AssertionError, "previous address line"):
                    namespace["assert_customer_address_line"](None, "CI", "42", edited, initial)
                content.text = initial
                with self.assertRaisesRegex(AssertionError, "saved address line"):
                    namespace["assert_customer_address_line"](None, "CI", "42", edited, initial)

    def test_email_login_and_logout_check_authenticated_and_signed_out_states(self) -> None:
        email_login = self.blocks["email_login"]
        self.assertIn("logout(", email_login)
        self.assertIn("login_url=login_url", email_login)
        self.assertIn('#login-form input[name="email"]', email_login)
        self.assertIn('get_attribute("type") != "email"', email_login)
        self.assertIn("driver.get(account_url)", email_login)
        self.assertIn("assert_my_page(driver, f\"CI-{label.title()}\")", email_login)

        for substage in ("logout", "login_form", "submit", "auth_result"):
            self.assertIn(f'email_login_substage = "{substage}"', email_login)
        self.assertIn("WebDriverWait(driver, 30).until(collect_email_login_result)", email_login)
        self.assertIn('login_result not in {"authenticated", "transitioned"}', email_login)
        self.assertIn("emit_email_login_diagnostics(", self.source)
        self.assertIn("email_login_account_route_classification", self.source)

        reset_request = self.blocks["password_reset_request"]
        self.assertIn("logout(driver, login_url=login_url)", reset_request)
        self.assertIn("reset_link_for(account_email, recovery_route_path)", reset_request)

        logout = self.source.split("def logout", 1)[1].split("def run_viewport", 1)[0]
        self.assertIn("visible_signout_link(driver)", logout)
        self.assertIn("driver.get(account_url)", logout)
        self.assertIn("driver.get(login_url)", logout)
        self.assertIn("return account_url", logout)
        self.assertIn('#login-form input[name="email"]', logout)
        self.assertIn('By.ID, "identity_main_link"', logout)
        self.assertIn('By.ID, "userMenuButton"', logout)

    def test_logout_navigates_to_authenticated_account_before_resolving_signout(self) -> None:
        logout = self.source.split("def logout", 1)[1].split("def run_viewport", 1)[0]
        self.assertIn("def wait_for_signed_out_state", self.source)
        helper = self.source.split("def wait_for_signed_out_state", 1)[1].split(
            "\n\ndef logout", 1
        )[0]

        account_route = logout.index("driver.get(account_url)")
        authenticated_page = logout.index('visible(driver, "#identity_main_link")')
        signout_lookup = logout.index("visible_signout_link(driver)")
        click_signout = logout.index("click_centered(driver, link)")
        wait_signed_out = logout.index("wait_for_signed_out_state(driver)")
        reopen_account = logout.index("driver.get(account_url)", account_route + 1)

        self.assertLess(account_route, authenticated_page)
        self.assertLess(authenticated_page, signout_lookup)
        self.assertLess(signout_lookup, click_signout)
        self.assertLess(click_signout, wait_signed_out)
        self.assertLess(wait_signed_out, reopen_account)
        login_route = logout.index("driver.get(login_url)", reopen_account)
        wait_login_form = logout.index("#login-form input[name=\"email\"]", login_route)
        self.assertLess(reopen_account, login_route)
        self.assertLess(login_route, wait_login_form)
        self.assertIn("WebDriverWait(driver, 30).until", helper)
        self.assertIn("document.getElementById('userMenuButton')", helper)
        self.assertIn("document.querySelectorAll('a.account-menu__link--signout')", helper)
        self.assertIn(
            "return !document.getElementById('userMenuButton') && !hasVisibleSignoutLink;",
            helper,
        )

    def test_native_account_page_logout_uses_centered_selenium_click(self) -> None:
        logout = self.source.split("def logout(", 1)[1].split("\n\ndef run_viewport", 1)[0]
        self.assertIn("click_centered(driver, link)", logout)

    def test_centered_click_interception_emits_bounded_blocker_and_reraises(self) -> None:
        click_helper = self.source.split("def click_centered(", 1)[1].split(
            "\n\ndef wait_for_registration_success", 1
        )[0]
        self.assertIn("except ElementClickInterceptedException:", click_helper)
        click_position = click_helper.index("element.click()")
        intercepted_position = click_helper.index("except ElementClickInterceptedException:", click_position)
        self.assertIn("emit_safe_click_blocker_summary(driver, element)", click_helper[intercepted_position:])
        self.assertIn("raise", click_helper[intercepted_position:])

        summary = self.source.split("def emit_safe_click_blocker_summary(", 1)[1].split(
            "\n\ndef click_centered", 1
        )[0]
        self.assertIn("ORDENOWA_CLICK_BLOCKER_SAFE_STATE", summary)
        self.assertIn("raw_tag.lower() in allowed_tags", summary)
        self.assertIn("token in allowed_classes", summary)
        self.assertIn('"id": ""', summary)
        self.assertNotIn("target.id", summary)
        for field in ("center_x", "center_y", "target_width", "target_height", "target_rect_count"):
            self.assertIn(field, summary)

    def test_click_blocker_summary_drops_arbitrary_dom_identity_and_keeps_safe_facts(self) -> None:
        helper = next(
            node
            for node in ast.parse(self.source).body
            if isinstance(node, ast.FunctionDef)
            and node.name == "emit_safe_click_blocker_summary"
        )
        class Browser:
            def execute_script(self, _script: str, _element: object) -> dict[str, object]:
                return {
                    "tag": "DIV",
                    "id": "qa-customer-jane@example.invalid",
                    "class_tokens": ["modal-backdrop", "qa-customer-jane@example.invalid", "unknown"],
                    "target_found": True,
                    "target_is_element_or_child": False,
                    "center_x": 423.4,
                    "center_y": 311.7,
                    "target_width": 390,
                    "target_height": 844,
                    "target_rect_count": 1,
                }

        import math

        namespace = {"json": json, "math": math, "sys": sys}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), str(ACCOUNT_FLOW), "exec"), namespace)
        output = StringIO()
        with redirect_stderr(output):
            namespace["emit_safe_click_blocker_summary"](Browser(), object())
        emitted = output.getvalue()
        marker = "ORDENOWA_CLICK_BLOCKER_SAFE_STATE="
        payload = emitted.split(marker, 1)[1].splitlines()[0]
        summary = json.loads(payload)

        self.assertEqual(summary["tag"], "div")
        self.assertEqual(summary["id"], "")
        self.assertEqual(summary["class_tokens"], ["modal-backdrop"])
        self.assertTrue(summary["target_found"])
        self.assertFalse(summary["target_is_element_or_child"])
        self.assertEqual(summary["center_x"], 423)
        self.assertEqual(summary["center_y"], 312)
        self.assertEqual(summary["target_width"], 390)
        self.assertEqual(summary["target_height"], 844)
        self.assertEqual(summary["target_rect_count"], 1)
        self.assertNotIn("qa-customer", emitted)

    def test_logout_compares_the_network_destination_before_protected_route_checks(self) -> None:
        logout = self.source.split("def logout(", 1)[1].split("\n\ndef run_viewport", 1)[0]
        self.assertIn(
            'driver.execute_cdp_cmd("Network.setBypassServiceWorker", {"bypass": True})',
            logout,
        )
        self.assertIn("clear_document_navigation_events(driver)", logout)
        self.assertIn("document_navigation_events(", logout)
        self.assertIn("safe_generated_route_match(driver.current_url, login_url)", logout)
        navigation_events = self.source.split("def document_navigation_events", 1)[1].split(
            "\n\ndef safe_registration_path", 1
        )[0]
        self.assertIn('"from_service_worker"', navigation_events)
        bypass = logout.index(
            'driver.execute_cdp_cmd("Network.setBypassServiceWorker", {"bypass": True})'
        )
        clear_trace = logout.index("clear_document_navigation_events(driver)")
        click_signout = logout.index("click_centered(driver, link)")
        capture_trace = logout.index("document_navigation_events(", click_signout)
        final_status = logout.index("status_code", capture_trace)
        login_route = logout.index("safe_generated_route_match(driver.current_url, login_url)")
        login_form = logout.index('#login-form input[name="email"]', login_route)
        restore_bypass = logout.index(
            'driver.execute_cdp_cmd("Network.setBypassServiceWorker", {"bypass": False})',
            login_form,
        )
        reopen_account = logout.index("driver.get(account_url)", restore_bypass)

        self.assertLess(bypass, clear_trace)
        self.assertLess(clear_trace, click_signout)
        self.assertLess(click_signout, capture_trace)
        self.assertLess(capture_trace, final_status)
        self.assertLess(final_status, login_route)
        self.assertLess(login_route, login_form)
        self.assertLess(login_form, restore_bypass)
        self.assertLess(restore_bypass, reopen_account)

    def test_network_logout_trace_matches_selected_link_and_preserves_safe_redirect_evidence(self) -> None:
        self.assertIn('"mylogout"', self.source.split("def safe_url_metadata", 1)[1].split("\n\ndef safe_generated_route_match", 1)[0])
        self.assertIn("def safe_same_shop_request_match(", self.source)
        self.assertIn("def safe_redirect_location_diagnostics(", self.source)
        self.assertIn("def safe_selected_signout_metadata(", self.source)
        events = self.source.split("def document_navigation_events", 1)[1].split("\n\ndef safe_registration_path", 1)[0]
        self.assertIn('"navigation_referrer_metadata"', events)
        self.assertIn('"selected_link_matches_request"', events)
        self.assertIn('"location_target_metadata"', events)
        self.assertIn('"location_matches_next_request"', events)
        self.assertIn('"location_matches_expected_login"', events)
        summary = self.source.split("def safe_registration_navigation_summary", 1)[1].split("\n\ndef safe_refresh_header_metadata", 1)[0]
        self.assertIn('"selected_link_matches_request"', summary)
        self.assertIn('"navigation_referrer"', summary)
        self.assertIn('"location_target"', summary)
        self.assertIn('"location_matches_next_request"', summary)
        self.assertIn('"location_matches_expected_login"', summary)
        logout = self.source.split("def logout(", 1)[1].split("\n\ndef run_viewport", 1)[0]
        self.assertIn('initial_logout_event.get("route_metadata")', logout)
        self.assertIn("initial_route_metadata.get(", logout)
        self.assertIn('"query_key_names"', logout)
        self.assertNotIn(
            'initial_logout_event.get("route", {}).get("query_keys", [])',
            logout,
        )
        self.assertIn("ORDENOWA_NORMAL_BROWSER_LOGOUT_SAFE_TRACE=", logout)
        self.assertIn("::notice title=ORDENOWA network-only customer logout::", logout)
        self.assertIn("safe_logout_trace", logout)

    def test_logout_reports_service_worker_bypass_restore_failure(self) -> None:
        logout = self.source.split("def logout(", 1)[1].split("\n\ndef run_viewport", 1)[0]
        restore_block = logout.split("    finally:", 1)[1]
        self.assertIn("primary_error = sys.exc_info()[1]", restore_block)
        self.assertIn("if primary_error is None:", restore_block)
        self.assertIn("ORDENOWA_SERVICE_WORKER_RESTORE_FAILURE=", restore_block)
        self.assertIn("add_note = getattr(primary_error, \"add_note\", None)", restore_block)
        self.assertNotIn("if sys.exc_info()[0] is None:", restore_block)

    def test_safe_native_logout_redirect_evidence_matches_without_exposing_query_values(self) -> None:
        tree = ast.parse(self.source)
        names = {
            "safe_same_origin_path",
            "safe_controller_category",
            "safe_url_metadata",
            "safe_generated_route_match",
            "safe_same_shop_request_match",
            "_header_value",
            "safe_redirect_location_diagnostics",
        }
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names
        ]
        namespace = {
            "BASE": "https://shop.example.test",
            "re": re,
            "parse_qs": parse_qs,
            "parse_qsl": parse_qsl,
            "unquote": unquote,
            "urljoin": urljoin,
            "urlparse": urlparse,
        }
        exec(
            compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )
        same_request = namespace["safe_same_shop_request_match"]
        self.assertTrue(
            same_request(
                "https://shop.example.test/ko/?mylogout&token=secret",
                "https://shop.example.test/ko/?token=secret&mylogout=",
            )
        )
        self.assertFalse(
            same_request(
                "https://shop.example.test/ko/?mylogout",
                "https://shop.example.test/ko/?controller=authentication",
            )
        )
        diagnostics = namespace["safe_redirect_location_diagnostics"](
            "https://shop.example.test/ko/?mylogout",
            {"Location": "/ko/authentication?back=my-account&token=secret"},
            "https://shop.example.test/ko/authentication?token=secret&back=my-account",
            "https://shop.example.test/ko/authentication",
        )
        self.assertTrue(diagnostics["location_matches_next_request"])
        self.assertTrue(diagnostics["location_matches_expected_login"])
        self.assertEqual("/ko/authentication", diagnostics["location_target_metadata"]["path"])
        self.assertNotIn("secret", repr(diagnostics))

    def test_native_signout_selection_accepts_mobile_account_page_link_without_desktop_id(self) -> None:
        tree = ast.parse(self.source)
        names = {
            "safe_same_origin_path",
            "safe_controller_category",
            "safe_url_metadata",
            "safe_selected_signout_metadata",
        }
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names
        ]
        namespace = {
            "BASE": "https://shop.example.test",
            "parse_qs": parse_qs,
            "re": re,
            "unquote": unquote,
            "urljoin": urljoin,
            "urlparse": urlparse,
        }
        exec(
            compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )

        class SignoutLink:
            def __init__(self, element_id: str | None) -> None:
                self.attributes = {
                    "id": element_id,
                    "class": "account-menu__link account-menu__link--signout",
                    "href": "https://shop.example.test/ko/?mylogout&token=private-token",
                }

            def get_attribute(self, name: str) -> str | None:
                return self.attributes.get(name)

        describe = namespace["safe_selected_signout_metadata"]
        mobile = describe(SignoutLink(None), "https://shop.example.test/")
        desktop = describe(SignoutLink("signout_link"), "https://shop.example.test/")
        external = SignoutLink(None)
        external.attributes["href"] = "https://other.example.test/ko/?mylogout"
        external_metadata = describe(external, "https://shop.example.test/")

        self.assertTrue(mobile["native_signout_control"])
        self.assertEqual(mobile["element_id"], "other")
        self.assertTrue(desktop["native_signout_control"])
        self.assertEqual(desktop["element_id"], "signout_link")
        self.assertTrue(mobile["target"]["same_origin"])
        self.assertEqual(mobile["target"]["query_key_names"], ["mylogout"])
        self.assertNotIn("private-token", repr(mobile))
        self.assertFalse(external_metadata["target"]["same_origin"])

        logout = self.source.split("def logout(", 1)[1].split("\n\ndef run_viewport", 1)[0]
        self.assertIn('selected_signout.get("native_signout_control") is not True', logout)
        self.assertIn('selected_signout.get("target", {}).get("same_origin") is not True', logout)
        self.assertNotIn('selected_signout.get("element_id") != "signout_link"', logout)

    def test_logout_uses_generated_account_and_login_routes_for_signed_out_access(self) -> None:
        login_form = self.source.split("def assert_korean_email_login_form", 1)[1].split(
            "\n\ndef emit_korean_login_diagnostics", 1
        )[0]
        logout = self.source.split("def logout", 1)[1].split("def run_viewport", 1)[0]
        run_viewport = self.source.split("def run_viewport", 1)[1].split("\n\nif __name__", 1)[0]

        wait_signed_out = logout.index("wait_for_signed_out_state(driver)")
        signed_out_section = logout[wait_signed_out:]
        self.assertIn(
            "driver.get(account_url)",
            signed_out_section,
            "logout must revisit the generated protected account route after signout",
        )
        self.assertIn("return login_url", login_form)
        self.assertTrue(
            "login_url = assert_korean_email_login_form(driver, korean_login_state)" in run_viewport,
            "run_viewport must retain the validated generated login URL",
        )
        logout_header = self.source.split("def logout(", 1)[1].split(") -> str:", 1)[0]
        self.assertIn("login_url: str", logout_header)
        self.assertIn("my_account_link_from_header(driver, open_menu=False)", logout)
        run_viewport_node = next(
            node
            for node in ast.parse(self.source).body
            if isinstance(node, ast.FunctionDef) and node.name == "run_viewport"
        )
        logout_calls = [
            node
            for node in ast.walk(run_viewport_node)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "logout"
        ]
        self.assertEqual(len(logout_calls), 5)
        self.assertTrue(
            all(
                len(call.args) == 1
                and isinstance(call.args[0], ast.Name)
                and call.args[0].id == "driver"
                and any(keyword.arg == "login_url" for keyword in call.keywords)
                for call in logout_calls
            ),
            "logout calls must use the validated generated login URL",
        )

        click_signout = logout.index("click_centered(driver, link)")
        wait_signed_out = logout.index("wait_for_signed_out_state(driver)")
        reopen_account = logout.index("driver.get(account_url)", wait_signed_out)
        login_route = logout.index("driver.get(login_url)", reopen_account)
        wait_login_form = logout.index("#login-form input[name=\"email\"]", login_route)
        self.assertLess(click_signout, wait_signed_out)
        self.assertLess(wait_signed_out, reopen_account)
        self.assertLess(reopen_account, login_route)
        self.assertIn('"identity_main_link"', logout[reopen_account:login_route])

        for stage in ("email_login", "password_reset_request", "password_reset_old_password_rejected"):
            self.assertIn("login_url=login_url", self.blocks[stage])
        for stage in ("verify_protected_route_signed_out", "open_generated_login", "wait_login_form"):
            self.assertIn(f'"{stage}"', logout)

    def test_generated_login_helper_returns_only_its_validated_same_origin_url(self) -> None:
        helper = self.source.split("def assert_korean_email_login_form", 1)[1].split(
            "\n\ndef emit_korean_login_diagnostics", 1
        )[0]
        self.assertIn("login_location.hostname != base_location.hostname", helper)
        self.assertIn("return login_url", helper)
        self.assertIn("driver.get(account_url)", self.blocks["email_login"])
        self.assertIn("driver.get(account_url)", self.blocks["password_reset_login"])

    def test_generated_route_match_requires_same_shop_and_same_route(self) -> None:
        helper_node = next(
            node
            for node in ast.parse(self.source).body
            if isinstance(node, ast.FunctionDef) and node.name == "safe_generated_route_match"
        )
        namespace = {
            "BASE": "https://shop.example.test/shop",
            "parse_qs": parse_qs,
            "unquote": unquote,
            "urlparse": urlparse,
        }
        exec(compile(ast.Module(body=[helper_node], type_ignores=[]), str(ACCOUNT_FLOW), "exec"), namespace)
        matches = namespace["safe_generated_route_match"]
        self.assertTrue(
            matches(
                "https://shop.example.test/shop/ko/register?back=%2Fko",
                "https://shop.example.test/shop/ko/register?back=%2Fko%2Fmy-page",
            )
        )
        self.assertFalse(
            matches(
                "https://attacker.example.test/shop/ko/register",
                "https://shop.example.test/shop/ko/register",
            )
        )
        self.assertFalse(
            matches(
                "https://shop.example.test/shop/ko/login",
                "https://shop.example.test/shop/ko/register",
            )
        )

    def test_profile_return_matches_the_canonical_localized_account_route(self) -> None:
        helper_node = next(
            node
            for node in ast.parse(self.source).body
            if isinstance(node, ast.FunctionDef) and node.name == "safe_generated_route_match"
        )
        namespace = {
            "BASE": "https://shop.example.test/shop",
            "parse_qs": parse_qs,
            "unquote": unquote,
            "urlparse": urlparse,
        }
        exec(
            compile(ast.Module(body=[helper_node], type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )
        matches = namespace["safe_generated_route_match"]
        canonical_account_url = (
            "https://shop.example.test/shop/ko/%EB%82%B4-%EA%B3%84%EC%A0%95?back=%2Fko"
        )
        self.assertTrue(
            matches(
                "https://shop.example.test/shop/ko/%EB%82%B4-%EA%B3%84%EC%A0%95?back=%2Fko%2Fidentity",
                canonical_account_url,
            )
        )
        self.assertFalse(
            matches(
                "https://shop.example.test/shop/ko/%EB%82%B4-%EC%A0%95%EB%B3%B4",
                canonical_account_url,
            )
        )
        self.assertFalse(
            matches(
                "https://outside.example.test/shop/ko/%EB%82%B4-%EA%B3%84%EC%A0%95",
                canonical_account_url,
            )
        )

        profile_save = self.blocks["profile_update_persist_wait"]
        navigate_to_account = profile_save.index("driver.get(account_url)")
        self.assertIn(
            "safe_generated_route_match(driver.current_url, account_url)",
            profile_save,
            "profile return must match the route from the authenticated header",
        )
        route_check = profile_save.index(
            "safe_generated_route_match(driver.current_url, account_url)"
        )
        my_page_check = profile_save.index(
            "assert_my_page(driver, expected_first_name, substage_callback=mark_profile_update_substage)"
        )
        identity_reload = profile_save.index('driver.get(f"{BASE}/index.php?controller=identity")')
        self.assertLess(navigate_to_account, route_check)
        self.assertLess(route_check, my_page_check)
        self.assertLess(my_page_check, identity_reload)
        self.assertNotIn("safe_account_route_classification(driver.current_url)", profile_save)
        self.assertIn('#customer-form input[name="firstname"]', profile_save)

    def test_generated_route_match_distinguishes_language_but_ignores_back(self) -> None:
        helper_node = next(
            node
            for node in ast.parse(self.source).body
            if isinstance(node, ast.FunctionDef) and node.name == "safe_generated_route_match"
        )
        namespace = {
            "BASE": "https://shop.example.test/shop",
            "parse_qs": parse_qs,
            "unquote": unquote,
            "urlparse": urlparse,
        }
        exec(compile(ast.Module(body=[helper_node], type_ignores=[]), str(ACCOUNT_FLOW), "exec"), namespace)
        matches = namespace["safe_generated_route_match"]

        for language_key, expected_language, other_language in (
            ("id_lang", "2", "1"),
            ("isolang", "ko", "ja"),
            ("lang", "ko", "ja"),
        ):
            with self.subTest(language_key=language_key):
                self.assertTrue(
                    matches(
                        f"https://shop.example.test/shop/ko/register?{language_key}={expected_language}&back=%2Fja",
                        f"https://shop.example.test/shop/ko/register?{language_key}={expected_language}&back=%2Fko",
                    )
                )
                self.assertFalse(
                    matches(
                        f"https://shop.example.test/shop/ko/register?{language_key}={other_language}&back=%2Fko",
                        f"https://shop.example.test/shop/ko/register?{language_key}={expected_language}&back=%2Fko",
                    )
                )

    def test_registration_form_requires_korean_document_language_after_navigation(self) -> None:
        registration_form = self.blocks["registration_form_load"]
        self.assertIn('get_attribute("lang")', registration_form)
        self.assertIn('startswith("ko")', registration_form)
        emitter = self.source.split("def emit_registration_diagnostics", 1)[1].split(
            "\n\ndef collect_profile_update_diagnostics", 1
        )[0]
        self.assertIn('"registration_document_language"', emitter)

    def test_logout_diagnostics_report_only_safe_stages_and_route_markers(self) -> None:
        logout = self.source.split("def logout", 1)[1].split("def run_viewport", 1)[0]
        collector = self.source.split("def collect_email_login_diagnostics", 1)[1].split(
            "\n\ndef emit_email_login_diagnostics", 1
        )[0]

        stages = (
            "resolve_account_link",
            "open_account",
            "wait_authenticated",
            "resolve_signout_link",
            "click_signout",
            "wait_signed_out",
            "reopen_account",
            "verify_protected_route_signed_out",
            "open_generated_login",
            "wait_login_form",
        )
        for stage in stages:
            self.assertTrue(f'"{stage}"' in logout, f"missing logout diagnostic stage {stage}")

        checkpoint_operations = (
            ('mark_substage("resolve_account_link")', "my_account_link_from_header(driver, open_menu=False)"),
            ('mark_substage("open_account")', "driver.get(account_url)"),
            ('mark_substage("wait_authenticated")', 'visible(driver, "#identity_main_link")'),
            ('mark_substage("resolve_signout_link")', "visible_signout_link(driver)"),
            ('mark_substage("click_signout")', "click_centered(driver, link)"),
            ('mark_substage("wait_signed_out")', "wait_for_signed_out_state(driver)"),
            ('mark_substage("reopen_account")', "driver.get(account_url)"),
            ('mark_substage("verify_protected_route_signed_out")', "document.readyState"),
            ('mark_substage("open_generated_login")', "driver.get(login_url)"),
            ('mark_substage("wait_login_form")', "visible(driver, '#login-form input[name=\"email\"]')"),
        )
        previous_position = -1
        for checkpoint, operation in checkpoint_operations:
            checkpoint_position = logout.index(checkpoint)
            operation_position = logout.index(operation, checkpoint_position)
            self.assertGreater(checkpoint_position, previous_position)
            self.assertGreater(operation_position, checkpoint_position)
            previous_position = operation_position

        self.assertTrue(
            '"user_menu_button_present"' in collector,
            "email login diagnostics omit the safe userMenuButton presence flag",
        )
        self.assertTrue(
            '"account_route_classification"' in collector,
            "email login diagnostics omit sanitized account route classification",
        )
        self.assertTrue(
            "def safe_account_route_classification" in self.source,
            "account route classification helper is missing",
        )

        classifier = next(
            node
            for node in ast.parse(self.source).body
            if isinstance(node, ast.FunctionDef)
            and node.name == "safe_account_route_classification"
        )
        namespace = {
            "BASE": "https://shop.example.test/shop",
            "parse_qs": parse_qs,
            "unquote": unquote,
            "urlparse": urlparse,
        }
        exec(
            compile(ast.Module(body=[classifier], type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )
        classify = namespace["safe_account_route_classification"]
        self.assertEqual(classify("https://shop.example.test/shop/"), "root")
        self.assertEqual(
            classify("https://shop.example.test/shop/?controller=my-account"),
            "account",
        )
        self.assertEqual(classify("https://shop.example.test/shop/identity"), "identity")
        self.assertEqual(
            classify("https://shop.example.test/shop/customers/secret-name"),
            "other",
        )
        self.assertEqual(
            classify("https://evil.example.test/shop/customers/secret-name"),
            "outside_shop",
        )

    def test_my_account_link_skips_identity_links_in_responsive_menu_candidates(self) -> None:
        module = ast.parse(self.source)
        helper_names = {"my_account_link_from_header", "safe_account_route_classification"}
        functions = [
            node for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name in helper_names
        ]
        namespace = {
            "BASE": "https://shop.example.test/shop",
            "By": SimpleNamespace(CSS_SELECTOR="css selector"),
            "parse_qs": parse_qs,
            "urljoin": urljoin,
            "unquote": unquote,
            "urlparse": urlparse,
        }
        exec(
            compile(ast.Module(body=functions, type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )

        class Link:
            def __init__(self, href: str) -> None:
                self.href = href

            def get_attribute(self, name: str) -> str | None:
                return self.href if name == "href" else None

            def is_displayed(self) -> bool:
                return True

            def is_enabled(self) -> bool:
                return True

        identity_link = Link("https://shop.example.test/shop/identity")
        account_link = Link("https://shop.example.test/shop/my-account")

        class Driver:
            current_url = "https://shop.example.test/shop/identity"

            def find_elements(self, by: str, selector: str) -> list[Link]:
                return [identity_link, account_link]

            def find_element(self, by: str, selector: str) -> Link:
                return identity_link

        selected_link, account_url = namespace["my_account_link_from_header"](
            Driver(), open_menu=False
        )

        self.assertIs(selected_link, account_link)
        self.assertEqual(account_url, "https://shop.example.test/shop/my-account")

    def test_my_account_link_accepts_the_first_menu_link_for_a_localized_account_slug(self) -> None:
        module = ast.parse(self.source)
        helper_names = {"my_account_link_from_header", "safe_account_route_classification"}
        functions = [
            node for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name in helper_names
        ]
        namespace = {
            "BASE": "https://shop.example.test/shop",
            "By": SimpleNamespace(CSS_SELECTOR="css selector"),
            "parse_qs": parse_qs,
            "urljoin": urljoin,
            "unquote": unquote,
            "urlparse": urlparse,
        }
        exec(
            compile(ast.Module(body=functions, type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )

        class Link:
            def __init__(self, href: str) -> None:
                self.href = href

            def get_attribute(self, name: str) -> str | None:
                return self.href if name == "href" else None

            def is_displayed(self) -> bool:
                return True

            def is_enabled(self) -> bool:
                return True

        localized_account_link = Link(
            "https://shop.example.test/shop/ko/%EB%82%B4-%EA%B3%84%EC%A0%95"
        )
        identity_link = Link("https://shop.example.test/shop/identity")

        class Driver:
            current_url = "https://shop.example.test/shop/ko/"

            def find_elements(self, by: str, selector: str) -> list[Link]:
                return [localized_account_link, identity_link]

            def find_element(self, by: str, selector: str) -> Link:
                return identity_link

        self.assertEqual(
            namespace["safe_account_route_classification"](localized_account_link.href),
            "other",
        )
        selected_link, account_url = namespace["my_account_link_from_header"](
            Driver(), open_menu=False
        )

        self.assertIs(selected_link, localized_account_link)
        self.assertEqual(
            account_url,
            "https://shop.example.test/shop/ko/%EB%82%B4-%EA%B3%84%EC%A0%95",
        )

    def test_visible_menu_uses_enabled_localized_first_account_link(self) -> None:
        module = ast.parse(self.source)
        helper_names = {"my_account_link_from_header", "safe_account_route_classification"}
        functions = [
            node for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name in helper_names
        ]
        namespace = {
            "BASE": "https://shop.example.test/shop",
            "By": SimpleNamespace(CSS_SELECTOR="css selector"),
            "parse_qs": parse_qs,
            "unquote": unquote,
            "urljoin": urljoin,
            "urlparse": urlparse,
        }

        state = {"menu_open": False, "clicks": 0}

        class Button:
            def get_attribute(self, name: str) -> str | None:
                if name == "aria-expanded":
                    return "true" if state["menu_open"] else "false"
                return None

        button = Button()

        class Link:
            def __init__(self, href: str, *, displayed: bool, enabled: bool) -> None:
                self.href = href
                self.displayed = displayed
                self.enabled = enabled

            def get_attribute(self, name: str) -> str | None:
                return self.href if name == "href" else None

            def is_displayed(self) -> bool:
                return self.displayed

            def is_enabled(self) -> bool:
                return self.enabled

        localized_account_link = Link(
            "https://shop.example.test/shop/ko/%EB%82%B4-%EA%B3%84%EC%A0%95",
            displayed=True,
            enabled=True,
        )
        identity_link = Link(
            "https://shop.example.test/shop/identity", displayed=True, enabled=True
        )

        class Driver:
            current_url = "https://shop.example.test/shop/ko/"

            def find_elements(self, by: str, selector: str) -> list[Link]:
                return [localized_account_link, identity_link]

        class ImmediateWait:
            def __init__(self, browser: Driver, _timeout: int) -> None:
                self.browser = browser

            def until(self, predicate, **_kwargs: object):
                return predicate(self.browser)

        def visible(_driver: Driver, selector: str):
            if selector != "#userMenuButton":
                raise AssertionError("the account header button must be opened first")
            return button

        def click_centered(_driver: Driver, element: Button) -> None:
            if element is not button:
                raise AssertionError("the account header button must be the menu click target")
            state["menu_open"] = True
            state["clicks"] += 1

        namespace.update(
            {
                "WebDriverWait": ImmediateWait,
                "visible": visible,
                "click_centered": click_centered,
            }
        )
        exec(
            compile(ast.Module(body=functions, type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )

        selected_link, account_url = namespace["my_account_link_from_header"](
            Driver(), open_menu=True
        )

        self.assertIs(selected_link, localized_account_link)
        self.assertEqual(account_url, localized_account_link.href)
        self.assertEqual(state, {"menu_open": True, "clicks": 1})

    def test_visible_menu_rejects_hidden_or_disabled_localized_fallback(self) -> None:
        module = ast.parse(self.source)
        helper_names = {"my_account_link_from_header", "safe_account_route_classification"}
        functions = [
            node for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name in helper_names
        ]
        namespace = {
            "BASE": "https://shop.example.test/shop",
            "By": SimpleNamespace(CSS_SELECTOR="css selector"),
            "parse_qs": parse_qs,
            "unquote": unquote,
            "urljoin": urljoin,
            "urlparse": urlparse,
        }

        class Button:
            def get_attribute(self, name: str) -> str | None:
                return "false" if name == "aria-expanded" else None

        class Link:
            def __init__(self, href: str, *, displayed: bool, enabled: bool) -> None:
                self.href = href
                self.displayed = displayed
                self.enabled = enabled

            def get_attribute(self, name: str) -> str | None:
                return self.href if name == "href" else None

            def is_displayed(self) -> bool:
                return self.displayed

            def is_enabled(self) -> bool:
                return self.enabled

        class Driver:
            current_url = "https://shop.example.test/shop/ko/"

            def __init__(self, first_link: Link) -> None:
                self.links = [
                    first_link,
                    Link("https://shop.example.test/shop/identity", displayed=True, enabled=True),
                ]

            def find_elements(self, by: str, selector: str) -> list[Link]:
                return self.links

        class ImmediateWait:
            def __init__(self, browser: Driver, _timeout: int) -> None:
                self.browser = browser

            def until(self, predicate, **_kwargs: object):
                if not predicate(self.browser):
                    raise RuntimeError("visible authenticated account link timed out")

        def visible(_driver: Driver, _selector: str) -> Button:
            return Button()

        def click_centered(_driver: Driver, _element: Button) -> None:
            return None

        namespace.update(
            {
                "WebDriverWait": ImmediateWait,
                "visible": visible,
                "click_centered": click_centered,
            }
        )
        exec(
            compile(ast.Module(body=functions, type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )

        localized_href = "https://shop.example.test/shop/ko/%EB%82%B4-%EA%B3%84%EC%A0%95"
        for displayed, enabled in ((False, True), (True, False)):
            with self.subTest(displayed=displayed, enabled=enabled):
                driver = Driver(
                    Link(localized_href, displayed=displayed, enabled=enabled)
                )
                with self.assertRaisesRegex(
                    RuntimeError,
                    "visible authenticated account link timed out",
                ):
                    namespace["my_account_link_from_header"](driver, open_menu=True)

    def test_registration_account_menu_diagnostics_expose_only_bounded_route_classes(self) -> None:
        module = ast.parse(self.source)
        helper_names = {
            "collect_registration_account_menu_route_diagnostics",
            "safe_account_route_classification",
        }
        functions = [
            node for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name in helper_names
        ]
        namespace = {
            "BASE": "https://shop.example.test/shop",
            "By": SimpleNamespace(CSS_SELECTOR="css selector"),
            "parse_qs": parse_qs,
            "urljoin": urljoin,
            "unquote": unquote,
            "urlparse": urlparse,
        }
        exec(
            compile(ast.Module(body=functions, type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )

        class Link:
            def __init__(self, href: str) -> None:
                self.href = href

            def get_attribute(self, name: str) -> str | None:
                return self.href if name == "href" else None

        localized_href = "https://shop.example.test/shop/ko/%EB%82%B4-%EA%B3%84%EC%A0%95"
        links = [
            Link(localized_href),
            Link("https://shop.example.test/shop/identity"),
        ]

        class Driver:
            current_url = "https://shop.example.test/shop/ko/"

            def find_elements(self, by: str, selector: str) -> list[Link]:
                return links

        diagnostics = namespace["collect_registration_account_menu_route_diagnostics"](Driver())

        self.assertEqual(
            diagnostics,
            {
                "candidate_count": 2,
                "candidate_route_classes": ["other", "identity"],
                "first_candidate_route_class": "other",
            },
        )
        self.assertNotIn(localized_href, json.dumps(diagnostics))
        emitter = self.source.split("def emit_registration_diagnostics", 1)[1].split(
            "def emit_korean_login_diagnostics", 1
        )[0]
        self.assertIn("collect_registration_account_menu_route_diagnostics(driver)", emitter)
        self.assertIn('"account_menu_candidate_route_classes"', emitter)

    def test_my_account_link_fails_closed_when_no_account_route_is_available(self) -> None:
        module = ast.parse(self.source)
        helper_names = {"my_account_link_from_header", "safe_account_route_classification"}
        functions = [
            node for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name in helper_names
        ]
        namespace = {
            "BASE": "https://shop.example.test/shop",
            "By": SimpleNamespace(CSS_SELECTOR="css selector"),
            "parse_qs": parse_qs,
            "urljoin": urljoin,
            "unquote": unquote,
            "urlparse": urlparse,
        }
        exec(
            compile(ast.Module(body=functions, type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )

        class Link:
            def get_attribute(self, name: str) -> str | None:
                return "https://shop.example.test/shop/identity" if name == "href" else None

        class Driver:
            current_url = "https://shop.example.test/shop/identity"

            def find_elements(self, by: str, selector: str) -> list[Link]:
                return [Link()]

            def find_element(self, by: str, selector: str) -> Link:
                return Link()

        with self.assertRaisesRegex(
            AssertionError,
            "authenticated My Page link did not resolve to the account route",
        ):
            namespace["my_account_link_from_header"](Driver(), open_menu=False)

    def test_email_login_failure_diagnostics_expose_state_without_page_text_or_values(self) -> None:
        result_helper = self.source.split("def collect_email_login_result", 1)[1].split(
            "\n\ndef collect_email_login_diagnostics", 1
        )[0]
        collector = self.source.split("def collect_email_login_diagnostics", 1)[1].split(
            "\n\ndef emit_email_login_diagnostics", 1
        )[0]
        emitter = self.source.split("def emit_email_login_diagnostics", 1)[1].split(
            "\n\ndef logout", 1
        )[0]

        self.assertIn("return 'authenticated'", result_helper)
        self.assertIn("return 'rejected'", result_helper)
        for field in (
            '"substage"',
            '"path"',
            '"login_result"',
            '"login_result_error_type"',
            '"login_form_visible"',
            '"identity_link_visible"',
            '"signout_link_visible"',
            '"danger_alert_visible"',
            '"alert_classification"',
        ):
            self.assertIn(field, collector)
        self.assertNotIn("innerText", collector)
        self.assertNotIn("textContent", collector)
        self.assertNotIn(".value", collector)
        self.assertIn("ORDENOWA_ACCOUNT_EMAIL_LOGIN_SAFE_STATE=", emitter)

    def test_email_login_safe_state_emits_escaped_github_annotation(self) -> None:
        emitter = next(
            node
            for node in ast.parse(self.source).body
            if isinstance(node, ast.FunctionDef) and node.name == "emit_email_login_diagnostics"
        )

        class FakeJson:
            @staticmethod
            def dumps(_value: object, **_kwargs: object) -> str:
                return "safe%state\r\ncontinued"

        namespace = {
            "collect_email_login_diagnostics": lambda _driver, _substage, _route_classification: {},
            "json": FakeJson,
            "sys": sys,
            "webdriver": SimpleNamespace(Chrome=object),
        }
        exec(compile(ast.Module(body=[emitter], type_ignores=[]), str(ACCOUNT_FLOW), "exec"), namespace)

        output = StringIO()
        with redirect_stderr(output):
            namespace["emit_email_login_diagnostics"](object(), "logout")

        self.assertEqual(
            output.getvalue(),
            "ORDENOWA_ACCOUNT_EMAIL_LOGIN_SAFE_STATE=safe%state\r\ncontinued\n"
            "::error title=Customer account email login safe state::safe%25state%0D%0Acontinued\n",
        )

    def test_registration_link_wait_has_its_own_failure_stage_after_korean_check(self) -> None:
        korean_check = self.blocks["korean_email_login_label"]
        self.assertIn("assert_korean_email_login_form(driver, korean_login_state)", korean_check)
        self.assertNotIn('driver.get(f"{BASE}/index.php?controller=authentication")', korean_check)
        registration = self.blocks["registration_link_load"]
        self.assertNotIn("driver.get(", registration)
        self.assertIn('visible(driver, \'a[data-link-action="display-register-form"]\')', registration)
        self.assertIn('set_registration_control(failure_control, "display-register-form", "anchor")', registration)
        validation = self.blocks["registration_link_validation"]
        self.assertIn('registration_link.get_attribute("href")', validation)
        self.assertIn("registration_location.hostname != base_location.hostname", validation)
        click = self.blocks["registration_link_click"]
        self.assertIn("clear_document_navigation_events(driver)", click)
        self.assertIn('registration_state["center_unobstructed"] = click_centered(driver, registration_link)', click)
        self.assertIn("finally:", click)
        self.assertIn("document_navigation_events(driver)", click)
        self.assertIn("safe_generated_route_match(\n                registration_after_click_url, registration_url", click)

        emitter = self.source.split("def emit_registration_diagnostics", 1)[1].split(
            "\n\ndef collect_profile_update_diagnostics", 1
        )[0]
        self.assertIn("registration_center_unobstructed", emitter)
        self.assertIn("registration_target_route_metadata", emitter)
        self.assertIn("registration_navigation_events", emitter)
        self.assertNotIn('"registration_url":', emitter)
        self.assertNotIn('"href":', emitter)

    def test_registration_click_probe_is_armed_before_click_and_reported_safely(self) -> None:
        probe = self.blocks["registration_link_click"]
        arm = probe.index("arm_registration_link_click_probe(")
        click = probe.index("click_centered(driver, registration_link)")
        capture = probe.index("read_registration_link_click_probe(")
        self.assertLess(arm, click)
        self.assertLess(click, capture)

        emitter = self.source.split("def emit_registration_diagnostics", 1)[1].split(
            "\n\ndef collect_profile_update_diagnostics", 1
        )[0]
        probe_helper = self.source.split("def arm_registration_link_click_probe", 1)[1].split(
            "\n\ndef read_registration_link_click_probe", 1
        )[0]
        self.assertIn(
            "window.addEventListener('click', capture, {capture: true, once: true})",
            probe_helper,
        )
        self.assertIn("window.addEventListener('click', after, {once: true})", probe_helper)
        self.assertIn("default_prevented: null", probe_helper)
        self.assertIn(
            "current.default_prevented = bubbleEvent.defaultPrevented === true",
            probe_helper,
        )
        self.assertIn('"registration_click": safe_registration_click_metadata(', emitter)
        self.assertIn('"registration_target_route_matched"', emitter)
        self.assertIn('"registration_url_changed"', emitter)
        self.assertNotIn('"href":', emitter)
        self.assertNotIn('"url":', emitter)

    def test_registration_click_metadata_redacts_unallowlisted_target_classes(self) -> None:
        helper = next(
            node
            for node in ast.parse(self.source).body
            if isinstance(node, ast.FunctionDef)
            and node.name == "safe_registration_click_metadata"
        )
        namespace = {"re": re}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), str(ACCOUNT_FLOW), "exec"), namespace)
        metadata = namespace["safe_registration_click_metadata"](
            {
                "probe_armed": True,
                "event_fired": True,
                "trusted": True,
                "default_prevented": True,
                "target_tag": "SPAN",
                "target_classes": [
                    "btn",
                    "btn-outline-primary",
                    "private@example.invalid",
                    "customer-session-secret",
                ],
                "href": "http://localhost:18080/register?token=private-token-sentinel",
            }
        )

        self.assertEqual(
            {
                "probe_armed": True,
                "event_fired": True,
                "trusted": True,
                "default_prevented": True,
                "registration_link_hit": None,
                "target_tag": "span",
                "target_classes": ["btn", "btn-outline-primary"],
            },
            metadata,
        )
        self.assertNotIn("private@example.invalid", repr(metadata))
        self.assertNotIn("customer-session-secret", repr(metadata))
        self.assertNotIn("private-token-sentinel", repr(metadata))

    def test_registration_navigation_summary_discards_raw_urls_and_query_values(self) -> None:
        helper_node = next(
            node
            for node in ast.parse(self.source).body
            if isinstance(node, ast.FunctionDef)
            and node.name == "safe_registration_navigation_summary"
        )
        namespace: dict[str, object] = {}
        namespace["re"] = re
        exec(compile(ast.Module(body=[helper_node], type_ignores=[]), str(ACCOUNT_FLOW), "exec"), namespace)
        summary = namespace["safe_registration_navigation_summary"](
            [
                {
                    "event": "document_redirect",
                    "route_metadata": {
                        "same_origin": True,
                        "path": "/secret",
                        "controller_category": "other",
                        "back_present": True,
                        "url": "https://shop.invalid/secret?email=qa@example.invalid&token=abc",
                    },
                    "redirect_from_metadata": {
                        "same_origin": True,
                        "path": "/ko/login",
                        "controller_category": "authentication",
                        "url": "https://shop.invalid/private?password=secret",
                    },
                    "status_code": 200,
                    "redirect_status_code": 302,
                    "request_url": "https://shop.invalid/private?email=qa@example.invalid",
                }
            ]
        )
        serialized = repr(summary)
        self.assertIn("/<redacted>", serialized)
        self.assertIn("authentication", serialized)
        self.assertIn("302", serialized)
        for forbidden in ("shop.invalid", "qa@example.invalid", "abc", "secret", "request_url", "password"):
            self.assertNotIn(forbidden, serialized)

    def test_login_reuses_the_current_generated_route_without_direct_authentication_gets(self) -> None:
        self.assertNotIn('driver.get(f"{BASE}/index.php?controller=authentication")', self.source)
        self.assertNotIn('driver.get(f"{BASE}/index.php?controller=password")', self.source)
        for helper_name in ("submit_login", "assert_login_rejected"):
            helper = self.source.split(f"def {helper_name}", 1)[1].split("\n\ndef ", 1)[0]
            self.assertNotIn("driver.get(", helper)
            self.assertIn("fill(driver, '#login-form input[name=\"email\"]'", helper)
        submit_login = self.source.split("def submit_login", 1)[1].split("\n\ndef assert_login_rejected", 1)[0]
        self.assertIn("collect_email_login_result", submit_login)
        self.assertNotIn("identity_main_link", submit_login)
        self.assertIn('login_result == "rejected"', submit_login)
        login_result = self.source.split("def collect_email_login_result", 1)[1].split(
            "\n\ndef collect_email_login_diagnostics", 1
        )[0]
        self.assertIn("!isVisible(loginForm)", login_result)
        self.assertIn("return 'transitioned'", login_result)
        old_password = self.blocks["password_reset_old_password_rejected"]
        self.assertLess(
            old_password.index("assert_my_page(driver,"),
            old_password.index("logout(driver, login_url=login_url)"),
        )
        self.assertLess(
            old_password.index("logout(driver, login_url=login_url)"),
            old_password.index("assert_login_rejected(driver,"),
        )

    def test_reset_email_matching_uses_the_rendered_localized_password_route(self) -> None:
        helper_nodes = [
            node
            for node in ast.parse(self.source).body
            if isinstance(node, ast.FunctionDef) and node.name == "reset_link_matches_route"
        ]
        self.assertEqual(len(helper_nodes), 1)
        namespace = {
            "BASE": "https://shop.example.test",
            "parse_qs": parse_qs,
            "unquote": unquote,
            "urljoin": urljoin,
            "urlparse": urlparse,
        }
        exec(
            compile(ast.Module(body=helper_nodes, type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )
        matches = namespace["reset_link_matches_route"]

        self.assertTrue(
            matches(
                "https://shop.example.test/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0"
                "?token=secure-key&reset_token=reset-secret&id_customer=12",
                "/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0",
            )
        )
        self.assertFalse(
            matches(
                "https://shop.example.test/password-reset?token=secure-key&reset_token=reset-secret",
                "/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0",
            )
        )
        self.assertFalse(
            matches(
                "https://attacker.example.test/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0"
                "?reset_token=reset-secret",
                "/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0",
            )
        )
        self.assertFalse(
            matches(
                "https://shop.example.test/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0",
                "/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0",
            )
        )

    def test_route_path_assertion_accepts_the_generated_encoded_locale_path(self) -> None:
        helper_nodes = [
            node
            for node in ast.parse(self.source).body
            if isinstance(node, ast.FunctionDef) and node.name == "assert_route_path_matches"
        ]
        self.assertEqual(len(helper_nodes), 1)
        namespace = {
            "BASE": "https://shop.example.test",
            "unquote": unquote,
            "urljoin": urljoin,
            "urlparse": urlparse,
        }
        exec(
            compile(ast.Module(body=helper_nodes, type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )

        class FakeDriver:
            def __init__(self, current_url: str) -> None:
                self.current_url = current_url

        assert_route = namespace["assert_route_path_matches"]
        generated_path = "/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0"
        assert_route(
            FakeDriver("https://shop.example.test/비밀번호-찾기/"),
            generated_path,
            "password recovery",
        )
        with self.assertRaises(AssertionError):
            assert_route(
                FakeDriver("https://shop.example.test/password-reset"),
                generated_path,
                "password recovery",
            )
        with self.assertRaises(AssertionError):
            assert_route(
                FakeDriver("https://attacker.example.test/비밀번호-찾기"),
                generated_path,
                "password recovery",
            )

    def test_password_recovery_assertions_compare_against_the_generated_href_path(self) -> None:
        self.assertIn('recovery_route_path = urlparse(recovery_url).path', self.source)
        reset_request = self.blocks["password_reset_request"]
        self.assertIn('assert_route_path_matches(driver, recovery_route_path, "password recovery")', reset_request)
        self.assertIn("reset_link_for(account_email, recovery_route_path)", reset_request)
        reset = self.blocks["password_reset"]
        self.assertIn('assert_route_path_matches(driver, recovery_route_path, "password reset")', reset)
        self.assertNotIn('assert_canonical_static_route(driver, "password-reset")', self.source)

    def test_mailpit_reset_checks_captured_link_and_password_change_with_separate_logo_qa(self) -> None:
        reset_request = self.blocks["password_reset_request"]
        self.assertIn("reset_link_for(account_email, recovery_route_path)", reset_request)
        self.assertIn('visible(driver, "#login-form a[href]")', reset_request)
        self.assertIn('recovery_link.get_attribute("href")', reset_request)
        self.assertIn("recovery_location.hostname != base_location.hostname", reset_request)
        self.assertIn("click_centered(driver, recovery_link)", reset_request)
        self.assertIn('assert_route_path_matches(driver, recovery_route_path, "password recovery")', reset_request)
        self.assertNotIn('"cid:shop_logo"', reset_request)
        self.assertNotIn("ContentID", reset_request)
        self.assertNotIn("hashlib.sha256", reset_request)
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        self.assertLess(
            workflow.index("tests/e2e/verify_reset_email_brand_browser.py"),
            workflow.index("tests/e2e/verify_customer_account_browser.py"),
        )

        mailpit_helper = self.source.split("def reset_link_for", 1)[1].split("def visible", 1)[0]
        self.assertIn("/api/v1/messages?", mailpit_helper)
        self.assertIn("/api/v1/message/", mailpit_helper)
        route_matcher = self.source.split("def reset_link_matches_route", 1)[1].split("def reset_link_for", 1)[0]
        self.assertIn("same_shop_origin", route_matcher)
        self.assertIn("actual_path == expected_path", route_matcher)
        self.assertIn("has_reset_token", route_matcher)

        reset = self.blocks["password_reset"]
        self.assertIn("driver.get(reset_url)", reset)
        self.assertIn('assert_route_path_matches(driver, recovery_route_path, "password reset")', reset)
        self.assertIn('#field-password[name="passwd"]', reset)
        self.assertIn('#field-confirmation-passwd[name="confirmation"]', reset)

        old_password = self.blocks["password_reset_old_password_rejected"]
        self.assertIn("assert_login_rejected(driver, account_email, initial_password)", old_password)

        reset_login = self.blocks["password_reset_login"]
        self.assertIn("submit_login(driver, account_email, reset_password)", reset_login)
        self.assertIn("assert_my_page(driver, f\"CI-{label.title()}\")", reset_login)
        self.assertIn("login_url=login_url", reset_login)
        self.assertIn("substage_callback=mark_email_login_substage", reset_login)

    def test_password_reset_login_failure_emits_bounded_substage_diagnostics(self) -> None:
        reset_login = self.blocks["password_reset_login"]
        submit_marker = reset_login.index('email_login_substage = "password_reset_submit"')
        submit_call = reset_login.index("submit_login(driver, account_email, reset_password)")
        my_page_marker = reset_login.index('email_login_substage = "password_reset_my_page"')
        my_page_assertion = reset_login.index("assert_my_page(driver, f\"CI-{label.title()}\")")
        self.assertLess(submit_marker, submit_call)
        self.assertLess(submit_call, my_page_marker)
        self.assertLess(my_page_marker, my_page_assertion)

        run_viewport = self.source.split("def run_viewport", 1)[1].split("\n\nif __name__", 1)[0]
        exception_handler = run_viewport.split("except Exception as error:", 1)[1].split(
            "finally:", 1
        )[0]
        self.assertIn('stage in {"email_login", "password_reset_login"}', exception_handler)
        self.assertIn("emit_email_login_diagnostics(", exception_handler)
        self.assertIn(
            'if stage in {"email_login", "password_reset_login"} and email_login_substage',
            exception_handler,
        )

    def test_password_reset_login_reopens_a_clean_form_after_rejecting_old_password(self) -> None:
        reset_login = self.blocks["password_reset_login"]

        reopen_login = reset_login.index("driver.get(login_url)")
        wait_for_email_field = reset_login.index("visible(driver, '#login-form input[name=\"email\"]')")
        reject_stale_alert = reset_login.index("if any(")
        mark_submit = reset_login.index('email_login_substage = "password_reset_submit"')
        submit_new_password = reset_login.index("submit_login(driver, account_email, reset_password)")

        self.assertLess(reopen_login, wait_for_email_field)
        self.assertLess(wait_for_email_field, reject_stale_alert)
        self.assertLess(reject_stale_alert, mark_submit)
        self.assertLess(mark_submit, submit_new_password)
        self.assertIn("fresh customer login form retained a prior authentication error", reset_login)

    def test_browser_flow_runs_on_desktop_and_mobile_viewports(self) -> None:
        self.assertIn('(1440, 960, "desktop")', self.source)
        self.assertIn('(390, 844, "mobile")', self.source)

    def test_profile_update_accepts_both_required_disclosures_before_valid_submit(self) -> None:
        required_stages = (
            "profile_update_current_password",
            "profile_update_required_disclosures",
            "profile_update_submit",
        )
        positions = [self.stages.index(stage) for stage in required_stages]
        self.assertEqual(positions, sorted(positions))

        disclosure_stage = self.blocks["profile_update_required_disclosures"]
        self.assertIn("accept_profile_update_disclosures(driver)", disclosure_stage)
        self.assertIn("assert_native_form_valid(driver, profile_form", disclosure_stage)

        disclosure_helper = self.source.split("def accept_profile_update_disclosures", 1)[1].split(
            "def assert_native_form_valid", 1
        )[0]
        self.assertIn('("customer_privacy", "psgdpr")', disclosure_helper)
        self.assertNotIn('("customer_privacy", "psgdpr_consent_checkbox")', disclosure_helper)
        self.assertIn("checkbox.is_displayed()", disclosure_helper)
        self.assertIn("checkbox.is_enabled()", disclosure_helper)
        self.assertIn("if not checkbox.is_selected()", disclosure_helper)
        self.assertIn("checkbox.click()", disclosure_helper)
        self.assertIn("WebDriverWait(driver, 5, poll_frequency=0.1)", disclosure_helper)
        self.assertIn("lambda _browser: checkbox.is_selected()", disclosure_helper)
        self.assertIn("checkbox.send_keys(Keys.SPACE)", disclosure_helper)

    def test_profile_update_waits_for_saved_identity_state_before_account_navigation(self) -> None:
        profile_save = self.source.split('stage = "profile_update_submit"', 1)[1].split(
            'stage = "email_login"', 1
        )[0]
        submit = profile_save.index("click_centered(driver, submit_button)")
        self.assertIn("wait_for_profile_update_success(driver, expected_first_name)", profile_save)
        success_wait = profile_save.index("wait_for_profile_update_success(driver, expected_first_name)")
        account_navigation = profile_save.index("driver.get(account_url)")

        self.assertLess(submit, success_wait)
        self.assertLess(success_wait, account_navigation)
        self.assertIn('profile_substage = "profile_update_success_notification"', profile_save)
        self.assertIn('assert_canonical_static_route(driver, "identity")', profile_save)
        self.assertIn("assert_my_page(driver, expected_first_name", profile_save)

    def test_profile_update_success_requires_success_alert_and_persisted_name(self) -> None:
        module = ast.parse(self.source)
        classifier = next(
            (
                node for node in module.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "classify_profile_update_response_state"
            ),
            None,
        )
        self.assertIsNotNone(classifier, "profile update needs an explicit PRG success-state classifier")
        if classifier is None:
            return

        namespace: dict[str, object] = {}
        exec(
            compile(ast.Module(body=[classifier], type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )
        classify = namespace["classify_profile_update_response_state"]

        self.assertEqual(
            classify({
                "identity_form_visible": True,
                "success_alert_visible": True,
                "first_name_matches_expected": True,
                "current_password_filled": False,
                "customer_privacy_checked": False,
                "psgdpr_checked": False,
            }),
            "saved",
            "a successful PrestaShop PRG reload clears password/disclosure inputs; the persisted name and success alert prove save",
        )
        self.assertEqual(
            classify({
                "identity_form_visible": True,
                "success_alert_visible": True,
                "first_name_matches_expected": False,
                "error_alert_visible": False,
            }),
            "pending",
            "a success notice without the expected persisted name is not sufficient",
        )
        self.assertEqual(
            classify({
                "identity_form_visible": True,
                "success_alert_visible": False,
                "first_name_matches_expected": True,
                "error_alert_visible": True,
            }),
            "rejected",
            "a visible form error must fail instead of being treated as a saved profile",
        )
    def test_profile_update_failure_reports_an_allowlisted_inner_substage(self) -> None:
        module = ast.parse(self.source)
        constant = next(
            node
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "PROFILE_UPDATE_SUBSTAGES" for target in node.targets)
        )
        helper = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "safe_profile_update_substage"
        )
        namespace: dict[str, object] = {}
        exec(
            compile(ast.Module(body=[constant, helper], type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )
        sanitize = namespace["safe_profile_update_substage"]
        self.assertEqual(sanitize("account_page_signout_link"), "account_page_signout_link")
        self.assertEqual(sanitize("identity_name_persistence"), "identity_name_persistence")
        self.assertEqual(sanitize("password=must-not-appear"), "unknown")

        profile_update = self.source.split('stage = "profile_update_persist_wait"', 1)[1].split(
            'stage = "email_login"', 1
        )[0]
        for substage in (
            "account_page_navigation",
            "account_page_identity_link",
            "account_page_signout_link",
            "account_page_saved_name",
            "identity_page_navigation",
            "identity_name_persistence",
            "profile_screenshot",
        ):
            self.assertIn(f'"{substage}"', self.source)
        self.assertIn(
            "assert_my_page(driver, expected_first_name, substage_callback=mark_profile_update_substage)",
            profile_update,
        )

        emitter = self.source.split("def emit_profile_update_diagnostics", 1)[1].split(
            "def fill", 1
        )[0]
        self.assertIn('"substage": safe_profile_update_substage(substage)', emitter)
        run_viewport = self.source.split("def run_viewport", 1)[1].split("\n\nif __name__", 1)[0]
        failure = run_viewport.split("except Exception as error:", 1)[1].split("print(f\"FAIL:", 1)[0]
        self.assertIn("profile_substage", failure)
        self.assertIn("safe_profile_update_substage(profile_substage)", failure)

        label_interaction = self.source.split("def click_required_checkbox_label", 1)[1].split(
            "def prepare_required_registration_fields", 1
        )[0]
        self.assertIn('form.find_elements(By.CSS_SELECTOR, "label[for]")', label_interaction)
        self.assertIn("candidate.get_attribute(\"for\") == checkbox_id", label_interaction)
        self.assertIn("label.click()", label_interaction)
        self.assertIn("checkbox.send_keys(Keys.SPACE)", label_interaction)

        customer_field_template = (
            ROOT / "themes" / "hummingbird" / "templates" / "_partials" / "form-fields.tpl"
        ).read_text(encoding="utf-8")
        self.assertIn('name="{$field.name}"', customer_field_template)
        self.assertIn('for="{$id_prefix}field-{$field.name}"', customer_field_template)
        psgdpr_template = (
            ROOT
            / "themes"
            / "hummingbird"
            / "modules"
            / "psgdpr"
            / "views"
            / "templates"
            / "hook"
            / "displayGDPRConsent.tpl"
        ).read_text(encoding="utf-8")
        self.assertIn('name="psgdpr_consent_checkbox"', psgdpr_template)
        self.assertIn('for="psgdpr_consent_checkbox_{$psgdpr_id_module|escape:', psgdpr_template)

        validity_helper = self.source.split("def assert_native_form_valid", 1)[1].split(
            "def submit_login", 1
        )[0]
        self.assertIn('find_elements(By.CSS_SELECTOR, ":invalid")', validity_helper)
        self.assertIn("arguments[0].checkValidity()", validity_helper)

        submit_stage = self.blocks["profile_update_submit"]
        self.assertIn("click_centered(driver, submit_button)", submit_stage)


if __name__ == "__main__":
    unittest.main()
