"""Keep the child-theme skip link keyboard-operable without editing Hummingbird."""
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "themes/kuranea"


class StorefrontSkipLinkContractTests(unittest.TestCase):
    def test_static_and_behavior_contract_runs_before_the_isolated_install(self):
        workflow = (ROOT / ".github/workflows/fresh-install.yml").read_text(encoding="utf-8")
        step = workflow.split("- name: Verify fresh-install workflow contracts", 1)[1].split(
            "\n      - name:", 1
        )[0]
        self.assertIn("tests.smoke.test_storefront_accessibility_contract", step)

    def test_child_theme_enhances_hummingbird_skip_link_target_focus(self):
        source = (THEME / "assets/js/skip-to-main.js").read_text(encoding="utf-8")
        head = (THEME / "templates/_partials/head.tpl").read_text(encoding="utf-8")
        hummingbird_layout = (ROOT / "themes/hummingbird/templates/layouts/layout-both-columns.tpl").read_text(
            encoding="utf-8"
        )

        self.assertIn('href="#main-content"', hummingbird_layout)
        self.assertIn('id="main-content"', hummingbird_layout)
        self.assertIn('js/skip-to-main.js', head)
        self.assertIn('a.skip-link[href="#main-content"]', source)
        self.assertIn("setAttribute('tabindex', '-1')", source)
        self.assertIn("target.focus(", source)

    def test_contract_runs_in_fresh_install_preflight_and_triggers_changes(self):
        workflow = (ROOT / ".github/workflows/fresh-install.yml").read_text(encoding="utf-8")
        self.assertEqual(
            2,
            workflow.count("'tests/smoke/test_storefront_accessibility_contract.py'"),
        )
        preflight = workflow.split("- name: Verify fresh-install workflow contracts", 1)[1].split(
            "\n      - name:", 1
        )[0]
        self.assertIn("tests.smoke.test_storefront_accessibility_contract", preflight)

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed for the DOM-free behavior fixture")
    def test_keyboard_skip_link_focus_behavior(self):
        result = subprocess.run(
            ["node", "--test", str(THEME / "assets/js/skip-to-main.test.cjs")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
