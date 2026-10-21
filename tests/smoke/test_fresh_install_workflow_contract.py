"""Keep the isolated installer pointed at Japan Post's published KEN_ALL archive."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "fresh-install.yml"


class FreshInstallWorkflowContractTests(unittest.TestCase):
    def test_downloads_ken_all_from_the_current_japan_post_archive_path(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "https://www.post.japanpost.jp/service/search/zipcode/download/kogaki/zip/ken_all.zip",
            workflow,
        )

    def test_failed_compose_bootstrap_uses_the_shared_redacting_diagnostics_script(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("if ! docker compose -p \"$CI_COMPOSE_PROJECT_NAME\" up", workflow)
        self.assertIn("bash tests/smoke/collect_failure_diagnostics.sh", workflow)
        self.assertIn("docker compose -p \"$project_name\" logs --tail=160 mariadb prestashop", (ROOT / "tests/smoke/collect_failure_diagnostics.sh").read_text(encoding="utf-8"))

    def test_failed_compose_bootstrap_publishes_a_redacted_step_summary(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        bootstrap = workflow.split("- name: Build and install into unique empty volumes", 1)[1].split("- name:", 1)[0]
        diagnostics = (ROOT / "tests/smoke/collect_failure_diagnostics.sh").read_text(encoding="utf-8")
        self.assertIn("bash tests/smoke/collect_failure_diagnostics.sh", bootstrap)
        self.assertIn("GITHUB_STEP_SUMMARY", diagnostics)
        self.assertIn("[REDACTED]", diagnostics)
        self.assertIn("Upload redacted install diagnostics", workflow)
        self.assertIn("retention-days: 2", workflow)

    def test_later_step_failures_also_use_the_redacting_collector(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        capture = workflow.split("- name: Capture bounded diagnostics on failure", 1)[1].split("- name:", 1)[0]
        self.assertIn("steps.compose_bootstrap.outcome == 'success'", capture)
        self.assertIn("bash tests/smoke/collect_failure_diagnostics.sh", capture)
        self.assertNotIn("docker compose", capture)


if __name__ == "__main__":
    unittest.main()
