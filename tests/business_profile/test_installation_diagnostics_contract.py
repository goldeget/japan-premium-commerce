from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
INSTALLATION_CHECK = ROOT / "tests" / "business_profile" / "verify_installation.php"


class BusinessProfileInstallationDiagnosticsContractTests(unittest.TestCase):
    def test_failed_assertions_emit_escaped_github_annotations_before_throwing(self) -> None:
        source = INSTALLATION_CHECK.read_text(encoding="utf-8")
        helper = source.split("function verifyBusinessProfile(", 1)[1].split("\n}", 1)[0]

        self.assertIn("str_replace(['%', \"\\r\", \"\\n\"], ['%25', '%0D', '%0A'], $message)", helper)
        self.assertIn("'::error title=ORDENOWA business profile verifier::' . $annotation . PHP_EOL", helper)
        self.assertLess(helper.index("fwrite(STDOUT"), helper.index("throw new RuntimeException($message)"))
        self.assertIn("ORDENOWA_BUSINESS_PROFILE_ASSERTION=", helper)


if __name__ == "__main__":
    unittest.main()
