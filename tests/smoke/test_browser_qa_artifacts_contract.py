"""Keep browser QA failures and execution logs in the retained artifact bundle."""
from __future__ import annotations

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

    def test_browser_qa_runs_independently_then_aggregates_failures(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for step_name, step_id in (
            ("Verify official ORDENOWA brand upload and publish in Chromium", "brand_browser_qa"),
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

    def test_checkout_restore_is_unconditional_and_final_gate_requires_successful_override_and_restore(self) -> None:
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
        self.assertIn('"$verification_phase" "$failure_status"', script)
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


if __name__ == "__main__":
    unittest.main()
