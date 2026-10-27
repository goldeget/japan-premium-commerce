#!/usr/bin/env python3
"""Validate redacted, boolean-only customer address isolation evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CUSTOMER_ADDRESS_ISOLATION_RESULT_KEYS = (
    "foreign_response_status_allowed",
    "foreign_response_same_shop",
    "foreign_response_network_backed",
    "foreign_response_target_matched",
    "foreign_session_authenticated_before_request",
    "foreign_session_network_backed_before_request",
    "owner_session_authenticated",
    "owner_session_network_backed",
    "foreign_session_authenticated",
    "foreign_session_network_backed",
    "foreign_edit_form_absent",
    "foreign_address_content_absent",
    "owner_fresh_readback_unchanged",
    "owner_fresh_readback_network_backed",
)


def safe_customer_address_isolation_result(result: object) -> dict[str, bool]:
    values = result if isinstance(result, dict) else {}
    return {key: values.get(key) is True for key in CUSTOMER_ADDRESS_ISOLATION_RESULT_KEYS}


def validate_payload(payload: Any, *, require_passed: bool) -> bool:
    if not isinstance(payload, dict) or set(payload) != set(CUSTOMER_ADDRESS_ISOLATION_RESULT_KEYS):
        return False
    if any(type(payload[key]) is not bool for key in CUSTOMER_ADDRESS_ISOLATION_RESULT_KEYS):
        return False
    return not require_passed or all(payload.values())


def validate_files(paths: list[Path], *, require_passed: bool) -> bool:
    if not paths:
        return False
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False
        if not validate_payload(payload, require_passed=require_passed):
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("files", nargs="+", type=Path)
    arguments = parser.parse_args()
    if not validate_files(arguments.files, require_passed=not arguments.allow_partial):
        print("FAIL: customer address isolation evidence is missing, malformed, or incomplete")
        return 1
    print("PASS: customer address isolation evidence contains only allowlisted booleans")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
