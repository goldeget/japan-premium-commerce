"""Ensure cross-customer address evidence stays limited to booleans."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT_MODULE = ROOT / "tests" / "e2e" / "customer_address_isolation_result.py"
SPEC = importlib.util.spec_from_file_location("customer_address_isolation_result", RESULT_MODULE)
assert SPEC and SPEC.loader
RESULTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RESULTS)


class CustomerAddressIsolationResultContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.passed = {key: True for key in RESULTS.CUSTOMER_ADDRESS_ISOLATION_RESULT_KEYS}

    def test_passed_result_requires_exact_allowlisted_boolean_keys(self) -> None:
        self.assertTrue(RESULTS.validate_payload(self.passed, require_passed=True))

        missing = dict(self.passed)
        missing.pop("foreign_address_content_absent")
        self.assertFalse(RESULTS.validate_payload(missing, require_passed=False))

        extra = dict(self.passed, email="customer@example.invalid")
        self.assertFalse(RESULTS.validate_payload(extra, require_passed=False))

    def test_result_values_must_be_booleans_and_success_requires_all_true(self) -> None:
        partial = dict(self.passed, owner_fresh_readback_unchanged=False)
        self.assertTrue(RESULTS.validate_payload(partial, require_passed=False))
        self.assertFalse(RESULTS.validate_payload(partial, require_passed=True))

        truthy_string = dict(self.passed, foreign_edit_form_absent="yes")
        self.assertFalse(RESULTS.validate_payload(truthy_string, require_passed=False))

        integer = dict(self.passed, foreign_edit_form_absent=1)
        self.assertFalse(RESULTS.validate_payload(integer, require_passed=False))

    def test_safe_result_drops_unlisted_and_non_boolean_values(self) -> None:
        supplied = dict(self.passed)
        supplied["owner_fresh_readback_unchanged"] = 1
        supplied["address_id"] = "private fixture identifier"

        result = RESULTS.safe_customer_address_isolation_result(supplied)

        self.assertEqual(set(result), set(RESULTS.CUSTOMER_ADDRESS_ISOLATION_RESULT_KEYS))
        self.assertFalse(result["owner_fresh_readback_unchanged"])
        self.assertTrue(all(type(value) is bool for value in result.values()))
        self.assertNotIn("private fixture identifier", repr(result))


if __name__ == "__main__":
    unittest.main()
