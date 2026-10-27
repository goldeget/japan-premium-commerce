"""Lock the synthetic Lighthouse and axe acceptance path into isolated CI."""
from __future__ import annotations

import ast
import json
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
