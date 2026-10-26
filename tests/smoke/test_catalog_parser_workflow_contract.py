"""Keep offline PHP failure details visible in Actions annotations and summary."""
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class CatalogParserWorkflowContract(unittest.TestCase):
    def test_php_failure_is_captured_without_shell_errexit_hiding_diagnostics(self):
        source = (ROOT / ".github/workflows/catalog-parser.yml").read_text(encoding="utf-8")
        step = source.split("- name: Run synthetic offline Amazon Japan and Rakuten parser tests", 1)[1].split(
            "\n      - name:", 1
        )[0]
        self.assertIn('if php tests/catalog/run.php >"$test_log" 2>&1; then', step)
        self.assertIn('test_status=$?', step)
        self.assertIn('failure_type=$(awk', step)
        self.assertIn('/^PHP Fatal error:/', step)
        self.assertIn('*) failure_type=\'UNKNOWN\' ;;', step)
        self.assertIn('failure_site=$(awk', step)
        self.assertIn("sub(/^.*\\/tests\\/catalog\\//, \"tests/catalog/\", source)", step)
        self.assertNotIn('tail -n', step)
        self.assertNotIn('grep -m1 -E', step)
        self.assertNotIn('head -n 1', step)
        self.assertIn('>> "$GITHUB_STEP_SUMMARY"', step)
        self.assertIn('echo "::error title=Offline catalog parser tests::$failure_line"', step)
        self.assertIn("tests.smoke.test_catalog_parser_workflow_contract", source)

    def test_failure_classifier_skips_prior_pass_lines_and_reports_only_safe_location(self):
        source = (ROOT / ".github" / "workflows" / "catalog-parser.yml").read_text(encoding="utf-8")
        step = source.split("- name: Run synthetic offline Amazon Japan and Rakuten parser tests", 1)[1].split(
            "\n      - name:", 1
        )[0]
        failure_branch = step.split('if [ "$test_status" -ne 0 ]; then', 1)[1].split("\n          else", 1)[0]
        type_program = failure_branch.split("failure_type=$(awk '\n", 1)[1].split("\n            ' \"$test_log\")", 1)[0]
        site_program = failure_branch.split("failure_site=$(awk '\n", 1)[1].split("\n            ' \"$test_log\")", 1)[0]

        log = "\n".join([
            "PASS: first parser fixture",
            "PASS: second repository fixture",
            "PHP Fatal error: Uncaught RuntimeException: expected token=fixture-value in /home/runner/work/repo/repo/tests/catalog/import_batch_repository.php:17",
            "#0 /home/runner/work/repo/repo/tests/catalog/import_batch_repository.php(215): catalogImportAssertSame('expected token', 'actual token')",
        ])
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "catalog-parser-tests.log"
            log_path.write_text(log, encoding="utf-8")
            failure_type = subprocess.run(
                ["awk", type_program, str(log_path)], check=True, capture_output=True, text=True
            ).stdout.strip()
            failure_site = subprocess.run(
                ["awk", site_program, str(log_path)], check=True, capture_output=True, text=True
            ).stdout.strip()

        self.assertEqual("RuntimeException", failure_type)
        self.assertEqual("tests/catalog/import_batch_repository.php:215", failure_site)
        self.assertNotIn("token", failure_type + failure_site)

        without_failure = "PASS: one\nPASS: two\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "catalog-parser-tests.log"
            log_path.write_text(without_failure, encoding="utf-8")
            no_failure_type = subprocess.run(
                ["awk", type_program, str(log_path)], check=True, capture_output=True, text=True
            ).stdout.strip()
        self.assertEqual("", no_failure_type)
        self.assertIn("*) failure_type='UNKNOWN' ;;", failure_branch)


if __name__ == "__main__":
    unittest.main()
