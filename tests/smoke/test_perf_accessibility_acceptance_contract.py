"""Lock the synthetic Lighthouse and axe acceptance path into isolated CI."""
from __future__ import annotations

import ast
import http.client
import json
from pathlib import Path
import socket
import ssl
from urllib.error import HTTPError, URLError
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/fresh-install.yml"
SCRIPT = ROOT / "tests/performance/run_quality_audit.py"
PACKAGE = ROOT / "tests/performance/package.json"
LOCK = ROOT / "tests/performance/package-lock.json"


class PerformanceAccessibilityAcceptanceContractTests(unittest.TestCase):
    def test_exact_tools_and_transitive_integrities_are_locked(self):
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        expected = {"axe-core": "4.14.0", "lighthouse": "13.5.0"}
        self.assertEqual(expected, package["dependencies"])
        self.assertEqual(expected, lock["packages"][""]["dependencies"])
        self.assertEqual(3, lock["lockfileVersion"])
        for name, version in expected.items():
            entry = lock["packages"][f"node_modules/{name}"]
            self.assertEqual(version, entry["version"])
            self.assertTrue(entry["resolved"].startswith("https://registry.npmjs.org/"))
            self.assertTrue(entry["integrity"].startswith("sha512-"))

    def test_browser_gate_uses_required_targets_and_wcag_22_axe_tags(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        assignments = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in {"TARGETS", "WCAG_TAGS"}
        }
        self.assertEqual(
            {
                "performance_mobile_min": 90.0,
                "performance_desktop_min": 95.0,
                "accessibility_min": 95.0,
                "seo_min": 95.0,
                "lcp_ms_max": 2500.0,
                "cls_max": 0.1,
                "scripted_interaction_next_paint_ms_lab_proxy_max": 200.0,
            },
            assignments["TARGETS"],
        )
        self.assertEqual(("wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"), assignments["WCAG_TAGS"])
        self.assertNotIn("wcag22a", assignments["WCAG_TAGS"])
        self.assertIn("def assert_supported_axe_tags()", SCRIPT.read_text(encoding="utf-8"))
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"inp_field_measurement": False', source)
        self.assertIn('"metric": "scripted_click_to_next_paint_ms_lab_proxy"', source)
        self.assertIn('"manual_review_required": bool(incomplete)', source)

    def test_full_isolated_ci_measures_after_fixtures_and_aggregates_real_outcome(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("tests/performance/**", workflow)
        self.assertIn("tests.smoke.test_perf_accessibility_acceptance_contract", workflow)
        self.assertIn("node-version: '24.19.0'", workflow)
        self.assertIn('EXPECTED_NODE_VERSION = "v24.19.0"', SCRIPT.read_text(encoding="utf-8"))
        self.assertIn("npm ci --ignore-scripts --no-audit --no-fund --prefix tests/performance", workflow)
        self.assertIn("steps.variant_fixture.outcome == 'success'", workflow)
        self.assertIn("steps.native_contact_route_fixture.outcome == 'success'", workflow)
        self.assertIn("steps.perf_accessibility_deps.outcome == 'success'", workflow)
        self.assertIn("tests/performance/run_quality_audit.py", workflow)
        self.assertIn("PERF_ACCESSIBILITY_QA_OUTCOME: ${{ steps.perf_accessibility_qa.outcome }}", workflow)
        self.assertIn('"perf_accessibility_qa=$PERF_ACCESSIBILITY_QA_OUTCOME"', workflow)

    def test_measurement_is_loopback_guarded_and_artifact_contains_only_safe_fields(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for required in (
            'parsed.hostname not in {"localhost", "127.0.0.1", "::1"}',
            'os.environ.get("KURANEA_ISOLATED_CI") != "1"',
            '"violation_rules": violations',
            '"incomplete_rules": incomplete',
            '"performance_score": performance',
            '"accessibility_score": accessibility',
            '"seo_score": seo',
            '"lcp_ms": round(lcp_ms, 1)',
            '"cls": round(cls, 4)',
            'report_path',
        ):
            self.assertIn(required, source)
        for disallowed in ("node.get('html')", "node.get('target')", "report['finalUrl']", "report_path.read_text()"):
            self.assertNotIn(disallowed, source)

    def test_route_preflight_is_bounded_and_one_failure_does_not_stop_other_routes(self):
        source = SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assignments = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "ROUTE_LABELS"
        }
        self.assertEqual(("home", "product", "contact_ja"), assignments["ROUTE_LABELS"])

        preflight = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "preflight_routes"
        )
        preflight_source = ast.get_source_segment(source, preflight)
        self.assertIn("for label in ROUTE_LABELS", preflight_source)
        self.assertIn("except HTTPError as error", preflight_source)
        self.assertIn("except Exception as error", preflight_source)
        self.assertIn('"status": status', preflight_source)
        self.assertIn('"exception_category": category', preflight_source)
        self.assertIn('"passed": passed', preflight_source)
        for sensitive in ("str(error)", "error.reason", "response.read(", "page_source", "screenshot"):
            self.assertNotIn(sensitive, preflight_source)

        main = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        main_source = ast.get_source_segment(source, main)
        self.assertIn("route_ready = preflight_routes(routes, result)", main_source)
        self.assertGreaterEqual(main_source.count("if not route_ready.get(label)"), 2)
        self.assertIn("all_routes_ready", main_source)
        self.assertIn("route_preflight={preflight_summary(result)}", main_source)
        self.assertIn("safe_failure_codes=", main_source)

    def test_route_status_mismatch_remains_a_failure_when_other_routes_are_scanned(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"route_status_mismatch" if status is not None else "route_unreachable"', source)
        self.assertIn('result["safe_failure_codes"].append(', source)
        self.assertIn('result["overall"] = "success" if lighthouse_passed and axe_passed and interaction_passed and not result["safe_failure_codes"] else "failure"', source)

    def test_preflight_records_numeric_status_and_fixed_exception_without_stopping(self):
        source = SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source)
        selected = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"preflight_exception_category", "preflight_routes", "preflight_summary"}
        ]
        namespace = {
            "ROUTE_LABELS": ("home", "product", "contact_ja"),
            "HTTPError": HTTPError,
            "URLError": URLError,
            "http": http,
            "socket": socket,
            "ssl": ssl,
        }
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(SCRIPT), "exec"), namespace)

        opened = []

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        def fake_urlopen(url):
            opened.append(url)
            if url.endswith("/product"):
                raise HTTPError(url, 404, "raw response text", None, None)
            if url.endswith("/contact"):
                raise URLError(ConnectionRefusedError("private transport detail"))
            return Response()

        namespace["urlopen"] = fake_urlopen
        result = {"route_preflight": [], "safe_failure_codes": []}
        routes = {
            "home": "http://localhost/home",
            "product": "http://localhost/product",
            "contact_ja": "http://localhost/contact",
        }
        ready = namespace["preflight_routes"](routes, result)

        self.assertEqual(["http://localhost/home", "http://localhost/product", "http://localhost/contact"], opened)
        self.assertEqual({"home": True, "product": False, "contact_ja": False}, ready)
        self.assertEqual(
            [
                {"route": "home", "status": 200, "exception_category": None, "passed": True},
                {"route": "product", "status": 404, "exception_category": None, "passed": False},
                {"route": "contact_ja", "status": None, "exception_category": "connection_error", "passed": False},
            ],
            result["route_preflight"],
        )
        self.assertEqual("home:200,product:404,contact_ja:connection_error", namespace["preflight_summary"](result))
        self.assertEqual(["route_status_mismatch", "route_unreachable"], result["safe_failure_codes"])


if __name__ == "__main__":
    unittest.main()
