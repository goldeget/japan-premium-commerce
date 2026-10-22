"""Verify the approved ORDENOWA brand pack and bundled legacy backups."""
from __future__ import annotations

import hashlib
import json
import re
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "assets" / "brand" / "ordenowa"


class OrdenowaBrandPackTests(unittest.TestCase):
    def test_all_approved_sources_and_derived_files_match_the_asset_manifest(self) -> None:
        manifest = json.loads((PACK / "asset-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("ORDENOWA", manifest["brand"])
        self.assertEqual(3, len(manifest["sources_sha256"]))
        self.assertEqual(17, len(manifest["derived"]))

        for name, expected_hash in manifest["sources_sha256"].items():
            with self.subTest(source=name):
                source = PACK / "official_originals" / name
                self.assertTrue(source.is_file(), f"missing approved source: {name}")
                self.assertEqual(expected_hash, hashlib.sha256(source.read_bytes()).hexdigest())

        for name, expected in manifest["derived"].items():
            with self.subTest(derived=name):
                image = PACK / "web_assets" / name
                content = image.read_bytes()
                self.assertEqual(expected["bytes"], len(content))
                self.assertEqual(expected["sha256"], hashlib.sha256(content).hexdigest())

    def test_approved_image_dimensions_and_formats_match_their_roles(self) -> None:
        expected = {
            "official_originals/ORDENOWA-logo.png": (2172, 724, b"\x89PNG\r\n\x1a\n"),
            "official_originals/ORDENOWA-favicon-source.png": (1254, 1254, b"\x89PNG\r\n\x1a\n"),
            "official_originals/ORDENOWA-pwa-icon-source.png": (1254, 1254, b"\x89PNG\r\n\x1a\n"),
            "web_assets/logo-desktop.png": (1600, 500, b"\x89PNG\r\n\x1a\n"),
            "web_assets/logo-mobile.png": (800, 250, b"\x89PNG\r\n\x1a\n"),
            "web_assets/apple-touch-icon.png": (180, 180, b"\x89PNG\r\n\x1a\n"),
            "web_assets/og-1200x630.png": (1200, 630, b"\x89PNG\r\n\x1a\n"),
            "web_assets/pwa-192x192.png": (192, 192, b"\x89PNG\r\n\x1a\n"),
            "web_assets/pwa-512x512.png": (512, 512, b"\x89PNG\r\n\x1a\n"),
            "web_assets/favicon.ico": (256, 256, b"\x00\x00\x01\x00"),
        }
        for relative, (width, height, signature) in expected.items():
            with self.subTest(image=relative):
                content = (PACK / relative).read_bytes()
                self.assertTrue(content.startswith(signature))
                if signature.startswith(b"\x89PNG"):
                    self.assertEqual((width, height), struct.unpack(">II", content[16:24]))
                else:
                    count = struct.unpack("<H", content[4:6])[0]
                    sizes = {
                        (content[offset] or 256, content[offset + 1] or 256)
                        for offset in range(6, 6 + count * 16, 16)
                    }
                    self.assertIn((width, height), sizes)

    def test_runtime_installs_approved_derivatives_at_the_profile_asset_paths(self) -> None:
        dockerfile = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
        entrypoint = (ROOT / "docker" / "kuranea-entrypoint.sh").read_text(encoding="utf-8")
        sync_script = ROOT / "docker" / "sync-ordenowa-brand-assets.php"
        profile_defaults = (ROOT / "modules" / "kuraneabusinessprofile" / "src" / "Domain" / "ProfileDefaults.php").read_text(encoding="utf-8")
        self.assertIn("assets/brand/ordenowa/web_assets/", dockerfile)
        self.assertIn("assets/brand/ordenowa/official_originals/", dockerfile)
        self.assertIn("sync-ordenowa-brand-assets.php", entrypoint)
        self.assertTrue(sync_script.is_file(), "Docker must install the integrity checked official asset set")
        self.assertIn("1ce6b0a015ed6748ef904cdff095ff0f38ab72c9c51fe189c33d19dc797f23fd", profile_defaults)
        self.assertIn("c357fde8a2942e5ed0483b78d3c1a1a134163a7e5197a80072f30f75b90d72f2", profile_defaults)
        self.assertIn("eae5c30405dcd420f03929a3a5fc882d94e057f75e26cf0a564aa7d5cbab3ea8", profile_defaults)

    def test_bundled_derivatives_do_not_collide_with_admin_upload_outputs(self) -> None:
        sync_script = (ROOT / "docker" / "sync-ordenowa-brand-assets.php").read_text(encoding="utf-8")
        processor = (ROOT / "modules" / "kuraneabusinessprofile" / "src" / "Infrastructure" / "BrandAssetProcessor.php").read_text(encoding="utf-8")
        self.assertIn("official-header-desktop.png", sync_script)
        self.assertIn("official-email-logo.png", sync_script)
        self.assertIn("'header_desktop' => ['filename' => 'header-desktop.png'", processor)
        self.assertIn("'email_logo' => ['filename' => 'email-logo.png'", processor)

    def test_runtime_brand_writers_preserve_kuranea_source_images(self) -> None:
        expected = {
            "kuranea-logo.png": "ae54c1ae9042cbef7de8c0a81a9d8d9e819f060b90ee2d46841a88f8f498de69",
            "kuranea-favicon.png": "abdcf6dc3145733b62f4732dfeeb38894356dcbebea8566570e796a6fdee7755",
            "kuranea-pwa-icon.png": "aef584f457e88097178a3280141f84046d71b5e7f63d843a4df378ed639d29d0",
        }
        legacy = ROOT / "assets" / "brand" / "source"
        for name, expected_hash in expected.items():
            with self.subTest(source=name):
                self.assertEqual(expected_hash, hashlib.sha256((legacy / name).read_bytes()).hexdigest())

        seed_script = (ROOT / "docker" / "sync-ordenowa-brand-assets.php").read_text(encoding="utf-8")
        upload_processor = (
            ROOT
            / "modules"
            / "kuraneabusinessprofile"
            / "src"
            / "Infrastructure"
            / "BrandAssetProcessor.php"
        ).read_text(encoding="utf-8")

        self.assertIn("$relativePath = 'img/ordenowa/versions/' . $sourceHash . '/' . $targetFilename;", seed_script)
        self.assertIn("installImmutable($webRoot . '/' . $relativePath", seed_script)
        self.assertIn("installImmutable($privateRoot . '/' . $relativePath", seed_script)
        self.assertIn("$privateRelative = 'source/' . $slot . '/' . $sourceHash . '.' . $extension;", upload_processor)
        self.assertIn("$privatePath = rtrim($privateRoot, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR . $privateRelative;", upload_processor)
        self.assertIn("$versionRoot = rtrim($webRoot, DIRECTORY_SEPARATOR) . '/img/ordenowa/versions/' . $sourceHash;", upload_processor)
        self.assertIn("self::writeImmutable($privatePath, $bytes, $sourceHash, 0600);", upload_processor)
        self.assertIn("self::writeImmutable($path, $output, hash('sha256', $output), 0644);", upload_processor)
        self.assertEqual(
            ["$privateRoot . '/' . $relativePath", "$webRoot . '/' . $relativePath", "$accessFile"],
            re.findall(r"(?m)^\s*installImmutable\(([^,]+),", seed_script),
            "runtime seeding writes must stay under the ORDENOWA private root or versioned web asset root",
        )
        self.assertEqual(
            ["$privatePath", "$path", "$path"],
            re.findall(r"self::writeImmutable\(([^,]+),", upload_processor),
            "uploads may write only their private original, private access file, and versioned derivative paths",
        )
        self.assertIn("$accessFile = $privateRoot . '/.htaccess';", seed_script)
        self.assertIn("if (!is_string($existingHash) || !hash_equals($expectedHash, $existingHash))", seed_script)
        self.assertIn("if (hash_file('sha256', $path) !== $expectedHash)", upload_processor)

        for writer_name, writer in (("seed script", seed_script), ("upload processor", upload_processor)):
            with self.subTest(writer=writer_name):
                self.assertNotIn("assets/brand/source", writer)
                for filename in expected:
                    self.assertNotIn(filename, writer)


if __name__ == "__main__":
    unittest.main()
