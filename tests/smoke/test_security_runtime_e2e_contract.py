"""Contract checks for the isolated admin and native password-reset security flows."""

import ast
from contextlib import redirect_stderr
from io import StringIO
import ipaddress
import os
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[2]
ADMIN_FLOW = ROOT / "tests" / "e2e" / "verify_admin_security_browser.py"
RESET_FLOW = ROOT / "tests" / "e2e" / "verify_customer_reset_token_browser.py"
FIXTURE = ROOT / "tests" / "business_profile" / "seed_security_fixtures.php"


def load_function(path: Path, function_name: str, namespace: dict[str, object]):
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    function = next(
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    isolated_module = ast.Module(body=[function], type_ignores=[])
    exec(compile(isolated_module, str(path), "exec"), namespace)
    return namespace[function_name]


class SecurityRuntimeE2EContractTests(unittest.TestCase):
    def test_view_only_settings_route_uses_the_employee_current_same_origin_tokenized_page(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        self.assertIn("def current_profile_settings_url(", source)
        self.assertIn("$employee->default_tab = (int) Tab::getIdFromClassName('AdminBusinessProfile');", FIXTURE.read_text(encoding="utf-8"))

        namespace: dict[str, object] = {
            "parse_qs": parse_qs,
            "urlparse": urlparse,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
            "webdriver": type("Webdriver", (), {"Chrome": object}),
        }
        route_from_current_employee = load_function(
            ADMIN_FLOW,
            "current_profile_settings_url",
            namespace,
        )

        class Driver:
            current_url = (
                "http://localhost:18080/admin-kuranea/index.php?"
                "controller=AdminBusinessProfile&token=view-only-session-token"
            )

        self.assertEqual(
            route_from_current_employee(Driver()),
            Driver.current_url,
        )
        for rejected_url in (
            "http://outside.example/admin-kuranea/index.php?controller=AdminBusinessProfile&token=secret",
            "http://localhost:18080/admin-kuranea-evil/index.php?controller=AdminBusinessProfile&token=secret",
            "http://localhost:18080/admin-kuranea/index.php?controller=AdminDashboard&token=secret",
            "http://localhost:18080/admin-kuranea/index.php?controller=AdminBusinessProfile",
        ):
            with self.subTest(rejected_url=rejected_url):
                Driver.current_url = rejected_url
                with self.assertRaises(AssertionError) as failure:
                    route_from_current_employee(Driver())
                self.assertNotIn("secret", str(failure.exception))
        run = source.split("def run()", 1)[1].split("\n\nif __name__", 1)[0]
        self.assertIn("current_profile_settings_url(restricted_driver)", run)
        self.assertNotIn("= settings_url(restricted_driver)", run)

    def test_view_only_post_login_state_reports_bounded_markers_without_urls_or_tokens(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        self.assertIn("def safe_admin_navigation_state(", source)
        namespace: dict[str, object] = {
            "parse_qs": parse_qs,
            "urlparse": urlparse,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
            "By": type("By", (), {"CSS_SELECTOR": "css selector"}),
            "webdriver": type("Webdriver", (), {"Chrome": object}),
        }
        load_function(ADMIN_FLOW, "_admin_controller_for_url", namespace)
        navigation_state = load_function(ADMIN_FLOW, "safe_admin_navigation_state", namespace)

        class Link:
            def __init__(self, href: str) -> None:
                self.href = href

            def get_attribute(self, name: str) -> str | None:
                return self.href if name == "href" else None

        class Driver:
            current_url = (
                "http://localhost:18080/admin-kuranea/index.php?"
                "controller=AdminBusinessProfile&token=private-route-token"
            )

            def find_elements(self, by: str, selector: str) -> list[Link]:
                if selector == "#login_form":
                    return []
                if selector == 'a[href*="controller=AdminBusinessProfile"]':
                    return [
                        Link(
                            "http://localhost:18080/admin-kuranea/index.php?"
                            "controller=AdminBusinessProfile&token=private-route-token"
                        )
                    ]
                if selector == 'a[href*="controller=AdminDashboard"]':
                    return [
                        Link(
                            "http://localhost:18080/admin-kuranea/index.php?"
                            "controller=AdminDashboard&token=private-dashboard-token"
                        )
                    ]
                return []

        state = navigation_state(Driver())
        self.assertEqual(
            state,
            {
                "login_form_visible": False,
                "current_controller": "AdminBusinessProfile",
                "business_profile_link_count": 1,
                "dashboard_link_count": 1,
            },
        )
        serialized = str(state)
        self.assertNotIn("private-route-token", serialized)
        self.assertNotIn("private-dashboard-token", serialized)
        self.assertNotIn("localhost", serialized)

    def test_admin_login_wait_retries_when_login_form_detaches_during_navigation(self):
        class StaleElementReferenceException(Exception):
            pass

        namespace: dict[str, object] = {
            "parse_qs": parse_qs,
            "urlparse": urlparse,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
            "By": type("By", (), {"CSS_SELECTOR": "css selector"}),
            "StaleElementReferenceException": StaleElementReferenceException,
            "safe_admin_navigation_state": lambda driver: {
                "business_profile_link_count": 1,
                "dashboard_link_count": 0,
            },
            "webdriver": type("Webdriver", (), {"Chrome": object}),
        }
        load_function(ADMIN_FLOW, "_admin_controller_for_url", namespace)
        wait_for_authenticated_route = load_function(
            ADMIN_FLOW,
            "_authenticated_admin_route_ready",
            namespace,
        )

        class StaleLoginForm:
            def is_displayed(self) -> bool:
                raise StaleElementReferenceException("detached during successful login navigation")

        class Driver:
            current_url = (
                "http://localhost:18080/admin-kuranea/index.php?"
                "controller=AdminBusinessProfile&token=private-session-token"
            )
            login_form_checks = 0

            def find_elements(self, by: str, selector: str) -> list[StaleLoginForm]:
                self.login_form_checks += 1
                if self.login_form_checks == 1:
                    return [StaleLoginForm()]
                return []

        driver = Driver()
        # A false result lets WebDriverWait poll again after the stale DOM probe.
        self.assertFalse(wait_for_authenticated_route(driver))
        self.assertTrue(wait_for_authenticated_route(driver))
        self.assertEqual(driver.login_form_checks, 2)

    def test_admin_login_accepts_authenticated_back_office_menu_on_nondefault_controller(self):
        class StaleElementReferenceException(Exception):
            pass

        namespace: dict[str, object] = {
            "parse_qs": parse_qs,
            "urlparse": urlparse,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
            "By": type("By", (), {"CSS_SELECTOR": "css selector"}),
            "StaleElementReferenceException": StaleElementReferenceException,
            "webdriver": type("Webdriver", (), {"Chrome": object}),
        }
        load_function(ADMIN_FLOW, "_admin_controller_for_url", namespace)
        safe_admin_navigation_state = load_function(
            ADMIN_FLOW,
            "safe_admin_navigation_state",
            namespace,
        )
        wait_for_authenticated_route = load_function(
            ADMIN_FLOW,
            "_authenticated_admin_route_ready",
            namespace,
        )

        class Element:
            def __init__(self, *, visible: bool = False, href: str | None = None) -> None:
                self.visible = visible
                self.href = href

            def is_displayed(self) -> bool:
                return self.visible

            def get_attribute(self, name: str) -> str | None:
                return self.href if name == "href" else None

        class Driver:
            current_url = (
                "http://localhost:18080/admin-kuranea/index.php?"
                "controller=AdminCatalog&token=private-session-token"
            )
            login_visible = False
            links_visible = True

            def find_elements(self, by: str, selector: str) -> list[Element]:
                if selector == "#login_form":
                    return [Element(visible=self.login_visible)]
                if not self.links_visible:
                    return []
                if selector == 'a[href*="controller=AdminBusinessProfile"]':
                    return [Element(href=(
                        "http://localhost:18080/admin-kuranea/index.php?"
                        "controller=AdminBusinessProfile&token=private-profile-token"
                    ))]
                if selector == 'a[href*="controller=AdminDashboard"]':
                    return [Element(href=(
                        "http://localhost:18080/admin-kuranea/index.php?"
                        "controller=AdminDashboard&token=private-dashboard-token"
                    ))]
                return []

        driver = Driver()
        self.assertTrue(wait_for_authenticated_route(driver))
        self.assertNotIn("private-session-token", str(safe_admin_navigation_state(driver)))
        self.assertNotIn("private-profile-token", str(safe_admin_navigation_state(driver)))

        driver.login_visible = True
        self.assertFalse(wait_for_authenticated_route(driver))
        driver.login_visible = False
        driver.current_url = "https://outside.invalid/admin-kuranea/index.php?controller=AdminCatalog"
        self.assertFalse(wait_for_authenticated_route(driver))
        driver.current_url = "http://localhost:18080/front-office/catalog"
        self.assertFalse(wait_for_authenticated_route(driver))
        driver.current_url = (
            "http://localhost:18080/admin-kuranea/index.php?"
            "controller=AdminLogin&token=private-session-token"
        )
        driver.links_visible = True
        self.assertFalse(wait_for_authenticated_route(driver))
        driver.current_url = (
            "http://localhost:18080/admin-kuranea/index.php?"
            "controller=AdminCatalog&token=private-session-token"
        )
        driver.links_visible = False
        self.assertFalse(wait_for_authenticated_route(driver))

    def test_admin_security_flow_covers_missing_invalid_and_view_only_requests(self):
        self.assertTrue(ADMIN_FLOW.is_file(), "the isolated admin security browser flow is missing")
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        for marker in (
            '"missing"',
            '"invalid"',
            '"view_only"',
            "submitOrdenowaSaveDraft",
            "profile[brand][name][ko-KR]",
            "assert_setting_unchanged",
            "current_draft_pointer",
            "assert_draft_pointer_unchanged",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        state_assertion = source.split("def assert_setting_unchanged(", 1)[1].split("\n\ndef ", 1)[0]
        self.assertIn(
            "assert_draft_pointer_unchanged(driver, expected_draft_pointer, label)",
            state_assertion,
        )
        guarded_attempt = source.split("def verify_security_attempt_without_mutation(", 1)[1].split("\n\ndef ", 1)[0]
        self.assertIn("assert_setting_unchanged(", guarded_attempt)
        self.assertIn("assert_security_attempt_rejected(response, mode)", guarded_attempt)
        run = source.split("def run()", 1)[1].split("\n\nif __name__", 1)[0]
        self.assertIn("verify_security_attempt_without_mutation(", run)
        for controller, screenshot_name in (
            ("AdminBusinessProfile", "profile"),
            ("AdminBusinessProfileBanks", "bank-accounts"),
            ("AdminOrdenowaProductManager", "product-manager"),
            ("AdminKuraneaCatalogReview", "catalog-review"),
        ):
            with self.subTest(controller=controller):
                self.assertIn(f'"{controller}"', run)
                self.assertIn(f"admin-security-legacy-{screenshot_name}-korean.png", run)
        route_helper = source.split("def generated_admin_controller_url(", 1)[1].split("\n\ndef ", 1)[0]
        self.assertIn("expected.hostname", route_helper)
        self.assertIn("employee-scoped admin token", route_helper)
        view_only = run.split('stage = "view_only_employee_post_login_state"', 1)[1]
        route_stages = (
            'stage = "view_only_employee_settings_route"',
            'stage = "view_only_employee_direct_route"',
            'stage = "view_only_employee_settings_form_visible"',
            'stage = "view_only_employee_settings_korean_label"',
            'stage = "view_only_employee_settings_document_locale"',
            'stage = "view_only_employee_settings_value"',
            'stage = "view_only_employee_draft_pointer"',
            'stage = "view_only_employee_valid_token_post"',
        )
        positions = [view_only.index(stage) for stage in route_stages]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("restricted_settings_url = current_profile_settings_url(restricted_driver)", view_only)
        self.assertNotIn("= settings_url(restricted_driver)", view_only)
        self.assertIn('emit_admin_post_login_state(restricted_driver, "view_only")', view_only)
        self.assertIn("restricted_driver.get(restricted_settings_url)", view_only)
        self.assertIn('visible(restricted_driver, "form.ordenowa-profile-settings")', view_only)

    def test_admin_security_flow_guards_exact_loopback_ci_target_before_browser_creation(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        for marker in (
            "def validate_isolated_ci_project",
            "def validate_loopback_admin_targets",
            "os.environ.get(\"CI\")",
            "os.environ.get(\"GITHUB_ACTIONS\")",
            "os.environ.get(\"KURANEA_ISOLATED_CI\")",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
            "CI_COMPOSE_PROJECT_NAME",
            "EXPECTED_SHOP_PORT = 18080",
            "ipaddress.ip_address(host).is_loopback",
            "ADMIN_MAIL",
            "@example.invalid",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        run = source.split("def run()", 1)[1].split("\n\nif __name__", 1)[0]
        self.assertLess(run.index("validate_isolated_ci_project()"), run.index("new_driver()"))
        self.assertLess(run.index("validate_loopback_admin_targets()"), run.index("new_driver()"))
        for screenshot in (
            "admin-security-view-only-settings-korean.png",
            "admin-security-view-only-dashboard-korean.png",
            "admin-security-view-only-orders-korean.png",
            "admin-security-legacy-profile-korean.png",
            "admin-security-legacy-bank-accounts-korean.png",
            "admin-security-legacy-product-manager-korean.png",
            "admin-security-legacy-catalog-review-korean.png",
        ):
            self.assertIn(screenshot, source)
        self.assertLess(run.index('assert_korean_admin_locale(restricted_driver, "view-only profile settings")'), run.index('admin-security-view-only-settings-korean.png'))

    def test_admin_security_browser_failure_emits_safe_stage_annotation(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        run = source.split("def run()", 1)[1].split("\n\nif __name__", 1)[0]
        handler = run.split("except Exception as error:", 1)[1].split("finally:", 1)[0]
        self.assertIn("::error title=ORDENOWA admin security browser QA::", handler)
        self.assertIn("{stage}", handler)
        self.assertIn("{error_type}", handler)
        self.assertIn("admin_security_substage", handler)
        self.assertIn("admin_security_response", handler)
        self.assertIn("admin_security_request", handler)
        self.assertIn("admin_security_state_recheck", handler)
        self.assertIn("admin_security_navigation_state", handler)
        self.assertIn("SAFE_ADMIN_NAVIGATION_STATE_PATTERN", handler)
        self.assertIn("substage={diagnostic_substage}", handler)
        self.assertIn("setting_value_mismatch", source)
        self.assertIn("draft_pointer_mismatch", source)
        self.assertIn("ORDENOWA_ADMIN_SECURITY_SUBSTAGE=", handler)
        self.assertIn("ORDENOWA_ADMIN_SECURITY_RESPONSE=", handler)
        self.assertNotIn("str(error)", handler)
        self.assertNotIn("{error}", handler)

    def test_view_only_orders_failure_captures_page_before_check_and_emits_bounded_diagnostic(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        self.assertIn("SAFE_ADMIN_ORDERS_STATE_PATTERN", source)
        self.assertIn("def safe_admin_orders_state(", source)
        self.assertIn("ORDENOWA_ADMIN_ORDERS_STATE=", source)

        run = source.split("def run()", 1)[1].split("\n\nif __name__", 1)[0]
        orders_stage = run.split('stage = "view_only_employee_orders_korean_locale"', 1)[1].split(
            'stage = "view_only_employee_settings_restore"', 1
        )[0]
        self.assertLess(
            orders_stage.index('save_screenshot(str(DEST / "admin-security-view-only-orders-korean.png"))'),
            orders_stage.index("if not orders_label_ready"),
        )
        self.assertIn("wait_for_korean_orders_label", orders_stage)
        self.assertIn("safe_admin_orders_state(restricted_driver)", orders_stage)
        wait_for_label = source.split("def wait_for_korean_orders_label(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('".header-toolbar h1.title"', wait_for_label)
        self.assertIn('".js-grid-panel .card-header-title"', wait_for_label)
        self.assertIn('".showcase-list-card__header"', wait_for_label)
        self.assertIn('"주문 관리"', wait_for_label)
        self.assertIn('"모든 주문"', wait_for_label)
        self.assertIn('re.search(r"\\border(s)?\\b", body_text, re.IGNORECASE)', wait_for_label)

        handler = run.split("except Exception as error:", 1)[1].split("finally:", 1)[0]
        self.assertIn("admin_security_orders_state", handler)
        self.assertIn("SAFE_ADMIN_ORDERS_STATE_PATTERN", handler)
        self.assertIn("ORDENOWA_ADMIN_ORDERS_STATE=", handler)

    def test_view_only_orders_diagnostic_contains_only_allowlisted_page_state(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        namespace: dict[str, object] = {
            "parse_qs": parse_qs,
            "urlparse": urlparse,
            "re": re,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
            "By": type("By", (), {"CSS_SELECTOR": "css selector", "TAG_NAME": "tag name"}),
            "is_korean_admin_language": lambda locale: locale.casefold() in {"ko", "ko-kr"},
            "webdriver": type("Webdriver", (), {"Chrome": object}),
        }
        load_function(ADMIN_FLOW, "_admin_controller_for_url", namespace)
        load_function(ADMIN_FLOW, "_diagnostic_bool", namespace)
        safe_state = load_function(ADMIN_FLOW, "safe_admin_orders_state", namespace)

        class Element:
            def __init__(self, text: str = "", lang: str | None = None) -> None:
                self.text = text
                self.lang = lang

            def get_attribute(self, name: str) -> str | None:
                return self.lang if name == "lang" else None

            def is_displayed(self) -> bool:
                return True

        class Driver:
            current_url = "http://localhost:18080/admin-kuranea/sell/orders"

            def find_element(self, by: str, selector: str) -> Element:
                if selector == "html":
                    return Element(lang="ko-KR")
                if selector == "body":
                    return Element("주문 고객 private@example.invalid")
                raise AssertionError(f"unexpected element selector: {selector}")

            def execute_script(self, script: str) -> dict[str, object]:
                return {"http_status": 200, "document_ready": "complete"}

            def find_elements(self, by: str, selector: str) -> list[Element]:
                if selector == "#login_form":
                    return []
                if selector == ".header-toolbar h1.title":
                    return [Element("주문")]
                if selector == ".js-grid-panel .card-header-title":
                    return [Element("주문 (0)")]
                if selector == "#main-div, #main-div .content-div":
                    return [Element()]
                if selector == "#main-div table.js-grid-table":
                    return [Element()]
                if selector == ".showcase-list-card":
                    return [Element()]
                if selector == ".showcase-list-card__header":
                    return [Element("주문 관리")]
                if selector == ".showcase-list-card__message":
                    return [Element("이 페이지에서 모든 주문을 확인하고 주문 상태도 변경할 수 있습니다.")]
                if selector == "[role='alert'], .alert-danger":
                    return []
                return []

        diagnostic = safe_state(Driver())
        self.assertEqual(
            diagnostic,
            "route=AdminOrders;orders_path=orders_list;http_status=200;document_ready=complete;"
            "document_locale=korean;login_form_visible=false;admin_shell_visible=true;"
            "body_text=present;orders_heading=korean;orders_grid_heading=korean;orders_grid_visible=true;"
            "orders_empty_state_visible=true;orders_empty_state_korean=true;"
            "permission_denied=false;english_order_label=false;alert_visible=false;"
            "body_has_korean_order_label=true",
        )
        pattern_assignment = next(
            node
            for node in ast.parse(source).body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "SAFE_ADMIN_ORDERS_STATE_PATTERN"
                for target in node.targets
            )
        )
        self.assertIsNotNone(re.fullmatch(ast.literal_eval(pattern_assignment.value), diagnostic))
        self.assertNotIn("private@example.invalid", diagnostic)

    def test_view_only_orders_diagnostic_matches_prestashop_92_markup(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        diagnostic_source = source.split("def safe_admin_orders_state(", 1)[1].split(
            "\ndef wait_for_korean_orders_label(", 1
        )[0]

        self.assertIn('".header-toolbar h1.title"', diagnostic_source)
        self.assertIn('"#main-div, #main-div .content-div"', diagnostic_source)
        self.assertIn('"#main-div table.js-grid-table"', diagnostic_source)
        self.assertNotIn('"main h1"', diagnostic_source)
        self.assertNotIn('"main, #content, #main, #main-content"', diagnostic_source)
        self.assertNotIn('"main table, main [role=\'grid\'], main .grid-table"', diagnostic_source)

        namespace: dict[str, object] = {
            "parse_qs": parse_qs,
            "urlparse": urlparse,
            "re": re,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
            "By": type("By", (), {"CSS_SELECTOR": "css selector", "TAG_NAME": "tag name"}),
            "is_korean_admin_language": lambda locale: locale.casefold() in {"ko", "ko-kr"},
            "webdriver": type("Webdriver", (), {"Chrome": object}),
        }
        load_function(ADMIN_FLOW, "_admin_controller_for_url", namespace)
        load_function(ADMIN_FLOW, "_diagnostic_bool", namespace)
        safe_state = load_function(ADMIN_FLOW, "safe_admin_orders_state", namespace)

        class Element:
            def __init__(self, text: str = "", lang: str | None = None) -> None:
                self.text = text
                self.lang = lang

            def get_attribute(self, name: str) -> str | None:
                return self.lang if name == "lang" else None

            def is_displayed(self) -> bool:
                return True

        class Driver:
            current_url = "http://localhost:18080/admin-kuranea/sell/orders"

            def find_element(self, by: str, selector: str) -> Element:
                if selector == "html":
                    return Element(lang="ko-KR")
                if selector == "body":
                    return Element("주문")
                raise AssertionError(f"unexpected element selector: {selector}")

            def execute_script(self, script: str) -> dict[str, object]:
                return {"http_status": 200, "document_ready": "complete"}

            def find_elements(self, by: str, selector: str) -> list[Element]:
                if selector == "#login_form":
                    return []
                if selector == ".header-toolbar h1.title":
                    return [Element("주문")]
                if selector == "#main-div, #main-div .content-div":
                    return [Element()]
                if selector == ".js-grid-panel .card-header-title":
                    return [Element("주문 (0)")]
                if selector == "#main-div table.js-grid-table":
                    return [Element()]
                if selector == ".showcase-list-card":
                    return [Element()]
                if selector == ".showcase-list-card__header":
                    return [Element("주문 관리")]
                if selector == ".showcase-list-card__message":
                    return [Element("모든 주문과 주문 상태를 확인할 수 있습니다.")]
                if selector == "[role='alert'], .alert-danger":
                    return []
                raise AssertionError(f"unexpected element selector: {selector}")

        diagnostic = safe_state(Driver())
        self.assertIn("orders_heading=korean", diagnostic)
        self.assertIn("admin_shell_visible=true", diagnostic)
        self.assertIn("orders_grid_visible=true", diagnostic)
        self.assertIn("english_order_label=false", diagnostic)
        self.assertIn("body_has_korean_order_label=true", diagnostic)

    def test_view_only_fixture_reads_back_native_admin_orders_view_permission(self):
        fixture = FIXTURE.read_text(encoding="utf-8")
        access_setup = fixture.split("$access = new Access();", 1)[1].split("$employee = new Employee();", 1)[0]
        self.assertIn("$ordersTabId = (int) Tab::getIdFromClassName('AdminOrders');", access_setup)
        self.assertIn("$ordersReadRole = sprintf(", access_setup)
        self.assertIn("Access::isGranted($ordersReadRole, (int) $profile->id)", access_setup)
        self.assertIn("$profileAccesses[$ordersTabId]['view'] ?? '0'", access_setup)
        self.assertIn("'AdminParentOrders'", access_setup)
        self.assertIn("$ordersParentTabId = (int) Tab::getIdFromClassName('AdminParentOrders');", access_setup)
        self.assertIn("$ordersParentReadRole = sprintf(", access_setup)
        self.assertIn("strtoupper('AdminParentOrders')", access_setup)
        self.assertIn("Access::isGranted($ordersParentReadRole, (int) $profile->id)", access_setup)
        self.assertIn("$profileAccesses[$ordersParentTabId]['view'] ?? '0'", access_setup)
        self.assertIn("'SELL'", access_setup)
        self.assertIn("$sellTabId = (int) Tab::getIdFromClassName('SELL');", access_setup)
        self.assertIn("$sellReadRole = sprintf(", access_setup)
        self.assertIn("strtoupper('SELL')", access_setup)
        self.assertIn("Access::isGranted($sellReadRole, (int) $profile->id)", access_setup)
        self.assertIn("$profileAccesses[$sellTabId]['view'] ?? '0'", access_setup)

    def test_view_only_employee_orders_link_accepts_only_same_origin_list_routes(self):
        namespace: dict[str, object] = {
            "urlparse": urlparse,
            "parse_qs": parse_qs,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
            "webdriver": type("Webdriver", (), {"Chrome": object}),
        }
        is_orders_list = load_function(ADMIN_FLOW, "is_admin_orders_list_url", namespace)
        for accepted in (
            "http://localhost:18080/admin-kuranea/sell/orders",
            "http://localhost:18080/admin-kuranea/sell/orders/",
            "http://localhost:18080/admin-kuranea/sell/orders?orderState=1",
            "http://localhost:18080/admin-kuranea/index.php?controller=AdminOrders&token=fixture",
        ):
            with self.subTest(url=accepted):
                self.assertTrue(is_orders_list(accepted))
        for rejected in (
            "http://localhost:18080/admin-kuranea/sell/orders/new",
            "http://localhost:18080/admin-kuranea/sell/orders/42/view",
            "http://localhost:18080/admin-kuranea/sell/orders/42/status",
            "http://localhost:18080/admin-kuranea/sell/orders-evil",
            "http://localhost:18080/admin-kuranea/index.php?controller=AdminOrders&action=add",
            "http://localhost:18080/admin-kuranea/index.php?controller=AdminOrders&vieworder&id_order=42&token=fixture",
            "http://localhost:18080/admin-kuranea/index.php?controller=AdminOrders&submitAction=deleteorder&id_order=42&token=fixture",
            "http://localhost:18080/admin-kuranea/index.php?controller=AdminOrders&token=fixture&unexpected=1",
            "http://localhost:18080/admin-kuranea/index.php?Controller=AdminOrders&token=fixture",
            "http://localhost:18080/admin-kuranea/index.php?controller=AdminOrders&Token=fixture",
            "http://outside.example/admin-kuranea/sell/orders",
            "http://localhost:18081/admin-kuranea/sell/orders",
            "http://localhost:18080/admin-kuranea-evil/sell/orders",
            "http://employee@localhost:18080/admin-kuranea/sell/orders",
        ):
            with self.subTest(url=rejected):
                self.assertFalse(is_orders_list(rejected))

        source = ADMIN_FLOW.read_text(encoding="utf-8")
        orders_stage = source.split('stage = "view_only_employee_orders_korean_locale"', 1)[1].split(
            'stage = "view_only_employee_settings_restore"', 1
        )[0]
        self.assertIn('for link in restricted_driver.find_elements(By.CSS_SELECTOR, "a[href]")', orders_stage)
        self.assertIn("is_admin_orders_list_url(link.get_attribute(\"href\") or \"\")", orders_stage)
        self.assertNotIn("_admin_controller_for_url(link.get_attribute(\"href\") or \"\")", orders_stage)

    def test_view_only_orders_link_failure_reports_only_bounded_route_counts(self):
        namespace: dict[str, object] = {
            "urlparse": urlparse,
            "parse_qs": parse_qs,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
            "By": type("By", (), {"CSS_SELECTOR": "a[href]"}),
            "webdriver": type("Webdriver", (), {"Chrome": object}),
        }
        load_function(ADMIN_FLOW, "is_admin_orders_list_url", namespace)
        self.assertIn("def safe_admin_orders_link_state(", ADMIN_FLOW.read_text(encoding="utf-8"))
        safe_link_state = load_function(ADMIN_FLOW, "safe_admin_orders_link_state", namespace)

        class Link:
            def __init__(self, href: str):
                self.href = href

            def get_attribute(self, name: str) -> str:
                return self.href

        class Driver:
            def find_elements(self, by: str, selector: str) -> list[Link]:
                self.selector = selector
                return [
                    Link("http://localhost:18080/admin-kuranea/sell/orders"),
                    Link("http://localhost:18080/admin-kuranea/sell/orders/new"),
                    Link("http://localhost:18080/admin-kuranea/sell/orders/42/view"),
                    Link("http://localhost:18080/admin-kuranea/sell/orders/42/cancellation"),
                    Link("http://localhost:18080/admin-kuranea/index.php?controller=AdminOrders&token=fixture"),
                    Link("http://localhost:18080/admin-kuranea/index.php?controller=AdminOrders&action=add&token=fixture"),
                    Link("http://outside.example/admin-kuranea/sell/orders"),
                ]

        diagnostic = safe_link_state(Driver())
        self.assertEqual(
            diagnostic,
            "orders_path_candidates=4;orders_root_candidates=1;orders_new_candidates=1;"
            "orders_item_candidates=2;orders_other_subroute_candidates=0;"
            "legacy_orders_candidates=2;eligible_list_links=2",
        )
        self.assertNotIn("fixture", diagnostic)
        self.assertNotIn("outside.example", diagnostic)

        source = ADMIN_FLOW.read_text(encoding="utf-8")
        orders_stage = source.split('stage = "view_only_employee_orders_korean_locale"', 1)[1].split(
            'stage = "view_only_employee_settings_restore"', 1
        )[0]
        self.assertIn("admin_security_orders_link_state", orders_stage)
        self.assertIn("ORDENOWA_ADMIN_ORDERS_LINKS=", source)

    def test_view_only_orders_diagnostic_marks_collection_errors_unknown(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        namespace: dict[str, object] = {
            "parse_qs": parse_qs,
            "urlparse": urlparse,
            "re": re,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
            "By": type("By", (), {"CSS_SELECTOR": "css selector", "TAG_NAME": "tag name"}),
            "is_korean_admin_language": lambda locale: locale.casefold() in {"ko", "ko-kr"},
            "webdriver": type("Webdriver", (), {"Chrome": object}),
        }
        load_function(ADMIN_FLOW, "_admin_controller_for_url", namespace)
        load_function(ADMIN_FLOW, "_diagnostic_bool", namespace)
        safe_state = load_function(ADMIN_FLOW, "safe_admin_orders_state", namespace)

        class Driver:
            current_url = "http://localhost:18080/admin-kuranea/sell/orders"

            def execute_script(self, script: str) -> None:
                raise RuntimeError("browser instrumentation unavailable")

        diagnostic = safe_state(Driver())
        self.assertIn("http_status=unknown", diagnostic)
        self.assertIn("document_ready=unknown", diagnostic)
        self.assertIn("login_form_visible=unknown", diagnostic)
        self.assertIn("body_text=unknown", diagnostic)
        self.assertNotIn("body_text=empty", diagnostic)
        pattern_assignment = next(
            node
            for node in ast.parse(source).body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "SAFE_ADMIN_ORDERS_STATE_PATTERN"
                for target in node.targets
            )
        )
        self.assertIsNotNone(re.fullmatch(ast.literal_eval(pattern_assignment.value), diagnostic))

    def test_view_only_orders_content_wait_retries_a_stale_dom_read(self):
        class StaleElementReferenceException(Exception):
            pass

        class TimeoutException(Exception):
            pass

        class Wait:
            def __init__(self, driver, timeout: int) -> None:
                self.driver = driver
                self.timeout = timeout

            def until(self, condition):
                for _ in range(3):
                    result = condition(self.driver)
                    if result:
                        return result
                raise TimeoutException()

        class Element:
            def __init__(self, text: str = "") -> None:
                self.text = text

            def is_displayed(self) -> bool:
                return True

        class Driver:
            reads = 0

            def find_element(self, by: str, selector: str) -> Element:
                if selector == "body":
                    return Element("주문")
                raise AssertionError(f"unexpected element selector: {selector}")

            def find_elements(self, by: str, selector: str) -> list[Element]:
                self.reads += 1
                if self.reads == 1:
                    raise StaleElementReferenceException()
                elements = {
                    ".header-toolbar h1.title": [Element("주문")],
                    ".js-grid-panel .card-header-title": [Element("주문 (0)")],
                    ".showcase-list-card": [Element()],
                    ".showcase-list-card__header": [Element("주문 관리")],
                    ".showcase-list-card__message": [Element("모든 주문과 주문 상태를 확인할 수 있습니다.")],
                }
                return elements.get(selector, [])

        namespace: dict[str, object] = {
            "WebDriverWait": Wait,
            "TimeoutException": TimeoutException,
            "StaleElementReferenceException": StaleElementReferenceException,
            "re": re,
            "By": type("By", (), {"CSS_SELECTOR": "css selector", "TAG_NAME": "tag name"}),
            "webdriver": type("Webdriver", (), {"Chrome": object}),
        }
        wait_for_label = load_function(ADMIN_FLOW, "wait_for_korean_orders_label", namespace)
        driver = Driver()
        self.assertTrue(wait_for_label(driver))
        self.assertEqual(driver.reads, 6)

    def test_read_only_fixture_opens_its_allowed_settings_tab_without_granting_write_roles(self):
        fixture = FIXTURE.read_text(encoding="utf-8")
        self.assertIn("$employee->default_tab = (int) Tab::getIdFromClassName('AdminBusinessProfile');", fixture)
        access_setup = fixture.split("$access = new Access();", 1)[1].split("$employee = new Employee();", 1)[0]
        self.assertIn("foreach (['AdminBusinessProfile', 'AdminDashboard', 'AdminOrders', 'AdminParentOrders', 'SELL', 'ShopParameters'] as $className)", access_setup)
        self.assertIn("$access->updateLgcAccess((int) $profile->id, $tabId, 'view', true, false)", access_setup)
        for permission in ("'edit' => 'UPDATE'", "'add' => 'CREATE'", "'delete' => 'DELETE'"):
            self.assertIn(permission, access_setup)
        self.assertIn("$action === 'view' ? $granted : !$granted", access_setup)

    def test_view_only_dashboard_access_is_read_back_and_opened_via_employee_default_tab(self):
        fixture = FIXTURE.read_text(encoding="utf-8")
        self.assertIn("$dashboardTabId = (int) Tab::getIdFromClassName('AdminDashboard');", fixture)
        self.assertIn("Profile::resetCacheAccesses();", fixture)
        self.assertIn("Profile::getProfileAccesses((int) $profile->id)", fixture)
        self.assertIn("$dashboardEmployee->default_tab = $dashboardTabId;", fixture)
        self.assertIn("'dashboard_view_only_employee_email' => $emails['dashboard']", fixture)

        source = ADMIN_FLOW.read_text(encoding="utf-8")
        self.assertIn('DASHBOARD_VIEW_ONLY_EMAIL = os.environ["DASHBOARD_VIEW_ONLY_EMAIL"]', source)
        run = source.split("def run()", 1)[1].split("\n\nif __name__", 1)[0]
        self.assertIn("login(restricted_driver, DASHBOARD_VIEW_ONLY_EMAIL)", run)
        self.assertIn('stage = "view_only_employee_dashboard_route"', run)
        self.assertIn('_admin_controller_for_url(restricted_driver.current_url) != "AdminDashboard"', run)
        self.assertNotIn('a[href*="controller=AdminDashboard"]', run)

    def test_dashboard_controller_requires_its_canonical_legacy_admin_path(self):
        namespace: dict[str, object] = {
            "parse_qs": parse_qs,
            "urlparse": urlparse,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
            "webdriver": type("Webdriver", (), {"Chrome": object}),
        }
        controller_for_url = load_function(ADMIN_FLOW, "_admin_controller_for_url", namespace)

        self.assertEqual(
            controller_for_url(
                "http://localhost:18080/admin-kuranea/index.php?controller=AdminDashboard&token=private-token"
            ),
            "AdminDashboard",
        )
        for url in (
            "http://localhost:18080/admin-kuranea/sell/dashboard?controller=AdminDashboard&token=private-token",
            "http://localhost:18080/admin-kuranea/other.php?controller=AdminDashboard&token=private-token",
        ):
            with self.subTest(url=url):
                self.assertNotEqual(controller_for_url(url), "AdminDashboard")

    def test_admin_security_attempt_exposes_compromised_page_evidence_to_classifier(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        submit = source.split("def submit_settings_attempt(", 1)[1].split("\n\ndef ", 1)[0]

        self.assertIn("...nativeCompromisedPage,", submit)
        self.assertNotIn(
            "bodyHasNativeCompromisedPage: nativeCompromisedPage",
            submit,
        )

    def test_admin_browser_cleanup_attempts_both_drivers_and_keeps_failure_redacted(self):
        namespace: dict[str, object] = {"sys": sys}
        close_drivers = load_function(ADMIN_FLOW, "close_browser_drivers", namespace)

        class FakeDriver:
            def __init__(self, fail: bool) -> None:
                self.fail = fail
                self.quit_calls = 0

            def quit(self) -> None:
                self.quit_calls += 1
                if self.fail:
                    raise RuntimeError("private browser session detail")

        admin = FakeDriver(fail=True)
        restricted = FakeDriver(fail=False)
        output = StringIO()
        with redirect_stderr(output):
            cleanup_ok = close_drivers(
                (("admin", admin), ("restricted", restricted)),
                primary_failure=False,
            )

        self.assertFalse(cleanup_ok)
        self.assertEqual(admin.quit_calls, 1)
        self.assertEqual(restricted.quit_calls, 1)
        self.assertIn("admin_chrome_shutdown", output.getvalue())
        self.assertIn("RuntimeError", output.getvalue())
        self.assertNotIn("private browser session detail", output.getvalue())

        admin = FakeDriver(fail=True)
        restricted = FakeDriver(fail=True)
        output = StringIO()
        with redirect_stderr(output):
            cleanup_ok = close_drivers(
                (("admin", admin), ("restricted", restricted)),
                primary_failure=True,
            )

        self.assertFalse(cleanup_ok)
        self.assertEqual(admin.quit_calls, 1)
        self.assertEqual(restricted.quit_calls, 1)
        self.assertIn("WARNING:", output.getvalue())
        self.assertNotIn("::error", output.getvalue())
        self.assertNotIn("private browser session detail", output.getvalue())

    def test_admin_ci_and_origin_guards_accept_only_the_matching_local_project(self):
        namespace: dict[str, object] = {
            "os": os,
            "ipaddress": ipaddress,
            "urlparse": urlparse,
            "COMPOSE_PROJECT": "kuranea-ci-123456789-2",
            "ADMIN_EMAIL": "ci-ordenowa@example.invalid",
            "VIEW_ONLY_EMAIL": "view-only@example.invalid",
            "DASHBOARD_VIEW_ONLY_EMAIL": "dashboard-view-only@example.invalid",
            "EXPECTED_SHOP_PORT": 18080,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
        }
        load_function(ADMIN_FLOW, "_loopback_http_origin", namespace)
        validate_targets = load_function(ADMIN_FLOW, "validate_loopback_admin_targets", namespace)
        validate_project = load_function(ADMIN_FLOW, "validate_isolated_ci_project", namespace)
        valid_environment = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "KURANEA_ISOLATED_CI": "1",
            "GITHUB_RUN_ID": "123456789",
            "GITHUB_RUN_ATTEMPT": "2",
            "CI_COMPOSE_PROJECT_NAME": "kuranea-ci-123456789-2",
        }
        with patch.dict(os.environ, valid_environment, clear=False):
            validate_project()
            validate_targets()
            for key, value in (
                ("CI", "false"),
                ("GITHUB_ACTIONS", "false"),
                ("KURANEA_ISOLATED_CI", "0"),
                ("GITHUB_RUN_ID", "run123"),
                ("GITHUB_RUN_ATTEMPT", "2 "),
                ("CI_COMPOSE_PROJECT_NAME", "kuranea-ci-123456789-3"),
            ):
                with self.subTest(variable=key, value=value), patch.dict(os.environ, {key: value}):
                    with self.assertRaises(ValueError):
                        validate_project()

        for shop_url, admin_url in (
            ("https://shop.example:18080", "https://shop.example:18080/admin-kuranea"),
            ("http://127.0.0.1:18080", "http://localhost:18080/admin-kuranea"),
            ("http://localhost:18081", "http://localhost:18081/admin-kuranea"),
        ):
            with self.subTest(shop_url=shop_url, admin_url=admin_url):
                namespace["BASE"] = shop_url
                namespace["ADMIN_LOGIN"] = admin_url
                with self.assertRaises(ValueError):
                    validate_targets()

    def test_admin_security_attempts_require_the_admin_handler_and_reject_not_found(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        for marker in (
            "responseUrl",
            "bodyHasSettingsForm",
            "bodyHasDangerAlert",
            "bodyHasAdminLoginForm",
            "bodyHasViewOnlyDenial",
            "status == 404",
            "response_url",
            "설정 초안을 수정할 권한이 없습니다.",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_admin_security_rejects_only_the_specific_prestashop_login_gate_page(self):
        namespace: dict[str, object] = {
            "re": re,
            "urlparse": urlparse,
            "parse_qs": parse_qs,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
        }
        is_login_rejection = load_function(
            ADMIN_FLOW,
            "is_prestashop_admin_login_rejection",
            namespace,
        )
        login_page = {
            "status": 200,
            "responseUrl": "http://localhost:18080/admin-kuranea/login",
            "bodyHasAdminLoginForm": True,
            "bodyHasSettingsForm": False,
        }
        self.assertTrue(is_login_rejection(login_page))
        self.assertTrue(
            is_login_rejection(
                {
                    **login_page,
                    "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminLogin",
                }
            )
        )

        for response in (
            {**login_page, "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminDashboard"},
            {**login_page, "responseUrl": "http://localhost:18080/admin-kuranea/another-route"},
            {**login_page, "responseUrl": "http://localhost:18080/login"},
            {**login_page, "responseUrl": "http://outside.example/admin-kuranea/login"},
            {**login_page, "status": 302},
            {**login_page, "bodyHasAdminLoginForm": False},
            {**login_page, "bodyHasSettingsForm": True},
        ):
            with self.subTest(response=response):
                self.assertFalse(is_login_rejection(response))

    def test_admin_security_response_classifier_preserves_explicit_rejections_only(self):
        namespace: dict[str, object] = {
            "re": re,
            "urlparse": urlparse,
            "parse_qs": parse_qs,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
        }
        load_function(ADMIN_FLOW, "response_summary", namespace)
        namespace["is_prestashop_compromised_token_rejection"] = load_function(
            ADMIN_FLOW,
            "is_prestashop_compromised_token_rejection",
            namespace,
        )
        namespace["is_prestashop_admin_login_rejection"] = load_function(
            ADMIN_FLOW,
            "is_prestashop_admin_login_rejection",
            namespace,
        )
        namespace["response_classification"] = load_function(
            ADMIN_FLOW,
            "response_classification",
            namespace,
        )
        namespace["raise_admin_security_response_failure"] = load_function(
            ADMIN_FLOW,
            "raise_admin_security_response_failure",
            namespace,
        )
        assert_rejected = load_function(
            ADMIN_FLOW,
            "assert_security_attempt_rejected",
            namespace,
        )

        assert_rejected(
            {
                "formPresent": True,
                "status": 200,
                "responseUrl": "http://localhost:18080/admin-kuranea/login",
                "bodyHasSettingsForm": False,
                "bodyHasDangerAlert": False,
                "bodyHasAdminLoginForm": True,
                "bodyHasViewOnlyDenial": False,
            },
            "missing",
        )
        assert_rejected(
            {
                "formPresent": True,
                "status": 403,
                "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminBusinessProfile",
                "bodyHasSettingsForm": False,
                "bodyHasDangerAlert": False,
                "bodyHasAdminLoginForm": False,
                "bodyHasViewOnlyDenial": False,
            },
            "invalid",
        )
        assert_rejected(
            {
                "formPresent": True,
                "status": 200,
                "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminBusinessProfile",
                "bodyHasSettingsForm": True,
                "bodyHasDangerAlert": True,
                "bodyHasAdminLoginForm": False,
                "bodyHasViewOnlyDenial": False,
            },
            "invalid",
        )

        for response in (
            {
                "formPresent": True,
                "status": 200,
                "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminDashboard",
                "bodyHasSettingsForm": False,
                "bodyHasDangerAlert": False,
                "bodyHasAdminLoginForm": True,
                "bodyHasViewOnlyDenial": False,
            },
            {
                "formPresent": True,
                "status": 200,
                "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminBusinessProfile",
                "bodyHasSettingsForm": True,
                "bodyHasDangerAlert": False,
                "bodyHasAdminLoginForm": False,
                "bodyHasViewOnlyDenial": False,
            },
        ):
            with self.subTest(response=response), self.assertRaises(AssertionError):
                assert_rejected(response, "missing")

        secret_redirect = {
            "formPresent": True,
            "status": 200,
            "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminDashboard&token=private-token",
            "bodyHasSettingsForm": False,
            "bodyHasDangerAlert": False,
            "bodyHasAdminLoginForm": True,
            "bodyHasViewOnlyDenial": False,
        }
        with self.assertRaises(AssertionError) as failure:
            assert_rejected(secret_redirect, "missing")
        self.assertEqual(
            failure.exception.admin_security_substage,
            "missing_token_rejection_unrecognized",
        )
        self.assertIn("classification=unrecognized", failure.exception.admin_security_response)
        self.assertIn("final_path=/admin-kuranea/index.php", failure.exception.admin_security_response)
        self.assertNotIn("private-token", failure.exception.admin_security_response)

    def test_admin_security_recognizes_native_invalid_token_warning_without_accepting_generic_pages(self):
        namespace = {
            "re": re, "urlparse": urlparse, "parse_qs": parse_qs,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
        }
        for function in (
            "is_prestashop_admin_login_rejection", "is_prestashop_compromised_token_rejection", "response_classification",
            "response_summary", "raise_admin_security_response_failure",
            "assert_security_attempt_rejected",
        ):
            load_function(ADMIN_FLOW, function, namespace)
        warning = {
            "formPresent": True, "status": 200,
            "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminBusinessProfile",
            "bodyHasSettingsForm": False, "bodyHasDangerAlert": False,
            "bodyHasAdminLoginForm": False, "bodyHasViewOnlyDenial": False,
            "bodyHasInvalidTokenPage": True,
        }
        self.assertEqual(namespace["response_classification"](warning), "prestashop_invalid_token")
        for mode in ("missing", "invalid"):
            with self.subTest(mode=mode):
                namespace["assert_security_attempt_rejected"](warning, mode)
        with self.assertRaises(AssertionError):
            namespace["assert_security_attempt_rejected"](warning, "view_only")
        for changes in (
            {"bodyHasInvalidTokenPage": False},
            {"bodyHasSettingsForm": True},
            {"bodyHasAdminLoginForm": True},
            {"responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminDashboard"},
            {"responseUrl": "http://localhost:18080/admin-kuranea/other"},
            {"responseUrl": "http://outside.example/admin-kuranea/index.php?controller=AdminBusinessProfile"},
            {"status": 302},
        ):
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                namespace["assert_security_attempt_rejected"]({**warning, **changes}, "missing")

    def test_admin_security_recognizes_only_the_native_prestashop_compromised_token_route(self):
        namespace = {
            "re": re, "urlparse": urlparse, "parse_qs": parse_qs,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
        }
        for function in (
            "is_prestashop_admin_login_rejection", "is_prestashop_compromised_token_rejection", "response_classification",
            "response_summary", "raise_admin_security_response_failure",
            "assert_security_attempt_rejected",
        ):
            load_function(ADMIN_FLOW, function, namespace)

        native = {
            "formPresent": True,
            "status": 200,
            "responseUrl": "http://localhost:18080/admin-kuranea/security/compromised",
            "bodyHasSettingsForm": False,
            "bodyHasDangerAlert": True,
            "bodyHasAdminLoginForm": False,
            "bodyHasViewOnlyDenial": False,
            "bodyHasNativeCompromisedPage": True,
        }
        self.assertEqual(namespace["response_classification"](native), "prestashop_compromised_token")
        for mode in ("missing", "invalid"):
            with self.subTest(mode=mode):
                namespace["assert_security_attempt_rejected"](native, mode)

        for changes in (
            {"bodyHasNativeCompromisedPage": False},
            {"bodyHasDangerAlert": False},
            {"bodyHasAdminLoginForm": True},
            {"bodyHasViewOnlyDenial": True},
            {"responseUrl": "http://localhost:18080/admin-kuranea/login"},
            {"responseUrl": "http://localhost:18080/admin-kuranea/other/security/compromised"},
            {"responseUrl": "http://outside.example/admin-kuranea/security/compromised"},
            {"status": 404},
            {"status": 302},
        ):
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                namespace["assert_security_attempt_rejected"]({**native, **changes}, "missing")

        generic_danger_alert = {
            **native,
            "bodyHasNativeCompromisedPage": False,
            "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminDashboard",
        }
        with self.assertRaises(AssertionError):
            namespace["assert_security_attempt_rejected"](generic_danger_alert, "missing")

        business_profile_error = {**native, "bodyHasSettingsForm": True}
        self.assertEqual(
            namespace["response_classification"](business_profile_error),
            "business_profile_error",
        )
        self.assertNotEqual(
            namespace["response_classification"](business_profile_error),
            "prestashop_compromised_token",
        )
        namespace["assert_security_attempt_rejected"](business_profile_error, "missing")

        source = ADMIN_FLOW.read_text(encoding="utf-8")
        fixture = ROOT / "tests" / "fixtures" / "prestashop-9.2-security-compromised.html"
        self.assertTrue(fixture.is_file(), "the native PrestaShop 9.2 compromised security fixture is missing")
        markup = fixture.read_text(encoding="utf-8")
        for marker in (
            'id="security-compromised-page"',
            'class="alert alert-danger"',
            "class=\"btn btn-lg btn-outline-danger mr-3\"",
            "class=\"btn btn-lg btn-primary ml-3\"",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, markup)
        self.assertIn("#security-compromised-page", source)
        self.assertIn("verify_native_compromised_page_fixture", source)
        self.assertIn("searchParams.getAll('token')", source)
        self.assertIn("searchParams.getAll('_token')", source)
        self.assertIn('"tokenless_request_link"', source)
        self.assertIn('"tokenized_request_link"', source)
        self.assertIn('"dashboard_symfony_token"', source)
        self.assertIn('"missing_dashboard_token"', source)
        self.assertIn('"duplicate_dashboard_tokens"', source)
        self.assertIn("&& details.compromisedContinueController", source)
        self.assertNotIn("&& details.compromisedContinueTokenPresent", source)
        self.assertIn("&& details.compromisedDashboardTokenPresent", source)
        for diagnostic in (
            "compromisedPageMarker",
            "compromisedWarning",
            "compromisedContinueLink",
            "compromisedDashboardLink",
            "compromisedResponseSameOrigin",
            "compromisedResponsePath",
            "compromisedContinueSameOrigin",
            "compromisedContinuePath",
            "compromisedContinueController",
            "compromisedContinueTokenPresent",
            "compromisedDashboardSameOrigin",
            "compromisedDashboardPath",
            "compromisedDashboardController",
            "compromisedDashboardTokenPresent",
        ):
            with self.subTest(diagnostic=diagnostic):
                self.assertIn(diagnostic, source)
        run = source.split("def run()", 1)[1].split("\n\nif __name__", 1)[0]
        self.assertIn("verify_native_compromised_page_fixture(admin_driver)", run)

    def test_compromised_page_detection_uses_trusted_admin_base_for_request_and_link_paths(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")

        self.assertIn("inspectNativeCompromisedPage(", source)
        self.assertIn("            adminBaseUrl\n          );", source)
        self.assertIn("        ADMIN_LOGIN,\n    )", source)
        self.assertIn(
            "function inspectNativeCompromisedPage(body, responseUrl, targetUrl, adminBaseUrl)",
            source,
        )
        self.assertIn("const adminBase = new URL(adminBaseUrl)", source)
        self.assertIn("target.pathname.startsWith(adminPath + '/')", source)
        self.assertIn("response.pathname === adminPath + '/security/compromised'", source)
        self.assertIn('("pretty_admin_request_path", pretty_admin_links, True)', source)
        self.assertIn("continueUrl.pathname === target.pathname", source)
        self.assertIn("isAdminControllerRoutePath", source)
        self.assertIn('("target_outside_admin_prefix", markup, False)', source)

    def test_admin_security_failure_summary_exposes_only_safe_invalid_token_dom_facts(self):
        namespace = {"re": re, "urlparse": urlparse, "parse_qs": parse_qs}
        load_function(ADMIN_FLOW, "is_prestashop_compromised_token_rejection", namespace)
        load_function(ADMIN_FLOW, "is_prestashop_admin_login_rejection", namespace)
        load_function(ADMIN_FLOW, "response_classification", namespace)
        summary = load_function(ADMIN_FLOW, "response_summary", namespace)
        result = {
            "status": 200,
            "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminBusinessProfile&token=secret",
            "bodyHasSettingsForm": False,
            "bodyHasDangerAlert": False,
            "bodyHasAdminLoginForm": False,
            "bodyHasInvalidTokenPage": False,
            "bodyHasInvalidTokenWarning": True,
            "bodyHasInvalidTokenContinue": True,
            "bodyHasInvalidTokenCancel": True,
            "invalidTokenRecoverySameOrigin": True,
            "invalidTokenRecoverySamePath": True,
            "invalidTokenRecoveryController": "AdminBusinessProfile",
            "invalidTokenRecoveryTokenPresent": True,
            "compromisedPageMarker": True,
            "compromisedRequestSameOrigin": True,
            "compromisedRequestInAdminPath": True,
            "compromisedWarning": True,
            "compromisedContinueLink": True,
            "compromisedDashboardLink": True,
            "compromisedResponseSameOrigin": True,
            "compromisedResponsePath": True,
            "compromisedContinueSameOrigin": True,
            "compromisedContinuePath": True,
            "compromisedContinueController": True,
            "compromisedContinueTokenPresent": True,
            "compromisedDashboardSameOrigin": True,
            "compromisedDashboardPath": True,
            "compromisedDashboardController": True,
            "compromisedDashboardTokenPresent": True,
        }
        diagnostic = summary(result)
        for safe_fact in (
            "response_controller=AdminBusinessProfile",
            "invalid_token_warning=true",
            "invalid_token_continue=true",
            "invalid_token_cancel=true",
            "recovery_same_origin=true",
            "recovery_same_path=true",
            "recovery_controller=AdminBusinessProfile",
            "recovery_token_present=true",
            "invalid_token_page=false",
            "native_compromised_page=false",
            "compromised_marker=true",
            "compromised_request_origin=true",
            "compromised_request_path=true",
            "compromised_warning=true",
            "compromised_continue=true",
            "compromised_dashboard=true",
            "compromised_response_origin=true",
            "compromised_response_path=true",
            "compromised_continue_origin=true",
            "compromised_continue_path=true",
            "compromised_continue_controller=true",
            "compromised_continue_token=true",
            "compromised_dashboard_origin=true",
            "compromised_dashboard_path=true",
            "compromised_dashboard_controller=true",
            "compromised_dashboard_token=true",
        ):
            with self.subTest(safe_fact=safe_fact):
                self.assertIn(safe_fact, diagnostic)
        self.assertIn("settings_form=false; danger_alert=false; admin_login_form=false", diagnostic)
        self.assertNotIn("secret", diagnostic)

        source = ADMIN_FLOW.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(ADMIN_FLOW))
        pattern_assignment = next(
            (
                node
                for node in module.body
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "SAFE_ADMIN_SECURITY_RESPONSE_PATTERN"
                    for target in node.targets
                )
            ),
            None,
        )
        self.assertIsNotNone(pattern_assignment)
        assert pattern_assignment is not None
        self.assertRegex(diagnostic, ast.literal_eval(pattern_assignment.value))

    def test_admin_security_browser_runs_native_token_dom_fixture_in_chromium(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        fixture = ROOT / "tests" / "fixtures" / "prestashop-9.2-invalid-token.html"
        self.assertTrue(fixture.is_file(), "the native PrestaShop invalid-token fixture is missing")
        markup = fixture.read_text(encoding="utf-8")
        self.assertIn('<img width="32px" alt="warning"', markup)
        self.assertIn('class="btn btn-continue"', markup)
        self.assertIn('class="btn btn-cancel" href="index.php"', markup)
        self.assertIn("TOKEN_DOM_DETECTOR_JS", source)
        self.assertIn("verify_native_invalid_token_dom_fixture", source)
        self.assertIn("verify_native_invalid_token_dom_fixture(admin_driver)", source)

    def test_admin_security_attempt_rechecks_state_before_classifying_a_rejection(self):
        events: list[str] = []

        def reject_unrecognized_response(response, mode):
            events.append("classification")
            error = AssertionError("unrecognized response")
            error.admin_security_substage = "missing_token_rejection_unrecognized"
            error.admin_security_response = "classification=unrecognized; status=200; final_path=/admin-kuranea/home; settings_form=false; danger_alert=false; admin_login_form=false"
            raise error

        namespace: dict[str, object] = {
            "webdriver": type("WebDriverTypes", (), {"Chrome": object}),
            "submit_settings_attempt": lambda driver, mode: events.append("request") or {"status": 200},
            "assert_setting_unchanged": lambda driver, value, pointer, label: events.append("state"),
            "assert_security_attempt_rejected": reject_unrecognized_response,
        }
        verify_attempt = load_function(
            ADMIN_FLOW,
            "verify_security_attempt_without_mutation",
            namespace,
        )
        with self.assertRaisesRegex(AssertionError, "unrecognized response") as response_failure:
            verify_attempt(object(), "missing", "original", "17", "missing-token")
        self.assertEqual(events, ["request", "state", "classification"])
        self.assertEqual(response_failure.exception.admin_security_request, "completed")
        self.assertEqual(response_failure.exception.admin_security_state_recheck, "passed")

        events.clear()
        namespace["submit_settings_attempt"] = lambda driver, mode: events.append("request") or {"status": 200}
        namespace["assert_setting_unchanged"] = lambda driver, value, pointer, label: (
            events.append("state") or (_ for _ in ()).throw(AssertionError("private setting value"))
        )
        with self.assertRaises(AssertionError) as state_failure:
            verify_attempt(object(), "missing", "original", "17", "missing-token")
        self.assertEqual(events, ["request", "state"])
        self.assertEqual(state_failure.exception.admin_security_substage, "state_recheck_failed")
        self.assertEqual(state_failure.exception.admin_security_request, "completed")
        self.assertEqual(state_failure.exception.admin_security_state_recheck, "failed:AssertionError")
        self.assertEqual(state_failure.exception.admin_security_response, "not_evaluated")
        self.assertNotIn("private setting value", str(state_failure.exception))

        events.clear()
        namespace["assert_setting_unchanged"] = lambda driver, value, pointer, label: events.append("state")
        namespace["assert_security_attempt_rejected"] = lambda response, mode: events.append("classification")
        with self.assertRaises(AssertionError) as request_failure:
            namespace["submit_settings_attempt"] = lambda driver, mode: (
                events.append("request") or (_ for _ in ()).throw(RuntimeError("browser request failed"))
            )
            verify_attempt(object(), "missing", "original", "17", "missing-token")
        self.assertEqual(events, ["request", "state"])
        self.assertEqual(request_failure.exception.admin_security_substage, "request_execution")
        self.assertEqual(request_failure.exception.admin_security_request, "failed:RuntimeError")
        self.assertEqual(request_failure.exception.admin_security_state_recheck, "passed")
        self.assertEqual(request_failure.exception.admin_security_response, "not_evaluated")

    def test_security_fixtures_create_read_only_admin_and_two_disposable_customers(self):
        self.assertTrue(FIXTURE.is_file(), "the isolated security fixture seeder is missing")
        source = FIXTURE.read_text(encoding="utf-8")
        for marker in (
            "AdminBusinessProfile",
            "AdminDashboard",
            "updateLgcAccess",
            "'view'",
            "'edit'",
            "'add'",
            "'delete'",
            "reset-token-replay",
            "reset-token-expired",
            "example.invalid",
            "getenv('CI') === 'true'",
            "getenv('GITHUB_ACTIONS') === 'true'",
            "getenv('KURANEA_ISOLATED_CI') === '1'",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
            "CI_COMPOSE_PROJECT_NAME",
            "FILTER_VALIDATE_EMAIL",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        guard_start = source.index("getenv('CI') === 'true'")
        bootstrap = source.index("require_once '/var/www/html/config/config.inc.php';")
        first_profile_write = source.index("new Profile();")
        self.assertLess(guard_start, bootstrap)
        self.assertLess(bootstrap, first_profile_write)

    def test_reset_token_browser_flow_replays_consumed_token_and_expires_live_fixture(self):
        self.assertTrue(RESET_FLOW.is_file(), "the isolated reset-token browser flow is missing")
        source = RESET_FLOW.read_text(encoding="utf-8")
        for marker in (
            "REPLAY_CUSTOMER_EMAIL",
            "EXPIRED_CUSTOMER_EMAIL",
            'button[type="submit"][name="submit"]',
            "expire_reset_token_in_isolated_container",
            "validate_isolated_ci_compose_project",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
            "KURANEA_ISOLATED_CI",
            "assert_reset_link_rejected",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        expiry = source[source.index("def expire_reset_token_in_isolated_container") :]
        self.assertLess(
            expiry.index("validate_isolated_ci_compose_project()"),
            expiry.index("subprocess.run(command"),
        )

    def test_reset_browser_guards_loopback_shop_and_mailpit_before_any_reset_request(self):
        source = RESET_FLOW.read_text(encoding="utf-8")
        for marker in (
            "EXPECTED_SHOP_PORT = 18080",
            "EXPECTED_MAILPIT_PORT = 8025",
            "def validate_loopback_endpoints",
            "ipaddress.ip_address(host).is_loopback",
            "validate_isolated_ci_compose_project()",
            "validate_loopback_endpoints()",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        run = source.split("def run()", 1)[1].split("\n\nif __name__", 1)[0]
        self.assertLess(run.index("validate_isolated_ci_compose_project()"), run.index("replay_scenario()"))
        self.assertLess(run.index("validate_loopback_endpoints()"), run.index("replay_scenario()"))

    def test_reset_endpoint_guard_rejects_remote_hosts_and_wrong_ports(self):
        namespace: dict[str, object] = {"ipaddress": ipaddress, "urlparse": urlparse}
        validate_endpoint = load_function(RESET_FLOW, "_validate_loopback_endpoint", namespace)
        self.assertEqual(
            validate_endpoint("http://localhost:18080", 18080, "SHOP_BASE_URL"),
            ("http", "localhost", 18080),
        )
        self.assertEqual(
            validate_endpoint("http://127.0.0.1:8025", 8025, "MAILPIT_API_URL"),
            ("http", "127.0.0.1", 8025),
        )
        for url, expected_port in (
            ("https://localhost:18080", 18080),
            ("http://shop.example:18080", 18080),
            ("http://127.0.0.1:18081", 18080),
            ("http://user@localhost:18080", 18080),
            ("http://localhost:18080/path", 18080),
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    validate_endpoint(url, expected_port, "test endpoint")

    def test_reset_rejection_and_replay_require_native_customer_account_state(self):
        source = RESET_FLOW.read_text(encoding="utf-8")
        for marker in (
            'form.forgotten-password .alert.alert-danger',
            "password change request expired",
            "def assert_customer_can_login_with_password",
            "a.account-menu__link--signout",
            "assert_customer_can_login_with_password(REPLAY_EMAIL, password)",
            "expected_reset_path",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        replay = source.split("def replay_scenario()", 1)[1].split("def expiry_scenario()", 1)[0]
        self.assertLess(
            replay.index("assert_customer_can_login_with_password(REPLAY_EMAIL, password)"),
            replay.index("assert_reset_link_rejected("),
        )

    def test_reset_rejection_marker_matches_native_expiry_error_not_generic_alerts(self):
        marker = load_function(RESET_FLOW, "is_native_expired_reset_message", {})
        self.assertTrue(marker("The password change request expired. You should ask for a new one."))
        self.assertTrue(marker("パスワード変更リクエストの有効期限が切れました。"))
        self.assertTrue(marker("비밀번호 변경 요청이 만료되었습니다."))
        self.assertFalse(marker("Page not found"))
        self.assertFalse(marker("Your email address is invalid."))


if __name__ == "__main__":
    unittest.main()
