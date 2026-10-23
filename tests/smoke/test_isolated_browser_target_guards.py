"""Contracts for run-scoped loopback targets used by mutating browser QA."""

from __future__ import annotations

import ast
import ipaddress
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
ACCOUNT_FLOW = ROOT / "tests" / "e2e" / "verify_customer_account_browser.py"
BRAND_FLOW = ROOT / "tests" / "e2e" / "verify_brand_admin_browser.py"
EMAIL_BRAND_FLOW = ROOT / "tests" / "e2e" / "verify_reset_email_brand_browser.py"
FREE_SHIPPING_FLOW = ROOT / "tests" / "e2e" / "verify_ci_free_shipping_browser.py"
CART_CONTROLS_FLOW = ROOT / "tests" / "e2e" / "verify_cart_controls_browser.py"
EMAIL_CUSTOMER_SEED = ROOT / "tests" / "business_profile" / "seed_reset_email_customer.php"


def load_functions(path: Path, names: set[str], namespace: dict[str, object]) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    selected = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    module = ast.Module(body=selected, type_ignores=[])
    exec(compile(module, str(path), "exec"), namespace)
    return namespace


class IsolatedBrowserTargetGuardTests(unittest.TestCase):
    def test_mutating_browser_flows_guard_ci_targets_before_browser_or_credentials(self) -> None:
        cases = (
            (ACCOUNT_FLOW, "run_viewport", "validate_isolated_ci_compose_project", "validate_loopback_endpoints"),
            (BRAND_FLOW, "run", "validate_isolated_ci_compose_project", "validate_loopback_admin_targets"),
            (EMAIL_BRAND_FLOW, "run", "validate_isolated_ci_compose_project", "validate_loopback_endpoints"),
        )
        for path, entry_name, project_guard, endpoint_guard in cases:
            with self.subTest(flow=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertIn(f"def {project_guard}(", source)
                self.assertIn(f"def {endpoint_guard}(", source)
                entry = source.split(f"def {entry_name}(", 1)[1]
                entry = entry.split("\n\ndef ", 1)[0]
                self.assertLess(entry.index(project_guard + "()"), entry.index("webdriver.Chrome("))
                self.assertLess(entry.index(endpoint_guard + "()"), entry.index("webdriver.Chrome("))

        account = ACCOUNT_FLOW.read_text(encoding="utf-8")
        run_viewport = account.split("def run_viewport(", 1)[1].split("\n\ndef ", 1)[0]
        self.assertLess(run_viewport.index("validate_isolated_ci_compose_project()"), run_viewport.index("webdriver.Chrome("))
        self.assertLess(run_viewport.index("validate_loopback_endpoints()"), run_viewport.index("webdriver.Chrome("))

    def test_free_shipping_modes_guard_the_isolated_shop_before_browser_or_admin_actions(self) -> None:
        source = FREE_SHIPPING_FLOW.read_text(encoding="utf-8")
        for entry_name in (
            "configure_free_carrier",
            "readback_free_carrier",
            "run_japan_customer_checkout",
            "run_japan_mobile_osaka_checkout",
            "run_japan_taxable_customer_checkout",
            "run_free_carrier_admin_order_view",
        ):
            with self.subTest(entry=entry_name):
                entry = source.split(f"def {entry_name}(", 1)[1].split("\n\ndef ", 1)[0]
                self.assertLess(entry.index("validate_isolated_ci_compose_project()"), entry.index("webdriver.Chrome("))
                self.assertLess(entry.index("validate_loopback_admin_targets()"), entry.index("webdriver.Chrome("))

    def test_free_shipping_guard_requires_exact_ci_project_and_same_origin_loopback_urls(self) -> None:
        valid = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "KURANEA_ISOLATED_CI": "1",
            "GITHUB_RUN_ID": "123456789",
            "GITHUB_RUN_ATTEMPT": "2",
            "CI_COMPOSE_PROJECT_NAME": "kuranea-ci-123456789-2",
        }
        namespace = load_functions(
            FREE_SHIPPING_FLOW,
            {"validate_isolated_ci_compose_project", "_loopback_http_origin", "validate_loopback_admin_targets"},
            {
                "os": os,
                "re": re,
                "ipaddress": ipaddress,
                "urlparse": urlparse,
                "BASE": "http://localhost:18080",
                "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
                "EXPECTED_SHOP_PORT": 18080,
            },
        )
        with patch.dict(os.environ, valid, clear=False):
            namespace["validate_isolated_ci_compose_project"]()
            namespace["validate_loopback_admin_targets"]()
            for key, value in (
                ("CI", "false"),
                ("GITHUB_ACTIONS", "false"),
                ("KURANEA_ISOLATED_CI", "0"),
                ("GITHUB_RUN_ID", "123x"),
                ("GITHUB_RUN_ATTEMPT", "2 "),
                ("CI_COMPOSE_PROJECT_NAME", "kuranea-ci-123456789-3"),
            ):
                with self.subTest(variable=key), patch.dict(os.environ, {key: value}):
                    with self.assertRaises(ValueError):
                        namespace["validate_isolated_ci_compose_project"]()

        for shop, admin in (
            ("https://localhost:18080", "https://localhost:18080/admin-kuranea"),
            ("http://shop.example:18080", "http://shop.example:18080/admin-kuranea"),
            ("http://localhost:18081", "http://localhost:18081/admin-kuranea"),
            ("http://localhost:18080/store", "http://localhost:18080/admin-kuranea"),
            ("http://localhost:18080", "http://127.0.0.1:18080/admin-kuranea"),
        ):
            with self.subTest(shop=shop, admin=admin):
                namespace["BASE"] = shop
                namespace["ADMIN_LOGIN"] = admin
                with self.assertRaises(ValueError):
                    namespace["validate_loopback_admin_targets"]()

    def test_cart_controls_browser_requires_isolated_ci_and_loopback_shop_before_driver(self) -> None:
        source = CART_CONTROLS_FLOW.read_text(encoding="utf-8")
        run = source.split("def run_viewport(", 1)[1].split("\n\ndef ", 1)[0]
        self.assertLess(run.index("validate_isolated_ci_compose_project()"), run.index("webdriver.Chrome("))
        self.assertLess(run.index("validate_loopback_shop()"), run.index("webdriver.Chrome("))

        valid = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "KURANEA_ISOLATED_CI": "1",
            "GITHUB_RUN_ID": "123456789",
            "GITHUB_RUN_ATTEMPT": "2",
            "CI_COMPOSE_PROJECT_NAME": "kuranea-ci-123456789-2",
        }
        namespace = load_functions(
            CART_CONTROLS_FLOW,
            {"validate_isolated_ci_compose_project", "validate_loopback_shop"},
            {
                "os": os,
                "re": re,
                "ipaddress": ipaddress,
                "urlparse": urlparse,
                "BASE": "http://localhost:18080",
                "EXPECTED_SHOP_PORT": 18080,
            },
        )
        with patch.dict(os.environ, valid, clear=False):
            namespace["validate_isolated_ci_compose_project"]()
            namespace["validate_loopback_shop"]()
            for key, value in (
                ("CI", "false"),
                ("KURANEA_ISOLATED_CI", "0"),
                ("CI_COMPOSE_PROJECT_NAME", "kuranea-ci-123456789-3"),
            ):
                with self.subTest(variable=key), patch.dict(os.environ, {key: value}):
                    with self.assertRaises(ValueError):
                        namespace["validate_isolated_ci_compose_project"]()

        for target in (
            "https://localhost:18080",
            "http://store.example:18080",
            "http://localhost:18081",
            "http://localhost:18080/shop",
        ):
            with self.subTest(target=target):
                namespace["BASE"] = target
                with self.assertRaises(ValueError):
                    namespace["validate_loopback_shop"]()

    def test_python_project_guard_requires_exact_github_run_scoped_compose_project(self) -> None:
        valid = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "KURANEA_ISOLATED_CI": "1",
            "GITHUB_RUN_ID": "123456789",
            "GITHUB_RUN_ATTEMPT": "2",
            "CI_COMPOSE_PROJECT_NAME": "kuranea-ci-123456789-2",
        }
        for path in (ACCOUNT_FLOW, BRAND_FLOW, EMAIL_BRAND_FLOW):
            with self.subTest(flow=path.name):
                namespace = load_functions(
                    path,
                    {"validate_isolated_ci_compose_project"},
                    {
                        "os": os,
                        "re": re,
                        "CUSTOMER_EMAIL": "ordenowa-reset-logo-123456789-2-ab12cd@example.invalid",
                        "ADMIN_EMAIL": "ci-ordenowa@example.invalid",
                    },
                )
                with patch.dict(os.environ, valid, clear=False):
                    namespace["validate_isolated_ci_compose_project"]()
                    for key, value in (
                        ("CI", "false"),
                        ("GITHUB_ACTIONS", "false"),
                        ("KURANEA_ISOLATED_CI", "0"),
                        ("GITHUB_RUN_ID", "123x"),
                        ("GITHUB_RUN_ATTEMPT", "2 "),
                        ("CI_COMPOSE_PROJECT_NAME", "kuranea-ci-123456789-3"),
                    ):
                        with self.subTest(variable=key, value=value), patch.dict(os.environ, {key: value}):
                            with self.assertRaises(ValueError):
                                namespace["validate_isolated_ci_compose_project"]()
                    if path == EMAIL_BRAND_FLOW:
                        namespace["CUSTOMER_EMAIL"] = "ordenowa-reset-logo-123456788-2-ab12cd@example.invalid"
                        with self.assertRaises(ValueError):
                            namespace["validate_isolated_ci_compose_project"]()

    def test_shop_and_mailpit_guards_accept_only_expected_loopback_ports(self) -> None:
        for path in (ACCOUNT_FLOW, EMAIL_BRAND_FLOW):
            with self.subTest(flow=path.name):
                namespace = load_functions(
                    path,
                    {"_validate_loopback_endpoint", "validate_loopback_endpoints"},
                    {
                        "ipaddress": ipaddress,
                        "urlparse": urlparse,
                        "BASE": "http://localhost:18080",
                        "MAILPIT_API": "http://127.0.0.1:8025",
                        "EXPECTED_SHOP_PORT": 18080,
                        "EXPECTED_MAILPIT_PORT": 8025,
                    },
                )
                namespace["validate_loopback_endpoints"]()
                for url, port in (
                    ("https://localhost:18080", 18080),
                    ("http://shop.example:18080", 18080),
                    ("http://localhost:18081", 18080),
                    ("http://localhost:18080/store", 18080),
                    ("http://127.0.0.1:8026", 8025),
                ):
                    with self.subTest(url=url):
                        with self.assertRaises(ValueError):
                            namespace["_validate_loopback_endpoint"](url, port, "endpoint")

    def test_brand_admin_guard_requires_same_loopback_shop_origin_and_admin_path(self) -> None:
        namespace = load_functions(
            BRAND_FLOW,
            {"_loopback_http_origin", "validate_loopback_admin_targets"},
            {
                "ipaddress": ipaddress,
                "urlparse": urlparse,
                "BASE": "http://localhost:18080",
                "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
                "EXPECTED_SHOP_PORT": 18080,
            },
        )
        namespace["validate_loopback_admin_targets"]()
        for shop, admin in (
            ("http://localhost:18080", "http://127.0.0.1:18080/admin-kuranea"),
            ("http://localhost:18081", "http://localhost:18081/admin-kuranea"),
            ("https://localhost:18080", "https://localhost:18080/admin-kuranea"),
            ("http://shop.example:18080", "http://shop.example:18080/admin-kuranea"),
            ("http://localhost:18080/store", "http://localhost:18080/admin-kuranea"),
        ):
            with self.subTest(shop=shop, admin=admin):
                namespace["BASE"] = shop
                namespace["ADMIN_LOGIN"] = admin
                with self.assertRaises(ValueError):
                    namespace["validate_loopback_admin_targets"]()

    def test_php_customer_seed_guards_ci_project_before_bootstrap_or_customer_write(self) -> None:
        source = EMAIL_CUSTOMER_SEED.read_text(encoding="utf-8")
        for marker in (
            "getenv('CI') !== 'true'",
            "getenv('GITHUB_ACTIONS') !== 'true'",
            "getenv('KURANEA_ISOLATED_CI') !== '1'",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
            "KURANEA_CI_PROJECT_NAME",
            "kuranea-ci-%s-%s",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        guard = source.index("ordenowaRequireIsolatedEmailBrandSeedContext();")
        self.assertLess(guard, source.index("require_once '/var/www/html/config/config.inc.php';"))
        self.assertLess(guard, source.index("new Customer();"))


if __name__ == "__main__":
    unittest.main()
