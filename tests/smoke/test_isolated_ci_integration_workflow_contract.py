"""Exercise CI outcome aggregation and evidence requirements without Docker."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/fresh-install.yml"
NEW_STEP_IDS = (
    "postcode_fixture", "tax_fixture", "shipping_product_fixture",
    "exemption_product_fixture",
    "variant_fixture", "cart_controls_browser_qa",
    "security_fixture", "admin_security_browser_qa", "reset_token_browser_qa",
    "pwa_browser_qa", "shipping_free_fixture", "shipping_free_admin_access", "shipping_free_admin_configure",
    "shipping_free_restart", "shipping_free_admin_readback",
    "shipping_free_customer_browser_qa", "shipping_free_osaka_mobile_browser_qa",
    "shipping_free_taxable_browser_qa", "shipping_free_order_persistence",
    "shipping_free_exemption_browser_qa",
    "shipping_free_admin_browser_qa",
)


def step(name: str) -> str:
    return WORKFLOW.read_text(encoding="utf-8").split(f"      - name: {name}\n", 1)[1].split("      - name:", 1)[0]


def shell_body(block: str) -> str:
    return textwrap.dedent(block.split("        run: |\n", 1)[1])


class IsolatedCiIntegrationWorkflowContractTests(unittest.TestCase):
    def test_postcode_fixture_failure_is_isolated_from_independent_browser_qa(self) -> None:
        fixture = step("Import synthetic Tokyo postcode fixture for isolated checkout QA")
        self.assertIn("id: postcode_fixture", fixture)
        self.assertIn("continue-on-error: true", fixture)

        postcode_consumers = (
            "Verify isolated CI Tokyo postcode lookup",
            "Verify saved native CI Tokyo address",
            "Verify synthetic Tokyo address in an unpaid native order and Back Office view",
        )
        for name in postcode_consumers:
            with self.subTest(step=name):
                self.assertIn("steps.postcode_fixture.outcome == 'success'", step(name))

        lookup_dependent_checkout = (
            "Verify browser customer search, Japan checkout, and unpaid offline order",
        )
        for name in lookup_dependent_checkout:
            with self.subTest(step=name):
                self.assertIn("steps.postcode_lookup.outcome == 'success'", step(name))

        independent_shipping_checkout = (
            "Enable run-scoped checkout only for the isolated order browser QA",
            "Verify zero shipping in Tokyo coupon and quantity checkout with Chromium",
            "Verify zero shipping in Osaka mobile checkout with Chromium",
            "Verify tax-included taxable Japan checkout with the free carrier",
        )
        for name in independent_shipping_checkout:
            with self.subTest(step=name):
                block = step(name)
                self.assertNotIn("steps.postcode_lookup.outcome", block)
                self.assertIn("steps.shipping_free_admin_readback.outcome == 'success'", block)

        independent_browser_qa = (
            "Verify Korean admin shipping links resolve in Chromium",
            "Verify official ORDENOWA brand upload and publish in Chromium",
            "Verify customer registration, email login, logout, password reset, and my page in Chromium",
            "Verify Korean admin native product create and edit in Chromium",
            "Verify real product detail and cart in Chromium (no payment)",
            "Verify native variant selection and cart controls in Chromium",
            "Verify Back Office token and view-only authorization in Chromium",
            "Verify Chromium PWA lifecycle and private-route cache protection",
        )
        for name in independent_browser_qa:
            with self.subTest(step=name):
                block = step(name)
                self.assertNotIn("steps.postcode_fixture.outcome", block)
                self.assertIn("continue-on-error: true", block)

    def test_pwa_qa_artifacts_include_only_hex_encoded_localized_account_rewrites(self) -> None:
        pwa = step("Verify Chromium PWA lifecycle and private-route cache protection")

        self.assertIn("HEX(ml.url_rewrite)", pwa)
        self.assertIn("pwa-account-route-rewrites.txt", pwa)
        self.assertIn("l.iso_code IN (", pwa)
        self.assertIn("my-account", pwa)
        self.assertIn("ja", pwa)
        self.assertIn("ko", pwa)
        self.assertNotIn("SELECT ml.url_rewrite ", pwa)

        aggregate = step("Aggregate browser QA and postal verification failures")
        self.assertIn("POSTCODE_FIXTURE_OUTCOME: ${{ steps.postcode_fixture.outcome }}", aggregate)
        self.assertIn('"postcode_fixture=$POSTCODE_FIXTURE_OUTCOME"', aggregate)

    def test_synthetic_postcode_count_uses_the_importers_canonical_values(self) -> None:
        fixture = step("Import synthetic Tokyo postcode fixture for isolated checkout QA")
        self.assertIn('postcode=\\"100-0004\\"', fixture)
        self.assertIn('postcode=\\"530-0001\\"', fixture)
        self.assertIn('postcode IN (\\"100-0004\\",\\"530-0001\\")', fixture)
        self.assertNotIn('postcode=\\"1000004\\"', fixture)
        self.assertNotIn('postcode=\\"5300001\\"', fixture)

    def test_new_contracts_run_before_build_and_trigger_both_events(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        contracts = (
            "test_account_address_routes", "test_product_tax_rules_contract", "test_variant_fixture_contract",
            "test_cart_controls_browser_contract", "test_security_runtime_e2e_contract",
            "test_pwa_service_worker", "test_taxable_checkout_browser_contract",
            "test_free_shipping_exemption_contract",
            "test_isolated_browser_target_guards", "test_isolated_ci_integration_workflow_contract",
            "test_currency_bootstrap_contract", "test_saved_order_tax_contract",
            "test_product_admin_browser_guard",
        )
        before_build = workflow.split("      - name: Build the PrestaShop image", 1)[0]
        for contract in contracts:
            with self.subTest(contract=contract):
                self.assertEqual(before_build.count(f"- 'tests/smoke/{contract}.py'"), 2)
                self.assertIn(f"tests.smoke.{contract}", before_build)

    def test_free_shipping_product_fixture_is_aggregated_and_retains_evidence(self) -> None:
        product_fixture = step("Prepare isolated active product for storefront and free-shipping QA")
        self.assertIn("id: shipping_product_fixture", product_fixture)

        aggregate = step("Aggregate browser QA and postal verification failures")
        self.assertIn("SHIPPING_PRODUCT_FIXTURE_OUTCOME: ${{ steps.shipping_product_fixture.outcome }}", aggregate)
        self.assertIn('"shipping_product_fixture=$SHIPPING_PRODUCT_FIXTURE_OUTCOME"', aggregate)

        coverage = step("Verify browser QA screenshot coverage")
        self.assertIn("SHIPPING_PRODUCT_FIXTURE_OUTCOME: ${{ steps.shipping_product_fixture.outcome }}", coverage)
        self.assertIn('if [[ "$SHIPPING_PRODUCT_FIXTURE_OUTCOME" == success ]]; then', coverage)
        self.assertIn("free-shipping-product-fixture.log", coverage)
        self.assertIn("free-shipping-product-fixture.json", coverage)

    def test_explicit_exemption_fixture_browser_order_and_admin_view_are_aggregated(self) -> None:
        fixture = step("Prepare isolated explicit exemption product fixture")
        browser = step("Verify explicit exemption free-shipping checkout with Chromium")
        persistence = step("Verify free-shipping orders and totals in the isolated database")
        admin = step("Verify free-shipping orders in a separate admin browser session")
        coverage = step("Verify browser QA screenshot coverage")
        for marker in (
            "KURANEA_ISOLATED_CI=1",
            "CI_TEST_EXEMPT_PRODUCT_ID",
            "CI_TEST_EXEMPT_TAX_RULES_GROUP_ID",
            '"$GITHUB_ENV"',
        ):
            self.assertIn(marker, fixture)
        self.assertIn("steps.exemption_product_fixture.outcome == 'success'", browser)
        self.assertIn("CI_TEST_PRODUCT_ID=\"$CI_TEST_EXEMPT_PRODUCT_ID\"", browser)
        self.assertIn("CI_TEST_PRODUCT_TAX_GROUP=\"$CI_TEST_EXEMPT_TAX_RULES_GROUP_ID\"", browser)
        self.assertIn("steps.shipping_free_exemption_browser_qa.outcome == 'success'", persistence)
        self.assertIn("verify_ci_free_shipping_exemption_order.php", persistence)
        self.assertIn("shipping-free-exemption-order.json", persistence)
        self.assertIn("shipping-free-exemption-verified.json", persistence)
        self.assertIn("steps.shipping_free_order_persistence.outcome == 'success'", admin)
        self.assertIn("verify_ci_free_shipping_browser.py admin", admin)
        self.assertIn("EXEMPTION_PRODUCT_FIXTURE_OUTCOME", coverage)
        self.assertIn("SHIPPING_FREE_EXEMPTION_BROWSER_QA_OUTCOME", coverage)
        self.assertIn("shipping-free-order-admin-exemption-desktop.png", coverage)

    def test_tax_and_variant_ids_are_validated_and_forwarded_to_consumers(self) -> None:
        tax = step("Create isolated synthetic tax product and reconcile native unpaid order")
        variant = step("Prepare isolated taxable variant fixture")
        for block in (tax, variant):
            for marker in ("CI=true", "GITHUB_ACTIONS=true", "KURANEA_ISOLATED_CI=1", "KURANEA_CI_RUN_ID", "KURANEA_CI_RUN_ATTEMPT", "KURANEA_CI_PROJECT_NAME", '"$GITHUB_ENV"'):
                self.assertIn(marker, block)
            self.assertIn('^[0-9]+$', block)
        self.assertIn("CI_TEST_TAX_RULES_GROUP_ID", variant)
        self.assertIn("steps.tax_fixture.outcome == 'success'", variant)
        cart = step("Verify native variant selection and cart controls in Chromium")
        self.assertIn("steps.variant_fixture.outcome == 'success'", cart)
        self.assertIn("CI_TEST_PRODUCT_ID=$CI_TEST_VARIANT_PRODUCT_ID", cart)
        product = step("Verify Korean admin native product create and edit in Chromium")
        self.assertIn("steps.tax_fixture.outcome == 'success'", product)

    def test_security_seed_values_are_validated_and_consumed_only_after_success(self) -> None:
        seed = step("Prepare isolated admin security and reset-token fixtures")
        for marker in ("CI_COMPOSE_PROJECT_NAME", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "KURANEA_ISOLATED_CI=1", "ORDENOWA_SECURITY_FIXTURE=", "@example", "fullmatch", "VIEW_ONLY_EMPLOYEE_EMAIL", "REPLAY_CUSTOMER_EMAIL", "EXPIRED_CUSTOMER_EMAIL"):
            self.assertIn(marker, seed)
        for name in ("Verify Back Office token and view-only authorization in Chromium", "Verify native customer reset-token replay and expiry in Chromium"):
            block = step(name)
            self.assertIn("steps.security_fixture.outcome == 'success'", block)
            self.assertIn("continue-on-error: true", block)
            self.assertIn("2>&1 | tee", block)

    def test_every_new_outcome_fails_the_aggregate_when_unsuccessful(self) -> None:
        aggregate = step("Aggregate browser QA and postal verification failures")
        outcome_vars = re.findall(r"^          ([A-Z_]+): \$\{\{ steps\.([a-z_]+)\.outcome \}\}", aggregate, re.MULTILINE)
        step_to_var = {step_id: variable for variable, step_id in outcome_vars}
        self.assertTrue(set(NEW_STEP_IDS).issubset(step_to_var), set(NEW_STEP_IDS) - step_to_var.keys())
        env = {**os.environ, **{variable: "success" for variable, _ in outcome_vars}}
        command = shell_body(aggregate)
        self.assertEqual(subprocess.run(["bash", "-c", command], env=env, capture_output=True).returncode, 0)
        for step_id in NEW_STEP_IDS:
            for outcome in ("failure", "skipped"):
                with self.subTest(step=step_id, outcome=outcome):
                    result = subprocess.run(["bash", "-c", command], env={**env, step_to_var[step_id]: outcome}, capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0, f"{step_id}={outcome} was ignored")
                    self.assertIn(outcome, result.stdout)

    def test_successful_cart_requires_its_evidence_even_when_another_step_failed(self) -> None:
        coverage = step("Verify browser QA screenshot coverage")
        variables = re.findall(r"^          ([A-Z_]+): \$\{\{ steps\.", coverage, re.MULTILINE)
        with tempfile.TemporaryDirectory() as temporary:
            artifact_dir = Path(temporary) / "ordenowa-browser-qa"
            artifact_dir.mkdir()
            (artifact_dir / "unrelated-failure.log").write_text("failed elsewhere\n", encoding="utf-8")
            env = {**os.environ, **{variable: "failure" for variable in variables}, "RUNNER_TEMP": temporary, "CART_CONTROLS_BROWSER_QA_OUTCOME": "success"}
            result = subprocess.run(["bash", "-c", shell_body(coverage)], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, "another failure hid the successful cart flow's missing evidence")
            self.assertIn("cart-controls-desktop-initial.png", result.stdout)

    def test_taxable_order_is_verified_with_its_own_fixture_identity(self) -> None:
        persistence = step("Verify free-shipping orders and totals in the isolated database")
        self.assertIn("steps.shipping_free_taxable_browser_qa.outcome == 'success'", persistence)
        self.assertIn("for viewport in tokyo osaka taxable", persistence)
        self.assertIn("shipping-free-taxable-order.json", persistence)
        self.assertIn('expected_product_id="$CI_TEST_TAX_PRODUCT_ID"', persistence)
        self.assertIn('expected_tax_group_id="$CI_TEST_TAX_RULES_GROUP_ID"', persistence)
        self.assertIn('"$product_id" != "$expected_product_id"', persistence)
        self.assertIn('"$product_tax_group_id" != "$expected_tax_group_id"', persistence)

    def test_free_carrier_readback_precedes_every_browser_order(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        names = (
            "Prepare isolated free-shipping order and coupon fixtures",
            "Configure the free Japan carrier through Chromium AdminCarriers",
            "Restart PrestaShop with the CI database volume intact",
            "Read back the free Japan carrier after a fresh admin login",
            "Enable run-scoped checkout only for the isolated order browser QA",
            "Verify browser customer search, Japan checkout, and unpaid offline order",
            "Verify a separate admin session can view both browser orders",
            "Verify zero shipping in Tokyo coupon and quantity checkout with Chromium",
            "Verify zero shipping in Osaka mobile checkout with Chromium",
            "Verify tax-included taxable Japan checkout with the free carrier",
        )
        positions = [workflow.index(f"      - name: {name}\n") for name in names]
        self.assertEqual(positions, sorted(positions), "browser orders must follow free-carrier configuration and restart readback")
        fixture = step(names[0])
        self.assertNotIn("steps.checkout_override", fixture)
        self.assertIn("steps.compose_up.outcome == 'success'", fixture)
        override = step(names[4])
        self.assertIn("steps.shipping_free_admin_readback.outcome == 'success'", override)
        restart = step(names[2])
        self.assertNotIn("tests/fixtures/ci-checkout.compose.yaml", restart)
        self.assertIn('docker compose -p "$CI_COMPOSE_PROJECT_NAME" restart prestashop', restart)
        for name in (names[7], names[9]):
            self.assertIn("steps.checkout_override.outcome == 'success'", step(name))
        osaka = step(names[8])
        self.assertIn("steps.shipping_free_admin_readback.outcome == 'success'", osaka)
        self.assertIn("steps.checkout_override.outcome == 'success'", osaka)
        self.assertNotIn("steps.shipping_free_customer_browser_qa.outcome", osaka)

    def test_osaka_state_fixture_uses_prestashop_scalar_state_name(self) -> None:
        fixture = step("Import synthetic Tokyo postcode fixture for isolated checkout QA")
        self.assertIn("$state->name = '大阪府';", fixture)
        self.assertNotIn("$state->name = [];", fixture)

    def test_free_shipping_mariadb_queries_receive_plain_sql_quotes(self) -> None:
        fixture = step("Prepare isolated free-shipping order and coupon fixtures")
        body = shell_body(fixture)
        queries = (
            ("product_record", 'LIKE "KURANEA-CI-%"'),
            ("japan_zone_id", 'iso_code="JP"'),
        )
        with tempfile.TemporaryDirectory() as temporary:
            maria = Path(temporary) / "mariadb"
            maria.write_text('#!/bin/sh\nprintf "%s" "$7"\n', encoding="utf-8")
            maria.chmod(0o755)
            for variable, expected_sql in queries:
                with self.subTest(variable=variable):
                    start = body.index(f"{variable}=$(") + len(f"{variable}=$(")
                    pipe = body.index("2>&1 | tee", start)
                    docker_command = body[start:pipe].rstrip()
                    if docker_command.endswith("\\"):
                        docker_command = docker_command[:-1].rstrip()
                    script = (
                        'docker() { while [ "$1" != "mariadb" ]; do shift; done; shift; "$@"; }\n'
                        'query=$(' + docker_command + ')\n'
                        'printf "%s" "$query"\n'
                    )
                    result = subprocess.run(
                        ["bash", "-c", script],
                        env={
                            **os.environ,
                            "PATH": f"{temporary}:{os.environ.get('PATH', '')}",
                            "CI_COMPOSE_PROJECT_NAME": "kuranea-ci-123-1",
                            "MARIADB_ROOT_PASSWORD": "ci-only-password",
                            "MARIADB_DATABASE": "prestashop",
                            "CI_TEST_PRODUCT_ID": "123",
                        },
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    self.assertIn(expected_sql, result.stdout)
                    self.assertNotIn(r'\"', result.stdout)


if __name__ == "__main__":
    unittest.main()
