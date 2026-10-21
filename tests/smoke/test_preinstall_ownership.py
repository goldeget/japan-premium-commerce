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
        self.assertIn('chown www-data:www-data "$cache_dir"', script)
        self.assertNotIn("chown -R", script)
        self.assertNotRegex(script, r"chmod\s+(?:-R\s+)?777")

    def test_bundled_module_files_are_readable_by_the_web_user_after_sync(self) -> None:
        entrypoint = ROOT / "docker/kuranea-entrypoint.sh"
        self.assertTrue(entrypoint.is_file(), "missing KURANEA module sync entrypoint")
        script = entrypoint.read_text(encoding="utf-8")

        self.assertIn('find "$target_dir" -type d -exec chmod 0755 {} +', script)
        self.assertIn('find "$target_dir" -type f -exec chmod 0644 {} +', script)

        fresh_install = (ROOT / "tests/smoke/fresh_install.sh").read_text(encoding="utf-8")
        self.assertIn("modules/kuraneabackoffice/src/AdminLocaleSubscriber.php", fresh_install)
        self.assertIn("runuser -g www-data -u www-data -- test -r", fresh_install)


if __name__ == "__main__":
    unittest.main()
