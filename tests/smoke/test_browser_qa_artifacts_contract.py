"""Keep browser QA failures and execution logs in the retained artifact bundle."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "fresh-install.yml"
STOREFRONT_E2E = ROOT / "tests" / "e2e" / "verify_storefront_browser.py"
PRODUCT_ADMIN_E2E = ROOT / "tests" / "e2e" / "verify_product_admin_browser.py"
FRESH_INSTALL = ROOT / "tests" / "smoke" / "fresh_install.sh"


class BrowserQAArtifactsContractTests(unittest.TestCase):
    def test_initial_storefront_browser_output_is_saved_to_the_qa_artifact(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        step = workflow.split(
            "- name: Verify real product detail and cart in Chromium (no payment)", 1
        )[1].split("- name:", 1)[0]

        self.assertIn("storefront-product-cart-e2e.log", step)
        self.assertIn("2>&1 | tee", step)
        self.assertIn("if: always()", workflow)
        self.assertIn('path: ${{ runner.temp }}/ordenowa-browser-qa/', workflow)
        self.assertIn("retention-days: 30", workflow)

    def test_successful_browser_qa_requires_desktop_and_mobile_screenshots(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("- name: Verify browser QA screenshot coverage", workflow)
        verification = workflow.split(
            "- name: Verify browser QA screenshot coverage", 1
        )[1].split("- name:", 1)[0]
        self.assertIn('RESET_EMAIL_BRAND_BROWSER_QA_OUTCOME: ${{ steps.reset_email_brand_browser_qa.outcome }}', verification)
        self.assertIn('"$RESET_EMAIL_BRAND_BROWSER_QA_OUTCOME" == success', verification)

        for screenshot in (
            "brand-desktop-published.png",
            "brand-mobile-published.png",
            "brand-english-published.png",
            "brand-admin-history-change-diff.png",
            "admin-security-view-only-settings-korean.png",
            "admin-security-view-only-dashboard-korean.png",
            "admin-security-view-only-orders-korean.png",
            "admin-security-legacy-profile-korean.png",
            "admin-security-legacy-bank-accounts-korean.png",
            "admin-security-legacy-product-manager-korean.png",
            "admin-security-legacy-catalog-review-korean.png",
            "password-reset-email-requested.png",
            "password-reset-email-logo.png",
            "desktop-customer-account-created.png",
            "mobile-customer-account-created.png",
            "product-admin-created-desktop.png",
            "product-admin-distinct-combination-stock-desktop.png",
            "product-admin-mobile.png",
            "desktop-home.png",
            "mobile-home.png",
            "checkout-desktop.png",
            "checkout-mobile.png",
            "password-reset-email-brand-e2e.log",
        ):
            with self.subTest(screenshot=screenshot):
                self.assertIn(screenshot, verification)

        self.assertIn("if: always()", verification)
        self.assertIn('if-no-files-found: error', workflow.split(
            "- name: Upload browser QA screenshots", 1
        )[1].split("- name:", 1)[0])

    def test_successful_back_office_recovery_requires_reset_screenshots_and_log(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        verification = workflow.split(
            "- name: Verify browser QA screenshot coverage", 1
        )[1].split("- name:", 1)[0]

        self.assertIn(
            "ADMIN_RECOVERY_BROWSER_OUTCOME: ${{ steps.admin_recovery_browser.outcome }}",
            verification,
        )
        self.assertIn(
            "ADMIN_RECOVERY_FIXTURE_OUTCOME: ${{ steps.admin_recovery_fixture.outcome }}",
            verification,
        )
        self.assertIn('if [[ "$ADMIN_RECOVERY_FIXTURE_OUTCOME" == success ]]; then', verification)
        self.assertIn("admin-recovery-fixture.log", verification)
        self.assertIn('if [[ "$ADMIN_RECOVERY_BROWSER_OUTCOME" == success ]]; then', verification)
        for artifact in (
            "admin-password-reset-e2e.log",
            "admin-password-reset-request.png",
            "admin-password-reset-login.png",
        ):
            with self.subTest(artifact=artifact):
                self.assertIn(artifact, verification)

    def test_pwa_success_requires_account_and_logout_captures_for_all_locale_viewport_cells(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        verification = workflow.split(
            "- name: Verify browser QA screenshot coverage", 1
        )[1].split("- name:", 1)[0]

        for viewport in ("desktop", "mobile"):
            for locale in ("ja", "en", "ko"):
                for capture in ("installability", "offline-fallback", "account", "logged-out-account"):
                    artifact = f"pwa-{viewport}-{locale}-{capture}.png"
                    with self.subTest(artifact=artifact):
                        self.assertTrue(artifact in verification, f"missing required PWA capture: {artifact}")

    def test_brand_stale_publish_target_is_forwarded_to_the_step_summary(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        step = workflow.split(
            "- name: Verify official ORDENOWA brand upload and publish in Chromium", 1
        )[1].split("- name:", 1)[0]

        self.assertIn('stale_target_line = latest_line("ORDENOWA_PUBLISH_STALE_TARGET=")', step)
        self.assertIn('for line in (diagnostics_line, stale_target_line, admin_login_safe_state):', step)
        self.assertIn('summary.write(line + "\\n")', step)
        self.assertNotIn("rg ", step)

    def test_browser_qa_runs_independently_then_aggregates_failures(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for step_name, step_id in (
            ("Verify official ORDENOWA brand upload and publish in Chromium", "brand_browser_qa"),
            (
                "Verify the published ORDENOWA password-reset email logo in Chromium",
                "reset_email_brand_browser_qa",
            ),
            (
                "Verify customer registration, email login, logout, password reset, and my page in Chromium",
                "account_browser_qa",
            ),
            ("Verify Korean admin native product create and edit in Chromium", "product_admin_browser_qa"),
            (
                "Verify real product detail and cart in Chromium (no payment)",
                "storefront_browser_qa",
            ),
            (
                "Verify browser customer search, Japan checkout, and unpaid offline order",
                "checkout_customer_browser_qa",
            ),
            (
                "Verify a separate admin session can view both browser orders",
                "checkout_admin_browser_qa",
            ),
        ):
            with self.subTest(step=step_name):
                step = workflow.split(f"- name: {step_name}", 1)[1].split("- name:", 1)[0]
                self.assertIn(f"id: {step_id}", step)
                self.assertIn("continue-on-error: true", step)

        self.assertIn("- name: Aggregate browser QA and postal verification failures", workflow)
        aggregate = workflow.split(
            "- name: Aggregate browser QA and postal verification failures", 1
        )[1].split("- name:", 1)[0]
        self.assertIn("if: always()", aggregate)
        for step_id in (
            "brand_browser_qa",
            "reset_email_brand_browser_qa",
            "account_browser_qa",
            "product_admin_browser_qa",
            "storefront_browser_qa",
            "checkout_override",
            "checkout_customer_browser_qa",
            "checkout_order_persistence",
            "checkout_admin_browser_qa",
            "checkout_restore",
            "checkout_gate_after_order",
            "fresh_install_restart",
            "postal_import",
            "postal_verify",
        ):
            self.assertIn(f"steps.{step_id}.outcome", aggregate)

        browser_artifact = workflow.index("- name: Upload browser QA screenshots")
        postal_verify = workflow.index("- name: Verify official Japan Post import contains national address data")
        self.assertLess(browser_artifact, postal_verify)
        self.assertLess(postal_verify, workflow.index("- name: Aggregate browser QA and postal verification failures"))
        self.assertLess(
            workflow.index("- name: Aggregate browser QA and postal verification failures"),
            workflow.index("- name: Capture bounded diagnostics on failure"),
        )

    def test_free_shipping_product_fixture_log_and_json_are_required_when_successful(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        coverage = workflow.split(
            "- name: Verify browser QA screenshot coverage", 1
        )[1].split("- name:", 1)[0]
        self.assertIn(
            'SHIPPING_PRODUCT_FIXTURE_OUTCOME: ${{ steps.shipping_product_fixture.outcome }}',
            coverage,
        )
        self.assertIn('if [[ "$SHIPPING_PRODUCT_FIXTURE_OUTCOME" == success ]]; then', coverage)
        self.assertIn("free-shipping-product-fixture.log", coverage)
        self.assertIn("free-shipping-product-fixture.json", coverage)

    def test_browser_order_checks_run_only_after_their_producer_succeeds(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        persistence = workflow.split(
            "- name: Verify saved browser orders are unpaid and retain Japan addresses", 1
        )[1].split("- name:", 1)[0]
        admin = workflow.split(
            "- name: Verify a separate admin session can view both browser orders", 1
        )[1].split("- name:", 1)[0]

        self.assertIn(
            "if: steps.checkout_customer_browser_qa.outcome == 'success'",
            persistence,
        )
        self.assertIn(
            "if: steps.checkout_customer_browser_qa.outcome == 'success' && "
            "steps.checkout_order_persistence.outcome == 'success'",
            admin,
        )

    def test_checkout_restore_is_unconditional_and_gate_rechecks_success_or_failure(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        restore = workflow.split("- name: Restore the fail-closed base checkout environment", 1)[1].split(
            "- name:", 1
        )[0]
        gate = workflow.split("- name: Recheck storefront checkout stays gated after unpaid CI order QA", 1)[1].split(
            "- name:", 1
        )[0]

        self.assertIn("id: checkout_restore", restore)
        self.assertIn("if: always()", restore)
        self.assertIn("id: checkout_gate_after_order", gate)
        self.assertIn("if: always()", gate)
        self.assertIn("steps.checkout_override.outcome == 'success'", gate)
        self.assertIn("steps.checkout_override.outcome == 'failure'", gate)
        self.assertIn("steps.checkout_restore.outcome == 'success'", gate)

    def test_storefront_browser_saves_a_failure_state_screenshot(self) -> None:
        browser_flow = STOREFRONT_E2E.read_text(encoding="utf-8")
        self.assertIn("    except Exception as error:", browser_flow)
        failure_handler = browser_flow.split("    except Exception as error:", 1)[1].split(
            "    finally:", 1
        )[0]

        self.assertIn('driver.save_screenshot(str(DEST / f"{label}-failure.png"))', failure_handler)

    def test_product_admin_browser_saves_a_failure_state_screenshot(self) -> None:
        browser_flow = PRODUCT_ADMIN_E2E.read_text(encoding="utf-8")
        failure_handler = browser_flow.split("    except Exception as error:", 1)[1].split(
            "    finally:", 1
        )[0]

        self.assertIn('driver.save_screenshot(str(DEST / "product-admin-failure.png"))', failure_handler)

    def test_fresh_install_reports_only_named_phase_and_exit_code_on_failure(self) -> None:
        script = FRESH_INSTALL.read_text(encoding="utf-8")

        self.assertIn("trap 'report_verification_failure \"$?\"' ERR", script)
        self.assertIn(
            "FRESH_INSTALL_VERIFICATION_FAILED phase=%s exit_code=%s",
            script,
        )
        self.assertIn('local failure_status=$1', script)
        self.assertIn('local sanitized_phase=${verification_phase:-unknown}', script)
        self.assertIn('local sanitized_status=$failure_status', script)
        self.assertIn(
            "::error title=Fresh install verification::FRESH_INSTALL_VERIFICATION_FAILED",
            script,
        )
        self.assertIn('"$sanitized_phase" "$sanitized_status"', script)
        self.assertNotIn("$BASH_COMMAND", script)
        self.assertNotIn('env |', script)
        for phase in (
            "restart_service_recovery",
            "restart_bootstrap_marker",
            "restart_persistent_files",
            "restart_admin_branding",
            "restart_jpy_currency",
            "restart_shop_identity_and_schema",
        ):
            with self.subTest(phase=phase):
                self.assertIn(f'verification_phase="{phase}"', script)

    def test_fresh_install_database_checks_have_static_failure_phases(self) -> None:
        script = FRESH_INSTALL.read_text(encoding="utf-8")
        checks = (
            ("initial_database_connectivity", "db_ok=$(db_query"),
            ("initial_database_theme", "theme=$(db_query"),
            ("initial_database_active_languages", "languages=$(db_query"),
            ("initial_database_default_language", "shop_default=$(db_query"),
            ("initial_database_checkout_route", "checkout_route=$(db_query"),
            ("initial_database_identity_route", "identity_route=$(db_query"),
            ("initial_database_password_route", "password_route=$(db_query"),
            ("initial_database_history_meta", "history_meta_count=$(db_query"),
            ("initial_database_history_route", "history_route=$(db_query"),
            ("initial_database_rewrite_settings", "checkout_rewriting=$(db_query"),
            (
                "initial_database_canonical_redirect",
                "canonical_redirect_before_restart=$(db_query",
            ),
            (
                "initial_database_route_migration_marker",
                "route_migration_marker=$(db_query",
            ),
            ("initial_database_default_currency", "default_currency=$(db_query"),
            ("initial_database_jpy_currency", "jpy_currency=$(db_query"),
            ("initial_database_jpy_translations", "jpy_translations=$(db_query"),
            ("initial_database_other_currency_state", "active_non_jpy=$(db_query"),
            ("initial_database_employee_locale", "employee_locale=$(db_query"),
            ("initial_database_postcode_module", "postcode_module=$(db_query"),
            ("initial_database_backoffice_module", "backoffice_module=$(db_query"),
            ("initial_database_backoffice_module_files", "for module_file in \\"),
            ("initial_database_japan_states", "postcode_states=$(db_query"),
            ("initial_database_postcode_address_table", "postcode_table=$(db_query"),
            ("initial_database_postcode_stage_table", "postcode_stage_table=$(db_query"),
            ("initial_database_postcode_stage_empty", "postcode_stage_rows=$(db_query"),
            ("initial_database_table_count", "table_count_before=$(db_query"),
        )

        self.assertTrue(
            'verification_phase="initial_database_shop_and_postcode_configuration"' not in script,
            "broad initial database phase still hides the individual failing check",
        )

        for phase, command in checks:
            with self.subTest(phase=phase):
                phase_marker = f'verification_phase="{phase}"'
                self.assertTrue(phase_marker in script, f"missing static phase {phase}")
                phase_position = script.index(phase_marker)
                next_phase_position = script.find(
                    'verification_phase="', phase_position + len(phase_marker)
                )
                if next_phase_position == -1:
                    next_phase_position = len(script)

                self.assertIn(command, script[phase_position:next_phase_position])

    def test_fresh_install_failure_phase_is_appended_to_step_summary(self) -> None:
        script = FRESH_INSTALL.read_text(encoding="utf-8")
        handler_start = script.index("report_verification_failure() {")
        handler_end = script.index("\n}\n", handler_start) + 2
        handler = script[handler_start:handler_end]

        with tempfile.TemporaryDirectory() as temporary_directory:
            summary = Path(temporary_directory) / "step-summary.md"
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    "verification_phase=restart_service_recovery\n"
                    f"{handler}\n"
                    "report_verification_failure 7\n",
                ],
                capture_output=True,
                check=False,
                env={
                    "PATH": os.environ["PATH"],
                    "GITHUB_STEP_SUMMARY": str(summary),
                    "SECRET_TOKEN": "must-not-be-printed",
                },
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                result.stderr,
                "FRESH_INSTALL_VERIFICATION_FAILED phase=restart_service_recovery exit_code=7\n"
                "::error title=Fresh install verification::FRESH_INSTALL_VERIFICATION_FAILED "
                "phase=restart_service_recovery exit_code=7\n",
            )
            self.assertTrue(summary.exists(), "failure phase was not written to the step summary")
            self.assertEqual(
                summary.read_text(encoding="utf-8"),
                "FRESH_INSTALL_VERIFICATION_FAILED phase=restart_service_recovery exit_code=7\n",
            )

    def test_fresh_install_error_annotation_sanitizes_workflow_command_fields(self) -> None:
        script = FRESH_INSTALL.read_text(encoding="utf-8")
        handler_start = script.index("report_verification_failure() {")
        handler_end = script.index("\n}\n", handler_start) + 2
        handler = script[handler_start:handler_end]

        result = subprocess.run(
            [
                "bash",
                "-c",
                "verification_phase=$'restart\\n::warning::injected'\n"
                f"{handler}\n"
                "report_verification_failure $'7\\n::add-mask::secret'\n",
            ],
            capture_output=True,
            check=False,
            env={"PATH": os.environ["PATH"]},
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertNotIn("::warning::injected", result.stderr)
        self.assertNotIn("::add-mask::secret", result.stderr)
        self.assertIn(
            "::error title=Fresh install verification::FRESH_INSTALL_VERIFICATION_FAILED "
            "phase=unknown exit_code=unknown\n",
            result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
