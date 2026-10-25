from __future__ import annotations

import unittest

from tests.e2e.admin_locale_diagnostics import parse_admin_locale_response_diagnostic


class AdminLocaleResponseDiagnosticTests(unittest.TestCase):
    def test_missing_response_header_is_distinct_from_malformed_header(self) -> None:
        self.assertEqual(
            parse_admin_locale_response_diagnostic(None),
            "unavailable:missing_header",
        )
        self.assertEqual(
            parse_admin_locale_response_diagnostic("missing"),
            "unavailable:missing_header",
        )
        self.assertEqual(
            parse_admin_locale_response_diagnostic("unexpected response header"),
            "unavailable:invalid_diagnostic",
        )

if __name__ == "__main__":
    unittest.main()
