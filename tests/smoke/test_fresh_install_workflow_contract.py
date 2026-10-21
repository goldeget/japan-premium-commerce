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

    def test_failed_compose_bootstrap_prints_bounded_service_diagnostics(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("if ! docker compose -p \"$CI_COMPOSE_PROJECT_NAME\" up", workflow)
        self.assertIn("docker compose -p \"$CI_COMPOSE_PROJECT_NAME\" logs --tail=160 mariadb prestashop", workflow)


if __name__ == "__main__":
    unittest.main()
