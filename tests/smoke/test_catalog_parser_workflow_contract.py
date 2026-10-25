"""Keep offline PHP failure details visible in Actions annotations and summary."""
from pathlib import Path
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
        self.assertIn('tail -n 80 "$test_log"', step)
        self.assertIn("grep -m1 '^PHP Fatal error: Uncaught ' \"$test_log\"", step)
        self.assertIn("s/; expected .*//; s/ in .*//", step)
        self.assertIn('Offline catalog tests failed; see the bounded step summary.', step)
        self.assertNotIn('tail -n 1 "$test_log"', step)
        self.assertIn('>> "$GITHUB_STEP_SUMMARY"', step)
        self.assertIn('echo "::error title=Offline catalog parser tests::$failure_line"', step)
        self.assertIn("tests.smoke.test_catalog_parser_workflow_contract", source)


if __name__ == "__main__":
    unittest.main()
