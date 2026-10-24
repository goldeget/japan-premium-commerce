"""Guard local Compose defaults and operator-configurable deployment identity."""
from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "compose.yaml"
ENV_EXAMPLE = ROOT / ".env.example"


class DeploymentConfigContractTests(unittest.TestCase):
    def test_shop_domain_and_bind_address_are_configurable_with_local_safe_defaults(self) -> None:
        compose = COMPOSE.read_text(encoding="utf-8")
        env_example = ENV_EXAMPLE.read_text(encoding="utf-8")

        self.assertIn('"${SHOP_BIND_ADDRESS:-127.0.0.1}:${SHOP_PORT:-8080}:80"', compose)
        self.assertIn("PS_DOMAIN: ${PS_DOMAIN:-localhost:${SHOP_PORT:-8080}}", compose)
        self.assertIn("${PS_DOMAIN:-localhost:${SHOP_PORT:-8080}}", compose)
        self.assertIn("SHOP_BIND_ADDRESS=127.0.0.1", env_example)
        self.assertIn("SHOP_PORT=8080", env_example)
        self.assertNotIn("PS_DOMAIN=", env_example, "the sample must not pin the host when SHOP_PORT changes")

    def test_compose_documents_that_the_domain_is_fixed_during_first_install(self) -> None:
        operations = ROOT / "docs" / "PRODUCTION_DEPLOYMENT.md"
        self.assertTrue(operations.is_file(), "operator deployment and environment requirements are undocumented")
        content = operations.read_text(encoding="utf-8")
        self.assertIn("PS_DOMAIN", content)
        self.assertIn("SHOP_BIND_ADDRESS", content)
        self.assertIn("최초 설치 전에", content)
        self.assertIn("운영 배포를 실행하지 않는다", content)


if __name__ == "__main__":
    unittest.main()
