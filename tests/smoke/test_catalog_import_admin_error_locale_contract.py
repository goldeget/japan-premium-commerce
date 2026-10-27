from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "modules/kuraneacatalog/controllers/admin/AdminKuraneaCatalogReviewController.php"


class CatalogImportAdminErrorLocaleContractTests(unittest.TestCase):
    def test_imported_draft_error_boundary_preserves_korean_and_hides_english_domain_errors(self) -> None:
        controller = CONTROLLER.read_text(encoding="utf-8")
        draft = controller.split("private function processImportedDraft(", 1)[1].split(
            "private function validateImportMutation(", 1
        )[0]
        invalid_input = draft.split("} catch (\\InvalidArgumentException $exception) {", 1)[1].split(
            "} catch (Throwable)", 1
        )[0]

        self.assertIn("$message = trim($exception->getMessage());", invalid_input)
        self.assertIn("preg_match('/[가-힣]/u', $message) === 1", invalid_input)
        self.assertIn("? $message", invalid_input)
        self.assertIn("비활성 상품 초안을 저장하지 못했습니다.", invalid_input)


if __name__ == "__main__":
    unittest.main()
