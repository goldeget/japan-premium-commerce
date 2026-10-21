from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PreinstallOwnershipTests(unittest.TestCase):
    def test_fresh_install_repairs_only_generated_production_cache_ownership(self) -> None:
        dockerfile = (ROOT / "docker/Dockerfile").read_text(encoding="utf-8")
        preinstall = ROOT / "docker/pre-install/10-kuranea-cache-ownership.sh"
        self.assertTrue(
            preinstall.is_file(),
            "fresh install needs a pre-install hook after the official source copy",
        )
        script = preinstall.read_text(encoding="utf-8")

        self.assertIn(
            "COPY --chmod=0755 docker/pre-install/10-kuranea-cache-ownership.sh /tmp/pre-install-scripts/10-kuranea-cache-ownership.sh",
            dockerfile,
        )
        self.assertIn("cache_dir=/var/www/html/var/cache/prod", script)
        self.assertIn('chown -R www-data:www-data "$cache_dir"', script)
        self.assertNotRegex(script, r"chmod\s+(?:-R\s+)?777")


if __name__ == "__main__":
    unittest.main()
