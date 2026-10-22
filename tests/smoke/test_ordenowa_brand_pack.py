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
LEGACY_WEBROOT_ARCHIVE = ROOT / "assets" / "brand" / "legacy-kuranea-webroot-archive"
LEGACY_WEBROOT_SHA256 = {
    "themes/kuranea/assets/img/brand/apple-touch-icon.png": "b7cc027940312212e2286f73bed947fb1d779da5eabb7bafdb7c4ecb22aece16",
    "themes/kuranea/assets/img/brand/favicon-16x16.png": "ac48fbd542b5b73804e843099d8a1c15ea4a8d8f6d853cd4da4fef5cf73b9df2",
    "themes/kuranea/assets/img/brand/favicon-32x32.png": "be8dbd1753cb7ea4cd868719d4b43bd24b881a8b91b4eb2464c942aeadff7316",
    "themes/kuranea/assets/img/brand/favicon.ico": "c970b09739475c82b74cf38922613579fe4ec1c6c12e91c31cbbe438cd9b10c5",
    "themes/kuranea/assets/img/brand/kuranea-logo-desktop.png": "ebb48eae7847c80f9618e7ba785889cc81b26fbbf3294b27591d2c44154954e1",
    "themes/kuranea/assets/img/brand/kuranea-logo-desktop.webp": "ad560064bd33ab50a08630d0f33c58d0bbec25cb44ee440c3497f411c87a7649",
    "themes/kuranea/assets/img/brand/kuranea-logo-light.png": "7067a06d739b3408058b54fcd6b983738d46c09c8cc4fd7d77844528e713c572",
    "themes/kuranea/assets/img/brand/kuranea-logo-light.webp": "77f9d962148018195dbc50f55d5e2d6d86135772284ae64e80f7c2943b0c2387",
    "themes/kuranea/assets/img/brand/kuranea-logo-mobile.png": "8d2c7bd0a8094c2e063980b93479cfbb6dddcbf03527207ba928f64d2633d006",
    "themes/kuranea/assets/img/brand/kuranea-logo-mobile.webp": "2f350c1a8d0c9e1be193851efdb67883544590f3dc56ebc2b56ad7527fb30cb1",
    "themes/kuranea/assets/img/brand/og-brand.png": "2ffd9bd643dce65389547762120df0420020a9c4162d31204cf0398a595585ce",
    "themes/kuranea/assets/img/brand/pwa-192x192.png": "99abcce8626721b278493929a36d7e2435ff229b4761245d2fcf588847fcbb8c",
    "themes/kuranea/assets/img/brand/pwa-512x512.png": "58ecda279cf4f6b9ad7c4ca522869bf601d23d1d5282a1bee8c6edc46a5838aa",
    "themes/kuranea/assets/img/brand/pwa-maskable-512x512.png": "7abde140ea39ec7e903745297cf1a429585153cf4f80d0423efb99f5d64d27e5",
    "modules/kuraneabackoffice/views/img/kuranea-logo.png": "ae54c1ae9042cbef7de8c0a81a9d8d9e819f060b90ee2d46841a88f8f498de69",
}


class OrdenowaBrandPackTests(unittest.TestCase):
    def test_legacy_kuranea_webroot_assets_are_archived_byte_for_byte(self) -> None:
        expected_sums = [
            f"{expected_hash}  {relative_path}"
            for relative_path, expected_hash in sorted(LEGACY_WEBROOT_SHA256.items())
        ]
        sums_file = LEGACY_WEBROOT_ARCHIVE / "SHA256SUMS.txt"
        self.assertEqual(expected_sums, sums_file.read_text(encoding="utf-8").splitlines())

        for public_relative_path, expected_hash in LEGACY_WEBROOT_SHA256.items():
            with self.subTest(public_path=public_relative_path):
                self.assertFalse((ROOT / public_relative_path).exists(), "legacy asset remains under the public webroot")
                archived = LEGACY_WEBROOT_ARCHIVE / public_relative_path
                self.assertTrue(archived.is_file(), f"legacy asset was not moved into the archive: {public_relative_path}")
                self.assertEqual(expected_hash, hashlib.sha256(archived.read_bytes()).hexdigest())

    def test_legacy_asset_generator_does_not_write_into_public_theme_assets(self) -> None:
        generator = (ROOT / "assets" / "brand" / "generate_assets.py").read_text(encoding="utf-8")
        self.assertNotIn("THEME_BRAND", generator)
        self.assertNotIn("themes/kuranea/assets/img/brand", generator)

    def test_legacy_webroot_archive_is_excluded_from_docker_build_context(self) -> None:
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("assets/brand/legacy-kuranea-webroot-archive/", dockerignore)
        self.assertNotIn("legacy-kuranea-webroot-archive", dockerfile)

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
