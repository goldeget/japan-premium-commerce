"""Guard the rendered Korean login's email identifier and password recovery wording."""
from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parents[2]


class KoreanCustomerLoginContractTests(unittest.TestCase):
    def test_safe_url_metadata_reports_route_shape_without_query_values(self) -> None:
        browser_flow_path = ROOT / "tests" / "e2e" / "verify_customer_account_browser.py"
        syntax_tree = ast.parse(browser_flow_path.read_text(encoding="utf-8"))
        helper_nodes = [
            node
            for node in syntax_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"safe_same_origin_path", "safe_controller_category", "safe_url_metadata"}
        ]
        namespace = {
            "BASE": "https://shop.example.test",
            "parse_qs": parse_qs,
            "re": re,
            "unquote": unquote,
            "urlparse": urlparse,
        }
        compiled_helpers = compile(
            ast.Module(body=helper_nodes, type_ignores=[]),
            str(browser_flow_path),
            "exec",
        )
        exec(compiled_helpers, namespace)

        metadata = namespace["safe_url_metadata"](
            "https://shop.example.test/ログイン?controller=authentication&id_lang=3&token=secret-token&email=private%40example.test"
        )
        self.assertTrue(metadata["same_origin"])
        self.assertTrue(metadata["id_lang_present"])
        self.assertTrue(metadata["controller_present"])
        self.assertEqual(metadata["controller_category"], "authentication")
        self.assertTrue(metadata["path_has_non_ascii"])
        self.assertEqual(metadata["path"], "/<redacted>")
        self.assertEqual(metadata["query_key_names"], ["controller", "id_lang"])
        self.assertNotIn("secret-token", repr(metadata))
        self.assertNotIn("private@example.test", repr(metadata))
        self.assertEqual(
            namespace["safe_same_origin_path"]("https://shop.example.test/a7"),
            "/<redacted>",
        )
        self.assertEqual(
            namespace["safe_same_origin_path"]("https://shop.example.test/ko/identity"),
            "/ko/identity",
        )
        self.assertFalse(
            namespace["safe_url_metadata"]("https://other.example.test/login")["same_origin"]
        )

        other_controller = namespace["safe_url_metadata"](
            "https://shop.example.test/index.php?controller=unknown%40private"
        )
        self.assertEqual(other_controller["controller_category"], "other")
        self.assertNotIn("unknown@private", repr(other_controller))

    def test_browser_redirect_initiator_is_reduced_to_a_safe_scope(self) -> None:
        browser_flow_path = ROOT / "tests" / "e2e" / "verify_customer_account_browser.py"
        syntax_tree = ast.parse(browser_flow_path.read_text(encoding="utf-8"))
        helper = next(
            node
            for node in syntax_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "safe_initiator_scope"
        )
        namespace = {
            "BASE": "https://shop.example.test",
            "unquote": unquote,
            "urlparse": urlparse,
        }
        exec(compile(ast.Module(body=[helper], type_ignores=[]), str(browser_flow_path), "exec"), namespace)

        self.assertEqual(
            namespace["safe_initiator_scope"]("https://shop.example.test/themes/kuranea/assets/app.js"),
            "kuranea_theme",
        )
        self.assertEqual(
            namespace["safe_initiator_scope"]("https://shop.example.test/modules/kuraneabusinessprofile/app.js"),
            "kuranea_module",
        )
        self.assertEqual(
            namespace["safe_initiator_scope"]("https://external.example.test/app.js"),
            "external",
        )

    def test_korean_login_failure_summary_exposes_inner_wait_and_frame_scope_safely(self) -> None:
        browser_flow_path = ROOT / "tests" / "e2e" / "verify_customer_account_browser.py"
        syntax_tree = ast.parse(browser_flow_path.read_text(encoding="utf-8"))
        helper_names = {
            "safe_korean_login_stage",
            "safe_document_frame_scope",
            "compact_korean_login_failure_summary",
        }
        helper_nodes = [
            node
            for node in syntax_tree.body
            if isinstance(node, ast.FunctionDef) and node.name in helper_names
        ]
        self.assertEqual({node.name for node in helper_nodes}, helper_names)

        namespace: dict[str, object] = {
            "re": re,
            "KOREAN_LOGIN_STAGES": {
                "korean_storefront_home",
                "korean_language_selector",
                "korean_language_destination",
                "korean_sign_in_link",
                "korean_login_page_navigation",
                "korean_login_form",
                "korean_email_field",
                "korean_password_reset_link",
            },
        }
        exec(
            compile(ast.Module(body=helper_nodes, type_ignores=[]), str(browser_flow_path), "exec"),
            namespace,
        )
        diagnostics = {
            "stage": "korean_password_reset_link",
            "failed_stage_elapsed_ms": 30_715,
            "document_language": "ja-JP",
            "final_url_metadata": {"path": "/<redacted>", "same_origin": True},
            "reset_link_before_wait_anchor_count": 1,
            "reset_link_before_wait_href_present": True,
            "reset_link_before_wait_visible": True,
            "reset_link_before_wait_computed_display": "block",
            "reset_link_before_wait_computed_visibility": "visible",
            "reset_link_before_wait_text_identifies_password_reset": True,
            "reset_link_before_wait_aria_label_identifies_password_reset": False,
            "reset_link_before_wait_href_metadata": {
                "path": "/ko/<redacted>",
                "same_origin": True,
                "query_key_names": ["back"],
            },
            "reset_wait_navigation_elapsed_ms": 1_200,
            "reset_wait_navigation_document_language": "ja-JP",
            "reset_wait_navigation_url_metadata": {"path": "/<redacted>", "same_origin": True},
            "reset_link_navigation_timeline": [
                {
                    "event": "beforeunload",
                    "elapsed_ms": 1_200,
                    "route_metadata": {"path": "/ko/<redacted>", "same_origin": True},
                    "document_language": "ko-KR",
                    "ready_state": "complete",
                    "navigation_type": "navigate",
                    "navigation_redirect_count": 0,
                    "navigation_response_end_ms": 500,
                    "interaction_click_count": 0,
                    "interaction_trusted_click_count": 0,
                    "interaction_login_recovery_link_click_count": 0,
                    "interaction_login_form_submit_count": 0,
                    "interaction_other_form_submit_count": 0,
                    "persisted": False,
                }
            ],
            "document_navigation_events": [
                {
                    "event": "document_request",
                    "route_metadata": {
                        "path": "/ko/<redacted>",
                        "controller_category": "",
                        "query_key_names": ["back"],
                        "same_origin": True,
                    },
                    "redirect_from_metadata": {},
                    "status_code": 200,
                    "initiator_type": "other",
                    "initiator_scope": "unknown",
                    "initiator_stack_depth": 0,
                    "frame_scope": "top_frame",
                },
                {
                    "event": "document_request",
                    "route_metadata": {
                        "path": "/index.php",
                        "controller_category": "authentication",
                        "query_key_names": ["controller"],
                        "same_origin": True,
                    },
                    "redirect_from_metadata": {},
                    "status_code": 404,
                    "initiator_type": "other",
                    "initiator_scope": "unknown",
                    "initiator_stack_depth": 0,
                    "frame_scope": "top_frame",
                },
            ],
            "private_sentinel": "never-expose-this",
        }

        summary = namespace["compact_korean_login_failure_summary"](diagnostics)
        encoded = json.dumps(summary, ensure_ascii=True, sort_keys=True)
        self.assertEqual(summary["inner_stage"], "korean_password_reset_link")
        self.assertEqual(summary["reset_link_before_wait"]["anchor_count"], 1)
        self.assertTrue(summary["reset_link_before_wait"]["visible"])
        self.assertEqual(summary["navigation_events"][0]["frame_scope"], "top_frame")
        self.assertEqual(summary["reset_wait_navigation"]["timeline"][0]["interaction_click_count"], 0)
        self.assertEqual(
            summary["reset_wait_navigation"]["timeline"][0]["interaction_login_form_submit_count"], 0
        )
        self.assertLess(len(encoded), 3_500)
        self.assertNotIn("never-expose-this", encoded)

        long_route = {
            "path": ("/<redacted>" * 14)[:160],
            "controller_category": "authentication",
            "query_key_names": ["back", "controller", "id_lang", "isolang", "lang"],
            "same_origin": True,
            "path_has_non_ascii": False,
            "path_has_percent_escape": False,
            "back_present": True,
        }
        long_event = {
            "event": "document_request",
            "route_metadata": long_route,
            "redirect_from_metadata": long_route,
            "status_code": 599,
            "initiator_type": "serviceWorker",
            "initiator_scope": "prestashop_module",
            "initiator_stack_depth": 20,
            "frame_scope": "subframe",
        }
        long_diagnostics = dict(diagnostics)
        long_diagnostics.update(
            {
                "final_url_metadata": long_route,
                "reset_link_before_wait_href_metadata": long_route,
                "reset_wait_navigation_url_metadata": long_route,
                "reset_link_navigation_timeline": [
                    {"event": "beforeunload", "route_metadata": long_route},
                    {"event": "pagehide", "route_metadata": long_route},
                ],
                "document_navigation_events": [long_event] * 4,
            }
        )
        long_encoded = json.dumps(
            namespace["compact_korean_login_failure_summary"](long_diagnostics),
            ensure_ascii=True,
            sort_keys=True,
        )
        self.assertLess(
            len("::error title=Korean customer login wait details::") + len(long_encoded),
            4_096,
        )
        self.assertLess(
            len("ORDENOWA_KOREAN_LOGIN_STAGE_SAFE_STATE=") + len(long_encoded),
            4_096,
        )

        frame_scope = namespace["safe_document_frame_scope"]
        self.assertEqual(frame_scope("main-frame-secret", "main-frame-secret"), "top_frame")
        self.assertEqual(frame_scope("subframe-secret", "main-frame-secret"), "subframe")
        self.assertEqual(frame_scope("subframe-secret", None), "unknown")

    def test_document_navigation_events_classify_main_and_subframes(self) -> None:
        browser_flow_path = ROOT / "tests" / "e2e" / "verify_customer_account_browser.py"
        syntax_tree = ast.parse(browser_flow_path.read_text(encoding="utf-8"))
        helper_names = {
            "safe_same_origin_path",
            "safe_controller_category",
            "safe_url_metadata",
            "safe_initiator_scope",
            "safe_document_frame_scope",
            "top_level_frame_id",
            "document_navigation_events",
        }
        helper_nodes = [
            node
            for node in syntax_tree.body
            if isinstance(node, ast.FunctionDef) and node.name in helper_names
        ]
        self.assertEqual({node.name for node in helper_nodes}, helper_names)

        class FakeDriver:
            def execute_cdp_cmd(self, command: str, _params: dict) -> dict:
                if command != "Page.getFrameTree":
                    raise AssertionError("unexpected CDP command")
                return {"frameTree": {"frame": {"id": "opaque-main-frame-id"}}}

            def get_log(self, _log_type: str) -> list[dict[str, str]]:
                messages = [
                    {
                        "method": "Network.requestWillBeSent",
                        "params": {
                            "type": "Document",
                            "requestId": "main-request",
                            "frameId": "opaque-main-frame-id",
                            "request": {"url": "https://shop.example.test/ko/login"},
                            "initiator": {"type": "other"},
                        },
                    },
                    {
                        "method": "Network.responseReceived",
                        "params": {
                            "type": "Document",
                            "requestId": "main-request",
                            "response": {"status": 200},
                        },
                    },
                    {
                        "method": "Network.requestWillBeSent",
                        "params": {
                            "type": "Document",
                            "requestId": "sub-request",
                            "frameId": "opaque-sub-frame-id",
                            "request": {"url": "https://shop.example.test/index.php?controller=authentication"},
                            "initiator": {"type": "other"},
                        },
                    },
                    {
                        "method": "Network.responseReceived",
                        "params": {
                            "type": "Document",
                            "requestId": "sub-request",
                            "response": {"status": 404},
                        },
                    },
                ]
                return [
                    {"message": json.dumps({"message": message})}
                    for message in messages
                ]

        webdriver_namespace = type("WebDriverNamespace", (), {"Chrome": object})
        namespace = {
            "BASE": "https://shop.example.test",
            "json": json,
            "parse_qs": parse_qs,
            "re": re,
            "unquote": unquote,
            "urlparse": urlparse,
            "webdriver": webdriver_namespace,
        }
        exec(
            compile(ast.Module(body=helper_nodes, type_ignores=[]), str(browser_flow_path), "exec"),
            namespace,
        )

        events = namespace["document_navigation_events"](FakeDriver())
        self.assertEqual([event["frame_scope"] for event in events], ["top_frame", "subframe"])
        self.assertEqual([event["status_code"] for event in events], [200, 404])
        self.assertNotIn("opaque-main-frame-id", repr(events))
        self.assertNotIn("opaque-sub-frame-id", repr(events))

    def test_account_browser_checks_korean_email_login_and_separate_password_recovery(self) -> None:
        browser_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(
            encoding="utf-8"
        )
        login_template = (
            ROOT / "themes" / "hummingbird" / "templates" / "customer" / "_partials" / "login-form.tpl"
        ).read_text(encoding="utf-8")
        language_template = (
            ROOT / "themes" / "hummingbird" / "modules" / "ps_languageselector" / "ps_languageselector.tpl"
        ).read_text(encoding="utf-8")
        signin_template = (
            ROOT / "themes" / "hummingbird" / "modules" / "ps_customersignin" / "ps_customersignin.tpl"
        ).read_text(encoding="utf-8")
        form_fields_template = (
            ROOT / "themes" / "hummingbird" / "templates" / "_partials" / "form-fields.tpl"
        ).read_text(encoding="utf-8")

        self.assertIn("def assert_korean_email_login_form", browser_flow)
        self.assertIn("assert_korean_email_login_form(driver, korean_login_state)", browser_flow)
        browser_check = browser_flow.split("def assert_korean_email_login_form", 1)[1].split(
            "\n\ndef ", 1
        )[0]
        for assertion in (
            'driver.get(f"{BASE}/")',
            'select.js-language-selector option[data-iso-code="ko"]',
            'driver.get(korean_language_url)',
            "#_desktop_ps_customersignin a[href], #_mobile_ps_customersignin a[href]",
            'driver.get(login_url)',
            'visible(driver, "#login-form")',
            'visible(driver, \'#login-form input[type="email"]\')',
            'get_attribute("name") != "email"',
            'get_attribute("type") != "email"',
            'document_language.startswith("ko")',
            'get_attribute("aria-label")',
            'label.get_attribute("for") == email_field_id',
            "aria_label or visible_label",
            "KOREAN_EMAIL_ACCESSIBLE_NAME.search(email_accessible_name)",
            "USER_ID_LOOKUP_ACCESSIBLE_NAME.search(email_accessible_name)",
            "PASSWORD_RESET_ACCESSIBLE_NAME.search(password_reset_name)",
            "USER_ID_LOOKUP_ACCESSIBLE_NAME.search(password_reset_name)",
        ):
            self.assertIn(assertion, browser_check)
        accessible_name_pattern = browser_flow.split(
            "KOREAN_EMAIL_ACCESSIBLE_NAME = re.compile(", 1
        )[1].split(")", 1)[0]
        for korean_email_term in ("이메일", r"전자\s*우편", r"메일\s*주소"):
            self.assertIn(korean_email_term, accessible_name_pattern)
        self.assertNotIn("e[", accessible_name_pattern.casefold())
        self.assertIn("korean-login-email", browser_flow)

        self.assertIn('select class="form-select js-language-selector"', language_template)
        self.assertIn('data-iso-code="{$language.iso_code}"', language_template)
        self.assertIn('{url entity=\'language\' id=$language.id_lang}', language_template)
        self.assertIn("{$urls.pages.authentication}", signin_template)
        self.assertIn('id="login-form"', login_template)
        self.assertIn('aria-label="{$field.label}"', form_fields_template)
        self.assertIn('for="{$id_prefix}field-{$field.name}"', form_fields_template)
        self.assertNotIn('driver.get(f"{BASE}/ko/login")', browser_check)
        self.assertIn('href="{$urls.pages.password}"', login_template)
        self.assertIn("Forgot your password?", login_template)
        self.assertNotIn("username recovery", login_template.casefold())
        self.assertNotIn("아이디 찾기", login_template)

    def test_korean_login_timeout_reports_the_exact_wait_and_safe_rendered_page_state(self) -> None:
        browser_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(
            encoding="utf-8"
        )
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        for stage in (
            "korean_storefront_home",
            "korean_language_selector",
            "korean_language_destination",
            "korean_sign_in_link",
            "korean_login_page_navigation",
            "korean_login_form",
            "korean_email_field",
            "korean_password_reset_link",
        ):
            self.assertIn(stage, browser_flow)
        self.assertIn("def emit_korean_login_diagnostics", browser_flow)
        self.assertIn("def safe_url_metadata", browser_flow)
        self.assertIn('korean_login_state: dict[str, object]', browser_flow)
        self.assertIn('for key in (\n                "document_language",', browser_flow)
        self.assertIn('"ORDENOWA_KOREAN_LOGIN_SAFE_STATE="', browser_flow)
        self.assertIn('emit_korean_login_diagnostics(driver, korean_login_state)', browser_flow)
        self.assertIn('korean_login_diagnostics=$(rg \'^ORDENOWA_KOREAN_LOGIN_SAFE_STATE=\'', workflow)
        self.assertIn('korean_login_stage_diagnostics=$(rg \'^ORDENOWA_KOREAN_LOGIN_STAGE_SAFE_STATE=\'', workflow)
        self.assertIn("ORDENOWA_KOREAN_LOGIN_SAFE_STATE", workflow)
        self.assertIn("ORDENOWA_KOREAN_LOGIN_STAGE_SAFE_STATE", workflow)
        self.assertIn("inner_stage=", browser_flow)
        for transition_fact in (
            'state["language_url_metadata"] = safe_url_metadata(korean_language_url)',
            'state["sign_in_url_metadata"] = safe_url_metadata(login_url)',
            '"final_url_metadata": safe_url_metadata',
            '"email_label_document_language"',
            '"login_navigation_document_language"',
            '"failed_stage_elapsed_ms"',
            '"reset_link_before_wait_href_present"',
            '"reset_link_before_wait_visible"',
            '"reset_link_before_wait_computed_display"',
            '"reset_link_before_wait_computed_visibility"',
            '"reset_link_before_wait_text_length"',
            '"reset_link_before_wait_aria_label_text_length"',
            '"reset_link_before_wait_url_metadata"',
            '"reset_wait_navigation_elapsed_ms"',
            '"reset_wait_navigation_url_metadata"',
            '"reset_wait_navigation_document_language"',
            '"reset_link_navigation_timeline"',
            '"document_navigation_events"',
            '"controller_category"',
            '"initiator_type"',
            '"initiator_scope"',
            '"initiator_stack_depth"',
            '"ORDENOWA_KOREAN_LOGIN_NAVIGATION_SAFE_STATE="',
            '::error title=Korean customer login navigation::{navigation_annotation}',
            '::error title=Korean customer login wait details::{stage_annotation}',
            '"frame_scope": safe_document_frame_scope',
            "const interactionKey = '__ordenowaKoreanLoginInteractions';",
            "interactionState.trusted_click_count",
            "interactionState.login_recovery_link_click_count",
            "const keyName = form?.id === 'login-form' ? 'login_form_submit_count' : 'other_form_submit_count'",
            '"interaction_login_recovery_link_click_count"',
            '"interaction_login_form_submit_count"',
            "addEventListener('beforeunload'",
            "addEventListener('pagehide'",
            '"performance": "ALL"',
            '"query_key_names"',
            '"id_lang_present"',
            '"path_has_non_ascii"',
        ):
            self.assertIn(transition_fact, browser_flow)
        diagnostics = browser_flow.split("def emit_korean_login_diagnostics", 1)[1].split(
            "\n\ndef ", 1
        )[0]
        for safe_field in (
            '"path": safe_same_origin_path',
            '"document_language"',
            '"korean_language_option_count"',
            '"customer_sign_in_link_count"',
            '"login_form_visible"',
            '"email_field_visible"',
            '"email_label_present"',
            '"password_reset_link_count"',
        ):
            self.assertIn(safe_field, diagnostics)
        self.assertNotIn("password_value", diagnostics)
        self.assertNotIn('"text":', diagnostics)
        self.assertNotIn('"aria_label":', diagnostics)


if __name__ == "__main__":
    unittest.main()
