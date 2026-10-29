from __future__ import annotations

import json
import unittest

from safe_authenticated_outcome import _safe_failure
from safe_native_facebook_cases import collect_cases
from test_safe_native_facebook_cases import good_inputs


ALLOWED_TEMPLATES = (
    "@PrestaShop/Admin/Layout/admin_layout.html.twig",
    "@PrestaShopCore/Admin/Exception/403.html.twig",
    "@Modules/ps_mbo/views/templates/admin/error.html.twig",
    "@Modules/ps_facebook/views/templates/admin/configure.html.twig",
)


def safe_failure_details(template: object = None, line: object = None) -> dict:
    payload = {}
    if template is not None:
        payload["twig_template"] = template
    if line is not None:
        payload["twig_template_line"] = line
    return _safe_failure("helper_nonzero", 1, payload, include_details=True)


class SafeTwigDiagnosticsTests(unittest.TestCase):
    def test_shared_failure_filter_accepts_only_allowlisted_template_and_bounded_line_pairs(self) -> None:
        for template in ALLOWED_TEMPLATES:
            with self.subTest(template=template):
                details = safe_failure_details(template, 713)
                self.assertEqual(details["twig_template"], template)
                self.assertEqual(details["twig_template_line"], 713)

    def test_shared_failure_filter_rejects_urls_paths_unknown_namespaces_and_malformed_pairs(self) -> None:
        invalid_templates = (
            ("https://private.example/template.twig?token=SECRET", 713),
            ("/var/www/private/template.twig", 713),
            ("@Modules/other_module/private/template.twig", 713),
            ("@Modules/ps_facebook/../../private.twig", 713),
            (None, 713),
        )
        for template, line in invalid_templates:
            with self.subTest(template=template, line=line):
                details = safe_failure_details(template, line)
                self.assertNotIn("twig_template", details)
                self.assertNotIn("twig_template_line", details)
                serialized = json.dumps(details)
                self.assertNotIn("SECRET", serialized)
                self.assertNotIn("private.example", serialized)
                self.assertNotIn("/var/www", serialized)

        for line in (None, True, 0, 100001):
            with self.subTest(template=ALLOWED_TEMPLATES[-1], line=line):
                details = safe_failure_details(ALLOWED_TEMPLATES[-1], line)
                self.assertEqual(details.get("twig_template"), ALLOWED_TEMPLATES[-1])
                self.assertNotIn("twig_template_line", details)

    def test_facebook_failure_aggregate_forwards_only_safe_template_pair(self) -> None:
        raw, statuses = good_inputs()
        template = "@Modules/ps_facebook/views/templates/admin/configure.html.twig"
        raw["access_denied"] = json.dumps({
            "schema": 1,
            "passed": False,
            "failed_stage": "single_fresh_process_case_request",
            "exception_class": "Twig\\Error\\RuntimeError",
            "cause_class": "Symfony\\Component\\HttpKernel\\Exception\\AccessDeniedHttpException",
            "twig_template": template,
            "twig_template_line": 713,
            "final_uri": "http://localhost/admin-kuranea/?token=PRIVATE_URL_TOKEN",
            "native_body_token": "PRIVATE_BODY_TOKEN",
            "exception_message": "PRIVATE_EXCEPTION_MESSAGE",
        }).encode("utf-8")
        statuses["access_denied"] = 1

        result = collect_cases(raw, statuses)

        self.assertFalse(result["passed"])
        self.assertEqual(result["failed_case"], "access_denied")
        self.assertEqual(result["twig_template"], template)
        self.assertEqual(result["twig_template_line"], 713)
        serialized = json.dumps(result)
        for secret in ("localhost", "PRIVATE_URL_TOKEN", "PRIVATE_BODY_TOKEN", "PRIVATE_EXCEPTION_MESSAGE"):
            self.assertNotIn(secret, serialized)

    def test_facebook_failure_aggregate_does_not_emit_orphan_or_untrusted_template_fields(self) -> None:
        invalid_pairs = (
            ("https://private.example/template.twig?token=SECRET", 713),
            ("/var/www/private/template.twig", 713),
            (None, 713),
            ("@Modules/ps_facebook/views/templates/admin/configure.html.twig", 100001),
        )
        for template, line in invalid_pairs:
            with self.subTest(template=template, line=line):
                raw, statuses = good_inputs()
                payload = {
                    "schema": 1,
                    "passed": False,
                    "failed_stage": "single_fresh_process_case_request",
                    "exception_class": "Twig\\Error\\RuntimeError",
                    "twig_template_line": line,
                    "final_uri": "https://private.example/?token=SECRET",
                }
                if template is not None:
                    payload["twig_template"] = template
                raw["access_denied"] = json.dumps(payload).encode("utf-8")
                statuses["access_denied"] = 1

                result = collect_cases(raw, statuses)

                self.assertFalse(result["passed"])
                self.assertNotIn("twig_template", result)
                self.assertNotIn("twig_template_line", result)
                serialized = json.dumps(result)
                self.assertNotIn("SECRET", serialized)
                self.assertNotIn("private.example", serialized)


if __name__ == "__main__":
    unittest.main()
