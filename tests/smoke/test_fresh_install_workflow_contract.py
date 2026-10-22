"""Keep the isolated installer pointed at Japan Post's published KEN_ALL archive."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "fresh-install.yml"
POSTAL_IMPORT = ROOT / "modules" / "kuraneapostcode" / "bin" / "import-ken-all.php"
POSTAL_UPDATER = ROOT / "modules" / "kuraneapostcode" / "bin" / "update-ken-all.sh"
FRESH_INSTALL_SMOKE = ROOT / "tests" / "smoke" / "fresh_install.sh"


class FreshInstallWorkflowContractTests(unittest.TestCase):
    def test_customer_account_e2e_uses_isolated_mailpit_and_publishes_browser_logs(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        account_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(encoding="utf-8")
        self.assertTrue("axllent/mailpit:v1.31.6" in workflow, "missing version-pinned disposable mail capture service")
        self.assertTrue('Configuration::updateValue("PS_MAIL_SERVER", "mailpit")' in workflow, "PrestaShop SMTP is not pointed at the CI-only mail service")
        self.assertTrue('Configuration::updateValue("PS_MAIL_SMTP_PORT", 1025)' in workflow, "PrestaShop SMTP port is not set for Mailpit")
        self.assertTrue("tests/e2e/verify_customer_account_browser.py" in workflow, "customer account browser flow is not run")
        self.assertTrue("MAILPIT_API_URL: http://127.0.0.1:8025" in workflow, "browser test cannot read captured reset mail")
        self.assertTrue("customer-account-e2e.log" in workflow, "account browser execution log is not preserved")
        self.assertTrue("docker rm -f \"${CI_COMPOSE_PROJECT_NAME}-mailpit\"" in workflow, "CI mail service cleanup is missing")
        self.assertTrue('input[name="email"]' in account_flow and 'get_attribute("type") != "email"' in account_flow, "customer login is not verified as email-based")
        self.assertTrue("reset_link_for(account_email)" in account_flow, "password reset does not follow the captured test email")
        self.assertTrue('parsed.hostname in {"localhost", "127.0.0.1"}' in account_flow, "reset links are not restricted to the isolated shop")
        self.assertIn('"cid:shop_logo"', account_flow, "captured reset email must render the approved brand logo")

    def test_official_brand_upload_preview_publish_and_browser_checks_run_in_isolated_ci(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        brand_flow_path = ROOT / "tests" / "e2e" / "verify_brand_admin_browser.py"
        self.assertTrue(brand_flow_path.is_file(), "official brand admin browser QA is missing")
        brand_flow = brand_flow_path.read_text(encoding="utf-8")
        self.assertIn("Verify official ORDENOWA brand upload and publish in Chromium", workflow)
        self.assertIn("tests/e2e/verify_brand_admin_browser.py", workflow)
        self.assertIn("ADMIN_MAIL: ci-kuranea@example.invalid", workflow)
        self.assertIn("ADMIN_PASSWD: Ci-Only-Admin-Password-92!", workflow)
        self.assertIn("ordenowa-brand-e2e.log", workflow)
        self.assertIn("brand-desktop-published.png", brand_flow)
        self.assertIn("brand-mobile-published.png", brand_flow)
        self.assertIn("submitOrdenowaPreview", brand_flow)
        self.assertIn("submitOrdenowaPublish", brand_flow)
        self.assertIn('brand_uploads[{slot}]', brand_flow)
        for source_slot in ('"primary_logo"', '"favicon_symbol"', '"pwa_icon"'):
            self.assertIn(source_slot, brand_flow)
        self.assertIn("확인 대기", brand_flow)
        self.assertNotIn("submitOrdenowaApproveSeller", brand_flow)
        storefront_flow = (ROOT / "tests" / "e2e" / "verify_storefront_browser.py").read_text(encoding="utf-8")
        self.assertIn("payment-option", storefront_flow, "the browser suite must keep live checkout controls inaccessible")

    def test_ci_uses_the_module_updater_for_the_official_japan_post_archive(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        postal_step = workflow.split("- name: Download and import official Japan Post KEN_ALL data", 1)[1].split("- name:", 1)[0]
        updater = POSTAL_UPDATER.read_text(encoding="utf-8")
        self.assertIn("https://www.post.japanpost.jp/service/search/zipcode/download/kogaki/zip/ken_all.zip", updater)
        self.assertIn("bash tests/smoke/run_postal_updater.sh \"$CI_COMPOSE_PROJECT_NAME\"", postal_step)
        self.assertNotIn("curl ", postal_step)
        self.assertNotIn("unzip", postal_step)
        runner = (ROOT / "tests" / "smoke" / "run_postal_updater.sh").read_text(encoding="utf-8")
        self.assertIn("runuser -g www-data -u www-data --", runner)
        self.assertIn("/var/www/html/modules/kuraneapostcode/bin/update-ken-all.sh", runner)

    def test_postal_updater_failure_is_summarized_without_raw_output(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("tests/smoke/run_postal_updater.sh", workflow)
        self.assertIn("tests/smoke/run_postal_updater.sh", workflow.split("paths:", 1)[1].split("permissions:", 1)[0])
        runner = (ROOT / "tests" / "smoke" / "run_postal_updater.sh").read_text(encoding="utf-8")
        self.assertIn("KURANEA_POSTAL_DOWNLOAD_FAILURE curl_exit=", runner)
        self.assertIn("GITHUB_STEP_SUMMARY", runner)
        self.assertIn("::error title=Japan Post postcode update::", runner)
        self.assertIn("updater/import failed; raw updater output was suppressed", runner)
        self.assertIn('>"$log_file" 2>&1', runner)

    def test_failed_compose_bootstrap_uses_the_shared_redacting_diagnostics_script(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("- name: Start the empty-volume shop", workflow)
        self.assertIn("id: compose_up", workflow)
        self.assertIn("bash tests/smoke/collect_failure_diagnostics.sh", workflow)
        self.assertIn("docker compose -p \"$project_name\" logs --tail=160 mariadb prestashop", (ROOT / "tests/smoke/collect_failure_diagnostics.sh").read_text(encoding="utf-8"))

    def test_isolated_preinstall_probe_repairs_a_root_owned_class_index(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        probe = workflow.split("- name: Verify fresh cache ownership in an isolated probe project", 1)[1].split("- name:", 1)[0]
        self.assertIn('probe_project="${CI_COMPOSE_PROJECT_NAME}-cache-probe"', probe)
        self.assertIn("run --rm --no-deps", probe)
        self.assertIn('chown -R root:root "$cache_dir"', probe)
        self.assertIn("/tmp/pre-install-scripts/10-kuranea-cache-ownership.sh", probe)
        self.assertIn('test "$(stat -c "%U:%G" "$cache_dir/class_index.php")" = www-data:www-data', probe)
        self.assertIn("runuser -g www-data -u www-data -- test -w", probe)
        self.assertIn('docker compose -p "$probe_project" down -v --remove-orphans', probe)
        start = workflow.split("- name: Start the empty-volume shop", 1)[1].split("- name:", 1)[0]
        self.assertIn('docker compose -p "$CI_COMPOSE_PROJECT_NAME" up -d --wait --wait-timeout 900', start)

    def test_catalog_install_and_queue_persistence_check_precedes_postal_download(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        shop_start = workflow.index("- name: Start the empty-volume shop")
        catalog_check = workflow.index("- name: Verify the installed KURANEA catalog review module and persistent queue")
        postal_download = workflow.index("- name: Download and import official Japan Post KEN_ALL data")
        self.assertLess(shop_start, catalog_check)
        self.assertLess(catalog_check, postal_download)

        catalog_step = workflow[catalog_check:postal_download]
        self.assertIn("tests/catalog/verify_catalog_installation.php", catalog_step)
        self.assertIn("tests/catalog/fixtures/amazon-jp-product.synthetic.html", catalog_step)
        self.assertIn("restart prestashop", catalog_step)
        self.assertGreaterEqual(catalog_step.count("php /tmp/verify_catalog_installation.php"), 2)

    def test_synthetic_order_qa_is_isolated_from_live_japan_post_download(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        fixture = workflow.index("- name: Import synthetic Tokyo postcode fixture for isolated checkout QA")
        postcode = workflow.index("- name: Verify isolated CI Tokyo postcode lookup")
        address = workflow.index("- name: Verify saved native CI Tokyo address")
        order = workflow.index("- name: Verify synthetic Tokyo address in an unpaid native order and Back Office view")
        official = workflow.index("- name: Download and import official Japan Post KEN_ALL data")
        self.assertLess(fixture, postcode)
        self.assertLess(postcode, address)
        self.assertLess(address, order)
        self.assertLess(order, official)
        self.assertIn("ISOLATED CI FIXTURE:", workflow)
        self.assertIn("Verify official Japan Post import contains national address data", workflow)
        self.assertIn("ps_kuraneapostcode_address", workflow)

    def test_failed_compose_bootstrap_publishes_a_redacted_step_summary(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        capture = workflow.split("- name: Capture bounded diagnostics on failure", 1)[1].split("- name:", 1)[0]
        diagnostics = (ROOT / "tests/smoke/collect_failure_diagnostics.sh").read_text(encoding="utf-8")
        self.assertIn("if: failure()", capture)
        self.assertIn("steps.image_build.outcome", capture)
        self.assertIn("steps.cache_probe.outcome", capture)
        self.assertIn("steps.compose_up.outcome", capture)
        self.assertIn("bash tests/smoke/collect_failure_diagnostics.sh", capture)
        self.assertIn("GITHUB_STEP_SUMMARY", diagnostics)
        self.assertIn("[REDACTED]", diagnostics)
        self.assertIn("Upload redacted install diagnostics", workflow)
        self.assertIn("retention-days: 2", workflow)

    def test_every_workflow_failure_uses_the_redacting_collector(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        capture = workflow.split("- name: Capture bounded diagnostics on failure", 1)[1].split("- name:", 1)[0]
        self.assertIn("if: failure()", capture)
        self.assertIn("bash tests/smoke/collect_failure_diagnostics.sh", capture)
        self.assertNotIn("docker compose", capture)

    def test_native_order_persistence_test_is_guarded_to_its_isolated_github_project(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        order_step = workflow.split("- name: Verify synthetic Tokyo address in an unpaid native order and Back Office view", 1)[1].split("- name:", 1)[0]
        order_test = (ROOT / "tests/postcode/verify_native_order_persistence.php").read_text(encoding="utf-8")
        self.assertIn("KURANEA_ISOLATED_CI=1", order_step)
        self.assertIn('KURANEA_CI_PROJECT_NAME="$CI_COMPOSE_PROJECT_NAME"', order_step)
        self.assertIn('KURANEA_CI_RUN_ID="$GITHUB_RUN_ID"', order_step)
        self.assertIn('KURANEA_CI_RUN_ATTEMPT="$GITHUB_RUN_ATTEMPT"', order_step)
        self.assertIn("getenv('CI') !== 'true'", order_test)
        self.assertIn("getenv('GITHUB_ACTIONS') !== 'true'", order_test)
        self.assertIn("$projectName !== $expectedProjectName", order_test)
        self.assertIn("instanceof PaymentModule", order_test)
        self.assertIn("GetOrderForViewing", order_test)
        self.assertIn("get('prestashop.core.query_bus')", order_test)
        self.assertIn("QuerySorting::DESC", order_test)
        self.assertNotIn("CommandBusInterface::class", order_test)
        self.assertIn("KURANEA_NATIVE_ORDER_STAGE", order_test)
        self.assertIn("::error title=KURANEA native order::", order_test)
        for stage in (
            "PrestaShop bootstrap",
            "Back Office kernel boot",
            "Japanese shop context",
            "offline payment module",
            "isolated CI postcode candidate",
            "customer and address persistence",
            "CI-only product creation",
            "CI-only carrier setup",
            "native cart and quantity",
            "delivery option",
            "unpaid native order",
            "Back Office shipping address projection",
        ):
            self.assertIn(stage, order_test)

    def test_postcode_lookup_and_native_address_save_report_separate_ci_failures(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python3 -m unittest tests.smoke.test_fresh_install_workflow_contract", workflow)
        self.assertIn("- name: Verify isolated CI Tokyo postcode lookup", workflow)
        self.assertIn("- name: Verify saved native CI Tokyo address", workflow)
        address_step = workflow.split("- name: Verify saved native CI Tokyo address", 1)[1].split("- name:", 1)[0]
        self.assertIn("tests/postcode/verify_native_address_persistence.php", address_step)

        verifier = (ROOT / "tests" / "postcode" / "verify_native_address_persistence.php").read_text(encoding="utf-8")
        self.assertIn("KURANEA_NATIVE_ADDRESS_STAGE", verifier)
        self.assertIn("::error title=KURANEA address persistence::", verifier)
        for stage in (
            "bootstrap",
            "Japan and state lookup",
            "isolated CI postcode candidate",
            "customer creation",
            "native address save",
            "saved address reload",
        ):
            self.assertIn(stage, verifier)

    def test_native_address_verifiers_do_not_assign_unsupported_shop_property(self) -> None:
        verifier_paths = (
            ROOT / "tests" / "postcode" / "verify_native_address_persistence.php",
            ROOT / "tests" / "postcode" / "verify_native_order_persistence.php",
        )
        for verifier_path in verifier_paths:
            with self.subTest(verifier=verifier_path.name):
                verifier = verifier_path.read_text(encoding="utf-8")
                self.assertNotRegex(verifier, r"\$address->id_shop\s*=")
                self.assertIn("$address->id_customer =", verifier)

    def test_successful_postal_import_clears_only_the_staging_copy(self) -> None:
        importer = POSTAL_IMPORT.read_text(encoding="utf-8")
        smoke = FRESH_INSTALL_SMOKE.read_text(encoding="utf-8")
        commit = importer.index("$database->execute('COMMIT')")
        cleanup = importer.index("$database->execute('TRUNCATE TABLE ' . $stageTable)", commit)
        self.assertGreater(cleanup, commit, "staging may only be cleared after the new main table commits")
        self.assertIn("ps_kuraneapostcode_stage", smoke)
        self.assertIn('test "$postcode_stage_rows" = 0', smoke)

    def test_catalog_parser_failure_diagnostics_are_bounded_and_escaped(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "catalog-parser.yml").read_text(encoding="utf-8")
        step = workflow.split("- name: Run synthetic offline Amazon Japan and Rakuten parser tests", 1)[1].split("- name:", 1)[0]
        failure_branch = step.split('if [ "$test_status" -ne 0 ]; then', 1)[1].split("fi", 1)[0]
        self.assertIn('tail -n 80 "$test_log"', failure_branch)
        self.assertIn("cut -c1-500", failure_branch)
        self.assertIn("%25", failure_branch)
        self.assertIn("%0D", failure_branch)
        self.assertIn("%0A", failure_branch)
        self.assertLess(step.index('if [ "$test_status"'), step.index('cat "$test_log"'))


if __name__ == "__main__":
    unittest.main()
