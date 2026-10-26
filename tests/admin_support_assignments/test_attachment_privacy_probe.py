"""Behavior contracts for the browser attachment probe; no browser is started."""
from __future__ import annotations

import unittest

from tests.e2e.test_ci_customer_support_browser_contract import load_script


class ProbeDriver:
    def __init__(self, response):
        self.response = response

    def execute_async_script(self, script, href, marker):
        return self.response


class AttachmentPrivacyProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.support = load_script()

    def probe(self, response):
        return self.support.attachment_visible_to_session(
            ProbeDriver(response), "http://localhost:18080/admin/synthetic-attachment", "SYNTHETIC_ONLY"
        )

    def test_transport_errors_and_server_failures_cannot_count_as_privacy_denial(self):
        for response in (None, {}, {"status": 0, "contentMatch": False},
                         {"status": 500, "contentMatch": False},
                         {"status": 200, "contentMatch": "false"}):
            with self.subTest(response=response), self.assertRaises(AssertionError):
                self.probe(response)

    def test_attachment_content_is_a_leak_even_with_a_denied_status(self):
        for status in (200, 403, 404, 500):
            with self.subTest(status=status):
                self.assertTrue(self.probe({"status": status, "contentMatch": True}))

    def test_completed_denials_and_login_pages_without_attachment_content_are_denied(self):
        for status in (200, 401, 403, 404):
            with self.subTest(status=status):
                self.assertFalse(self.probe({"status": status, "contentMatch": False}))


if __name__ == "__main__":
    unittest.main()
