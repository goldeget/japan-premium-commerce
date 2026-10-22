"""Contracts for blocking publication of unsaved brand/profile form data."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "modules/kuraneabusinessprofile/controllers/admin/AdminBusinessProfileController.php"
FORM = ROOT / "modules/kuraneabusinessprofile/src/Admin/AdminProfileForm.php"


class BrandPublishGuardContractTests(unittest.TestCase):
    def test_publish_rejects_unsaved_fields_or_selected_uploads_before_service_call(self) -> None:
        controller = CONTROLLER.read_text(encoding="utf-8")
        publish = controller.split("if (Tools::isSubmit('submitOrdenowaPublish'))", 1)[1].split(
            "if (Tools::isSubmit('submitOrdenowaApproveSeller')", 1
        )[0]

        guard = publish.index("hasUnsavedChanges")
        service_publish = publish.index("$service->publish(")
        self.assertIn("hasPendingBrandUpload", publish)
        self.assertLess(guard, service_publish)
        self.assertIn("저장되지 않은 변경사항", publish)
        self.assertIn("초안 저장", publish)

    def test_unsaved_change_comparison_uses_the_form_allowlist(self) -> None:
        form = FORM.read_text(encoding="utf-8")
        self.assertIn("public static function hasUnsavedChanges(array $current, array $submitted): bool", form)
        self.assertIn("return self::apply($current, $submitted) !== $current;", form)


if __name__ == "__main__":
    unittest.main()
