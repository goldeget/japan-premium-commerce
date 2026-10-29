from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE = ROOT / "tests" / "procurement" / "ci_acceptance.sh"


def snapshot(status="ok"):
    return {
        "status": status, "shop_id": 1, "database_select_1": True,
        "disk_free_ratio": {"ok": 0.8, "warning": 0.08, "critical": 0.04}[status],
        "notification_counts": {
            "backlog": 0, "future_retry": 0, "undelivered_events": 0,
            "failed": 0, "uncertain": 0, "oldest_stale_age_seconds": 0,
        },
    }


class HealthSnapshotAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.source = ACCEPTANCE.read_text(encoding="utf-8")
        self.validator = self.source.split("<<'PYHEALTH'\n", 1)[1].split("\nPYHEALTH", 1)[0]

    def run_validator(self, raw, exit_code):
        with tempfile.TemporaryDirectory(prefix="health-outcome-") as directory:
            base = Path(directory)
            private_input = base / "private.json"
            public_output = base / "outcome.json"
            private_input.write_text(raw, encoding="utf-8")
            run = subprocess.run(
                [sys.executable, "-c", self.validator, str(private_input), str(public_output), str(exit_code)],
                capture_output=True, text=True, check=False, timeout=10,
            )
            self.assertTrue(public_output.is_file(), run.stderr)
            public_text = public_output.read_text(encoding="utf-8")
            return run, json.loads(public_text), public_text

    def test_health_phase_is_required_and_uses_private_stdout(self):
        required = re.search(r"^required = (\([^\n]+\))$", self.source, re.MULTILINE)
        self.assertIsNotNone(required)
        self.assertIn("notifications_health", ast.literal_eval(required.group(1)))
        self.assertIn("run_phase notifications_health health_snapshot_acceptance", self.source)
        body = self.source.split("health_snapshot_acceptance() {", 1)[1].split("\n}\nrun_phase notifications_health", 1)[0]
        self.assertIn('behavior notifications_health || return "$?"', body)
        self.assertIn('>"$private_dir/health-native.json"', body)
        self.assertNotIn('>"$QA_ARTIFACT_DIR/health-native.json"', body)

    def test_observed_ok_warning_and_critical_use_their_real_exit_codes(self):
        for status, exit_code in (("ok", 0), ("warning", 1), ("critical", 2)):
            with self.subTest(status=status):
                run, outcome, _ = self.run_validator(json.dumps(snapshot(status)), exit_code)
                self.assertEqual(0, run.returncode, run.stderr)
                self.assertTrue(outcome["passed"])
                self.assertEqual(status, outcome["snapshot"]["status"])
                self.assertEqual(exit_code, outcome["exit_code"])
                self.assertFalse(outcome["bootstrap_side_effects_instrumented"])

    def test_unavailable_and_mismatched_exit_do_not_become_valid_snapshots(self):
        for raw, exit_code in ((json.dumps(snapshot()), 1), ("", 3), ("private-health-marker", 0)):
            with self.subTest(exit_code=exit_code, raw=raw[:12]):
                run, outcome, public_text = self.run_validator(raw, exit_code)
                self.assertNotEqual(0, run.returncode)
                self.assertFalse(outcome["passed"])
                self.assertNotIn("snapshot", outcome)
                self.assertNotIn("private-health-marker", public_text + run.stdout + run.stderr)

    def test_cross_shop_extra_fields_and_invalid_metrics_are_redacted(self):
        invalid = []
        value = snapshot(); value["shop_id"] = 2; invalid.append(value)
        value = snapshot(); value["password"] = "private-health-marker"; invalid.append(value)
        value = snapshot(); value["notification_counts"]["failed"] = -1; invalid.append(value)
        value = snapshot(); value["notification_counts"]["failed"] = True; invalid.append(value)
        value = snapshot(); value["disk_free_ratio"] = True; invalid.append(value)
        value = snapshot(); value["disk_free_ratio"] = float("nan"); invalid.append(value)
        for value in invalid:
            with self.subTest(value=value):
                run, outcome, text = self.run_validator(json.dumps(value), 0)
                self.assertNotEqual(0, run.returncode)
                self.assertFalse(outcome["passed"])
                self.assertNotIn("snapshot", outcome)
                self.assertNotIn("private-health-marker", text + run.stdout + run.stderr)

    def test_duplicate_json_keys_are_rejected_without_publishing_raw_data(self):
        raw = json.dumps(snapshot()).replace('"status": "ok"', '"status": "private-health-marker", "status": "ok"')
        run, outcome, text = self.run_validator(raw, 0)
        self.assertNotEqual(0, run.returncode)
        self.assertFalse(outcome["passed"])
        self.assertNotIn("private-health-marker", text + run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
