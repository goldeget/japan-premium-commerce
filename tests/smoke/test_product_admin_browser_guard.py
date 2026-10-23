"""Fail-closed target contracts for the mutating Korean product admin browser QA."""

from __future__ import annotations

import ipaddress
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ADMIN_FLOW = ROOT / "tests" / "e2e" / "verify_product_admin_browser.py"


def load_functions(names: set[str], namespace: dict[str, object]) -> dict[str, object]:
    """Load only guard functions so contracts run without Selenium or CI credentials."""
    import ast

    tree = ast.parse(PRODUCT_ADMIN_FLOW.read_text(encoding="utf-8"), filename=str(PRODUCT_ADMIN_FLOW))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    module = ast.Module(body=selected, type_ignores=[])
    exec(compile(module, str(PRODUCT_ADMIN_FLOW), "exec"), namespace)
    return namespace


class ProductAdminBrowserGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.namespace = load_functions(
            {
                "validate_isolated_ci_compose_project",
                "_loopback_http_origin",
                "validate_loopback_admin_targets",
            },
            {
                "os": os,
                "ipaddress": ipaddress,
                "urlparse": urlparse,
                "BASE": "http://localhost:18080",
                "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
                "EXPECTED_SHOP_PORT": 18080,
            },
        )

    def test_browser_entrypoints_guard_before_driver_startup(self) -> None:
        source = PRODUCT_ADMIN_FLOW.read_text(encoding="utf-8")
        for entry_name in ("run", "run_mobile_layout"):
            with self.subTest(entry=entry_name):
                entry = source.split(f"def {entry_name}(", 1)[1].split("\n\ndef ", 1)[0]
                for guard in (
                    "validate_isolated_ci_compose_project()",
                    "validate_loopback_admin_targets()",
                ):
                    self.assertLess(entry.index(guard), entry.index("webdriver.Chrome("))
                    self.assertLess(entry.index(guard), entry.index('driver.get(ADMIN_LOGIN + "/login")'))
                    self.assertLess(entry.index(guard), entry.index("email.send_keys(ADMIN_EMAIL)"))

        desktop = source.split("def run(", 1)[1].split("\n\ndef ", 1)[0]
        for guard in (
            "validate_isolated_ci_compose_project()",
            "validate_loopback_admin_targets()",
        ):
            self.assertLess(desktop.index(guard), desktop.index('button[name="submitKuraneaProductSave"]'))

    def test_project_guard_requires_exact_run_scoped_isolated_ci_project(self) -> None:
        valid = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "KURANEA_ISOLATED_CI": "1",
            "GITHUB_RUN_ID": "123456789",
            "GITHUB_RUN_ATTEMPT": "2",
            "CI_COMPOSE_PROJECT_NAME": "kuranea-ci-123456789-2",
        }
        with patch.dict(os.environ, valid, clear=False):
            self.namespace["validate_isolated_ci_compose_project"]()
            for key, value in (
                ("CI", "false"),
                ("GITHUB_ACTIONS", "false"),
                ("KURANEA_ISOLATED_CI", "0"),
                ("GITHUB_RUN_ID", "123x"),
                ("GITHUB_RUN_ID", "１２３"),
                ("GITHUB_RUN_ATTEMPT", "2 "),
                ("CI_COMPOSE_PROJECT_NAME", "kuranea-ci-123456789-3"),
            ):
                with self.subTest(variable=key, value=value), patch.dict(os.environ, {key: value}):
                    with self.assertRaises(ValueError):
                        self.namespace["validate_isolated_ci_compose_project"]()

    def test_admin_guard_requires_same_loopback_shop_origin_and_backoffice_path(self) -> None:
        self.namespace["validate_loopback_admin_targets"]()
        for shop, admin in (
            ("https://localhost:18080", "https://localhost:18080/admin-kuranea"),
            ("http://shop.example:18080", "http://shop.example:18080/admin-kuranea"),
            ("http://localhost:18081", "http://localhost:18081/admin-kuranea"),
            ("http://localhost:18080/store", "http://localhost:18080/admin-kuranea"),
            ("http://localhost:18080", "http://127.0.0.1:18080/admin-kuranea"),
            ("http://localhost:18080", "http://localhost:18080/admin-kuranea-extra"),
            ("http://user@localhost:18080", "http://user@localhost:18080/admin-kuranea"),
            ("http://localhost:18080", "http://localhost:18080/admin-kuranea?token=secret"),
        ):
            with self.subTest(shop=shop, admin=admin):
                self.namespace["BASE"] = shop
                self.namespace["ADMIN_LOGIN"] = admin
                with self.assertRaises(ValueError):
                    self.namespace["validate_loopback_admin_targets"]()


if __name__ == "__main__":
    unittest.main()
