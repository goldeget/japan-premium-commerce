"""Contracts for uploaded brand-image compositing and admin previews."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class BrandAssetDisplayContractTests(unittest.TestCase):
    def test_admin_rejects_oversized_upload_before_reading_file_bytes(self) -> None:
        controller = (ROOT / "modules/kuraneabusinessprofile/controllers/admin/AdminBusinessProfileController.php").read_text(encoding="utf-8")
        upload = controller.split("private function applyUploadedBrandAssets", 1)[1]
        self.assertIn("$temporarySize = filesize($temporaryPath);", upload)
        self.assertIn("$temporarySize > BrandAssetProcessor::MAX_BYTES", upload)
        self.assertIn("if ($temporarySize === false)", upload)
        size_check = upload.index("$temporarySize = filesize($temporaryPath);")
        size_limit = upload.index("$temporarySize > BrandAssetProcessor::MAX_BYTES")
        file_read = upload.index("file_get_contents($temporaryPath)")

        self.assertLess(size_check, size_limit)
        self.assertLess(size_limit, file_read)

    def test_uploaded_og_derivative_is_composited_onto_opaque_white(self) -> None:
        processor = (ROOT / "modules/kuraneabusinessprofile/src/Infrastructure/BrandAssetProcessor.php").read_text(encoding="utf-8")
        png_bytes = processor.split("private static function pngBytes", 1)[1].split("private static function icoFromPng", 1)[0]

        self.assertIn("imagealphablending($canvas, $white);", png_bytes)
        self.assertIn("imagecolorallocate($canvas, 255, 255, 255)", png_bytes)
        self.assertIn("'opaque_white_background' => true", processor)

    def test_draft_preview_includes_admin_login_derivative(self) -> None:
        form = (ROOT / "modules/kuraneabusinessprofile/src/Admin/AdminProfileForm.php").read_text(encoding="utf-8")
        preview = form.split("public static function renderPreview", 1)[1].split("private static function renderField", 1)[0]

        self.assertIn("'admin_login' => '관리자 로그인 로고'", preview)


if __name__ == "__main__":
    unittest.main()
